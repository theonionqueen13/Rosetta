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
from typing import Any, Dict
from supabase_client import get_authed_supabase

TABLE = "user_profiles"


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
    return response.data[0]


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
    """
    client = get_authed_supabase()
    response = (
        client.table(TABLE)
        .select("profile_name, payload")
        .eq("user_id", user_id)
        .execute()
    )
    rows = response.data or []
    
    # Organize into groups
    groups_response = (
        client.table("user_profile_groups")
        .select("id, group_name")
        .eq("user_id", user_id)
        .order("group_name")
        .execute()
    )
    groups_data = {row["id"]: row["group_name"] for row in (groups_response.data or [])}
    groups_data["__ungrouped__"] = "Ungrouped"
    
    result = {gid: {"group_name": gname, "profiles": {}} for gid, gname in groups_data.items()}
    
    for row in rows:
        # Extract group_id from payload (optional field)
        gid = row["payload"].get("group_id") if isinstance(row["payload"], dict) else None
        gid = gid or "__ungrouped__"
        if gid not in result:
            result[gid] = {"group_name": "Unknown Group", "profiles": {}}
        result[gid]["profiles"][row["profile_name"]] = row["payload"]
    
    return result
