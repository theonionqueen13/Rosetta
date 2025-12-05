"""Centralized, typed configuration for secrets and API keys."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Mapping

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:  # Streamlit is optional
    import streamlit as st

    _secrets: Mapping[str, Any] = st.secrets
except Exception:  # pragma: no cover - streamlit not always installed
    st = None
    _secrets = {}


_ENV_FIELD_MAP: dict[str, str] = {
    "GOOGLE_API_KEY": "google_api_key",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENCAGE_API_KEY": "opencage_api_key",
    "SUPABASE_URL": "supabase_url",
    "SUPABASE_KEY": "supabase_key",
    "SUPABASE_SERVICE_ROLE_KEY": "supabase_service_role_key",
}


class Settings(BaseSettings):
    """Strongly typed application settings.

    Environment variables take precedence, with optional fallbacks to
    ``.env`` files and ``.streamlit/secrets.toml``.
    """

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    google_api_key: str | None = Field(default=None, env="GOOGLE_API_KEY")
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    opencage_api_key: str | None = Field(default=None, env="OPENCAGE_API_KEY")
    supabase_url: str | None = Field(default=None, env="SUPABASE_URL")
    supabase_key: str | None = Field(default=None, env="SUPABASE_KEY")
    supabase_service_role_key: str | None = Field(
        default=None, env="SUPABASE_SERVICE_ROLE_KEY"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Prefer environment variables, then Streamlit secrets, then .env.
        return (
            init_settings,
            env_settings,
            _streamlit_settings_source,
            dotenv_settings,
            file_secret_settings,
        )

    @property
    def supabase_auth_key(self) -> str | None:
        """Return the most privileged Supabase key available."""

        return self.supabase_service_role_key or self.supabase_key

    def lookup(self, key: str, default: str | None = None) -> str | None:
        """Lookup helper compatible with previous ``get_secret`` usage."""

        field_name = _ENV_FIELD_MAP.get(key.upper())
        if field_name and getattr(self, field_name) is not None:
            return getattr(self, field_name)
        return os.getenv(key, default)


def _streamlit_settings_source() -> dict[str, Any]:
    """Load settings from ``st.secrets`` if available."""

    data: dict[str, Any] = {}
    if not isinstance(_secrets, Mapping):
        return data

    try:
        secrets_mapping = dict(_secrets)
    except Exception:
        return data

    # Flat keys (e.g. st.secrets["GOOGLE_API_KEY"]).
    for env_name, field_name in _ENV_FIELD_MAP.items():
        if env_name in secrets_mapping:
            data[field_name] = secrets_mapping.get(env_name)

    # Nested block (e.g. st.secrets["supabase"].url / .service_role).
    supabase_cfg = secrets_mapping.get("supabase")
    if isinstance(supabase_cfg, Mapping):
        data.setdefault("supabase_url", supabase_cfg.get("url"))
        data.setdefault(
            "supabase_service_role_key",
            supabase_cfg.get("service_role") or supabase_cfg.get("key"),
        )
        data.setdefault("supabase_key", supabase_cfg.get("key"))

    return data


@lru_cache()
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance."""

    return Settings()


def ensure_required_api_keys() -> None:
    """Validate that required API keys are present with helpful guidance."""

    settings = get_settings()
    missing_messages: list[str] = []

    if not settings.google_api_key:
        missing_messages.append(
            "- GOOGLE_API_KEY is required for Gemini. Set it as an environment "
            "variable or add GOOGLE_API_KEY=\"your-key\" to .streamlit/secrets.toml."
        )

    if not settings.supabase_url or not settings.supabase_auth_key:
        missing_messages.append(
            "- SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) are "
            "required for database access. Provide them via environment "
            "variables or under a [supabase] block in .streamlit/secrets.toml."
        )

    if not settings.opencage_api_key:
        missing_messages.append(
            "- OPENCAGE_API_KEY is required for geocoding. Set it as an "
            "environment variable or add OPENCAGE_API_KEY=\"your-key\" to .streamlit/secrets.toml."
        )

    if missing_messages:
        raise RuntimeError(
            "Missing required configuration:\n" + "\n".join(missing_messages)
        )

