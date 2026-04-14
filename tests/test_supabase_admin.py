"""Tests for src.db.supabase_admin — admin checks with mocked Supabase."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


MODULE = "src.db.supabase_admin"


@pytest.fixture()
def _mock_deps():
    """Patch all external dependencies for supabase_admin."""
    client = MagicMock(name="SupabaseClient")
    builder = client.table.return_value
    for method in ("select", "eq"):
        getattr(builder, method).return_value = builder
    builder.execute.return_value = MagicMock(data=[])

    patches = {
        "client": patch(f"{MODULE}.get_authed_supabase", return_value=client),
        "uid": patch(f"{MODULE}.get_current_user_id", return_value="user-123"),
        "email": patch(f"{MODULE}.get_current_user_email", return_value="admin@example.com"),
    }
    mocks = {}
    for key, p in patches.items():
        mocks[key] = p.start()
    mocks["_client_instance"] = client
    yield mocks
    for p in patches.values():
        p.stop()


# ---------------------------------------------------------------------------
# is_admin
# ---------------------------------------------------------------------------
class TestIsAdmin:
    def test_true_when_row_exists(self, _mock_deps):
        from src.db.supabase_admin import is_admin

        builder = _mock_deps["_client_instance"].table.return_value
        builder.execute.return_value = MagicMock(data=[{"user_id": "user-123"}])

        assert is_admin("user-123") is True

    def test_false_when_no_rows(self, _mock_deps):
        from src.db.supabase_admin import is_admin

        builder = _mock_deps["_client_instance"].table.return_value
        builder.execute.return_value = MagicMock(data=[])

        assert is_admin("user-123") is False

    def test_false_on_exception(self, _mock_deps):
        from src.db.supabase_admin import is_admin

        _mock_deps["_client_instance"].table.side_effect = Exception("boom")

        assert is_admin("user-123") is False

    def test_false_when_no_user_id(self, _mock_deps):
        from src.db.supabase_admin import is_admin

        _mock_deps["uid"].return_value = None

        # Call without explicit user_id → resolves via get_current_user_id
        assert is_admin() is False

    def test_uses_get_current_user_id_when_none(self, _mock_deps):
        from src.db.supabase_admin import is_admin

        builder = _mock_deps["_client_instance"].table.return_value
        builder.execute.return_value = MagicMock(data=[{"user_id": "user-123"}])

        result = is_admin()  # user_id=None, resolves from mock
        assert result is True


# ---------------------------------------------------------------------------
# get_admin_email
# ---------------------------------------------------------------------------
class TestGetAdminEmail:
    def test_returns_email_when_admin(self, _mock_deps):
        from src.db.supabase_admin import get_admin_email

        builder = _mock_deps["_client_instance"].table.return_value
        builder.execute.return_value = MagicMock(data=[{"user_id": "user-123"}])

        assert get_admin_email() == "admin@example.com"

    def test_returns_none_when_not_admin(self, _mock_deps):
        from src.db.supabase_admin import get_admin_email

        builder = _mock_deps["_client_instance"].table.return_value
        builder.execute.return_value = MagicMock(data=[])

        assert get_admin_email() is None

    def test_returns_none_when_no_session(self, _mock_deps):
        from src.db.supabase_admin import get_admin_email

        _mock_deps["uid"].return_value = None

        assert get_admin_email() is None
