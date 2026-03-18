# supabase_admin.py
"""Admin utilities for Supabase-authenticated users."""
import streamlit as st
from supabase_client import get_authed_supabase

TABLE = "user_admins"


def is_admin(user_id: str = None) -> bool:
    """Returns True if the current user is in the admin table.
    
    If user_id is not provided, uses the session state value.
    """
    if user_id is None:
        user_id = st.session_state.get("supabase_user_id")
    if not user_id:
        return False
    try:
        client = get_authed_supabase()
        resp = client.table(TABLE).select("user_id").eq("user_id", user_id).execute()
        return bool(resp.data and len(resp.data) > 0)
    except Exception:
        return False


def get_admin_email() -> str | None:
    """Get the email address of the currently logged-in admin user.
    
    Returns the email if the user is an admin, otherwise None.
    """
    user_id = st.session_state.get("supabase_user_id")
    if not user_id:
        return None
    if not is_admin(user_id):
        return None
    return st.session_state.get("supabase_user_email")
