# db.py — SQLAlchemy engine for Supabase (psycopg2-only)
from __future__ import annotations
from contextlib import contextmanager
from typing import Optional, Any
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_engine: Optional[Engine] = None

def _dsn() -> str:
    """Build a psycopg2 DSN with sslmode=require and search_path=public."""
    sec = st.secrets["postgres"]  # must be defined in Streamlit Secrets
    host = sec["host"]
    port = int(sec.get("port", 5432))
    db   = sec["dbname"]
    user = sec["user"]
    pwd  = sec["password"]
    search_path = sec.get("search_path", "public")

    # Note: we set search_path via 'options' param; URL-encoded.
    # sslmode=require is mandatory on Supabase.
    return (
        "postgresql+psycopg2://"
        f"{user}:{pwd}@{host}:{port}/{db}"
        f"?sslmode=require&options=-csearch_path%3D{search_path}"
    )

def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    url = _dsn()
    masked_url = url.replace(st.secrets["postgres"]["password"], "****")
    print("SQLAlchemy URL (masked):", masked_url)

    # Simple, robust engine. pool_pre_ping keeps long-lived apps healthy.
    _engine = create_engine(
        url,
        future=True,
        pool_pre_ping=True,
        pool_recycle=1800,  # optional: recycle every 30 min
    )
    return _engine

@contextmanager
def connect():
    eng = get_engine()
    with eng.begin() as conn:
        # Ensure we’re on the right schema (safety net – also set via options)
        conn.execute(text("SET search_path TO public"))
        yield conn

def scalar(conn, sql: str, **params: Any):
    row = conn.execute(text(sql), params).one_or_none()
    return None if row is None else row[0]
