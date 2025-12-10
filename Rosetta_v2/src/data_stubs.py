# src/data_stubs.py

from typing import Dict, Any, List, Optional
import os
import streamlit as st

# --- Configuration ---
# This ID is used for testing and should ideally be managed by a proper auth system later.
current_user_id = "test-user"


# In-memory stores used by the stubs (Replaces stubs at top of test_calc_v2.py)
_TEST_PROFILES: Dict[str, Dict[str, Any]] = {}
_TEST_COMMUNITY: Dict[str, Dict[str, Any]] = {}


# --- User Profile DB Functions ---

def save_user_profile_db(user_id: str, name: str, payload: Dict[str, Any]) -> None:
    """Saves a profile payload for a specific user ID."""
    users = _TEST_PROFILES.setdefault(user_id, {})
    users[name] = payload.copy()

def load_user_profiles_db(user_id: str) -> Dict[str, Any]:
    """Loads all profiles for a specific user ID."""
    return _TEST_PROFILES.get(user_id, {}).copy()

def delete_user_profile_db(user_id: str, name: str) -> None:
    """Deletes a specific profile for a user ID."""
    if user_id in _TEST_PROFILES and name in _TEST_PROFILES[user_id]:
        del _TEST_PROFILES[user_id][name]

# --- Community DB Functions ---

def community_save(profile_name: str, payload: Dict[str, Any], submitted_by: Optional[str] = None) -> str:
    """Saves a chart to the community, returning a fake ID."""
    new_id = f"comm_{len(_TEST_COMMUNITY)+1}"
    _TEST_COMMUNITY[new_id] = {
        "id": new_id,
        "profile_name": profile_name,
        "payload": payload.copy(),
        "submitted_by": submitted_by or current_user_id,
    }
    return new_id

def community_list(limit: int = 100) -> List[Dict[str, Any]]:
    """Returns a list of community charts."""
    return list(_TEST_COMMUNITY.values())[:limit]

def community_get(comm_id: str) -> Optional[Dict[str, Any]]:
    """Gets a single community chart by ID."""
    return _TEST_COMMUNITY.get(comm_id)

def community_delete(comm_id: str) -> None:
    """Deletes a community chart by ID."""
    _TEST_COMMUNITY.pop(comm_id, None)

# Back-compat alias if something imports 'community_load'
community_load = community_get

def is_admin(user_id: str) -> bool:
    """Admin check stub."""
    return True