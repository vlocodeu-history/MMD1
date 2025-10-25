# db.py — Supabase-only helpers (no SQLAlchemy / psycopg2)
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache
import streamlit as st
from supabase import create_client, Client


# -----------------------------------------------------------------------------
# Core client
# -----------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """
    Build a Supabase client from Streamlit secrets.

    In .streamlit/secrets.toml you should have:
      SUPABASE_URL = "https://xxxx.supabase.co"
      SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR..."  # preferred on server
      # or SUPABASE_ANON_KEY as a fallback if RLS is configured for anon
    """
    url = st.secrets.get("SUPABASE_URL")
    key = (
        st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        or st.secrets.get("SUPABASE_ANON_KEY")
    )
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL and/or key in secrets.toml. "
            "Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY)."
        )
    return create_client(url, key)


# -----------------------------------------------------------------------------
# Convenience helpers (simple wrappers you can use in repos)
# -----------------------------------------------------------------------------
def insert(table: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a single row and return the inserted row."""
    sb = get_supabase()
    res = sb.table(table).insert(row).select("*").single().execute()
    return res.data or {}

def update(table: str, match: Dict[str, Any], patch: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Update rows that match filters in `match` and return the updated rows."""
    sb = get_supabase()
    q = sb.table(table).update(patch)
    for k, v in (match or {}).items():
        q = q.eq(k, v)
    res = q.select("*").execute()
    return res.data or []

def delete(table: str, match: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Delete rows that match filters in `match` and return deleted rows (if enabled)."""
    sb = get_supabase()
    q = sb.table(table).delete()
    for k, v in (match or {}).items():
        q = q.eq(k, v)
    res = q.execute()
    return res.data or []

def select_one(table: str, match: Dict[str, Any], columns: str = "*") -> Optional[Dict[str, Any]]:
    """Select a single row by filters; returns dict or None."""
    sb = get_supabase()
    q = sb.table(table).select(columns)
    for k, v in (match or {}).items():
        q = q.eq(k, v)
    res = q.single().execute()
    return res.data or None

def select_many(
    table: str,
    match: Optional[Dict[str, Any]] = None,
    columns: str = "*",
    limit: Optional[int] = None,
    order_by: Optional[Tuple[str, bool]] = None,  # ("updated_at", True for desc)
) -> List[Dict[str, Any]]:
    """Select multiple rows with optional filters, order, and limit."""
    sb = get_supabase()
    q = sb.table(table).select(columns)
    for k, v in (match or {}).items():
        q = q.eq(k, v)
    if order_by:
        col, desc = order_by
        q = q.order(col, desc=bool(desc))
    if limit is not None:
        q = q.limit(int(limit))
    res = q.execute()
    return res.data or []

def count_rows(table: str, match: Optional[Dict[str, Any]] = None) -> int:
    """Return an exact count of rows (using PostgREST count)."""
    sb = get_supabase()
    q = sb.table(table).select("id", count="exact", head=True)
    for k, v in (match or {}).items():
        q = q.eq(k, v)
    res = q.execute()
    # supabase-py v2 surfaces count on the response
    return int(getattr(res, "count", 0) or 0)


# -----------------------------------------------------------------------------
# Back-compat stubs (only if some code still imports these)
# -----------------------------------------------------------------------------
def get_engine():
    """
    Backward-compat stub to avoid import errors if something still imports get_engine().
    Migrate callers to use get_supabase() instead.
    """
    raise RuntimeError("get_engine() is not available. Use get_supabase() from db.py.")

class _NoSQLAlchemyContext:
    def __enter__(self):
        raise RuntimeError("connect() is not available. Use Supabase helpers in db.py.")
    def __exit__(self, exc_type, exc, tb):
        return False

def connect():
    """
    Backward-compat stub to avoid import errors if something still imports connect().
    """
    return _NoSQLAlchemyContext()

def scalar(*_args, **_kwargs):
    """
    Backward-compat stub; remove usages. Use select_one()/count_rows() instead.
    """
    raise RuntimeError("scalar() is not available. Use select_one()/count_rows().")
