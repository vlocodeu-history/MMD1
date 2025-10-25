# valve_repo.py — Supabase client version (fixed: no .select() after .insert())
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from db import get_supabase
from audit import log_on_conn  # our audit ignores the conn param

def _diff_name(old: Optional[str], new: Optional[str]) -> Dict[str, Any]:
    if old == new:
        return {}
    return {"name": {"old": old, "new": new}}

def _diff_top_level(old_data: Dict[str, Any] | None, new_data: Dict[str, Any] | None) -> Dict[str, Any]:
    old_data = old_data or {}
    new_data = new_data or {}
    out: Dict[str, Any] = {}
    for k in ("inputs", "calculated", "base"):
        if (old_data.get(k) != new_data.get(k)):
            out[k] = {"changed": True}
    return out

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

TABLE = "valve_designs"

# -----------------------
# Basic CRUD (per-user)
# -----------------------

def create_valve_design(user_id: str, name: str, payload: Dict[str, Any]) -> str:
    clean_name = (name or "").strip() or "Untitled"
    sb = get_supabase()

    ins = {
        "user_id": user_id,
        "name": clean_name,
        "data": payload,
    }
    # ✅ Do NOT chain .select() after insert in supabase-py v2
    res = sb.table(TABLE).insert(ins, returning="representation").execute()
    if getattr(res, "error", None):
        raise RuntimeError(str(res.error))
    rows = res.data or []
    if not rows:
        raise RuntimeError("Insert returned no rows.")
    new_id = str(rows[0]["id"])

    try:
        log_on_conn(
            None, "CREATE", "valve_design",
            entity_id=new_id,
            name=clean_name,
            details={"summary": {"nps_in": payload.get("nps_in"), "asme_class": payload.get("asme_class")}},
        )
    except Exception:
        pass

    return new_id

def list_valve_designs(user_id: str, limit: int = 200) -> List[Tuple[str, str, Any, Any]]:
    sb = get_supabase()
    res = (
        sb.table(TABLE)
        .select("id,name,created_at,updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .order("created_at", desc=True)
        .limit(int(limit))
        .execute()
    )
    if getattr(res, "error", None):
        raise RuntimeError(str(res.error))
    out: List[Tuple[str, str, Any, Any]] = []
    for r in res.data or []:
        out.append((str(r["id"]), r["name"], r.get("created_at"), r.get("updated_at")))
    return out

def get_valve_design(design_id: str, user_id: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table(TABLE)
        .select("id,name,data,created_at,updated_at")
        .eq("id", design_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if getattr(res, "error", None):
        return None
    r = res.data
    out = dict(r.get("data") or {})
    out["_meta"] = {
        "id": str(r["id"]),
        "name": r["name"],
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }
    return out

def update_valve_design(
    design_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> bool:
    if name is None and data is None:
        return False

    sb = get_supabase()

    # Fetch old for diff
    old_res = (
        sb.table(TABLE)
        .select("name,data")
        .eq("id", design_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if getattr(old_res, "error", None) or not old_res.data:
        return False
    old = old_res.data
    old_name = old.get("name")
    old_data = old.get("data") or {}

    upd: Dict[str, Any] = {}
    if name is not None:
        upd["name"] = (name or "").strip() or "Untitled"
    if data is not None:
        upd["data"] = data
    # If you want to control timestamps explicitly:
    # upd["updated_at"] = _utc_now()

    # ✅ Do NOT chain .single()/.select() after update in v2
    res = sb.table(TABLE).update(upd).eq("id", design_id).eq("user_id", user_id).execute()
    if getattr(res, "error", None):
        return False
    if not res.data:
        # nothing updated
        return False

    try:
        new_name = upd.get("name", old_name)
        name_diff = _diff_name(old_name, new_name)
        new_data = upd.get("data", old_data)
        top_level_diff = _diff_top_level(old_data, new_data)

        changes: Dict[str, Any] = {}
        changes.update(name_diff)
        if top_level_diff:
            changes["data"] = top_level_diff

        nm_for_log = new_name or old_name
        log_on_conn(
            None,
            "UPDATE",
            "valve_design",
            entity_id=design_id,
            name=nm_for_log,
            details={"diff": changes} if changes else None,
        )
    except Exception:
        pass

    return True

def delete_valve_design(design_id: str, user_id: str) -> bool:
    sb = get_supabase()
    name_before = None
    try:
        r = (
            sb.table(TABLE)
            .select("name")
            .eq("id", design_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not getattr(r, "error", None) and r.data:
            name_before = r.data.get("name")
    except Exception:
        pass

    res = sb.table(TABLE).delete().eq("id", design_id).eq("user_id", user_id).execute()
    if getattr(res, "error", None):
        return False
    deleted = bool(res.data)
    if deleted:
        try:
            log_on_conn(None, "DELETE", "valve_design", entity_id=design_id, name=name_before)
        except Exception:
            pass
    return deleted

# -----------------------
# Admin helpers
# -----------------------

def list_all_valve_designs(
    *,
    limit: int = 200,
    username_like: Optional[str] = None,
    name_like: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Admin listing across all users. Requires:
      - FK valve_designs.user_id -> users.id
      - RLS/policy permitting cross-user reads for the caller (e.g., service role)
    """
    sb = get_supabase()

    q = (
        sb.table(TABLE)
        .select("id,user_id,name,created_at,updated_at,data,users!inner(username)")
        .order("updated_at", desc=True)
        .order("created_at", desc=True)
        .limit(int(limit))
    )
    # Not all PostgREST builds support ilike on joined columns;
    # safest is to fetch then filter in Python for username_like.
    if name_like:
        q = q.ilike("name", f"%{name_like}%")

    res = q.execute()
    if getattr(res, "error", None):
        raise RuntimeError(str(res.error))

    rows = res.data or []

    if username_like:
        ul = username_like.lower()
        rows = [r for r in rows if (r.get("users") or {}).get("username", "").lower().find(ul) >= 0]

    out: List[Dict[str, Any]] = []
    for r in rows:
        data = r.get("data") or {}
        calc = (data.get("calculated") or {}) if isinstance(data, dict) else {}
        out.append(
            {
                "id": str(r["id"]),
                "username": (r.get("users") or {}).get("username"),
                "name": r.get("name"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "nps_in": (data.get("nps_in") if isinstance(data, dict) else None),
                "asme_class": (data.get("asme_class") if isinstance(data, dict) else None),
                "t_mm": calc.get("body_wall_thickness_mm"),
                "bore_mm": calc.get("bore_diameter_mm"),
                "f2f_mm": calc.get("face_to_face_mm"),
            }
        )
    return out

def get_valve_design_with_user(design_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    res = (
        sb.table(TABLE)
        .select("id,name,created_at,updated_at,data,users!inner(username)")
        .eq("id", design_id)
        .single()
        .execute()
    )
    if getattr(res, "error", None) or not res.data:
        return None
    r = res.data
    return {
        "id": str(r["id"]),
        "username": (r.get("users") or {}).get("username"),
        "name": r.get("name"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
        "data": r.get("data"),
    }
