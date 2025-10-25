# audit.py — Supabase-only logging (JSON/INET), lowercase action/entity
from __future__ import annotations
from typing import Any, Optional, Dict
import ipaddress
import streamlit as st

from db import get_supabase
from auth import current_user

# ---------- helpers ----------
def _actor() -> Dict[str, Optional[str]]:
    u = current_user() or {}
    return {
        "user_id": u.get("id"),
        "username": u.get("username"),
        "role": u.get("role"),
    }

def _guess_ip() -> Optional[str]:
    # Set this in your app once per session if you proxy the IP to the app.
    # e.g. st.session_state["client_ip"] = st.request.headers.get("X-Forwarded-For")
    return st.session_state.get("client_ip")

def _clean_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    # strip common "host:port"
    if ":" in ip and ip.count(":") == 1 and ip.split(":")[-1].isdigit():
        ip = ip.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(ip)
        return ip
    except Exception:
        return None

def _normalize(s: Optional[str]) -> str:
    return (s or "").strip().lower()

def _insert_row(payload: Dict[str, Any]) -> None:
    """Insert into public.audit_logs using Supabase. Never raise."""
    try:
        sb = get_supabase()
        # Supabase will accept JSON dicts for json/jsonb columns
        # and strings for inet columns.
        res = sb.table("audit_logs").insert(payload).execute()
        # soft-fail: do nothing if error
        if getattr(res, "error", None):
            # last-ditch: drop details/ip if they caused validation issues
            try:
                payload2 = dict(payload)
                payload2["details"] = None
                payload2["ip_addr"] = None
                sb.table("audit_logs").insert(payload2).execute()
            except Exception:
                pass
    except Exception:
        # Never break the app for audit failures
        pass

# ---------- public API ----------
def log_action(
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_addr: Optional[str] = None,
) -> None:
    """Standalone audit call (no transaction context)."""
    act = _actor()
    ip = _clean_ip(ip_addr or _guess_ip())

    payload = {
        "actor_user_id": act["user_id"],
        "actor_username": act["username"],
        "actor_role": act["role"],
        "action": _normalize(action),
        "entity_type": _normalize(entity_type),
        "entity_id": entity_id,
        "name": name,
        "details": details or {},
        "ip_addr": ip,  # string; Postgres inet will parse
    }
    _insert_row(payload)

def log_on_conn(
    conn,  # kept for backward-compat; ignored in Supabase mode
    action: str,
    entity: str,
    *,
    entity_id: Optional[str] = None,
    name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_addr: Optional[str] = None,
):
    """
    Backward-compatible signature. `conn` is ignored because we are not using
    SQLAlchemy anymore. Behaves the same as log_action().
    """
    log_action(
        action=action,
        entity_type=entity,
        entity_id=entity_id,
        name=name,
        details=details,
        ip_addr=ip_addr,
    )
