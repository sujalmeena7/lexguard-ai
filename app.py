import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional

import plotly.graph_objects as go
import streamlit as st

from auth_utils import (
    init_auth_state,
    restore_session_from_token,
    sign_in_with_email,
    sign_out,
    sign_up_with_email,
    reset_password_request,
    update_password,
)
from database import (
    SCHEMA_REFERENCE_SQL,
    delete_user_audit,
    fetch_user_audits,
    save_audit_log,
    save_uploaded_file,
    deduct_user_credit,
    get_or_create_user_profile,
    update_user_premium_status,
    add_user_credits,
    log_security_event,
    check_rate_limit,
)
from main import (
    get_retriever,
    get_user_workspace_retriever,
    index_user_document,
    run_compliance_audit,
)
from report_gen import generate_report


ACCESS_KEY = st.secrets.get("ACCESS_KEY")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DATA_ROOT = os.path.join(BASE_DIR, "data")
logger = logging.getLogger(__name__)


def utc_now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sanitize_user_id(user_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", user_id)


def mask_pii(text: str) -> str:
    """Simple regex to mask emails and phone numbers for extra privacy."""
    if not text:
        return text
    # Mask emails: user@domain.com -> u***@domain.com
    text = re.sub(r"([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*(@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)", r"\1***\2", text)
    # Mask potential phone numbers (simple 10 digit check)
    text = re.sub(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", "[REDACTED PHONE]", text)
    return text


def get_user_workspace_paths(user_id: str) -> Dict[str, str]:
    safe_user_id = sanitize_user_id(user_id)
    user_root = os.path.join(USER_DATA_ROOT, safe_user_id)
    uploads_dir = os.path.join(user_root, "uploads")
    cache_dir = os.path.join(user_root, "cache")

    return {
        "user_root": user_root,
        "uploads_dir": uploads_dir,
        "cache_dir": cache_dir,
        "session_cache": os.path.join(cache_dir, "session_cache.json"),
        "report_pdf": os.path.join(cache_dir, "report.pdf"),
        "audit_json": os.path.join(cache_dir, "audit_report.json"),
    }


def ensure_workspace_dirs(paths: Dict[str, str]) -> None:
    os.makedirs(paths["uploads_dir"], exist_ok=True)
    os.makedirs(paths["cache_dir"], exist_ok=True)


def reset_audit_state() -> None:
    st.session_state.audit_complete = False
    st.session_state.audit_results = None
    st.session_state.pdf_bytes = None
    st.session_state.last_filename = None
    st.session_state.last_source_type = None
    st.session_state.metrics = {
        "total_clauses": 0,
        "high_risk": 0,
        "medium_risk": 0,
        "compliant": 0,
    }


def clear_user_cache(paths: Dict[str, str]) -> None:
    for target in (paths["session_cache"], paths["report_pdf"], paths["audit_json"]):
        if os.path.exists(target):
            try:
                os.remove(target)
            except Exception as exc:
                logger.warning("Failed to remove cache file %s: %s", target, exc)


def load_user_cache(paths: Dict[str, str]) -> None:
    reset_audit_state()

    if not os.path.exists(paths["session_cache"]):
        return

    try:
        with open(paths["session_cache"], "r", encoding="utf-8") as cache_file:
            cache_data = json.load(cache_file)

        st.session_state.audit_complete = cache_data.get("audit_complete", False)
        st.session_state.audit_results = cache_data.get("audit_results", None)
        st.session_state.last_filename = cache_data.get("last_filename", None)
        st.session_state.last_source_type = cache_data.get("last_source_type", None)
        st.session_state.metrics = cache_data.get(
            "metrics",
            {
                "total_clauses": 0,
                "high_risk": 0,
                "medium_risk": 0,
                "compliant": 0,
            },
        )

        cached_pdf_path = cache_data.get("pdf_path")
        if cached_pdf_path and os.path.exists(cached_pdf_path):
            with open(cached_pdf_path, "rb") as pdf_file:
                st.session_state.pdf_bytes = pdf_file.read()
    except Exception:
        reset_audit_state()


def save_user_cache(paths: Dict[str, str]) -> None:
    cache_payload = {
        "audit_complete": st.session_state.audit_complete,
        "audit_results": st.session_state.audit_results,
        "last_filename": st.session_state.last_filename,
        "last_source_type": st.session_state.last_source_type,
        "metrics": st.session_state.metrics,
        "pdf_path": paths["report_pdf"],
    }

    try:
        with open(paths["session_cache"], "w", encoding="utf-8") as cache_file:
            json.dump(cache_payload, cache_file, indent=2)
    except Exception as exc:
        logger.warning("Failed to write session cache to %s: %s", paths["session_cache"], exc)


def ensure_user_session_defaults() -> None:
    defaults = {
        "current_page": "audit",
        "credits": 0,
        "is_premium": False,
        "show_key_input": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if st.session_state.authenticated:
        profile = get_or_create_user_profile(
            str(st.session_state.user_id), str(st.session_state.user_email)
        )
        st.session_state.credits = profile.get("credits", 0)
        st.session_state.is_premium = profile.get("is_premium", False)

    if "audit_complete" not in st.session_state:
        reset_audit_state()


@st.cache_resource(show_spinner="Loading legal knowledge base...")
def load_retriever():
    return get_retriever(ingest=False)


def summarize_results(metrics: Dict[str, int]) -> str:
    return (
        f"Total: {metrics.get('total_clauses', 0)} | "
        f"High Risk: {metrics.get('high_risk', 0)} | "
        f"Medium Risk: {metrics.get('medium_risk', 0)} | "
        f"Compliant: {metrics.get('compliant', 0)}"
    )


def render_auth_controls() -> None:
    pass


def persist_uploaded_input(
    user_id: str,
    workspace_paths: Dict[str, str],
    uploaded_file=None,
    pasted_text: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    ensure_workspace_dirs(workspace_paths)

    if uploaded_file is not None:
        original_name = uploaded_file.name or "uploaded_document"
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", original_name)
        file_name = f"{utc_now_slug()}_{uuid.uuid4().hex[:8]}_{safe_name}"
        output_path = os.path.join(workspace_paths["uploads_dir"], file_name)

        raw_bytes = uploaded_file.getbuffer()
        with open(output_path, "wb") as output_file:
            output_file.write(raw_bytes)

        save_uploaded_file(
            user_id=user_id,
            filename=original_name,
            storage_path=output_path,
            size_bytes=len(raw_bytes),
            mime_type=uploaded_file.type or "application/octet-stream",
        )

        return {
            "path": output_path,
            "source_name": original_name,
            "source_type": "upload",
        }

    if pasted_text is not None and pasted_text.strip():
        file_name = f"{utc_now_slug()}_{uuid.uuid4().hex[:8]}_pasted_clause.txt"
        output_path = os.path.join(workspace_paths["uploads_dir"], file_name)

        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(pasted_text.strip())

        save_uploaded_file(
            user_id=user_id,
            filename="pasted_clause.txt",
            storage_path=output_path,
            size_bytes=len(pasted_text.encode("utf-8")),
            mime_type="text/plain",
        )

        return {
            "path": output_path,
            "source_name": "pasted_clause.txt",
            "source_type": "pasted_text",
        }

    return None


def run_user_audit(
    user_id: str,
    workspace_paths: Dict[str, str],
    source_path: str,
    source_name: str,
    source_type: str,
) -> None:
    if st.session_state.credits <= 0 and not st.session_state.is_premium:
        st.warning("You do not have enough credits to run an audit.")
        return

    if not check_rate_limit("AUDIT_RUN", user_id=user_id, limit=3, window_minutes=10):
        st.warning("Audit rate limit reached. Please wait a few minutes.")
        return

    clear_user_cache(workspace_paths)
    reset_audit_state()
    st.session_state.last_filename = source_name
    st.session_state.last_source_type = source_type

    with st.spinner("Analyzing document against DPDP Act 2023..."):
        retriever = load_retriever()

        indexed_chunks = index_user_document(user_id=user_id, user_doc_path=source_path)
        user_workspace_retriever = get_user_workspace_retriever(user_id=user_id)

        st.markdown("### Real-Time Diagnostics")
        st.caption(f"Indexed {indexed_chunks} user chunks in isolated workspace store.")

        progress_bar = st.progress(0)
        col1, col2, col3, col4 = st.columns(4)
        metric_total = col1.empty()
        metric_high = col2.empty()
        metric_medium = col3.empty()
        metric_compliant = col4.empty()

        metric_total.metric("Total Clauses", 0)
        metric_high.metric("High Risk", 0)
        metric_medium.metric("Medium Risk", 0)
        metric_compliant.metric("Compliant", 0)

        def progress_update(current_step, total_steps, record, is_high_risk_flag):
            metrics = st.session_state.metrics
            metrics["total_clauses"] += 1
            if is_high_risk_flag:
                metrics["high_risk"] += 1
            elif "Medium" in record.get("status", ""):
                metrics["medium_risk"] += 1
            else:
                metrics["compliant"] += 1

            progress_val = current_step / total_steps if total_steps > 0 else 1.0
            progress_bar.progress(progress_val)

            metric_total.metric("Total Clauses", metrics["total_clauses"])
            metric_high.metric("High Risk", metrics["high_risk"])
            metric_medium.metric("Medium Risk", metrics["medium_risk"])
            metric_compliant.metric("Compliant", metrics["compliant"])

        results = run_compliance_audit(
            retriever=retriever,
            user_doc_path=source_path,
            progress_callback=progress_update,
            user_workspace_retriever=user_workspace_retriever,
            report_output_path=workspace_paths["audit_json"],
        )

        if "summary" in results:
            results["summary"] = mask_pii(results["summary"])

        st.session_state.audit_results = results
        st.session_state.audit_complete = True

    if not results:
        st.error("Audit failed. Please verify your input document and try again.")
        return
    st.session_state.credits -= 1

    generated_pdf_path = generate_report(
        report_data=results,
        output_pdf_path=workspace_paths["report_pdf"],
    )
    if generated_pdf_path and os.path.exists(generated_pdf_path):
        with open(generated_pdf_path, "rb") as pdf_file:
            st.session_state.pdf_bytes = pdf_file.read()

    summary = summarize_results(st.session_state.metrics)
    save_audit_log(
        user_id=user_id,
        source_name=source_name,
        source_type=source_type,
        summary=summary,
        findings_json=results,
        metrics_json=st.session_state.metrics,
    )

    # Deduct credit and log event
    deduct_user_credit(user_id)
    log_security_event(
        "AUDIT_RUN",
        user_id=user_id,
        description=f"Ran audit on {source_name}",
        metadata={"source_type": source_type, "total_clauses": st.session_state.metrics["total_clauses"]},
    )

    save_user_cache(workspace_paths)

    st.success(
        f"Audit successful. 1 credit deducted. Remaining balance: {st.session_state.credits}"
    )
    st.rerun()


# Configure Streamlit page
st.set_page_config(
    page_title="LexGuard AI | DPDP Compliance",
    page_icon="L",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Visual style
st.markdown(
    """
<style>
    @import url('https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@800,700,500,400&f[]=satoshi@400,500,700,900&display=swap');

    :root {
        --primary: #002FA7;
        --primary-hover: #0040d9;
        --bg-dark: #09090b;
        --card-bg: rgba(255, 255, 255, 0.03);
        --border: rgba(255, 255, 255, 0.1);
        --zinc-400: #a1a1aa;
    }

    .stApp {
        background-color: var(--bg-dark);
        color: #ffffff;
        font-family: 'Satoshi', sans-serif;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stHeader"] {background: rgba(0,0,0,0); height: 0;}

    [data-testid="stSidebar"] {
        background-color: #0f1115;
        border-right: 1px solid var(--border);
        padding-top: 2rem;
    }

    .stButton > button {
        background-color: transparent;
        color: white;
        border: 1px solid var(--border);
        border-radius: 4px;
        font-weight: 500;
        transition: all 0.2s ease;
        width: 100%;
    }
    .stButton > button:hover {
        border-color: var(--primary);
        color: var(--primary);
        background: rgba(0, 47, 167, 0.05);
    }

    div.stButton > button[kind="primary"] {
        background-color: var(--primary);
        border: none;
        color: white !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: var(--primary-hover);
        color: white !important;
    }

    .lg-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        backdrop-filter: blur(12px);
    }

    [data-testid="stMetricValue"] {
        font-family: 'Cabinet Grotesk', sans-serif;
        font-weight: 800;
        letter-spacing: -0.02em;
    }

    [data-testid="stFileUploader"] {
        background: var(--card-bg);
        border: 1px dashed var(--border);
        border-radius: 12px;
        padding: 20px;
    }

    h1, h2, h3 {
        font-family: 'Cabinet Grotesk', sans-serif;
        font-weight: 800;
        letter-spacing: -0.03em;
    }

    .paywall-box {
        background: linear-gradient(135deg, rgba(0, 47, 167, 0.1) 0%, rgba(0, 20, 80, 0.2) 100%);
        border: 1px solid rgba(0, 47, 167, 0.3);
        padding: 24px;
        border-radius: 12px;
        text-align: center;
        margin: 20px 0;
    }

    .paywall-box h4 {
        color: #ffffff !important;
        margin-bottom: 8px;
    }

    .paywall-box p {
        color: var(--zinc-400) !important;
        font-size: 0.9rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Auth bootstrap and guardrails
init_auth_state()
if not st.session_state.authenticated:
    restore_session_from_token()

render_auth_controls()

if not st.session_state.authenticated:
    st.markdown(
        """
        <div style='padding: 2rem 0;'>
            <h1 style='margin-top: 0;'>LexGuard AI Workspace</h1>
            <p style='color: #a1a1aa; font-size: 1.05rem; max-width: 700px;'>
                Sign in from the sidebar to access your isolated workspace. Your uploaded files,
                audit history, and configuration data are private to your account.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("Authentication required. Main app logic is blocked until sign in succeeds.")
    st.stop()


# User-scoped bootstrap
ensure_user_session_defaults()

current_user_id = str(st.session_state.user_id)
workspace_paths = get_user_workspace_paths(current_user_id)
ensure_workspace_dirs(workspace_paths)

if st.session_state.get("active_user_id") != current_user_id:
    st.session_state.active_user_id = current_user_id
    load_user_cache(workspace_paths)

# Removed trivial admin bypass via query parameter


# Sidebar content for authenticated users
# --- CSS Injection for Sidebar Styling ---
active_page = st.session_state.current_page
active_idx = 1
if active_page == "dashboard":
    active_idx = 1
elif active_page == "audit":
    active_idx = 2
elif active_page == "library":
    active_idx = 3
elif active_page == "settings":
    active_idx = 4
else:
    active_idx = 1

st.markdown(f"""
<style>
    /* Styling the sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {{
        border: none;
        text-align: left;
        justify-content: flex-start;
        padding-left: 20px;
        background: transparent;
        font-size: 1rem;
        color: #a1a1aa;
        border-radius: 4px;
        height: auto;
        padding-top: 10px;
        padding-bottom: 10px;
    }}
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: rgba(255, 255, 255, 0.05);
        color: white;
    }}
    
    /* Highlight the active menu item */
    [data-testid="stSidebar"] .stButton:nth-of-type({active_idx}) > button {{
        background: rgba(96, 165, 250, 0.1) !important;
        border-left: 4px solid #60a5fa !important;
        border-radius: 0px !important;
        color: #60a5fa !important;
        font-weight: 600;
    }}

    /* Position bottom auth container */
    .sidebar-bottom {{
        position: absolute;
        bottom: 20px;
        width: 100%;
        padding: 0 20px;
    }}

    /* Style the sign out button specifically (it's the 5th button in the sidebar) */
    [data-testid="stSidebar"] .stButton:nth-of-type(5) > button {{
        background: rgba(239, 68, 68, 0.1) !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
        color: #ef4444 !important;
        justify-content: center !important;
        padding-left: 0 !important;
        margin-top: 8px;
    }}
    [data-testid="stSidebar"] .stButton:nth-of-type(5) > button:hover {{
        background: rgba(239, 68, 68, 0.2) !important;
    }}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    # Sidebar Header
    st.markdown(
        """
        <div style="padding-bottom: 30px; padding-left: 10px;">
            <h2 style="margin: 0; color: white; display: flex; align-items: center; gap: 12px; font-family: 'Cabinet Grotesk', sans-serif;">
                <span style="color: #60a5fa; font-size: 1.4rem;">⚖️</span> LexGuard AI
            </h2>
            <p style="margin: 0; color: #6b7280; font-size: 0.65rem; letter-spacing: 0.15em; font-weight: 700; margin-left: 36px; margin-top: -2px;">LEGAL INTELLIGENCE</p>
        </div>
        """, unsafe_allow_html=True
    )

    # Navigation Menu
    if st.button("🎛️ Dashboard", use_container_width=True):
        st.session_state.current_page = "dashboard"
    if st.button("📑 Document Audit", use_container_width=True):
        st.session_state.current_page = "audit"
    if st.button("📚 Compliance Library", use_container_width=True):
        st.session_state.current_page = "library"
    if st.button("⚙️ Settings", use_container_width=True):
        st.session_state.current_page = "settings"

    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Auth Controls (at bottom)
    st.markdown("<div style='flex-grow: 1;'></div>", unsafe_allow_html=True)
    st.markdown("---")
    if st.session_state.authenticated:
        # Professional User Profile Card
        credits_pct = (st.session_state.credits / 10.0) * 100
        profile_html = f"""
        <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 16px; margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
                <div style="background: #3b82f6; color: white; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 14px;">
                    {st.session_state.user_email[0].upper() if st.session_state.user_email else 'U'}
                </div>
                <div style="overflow: hidden;">
                    <div style="color: #f1f5f9; font-size: 13px; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                        {st.session_state.user_email}
                    </div>
                    <div style="color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">
                        Enterprise Plan
                    </div>
                </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="color: #94a3b8; font-size: 12px; font-weight: 500;">Audit Credits</span>
                <span style="color: #e2e8f0; font-size: 12px; font-weight: 600;">{st.session_state.credits}/10</span>
            </div>
            <div style="background: rgba(0,0,0,0.3); border-radius: 4px; height: 6px; width: 100%; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #3b82f6, #60a5fa); width: {credits_pct}%; height: 100%; border-radius: 4px;"></div>
            </div>
        </div>
        """
        st.markdown(profile_html, unsafe_allow_html=True)
        
        # We need a custom class for the sign-out button to make it look professional
        if st.button("Sign Out", use_container_width=True, key="sign_out_btn"):
            from auth_utils import sign_out
            sign_out()
            st.rerun()
    else:
        st.markdown("### Secure Access")
        tab_signin, tab_signup = st.tabs(["Sign In", "Sign Up"])
        with tab_signin:
            with st.form("signin_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)
                if submitted:
                    from auth_utils import sign_in_with_email
                    ok, msg = sign_in_with_email(email, password)
                    if ok:
                        st.success("Signed in")
                        st.rerun()
                    else:
                        st.error(msg)
        with tab_signup:
            with st.form("signup_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                conf_password = st.text_input("Confirm", type="password")
                submitted = st.form_submit_button("Create Account", use_container_width=True)
                if submitted:
                    if password != conf_password:
                        st.error("Passwords mismatch")
                    else:
                        from auth_utils import sign_up_with_email
                        ok, msg = sign_up_with_email(email, password)
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)


if st.session_state.current_page == "audit":
    # --- Top Bar RAG Badges ---
    st.markdown(
        """
        <div style="display: flex; gap: 12px; margin-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px; align-items: center;">
            <h2 style="margin: 0; font-family: 'Cabinet Grotesk', sans-serif; font-weight: 800; letter-spacing: -0.5px; margin-right: auto;">WORKSPACE</h2>
            <span style="background: rgba(22, 163, 74, 0.15); color: #4ade80; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; font-family: monospace; border: 1px solid rgba(22, 163, 74, 0.3);">🟢 MODEL: GEMINI 1.5 PRO</span>
            <span style="background: rgba(0, 47, 167, 0.15); color: #60a5fa; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; font-family: monospace; border: 1px solid rgba(0, 47, 167, 0.3);">🧠 RAG: ACTIVE</span>
            <span style="background: rgba(217, 119, 6, 0.15); color: #fbbf24; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; font-family: monospace; border: 1px solid rgba(217, 119, 6, 0.3);">🗂️ CONTEXT: 1M TOKENS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # --- Split Pane Layout ---
    col_left, col_right = st.columns([1.1, 1], gap="large")

    with col_left:
        st.markdown("<h3 style='color: #fff; margin-top:0;'>Document Analyzer</h3>", unsafe_allow_html=True)
        
        if st.session_state.audit_complete and st.session_state.audit_results is not None:
            if st.button("Start New Audit", type="secondary"):
                clear_user_cache(workspace_paths)
                reset_audit_state()
                st.rerun()

            st.success("Audit complete. Results loaded from your workspace cache.")

            metrics = st.session_state.metrics
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Clauses", metrics["total_clauses"])
            c2.metric("High Risk", metrics["high_risk"])
            c3.metric("Medium Risk", metrics["medium_risk"])
            c4.metric("Compliant", metrics["compliant"])

            total = metrics["total_clauses"]
            high_risk = metrics["high_risk"]
            raw_score = (metrics["compliant"] / total) * 100 if total > 0 else 100
            score = min(49.0, raw_score) if high_risk > 0 else raw_score

            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=score,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": "Compliance Health", "font": {"size": 20, "color": "white"}},
                    gauge={
                        "axis": {"range": [0, 100], "tickcolor": "white"},
                        "bar": {"color": "#002FA7"},
                        "bgcolor": "rgba(255,255,255,0.05)",
                        "borderwidth": 2,
                        "bordercolor": "rgba(255,255,255,0.1)",
                        "steps": [
                            {"range": [0, 50], "color": "rgba(185, 28, 28, 0.3)"},
                            {"range": [50, 80], "color": "rgba(180, 83, 9, 0.3)"},
                            {"range": [80, 100], "color": "rgba(22, 101, 52, 0.3)"},
                        ],
                    },
                )
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "white"},
                height=300,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)

            report_data = st.session_state.audit_results
            preview_count = min(3, len(report_data))
            for idx in range(preview_count):
                item = report_data[idx]
                is_high = "High" in item.get("status", "")
                status_label = "CRITICAL RISK" if is_high else "VERIFIED"
                with st.expander(f"Clause #{item.get('clause_id')} - {status_label}", expanded=(idx == 0)):
                    st.info(item.get("clause_text"))
                    st.write(item.get("audit_result"))

            if st.session_state.pdf_bytes is not None:
                if st.session_state.is_premium:
                    st.download_button(
                        label="📄 Download Full PDF Report",
                        data=st.session_state.pdf_bytes,
                        file_name=f"DPDP_Compliance_Report.pdf",
                        mime="application/pdf",
                        type="primary",
                        use_container_width=True
                    )
                else:
                    st.info("⭐ Premium feature: full PDF report download is locked.")

        else:
            # Document Upload State
            tab_upload, tab_paste = st.tabs(["Upload Document", "Paste Clause"])
            with tab_upload:
                with st.form("upload_audit_form", clear_on_submit=False):
                    uploaded_file = st.file_uploader("Drag and drop PDF or TXT", type=["pdf", "txt"])
                    submitted_upload = st.form_submit_button("Run Full Audit", type="primary", use_container_width=True)

                if submitted_upload:
                    if uploaded_file is None:
                        st.warning("Please upload a PDF or TXT file first.")
                    else:
                        upload_info = persist_uploaded_input(current_user_id, workspace_paths, uploaded_file=uploaded_file)
                        if upload_info:
                            run_user_audit(current_user_id, workspace_paths, upload_info["path"], upload_info["source_name"], upload_info["source_type"])

            with tab_paste:
                with st.form("paste_audit_form", clear_on_submit=False):
                    pasted_clause = st.text_area("Paste a clause or policy text", height=200)
                    submitted_paste = st.form_submit_button("Audit Text", type="primary", use_container_width=True)

                if submitted_paste:
                    if not pasted_clause.strip():
                        st.warning("Please paste text before running.")
                    else:
                        paste_info = persist_uploaded_input(current_user_id, workspace_paths, pasted_text=pasted_clause)
                        if paste_info:
                            run_user_audit(current_user_id, workspace_paths, paste_info["path"], paste_info["source_name"], paste_info["source_type"])

            st.markdown("### Past Audits")
            ok_history, history_message, history_records = fetch_user_audits(current_user_id, limit=3)
            if ok_history and history_records:
                for r in history_records:
                    metrics = r.get("metrics_json") or {}
                    st.caption(f"**{r.get('source_name')}** ({r.get('source_type')}) - {metrics.get('high_risk', 0)} High Risk")
            else:
                st.caption("No past audits found.")

    with col_right:
        st.markdown("<h3 style='color: #fff; margin-top:0;'>LexGuard Intelligence</h3>", unsafe_allow_html=True)
        
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {"role": "assistant", "content": "Welcome to LexGuard! I can help you analyze DPDP Act implications or review specific clauses in your documents. How can I assist you today?"}
            ]

        chat_container = st.container(height=550, border=True)
        with chat_container:
            for msg in st.session_state.chat_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    if msg.get("reasoning"):
                        with st.expander("🤔 Thinking Process & Retrieval"):
                            st.info(msg["reasoning"])
                    if msg.get("sources"):
                        st.markdown("**Citations:**")
                        for i, src in enumerate(msg["sources"]):
                            st.button(f"📄 {src}", key=f"src_{i}_{hash(msg['content'])}")

        if prompt := st.chat_input("Ask a legal or compliance question..."):
            st.session_state.chat_messages.append({"role": "user", "content": prompt})
            st.rerun()
            
        # Handle processing of the last user message
        if len(st.session_state.chat_messages) > 0 and st.session_state.chat_messages[-1]["role"] == "user":
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing DPDP context..."):
                        import time
                        time.sleep(1) # Simulate RAG latency
                        
                        try:
                            # Use cached load_retriever() instead of get_retriever()
                            from main import build_chain
                            retriever = load_retriever()
                            chain = build_chain(retriever)
                            
                            user_query = st.session_state.chat_messages[-1]["content"]
                            result = chain.invoke({"query": user_query})
                            
                            response = result.get("result", "I could not find a specific answer in the legal database.")
                            docs = result.get("source_documents", [])
                            
                            reasoning = f"Context retrieval successful. Found {len(docs)} relevant chunks."
                            sources = []
                            for d in docs[:3]:
                                sec = d.metadata.get('section', 'Unknown')
                                sources.append(f"Section {sec} - DPDP Act")
                                
                        except Exception as e:
                            reasoning = f"Retrieval error: {str(e)}"
                            sources = ["LexGuard Base Knowledge"]
                            response = "I encountered an error accessing the DPDP database. Please check your document audit for specific risks."
                        
                        st.session_state.chat_messages.append({
                            "role": "assistant",
                            "content": response,
                            "reasoning": reasoning,
                            "sources": sources
                        })
                        st.rerun()

elif st.session_state.current_page == "dashboard":
    st.markdown("<h2 style='color: white; margin-top:0; font-family: Cabinet Grotesk, sans-serif;'>Dashboard Overview</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Metrics and quick actions for your LexGuard workspace.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    ok_history, msg, history_records = fetch_user_audits(current_user_id, limit=100)
    
    total_audits = len(history_records) if history_records else 0
    total_high_risk = sum(r.get("metrics_json", {}).get("high_risk", 0) for r in history_records) if history_records else 0
    
    with col1:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("Total Documents Audited", total_audits)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("Total High Risks Found", total_high_risk)
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("Workspace Status", "Secure 🔒")
        st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("### Recent Activity")
    if history_records:
        for r in history_records[:5]:
            metrics = r.get("metrics_json") or {}
            st.info(f"📄 **{r.get('source_name')}** audited recently. Found **{metrics.get('high_risk', 0)} High Risk** clauses.")
    else:
        st.caption("No recent activity. Go to Document Audit to scan your first file.")

elif st.session_state.current_page == "library":
    st.markdown("<h2 style='color: white; margin-top:0; font-family: Cabinet Grotesk, sans-serif;'>Compliance Library</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Your full history of audited documents and generated reports.</p>", unsafe_allow_html=True)
    st.markdown("---")
    
    ok_history, msg, history_records = fetch_user_audits(current_user_id, limit=50)
    if ok_history and history_records:
        for r in history_records:
            with st.expander(f"📄 {r.get('source_name')} - Risk Score: {r.get('metrics_json', {}).get('high_risk', 0)} High Risks"):
                metrics = r.get("metrics_json") or {}
                st.write(f"**High Risk:** {metrics.get('high_risk', 0)} | **Medium Risk:** {metrics.get('medium_risk', 0)} | **Compliant:** {metrics.get('compliant', 0)}")
                
                pdf_path = r.get("report_pdf_path")
                if pdf_path and os.path.exists(pdf_path):
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "⬇️ Download PDF Report", 
                            data=f, 
                            file_name=f"LexGuard_Audit_{r.get('source_name')}.pdf", 
                            mime="application/pdf", 
                            key=f"dl_{r.get('id')}"
                        )
                else:
                    st.caption("PDF report not available for this legacy audit.")
    else:
        st.info("Your compliance library is currently empty. Run an audit to start building history.")

elif st.session_state.current_page == "settings":
    st.header("System Configuration")
    st.markdown("Manage your authenticated workspace preferences and storage.")
    st.markdown("---")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Workspace")
        st.text_input(
            "User / Organization",
            placeholder="e.g. Acme Corp Legal",
        )
        st.toggle(
            "Advanced Analysis Mode",
            value=False,
            help="Enable deeper semantic indexing for complex legal constructs.",
        )
        
        st.markdown("---")
        st.subheader("Security")
        with st.form("change_password_form"):
            st.markdown("#### Change Password")
            new_pwd = st.text_input("New Password", type="password")
            conf_pwd = st.text_input("Confirm New Password", type="password")
            pwd_submitted = st.form_submit_button("Update Password", use_container_width=True)
            
            if pwd_submitted:
                if not new_pwd:
                    st.error("Please enter a new password.")
                elif new_pwd != conf_pwd:
                    st.error("Passwords do not match.")
                elif len(new_pwd) < 8 or not any(c.isdigit() for c in new_pwd) or not any(c.isupper() for c in new_pwd):
                    st.error("Password must be at least 8 characters long, contain a number and an uppercase letter.")
                else:
                    ok, msg = update_password(new_pwd)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)

    with c2:
        st.subheader("Data and Privacy")
        st.markdown(
            "**This workspace stores files in a user-isolated directory and writes audit metadata with user_id in Supabase.**"
        )
        st.code(workspace_paths["uploads_dir"], language="text")

        if st.button("Reset Current User Session Cache", type="primary"):
            clear_user_cache(workspace_paths)
            reset_audit_state()
            st.success("Current user cache reset.")
            st.rerun()

    st.markdown("---")
    st.subheader("Supabase Schema Reference")
    st.code(SCHEMA_REFERENCE_SQL, language="sql")
