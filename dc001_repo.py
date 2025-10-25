# dc001_repo.py — psycopg2-safe, no exception probing, JSONB binding
from __future__ import annotations
from typing import Any, Dict, List, Optional
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from db import connect
from audit import log_on_conn

TABLE = "public.dc001_calcs"
ENTITY = "dc001"

# cache for schema probe
_has_design_id_cache: Optional[bool] = None

def _has_design_id(conn) -> bool:
    global _has_design_id_cache
    if _has_design_id_cache is not None:
        return _has_design_id_cache
    row = conn.execute(
        text("""
            select exists (
              select 1
              from information_schema.columns
              where table_schema = 'public'
                and table_name   = 'dc001_calcs'
                and column_name  = 'design_id'
            )
        """)
    ).scalar()
    _has_design_id_cache = bool(row)
    return _has_design_id_cache

# -------------------------------------------------------------------
# Create
# -------------------------------------------------------------------
def create_dc001_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,
) -> str:
    nm = (name or "DC001").strip() or "DC001"
    with connect() as conn:
        if _has_design_id(conn) and design_id is not None:
            stmt = text(f"""
                INSERT INTO {TABLE} (user_id, design_id, name, data)
                VALUES (:uid, :design_id, :name, :data)
                RETURNING id::text
            """).bindparams(bindparam("data", type_=JSONB))
            params = {"uid": user_id, "design_id": design_id, "name": nm, "data": payload}
        else:
            stmt = text(f"""
                INSERT INTO {TABLE} (user_id, name, data)
                VALUES (:uid, :name, :data)
                RETURNING id::text
            """).bindparams(bindparam("data", type_=JSONB))
            params = {"uid": user_id, "name": nm, "data": payload}

        new_id = conn.execute(stmt, params).scalar()

        # AUDIT (best-effort)
        try:
            log_on_conn(
                conn,
                "CREATE",
                ENTITY,
                entity_id=new_id,
                name=nm,
                details={
                    "summary": {
                        "nps_in": payload.get("base", {}).get("nps_in"),
                        "asme_class": payload.get("base", {}).get("asme_class"),
                    }
                },
            )
        except Exception:
            pass

        return new_id  # type: ignore[return-value]

# -------------------------------------------------------------------
# Read (user-scoped)
# -------------------------------------------------------------------
def list_dc001_calcs(user_id: str, limit: int = 200):
    with connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT id::text, name, created_at, updated_at
                FROM {TABLE}
                WHERE user_id = :uid
                ORDER BY updated_at DESC, created_at DESC
                LIMIT :lim
            """),
            {"uid": user_id, "lim": limit},
        ).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]

def get_dc001_calc(calc_id: str, user_id: str) -> dict | None:
    with connect() as conn:
        r = conn.execute(
            text(f"""
                SELECT id::text, name, data, created_at, updated_at
                FROM {TABLE}
                WHERE id = :id AND user_id = :uid
            """),
            {"id": calc_id, "uid": user_id},
        ).mappings().first()
    if not r:
        return None
    out = dict(r["data"] or {})
    out["_meta"] = {
        "id": r["id"],
        "name": r["name"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }
    return out

def get_dc001_meta(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        if _has_design_id(conn):
            sql = f"""
                SELECT id::text AS id, name, design_id::text AS design_id,
                       created_at, updated_at, data
                FROM {TABLE}
                WHERE id = :id AND user_id = :uid
            """
        else:
            sql = f"""
                SELECT id::text AS id, name,
                       created_at, updated_at, data
                FROM {TABLE}
                WHERE id = :id AND user_id = :uid
            """
        row = conn.execute(text(sql), {"id": calc_id, "uid": user_id}).mappings().one_or_none()
    if not row:
        return None
    d = dict(row)
    if "design_id" not in d:
        d["design_id"] = None
    return d

# -------------------------------------------------------------------
# Update / Delete (user-scoped)
# -------------------------------------------------------------------
def update_dc001_calc(
    calc_id: str,
    user_id: str,
    *,
    name: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    design_id: Optional[str] = None,
) -> bool:
    sets: List[str] = []
    params: Dict[str, Any] = {"id": calc_id, "uid": user_id}
    bind_json = False

    if name is not None:
        params["name"] = (name or "DC001").strip() or "DC001"
        sets.append("name = :name")
    if data is not None:
        params["data"] = data
        sets.append("data = :data")
        bind_json = True

    with connect() as conn:
        sql: str
        if design_id is not None and _has_design_id(conn):
            params["design_id"] = design_id
            if sets:
                sets.append("design_id = :design_id")
            else:
                sets = ["design_id = :design_id"]
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

        res = conn.execute(stmt, params)
        ok = (res.rowcount or 0) > 0

        if ok:
            # ensure we log a name even if not provided
            nm_for_log = params.get("name")
            if not nm_for_log:
                try:
                    nm_for_log = conn.execute(
                        text(f"SELECT name FROM {TABLE} WHERE id = :id AND user_id = :uid"),
                        {"id": calc_id, "uid": user_id},
                    ).scalar()
                except Exception:
                    nm_for_log = None
            try:
                log_on_conn(conn, "UPDATE", ENTITY, entity_id=calc_id, name=nm_for_log)
            except Exception:
                pass

        return ok

def delete_dc001_calc(calc_id: str, user_id: str) -> bool:
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
                log_on_conn(conn, "DELETE", ENTITY, entity_id=calc_id, name=name_before)
            except Exception:
                pass
        return ok

# -------------------------------------------------------------------
# Admin helpers (no user filter)
# -------------------------------------------------------------------
def admin_delete_dc001_calc(calc_id: str) -> bool:
    with connect() as conn:
        try:
            name_before = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id"),
                {"id": calc_id},
            ).scalar()
        except Exception:
            name_before = None

        res = conn.execute(text(f"DELETE FROM {TABLE} WHERE id = :id"), {"id": calc_id})
        ok = (res.rowcount or 0) > 0
        if ok:
            try:
                log_on_conn(conn, "DELETE", ENTITY, entity_id=calc_id, name=name_before)
            except Exception:
                pass
        return ok

def get_dc001_calc_with_user(calc_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        if _has_design_id(conn):
            sql = f"""
                SELECT
                  dc.id::text AS id,
                  dc.name,
                  dc.design_id::text AS design_id,
                  dc.created_at,
                  dc.updated_at,
                  u.id::text AS user_id,
                  u.username,
                  dc.data
                FROM {TABLE} dc
                JOIN public.users u ON u.id = dc.user_id
                WHERE dc.id = :id
            """
        else:
            sql = f"""
                SELECT
                  dc.id::text AS id,
                  dc.name,
                  dc.created_at,
                  dc.updated_at,
                  u.id::text AS user_id,
                  u.username,
                  dc.data
                FROM {TABLE} dc
                JOIN public.users u ON u.id = dc.user_id
                WHERE dc.id = :id
            """
        row = conn.execute(text(sql), {"id": calc_id}).mappings().one_or_none()
    if not row:
        return None
    d = dict(row)
    if "design_id" not in d:
        d["design_id"] = None
    return d

def list_all_dc001_calcs(
    *,
    limit: int = 500,
    username_like: Optional[str] = None,
    name_like: Optional[str] = None,
    design_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    where = ["1=1"]
    params: Dict[str, Any] = {"lim": int(limit)}

    if username_like:
        where.append("u.username ILIKE :uname")
        params["uname"] = f"%{username_like}%"
    if name_like:
        where.append("dc.name ILIKE :dname")
        params["dname"] = f"%{name_like}%"
    if design_id:
        where.append("dc.design_id = :design_id")
        params["design_id"] = design_id

    with connect() as conn:
        if _has_design_id(conn):
            sql = f"""
                SELECT
                  dc.id::text           AS id,
                  dc.name               AS name,
                  dc.design_id::text    AS design_id,
                  dc.created_at         AS created_at,
                  dc.updated_at         AS updated_at,
                  u.id::text            AS user_id,
                  u.username            AS username,

                  (dc.data->'base'->>'nps_in')::text         AS nps_in,
                  (dc.data->'base'->>'asme_class')::text     AS asme_class,
                  (dc.data->'inputs'->>'material')::text     AS material,
                  (dc.data->'inputs'->>'Y_max_MPa')::text    AS Y_max_MPa,
                  (dc.data->'inputs'->>'Dm_mm')::text        AS Dm_mm,
                  (dc.data->'inputs'->>'De_mm')::text        AS De_mm,
                  (dc.data->'inputs'->>'Di_mm')::text        AS Di_mm,
                  (dc.data->'inputs'->>'Dc_mm')::text        AS Dc_mm,
                  (dc.data->'inputs'->>'Pa_MPa')::text       AS Pa_MPa,

                  (dc.data->'computed'->>'Fmt_N')::text                    AS Fmt_N,
                  (dc.data->'computed'->>'Pr_N')::text                     AS Pr_N,
                  (dc.data->'computed'->>'Nm')::text                       AS Nm,
                  (dc.data->'computed'->>'Nmr')::text                      AS Nmr,
                  (dc.data->'computed'->>'Fmr_N')::text                    AS Fmr_N,
                  (dc.data->'computed'->>'F_N')::text                      AS F_N,
                  (dc.data->'computed'->>'Q_MPa')::text                    AS Q_MPa,
                  (dc.data->'computed'->>'Dcs_mm')::text                   AS Dcs_mm,
                  (dc.data->'computed'->>'C1_effective_N_per_mm')::text    AS C1_effective_N_per_mm,
                  (dc.data->'computed'->>'spring_check')::text             AS spring_check,
                  (dc.data->'computed'->>'result')::text                   AS result

                FROM {TABLE} dc
                JOIN public.users u ON u.id = dc.user_id
                WHERE {" AND ".join(where)}
                ORDER BY dc.updated_at DESC, dc.created_at DESC
                LIMIT :lim
            """
        else:
            sql = f"""
                SELECT
                  dc.id::text           AS id,
                  dc.name               AS name,
                  NULL::text            AS design_id,
                  dc.created_at         AS created_at,
                  dc.updated_at         AS updated_at,
                  u.id::text            AS user_id,
                  u.username            AS username,

                  (dc.data->'base'->>'nps_in')::text         AS nps_in,
                  (dc.data->'base'->>'asme_class')::text     AS asme_class,
                  (dc.data->'inputs'->>'material')::text     AS material,
                  (dc.data->'inputs'->>'Y_max_MPa')::text    AS Y_max_MPa,
                  (dc.data->'inputs'->>'Dm_mm')::text        AS Dm_mm,
                  (dc.data->'inputs'->>'De_mm')::text        AS De_mm,
                  (dc.data->'inputs'->>'Di_mm')::text        AS Di_mm,
                  (dc.data->'inputs'->>'Dc_mm')::text        AS Dc_mm,
                  (dc.data->'inputs'->>'Pa_MPa')::text       AS Pa_MPa,

                  (dc.data->'computed'->>'Fmt_N')::text                    AS Fmt_N,
                  (dc.data->'computed'->>'Pr_N')::text                     AS Pr_N,
                  (dc.data->'computed'->>'Nm')::text                       AS Nm,
                  (dc.data->'computed'->>'Nmr')::text                      AS Nmr,
                  (dc.data->'computed'->>'Fmr_N')::text                    AS Fmr_N,
                  (dc.data->'computed'->>'F_N')::text                      AS F_N,
                  (dc.data->'computed'->>'Q_MPa')::text                    AS Q_MPa,
                  (dc.data->'computed'->>'Dcs_mm')::text                   AS Dcs_mm,
                  (dc.data->'computed'->>'C1_effective_N_per_mm')::text    AS C1_effective_N_per_mm,
                  (dc.data->'computed'->>'spring_check')::text             AS spring_check,
                  (dc.data->'computed'->>'result')::text                   AS result

                FROM {TABLE} dc
                JOIN public.users u ON u.id = dc.user_id
                WHERE {" AND ".join(where)}
                ORDER BY dc.updated_at DESC, dc.created_at DESC
                LIMIT :lim
            """
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
