import logging
import os
from typing import Optional, Tuple

import streamlit as st
from supabase import Client, create_client
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def _log_event(*args, **kwargs):
    try:
        from database import log_security_event

        # Mask email PII if present in metadata
        if "metadata" in kwargs and isinstance(kwargs["metadata"], dict):
            if "email" in kwargs["metadata"]:
                email = str(kwargs["metadata"]["email"])
                if "@" in email:
                    # Use rsplit to correctly handle multiple '@' (split on the last one)
                    parts = email.rsplit("@", 1)
                    local_part = parts[0]
                    # Securely handle short or empty local parts
                    masked_local = (local_part[0] if local_part else "") + "***"
                    kwargs["metadata"]["email"] = masked_local + "@" + parts[1]

        return log_security_event(*args, **kwargs)
    except Exception:
        pass


def _check_limit(*args, **kwargs):
    try:
        from database import check_rate_limit
        return check_rate_limit(*args, **kwargs)
    except Exception:
        # Fail-closed for security: if we can't check the limit, assume it's reached
        return False
 
 
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
    """Create or return a cached Supabase client.

    Reads SUPABASE_URL and SUPABASE_ANON_KEY from Streamlit secrets first,
    falling back to environment variables. Never embeds credentials in source.
    """
    supabase_url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    supabase_anon_key = (
        st.secrets.get("SUPABASE_ANON_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    )

    if not supabase_url or not supabase_anon_key:
        st.session_state["_supabase_client_error"] = (
            "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY "
            "in .streamlit/secrets.toml (or as environment variables) before "
            "starting the app."
        )
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

    if not _check_limit("SIGNUP_ATTEMPT", limit=3, window_minutes=60):
        return False, "Too many signup attempts. Please try again later."

    try:
        _log_event("SIGNUP_ATTEMPT", metadata={"email": email})
        client.auth.sign_up({"email": email, "password": password})
        return True, "Account created. Please verify your inbox before signing in."
    except Exception as exc:
        _log_event("SIGNUP_FAILURE", severity="WARNING", description=str(exc), metadata={"email": email})
        return False, f"Sign up failed: {exc}"


def sign_in_with_email(email: str, password: str) -> Tuple[bool, str]:
    client = get_supabase_client()
    if client is None:
        return False, get_supabase_client_error() or "Missing SUPABASE_URL or SUPABASE_ANON_KEY in Streamlit secrets."

    if not _check_limit("LOGIN_ATTEMPT", limit=5, window_minutes=15):
        return False, "Too many login attempts. Please try again later."

    try:
        _log_event("LOGIN_ATTEMPT", metadata={"email": email})
        auth_response = client.auth.sign_in_with_password({"email": email, "password": password})
        if not auth_response or not auth_response.user:
            _log_event("LOGIN_FAILURE", severity="WARNING", description="No user in response", metadata={"email": email})
            return False, "Login failed. Please check your credentials."

        user = auth_response.user
        # Strict security: Check email verification
        if not user.email_confirmed_at:
            _log_event("LOGIN_FAILURE", severity="LOW", description="Email not verified", metadata={"email": email, "user_id": user.id})
            return False, "Please verify your email address before signing in."

        st.session_state.authenticated = True
        st.session_state.user_id = user.id
        st.session_state.user_email = user.email
        st.session_state.auth_access_token = (
            auth_response.session.access_token if auth_response.session else None
        )
        _log_event("LOGIN_SUCCESS", user_id=user.id, metadata={"email": email})
        return True, "Signed in successfully."
    except Exception as exc:
        _log_event("LOGIN_FAILURE", severity="WARNING", description=str(exc), metadata={"email": email})
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


def reset_password_request(email: str) -> Tuple[bool, str]:
    """Send a password reset email to the user."""
    client = get_supabase_client()
    if client is None:
        return False, get_supabase_client_error() or "Missing Supabase configuration."

    if not _check_limit("PASSWORD_RESET_REQUEST", limit=3, window_minutes=60):
        return False, "Too many password reset requests. Please try again later."

    try:
        _log_event("PASSWORD_RESET_REQUEST", metadata={"email": email})
        client.auth.reset_password_for_email(email)
        return True, "Password reset email sent. Please check your inbox."
    except Exception as exc:
        _log_event("PASSWORD_RESET_FAILURE", severity="WARNING", description=str(exc), metadata={"email": email})
        return False, f"Failed to send reset email: {exc}"


def update_password(new_password: str) -> Tuple[bool, str]:
    """Update the password for the currently authenticated user (used during reset flow)."""
    client = get_supabase_client()
    if client is None:
        return False, "Missing Supabase configuration."

    try:
        client.auth.update_user({"password": new_password})
        _log_event("PASSWORD_UPDATE_SUCCESS", user_id=st.session_state.get("user_id"))
        return True, "Password updated successfully."
    except Exception as exc:
        _log_event("PASSWORD_UPDATE_FAILURE", severity="WARNING", description=str(exc))
        return False, f"Failed to update password: {exc}"
