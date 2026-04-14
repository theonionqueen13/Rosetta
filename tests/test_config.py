"""Tests for config.py — secret / configuration reader."""
import os

import pytest

from config import _env_var_name, get_secret


# ═══════════════════════════════════════════════════════════════════════
# _env_var_name
# ═══════════════════════════════════════════════════════════════════════

class TestEnvVarName:
    """Tests for the (section, key) → env-var-name mapping."""

    def test_fallback_pattern(self):
        assert _env_var_name("foo", "bar") == "FOO_BAR"

    def test_case_insensitive(self):
        assert _env_var_name("Foo", "Bar") == "FOO_BAR"

    def test_override_supabase_key(self):
        assert _env_var_name("supabase", "key") == "SUPABASE_KEY"

    def test_override_auth_redirect(self):
        assert _env_var_name("auth", "redirect_url") == "AUTH_REDIRECT_URL"

    def test_override_openrouter(self):
        assert _env_var_name("openrouter", "api_key") == "OPENROUTER_API_KEY"

    def test_override_opencage(self):
        assert _env_var_name("opencage", "api_key") == "OPENCAGE_API_KEY"

    def test_supabase_url_not_overridden(self):
        # ("supabase", "url") is NOT in _ENV_OVERRIDES → fallback
        assert _env_var_name("supabase", "url") == "SUPABASE_URL"

    def test_override_case_insensitive(self):
        assert _env_var_name("Supabase", "Key") == "SUPABASE_KEY"
        assert _env_var_name("OPENCAGE", "API_KEY") == "OPENCAGE_API_KEY"


# ═══════════════════════════════════════════════════════════════════════
# get_secret
# ═══════════════════════════════════════════════════════════════════════

class TestGetSecret:
    """Tests for get_secret() env-var lookup."""

    def test_primary_env_var(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        assert get_secret("supabase", "url") == "https://example.supabase.co"

    def test_default_when_missing(self, monkeypatch):
        monkeypatch.delenv("FOO_BAR", raising=False)
        assert get_secret("foo", "bar") is None

    def test_explicit_default(self, monkeypatch):
        monkeypatch.delenv("FOO_BAR", raising=False)
        assert get_secret("foo", "bar", default="fallback") == "fallback"

    def test_supabase_key_primary(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_KEY", "pk-123")
        monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
        assert get_secret("supabase", "key") == "pk-123"

    def test_supabase_key_anon_fallback(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-456")
        assert get_secret("supabase", "key") == "anon-456"

    def test_supabase_key_primary_wins_over_anon(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_KEY", "pk-primary")
        monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-secondary")
        assert get_secret("supabase", "key") == "pk-primary"

    def test_override_key_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key-789")
        assert get_secret("openrouter", "api_key") == "or-key-789"

    def test_missing_everything_returns_none(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert get_secret("openrouter", "api_key") is None

    def test_empty_string_treated_as_missing(self, monkeypatch):
        """Empty string is falsy — falls through to default."""
        monkeypatch.setenv("FOO_BAR", "")
        assert get_secret("foo", "bar", default="d") == "d"
