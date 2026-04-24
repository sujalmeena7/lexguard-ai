import logging
import os
from typing import Optional, Tuple

import streamlit as st
from supabase import Client, create_client

logger = logging.getLogger(__name__)

AUTH_STATE_DEFAULTS = {
    "authenticated": False,
    "user_id": None,
    "user_email": None,
    "auth_access_token": None,
    "_supabase_client_error": None,
}


def init_auth_state() -> None:
    """Ensure auth-related keys exist in Streamlit session state."""
    for key, value in AUTH_STATE_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_supabase_client() -> Optional[Client]:
    """Create or return a cached Supabase client from Streamlit secrets/env vars."""
    supabase_url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
    supabase_anon_key = st.secrets.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_ANON_KEY"))

    if not supabase_url or not supabase_anon_key:
        return None

    st.session_state["_supabase_client_error"] = None

    if "_supabase_client" not in st.session_state:
        try:
            st.session_state["_supabase_client"] = create_client(supabase_url, supabase_anon_key)
        except Exception as exc:
            hint = ""
            if isinstance(supabase_anon_key, str) and supabase_anon_key.startswith("sb_publishable_"):
                hint = (
                    " Detected a publishable key. For this app/client combo, use the JWT anon key "
                    "from Supabase API settings (starts with 'eyJ')."
                )

            st.session_state["_supabase_client_error"] = f"Supabase client init failed: {exc}.{hint}"
            return None

    return st.session_state["_supabase_client"]


def get_supabase_client_error() -> Optional[str]:
    return st.session_state.get("_supabase_client_error")


def sign_up_with_email(email: str, password: str) -> Tuple[bool, str]:
    client = get_supabase_client()
    if client is None:
        return False, get_supabase_client_error() or "Missing SUPABASE_URL or SUPABASE_ANON_KEY in Streamlit secrets."

    try:
        client.auth.sign_up({"email": email, "password": password})
        return True, "Account created. If email confirmation is enabled, verify your inbox before signing in."
    except Exception as exc:
        return False, f"Sign up failed: {exc}"


def sign_in_with_email(email: str, password: str) -> Tuple[bool, str]:
    client = get_supabase_client()
    if client is None:
        return False, get_supabase_client_error() or "Missing SUPABASE_URL or SUPABASE_ANON_KEY in Streamlit secrets."

    try:
        auth_response = client.auth.sign_in_with_password({"email": email, "password": password})
        if not auth_response or not auth_response.user:
            return False, "Login failed. Please check your credentials."

        st.session_state.authenticated = True
        st.session_state.user_id = auth_response.user.id
        st.session_state.user_email = auth_response.user.email
        st.session_state.auth_access_token = (
            auth_response.session.access_token if auth_response.session else None
        )
        return True, "Signed in successfully."
    except Exception as exc:
        return False, f"Sign in failed: {exc}"


def restore_session_from_token() -> bool:
    """Attempt to restore auth state using a previously saved access token."""
    init_auth_state()
    token = st.session_state.get("auth_access_token")
    if not token:
        return False

    client = get_supabase_client()
    if client is None:
        return False

    try:
        user_response = client.auth.get_user(token)
        user = user_response.user
        if user is None:
            return False

        st.session_state.authenticated = True
        st.session_state.user_id = user.id
        st.session_state.user_email = user.email
        return True
    except Exception:
        return False


def sign_out() -> None:
    """Sign out from Supabase and clear all Streamlit session state keys."""
    client = get_supabase_client()
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception as exc:
            logger.warning("Supabase sign-out request failed: %s", exc)

    for key in list(st.session_state.keys()):
        del st.session_state[key]
