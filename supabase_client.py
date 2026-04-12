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
import httpx
from supabase import create_client, Client, ClientOptions

from config import get_secret

# ---------------------------------------------------------------------------
# Framework-agnostic session lookup
# ---------------------------------------------------------------------------

def _get_session_dict() -> dict:
    """Return the Supabase session dict from whichever framework is active.

    Tries NiceGUI app.storage.user first, then Streamlit st.session_state.
    Returns a dict with access_token/refresh_token keys.
    Raises RuntimeError if no session is found in either framework.
    """
    # --- Try NiceGUI first ---
    try:
        from nicegui import app as _ng_app
        _store = _ng_app.storage.user
        _sess = _store.get("supabase_session")
        if _sess:
            return _sess
    except Exception:
        pass

    # --- Fall back to Streamlit ---
    try:
        import streamlit as _st
        _sess = _st.session_state.get("supabase_session")
        if _sess:
            return _sess
    except Exception:
        pass

    raise RuntimeError(
        "No Supabase session found. Please log in again."
    )


# In-memory client cache keyed by access_token (avoids JSON serialisation
# issues with NiceGUI's file-backed storage).
_authed_client_cache: dict[str, Client] = {}  # {access_token: Client}

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

    Uses config.get_secret() which checks env vars first, then falls back
    to st.secrets when running under Streamlit.
    """
    url = get_secret("supabase", "url")
    key = get_secret("supabase", "key")
    if url and key:
        return url, key

    raise KeyError(
        "Supabase credentials not found. "
        "Set SUPABASE_URL and SUPABASE_KEY environment variables (or in .env), "
        "or add a [supabase] section with 'url' and 'key' in .streamlit/secrets.toml."
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

    Session is resolved via _get_session_dict(), which checks NiceGUI
    storage first, then Streamlit session_state.
    The client is cached by access token in a module-level dict (avoids
    JSON serialisation issues with NiceGUI's file-backed storage).
    All postgrest sub-client re-creations reuse a shared httpx.Client so
    auth events never leak file handles.
    Raises RuntimeError if there is no active session (caller must re-auth).
    """
    session = _get_session_dict()
    token = session.get("access_token")

    # Reuse the client as long as the access token hasn't changed
    cached = _authed_client_cache.get(token)
    if cached is not None:
        return cached

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
    # Cache the client in-memory (keyed by token)
    _authed_client_cache[token] = client
    return client


def reset_authed_client_state() -> None:
    """Reset the authed client cache and shared transport.

    Call this after a connection error (e.g. Supabase pause/resume) to force
    a fresh transport and new client on the next request instead of reusing
    stale dead HTTP connections.
    """
    global _shared_authed_transport, _shared_authed_transport_credentials
    _authed_client_cache.clear()
    if _shared_authed_transport is not None:
        try:
            _shared_authed_transport.close()
        except Exception:
            pass
        _shared_authed_transport = None
        _shared_authed_transport_credentials = None
