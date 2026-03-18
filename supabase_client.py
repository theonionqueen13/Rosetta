# supabase_client.py
"""
Factory helpers for creating Supabase clients.

Two modes are supported:
  - get_supabase()       : plain anon-key client; use for auth operations
  - get_authed_supabase(): same but with the current user's JWT applied so
                           that Postgres RLS policies (auth.uid()) resolve
                           to the logged-in user.

===== Root cause of [Errno 24] Too many open files =====

supabase-py v2's `_listen_to_auth_events` fires on every SIGNED_IN /
TOKEN_REFRESHED / SIGNED_OUT event and sets `self._postgrest = None`.  On
the next `client.table()` call, `_init_postgrest_client` runs again and
creates a brand-new httpx.Client (with a new SSL context + connection pool).
Each discarded httpx.Client may hold file/socket handles that are never
explicitly closed, so they accumulate until EMFILE.

===== Fix =====

Pass a single shared `httpx.Client` via `ClientOptions(httpx_client=...)`.
supabase-py passes it as `http_client=self.options.httpx_client` every time
it re-initialises the postgrest sub-client, so all re-creations reuse the
same underlying transport — no new SSL contexts, no new connection pools,
no leaked handles.

One shared httpx.Client is created per credentials set (app lifetime).
The authed client gets a separate shared transport so session headers
don't bleed between the anon and authed paths.
"""
import streamlit as st
import httpx
from supabase import create_client, Client, ClientOptions

# ---------------------------------------------------------------------------
# Shared httpx transports (one per credential set, created lazily)
# ---------------------------------------------------------------------------
_shared_transport: httpx.Client | None = None
_shared_transport_credentials: tuple[str, str] | None = None

_shared_authed_transport: httpx.Client | None = None
_shared_authed_transport_credentials: tuple[str, str] | None = None

# Module-level singleton for the unauthenticated client
_anon_client: Client | None = None
_anon_client_credentials: tuple[str, str] | None = None


def _get_shared_transport(url: str, key: str) -> httpx.Client:
    """Return (or create) the shared httpx.Client for the anon supabase client."""
    global _shared_transport, _shared_transport_credentials
    if _shared_transport is None or _shared_transport_credentials != (url, key):
        if _shared_transport is not None:
            try:
                _shared_transport.close()
            except Exception:
                pass
        _shared_transport = httpx.Client(http2=True)
        _shared_transport_credentials = (url, key)
    return _shared_transport


def _get_shared_authed_transport(url: str, key: str) -> httpx.Client:
    """Return (or create) the shared httpx.Client for the authed supabase client."""
    global _shared_authed_transport, _shared_authed_transport_credentials
    if _shared_authed_transport is None or _shared_authed_transport_credentials != (url, key):
        if _shared_authed_transport is not None:
            try:
                _shared_authed_transport.close()
            except Exception:
                pass
        _shared_authed_transport = httpx.Client(http2=True)
        _shared_authed_transport_credentials = (url, key)
    return _shared_authed_transport


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
    """Returns a cached anon Supabase client. Safe for auth operations.

    A single client is reused for the entire process lifetime.  All postgrest
    sub-client re-creations (triggered by supabase-py on every auth event)
    reuse the shared httpx.Client, so no new SSL contexts or connection pools
    are created.
    """
    global _anon_client, _anon_client_credentials
    url, key = _credentials()

    if _anon_client is not None and _anon_client_credentials == (url, key):
        return _anon_client

    # Close old supabase client's auth httpx session if it has one
    if _anon_client is not None:
        try:
            if hasattr(_anon_client, "auth") and hasattr(_anon_client.auth, "_client"):
                _anon_client.auth._client.close()
        except Exception:
            pass

    transport = _get_shared_transport(url, key)
    _anon_client = create_client(url, key, options=ClientOptions(httpx_client=transport))
    _anon_client_credentials = (url, key)
    return _anon_client


def get_authed_supabase() -> Client:
    """
    Returns a Supabase client with the current user's session injected.
    This makes every DB query run as the logged-in user and activates RLS.

    The client is cached by access token to avoid recreating on every call.
    All postgrest sub-client re-creations reuse a shared httpx.Client so
    auth events never leak file handles.
    Raises RuntimeError if there is no active session (caller must re-auth).
    """
    session = st.session_state.get("supabase_session")
    if not session:
        raise RuntimeError(
            "No Supabase session in st.session_state['supabase_session']. "
            "Please log in again."
        )
    # Reuse the client within the same rerun as long as the access token hasn't changed
    _cached = st.session_state.get("_supabase_authed_client")
    _cached_token = st.session_state.get("_supabase_authed_token")
    if _cached is not None and _cached_token == session.get("access_token"):
        return _cached

    url, key = _credentials()
    # Use a separate shared transport for authed calls (keeps auth headers
    # isolated from the anon path)
    transport = _get_shared_authed_transport(url, key)
    client = create_client(url, key, options=ClientOptions(httpx_client=transport))
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
    # Cache the client for subsequent calls in this script run
    st.session_state["_supabase_authed_client"] = client
    st.session_state["_supabase_authed_token"] = session.get("access_token")
    return client
