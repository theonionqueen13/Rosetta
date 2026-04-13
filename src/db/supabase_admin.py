# supabase_admin.py
"""Admin utilities for Supabase-authenticated users.

Framework-agnostic: reads user identity from NiceGUI ``app.storage.user`` via helpers in
``supabase_client``.  No direct ``streamlit`` import.
"""
from .supabase_client import get_authed_supabase, get_current_user_id, get_current_user_email

TABLE = "user_admins"


def is_admin(user_id: str = None) -> bool:
    """Return True if *user_id* (or the currently logged-in user) is an admin.

    If *user_id* is not provided, it is resolved from the active framework's
    session storage via ``get_current_user_id()``.
    """
    if user_id is None:
        user_id = get_current_user_id()
    if not user_id:
        return False
    try:
        client = get_authed_supabase()
        resp = client.table(TABLE).select("user_id").eq("user_id", user_id).execute()
        return bool(resp.data and len(resp.data) > 0)
    except Exception:
        return False


def get_admin_email() -> str | None:
    """Return the email of the currently logged-in user if they are an admin.

    Returns ``None`` if there is no active session or the user is not an admin.
    """
    user_id = get_current_user_id()
    if not user_id:
        return None
    if not is_admin(user_id):
        return None
    return get_current_user_email()
