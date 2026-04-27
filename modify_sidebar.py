import sys
import re

def main():
    try:
        with open("app.py", "r", encoding="utf-8") as f:
            code = f.read()
    except FileNotFoundError:
        print("Error: app.py not found.")
        sys.exit(1)

    # 1. Replace render_auth_controls
    # We find the function start and replace everything until the next top-level definition
    fn_start_marker = "def render_auth_controls() -> None:"
    next_fn_marker = "def load_retriever():"
    
    fn_start_idx = code.find(fn_start_marker)
    next_fn_idx = code.find(next_fn_marker)
    
    if fn_start_idx != -1 and next_fn_idx != -1 and next_fn_idx > fn_start_idx:
        new_auth = "def render_auth_controls() -> None:\n    pass\n\n\n"
        code = code[:fn_start_idx] + new_auth + code[next_fn_idx:]
    else:
        print("Warning: Could not identify render_auth_controls block uniquely.")

    # 2. Replace authenticated sidebar block
    start_marker = "# Sidebar content for authenticated users"
    end_marker = 'if st.session_state.current_page == "audit":'
    
    start_idx = code.find(start_marker)
    end_idx = code.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print(f"Error: Could not find markers in app.py (Start: {start_idx}, End: {end_idx})")
        sys.exit(1)

    new_sidebar_content = """# Sidebar content for authenticated users
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

st.markdown(f\"\"\"
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
</style>
\"\"\", unsafe_allow_html=True)

with st.sidebar:
    # Sidebar Header
    st.markdown(
        \"\"\"
        <div style="padding-bottom: 30px; padding-left: 10px;">
            <h2 style="margin: 0; color: white; display: flex; align-items: center; gap: 12px; font-family: 'Cabinet Grotesk', sans-serif;">
                <span style="color: #60a5fa; font-size: 1.4rem;">⚖️</span> LexGuard AI
            </h2>
            <p style="margin: 0; color: #6b7280; font-size: 0.65rem; letter-spacing: 0.15em; font-weight: 700; margin-left: 36px; margin-top: -2px;">LEGAL INTELLIGENCE</p>
        </div>
        \"\"\", unsafe_allow_html=True
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
        st.caption(f"👤 {st.session_state.user_email}")
        if st.session_state.credits < 10:
            st.caption(f"Credits: {st.session_state.credits}/10")
            st.progress(st.session_state.credits / 10.0)
        
        if st.button("Sign Out", use_container_width=True):
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
"""
    
    updated_code = code[:start_idx] + new_sidebar_content + "\n\n" + code[end_idx:]
    
    if updated_code == code:
        print("Error: String replacement produced no change.")
        sys.exit(1)

    with open("app.py", "w", encoding="utf-8") as f:
        f.write(updated_code)
    
    print("Sidebar successfully updated in app.py.")

if __name__ == "__main__":
    main()
