# rosetta/config.py
from __future__ import annotations
import os
import google.generativeai as genai

# Streamlit is optional; this module should also work in plain Python.
try:
    import streamlit as st
    _cache_resource = st.cache_resource
    _secrets = st.secrets
except Exception:
    st = None
    _secrets = {}
    def _cache_resource(fn):  # no-op fallback
        return fn

def get_secret(key: str, default: str | None = None) -> str | None:
    """
    Resolve a secret from environment first, then Streamlit secrets.
    Example keys: "OPENAI_API_KEY", "OPENCAGE_API_KEY"
    """
    val = os.getenv(key)
    if val:
        return val
    try:
        # allow both flat and nested secrets.toml usage
        if isinstance(_secrets, dict) and key in _secrets:
            return _secrets.get(key)
        # common nested: st.secrets["supabase"]["url"], etc.
        # (leave nested lookups to callers who know the path)
    except Exception:
        pass
    return default

def _get_gemini_api_key() -> str:
    key = get_secret("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("Missing GOOGLE_API_KEY. Set it in env or Streamlit secrets.")
    return key

@_cache_resource
def get_gemini_client() -> None:
    genai.configure(api_key=_get_gemini_api_key())
    return genai  # module acts as the configured client