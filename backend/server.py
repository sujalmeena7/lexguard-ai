from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import certifi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import json
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone
from groq import AsyncGroq


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(
    mongo_url, 
    tls=True, 
    tlsCAFile=certifi.where(), 
    tlsAllowInvalidCertificates=True
)
db = client[os.environ['DB_NAME']]

# Groq client
GROQ_API_KEY = os.environ['GROQ_API_KEY']
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'lexguard-admin-2026')
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

# Rate limiter (per client IP, proxy-aware: honors X-Forwarded-For)
def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)

limiter = Limiter(key_func=_client_ip)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/")
async def health_check():
    return {"service": "LexGuard AI", "status": "ok", "version": "1.0.0"}

api_router = APIRouter(prefix="/api")

logger = logging.getLogger(__name__)


# ====================== Models ======================

class AnalyzeRequest(BaseModel):
    policy_text: str = Field(..., min_length=50, max_length=25000)


class UnlockRequest(BaseModel):
    analysis_id: str
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None


class FlaggedClause(BaseModel):
    clause_id: str
    risk_level: str
    dpdp_section: str
    clause_excerpt: str
    issue: str
    suggested_fix: str


class ChecklistItem(BaseModel):
    focus_area: str
    status: str
    note: str


class AnalysisResult(BaseModel):
    analysis_id: str
    compliance_score: int
    verdict: str
    summary: str
    total_clauses_flagged: int
    flagged_clauses: List[FlaggedClause]
    checklist: List[ChecklistItem]
    created_at: str


class Lead(BaseModel):
    lead_id: str
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    analysis_id: str
    created_at: str
    source: str


# ====================== Groq Prompt ======================

SYSTEM_PROMPT = """You are LexGuard AI, a senior legal compliance auditor specializing in India's Digital Personal Data Protection Act 2023 (DPDP Act 2023).

You analyze privacy policies, terms of service, or data-sharing agreements submitted by Indian businesses. Your job is to:
1. Assign a compliance score (0-100) based on adherence to the DPDP Act 2023.
2. Identify flagged clauses with risk level, DPDP section cited, an excerpt from the text, the issue, and a suggested fix.
3. Evaluate the document against 6 DPDP focus areas: Consent, Notice, Purpose Limitation, Data Minimization, Data Principal Rights, Breach Notification.

Score guidance:
- 80-100: LOW RISK (mostly compliant, minor gaps)
- 50-79: MODERATE RISK (meaningful gaps requiring attention)
- 0-49: HIGH RISK (major violations / missing critical DPDP obligations)

You MUST respond with ONLY a valid JSON object, no markdown fences, no prose. Use this exact schema:

{
  "compliance_score": <integer 0-100>,
  "verdict": "<LOW RISK | MODERATE RISK | HIGH RISK>",
  "summary": "<2-3 sentence board-ready summary>",
  "flagged_clauses": [
    {
      "clause_id": "<short identifier like '§ 4.1' or 'Clause 3'>",
      "risk_level": "<High | Medium | Low>",
      "dpdp_section": "<DPDP Act section cited, e.g. 'DPDP §6 Consent' or 'DPDP §8(6) Breach Notification'>",
      "clause_excerpt": "<short excerpt from the user's policy (<=200 chars)>",
      "issue": "<what's wrong, 1-2 sentences>",
      "suggested_fix": "<concrete remediation, 1-2 sentences>"
    }
  ],
  "checklist": [
    {"focus_area": "Consent", "status": "<Compliant | Partial | Non-Compliant | Not Addressed>", "note": "<1 sentence>"},
    {"focus_area": "Notice", "status": "...", "note": "..."},
    {"focus_area": "Purpose Limitation", "status": "...", "note": "..."},
    {"focus_area": "Data Minimization", "status": "...", "note": "..."},
    {"focus_area": "Data Principal Rights", "status": "...", "note": "..."},
    {"focus_area": "Breach Notification", "status": "...", "note": "..."}
  ]
}

Return at minimum 4 flagged_clauses if any risks exist, up to 8. All 6 checklist items are mandatory. Be decisive, specific, and cite DPDP sections where possible."""


# ====================== Admin auth ======================

def require_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


# ====================== Routes ======================

@api_router.get("/")
async def root():
    return {"service": "LexGuard AI", "status": "ok"}


@api_router.post("/analyze", response_model=AnalysisResult)
@limiter.limit("5/minute;30/hour")
async def analyze_policy(request: Request, req: AnalyzeRequest):
    """Analyze privacy policy against DPDP Act 2023. Rate limited: 5/min, 30/hour per IP."""
    try:
        completion = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Audit this document against DPDP Act 2023:\n\n---\n{req.policy_text}\n---"},
            ],
            temperature=0.2,
            max_completion_tokens=2048,
            response_format={"type": "json_object"},
        )
        raw = completion.choices[0].message.content
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Groq returned invalid JSON: {e}")
        raise HTTPException(status_code=502, detail="Model returned invalid response. Please retry.")
    except Exception as e:
        logger.error(f"Groq error: {e}")
        raise HTTPException(status_code=502, detail=f"Analysis failed: {str(e)[:120]}")

    analysis_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    flagged = data.get("flagged_clauses", []) or []
    checklist = data.get("checklist", []) or []

    result = {
        "analysis_id": analysis_id,
        "compliance_score": int(data.get("compliance_score", 0)),
        "verdict": data.get("verdict", "MODERATE RISK"),
        "summary": data.get("summary", ""),
        "total_clauses_flagged": len(flagged),
        "flagged_clauses": flagged,
        "checklist": checklist,
        "created_at": created_at,
        "unlocked": False,
    }

    await db.analyses.insert_one({**result})

    preview = AnalysisResult(
        analysis_id=analysis_id,
        compliance_score=result["compliance_score"],
        verdict=result["verdict"],
        summary=result["summary"],
        total_clauses_flagged=len(flagged),
        flagged_clauses=[FlaggedClause(**c) for c in flagged[:2]],
        checklist=[],
        created_at=created_at,
    )
    return preview


@api_router.post("/unlock", response_model=AnalysisResult)
@limiter.limit("20/minute")
async def unlock_full_report(request: Request, req: UnlockRequest):
    """Capture email → store in leads collection → return FULL analysis."""
    doc = await db.analyses.find_one({"analysis_id": req.analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found. Please re-run analysis.")

    lead = {
        "lead_id": str(uuid.uuid4()),
        "email": req.email,
        "name": req.name,
        "company": req.company,
        "analysis_id": req.analysis_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "hero_try_it_now",
    }
    await db.leads.insert_one(lead)
    await db.analyses.update_one(
        {"analysis_id": req.analysis_id},
        {"$set": {"unlocked": True, "unlocked_email": req.email}},
    )

    return AnalysisResult(
        analysis_id=doc["analysis_id"],
        compliance_score=doc["compliance_score"],
        verdict=doc["verdict"],
        summary=doc["summary"],
        total_clauses_flagged=doc["total_clauses_flagged"],
        flagged_clauses=[FlaggedClause(**c) for c in doc.get("flagged_clauses", [])],
        checklist=[ChecklistItem(**c) for c in doc.get("checklist", [])],
        created_at=doc["created_at"],
    )


@api_router.get("/leads/count")
async def leads_count():
    count = await db.leads.count_documents({})
    return {"total_leads": count}


# ====================== Admin routes ======================

@api_router.post("/admin/login")
@limiter.limit("10/minute")
async def admin_login(request: Request, payload: dict):
    """Validate admin token. Rate limited to prevent brute force."""
    token = (payload or {}).get("token", "")
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {"ok": True}


@api_router.get("/admin/leads", response_model=List[Lead])
async def admin_list_leads(
    _: bool = Depends(require_admin),
    limit: int = 200,
    skip: int = 0,
):
    """List captured leads (most recent first)."""
    cursor = db.leads.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(min(limit, 500))
    leads = await cursor.to_list(length=min(limit, 500))
    return [Lead(**l) for l in leads]


@api_router.get("/admin/stats")
async def admin_stats(_: bool = Depends(require_admin)):
    """Admin dashboard stats."""
    total_leads = await db.leads.count_documents({})
    total_analyses = await db.analyses.count_documents({})
    unlocked_analyses = await db.analyses.count_documents({"unlocked": True})
    # Last 24h
    from datetime import timedelta
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    leads_24h = await db.leads.count_documents({"created_at": {"$gte": since}})
    analyses_24h = await db.analyses.count_documents({"created_at": {"$gte": since}})
    return {
        "total_leads": total_leads,
        "total_analyses": total_analyses,
        "unlocked_analyses": unlocked_analyses,
        "conversion_rate": round((unlocked_analyses / total_analyses * 100), 1) if total_analyses else 0,
        "leads_last_24h": leads_24h,
        "analyses_last_24h": analyses_24h,
    }


@api_router.get("/admin/lead/{lead_id}")
async def admin_lead_detail(lead_id: str, _: bool = Depends(require_admin)):
    """Get a single lead + the audit they unlocked."""
    lead = await db.leads.find_one({"lead_id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    analysis = await db.analyses.find_one({"analysis_id": lead["analysis_id"]}, {"_id": 0})
    return {"lead": lead, "analysis": analysis}


@api_router.get("/admin/leads.csv")
async def admin_leads_csv(token: str = ""):
    """Export all leads as CSV. Auth via ?token=... query param (so the browser can open the URL directly)."""
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")

    import csv
    import io

    async def stream_csv():
        # Header
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "lead_id", "email", "name", "company", "analysis_id",
            "compliance_score", "verdict", "total_clauses_flagged",
            "source", "created_at"
        ])
        yield buf.getvalue()

        # Rows — join with analysis data
        cursor = db.leads.find({}, {"_id": 0}).sort("created_at", -1)
        async for lead in cursor:
            analysis = await db.analyses.find_one(
                {"analysis_id": lead.get("analysis_id")},
                {"_id": 0, "compliance_score": 1, "verdict": 1, "total_clauses_flagged": 1},
            ) or {}
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                lead.get("lead_id", ""),
                lead.get("email", ""),
                lead.get("name", "") or "",
                lead.get("company", "") or "",
                lead.get("analysis_id", ""),
                analysis.get("compliance_score", ""),
                analysis.get("verdict", ""),
                analysis.get("total_clauses_flagged", ""),
                lead.get("source", ""),
                lead.get("created_at", ""),
            ])
            yield buf.getvalue()

    filename = f"lexguard-leads-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.csv"
    return StreamingResponse(
        stream_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


app.include_router(api_router)

cors_origins = os.environ.get('CORS_ORIGINS', '*').split(',')
if "http://localhost:3000" not in cors_origins:
    cors_origins.append("http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@app.on_event("startup")
async def startup_indexes():
    """Create MongoDB indexes for performance at scale."""
    try:
        await db.analyses.create_index("analysis_id", unique=True)
        await db.analyses.create_index("created_at")
        await db.leads.create_index("email")
        await db.leads.create_index("lead_id", unique=True)
        await db.leads.create_index("created_at")
        await db.leads.create_index("analysis_id")
        logger.info("MongoDB indexes created/verified")
    except Exception as e:
        logger.error(f"Index creation failed: {e}")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
