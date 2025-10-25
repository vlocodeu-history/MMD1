# dc003_repo.py — psycopg2-safe JSONB writes + optional design_id + public schema
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import ProgrammingError, DBAPIError
from db import connect
from audit import log_on_conn
import json

TABLE = "public.dc003_calcs"
ENTITY = "dc003"

# cache schema probe
_has_design_id_cache: Optional[bool] = None
def _has_design_id(conn) -> bool:
    global _has_design_id_cache
    if _has_design_id_cache is not None:
        return _has_design_id_cache
    row = conn.execute(text("""
        select exists (
          select 1
          from information_schema.columns
          where table_schema = 'public'
            and table_name   = 'dc003_calcs'
            and column_name  = 'design_id'
        )
    """)).scalar()
    _has_design_id_cache = bool(row)
    return _has_design_id_cache

def _insert_stmt(with_design: bool):
    if with_design:
        return text(f"""
            INSERT INTO {TABLE} (user_id, design_id, name, data)
            VALUES (:uid, :design_id, :name, :data)
            RETURNING id::text
        """).bindparams(bindparam("data", type_=JSONB))
    else:
        return text(f"""
            INSERT INTO {TABLE} (user_id, name, data)
            VALUES (:uid, :name, :data)
            RETURNING id::text
        """).bindparams(bindparam("data", type_=JSONB))

def _insert_stmt_fallback(with_design: bool):
    # accepts JSON text via :data_text and casts to jsonb
    if with_design:
        return text(f"""
            INSERT INTO {TABLE} (user_id, design_id, name, data)
            VALUES (:uid, :design_id, :name, (:data_text)::jsonb)
            RETURNING id::text
        """)
    else:
        return text(f"""
            INSERT INTO {TABLE} (user_id, name, data)
            VALUES (:uid, :name, (:data_text)::jsonb)
            RETURNING id::text
        """)

# -------------------------------------------------------------------
# Create
# -------------------------------------------------------------------
def create_dc003_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,   # optional; stored only if column exists
) -> str:
    clean_name = (name or "DC003").strip() or "DC003"
    with connect() as conn:
        use_design = _has_design_id(conn) and (design_id is not None)

        # Preferred: JSONB bind
        try:
            stmt = _insert_stmt(use_design)
            params = {"uid": user_id, "name": clean_name, "data": payload}
            if use_design:
                params["design_id"] = design_id
            rid = conn.execute(stmt, params).scalar()
        except (ProgrammingError, DBAPIError, TypeError):
            # Fallback: serialize then cast ::jsonb in SQL
            stmt = _insert_stmt_fallback(use_design)
            params = {"uid": user_id, "name": clean_name, "data_text": json.dumps(payload)}
            if use_design:
                params["design_id"] = design_id
            rid = conn.execute(stmt, params).scalar()

        # AUDIT (compact base summary if available)
        try:
            base = (payload or {}).get("base", {}) or {}
            log_on_conn(
                conn, "create", ENTITY,
                entity_id=rid, name=clean_name,
                details={"summary": {
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                }},
            )
        except Exception:
            pass

    return str(rid)

# -------------------------------------------------------------------
# List (user-scoped)
# -------------------------------------------------------------------
def list_dc003_calcs(user_id: str, limit: int = 50) -> List[Tuple[str, str, Any, Any]]:
    sql = text(f"""
        SELECT id::text, name, created_at, updated_at
        FROM {TABLE}
        WHERE user_id = :uid
        ORDER BY updated_at DESC, created_at DESC
        LIMIT :lim
    """)
    with connect() as conn:
        rows = conn.execute(sql, {"uid": user_id, "lim": int(limit)}).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]

# -------------------------------------------------------------------
# Get one (user-scoped)
# -------------------------------------------------------------------
def get_dc003_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    sql = text(f"""
        SELECT data
        FROM {TABLE}
        WHERE id = :id AND user_id = :uid
    """)
    with connect() as conn:
        row = conn.execute(sql, {"id": calc_id, "uid": user_id}).one_or_none()
    return row[0] if row else None

# -------------------------------------------------------------------
# Update (user-scoped) + audit
# -------------------------------------------------------------------
def update_dc003_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,   # optional; applied only if column exists
) -> bool:
    sets: List[str] = []
    params: Dict[str, Any] = {"id": calc_id, "uid": user_id}
    bind_json = False

    if name is not None:
        params["name"] = (name or "DC003").strip() or "DC003"
        sets.append("name = :name")
    if payload is not None:
        params["data"] = payload
        sets.append("data = :data")
        bind_json = True

    with connect() as conn:
        if design_id is not None and _has_design_id(conn):
            params["design_id"] = design_id
            sets.append("design_id = :design_id")

        if not sets:
            return False

        sql = f"""
            UPDATE {TABLE}
            SET {', '.join(sets)}, updated_at = now()
            WHERE id = :id AND user_id = :uid
        """
        stmt = text(sql)
        if bind_json:
            stmt = stmt.bindparams(bindparam("data", type_=JSONB))

        # fetch old name for robust logging
        try:
            old_name = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id AND user_id = :uid"),
                {"id": calc_id, "uid": user_id},
            ).scalar()
        except Exception:
            old_name = None

        # Try JSONB bind; fallback to text cast if needed
        try:
            res = conn.execute(stmt, params)
            ok = (res.rowcount or 0) > 0
        except (ProgrammingError, DBAPIError, TypeError):
            if "data" in params:
                params = dict(params)
                params["data_text"] = json.dumps(params.pop("data"))
                stmt = text(sql.replace("data = :data", "data = (:data_text)::jsonb"))
            res = conn.execute(stmt, params)
            ok = (res.rowcount or 0) > 0

        if ok:
            try:
                nm_for_log = params.get("name", old_name)
                log_on_conn(conn, "update", ENTITY, entity_id=calc_id, name=nm_for_log)
            except Exception:
                pass

        return ok

# -------------------------------------------------------------------
# Delete (user-scoped) + audit with deleted name
# -------------------------------------------------------------------
def delete_dc003_calc(calc_id: str, user_id: str) -> bool:
    with connect() as conn:
        # prefetch name BEFORE delete so audit shows the deleted name
        try:
            name_before = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id AND user_id = :uid"),
                {"id": calc_id, "uid": user_id},
            ).scalar()
        except Exception:
            name_before = None

        res = conn.execute(
            text(f"DELETE FROM {TABLE} WHERE id = :id AND user_id = :uid"),
            {"id": calc_id, "uid": user_id},
        )
        ok = (res.rowcount or 0) > 0

        if ok:
            try:
                log_on_conn(conn, "delete", ENTITY, entity_id=calc_id, name=name_before)
            except Exception:
                pass

        return ok
