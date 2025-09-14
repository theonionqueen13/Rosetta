# rosetta/profiles.py
from __future__ import annotations

import json
import time
from typing import Dict, List, Optional, Tuple

import bcrypt  # type: ignore

from .db import supa


# ---------- Users ----------

def user_exists(username: str) -> bool:
    sb = supa()
    res = sb.table("users").select("username").eq("username", username).limit(1).execute()
    return bool(res.data)


def create_user(username: str, name: str, email: str, plain_password: str, role: str = "user") -> None:
    sb = supa()
    pw_hash = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()
    sb.table("users").upsert([{
        "username": username,
        "name": name,
        "email": email,
        "pw_hash": pw_hash,
        "role": role
    }]).execute()


def get_user_role(username: str) -> str:
    sb = supa()
    res = sb.table("users").select("role").eq("username", username).limit(1).execute()
    rows = res.data or []
    return rows[0].get("role", "user") if rows else "user"


def is_admin(username: str) -> bool:
    return get_user_role(username) == "admin"


def verify_password(username: str, candidate_password: str) -> bool:
    sb = supa()
    res = sb.table("users").select("pw_hash").eq("username", username).maybe_single().execute()
    if not res.data:
        return False
    stored_hash = res.data["pw_hash"]
    if isinstance(stored_hash, str):
        stored_hash = stored_hash.encode()
    return bcrypt.checkpw(candidate_password.encode(), stored_hash)


def set_password(username: str, new_plain_password: str) -> None:
    sb = supa()
    pw_hash = bcrypt.hashpw(new_plain_password.encode(), bcrypt.gensalt()).decode()
    sb.table("users").update({"pw_hash": pw_hash}).eq("username", username).execute()


def delete_user_account(username: str) -> None:
    sb = supa()
    # clean up related rows if your schema expects it
    sb.table("profiles").delete().eq("user_id", username).execute()
    sb.table("community_profiles").delete().eq("submitted_by", username).execute()
    sb.table("users").delete().eq("username", username).execute()


# ---------- Private Profiles (per-user) ----------

def load_user_profiles_db(user_id: str) -> Dict[str, dict]:
    sb = supa()
    res = sb.table("profiles").select("profile_name,payload").eq("user_id", user_id).execute()
    rows = res.data or []
    out: Dict[str, dict] = {}
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        out[r["profile_name"]] = payload
    return out


def save_user_profile_db(user_id: str, profile_name: str, payload: dict) -> None:
    sb = supa()
    sb.table("profiles").upsert({
        "user_id": user_id,
        "profile_name": profile_name,
        "payload": json.dumps(payload),
    }).execute()


def delete_user_profile_db(user_id: str, profile_name: str) -> None:
    sb = supa()
    sb.table("profiles").delete().eq("user_id", user_id).eq("profile_name", profile_name).execute()


# ---------- Community Profiles (admin-visible dataset) ----------

def community_list(limit: int = 200) -> List[dict]:
    sb = supa()
    res = sb.table("community_profiles").select("*").order("created_at", desc=True).limit(limit).execute()
    rows = res.data or []
    out: List[dict] = []
    for r in rows:
        payload = r["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        r["payload"] = payload
        out.append(r)
    return out


def community_get(pid: int) -> Optional[dict]:
    sb = supa()
    res = sb.table("community_profiles").select("*").eq("id", pid).limit(1).execute()
    rows = res.data or []
    if not rows:
        return None
    row = rows[0]
    if isinstance(row.get("payload"), str):
        row["payload"] = json.loads(row["payload"])
    return row


def community_save(profile_name: str, payload: dict, submitted_by: str) -> int:
    sb = supa()
    # keep your UTC timestamp behavior
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    res = sb.table("community_profiles").insert({
        "profile_name": profile_name,
        "payload": json.dumps(payload),
        "submitted_by": submitted_by,
        "created_at": ts,
        "updated_at": ts,
    }).execute()
    return res.data[0]["id"]


def community_delete(pid: int) -> None:
    sb = supa()
    sb.table("community_profiles").delete().eq("id", pid).execute()