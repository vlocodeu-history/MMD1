# supa_client.py
from __future__ import annotations
from functools import lru_cache
import streamlit as st
from supabase import create_client, Client


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = st.secrets.get("SUPABASE_URL")
    # Prefer SERVICE_ROLE on the server (Streamlit runs on the server).
    key = (
        st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        or st.secrets.get("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or key in secrets.toml")
    return create_client(url, key)
