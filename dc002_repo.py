# dc002_repo.py — Supabase client version (optional design_id, public schema)
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from db import get_supabase

# ---- optional audit (Supabase) ----
try:
    from audit import log_action as _audit_log  # type: ignore
except Exception:
    try:
        from audit import log_action_supabase as _audit_log  # type: ignore
    except Exception:
        def _audit_log(*args, **kwargs):  # no-op fallback
            return

TABLE = "dc002_calcs"   # bare; we'll pin schema via .schema("public")
ENTITY = "dc002"

print("[dc002_repo] loaded (Supabase) from:", __file__)

# Cache: whether table has column `design_id`
_HAS_DESIGN_ID: Optional[bool] = None


def _tbl():
    return get_supabase().schema("public").table(TABLE)


def _is_undefined_column(exc: Exception) -> bool:
    """
    Detect PostgREST 'undefined_column' (SQLSTATE 42703) from supabase-py exceptions.
    We heuristically check message text.
    """
    msg = str(exc).lower()
    return ("42703" in msg) or ("does not exist" in msg and "design_id" in msg)


def _probe_design_id() -> bool:
    """
    Try to select the design_id column once; cache the outcome.
    """
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
            # Conservative default (don’t mask unrelated errors)
            _HAS_DESIGN_ID = True
    return _HAS_DESIGN_ID


def _first_or_none(resp):
    data = getattr(resp, "data", None)
    if not data:
        return None
    return data[0]


# -------------------------------------------------------------------
# Create
# -------------------------------------------------------------------
def create_dc002_calc(
    user_id: str,
    name: str,
    data: Dict[str, Any],
    design_id: Optional[str] = None,
) -> str:
    nm = (name or "DC002").strip() or "DC002"
    row: Dict[str, Any] = {"user_id": user_id, "name": nm, "data": data}

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

    # AUDIT (compact base summary if present)
    try:
        base = (data or {}).get("base", {}) or {}
        _audit_log(
            action="create",
            entity_type=ENTITY,
            entity_id=str(rec["id"]),
            name=nm,
            details={"summary": {
                "nps_in": base.get("nps_in"),
                "asme_class": base.get("asme_class"),
            }},
        )
    except Exception:
        pass

    return str(rec["id"])


# -------------------------------------------------------------------
# List (by user)
# -------------------------------------------------------------------
def list_dc002_calcs(user_id: str, limit: int = 500) -> List[Tuple[str, str, str, str]]:
    # Use server-side ordering; Supabase returns timestamps in ISO8601 with TZ
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
    out: List[Tuple[str, str, str, str]] = []
    for r in rows:
        out.append((
            str(r.get("id")),
            r.get("name", ""),
            r.get("created_at"),
            r.get("updated_at"),
        ))
    return out


# -------------------------------------------------------------------
# Get one (merge data + meta)
# -------------------------------------------------------------------
def get_dc002_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        _tbl()
        .select("id,name,data,created_at,updated_at")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    r = _first_or_none(resp)
    if not r:
        return None
    payload = r.get("data") or {}
    out: Dict[str, Any] = {}
    if isinstance(payload, dict):
        out.update(payload)
    out["id"] = str(r.get("id")) if r.get("id") is not None else None
    out["name"] = r.get("name")
    out["created_at"] = r.get("created_at")
    out["updated_at"] = r.get("updated_at")
    return out


def get_dc002_calc_with_meta(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        _tbl()
        .select("id,name,data,created_at,updated_at")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    r = _first_or_none(resp)
    return dict(r) if r else None


# -------------------------------------------------------------------
# Update (name/data/design_id) + audit
# -------------------------------------------------------------------
def update_dc002_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,
) -> bool:
    sets: Dict[str, Any] = {}
    if name is not None:
        sets["name"] = (name or "DC002").strip() or "DC002"
    if data is not None:
        sets["data"] = data

    has_design = _probe_design_id()
    if has_design and design_id is not None:
        sets["design_id"] = design_id

    if not sets:
        return False

    # Prefetch old name for audit fallback if needed
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

    updated = (getattr(resp, "data", None) or [])
    ok = resp.count is None or (resp.count or 0) > 0 or bool(updated)

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


# -------------------------------------------------------------------
# Delete + audit
# -------------------------------------------------------------------
def delete_dc002_calc(calc_id: str, user_id: str) -> bool:
    # Prefetch name for audit
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
# Admin list all (optional)
# -------------------------------------------------------------------
def list_dc002_all(limit: int = 500) -> List[Dict[str, Any]]:
    # Note: This exposes all rows; ensure your RLS policies allow appropriate access.
    resp = (
        _tbl()
        .select("id,user_id,name,created_at,updated_at")
        .order("updated_at", desc=True)
        .order("created_at", desc=True)
        .limit(int(limit))
        .execute()
    )
    rows = getattr(resp, "data", []) or []
    # If you need usernames here, join in SQL or fetch from users table separately.
    return [
        {
            "id": str(r.get("id")) if r.get("id") is not None else None,
            "user_id": str(r.get("user_id")) if r.get("user_id") is not None else None,
            "username": None,  # left blank unless you enrich via another call
            "name": r.get("name"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
        }
        for r in rows
    ]
