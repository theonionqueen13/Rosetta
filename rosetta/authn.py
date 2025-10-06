# rosetta/authn.py
from __future__ import annotations
import streamlit as st
from rosetta.db import supa


def get_auth_credentials() -> dict:
    """
    Return the dict structure streamlit_authenticator expects.
    """
    sb = supa()
    res = sb.table("users").select("username,name,email,pw_hash").execute()
    users = res.data or []
    return {
        "usernames": {
            u["username"]: {
                "name": u["name"],
                "email": u["email"],
                "password": u["pw_hash"],  # bcrypt hash
            }
            for u in users
        }
    }


@st.cache_data(ttl=60)
def get_user_role_cached(username: str) -> str:
    # 👉 lazy import to avoid circular import and ensure symbol exists in scope
    from rosetta.users import get_user_role as _get_user_role

    return _get_user_role(username)


@st.cache_data(ttl=60)
def is_admin_cached(username: str) -> bool:
    # 👉 lazy import here too
    from rosetta.users import is_admin as _is_admin

    return _is_admin(username)


def ensure_user_row_linked(
    current_user_id: str, creds: dict, display_name: str | None = None
) -> tuple[bool, str]:
    sb = supa()
    exists = (
        sb.table("users")
        .select("username")
        .eq("username", current_user_id)
        .limit(1)
        .execute()
    )
    if exists.data:
        return True, ""

    rec = (creds or {}).get("usernames", {}).get(current_user_id, {})
    pw_hash = rec.get("password")
    if not pw_hash:
        return False, (
            "This login exists in authenticator, but no password hash was found in creds. "
            "Add it via Admin → User Management once, or migrate your creds loader."
        )

    sb.table("users").insert(
        {
            "username": current_user_id,
            "name": rec.get("name") or display_name or current_user_id,
            "email": rec.get("email") or f"{current_user_id}@local",
            "pw_hash": pw_hash,  # use existing hash, no password change
            "role": rec.get("role") or "user",
        }
    ).execute()
    return (
        True,
        f"Linked '{current_user_id}' to DB users (no password change). Reloading…",
    )
