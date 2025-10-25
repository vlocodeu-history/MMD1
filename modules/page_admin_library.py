# page_admin_library.py  — rebuilt from scratch, tab by tab
from __future__ import annotations
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text

from auth import require_role
from db import connect
from valve_repo import list_valve_designs, get_valve_design_with_user

# ---------- Pretty renderers used by Tabs 3–5 ----------

def _normalize_id_name_pairs(rows):
    """
    Turn a variety of shapes (tuple/list/dict/str) into [(id, name), ...].
    - Tuples/lists: (id, name, ...)  -> (id, name)
    - Dicts:        {"id":..,"name":..} or {"design_id":..} -> (id, name)
    - Strings:      "id" -> (id, "Untitled")
    """
    out = []
    for r in rows or []:
        rid, nm = None, "Untitled"
        if isinstance(r, (list, tuple)):
            if len(r) >= 1: rid = r[0]
            if len(r) >= 2 and r[1] not in (None, ""): nm = r[1]
        elif isinstance(r, dict):
            rid = r.get("id") or r.get("design_id")
            nm  = r.get("name") or nm
        elif isinstance(r, str):
            rid = r
        if rid:
            out.append((str(rid), str(nm)))
    return out
# ---------------- DC001: summarize + pretty render (defensive) ----------------
def _dc001_summarize(data: dict) -> dict:
    """
    Accepts any of these shapes:
      {"base": {...}, "inputs": {...}, "computed": {...}}   # new shape
      {"calculated": {...}, "geometry": {...}}              # legacy/alt
      or mixed.

    Returns a flat dict with the most relevant fields for display.
    """
    data = data or {}
    base     = data.get("base") or {}
    inputs   = data.get("inputs") or {}
    computed = data.get("computed") or {}
    calc     = data.get("calculated") or {}
    geom     = data.get("geometry") or {}

    def pick(*names, default=None):
        for n in names:
            if n in data and data[n] not in (None, ""):       return data[n]
            if n in base and base[n] not in (None, ""):       return base[n]
            if n in inputs and inputs[n] not in (None, ""):   return inputs[n]
            if n in computed and computed[n] not in (None, ""): return computed[n]
            if n in calc and calc[n] not in (None, ""):       return calc[n]
            if n in geom and geom[n] not in (None, ""):       return geom[n]
        return default

    return {
        # ---- base / valve context ----
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "P_base_MPa":        base.get("operating_pressure_mpa"),

        # ---- core computed results (common variants) ----
        "Q_MPa":       pick("Q_MPa", "Q"),
        "stress_MPa":  pick("stress_MPa", "sigma_MPa", "tau_MPa"),
        "verdict":     pick("verdict", "result"),

        # ---- common DC001 inputs/derived (use if available; otherwise None) ----
        "Dm":   pick("Dm_mm", "Dm"),
        "c1":   pick("c1_N_per_mm", "c1"),
        "z":    pick("z"),
        "Fmt":  pick("Fmt_N", "Fmt"),
        "P":    pick("P_N", "P"),
        "f":    pick("f_mm", "f"),
        "Nm":   pick("Nm"),
        "Nmr":  pick("Nmr"),
        "Pr":   pick("Pr_N", "Pr"),
        "Nma":  pick("Nma"),
        "Fmr":  pick("Fmr_N", "Fmr"),
        "C1eff": pick("C1_effective_N_per_mm", "C1effective"),
        "Material": pick("material", "Material"),
        "Y_max": pick("Y_max_MPa", "Y_max"),
        "De":   pick("De_mm", "De"),
        "Di":   pick("Di_mm", "Di"),
        "Dcs":  pick("Dcs_mm", "Dcs"),
        "Dc":   pick("Dc_mm", "Dc"),
        "Pa":   pick("Pa_MPa", "Pa"),
        "F":    pick("F_N", "F"),
    }

def _render_dc001_pretty(data: dict):
    """Prettified DC001 view using the summary above."""
    s = _dc001_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("P (base) [MPa]",    s.get("P_base_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs / Derived")
        _kv_table([
            ("Seat insert medium dia. Dm [mm]", s.get("Dm")),
            ("c1 [N/mm]", s.get("c1")),
            ("z [-]", s.get("z")),
            ("Fmt [N]", s.get("Fmt")),
            ("Load at theoric packing P [N]", s.get("P")),
            ("f [mm]", s.get("f")),
            ("Nma [-]", s.get("Nma")),
            ("Nm [-]", s.get("Nm")),
            ("Nmr [-]", s.get("Nmr")),
        ])
        st.markdown("#### Spring Check")
        _kv_table([
            ("Pr [N]", s.get("Pr")),
            ("Fmr [N]", s.get("Fmr")),
            ("C1 effective [N/mm]", s.get("C1eff")),
        ])

    with col2:
        st.markdown("#### Material & Limits")
        _kv_table([
            ("Material", s.get("Material")),
            ("Y max [MPa]", s.get("Y_max")),
        ])
        st.markdown("#### Geometry & Validation")
        _kv_table([
            ("De [mm]", s.get("De")),
            ("Di [mm]", s.get("Di")),
            ("Dcs [mm]", s.get("Dcs")),
            ("Dc [mm]", s.get("Dc")),
            ("Pa [MPa]", s.get("Pa")),
            ("F [N]", s.get("F")),
            ("Q [MPa]", s.get("Q_MPa")),
            ("Stress [MPa]", s.get("stress_MPa")),
            ("Check / Verdict", s.get("verdict")),
        ])

def _render_dc001a_pretty(data: Dict[str, Any]):
    """Show a DC001A record (base/inputs/computed) in tidy tables."""
    data = data or {}
    base = data.get("base") or {}
    ins  = data.get("inputs") or {}
    comp = data.get("computed") or {}

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", base.get("valve_design_name")),
        ("Valve design ID",   base.get("valve_design_id")),
        ("NPS [in]",          base.get("nps_in")),
        ("ASME Class",        base.get("asme_class")),
        ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
        ("Source DC001 name", base.get("source_dc001_name")),
        ("Source DC001 ID",   base.get("source_dc001_id")),
    ])

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Dc [mm] (from DC001 Dm)",  ins.get("Dc_mm_from_dc001_Dm")),
            ("Dts [mm] (from DC001 Dc)", ins.get("Dts_mm_from_dc001_Dc")),
            # Add any extra inputs your schema might have:
            ("Pa [MPa]",                 ins.get("Pa_MPa")),
            ("Material",                 ins.get("material")),
        ])
    with c2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("SR [N] (from DC001 F)",     comp.get("SR_N")),
            ("F_molle [N] (from DC001 Pr)", comp.get("F_molle_N")),
            ("Verdict",                   comp.get("verdict") or comp.get("result")),
        ])


def _render_dc002_pretty(data: Dict[str, Any]):
    """Show a DC002 (bolting) record (base/inputs/computed) in tidy tables."""
    data = data or {}
    base = data.get("base") or {}
    ins  = data.get("inputs") or {}
    comp = data.get("computed") or {}

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", base.get("valve_design_name")),
        ("Valve design ID",   base.get("valve_design_id")),
        ("NPS [in]",          base.get("nps_in")),
        ("ASME Class",        base.get("asme_class")),
        ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
    ])

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Gasket tight diameter G [mm]", ins.get("G_mm")),
            ("Design pressure Pa [MPa]",     ins.get("Pa_MPa")),
            ("Pressure rating Pe [MPa]",     ins.get("Pe_MPa")),
            ("Bolt material",                ins.get("bolt_material")),
            ("Bolts number n",               ins.get("n")),
            ("Bolt size",                    ins.get("bolt_size")),
        ])
    with c2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("Allowable bolt stress S [MPa]",      comp.get("S_MPa")),
            ("Total hydrostatic end force H [N]",   comp.get("H_N")),
            ("Minimum required bolt load Wm1 [N]",  comp.get("Wm1_N")),
            ("Total required area Am [mm²]",        comp.get("Am_mm2")),
            ("Req. area per bolt a' [mm²]",         comp.get("a_req_each_mm2")),
            ("Actual area per bolt a [mm²]",        comp.get("a_mm2")),
            ("Total area Ab [mm²]",                 comp.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]", comp.get("Sa_eff_MPa")),
            ("Check",                               comp.get("verdict") or comp.get("result")),
        ])


def _render_dc002a_pretty(data: Dict[str, Any]):
    """
    Show a DC002A record (base / inputs / computed).
    Covers the full schema used by page_dc002a.py and also supports
    generic fallbacks (input_param, result_val) for legacy records.
    """
    data = data or {}
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", base.get("valve_design_name")),
        ("Valve design ID",   base.get("valve_design_id")),
        ("NPS [in]",          base.get("nps_in")),
        ("ASME Class",        base.get("asme_class")),
        ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
    ])

    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("#### Inputs")
        _kv_table([
            # Full DC002A inputs
            ("Gasket tight diameter G [mm]", ins.get("G_mm")),
            ("Test pressure Pa_test [MPa]",  ins.get("Pa_test_MPa")),
            ("Pressure rating Pe [MPa]",     ins.get("Pe_MPa")),
            ("Bolt material",                ins.get("bolt_material")),
            ("Syb (bolt yield) [MPa]",       ins.get("Syb_MPa")),
            ("Bolts number n",               ins.get("n")),
            ("Bolt size",                    ins.get("bolt_size")),

            # Fallbacks for older/other shapes
            ("Input parameter (legacy)",     ins.get("input_param")),
        ])

    with c2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("Allowable bolt stress S [MPa]",            comp.get("S_MPa")),
            ("Total hydrostatic end force H [N]",         comp.get("H_N")),
            ("Min. required bolt load Wm1 [N]",          comp.get("Wm1_N")),
            ("Total required area Am [mm²]",              comp.get("Am_mm2")),
            ("Req. area per bolt a' [mm²]",               comp.get("a_req_each_mm2")),
            ("Actual area per bolt a [mm²]",              comp.get("a_mm2")),
            ("Total area Ab [mm²]",                       comp.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]",   comp.get("Sa_eff_MPa")),
            ("Result value (legacy)",                     comp.get("result_val")),
            ("Verdict",                                   comp.get("verdict") or comp.get("result")),
        ])

# =============== small display helpers ===============
def _fmt_num(x: Any, digits: int = 2) -> str:
    if x in (None, "", "None"):
        return "—"
    try:
        f = float(x)
        if abs(f - round(f)) < 1e-9:
            return f"{int(round(f))}"
        return f"{f:.{digits}f}"
    except Exception:
        return str(x)

def _fmt_ts(ts: Optional[Any]) -> str:
    """Display timestamps as 'YYYY-MM-DD HH:MM:SS' when possible."""
    if not ts:
        return "—"
    s = str(ts).strip()
    return s[:19] if len(s) >= 19 else s

def _kv_table(pairs: List[tuple[str, Any]], *, digits: int = 2):
    rows = []
    for k, v in pairs:
        if isinstance(v, (int, float)):
            rows.append({"Field": k, "Value": _fmt_num(v, digits)})
        else:
            rows.append({"Field": k, "Value": v if v not in (None, "", "None") else "—"})
    df = pd.DataFrame(rows)
    st.table(df)

# ---------------- Valve pretty renderer ----------------
def _render_valve_pretty(data: Dict[str, Any]):
    inputs     = data.get("inputs", {}) or {}
    materials  = inputs.get("materials", {}) or {}
    allow_st   = inputs.get("allowable_stress", {}) or {}
    calc       = data.get("calculated", {}) or {}

    st.markdown("#### Overview")
    _kv_table([
        ("Nominal Pipe Size (NPS) [in]", data.get("nps_in")),
        ("ASME Class", data.get("asme_class")),
        ("Operating Pressure (MPa)", data.get("calc_operating_pressure_mpa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Input Parameters")
        _kv_table([
            ("Internal Bore (Ball/Seat) [mm]", inputs.get("internal_bore_mm")),
            ("Face to Face (F-F) [mm]", inputs.get("face_to_face_mm")),
            ("Design Temperature Min (°C)", inputs.get("temp_min_c")),
            ("Design Temperature Max (°C)", inputs.get("temp_max_c")),
            ("Corrosion Allowance CA [mm]", inputs.get("corrosion_allowance_mm")),
        ])
        st.markdown("#### Allowable Stress")
        _kv_table([
            ("Preset", allow_st.get("preset")),
            ("Allowable Stress S [MPa]", allow_st.get("S_mpa")),
        ])
    with col2:
        st.markdown("#### Materials")
        _kv_table([
            ("Body / Closure", materials.get("body_closure")),
            ("Ball / Seat", materials.get("ball_seat")),
            ("Stem", materials.get("stem_material")),
            ("Insert", materials.get("insert_material")),
            ("Bolts", materials.get("bolts_material")),
            ("Flange Ends", materials.get("flange_ends")),
        ])
        st.markdown("#### Calculated Values")
        _kv_table([
            ("Bore Diameter (mm)", calc.get("bore_diameter_mm")),
            ("Face to Face (mm)", calc.get("face_to_face_mm")),
            ("Body Wall Thickness (mm) — demo", calc.get("body_wall_thickness_mm")),
        ])

# =============== PAGE ENTRYPOINT ===============
def render_admin_library():
    require_role(["superadmin"])
    st.subheader("Admin Library")

    # NOTE: We will fill the tab bodies one by one across messages.
    tabs = st.tabs([
        "Activity Logs (Users + Admin)",   # tabs[0] NEW — full audit stream
        "Valve Designs (All Users)",       # tabs[1]
        "DC001 Calculations (All Users)",  # tabs[2]
        "DC001A Calculations (All Users)", # tabs[3]
        "DC002 Calculations (All Users)",  # tabs[4]
        "DC002A Calculations (All Users)", # tabs[5]
        "DC003 Calculations (All Users)",  # tabs[6]
        "DC004 Calculations (All Users)",  # tabs[7]
        "DC005 Calculations (All Users)",  # tabs[8]
        "DC005A Calculations (All Users)", # tabs[9]
        "DC006 Calculations (All Users)",  # tabs[10]
        "DC006A Calculations (All Users)", # tabs[11]
        "DC007 Body (All Users)",          # tabs[12]
        "DC007 Body Holes (All Users)",    # tabs[13]
        "DC008 Ball Sizing (All Users)",   # tabs[14]
        "DC010 (All Users)",               # tabs[15]
        "DC011 (All Users)",               # tabs[16]
        "DC012 (All Users)",               # tabs[17]
    ])

    # ======================= TAB 0: ACTIVITY LOGS =======================
    with tabs[0]:
        st.caption("Unified audit stream of creates / updates / deletes across all entities, by users and admins.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username / Email contains", key="audit_user_filter")
                f_role = st.selectbox("Actor Role", ["(any)","user","superadmin","admin"], index=0, key="audit_role_filter")
            with c2:
                f_entity = st.selectbox(
                    "Entity Type",
                    ["(any)","valve_design","dc001","dc001a","dc002","dc002a","dc003","dc004","dc005","dc005a","dc006","dc006a","dc007_body","dc007_body_holes","dc008","dc010","dc011","dc012"],
                    index=0, key="audit_entity_filter"
                )
                f_action = st.selectbox("Action", ["(any)","create","update","delete","rename","login","export"], index=0, key="audit_action_filter")
            with c3:
                limit = st.number_input("Max rows", min_value=50, max_value=20000, step=50, value=1000, key="audit_limit")
                order_desc = st.checkbox("Newest first", value=True, key="audit_desc")
            btn = st.button("Apply filters / Refresh (Logs)", type="primary", key="audit_refresh")

        # Build SQL (assumes an 'audit_logs' table)
        # Columns assumed:
        #   id, created_at, actor_user_id, actor_username, actor_role,
        #   action, entity_type, entity_id, name, details (json/text), ip_addr
        where = ["1=1"]
        params = {"lim": int(limit)}

        if f_user.strip():
            where.append("al.actor_username ILIKE :uname")
            params["uname"] = f"%{f_user.strip()}%"

        if f_role != "(any)":
            where.append("lower(al.actor_role) = :role")
            params["role"] = f_role.lower()

        if f_entity != "(any)":
            where.append("lower(al.entity_type) = :etype")
            params["etype"] = f_entity.lower()

        if f_action != "(any)":
            where.append("lower(al.action) = :action")
            params["action"] = f_action.lower()

        sql = f"""
            SELECT
            al.id::text            AS id,
            al.created_at          AS created_at,
            al.actor_user_id::text AS actor_user_id,
            al.actor_username      AS actor_username,
            al.actor_role          AS actor_role,
            al.action              AS action,
            al.entity_type         AS entity_type,
            al.entity_id::text     AS entity_id,
            al.name                AS name,
            al.details             AS details,
            al.ip_addr             AS ip_addr
            FROM public.audit_logs al
            WHERE {" AND ".join(where)}
            ORDER BY al.created_at {"DESC" if order_desc else "ASC"}
            LIMIT :lim
        """


        if btn or "admin_cache_audit" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), params).mappings().all()
                    st.session_state["admin_cache_audit"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Failed to read audit logs: {e}")
                st.session_state["admin_cache_audit"] = []

        logs: List[Dict[str, Any]] = st.session_state.get("admin_cache_audit", [])

        if not logs:
            st.info("No audit rows for the selected filters.")
        else:
            df = pd.DataFrame(logs)
            if "created_at" in df: df["created_at"] = df["created_at"].map(_fmt_ts)
            cols = ["created_at","actor_username","actor_role","action","entity_type","name","entity_id","ip_addr","id"]
            # include details if it exists
            if "details" in df.columns:
                cols.insert(7, "details")
            df_show = df.reindex(columns=[c for c in cols if c in df.columns])
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=420)

            # Export
            csv = df_show.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (Audit Logs)", data=csv, file_name="audit_logs.csv", mime="text/csv", key="audit_export")

            st.markdown("---")
            st.markdown("### Inspect: focus on one actor")
            actor_opts = ["-- select actor --"] + sorted({f"{r['actor_username']} • {r.get('actor_role','')}" for r in logs if r.get("actor_username")})
            pick_actor = st.selectbox("Actor", actor_opts, key="audit_pick_actor")
            if pick_actor and pick_actor != "-- select actor --":
                actor_username = pick_actor.split(" • ", 1)[0]
                df_actor = df[df["actor_username"] == actor_username].copy()
                df_actor["created_at"] = df_actor["created_at"].map(_fmt_ts)
                st.dataframe(
                    df_actor.reindex(columns=[c for c in df_show.columns if c in df_actor.columns]),
                    use_container_width=True, hide_index=True, height=360
                )
                csv_a = df_actor.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Export CSV (Actor subset)", data=csv_a,
                                   file_name=f"audit_{actor_username.replace('@','_')}.csv", mime="text/csv", key="audit_export_actor")
    # ======================= TAB 1: VALVE DESIGNS (ALL USERS) =======================
    with tabs[1]:
        st.caption("Browse users, see their most recent valve design at a glance, then drill into full summaries or any saved design.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                f_user = st.text_input("Username contains", value="", key="adm_valve_user_filter")
            with c2:
                f_name = st.text_input("Latest design name contains", value="", key="adm_valve_designname_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_valve_limit")
            btn_refresh = st.button("Apply filters / Refresh (Valve)", type="primary", key="adm_valve_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("vd_latest.name ILIKE :dname")

        sql = f"""
            SELECT
            u.id::text                  AS user_id,
            u.username                  AS username,
            COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
            vd_latest.id::text          AS design_id,
            vd_latest.name              AS design_name,
            vd_latest.created_at        AS created_at,
            vd_latest.updated_at        AS updated_at,
            (vd_latest.data->>'nps_in')::text AS nps_in,
            (vd_latest.data->>'asme_class')::text AS asme_class,
            (vd_latest.data->'calculated'->>'bore_diameter_mm')::text  AS bore_mm,
            (vd_latest.data->'calculated'->>'face_to_face_mm')::text   AS f2f_mm,
            (vd_latest.data->'calculated'->>'body_wall_thickness_mm')::text AS t_mm
            FROM users u
            LEFT JOIN LATERAL (
                SELECT id, name, created_at, updated_at, data
                FROM valve_designs vd
                WHERE vd.user_id = u.id
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
            ) vd_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(vd_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn_refresh or "admin_users_cache_valve" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_valve"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_valve"] = []
        users_latest: List[Dict[str, Any]] = st.session_state.get("admin_users_cache_valve", [])

        if not users_latest:
            st.info("No users or designs found for the filters.")
        else:
            df_u = pd.DataFrame(users_latest)
            for col in ("nps_in","asme_class","bore_mm","f2f_mm","t_mm"):
                if col in df_u.columns:
                    df_u[col] = pd.to_numeric(df_u[col], errors="coerce")

            st.markdown("### Users • Latest valve design at a glance")
            df_u["created_at"] = df_u["created_at"].map(_fmt_ts)
            df_u["updated_at"] = df_u["updated_at"].map(_fmt_ts)
            cols_out = ["user_id","full_name","username","design_id","design_name","nps_in","asme_class","bore_mm","f2f_mm","t_mm","created_at","updated_at"]
            df_show = df_u.reindex(columns=cols_out)
            st.dataframe(df_show, use_container_width=True, hide_index=True)

            csv = df_show.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (Valve latest per user)", data=csv, file_name="users_latest_valve_designs.csv", mime="text/csv", key="adm_valve_export_latest")

            st.markdown("---")
            st.markdown("### Inspect a specific user's valve designs")
            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_label = st.selectbox("User", user_opts, key="adm_valve_pick_user")
            if pick_label and pick_label != "-- select user --":
                label_to_id = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}
                sel_user_id = label_to_id.get(pick_label)
                sel_user = next((r for r in users_latest if r["user_id"] == sel_user_id), None)
                if sel_user:
                    st.markdown(f"**User:** {sel_user.get('full_name') or sel_user['username']}  \n**Username / Email:** {sel_user['username']}")
                    latest_design_id = sel_user.get("design_id")
                    if latest_design_id:
                        st.markdown("#### Latest Design (prettified)")
                        try:
                            rec = get_valve_design_with_user(latest_design_id)
                        except Exception:
                            rec = None
                        if rec and rec.get("data"):
                            _render_valve_pretty(rec["data"])
                            st.caption(
                                f"Name: **{rec.get('name','—')}** • "
                                f"Created: **{_fmt_ts(rec.get('created_at'))}** • "
                                f"Updated: **{_fmt_ts(rec.get('updated_at'))}**"
                            )
                        else:
                            st.info("No latest design data available.")
                    else:
                        st.info("This user hasn't saved any designs yet.")

                    st.markdown("---")
                    st.markdown("#### All Designs for this User")
                    try:
                        raw_designs = list_valve_designs(sel_user_id, limit=500)
                    except Exception:
                        raw_designs = []
                    designs = _normalize_id_name_pairs(raw_designs)

                    if not designs:
                        st.info("No designs found for this user.")
                    else:
                        labels = [f"{nm} ({did[:8]}…)" for (did, nm) in designs]
                        d_opts = ["-- select design --"] + labels
                        d_pick = st.selectbox("Design", d_opts, key=f"adm_pick_design_{sel_user_id}")
                        if d_pick and d_pick != "-- select design --":
                            label_to_id2 = dict(zip(labels, [did for (did, _nm) in designs]))
                            design_id = label_to_id2.get(d_pick)
                            if design_id:
                                try:
                                    rec = get_valve_design_with_user(design_id)
                                except Exception:
                                    rec = None
                                if rec and rec.get("data"):
                                    st.markdown(
                                        f"**Owner:** {rec.get('username','—')} • "
                                        f"**Name:** {rec.get('name','—')} • "
                                        f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                        f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                                    )
                                    _render_valve_pretty(rec["data"])

                                    st.markdown("")
                                    if st.button("🗑️ Delete this design (admin)", type="secondary", key=f"adm_del_valve_{design_id}"):
                                        try:
                                            with connect() as conn:
                                                conn.execute(text("DELETE FROM valve_designs WHERE id = :id"), {"id": design_id})
                                        except Exception as e:
                                            st.error(f"Delete failed: {e}")
                                        else:
                                            st.success("Deleted.")
                                            st.session_state.pop("admin_users_cache_valve", None)
                                            st.rerun()
                            else:
                                st.error("Couldn't resolve selected design.")

    # ======================= TAB 2: DC001 CALCULATIONS (ALL USERS) =======================
    with tabs[2]:
        st.caption("Browse users, see their most recent DC001 calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc001_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc001_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc001_limit")
            btn = st.button("Apply filters / Refresh (DC001)", type="primary", key="adm_dc001_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d1_latest.name ILIKE :dname")

        # -------- Latest DC001 per user --------
        sql = f"""
            SELECT
            u.id::text AS user_id,
            u.username,
            COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
            d1_latest.id::text   AS calc_id,
            d1_latest.name       AS calc_name,
            d1_latest.created_at AS created_at,
            d1_latest.updated_at AS updated_at,
            (d1_latest.data->'base'->>'nps_in')::text         AS nps_in,
            (d1_latest.data->'base'->>'asme_class')::text     AS asme_class,
            (d1_latest.data->'computed'->>'verdict')::text    AS verdict,
            (d1_latest.data->'computed'->>'Q_MPa')::text      AS q_mpa,
            (d1_latest.data->'computed'->>'stress_MPa')::text AS stress_mpa
            FROM users u
            LEFT JOIN LATERAL (
            SELECT id, name, created_at, updated_at, data
            FROM dc001_calcs d1
            WHERE d1.user_id = u.id
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            ) d1_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d1_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc001" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc001"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc001"] = []

        users_latest = st.session_state.get("admin_users_cache_dc001", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC001 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            # Coerce numerics (won't fail if column missing)
            for col in ("nps_in", "asme_class", "q_mpa", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name",
                    "nps_in","asme_class","q_mpa","stress_mpa","verdict",
                    "created_at","updated_at"]
            st.markdown("### Users • Latest DC001 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC001 latest per user)", data=csv,
                            file_name="users_latest_dc001.csv", mime="text/csv", key="adm_dc001_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC001 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc001_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                # Full list for this user
                try:
                    with connect() as conn:
                        recs = conn.execute(text("""
                            SELECT id::text AS id, name, data, created_at, updated_at
                            FROM dc001_calcs
                            WHERE user_id = :uid
                            ORDER BY updated_at DESC, created_at DESC
                            LIMIT 1000
                        """), {"uid": uid}).mappings().all()
                    items = [dict(r) for r in recs]
                except Exception as e:
                    st.error(f"Load failed: {e}")
                    items = []

                if not items:
                    st.info("No DC001 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc001_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        # Proper DC001 prettified view (not the valve renderer)
                        _render_dc001_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC001 record (admin)", type="secondary", key=f"adm_del_dc001_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc001_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc001", None)
                                st.rerun()

    # ======================= TAB 3: DC001A CALCULATIONS (ALL USERS) =======================
    # ======================= TAB 3: DC001A CALCULATIONS (ALL USERS) =======================
    with tabs[3]:
        st.caption("Browse users, see their most recent DC001A calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc001a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc001a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc001a_limit")
            btn = st.button("Apply filters / Refresh (DC001A)", type="primary", key="adm_dc001a_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d1a_latest.name ILIKE :dname")

        # -------- Latest DC001A per user --------
        sql = f"""
            SELECT
            u.id::text AS user_id,
            u.username,
            COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
            d1a_latest.id::text   AS calc_id,
            d1a_latest.name       AS calc_name,
            d1a_latest.created_at AS created_at,
            d1a_latest.updated_at AS updated_at,
            (d1a_latest.data->'base'->>'nps_in')::text       AS nps_in,
            (d1a_latest.data->'base'->>'asme_class')::text   AS asme_class,
            (d1a_latest.data->'computed'->>'SR_N')::text     AS sr_n,
            (d1a_latest.data->'computed'->>'verdict')::text  AS verdict
            FROM users u
            LEFT JOIN LATERAL (
            SELECT id, name, created_at, updated_at, data
            FROM dc001a_calcs d1a
            WHERE d1a.user_id = u.id
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            ) d1a_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d1a_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc001a" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc001a"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc001a"] = []

        users_latest = st.session_state.get("admin_users_cache_dc001a", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC001A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            # Safe numeric casts
            for col in ("nps_in", "asme_class", "sr_n"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","sr_n","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC001A at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC001A latest per user)", data=csv,
                            file_name="users_latest_dc001a.csv", mime="text/csv", key="adm_dc001a_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC001A calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc001a_pick_user")
            if pick_user and pick_user != "-- select user --":
                label_to_uid = {f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"] for r in users_latest}
                uid = label_to_uid.get(pick_user)

                # full list for this user
                try:
                    with connect() as conn:
                        recs = conn.execute(text("""
                            SELECT
                            id::text AS id,
                            name,
                            data,
                            created_at,
                            updated_at
                            FROM dc001a_calcs
                            WHERE user_id = :uid
                            ORDER BY updated_at DESC, created_at DESC
                            LIMIT 1000
                        """), {"uid": uid}).mappings().all()
                    items = [dict(r) for r in recs]
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC001A records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc001a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None) or {}

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )

                        # Pretty view (fallback to simple table if helper is missing)
                        try:
                            _render_dc001a_pretty(rec.get("data") or {})
                        except NameError:
                            st.warning("Pretty renderer for DC001A not found; showing raw key-values.")
                            dat = rec.get("data") or {}
                            left, right = st.columns(2)
                            with left:
                                st.markdown("#### Base")
                                _kv_table([(k, (dat.get("base") or {}).get(k)) for k in (dat.get("base") or {}).keys()])
                                st.markdown("#### Inputs")
                                _kv_table([(k, (dat.get("inputs") or {}).get(k)) for k in (dat.get("inputs") or {}).keys()])
                            with right:
                                st.markdown("#### Computed")
                                _kv_table([(k, (dat.get("computed") or {}).get(k)) for k in (dat.get("computed") or {}).keys()])

                        st.markdown("")
                        if st.button("🗑️ Delete this DC001A record (admin)", type="secondary", key=f"adm_del_dc001a_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc001a_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc001a", None)
                                st.rerun()

    # ======================= TAB 4: DC002 CALCULATIONS (ALL USERS) =======================
    with tabs[4]:
        st.caption("Browse users, see their most recent DC002 calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc002_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc002_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc002_limit")
            btn = st.button("Apply filters / Refresh (DC002)", type="primary", key="adm_dc002_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d2_latest.name ILIKE :dname")

        # -------- Latest DC002 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d2_latest.id::text   AS calc_id,
              d2_latest.name       AS calc_name,
              d2_latest.created_at AS created_at,
              d2_latest.updated_at AS updated_at,
              (d2_latest.data->'base'->>'nps_in')::text         AS nps_in,
              (d2_latest.data->'base'->>'asme_class')::text     AS asme_class,
              (d2_latest.data->'inputs'->>'G_mm')::text         AS g_mm,
              (d2_latest.data->'inputs'->>'Pa_MPa')::text       AS pa_mpa,
              (d2_latest.data->'computed'->>'Wm1_N')::text      AS wm1_n,
              (d2_latest.data->'computed'->>'S_MPa')::text      AS s_mpa,
              (d2_latest.data->'inputs'->>'n')::text            AS n_bolts,
              (d2_latest.data->'inputs'->>'bolt_size')::text    AS bolt_size,
              (d2_latest.data->'computed'->>'Sa_eff_MPa')::text AS sa_eff_mpa,
              (d2_latest.data->'computed'->>'verdict')::text    AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc002_calcs d2
              WHERE d2.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d2_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d2_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc002" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc002"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc002"] = []

        users_latest = st.session_state.get("admin_users_cache_dc002", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC002 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in","asme_class","g_mm","pa_mpa","wm1_n","s_mpa","n_bolts","sa_eff_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","g_mm","pa_mpa","wm1_n","s_mpa","n_bolts","bolt_size","sa_eff_mpa","verdict",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC002 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC002 latest per user)", data=csv,
                               file_name="users_latest_dc002.csv", mime="text/csv", key="adm_dc002_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC002 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc002_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT id::text AS id, name, data, created_at, updated_at
                        FROM dc002_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC002 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc002_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        # pretty view for DC002
                        _render_dc002_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC002 record (admin)", type="secondary", key=f"adm_del_dc002_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc002_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc002", None)
                                st.rerun()
# ======================= TAB 5: DC002A CALCULATIONS (ALL USERS) =======================
# ======================= TAB 5: DC002A CALCULATIONS (ALL USERS) =======================
    with tabs[5]:
        st.caption("Browse users, see their most recent DC002A calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc002a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc002a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc002a_limit")
            btn = st.button("Apply filters / Refresh (DC002A)", type="primary", key="adm_dc002a_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d2a_latest.name ILIKE :dname")

        # -------- Latest DC002A per user (includes the full saved payload fields) --------
        sql = f"""
            SELECT
            u.id::text AS user_id,
            u.username,
            COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
            d2a_latest.id::text   AS calc_id,
            d2a_latest.name       AS calc_name,
            d2a_latest.created_at AS created_at,
            d2a_latest.updated_at AS updated_at,

            -- base
            (d2a_latest.data->'base'->>'valve_design_name')::text      AS valve_design_name,
            (d2a_latest.data->'base'->>'valve_design_id')::text        AS valve_design_id,
            (d2a_latest.data->'base'->>'nps_in')::text                 AS nps_in,
            (d2a_latest.data->'base'->>'asme_class')::text             AS asme_class,
            (d2a_latest.data->'base'->>'bore_diameter_mm')::text       AS bore_mm,
            (d2a_latest.data->'base'->>'operating_pressure_mpa')::text AS po_mpa,

            -- inputs
            (d2a_latest.data->'inputs'->>'G_mm')::text          AS G_mm,
            (d2a_latest.data->'inputs'->>'Pa_test_MPa')::text   AS Pa_test_MPa,
            (d2a_latest.data->'inputs'->>'Pe_MPa')::text        AS Pe_MPa,
            (d2a_latest.data->'inputs'->>'bolt_material')::text AS bolt_material,
            (d2a_latest.data->'inputs'->>'Syb_MPa')::text       AS Syb_MPa,
            (d2a_latest.data->'inputs'->>'n')::text             AS n_bolts,
            (d2a_latest.data->'inputs'->>'bolt_size')::text     AS bolt_size,

            -- computed
            (d2a_latest.data->'computed'->>'S_MPa')::text            AS S_MPa,
            (d2a_latest.data->'computed'->>'H_N')::text              AS H_N,
            (d2a_latest.data->'computed'->>'Wm1_N')::text            AS Wm1_N,
            (d2a_latest.data->'computed'->>'Am_mm2')::text           AS Am_mm2,
            (d2a_latest.data->'computed'->>'a_req_each_mm2')::text   AS a_req_each_mm2,
            (d2a_latest.data->'computed'->>'a_mm2')::text            AS a_mm2,
            (d2a_latest.data->'computed'->>'Ab_mm2')::text           AS Ab_mm2,
            (d2a_latest.data->'computed'->>'Sa_eff_MPa')::text       AS Sa_eff_MPa,
            (d2a_latest.data->'computed'->>'verdict')::text          AS verdict

            FROM users u
            LEFT JOIN LATERAL (
            SELECT id, name, created_at, updated_at, data
            FROM dc002a_calcs d2a
            WHERE d2a.user_id = u.id
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            ) d2a_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d2a_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc002a" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc002a"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc002a"] = []

        users_latest = st.session_state.get("admin_users_cache_dc002a", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC002A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric casts (safe)
            for col in (
                "nps_in","asme_class","bore_mm","po_mpa",
                "G_mm","Pa_test_MPa","Pe_MPa","Syb_MPa","n_bolts",
                "S_MPa","H_N","Wm1_N","Am_mm2","a_req_each_mm2","a_mm2","Ab_mm2","Sa_eff_MPa"
            ):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "valve_design_name","valve_design_id","nps_in","asme_class","bore_mm","po_mpa",
                "G_mm","Pa_test_MPa","Pe_MPa","bolt_material","Syb_MPa","n_bolts","bolt_size",
                "S_MPa","H_N","Wm1_N","Am_mm2","a_req_each_mm2","a_mm2","Ab_mm2","Sa_eff_MPa","verdict",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC002A at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC002A latest per user)",
                data=csv,
                file_name="users_latest_dc002a.csv",
                mime="text/csv",
                key="adm_dc002a_export",
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC002A calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc002a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                # list all for this user
                try:
                    with connect() as conn:
                        recs = conn.execute(text("""
                            SELECT id::text AS id, name, data, created_at, updated_at
                            FROM dc002a_calcs
                            WHERE user_id = :uid
                            ORDER BY updated_at DESC, created_at DESC
                            LIMIT 1000
                        """), {"uid": uid}).mappings().all()
                    items = [dict(r) for r in recs]
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC002A records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc002a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )

                        data_obj = rec.get("data") or {}
                        # Pretty view using our helper (matches page_my_library style)
                        _render_dc002a_pretty(data_obj)

                        st.markdown("")
                        if st.button("🗑️ Delete this DC002A record (admin)", type="secondary", key=f"adm_del_dc002a_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc002a_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc002a", None)
                                st.rerun()


    # ======================= TAB 6: DC003 CALCULATIONS (ALL USERS) =======================
    with tabs[6]:
        st.caption("Browse users, see their most recent DC003 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Small inline pretty-renderer (generic base/inputs/computed) ----
        def _render_generic_calc(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                if ins:
                    _kv_table([(k.replace("_", " ").title(), v) for k, v in ins.items()])
                else:
                    _kv_table([])
            with c2:
                st.markdown("#### Computed / Checks")
                if comp:
                    _kv_table([(k.replace("_", " ").title(), v) for k, v in comp.items()])
                else:
                    _kv_table([])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc003_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc003_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc003_limit")
            btn = st.button("Apply filters / Refresh (DC003)", type="primary", key="adm_dc003_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d3_latest.name ILIKE :dname")

        # -------- Latest DC003 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d3_latest.id::text   AS calc_id,
              d3_latest.name       AS calc_name,
              d3_latest.created_at AS created_at,
              d3_latest.updated_at AS updated_at,
              (d3_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d3_latest.data->'base'->>'asme_class')::text    AS asme_class,
              (d3_latest.data->'computed'->>'sigma_MPa')::text AS sigma_mpa,
              COALESCE(
                (d3_latest.data->'computed'->>'verdict'),
                (d3_latest.data->'computed'->>'result'),
                (d3_latest.data->>'verdict'),
                (d3_latest.data->>'result')
              ) AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc003_calcs d3
              WHERE d3.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d3_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d3_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc003" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc003"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc003"] = []

        users_latest = st.session_state.get("admin_users_cache_dc003", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC003 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "sigma_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","sigma_mpa","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC003 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC003 latest per user)", data=csv,
                               file_name="users_latest_dc003.csv", mime="text/csv", key="adm_dc003_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC003 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc003_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc003_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC003 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc003_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_generic_calc(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC003 record (admin)", type="secondary", key=f"adm_del_dc003_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc003_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc003", None)
                                st.rerun()
    # ======================= TAB 7: DC004 CALCULATIONS (ALL USERS) =======================
    with tabs[7]:
        st.caption("Browse users, see their most recent DC004 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Small inline pretty-renderer (generic base/inputs/computed) ----
        def _render_generic_calc_dc004(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                if ins:
                    _kv_table([(k.replace("_", " ").title(), v) for k, v in ins.items()])
                else:
                    _kv_table([])
            with c2:
                st.markdown("#### Computed / Checks")
                if comp:
                    _kv_table([(k.replace("_", " ").title(), v) for k, v in comp.items()])
                else:
                    _kv_table([])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc004_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc004_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc004_limit")
            btn = st.button("Apply filters / Refresh (DC004)", type="primary", key="adm_dc004_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d4_latest.name ILIKE :dname")

        # -------- Latest DC004 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d4_latest.id::text   AS calc_id,
              d4_latest.name       AS calc_name,
              d4_latest.created_at AS created_at,
              d4_latest.updated_at AS updated_at,
              (d4_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d4_latest.data->'base'->>'asme_class')::text    AS asme_class,
              COALESCE(
                (d4_latest.data->'computed'->>'Sf_MPa'),
                (d4_latest.data->'computed'->>'sigma_MPa'),
                (d4_latest.data->'computed'->>'stress_MPa')
              ) AS stress_mpa,
              COALESCE(
                (d4_latest.data->'computed'->>'verdict'),
                (d4_latest.data->'computed'->>'result'),
                (d4_latest.data->>'verdict'),
                (d4_latest.data->>'result')
              ) AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc004_calcs d4
              WHERE d4.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d4_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d4_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc004" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc004"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc004"] = []

        users_latest = st.session_state.get("admin_users_cache_dc004", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC004 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","stress_mpa","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC004 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC004 latest per user)", data=csv,
                               file_name="users_latest_dc004.csv", mime="text/csv", key="adm_dc004_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC004 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc004_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc004_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC004 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc004_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_generic_calc_dc004(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC004 record (admin)", type="secondary", key=f"adm_del_dc004_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc004_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc004", None)
                                st.rerun()
    # ======================= TAB 8: DC005 CALCULATIONS (ALL USERS) =======================
    with tabs[8]:
        st.caption("Browse users, see their most recent DC005 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Small inline pretty-renderer (generic base/inputs/computed) ----
        def _render_generic_calc_dc005(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                if ins:
                    _kv_table([(k.replace("_", " ").title(), v) for k, v in ins.items()])
                else:
                    _kv_table([])
            with c2:
                st.markdown("#### Computed / Checks")
                if comp:
                    _kv_table([(k.replace("_", " ").title(), v) for k, v in comp.items()])
                else:
                    _kv_table([])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc005_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc005_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc005_limit")
            btn = st.button("Apply filters / Refresh (DC005)", type="primary", key="adm_dc005_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d5_latest.name ILIKE :dname")

        # -------- Latest DC005 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d5_latest.id::text   AS calc_id,
              d5_latest.name       AS calc_name,
              d5_latest.created_at AS created_at,
              d5_latest.updated_at AS updated_at,
              (d5_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d5_latest.data->'base'->>'asme_class')::text    AS asme_class,
              COALESCE(
                (d5_latest.data->'computed'->>'Sf_MPa'),
                (d5_latest.data->'computed'->>'sigma_MPa'),
                (d5_latest.data->'computed'->>'stress_MPa')
              ) AS stress_mpa,
              COALESCE(
                (d5_latest.data->'computed'->>'verdict'),
                (d5_latest.data->'computed'->>'result'),
                (d5_latest.data->>'verdict'),
                (d5_latest.data->>'result')
              ) AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc005_calcs d5
              WHERE d5.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d5_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d5_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc005" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc005"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc005"] = []

        users_latest = st.session_state.get("admin_users_cache_dc005", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC005 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","stress_mpa","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC005 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC005 latest per user)", data=csv,
                               file_name="users_latest_dc005.csv", mime="text/csv", key="adm_dc005_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC005 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc005_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc005_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC005 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc005_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_generic_calc_dc005(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC005 record (admin)", type="secondary", key=f"adm_del_dc005_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc005_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc005", None)
                                st.rerun()
    # ======================= TAB 9: DC005A CALCULATIONS (ALL USERS) =======================
    with tabs[9]:
        st.caption("Browse users, see their most recent DC005A calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Small inline pretty-renderer (generic base/inputs/computed) ----
        def _render_generic_calc_dc005a(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                _kv_table([(k.replace("_", " ").title(), v) for k, v in ins.items()]) if ins else _kv_table([])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([(k.replace("_", " ").title(), v) for k, v in comp.items()]) if comp else _kv_table([])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc005a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc005a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc005a_limit")
            btn = st.button("Apply filters / Refresh (DC005A)", type="primary", key="adm_dc005a_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d5a_latest.name ILIKE :dname")

        # -------- Latest DC005A per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d5a_latest.id::text   AS calc_id,
              d5a_latest.name       AS calc_name,
              d5a_latest.created_at AS created_at,
              d5a_latest.updated_at AS updated_at,
              (d5a_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d5a_latest.data->'base'->>'asme_class')::text    AS asme_class,
              COALESCE(
                (d5a_latest.data->'computed'->>'Sf_MPa'),
                (d5a_latest.data->'computed'->>'sigma_MPa'),
                (d5a_latest.data->'computed'->>'stress_MPa')
              ) AS stress_mpa,
              COALESCE(
                (d5a_latest.data->'computed'->>'verdict'),
                (d5a_latest.data->'computed'->>'result'),
                (d5a_latest.data->>'verdict'),
                (d5a_latest.data->>'result')
              ) AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc005a_calcs d5a
              WHERE d5a.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d5a_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d5a_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc005a" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc005a"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc005a"] = []

        users_latest = st.session_state.get("admin_users_cache_dc005a", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC005A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","stress_mpa","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC005A at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC005A latest per user)", data=csv,
                               file_name="users_latest_dc005a.csv", mime="text/csv", key="adm_dc005a_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC005A calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc005a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc005a_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC005A records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc005a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_generic_calc_dc005a(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC005A record (admin)", type="secondary", key=f"adm_del_dc005a_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc005a_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc005a", None)
                                st.rerun()
    # ======================= TAB 10: DC006 CALCULATIONS (ALL USERS) =======================
    with tabs[10]:
        st.caption("Browse users, see their most recent DC006 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer tailored for DC006 (flange stress at operating condition) ----
        def _render_dc006_pretty(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("Design pressure Pa [MPa]", ins.get("Pa_MPa") or ins.get("Pa_test_MPa")),
                    ("Flange thickness FT [mm]", ins.get("FT_mm")),
                    ("Internal Seal Gasket Dia ISGD [mm]", ins.get("ISGD_mm")),
                    ("Bolt circle diameter Bcd [mm]", ins.get("Bcd_mm")),
                    ("External Seal Gasket Dia ESGD [mm]", ins.get("ESGD_mm")),
                    ("Gasket", ins.get("gasket")),
                    ("m [-]", ins.get("m")),
                    ("y [MPa]", ins.get("y_MPa")),
                ])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("Gasket width N [mm]", comp.get("N_mm")),
                    ("Basic seating width b0 [mm]", comp.get("b0_mm")),
                    ("Effective seating width b [mm]", comp.get("b_mm")),
                    ("Gasket load reaction dia G [mm]", comp.get("G_mm")),
                    ("Hydrostatic end force H [N]", comp.get("H_N")),
                    ("Joint compression load Hp [N]", comp.get("Hp_N")),
                    ("Wm1 [N]", comp.get("Wm1_N")),
                    ("Wm2 [N]", comp.get("Wm2_N")),
                    ("Factor K [-]", comp.get("K")),
                    ("Sf₁ [MPa]", comp.get("Sf1_MPa")),
                    ("Sf₂ [MPa]", comp.get("Sf2_MPa")),
                    ("Sf [MPa]",  comp.get("Sf_MPa") or comp.get("Sf")),
                    ("Allowable [MPa]", comp.get("allow_MPa")),
                    ("Check", comp.get("verdict") or comp.get("result")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc006_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc006_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc006_limit")
            btn = st.button("Apply filters / Refresh (DC006)", type="primary", key="adm_dc006_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d6_latest.name ILIKE :dname")

        # -------- Latest DC006 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d6_latest.id::text   AS calc_id,
              d6_latest.name       AS calc_name,
              d6_latest.created_at AS created_at,
              d6_latest.updated_at AS updated_at,
              (d6_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d6_latest.data->'base'->>'asme_class')::text    AS asme_class,
              -- show key outcome columns if present in computed
              (d6_latest.data->'computed'->>'Sf_MPa')::text    AS sf_mpa,
              (d6_latest.data->'computed'->>'allow_MPa')::text AS allow_mpa,
              COALESCE(
                (d6_latest.data->'computed'->>'verdict'),
                (d6_latest.data->'computed'->>'result'),
                (d6_latest.data->>'verdict'),
                (d6_latest.data->>'result')
              ) AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc006_calcs d6
              WHERE d6.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d6_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d6_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc006" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc006"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc006"] = []

        users_latest = st.session_state.get("admin_users_cache_dc006", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC006 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "sf_mpa", "allow_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","sf_mpa","allow_mpa","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC006 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC006 latest per user)", data=csv,
                               file_name="users_latest_dc006.csv", mime="text/csv", key="adm_dc006_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC006 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc006_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc006_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC006 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc006_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc006_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC006 record (admin)", type="secondary", key=f"adm_del_dc006_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc006_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc006", None)
                                st.rerun()
    # ======================= TAB 11: DC006A CALCULATIONS (ALL USERS) =======================
    with tabs[11]:
        st.caption("Browse users, see their most recent DC006A (Test condition ×1.5) calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer tailored for DC006A (App.2 at test pressure 1.5×) ----
        def _render_dc006a_pretty(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs (Test condition)")
                _kv_table([
                    ("Pa_test [MPa]", ins.get("Pa_test_MPa")),
                    ("FT [mm]", ins.get("FT_mm")),
                    ("ISGD [mm]", ins.get("ISGD_mm")),
                    ("Bcd [mm]", ins.get("Bcd_mm")),
                    ("ESGD [mm]", ins.get("ESGD_mm")),
                    ("Gasket", ins.get("gasket")),
                    ("m [-]", ins.get("m")),
                    ("y [MPa]", ins.get("y_MPa")),
                ])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("N [mm]", comp.get("N_mm")),
                    ("b0 [mm]", comp.get("b0_mm")),
                    ("b [mm]", comp.get("b_mm")),
                    ("G [mm]", comp.get("G_mm")),
                    ("H [N]", comp.get("H_N")),
                    ("Hp [N]", comp.get("Hp_N")),
                    ("Wm1 [N]", comp.get("Wm1_N")),
                    ("Wm2 [N]", comp.get("Wm2_N")),
                    ("K [-]", comp.get("K")),
                    ("Sf₁ [MPa]", comp.get("Sf1_MPa")),
                    ("Sf₂ [MPa]", comp.get("Sf2_MPa")),
                    ("Sf [MPa]", comp.get("Sf_MPa")),
                    ("Allowable [MPa]", comp.get("allow_MPa")),
                    ("Check", comp.get("verdict") or comp.get("result")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc006a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc006a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc006a_limit")
            btn = st.button("Apply filters / Refresh (DC006A)", type="primary", key="adm_dc006a_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d6a_latest.name ILIKE :dname")

        # -------- Latest DC006A per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d6a_latest.id::text   AS calc_id,
              d6a_latest.name       AS calc_name,
              d6a_latest.created_at AS created_at,
              d6a_latest.updated_at AS updated_at,
              (d6a_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d6a_latest.data->'base'->>'asme_class')::text    AS asme_class,
              (d6a_latest.data->'inputs'->>'Pa_test_MPa')::text AS patest_mpa,
              (d6a_latest.data->'computed'->>'Sf_MPa')::text    AS sf_mpa,
              (d6a_latest.data->'computed'->>'allow_MPa')::text AS allow_mpa,
              COALESCE(
                (d6a_latest.data->'computed'->>'verdict'),
                (d6a_latest.data->>'verdict'),
                (d6a_latest.data->'computed'->>'result'),
                (d6a_latest.data->>'result')
              ) AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc006a_calcs d6a
              WHERE d6a.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d6a_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d6a_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc006a" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc006a"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc006a"] = []

        users_latest = st.session_state.get("admin_users_cache_dc006a", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC006A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "patest_mpa", "sf_mpa", "allow_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","patest_mpa","sf_mpa","allow_mpa","verdict","created_at","updated_at"]
            st.markdown("### Users • Latest DC006A at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC006A latest per user)", data=csv,
                               file_name="users_latest_dc006a.csv", mime="text/csv", key="adm_dc006a_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC006A calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc006a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc006a_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC006A records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc006a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc006a_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC006A record (admin)", type="secondary", key=f"adm_del_dc006a_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc006a_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc006a", None)
                                st.rerun()
    # ======================= TAB 12: DC007-1 (BODY) CALCULATIONS (ALL USERS) =======================
    with tabs[12]:
        st.caption("Browse users, see their most recent DC007-1 (Body wall thickness per ASME B16.34) calc at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer for DC007-1 Body ----
        def _render_dc007_body_pretty(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("NPS [in]",             ins.get("nps_in")),
                    ("ASME Class",           ins.get("asme_class")),
                    ("Pa [MPa]",             ins.get("Pa_MPa")),
                    ("T [°C]",               ins.get("T_C")),
                    ("C/A [mm]",             ins.get("CA_mm")),
                    ("Material",             ins.get("material")),
                    ("Body ID [mm]",         ins.get("body_ID_mm")),
                    ("Flow passage d [mm]",  ins.get("flow_pass_d_mm")),
                    ("End flange ID [mm]",   ins.get("end_flange_ID_mm")),
                    ("t_body [mm]",          ins.get("t_body_mm")),
                    ("t_body_top [mm]",      ins.get("t_body_top_mm")),
                ])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("tₘ [mm]",                    comp.get("t_m_mm")),
                    ("tₘ + C/A [mm]",              comp.get("t_m_plus_CA_mm")),
                    ("Check body t ≥ tₘ",          "OK" if comp.get("ok_body_vs_tm") else "NOT OK"),
                    ("Check body/t ≥ tₘ",          "OK" if comp.get("ok_top_vs_tm") else "NOT OK"),
                    ("Check body t ≥ tₘ + C/A",    "OK" if comp.get("ok_body_vs_tmCA") else "NOT OK"),
                    ("Check body/t ≥ tₘ + C/A",    "OK" if comp.get("ok_top_vs_tmCA") else "NOT OK"),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc007b_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc007b_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc007b_limit")
            btn = st.button("Apply filters / Refresh (DC007-1 Body)", type="primary", key="adm_dc007b_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d7b_latest.name ILIKE :dname")

        # -------- Latest DC007-1 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d7b_latest.id::text   AS calc_id,
              d7b_latest.name       AS calc_name,
              d7b_latest.created_at AS created_at,
              d7b_latest.updated_at AS updated_at,
              (d7b_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d7b_latest.data->'base'->>'asme_class')::text    AS asme_class,
              (d7b_latest.data->'inputs'->>'Pa_MPa')::text      AS pa_mpa,
              (d7b_latest.data->'computed'->>'t_m_mm')::text    AS tm_mm,
              (d7b_latest.data->'computed'->>'t_m_plus_CA_mm')::text AS tmca_mm,
              (d7b_latest.data->'inputs'->>'t_body_mm')::text   AS t_body_mm,
              (d7b_latest.data->'inputs'->>'t_body_top_mm')::text AS t_body_top_mm
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc007_body_calcs d7b
              WHERE d7b.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d7b_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d7b_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc007_body" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc007_body"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc007_body"] = []

        users_latest = st.session_state.get("admin_users_cache_dc007_body", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC007-1 (Body) calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "pa_mpa", "tm_mm", "tmca_mm", "t_body_mm", "t_body_top_mm"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","pa_mpa","t_body_mm","t_body_top_mm","tm_mm","tmca_mm",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC007-1 (Body) at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC007-1 latest per user)", data=csv,
                               file_name="users_latest_dc007_body.csv", mime="text/csv", key="adm_dc007b_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC007-1 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc007b_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc007_body_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC007-1 Body records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc007b_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc007_body_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC007-1 record (admin)", type="secondary", key=f"adm_del_dc007b_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc007_body_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc007_body", None)
                                st.rerun()
    # ======================= TAB 13: DC007-2 (BODY HOLES) CALCULATIONS (ALL USERS) =======================
    with tabs[13]:
        st.caption("Browse users, see their most recent DC007-2 (Body Holes per ASME B16.34 §6.1.1) calc at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer for DC007-2 Body Holes ----
        def _render_dc007_body_holes_pretty(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("tₘ [mm] (reference)", ins.get("t_m_mm")),
                    ("f' [mm]",             ins.get("f_min_mm")),
                    ("f' + g' [mm]",        ins.get("fg_min_mm")),
                    ("e° [mm]",             ins.get("e_min_mm")),
                ])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("Req. f' ≥ 0.25·tₘ [mm]",  comp.get("req_f_mm")),
                    ("Req. f'+g' ≥ tₘ [mm]",    comp.get("req_fg_mm")),
                    ("Req. e° ≥ 0.25·tₘ [mm]",  comp.get("req_e_mm")),
                    ("Check f'",                "OK" if comp.get("ok_f") else "NOT OK"),
                    ("Check f'+g'",            "OK" if comp.get("ok_fg") else "NOT OK"),
                    ("Check e°",               "OK" if comp.get("ok_e") else "NOT OK"),
                    ("Overall",                "ALL REQUIREMENTS MET" if comp.get("overall_ok") else "REQUIREMENTS NOT MET"),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc007h_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc007h_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc007h_limit")
            btn = st.button("Apply filters / Refresh (DC007-2 Holes)", type="primary", key="adm_dc007h_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d7h_latest.name ILIKE :dname")

        # -------- Latest DC007-2 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d7h_latest.id::text   AS calc_id,
              d7h_latest.name       AS calc_name,
              d7h_latest.created_at AS created_at,
              d7h_latest.updated_at AS updated_at,
              (d7h_latest.data->'base'->>'nps_in')::text          AS nps_in,
              (d7h_latest.data->'base'->>'asme_class')::text      AS asme_class,
              (d7h_latest.data->'inputs'->>'t_m_mm')::text        AS tm_mm,
              (d7h_latest.data->'inputs'->>'f_min_mm')::text      AS f_min_mm,
              (d7h_latest.data->'inputs'->>'fg_min_mm')::text     AS fg_min_mm,
              (d7h_latest.data->'inputs'->>'e_min_mm')::text      AS e_min_mm,
              (d7h_latest.data->'computed'->>'req_f_mm')::text    AS req_f_mm,
              (d7h_latest.data->'computed'->>'req_fg_mm')::text   AS req_fg_mm,
              (d7h_latest.data->'computed'->>'req_e_mm')::text    AS req_e_mm,
              (d7h_latest.data->'computed'->>'overall_ok')::text  AS overall_ok
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc007_body_holes_calcs d7h
              WHERE d7h.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d7h_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d7h_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc007_holes" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc007_holes"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc007_holes"] = []

        users_latest = st.session_state.get("admin_users_cache_dc007_holes", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC007-2 (Body Holes) calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in","asme_class","tm_mm","f_min_mm","fg_min_mm","e_min_mm","req_f_mm","req_fg_mm","req_e_mm"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            # Normalize boolean/text overall_ok to readable form
            if "overall_ok" in df.columns:
                df["overall_ok"] = df["overall_ok"].map(lambda x: "ALL REQUIREMENTS MET" if str(x).lower() in ("true","1","yes") else ("REQUIREMENTS NOT MET" if x not in (None,"") else "—"))
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","tm_mm","f_min_mm","fg_min_mm","e_min_mm",
                "req_f_mm","req_fg_mm","req_e_mm","overall_ok",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC007-2 (Body Holes) at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC007-2 latest per user)", data=csv,
                               file_name="users_latest_dc007_body_holes.csv", mime="text/csv", key="adm_dc007h_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC007-2 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc007h_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc007_body_holes_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC007-2 Body Holes records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc007h_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc007_body_holes_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC007-2 record (admin)", type="secondary", key=f"adm_del_dc007h_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc007_body_holes_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc007_holes", None)
                                st.rerun()
    # ======================= TAB 14: DC008 (BALL SIZING) CALCULATIONS (ALL USERS) =======================
    with tabs[14]:
        st.caption("Browse users, see their most recent DC008 (Ball Sizing) calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer for DC008 ----
        def _render_dc008_pretty(data: Dict[str, Any]):
            base = (data or {}).get("base") or {}
            ins  = (data or {}).get("inputs") or {}
            comp = (data or {}).get("computed") or {}

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", base.get("valve_design_name")),
                ("Valve design ID",   base.get("valve_design_id")),
                ("NPS [in]",          base.get("nps_in")),
                ("ASME Class",        base.get("asme_class")),
                ("Bore (base) [mm]",  base.get("bore_diameter_mm")),
                ("Po (base) [MPa]",   base.get("operating_pressure_mpa")),
            ])

            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("Design pressure Pr [MPa]",     ins.get("Pr_MPa")),
                    ("Ball diameter D_ball [mm]",    ins.get("D_ball_mm")),
                    ("Bore diameter B [mm]",         ins.get("B_mm")),
                    ("Contact angle α [deg]",        ins.get("alpha_deg")),
                    ("Ball material",                 ins.get("ball_material")),
                    ("Yield stress Sy [MPa]",         ins.get("Sy_MPa")),
                    ("Flat-top distance H [mm]",      ins.get("H_mm")),
                ])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("Top thickness T [mm]",          comp.get("T_mm")),
                    ("Class (yield)",                 comp.get("criteria_class_yield")),
                    ("Class (ratio)",                 comp.get("criteria_class_ratio")),
                    ("Req. Sy(min) [MPa]",            comp.get("req_Sy_min")),
                    ("Req. (D/B)min",                 comp.get("req_DB_min")),
                    ("Actual D/B",                    comp.get("actual_DB")),
                    ("Shell (circ.) stress St1a [MPa]", comp.get("St1a_MPa")),
                    ("Allowable 2/3 Sy [MPa]",        comp.get("allow_23Sy_MPa")),
                    ("Check Sy",                      "OK" if comp.get("check_sy") else "NOT OK"),
                    ("Check D/B",                     "OK" if comp.get("check_db") else "NOT OK"),
                    ("Verdict",                       comp.get("verdict")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc008_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc008_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc008_limit")
            btn = st.button("Apply filters / Refresh (DC008)", type="primary", key="adm_dc008_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d8_latest.name ILIKE :dname")

        # -------- Latest DC008 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d8_latest.id::text   AS calc_id,
              d8_latest.name       AS calc_name,
              d8_latest.created_at AS created_at,
              d8_latest.updated_at AS updated_at,
              (d8_latest.data->'base'->>'nps_in')::text          AS nps_in,
              (d8_latest.data->'base'->>'asme_class')::text      AS asme_class,
              (d8_latest.data->'inputs'->>'Pr_MPa')::text        AS pr_mpa,
              (d8_latest.data->'inputs'->>'D_ball_mm')::text     AS d_ball_mm,
              (d8_latest.data->'inputs'->>'B_mm')::text          AS b_mm,
              (d8_latest.data->'inputs'->>'alpha_deg')::text     AS alpha_deg,
              (d8_latest.data->'inputs'->>'Sy_MPa')::text        AS sy_mpa,
              (d8_latest.data->'computed'->>'T_mm')::text        AS t_mm,
              (d8_latest.data->'computed'->>'actual_DB')::text   AS actual_db,
              (d8_latest.data->'computed'->>'St1a_MPa')::text    AS st1a_mpa,
              (d8_latest.data->'computed'->>'allow_23Sy_MPa')::text AS allow_23sy_mpa,
              (d8_latest.data->'computed'->>'verdict')::text     AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc008_calcs d8
              WHERE d8.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d8_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d8_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc008" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc008"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc008"] = []

        users_latest = st.session_state.get("admin_users_cache_dc008", [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC008 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in","asme_class","pr_mpa","d_ball_mm","b_mm","alpha_deg","sy_mpa","t_mm","actual_db","st1a_mpa","allow_23sy_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","pr_mpa","d_ball_mm","b_mm","alpha_deg","sy_mpa",
                "t_mm","actual_db","st1a_mpa","allow_23sy_mpa","verdict",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC008 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC008 latest per user)", data=csv,
                               file_name="users_latest_dc008.csv", mime="text/csv", key="adm_dc008_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC008 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc008_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc008_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC008 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc008_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc008_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC008 record (admin)", type="secondary", key=f"adm_del_dc008_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc008_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc008", None)
                                st.rerun()
    # ======================= TAB 15: DC010 CALCULATIONS (ALL USERS) =======================
    # ======================= TAB 16: DC010 CALCULATIONS (ALL USERS) =======================
# ======================= TAB 16: DC010 CALCULATIONS (ALL USERS) =======================
    with tabs[15]:
        st.caption("Browse users, see their most recent DC010 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Summarizer (fields expected by your page_my_library.py pretty view) ----
        def _dc010_summarize(data: Dict[str, Any]) -> Dict[str, Any]:
            data = data or {}
            base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
            ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
            comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}
            calc = (data.get("calculated") or {}) if isinstance(data.get("calculated"), dict) else {}
            geo  = (data.get("geometry") or {}) if isinstance(data.get("geometry"), dict) else {}

            def pick(*keys, default=None):
                for k in keys:
                    for d in (data, base, ins, comp, calc, geo):
                        if isinstance(d, dict) and k in d and d[k] not in (None, "", "None"):
                            return d[k]
                return default

            return {
                # base
                "valve_design_id":   base.get("valve_design_id"),
                "valve_design_name": base.get("valve_design_name"),
                "nps_in":            base.get("nps_in"),
                "asme_class":        base.get("asme_class"),
                "bore_mm":           pick("bore_diameter_mm", "bore_mm", "B_mm"),
                "Po_MPa":            pick("operating_pressure_mpa", "Po_MPa", "Pr_MPa", "P_MPa"),

                # inputs
                "Po_MPa_in": pick("Po_MPa_in", "Po_MPa", "Pr_MPa", "P_MPa", "pressure_MPa"),
                "D_mm":      pick("D_mm", "ball_D_mm", "D_ball_mm", "D"),
                "Dc_mm":     pick("Dc_mm", "cavity_Dc_mm", "Dc"),
                "b1_mm":     pick("b1_mm", "b1"),
                "Dm_mm":     pick("Dm_mm", "Dm"),
                "Db_mm":     pick("Db_mm", "Db"),
                "Pr_N":      pick("Pr_N", "Pr"),
                "Nma":       pick("Nma"),
                "f1":        pick("f1"),
                "f2":        pick("f2"),

                # computed
                "Fb_N":     pick("Fb_N", "Fb"),
                "Mtb_Nm":   pick("Mtb_Nm", "Mtb"),
                "Fm_N":     pick("Fm_N", "Fm"),
                "Mtm_Nm":   pick("Mtm_Nm", "Mtm"),
                "Fi_N":     pick("Fi_N", "Fi"),
                "Mti_Nm":   pick("Mti_Nm", "Mti"),
                "Tbb1_Nm":  pick("Tbb1_Nm", "torque_Nm", "T_Nm"),
            }

        # ---- Pretty renderer (exactly your page_my_library.py version) ----
        def _dc010_render_pretty(data: Dict[str, Any]):
            s = _dc010_summarize(data)

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", s.get("valve_design_name")),
                ("Valve design ID",   s.get("valve_design_id")),
                ("NPS [in]",          s.get("nps_in")),
                ("ASME Class",        s.get("asme_class")),
                ("Bore (base) [mm]",  s.get("bore_mm")),
                ("Po (base) [MPa]",   s.get("Po_MPa")),
            ])

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("Po [MPa]", s.get("Po_MPa_in")),
                    ("D [mm]", s.get("D_mm")),
                    ("Dc [mm]", s.get("Dc_mm")),
                    ("b1 [mm]", s.get("b1_mm")),
                    ("Dm [mm]", s.get("Dm_mm")),
                    ("Db [mm]", s.get("Db_mm")),
                    ("Pr [N]", s.get("Pr_N")),
                    ("Nma [-]", s.get("Nma")),
                    ("f1 [-]", s.get("f1")),
                    ("f2 [-]", s.get("f2")),
                ])
            with col2:
                st.markdown("#### Computed")
                _kv_table([
                    ("Fb [N]", s.get("Fb_N")),
                    ("Mtb [N·m]", s.get("Mtb_Nm")),
                    ("Fm [N]", s.get("Fm_N")),
                    ("Mtm [N·m]", s.get("Mtm_Nm")),
                    ("Fi [N]", s.get("Fi_N")),
                    ("Mti [N·m]", s.get("Mti_Nm")),
                    ("Tbb1 [N·m]", s.get("Tbb1_Nm")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc010_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc010_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc010_limit")
            btn = st.button("Apply filters / Refresh (DC010)", type="primary", key="adm_dc010_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d10_latest.name ILIKE :dname")

        # Fetch only id/name/timestamps; load JSON per row and summarize (prevents “—”)
        sql = f"""
            SELECT
            u.id::text AS user_id,
            u.username,
            COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
            d10_latest.id::text   AS calc_id,
            d10_latest.name       AS calc_name,
            d10_latest.created_at AS created_at,
            d10_latest.updated_at AS updated_at
            FROM users u
            LEFT JOIN LATERAL (
            SELECT id, name, created_at, updated_at
            FROM dc010_calcs d10
            WHERE d10.user_id = u.id
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            ) d10_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d10_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc010_ids" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc010_ids"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc010_ids"] = []

        users_latest_ids = st.session_state.get("admin_users_cache_dc010_ids", [])

        # Hydrate and summarize for table
        if not users_latest_ids:
            st.info("No DC010 calculations found for the filters.")
        else:
            records: List[Dict[str, Any]] = []
            for row in users_latest_ids:
                calc_id = row.get("calc_id")
                if calc_id:
                    try:
                        with connect() as conn:
                            rec = conn.execute(text("""
                                SELECT id::text AS id, name, data, created_at, updated_at
                                FROM dc010_calcs
                                WHERE id = :id
                            """), {"id": calc_id}).mappings().first()
                    except Exception:
                        rec = None
                    s = _dc010_summarize((rec or {}).get("data") or {})
                else:
                    s = {}

                records.append({
                    "user_id": row.get("user_id"),
                    "full_name": row.get("full_name"),
                    "username": row.get("username"),
                    "calc_id": calc_id,
                    "calc_name": row.get("calc_name"),
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "Po [MPA]": s.get("Po_MPa_in"),
                    "D [mm]": s.get("D_mm"),
                    "Dc [mm]": s.get("Dc_mm"),
                    "Tbb1 [N·m]": s.get("Tbb1_Nm"),
                    "created_at": _fmt_ts(row.get("created_at")),
                    "updated_at": _fmt_ts(row.get("updated_at")),
                })

            df = pd.DataFrame(records)
            for c in ["nps_in", "asme_class", "Po [MPA]", "D [mm]", "Dc [mm]", "Tbb1 [N·m]"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","Po [MPA]","D [mm]","Dc [mm]","Tbb1 [N·m]",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC010 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC010 latest per user)", data=csv,
                            file_name="users_latest_dc010.csv", mime="text/csv", key="adm_dc010_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC010 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest_ids]
            pick_user = st.selectbox("User", user_opts, key="adm_dc010_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest_ids}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                        id::text AS id,
                        name,
                        data,
                        created_at,
                        updated_at
                        FROM dc010_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC010 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc010_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _dc010_render_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC010 record (admin)", type="secondary", key=f"adm_del_dc010_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc010_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc010_ids", None)
                                st.rerun()


    # ======================= TAB 16: DC011 CALCULATIONS (ALL USERS) =======================
    with tabs[16]:
        st.caption("Browse users, see their most recent DC011 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer for DC011 (schema-agnostic) ----
        # ---- DC011 summarizer + pretty renderer (matches page_my_library.py style) ----
        def _dc011_summarize(data: Dict[str, Any]) -> Dict[str, Any]:
            """
            Normalize a DC011 record to the keys your page_my_library.py view expects.
            Handles base/inputs/computed plus common alias keys.
            """
            data = data or {}
            base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
            ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
            comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}
            calc = (data.get("calculated") or {}) if isinstance(data.get("calculated"), dict) else {}
            geo  = (data.get("geometry") or {}) if isinstance(data.get("geometry"), dict) else {}

            def pick(*keys, default=None):
                for k in keys:
                    for d in (data, base, ins, comp, calc, geo):
                        if isinstance(d, dict) and k in d and d[k] not in (None, "", "None"):
                            return d[k]
                return default

            return {
                # base (displayed at the top)
                "valve_design_id":   base.get("valve_design_id"),
                "valve_design_name": base.get("valve_design_name"),
                "nps_in":            base.get("nps_in"),
                "asme_class":        base.get("asme_class"),
                "bore_mm":           pick("bore_diameter_mm", "bore_mm", "B_mm"),
                "Po_MPa":            pick("operating_pressure_mpa", "Po_MPa", "Pr_MPa", "P_MPa"),

                # inputs (left column)
                "inner_bore_mm": pick("inner_bore_mm", "Di_mm", "inner_D_mm", "bore_inner_mm"),
                "seat_bore_mm":  pick("seat_bore_mm", "Dc_mm", "seat_Dc_mm", "D_seat_mm"),
                "beta":          pick("beta", "β", "Beta"),
                "theta_deg":     pick("theta_deg", "θ_deg", "theta_degree", "theta_degrees"),
                "theta_rad":     pick("theta_rad", "θ_rad"),
                "taper_len_mm":  pick("taper_len_mm", "L_taper_mm", "Lt_mm", "taper_L_mm"),
                "dn_choice_in":  pick("dn_choice_in", "DN_in", "dn_in", "DN"),
                "ft":            pick("ft", "f_t", "f_taper"),

                # computed (right column)
                "K1":       pick("K1"),
                "K2":       pick("K2"),
                "K_local":  pick("K_local", "Klocal"),
                "K_fric":   pick("K_fric", "Kfric"),
                "K_total":  pick("K_total", "Ktotal"),
                "Cv":       pick("Cv", "Cv_gpm_1psi", "Cv_gpm_at_1psi"),
            }

        def _render_dc011_pretty(data: Dict[str, Any]):
            s = _dc011_summarize(data)

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", s.get("valve_design_name")),
                ("Valve design ID",   s.get("valve_design_id")),
                ("NPS [in]",          s.get("nps_in")),
                ("ASME Class",        s.get("asme_class")),
                ("Bore (base) [mm]",  s.get("bore_mm")),
                ("Po (base) [MPa]",   s.get("Po_MPa")),
            ])

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("Inner bore [mm]", s.get("inner_bore_mm")),
                    ("Seat bore [mm]",  s.get("seat_bore_mm")),
                    ("β [-]",           s.get("beta")),
                    ("θ [deg]",         s.get("theta_deg")),
                    ("θ [rad]",         s.get("theta_rad")),
                    ("Taper L [mm]",    s.get("taper_len_mm")),
                    ("DN [in]",         s.get("dn_choice_in")),
                    ("fₜ [-]",          s.get("ft")),
                ])
            with col2:
                st.markdown("#### Computed")
                _kv_table([
                    ("K1 [-]",        s.get("K1")),
                    ("K2 [-]",        s.get("K2")),
                    ("K_local [-]",   s.get("K_local")),
                    ("K_fric [-]",    s.get("K_fric")),
                    ("K_total [-]",   s.get("K_total")),
                    ("Cv (gpm @ 1 psi)", s.get("Cv")),
                ])


        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc011_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc011_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc011_limit")
            btn = st.button("Apply filters / Refresh (DC011)", type="primary", key="adm_dc011_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d11_latest.name ILIKE :dname")

        # -------- Latest DC011 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d11_latest.id::text   AS calc_id,
              d11_latest.name       AS calc_name,
              d11_latest.created_at AS created_at,
              d11_latest.updated_at AS updated_at,
              (d11_latest.data->'base'->>'nps_in')::text         AS nps_in,
              (d11_latest.data->'base'->>'asme_class')::text     AS asme_class,
              (d11_latest.data->'computed'->>'stress_MPa')::text AS stress_mpa,
              (d11_latest.data->'computed'->>'tau_MPa')::text    AS tau_mpa,
              (d11_latest.data->'computed'->>'verdict')::text    AS verdict,
              (d11_latest.data->'computed'->>'result')::text     AS result
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc011_calcs d11
              WHERE d11.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d11_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d11_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc011" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc011"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc011"] = []

        users_latest = st.session_state.get("admin_users_cache_dc011", [])

        # -------- Table: latest per user --------
        if not users_latest:
            st.info("No DC011 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in","asme_class","stress_mpa","tau_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","tau_mpa","verdict","result",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC011 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC011 latest per user)", data=csv,
                               file_name="users_latest_dc011.csv", mime="text/csv", key="adm_dc011_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC011 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc011_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc011_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC011 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc011_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc011_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC011 record (admin)", type="secondary", key=f"adm_del_dc011_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc011_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc011", None)
                                st.rerun()
    # ======================= TAB 17: DC012 CALCULATIONS (ALL USERS) =======================
    with tabs[17]:
        st.caption("Browse users, see their most recent DC012 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- Pretty renderer for DC012 (schema-agnostic) ----
        def _dc012_summarize(data: dict) -> dict:
            """
            Normalize a DC012 record. Handles aliasing so Admin/My Library both render well.
            Expected data shape: { base, inputs, computed } but we tolerate variants.
            """
            data = data or {}
            base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
            ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
            comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}
            calc = (data.get("calculated") or {}) if isinstance(data.get("calculated"), dict) else {}

            def pick(*keys, default=None):
                for k in keys:
                    for d in (data, base, ins, comp, calc):
                        if isinstance(d, dict) and k in d and d[k] not in (None, "", "None"):
                            return d[k]
                return default

            return {
                # base (top banner)
                "valve_design_id":   base.get("valve_design_id"),
                "valve_design_name": base.get("valve_design_name"),
                "nps_in":            base.get("nps_in"),
                "asme_class":        base.get("asme_class"),
                "bore_mm":           pick("bore_diameter_mm", "bore_mm"),
                "Po_MPa":            pick("operating_pressure_mpa", "Po_MPa", "Pr_MPa", "P_MPa"),

                # inputs (left column)
                "P_kg":        pick("P_kg", "valve_weight_kg"),
                "thread":      pick("thread", "thread_spec"),
                "A_mm2":       pick("A_mm2", "area_mm2"),
                "N":           pick("N", "count", "qty"),
                "angle":       pick("angle", "angle_deg", "angle_rad"),
                "F_rated_kg":  pick("F_rated_kg", "rated_load_kg"),
                "material":    pick("material", "mat"),

                # computed (right column)
                "per_bolt_kg":   pick("per_bolt_kg"),
                "Ec_ok":         pick("Ec_ok", "UNI_ISO_ok", "Ec"),
                "Es_MPa":        pick("Es_MPa", "stress_MPa", "sigma_MPa"),
                "allowable_MPa": pick("allowable_MPa", "allow_MPa", "S_MPa", "limit_MPa"),
                "stress_ok":     pick("stress_ok", "verdict_bool"),

                # extras that your Admin tab sometimes shows in the table
                "tau_MPa":       pick("tau_MPa"),
                "verdict":       pick("verdict", "result"),
            }

        def _render_dc012_pretty(data: Dict[str, Any]):
            s = _dc012_summarize(data)

            st.markdown("#### Base (from Valve Data)")
            _kv_table([
                ("Valve design name", s.get("valve_design_name")),
                ("Valve design ID",   s.get("valve_design_id")),
                ("NPS [in]",          s.get("nps_in")),
                ("ASME Class",        s.get("asme_class")),
                ("Bore (base) [mm]",  s.get("bore_mm")),
                ("Po (base) [MPa]",   s.get("Po_MPa")),
            ])

            col1, col2 = st.columns(2, gap="large")
            with col1:
                st.markdown("#### Inputs")
                _kv_table([
                    ("Valve weight P [kg]", s.get("P_kg")),
                    ("Thread",              s.get("thread")),
                    ("Area A [mm²]",        s.get("A_mm2")),
                    ("Quantity N [-]",      s.get("N")),
                    ("Angle",               s.get("angle")),
                    ("Rated load F [kg]",   s.get("F_rated_kg")),
                    ("Material",            s.get("material")),
                ])
            with col2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("Per-bolt weight [kg]",            s.get("per_bolt_kg")),
                    ("UNI-ISO Load Check (Ec)",        "OK" if s.get("Ec_ok") else ("NOT OK" if s.get("Ec_ok") is not None else "—")),
                    ("Es [MPa]",                        s.get("Es_MPa")),
                    ("Allowable [MPa]",                 s.get("allowable_MPa")),
                    ("Final Check (Es ≤ Allowable)",    "OK" if s.get("stress_ok") else ("NOT OK" if s.get("stress_ok") is not None else "—")),
                    # Optional extras (visible if present)
                    ("Shear τ [MPa]",                   s.get("tau_MPa")),
                    ("Result",                          s.get("verdict")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="adm_dc012_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="adm_dc012_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="adm_dc012_limit")
            btn = st.button("Apply filters / Refresh (DC012)", type="primary", key="adm_dc012_refresh")

        params = {
            "lim": int(limit),
            "uname": f"%{f_user.strip()}%" if f_user.strip() else None,
            "dname": f"%{f_name.strip()}%" if f_name.strip() else None,
        }
        where = ["1=1"]
        if params["uname"]:
            where.append("u.username ILIKE :uname")
        if params["dname"]:
            where.append("d12_latest.name ILIKE :dname")

        # -------- Latest DC012 per user --------
        sql = f"""
            SELECT
              u.id::text AS user_id,
              u.username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d12_latest.id::text   AS calc_id,
              d12_latest.name       AS calc_name,
              d12_latest.created_at AS created_at,
              d12_latest.updated_at AS updated_at,
              (d12_latest.data->'base'->>'nps_in')::text          AS nps_in,
              (d12_latest.data->'base'->>'asme_class')::text      AS asme_class,
              (d12_latest.data->'computed'->>'stress_MPa')::text  AS stress_mpa,
              (d12_latest.data->'computed'->>'tau_MPa')::text     AS tau_mpa,
              (d12_latest.data->'computed'->>'verdict')::text     AS verdict,
              (d12_latest.data->'computed'->>'result')::text      AS result
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc012_calcs d12
              WHERE d12.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) d12_latest ON TRUE
            WHERE {" AND ".join(where)}
            ORDER BY COALESCE(d12_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn or "admin_users_cache_dc012" not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                    st.session_state["admin_users_cache_dc012"] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Query failed: {e}")
                st.session_state["admin_users_cache_dc012"] = []

        users_latest = st.session_state.get("admin_users_cache_dc012", [])

        # -------- Table: latest per user --------
        if not users_latest:
            st.info("No DC012 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in","asme_class","stress_mpa","tau_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df["created_at"] = df["created_at"].map(_fmt_ts)
            df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","tau_mpa","verdict","result",
                "created_at","updated_at"
            ]
            st.markdown("### Users • Latest DC012 at a glance")
            st.dataframe(df.reindex(columns=cols), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC012 latest per user)", data=csv,
                               file_name="users_latest_dc012.csv", mime="text/csv", key="adm_dc012_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC012 calculations")

            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_user = st.selectbox("User", user_opts, key="adm_dc012_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}[pick_user]

                with connect() as conn:
                    recs = conn.execute(text("""
                        SELECT
                          id::text AS id,
                          name,
                          data,
                          created_at,
                          updated_at
                        FROM dc012_calcs
                        WHERE user_id = :uid
                        ORDER BY updated_at DESC, created_at DESC
                        LIMIT 1000
                    """), {"uid": uid}).mappings().all()
                items = [dict(r) for r in recs]

                if not items:
                    st.info("No DC012 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"adm_dc012_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in items}[sel]
                        rec = next((r for r in items if r["id"] == pick_id), None)

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc012_pretty(rec.get("data") or {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC012 record (admin)", type="secondary", key=f"adm_del_dc012_{pick_id}"):
                            try:
                                with connect() as conn:
                                    conn.execute(text("DELETE FROM dc012_calcs WHERE id = :id"), {"id": pick_id})
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop("admin_users_cache_dc012", None)
                                st.rerun()
