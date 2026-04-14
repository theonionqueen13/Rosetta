"""Tests for src.db.supabase_profiles — profile CRUD with mocked Supabase."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


MODULE = "src.db.supabase_profiles"


@pytest.fixture()
def _mock_client():
    """Patch get_authed_supabase and return the mock client."""
    client = MagicMock(name="SupabaseClient")
    builder = client.table.return_value
    for method in ("upsert", "select", "delete", "insert", "update",
                    "eq", "neq", "order", "limit"):
        getattr(builder, method).return_value = builder
    builder.execute.return_value = MagicMock(data=[])
    with patch(f"{MODULE}.get_authed_supabase", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# save_user_profile_db
# ---------------------------------------------------------------------------
class TestSaveUserProfileDb:
    def test_calls_upsert(self, _mock_client):
        from src.db.supabase_profiles import save_user_profile_db

        # Make upsert return a row (success)
        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[{"user_id": "u1"}])

        save_user_profile_db("u1", "Alice", {"year": 1990})

        _mock_client.table.assert_called_with("user_profiles")
        builder.upsert.assert_called_once()
        call_args = builder.upsert.call_args
        row = call_args[0][0]
        assert row["user_id"] == "u1"
        assert row["profile_name"] == "Alice"
        assert row["payload"] == {"year": 1990}

    def test_rls_rejection_raises(self, _mock_client):
        from src.db.supabase_profiles import save_user_profile_db

        # Simulate empty response (RLS blocked write)
        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[])

        with pytest.raises(RuntimeError, match="rejected"):
            save_user_profile_db("u1", "Alice", {"year": 1990})


# ---------------------------------------------------------------------------
# load_user_profiles_db
# ---------------------------------------------------------------------------
class TestLoadUserProfilesDb:
    def test_returns_dict(self, _mock_client):
        from src.db.supabase_profiles import load_user_profiles_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[
            {"profile_name": "Alice", "payload": {"year": 1990}},
            {"profile_name": "Bob", "payload": {"year": 1985}},
        ])

        result = load_user_profiles_db("u1")
        assert result == {"Alice": {"year": 1990}, "Bob": {"year": 1985}}

    def test_empty_profiles(self, _mock_client):
        from src.db.supabase_profiles import load_user_profiles_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[])

        result = load_user_profiles_db("u1")
        assert result == {}

    def test_caches_result(self, _mock_client):
        from src.db.supabase_profiles import load_user_profiles_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[
            {"profile_name": "A", "payload": {}},
        ])

        load_user_profiles_db("u1")
        load_user_profiles_db("u1")
        # Second call should hit cache — only one execute call
        assert builder.execute.call_count == 1

    def test_retry_on_failure(self, _mock_client):
        from src.db.supabase_profiles import load_user_profiles_db

        builder = _mock_client.table.return_value
        # First call raises, second succeeds
        builder.execute.side_effect = [
            Exception("transport error"),
            MagicMock(data=[{"profile_name": "A", "payload": {}}]),
        ]

        with patch("src.db.supabase_client.reset_authed_client_state"):
            result = load_user_profiles_db("u1")
        assert result == {"A": {}}


# ---------------------------------------------------------------------------
# load_self_profile_db
# ---------------------------------------------------------------------------
class TestLoadSelfProfileDb:
    def test_finds_self(self, _mock_client):
        from src.db.supabase_profiles import load_self_profile_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[
            {"profile_name": "Me", "payload": {"relationship_to_querent": "self", "year": 1990}},
            {"profile_name": "Friend", "payload": {"relationship_to_querent": "friend"}},
        ])

        result = load_self_profile_db("u1")
        assert result is not None
        assert result["relationship_to_querent"] == "self"

    def test_returns_none_when_no_self(self, _mock_client):
        from src.db.supabase_profiles import load_self_profile_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[
            {"profile_name": "Friend", "payload": {"relationship_to_querent": "friend"}},
        ])

        result = load_self_profile_db("u1")
        assert result is None


# ---------------------------------------------------------------------------
# delete_user_profile_db
# ---------------------------------------------------------------------------
class TestDeleteUserProfileDb:
    def test_calls_delete_chain(self, _mock_client):
        from src.db.supabase_profiles import delete_user_profile_db

        delete_user_profile_db("u1", "Alice")

        _mock_client.table.assert_called_with("user_profiles")
        builder = _mock_client.table.return_value
        builder.delete.assert_called_once()


# ---------------------------------------------------------------------------
# save_user_profile_group_db
# ---------------------------------------------------------------------------
class TestSaveUserProfileGroupDb:
    def test_returns_created_group(self, _mock_client):
        from src.db.supabase_profiles import save_user_profile_group_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[
            {"id": "g1", "group_name": "Family"},
        ])

        result = save_user_profile_group_db("u1", "Family")
        assert result == {"id": "g1", "group_name": "Family"}

    def test_raises_on_empty_response(self, _mock_client):
        from src.db.supabase_profiles import save_user_profile_group_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[])

        with pytest.raises(RuntimeError, match="Could not create"):
            save_user_profile_group_db("u1", "Dup")


# ---------------------------------------------------------------------------
# load_user_profile_groups_db
# ---------------------------------------------------------------------------
class TestLoadUserProfileGroupsDb:
    def test_includes_ungrouped(self, _mock_client):
        from src.db.supabase_profiles import load_user_profile_groups_db

        builder = _mock_client.table.return_value
        builder.execute.return_value = MagicMock(data=[
            {"id": "g1", "group_name": "Work"},
        ])

        result = load_user_profile_groups_db("u1")
        assert "__ungrouped__" in result
        assert "g1" in result
        assert result["g1"]["group_name"] == "Work"


# ---------------------------------------------------------------------------
# delete_user_profile_group_db
# ---------------------------------------------------------------------------
class TestDeleteUserProfileGroupDb:
    def test_calls_delete(self, _mock_client):
        from src.db.supabase_profiles import delete_user_profile_group_db

        delete_user_profile_group_db("u1", "g1")

        _mock_client.table.assert_called_with("user_profile_groups")
        builder = _mock_client.table.return_value
        builder.delete.assert_called_once()


# ---------------------------------------------------------------------------
# load_user_profiles_by_group_db
# ---------------------------------------------------------------------------
class TestLoadUserProfilesByGroupDb:
    def test_organizes_profiles(self, _mock_client):
        from src.db.supabase_profiles import load_user_profiles_by_group_db

        builder = _mock_client.table.return_value
        # Two calls: first for profiles, second for groups
        # We need to configure execute to return different data depending on context.
        # Because of caching, we need to do this carefully.
        profiles_data = [
            {"profile_name": "Alice", "payload": {"group_id": "g1", "year": 1990}},
            {"profile_name": "Bob", "payload": {"year": 1985}},  # no group → ungrouped
        ]
        groups_data = [
            {"id": "g1", "group_name": "Family"},
        ]

        # The function internally calls load_user_profiles_db then load_user_profile_groups_db.
        # Both use the same mock chain. We sequence the responses.
        builder.execute.side_effect = [
            MagicMock(data=profiles_data),
            MagicMock(data=groups_data),
        ]

        result = load_user_profiles_by_group_db("u1")
        assert "g1" in result
        assert "__ungrouped__" in result
        assert "Alice" in result["g1"]["profiles"]
        assert "Bob" in result["__ungrouped__"]["profiles"]
