# dc011_repo.py — psycopg2-safe JSONB writes + optional design_id + public schema
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import text, bindparam
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import ProgrammingError, DBAPIError
from db import connect
from audit import log_on_conn
import json

TABLE  = "public.dc011_calcs"
ENTITY = "dc011"

# --- schema probe cache (design_id optional) ---
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
            and table_name   = 'dc011_calcs'
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
    # Fallback path when the driver can't adapt dict -> use text + ::jsonb
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
def create_dc011_calc(
    user_id: str,
    name: str,
    payload: Dict[str, Any],
    design_id: Optional[str] = None,
) -> str:
    clean_name = (name or "DC011").strip() or "DC011"
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
            # Fallback: serialize -> ::jsonb cast
            stmt = _insert_stmt_fallback(use_design)
            params = {"uid": user_id, "name": clean_name, "data_text": json.dumps(payload)}
            if use_design:
                params["design_id"] = design_id
            rid = conn.execute(stmt, params).scalar()

        # AUDIT (compact summary if available)
        try:
            base = (payload or {}).get("base", {}) or {}
            log_on_conn(
                conn, "create", ENTITY,
                entity_id=rid, name=clean_name,
                details={"summary": {
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "valve_design_id": base.get("valve_design_id") or design_id,
                }},
            )
        except Exception:
            pass

        return str(rid)

# -------------------------------------------------------------------
# Read (user-scoped)
# -------------------------------------------------------------------
def list_dc011_calcs(user_id: str, limit: int = 200) -> List[Tuple[str, str, Any, Any]]:
    with connect() as conn:
        rows = conn.execute(
            text(f"""
                SELECT id::text, name, created_at, updated_at
                FROM {TABLE}
                WHERE user_id = :uid
                ORDER BY updated_at DESC, created_at DESC
                LIMIT :lim
            """),
            {"uid": user_id, "lim": int(limit)},
        ).fetchall()
    return [(r[0], r[1], r[2], r[3]) for r in rows]

def get_dc011_calc(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        r = conn.execute(
            text(f"""
                SELECT id::text, name, data, created_at, updated_at,
                       design_id::text AS design_id
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
        "design_id": r["design_id"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }
    return out

def get_dc011_meta(calc_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    sql = f"""
        SELECT id::text AS id, name, design_id::text AS design_id,
               created_at, updated_at, data
        FROM {TABLE}
        WHERE id = :id AND user_id = :uid
    """
    with connect() as conn:
        row = conn.execute(text(sql), {"id": calc_id, "uid": user_id}).mappings().one_or_none()
    return dict(row) if row else None

# -------------------------------------------------------------------
# Update / Delete (user-scoped)
# -------------------------------------------------------------------
def update_dc011_calc(
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
        params["name"] = (name or "DC011").strip() or "DC011"
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
            SET {", ".join(sets)}, updated_at = now()
            WHERE id = :id AND user_id = :uid
        """
        stmt = text(sql)
        if bind_json:
            stmt = stmt.bindparams(bindparam("data", type_=JSONB))

        # Fetch old name for robust audit logging
        try:
            old_name = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id AND user_id = :uid"),
                {"id": calc_id, "uid": user_id},
            ).scalar()
        except Exception:
            old_name = None

        # Try JSONB bind; fallback to text cast if driver objects
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
                name_for_log = params.get("name", old_name)
                log_on_conn(conn, "update", ENTITY, entity_id=calc_id, name=name_for_log)
            except Exception:
                pass

        return ok

def delete_dc011_calc(calc_id: str, user_id: str) -> bool:
    sql = f"DELETE FROM {TABLE} WHERE id = :id AND user_id = :uid"
    with connect() as conn:
        # Fetch name before delete so the audit includes it
        try:
            name_before = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id AND user_id = :uid"),
                {"id": calc_id, "uid": user_id},
            ).scalar()
        except Exception:
            name_before = None

        res = conn.execute(text(sql), {"id": calc_id, "uid": user_id})
        ok = (res.rowcount or 0) > 0

        if ok:
            try:
                log_on_conn(conn, "delete", ENTITY, entity_id=calc_id, name=name_before)
            except Exception:
                pass

        return ok

# -------------------------------------------------------------------
# Admin helpers (no user filter)
# -------------------------------------------------------------------
def admin_delete_dc011_calc(calc_id: str) -> bool:
    sql = f"DELETE FROM {TABLE} WHERE id = :id"
    with connect() as conn:
        # Fetch name before delete (admin path) so audit has it
        try:
            name_before = conn.execute(
                text(f"SELECT name FROM {TABLE} WHERE id = :id"),
                {"id": calc_id},
            ).scalar()
        except Exception:
            name_before = None

        res = conn.execute(text(sql), {"id": calc_id})
        ok = (res.rowcount or 0) > 0

        if ok:
            try:
                log_on_conn(conn, "delete", ENTITY, entity_id=calc_id, name=name_before)
            except Exception:
                pass

        return ok

def get_dc011_calc_with_user(calc_id: str) -> Optional[Dict[str, Any]]:
    """
    Return one DC011 row + owner username, name, timestamps, data, design_id.
    """
    sql = f"""
        SELECT
          d.id::text AS id,
          d.name,
          d.design_id::text AS design_id,
          d.created_at,
          d.updated_at,
          u.id::text AS user_id,
          u.username,
          d.data
        FROM {TABLE} d
        JOIN public.users u ON u.id = d.user_id
        WHERE d.id = :id
    """
    with connect() as conn:
        row = conn.execute(text(sql), {"id": calc_id}).mappings().one_or_none()
    return dict(row) if row else None

def list_all_dc011_calcs(
    *,
    limit: int = 500,
    username_like: Optional[str] = None,
    name_like: Optional[str] = None,
    design_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Admin listing across all users with JSON summary columns extracted.
    """
    where = ["1=1"]
    params: Dict[str, Any] = {"lim": int(limit)}

    if username_like:
        where.append("u.username ILIKE :uname")
        params["uname"] = f"%{username_like}%"

    if name_like:
        where.append("d.name ILIKE :dname")
        params["dname"] = f"%{name_like}%"

    if design_id:
        where.append("d.design_id = :design_id")
        params["design_id"] = design_id

    sql = f"""
        SELECT
          d.id::text         AS id,
          d.name             AS name,
          d.design_id::text  AS design_id,
          d.created_at       AS created_at,
          d.updated_at       AS updated_at,
          u.id::text         AS user_id,
          u.username         AS username,

          -- base
          (d.data->'base'->>'valve_design_id')::text    AS valve_design_id,
          (d.data->'base'->>'valve_design_name')::text  AS valve_design_name,
          (d.data->'base'->>'nps_in')::text             AS nps_in,
          (d.data->'base'->>'asme_class')::text         AS asme_class,
          (d.data->'base'->>'bore_diameter_mm')::text   AS bore_mm,
          (d.data->'base'->>'operating_pressure_mpa')::text AS Po_MPa,

          -- inputs
          (d.data->'inputs'->>'inner_bore_mm')::text    AS inner_bore_mm,
          (d.data->'inputs'->>'seat_bore_mm')::text     AS seat_bore_mm,
          (d.data->'inputs'->>'beta')::text             AS beta,
          (d.data->'inputs'->>'theta_deg')::text        AS theta_deg,
          (d.data->'inputs'->>'theta_rad')::text        AS theta_rad,
          (d.data->'inputs'->>'taper_len_mm')::text     AS taper_len_mm,
          (d.data->'inputs'->>'dn_choice_in')::text     AS dn_choice_in,
          (d.data->'inputs'->>'ft')::text               AS ft,

          -- computed
          (d.data->'computed'->>'K1')::text             AS K1,
          (d.data->'computed'->>'K2')::text             AS K2,
          (d.data->'computed'->>'K_local')::text        AS K_local,
          (d.data->'computed'->>'K_fric')::text         AS K_fric,
          (d.data->'computed'->>'K_total')::text        AS K_total,
          (d.data->'computed'->>'Cv_gpm_at_1psi')::text AS Cv

        FROM {TABLE} d
        JOIN public.users u ON u.id = d.user_id
        WHERE {" AND ".join(where)}
        ORDER BY d.updated_at DESC, d.created_at DESC
        LIMIT :lim
    """
    with connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]
