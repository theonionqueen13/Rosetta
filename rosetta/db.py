"""Supabase client creation with typed settings."""

import httpx
from supabase import ClientOptions, create_client  # type: ignore

from rosetta.settings import get_settings

try:
    import streamlit as st

    _cache_resource = st.cache_resource  # Streamlit >= 1.18
except Exception:  # pragma: no cover - streamlit not always installed
    st = None

    def _cache_resource(func):  # type: ignore[return-type]
        return func


@_cache_resource
def _get_supabase_keys() -> tuple[str, str]:
    settings = get_settings()
    url = settings.supabase_url
    key = settings.supabase_auth_key

    if not url or not key:
        raise RuntimeError(
            "Supabase configuration missing. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_KEY) as environment variables "
            "or provide them under a [supabase] block in .streamlit/secrets.toml."
        )

    return url, key


@_cache_resource
def supa():  # -> Client
    url, key = _get_supabase_keys()

    # HTTP/2 -> HTTP/1.1 to avoid RemoteProtocolError
    http_client = httpx.Client(http2=False)
    options = ClientOptions(httpx_client=http_client)  # supabase 2.18.1 supports this

    return create_client(url, key, options=options)
