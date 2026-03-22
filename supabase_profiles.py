# supabase_profiles.py
"""
Supabase-backed implementations of the user-profile CRUD functions.

These are drop-in replacements for the in-memory stubs in src/data_stubs.py.
Import these in test_calc_v2.py once the user is authenticated.

Required Supabase table (run the SQL from supabase_setup.sql in the dashboard):
    public.user_profiles (
        id            uuid primary key default gen_random_uuid(),
        user_id       uuid not null references auth.users(id) on delete cascade,
        profile_name  text not null,
        payload       jsonb not null default '{}',
        created_at    timestamptz default now(),
        updated_at    timestamptz default now(),
        unique (user_id, profile_name)
    )

Row-Level Security ensures every user can only read/write their own rows.
"""
from __future__ import annotations
import streamlit as st
from typing import Any, Dict
from supabase_client import get_authed_supabase

TABLE = "user_profiles"


def _clear_profile_caches() -> None:
    """Invalidate all cached profile/group reads after a write."""
    load_user_profiles_db.clear()
    load_user_profile_groups_db.clear()
    load_user_profiles_by_group_db.clear()


def save_user_profile_db(user_id: str, profile_name: str, payload: Dict[str, Any]) -> None:
    """
    Creates or replaces a saved profile in Supabase.
    The combination (user_id, profile_name) is the unique key.
    Raises an exception (with message) if the write fails.
    """
    client = get_authed_supabase()
    response = client.table(TABLE).upsert(
        {
            "user_id":      user_id,
            "profile_name": profile_name,
            "payload":      payload,
        },
        on_conflict="user_id,profile_name",
    ).execute()
    # supabase-py v2 raises APIError on failure, but double-check for
    # silent failures (e.g. RLS blocking the write without raising).
    if hasattr(response, "data") and response.data is not None:
        # A successful upsert returns the upserted row(s).
        # If data is an empty list the RLS policy silently rejected the write.
        if isinstance(response.data, list) and len(response.data) == 0:
            raise RuntimeError(
                f"Profile write was rejected by the database (empty response). "
                f"Check that user_id '{user_id}' matches the logged-in account "
                f"and that Row Level Security allows INSERT/UPDATE on '{TABLE}'."
            )
    _clear_profile_caches()


@st.cache_data(ttl=120, show_spinner=False)
def load_user_profiles_db(user_id: str) -> Dict[str, Any]:
    """
    Returns all saved profiles for the given user as a dict:
        { profile_name: payload_dict, ... }
    Returns an empty dict if the user has no profiles yet.
    """
    client = get_authed_supabase()
    response = (
        client.table(TABLE)
        .select("profile_name, payload")
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    return {row["profile_name"]: row["payload"] for row in rows}


def load_self_profile_db(user_id: str):
    """Return the user's self-PersonProfile dict, or None if not yet created.

    Scans the user's regular profiles for the one whose payload has
    ``relationship_to_querent == "self"``.  No separate hidden record is used.
    Skips any legacy ``__``-prefixed profile names that may still be in the DB.
    Returns the raw payload dict (a PersonProfile.to_dict() output) on
    success, or ``None`` if the user hasn't designated their own chart yet.
    """
    all_profiles = load_user_profiles_db(user_id)
    for name, payload in all_profiles.items():
        if name.startswith("__"):
            continue
        if isinstance(payload, dict) and payload.get("relationship_to_querent") == "self":
            return payload
    return None


def delete_user_profile_db(user_id: str, profile_name: str) -> None:
    """Permanently deletes a single saved profile for the given user."""
    client = get_authed_supabase()
    (
        client.table(TABLE)
        .delete()
        .eq("user_id", user_id)
        .eq("profile_name", profile_name)
        .execute()
    )
    _clear_profile_caches()


def save_user_profile_group_db(user_id: str, group_name: str) -> Dict[str, Any]:
    """
    Creates a new profile group for the user.
    Returns the created group dict with 'id' and 'group_name'.
    Raises an exception if the group already exists or if the write fails.
    """
    client = get_authed_supabase()
    response = client.table("user_profile_groups").insert(
        {
            "user_id": user_id,
            "group_name": group_name,
        }
    ).execute()
    if not response.data or len(response.data) == 0:
        raise RuntimeError(
            f"Could not create group '{group_name}'. "
            f"It may already exist or Row Level Security may be blocking the write."
        )
    _clear_profile_caches()
    return response.data[0]


@st.cache_data(ttl=120, show_spinner=False)
def load_user_profile_groups_db(user_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns all profile groups for the given user as a dict:
        { group_id: {"id": group_id, "group_name": name}, ... }
    Also includes a special key "__ungrouped__" for profiles without a group.
    Returns an empty dict if the user has no groups yet.
    """
    client = get_authed_supabase()
    response = (
        client.table("user_profile_groups")
        .select("id, group_name")
        .eq("user_id", user_id)
        .order("group_name")
        .execute()
    )
    result = {row["id"]: row for row in (response.data or [])}
    # Add a special virtual group for ungrouped profiles
    result["__ungrouped__"] = {"id": "__ungrouped__", "group_name": "Ungrouped"}
    return result


def delete_user_profile_group_db(user_id: str, group_id: str) -> None:
    """
    Permanently deletes a profile group and all profiles in it.
    """
    client = get_authed_supabase()
    (
        client.table("user_profile_groups")
        .delete()
        .eq("user_id", user_id)
        .eq("id", group_id)
        .execute()
    )
    _clear_profile_caches()


@st.cache_data(ttl=120, show_spinner=False)
def load_user_profiles_by_group_db(user_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Returns profiles organized by group:
        {
            group_id: {
                "group_name": "...",
                "profiles": { profile_name: payload_dict, ... }
            },
            ...
        }
    Profiles without a group_id (or with group_id=None) appear under "__ungrouped__".

    Reuses the individually-cached load_user_profiles_db / load_user_profile_groups_db
    so that the heavy Supabase round-trips are shared across call sites.
    """
    # Reuse cached helpers instead of making fresh Supabase calls
    all_profiles = load_user_profiles_db(user_id)
    all_groups = load_user_profile_groups_db(user_id)

    # Build result structure from groups
    groups_data = {gid: gdata.get("group_name", gid) for gid, gdata in all_groups.items()}
    result = {gid: {"group_name": gname, "profiles": {}} for gid, gname in groups_data.items()}

    for name, payload in all_profiles.items():
        # Skip legacy __-prefixed profile names (safety guard)
        if name.startswith("__"):
            continue
        # Support both old-format (top-level group_id) and new-format (group_id inside chart)
        gid = None
        if isinstance(payload, dict):
            gid = payload.get("group_id")
            if gid is None:
                _chart_d = payload.get("chart")
                if isinstance(_chart_d, dict):
                    gid = _chart_d.get("group_id")
        gid = gid or "__ungrouped__"
        if gid not in result:
            result[gid] = {"group_name": "Unknown Group", "profiles": {}}
        result[gid]["profiles"][name] = payload

    return result
