from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Header
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from supabase import create_client, Client
import certifi
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import os
import json
import logging
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import asyncio
import secrets
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("lexguard-backend")


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ── MongoDB connection (fully optional — AI works without it) ──
mongo_url = os.environ.get('MONGO_URL', '')
db = None  # Will be set below if connection succeeds
client: Optional[AsyncIOMotorClient] = None

class _NullCollection:
    """Stub that silently no-ops every DB call so the app never crashes."""
    async def insert_one(self, *a, **kw): return None
    async def find_one(self, *a, **kw): return None
    async def update_one(self, *a, **kw): return None
    async def create_index(self, *a, **kw): return None
    async def aggregate(self, *a, **kw): return []
    def find(self, *a, **kw): return self
    def sort(self, *a, **kw): return self
    async def to_list(self, *a, **kw): return []

class _NullDB:
    """Provides attribute access that always returns a _NullCollection."""
    def __getattr__(self, name):
        return _NullCollection()

if mongo_url:
    try:
        # Auto-detect TLS: Atlas (mongodb+srv://) needs TLS; localhost does not
        use_tls = mongo_url.startswith('mongodb+srv://') or 'mongodb.net' in mongo_url
        connect_kwargs = {}
        if use_tls:
            connect_kwargs = dict(tls=True, tlsCAFile=certifi.where())

        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000, **connect_kwargs)
        db = client[os.environ.get('DB_NAME', 'lexguard_db')]
        logging.info(f"MongoDB configured: {mongo_url[:30]}... (TLS={'on' if use_tls else 'off'})")
    except Exception as e:
        logging.warning(f"MongoDB connection failed — running without database: {e}")
        db = _NullDB()
else:
    logging.warning("MONGO_URL not set — running without database (AI features still work)")
    db = _NullDB()

# ── Gemini client ──
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
# Widget endpoint uses Gemini 2.0 Flash by default: ~3-5x faster than Pro and
# accurate enough for a one-shot landing-page summary that only previews 2
# clauses. The full deep audit lives in the Streamlit dashboard's two-layer
# pipeline (Flash triage → Pro deep audit on flagged clauses only).
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'dev-token-local')
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY environment variable is required but not set.")

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

# ── Groq fallback (used when Gemini hits quota/429) ──
# When GROQ_API_KEY is set, /api/analyze automatically retries on Groq
# Llama-3.3-70B if Gemini exhausts its tenacity retries with a quota error.
# Same prompt + JSON schema, sub-second latency on Groq's LPU.
GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')
groq_client = None
if GROQ_API_KEY:
    try:
        from groq import AsyncGroq
        groq_client = AsyncGroq(api_key=GROQ_API_KEY)
        logging.info(f"Groq fallback enabled (model={GROQ_MODEL}).")
    except Exception as exc:
        logging.warning(f"Groq SDK unavailable; fallback disabled: {exc}")
else:
    logging.info("GROQ_API_KEY not set \u2014 Gemini-only mode (no fallback on quota).")

# ── Supabase Auth Guard ──
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY')
supabase_client: Optional[Client] = None

if SUPABASE_URL and SUPABASE_ANON_KEY:
    try:
        supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        logging.info("Supabase client configured for JWT verification")
    except Exception as e:
        logging.error(f"Supabase init failed: {e}")

AUTH_HANDOFF_TTL_SECONDS = int(os.environ.get("AUTH_HANDOFF_TTL_SECONDS", "120"))
_auth_handoff_store: Dict[str, Dict[str, str]] = {}


def _cleanup_expired_handoffs() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    expired_codes = [
        code
        for code, payload in _auth_handoff_store.items()
        if payload.get("expires_at", "") <= now_iso
    ]
    for code in expired_codes:
        _auth_handoff_store.pop(code, None)

ANONYMOUS_USER_PREFIX = "anonymous_"


def _is_anonymous_user(user: dict) -> bool:
    return str(user.get("id", "")).startswith(ANONYMOUS_USER_PREFIX)


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Verify Supabase JWT and return user data. STRICT (401 if missing)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required (Bearer token missing)")

    token = authorization.split(" ")[1]
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Auth service unavailable")

    try:
        res = supabase_client.auth.get_user(token)
        if not res or not res.user:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        return {"id": res.user.id, "email": res.user.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth verification error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user_optional(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    """Optional auth: returns the real user if a valid Bearer token is present,
    otherwise returns a per-IP anonymous sentinel. Used by public lead-gen
    endpoints (/api/analyze, /api/unlock) so the landing-page widget works
    without forcing visitors to sign in. Per-IP rate limits still apply.
    """
    if authorization and authorization.startswith("Bearer ") and supabase_client:
        token = authorization.split(" ", 1)[1].strip()
        if token:
            try:
                res = supabase_client.auth.get_user(token)
                if res and res.user:
                    return {"id": res.user.id, "email": res.user.email}
            except Exception as e:
                # Fall through to anonymous on auth failure—public endpoints
                # should not 401 a visitor whose session merely expired.
                logger.info(f"Optional auth fell back to anonymous: {e}")

    ip = _client_ip(request) if request is not None else "unknown"
    # Hash the IP so we never persist a raw IP in the DB.
    anon_id = ANONYMOUS_USER_PREFIX + hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]
    return {"id": anon_id, "email": None}

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

# ====================== Models ======================

class AnalyzeRequest(BaseModel):
    policy_text: str = Field(..., min_length=50, max_length=25000)


class UnlockRequest(BaseModel):
    analysis_id: str
    email: EmailStr
    name: Optional[str] = None
    company: Optional[str] = None


class HandoffExchangeRequest(BaseModel):
    handoff_code: str


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

Return at minimum 4 flagged_clauses if any risks exist, up to 8. All 6 checklist items are mandatory. Use normal sentence case. Do NOT write responses in ALL CAPS.
Be decisive, specific, and cite DPDP sections where possible."""


# ====================== Admin auth ======================

def require_admin(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


# ====================== Routes ======================

@api_router.get("/")
async def root():
    return {"service": "LexGuard AI", "status": "ok"}


@api_router.post("/auth/handoff")
async def create_auth_handoff(
    user: dict = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required (Bearer token missing)")

    access_token = authorization.split(" ", 1)[1].strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    _cleanup_expired_handoffs()
    handoff_code = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=AUTH_HANDOFF_TTL_SECONDS)).isoformat()
    _auth_handoff_store[handoff_code] = {
        "access_token": access_token,
        "user_id": user["id"],
        "expires_at": expires_at,
    }
    return {"handoff_code": handoff_code, "expires_in": AUTH_HANDOFF_TTL_SECONDS}


@api_router.post("/auth/handoff/exchange")
async def exchange_auth_handoff(req: HandoffExchangeRequest):
    handoff_code = req.handoff_code.strip()
    if not handoff_code:
        raise HTTPException(status_code=400, detail="handoff_code is required")

    _cleanup_expired_handoffs()
    payload = _auth_handoff_store.pop(handoff_code, None)
    if not payload:
        raise HTTPException(status_code=404, detail="Invalid or expired handoff code")

    now_iso = datetime.now(timezone.utc).isoformat()
    if payload.get("expires_at", "") <= now_iso:
        raise HTTPException(status_code=410, detail="Handoff code expired")

    access_token = payload.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=404, detail="Invalid handoff payload")
    return {"access_token": access_token}


@api_router.post("/analyze", response_model=AnalysisResult)
@limiter.limit("5/minute;50/day")
async def analyze_policy(
    request: Request,
    req: AnalyzeRequest,
    user: dict = Depends(get_current_user_optional),
):
    """Analyze privacy policy against DPDP Act 2023.

    Public endpoint: anonymous visitors using the landing-page widget are
    served via a per-IP anonymous user id; logged-in users get their record
    attached to their Supabase user id. Per-IP rate limit (5/min, 50/day)
    bounds abuse from anonymous callers.
    """

    def _extract_json(text: str) -> dict:
        """Robustly extract JSON from model output."""
        import re
        # 1. Try raw JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # 2. Strip markdown fences and try again
        cleaned = re.sub(r'```(?:json)?', '', text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
            
        # 3. Find the first '{' and last '}'
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
            
        raise json.JSONDecodeError("Failed to find valid JSON in model output", text, 0)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def get_gemini_completion(text: str):
        prompt = f"{SYSTEM_PROMPT}\n\nAudit this document against DPDP Act 2023:\n\n---\n{text}\n---"
        response = await model.generate_content_async(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0,
                # Schema is bounded (~6 clauses + 6 checklist items); 2048 is
                # plenty and keeps Flash latency tight (~5-10s end-to-end).
                max_output_tokens=2048,
                response_mime_type="application/json",
            )
        )
        return response.text

    async def get_groq_completion(text: str) -> str:
        """Fallback: ask Groq Llama-3.3-70B for the same JSON schema."""
        completion = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Audit this document against DPDP Act 2023:\n\n---\n{text}\n---",
                },
            ],
            temperature=0,
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content or ""

    def _is_quota_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(
            token in msg
            for token in (
                "quota", "429", "rate limit", "rate_limit",
                "exceeded", "resource_exhausted", "resource exhausted",
            )
        )

    raw = None
    used_provider = "gemini"
    try:
        raw = await asyncio.wait_for(get_gemini_completion(req.policy_text), timeout=3.0)
        logger.info(f"Gemini raw response (first 500 chars): {raw[:500]}")
        data = _extract_json(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON after retries: {e}\nRaw: {raw[:1000] if raw else 'N/A'}")
        raise HTTPException(status_code=502, detail="Model returned invalid response. Please retry.")
    except asyncio.TimeoutError:
        logger.warning(
            f"Gemini audit exceeded 3s timeout; falling back to Groq {GROQ_MODEL}"
        )
        if groq_client is not None:
            try:
                raw = await get_groq_completion(req.policy_text)
                logger.info(f"Groq fallback raw response (first 500 chars): {raw[:500]}")
                data = _extract_json(raw)
                used_provider = f"groq:{GROQ_MODEL}"
            except json.JSONDecodeError as je:
                logger.error(f"Groq fallback returned invalid JSON: {je}\nRaw: {raw[:1000] if raw else 'N/A'}")
                raise HTTPException(status_code=502, detail="Fallback model returned invalid response. Please retry.")
            except Exception as ge:
                logger.error(f"Groq fallback also failed: {ge}")
                raise HTTPException(
                    status_code=503,
                    detail="All AI providers are unavailable right now. Please retry in a minute.",
                )
        else:
            raise HTTPException(status_code=504, detail="Audit timed out and no fallback is available.")
    except Exception as e:
        gemini_err_str = str(e)
        if groq_client is not None and _is_quota_error(e):
            logger.warning(
                f"Gemini quota error after retries; falling back to Groq {GROQ_MODEL}: {gemini_err_str[:200]}"
            )
            try:
                raw = await get_groq_completion(req.policy_text)
                logger.info(f"Groq fallback raw response (first 500 chars): {raw[:500]}")
                data = _extract_json(raw)
                used_provider = f"groq:{GROQ_MODEL}"
            except json.JSONDecodeError as je:
                logger.error(f"Groq fallback returned invalid JSON: {je}\nRaw: {raw[:1000] if raw else 'N/A'}")
                raise HTTPException(status_code=502, detail="Fallback model returned invalid response. Please retry.")
            except Exception as ge:
                logger.error(f"Groq fallback also failed: {ge}")
                raise HTTPException(
                    status_code=503,
                    detail="All AI providers are over their quota right now. Please retry in a minute.",
                )
        else:
            logger.error(f"Gemini error after multiple attempts: {gemini_err_str}")
            raise HTTPException(status_code=502, detail=f"Analysis failed after multiple attempts: {gemini_err_str[:120]}")

    logger.info(f"Analysis served by provider={used_provider}")

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

    # Save to DB (Tied to user_id for IDOR protection)
    try:
        await db.analyses.insert_one({
            **result,
            "user_id": user["id"],
            "user_email": user["email"]
        })
    except Exception as db_err:
        logger.warning(f"Database insertion failed (is MongoDB running?): {db_err}")

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

@api_router.get("/audits")
async def get_user_audits(user: dict = Depends(get_current_user)):
    """Fetch all past audits securely isolated to the authenticated user."""
    try:
        cursor = db.analyses.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
        audits = await cursor.to_list(length=100)
        return audits
    except Exception as e:
        logger.warning(f"Failed to fetch audits: {e}")
        return []


@api_router.post("/unlock", response_model=AnalysisResult)
@limiter.limit("20/minute")
async def unlock_full_report(
    request: Request,
    req: UnlockRequest,
    user: dict = Depends(get_current_user_optional),
):
    """Capture email → store in leads collection → return FULL analysis."""
    # Find in DB or fallback to a dummy if DB is down
    doc = None
    try:
        doc = await db.analyses.find_one({"analysis_id": req.analysis_id}, {"_id": 0})
    except Exception as db_err:
        logger.warning(f"Database lookup failed: {db_err}")

    if not doc:
        # If DB is down, we can't fetch the specific analysis, but we can tell the user why
        raise HTTPException(status_code=404, detail="Analysis not found or Database is offline.")

    # Ownership / IDOR protection.
    # Analyses created anonymously (via the public landing-page widget) are
    # gated only by knowledge of the random analysis_id + the email-capture
    # form below, which is the intended lead-gen contract. Authenticated
    # users still get strict per-user IDOR enforcement.
    doc_owner = doc.get("user_id", "")
    doc_is_anonymous = str(doc_owner).startswith(ANONYMOUS_USER_PREFIX)
    if not doc_is_anonymous and doc_owner != user["id"]:
        logger.warning(
            f"IDOR ATTEMPT: User {user['id']} tried to access analysis "
            f"{req.analysis_id} owned by {doc_owner}"
        )
        raise HTTPException(status_code=403, detail="You do not have permission to access this report.")

    # Store lead
    try:
        await db.leads.insert_one({
            "lead_id": str(uuid.uuid4()),
            "email": req.email,
            "name": req.name,
            "company": req.company,
            "analysis_id": req.analysis_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "hero_try_it_now",
            "user_id": user["id"]
        })
    except Exception as db_err:
        logger.warning(f"Lead storage failed: {db_err}")

    try:
        await db.analyses.update_one(
            {"analysis_id": req.analysis_id},
            {"$set": {"unlocked": True, "unlocked_email": req.email}},
        )
    except Exception as db_err:
        logger.warning(f"Database update failed: {db_err}")

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

# ── CORS: Allow all known frontends (local + production + previews) ──
_DEFAULT_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8501",
    "http://127.0.0.1:8501",
]

# Add any extra origins from env (e.g. your Vercel production URL)
cors_origins = list(_DEFAULT_ORIGINS)
for origin in os.environ.get('CORS_ORIGINS', '').split(','):
    o = origin.strip()
    if o and o not in cors_origins:
        cors_origins.append(o)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    # Allow HTTPS origins for public web/preview deployments.
    allow_origin_regex=r"https://.*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
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
    if client is not None:
        client.close()
