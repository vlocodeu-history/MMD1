# dc001a_repo.py — Supabase client version with graceful design_id handling
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

TABLE = "dc001a_calcs"  # bare name; we'll attach schema via .schema("public")
ENTITY = "dc001a"

print("[dc001a_repo] loaded (Supabase) from:", __file__)

# Cache whether table has column `design_id`
_HAS_DESIGN_ID: Optional[bool] = None


def _tbl():
    return get_supabase().schema("public").table(TABLE)


def _is_undefined_column(exc: Exception) -> bool:
    """
    Detect PostgREST 'undefined_column' (SQLSTATE 42703) from supabase-py exceptions.
    Works across different library versions by checking message text and known fields.
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
        # cheap probe: limit(1) – we only need to see if PostgREST accepts the column
        _tbl().select("id,design_id").limit(1).execute()
        _HAS_DESIGN_ID = True
    except Exception as e:
        if _is_undefined_column(e):
            _HAS_DESIGN_ID = False
        else:
            # unknown error: be conservative and assume column exists (so we don't hide real issues)
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
def create_dc001a_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,
) -> str:
    nm = (name or "DC001A").strip() or "DC001A"
    row: Dict[str, Any] = {"user_id": user_id, "name": nm, "data": payload}

    has_design = _probe_design_id()
    if has_design and design_id:
        row["design_id"] = design_id

    try:
        resp = _tbl().insert(row, returning="representation").execute()
    except Exception as e:
        # retry without design_id if undefined column
        if "design_id" in row and _is_undefined_column(e):
            row.pop("design_id", None)
            resp = _tbl().insert(row, returning="representation").execute()
        else:
            raise

    rec = _first_or_none(resp)
    if not rec or "id" not in rec:
        raise RuntimeError(f"Insert failed for {ENTITY}: {getattr(resp, 'error', None)}")

    # AUDIT (best-effort)
    try:
        base = (payload or {}).get("base", {}) or {}
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
# Read (user-scoped)
# -------------------------------------------------------------------
def list_dc001a_calcs(user_id: str, limit: int = 200) -> List[Tuple[str, str, Any]]:
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
    out: List[Tuple[str, str, Any]] = []
    for r in rows:
        out.append((str(r["id"]), r.get("name", ""), r.get("created_at")))
    return out


def get_dc001a_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    has_design = _probe_design_id()
    fields = "id,name,data,created_at,updated_at" + (",design_id" if has_design else "")
    try:
        resp = (
            _tbl()
            .select(fields)
            .eq("id", calc_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        if _is_undefined_column(e):
            # retry without design_id (and mark cache)
            global _HAS_DESIGN_ID
            _HAS_DESIGN_ID = False
            resp = (
                _tbl()
                .select("id,name,data,created_at,updated_at")
                .eq("id", calc_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
        else:
            raise

    rec = _first_or_none(resp)
    if not rec:
        return None

    data = (rec.get("data") or {}) if isinstance(rec.get("data"), dict) else {}
    data["_meta"] = {
        "id": str(rec["id"]),
        "name": rec.get("name"),
        "design_id": rec.get("design_id") if has_design and "design_id" in rec else None,
        "created_at": rec.get("created_at"),
        "updated_at": rec.get("updated_at"),
    }
    return data


# -------------------------------------------------------------------
# Update / Delete (user-scoped)
# -------------------------------------------------------------------
def update_dc001a_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,
) -> bool:
    sets: Dict[str, Any] = {}
    if name is not None:
        sets["name"] = (name or "DC001A").strip() or "DC001A"
    if data is not None:
        sets["data"] = data

    has_design = _probe_design_id()
    if has_design and design_id is not None:
        sets["design_id"] = design_id

    if not sets:
        return False

    # prefetch name for audit (if not provided)
    nm_for_log = sets.get("name")
    if not nm_for_log:
        pre = (
            _tbl()
            .select("name")
            .eq("id", calc_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        pre_rec = _first_or_none(pre)
        if pre_rec:
            nm_for_log = pre_rec.get("name")

    try:
        resp = (
            _tbl()
            .update(sets)
            .eq("id", calc_id)
            .eq("user_id", user_id)
            .execute()
        )
    except Exception as e:
        if "design_id" in sets and _is_undefined_column(e):
            sets.pop("design_id", None)
            resp = (
                _tbl()
                .update(sets)
                .eq("id", calc_id)
                .eq("user_id", user_id)
                .execute()
            )
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


def delete_dc001a_calc(calc_id: str, user_id: str) -> bool:
    # prefetch name for audit
    name_before = None
    try:
        pre = (
            _tbl()
            .select("name")
            .eq("id", calc_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
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
