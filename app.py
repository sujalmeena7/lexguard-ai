import hmac
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

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
    fetch_user_uploaded_files,
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
    get_document_namespace,
    get_retriever,
    get_user_workspace_retriever,
    get_user_workspace_vector_stats,
    index_user_document,
    run_compliance_audit,
)
from report_gen import generate_report
from privacy_architect import (
    generate_privacy_roadmap,
    generate_roadmap_from_audit,
    save_roadmap_json,
)


# Premium upgrade access key. Read from Streamlit secrets or environment;
# never hardcoded. When unset, the Upgrade-to-Premium UI is hidden so no
# spoofable default exists in source.
ACCESS_KEY = (
    (st.secrets.get("ACCESS_KEY") or os.environ.get("ACCESS_KEY") or "").strip()
    or None
)
PREMIUM_CREDIT_GRANT = 10
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
    user_path = f"data/{safe_user_id}/"
    uploads_rel_dir = f"{user_path}uploads/"
    cache_rel_dir = f"{user_path}cache/"
    user_root = os.path.join(USER_DATA_ROOT, safe_user_id)
    uploads_dir = os.path.join(user_root, "uploads")
    cache_dir = os.path.join(user_root, "cache")

    return {
        "user_path": user_path,
        "uploads_rel_dir": uploads_rel_dir,
        "cache_rel_dir": cache_rel_dir,
        "user_root": user_root,
        "uploads_dir": uploads_dir,
        "cache_dir": cache_dir,
        "session_cache": os.path.join(cache_dir, "session_cache.json"),
        "report_pdf": os.path.join(cache_dir, "report.pdf"),
        "audit_json": os.path.join(cache_dir, "audit_report.json"),
    }


def resolve_user_storage_path(workspace_paths: Dict[str, str], storage_path: Optional[str]) -> Optional[str]:
    if not storage_path:
        return None

    def _is_within(candidate_path: str, root_path: str) -> bool:
        candidate_abs = os.path.normcase(os.path.abspath(candidate_path))
        root_abs = os.path.normcase(os.path.abspath(root_path))
        return candidate_abs == root_abs or candidate_abs.startswith(root_abs + os.sep)

    allowed_roots = (workspace_paths["uploads_dir"], workspace_paths["cache_dir"])
    normalized = storage_path.replace("\\", "/")
    for rel_prefix in (workspace_paths["uploads_rel_dir"], workspace_paths["cache_rel_dir"]):
        if normalized.startswith(rel_prefix):
            relative_fragment = normalized.replace("/", os.sep)
            resolved_path = os.path.normpath(os.path.join(BASE_DIR, relative_fragment))
            if any(_is_within(resolved_path, root) for root in allowed_roots):
                return resolved_path
            return None

    if os.path.isabs(storage_path):
        resolved_path = os.path.normpath(storage_path)
        if any(_is_within(resolved_path, root) for root in allowed_roots):
            return resolved_path

    return None


def list_local_files(path: str) -> List[str]:
    if not os.path.isdir(path):
        return []
    return sorted(
        [entry for entry in os.listdir(path) if os.path.isfile(os.path.join(path, entry))],
        reverse=True,
    )


def refresh_user_metadata(user_id: str) -> None:
    ok_audits, _, audits = fetch_user_audits(user_id, limit=100)
    ok_uploads, _, uploads = fetch_user_uploaded_files(user_id, limit=100)
    st.session_state.supabase_audits = audits if ok_audits else []
    st.session_state.supabase_uploads = uploads if ok_uploads else []


def _query_param_str(key: str) -> Optional[str]:
    value = st.query_params.get(key)
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _remove_query_param(key: str) -> None:
    try:
        del st.query_params[key]
    except Exception as exc:
        logger.warning("Failed to remove query param '%s': %s", key, exc)


def get_validated_backend_url() -> Optional[str]:
    default_backend_url = "https://lexguard-backend-3mmj.onrender.com"
    raw_backend_url = st.secrets.get(
        "BACKEND_URL",
        os.environ.get("BACKEND_URL", default_backend_url),
    )

    if not isinstance(raw_backend_url, str):
        logger.warning("Invalid BACKEND_URL type; expected string.")
        return None

    backend_url = raw_backend_url.strip()
    if not backend_url:
        logger.warning("BACKEND_URL is empty.")
        return None

    parsed = urllib.parse.urlparse(backend_url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        logger.warning("Rejected BACKEND_URL with invalid scheme/netloc: %s", backend_url)
        return None

    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" and hostname not in {"localhost", "127.0.0.1"}:
        logger.warning("Rejected non-HTTPS BACKEND_URL for non-localhost host '%s'.", hostname)
        return None

    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def exchange_handoff_code_for_token(handoff_code: str) -> Optional[str]:
    backend_url = get_validated_backend_url()
    if not backend_url:
        logger.warning("Auth handoff skipped because BACKEND_URL failed validation.")
        return None

    endpoint = f"{backend_url}/api/auth/handoff/exchange"
    payload = json.dumps({"handoff_code": handoff_code}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        logger.warning("Auth handoff exchange request failed: %s", exc)
        return None

    try:
        data = json.loads(body)
    except json.JSONDecodeError as exc:
        logger.warning("Auth handoff exchange returned invalid JSON: %s", exc)
        return None

    token = data.get("access_token")
    if not isinstance(token, str) or not token.strip():
        logger.warning("Auth handoff exchange missing access_token in response.")
        return None
    return token


def bootstrap_auth_from_query() -> None:
    handoff_code = _query_param_str("handoff_code")
    entry_source = _query_param_str("src")
    access_token = _query_param_str("access_token")

    if handoff_code:
        exchanged_token = exchange_handoff_code_for_token(handoff_code)
        if exchanged_token:
            st.session_state.auth_access_token = exchanged_token
            st.session_state.requested_page = "dashboard"
            st.session_state.handoff_exchange_failed = False
        else:
            st.session_state.handoff_exchange_failed = True
        _remove_query_param("handoff_code")

    if access_token:
        st.session_state.auth_access_token = access_token
        st.session_state.requested_page = "dashboard"
        _remove_query_param("access_token")

    if entry_source:
        st.session_state.entry_source = entry_source


def _is_same_origin_redirect(url: str) -> bool:
    """Return True if the URL points back to this same app (causing a loop)."""
    if not url or url.strip() == "/" or url.strip() == "":
        return True
    # On Streamlit Cloud the hostname ends with .streamlit.app
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        # Heuristic: if redirecting to localhost/127 or same streamlit app domain
        if host in ("localhost", "127.0.0.1", ""):
            return True
        # If the URL contains streamlit.app and we're on streamlit.app, it's same app
        if ".streamlit.app" in host and ".streamlit.app" in str(st_javascript.st_javascript or "").lower():
            return True
    except Exception:
        pass
    return False


def render_redirect_fallback(landing_page_url: str) -> None:
    st.caption("If automatic redirect does not work, use the button below.")
    st.link_button("Go to Landing Page", landing_page_url, use_container_width=True)


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
        storage_path = f"{workspace_paths['uploads_rel_dir']}{file_name}"

        raw_bytes = uploaded_file.getbuffer()
        with open(output_path, "wb") as output_file:
            output_file.write(raw_bytes)

        save_uploaded_file(
            user_id=user_id,
            filename=original_name,
            storage_path=storage_path,
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
        storage_path = f"{workspace_paths['uploads_rel_dir']}{file_name}"

        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write(pasted_text.strip())

        save_uploaded_file(
            user_id=user_id,
            filename="pasted_clause.txt",
            storage_path=storage_path,
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

        document_namespace = get_document_namespace(user_id=user_id, user_doc_path=source_path)
        indexed_chunks = index_user_document(user_id=user_id, user_doc_path=source_path)
        user_workspace_retriever = get_user_workspace_retriever(
            user_id=user_id,
            document_namespace=document_namespace,
        )

        st.markdown("### Real-Time Diagnostics")
        st.caption(
            f"Indexed {indexed_chunks} user chunks in isolated workspace store "
            f"(namespace: {document_namespace})."
        )

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
            status = record.get("status", "")
            if "High" in status:
                metrics["high_risk"] += 1
            elif "Medium" in status or "Moderate" in status:
                metrics["medium_risk"] += 1
            elif "Low" in status or "Compliant" in status:
                metrics["compliant"] += 1
            else:
                metrics["compliant"] += 1  # catch-all for unknown/empty status

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
    refresh_user_metadata(user_id)

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
bootstrap_auth_from_query()
if not st.session_state.authenticated:
    restore_session_from_token()

render_auth_controls()

if not st.session_state.authenticated:
    landing_page_url = st.secrets.get("LANDING_PAGE_URL", "/")
    from_landing = st.session_state.get("entry_source") == "landing"
    handoff_failed = st.session_state.get("handoff_exchange_failed", False)
    would_loop = _is_same_origin_redirect(landing_page_url)

    if from_landing or would_loop:
        st.markdown(
            """
            <div style='padding: 2rem 0;'>
                <h1 style='margin-top: 0;'>LexGuard Dashboard Sign-In</h1>
                <p style='color: #a1a1aa; font-size: 1.05rem; max-width: 700px;'>
                    We couldn't auto-complete your landing-page sign-in handoff. Please sign in once here to open your dashboard session.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if handoff_failed:
            st.warning("Automatic sign-in handoff failed. Use the form below to continue.")
        if would_loop and not from_landing:
            st.info("Landing page URL isn't configured, so you're seeing the sign-in form directly.")

        with st.form("landing_handoff_signin_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)
            if submitted:
                ok, msg = sign_in_with_email(email, password)
                if ok:
                    st.success("Signed in successfully. Opening dashboard…")
                    st.session_state.current_page = "dashboard"
                    st.rerun()
                st.error(msg)
    else:
        st.markdown(
            f"<meta http-equiv='refresh' content='0;url={landing_page_url}'>",
            unsafe_allow_html=True,
        )
        st.markdown(
            """
            <div style='padding: 2rem 0;'>
                <h1 style='margin-top: 0;'>LexGuard Landing Redirect</h1>
                <p style='color: #a1a1aa; font-size: 1.05rem; max-width: 700px;'>
                    Your session is not authenticated, so this workspace is redirecting to the landing page.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.info("Authentication required. Redirecting now.")
        render_redirect_fallback(landing_page_url)
    st.stop()


# User-scoped bootstrap
ensure_user_session_defaults()

if st.session_state.get("user_id") is None:
    landing_page_url = st.secrets.get("LANDING_PAGE_URL", "/")
    if _is_same_origin_redirect(landing_page_url):
        st.warning("No active user session found.")
        st.info("Landing page URL isn't configured. Please sign in above to continue.")
    else:
        st.markdown(
            f"<meta http-equiv='refresh' content='0;url={landing_page_url}'>",
            unsafe_allow_html=True,
        )
        st.warning("No active user session found. Redirecting to the landing page.")
        render_redirect_fallback(landing_page_url)
    st.stop()

current_user_id = str(st.session_state.user_id)
USER_PATH = f"data/{st.session_state.user_id}/"
workspace_paths = get_user_workspace_paths(current_user_id)
ensure_workspace_dirs(workspace_paths)

if st.session_state.authenticated and st.session_state.get("requested_page"):
    st.session_state.current_page = st.session_state.requested_page
    del st.session_state["requested_page"]

if st.session_state.get("active_user_id") != current_user_id:
    st.session_state.active_user_id = current_user_id
    load_user_cache(workspace_paths)
    refresh_user_metadata(current_user_id)
elif "supabase_audits" not in st.session_state or "supabase_uploads" not in st.session_state:
    refresh_user_metadata(current_user_id)

# Removed trivial admin bypass via query parameter


# Sidebar content for authenticated users
# --- CSS Injection for Sidebar Styling ---
active_page = st.session_state.current_page
active_idx = 1
if active_page == "dashboard":
    active_idx = 1
elif active_page == "audit":
    active_idx = 2
elif active_page == "roadmap":
    active_idx = 3
elif active_page == "library":
    active_idx = 4
elif active_page == "settings":
    active_idx = 5
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

    /* Style the sign out button specifically (it's the 6th button in the sidebar) */
    [data-testid="stSidebar"] .stButton:nth-of-type(6) > button {{
        background: rgba(239, 68, 68, 0.1) !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
        color: #ef4444 !important;
        justify-content: center !important;
        padding-left: 0 !important;
        margin-top: 8px;
    }}
    [data-testid="stSidebar"] .stButton:nth-of-type(6) > button:hover {{
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
    if st.button("🗺️ Privacy Roadmap", use_container_width=True):
        st.session_state.current_page = "roadmap"
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
                        {'Premium Plan' if st.session_state.is_premium else 'Enterprise Plan'}
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

        # ---------- Upgrade to Premium ----------
        # Reveals an access-key form. A correct key grants the user
        # PREMIUM_CREDIT_GRANT additional audit credits.
        # Only rendered when ACCESS_KEY is configured via secrets/env so the
        # repo never ships a guessable default.
        if ACCESS_KEY and not st.session_state.get("show_key_input", False):
            if st.button(
                "⭐ Upgrade to Premium",
                use_container_width=True,
                key="upgrade_premium_btn",
            ):
                st.session_state.show_key_input = True
                st.rerun()
        elif ACCESS_KEY:
            with st.form("premium_access_form", clear_on_submit=True):
                st.caption("Enter your access key to unlock premium credits.")
                access_key_input = st.text_input(
                    "Access Key",
                    type="password",
                    key="premium_access_key_input",
                    placeholder="lexguard-xxxx-xxxx",
                )
                col_apply, col_cancel = st.columns(2)
                with col_apply:
                    apply_clicked = st.form_submit_button(
                        "Apply Key", use_container_width=True
                    )
                with col_cancel:
                    cancel_clicked = st.form_submit_button(
                        "Cancel", use_container_width=True
                    )

                if cancel_clicked:
                    st.session_state.show_key_input = False
                    st.rerun()
                elif apply_clicked:
                    submitted_key = (access_key_input or "").strip()
                    if not submitted_key:
                        st.error("Please enter an access key.")
                    elif not check_rate_limit(
                        "PREMIUM_KEY_ATTEMPT",
                        user_id=st.session_state.user_id,
                        limit=5,
                        window_minutes=15,
                    ):
                        st.error("Too many attempts. Please try again later.")
                        log_security_event(
                            "PREMIUM_KEY_RATE_LIMITED",
                            user_id=st.session_state.user_id,
                            severity="WARNING",
                            description="Rate limit hit on premium access-key attempts.",
                        )
                    elif submitted_key == ACCESS_KEY:
                        ok, new_balance = add_user_credits(
                            str(st.session_state.user_id),
                            PREMIUM_CREDIT_GRANT,
                        )
                        if ok:
                            # Upgrade plan to Premium in DB and session
                            update_user_premium_status(
                                str(st.session_state.user_id), True
                            )
                            old_balance = st.session_state.credits
                            actual_added = new_balance - old_balance
                            st.session_state.credits = new_balance
                            st.session_state.is_premium = True
                            st.session_state.show_key_input = False
                            log_security_event(
                                "PREMIUM_KEY_REDEEMED",
                                user_id=st.session_state.user_id,
                                severity="INFO",
                                description=(
                                    f"Premium access key redeemed: "
                                    f"+{actual_added} credits "
                                    f"(new balance: {new_balance})."
                                ),
                                metadata={"granted": actual_added, "capped": actual_added < PREMIUM_CREDIT_GRANT},
                            )
                            st.success(
                                f"✅ Access key accepted. +{actual_added} "
                                f"credits added (new balance: {new_balance})."
                            )
                            st.rerun()
                        else:
                            st.error(
                                "Could not credit your account. "
                                "Please contact support."
                            )
                    else:
                        log_security_event(
                            "PREMIUM_KEY_INVALID",
                            user_id=st.session_state.user_id,
                            severity="WARNING",
                            description="Invalid premium access key submitted.",
                        )
                        st.error("Invalid access key.")

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
            preview_count = min(2, len(report_data))
            for idx in range(preview_count):
                item = report_data[idx]
                status_label = item.get("status") or "Compliant"
                with st.expander(f"Clause #{item.get('clause_id')} - {status_label}", expanded=(idx == 0)):
                    st.info(item.get("clause_text"))
                    st.write(item.get("audit_result"))

            if not st.session_state.is_premium:
                st.divider()
                st.markdown(
                    "<div style='text-align:center; padding: 16px; border: 1px dashed rgba(255,255,255,0.15); border-radius: 8px;'>"
                    "<p style='color: #94a3b8; font-size: 14px; margin-bottom: 8px;'>"
                    "🔒 <strong>2 more clauses hidden</strong></p>"
                    "<p style='color: #64748b; font-size: 12px; margin: 0;'>"
                    "To view the full audit and download the professional PDF report, upgrade to Premium by clicking the "
                    "<strong>⭐ Upgrade to Premium</strong> button in the sidebar."
                    "</p></div>",
                    unsafe_allow_html=True,
                )
            elif st.session_state.pdf_bytes is not None:
                st.download_button(
                    label="📄 Download Full PDF Report",
                    data=st.session_state.pdf_bytes,
                    file_name=f"DPDP_Compliance_Report.pdf",
                    mime="application/pdf",
                    type="primary",
                    use_container_width=True
                )

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
            history_records = st.session_state.get("supabase_audits", [])[:3]
            if history_records:
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
                            # Modern chain uses "input" instead of "query"
                            result = chain.invoke({"input": user_query})
                            
                            # Modern chain uses "answer" instead of "result" and "context" instead of "source_documents"
                            response = result.get("answer", "I could not find a specific answer in the legal database.")
                            docs = result.get("context", [])
                            
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

    history_records = st.session_state.get("supabase_audits", [])
    uploaded_records = st.session_state.get("supabase_uploads", [])
    vector_stats = get_user_workspace_vector_stats(current_user_id)
    local_upload_files = list_local_files(workspace_paths["uploads_dir"])
    local_cache_files = list_local_files(workspace_paths["cache_dir"])

    col1, col2, col3, col4 = st.columns(4)
    total_audits = len(history_records)
    total_uploaded = len(uploaded_records)
    total_high_risk = sum(r.get("metrics_json", {}).get("high_risk", 0) for r in history_records)

    with col1:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("Total Documents Audited", total_audits)
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("Uploaded Files (Supabase)", total_uploaded)
        st.markdown("</div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("Total High Risks Found", total_high_risk)
        st.markdown("</div>", unsafe_allow_html=True)
    with col4:
        st.markdown("<div class='lg-card'>", unsafe_allow_html=True)
        st.metric("User Vector Chunks", vector_stats.get("total_chunks", 0))
        st.markdown("</div>", unsafe_allow_html=True)

    st.caption(
        f"USER_PATH: {USER_PATH} | Local uploads: {len(local_upload_files)} | Local cache files: {len(local_cache_files)}"
    )

    if not history_records and not uploaded_records:
        st.info("Start your first audit to populate your dashboard history.")
        if st.button("Start your first audit", type="primary", use_container_width=True):
            st.session_state.current_page = "audit"
            st.rerun()
        st.stop()

    st.markdown("### Recent Activity")
    if history_records:
        for r in history_records[:5]:
            metrics = r.get("metrics_json") or {}
            st.info(f"📄 **{r.get('source_name')}** audited recently. Found **{metrics.get('high_risk', 0)} High Risk** clauses.")
    else:
        st.caption("No recent audit activity yet.")

    st.markdown("### Report Download")
    st.caption(f"Report cache path: {workspace_paths['cache_rel_dir']}")
    if os.path.exists(workspace_paths["report_pdf"]):
        with open(workspace_paths["report_pdf"], "rb") as report_file:
            st.download_button(
                label="Report Download",
                data=report_file.read(),
                file_name="LexGuard_Latest_Report.pdf",
                mime="application/pdf",
                key="dashboard_report_download",
                use_container_width=True,
            )
    else:
        st.caption("No cached report found in your USER_PATH/cache directory.")

    st.markdown("### Uploaded Documents")
    st.caption(f"Document source path: {workspace_paths['uploads_rel_dir']}")
    if uploaded_records:
        for doc in uploaded_records[:5]:
            storage_path = doc.get("storage_path")
            resolved_path = resolve_user_storage_path(workspace_paths, storage_path)
            display_path = storage_path or f"{workspace_paths['uploads_rel_dir']}{doc.get('filename', '')}"

            c1, c2, c3 = st.columns([2.5, 2.0, 1.0])
            c1.markdown(f"**{doc.get('filename', 'document')}**")
            c2.caption(display_path)
            if resolved_path and os.path.exists(resolved_path):
                with open(resolved_path, "rb") as doc_file:
                    c3.download_button(
                        "View Document",
                        data=doc_file.read(),
                        file_name=os.path.basename(resolved_path),
                        mime=doc.get("mime_type") or "application/octet-stream",
                        key=f"view_doc_{doc.get('id')}",
                    )
            else:
                c3.caption("Missing")
    else:
        st.caption("No uploaded documents recorded in Supabase for this user yet.")

elif st.session_state.current_page == "roadmap":
    # ── Privacy Architect Roadmap Page ──────────────────────────────────
    st.markdown(
        """
        <div style="display: flex; gap: 12px; margin-bottom: 24px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 15px; align-items: center;">
            <h2 style="margin: 0; font-family: 'Cabinet Grotesk', sans-serif; font-weight: 800; letter-spacing: -0.5px; margin-right: auto;">PRIVACY ROADMAP</h2>
            <span style="background: rgba(168, 85, 247, 0.15); color: #c084fc; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; font-family: monospace; border: 1px solid rgba(168, 85, 247, 0.3);">🏗️ ARCHITECT MODE</span>
            <span style="background: rgba(22, 163, 74, 0.15); color: #4ade80; padding: 4px 12px; border-radius: 6px; font-size: 0.8rem; font-family: monospace; border: 1px solid rgba(22, 163, 74, 0.3);">📅 DPDP 2025 PHASE-AWARE</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Check for existing roadmap in session
    if "roadmap_data" not in st.session_state:
        st.session_state.roadmap_data = None

    if st.session_state.roadmap_data is not None:
        roadmap = st.session_state.roadmap_data

        if st.button("🔄 Generate New Roadmap", type="secondary"):
            st.session_state.roadmap_data = None
            st.rerun()

        # ── Overall Risk Rating Banner ──
        risk_rating = roadmap.get("overall_risk_rating", "Moderate")
        risk_colors = {
            "Critical": ("#dc2626", "rgba(220, 38, 38, 0.15)"),
            "High": ("#ea580c", "rgba(234, 88, 12, 0.15)"),
            "Moderate": ("#d97706", "rgba(217, 119, 6, 0.15)"),
            "Low": ("#16a34a", "rgba(22, 163, 74, 0.15)"),
        }
        rc = risk_colors.get(risk_rating, ("#d97706", "rgba(217, 119, 6, 0.15)"))
        total_gaps = roadmap.get("total_gaps_found", 0)

        st.markdown(
            f"""
            <div style="background: {rc[1]}; border: 1px solid {rc[0]}30; border-radius: 12px; padding: 20px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h3 style="margin: 0; color: {rc[0]}; font-family: 'Cabinet Grotesk', sans-serif;">Overall Risk: {risk_rating}</h3>
                    <p style="margin: 4px 0 0; color: #94a3b8; font-size: 0.9rem;">{total_gaps} compliance gap(s) identified</p>
                </div>
                <div style="font-size: 2.5rem;">{"🔴" if risk_rating in ('Critical', 'High') else "🟡" if risk_rating == 'Moderate' else "🟢"}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Readability Health Gauge + UX Scorecard ──
        col_gauge, col_ux = st.columns([1, 1], gap="large")

        with col_gauge:
            st.markdown("### 📊 Readability Health")
            scorecard = roadmap.get("privacy_ux_scorecard", {})
            readability = scorecard.get("readability_score", 0)
            grade = scorecard.get("readability_grade", "Unknown")

            fig = go.Figure(
                go.Indicator(
                    mode="gauge+number",
                    value=readability,
                    domain={"x": [0, 1], "y": [0, 1]},
                    title={"text": f"Flesch-Kincaid ({grade})", "font": {"size": 16, "color": "white"}},
                    gauge={
                        "axis": {"range": [0, 100], "tickcolor": "white"},
                        "bar": {"color": "#8b5cf6"},
                        "bgcolor": "rgba(255,255,255,0.05)",
                        "borderwidth": 2,
                        "bordercolor": "rgba(255,255,255,0.1)",
                        "steps": [
                            {"range": [0, 30], "color": "rgba(185, 28, 28, 0.3)"},
                            {"range": [30, 60], "color": "rgba(180, 83, 9, 0.3)"},
                            {"range": [60, 100], "color": "rgba(22, 101, 52, 0.3)"},
                        ],
                    },
                )
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "white"},
                height=280,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_ux:
            st.markdown("### 🌐 Multilingual Readiness")
            ml = scorecard.get("multilingual_readiness", {})
            ml_status = ml.get("status", "Not Ready")
            ml_color = {"Ready": "#4ade80", "Partially Ready": "#fbbf24", "Not Ready": "#ef4444"}.get(ml_status, "#94a3b8")
            st.markdown(
                f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.1); border-radius: 12px; padding: 20px; margin-bottom: 16px;">
                    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                        <span style="background: {ml_color}20; color: {ml_color}; padding: 4px 12px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; border: 1px solid {ml_color}40;">{ml_status}</span>
                        <span style="color: #94a3b8; font-size: 0.8rem;">22 Scheduled Languages</span>
                    </div>
                    <p style="color: #d1d5db; font-size: 0.9rem; margin: 8px 0 0;">{ml.get('rationale', 'No assessment available.')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("### ⚠️ Jargon Alerts")
            jargon = scorecard.get("jargon_alerts", [])
            for ja in jargon:
                st.markdown(
                    f"""
                    <div style="background: rgba(251, 191, 36, 0.08); border-left: 3px solid #fbbf24; padding: 10px 14px; margin-bottom: 8px; border-radius: 0 8px 8px 0;">
                        <span style="color: #fbbf24; font-weight: 600;">"{ja.get('term', '')}"</span>
                        <span style="color: #94a3b8;"> → </span>
                        <span style="color: #4ade80; font-weight: 500;">"{ja.get('plain_language', '')}"</span>
                        <div style="color: #6b7280; font-size: 0.8rem; margin-top: 4px;">Context: {ja.get('context', '')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # ── Remediation Roadmap (Golden Clauses) ──
        st.markdown("### 🏗️ Remediation Roadmap")
        remediation = roadmap.get("remediation_roadmap", [])

        for gap in remediation:
            gap_id = gap.get("gap_id", "GAP-?")
            enforcement = gap.get("enforcement_status", "active")
            enforcement_badge = (
                '<span style="background: rgba(239, 68, 68, 0.15); color: #ef4444; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(239, 68, 68, 0.3);">🔴 ACTIVE</span>'
                if enforcement == "active"
                else '<span style="background: rgba(59, 130, 246, 0.15); color: #60a5fa; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; border: 1px solid rgba(59, 130, 246, 0.3);">🔵 UPCOMING</span>'
            )

            with st.expander(f"{gap_id}: {gap.get('gap_description', 'Gap')} — {gap.get('dpdp_section', '')}", expanded=False):
                st.markdown(
                    f"""
                    <div style="margin-bottom: 8px;">{enforcement_badge} <span style="color: #94a3b8; font-size: 0.8rem; margin-left: 8px;">{gap.get('dpdp_section', '')}</span></div>
                    """,
                    unsafe_allow_html=True,
                )

                col_action, col_ops = st.columns(2)
                with col_action:
                    st.markdown("**⚡ Immediate Action**")
                    st.info(gap.get("immediate_action", "N/A"))
                with col_ops:
                    st.markdown("**🔧 Operational Change**")
                    st.warning(gap.get("operational_change", "N/A"))

                st.markdown("**✨ Golden Clause** *(copy-ready DPDP-compliant replacement)*")
                golden_clause = gap.get("golden_clause", "N/A")
                st.code(golden_clause, language=None)

        st.markdown("---")

        # ── Executive Summary Table ──
        st.markdown("### 📋 Executive Summary")
        exec_summary = roadmap.get("executive_summary", [])
        if exec_summary:
            import pandas as pd
            df = pd.DataFrame(exec_summary)
            column_rename = {
                "violation": "Violation",
                "remediation_effort": "Effort",
                "business_impact": "Business Impact",
                "fix_priority": "Priority",
            }
            df = df.rename(columns=column_rename)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Priority": st.column_config.TextColumn(width="medium"),
                    "Effort": st.column_config.TextColumn(width="small"),
                },
            )
        else:
            st.caption("No executive summary items generated.")

        # ── Save/Download Roadmap JSON ──
        if st.session_state.roadmap_data:
            roadmap_json_str = json.dumps(st.session_state.roadmap_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="📥 Download Roadmap JSON",
                data=roadmap_json_str,
                file_name="privacy_roadmap.json",
                mime="application/json",
                type="primary",
                use_container_width=True,
            )

    else:
        # ── Input Form ──
        st.markdown(
            """
            <div style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.1) 0%, rgba(59, 130, 246, 0.1) 100%); border: 1px solid rgba(139, 92, 246, 0.2); border-radius: 12px; padding: 24px; margin-bottom: 24px;">
                <h3 style="margin: 0 0 8px; color: #c084fc; font-family: 'Cabinet Grotesk', sans-serif;">🏗️ Privacy Architect</h3>
                <p style="color: #94a3b8; font-size: 0.95rem; margin: 0;">Transform any privacy policy or compliance audit into an actionable business roadmap with legally vetted replacement clauses, readability scoring, and a prioritised fix list.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Option 1: Generate from existing audit
        if st.session_state.audit_complete and st.session_state.audit_results:
            st.markdown("#### From Latest Audit")
            st.caption(f"Use your most recent audit ({st.session_state.last_filename or 'cached result'}) as input.")
            if st.button("🚀 Generate Roadmap from Audit Results", type="primary", use_container_width=True, key="roadmap_from_audit"):
                if st.session_state.credits <= 0 and not st.session_state.is_premium:
                    st.warning("You need audit credits to generate a roadmap.")
                else:
                    with st.spinner("Generating Privacy Architect roadmap from audit results..."):
                        try:
                            roadmap = generate_roadmap_from_audit(
                                st.session_state.audit_results,
                            )
                            if roadmap:
                                st.session_state.roadmap_data = roadmap
                                roadmap_path = os.path.join(workspace_paths["cache_dir"], "privacy_roadmap.json")
                                save_roadmap_json(roadmap, roadmap_path)
                                st.success("Roadmap generated successfully!")
                                st.rerun()
                            else:
                                st.error("Roadmap generation returned no data.")
                        except Exception as e:
                            st.error(f"Roadmap generation failed: {e}")
            st.markdown("---")

        # Option 2: Paste policy text
        st.markdown("#### From Policy Text")
        with st.form("roadmap_text_form", clear_on_submit=False):
            policy_text = st.text_area(
                "Paste your privacy policy, terms of service, or any legal document",
                height=250,
                placeholder="Paste at least 50 characters of policy text here...",
            )
            submitted = st.form_submit_button("🗺️ Generate Privacy Roadmap", type="primary", use_container_width=True)

        if submitted:
            if not policy_text or len(policy_text.strip()) < 50:
                st.warning("Please paste at least 50 characters of policy text.")
            elif st.session_state.credits <= 0 and not st.session_state.is_premium:
                st.warning("You need audit credits to generate a roadmap.")
            else:
                with st.spinner("Generating Privacy Architect roadmap..."):
                    try:
                        roadmap = generate_privacy_roadmap(policy_text.strip())
                        if roadmap:
                            st.session_state.roadmap_data = roadmap
                            roadmap_path = os.path.join(workspace_paths["cache_dir"], "privacy_roadmap.json")
                            save_roadmap_json(roadmap, roadmap_path)
                            st.success("Roadmap generated successfully!")
                            st.rerun()
                        else:
                            st.error("Roadmap generation returned no data.")
                    except Exception as e:
                        st.error(f"Roadmap generation failed: {e}")

        # Option 3: Upload document
        st.markdown("#### From Document Upload")
        with st.form("roadmap_upload_form", clear_on_submit=False):
            uploaded_doc = st.file_uploader("Upload a PDF or TXT document", type=["pdf", "txt"], key="roadmap_file_upload")
            upload_submitted = st.form_submit_button("🗺️ Generate from Document", type="primary", use_container_width=True)

        if upload_submitted:
            if uploaded_doc is None:
                st.warning("Please upload a document first.")
            elif st.session_state.credits <= 0 and not st.session_state.is_premium:
                st.warning("You need audit credits to generate a roadmap.")
            else:
                with st.spinner("Reading document and generating roadmap..."):
                    try:
                        upload_info = persist_uploaded_input(current_user_id, workspace_paths, uploaded_file=uploaded_doc)
                        if upload_info:
                            # Read the file content
                            doc_path = upload_info["path"]
                            if doc_path.lower().endswith(".txt"):
                                with open(doc_path, "r", encoding="utf-8") as f:
                                    doc_text = f.read()
                            else:
                                from langchain_community.document_loaders import PyPDFLoader
                                loader = PyPDFLoader(doc_path)
                                pages = loader.load()
                                doc_text = "\n\n".join(p.page_content for p in pages)

                            if len(doc_text.strip()) < 50:
                                st.warning("Document content is too short for analysis.")
                            else:
                                roadmap = generate_privacy_roadmap(doc_text.strip())
                                if roadmap:
                                    st.session_state.roadmap_data = roadmap
                                    roadmap_path = os.path.join(workspace_paths["cache_dir"], "privacy_roadmap.json")
                                    save_roadmap_json(roadmap, roadmap_path)
                                    st.success("Roadmap generated successfully!")
                                    st.rerun()
                                else:
                                    st.error("Roadmap generation returned no data.")
                    except Exception as e:
                        st.error(f"Roadmap generation failed: {e}")

elif st.session_state.current_page == "library":
    st.markdown("<h2 style='color: white; margin-top:0; font-family: Cabinet Grotesk, sans-serif;'>Compliance Library</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Your full history of audited documents and generated reports.</p>", unsafe_allow_html=True)
    st.markdown("---")

    history_records = st.session_state.get("supabase_audits", [])
    uploaded_records = st.session_state.get("supabase_uploads", [])
    uploads_by_filename = {}
    for record in uploaded_records:
        filename = record.get("filename")
        if filename and filename not in uploads_by_filename:
            uploads_by_filename[filename] = record

    if history_records:
        for r in history_records:
            with st.expander(f"📄 {r.get('source_name')} - Risk Score: {r.get('metrics_json', {}).get('high_risk', 0)} High Risks"):
                metrics = r.get("metrics_json") or {}
                st.write(f"**High Risk:** {metrics.get('high_risk', 0)} | **Medium Risk:** {metrics.get('medium_risk', 0)} | **Compliant:** {metrics.get('compliant', 0)}")

                st.caption(f"Report path: {workspace_paths['cache_rel_dir']}report.pdf")
                if os.path.exists(workspace_paths["report_pdf"]):
                    with open(workspace_paths["report_pdf"], "rb") as f:
                        st.download_button(
                            "⬇️ Download PDF Report", 
                            data=f.read(), 
                            file_name=f"LexGuard_Audit_{r.get('source_name')}.pdf", 
                            mime="application/pdf", 
                            key=f"dl_{r.get('id')}"
                        )
                else:
                    st.caption("Cached report not available in USER_PATH/cache.")

                linked_upload = uploads_by_filename.get(r.get("source_name"))
                if linked_upload:
                    upload_storage = linked_upload.get("storage_path")
                    upload_abs_path = resolve_user_storage_path(workspace_paths, upload_storage)
                    st.caption(f"Document path: {upload_storage}")
                    if upload_abs_path and os.path.exists(upload_abs_path):
                        with open(upload_abs_path, "rb") as doc_file:
                            st.download_button(
                                "View Document",
                                data=doc_file.read(),
                                file_name=os.path.basename(upload_abs_path),
                                mime=linked_upload.get("mime_type") or "application/octet-stream",
                                key=f"view_lib_doc_{linked_upload.get('id')}_{r.get('id')}",
                            )
                    else:
                        st.caption("Uploaded document file is not available in local USER_PATH/uploads.")
                else:
                    st.caption("No linked uploaded file metadata found for this audit record.")
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
