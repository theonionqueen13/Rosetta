"""Tests for src.ui.auth — session helpers with mocked Supabase + NiceGUI."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MODULE = "src.ui.auth"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def storage():
    """Provide a plain dict standing in for app.storage.user."""
    return {}


@pytest.fixture()
def _patch_app(storage):
    """Patch nicegui.app so auth helpers see our dict as app.storage.user."""
    mock_app = MagicMock(name="nicegui_app")
    mock_app.storage.user = storage
    with patch(f"{MODULE}.app", mock_app):
        yield mock_app


@pytest.fixture()
def mock_sb():
    """Patch get_supabase() and return the mock client."""
    client = MagicMock(name="SupabaseClient")
    with patch(f"{MODULE}.get_supabase", return_value=client):
        yield client


# ---------------------------------------------------------------------------
# Helper — build a fake auth_response
# ---------------------------------------------------------------------------

def _make_auth_response(uid="user-123", email="a@b.com",
                        access_token="tok-a", refresh_token="tok-r",
                        expires_at=None):
    resp = MagicMock(name="AuthResponse")
    resp.session.access_token = access_token
    resp.session.refresh_token = refresh_token
    resp.session.expires_at = expires_at or int(time.time()) + 3600
    resp.user.id = uid
    resp.user.email = email
    return resp


# ===================================================================
# store_session_nicegui
# ===================================================================

class TestStoreSessionNicegui:
    def test_stores_session_data(self, _patch_app, storage):
        from src.ui.auth import store_session_nicegui
        resp = _make_auth_response()
        uid = store_session_nicegui(resp)

        assert uid == "user-123"
        assert storage["supabase_user_id"] == "user-123"
        assert storage["supabase_user_email"] == "a@b.com"
        assert storage["supabase_session"]["access_token"] == "tok-a"
        assert storage["supabase_session"]["refresh_token"] == "tok-r"

    def test_returns_user_id_as_string(self, _patch_app, storage):
        from src.ui.auth import store_session_nicegui
        resp = _make_auth_response(uid=42)
        uid = store_session_nicegui(resp)
        assert uid == "42"
        assert isinstance(uid, str)

    def test_overwrites_previous_session(self, _patch_app, storage):
        from src.ui.auth import store_session_nicegui
        storage["supabase_user_id"] = "old-id"
        resp = _make_auth_response(uid="new-id")
        store_session_nicegui(resp)
        assert storage["supabase_user_id"] == "new-id"


# ===================================================================
# clear_session
# ===================================================================

class TestClearSession:
    def test_removes_auth_keys(self, _patch_app, storage, mock_sb):
        from src.ui.auth import clear_session
        storage.update({
            "supabase_session": {"access_token": "x"},
            "supabase_user_id": "u1",
            "supabase_user_email": "a@b.com",
            "other_key": "keep",
        })
        clear_session()

        assert "supabase_session" not in storage
        assert "supabase_user_id" not in storage
        assert "supabase_user_email" not in storage
        assert storage["other_key"] == "keep"

    def test_empty_storage_noop(self, _patch_app, storage, mock_sb):
        from src.ui.auth import clear_session
        clear_session()  # should not raise

    def test_calls_sign_out(self, _patch_app, storage, mock_sb):
        from src.ui.auth import clear_session
        clear_session()
        mock_sb.auth.sign_out.assert_called_once()

    def test_sign_out_failure_still_clears(self, _patch_app, storage, mock_sb):
        from src.ui.auth import clear_session
        mock_sb.auth.sign_out.side_effect = RuntimeError("network")
        storage["supabase_user_id"] = "u1"
        clear_session()
        assert "supabase_user_id" not in storage


# ===================================================================
# get_user_id
# ===================================================================

class TestGetUserId:
    def test_returns_uid_when_present(self, _patch_app, storage):
        from src.ui.auth import get_user_id
        storage["supabase_user_id"] = "uid-abc"
        assert get_user_id() == "uid-abc"

    def test_returns_none_when_missing(self, _patch_app, storage):
        from src.ui.auth import get_user_id
        assert get_user_id() is None


# ===================================================================
# session_is_expired
# ===================================================================

class TestSessionIsExpired:
    def test_no_session_is_expired(self, _patch_app, storage):
        from src.ui.auth import session_is_expired
        assert session_is_expired() is True

    def test_future_expiry_not_expired(self, _patch_app, storage):
        from src.ui.auth import session_is_expired
        storage["supabase_session"] = {"expires_at": int(time.time()) + 3600}
        assert session_is_expired() is False

    def test_past_expiry_is_expired(self, _patch_app, storage):
        from src.ui.auth import session_is_expired
        storage["supabase_session"] = {"expires_at": int(time.time()) - 100}
        assert session_is_expired() is True

    def test_missing_expires_at_is_expired(self, _patch_app, storage):
        from src.ui.auth import session_is_expired
        storage["supabase_session"] = {}
        assert session_is_expired() is True

    def test_within_60s_buffer_is_expired(self, _patch_app, storage):
        from src.ui.auth import session_is_expired
        # expires_at exactly 30s from now → within 60s buffer → expired
        storage["supabase_session"] = {"expires_at": int(time.time()) + 30}
        assert session_is_expired() is True


# ===================================================================
# try_refresh_session
# ===================================================================

class TestTryRefreshSession:
    def test_success(self, _patch_app, storage, mock_sb):
        from src.ui.auth import try_refresh_session
        storage["supabase_session"] = {
            "access_token": "old", "refresh_token": "rt-1", "expires_at": 0,
        }
        new_resp = _make_auth_response(uid="u1", access_token="new-tok")
        mock_sb.auth.refresh_session.return_value = new_resp
        assert try_refresh_session() is True
        assert storage["supabase_session"]["access_token"] == "new-tok"

    def test_no_refresh_token_returns_false(self, _patch_app, storage, mock_sb):
        from src.ui.auth import try_refresh_session
        storage["supabase_session"] = {"access_token": "x"}
        assert try_refresh_session() is False
        mock_sb.auth.refresh_session.assert_not_called()

    def test_no_session_returns_false(self, _patch_app, storage, mock_sb):
        from src.ui.auth import try_refresh_session
        assert try_refresh_session() is False

    def test_refresh_exception_returns_false(self, _patch_app, storage, mock_sb):
        from src.ui.auth import try_refresh_session
        storage["supabase_session"] = {"refresh_token": "rt-1"}
        mock_sb.auth.refresh_session.side_effect = RuntimeError("network error")
        assert try_refresh_session() is False

    def test_refresh_returns_none_session(self, _patch_app, storage, mock_sb):
        from src.ui.auth import try_refresh_session
        storage["supabase_session"] = {"refresh_token": "rt-1"}
        resp = MagicMock()
        resp.session = None
        mock_sb.auth.refresh_session.return_value = resp
        assert try_refresh_session() is False


# ===================================================================
# do_logout
# ===================================================================

class TestDoLogout:
    async def test_clears_and_navigates(self, _patch_app, storage, mock_sb):
        from src.ui.auth import do_logout
        storage["supabase_user_id"] = "u1"

        with patch(f"{MODULE}.ui") as mock_ui:
            mock_ui.navigate = MagicMock()
            await do_logout()

        assert "supabase_user_id" not in storage
        mock_ui.navigate.to.assert_called_once_with("/login")

    async def test_logout_when_already_logged_out(self, _patch_app, storage, mock_sb):
        from src.ui.auth import do_logout
        with patch(f"{MODULE}.ui") as mock_ui:
            mock_ui.navigate = MagicMock()
            await do_logout()  # should not raise
        mock_ui.navigate.to.assert_called_once_with("/login")
