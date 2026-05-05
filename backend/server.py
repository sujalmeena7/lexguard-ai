from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends, Header, UploadFile, File, Form
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
import re
import json
import logging
import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import Dict, List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import asyncio
import hmac
import secrets
from google import genai
from google.genai import types as genai_types
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
# clauses. The full deep audit lives in the dashboard's two-layer
# pipeline (Flash triage → Pro deep audit on flagged clauses only).
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', '')
if not ADMIN_TOKEN:
    logging.critical("ADMIN_TOKEN env var is NOT set — admin endpoints are DISABLED. Set ADMIN_TOKEN before deploying.")
if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY environment variable is required but not set.")

genai_client = genai.Client(api_key=GOOGLE_API_KEY)

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
# In-memory fallback used only when MongoDB is unavailable. NOT safe for
# multi-worker / multi-replica deployments — a code generated on worker A
# will not be visible to worker B. The MongoDB-backed path below is the
# authoritative store; this dict only exists so single-process dev works
# when Mongo is offline.
_auth_handoff_store: Dict[str, Dict[str, str]] = {}


def _auth_handoff_collection_available() -> bool:
    """True when we have a real MongoDB connection (not the _NullDB stub)."""
    return not isinstance(db, _NullDB)


async def _store_auth_handoff(handoff_code: str, payload: Dict[str, str]) -> None:
    """Persist an auth handoff. Uses Mongo when available so it survives
    across workers/replicas; falls back to the in-memory dict only when
    MongoDB is offline (single-process dev mode)."""
    if _auth_handoff_collection_available():
        doc = {"_id": handoff_code, **payload}
        try:
            await db.auth_handoffs.insert_one(doc)
            return
        except Exception as exc:
            logger.warning(f"Auth handoff Mongo write failed; using in-memory fallback: {exc}")
    _auth_handoff_store[handoff_code] = payload


async def _consume_auth_handoff(handoff_code: str) -> Optional[Dict[str, str]]:
    """Atomically fetch + delete a handoff payload (single-use)."""
    if _auth_handoff_collection_available():
        try:
            doc = await db.auth_handoffs.find_one_and_delete({"_id": handoff_code})
            if doc:
                doc.pop("_id", None)
                # Strip the Mongo TTL helper field before returning to caller
                doc.pop("expires_dt", None)
                return doc
        except Exception as exc:
            logger.warning(f"Auth handoff Mongo read failed; trying in-memory fallback: {exc}")
    return _auth_handoff_store.pop(handoff_code, None)


def _cleanup_expired_handoffs() -> None:
    """Best-effort sweep of the in-memory fallback. The Mongo TTL index
    handles expiry automatically for the persistent path."""
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Replaces deprecated @app.on_event startup/shutdown handlers."""
    try:
        await db.analyses.create_index("analysis_id", unique=True)
        await db.analyses.create_index("created_at")
        await db.leads.create_index("email")
        await db.leads.create_index("lead_id", unique=True)
        await db.leads.create_index("created_at")
        await db.leads.create_index("analysis_id")
        # TTL index expires handoff codes automatically once `expires_dt` passes,
        # so abandoned codes are cleaned up even without a sweeper.
        await db.auth_handoffs.create_index("expires_dt", expireAfterSeconds=0)
        logger.info("MongoDB indexes created/verified")
    except Exception as e:
        logger.error(f"Index creation failed: {e}")
    try:
        yield
    finally:
        if client is not None:
            client.close()


app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security headers middleware ──
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Prevent MIME-type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Enable browser XSS filter
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Enforce HTTPS (1 year, include subdomains)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Restrict referrer leakage
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Basic CSP — restrict script sources
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
    return response

# ── Request logging for suspicious patterns ──
_SUSPICIOUS_EXACT = {"/.env", "/.git", "/wp-admin", "/wp-login.php", "/phpmyadmin"}
_SUSPICIOUS_PREFIXES = ("/wp-", "/phpmy", "/.env", "/.git")
@app.middleware("http")
async def log_suspicious_requests(request: Request, call_next):
    path = request.url.path.lower()
    if path.startswith("/api/"):
        return await call_next(request)
    if path in _SUSPICIOUS_EXACT or any(path.startswith(p) for p in _SUSPICIOUS_PREFIXES):
        logger.warning(f"Suspicious request: {request.method} {request.url.path} from IP={_client_ip(request)}")
    return await call_next(request)

@app.get("/")
async def health_check():
    return {"service": "LexGuard AI", "status": "ok", "version": "1.0.0"}

api_router = APIRouter(prefix="/api")

# ====================== Models ======================

class AnalyzeRequest(BaseModel):
    policy_text: str = Field(..., min_length=50, max_length=25000)


class UnlockRequest(BaseModel):
    analysis_id: str = Field(..., min_length=1, max_length=64)
    email: EmailStr
    name: Optional[str] = Field(None, max_length=100)
    company: Optional[str] = Field(None, max_length=100)


class HandoffExchangeRequest(BaseModel):
    handoff_code: str = Field(..., min_length=1, max_length=128)


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


class RoadmapRequest(BaseModel):
    policy_text: str = Field(..., min_length=50, max_length=25000)
    analysis_id: Optional[str] = None  # Link to a prior analysis if available


class RoadmapGap(BaseModel):
    gap_id: str
    gap_description: str
    immediate_action: str
    golden_clause: str
    operational_change: str
    dpdp_section: str
    enforcement_status: str  # "active" | "upcoming"


class JargonAlert(BaseModel):
    term: str
    plain_language: str
    context: str


class MultilingualReadiness(BaseModel):
    status: str  # "Ready" | "Partially Ready" | "Not Ready"
    rationale: str


class PrivacyUXScorecard(BaseModel):
    readability_score: int
    readability_grade: str
    jargon_alerts: List[JargonAlert]
    multilingual_readiness: MultilingualReadiness


class ExecutiveSummaryItem(BaseModel):
    violation: str
    remediation_effort: str
    business_impact: str
    fix_priority: str


class RoadmapResult(BaseModel):
    roadmap_id: str
    remediation_roadmap: List[RoadmapGap]
    privacy_ux_scorecard: PrivacyUXScorecard
    executive_summary: List[ExecutiveSummaryItem]
    overall_risk_rating: str
    total_gaps_found: int
    generated_at: str
    analysis_id: Optional[str] = None


# ====================== Groq Prompt ======================

SYSTEM_PROMPT = """### SYSTEM_PROMPT: DPDP ZERO-TRUST AUDITOR
You are a deterministic Legal Auditor. You MUST follow these layers:

1. PII SCAN: Identify Aadhaar, Phone, and Email patterns in the document. Do NOT include raw PII in your output. If PII is present, note it briefly in the summary. In clause_excerpt fields, replace any detected PII with redacted placeholders (e.g., [AADHAAR], [PHONE], [EMAIL], [NAME]).

2. STATUTORY AUDIT: Every finding MUST cite a valid DPDP Act 2023 §Section(Sub-section). Explain the legal logic connecting the text to the Act in the issue field. If you are unsure of the exact section, state "Requires manual legal review" instead of guessing.

3. HALLUCINATION CHECK: Cross-reference your citations. The DPDP Act 2023 does NOT have a Section 99. If a citation is not explicitly in the 2023 Act, flag it as "General Regulatory Risk."

Your job is to:
- Assign a compliance score (0-100) based on adherence to the DPDP Act 2023.
- Identify flagged clauses with risk level, exact DPDP section/sub-section, excerpt, issue (with legal rationale), and suggested fix.
- Evaluate against 6 DPDP focus areas: Consent, Notice, Purpose Limitation, Data Minimization, Data Principal Rights, Breach Notification.

### FORMATTING CONSTRAINTS
- NO ALL-CAPS: Do not use uppercase for emphasis or prose.
- CASE SENSITIVITY: Use Title Case for Verdicts (e.g., "High Risk", "Low Risk").
- OUTPUT: Valid JSON matching the defined schema.

Score guidance:
- 80-100: Low Risk (mostly compliant, minor gaps)
- 50-79: Moderate Risk (meaningful gaps requiring attention)
- 0-49: High Risk (major violations / missing critical DPDP obligations)

You MUST respond with ONLY a valid JSON object, no markdown fences, no prose. Use this exact schema:

{
  "compliance_score": <integer 0-100>,
  "verdict": "<Low Risk | Moderate Risk | High Risk>",
  "summary": "<2-3 sentence board-ready summary>",
  "flagged_clauses": [
    {
      "clause_id": "<short identifier like '§ 4.1' or 'Clause 3'>",
      "risk_level": "<High | Medium | Low>",
      "dpdp_section": "<Exact DPDP Act 2023 citation, e.g. 'DPDP §6(1) Consent' or 'DPDP §8(6) Breach Notification'>",
      "clause_excerpt": "<short excerpt from the user's policy (<=200 chars)>",
      "issue": "<what's wrong, with legal rationale connecting text to the cited DPDP section. If unsure, write 'Requires manual legal review'>",
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

Return at minimum 4 flagged_clauses if any risks exist, up to 8. All 6 checklist items are mandatory.
Be decisive, specific, cite exact DPDP sections, and never fabricate citations."""


# ====================== Admin auth ======================

def require_admin(x_admin_token: Optional[str] = Header(None)):
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled — ADMIN_TOKEN not configured")
    if not hmac.compare_digest(x_admin_token or "", ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


# ====================== Routes ======================

@api_router.get("/config")
async def get_config():
    """Return Supabase public config for frontend initialization.
    The anon key is a public key protected by RLS — safe to expose."""
    return {
        "supabase_url": SUPABASE_URL or "",
        "supabase_anon_key": SUPABASE_ANON_KEY or "",
    }


@api_router.get("/")
async def root():
    return {"service": "LexGuard AI", "status": "ok"}


class HandoffCreateRequest(BaseModel):
    refresh_token: Optional[str] = Field(None, max_length=2048)


@api_router.post("/auth/handoff")
async def create_auth_handoff(
    user: dict = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    body: Optional[HandoffCreateRequest] = None,
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required (Bearer token missing)")

    access_token = authorization.split(" ", 1)[1].strip()
    if not access_token:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    _cleanup_expired_handoffs()
    handoff_code = secrets.token_urlsafe(32)
    expires_dt = datetime.now(timezone.utc) + timedelta(seconds=AUTH_HANDOFF_TTL_SECONDS)
    payload = {
        "access_token": access_token,
        "refresh_token": (body.refresh_token if body else None) or "",
        "user_id": user["id"],
        "expires_at": expires_dt.isoformat(),
        # Stored as a real datetime so the Mongo TTL index can expire it.
        "expires_dt": expires_dt,
    }
    await _store_auth_handoff(handoff_code, payload)
    return {"handoff_code": handoff_code, "expires_in": AUTH_HANDOFF_TTL_SECONDS}


@api_router.post("/auth/handoff/exchange")
@limiter.limit("10/minute")
async def exchange_auth_handoff(request: Request, req: HandoffExchangeRequest):
    handoff_code = req.handoff_code.strip()
    if not handoff_code:
        raise HTTPException(status_code=400, detail="handoff_code is required")

    _cleanup_expired_handoffs()
    payload = await _consume_auth_handoff(handoff_code)
    if not payload:
        raise HTTPException(status_code=404, detail="Invalid or expired handoff code")

    now_iso = datetime.now(timezone.utc).isoformat()
    if payload.get("expires_at", "") <= now_iso:
        raise HTTPException(status_code=410, detail="Handoff code expired")

    access_token = payload.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=404, detail="Invalid handoff payload")
    return {
        "access_token": access_token,
        "refresh_token": payload.get("refresh_token", ""),
    }


# ── Text normalization (module-level so every endpoint can reuse) ──
def _redact_pii(text: str) -> str:
    """Redact common Indian PII patterns from text as a backend safety net."""
    if not text or not isinstance(text, str):
        return text or ""
    text = re.sub(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', '[AADHAAR]', text)
    text = re.sub(r'\b(?:\+91[-\s]?)?[6-9]\d{9}\b', '[PHONE]', text)
    text = re.sub(r'[\w.-]+@[\w.-]+\.\w+', '[EMAIL]', text)
    return text

def _normalize_text(text: str) -> str:
    """Convert ALL-CAPS strings to sentence case; leave mixed-case text alone.
    Protected terms (e.g., DPDP, Aadhaar, PII) retain their correct casing.
    Also fixes excessive uppercase even when some lowercase is mixed in."""
    if not text or not isinstance(text, str):
        return text or ""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return text
    upper_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
    if upper_ratio > 0.5:
        text = text.lower()
        sentences = re.split(r'([.!?]\s+)', text)
        result = []
        for i, s in enumerate(sentences):
            if i % 2 == 0 and s:
                s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
            result.append(s)
        text = ''.join(result)
        text = re.sub(r'(?<=\n)([a-z])', lambda m: m.group(1).upper(), text)
        protected = [
            ("aadhaar", "Aadhaar"),
            ("dpdp", "DPDP"),
            ("pii", "PII"),
            ("kyc", "KYC"),
            ("gdpr", "GDPR"),
            ("hipaa", "HIPAA"),
            ("india", "India"),
            ("indian", "Indian"),
            ("ai", "AI"),
            ("api", "API"),
            ("dpdp act", "DPDP Act"),
            ("i", "I"),
        ]
        for lower, proper in protected:
            text = re.sub(rf'\b{re.escape(lower)}\b', proper, text, flags=re.IGNORECASE)
    return text

def _normalize_verdict(v: str) -> str:
    return {"LOW RISK": "Low Risk", "MODERATE RISK": "Moderate Risk",
            "HIGH RISK": "High Risk", "CRITICAL RISK": "High Risk"}.get(v, _normalize_text(v))

def _normalize_risk(v: str) -> str:
    return {"HIGH": "High", "MEDIUM": "Medium", "LOW": "Low",
            "CRITICAL": "High"}.get(v, _normalize_text(v))

def _normalize_status(v: str) -> str:
    return {"COMPLIANT": "Compliant", "NON-COMPLIANT": "Non-Compliant",
            "NOT ADDRESSED": "Not Addressed", "PARTIAL": "Partial"}.get(v, _normalize_text(v))

def _normalize_audit_data(data: dict) -> dict:
    """Recursively normalize text case and redact PII from model output."""
    data["verdict"] = _normalize_verdict(data.get("verdict", ""))
    data["summary"] = _normalize_text(data.get("summary", ""))
    for fc in data.get("flagged_clauses", []) or []:
        fc["risk_level"] = _normalize_risk(fc.get("risk_level", ""))
        fc["issue"] = _normalize_text(fc.get("issue", ""))
        fc["suggested_fix"] = _normalize_text(fc.get("suggested_fix", ""))
        fc["clause_excerpt"] = _redact_pii(_normalize_text(fc.get("clause_excerpt", "")))
        fc["dpdp_section"] = fc.get("dpdp_section", "")
        fc["clause_id"] = fc.get("clause_id", "")
    for item in data.get("checklist", []) or []:
        item["status"] = _normalize_status(item.get("status", ""))
        item["note"] = _normalize_text(item.get("note", ""))
        item["focus_area"] = item.get("focus_area", "")
    return data


def _extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    """Extract text from PDF or plain-text files."""
    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            import io
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            extracted = "\n".join(text_parts).strip()
            if len(extracted) < 50:
                raise ValueError("PDF text extraction returned too little content; file may be image-based.")
            return extracted
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            raise HTTPException(status_code=400, detail=f"Could not extract text from PDF: {str(e)[:120]}")
    else:
        # Plain text (txt, docx not supported here — frontend should warn)
        try:
            text = file_bytes.decode("utf-8")
            if len(text.strip()) < 50:
                raise ValueError("File content too short (minimum 50 characters).")
            return text
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="File is not valid UTF-8 text. Please upload a .txt or .pdf file.")


async def _execute_audit(policy_text: str, user: dict) -> AnalysisResult:
    """Core audit logic shared by JSON and file-upload endpoints."""

    def _extract_json(text: str) -> dict:
        """Robustly extract JSON from model output."""
        import re
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        cleaned = re.sub(r'```(?:json)?', '', text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
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
        response = await genai_client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=2048,
                response_mime_type="application/json",
            )
        )
        return response.text

    async def get_groq_completion(text: str) -> str:
        completion = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Audit this document against DPDP Act 2023:\n\n---\n{text}\n---"},
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
            for token in ("quota", "429", "rate limit", "rate_limit", "exceeded", "resource_exhausted", "resource exhausted")
        )

    raw = None
    used_provider = "gemini"
    try:
        raw = await asyncio.wait_for(get_gemini_completion(policy_text), timeout=45.0)
        logger.info(f"Gemini raw response (first 500 chars): {raw[:500]}")
        data = _extract_json(raw)
        _normalize_audit_data(data)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON after retries: {e}\nRaw: {raw[:1000] if raw else 'N/A'}")
        raise HTTPException(status_code=502, detail="Model returned invalid response. Please retry.")
    except asyncio.TimeoutError:
        logger.warning(f"Gemini audit exceeded 45s timeout; falling back to Groq {GROQ_MODEL}")
        if groq_client is not None:
            try:
                raw = await get_groq_completion(policy_text)
                logger.info(f"Groq fallback raw response (first 500 chars): {raw[:500]}")
                data = _extract_json(raw)
                _normalize_audit_data(data)
                used_provider = f"groq:{GROQ_MODEL}"
            except json.JSONDecodeError as je:
                logger.error(f"Groq fallback returned invalid JSON: {je}\nRaw: {raw[:1000] if raw else 'N/A'}")
                raise HTTPException(status_code=502, detail="Fallback model returned invalid response. Please retry.")
            except Exception as ge:
                logger.error(f"Groq fallback also failed: {ge}")
                raise HTTPException(status_code=503, detail="All AI providers are unavailable right now. Please retry in a minute.")
        else:
            raise HTTPException(status_code=504, detail="Audit timed out and no fallback is available.")
    except Exception as e:
        gemini_err_str = str(e)
        if groq_client is not None:
            logger.warning(f"Gemini failed ({gemini_err_str[:120]}); falling back to Groq {GROQ_MODEL}")
            try:
                raw = await get_groq_completion(policy_text)
                logger.info(f"Groq fallback raw response (first 500 chars): {raw[:500]}")
                data = _extract_json(raw)
                _normalize_audit_data(data)
                used_provider = f"groq:{GROQ_MODEL}"
            except json.JSONDecodeError as je:
                logger.error(f"Groq fallback returned invalid JSON: {je}\nRaw: {raw[:1000] if raw else 'N/A'}")
                raise HTTPException(status_code=502, detail="Fallback model returned invalid response. Please retry.")
            except Exception as ge:
                logger.error(f"Groq fallback also failed: {ge}")
                raise HTTPException(status_code=503, detail="All AI providers are unavailable right now. Please retry in a minute.")
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

    try:
        await db.analyses.insert_one({**result, "user_id": user["id"], "user_email": user["email"]})
    except Exception as db_err:
        logger.warning(f"Database insertion failed (is MongoDB running?): {db_err}")

    return AnalysisResult(
        analysis_id=analysis_id,
        compliance_score=result["compliance_score"],
        verdict=result["verdict"],
        summary=result["summary"],
        total_clauses_flagged=len(flagged),
        flagged_clauses=[FlaggedClause(**c) for c in flagged[:2]],
        checklist=[],
        created_at=created_at,
    )


@api_router.post("/analyze", response_model=AnalysisResult)
@limiter.limit("5/minute;50/day")
async def analyze_policy(
    request: Request,
    req: AnalyzeRequest,
    user: dict = Depends(get_current_user_optional),
):
    """Analyze privacy policy against DPDP Act 2023 (JSON endpoint)."""
    return await _execute_audit(req.policy_text, user)


@api_router.post("/analyze/upload", response_model=AnalysisResult)
@limiter.limit("5/minute;50/day")
async def analyze_upload(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user_optional),
):
    """Analyze privacy policy from uploaded PDF or text file."""
    contents = await file.read()
    policy_text = _extract_text_from_file(contents, file.filename or "upload")
    return await _execute_audit(policy_text, user)

@api_router.get("/audits")
@limiter.limit("30/minute")
async def get_user_audits(request: Request, user: dict = Depends(get_current_user)):
    """Fetch all past audits securely isolated to the authenticated user."""
    try:
        cursor = db.analyses.find({"user_id": user["id"]}, {"_id": 0}).sort("created_at", -1)
        audits = await cursor.to_list(length=100)
        # Normalize old DB entries that may have ALL-CAPS text
        for a in audits:
            _normalize_audit_data(a)
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

    # Normalize in case old DB entries have ALL-CAPS text
    _normalize_audit_data(doc)

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
@limiter.limit("30/minute")
async def leads_count(request: Request, _: bool = Depends(require_admin)):
    count = await db.leads.count_documents({})
    return {"total_leads": count}


# ====================== Admin routes ======================

@api_router.post("/admin/login")
@limiter.limit("5/minute")
async def admin_login(request: Request, payload: dict):
    """Validate admin token. Rate limited to prevent brute force."""
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled — ADMIN_TOKEN not configured")
    token = (payload or {}).get("token", "")
    if not hmac.compare_digest(token, ADMIN_TOKEN):
        logger.warning(f"Admin login failed from IP={_client_ip(request)}")
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
@limiter.limit("10/minute")
async def admin_leads_csv(request: Request, token: str = ""):
    """Export all leads as CSV. Auth via ?token=... query param (so the browser can open the URL directly).
    Rate-limited per IP so a leaked token cannot be used for unbounded exfiltration."""
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin endpoints disabled — ADMIN_TOKEN not configured")
    if not hmac.compare_digest(token, ADMIN_TOKEN):
        logger.warning(f"Admin CSV export auth failed from IP={_client_ip(request)}")
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


# ====================== Privacy Architect Roadmap ======================

_CURRENT_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_DPDP_DEADLINE = "2027-05-31"

PRIVACY_ARCHITECT_PROMPT = f"""### ROLE
You are a Senior Privacy Architect and Legal Strategist. Your goal is to
transform a compliance audit into an actionable business roadmap.

### CONTEXT
- Current Date: {_CURRENT_DATE}
- DPDP Rules 2025 full compliance deadline: {_DPDP_DEADLINE}
- Rules that are currently "active" should be treated as immediately
  enforceable. Rules with enforcement dates after {_CURRENT_DATE} should
  be labelled as "upcoming" in your output.

### STEP 1: REMEDIATION ROADMAP (THE FIX)
For every compliance gap identified in the document, provide:
1. IMMEDIATE ACTION: A single, non-technical step the business must take
   today (e.g., "Appoint a Data Protection Officer").
2. REPLACEMENT CLAUSE (Golden Clause): A legally vetted, DPDP-compliant
   paragraph that can replace the offending text. For consent gaps
   (Section 6), ensure placeholders for Consent Managers are included.
3. OPERATIONAL CHANGE: Describe one backend process change required.
   For "High Risk" gaps, specifically mandate a 72-hour breach notification
   clock to the DPB and affected individuals.

### STEP 2: PRIVACY UX SCORECARD (THE USER EXPERIENCE)
Evaluate the document's transparency and accessibility for the average
Indian consumer (aligning with the SARAL initiative: Simple, Accessible,
Rational, Action-oriented, Lawful):
1. READABILITY SCORE: Rate the text (0-100) using the Flesch-Kincaid scale.
2. JARGON ALERT: Identify 3 legal terms that are too complex and suggest
   "Plain Language" alternatives for SARAL compliance.
3. MULTILINGUAL READINESS: Check if the notice structure allows for easy
   translation into the 22 scheduled Indian languages as per DPDP requirements.
   Rate as "Ready", "Partially Ready", or "Not Ready" with a rationale.

### STEP 3: EXECUTIVE SUMMARY TABLE
Return a table (as a JSON array) with columns: violation, remediation_effort
(Low/Medium/High), business_impact (one sentence), fix_priority
(P0 - Immediate / P1 - This Quarter / P2 - Next Quarter / P3 - Long-term).

### OUTPUT FORMAT
Respond with ONLY a valid JSON object matching this schema:
{{{{
  "remediation_roadmap": [
    {{{{
      "gap_id": "<GAP-1>",
      "gap_description": "<what is non-compliant>",
      "immediate_action": "<single non-technical step>",
      "golden_clause": "<full replacement paragraph>",
      "operational_change": "<backend process change>",
      "dpdp_section": "<cited DPDP section>",
      "enforcement_status": "active" | "upcoming"
    }}}}
  ],
  "privacy_ux_scorecard": {{{{
    "readability_score": <integer 0-100>,
    "readability_grade": "<e.g. College Level>",
    "jargon_alerts": [
      {{{{
        "term": "<complex term>",
        "plain_language": "<simple alternative>",
        "context": "<where it appears>"
      }}}}
    ],
    "multilingual_readiness": {{{{
      "status": "Ready" | "Partially Ready" | "Not Ready",
      "rationale": "<brief explanation>"
    }}}}
  }}}},
  "executive_summary": [
    {{{{
      "violation": "<description>",
      "remediation_effort": "Low" | "Medium" | "High",
      "business_impact": "<one sentence>",
      "fix_priority": "P0 - Immediate" | "P1 - This Quarter" | "P2 - Next Quarter" | "P3 - Long-term"
    }}}}
  ],
  "overall_risk_rating": "Critical" | "High" | "Moderate" | "Low",
  "total_gaps_found": <integer>,
  "generated_at": "{_CURRENT_DATE}"
}}}}
"""


@api_router.post("/roadmap", response_model=RoadmapResult)
@limiter.limit("3/minute;20/day")
async def generate_roadmap(
    request: Request,
    req: RoadmapRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a Privacy Architect roadmap from policy text.

    This is a premium, authenticated endpoint that produces an actionable
    business roadmap with golden clauses, readability scoring, and a
    prioritised executive summary.
    """

    def _extract_json(text: str) -> dict:
        import re
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        cleaned = re.sub(r'```(?:json)?', '', text).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        try:
            start = text.find('{')
            end = text.rfind('}')
            if start != -1 and end != -1:
                return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
        raise json.JSONDecodeError("Failed to find valid JSON in model output", text, 0)

    def _is_quota_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(
            token in msg
            for token in ("quota", "429", "rate limit", "exceeded", "resource_exhausted")
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def get_gemini_roadmap(text: str):
        prompt = f"{PRIVACY_ARCHITECT_PROMPT}\n\n### INPUT DOCUMENT\n---\n{text}\n---"
        response = await genai_client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=4096,
                response_mime_type="application/json",
            )
        )
        return response.text

    async def get_groq_roadmap(text: str) -> str:
        completion = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": PRIVACY_ARCHITECT_PROMPT},
                {
                    "role": "user",
                    "content": f"Generate a Privacy Architect roadmap for this document:\n\n---\n{text}\n---",
                },
            ],
            temperature=0,
            max_tokens=4096,
            response_format={"type": "json_object"},
        )
        return completion.choices[0].message.content or ""

    raw = None
    used_provider = "gemini"
    try:
        raw = await asyncio.wait_for(get_gemini_roadmap(req.policy_text), timeout=60.0)
        logger.info(f"Gemini roadmap response (first 500 chars): {raw[:500]}")
        data = _extract_json(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON for roadmap: {e}")
        raise HTTPException(status_code=502, detail="Model returned invalid response. Please retry.")
    except asyncio.TimeoutError:
        logger.warning("Gemini roadmap exceeded 60s timeout; falling back to Groq")
        if groq_client is not None:
            try:
                raw = await get_groq_roadmap(req.policy_text)
                data = _extract_json(raw)
                used_provider = f"groq:{GROQ_MODEL}"
            except Exception as ge:
                logger.error(f"Groq roadmap fallback failed: {ge}")
                raise HTTPException(status_code=503, detail="All AI providers unavailable.")
        else:
            raise HTTPException(status_code=504, detail="Roadmap generation timed out.")
    except Exception as e:
        if groq_client is not None and _is_quota_error(e):
            logger.warning(f"Gemini quota error on roadmap; falling back to Groq")
            try:
                raw = await get_groq_roadmap(req.policy_text)
                data = _extract_json(raw)
                used_provider = f"groq:{GROQ_MODEL}"
            except Exception as ge:
                logger.error(f"Groq roadmap fallback failed: {ge}")
                raise HTTPException(status_code=503, detail="All AI providers unavailable.")
        else:
            logger.error(f"Gemini roadmap error: {e}")
            raise HTTPException(status_code=502, detail=f"Roadmap generation failed: {str(e)[:120]}")

    logger.info(f"Roadmap served by provider={used_provider}")

    roadmap_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Build validated result
    remediation = data.get("remediation_roadmap", []) or []
    scorecard_raw = data.get("privacy_ux_scorecard", {}) or {}
    exec_summary = data.get("executive_summary", []) or []

    # Ensure nested structures have defaults
    ml_readiness = scorecard_raw.get("multilingual_readiness", {})
    if not isinstance(ml_readiness, dict):
        ml_readiness = {"status": "Not Ready", "rationale": "Could not assess."}

    scorecard = PrivacyUXScorecard(
        readability_score=int(scorecard_raw.get("readability_score", 0)),
        readability_grade=scorecard_raw.get("readability_grade", "Unknown"),
        jargon_alerts=[
            JargonAlert(**ja) for ja in (scorecard_raw.get("jargon_alerts", []) or [])
        ],
        multilingual_readiness=MultilingualReadiness(**ml_readiness),
    )

    result = RoadmapResult(
        roadmap_id=roadmap_id,
        remediation_roadmap=[RoadmapGap(**g) for g in remediation],
        privacy_ux_scorecard=scorecard,
        executive_summary=[ExecutiveSummaryItem(**e) for e in exec_summary],
        overall_risk_rating=data.get("overall_risk_rating", "Moderate"),
        total_gaps_found=data.get("total_gaps_found", len(remediation)),
        generated_at=created_at,
        analysis_id=req.analysis_id,
    )

    # Persist to MongoDB
    try:
        await db.roadmaps.insert_one({
            **result.model_dump(),
            "user_id": user["id"],
            "user_email": user.get("email"),
            "provider": used_provider,
        })
    except Exception as db_err:
        logger.warning(f"Roadmap DB insertion failed: {db_err}")

    return result


def _normalize_roadmap_data(data: dict) -> dict:
    """Normalize text case in roadmap entries (back-compat for old ALL-CAPS data)."""
    if not isinstance(data, dict):
        return data
    for key in ("overall_risk_rating", "generated_at", "roadmap_id"):
        if key in data:
            continue  # skip non-text fields
    data["overall_risk_rating"] = _normalize_text(data.get("overall_risk_rating", ""))
    for gap in data.get("remediation_roadmap", []) or []:
        for field in ("gap_description", "immediate_action", "golden_clause", "operational_change", "dpdp_section"):
            if field in gap:
                gap[field] = _normalize_text(gap[field])
    for item in data.get("executive_summary", []) or []:
        for field in ("violation", "remediation_effort", "business_impact", "fix_priority"):
            if field in item:
                item[field] = _normalize_text(item[field])
    scorecard = data.get("privacy_ux_scorecard", {})
    if isinstance(scorecard, dict):
        scorecard["readability_grade"] = _normalize_text(scorecard.get("readability_grade", ""))
        for ja in scorecard.get("jargon_alerts", []) or []:
            for field in ("term", "plain_language", "context"):
                if field in ja:
                    ja[field] = _normalize_text(ja[field])
        mr = scorecard.get("multilingual_readiness", {})
        if isinstance(mr, dict):
            mr["status"] = _normalize_text(mr.get("status", ""))
            mr["rationale"] = _normalize_text(mr.get("rationale", ""))
    return data


@api_router.get("/roadmaps")
@limiter.limit("30/minute")
async def get_user_roadmaps(request: Request, user: dict = Depends(get_current_user)):
    """Fetch all past roadmaps for the authenticated user."""
    try:
        cursor = db.roadmaps.find({"user_id": user["id"]}, {"_id": 0}).sort("generated_at", -1)
        roadmaps = await cursor.to_list(length=50)
        for r in roadmaps:
            _normalize_roadmap_data(r)
        return roadmaps
    except Exception as e:
        logger.warning(f"Failed to fetch roadmaps: {e}")
        return []


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

# Optional regex for matching ephemeral preview deployments (e.g. Vercel).
# Defaults to None so the explicit allow-list is enforced unless the operator
# opts in via env (e.g. CORS_ORIGIN_REGEX="https://([a-z0-9-]+\\.)*vercel\\.app$").
cors_origin_regex = os.environ.get("CORS_ORIGIN_REGEX") or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token"],
)

