# rosetta/profiles.py
from __future__ import annotations
import httpx
import streamlit as st
import json
import time
import bcrypt
from typing import Dict, List, Optional
from .db import supa

# ---------- Users ----------


def user_exists(username: str) -> bool:
    try:
        sb = supa()
        res = (
            sb.table("users")
            .select("username")
            .eq("username", username)
            .limit(1)
            .execute()
        )
        return bool(res.data)
    except httpx.HTTPError:
        st.error("Unable to verify user existence.")
    except Exception:
        st.error("Unexpected error verifying user existence.")
    return False


def create_user(
    username: str, name: str, email: str, plain_password: str, role: str = "user"
) -> None:
    try:
        sb = supa()
        pw_hash = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()
        sb.table("users").upsert(
            [
                {
                    "username": username,
                    "name": name,
                    "email": email,
                    "pw_hash": pw_hash,
                    "role": role,
                }
            ]
        ).execute()
    except httpx.HTTPError:
        st.error("Unable to create user account.")
    except Exception:
        st.error("Unexpected error creating user account.")


def get_user_role(username: str) -> str:
    try:
        sb = supa()
        res = (
            sb.table("users").select("role").eq("username", username).limit(1).execute()
        )
        rows = res.data or []
        return rows[0].get("role", "user") if rows else "user"
    except httpx.HTTPError:
        st.error("Unable to fetch user role.")
    except Exception:
        st.error("Unexpected error fetching user role.")
    return "user"


def is_admin(username: str) -> bool:
    return get_user_role(username) == "admin"


def verify_password(username: str, candidate_password: str) -> bool:
    try:
        sb = supa()
        res = (
            sb.table("users")
            .select("pw_hash")
            .eq("username", username)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return False
        stored_hash = res.data["pw_hash"]
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode()
        return bcrypt.checkpw(candidate_password.encode(), stored_hash)
    except httpx.HTTPError:
        st.error("Unable to verify password.")
    except Exception:
        st.error("Unexpected error verifying password.")
    return False


def set_password(username: str, new_plain_password: str) -> None:
    try:
        sb = supa()
        pw_hash = bcrypt.hashpw(new_plain_password.encode(), bcrypt.gensalt()).decode()
        sb.table("users").update({"pw_hash": pw_hash}).eq(
            "username", username
        ).execute()
    except httpx.HTTPError:
        st.error("Unable to set password.")
    except Exception:
        st.error("Unexpected error setting password.")


def delete_user_account(username: str) -> None:
    try:
        sb = supa()
        # clean up related rows if your schema expects it
        sb.table("profiles").delete().eq("user_id", username).execute()
        sb.table("community_profiles").delete().eq("submitted_by", username).execute()
        sb.table("users").delete().eq("username", username).execute()
    except httpx.HTTPError:
        st.error("Unable to delete user account.")
    except Exception:
        st.error("Unexpected error deleting user account.")


# ---------- Private Profiles (per-user) ----------
def load_user_profiles_db(user_id: str) -> Dict[str, dict]:
    try:
        sb = supa()
        res = (
            sb.table("profiles")
            .select("profile_name,payload")
            .eq("user_id", user_id)
            .execute()
        )
        rows = res.data or []
        out: Dict[str, dict] = {}
        for r in rows:
            payload = r["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            out[r["profile_name"]] = payload
        return out
    except httpx.HTTPError:
        st.error("Unable to load user profiles.")
    except Exception:
        st.error("Unexpected error loading user profiles.")
    return {}


def save_user_profile_db(user_id: str, profile_name: str, payload: dict) -> None:
    try:
        sb = supa()
        sb.table("profiles").upsert(
            {
                "user_id": user_id,
                "profile_name": profile_name,
                "payload": json.dumps(payload),
            }
        ).execute()
    except httpx.HTTPError:
        st.error("Unable to save user profile.")
    except Exception:
        st.error("Unexpected error saving user profile.")


def delete_user_profile_db(user_id: str, profile_name: str) -> None:
    try:
        sb = supa()
        sb.table("profiles").delete().eq("user_id", user_id).eq(
            "profile_name", profile_name
        ).execute()
    except httpx.HTTPError:
        st.error("Unable to delete user profile.")
    except Exception:
        st.error("Unexpected error deleting user profile.")


# ---------- Community Profiles (admin-visible dataset) ----------
def community_list(limit: int = 200) -> List[dict]:
    try:
        sb = supa()
        res = (
            sb.table("community_profiles")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = res.data or []
        out: List[dict] = []
        for r in rows:
            payload = r["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            r["payload"] = payload
            out.append(r)
        return out
    except httpx.HTTPError:
        st.error("Unable to load community profiles.")
    except Exception:
        st.error("Unexpected error loading community profiles.")
    return []


def community_get(pid: int) -> Optional[dict]:
    try:
        sb = supa()
        res = (
            sb.table("community_profiles").select("*").eq("id", pid).limit(1).execute()
        )
        rows = res.data or []
        if not rows:
            return None
        row = rows[0]
        if isinstance(row.get("payload"), str):
            row["payload"] = json.loads(row["payload"])
        return row
    except httpx.HTTPError:
        st.error("Unable to fetch community profile.")
    except Exception:
        st.error("Unexpected error fetching community profile.")
    return None


def community_save(profile_name: str, payload: dict, submitted_by: str) -> int:
    try:
        sb = supa()
        # keep your UTC timestamp behavior
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        res = (
            sb.table("community_profiles")
            .insert(
                {
                    "profile_name": profile_name,
                    "payload": json.dumps(payload),
                    "submitted_by": submitted_by,
                    "created_at": ts,
                    "updated_at": ts,
                }
            )
            .execute()
        )
        return res.data[0]["id"]
    except httpx.HTTPError:
        st.error("Unable to save community profile.")
    except Exception:
        st.error("Unexpected error saving community profile.")
    return -1


def community_delete(pid: int) -> None:
    try:
        sb = supa()
        sb.table("community_profiles").delete().eq("id", pid).execute()
    except httpx.HTTPError:
        st.error("Unable to delete community profile.")
    except Exception:
        st.error("Unexpected error deleting community profile.")
