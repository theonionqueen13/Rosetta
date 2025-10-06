# rosetta/db.py
import os
import httpx
import streamlit as st
from supabase import create_client, ClientOptions  # type: ignore

try:
    _cache_resource = st.cache_resource  # Streamlit >= 1.18
except Exception:

    def _cache_resource(func):
        return func


@_cache_resource
def _get_supabase_keys() -> tuple[str, str]:
    # Hard-wire to your nested secrets format. No env, no flat names.
    blk = st.secrets["supabase"]  # raises clearly if the block is missing
    url = blk["url"]  # raises clearly if missing
    key = blk.get("service_role") or blk["key"]  # prefer service_role, else key
    if not url or not key:
        raise RuntimeError(
            "Missing [supabase].url and key/service_role in secrets.toml"
        )
    return url, key


@_cache_resource
def supa():  # -> Client
    url, key = _get_supabase_keys()

    # HTTP/2 -> HTTP/1.1 to avoid RemoteProtocolError
    http_client = httpx.Client(http2=False)
    options = ClientOptions(httpx_client=http_client)  # supabase 2.18.1 supports this

    return create_client(url, key, options=options)
