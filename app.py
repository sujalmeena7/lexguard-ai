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
)
from database import (
    SCHEMA_REFERENCE_SQL,
    delete_user_audit,
    fetch_user_audits,
    save_audit_log,
    save_uploaded_file,
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
        "credits": 5,
        "is_premium": False,
        "show_key_input": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

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
    with st.sidebar:
        st.markdown(
            """
            <div style='text-align: center; padding-bottom: 20px;'>
                <h2 style='color: #002FA7; margin-bottom: 0;'>LexGuard/AI</h2>
                <p style='color: #a1a1aa; font-size: 0.8rem; letter-spacing: 0.1em; text-transform: uppercase;'>Secure Workspace</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.authenticated:
            st.success(f"Signed in as {st.session_state.user_email}")
            if st.button("Sign Out", use_container_width=True, type="primary"):
                sign_out()
                st.rerun()
            return

        st.markdown("### Sign In / Sign Up")

        sign_in_tab, sign_up_tab = st.tabs(["Sign In", "Sign Up"])

        with sign_in_tab:
            with st.form("sign_in_form", clear_on_submit=False):
                email = st.text_input("Email", key="login_email")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Sign In", use_container_width=True)

            if submitted:
                ok, msg = sign_in_with_email(email.strip(), password)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

        with sign_up_tab:
            with st.form("sign_up_form", clear_on_submit=False):
                email = st.text_input("Email", key="signup_email")
                password = st.text_input("Password", type="password", key="signup_password")
                confirm = st.text_input("Confirm Password", type="password", key="signup_confirm")
                submitted = st.form_submit_button("Create Account", use_container_width=True)

            if submitted:
                if password != confirm:
                    st.error("Passwords do not match.")
                elif len(password) < 8:
                    st.error("Use at least 8 characters for password security.")
                else:
                    ok, msg = sign_up_with_email(email.strip(), password)
                    if ok:
                        st.success(msg)
                    else:
                        st.error(msg)


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
    if st.session_state.credits <= 0:
        st.warning("You do not have enough credits to run an audit.")
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

    if not results:
        st.error("Audit failed. Please verify your input document and try again.")
        return

    st.session_state.audit_results = results
    st.session_state.audit_complete = True
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
with st.sidebar:
    if st.button("Run Audit", use_container_width=True):
        st.session_state.current_page = "audit"

    if st.button("Settings", use_container_width=True):
        st.session_state.current_page = "settings"

    st.markdown("---")
    st.markdown("### Account Credits")

    progress_ratio = max(0.0, min(st.session_state.credits / 10.0, 1.0))
    st.progress(progress_ratio)
    st.caption(f"Credits: {st.session_state.credits}/10 remaining")

    if st.session_state.credits <= 0:
        st.error("Insufficient credits. Top up required.")

    st.markdown("---")
    if not st.session_state.is_premium:
        st.markdown("### Premium Access")
        if not st.session_state.show_key_input:
            if st.button("Upgrade to Premium", type="primary", use_container_width=True):
                st.session_state.show_key_input = True
                st.rerun()
        else:
            access_input = st.text_input(
                "Enter Access Key",
                type="password",
                placeholder="Enter your key...",
                key="access_key_input",
            )

            if access_input:
                if ACCESS_KEY and hmac.compare_digest(access_input, ACCESS_KEY):
                    st.session_state.is_premium = True
                    st.session_state.show_key_input = False
                    st.success("Premium unlocked.")
                    st.rerun()
                else:
                    st.error("Invalid key.")
    else:
        st.success("Premium active.")


if st.session_state.current_page == "audit":
    st.markdown(
        """
        <div style='margin-bottom: 24px;'>
            <p style='color: #002FA7; font-family: monospace; font-size: 0.8rem; letter-spacing: 0.2em; margin-bottom: 8px;'>SECURE WORKSPACE</p>
            <h1 style='margin-top: 0;'>DPDP Compliance Auditor</h1>
            <p style='color: #a1a1aa; font-size: 1.05rem; max-width: 760px;'>
                Upload a contract/policy or paste a clause. Files are stored only in your user path:
                <strong>data/{sanitize_user_id(current_user_id)}/uploads/</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Past Audits")
    ok_history, history_message, history_records = fetch_user_audits(current_user_id)
    if ok_history and history_records:
        table_rows = []
        for record in history_records:
            metrics = record.get("metrics_json") or {}
            table_rows.append(
                {
                    "Audit ID": record.get("id"),
                    "Source": record.get("source_name"),
                    "Type": record.get("source_type"),
                    "Created At": record.get("created_at"),
                    "Total": metrics.get("total_clauses", 0),
                    "High Risk": metrics.get("high_risk", 0),
                }
            )

        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        selected_audit_id = st.selectbox(
            "Select an audit to delete",
            options=[item.get("id") for item in history_records if item.get("id")],
            key="selected_audit_id",
        )
        if st.button("Delete Selected Audit", type="secondary"):
            ok_delete, delete_message = delete_user_audit(current_user_id, selected_audit_id)
            if ok_delete:
                st.success(delete_message)
                st.rerun()
            else:
                st.error(delete_message)
    elif ok_history:
        st.info("No past audits yet for this account.")
    else:
        st.warning(history_message)

    st.markdown("---")

    if st.session_state.audit_complete and st.session_state.audit_results is not None:
        if st.button("Start New Audit", type="secondary"):
            clear_user_cache(workspace_paths)
            reset_audit_state()
            st.rerun()

        st.success("Audit complete. Results loaded from your workspace cache.")

        metrics = st.session_state.metrics
        st.markdown("### Findings Summary")
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
                title={"text": "Compliance Health Score", "font": {"size": 24, "color": "white", "family": "Cabinet Grotesk"}},
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
        )
        st.plotly_chart(fig, use_container_width=True)

        report_data = st.session_state.audit_results
        st.markdown("### Findings Preview (First 2 Results)")

        preview_count = min(2, len(report_data))
        for idx in range(preview_count):
            item = report_data[idx]
            is_high = "High" in item.get("status", "")
            status_label = "CRITICAL RISK" if is_high else "VERIFIED"
            with st.expander(
                f"Clause #{item.get('clause_id')} (Page {item.get('page_num')}) - {status_label}",
                expanded=True,
            ):
                st.markdown("**Original Excerpt**")
                st.info(item.get("clause_text"))
                st.markdown("**Audit Verdict**")
                st.write(item.get("audit_result"))

        viewed_findings = preview_count
        total_findings = len(report_data)
        st.markdown(
            f"""
            <div class='paywall-box'>
                <h4>Upgrade to Unlock Full Insights</h4>
                <p>You have seen {viewed_findings} of {total_findings} findings. Download the complete report below.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        download_name = st.session_state.last_filename or "document"
        if st.session_state.pdf_bytes is not None:
            if st.session_state.is_premium:
                st.download_button(
                    label="Download Full PDF Report",
                    data=st.session_state.pdf_bytes,
                    file_name=f"DPDP_Compliance_{download_name}.pdf",
                    mime="application/pdf",
                    type="primary",
                )
            else:
                st.info("Premium feature: full PDF report download is locked.")

    else:
        tab_upload, tab_paste = st.tabs(["Upload Document", "Paste Clause"])

        with tab_upload:
            with st.form("upload_audit_form", clear_on_submit=False):
                uploaded_file = st.file_uploader(
                    "Drag and drop PDF or TXT",
                    type=["pdf", "txt"],
                )
                submitted_upload = st.form_submit_button("Run Full Audit", type="primary")

            if submitted_upload:
                if uploaded_file is None:
                    st.warning("Please upload a PDF or TXT file first.")
                else:
                    upload_info = persist_uploaded_input(
                        user_id=current_user_id,
                        workspace_paths=workspace_paths,
                        uploaded_file=uploaded_file,
                    )
                    if upload_info is None:
                        st.error("Unable to save uploaded file to user workspace.")
                    else:
                        run_user_audit(
                            user_id=current_user_id,
                            workspace_paths=workspace_paths,
                            source_path=upload_info["path"],
                            source_name=upload_info["source_name"],
                            source_type=upload_info["source_type"],
                        )

        with tab_paste:
            with st.form("paste_audit_form", clear_on_submit=False):
                pasted_clause = st.text_area(
                    "Paste a clause or policy text",
                    height=220,
                    max_chars=25000,
                )
                submitted_paste = st.form_submit_button(
                    "Run Full Audit On Pasted Text",
                    type="primary",
                )

            if submitted_paste:
                if not pasted_clause.strip():
                    st.warning("Please paste a clause before running the audit.")
                else:
                    paste_info = persist_uploaded_input(
                        user_id=current_user_id,
                        workspace_paths=workspace_paths,
                        pasted_text=pasted_clause,
                    )
                    if paste_info is None:
                        st.error("Unable to save pasted text to user workspace.")
                    else:
                        run_user_audit(
                            user_id=current_user_id,
                            workspace_paths=workspace_paths,
                            source_path=paste_info["path"],
                            source_name=paste_info["source_name"],
                            source_type=paste_info["source_type"],
                        )

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
