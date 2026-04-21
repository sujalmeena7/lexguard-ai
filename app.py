import streamlit as st
import os
import tempfile
import json

# Import functions from existing backend
from main import get_retriever, run_compliance_audit

# Premium Access Key
ACCESS_KEY = "EM84vz81##"
from report_gen import generate_report

# Paths for Disk Persistence
SESSION_DIR = os.path.join(os.path.dirname(__file__), "data_store")
SESSION_CACHE = os.path.join(SESSION_DIR, "session_cache.json")
SESSION_PDF = os.path.join(SESSION_DIR, "report.pdf")

# Ensure directory exists
os.makedirs(SESSION_DIR, exist_ok=True)

def clear_session_cache():
    if os.path.exists(SESSION_CACHE):
        try:
            os.remove(SESSION_CACHE)
        except Exception:
            pass
    if os.path.exists(SESSION_PDF):
        try:
            os.remove(SESSION_PDF)
        except Exception:
            pass

# Configure Streamlit page
st.set_page_config(
    page_title="LexGuard AI - DPDP Auditor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Styling (CSS)
st.markdown("""
<style>
    .reportview-container {
        background: #f0f2f6;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    .paywall-box {
        background: linear-gradient(135deg, #0f2044 0%, #1a3a6b 60%, #0d1f42 100%);
        border: 1.5px solid #4a7fd4;
        padding: 28px 32px;
        border-radius: 14px;
        text-align: center;
        margin-top: 30px;
        margin-bottom: 20px;
        box-shadow: 0 4px 24px rgba(10, 30, 80, 0.45);
    }
    .paywall-box h4 {
        color: #f0c93a !important;
        font-size: 1.2rem;
        font-weight: 700;
        margin-bottom: 10px;
        letter-spacing: 0.03em;
    }
    .paywall-box p {
        color: #d0dff8 !important;
        font-size: 0.97rem;
        margin: 0;
        line-height: 1.6;
    }
    .sidebar .stButton>button {
        text-align: left;
    }
</style>
""", unsafe_allow_html=True)

# State Initialization (State Guardrails + Disk Persistence)
if "current_page" not in st.session_state:
    st.session_state.current_page = "audit"
if "credits" not in st.session_state:
    st.session_state.credits = 5
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False

# Admin Backdoor: ?admin=true in URL auto-grants premium
query_params = st.query_params
if query_params.get("admin", "").lower() == "true":
    st.session_state.is_premium = True

if "audit_results" not in st.session_state:
    # Load from Disk Cache if it exists
    if os.path.exists(SESSION_CACHE):
        try:
            with open(SESSION_CACHE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            st.session_state.audit_complete = cache_data.get("audit_complete", False)
            st.session_state.audit_results = cache_data.get("audit_results", None)
            st.session_state.last_filename = cache_data.get("last_filename", None)
            st.session_state.metrics = cache_data.get("metrics", {"total_clauses": 0, "high_risk": 0, "medium_risk": 0, "compliant": 0})
            
            # Load PDF bytes if the file exists
            pdf_path = cache_data.get("pdf_path")
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    st.session_state.pdf_bytes = f.read()
            else:
                st.session_state.pdf_bytes = None
                
        except Exception as e:
            # Handle corrupted or invalid JSON safely
            st.session_state.audit_complete = False
            st.session_state.audit_results = None
            st.session_state.pdf_bytes = None
            st.session_state.last_filename = None
            st.session_state.metrics = {"total_clauses": 0, "high_risk": 0, "medium_risk": 0, "compliant": 0}
    else:
        st.session_state.audit_complete = False
        st.session_state.audit_results = None
        st.session_state.pdf_bytes = None
        st.session_state.last_filename = None
        st.session_state.metrics = {"total_clauses": 0, "high_risk": 0, "medium_risk": 0, "compliant": 0}

if "audit_complete" not in st.session_state:
    st.session_state.audit_complete = False

# Load Retriever (Cached so it doesn't reload on every UI interaction)
@st.cache_resource(show_spinner="Loading Legal Knowledge Base...")
def load_retriever():
    return get_retriever(ingest=False)

# ---- Sidebar ----
with st.sidebar:
    st.title("⚖️ LexGuard AI")
    st.markdown("---")
    
    # Navigation Buttons
    if st.button("📊 Run Audit", use_container_width=True):
        st.session_state.current_page = "audit"
    if st.button("⚙️ Settings", use_container_width=True):
        st.session_state.current_page = "settings"
    
    st.markdown("---")
    
    # Credit Balance (Mock Paywall)
    st.markdown("### Account Credits")
    progress_ratio = max(0.0, min(st.session_state.credits / 10.0, 1.0))
    st.progress(progress_ratio)
    st.caption(f"Credits: {st.session_state.credits}/10 remaining")
    
    if st.session_state.credits <= 0:
        st.error("Insufficient Credits! Please Top Up.")

    st.markdown("---")
    # Premium Access Key Gate
    if not st.session_state.is_premium:
        st.markdown("### 🔐 Premium Access")
        if "show_key_input" not in st.session_state:
            st.session_state.show_key_input = False

        if not st.session_state.show_key_input:
            if st.button("⭐ Upgrade to Premium", type="primary", use_container_width=True):
                st.session_state.show_key_input = True
                st.rerun()
        else:
            access_input = st.text_input(
                "Enter Access Key",
                type="password",
                placeholder="Enter your key...",
                key="access_key_input"
            )
            if access_input:
                if access_input == ACCESS_KEY:
                    st.session_state.is_premium = True
                    st.session_state.show_key_input = False
                    st.success("Access Granted: Premium Features Unlocked!")
                    st.rerun()
                else:
                    st.error("Invalid key. Please try again.")
            
            st.info(
                "Need an Access Key for full professional reports and 100+ document audits? "
                "Contact our team for enterprise and individual plans.\n\n"
                "📧 **Email:** meenasujal60@gmail.com\n\n"
                "⏱️ Get a response within 2 hours."
            )
    else:
        st.success("✅ Premium Active — Full Access Enabled")


# ---- Page Routing ----
if st.session_state.current_page == "audit":
    st.header("📄 DPDP Compliance Auditor")
    st.markdown("Upload a contract or policy document to automatically audit it against the **DPDP Act 2023**.")

    # Persistent Rendering Logic
    if st.session_state.audit_complete and st.session_state.audit_results is not None:
        if st.button("🔄 Start New Audit", type="secondary"):
            clear_session_cache() # Purge the JSON file and PDF
            st.session_state.audit_complete = False
            st.session_state.audit_results = None
            st.session_state.pdf_bytes = None
            st.session_state.last_filename = None
            st.session_state.metrics = {"total_clauses": 0, "high_risk": 0, "medium_risk": 0, "compliant": 0}
            st.rerun()

        st.success("✅ Audit Complete! Results loaded from Session Vault.")
        
        m = st.session_state.metrics
        st.markdown("### Findings Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Clauses", m["total_clauses"])
        c2.metric("High Risk", f"{m['high_risk']} 🔴")
        c3.metric("Medium Risk", f"{m['medium_risk']} 🟠")
        c4.metric("Compliant", f"{m['compliant']} 🟢")
        
        # --- Compliance Gauge Chart ---
        import plotly.graph_objects as go
        total = m["total_clauses"]
        high_risk = m["high_risk"]
        raw_score = (m["compliant"] / total) * 100 if total > 0 else 100
        
        # Force Red Zone if High Risks are detected
        score = min(49.0, raw_score) if high_risk > 0 else raw_score
            
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = score,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Compliance Health Score", 'font': {'size': 20}},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "black"},
                'steps': [
                    {'range': [0, 50], 'color': "red"},
                    {'range': [50, 80], 'color': "orange"},
                    {'range': [80, 100], 'color': "green"}
                ]
            }
        ))
        st.plotly_chart(fig, use_container_width=True)
        
        report_data = st.session_state.audit_results
        st.markdown("### 🔍 Findings Preview (First 2 Results)")
        
        preview_count = min(2, len(report_data))
        for i in range(preview_count):
            item = report_data[i]
            is_high = "High" in item.get("status", "")
            with st.expander(f"Clause #{item.get('clause_id')} (Page {item.get('page_num')}) - {'🔴 HIGH RISK' if is_high else '🟢 COMPLIANT'}", expanded=True):
                st.markdown("**Original Clause:**")
                st.info(item.get("clause_text"))
                st.markdown("**AI Audit Result:**")
                st.warning(item.get("audit_result"))
        
        viewed_findings = preview_count
        total_findings = len(report_data)
        st.markdown(f"""
        <div class='paywall-box'>
            <h4>🔒 Upgrade to Unlock Full Insights</h4>
            <p>You have seen {viewed_findings} out of {total_findings} findings. Download the complete professional report below to see all risks and suggested corrections.</p>
        </div>
        """, unsafe_allow_html=True)
        
        file_dl_name = st.session_state.last_filename if st.session_state.last_filename else "Document"
        if st.session_state.pdf_bytes is not None:
            if st.session_state.get('is_premium', False):
                st.download_button(
                    label="📄 Download Full Professional PDF Report",
                    data=st.session_state.pdf_bytes,
                    file_name=f"DPDP_Compliance_{file_dl_name}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            else:
                st.info("💡 Premium Feature: The full 10-page Legal Audit Report is locked. Click 'Upgrade' in the sidebar to unlock.")

    else:
        # ---- Main Page: Upload Zone ----
        uploaded_file = st.file_uploader("Upload Document (.pdf, .txt)", type=["pdf", "txt"])

        if uploaded_file is not None:
            if uploaded_file.name != st.session_state.last_filename:
                # Purge session on a new file to enforce full security
                clear_session_cache()
                st.session_state.audit_complete = False
                st.session_state.audit_results = None
                st.session_state.pdf_bytes = None
                st.session_state.last_filename = uploaded_file.name
                st.session_state.metrics = {"total_clauses": 0, "high_risk": 0, "medium_risk": 0, "compliant": 0}
                
            st.success(f"File '{uploaded_file.name}' loaded successfully!")
            
            if st.session_state.credits > 0:
                if st.button("🚀 Run Full Audit", type="primary"):
                    # Run Logic
                    file_ext = "." + uploaded_file.name.split('.')[-1] if '.' in uploaded_file.name else ".pdf"
                    fd, temp_path = tempfile.mkstemp(suffix=file_ext)
                    with os.fdopen(fd, 'wb') as f:
                        f.write(uploaded_file.getbuffer())

                    try:
                        with st.spinner("Analyzing against DPDP Act 2023..."):
                            retriever = load_retriever()
                            
                            st.markdown("### Real-Time Diagnostics")
                            progress_bar = st.progress(0)
                            
                            col1, col2, col3, col4 = st.columns(4)
                            metric_total = col1.empty()
                            metric_high = col2.empty()
                            metric_med = col3.empty()
                            metric_compliant = col4.empty()
                            
                            def progress_update(current_step, total_steps, record, is_high_risk_flag):
                                m = st.session_state.metrics
                                m["total_clauses"] += 1
                                if is_high_risk_flag:
                                    m["high_risk"] += 1
                                elif "Medium" in record.get("status", ""):
                                    m["medium_risk"] += 1
                                else:
                                    m["compliant"] += 1
                                    
                                progress_val = current_step / total_steps if total_steps > 0 else 1.0
                                progress_bar.progress(progress_val)
                                
                                metric_total.metric("Total Clauses", m["total_clauses"])
                                metric_high.metric("High Risk", f"{m['high_risk']} 🔴")
                                metric_med.metric("Medium Risk", f"{m['medium_risk']} 🟠")
                                metric_compliant.metric("Compliant", f"{m['compliant']} 🟢")
                            
                            metric_total.metric("Total Clauses", 0)
                            metric_high.metric("High Risk", "0 🔴")
                            metric_med.metric("Medium Risk", "0 🟠")
                            metric_compliant.metric("Compliant", "0 🟢")
                            
                            results = run_compliance_audit(
                                retriever=retriever, 
                                user_doc_path=temp_path, 
                                progress_callback=progress_update
                            )
                        
                        # Store in Vault locally
                        st.session_state.audit_results = results
                        
                        # Generate PDF Directly into Data Store
                        returned_pdf_path = generate_report(report_data=st.session_state.audit_results, output_pdf_path=SESSION_PDF)
                        
                        if returned_pdf_path and os.path.exists(returned_pdf_path):
                            with open(returned_pdf_path, "rb") as pdf_file:
                                st.session_state.pdf_bytes = pdf_file.read()
                        
                        # Deduct credit and mark complete
                        st.session_state.credits -= 1
                        st.session_state.audit_complete = True
                        
                        # --- DISK PERSISTENCE SAVE ---
                        cache_data = {
                            "audit_complete": st.session_state.audit_complete,
                            "audit_results": st.session_state.audit_results,
                            "last_filename": st.session_state.last_filename,
                            "metrics": st.session_state.metrics,
                            "pdf_path": SESSION_PDF
                        }
                        
                        try:
                            with open(SESSION_CACHE, 'w', encoding='utf-8') as f:
                                json.dump(cache_data, f, indent=4)
                        except Exception as e:
                            print(f"Failed to persist cache: {e}")

                        st.success(f"Audit Successful! 1 Credit deducted. Remaining Balance: {st.session_state.credits} Credits")
                        
                        # Rerun to update UI explicitly 
                        st.rerun()

                    finally:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
            else:
                st.warning("You do not have enough credits to run an audit. Please Top Up.")

elif st.session_state.current_page == "settings":
    st.header("⚙️ System Configuration")
    st.markdown("Manage your LexGuard AI preferences and session data here.")
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Global Settings")
        st.text_input("User Name / Organization", placeholder="e.g. Acme Corp Legal")
        st.toggle("Advanced Analysis Mode", value=False, help="Enable deeper semantic indexing for complex legal constructs.")
        
    with col2:
        st.subheader("Data & Privacy")
        st.markdown("**Privacy First: This auditor runs on a private local server. Your legal documents are never sent to OpenAI or third-party cloud LLMs.**")
        st.info("Your data is processed locally. Check 'data_store' for the active Session Cache.")
        
        if st.button("🗑️ Reset Session", type="primary"):
            clear_session_cache()
            st.session_state.audit_complete = False
            st.session_state.audit_results = None
            st.session_state.pdf_bytes = None
            st.session_state.last_filename = None
            st.session_state.metrics = {"total_clauses": 0, "high_risk": 0, "medium_risk": 0, "compliant": 0}
            st.success("Session reset successfully! Data Store wiped.")
            st.rerun()
