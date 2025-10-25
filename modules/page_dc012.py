# page_dc012.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import streamlit as st
from datetime import datetime

# ── Auth + wizard base (same pattern as DC010/DC011)
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# Optional: if your wizard_base exposes a "finish" helper, we’ll use it gracefully.
try:
    from wizard_base import finish as wizard_finish  # type: ignore
except Exception:
    wizard_finish = None

# ── Backend repo (PostgreSQL) for DC012
from dc012_repo import (
    create_dc012_calc, list_dc012_calcs, get_dc012_calc,
    update_dc012_calc, delete_dc012_calc
)

# ──────────────────────────────────────────────────────────────────────────────
# UNI-ISO 3266 tables (from your sheet)
THREADS = ["M8", "M10", "M12", "M16", "M20", "M24", "M30", "M36", "M42", "M48", "M56"]

# Cross-sectional areas A [mm²]
AREA_MAP = {
    "M8": 36, "M10": 58, "M12": 84, "M16": 157, "M20": 245,
    "M24": 353, "M30": 561, "M36": 817, "M42": 1120, "M48": 1470, "M56": 2030
}

# Rated load per eye bolt [kg] – straight (0°) and at 45°
RATED_0_MAP = {  # CARICO CON TIRO DIRITTO (kg)
    "M8": 140, "M10": 230, "M12": 340, "M16": 700, "M20": 1200,
    "M24": 1800, "M30": 3600, "M36": 5100, "M42": 7000, "M48": 8600, "M56": None
}
RATED_45_MAP = {  # CARICO CON TIRO A 45° (kg)
    "M8": 95, "M10": 170, "M12": 240, "M16": 500, "M20": 830,
    "M24": 1270, "M30": 2600, "M36": 3700, "M42": 5000, "M48": 6100, "M56": 8300
}

# Material line (as on your sheet)
MATERIALS = {
    "C15": {"tensile": 540.0, "yield": 295.0, "allowable": 295.0 / 4.0},  # 73.75 MPa
}

# ──────────────────────────────────────────────────────────────────────────────
# CSS + layout helpers (same pattern as DC010/DC011)
_ROW_CSS = """
<style>
.row-label{
  flex:0 0 360px; text-align:right;
  height:40px; display:flex; align-items:center; justify-content:flex-end;
  font-weight:600; color:#0f172a; white-space:nowrap; padding:0 .5rem;
}
.row-input{ display:flex; align-items:center; }
.stTextInput > div > div > input,
.stNumberInput > div > div > input{ height:40px !important; padding:0 .7rem !important; }
.stSelectbox > div > div{ min-height:40px !important; }
.block-container .stMarkdown{ margin:0; }
.badge{ padding:.35rem .8rem; border-radius:.5rem; color:#fff; font-weight:800; letter-spacing:.3px; display:inline-block; }
.badge.ok{ background:#22c55e; }
.badge.bad{ background:#ef4444; }
</style>
"""

def _css():
    st.markdown(_ROW_CSS, unsafe_allow_html=True)

def _row(label: str):
    lc, rc = st.columns([1.25, 2.25])
    with lc:
        st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
    return rc

def _out_calc(key: str, value, fmt: str = "{}"):
    """Read-only field aligned in the right column."""
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s
    st.text_input("", key=key, value=s, disabled=True, label_visibility="collapsed")

def _selectbox_with_state(key: str, options, default_index=0):
    if key in st.session_state:
        return st.selectbox("", options, key=key, label_visibility="collapsed")
    return st.selectbox("", options, index=default_index, key=key, label_visibility="collapsed")

# ──────────────────────────────────────────────────────────────────────────────
# Small helpers for base hydration (same approach as DC010/DC011)
def _is_set(v) -> bool:
    return v not in (None, "", "None")

def _fmt_dt(x: Any) -> str:
    if not x: return "—"
    try:
        base = str(x)[:26]
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(base, fmt).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
    except Exception:
        pass
    return str(x)[:16]

def _normalize_first_pair(rows: List[Any]) -> Tuple[Optional[str], Optional[str]]:
    if not rows: return None, None
    first = rows[0]
    rid, nm = None, "Untitled"
    if isinstance(first, (list, tuple)):
        if len(first) >= 1: rid = first[0]
        if len(first) >= 2 and first[1] not in (None, ""): nm = first[1]
    elif isinstance(first, dict):
        rid = first.get("id") or first.get("design_id") or first.get("calc_id") or first.get("id_")
        nm = first.get("name") or first.get("title") or nm
    elif isinstance(first, str):
        rid = first
    return (str(rid) if rid else None, str(nm) if nm else None)

def _seed_base_from_valve(user_id: Optional[str]):
    """
    Populate st.session_state with base values using:
    1) locked wizard_base if present,
    2) latest valve design if still missing essentials.
    """
    # 1) From locked wizard base
    if is_locked():
        wb = get_base() or {}
        st.session_state.setdefault("valve_nps", wb.get("nps_in"))
        st.session_state.setdefault("valve_asme_class", wb.get("asme_class"))
        if wb.get("bore_diameter_mm") is not None:
            st.session_state.setdefault("bore_diameter_mm", wb.get("bore_diameter_mm"))
        if wb.get("operating_pressure_mpa") is not None:
            st.session_state.setdefault("operating_pressure_mpa", wb.get("operating_pressure_mpa"))
        if wb.get("design_id"):
            st.session_state.setdefault("active_design_id", wb.get("design_id"))
        if wb.get("name"):
            st.session_state.setdefault("active_design_name", wb.get("name"))

    # 2) From user's latest valve design if still missing essentials
    have_essential = all(
        st.session_state.get(k) not in (None, "", 0)
        for k in ("valve_nps", "valve_asme_class")
    )
    if have_essential or not user_id:
        return

    try:
        rows = list_valve_designs(user_id, limit=1)
        vid, vname = _normalize_first_pair(rows)
        if not vid:
            return
        vdata = get_valve_design(vid, user_id) or {}
        vcalc = vdata.get("calculated") or {}

        st.session_state.setdefault("valve_nps", vdata.get("nps_in"))
        st.session_state.setdefault("valve_asme_class", vdata.get("asme_class"))
        st.session_state.setdefault("bore_diameter_mm", vcalc.get("bore_diameter_mm"))
        st.session_state.setdefault(
            "operating_pressure_mpa",
            vcalc.get("operating_pressure_mpa") or vdata.get("calc_operating_pressure_mpa")
        )
        st.session_state.setdefault("active_design_id", vid)
        st.session_state.setdefault("active_design_name", vname)
    except Exception:
        pass  # keep quiet if repo is not available

def _default_bore_mm() -> float:
    for k in ("bore_diameter_mm", "bore_mm", "internal_bore_mm"):
        if k in st.session_state and st.session_state.get(k) not in (None, "", "None"):
            try:
                return float(st.session_state.get(k))
            except Exception:
                pass
    return 51.0

def _base_banner_from_session():
    nps = st.session_state.get("valve_nps")
    cls = st.session_state.get("valve_asme_class")
    po  = st.session_state.get("operating_pressure_mpa")
    po_txt = f"{po:.2f}" if isinstance(po, (int, float)) else (str(po) if _is_set(po) else "—")
    if st.session_state.get("active_design_id"):
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{nps if _is_set(nps) else "—"}** • '
            f'ASME **{cls if _is_set(cls) else "—"}** • '
            f'Bore **{_default_bore_mm():.2f} mm** • '
            f'Po **{po_txt} MPa**'
        )

# ──────────────────────────────────────────────────────────────────────────────
def render_dc012():
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>LIFTING LUGS CALCULATION</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC012</h4>", unsafe_allow_html=True)
    st.markdown("---")
    _base_banner_from_session()

    st.markdown("### LIFTING EYE BOLTS")

    # Defaults
    P_default = float(st.session_state.get("valve_weight_kg", 41.0))

    # ── INPUTS (labels left, fields right)
    i = _row("Valve weight  P  [kg]")
    P_kg = i.number_input("", value=P_default, step=0.1, format="%.2f",
                          key="dc012_Pkg", label_visibility="collapsed")

    i = _row("Eye bolt thread")
    with i:
        thread = _selectbox_with_state("dc012_thread", THREADS, default_index=THREADS.index("M10"))

    # Cross-sectional area A (prefill from table; editable)
    default_A = float(AREA_MAP[thread])
    # If the selected thread changed and A was still equal to the previous default, refresh it
    last_thr = st.session_state.get("dc012_last_thread")
    prev_a = st.session_state.get("dc012_A_mm2")
    if last_thr is not None and last_thr != thread and (prev_a is None or prev_a == AREA_MAP.get(last_thr)):
        st.session_state["dc012_A_mm2"] = default_A
    st.session_state["dc012_last_thread"] = thread

    i = _row("Cross sectional area  A  [mm²]")
    A_mm2 = i.number_input("", value=float(st.session_state.get("dc012_A_mm2", default_A)),
                           step=1.0, format="%.0f", key="dc012_A_mm2", label_visibility="collapsed")

    i = _row("Quantity of eye bolts  N")
    N = i.number_input("", value=4, step=1, min_value=1, format="%d",
                       key="dc012_N", label_visibility="collapsed")

    i = _row("Lifting angle")
    angle = i.radio("", ["0° (straight)", "45°"], index=0, horizontal=True,
                    key="dc012_angle", label_visibility="collapsed")

    # Rated load (from UNI-ISO table) selection by angle + thread, but allow override
    rated_tbl = RATED_0_MAP if "0°" in angle else RATED_45_MAP
    rated_default = rated_tbl.get(thread) or 0.0
    i = _row("Force eye bolt  F  [kg] — (UNI-ISO 3266)")
    F_rated_kg = i.number_input("", value=float(st.session_state.get("dc012_Frated", rated_default)),
                                step=1.0, format="%.0f", key="dc012_Frated", label_visibility="collapsed")

    # Side reference table like your sheet
    i = _row("UNI-ISO 3266 reference table")
    with i:
        df = pd.DataFrame({
            "Thread": THREADS,
            "Area A [mm²]": [AREA_MAP[t] for t in THREADS],
            "Rated 0° [kg]": [RATED_0_MAP[t] if RATED_0_MAP[t] is not None else "" for t in THREADS],
            "Rated 45° [kg]": [RATED_45_MAP[t] for t in THREADS],
        })
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── CHECKS & CALCULATIONS
    per_bolt_kg = P_kg / N if N else float("inf")
    ec_ok = (F_rated_kg > 0) and (per_bolt_kg <= F_rated_kg)

    g = 9.81  # m/s²
    Es_MPa = (P_kg * g) / (N * A_mm2) if (N > 0 and A_mm2 > 0) else float("nan")

    st.markdown("---")
    st.markdown("### EYE BOLT STRESS CONDITION  Ec  (UNI-ISO 3266)")
    i = _row("Result  (per-bolt weight ≤ rated load)")
    with i:
        st.markdown(
            f"<span class='badge {'ok' if ec_ok else 'bad'}'>{'OK' if ec_ok else 'NOT OK'}</span>",
            unsafe_allow_html=True
        )

    st.markdown("### EFFECTIVE EYE BOLT STRESS CALCULATION  Es")
    i = _row("Es  [MPa]  = (P·g) / (N·A)")
    with i:
        _out_calc("dc012_Es", f"{Es_MPa:.2f}" if Es_MPa == Es_MPa else "—", "{}")

    # ── MATERIAL & FINAL CHECKS
    i = _row("MATERIAL")
    with i:
        mat_name = _selectbox_with_state("dc012_material", list(MATERIALS.keys()), default_index=0)
        mat = MATERIALS[mat_name]

    i = _row("TENSILE  [MPa]")
    with i:
        _out_calc("dc012_mat_tensile", f"{mat['tensile']:.0f}", "{}")

    i = _row("YIELD  [MPa]")
    with i:
        _out_calc("dc012_mat_yield", f"{mat['yield']:.0f}", "{}")

    i = _row("ALLOWABLE  [MPa]  (= Yield / 4)")
    with i:
        _out_calc("dc012_mat_allow", f"{mat['allowable']:.2f}", "{}")

    i = _row("Es  [MPa]  (again)")
    with i:
        _out_calc("dc012_Es_again", f"{Es_MPa:.2f}" if Es_MPa == Es_MPa else "—", "{}")

    stress_ok = (Es_MPa == Es_MPa) and (Es_MPa <= mat["allowable"])
    i = _row("Final check  (Es ≤ Allowable)")
    with i:
        st.markdown(
            f"<span class='badge {'ok' if stress_ok else 'bad'}'>{'OK' if stress_ok else 'NOT OK'}</span>",
            unsafe_allow_html=True
        )

    # Persist for reports/export
    st.session_state["dc012"] = {
        "P_kg": float(P_kg),
        "thread": thread,
        "A_mm2": float(A_mm2),
        "N": int(N),
        "angle": angle,
        "F_rated_kg": float(F_rated_kg),
        "per_bolt_kg": float(per_bolt_kg),
        "Ec_ok": bool(ec_ok),
        "Es_MPa": float(Es_MPa) if Es_MPa == Es_MPa else None,
        "material": mat_name,
        "allowable_MPa": float(mat["allowable"]),
        "stress_ok": bool(stress_ok),
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC012")

    if not user_id:
        st.info("Log in to save your DC012 calculations.")
        return

    # Build payload (Base + Inputs + Computed)
    base_payload: Dict[str, Any] = {
        "valve_design_id":   st.session_state.get("active_design_id"),
        "valve_design_name": st.session_state.get("active_design_name"),
        "nps_in":            st.session_state.get("valve_nps"),
        "asme_class":        st.session_state.get("valve_asme_class"),
        "bore_diameter_mm":  _default_bore_mm(),
        "operating_pressure_mpa": st.session_state.get("operating_pressure_mpa"),
        "valve_weight_kg":   st.session_state.get("valve_weight_kg", P_kg),
    }
    inputs_payload: Dict[str, Any] = {
        "P_kg": float(P_kg),
        "thread": thread,
        "A_mm2": float(A_mm2),
        "N": int(N),
        "angle": angle,
        "F_rated_kg": float(F_rated_kg),
    }
    computed_payload: Dict[str, Any] = {
        "per_bolt_kg": float(per_bolt_kg),
        "Ec_ok": bool(ec_ok),
        "Es_MPa": float(Es_MPa) if Es_MPa == Es_MPa else None,
        "material": mat_name,
        "allowable_MPa": float(mat["allowable"]),
        "stress_ok": bool(stress_ok),
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC012_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as", value=default_name, key="dc012_save_name")
        if st.button("💾 Save DC012", type="primary", use_container_width=True, key="dc012_btn_save"):
            try:
                new_id = create_dc012_calc(
                    user_id,
                    save_name,
                    payload,
                    design_id=st.session_state.get("active_design_id"),
                )
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    def _normalize_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
        out: List[Tuple[str, str, Any, Any]] = []
        for r in rows or []:
            rid, nm, ca, ua = None, "Untitled", None, None
            if isinstance(r, (list, tuple)):
                if len(r) >= 1: rid = r[0]
                if len(r) >= 2 and r[1] not in (None, ""): nm = r[1]
                if len(r) >= 3: ca = r[2]
                if len(r) >= 4: ua = r[3]
            elif isinstance(r, dict):
                rid = r.get("id") or r.get("calc_id") or r.get("id_")
                nm  = r.get("name") or nm
                ca  = r.get("created_at")
                ua  = r.get("updated_at")
            elif isinstance(r, str):
                rid = r
            if rid:
                out.append((str(rid), str(nm), ca, ua))
        return out

    with colR:
        items_raw = list_dc012_calcs(user_id, limit=500)
        items = _normalize_list(items_raw)
        if not items:
            st.info("No DC012 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC012 saves", ["-- none --", *label_to_id.keys()], key="dc012_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc012_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC012')}** • "
                    f"Created: **{_fmt_dt(created_at)}** • "
                    f"Updated: **{_fmt_dt(updated_at)}**"
                )

                st.markdown("#### Summary (Base)")
                st.table(pd.DataFrame([
                    ["Valve design name", base_s.get("valve_design_name")],
                    ["Valve design ID",   base_s.get("valve_design_id")],
                    ["NPS [in]",          base_s.get("nps_in")],
                    ["ASME Class",        base_s.get("asme_class")],
                    ["Bore (base) [mm]",  base_s.get("bore_diameter_mm")],
                    ["Po (base) [MPa]",   base_s.get("operating_pressure_mpa")],
                    ["Valve weight [kg]", base_s.get("valve_weight_kg")],
                ], columns=["Field", "Value"]))

                st.markdown("**Inputs**")
                st.table(pd.DataFrame([
                    ["P [kg]", ins_s.get("P_kg")],
                    ["Thread", ins_s.get("thread")],
                    ["A [mm²]", ins_s.get("A_mm2")],
                    ["N", ins_s.get("N")],
                    ["Angle", ins_s.get("angle")],
                    ["F rated [kg]", ins_s.get("F_rated_kg")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed**")
                st.table(pd.DataFrame([
                    ["Per-bolt load [kg]", comp_s.get("per_bolt_kg")],
                    ["Ec OK", comp_s.get("Ec_ok")],
                    ["Es [MPa]", comp_s.get("Es_MPa")],
                    ["Material", comp_s.get("material")],
                    ["Allowable [MPa]", comp_s.get("allowable_MPa")],
                    ["Stress OK", comp_s.get("stress_ok")],
                ], columns=["Field", "Value"]))

                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=picked.split(" (", 1)[0], key=f"dc012_rename_{sel_id}")
                    if st.button("Save name", key=f"dc012_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc012_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc012_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc012_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load into page", key=f"dc012_btn_load_{sel_id}", use_container_width=True):
                        # inputs back into page
                        st.session_state["dc012_Pkg"]    = ins_s.get("P_kg", st.session_state.get("dc012_Pkg"))
                        st.session_state["dc012_thread"] = ins_s.get("thread", st.session_state.get("dc012_thread"))
                        st.session_state["dc012_A_mm2"]  = ins_s.get("A_mm2", st.session_state.get("dc012_A_mm2"))
                        st.session_state["dc012_N"]      = ins_s.get("N", st.session_state.get("dc012_N"))
                        st.session_state["dc012_angle"]  = ins_s.get("angle", st.session_state.get("dc012_angle"))
                        st.session_state["dc012_Frated"] = ins_s.get("F_rated_kg", st.session_state.get("dc012_Frated"))

                        # refresh base banner from the record
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")
                        st.session_state["valve_weight_kg"]        = base_s.get("valve_weight_kg") or st.session_state.get("valve_weight_kg")
                        st.session_state["active_design_id"]       = base_s.get("valve_design_id") or st.session_state.get("active_design_id")
                        st.session_state["active_design_name"]     = base_s.get("valve_design_name") or st.session_state.get("active_design_name")

                        st.success("Loaded into page and base banner refreshed.")
                        st.rerun()

    # ───────────────────────── Finish Wizard (final step) ─────────────────────
    st.markdown("---")
    with st.expander("✅ Finish Wizard", expanded=False):
        st.write("This will finalize the design using the base values shown in the banner and save this DC012 summary.")
        colf1, colf2 = st.columns(2)
        with colf1:
            if st.button("Save DC012 summary now", key="dc012_btn_save_summary_finish", use_container_width=True):
                try:
                    new_id = create_dc012_calc(
                        user_id,
                        f"DC012_{st.session_state.get('active_design_name') or 'calc'}",
                        payload,
                        design_id=st.session_state.get("active_design_id"),
                    )
                    st.success(f"Summary saved ✔ (ID: {new_id[:8]}…)")
                    st.session_state["dc012_last_saved_id"] = new_id
                except Exception as e:
                    st.error(f"Save failed: {e}")
        with colf2:
            if st.button("Mark wizard as finished", key="dc012_btn_finish_wizard", use_container_width=True):
                # If your wizard module exposes a finisher, use it, else set a session flag.
                if callable(wizard_finish):
                    try:
                        wizard_finish(
                            design_id=st.session_state.get("active_design_id"),
                            base={
                                "nps_in": st.session_state.get("valve_nps"),
                                "asme_class": st.session_state.get("valve_asme_class"),
                                "bore_diameter_mm": _default_bore_mm(),
                                "operating_pressure_mpa": st.session_state.get("operating_pressure_mpa"),
                                "name": st.session_state.get("active_design_name"),
                            },
                        )
                        st.success("Wizard was marked finished and base values were locked.")
                    except Exception as e:
                        st.warning(f"Tried to finish via wizard module, but got: {e}. Setting a local finish flag instead.")
                        st.session_state["wizard_finished"] = True
                        st.success("Wizard marked finished (local flag).")
                else:
                    st.session_state["wizard_finished"] = True
                    st.success("Wizard marked finished (local flag).")
