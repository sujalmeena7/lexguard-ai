from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    policy_text: str

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    time.sleep(2) # Simulate processing
    return {
        "analysis_id": str(uuid.uuid4()),
        "compliance_score": 42,
        "verdict": "HIGH RISK",
        "summary": "The submitted document contains several clauses that appear to be in direct violation of the DPDP Act 2023, particularly regarding indefinite data retention and lack of specific consent mechanisms.",
        "total_clauses_flagged": 4,
        "flagged_clauses": [
            {
                "clause_id": "§ Ret. 1",
                "risk_level": "High",
                "dpdp_section": "DPDP §12 Data Retention",
                "clause_excerpt": "We may retain your data indefinitely, even after your account is closed.",
                "issue": "Data retention must be limited to the duration necessary for the specified purpose.",
                "suggested_fix": "Amend to state that data will be deleted after the fulfillment of the purpose or withdrawal of consent."
            },
            {
                "clause_id": "§ Cons. 4",
                "risk_level": "High",
                "dpdp_section": "DPDP §6 Consent",
                "clause_excerpt": "By using this service, you are deemed to have given your consent to all current and future uses.",
                "issue": "Deemed consent for future unspecified uses is not valid under the DPDP Act.",
                "suggested_fix": "Implement granular, affirmative consent for specific processing activities."
            }
        ],
        "checklist": [],
        "created_at": "2026-04-22T18:00:00Z"
    }

@app.post("/api/unlock")
async def unlock(req: dict):
    return {
        "analysis_id": req.get("analysis_id"),
        "compliance_score": 42,
        "verdict": "HIGH RISK",
        "summary": "Full report unlocked.",
        "total_clauses_flagged": 4,
        "flagged_clauses": [], # Mock full list
        "checklist": [
            {"focus_area": "Consent", "status": "Non-Compliant", "note": "Missing granular consent."},
            {"focus_area": "Notice", "status": "Partial", "note": "Notice is provided but lacks details."},
            {"focus_area": "Data Minimization", "status": "Compliant", "note": "Data collection is relevant."}
        ],
        "created_at": "2026-04-22T18:00:00Z"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
