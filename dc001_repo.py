# dc001_repo.py — Supabase client version (v2), no SQLAlchemy
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from db import get_supabase
from audit import log_on_conn  # our audit function ignores the conn param

TABLE = "dc001_calcs"
ENTITY = "dc001"

# -----------------------
# Helpers
# -----------------------

def _summary_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = (payload or {}).get("base", {}) if isinstance(payload, dict) else {}
    return {
        "nps_in": base.get("nps_in"),
        "asme_class": base.get("asme_class"),
    }

def _attempt_insert(ins: Dict[str, Any]) -> Dict[str, Any]:
    """Insert and return first row; raise RuntimeError on failure."""
    sb = get_supabase()
    res = sb.table(TABLE).insert(ins, returning="representation").execute()
    if getattr(res, "error", None):
        raise RuntimeError(str(res.error))
    rows = res.data or []
    if not rows:
        raise RuntimeError("Insert returned no rows.")
    return rows[0]

# -----------------------
# Create
# -----------------------

def create_dc001_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,
) -> str:
    nm = (name or "DC001").strip() or "DC001"
    ins = {"user_id": user_id, "name": nm, "data": payload}

    # Try including design_id if provided; if PostgREST complains about unknown column, retry without it.
    if design_id:
        ins["design_id"] = design_id
        try:
            row = _attempt_insert(ins)
        except RuntimeError as e:
            msg = str(e).lower()
            if "column" in msg and "design_id" in msg:
                # Retry without design_id
                ins.pop("design_id", None)
                row = _attempt_insert(ins)
            else:
                raise
    else:
        row = _attempt_insert(ins)

    new_id = str(row["id"])

    # AUDIT (best effort)
    try:
        log_on_conn(
            None, "CREATE", ENTITY,
            entity_id=new_id,
            name=nm,
            details={"summary": _summary_from_payload(payload)},
        )
    except Exception:
        pass

    return new_id

# -----------------------
# Read (user-scoped)
# -----------------------

def list_dc001_calcs(user_id: str, limit: int = 200) -> List[Tuple[str, str, Any, Any]]:
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
        out.append((str(r["id"]), r.get("name"), r.get("created_at"), r.get("updated_at")))
    return out

def get_dc001_calc(calc_id: str, user_id: str) -> dict | None:
    sb = get_supabase()
    res = (
        sb.table(TABLE)
        .select("id,name,data,created_at,updated_at")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if getattr(res, "error", None) or not res.data:
        return None
    r = res.data
    out = dict(r.get("data") or {})
    out["_meta"] = {
        "id": str(r["id"]),
        "name": r.get("name"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }
    return out

def get_dc001_meta(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    # Use * to avoid selecting a column that may not exist (design_id).
    res = (
        sb.table(TABLE)
        .select("*")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if getattr(res, "error", None) or not res.data:
        return None
    r = res.data
    return {
        "id": str(r["id"]),
        "name": r.get("name"),
        "design_id": r.get("design_id"),  # may be None / missing depending on schema
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
        "data": r.get("data"),
    }

# -----------------------
# Update / Delete (user-scoped)
# -----------------------

def update_dc001_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,
) -> bool:
    if name is None and data is None and design_id is None:
        return False

    sb = get_supabase()

    # Fetch old to ensure we can log something meaningful
    old_res = (
        sb.table(TABLE)
        .select("name")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if getattr(old_res, "error", None) or not old_res.data:
        return False
    old_name = old_res.data.get("name")

    upd: Dict[str, Any] = {}
    if name is not None:
        upd["name"] = (name or "DC001").strip() or "DC001"
    if data is not None:
        upd["data"] = data
    if design_id is not None:
        # Try to set it; if the column doesn't exist, we'll catch and retry without it.
        upd["design_id"] = design_id

    try:
        res = (
            sb.table(TABLE)
            .update(upd)
            .eq("id", calc_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as e:
        # If design_id caused a column error, strip and retry
        msg = str(e).lower()
        if "design_id" in upd and "column" in msg and "design_id" in msg:
            upd.pop("design_id", None)
            res = (
                sb.table(TABLE)
                .update(upd)
                .eq("id", calc_id)
                .eq("user_id", user_id)
                .execute()
            )
        else:
            raise

    if getattr(res, "error", None):
        return False
    if not res.data:
        return False

    # AUDIT
    try:
        nm_for_log = upd.get("name", old_name)
        log_on_conn(None, "UPDATE", ENTITY, entity_id=calc_id, name=nm_for_log)
    except Exception:
        pass

    return True

def delete_dc001_calc(calc_id: str, user_id: str) -> bool:
    sb = get_supabase()
    # Prefetch name for audit
    name_before = None
    try:
        r = (
            sb.table(TABLE)
            .select("name")
            .eq("id", calc_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not getattr(r, "error", None) and r.data:
            name_before = r.data.get("name")
    except Exception:
        pass

    res = sb.table(TABLE).delete().eq("id", calc_id).eq("user_id", user_id).execute()
    if getattr(res, "error", None):
        return False
    deleted = bool(res.data)
    if deleted:
        try:
            log_on_conn(None, "DELETE", ENTITY, entity_id=calc_id, name=name_before)
        except Exception:
            pass
    return deleted

# -----------------------
# Admin helpers (no user filter)
# -----------------------

def admin_delete_dc001_calc(calc_id: str) -> bool:
    sb = get_supabase()
    # Prefetch name for audit
    name_before = None
    try:
        r = sb.table(TABLE).select("name").eq("id", calc_id).single().execute()
        if not getattr(r, "error", None) and r.data:
            name_before = r.data.get("name")
    except Exception:
        pass

    res = sb.table(TABLE).delete().eq("id", calc_id).execute()
    if getattr(res, "error", None):
        return False
    ok = bool(res.data)
    if ok:
        try:
            log_on_conn(None, "DELETE", ENTITY, entity_id=calc_id, name=name_before)
        except Exception:
            pass
    return ok

def get_dc001_calc_with_user(calc_id: str) -> Optional[Dict[str, Any]]:
    sb = get_supabase()
    res = (
        sb.table(TABLE)
        .select("id,name,created_at,updated_at,data,design_id,users!inner(username,id)")
        .eq("id", calc_id)
        .single()
        .execute()
    )
    if getattr(res, "error", None) or not res.data:
        return None
    r = res.data
    u = r.get("users") or {}
    return {
        "id": str(r["id"]),
        "name": r.get("name"),
        "design_id": r.get("design_id"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
        "user_id": str(u.get("id")) if u.get("id") is not None else None,
        "username": u.get("username"),
        "data": r.get("data"),
    }

def list_all_dc001_calcs(
    *,
    limit: int = 500,
    username_like: Optional[str] = None,
    name_like: Optional[str] = None,
    design_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Admin listing across all users.
    Requires policies permitting cross-user reads (e.g., service role).
    """
    sb = get_supabase()

    q = (
        sb.table(TABLE)
        .select("id,name,design_id,created_at,updated_at,data,users!inner(username)")
        .order("updated_at", desc=True)
        .order("created_at", desc=True)
        .limit(int(limit))
    )
    if name_like:
        q = q.ilike("name", f"%{name_like}%")
    if design_id:
        q = q.eq("design_id", design_id)

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
        inputs = (data.get("inputs") or {}) if isinstance(data, dict) else {}
        computed = (data.get("computed") or {}) if isinstance(data, dict) else {}
        base = (data.get("base") or {}) if isinstance(data, dict) else {}
        out.append(
            {
                "id": str(r["id"]),
                "name": r.get("name"),
                "design_id": r.get("design_id"),
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "user_id": None,  # not selected here; add if you need it
                "username": (r.get("users") or {}).get("username"),
                # a few handy columns mirrored from your SQL version:
                "nps_in": base.get("nps_in"),
                "asme_class": base.get("asme_class"),
                "material": inputs.get("material"),
                "Y_max_MPa": inputs.get("Y_max_MPa"),
                "Dm_mm": inputs.get("Dm_mm"),
                "De_mm": inputs.get("De_mm"),
                "Di_mm": inputs.get("Di_mm"),
                "Dc_mm": inputs.get("Dc_mm"),
                "Pa_MPa": inputs.get("Pa_MPa"),
                "Fmt_N": computed.get("Fmt_N"),
                "Pr_N": computed.get("Pr_N"),
                "Nm": computed.get("Nm"),
                "Nmr": computed.get("Nmr"),
                "Fmr_N": computed.get("Fmr_N"),
                "F_N": computed.get("F_N"),
                "Q_MPa": computed.get("Q_MPa"),
                "Dcs_mm": computed.get("Dcs_mm"),
                "C1_effective_N_per_mm": computed.get("C1_effective_N_per_mm"),
                "spring_check": computed.get("spring_check"),
                "result": computed.get("result"),
            }
        )
    return out
