# page_dc006.py
from __future__ import annotations
import math, os
from typing import List, Any, Dict, Optional, Tuple
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Auth + wizard base
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── Backend repo (PostgreSQL) for DC006
from dc006_repo import (
    create_dc006_calc, list_dc006_calcs, get_dc006_calc,
    update_dc006_calc, delete_dc006_calc
)

# Simple gasket library (you can extend)
GASKETS = {
    "GRAPHITE": {"m": 2.0, "y": 5.0},   # from your sheet
    "PTFE":     {"m": 3.0, "y": 14.0},
    "Non-asb.": {"m": 2.5, "y": 7.0},
}

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
    c1, c2 = st.columns([1.25, 2.25])
    with c1:
        st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
    return c2

def _out_calc(key: str, value, fmt: str = "{}"):
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s  # keep widget synced to current value
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _img(container, size_px: int = 300):
    for p in ["dc006_flange.png", "assets/dc006_flange.png", "static/dc006_flange.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Flange / gasket geometry", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Could not load DC006 image ({e}).")
            return
    with container:
        st.info("Add **dc006_flange.png** (or put it in ./assets/ or ./static/) to display the drawing.")

# ──────────────────────────────────────────────────────────────────────────────
# Wizard hydration helpers (same pattern as other pages)
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
    # 1) hydrate from wizard if locked
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

    # already enough?
    if all(st.session_state.get(k) not in (None, "", 0) for k in ("valve_nps", "valve_asme_class")):
        return

    # 2) fallback to latest valve design
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
def render_dc006():
    """
    DC006 — Flange Stress Calculation ASME VIII Div.1 App.2
    """
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>Flange Stress Calculation ASME VIII div.1 App.2</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC 006</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Base banner (if Valve base present)
    if st.session_state.get("active_design_id"):
        po = st.session_state.get("operating_pressure_mpa")
        po_txt = f"{po:.2f}" if isinstance(po, (int, float)) else str(po or "—")
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{st.session_state.get("valve_nps","—")}** • '
            f'ASME **{st.session_state.get("valve_asme_class","—")}** • '
            f'Po **{po_txt} MPa**'
        )

    # ── Inputs
    Pa_default = float(st.session_state.get("operating_pressure_mpa", 10.21))

    i = _row("Design pressure at ambient temperature  Pa  [MPa]")
    with i:
        Pa  = st.number_input("", value=Pa_default, step=0.01, format="%.2f",
                              key="dc006_Pa", label_visibility="collapsed")

    i = _row("Flange thickness  FT  [mm]")
    with i:
        FT  = st.number_input("", value=23.0, step=0.1, format="%.1f",
                              key="dc006_FT", label_visibility="collapsed")

    i = _row("Internal Seal Gasket Diameter  ISGD  [mm]")
    with i:
        ISGD = st.number_input("", value=113.9, step=0.1, format="%.1f",
                               key="dc006_ISGD", label_visibility="collapsed")

    i = _row("Bolt circle diameter  Bcd  [mm]")
    with i:
        Bcd = st.number_input("", value=142.0, step=0.1, format="%.1f",
                              key="dc006_Bcd", label_visibility="collapsed")

    i = _row("External Seal Gasket Diameter  ESGD  [mm]")
    with i:
        ESGD = st.number_input("", value=122.7, step=0.1, format="%.1f",
                               key="dc006_ESGD", label_visibility="collapsed")

    i = _row("Gasket type")
    with i:
        gasket_names: List[str] = list(GASKETS.keys())
        gasket = st.selectbox("", options=gasket_names,
                              index=gasket_names.index("GRAPHITE"),
                              key="dc006_gasket", label_visibility="collapsed")

    i = _row("Gasket factor  m  [−]")
    with i:
        m = st.number_input("", value=float(GASKETS[gasket]["m"]), step=0.1, format="%.1f",
                            key="dc006_m", label_visibility="collapsed")

    i = _row("Gasket unit seating load  y  [MPa]")
    with i:
        y = st.number_input("", value=float(GASKETS[gasket]["y"]), step=0.1, format="%.1f",
                            key="dc006_y", label_visibility="collapsed")

    # Image
    i = _row("Sketch")
    _img(i, 300)

    st.markdown("### GASKET LOAD REACTION DIAMETER CALCULATION G (ASME VIII DIV.1 APP.2)")

    N  = (ESGD - ISGD) / 2.0
    b0 = N / 2.0
    b  = b0
    G  = ESGD - 2.0 * b

    i = _row("Gasket width  N  [mm] = (ESGD − ISGD) / 2")
    with i: _out_calc("dc006_out_N",  N,  "{:.2f}")

    i = _row("Basic gasket seating width  b0  [mm] = N / 2")
    with i: _out_calc("dc006_out_b0", b0, "{:.2f}")

    i = _row("Effective gasket seating width  b  [mm]")
    with i: _out_calc("dc006_out_b",  b,  "{:.2f}")

    i = _row("Gasket load reaction diameter  G  [mm] = ESGD − 2b")
    with i: _out_calc("dc006_out_G",  G,  "{:.2f}")

    st.markdown("### FLANGE LOAD IN OPERATING CONDITION  Wm1  (ASME VIII DIV.1 APP.2)")

    H  = (math.pi/4.0) * (G**2) * Pa
    Hp = 2.0 * b * math.pi * G * m * Pa
    Wm1 = H + Hp

    i = _row("Hydrostatic end force  H  [N] = π/4 × G² × Pa")
    with i: _out_calc("dc006_out_H",  H,  "{:,.2f}")

    i = _row("Joint contact surface compression load  Hp  [N] = 2 × b × π × G × m × Pa")
    with i: _out_calc("dc006_out_Hp", Hp, "{:,.2f}")

    i = _row("Min. required bolt load at ambient temperature  Wm1  [N] = H + Hp")
    with i: _out_calc("dc006_out_Wm1", Wm1, "{:,.2f}")

    st.markdown("### FLANGE LOAD IN GASKET SEATING CONDITION  Wm2  (ASME VIII DIV.1 APP.2)")

    Wm2 = math.pi * b * G * y

    i = _row("Min. initial required bolt load  Wm2  [N] = π × b × G × y")
    with i: _out_calc("dc006_out_Wm2", Wm2, "{:,.2f}")

    st.markdown("### CLOSURE FLANGE STRESS CALCULATION  Sf")

    K = (2.0 / math.pi) * (1.0 - 0.67 * ESGD / max(Bcd, 1e-9))
    Sf1 = K * Wm1 / max(FT, 1e-9)**2
    Sf2 = K * Wm2 / max(FT, 1e-9)**2
    Sf  = max(Sf1, Sf2)

    i = _row("Operating condition at ambient temperature  Sf₁  [MPa] = (2/π)·(1−0.67·ESGD/Bcd)·Wm1/FT²")
    with i: _out_calc("dc006_out_Sf1", Sf1, "{:.2f}")

    i = _row("Gasket seating condition  Sf₂  [MPa] = (2/π)·(1−0.67·ESGD/Bcd)·Wm2/FT²")
    with i: _out_calc("dc006_out_Sf2", Sf2, "{:.2f}")

    i = _row("Max stress  Sf  [MPa] = MAX(Sf₁, Sf₂)")
    with i: _out_calc("dc006_out_Sf",  Sf,  "{:.2f}")

    st.markdown("#### MATERIAL ALLOWABLE & CHECK")

    i = _row("Allowable stress (ALL.) [MPa] — e.g., ASTM A350 LF2 CL.1")
    with i:
        allow = st.number_input("", value=161.0, step=1.0, format="%.0f",
                                key="dc006_allow", label_visibility="collapsed")

    verdict = "OK" if Sf <= allow else "NOT OK"

    i = _row("Result")
    with i:
        st.markdown(
            f"<div style='display:flex;gap:1rem;align-items:center;'>"
            f"<div><b>Sf</b> = {Sf:.2f} MPa</div>"
            f"<div><b>Allowable</b> = {allow:.0f} MPa</div>"
            f"<div class='badge {'ok' if verdict=='OK' else 'bad'}'>{verdict}</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # Persist in session
    st.session_state["dc006"] = {
        "Pa_MPa": Pa, "Bcd_mm": Bcd, "FT_mm": FT, "ESGD_mm": ESGD, "ISGD_mm": ISGD,
        "gasket": gasket, "m": m, "y_MPa": y,
        "N_mm": N, "b0_mm": b0, "b_mm": b, "G_mm": G,
        "H_N": H, "Hp_N": Hp, "Wm1_N": Wm1, "Wm2_N": Wm2,
        "K": K, "Sf1_MPa": Sf1, "Sf2_MPa": Sf2, "Sf_MPa": Sf, "allow_MPa": allow, "verdict": verdict
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC006")

    if not user_id:
        st.info("Log in to save your DC006 calculations.")
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
        "Pa_MPa": Pa, "FT_mm": FT, "ISGD_mm": ISGD, "Bcd_mm": Bcd, "ESGD_mm": ESGD,
        "gasket": gasket, "m": m, "y_MPa": y
    }
    computed_payload: Dict[str, Any] = {
        "N_mm": N, "b0_mm": b0, "b_mm": b, "G_mm": G,
        "H_N": H, "Hp_N": Hp, "Wm1_N": Wm1, "Wm2_N": Wm2,
        "K": K, "Sf1_MPa": Sf1, "Sf2_MPa": Sf2, "Sf_MPa": Sf,
        "allow_MPa": allow, "verdict": verdict
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC006_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc006_save_name")
        if st.button("💾 Save DC006", type="primary", key="dc006_btn_save", use_container_width=True):
            try:
                new_id = create_dc006_calc(user_id, save_name, payload, design_id=st.session_state.get("active_design_id"))
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    def _normalize_dc006_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
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
        items_raw = list_dc006_calcs(user_id)
        items = _normalize_dc006_list(items_raw)
        if not items:
            st.info("No DC006 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC006 saves", ["-- none --", *label_to_id.keys()], key="dc006_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc006_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC006')}** • "
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
                    ["Pa [MPa]", ins_s.get("Pa_MPa")],
                    ["FT [mm]", ins_s.get("FT_mm")],
                    ["ISGD [mm]", ins_s.get("ISGD_mm")],
                    ["Bcd [mm]", ins_s.get("Bcd_mm")],
                    ["ESGD [mm]", ins_s.get("ESGD_mm")],
                    ["Gasket", ins_s.get("gasket")],
                    ["m [-]", ins_s.get("m")],
                    ["y [MPa]", ins_s.get("y_MPa")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed**")
                st.table(pd.DataFrame([
                    ["N [mm]", comp_s.get("N_mm")],
                    ["b0 [mm]", comp_s.get("b0_mm")],
                    ["b [mm]", comp_s.get("b_mm")],
                    ["G [mm]", comp_s.get("G_mm")],
                    ["H [N]", comp_s.get("H_N")],
                    ["Hp [N]", comp_s.get("Hp_N")],
                    ["Wm1 [N]", comp_s.get("Wm1_N")],
                    ["Wm2 [N]", comp_s.get("Wm2_N")],
                    ["K [-]", comp_s.get("K")],
                    ["Sf1 [MPa]", comp_s.get("Sf1_MPa")],
                    ["Sf2 [MPa]", comp_s.get("Sf2_MPa")],
                    ["Sf [MPa]", comp_s.get("Sf_MPa")],
                    ["Allowable [MPa]", comp_s.get("allow_MPa")],
                    ["Check", comp_s.get("verdict")],
                ], columns=["Field", "Value"]))

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC006"), key=f"dc006_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc006_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc006_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc006_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc006_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc006_btn_load_{sel_id}", use_container_width=True):
                        # Inputs back to session
                        st.session_state["dc006_Pa"]   = ins_s.get("Pa_MPa", st.session_state.get("dc006_Pa"))
                        st.session_state["dc006_FT"]   = ins_s.get("FT_mm",  st.session_state.get("dc006_FT"))
                        st.session_state["dc006_ISGD"] = ins_s.get("ISGD_mm",st.session_state.get("dc006_ISGD"))
                        st.session_state["dc006_Bcd"]  = ins_s.get("Bcd_mm", st.session_state.get("dc006_Bcd"))
                        st.session_state["dc006_ESGD"] = ins_s.get("ESGD_mm",st.session_state.get("dc006_ESGD"))

                        # gasket (if exists in options)
                        gname = ins_s.get("gasket")
                        if isinstance(gname, str) and gname in GASKETS:
                            st.session_state["dc006_gasket"] = gname
                        st.session_state["dc006_m"] = ins_s.get("m", st.session_state.get("dc006_m"))
                        st.session_state["dc006_y"] = ins_s.get("y_MPa", st.session_state.get("dc006_y"))

                        # base (optional)
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
