# dc005_repo.py — Supabase client version (optional design_id, public schema)
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

TABLE  = "dc005_calcs"   # bare table; use schema("public") via client
ENTITY = "dc005"

print("[dc005_repo] loaded (Supabase) from:", __file__)

# Cache: whether table has column `design_id`
_HAS_DESIGN_ID: Optional[bool] = None


def _tbl():
    return get_supabase().schema("public").table(TABLE)


def _first_or_none(resp):
    data = getattr(resp, "data", None)
    if not data:
        return None
    return data[0]


def _is_undefined_column(exc: Exception) -> bool:
    """
    Detect PostgREST undefined column (SQLSTATE 42703) from supabase-py error strings.
    """
    msg = str(exc).lower()
    return ("42703" in msg) or ("does not exist" in msg and "design_id" in msg)


def _probe_design_id() -> bool:
    """
    Try to select the design_id column once; cache result.
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
            # On unrelated errors, default True so real issues surface rather than silently skipping.
            _HAS_DESIGN_ID = True
    return _HAS_DESIGN_ID


# -------------------------
# Create
# -------------------------
def create_dc005_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,   # optional; used only if column exists
) -> str:
    clean_name = (name or "DC005").strip() or "DC005"
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

    # AUDIT (tiny summary if available)
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
            }},
        )
    except Exception:
        pass

    return str(rec["id"])


# -------------------------
# List (user-scoped)
# -------------------------
def list_dc005_calcs(user_id: str, limit: int = 100) -> List[Tuple[str, str, Any, Any]]:
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
    out: List[Tuple[str, str, Any, Any]] = []
    for r in rows:
        out.append((
            str(r.get("id")) if r.get("id") is not None else None,
            r.get("name", ""),
            r.get("created_at"),
            r.get("updated_at"),
        ))
    return out


# -------------------------
# Get one (user-scoped)
# -------------------------
def get_dc005_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    resp = (
        _tbl()
        .select("data")
        .eq("id", calc_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    row = _first_or_none(resp)
    if not row:
        return None
    return row.get("data") if isinstance(row.get("data"), dict) else None


# -------------------------
# Update (user-scoped) + audit
# -------------------------
def update_dc005_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,   # optional; applied only if column exists
) -> bool:
    sets: Dict[str, Any] = {}
    if name is not None:
        sets["name"] = (name or "DC005").strip() or "DC005"
    if payload is not None:
        sets["data"] = payload

    has_design = _probe_design_id()
    if has_design and design_id is not None:
        sets["design_id"] = design_id

    if not sets:
        return False

    # Fetch old name for audit fallback if not provided
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


# -------------------------
# Delete (user-scoped) + audit
# -------------------------
def delete_dc005_calc(calc_id: str, user_id: str) -> bool:
    # prefetch name BEFORE delete so the audit shows the deleted name
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
