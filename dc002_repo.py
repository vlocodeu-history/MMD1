# dc002_repo.py — psycopg2-safe JSONB writes + optional design_id + public schema
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import ProgrammingError, DBAPIError
from db import connect
from audit import log_on_conn
import json

TABLE = "public.dc002_calcs"
ENTITY = "dc002"

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
            and table_name   = 'dc002_calcs'
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
def create_dc002_calc(
    user_id: str,
    name: str,
    data: Dict[str, Any],
    design_id: Optional[str] = None,   # optional; stored only if the column exists
) -> str:
    nm = (name or "DC002").strip() or "DC002"
    with connect() as conn:
        use_design = _has_design_id(conn) and (design_id is not None)

        # Preferred: JSONB bind
        try:
            stmt = _insert_stmt(use_design)
            params = {"uid": user_id, "name": nm, "data": data}
            if use_design:
                params["design_id"] = design_id
            rid = conn.execute(stmt, params).scalar()
        except (ProgrammingError, DBAPIError, TypeError):
            # Fallback: serialize then cast ::jsonb in SQL
            stmt = _insert_stmt_fallback(use_design)
            params = {"uid": user_id, "name": nm, "data_text": json.dumps(data)}
            if use_design:
                params["design_id"] = design_id
            rid = conn.execute(stmt, params).scalar()

        # AUDIT (compact base summary if present)
        try:
            base = (data or {}).get("base", {}) or {}
            log_on_conn(
                conn, "create", ENTITY,
                entity_id=rid, name=nm,
                details={"summary": {
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                }},
            )
        except Exception:
            pass

    return str(rid)

# -------------------------------------------------------------------
# List (by user)
# -------------------------------------------------------------------
def list_dc002_calcs(user_id: str, limit: int = 500) -> List[Tuple[str, str, str, str]]:
    sql = text(f"""
        SELECT
            id::text,
            name,
            to_char((created_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS created_at,
            to_char((updated_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS updated_at
        FROM {TABLE}
        WHERE user_id = :uid
        ORDER BY updated_at DESC, created_at DESC
        LIMIT :lim
    """)
    with connect() as conn:
        rows = conn.execute(sql, {"uid": user_id, "lim": int(limit)}).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]

# -------------------------------------------------------------------
# Get one (merge data + meta)
# -------------------------------------------------------------------
def get_dc002_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    sql = text(f"""
        SELECT
            id::text AS id,
            name,
            data,
            to_char((created_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS created_at,
            to_char((updated_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS updated_at
        FROM {TABLE}
        WHERE id = :id AND user_id = :uid
    """)
    with connect() as conn:
        row = conn.execute(sql, {"id": calc_id, "uid": user_id}).mappings().first()
    if not row:
        return None
    data = row.get("data") or {}
    out: Dict[str, Any] = {}
    out.update(data if isinstance(data, dict) else {})
    out["id"] = row.get("id")
    out["name"] = row.get("name")
    out["created_at"] = row.get("created_at")
    out["updated_at"] = row.get("updated_at")
    return out

def get_dc002_calc_with_meta(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    sql = text(f"""
        SELECT
            id::text AS id,
            name,
            data,
            to_char((created_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS created_at,
            to_char((updated_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS updated_at
        FROM {TABLE}
        WHERE id = :id AND user_id = :uid
    """)
    with connect() as conn:
        r = conn.execute(sql, {"id": calc_id, "uid": user_id}).mappings().first()
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
    if name is None and data is None and design_id is None:
        return False

    sets: List[str] = []
    params: Dict[str, Any] = {"id": calc_id, "uid": user_id}
    bind_json = False

    if name is not None:
        params["name"] = (name or "DC002").strip() or "DC002"
        sets.append("name = :name")
    if data is not None:
        params["data"] = data
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

        # fetch old name first for audit fallback
        try:
            old_name = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id AND user_id = :uid"),
                {"id": calc_id, "uid": user_id},
            ).scalar()
        except Exception:
            old_name = None

        # try JSONB bind, then fallback to ::jsonb text cast if needed
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
# Delete + audit
# -------------------------------------------------------------------
def delete_dc002_calc(calc_id: str, user_id: str) -> bool:
    with connect() as conn:
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

# -------------------------------------------------------------------
# Admin list all (optional)
# -------------------------------------------------------------------
def list_dc002_all(limit: int = 500) -> List[Dict[str, Any]]:
    sql = text(f"""
        SELECT
            c.id::text,
            c.user_id::text,
            u.username,
            c.name,
            to_char((c.created_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS created_at,
            to_char((c.updated_at AT TIME ZONE 'UTC'), 'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS updated_at
        FROM {TABLE} c
        JOIN public.users u ON u.id = c.user_id
        ORDER BY c.updated_at DESC, c.created_at DESC
        LIMIT :lim
    """)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, {"lim": int(limit)}).mappings().all()]
