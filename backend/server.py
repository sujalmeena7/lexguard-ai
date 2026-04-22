from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
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
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Groq client
GROQ_API_KEY = os.environ['GROQ_API_KEY']
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
groq_client = AsyncGroq(api_key=GROQ_API_KEY)

app = FastAPI()
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
    risk_level: str  # High | Medium | Low
    dpdp_section: str
    clause_excerpt: str
    issue: str
    suggested_fix: str


class ChecklistItem(BaseModel):
    focus_area: str
    status: str  # Compliant | Partial | Non-Compliant | Not Addressed
    note: str


class AnalysisResult(BaseModel):
    analysis_id: str
    compliance_score: int
    verdict: str  # LOW RISK | MODERATE RISK | HIGH RISK
    summary: str
    total_clauses_flagged: int
    flagged_clauses: List[FlaggedClause]
    checklist: List[ChecklistItem]
    created_at: str


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


# ====================== Routes ======================

@api_router.get("/")
async def root():
    return {"service": "LexGuard AI", "status": "ok"}


@api_router.post("/analyze", response_model=AnalysisResult)
async def analyze_policy(req: AnalyzeRequest):
    """Analyze privacy policy against DPDP Act 2023. Returns PREVIEW (2 clauses visible)."""
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
        "policy_text": req.policy_text[:5000],  # store truncated for auditability
    }

    # Persist full analysis for email-gate unlock later
    await db.analyses.insert_one({**result})

    # Return PREVIEW: only first 2 flagged clauses
    preview = AnalysisResult(
        analysis_id=analysis_id,
        compliance_score=result["compliance_score"],
        verdict=result["verdict"],
        summary=result["summary"],
        total_clauses_flagged=len(flagged),
        flagged_clauses=[FlaggedClause(**c) for c in flagged[:2]],
        checklist=[],  # checklist is part of full report
        created_at=created_at,
    )
    return preview


@api_router.post("/unlock", response_model=AnalysisResult)
async def unlock_full_report(req: UnlockRequest):
    """Capture email → store in leads collection → return FULL analysis (all clauses + checklist)."""
    doc = await db.analyses.find_one({"analysis_id": req.analysis_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Analysis not found. Please re-run analysis.")

    # Store lead
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
    """Simple stat for admin."""
    count = await db.leads.count_documents({})
    return {"total_leads": count}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
