# tests/fixtures/data_stubs.py
"""
In-memory test doubles for profile and community CRUD.

Moved here from ``src/db/data_stubs.py`` so the always-True ``is_admin``
stub is no longer importable from production code.  Use the real
implementations in ``src.db.supabase_profiles`` and ``src.db.supabase_admin``
for production.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# --- Configuration ---
current_user_id = "test-user"

# In-memory stores
_TEST_PROFILES: Dict[str, Dict[str, Any]] = {}
_TEST_COMMUNITY: Dict[str, Dict[str, Any]] = {}


# --- User Profile DB Test Doubles ---

def save_user_profile_db(user_id: str, name: str, payload: Dict[str, Any]) -> None:
    users = _TEST_PROFILES.setdefault(user_id, {})
    users[name] = payload.copy()


def load_user_profiles_db(user_id: str) -> Dict[str, Any]:
    return _TEST_PROFILES.get(user_id, {}).copy()


def delete_user_profile_db(user_id: str, name: str) -> None:
    if user_id in _TEST_PROFILES and name in _TEST_PROFILES[user_id]:
        del _TEST_PROFILES[user_id][name]


# --- Community DB Test Doubles ---

def community_save(profile_name: str, payload: Dict[str, Any], submitted_by: Optional[str] = None) -> str:
    new_id = f"comm_{len(_TEST_COMMUNITY) + 1}"
    _TEST_COMMUNITY[new_id] = {
        "id": new_id,
        "profile_name": profile_name,
        "payload": payload.copy(),
        "submitted_by": submitted_by or current_user_id,
    }
    return new_id


def community_list(limit: int = 100) -> List[Dict[str, Any]]:
    return list(_TEST_COMMUNITY.values())[:limit]


def community_get(comm_id: str) -> Optional[Dict[str, Any]]:
    return _TEST_COMMUNITY.get(comm_id)


community_load = community_get


def community_delete(comm_id: str) -> None:
    _TEST_COMMUNITY.pop(comm_id, None)


def is_admin(user_id: str) -> bool:
    """Stub — always returns True. ONLY for tests."""
    return True
