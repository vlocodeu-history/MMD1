# page_admin_library.py
from __future__ import annotations
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
from sqlalchemy import text

from auth import require_role
from db import connect
from valve_repo import list_valve_designs, get_valve_design_with_user

# ---------------- small display helpers ----------------
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
    """Display timestamps consistently as 'YYYY-MM-DD HH:MM:SS' when possible."""
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

# ---------------- Valve: pretty render ----------------
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

# ---------------- DC001: summarize + pretty render (new + legacy) ----------------
def _dc001_summarize(data: dict) -> dict:
    base     = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    inputs   = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    computed = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}
    calc     = (data.get("calculated") or {}) if isinstance(data.get("calculated"), dict) else {}
    geom     = (data.get("geometry") or {}) if isinstance(data.get("geometry"), dict) else {}

    def pick(*candidates, default=None):
        for c in candidates:
            if c in data:     return data[c]
            if c in base:     return base[c]
            if c in inputs:   return inputs[c]
            if c in computed: return computed[c]
            if c in calc:     return calc[c]
            if c in geom:     return geom[c]
        return default

    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "P_base_MPa":        base.get("operating_pressure_mpa"),

        # spring load & count
        "Dm":  pick("Dm_mm", "Dm"),
        "c1":  pick("c1_N_per_mm", "c1"),
        "z":   pick("z"),
        "Fmt": pick("Fmt_N", "Fmt"),
        "P":   pick("P_N", "P"),
        "f":   pick("f_mm", "f"),
        "Nm":  pick("Nm"),
        "Nmr": pick("Nmr"),
        "Pr":  pick("Pr_N", "Pr"),
        "Nma": pick("Nma"),

        # spring check
        "Fmr":     pick("Fmr_N", "Fmr"),
        "C1eff":   pick("C1_effective_N_per_mm", "C1effective"),
        "Check":   pick("spring_check"),

        # material
        "Material": pick("material", "Material"),
        "Y_max":    pick("Y_max_MPa", "Y_max"),

        # geometry & validation
        "De":   pick("De_mm", "De"),
        "Di":   pick("Di_mm", "Di"),
        "Dcs":  pick("Dcs_mm", "Dcs"),
        "Dc":   pick("Dc_mm", "Dc"),
        "Pa":   pick("Pa_MPa", "Pa"),
        "F":    pick("F_N", "F"),
        "Q":    pick("Q_MPa", "Q"),
        "Result": pick("result"),
    }

def _render_dc001_pretty(data: Dict[str, Any]):
    s = _dc001_summarize(data)

    # Base (Valve) table
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
        st.markdown("#### Spring Load & Count")
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
            ("Check", s.get("Check")),
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
            ("Q [MPa]", s.get("Q")),
            ("Result", s.get("Result")),
        ])

# ---------------- DC001A: summarize + pretty render ----------------
def _dc001a_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    return {
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),
        "source_dc001_id":   base.get("source_dc001_id"),
        "source_dc001_name": base.get("source_dc001_name"),

        "Dc_mm":             ins.get("Dc_mm_from_dc001_Dm"),
        "Dts_mm":            ins.get("Dts_mm_from_dc001_Dc"),

        "SR_N":              comp.get("SR_N"),
        "F_molle_N":         comp.get("F_molle_N"),
        "verdict":           comp.get("verdict"),
    }

def _render_dc001a_pretty(data: Dict[str, Any]):
    s = _dc001a_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    st.markdown("#### Sourced from DC001")
    _kv_table([
        ("Source DC001 name", s.get("source_dc001_name")),
        ("Source DC001 ID",   s.get("source_dc001_id")),
        ("Dc [mm] (Dm from DC001)", s.get("Dc_mm")),
        ("Dts [mm] (Dc from DC001)", s.get("Dts_mm")),
    ])

    st.markdown("#### Result")
    _kv_table([
        ("SR [N] (F from DC001)", s.get("SR_N")),
        ("F_molle [N] (Pr from DC001)", s.get("F_molle_N")),
        ("Verdict", s.get("verdict")),
    ])

# ---------------- DC002: summarize + pretty render (NEW) ----------------
def _dc002_summarize_from_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Data shape: {"base": {...}, "inputs": {...}, "computed": {...}}
    """
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),

        # inputs
        "G_mm":              ins.get("G_mm"),
        "Pa_MPa":            ins.get("Pa_MPa"),
        "Pe_MPa":            ins.get("Pe_MPa"),
        "bolt_material":     ins.get("bolt_material"),
        "n":                 ins.get("n"),
        "bolt_size":         ins.get("bolt_size"),

        # computed
        "S_MPa":             comp.get("S_MPa"),
        "H_N":               comp.get("H_N"),
        "Wm1_N":             comp.get("Wm1_N"),
        "Am_mm2":            comp.get("Am_mm2"),
        "a_req_each_mm2":    comp.get("a_req_each_mm2"),
        "a_mm2":             comp.get("a_mm2"),
        "Ab_mm2":            comp.get("Ab_mm2"),
        "Sa_eff_MPa":        comp.get("Sa_eff_MPa"),
        "verdict":           comp.get("verdict"),
    }

def _render_dc002_pretty(data: Dict[str, Any]):
    s = _dc002_summarize_from_record(data)

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
            ("Gasket tight diameter G [mm]", s.get("G_mm")),
            ("Design pressure Pa [MPa]", s.get("Pa_MPa")),
            ("Pressure rating Pe [MPa]", s.get("Pe_MPa")),
            ("Bolt material", s.get("bolt_material")),
            ("Bolts number n", s.get("n")),
            ("Bolt size", s.get("bolt_size")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Allowable bolt stress S [MPa]", s.get("S_MPa")),
            ("Total hydrostatic end force H [N]", s.get("H_N")),
            ("Minimum required bolt load Wm1 [N]", s.get("Wm1_N")),
            ("Total required area Am [mm²]", s.get("Am_mm2")),
            ("Req. area per bolt a' [mm²]", s.get("a_req_each_mm2")),
            ("Actual area per bolt a [mm²]", s.get("a_mm2")),
            ("Total area Ab [mm²]", s.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]", s.get("Sa_eff_MPa")),
            ("Check", s.get("verdict")),
        ])

# --------------- Admin page ---------------
def render_admin_library():
    require_role(["superadmin"])
    st.subheader("Admin Library")
    tabs = st.tabs([
        "Valve Designs (All Users)",
        "DC001 Calculations (All Users)",
        "DC001A Calculations (All Users)",
        "DC002 Calculations (All Users)",
    ])

    # ======================= TAB 1: VALVE DESIGNS =======================
    with tabs[0]:
        st.caption("Browse users, see their most recent valve design at a glance, then drill into full summaries or any saved design.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                f_user = st.text_input("Username contains", value="", key="admin_valve_user_filter")
            with c2:
                f_name = st.text_input("Latest design name contains", value="", key="admin_valve_designname_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_valve_limit")
            btn_refresh = st.button("Apply filters / Refresh (Valve)", type="primary", key="admin_valve_refresh")

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
            with connect() as conn:
                rows = conn.execute(text(sql), {k: v for k, v in params.items() if v is not None}).mappings().all()
                st.session_state["admin_users_cache_valve"] = [dict(r) for r in rows]
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
            st.download_button("⬇️ Export CSV (Valve latest per user)", data=csv, file_name="users_latest_valve_designs.csv", mime="text/csv")

            st.markdown("---")
            st.markdown("### Inspect a specific user's valve designs")
            user_opts = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest]
            pick_label = st.selectbox("User", user_opts, key="admin_valve_pick_user")
            if pick_label and pick_label != "-- select user --":
                label_to_id = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest}
                sel_user_id = label_to_id.get(pick_label)
                sel_user = next((r for r in users_latest if r["user_id"] == sel_user_id), None)
                if sel_user:
                    st.markdown(f"**User:** {sel_user.get('full_name') or sel_user['username']}  \n**Username / Email:** {sel_user['username']}")
                    latest_design_id = sel_user.get("design_id")
                    if latest_design_id:
                        st.markdown("#### Latest Design (prettified)")
                        rec = get_valve_design_with_user(latest_design_id)
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
                    designs = list_valve_designs(sel_user_id, limit=500)  # [(id, name), ...]
                    if not designs:
                        st.info("No designs found for this user.")
                    else:
                        d_opts = ["-- select design --"] + [f"{nm} ({did[:8]}…)" for (did, nm) in designs]
                        d_pick = st.selectbox("Design", d_opts, key=f"admin_pick_design_{sel_user_id}")
                        if d_pick and d_pick != "-- select design --":
                            lbl_to_id = {f"{nm} ({did[:8]}…)": did for (did, nm) in designs}
                            design_id = lbl_to_id.get(d_pick)
                            if design_id:
                                rec = get_valve_design_with_user(design_id)
                                if rec and rec.get("data"):
                                    st.markdown(
                                        f"**Owner:** {rec.get('username','—')} • "
                                        f"**Name:** {rec.get('name','—')} • "
                                        f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                        f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                                    )
                                    _render_valve_pretty(rec["data"])

                                    st.markdown("")
                                    if st.button("🗑️ Delete this design (admin)", type="secondary", key=f"admin_del_valve_{design_id}"):
                                        with connect() as conn:
                                            conn.execute(text("DELETE FROM valve_designs WHERE id = :id"), {"id": design_id})
                                        st.success("Deleted.")
                                        st.session_state.pop("admin_users_cache_valve", None)
                                        st.rerun()
                            else:
                                st.error("Couldn't resolve selected design.")

    # ======================= TAB 2: DC001 CALCULATIONS =======================
    with tabs[1]:
        st.caption("Browse users, see their most recent DC001 calculation at a glance, then drill into full summaries or any calculation.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                f_user_d = st.text_input("Username contains", value="", key="admin_dc001_user_filter")
            with c2:
                f_name_d = st.text_input("Latest calc name contains", value="", key="admin_dc001_name_filter")
            with c3:
                limit_d = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc001_limit")
            btn_refresh_d = st.button("Apply filters / Refresh (DC001)", type="primary", key="admin_dc001_refresh")

        params_d = {
            "lim": int(limit_d),
            "uname": f"%{f_user_d.strip()}%" if f_user_d.strip() else None,
            "dname": f"%{f_name_d.strip()}%" if f_name_d.strip() else None,
        }
        where_d = ["1=1"]
        if params_d["uname"]:
            where_d.append("u.username ILIKE :uname")
        if params_d["dname"]:
            where_d.append("dc_latest.name ILIKE :dname")

        sql_dc_latest = f"""
            SELECT
              u.id::text AS user_id,
              u.username AS username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              dc_latest.id::text   AS calc_id,
              dc_latest.name       AS calc_name,
              dc_latest.created_at AS created_at,
              dc_latest.updated_at AS updated_at,
              (dc_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (dc_latest.data->'base'->>'asme_class')::text    AS asme_class,
              (dc_latest.data->'computed'->>'Q_MPa')::text     AS q_mpa,
              (dc_latest.data->'computed'->>'result')::text    AS result
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc001_calcs dc
              WHERE dc.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) dc_latest ON TRUE
            WHERE {" AND ".join(where_d)}
            ORDER BY COALESCE(dc_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn_refresh_d or "admin_users_cache_dc001" not in st.session_state:
            with connect() as conn:
                rows = conn.execute(text(sql_dc_latest), {k: v for k, v in params_d.items() if v is not None}).mappings().all()
                st.session_state["admin_users_cache_dc001"] = [dict(r) for r in rows]
        users_latest_dc: List[Dict[str, Any]] = st.session_state.get("admin_users_cache_dc001", [])

        if not users_latest_dc:
            st.info("No users or DC001 calculations found for the filters.")
        else:
            st.markdown("### Users • Latest DC001 at a glance")
            df_udc = pd.DataFrame(users_latest_dc)
            for col in ("nps_in", "asme_class", "q_mpa"):
                if col in df_udc.columns:
                    df_udc[col] = pd.to_numeric(df_udc[col], errors="coerce")
            df_udc["created_at"] = df_udc["created_at"].map(_fmt_ts)
            df_udc["updated_at"] = df_udc["updated_at"].map(_fmt_ts)
            cols_udc = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","q_mpa","result","created_at","updated_at"]
            st.dataframe(df_udc.reindex(columns=cols_udc), use_container_width=True, hide_index=True)

            csv_udc = df_udc.reindex(columns=cols_udc).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC001 latest per user)", data=csv_udc,
                               file_name="users_latest_dc001.csv", mime="text/csv", key="admin_dc001_export_latest")

            st.markdown("---")
            st.markdown("### Inspect a specific user's DC001 calculations")

            user_opts_dc = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest_dc]
            pick_user_dc = st.selectbox("User", user_opts_dc, key="admin_dc001_pick_user")
            if pick_user_dc and pick_user_dc != "-- select user --":
                label_to_uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest_dc}
                sel_user_id = label_to_uid.get(pick_user_dc)
                sel_user = next((r for r in users_latest_dc if r["user_id"] == sel_user_id), None)
                if not sel_user:
                    st.error("Couldn't resolve selected user.")
                else:
                    st.markdown(f"**User:** {sel_user.get('full_name') or sel_user['username']}  \n**Username / Email:** {sel_user['username']}")

                    latest_calc_id = sel_user.get("calc_id")
                    if latest_calc_id:
                        st.markdown("#### Latest DC001 (prettified)")
                        with connect() as conn:
                            rec = conn.execute(
                                text("""
                                    SELECT
                                      dc.id::text AS id,
                                      dc.name,
                                      dc.data,
                                      dc.created_at,
                                      dc.updated_at,
                                      u.username,
                                      COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name
                                    FROM dc001_calcs dc
                                    JOIN users u ON u.id = dc.user_id
                                    WHERE dc.id = :id
                                """),
                                {"id": latest_calc_id}
                            ).mappings().first()
                        if rec and rec.get("data"):
                            st.write(
                                f"**Owner:** {rec.get('full_name','—')} ({rec.get('username','—')})  •  "
                                f"**Name:** {rec.get('name','—')}  •  "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))}  •  "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc001_pretty(rec["data"])
                        else:
                            st.info("No latest DC001 data available.")
                    else:
                        st.info("This user hasn't saved any DC001 calculations yet.")

                    st.markdown("---")
                    st.markdown("#### All DC001 calculations for this user")
                    with connect() as conn:
                        recs = conn.execute(
                            text("""
                                SELECT
                                  dc.id::text   AS id,
                                  dc.name       AS name,
                                  dc.created_at AS created_at,
                                  dc.updated_at AS updated_at
                                FROM dc001_calcs dc
                                WHERE dc.user_id = :uid
                                ORDER BY dc.updated_at DESC, dc.created_at DESC
                                LIMIT 1000
                            """),
                            {"uid": sel_user_id},
                        ).mappings().all()
                    user_dc_list = [dict(r) for r in recs]

                    if not user_dc_list:
                        st.info("No DC001 records for this user.")
                    else:
                        d_opts = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in user_dc_list]
                        d_pick = st.selectbox("Calculation", d_opts, key=f"admin_dc001_pick_calc_{sel_user_id}")
                        if d_pick and d_pick != "-- select calculation --":
                            lbl_to_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in user_dc_list}
                            pick_id = lbl_to_id.get(d_pick)

                            with connect() as conn:
                                rec = conn.execute(
                                    text("""
                                        SELECT
                                          dc.id::text AS id,
                                          dc.name,
                                          dc.data,
                                          dc.created_at,
                                          dc.updated_at,
                                          u.username,
                                          COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name
                                        FROM dc001_calcs dc
                                        JOIN users u ON u.id = dc.user_id
                                        WHERE dc.id = :id
                                    """),
                                    {"id": pick_id}
                                ).mappings().first()

                            if not rec:
                                st.error("Record not found.")
                            else:
                                st.write(
                                    f"**Owner:** {rec.get('full_name','—')} ({rec.get('username','—')})  •  "
                                    f"**Name:** {rec.get('name','—')}  •  "
                                    f"**Created:** {_fmt_ts(rec.get('created_at'))}  •  "
                                    f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                                )
                                data = rec.get("data") or {}
                                _render_dc001_pretty(data)

                                st.markdown("")
                                if st.button("🗑️ Delete this DC001 record (admin)", type="secondary", key=f"admin_del_dc001_{pick_id}"):
                                    with connect() as conn:
                                        conn.execute(text("DELETE FROM dc001_calcs WHERE id = :id"), {"id": pick_id})
                                    st.success("Deleted.")
                                    st.session_state.pop("admin_users_cache_dc001", None)
                                    st.rerun()

    # ======================= TAB 3: DC001A CALCULATIONS (ALL USERS) =======================
    with tabs[2]:
        st.caption("Browse users, see their most recent DC001A calculation at a glance, then drill into full summaries or any calculation.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                f_user_a = st.text_input("Username contains", value="", key="admin_dc001a_user_filter")
            with c2:
                f_name_a = st.text_input("Latest calc name contains", value="", key="admin_dc001a_name_filter")
            with c3:
                limit_a = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc001a_limit")
            btn_refresh_a = st.button("Apply filters / Refresh (DC001A)", type="primary", key="admin_dc001a_refresh")

        params_a = {
            "lim": int(limit_a),
            "uname": f"%{f_user_a.strip()}%" if f_user_a.strip() else None,
            "dname": f"%{f_name_a.strip()}%" if f_name_a.strip() else None,
        }
        where_a = ["1=1"]
        if params_a["uname"]:
            where_a.append("u.username ILIKE :uname")
        if params_a["dname"]:
            where_a.append("dca_latest.name ILIKE :dname")

        sql_dca_latest = f"""
            SELECT
              u.id::text AS user_id,
              u.username AS username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              dca_latest.id::text   AS calc_id,
              dca_latest.name       AS calc_name,
              dca_latest.created_at AS created_at,
              dca_latest.updated_at AS updated_at,
              (dca_latest.data->'base'->>'nps_in')::text     AS nps_in,
              (dca_latest.data->'base'->>'asme_class')::text AS asme_class,
              (dca_latest.data->'computed'->>'SR_N')::text   AS sr_n,
              (dca_latest.data->'computed'->>'verdict')::text AS verdict
            FROM users u
            LEFT JOIN LATERAL (
              SELECT id, name, created_at, updated_at, data
              FROM dc001a_calcs dca
              WHERE dca.user_id = u.id
              ORDER BY updated_at DESC, created_at DESC
              LIMIT 1
            ) dca_latest ON TRUE
            WHERE {" AND ".join(where_a)}
            ORDER BY COALESCE(dca_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn_refresh_a or "admin_users_cache_dc001a" not in st.session_state:
            with connect() as conn:
                rows = conn.execute(text(sql_dca_latest), {k: v for k, v in params_a.items() if v is not None}).mappings().all()
                st.session_state["admin_users_cache_dc001a"] = [dict(r) for r in rows]
        users_latest_dca: List[Dict[str, Any]] = st.session_state.get("admin_users_cache_dc001a", [])

        if not users_latest_dca:
            st.info("No users or DC001A calculations found for the filters.")
        else:
            st.markdown("### Users • Latest DC001A at a glance")
            df_u_a = pd.DataFrame(users_latest_dca)
            for col in ("nps_in", "asme_class", "sr_n"):
                if col in df_u_a.columns:
                    df_u_a[col] = pd.to_numeric(df_u_a[col], errors="coerce")
            df_u_a["created_at"] = df_u_a["created_at"].map(_fmt_ts)
            df_u_a["updated_at"] = df_u_a["updated_at"].map(_fmt_ts)
            cols_u_a = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","sr_n","verdict","created_at","updated_at"]
            st.dataframe(df_u_a.reindex(columns=cols_u_a), use_container_width=True, hide_index=True)

            csv_u_a = df_u_a.reindex(columns=cols_u_a).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC001A latest per user)", data=csv_u_a,
                               file_name="users_latest_dc001a.csv", mime="text/csv", key="admin_dc001a_export_latest")

            st.markdown("---")
            st.markdown("### Inspect a specific user's DC001A calculations")

            user_opts_dca = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest_dca]
            pick_user_dca = st.selectbox("User", user_opts_dca, key="admin_dc001a_pick_user")
            if pick_user_dca and pick_user_dca != "-- select user --":
                label_to_uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest_dca}
                sel_user_id = label_to_uid.get(pick_user_dca)
                sel_user = next((r for r in users_latest_dca if r["user_id"] == sel_user_id), None)
                if not sel_user:
                    st.error("Couldn't resolve selected user.")
                else:
                    st.markdown(f"**User:** {sel_user.get('full_name') or sel_user['username']}  \n**Username / Email:** {sel_user['username']}")

                    # latest DC001A prettified
                    latest_calc_id = sel_user.get("calc_id")
                    if latest_calc_id:
                        st.markdown("#### Latest DC001A (prettified)")
                        with connect() as conn:
                            rec = conn.execute(
                                text("""
                                    SELECT
                                      dca.id::text AS id,
                                      dca.name,
                                      dca.data,
                                      dca.created_at,
                                      dca.updated_at,
                                      u.username,
                                      COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name
                                    FROM dc001a_calcs dca
                                    JOIN users u ON u.id = dca.user_id
                                    WHERE dca.id = :id
                                """),
                                {"id": latest_calc_id}
                            ).mappings().first()
                        if rec and rec.get("data"):
                            st.write(
                                f"**Owner:** {rec.get('full_name','—')} ({rec.get('username','—')})  •  "
                                f"**Name:** {rec.get('name','—')}  •  "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))}  •  "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc001a_pretty(rec["data"])
                        else:
                            st.info("No latest DC001A data available.")
                    else:
                        st.info("This user hasn't saved any DC001A calculations yet.")

                    st.markdown("---")
                    st.markdown("#### All DC001A calculations for this user")
                    with connect() as conn:
                        recs = conn.execute(
                            text("""
                                SELECT
                                  dca.id::text   AS id,
                                  dca.name       AS name,
                                  dca.created_at AS created_at,
                                  dca.updated_at AS updated_at
                                FROM dc001a_calcs dca
                                WHERE dca.user_id = :uid
                                ORDER BY dca.updated_at DESC, dca.created_at DESC
                                LIMIT 1000
                            """),
                            {"uid": sel_user_id},
                        ).mappings().all()
                    user_dca_list = [dict(r) for r in recs]

                    if not user_dca_list:
                        st.info("No DC001A records for this user.")
                    else:
                        d_opts = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in user_dca_list]
                        d_pick = st.selectbox("Calculation", d_opts, key=f"admin_dc001a_pick_calc_{sel_user_id}")
                        if d_pick and d_pick != "-- select calculation --":
                            lbl_to_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in user_dca_list}
                            pick_id = lbl_to_id.get(d_pick)

                            with connect() as conn:
                                rec = conn.execute(
                                    text("""
                                        SELECT
                                          dca.id::text AS id,
                                          dca.name,
                                          dca.data,
                                          dca.created_at,
                                          dca.updated_at,
                                          u.username,
                                          COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name
                                        FROM dc001a_calcs dca
                                        JOIN users u ON u.id = dca.user_id
                                        WHERE dca.id = :id
                                    """),
                                    {"id": pick_id}
                                ).mappings().first()

                            if not rec:
                                st.error("Record not found.")
                            else:
                                st.write(
                                    f"**Owner:** {rec.get('full_name','—')} ({rec.get('username','—')})  •  "
                                    f"**Name:** {rec.get('name','—')}  •  "
                                    f"**Created:** {_fmt_ts(rec.get('created_at'))}  •  "
                                    f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                                )
                                data = rec.get("data") or {}
                                _render_dc001a_pretty(data)

                                st.markdown("")
                                if st.button("🗑️ Delete this DC001A record (admin)", type="secondary", key=f"admin_del_dc001a_{pick_id}"):
                                    with connect() as conn:
                                        conn.execute(text("DELETE FROM dc001a_calcs WHERE id = :id"), {"id": pick_id})
                                    st.success("Deleted.")
                                    st.session_state.pop("admin_users_cache_dc001a", None)
                                    st.rerun()

    # ======================= TAB 4: DC002 CALCULATIONS (ALL USERS) =======================
    with tabs[3]:
        st.caption("Browse users, see their most recent DC002 calculation at a glance, then drill into full summaries or any calculation.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns([1,1,1])
            with c1:
                f_user_2 = st.text_input("Username contains", value="", key="admin_dc002_user_filter")
            with c2:
                f_name_2 = st.text_input("Latest calc name contains", value="", key="admin_dc002_name_filter")
            with c3:
                limit_2 = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc002_limit")
            btn_refresh_2 = st.button("Apply filters / Refresh (DC002)", type="primary", key="admin_dc002_refresh")

        params_2 = {
            "lim": int(limit_2),
            "uname": f"%{f_user_2.strip()}%" if f_user_2.strip() else None,
            "dname": f"%{f_name_2.strip()}%" if f_name_2.strip() else None,
        }
        where_2 = ["1=1"]
        if params_2["uname"]:
            where_2.append("u.username ILIKE :uname")
        if params_2["dname"]:
            where_2.append("d2_latest.name ILIKE :dname")

        # Latest DC002 per user
        sql_d2_latest = f"""
            SELECT
              u.id::text AS user_id,
              u.username AS username,
              COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name,
              d2_latest.id::text   AS calc_id,
              d2_latest.name       AS calc_name,
              d2_latest.created_at AS created_at,
              d2_latest.updated_at AS updated_at,
              (d2_latest.data->'base'->>'nps_in')::text        AS nps_in,
              (d2_latest.data->'base'->>'asme_class')::text    AS asme_class,
              (d2_latest.data->'inputs'->>'G_mm')::text        AS g_mm,
              (d2_latest.data->'inputs'->>'Pa_MPa')::text      AS pa_mpa,
              (d2_latest.data->'computed'->>'Wm1_N')::text     AS wm1_n,
              (d2_latest.data->'computed'->>'S_MPa')::text     AS s_mpa,
              (d2_latest.data->'inputs'->>'n')::text           AS n_bolts,
              (d2_latest.data->'inputs'->>'bolt_size')::text   AS bolt_size,
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
            WHERE {" AND ".join(where_2)}
            ORDER BY COALESCE(d2_latest.updated_at, u.created_at) DESC
            LIMIT :lim
        """

        if btn_refresh_2 or "admin_users_cache_dc002" not in st.session_state:
            with connect() as conn:
                rows = conn.execute(text(sql_d2_latest), {k: v for k, v in params_2.items() if v is not None}).mappings().all()
                st.session_state["admin_users_cache_dc002"] = [dict(r) for r in rows]
        users_latest_d2: List[Dict[str, Any]] = st.session_state.get("admin_users_cache_dc002", [])

        if not users_latest_d2:
            st.info("No users or DC002 calculations found for the filters.")
        else:
            st.markdown("### Users • Latest DC002 at a glance")
            df_u2 = pd.DataFrame(users_latest_d2)
            for col in ("nps_in", "asme_class", "g_mm", "pa_mpa", "wm1_n", "s_mpa", "n_bolts", "sa_eff_mpa"):
                if col in df_u2.columns:
                    df_u2[col] = pd.to_numeric(df_u2[col], errors="coerce")
            df_u2["created_at"] = df_u2["created_at"].map(_fmt_ts)
            df_u2["updated_at"] = df_u2["updated_at"].map(_fmt_ts)
            cols_u2 = ["user_id","full_name","username","calc_id","calc_name","nps_in","asme_class","g_mm","pa_mpa","wm1_n","s_mpa","n_bolts","bolt_size","sa_eff_mpa","verdict","created_at","updated_at"]
            st.dataframe(df_u2.reindex(columns=cols_u2), use_container_width=True, hide_index=True)

            csv_u2 = df_u2.reindex(columns=cols_u2).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC002 latest per user)", data=csv_u2,
                               file_name="users_latest_dc002.csv", mime="text/csv", key="admin_dc002_export_latest")

            st.markdown("---")
            st.markdown("### Inspect a specific user's DC002 calculations")

            user_opts_d2 = ["-- select user --"] + [f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest_d2]
            pick_user_d2 = st.selectbox("User", user_opts_d2, key="admin_dc002_pick_user")
            if pick_user_d2 and pick_user_d2 != "-- select user --":
                label_to_uid = {f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"] for r in users_latest_d2}
                sel_user_id = label_to_uid.get(pick_user_d2)
                sel_user = next((r for r in users_latest_d2 if r["user_id"] == sel_user_id), None)
                if not sel_user:
                    st.error("Couldn't resolve selected user.")
                else:
                    st.markdown(f"**User:** {sel_user.get('full_name') or sel_user['username']}  \n**Username / Email:** {sel_user['username']}")

                    # Latest DC002 prettified
                    latest_calc_id = sel_user.get("calc_id")
                    if latest_calc_id:
                        st.markdown("#### Latest DC002 (prettified)")
                        with connect() as conn:
                            rec = conn.execute(
                                text("""
                                    SELECT
                                      d2.id::text AS id,
                                      d2.name,
                                      d2.data,
                                      d2.created_at,
                                      d2.updated_at,
                                      u.username,
                                      COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name
                                    FROM dc002_calcs d2
                                    JOIN users u ON u.id = d2.user_id
                                    WHERE d2.id = :id
                                """),
                                {"id": latest_calc_id}
                            ).mappings().first()
                        if rec and rec.get("data"):
                            st.write(
                                f"**Owner:** {rec.get('full_name','—')} ({rec.get('username','—')})  •  "
                                f"**Name:** {rec.get('name','—')}  •  "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))}  •  "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc002_pretty(rec["data"])
                        else:
                            st.info("No latest DC002 data available.")
                    else:
                        st.info("This user hasn't saved any DC002 calculations yet.")

                    st.markdown("---")
                    st.markdown("#### All DC002 calculations for this user")
                    with connect() as conn:
                        recs = conn.execute(
                            text("""
                                SELECT
                                  d2.id::text   AS id,
                                  d2.name       AS name,
                                  d2.created_at AS created_at,
                                  d2.updated_at AS updated_at
                                FROM dc002_calcs d2
                                WHERE d2.user_id = :uid
                                ORDER BY d2.updated_at DESC, d2.created_at DESC
                                LIMIT 1000
                            """),
                            {"uid": sel_user_id},
                        ).mappings().all()
                    user_d2_list = [dict(r) for r in recs]

                    if not user_d2_list:
                        st.info("No DC002 records for this user.")
                    else:
                        d_opts = ["-- select calculation --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in user_d2_list]
                        d_pick = st.selectbox("Calculation", d_opts, key=f"admin_dc002_pick_calc_{sel_user_id}")
                        if d_pick and d_pick != "-- select calculation --":
                            lbl_to_id = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in user_d2_list}
                            pick_id = lbl_to_id.get(d_pick)

                            with connect() as conn:
                                rec = conn.execute(
                                    text("""
                                        SELECT
                                          d2.id::text AS id,
                                          d2.name,
                                          d2.data,
                                          d2.created_at,
                                          d2.updated_at,
                                          u.username,
                                          COALESCE(NULLIF(TRIM(u.first_name || ' ' || u.last_name), ''), u.username) AS full_name
                                        FROM dc002_calcs d2
                                        JOIN users u ON u.id = d2.user_id
                                        WHERE d2.id = :id
                                    """),
                                    {"id": pick_id}
                                ).mappings().first()

                            if not rec:
                                st.error("Record not found.")
                            else:
                                st.write(
                                    f"**Owner:** {rec.get('full_name','—')} ({rec.get('username','—')})  •  "
                                    f"**Name:** {rec.get('name','—')}  •  "
                                    f"**Created:** {_fmt_ts(rec.get('created_at'))}  •  "
                                    f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                                )
                                data = rec.get("data") or {}
                                _render_dc002_pretty(data)

                                st.markdown("")
                                if st.button("🗑️ Delete this DC002 record (admin)", type="secondary", key=f"admin_del_dc002_{pick_id}"):
                                    with connect() as conn:
                                        conn.execute(text("DELETE FROM dc002_calcs WHERE id = :id"), {"id": pick_id})
                                    st.success("Deleted.")
                                    st.session_state.pop("admin_users_cache_dc002", None)
                                    st.rerun()
