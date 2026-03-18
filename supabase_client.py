# supabase_client.py
"""
Factory helpers for creating Supabase clients.

Two modes are supported:
  - get_supabase()       : plain anon-key client; use for auth operations
  - get_authed_supabase(): same but with the current user's JWT applied so
                           that Postgres RLS policies (auth.uid()) resolve
                           to the logged-in user.

Each call returns a *new* Client object so that setting a session on one
call never leaks into another user's requests (important in Streamlit where
@st.cache_resource objects are shared across sessions).
"""
import streamlit as st
from supabase import create_client, Client


def _credentials() -> tuple[str, str]:
    """Return (url, anon_key) for Supabase.

    This supports two common config formats:
      1) [supabase] url/key (recommended)
      2) SUPABASE_URL / SUPABASE_ANON_KEY (legacy/alternate)

    If neither works, we raise a clear error explaining how to fix it.
    """

    supabase = st.secrets.get("supabase")
    if supabase is not None:
        def _get(m, *keys):
            for k in keys:
                try:
                    if k in m:
                        return m[k]
                except Exception:
                    pass
            return None

        url = _get(supabase, "url", "URL")
        key = _get(supabase, "key", "KEY")
        if url and key:
            return url, key

    # Fallback to top-level keys (commonly used in older examples)
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_ANON_KEY")
    if url and key:
        return url, key

    raise KeyError(
        "st.secrets does not contain Supabase credentials. "
        "Add a [supabase] section with 'url' and 'key', or define "
        "SUPABASE_URL and SUPABASE_ANON_KEY in .streamlit/secrets.toml."
    )


def get_supabase() -> Client:
    """Returns a fresh Supabase client.  Safe for auth operations only."""
    url, key = _credentials()
    return create_client(url, key)


def get_authed_supabase() -> Client:
    """
    Returns a fresh Supabase client with the current user's session injected.
    This makes every DB query run as the logged-in user and activates RLS.
    Raises RuntimeError if there is no active session (caller must re-auth).
    """
    url, key = _credentials()
    client = create_client(url, key)
    session = st.session_state.get("supabase_session")
    if not session:
        raise RuntimeError(
            "No Supabase session in st.session_state['supabase_session']. "
            "Please log in again."
        )
    try:
        client.auth.set_session(
            session["access_token"],
            session["refresh_token"],
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not restore Supabase session (token may be expired). "
            f"Please log in again. Detail: {exc}"
        ) from exc
    return client
