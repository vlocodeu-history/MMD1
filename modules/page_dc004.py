# page_dc004.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import streamlit as st
from datetime import datetime

# ── Auth + wizard base (same pattern as DC002A/DC003)
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── Backend repo for DC004 saves
from dc004_repo import (
    create_dc004_calc, list_dc004_calcs, get_dc004_calc,
    update_dc004_calc, delete_dc004_calc
)

# ──────────────────────────────────────────────────────────────────────────────
# CSS + layout helpers (labels left, fields right) — same pattern as dc003
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
    """
    Render a disabled text field that ALWAYS reflects the latest computed value.
    We write the formatted value into session_state before drawing the widget.
    """
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _show_dc004_image(container, size_px: int = 300):
    for p in ["dc004_seat_section.png", "assets/dc004_seat_section.png", "static/dc004_seat_section.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Seat section / load sketch", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Could not load DC004 diagram ({e}).")
            return
    with container:
        st.info("Add **dc004_seat_section.png** (or put it in ./assets/ or ./static/) to show the sketch here.")

# ──────────────────────────────────────────────────────────────────────────────
# Wizard hydration helpers (same as other pages)
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
    # 1) If wizard is locked, hydrate from wizard_base
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

    # If essential bits exist, done
    have_essential = all(
        st.session_state.get(k) not in (None, "", 0)
        for k in ("valve_nps", "valve_asme_class")
    )
    if have_essential:
        return

    # 2) Fallback to user's latest valve design
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
def render_dc004():
    # Access guard + base hydration (no layout change)
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")
    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>Seat Thickness Calculation ASME VIII Div.1, ASME VIII Div.2</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC004</h4>", unsafe_allow_html=True)
    st.caption("REFERENCES: ASME II PART. D TABLE 1A Ed.2023 · ASME VIII DIV.1 UG-27 · ASME VIII DIV.2: Sm")
    st.markdown("---")

    # Header (from Valve page if available) — read-only on right
    i = _row("NPS")
    with i:
        _out_calc("dc004_hdr_nps", st.session_state.get("valve_nps", ""), "{}")
    i = _row("Valve Class")
    with i:
        _out_calc("dc004_hdr_asme", st.session_state.get("valve_asme_class", ""), "{}")

    st.markdown("### INPUT DATA")

    # Allowables (editable)
    i = _row("LIMIT VALUES — ASME VIII, Div.2  SmF316 [MPa]")
    with i:
        SmF316 = st.number_input("", value=138.0, step=1.0, format="%.0f",
                                 key="dc004_SmF316", label_visibility="collapsed")
    i = _row("LIMIT VALUES — ASME VIII, Div.1  SaF316 [MPa]")
    with i:
        SaF316 = st.number_input("", value=138.0, step=1.0, format="%.0f",
                                 key="dc004_SaF316", label_visibility="collapsed")

    # Sketch/image aligned to layout
    i = _row("Sketch")
    _show_dc004_image(i, size_px=300)

    # Geometry & pressures (editable)
    P_default  = float(st.session_state.get("operating_pressure_mpa", 10.21))
    Di_default = float(st.session_state.get("bore_diameter_mm", 51.00))

    i = _row("INTERNAL SEAT DIAM.  Di [mm]")
    with i:
        Di = st.number_input("", value=Di_default, step=0.01, format="%.2f",
                             key="dc004_Di", label_visibility="collapsed")
    i = _row("DESIGN PRESSURE  P [MPa]")
    with i:
        P  = st.number_input("", value=P_default, step=0.01, format="%.2f",
                             key="dc004_P", label_visibility="collapsed")
    i = _row("SEAT TEST PRESSURE  PT = 1.1 × P [MPa]")
    with i:
        PT = st.number_input("", value=round(1.1 * P, 2), step=0.01, format="%.2f",
                             key="dc004_PT", label_visibility="collapsed")

    st.markdown("---")

    # DESIGN CONDITION — Div.1 (dynamic)  (MATH UNCHANGED)
    st.markdown("#### DESIGN CONDITION: ASME VIII, DIV.1 — Ed.2023")
    st.caption("MINIMUM THK. FOR F316 MATERIAL")
    denom_d1 = 2.0 * (SaF316 - 0.6 * P)
    t_design = (P * Di) / denom_d1 if denom_d1 > 0 else float("nan")
    i = _row("t = ( P × Di ) / ( 2 × ( SaF316 − 0.6 × P ) )")
    with i:
        _out_calc("dc004_t_design", t_design, "{:.2f}")

    # SEAT TEST CONDITION — Div.2 (dynamic)
    st.markdown("#### SEAT TEST CONDITION: ASME VIII, DIV.2 — Ed.2023")
    st.caption("MINIMUM THK. FOR F316 MATERIAL")
    denom_d2 = 2.0 * (SmF316 - 0.6 * PT)
    t_test = (PT * Di) / denom_d2 if denom_d2 > 0 else float("nan")
    i = _row("t = ( PT × Di ) / ( 2 × ( SmF316 − 0.6 × PT ) )")
    with i:
        _out_calc("dc004_t_test", t_test, "{:.2f}")

    st.markdown("---")

    # Real thickness (kept read-only as in your file)
    real_t = 6.90
    i = _row("REAL THICKNESS  [mm]")
    with i:
        _out_calc("dc004_real_t", real_t, "{:.2f}")

    # Required & verdict (unchanged logic)
    req_t  = max(t_design, t_test)
    is_nan = (req_t != req_t)  # NaN check
    verdict = "VERIFIED" if (not is_nan) and real_t >= req_t else "NOT VERIFIED"

    i = _row("Check")
    with i:
        st.markdown(
            f"<div>Required minimum thickness = <b>{(0 if is_nan else req_t):.2f} mm</b> "
            f"<span class='badge {'ok' if verdict=='VERIFIED' else 'bad'}' style='margin-left:.6rem;'>{verdict}</span></div>",
            unsafe_allow_html=True
        )

    st.caption("Dimensions in mm · Pressure in MPa")

    # persist (useful for other sheets)
    st.session_state["dc004"] = {
        "Di_mm": Di, "P_MPa": P, "PT_MPa": PT,
        "SaF316_MPa": SaF316, "SmF316_MPa": SmF316,
        "t_design_mm": t_design, "t_test_mm": t_test,
        "real_t_mm": real_t, "required_t_mm": req_t, "verdict": verdict,
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC004")

    if not user_id:
        st.info("Log in to save your DC004 calculations.")
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
        "SmF316_MPa": SmF316, "SaF316_MPa": SaF316,
        "Di_mm": Di, "P_MPa": P, "PT_MPa": PT, "real_t_mm": real_t
    }
    computed_payload: Dict[str, Any] = {
        "t_design_mm": t_design, "t_test_mm": t_test,
        "required_t_mm": req_t, "verdict": verdict
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC004_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc004_save_name")
        if st.button("💾 Save DC004", type="primary", key="dc004_btn_save", use_container_width=True):
            try:
                new_id = create_dc004_calc(user_id, save_name, payload)
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    def _normalize_dc004_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
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
        items_raw = list_dc004_calcs(user_id)
        items = _normalize_dc004_list(items_raw)
        if not items:
            st.info("No DC004 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC004 saves", ["-- none --", *label_to_id.keys()], key="dc004_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc004_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC004')}** • "
                    f"Created: **{_fmt_dt(created_at)}** • "
                    f"Updated: **{_fmt_dt(updated_at)}**"
                )

                st.markdown("#### Summary (Prettified)")
                st.markdown("**Base (from Valve Data)**")
                st.table(
                    [
                        ["Valve design name", base_s.get("valve_design_name")],
                        ["Valve design ID",   base_s.get("valve_design_id")],
                        ["NPS [in]",          base_s.get("nps_in")],
                        ["ASME Class",        base_s.get("asme_class")],
                        ["Bore (base) [mm]",  base_s.get("bore_diameter_mm")],
                        ["Po (base) [MPa]",   base_s.get("operating_pressure_mpa")],
                    ]
                )

                st.markdown("**Inputs**")
                st.table(
                    [
                        ["SmF316 [MPa]", ins_s.get("SmF316_MPa")],
                        ["SaF316 [MPa]", ins_s.get("SaF316_MPa")],
                        ["Di [mm]",      ins_s.get("Di_mm")],
                        ["P [MPa]",      ins_s.get("P_MPa")],
                        ["PT [MPa]",     ins_s.get("PT_MPa")],
                        ["Real t [mm]",  ins_s.get("real_t_mm")],
                    ]
                )

                st.markdown("**Computed**")
                st.table(
                    [
                        ["t_design [mm]", comp_s.get("t_design_mm")],
                        ["t_test [mm]",   comp_s.get("t_test_mm")],
                        ["Required t [mm]", comp_s.get("required_t_mm")],
                        ["Check", comp_s.get("verdict")],
                    ]
                )

                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC004"), key=f"dc004_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc004_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc004_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc004_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc004_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc004_btn_load_{sel_id}", use_container_width=True):
                        # restore inputs to session
                        st.session_state["dc004_SmF316"] = ins_s.get("SmF316_MPa") or st.session_state.get("dc004_SmF316")
                        st.session_state["dc004_SaF316"] = ins_s.get("SaF316_MPa") or st.session_state.get("dc004_SaF316")
                        st.session_state["dc004_Di"] = ins_s.get("Di_mm") or st.session_state.get("dc004_Di")
                        st.session_state["dc004_P"]  = ins_s.get("P_MPa") or st.session_state.get("dc004_P")
                        st.session_state["dc004_PT"] = ins_s.get("PT_MPa") or st.session_state.get("dc004_PT")

                        # also refresh base
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"] = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"] = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"] = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
