# rosetta/db.py
import os
import json
try:
    import streamlit as st
    _cache_resource = st.cache_resource
except Exception:
    # Fallback if executed outside Streamlit
    def _cache_resource(fn): 
        return fn

from supabase import create_client, Client  # type: ignore


def _get_supabase_keys():
    """
    Resolve Supabase URL/key from env first, then Streamlit secrets.
    Expected env vars (either works):
      - SUPABASE_URL + SUPABASE_ANON_KEY
      - SUPABASE_URL + SUPABASE_KEY
    Or in Streamlit secrets:
      st.secrets["supabase"]["url"]
      st.secrets["supabase"]["key"]
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

    if not (url and key):
        try:
            # tolerate secrets missing in non-Streamlit contexts
            s = getattr(st, "secrets", {})
            sb = s.get("supabase", {}) if isinstance(s, dict) else st.secrets["supabase"]
            url = url or sb.get("url")
            key = key or sb.get("key")
        except Exception:
            pass

    if not (url and key):
        raise RuntimeError(
            "Supabase credentials missing. Set SUPABASE_URL + SUPABASE_ANON_KEY in env, "
            "or add to Streamlit secrets: [supabase] url=... key=..."
        )
    return url, key

@st.cache_resource
def supa() -> Client:
    cfg = st.secrets.get("supabase", {})
    url = cfg.get("url")
    key = cfg.get("key")
    if not url or not key:
        raise RuntimeError("Missing supabase.url/key in Streamlit secrets.")
    return create_client(url, key)