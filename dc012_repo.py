# dc012_repo.py — Supabase client version (optional design_id, public schema)
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from db import get_supabase

# ---- audit (Supabase-backed or no-op fallback) ----
try:
    from audit import log_action as _audit_log  # type: ignore
except Exception:
    try:
        from audit import log_action_supabase as _audit_log  # type: ignore
    except Exception:
        def _audit_log(*args, **kwargs):
            return  # no-op if audit not available

TABLE = "dc012_calcs"  # bare name; we call .schema("public")
ENTITY = "dc012"

print("[dc012_repo] loaded (Supabase) from:", __file__)

_HAS_DESIGN_ID: Optional[bool] = None


def _tbl():
    return get_supabase().schema("public").table(TABLE)


def _users_tbl():
    return get_supabase().schema("public").table("users")


def _first_or_none(resp):
    data = getattr(resp, "data", None)
    if not data:
        return None
    return data[0]


def _is_undefined_column(exc: Exception) -> bool:
    msg = str(exc).lower()
    return ("42703" in msg) or ("does not exist" in msg and "design_id" in msg)


def _probe_design_id() -> bool:
    global _HAS_DESIGN_ID
    if _HAS_DESIGN_ID is not None:
        return _HAS_DESIGN_ID
    try:
        _tbl().select("id,design_id").limit(1).execute()
        _HAS_DESIGN_ID = True
    except Exception as e:
        if _is_undefined_column(e):
            _HAS_DESIGN_ID = False
        else:
            _HAS_DESIGN_ID = True
    return _HAS_DESIGN_ID


# -------------------------------------------------------------------
# Create
# -------------------------------------------------------------------
def create_dc012_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,
) -> str:
    clean_name = (name or "DC012").strip() or "DC012"
    row: Dict[str, Any] = {"user_id": user_id, "name": clean_name, "data": payload}

    has_design = _probe_design_id()
    if has_design and design_id:
        row["design_id"] = design_id

    try:
        resp = _tbl().insert(row, returning="representation").execute()
    except Exception as e:
        if "design_id" in row and _is_undefined_column(e):
            row.pop("design_id", None)
            resp = _tbl().insert(row, returning="representation").execute()
        else:
            raise

    rec = _first_or_none(resp)
    if not rec or "id" not in rec:
        raise RuntimeError(f"Insert failed for {ENTITY}: {getattr(resp, 'error', None)}")

    # AUDIT (compact base summary)
    try:
        base = (payload or {}).get("base", {}) or {}
        _audit_log(
            action="create",
            entity_type=ENTITY,
            entity_id=str(rec["id"]),
            name=clean_name,
            details={"summary": {
                "nps_in": base.get("nps_in"),
                "asme_class": base.get("asme_class"),
                "valve_weight_kg": base.get("valve_weight_kg"),
                "valve_design_id": base.get("valve_design_id") or design_id,
            }},
        )
    except Exception:
        pass

    return str(rec["id"])


# -------------------------------------------------------------------
# List (user-scoped)
# -------------------------------------------------------------------
def list_dc012_calcs(user_id: str, limit: int = 200) -> List[Tuple[str, str, Any, Any]]:
    resp = (
        _tbl()
        .select("id,name,created_at,updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .order("created_at", desc=True)
        .limit(int(limit))
        .execute()
    )
    rows = getattr(resp, "data", []) or []
    return [
        (
            str(r.get("id")) if r.get("id") is not None else None,
            r.get("name", ""),
            r.get("created_at"),
            r.get("updated_at"),
        )
        for r in rows
    ]


# -------------------------------------------------------------------
# Get one (user-scoped)
# -------------------------------------------------------------------
def get_dc012_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        _tbl()
        .select("id,name,data,created_at,updated_at,design_id")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    r = _first_or_none(resp)
    if not r:
        return None

    data = r.get("data") or {}
    out = dict(data) if isinstance(data, dict) else {}
    out["_meta"] = {
        "id": str(r.get("id")) if r.get("id") is not None else None,
        "name": r.get("name"),
        "design_id": r.get("design_id"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
    }
    return out


# -------------------------------------------------------------------
# Update / Delete (user-scoped)
# -------------------------------------------------------------------
def update_dc012_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,
) -> bool:
    sets: Dict[str, Any] = {}

    if name is not None:
        sets["name"] = (name or "DC012").strip() or "DC012"
    if data is not None:
        sets["data"] = data

    has_design = _probe_design_id()
    if has_design and design_id is not None:
        sets["design_id"] = design_id

    if not sets:
        return False

    # Fetch existing name for audit if not provided
    nm_for_log = sets.get("name")
    if not nm_for_log:
        pre = _tbl().select("name").eq("id", calc_id).eq("user_id", user_id).limit(1).execute()
        pre_rec = _first_or_none(pre)
        if pre_rec:
            nm_for_log = pre_rec.get("name")

    try:
        resp = _tbl().update(sets).eq("id", calc_id).eq("user_id", user_id).execute()
    except Exception as e:
        if "design_id" in sets and _is_undefined_column(e):
            sets.pop("design_id", None)
            resp = _tbl().update(sets).eq("id", calc_id).eq("user_id", user_id).execute()
        else:
            raise

    updated_rows = getattr(resp, "data", None) or []
    ok = resp.count is None or (resp.count or 0) > 0 or bool(updated_rows)

    if ok:
        try:
            _audit_log(
                action="update",
                entity_type=ENTITY,
                entity_id=str(calc_id),
                name=nm_for_log,
            )
        except Exception:
            pass

    return ok


def delete_dc012_calc(calc_id: str, user_id: str) -> bool:
    # Prefetch name BEFORE delete so audit shows the deleted name
    name_before = None
    try:
        pre = _tbl().select("name").eq("id", calc_id).eq("user_id", user_id).limit(1).execute()
        pre_rec = _first_or_none(pre)
        if pre_rec:
            name_before = pre_rec.get("name")
    except Exception:
        pass

    resp = _tbl().delete().eq("id", calc_id).eq("user_id", user_id).execute()
    ok = resp.count is None or (resp.count or 0) > 0

    if ok:
        try:
            _audit_log(
                action="delete",
                entity_type=ENTITY,
                entity_id=str(calc_id),
                name=name_before,
            )
        except Exception:
            pass

    return ok


# -------------------------------------------------------------------
# Admin helpers (no user filter) — rely on RLS/policies to allow superadmin
# -------------------------------------------------------------------
def admin_delete_dc012_calc(calc_id: str) -> bool:
    # Prefetch name for audit
    name_before = None
    try:
        pre = _tbl().select("name").eq("id", calc_id).limit(1).execute()
        pre_rec = _first_or_none(pre)
        if pre_rec:
            name_before = pre_rec.get("name")
    except Exception:
        pass

    resp = _tbl().delete().eq("id", calc_id).execute()
    ok = resp.count is None or (resp.count or 0) > 0

    if ok:
        try:
            _audit_log(action="delete", entity_type=ENTITY, entity_id=str(calc_id), name=name_before)
        except Exception:
            pass
    return ok


def get_dc012_calc_with_user(calc_id: str) -> Optional[Dict[str, Any]]:
    """Return one DC012 row + owner username, name, timestamps, data, design_id."""
    r = _first_or_none(_tbl().select("*").eq("id", calc_id).limit(1).execute())
    if not r:
        return None
    out = {
        "id": str(r.get("id")) if r.get("id") is not None else None,
        "name": r.get("name"),
        "design_id": r.get("design_id"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
        "user_id": str(r.get("user_id")) if r.get("user_id") is not None else None,
        "data": r.get("data"),
        "username": None,
    }
    uid = r.get("user_id")
    if uid:
        u = _first_or_none(_users_tbl().select("username").eq("id", uid).limit(1).execute())
        if u:
            out["username"] = u.get("username")
    return out


def list_all_dc012_calcs(
    *,
    limit: int = 500,
    username_like: Optional[str] = None,
    name_like: Optional[str] = None,
    design_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Admin listing across all users. We fetch rows and optionally filter by username
    by first resolving matching user IDs, then query calcs. Summary fields are
    projected in Python to avoid SQL JSON path usage.
    """
    q = _tbl().select("id,user_id,name,design_id,data,created_at,updated_at")

    if name_like:
        q = q.ilike("name", f"%{name_like}%")
    if design_id:
        q = q.eq("design_id", design_id)

    if username_like:
        users_resp = _users_tbl().select("id,username").ilike("username", f"%{username_like}%").execute()
        user_rows = getattr(users_resp, "data", []) or []
        user_ids = [u["id"] for u in user_rows if "id" in u]
        if not user_ids:
            return []
        q = q.in_("user_id", user_ids)

    q = q.order("updated_at", desc=True).order("created_at", desc=True).limit(int(limit))
    resp = q.execute()
    rows = getattr(resp, "data", []) or []

    out: List[Dict[str, Any]] = []
    for r in rows:
        data = r.get("data") or {}
        base = (data.get("base") or {}) if isinstance(data, dict) else {}
        inputs = (data.get("inputs") or {}) if isinstance(data, dict) else {}
        computed = (data.get("computed") or {}) if isinstance(data, dict) else {}

        out.append({
            "id": str(r.get("id")) if r.get("id") is not None else None,
            "name": r.get("name"),
            "design_id": r.get("design_id"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "user_id": str(r.get("user_id")) if r.get("user_id") is not None else None,

            # summaries (ported from your SQL projections)
            "valve_design_id": base.get("valve_design_id"),
            "valve_design_name": base.get("valve_design_name"),
            "nps_in": base.get("nps_in"),
            "asme_class": base.get("asme_class"),
            "bore_mm": base.get("bore_diameter_mm"),
            "Po_MPa": base.get("operating_pressure_mpa"),
            "valve_weight_kg": base.get("valve_weight_kg"),

            "P_kg": inputs.get("P_kg"),
            "thread": inputs.get("thread"),
            "A_mm2": inputs.get("A_mm2"),
            "N": inputs.get("N"),
            "angle": inputs.get("angle"),
            "F_rated_kg": inputs.get("F_rated_kg"),

            "per_bolt_kg": computed.get("per_bolt_kg"),
            "Ec_ok": computed.get("Ec_ok"),
            "Es_MPa": computed.get("Es_MPa"),
            "material": computed.get("material"),
            "allowable_MPa": computed.get("allowable_MPa"),
            "stress_ok": computed.get("stress_ok"),
        })

    return out
