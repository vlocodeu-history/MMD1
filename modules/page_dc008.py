# page_dc008.py
from __future__ import annotations
import math, os
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime

# ----------------------------- constants from your original page -----------------------------
REQ_SY = {"150-600": 170.00, "900": 205.00, "1500": 250.00, "2500": 300.00}
REQ_DB = {"150-600": 1.50, "900": 1.55, "1500": 1.60, "2500": 1.70}
CLASS_LEVELS = ["150-600", "900", "1500", "2500"]

# ── Auth + wizard base
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── Backend repo (PostgreSQL)
from dc008_repo import (
    create_dc008_calc, list_dc008_calcs, get_dc008_calc,
    update_dc008_calc, delete_dc008_calc
)

# ──────────────────────────────────────────────────────────────────────────────
# CSS + layout helpers (labels left, fields right)
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
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _class_to_band(asme_class: int) -> str:
    if asme_class <= 600:  return "150-600"
    if asme_class <= 900:  return "900"
    if asme_class <= 1500: return "1500"
    return "2500"

def _show_dc008_image(container, size_px: int = 300):
    for p in ["dc008_ball.png", "assets/dc008_ball.png", "static/dc008_ball.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Ball / bore geometry (schematic)", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Could not load DC008 diagram ({e}).")
            return
    with container:
        st.info("Add **dc008_ball.png** (or put it in ./assets/ or ./static/) to show the sketch here.")

# ──────────────────────────────────────────────────────────────────────────────
# Wizard hydration helpers
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
    # 1) Hydrate from wizard if locked
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

    # 2) Fallback to latest valve design if needed
    if all(st.session_state.get(k) not in (None, "", 0) for k in ("valve_nps", "valve_asme_class")):
        return
    if not user_id:
        return
    try:
        rows = list_valve_designs(user_id, limit=1)
        vid, vname = _normalize_first_pair(rows)
        if not vid: return
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
        pass

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

# ──────────────────────────────────────────────────────────────────────────────
def render_dc008():
    """DC008 — BALL SIZING CALCULATION"""
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>BALL SIZING CALCULATION</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC008</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Optional base banner
    if st.session_state.get("active_design_id"):
        po = st.session_state.get("operating_pressure_mpa")
        po_txt = f"{po:.2f}" if isinstance(po, (int, float)) else str(po or "—")
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{st.session_state.get("valve_nps","—")}** • '
            f'ASME **{st.session_state.get("valve_asme_class","—")}** • '
            f'Po **{po_txt} MPa**'
        )

    # Defaults from earlier pages
    asme_cls_num = int(st.session_state.get("valve_asme_class", 600))
    asme_band_default = _class_to_band(asme_cls_num)
    Pr_default = float(st.session_state.get("operating_pressure_mpa", 10.21))
    B_default  = float(st.session_state.get("bore_diameter_mm", 51.0))

    st.markdown("### INPUT DATA")

    i = _row("Design pressure  Pr  [MPa]")
    with i:
        Pr = st.number_input("", value=Pr_default, step=0.01, format="%.2f",
                             key="dc008_Pr", label_visibility="collapsed")

    i = _row("Ball diameter  D ball  [mm]")
    with i:
        D_ball = st.number_input("", value=88.95, step=0.01, format="%.2f",
                                 key="dc008_Dball", label_visibility="collapsed")

    i = _row("Bore diameter  B  [mm]")
    with i:
        B = st.number_input("", value=B_default, step=0.1, format="%.1f",
                            key="dc008_B", label_visibility="collapsed")

    i = _row("Contact angle  α  [deg]")
    with i:
        alpha_deg = st.number_input("", value=45.0, step=0.5, format="%.1f",
                                    key="dc008_alpha", label_visibility="collapsed")

    i = _row("Ball Material")
    with i:
        ball_material = st.text_input("", value="ASTM A479 UNS S31600",
                                      key="dc008_mat", label_visibility="collapsed")

    i = _row("Yield stress  Sy  [MPa]")
    with i:
        Sy = st.number_input("", value=205.0, step=1.0, format="%.0f",
                             key="dc008_Sy", label_visibility="collapsed")

    i = _row("Distance of flat top from Centerline  H  [mm]")
    with i:
        H = st.number_input("", value=32.5, step=0.1, format="%.1f",
                            key="dc008_H", label_visibility="collapsed")

    # Derived thickness at top
    T = H - B / 2.0
    i = _row("Ball thickness in the top region  T  [mm] = H − B/2")
    with i:
        _out_calc("dc008_T", f"{T:.3f}", "{}")

    # Valve class (read-only)
    i = _row("Valve Class (from Valve Data)")
    with i:
        _out_calc("dc008_class_ro", str(asme_cls_num), "{}")

    # Figure
    i = _row("Figure")
    _show_dc008_image(i, 300)

    st.markdown("---")
    st.markdown("### SIZING CRITERIA")

    i = _row("Minimum Yield stress of selected material — pick Class")
    with i:
        cls_yield = st.selectbox("", CLASS_LEVELS,
                                 index=CLASS_LEVELS.index(asme_band_default),
                                 key="dc008_cls_yield", label_visibility="collapsed")
    req_Sy_min = REQ_SY[cls_yield]
    i = _row("Required  Sy(min)  [MPa]")
    with i:
        _out_calc("dc008_req_sy", f"{req_Sy_min:.2f}", "{}")

    i = _row("Minimum Ratio Spherical Diameter / internal Bore — pick Class")
    with i:
        cls_ratio = st.selectbox("", CLASS_LEVELS,
                                 index=CLASS_LEVELS.index(asme_band_default),
                                 key="dc008_cls_ratio", label_visibility="collapsed")
    req_DB_min = REQ_DB[cls_ratio]
    i = _row("Required  (D/B)min")
    with i:
        _out_calc("dc008_req_db", f"{req_DB_min:.3f}", "{}")

    # Actual D/B
    actual_DB = (D_ball / B) if B else float("nan")
    i = _row("Actual Ratio  D / B")
    with i:
        _out_calc("dc008_actual_db", f"{actual_DB:.2f}", "{}")

    # Checks
    ok_sy = Sy >= req_Sy_min
    ok_db = actual_DB >= req_DB_min

    i = _row("Material check  (Sy ≥ Sy(min))")
    with i:
        _out_calc("dc008_check_sy", "OK" if ok_sy else "NOT OK", "{}")

    i = _row("Geometry check  (D/B ≥ (D/B)min)")
    with i:
        _out_calc("dc008_check_db", "OK" if ok_db else "NOT OK", "{}")

    st.markdown("---")
    st.markdown("### SHELL STRESS CALCULATION  St1  \naccording to ASME VIII DIV.1 Ed.2023 / Appendix 1 Ed.2023")

    # Circumferential (hoop) stress at top
    if T <= 0:
        St1a = float("nan")
    else:
        St1a = Pr * (0.5 * (B / T) + 0.6)

    allow_23Sy = (2.0 / 3.0) * Sy

    i = _row("Circumferential stress  St1a  [MPa] = Pr × [ 0.5 × B/T + 0.6 ]")
    with i:
        _out_calc("dc008_St1a", f"{St1a:.2f}", "{}")

    i = _row("Allowable limit  2/3 Sy  [MPa]")
    with i:
        _out_calc("dc008_allow23", f"{allow_23Sy:.2f}", "{}")

    verdict = "OK" if (not (St1a != St1a)) and (St1a <= allow_23Sy) else "NOT OK"
    i = _row("Final check  (St1a ≤ 2/3 Sy)")
    with i:
        _out_calc("dc008_verdict", verdict, "{}")

    # Persist into session
    st.session_state["dc008"] = {
        "Pr_MPa": Pr, "D_ball_mm": D_ball, "B_mm": B, "alpha_deg": alpha_deg,
        "material": ball_material, "Sy_MPa": Sy, "H_mm": H, "T_mm": T,
        "criteria_class_yield": cls_yield, "criteria_class_ratio": cls_ratio,
        "req_Sy_min": req_Sy_min, "req_DB_min": req_DB_min,
        "actual_DB": actual_DB, "St1a_MPa": St1a, "allow_23Sy_MPa": allow_23Sy,
        "check_sy": ok_sy, "check_db": ok_db, "verdict": verdict
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC008")

    if not user_id:
        st.info("Log in to save your DC008 calculations.")
        return

    # Build payload (Base + Inputs + Computed)
    base_payload: Dict[str, Any] = {
        "valve_design_id":   st.session_state.get("active_design_id"),
        "valve_design_name": st.session_state.get("active_design_name"),
        "nps_in":            st.session_state.get("valve_nps"),
        "asme_class":        st.session_state.get("valve_asme_class"),
        "bore_diameter_mm":  st.session_state.get("bore_diameter_mm"),
        "operating_pressure_mpa": st.session_state.get("operating_pressure_mpa"),
    }
    inputs_payload: Dict[str, Any] = {
        "Pr_MPa": Pr,
        "D_ball_mm": D_ball,
        "B_mm": B,
        "alpha_deg": alpha_deg,
        "ball_material": ball_material,
        "Sy_MPa": Sy,
        "H_mm": H,
    }
    computed_payload: Dict[str, Any] = {
        "T_mm": T,
        "criteria_class_yield": cls_yield,
        "criteria_class_ratio": cls_ratio,
        "req_Sy_min": req_Sy_min,
        "req_DB_min": req_DB_min,
        "actual_DB": actual_DB,
        "St1a_MPa": St1a,
        "allow_23Sy_MPa": allow_23Sy,
        "check_sy": ok_sy,
        "check_db": ok_db,
        "verdict": verdict,
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC008_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc008_save_name")
        if st.button("💾 Save DC008", type="primary", key="dc008_btn_save", use_container_width=True):
            try:
                new_id = create_dc008_calc(
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
        items_raw = list_dc008_calcs(user_id)
        items = _normalize_list(items_raw)
        if not items:
            st.info("No DC008 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC008 saves", ["-- none --", *label_to_id.keys()], key="dc008_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc008_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC008')}** • "
                    f"Created: **{_fmt_dt(created_at)}** • "
                    f"Updated: **{_fmt_dt(updated_at)}**"
                )

                st.markdown("#### Summary (Prettified)")
                st.markdown("**Base (from Valve Data)**")
                st.table(pd.DataFrame([
                    ["Valve design name", base_s.get("valve_design_name")],
                    ["Valve design ID",   base_s.get("valve_design_id")],
                    ["NPS [in]",          base_s.get("nps_in")],
                    ["ASME Class",        base_s.get("asme_class")],
                    ["Bore (base) [mm]",  base_s.get("bore_diameter_mm")],
                    ["Po (base) [MPa]",   base_s.get("operating_pressure_mpa")],
                ], columns=["Field", "Value"]))

                st.markdown("**Inputs**")
                st.table(pd.DataFrame([
                    ["Pr [MPa]", ins_s.get("Pr_MPa")],
                    ["D ball [mm]", ins_s.get("D_ball_mm")],
                    ["B [mm]", ins_s.get("B_mm")],
                    ["α [deg]", ins_s.get("alpha_deg")],
                    ["Ball material", ins_s.get("ball_material")],
                    ["Sy [MPa]", ins_s.get("Sy_MPa")],
                    ["H [mm]", ins_s.get("H_mm")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed / Checks**")
                st.table(pd.DataFrame([
                    ["T [mm]", comp_s.get("T_mm")],
                    ["Class (yield)", comp_s.get("criteria_class_yield")],
                    ["Class (ratio)", comp_s.get("criteria_class_ratio")],
                    ["Req. Sy min [MPa]", comp_s.get("req_Sy_min")],
                    ["Req. D/B min", comp_s.get("req_DB_min")],
                    ["Actual D/B", comp_s.get("actual_DB")],
                    ["St1a [MPa]", comp_s.get("St1a_MPa")],
                    ["Allow 2/3 Sy [MPa]", comp_s.get("allow_23Sy_MPa")],
                    ["Check Sy", "OK" if comp_s.get("check_sy") else "NOT OK"],
                    ["Check D/B", "OK" if comp_s.get("check_db") else "NOT OK"],
                    ["Verdict", comp_s.get("verdict")],
                ], columns=["Field", "Value"]))

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC008"), key=f"dc008_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc008_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc008_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc008_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc008_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc008_btn_load_{sel_id}", use_container_width=True):
                        # inputs back to session
                        st.session_state["dc008_Pr"]    = ins_s.get("Pr_MPa",  st.session_state.get("dc008_Pr"))
                        st.session_state["dc008_Dball"] = ins_s.get("D_ball_mm", st.session_state.get("dc008_Dball"))
                        st.session_state["dc008_B"]     = ins_s.get("B_mm",    st.session_state.get("dc008_B"))
                        st.session_state["dc008_alpha"] = ins_s.get("alpha_deg", st.session_state.get("dc008_alpha"))
                        st.session_state["dc008_mat"]   = ins_s.get("ball_material", st.session_state.get("dc008_mat"))
                        st.session_state["dc008_Sy"]    = ins_s.get("Sy_MPa",  st.session_state.get("dc008_Sy"))
                        st.session_state["dc008_H"]     = ins_s.get("H_mm",    st.session_state.get("dc008_H"))

                        # base convenience
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
