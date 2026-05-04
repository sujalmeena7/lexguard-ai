"""
LexGuard AI — FastAPI Backend Template
Production-ready API with SSE streaming for real-time document analysis.
"""

import asyncio
import json
import random
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


# ── Models ────────────────────────────────────────────────────────────

class AnalysisStatus(BaseModel):
    stage: str
    message: str
    progress: int = Field(ge=0, le=100)


class Clause(BaseModel):
    id: str
    text: str
    riskLevel: str  # "low" | "medium" | "high" | "critical"
    section: Optional[str] = None
    recommendation: Optional[str] = None


class AnalysisResult(BaseModel):
    overallScore: int = Field(ge=0, le=100)
    riskBreakdown: Dict[str, int]
    clauses: List[Clause]
    summary: str
    complianceFlags: List[str]


class AnalysisResponse(BaseModel):
    status: str
    result: Optional[AnalysisResult] = None
    processing_time_ms: Optional[int] = None


# ── Mock Data ───────────────────────────────────────────────────────────

MOCK_CLAUSES = [
    {
        "id": "c1",
        "text": "We may share your personal data with trusted partners for marketing purposes without obtaining explicit consent.",
        "riskLevel": "critical",
        "section": "Section 4.2 — Third-Party Disclosure",
        "recommendation": "Replace with explicit opt-in consent language per DPDP Section 6.",
    },
    {
        "id": "c2",
        "text": "Data may be transferred to servers located outside India for processing and storage.",
        "riskLevel": "high",
        "section": "Section 7.1 — Data Localization",
        "recommendation": "Add explicit notice of cross-border transfer and adequacy safeguards per DPDP Section 16.",
    },
    {
        "id": "c3",
        "text": "We retain user data for as long as necessary to provide our services.",
        "riskLevel": "high",
        "section": "Section 5.3 — Data Retention",
        "recommendation": "Define specific retention periods per data category. Implement auto-deletion.",
    },
    {
        "id": "c4",
        "text": "Users can request access to their data by contacting our support team.",
        "riskLevel": "medium",
        "section": "Section 8.2 — Data Principal Rights",
        "recommendation": "Provide self-service portal for DPDP rights. Response within 30 days.",
    },
    {
        "id": "c5",
        "text": "In case of a data breach, we will notify affected users as soon as reasonably possible.",
        "riskLevel": "medium",
        "section": "Section 9.1 — Breach Notification",
        "recommendation": "Mandate 72-hour notification to Data Protection Board.",
    },
]


# ── App ───────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 LexGuard AI backend starting...")
    yield
    print("🛑 LexGuard AI backend shutting down...")


app = FastAPI(
    title="LexGuard AI API",
    description="Enterprise DPDP Compliance Auditing API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "lexguard-ai", "timestamp": datetime.utcnow().isoformat()}


# ── Sync Analysis ─────────────────────────────────────────────────────

@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_document(file: UploadFile = File(...)):
    """
    Upload a PDF/DOCX and receive a compliance analysis.
    This is the synchronous version — blocks until analysis is complete.
    """
    start = time.time()

    # Validate file type
    allowed = {"application/pdf", "text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    content_type = file.content_type or ""
    if not any(ct in content_type for ct in allowed):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}")

    # Simulate processing delay
    await asyncio.sleep(2.5)

    score = random.randint(45, 85)
    result = AnalysisResult(
        overallScore=score,
        riskBreakdown={
            "critical": 1 if score < 60 else 0,
            "high": 2 if score < 70 else 1,
            "medium": 3 if score < 75 else 2,
            "low": 5 if score > 70 else 3,
        },
        clauses=[Clause(**c) for c in MOCK_CLAUSES],
        summary=(
            "The document contains several high-risk clauses regarding third-party data sharing "
            "and inadequate consent mechanisms. While basic security measures are mentioned, the "
            "lack of explicit data retention limits and cross-border transfer safeguards raises "
            "significant DPDP compliance concerns."
        ),
        complianceFlags=[
            "Consent Mechanism",
            "Data Retention",
            "Cross-Border Transfer",
            "Third-Party Sharing",
            "User Rights",
        ],
    )

    return AnalysisResponse(
        status="complete",
        result=result,
        processing_time_ms=int((time.time() - start) * 1000),
    )


# ── SSE Streaming Analysis ────────────────────────────────────────────

async def analysis_stream() -> AsyncGenerator[str, None]:
    """
    Server-Sent Events generator that simulates real-time analysis progress.
    Yields JSON-encoded status updates until the final result is ready.
    """
    stages = [
        ("uploading", "Uploading document...", 10),
        ("parsing", "Parsing legal structure...", 30),
        ("analyzing", "Running AI risk analysis...", 55),
        ("scoring", "Calculating compliance score...", 80),
        ("complete", "Audit complete", 100),
    ]

    score = random.randint(45, 85)
    result = AnalysisResult(
        overallScore=score,
        riskBreakdown={
            "critical": 1 if score < 60 else 0,
            "high": 2 if score < 70 else 1,
            "medium": 3 if score < 75 else 2,
            "low": 5 if score > 70 else 3,
        },
        clauses=[Clause(**c) for c in MOCK_CLAUSES],
        summary=(
            "The document contains several high-risk clauses regarding third-party data sharing "
            "and inadequate consent mechanisms. While basic security measures are mentioned, the "
            "lack of explicit data retention limits and cross-border transfer safeguards raises "
            "significant DPDP compliance concerns."
        ),
        complianceFlags=[
            "Consent Mechanism",
            "Data Retention",
            "Cross-Border Transfer",
            "Third-Party Sharing",
            "User Rights",
        ],
    )

    for stage, message, progress in stages:
        payload = {"status": {"stage": stage, "message": message, "progress": progress}}
        if stage == "complete":
            payload["result"] = result.model_dump()
        yield f"data: {json.dumps(payload)}\n\n"
        await asyncio.sleep(1.2)  # Simulate per-stage latency


@app.post("/api/analyze/stream")
async def analyze_document_stream():
    """
    Upload a PDF/DOCX and receive real-time SSE updates as the AI analyzes it.
    Connect with an EventSource on the frontend for live progress bars.
    """
    return StreamingResponse(
        analysis_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Config ────────────────────────────────────────────────────────────

@app.get("/api/config")
async def public_config():
    """Public configuration required by the frontend widget."""
    return {
        "supabase_url": "https://your-project.supabase.co",
        "supabase_anon_key": "eyJ...",
        "version": "1.0.0",
    }


# ── Main ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
