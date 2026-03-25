# config.py
"""
Framework-agnostic secret / configuration reader.

Priority order for get_secret(section, key):
  1. Environment variable  (flattened:  SECTION_KEY,  e.g. SUPABASE_URL)
  2. Streamlit st.secrets[section][key]  (only when Streamlit is importable
     and the key exists)

This lets both Streamlit and NiceGUI share the same credential source
without either framework being a hard dependency.
"""
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

# Load .env file (if present) into os.environ.  Existing env vars take
# precedence — load_dotenv(override=False) is the default.
load_dotenv()

# ---------------------------------------------------------------------------
# Env-var name mapping
# ---------------------------------------------------------------------------
# Maps (section, key) → env-var name.  If a pair isn't listed here, the
# fallback is  f"{section}_{key}".upper()  (e.g. ("supabase", "url") → SUPABASE_URL).
_ENV_OVERRIDES: dict[tuple[str, str], str] = {
    ("supabase", "key"):  "SUPABASE_KEY",       # also accept SUPABASE_ANON_KEY below
    ("auth", "redirect_url"): "AUTH_REDIRECT_URL",
    ("openrouter", "api_key"): "OPENROUTER_API_KEY",
    ("opencage", "api_key"):  "OPENCAGE_API_KEY",
}


def _env_var_name(section: str, key: str) -> str:
    """Return the canonical env-var name for a (section, key) pair."""
    return _ENV_OVERRIDES.get((section.lower(), key.lower()),
                              f"{section}_{key}".upper())


def get_secret(section: str, key: str, default: Optional[str] = None) -> Optional[str]:
    """Return the secret value for *section*/*key*, or *default*.

    Lookup order:
      1. os.environ[<canonical env-var name>]
      2. os.environ[<alternate env-var name>]   (e.g. SUPABASE_ANON_KEY)
      3. st.secrets[section][key]               (Streamlit fallback)
      4. *default*
    """
    env_name = _env_var_name(section, key)

    # 1. Primary env var
    value = os.environ.get(env_name)
    if value:
        return value

    # 2. Common alternates  (only for known aliases)
    if (section.lower(), key.lower()) == ("supabase", "key"):
        value = os.environ.get("SUPABASE_ANON_KEY")
        if value:
            return value

    # 3. Streamlit fallback (import lazily so NiceGUI never pulls it in)
    try:
        import streamlit as st  # noqa: F811
        sec = st.secrets.get(section)
        if sec is not None:
            val = sec.get(key) if hasattr(sec, "get") else None
            if val:
                return val
        # Also try top-level key (legacy flat layout in secrets.toml)
        val = st.secrets.get(env_name)
        if val:
            return val
    except Exception:
        # Streamlit not installed, not running, or secrets not configured
        pass

    return default
