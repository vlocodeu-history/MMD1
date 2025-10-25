# audit.py — robust logging (JSONB/INET, lowercase action/entity)
from __future__ import annotations
from typing import Any, Optional, Dict
import streamlit as st
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB, INET
from db import connect
from auth import current_user
import ipaddress

def _actor() -> Dict[str, Optional[str]]:
    u = current_user() or {}
    return {"user_id": u.get("id"), "username": u.get("username"), "role": u.get("role")}

def _guess_ip() -> Optional[str]:
    return st.session_state.get("client_ip")

def _clean_ip(ip: Optional[str]) -> Optional[str]:
    if not ip: return None
    # strip common "host:port"
    if ":" in ip and ip.count(":") == 1 and ip.split(":")[-1].isdigit():
        ip = ip.rsplit(":", 1)[0]
    try:
        ipaddress.ip_address(ip)
        return ip
    except Exception:
        return None

_INSERT_AUDIT = text("""
    INSERT INTO public.audit_logs
      (actor_user_id, actor_username, actor_role, action,
       entity_type, entity_id, name, details, ip_addr)
    VALUES
      (:uid, :uname, :urole, :action,
       :etype, :eid, :name, :details, :ip)
""").bindparams(
    bindparam("details", type_=JSONB),
    bindparam("ip", type_=INET),
)

def _do_insert(conn, payload: Dict[str, Any]) -> None:
    try:
        conn.execute(_INSERT_AUDIT, payload)
    except Exception:
        # last-ditch: drop details/ip if they’re the problem
        payload2 = dict(payload)
        payload2["details"] = None
        payload2["ip"] = None
        conn.execute(_INSERT_AUDIT, payload2)

def log_action(
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_addr: Optional[str] = None,
) -> None:
    act = _actor()
    ip = _clean_ip(ip_addr or _guess_ip())
    payload = {
        "uid": act["user_id"],
        "uname": act["username"],
        "urole": act["role"],
        "action": (action or "").lower(),        # normalize
        "etype": (entity_type or "").lower(),    # normalize
        "eid": entity_id,
        "name": name,
        "details": details or {},
        "ip": ip,
    }
    with connect() as conn:
        _do_insert(conn, payload)

def log_on_conn(
    conn,
    action: str,
    entity: str,
    *,
    entity_id: Optional[str] = None,
    name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_addr: Optional[str] = None,
):
    u = current_user() or {}
    ip = _clean_ip(ip_addr or _guess_ip())
    payload = {
        "uid": u.get("id"),
        "uname": u.get("username"),
        "urole": u.get("role"),
        "action": (action or "").lower(),
        "etype": (entity or "").lower(),
        "eid": entity_id,
        "name": name,
        "details": details or {},
        "ip": ip,
    }
    _do_insert(conn, payload)
