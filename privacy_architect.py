"""
Privacy Architect & Legal Strategist Module
=============================================
Transforms a standard DPDP compliance audit into an actionable business roadmap
with three deliverables:
  1. Remediation Roadmap (Immediate Action + Golden Clause + Operational Change)
  2. Privacy UX Scorecard (Readability + Jargon Alerts + Multilingual Readiness)
  3. Executive Summary Table (Violation × Effort × Impact × Priority)

Designed to run against an existing audit_report.json OR raw document text.
Uses the same Gemini/Groq dual-provider pattern as the core audit engine.
"""

import json
import os
import re
import textwrap
from datetime import datetime, timezone
from typing import Dict, List, Optional

import streamlit as st
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# ── Configuration ─────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Reuse the same model tiers from main.py
DEEP_MODEL = os.environ.get("DEEP_MODEL", "gemini-2.0-pro")
TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL", "gemini-2.0-flash")

# Current DPDP phase context (auto-injected per the engineering tip)
CURRENT_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%d")
DPDP_FULL_COMPLIANCE_DEADLINE = "2027-05-31"


# ── Privacy Architect System Prompt ───────────────────────────────────
PRIVACY_ARCHITECT_PROMPT_STR = textwrap.dedent("""\
    ### ROLE
    You are a Senior Privacy Architect and Legal Strategist. Your goal is to
    transform a compliance audit into an actionable business roadmap.

    ### CONTEXT
    - Current Date: {current_date}
    - DPDP Rules 2025 full compliance deadline: {compliance_deadline}
    - Rules that are currently "active" should be treated as immediately
      enforceable. Rules with enforcement dates after {current_date} should
      be labelled as "upcoming" in your output.

    ### INPUT DOCUMENT
    {document_text}

    ### STEP 1: REMEDIATION ROADMAP (THE FIX)
    For every compliance gap identified in the document, provide:
    1. **IMMEDIATE ACTION**: A single, non-technical step the business must take
       today (e.g., "Appoint a Data Protection Officer").
    2. **REPLACEMENT CLAUSE** (Golden Clause): A legally vetted, DPDP-compliant
       paragraph that can replace the offending text. Wrap it in a clearly
       delimited block. For consent-related gaps (Section 6), ensure the clause
       includes placeholders for **Consent Managers** as per finalized rules.
    3. **OPERATIONAL CHANGE**: Describe one backend process change required.
       For "High Risk" security or breach-related gaps, specifically mandate a
       **72-hour notification clock** to the Data Protection Board (DPB) and
       affected individuals.

    ### STEP 2: PRIVACY UX SCORECARD (THE USER EXPERIENCE)
    Evaluate the document's transparency and accessibility for the average
    Indian consumer (aligning with the **SARAL** initiative: Simple, Accessible,
    Rational, Action-oriented, Lawful):
    1. **READABILITY SCORE**: Rate the text (0-100) using the Flesch-Kincaid
       scale. Provide the exact numeric score.
    2. **JARGON ALERT**: Identify 3 legal terms that are too complex and
       suggest "Plain Language" alternatives. This is critical for SARAL
       compliance (e.g., "Indemnification" → "Protection against loss").
    3. **MULTILINGUAL READINESS**: Check if the notice structure allows for
       easy translation into the 22 scheduled Indian languages as per DPDP
       requirements. Rate as "Ready", "Partially Ready", or "Not Ready"
       with a brief rationale.

    ### STEP 3: EXECUTIVE SUMMARY TABLE
    Return a table (as a JSON array) with these columns:
    - violation: string
    - remediation_effort: "Low" | "Medium" | "High"
    - business_impact: string (one sentence)
    - fix_priority: "P0 - Immediate" | "P1 - This Quarter" | "P2 - Next Quarter" | "P3 - Long-term"

    ### OUTPUT FORMAT
    You MUST respond with ONLY a valid JSON object. No markdown fences, no
    prose outside the JSON. Use this exact schema:

    {{
      "remediation_roadmap": [
        {{
          "gap_id": "<short ID like GAP-1>",
          "gap_description": "<what is non-compliant>",
          "immediate_action": "<single non-technical step>",
          "golden_clause": "<full replacement paragraph>",
          "operational_change": "<backend process change>",
          "dpdp_section": "<cited DPDP section>",
          "enforcement_status": "active" | "upcoming"
        }}
      ],
      "privacy_ux_scorecard": {{
        "readability_score": <integer 0-100>,
        "readability_grade": "<e.g. 'College Level', 'High School', 'Easy'>",
        "jargon_alerts": [
          {{
            "term": "<complex legal term>",
            "plain_language": "<simple alternative>",
            "context": "<where it appears in the document>"
          }}
        ],
        "multilingual_readiness": {{
          "status": "Ready" | "Partially Ready" | "Not Ready",
          "rationale": "<brief explanation>"
        }}
      }},
      "executive_summary": [
        {{
          "violation": "<description>",
          "remediation_effort": "Low" | "Medium" | "High",
          "business_impact": "<one sentence>",
          "fix_priority": "P0 - Immediate" | "P1 - This Quarter" | "P2 - Next Quarter" | "P3 - Long-term"
        }}
      ],
      "overall_risk_rating": "Critical" | "High" | "Moderate" | "Low",
      "total_gaps_found": <integer>,
      "generated_at": "{current_date}"
    }}
    """)


def _extract_roadmap_json(text: str) -> Dict:
    """Extract JSON from raw LLM output, handling markdown fences and unescaped control characters."""
    # 1) Try literal parse
    try:
        return json.loads(text.strip(), strict=False)
    except json.JSONDecodeError:
        pass
    # 2) Strip markdown fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass
    # 3) Find first { to last }
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1], strict=False)
        except json.JSONDecodeError:
            pass
    raise json.JSONDecodeError("Roadmap JSON not found or invalid control chars", text, 0)


def _is_quota_error(exc: Exception) -> bool:
    """Detect Google 429 / RESOURCE_EXHAUSTED errors."""
    s = str(exc).lower()
    return any(k in s for k in ("429", "resource_exhausted", "quota",
                                "rate limit", "exceeded your current quota"))


def _init_groq_sync():
    """Lazy-init sync Groq client."""
    key = None
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        pass
    key = key or os.environ.get("GROQ_API_KEY")
    if key:
        try:
            from groq import Groq
            return Groq(api_key=key)
        except Exception:
            pass
    return None


def generate_privacy_roadmap(
    document_text: str,
    progress_callback=None,
) -> Optional[Dict]:
    """
    Runs the Privacy Architect prompt against the provided document text.
    Returns the structured roadmap dict or None on failure.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    google_key = None
    try:
        google_key = st.secrets.get("GOOGLE_API_KEY")
    except Exception:
        pass
    google_key = google_key or os.environ.get("GOOGLE_API_KEY")
    if not google_key:
        raise RuntimeError("GOOGLE_API_KEY not found in secrets or environment.")

    prompt_text = PRIVACY_ARCHITECT_PROMPT_STR.format(
        current_date=CURRENT_DATE,
        compliance_deadline=DPDP_FULL_COMPLIANCE_DEADLINE,
        document_text=document_text,
    )

    if progress_callback:
        progress_callback("phase", "Generating Privacy Architect roadmap...")

    llm = ChatGoogleGenerativeAI(
        model=DEEP_MODEL, google_api_key=google_key, temperature=0
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _call_llm() -> str:
        try:
            raw = llm.invoke(prompt_text)
            return raw.content if hasattr(raw, "content") else str(raw)
        except Exception as e:
            if _is_quota_error(e):
                groq = _init_groq_sync()
                if groq:
                    groq_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
                    resp = groq.chat.completions.create(
                        model=groq_model,
                        messages=[
                            {"role": "system", "content": "You are a Senior Privacy Architect."},
                            {"role": "user", "content": prompt_text},
                        ],
                        temperature=0,
                    )
                    return resp.choices[0].message.content
            raise

    raw_text = _call_llm()
    roadmap = _extract_roadmap_json(raw_text)

    # Ensure generated_at is set
    roadmap.setdefault("generated_at", CURRENT_DATE)
    roadmap.setdefault("total_gaps_found", len(roadmap.get("remediation_roadmap", [])))

    if progress_callback:
        progress_callback("complete", "Privacy roadmap generated successfully.")

    return roadmap


def generate_roadmap_from_audit(
    audit_results: List[Dict],
    progress_callback=None,
) -> Optional[Dict]:
    """
    Convenience wrapper: takes existing audit results (list of clause records)
    and synthesizes them into a document for the Privacy Architect prompt.
    """
    # Build a synthetic document from audit results
    parts = []
    for record in audit_results:
        clause_text = record.get("clause_text", "")
        audit_result = record.get("audit_result", "")
        status = record.get("status", "")
        parts.append(
            f"[Clause {record.get('clause_id', '?')} | Status: {status}]\n"
            f"Text: {clause_text}\n"
            f"Audit Finding: {audit_result}\n"
        )

    document_text = "\n---\n".join(parts)
    return generate_privacy_roadmap(document_text, progress_callback)


def save_roadmap_json(roadmap: Dict, output_path: str) -> str:
    """Persist the roadmap to disk as JSON."""
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(roadmap, f, indent=2, ensure_ascii=False)
    return output_path
