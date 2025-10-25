# page_admin_library.py  — rebuilt from scratch, tab by tab
from __future__ import annotations
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from db import get_supabase
from auth import require_role
from db import connect  # <-- missing import; required for raw SQL blocks


# If later tabs need these, re-add when you paste them in:
# from valve_repo import list_valve_designs, get_valve_design_with_user


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
    data = data or {}
    base     = data.get("base") or {}
    inputs   = data.get("inputs") or {}
    computed = data.get("computed") or {}
    calc     = data.get("calculated") or {}
    geom     = data.get("geometry") or {}

    def pick(*names, default=None):
        for n in names:
            if n in data and data[n] not in (None, ""):         return data[n]
            if n in base and base[n] not in (None, ""):         return base[n]
            if n in inputs and inputs[n] not in (None, ""):     return inputs[n]
            if n in computed and computed[n] not in (None, ""): return computed[n]
            if n in calc and calc[n] not in (None, ""):         return calc[n]
            if n in geom and geom[n] not in (None, ""):         return geom[n]
        return default

    return {
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "P_base_MPa":        base.get("operating_pressure_mpa"),
        "Q_MPa":       pick("Q_MPa", "Q"),
        "stress_MPa":  pick("stress_MPa", "sigma_MPa", "tau_MPa"),
        "verdict":     pick("verdict", "result"),
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
            ("Pa [MPa]",                 ins.get("Pa_MPa")),
            ("Material",                 ins.get("material")),
        ])
    with c2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("SR [N] (from DC001 F)",       comp.get("SR_N")),
            ("F_molle [N] (from DC001 Pr)", comp.get("F_molle_N")),
            ("Verdict",                     comp.get("verdict") or comp.get("result")),
        ])

def _render_dc002_pretty(data: Dict[str, Any]):
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
            ("Allowable bolt stress S [MPa]",        comp.get("S_MPa")),
            ("Total hydrostatic end force H [N]",     comp.get("H_N")),
            ("Minimum required bolt load Wm1 [N]",    comp.get("Wm1_N")),
            ("Total required area Am [mm²]",          comp.get("Am_mm2")),
            ("Req. area per bolt a' [mm²]",           comp.get("a_req_each_mm2")),
            ("Actual area per bolt a [mm²]",          comp.get("a_mm2")),
            ("Total area Ab [mm²]",                   comp.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]", comp.get("Sa_eff_MPa")),
            ("Check",                                 comp.get("verdict") or comp.get("result")),
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

# ===================== PAGE ENTRYPOINT =====================
def render_admin_library():
    require_role(["superadmin"])
    st.subheader("Admin Library")

    tabs = st.tabs([
        "Activity Logs (Users + Admin)",   # tabs[0]
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

    # ==================== Tab 0: Activity Logs ====================
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

        # ---- Supabase fetch (replaces connect()/raw SQL) ----
        def _fetch_audit_logs_supabase() -> List[Dict[str, Any]]:
            sb = get_supabase().schema("public").table("audit_logs")
            q = sb.select(
                "id,created_at,actor_user_id,actor_username,actor_role,"
                "action,entity_type,entity_id,name,details,ip_addr"
            )

            if f_user.strip():
                q = q.ilike("actor_username", f"%{f_user.strip()}%")

            if f_role != "(any)":
                q = q.eq("actor_role", f_role.lower())

            if f_entity != "(any)":
                q = q.eq("entity_type", f_entity.lower())

            if f_action != "(any)":
                q = q.eq("action", f_action.lower())

            q = q.order("created_at", desc=bool(order_desc)).limit(int(limit))

            resp = q.execute()
            return (resp.data or []) if hasattr(resp, "data") else []

        if btn or "admin_cache_audit" not in st.session_state:
            try:
                rows = _fetch_audit_logs_supabase()
                st.session_state["admin_cache_audit"] = rows
            except Exception as e:
                st.error(f"Failed to read audit logs: {e}")
                st.session_state["admin_cache_audit"] = []

        logs: List[Dict[str, Any]] = st.session_state.get("admin_cache_audit", [])

        if not logs:
            st.info("No audit rows for the selected filters.")
        else:
            df = pd.DataFrame(logs)
            if "created_at" in df:
                df["created_at"] = df["created_at"].map(_fmt_ts)

            cols = ["created_at","actor_username","actor_role","action","entity_type","name","entity_id","ip_addr","id"]
            if "details" in df.columns:
                cols.insert(7, "details")

            df_show = df.reindex(columns=[c for c in cols if c in df.columns])
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=420)

            # Export
            csv = df_show.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (Audit Logs)",
                data=csv,
                file_name="audit_logs.csv",
                mime="text/csv",
                key="audit_export",
            )

            st.markdown("---")
            st.markdown("### Inspect: focus on one actor")
            actor_opts = ["-- select actor --"] + sorted({
                f"{r['actor_username']} • {r.get('actor_role','')}"
                for r in logs if r.get("actor_username")
            })
            pick_actor = st.selectbox("Actor", actor_opts, key="audit_pick_actor")
            if pick_actor and pick_actor != "-- select actor --":
                actor_username = pick_actor.split(" • ", 1)[0]
                df_actor = df[df["actor_username"] == actor_username].copy()
                if "created_at" in df_actor:
                    df_actor["created_at"] = df_actor["created_at"].map(_fmt_ts)
                st.dataframe(
                    df_actor.reindex(columns=[c for c in df_show.columns if c in df_actor.columns]),
                    use_container_width=True, hide_index=True, height=360
                )
                csv_a = df_actor.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Export CSV (Actor subset)",
                    data=csv_a,
                    file_name=f"audit_{actor_username.replace('@','_')}.csv",
                    mime="text/csv",
                    key="audit_export_actor",
                )

    # ======================= TAB 0: ACTIVITY LOGS =======================
    with tabs[0]:
        st.caption("Unified audit stream of creates / updates / deletes across all entities, by users and admins.")

        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username / Email contains", key="admin_audit_user_filter")
                f_role = st.selectbox("Actor Role", ["(any)", "user", "superadmin", "admin"], index=0, key="admin_audit_role_filter")
            with c2:
                f_entity = st.selectbox(
                    "Entity Type",
                    ["(any)", "valve_design", "dc001", "dc001a", "dc002", "dc002a", "dc003", "dc004", "dc005", "dc005a",
                    "dc006", "dc006a", "dc007_body", "dc007_body_holes", "dc008", "dc010", "dc011", "dc012"],
                    index=0, key="admin_audit_entity_filter"
                )
                f_action = st.selectbox("Action", ["(any)", "create", "update", "delete", "rename", "login", "export"],
                                        index=0, key="admin_audit_action_filter")
            with c3:
                limit = st.number_input("Max rows", min_value=50, max_value=20000, step=50, value=1000, key="admin_audit_limit")
                order_desc = st.checkbox("Newest first", value=True, key="admin_audit_desc")
            btn = st.button("Apply filters / Refresh (Logs)", type="primary", key="admin_audit_refresh")

        # Build SQL
        where = ["1=1"]
        params: Dict[str, Any] = {"lim": int(limit)}

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

        cache_key = "admin_audit_cache_rows"
        if btn or cache_key not in st.session_state:
            try:
                with connect() as conn:
                    rows = conn.execute(text(sql), params).mappings().all()
                    st.session_state[cache_key] = [dict(r) for r in rows]
            except Exception as e:
                st.error(f"Failed to read audit logs: {e}")
                st.session_state[cache_key] = []

        logs: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        if not logs:
            st.info("No audit rows for the selected filters.")
        else:
            df = pd.DataFrame(logs)
            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)

            cols = ["created_at","actor_username","actor_role","action","entity_type","name","entity_id","ip_addr","id"]
            if "details" in df.columns:
                cols.insert(7, "details")  # place details before ip_addr

            df_show = df.reindex(columns=[c for c in cols if c in df.columns])
            st.dataframe(df_show, use_container_width=True, hide_index=True, height=420)

            # Export all
            csv = df_show.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (Audit Logs)", data=csv,
                            file_name="audit_logs.csv", mime="text/csv",
                            key="admin_audit_export")

            st.markdown("---")
            st.markdown("### Inspect: focus on one actor")
            actor_opts = ["-- select actor --"] + sorted({
                f"{r['actor_username']} • {r.get('actor_role','')}"
                for r in logs if r.get("actor_username")
            })
            pick_actor = st.selectbox("Actor", actor_opts, key="admin_audit_pick_actor")

            if pick_actor and pick_actor != "-- select actor --":
                actor_username = pick_actor.split(" • ", 1)[0]
                df_actor = df[df["actor_username"] == actor_username].copy()
                if "created_at" in df_actor.columns:
                    df_actor["created_at"] = df_actor["created_at"].map(_fmt_ts)

                st.dataframe(
                    df_actor.reindex(columns=[c for c in df_show.columns if c in df_actor.columns]),
                    use_container_width=True, hide_index=True, height=360
                )
                csv_a = df_actor.to_csv(index=False).encode("utf-8")
                st.download_button("⬇️ Export CSV (Actor subset)", data=csv_a,
                                file_name=f"audit_{actor_username.replace('@','_')}.csv",
                                mime="text/csv", key="admin_audit_export_actor")

    # ======================= TAB 1: VALVE DESIGNS (ALL USERS) =======================
    with tabs[1]:
        st.caption("Browse users, see their most recent valve design at a glance, then drill into full summaries or any saved design.")

        # ---------------- Filters ----------------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                f_user = st.text_input("Username contains", value="", key="admin_valve_user_filter")
            with c2:
                f_name = st.text_input("Latest design name contains", value="", key="admin_valve_designname_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_valve_limit")
            btn_refresh = st.button("Apply filters / Refresh (Valve)", type="primary", key="admin_valve_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_design() -> List[Dict[str, Any]]:
            """
            Supabase approach:
            1) Pull users (filter + limit)
            2) For each user, fetch latest valve_design by updated_at, created_at
            3) Optional name filter applied on the latest design
            """
            # 1) Users list
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            # 2) Latest valve design per user
            out: List[Dict[str, Any]] = []
            vtab = sb.table("valve_designs")
            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                try:
                    dresp = (
                        vtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional latest name filter
                if f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                calc = data.get("calculated") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "design_id": str(latest["id"]) if latest else None,
                    "design_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # preview fields from JSON
                    "nps_in": data.get("nps_in"),
                    "asme_class": data.get("asme_class"),
                    "bore_mm": calc.get("bore_diameter_mm"),
                    "f2f_mm": calc.get("face_to_face_mm"),
                    "t_mm": calc.get("body_wall_thickness_mm"),
                    # fallback for sort if no design
                    "_user_created_at": u.get("created_at"),
                })

            # 3) Sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_valve_cache_rows"
        if btn_refresh or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_design()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        if not users_latest:
            st.info("No users or designs found for the filters.")
        else:
            df_u = pd.DataFrame(users_latest)

            # numeric coercions for preview columns (keep asme_class as text)
            for col in ("nps_in", "bore_mm", "f2f_mm", "t_mm"):
                if col in df_u.columns:
                    df_u[col] = pd.to_numeric(df_u[col], errors="coerce")

            st.markdown("### Users • Latest valve design at a glance")
            if "created_at" in df_u.columns: df_u["created_at"] = df_u["created_at"].map(_fmt_ts)
            if "updated_at" in df_u.columns: df_u["updated_at"] = df_u["updated_at"].map(_fmt_ts)

            cols_out = [
                "user_id","full_name","username","design_id","design_name",
                "nps_in","asme_class","bore_mm","f2f_mm","t_mm","created_at","updated_at"
            ]
            df_show = df_u.reindex(columns=[c for c in cols_out if c in df_u.columns])
            st.dataframe(df_show, use_container_width=True, hide_index=True)

            csv = df_show.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (Valve latest per user)",
                data=csv, file_name="users_latest_valve_designs.csv",
                mime="text/csv",
                key="admin_valve_export_latest"
            )

            st.markdown("---")
            st.markdown("### Inspect a specific user's valve designs")

            # user picker
            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_label = st.selectbox("User", user_opts, key="admin_valve_pick_user")
            if pick_label and pick_label != "-- select user --":
                label_to_id = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }
                sel_user_id = label_to_id.get(pick_label)
                sel_user = next((r for r in users_latest if r["user_id"] == sel_user_id), None)

                if sel_user:
                    st.markdown(
                        f"**User:** {sel_user.get('full_name') or sel_user['username']}  \n"
                        f"**Username / Email:** {sel_user['username']}"
                    )
                    latest_design_id = sel_user.get("design_id")
                    if latest_design_id:
                        st.markdown("#### Latest Design (prettified)")
                        # Try to load directly from Supabase (avoid repo to stay consistent with Tab 2)
                        rec = None
                        err_msg = None
                        try:
                            sb_rec = (
                                sb.table("valve_designs")
                                .select("id, user_id, name, created_at, updated_at, data, users!inner(username)")
                                .eq("id", latest_design_id)
                                .limit(1)
                                .execute()
                            )
                            rows = sb_rec.data or []
                            if rows:
                                r0 = rows[0]
                                rec = {
                                    "id": r0.get("id"),
                                    "username": (r0.get("users") or {}).get("username"),
                                    "name": r0.get("name"),
                                    "created_at": r0.get("created_at"),
                                    "updated_at": r0.get("updated_at"),
                                    "data": r0.get("data"),
                                }
                        except Exception as e:
                            err_msg = str(e)

                        if rec and rec.get("data"):
                            _render_valve_pretty(rec["data"])
                            st.caption(
                                f"Name: **{rec.get('name','—')}** • "
                                f"Created: **{_fmt_ts(rec.get('created_at'))}** • "
                                f"Updated: **{_fmt_ts(rec.get('updated_at'))}**"
                            )
                        else:
                            st.info("No latest design data available.")
                            with st.expander("Why am I seeing this? (debug)"):
                                st.write({
                                    "latest_design_id": latest_design_id,
                                    "error": err_msg,
                                    "rec_has_data": bool(rec.get("data")) if isinstance(rec, dict) else None,
                                })
                    else:
                        st.info("This user hasn't saved any designs yet.")

                    st.markdown("---")
                    st.markdown("#### All Designs for this User")
                    # Full list (Supabase)
                    try:
                        recs = (
                            sb.table("valve_designs")
                            .select("id, name, data, created_at, updated_at")
                            .eq("user_id", sel_user_id)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(500)
                            .execute()
                        )
                        all_designs = recs.data or []
                    except Exception as e:
                        st.error(f"Load failed: {e}")
                        all_designs = []

                    if not all_designs:
                        st.info("No designs found for this user.")
                    else:
                        labels = [f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in all_designs]
                        d_opts = ["-- select design --"] + labels
                        d_pick = st.selectbox("Design", d_opts, key=f"admin_valve_pick_design_{sel_user_id}")
                        if d_pick and d_pick != "-- select design --":
                            # map back to id
                            label_to_id2 = {
                                f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                                for r in all_designs
                            }
                            design_id = label_to_id2.get(d_pick)
                            if design_id:
                                rec = next((r for r in all_designs if str(r.get("id")) == design_id), None)
                                if rec and rec.get("data"):
                                    st.markdown(
                                        f"**Owner:** {sel_user.get('username','—')} • "
                                        f"**Name:** {rec.get('name','—')} • "
                                        f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                        f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                                    )
                                    _render_valve_pretty(rec["data"])

                                    st.markdown("")
                                    if st.button("🗑️ Delete this design (admin)", type="secondary", key=f"admin_valve_del_{design_id}"):
                                        try:
                                            sb.table("valve_designs").delete().eq("id", design_id).execute()
                                        except Exception as e:
                                            st.error(f"Delete failed: {e}")
                                        else:
                                            st.success("Deleted.")
                                            st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc001_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc001_name_filter")
            with c3:
                limit = st.number_input(
                    "Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc001_limit"
                )
            btn = st.button("Apply filters / Refresh (DC001)", type="primary", key="admin_dc001_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc001() -> List[Dict[str, Any]]:
            """
            Supabase approach:
            1) Pull users (filtered & limited)
            2) For each user, fetch latest dc001_calc (by updated_at, created_at)
            3) Optional name filter applied on latest calc
            """
            # 1) Users list
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            # Order by user recency just for initial list (we'll sort by calc later)
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            # 2) Latest DC001 per user
            out: List[Dict[str, Any]] = []
            vtab = sb.table("dc001_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                try:
                    dresp = (
                        vtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional latest name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # preview fields from JSON (defensive)
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "verdict": comp.get("verdict"),
                    "q_mpa": comp.get("Q_MPa") if "Q_MPa" in comp else comp.get("Q") or comp.get("q_mpa"),
                    "stress_mpa": comp.get("stress_MPa") if "stress_MPa" in comp else comp.get("sigma_MPa"),
                    "_user_created_at": u.get("created_at"),
                })

            # 3) Sort by calc updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc001_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc001()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC001 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # Coerce numerics where appropriate (keep asme_class textual)
            for col in ("nps_in", "q_mpa", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","q_mpa","stress_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC001 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC001 latest per user)",
                data=csv,
                file_name="users_latest_dc001.csv",
                mime="text/csv",
                key="admin_dc001_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC001 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']} • {r['username']}"
                for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc001_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc001_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load failed: {e}")
                    items = []

                if not items:
                    st.info("No DC001 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": len(items)})
                else:
                    lbls = ["-- select calculation --"] + [f"{r.get('name','Untitled')} ({str(r.get('id'))[:8]}…)" for r in items]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc001_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id = {
                            f"{r.get('name','Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }[sel]
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None) or {}

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )
                        _render_dc001_pretty((rec.get("data") or {}) if isinstance(rec.get("data"), dict) else {})

                        st.markdown("")
                        if st.button("🗑️ Delete this DC001 record (admin)", type="secondary", key=f"admin_dc001_del_{pick_id}"):
                            try:
                                sb.table("dc001_calcs").delete().eq("id", pick_id).execute()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop(cache_key, None)
                                st.rerun()


    # ======================= TAB 3: DC001A CALCULATIONS (ALL USERS) =======================
    # ======================= TAB 3: DC001A CALCULATIONS (ALL USERS) =======================
    with tabs[3]:
        st.caption("Browse users, see their most recent DC001A calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="admin_dc001a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc001a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc001a_limit")
            btn = st.button("Apply filters / Refresh (DC001A)", type="primary", key="admin_dc001a_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc001a() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, fetch their latest dc001a_calcs by updated_at, created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc001a_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC001A
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional filter on latest calc name
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "sr_n": comp.get("SR_N"),
                    "verdict": comp.get("verdict"),
                    # fallback for sort if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # Sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc001a_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc001a()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC001A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # Coerce numeric where appropriate (keep asme_class textual)
            for col in ("nps_in", "sr_n"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","sr_n","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC001A at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC001A latest per user)",
                data=csv,
                file_name="users_latest_dc001a.csv",
                mime="text/csv",
                key="admin_dc001a_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC001A calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc001a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid_lookup = {
                    f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"]
                    for r in users_latest
                }
                uid = uid_lookup.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc001a_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC001A records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc001a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None) or {}

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )

                        # Pretty view, fallback to raw tables if renderer is missing
                        try:
                            _render_dc001a_pretty(rec.get("data") or {})
                        except NameError:
                            st.warning("Pretty renderer for DC001A not found; showing raw key-values.")
                            dat = rec.get("data") or {}
                            left, right = st.columns(2)
                            with left:
                                st.markdown("#### Base")
                                base = dat.get("base") or {}
                                _kv_table([(k, base.get(k)) for k in base.keys()])
                                st.markdown("#### Inputs")
                                inputs = dat.get("inputs") or {}
                                _kv_table([(k, inputs.get(k)) for k in inputs.keys()])
                            with right:
                                st.markdown("#### Computed")
                                comp = dat.get("computed") or {}
                                _kv_table([(k, comp.get(k)) for k in comp.keys()])

                        st.markdown("")
                        if st.button("🗑️ Delete this DC001A record (admin)", type="secondary", key=f"admin_dc001a_del_{pick_id}"):
                            try:
                                sb.table("dc001a_calcs").delete().eq("id", pick_id).execute()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop(cache_key, None)
                                st.rerun()


    # ======================= TAB 4: DC002 CALCULATIONS (ALL USERS) =======================
    with tabs[4]:
        st.caption("Browse users, see their most recent DC002 calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="admin_dc002_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc002_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc002_limit")
            btn = st.button("Apply filters / Refresh (DC002)", type="primary", key="admin_dc002_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc002() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, pull latest dc002_calcs by updated_at, created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc002_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC002
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                ins  = data.get("inputs") or {}
                comp = data.get("computed") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "g_mm": ins.get("G_mm"),
                    "pa_mpa": ins.get("Pa_MPa"),
                    "n_bolts": ins.get("n"),
                    "bolt_size": ins.get("bolt_size"),
                    "wm1_n": comp.get("Wm1_N"),
                    "s_mpa": comp.get("S_MPa"),
                    "sa_eff_mpa": comp.get("Sa_eff_MPa"),
                    "verdict": comp.get("verdict"),
                    # fallback for sort if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc002_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc002()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC002 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions (keep asme_class textual)
            for col in ("nps_in", "g_mm", "pa_mpa", "wm1_n", "s_mpa", "n_bolts", "sa_eff_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","g_mm","pa_mpa","wm1_n","s_mpa","n_bolts","bolt_size","sa_eff_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC002 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC002 latest per user)",
                data=csv,
                file_name="users_latest_dc002.csv",
                mime="text/csv",
                key="admin_dc002_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC002 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc002_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid_lookup = {
                    f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"]
                    for r in users_latest
                }
                uid = uid_lookup.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc002_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC002 records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc002_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None) or {}

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )

                        # Pretty DC002 view
                        try:
                            _render_dc002_pretty(rec.get("data") or {})
                        except NameError:
                            # Minimal raw fallback
                            dat = rec.get("data") or {}
                            base = dat.get("base") or {}
                            ins  = dat.get("inputs") or {}
                            comp = dat.get("computed") or {}
                            l, r = st.columns(2)
                            with l:
                                st.markdown("#### Base")
                                _kv_table([(k, base.get(k)) for k in base.keys()])
                                st.markdown("#### Inputs")
                                _kv_table([(k, ins.get(k)) for k in ins.keys()])
                            with r:
                                st.markdown("#### Computed")
                                _kv_table([(k, comp.get(k)) for k in comp.keys()])

                        st.markdown("")
                        if st.button("🗑️ Delete this DC002 record (admin)", type="secondary", key=f"admin_dc002_del_{pick_id}"):
                            try:
                                sb.table("dc002_calcs").delete().eq("id", pick_id).execute()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop(cache_key, None)
                                st.rerun()

# ======================= TAB 5: DC002A CALCULATIONS (ALL USERS) =======================
# ======================= TAB 5: DC002A CALCULATIONS (ALL USERS) =======================
    with tabs[5]:
        st.caption("Browse users, see their most recent DC002A calculation at a glance, then drill into full summaries or any calculation.")

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="admin_dc002a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc002a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc002a_limit")
            btn = st.button("Apply filters / Refresh (DC002A)", type="primary", key="admin_dc002a_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc002a() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, pull latest dc002a_calcs by updated_at, created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc002a_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC002A
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                ins  = data.get("inputs") or {}
                comp = data.get("computed") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # base preview
                    "valve_design_name": base.get("valve_design_name"),
                    "valve_design_id": base.get("valve_design_id"),
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "bore_mm": base.get("bore_diameter_mm"),
                    "po_mpa": base.get("operating_pressure_mpa"),

                    # inputs
                    "G_mm": ins.get("G_mm"),
                    "Pa_test_MPa": ins.get("Pa_test_MPa"),
                    "Pe_MPa": ins.get("Pe_MPa"),
                    "bolt_material": ins.get("bolt_material"),
                    "Syb_MPa": ins.get("Syb_MPa"),
                    "n_bolts": ins.get("n"),
                    "bolt_size": ins.get("bolt_size"),

                    # computed
                    "S_MPa": comp.get("S_MPa"),
                    "H_N": comp.get("H_N"),
                    "Wm1_N": comp.get("Wm1_N"),
                    "Am_mm2": comp.get("Am_mm2"),
                    "a_req_each_mm2": comp.get("a_req_each_mm2"),
                    "a_mm2": comp.get("a_mm2"),
                    "Ab_mm2": comp.get("Ab_mm2"),
                    "Sa_eff_MPa": comp.get("Sa_eff_MPa"),
                    "verdict": comp.get("verdict"),

                    # fallback for sorting if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc002a_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc002a()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC002A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric casts (keep asme_class textual)
            for col in (
                "nps_in","bore_mm","po_mpa",
                "G_mm","Pa_test_MPa","Pe_MPa","Syb_MPa","n_bolts",
                "S_MPa","H_N","Wm1_N","Am_mm2","a_req_each_mm2","a_mm2","Ab_mm2","Sa_eff_MPa"
            ):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "valve_design_name","valve_design_id","nps_in","asme_class","bore_mm","po_mpa",
                "G_mm","Pa_test_MPa","Pe_MPa","bolt_material","Syb_MPa","n_bolts","bolt_size",
                "S_MPa","H_N","Wm1_N","Am_mm2","a_req_each_mm2","a_mm2","Ab_mm2","Sa_eff_MPa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC002A at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC002A latest per user)",
                data=csv,
                file_name="users_latest_dc002a.csv",
                mime="text/csv",
                key="admin_dc002a_export",
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC002A calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']} • {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc002a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']} • {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # List all DC002A for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc002a_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC002A records for this user.")
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc002a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None) or {}

                        st.write(
                            f"**Name:** {rec.get('name','—')} • "
                            f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                        )

                        data_obj = rec.get("data") or {}
                        # Pretty view using helper (falls back to raw if helper missing)
                        try:
                            _render_dc002a_pretty(data_obj)
                        except NameError:
                            base = data_obj.get("base") or {}
                            ins  = data_obj.get("inputs") or {}
                            comp = data_obj.get("computed") or {}
                            l, r = st.columns(2)
                            with l:
                                st.markdown("#### Base")
                                _kv_table([(k, base.get(k)) for k in base.keys()])
                                st.markdown("#### Inputs")
                                _kv_table([(k, ins.get(k)) for k in ins.keys()])
                            with r:
                                st.markdown("#### Computed")
                                _kv_table([(k, comp.get(k)) for k in comp.keys()])

                        st.markdown("")
                        if st.button("🗑️ Delete this DC002A record (admin)", type="secondary", key=f"admin_dc002a_del_{pick_id}"):
                            try:
                                sb.table("dc002a_calcs").delete().eq("id", pick_id).execute()
                            except Exception as e:
                                st.error(f"Delete failed: {e}")
                            else:
                                st.success("Deleted.")
                                st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc003_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc003_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc003_limit")
            btn = st.button("Apply filters / Refresh (DC003)", type="primary", key="admin_dc003_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc003() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, pull latest dc003_calcs by updated_at, created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc003_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC003
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                sigma_mpa = comp.get("sigma_MPa")
                # Verdict fallback like SQL COALESCE in your previous snippet
                verdict = (
                    comp.get("verdict")
                    or comp.get("result")
                    or data.get("verdict")
                    or data.get("result")
                )

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "sigma_mpa": sigma_mpa,
                    "verdict": verdict,

                    # fallback for sorting if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc003_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc003()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC003 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions (keep asme_class textual)
            for col in ("nps_in", "sigma_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","sigma_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC003 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC003 latest per user)",
                            data=csv, file_name="users_latest_dc003.csv",
                            mime="text/csv", key="admin_dc003_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC003 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc003_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # List all DC003 for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc003_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC003 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc003_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_generic_calc(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC003 record (admin)", type="secondary", key=f"admin_dc003_del_{pick_id}"):
                                try:
                                    sb.table("dc003_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc004_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc004_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc004_limit")
            btn = st.button("Apply filters / Refresh (DC004)", type="primary", key="admin_dc004_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc004() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, pull latest dc004_calcs by updated_at, created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc004_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC004 for this user
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                # Stress fallback (like your SQL COALESCE)
                stress_mpa = (
                    comp.get("Sf_MPa")
                    or comp.get("sigma_MPa")
                    or comp.get("stress_MPa")
                )
                verdict = (
                    comp.get("verdict")
                    or comp.get("result")
                    or data.get("verdict")
                    or data.get("result")
                )

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "stress_mpa": stress_mpa,
                    "verdict": verdict,

                    # fallback for sorting if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc004_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc004()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC004 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions (keep asme_class textual)
            for col in ("nps_in", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC004 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC004 latest per user)",
                data=csv, file_name="users_latest_dc004.csv",
                mime="text/csv", key="admin_dc004_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC004 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc004_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # List all DC004 for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc004_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC004 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc004_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_generic_calc_dc004(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC004 record (admin)", type="secondary", key=f"admin_dc004_del_{pick_id}"):
                                try:
                                    sb.table("dc004_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc005_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc005_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc005_limit")
            btn = st.button("Apply filters / Refresh (DC005)", type="primary", key="admin_dc005_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc005() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, pull latest dc005_calcs by updated_at/created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc005_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC005 for this user
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                # Stress + verdict fallbacks (like your SQL COALESCE)
                stress_mpa = (
                    comp.get("Sf_MPa")
                    or comp.get("sigma_MPa")
                    or comp.get("stress_MPa")
                )
                verdict = (
                    comp.get("verdict")
                    or comp.get("result")
                    or data.get("verdict")
                    or data.get("result")
                )

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "stress_mpa": stress_mpa,
                    "verdict": verdict,

                    # fallback for sorting if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc005_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc005()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC005 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions (keep asme_class textual)
            for col in ("nps_in", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC005 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC005 latest per user)",
                data=csv, file_name="users_latest_dc005.csv",
                mime="text/csv", key="admin_dc005_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC005 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc005_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # List all DC005 for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc005_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC005 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc005_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_generic_calc_dc005(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC005 record (admin)", type="secondary", key=f"admin_dc005_del_{pick_id}"):
                                try:
                                    sb.table("dc005_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc005a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc005a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc005a_limit")
            btn = st.button("Apply filters / Refresh (DC005A)", type="primary", key="admin_dc005a_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc005a() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter, limited)
            2) For each user, pull latest dc005a_calcs by updated_at/created_at
            3) Optional latest-name filter
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc005a_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC005A for this user
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                # Stress + verdict fallbacks (mirror your SQL COALESCE)
                stress_mpa = (
                    comp.get("Sf_MPa")
                    or comp.get("sigma_MPa")
                    or comp.get("stress_MPa")
                )
                verdict = (
                    comp.get("verdict")
                    or comp.get("result")
                    or data.get("verdict")
                    or data.get("result")
                )

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "stress_mpa": stress_mpa,
                    "verdict": verdict,

                    # fallback for sorting if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc005a_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc005a()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC005A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions (keep asme_class textual)
            for col in ("nps_in", "stress_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC005A at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC005A latest per user)",
                data=csv,
                file_name="users_latest_dc005a.csv",
                mime="text/csv",
                key="admin_dc005a_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC005A calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc005a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # List all DC005A for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc005a_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC005A records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc005a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_generic_calc_dc005a(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC005A record (admin)", type="secondary", key=f"admin_dc005a_del_{pick_id}"):
                                try:
                                    sb.table("dc005a_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc006_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc006_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc006_limit")
            btn = st.button("Apply filters / Refresh (DC006)", type="primary", key="admin_dc006_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc006() -> List[Dict[str, Any]]:
            """
            1) Fetch users (optional username filter)
            2) For each, fetch latest dc006_calcs by updated_at/created_at
            3) Optional filter by latest calc name
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc006_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # latest DC006 for this user
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional latest-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                comp = data.get("computed") or {}

                verdict = (
                    comp.get("verdict")
                    or comp.get("result")
                    or data.get("verdict")
                    or data.get("result")
                )

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "sf_mpa": (comp.get("Sf_MPa") if isinstance(comp.get("Sf_MPa"), (int, float, str)) else None),
                    "allow_mpa": comp.get("allow_MPa"),
                    "verdict": verdict,

                    "_user_created_at": u.get("created_at"),
                })

            # sort by calc updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc006_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc006()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC006 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions (keep asme_class text)
            for col in ("nps_in", "sf_mpa", "allow_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","sf_mpa","allow_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC006 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC006 latest per user)",
                data=csv,
                file_name="users_latest_dc006.csv",
                mime="text/csv",
                key="admin_dc006_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC006 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc006_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Fetch full list for this user via Supabase
                try:
                    recs = (
                        sb.table("dc006_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC006 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc006_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc006_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC006 record (admin)", type="secondary", key=f"admin_dc006_del_{pick_id}"):
                                try:
                                    sb.table("dc006_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc006a_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc006a_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc006a_limit")
            btn = st.button("Apply filters / Refresh (DC006A)", type="primary", key="admin_dc006a_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc006a() -> List[Dict[str, Any]]:
            """
            1) Fetch users (with optional username filter)
            2) For each user, fetch their latest dc006a_calcs by updated_at/created_at
            3) Optional filter by latest calc name
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc006a_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # Latest DC006A for this user
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional calc-name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                ins  = data.get("inputs") or {}
                comp = data.get("computed") or {}

                verdict = (
                    comp.get("verdict")
                    or data.get("verdict")
                    or comp.get("result")
                    or data.get("result")
                )

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # Preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "patest_mpa": ins.get("Pa_test_MPa"),
                    "sf_mpa": comp.get("Sf_MPa"),
                    "allow_mpa": comp.get("allow_MPa"),
                    "verdict": verdict,

                    "_user_created_at": u.get("created_at"),
                })

            # Sort by calc updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc006a_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc006a()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC006A calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # Numeric coercions (keep asme_class text)
            for col in ("nps_in", "patest_mpa", "sf_mpa", "allow_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","patest_mpa","sf_mpa","allow_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC006A at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC006A latest per user)",
                data=csv,
                file_name="users_latest_dc006a.csv",
                mime="text/csv",
                key="admin_dc006a_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC006A calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc006a_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc006a_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC006A records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc006a_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc006a_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC006A record (admin)", type="secondary", key=f"admin_dc006a_del_{pick_id}"):
                                try:
                                    sb.table("dc006a_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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
                f_user = st.text_input("Username contains", key="admin_dc007b_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc007b_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc007b_limit")
            btn = st.button("Apply filters / Refresh (DC007-1 Body)", type="primary", key="admin_dc007b_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc007_body() -> List[Dict[str, Any]]:
            """
            1) Fetch users (filter + limit)
            2) For each user, fetch latest dc007_body_calcs by updated_at/created_at
            3) Optional filter by latest calc name
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc007_body_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                ins  = data.get("inputs") or {}
                comp = data.get("computed") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),

                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "pa_mpa": ins.get("Pa_MPa"),
                    "t_body_mm": ins.get("t_body_mm"),
                    "t_body_top_mm": ins.get("t_body_top_mm"),
                    "tm_mm": comp.get("t_m_mm"),
                    "tmca_mm": comp.get("t_m_plus_CA_mm"),

                    "_user_created_at": u.get("created_at"),
                })

            # Sort by calc updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc007b_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc007_body()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC007-1 (Body) calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "pa_mpa", "tm_mm", "tmca_mm", "t_body_mm", "t_body_top_mm"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","pa_mpa","t_body_mm","t_body_top_mm","tm_mm","tmca_mm",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC007-1 (Body) at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC007-1 latest per user)",
                data=csv,
                file_name="users_latest_dc007_body.csv",
                mime="text/csv",
                key="admin_dc007b_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC007-1 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc007b_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc007_body_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC007-1 Body records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    lbls = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", lbls, key=f"admin_dc007b_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_id_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_id_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc007_body_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC007-1 record (admin)", type="secondary", key=f"admin_dc007b_del_{pick_id}"):
                                try:
                                    sb.table("dc007_body_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
                                    st.rerun()

    # ======================= TAB 13: DC007-2 (BODY HOLES) CALCULATIONS (ALL USERS) =======================
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
                    ("Ball material",                ins.get("ball_material")),
                    ("Yield stress Sy [MPa]",        ins.get("Sy_MPa")),
                    ("Flat-top distance H [mm]",     ins.get("H_mm")),
                ])
            with c2:
                st.markdown("#### Computed / Checks")
                _kv_table([
                    ("Top thickness T [mm]",            comp.get("T_mm")),
                    ("Class (yield)",                   comp.get("criteria_class_yield")),
                    ("Class (ratio)",                   comp.get("criteria_class_ratio")),
                    ("Req. Sy(min) [MPa]",              comp.get("req_Sy_min")),
                    ("Req. (D/B)min",                   comp.get("req_DB_min")),
                    ("Actual D/B",                      comp.get("actual_DB")),
                    ("Shell (circ.) stress St1a [MPa]", comp.get("St1a_MPa")),
                    ("Allowable 2/3 Sy [MPa]",          comp.get("allow_23Sy_MPa")),
                    ("Check Sy",                        "OK" if comp.get("check_sy") else "NOT OK"),
                    ("Check D/B",                       "OK" if comp.get("check_db") else "NOT OK"),
                    ("Verdict",                         comp.get("verdict")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="admin_dc008_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc008_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc008_limit")
            btn = st.button("Apply filters / Refresh (DC008)", type="primary", key="admin_dc008_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc008() -> List[Dict[str, Any]]:
            """
            1) Fetch users (filter + limit)
            2) For each user, fetch the latest dc008_calcs
            3) Optional filter by latest calc name
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc008_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional name filter on latest
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                data = (latest or {}).get("data") or {}
                base = data.get("base") or {}
                ins  = data.get("inputs") or {}
                comp = data.get("computed") or {}

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # preview fields
                    "nps_in": base.get("nps_in"),
                    "asme_class": base.get("asme_class"),
                    "pr_mpa": ins.get("Pr_MPa"),
                    "d_ball_mm": ins.get("D_ball_mm"),
                    "b_mm": ins.get("B_mm"),
                    "alpha_deg": ins.get("alpha_deg"),
                    "sy_mpa": ins.get("Sy_MPa"),
                    "t_mm": comp.get("T_mm"),
                    "actual_db": comp.get("actual_DB"),
                    "st1a_mpa": comp.get("St1a_MPa"),
                    "allow_23sy_mpa": comp.get("allow_23Sy_MPa"),
                    "verdict": comp.get("verdict"),
                    "_user_created_at": u.get("created_at"),
                })

            # Sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc008_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc008()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC008 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in","pr_mpa","d_ball_mm","b_mm","alpha_deg","sy_mpa","t_mm","actual_db","st1a_mpa","allow_23sy_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","pr_mpa","d_ball_mm","b_mm","alpha_deg","sy_mpa",
                "t_mm","actual_db","st1a_mpa","allow_23sy_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC008 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export CSV (DC008 latest per user)",
                data=csv,
                file_name="users_latest_dc008.csv",
                mime="text/csv",
                key="admin_dc008_export"
            )

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC008 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc008_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc008_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC008 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    labels = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", labels, key=f"admin_dc008_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc008_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC008 record (admin)", type="secondary", key=f"admin_dc008_del_{pick_id}"):
                                try:
                                    sb.table("dc008_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
                                    st.rerun()

   
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

        # ---- Pretty renderer (same layout you used elsewhere) ----
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
                f_user = st.text_input("Username contains", key="admin_dc010_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc010_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc010_limit")
            btn = st.button("Apply filters / Refresh (DC010)", type="primary", key="admin_dc010_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc010() -> List[Dict[str, Any]]:
            """
            Supabase-first:
            1) Fetch users (filter + limit)
            2) For each user, fetch the latest dc010_calcs (with data)
            3) Optional filter by latest calc name
            4) Summarize JSON for table preview
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc010_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional filter on latest calc name
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str)
                            and f_name.strip().lower() in latest["name"].lower()):
                        continue

                s = _dc010_summarize(((latest or {}).get("data")) or {})

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # summary preview fields
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "Po [MPA]": s.get("Po_MPa_in"),
                    "D [mm]": s.get("D_mm"),
                    "Dc [mm]": s.get("Dc_mm"),
                    "Tbb1 [N·m]": s.get("Tbb1_Nm"),
                    # fallback for sorting if no calc
                    "_user_created_at": u.get("created_at"),
                })

            # Sort by latest updated_at desc, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc010_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc010()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table (latest per user) --------
        if not users_latest:
            st.info("No DC010 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)

            # numeric coercions
            for c in ["nps_in", "asme_class", "Po [MPA]", "D [mm]", "Dc [mm]", "Tbb1 [N·m]"]:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors="coerce")

            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","Po [MPA]","D [mm]","Dc [mm]","Tbb1 [N·m]",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC010 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC010 latest per user)", data=csv,
                            file_name="users_latest_dc010.csv", mime="text/csv", key="admin_dc010_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC010 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc010_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc010_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC010 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    labels = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", labels, key=f"admin_dc010_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _dc010_render_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC010 record (admin)", type="secondary", key=f"admin_dc010_del_{pick_id}"):
                                try:
                                    sb.table("dc010_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
                                    st.rerun()



    # ======================= TAB 16: DC011 CALCULATIONS (ALL USERS) =======================
    with tabs[16]:
        st.caption("Browse users, see their most recent DC011 calculation at a glance, then drill into full summaries or any calculation.")

        # ---- DC011 summarizer (schema-agnostic; aligns with page_my_library style) ----
        def _dc011_summarize(data: Dict[str, Any]) -> Dict[str, Any]:
            """
            Normalize a DC011 record to stable keys for table/pretty display.
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
                # base
                "valve_design_id":   base.get("valve_design_id"),
                "valve_design_name": base.get("valve_design_name"),
                "nps_in":            base.get("nps_in"),
                "asme_class":        base.get("asme_class"),
                "bore_mm":           pick("bore_diameter_mm", "bore_mm", "B_mm"),
                "Po_MPa":            pick("operating_pressure_mpa", "Po_MPa", "Pr_MPa", "P_MPa"),

                # inputs
                "inner_bore_mm": pick("inner_bore_mm", "Di_mm", "inner_D_mm", "bore_inner_mm"),
                "seat_bore_mm":  pick("seat_bore_mm", "Dc_mm", "seat_Dc_mm", "D_seat_mm"),
                "beta":          pick("beta", "β", "Beta"),
                "theta_deg":     pick("theta_deg", "θ_deg", "theta_degree", "theta_degrees"),
                "theta_rad":     pick("theta_rad", "θ_rad"),
                "taper_len_mm":  pick("taper_len_mm", "L_taper_mm", "Lt_mm", "taper_L_mm"),
                "dn_choice_in":  pick("dn_choice_in", "DN_in", "dn_in", "DN"),
                "ft":            pick("ft", "f_t", "f_taper"),

                # computed (incl. common aliases)
                "K1":       pick("K1"),
                "K2":       pick("K2"),
                "K_local":  pick("K_local", "Klocal"),
                "K_fric":   pick("K_fric", "Kfric"),
                "K_total":  pick("K_total", "Ktotal"),
                "Cv":       pick("Cv", "Cv_gpm_1psi", "Cv_gpm_at_1psi"),
                "stress_mpa": pick("stress_MPa", "sigma_MPa"),
                "tau_mpa":    pick("tau_MPa", "tau"),
                "verdict":    pick("verdict", "result"),
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
                    ("σ [MPa]",       s.get("stress_mpa")),
                    ("τ [MPa]",       s.get("tau_mpa")),
                    ("Verdict",       s.get("verdict")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="admin_dc011_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc011_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc011_limit")
            btn = st.button("Apply filters / Refresh (DC011)", type="primary", key="admin_dc011_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc011() -> List[Dict[str, Any]]:
            """
            1) Fetch users (filter + limit)
            2) For each user, fetch latest dc011_calcs (with data)
            3) Optional filter by latest name
            4) Summarize JSON for table preview
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc011_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # Latest calc
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # Optional name filter
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str) and f_name.strip().lower() in latest["name"].lower()):
                        continue

                s = _dc011_summarize(((latest or {}).get("data")) or {})

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # summary preview fields
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "stress_mpa": s.get("stress_mpa"),
                    "tau_mpa": s.get("tau_mpa"),
                    "K_total": s.get("K_total"),
                    "Cv": s.get("Cv"),
                    "_user_created_at": u.get("created_at"),  # fallback sort
                })

            # Sort by latest updated_at desc, fallback to user created
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc011_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc011()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table: latest per user --------
        if not users_latest:
            st.info("No DC011 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            # numeric coercions
            for col in ("nps_in", "asme_class", "stress_mpa", "tau_mpa", "K_total", "Cv"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","tau_mpa","K_total","Cv",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC011 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC011 latest per user)", data=csv,
                            file_name="users_latest_dc011.csv", mime="text/csv", key="admin_dc011_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC011 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc011_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list (Supabase)
                try:
                    recs = (
                        sb.table("dc011_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC011 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    labels = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", labels, key=f"admin_dc011_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc011_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC011 record (admin)", type="secondary", key=f"admin_dc011_del_{pick_id}"):
                                try:
                                    sb.table("dc011_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
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

                # extras sometimes shown in the table
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
                    ("Shear τ [MPa]",                   s.get("tau_MPa")),
                    ("Result",                          s.get("verdict")),
                ])

        # -------- Filters --------
        with st.expander("Filters", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                f_user = st.text_input("Username contains", key="admin_dc012_user_filter")
            with c2:
                f_name = st.text_input("Latest calc name contains", key="admin_dc012_name_filter")
            with c3:
                limit = st.number_input("Max users", min_value=10, max_value=5000, step=10, value=200, key="admin_dc012_limit")
            btn = st.button("Apply filters / Refresh (DC012)", type="primary", key="admin_dc012_refresh")

        sb = get_supabase()

        def _fetch_users_with_latest_dc012() -> List[Dict[str, Any]]:
            """
            Supabase version:
            1) pull users (filter+limit)
            2) per-user fetch latest dc012_calcs (with data)
            3) optional latest-name filter
            4) summarize JSON for table preview
            """
            uq = sb.table("users").select("id, username, first_name, last_name, created_at")
            if f_user and f_user.strip():
                uq = uq.ilike("username", f"%{f_user.strip()}%")
            uq = uq.order("created_at", desc=True).limit(int(limit))

            try:
                uresp = uq.execute()
                users = uresp.data or []
            except Exception as e:
                st.error(f"User query failed: {e}")
                return []

            out: List[Dict[str, Any]] = []
            dtab = sb.table("dc012_calcs")

            for u in users:
                uid = u.get("id")
                uname = u.get("username")
                full_name = (f"{(u.get('first_name') or '').strip()} {(u.get('last_name') or '').strip()}").strip() or uname

                # Fetch latest calc for this user
                try:
                    dresp = (
                        dtab.select("id, name, created_at, updated_at, data")
                            .eq("user_id", uid)
                            .order("updated_at", desc=True)
                            .order("created_at", desc=True)
                            .limit(1)
                            .execute()
                    )
                    drows = dresp.data or []
                    latest = drows[0] if drows else None
                except Exception:
                    latest = None

                # optional name filter on the latest
                if f_name and f_name.strip():
                    if not (latest and isinstance(latest.get("name"), str) and f_name.strip().lower() in latest["name"].lower()):
                        continue

                s = _dc012_summarize(((latest or {}).get("data")) or {})

                out.append({
                    "user_id": str(uid),
                    "username": uname,
                    "full_name": full_name,
                    "calc_id": str(latest["id"]) if latest else None,
                    "calc_name": (latest or {}).get("name"),
                    "created_at": (latest or {}).get("created_at"),
                    "updated_at": (latest or {}).get("updated_at"),
                    # table preview fields
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "stress_mpa": s.get("Es_MPa"),
                    "tau_mpa": s.get("tau_MPa"),
                    "verdict": s.get("verdict"),
                    "_user_created_at": u.get("created_at"),  # fallback sort
                })

            # sort by latest updated_at, fallback to user created_at
            def _sort_key(r):
                return (r.get("updated_at") or r.get("_user_created_at") or "")
            out.sort(key=_sort_key, reverse=True)
            return out

        cache_key = "admin_dc012_cache_rows"
        if btn or cache_key not in st.session_state:
            st.session_state[cache_key] = _fetch_users_with_latest_dc012()

        users_latest: List[Dict[str, Any]] = st.session_state.get(cache_key, [])

        # -------- Table: latest per user --------
        if not users_latest:
            st.info("No DC012 calculations found for the filters.")
        else:
            df = pd.DataFrame(users_latest)
            for col in ("nps_in", "asme_class", "stress_mpa", "tau_mpa"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            if "created_at" in df.columns:
                df["created_at"] = df["created_at"].map(_fmt_ts)
            if "updated_at" in df.columns:
                df["updated_at"] = df["updated_at"].map(_fmt_ts)

            cols = [
                "user_id","full_name","username","calc_id","calc_name",
                "nps_in","asme_class","stress_mpa","tau_mpa","verdict",
                "created_at","updated_at"
            ]
            cols_present = [c for c in cols if c in df.columns]

            st.markdown("### Users • Latest DC012 at a glance")
            st.dataframe(df.reindex(columns=cols_present), use_container_width=True, hide_index=True)

            csv = df.reindex(columns=cols_present).to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Export CSV (DC012 latest per user)", data=csv,
                            file_name="users_latest_dc012.csv", mime="text/csv", key="admin_dc012_export")

            # -------- Drill-down: one user's list + one record prettified --------
            st.markdown("---")
            st.markdown("### Inspect a specific user's DC012 calculations")

            user_opts = ["-- select user --"] + [
                f"{r.get('full_name') or r['username']}  •  {r['username']}" for r in users_latest
            ]
            pick_user = st.selectbox("User", user_opts, key="admin_dc012_pick_user")
            if pick_user and pick_user != "-- select user --":
                uid = {
                    f"{r.get('full_name') or r['username']}  •  {r['username']}": r["user_id"]
                    for r in users_latest
                }.get(pick_user)

                # Full list for this user (Supabase)
                try:
                    recs = (
                        sb.table("dc012_calcs")
                        .select("id, name, data, created_at, updated_at")
                        .eq("user_id", uid)
                        .order("updated_at", desc=True)
                        .order("created_at", desc=True)
                        .limit(1000)
                        .execute()
                    )
                    items = recs.data or []
                except Exception as e:
                    st.error(f"Load list failed: {e}")
                    items = []

                if not items:
                    st.info("No DC012 records for this user.")
                    with st.expander("Why am I seeing this? (debug)"):
                        st.write({"user_id": uid, "records_found": 0})
                else:
                    labels = ["-- select calculation --"] + [
                        f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)" for r in items
                    ]
                    sel = st.selectbox("Calculation", labels, key=f"admin_dc012_pick_calc_{uid}")
                    if sel and sel != "-- select calculation --":
                        pick_map = {
                            f"{(r.get('name') or 'Untitled')} ({str(r.get('id'))[:8]}…)": str(r.get("id"))
                            for r in items
                        }
                        pick_id = pick_map.get(sel)
                        rec = next((r for r in items if str(r.get("id")) == pick_id), None)

                        if rec:
                            st.write(
                                f"**Name:** {rec.get('name','—')} • "
                                f"**Created:** {_fmt_ts(rec.get('created_at'))} • "
                                f"**Updated:** {_fmt_ts(rec.get('updated_at'))}"
                            )
                            _render_dc012_pretty(rec.get("data") or {})

                            st.markdown("")
                            if st.button("🗑️ Delete this DC012 record (admin)", type="secondary", key=f"admin_dc012_del_{pick_id}"):
                                try:
                                    sb.table("dc012_calcs").delete().eq("id", pick_id).execute()
                                except Exception as e:
                                    st.error(f"Delete failed: {e}")
                                else:
                                    st.success("Deleted.")
                                    st.session_state.pop(cache_key, None)
                                    st.rerun()
