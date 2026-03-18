# supabase_admin.py
"""Admin utilities for Supabase-authenticated users."""
from supabase_client import get_authed_supabase

TABLE = "user_admins"


def is_admin(user_id: str) -> bool:
    """Returns True if the current user is in the admin table."""
    if not user_id:
        return False
    client = get_authed_supabase()
    resp = client.table(TABLE).select("user_id").eq("user_id", user_id).execute()
    return bool(resp.data and len(resp.data) > 0)
