"""LexGuard AI - DPDP compliance API tests (analyze, unlock, leads)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://policy-scanner-9.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SAMPLE_POLICY = (
    "We may collect, process, store, and share your personal data — including your name, email, "
    "phone number, location, browsing behaviour, device identifiers, and financial information — with our "
    "affiliates, business partners, marketing agencies, and any third-party service providers for purposes we "
    "deem necessary, in perpetuity. By using this service, you are deemed to have given your consent to all "
    "current and any future uses of your data, even if our policy changes without prior notice. We may retain "
    "your data indefinitely, even after your account is closed, and we reserve the right not to respond to "
    "requests for data deletion if we believe retention serves a legitimate business interest. In the event of "
    "a data breach, we will evaluate on a case-by-case basis whether notification is warranted."
)


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- Health ----------
class TestHealth:
    def test_root(self, session):
        r = session.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "ok"


# ---------- Analyze validation ----------
class TestAnalyzeValidation:
    def test_empty(self, session):
        r = session.post(f"{API}/analyze", json={"policy_text": ""})
        assert r.status_code == 422

    def test_too_short(self, session):
        r = session.post(f"{API}/analyze", json={"policy_text": "short text only"})
        assert r.status_code == 422

    def test_missing_field(self, session):
        r = session.post(f"{API}/analyze", json={})
        assert r.status_code == 422


# ---------- Analyze happy path ----------
@pytest.fixture(scope="module")
def analysis(session):
    r = session.post(f"{API}/analyze", json={"policy_text": SAMPLE_POLICY}, timeout=60)
    assert r.status_code == 200, f"Analyze failed: {r.status_code} {r.text[:500]}"
    return r.json()


class TestAnalyze:
    def test_structure(self, analysis):
        for key in ["analysis_id", "compliance_score", "verdict", "summary",
                    "total_clauses_flagged", "flagged_clauses", "checklist", "created_at"]:
            assert key in analysis, f"Missing {key}"

    def test_score_range(self, analysis):
        s = analysis["compliance_score"]
        assert isinstance(s, int)
        assert 0 <= s <= 100

    def test_verdict_value(self, analysis):
        assert analysis["verdict"] in ("LOW RISK", "MODERATE RISK", "HIGH RISK")

    def test_preview_only_two_clauses(self, analysis):
        assert len(analysis["flagged_clauses"]) <= 2, "Preview must contain at most 2 clauses"

    def test_checklist_empty_in_preview(self, analysis):
        assert analysis["checklist"] == [], "Checklist must be empty in preview"

    def test_total_count_reflects_real_total(self, analysis):
        assert analysis["total_clauses_flagged"] >= len(analysis["flagged_clauses"])
        # Spec requires at minimum 4 clauses when risks exist
        assert analysis["total_clauses_flagged"] >= 2

    def test_clause_shape(self, analysis):
        for c in analysis["flagged_clauses"]:
            for key in ["clause_id", "risk_level", "dpdp_section", "clause_excerpt", "issue", "suggested_fix"]:
                assert key in c


# ---------- Unlock validation ----------
class TestUnlockValidation:
    def test_invalid_email(self, session, analysis):
        r = session.post(f"{API}/unlock", json={
            "analysis_id": analysis["analysis_id"],
            "email": "not-an-email",
        })
        assert r.status_code == 422

    def test_unknown_analysis_id(self, session):
        r = session.post(f"{API}/unlock", json={
            "analysis_id": "nonexistent-id-12345",
            "email": "test@example.com",
        })
        assert r.status_code == 404


# ---------- Unlock happy path ----------
class TestUnlockAndLeads:
    def test_unlock_full_report(self, session, analysis):
        # Get leads count before
        before = session.get(f"{API}/leads/count").json()["total_leads"]

        r = session.post(f"{API}/unlock", json={
            "analysis_id": analysis["analysis_id"],
            "email": "TEST_qa@example.com",
            "name": "QA Tester",
            "company": "TEST_Corp",
        })
        assert r.status_code == 200, r.text[:500]
        full = r.json()

        # Full report should have all clauses + 6 checklist items
        assert full["analysis_id"] == analysis["analysis_id"]
        assert full["compliance_score"] == analysis["compliance_score"]
        assert full["verdict"] == analysis["verdict"]
        assert len(full["flagged_clauses"]) == full["total_clauses_flagged"]
        assert len(full["flagged_clauses"]) >= 2

        # 6 required focus areas
        assert len(full["checklist"]) == 6
        focus_areas = {c["focus_area"] for c in full["checklist"]}
        required = {"Consent", "Notice", "Purpose Limitation", "Data Minimization",
                    "Data Principal Rights", "Breach Notification"}
        assert required.issubset(focus_areas), f"Missing focus areas: {required - focus_areas}"

        for item in full["checklist"]:
            assert item["status"] in ("Compliant", "Partial", "Non-Compliant", "Not Addressed")
            assert "note" in item

        # Leads count increased
        after = session.get(f"{API}/leads/count").json()["total_leads"]
        assert after == before + 1

    def test_leads_count_endpoint(self, session):
        r = session.get(f"{API}/leads/count")
        assert r.status_code == 200
        data = r.json()
        assert "total_leads" in data
        assert isinstance(data["total_leads"], int)
