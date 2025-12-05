# rosetta/config.py
from __future__ import annotations

import google.generativeai as genai

from rosetta.settings import ensure_required_api_keys, get_settings

# Streamlit is optional; this module should also work in plain Python.
try:
    import streamlit as st

    _cache_resource = st.cache_resource
except Exception:  # pragma: no cover - streamlit not always installed
    st = None

    def _cache_resource(fn):  # type: ignore[return-type]
        return fn


def get_secret(key: str, default: str | None = None) -> str | None:
    """Backward compatible lookup using centralized settings."""

    return get_settings().lookup(key, default=default)


def _get_gemini_api_key() -> str:
    settings = get_settings()
    key = settings.google_api_key
    if not key:
        raise RuntimeError(
            "Missing GOOGLE_API_KEY. Set the environment variable or add "
            "`GOOGLE_API_KEY=your-key` to .streamlit/secrets.toml."
        )
    return key


@_cache_resource
def get_gemini_client() -> None:
    ensure_required_api_keys()
    genai.configure(api_key=_get_gemini_api_key())
    return genai  # module acts as the configured client
