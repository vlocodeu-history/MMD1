# page_dc007_body.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime

# --- ASME B16.34 Table lookup (minimal set; includes your case) ---
# Table 3A & Table VI-1 -> minimum body wall thickness t_m [mm]
B1634_TMIN = {
    (2, 600): 12.7,   # your sheet value
    # add more as needed, e.g. (2,150): x, (2,300): y, etc.
}

# ── Auth + wizard base
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── Backend repo (PostgreSQL) for DC007-1 Body
from dc007_body_repo import (
    create_dc007_body_calc, list_dc007_body_calcs, get_dc007_body_calc,
    update_dc007_body_calc, delete_dc007_body_calc
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
    c1, c2 = st.columns([1.25, 2.25])
    with c1:
        st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
    return c2

def _out_calc(key: str, value, fmt: str = "{}"):
    """
    Disabled text field that always shows the latest value.
    """
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _img_dc007(container, size_px: int = 300):
    for p in ["dc007_body.png", "assets/dc007_body.png", "static/dc007_body.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Fig. 2 ASME B16.34 (body section)", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Could not load DC007 body diagram ({e}).")
            return
    with container:
        st.info("Add **dc007_body.png** (or put it in ./assets/ or ./static/) to show the figure here.")

# ──────────────────────────────────────────────────────────────────────────────
# Wizard hydration helpers (same pattern used on other pages)
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
    # (1) Hydrate from wizard if locked
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

    # already enough info?
    if all(st.session_state.get(k) not in (None, "", 0) for k in ("valve_nps", "valve_asme_class")):
        return

    # (2) Fallback: latest valve design
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
def render_dc007_body():
    """
    DC007-1 — Body Wall Thickness Calc. per ASME B16.34 (Body)
    """
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>Body Wall Thickness Calc. in acc. With ASME B16.34</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC 007-1-(Body)</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Optional base banner if available
    if st.session_state.get("active_design_id"):
        po = st.session_state.get("operating_pressure_mpa")
        po_txt = f"{po:.2f}" if isinstance(po, (int, float)) else str(po or "—")
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{st.session_state.get("valve_nps","—")}** • '
            f'ASME **{st.session_state.get("valve_asme_class","—")}** • '
            f'Po **{po_txt} MPa**'
        )

    # Header (pull NPS & class if available)
    nps_default   = int(st.session_state.get("valve_nps", 2))   # 2 in
    class_default = int(st.session_state.get("valve_asme_class", 600))
    Pa_default    = float(st.session_state.get("operating_pressure_mpa", 10.21))

    i = _row("Class rating — NPS [in]")
    with i:
        nps = st.number_input("", value=nps_default, step=1, key="dc007_b_nps", label_visibility="collapsed")

    i = _row("ASME (Valve Class)")
    with i:
        asme_class = st.number_input("", value=class_default, step=50, key="dc007_b_class", label_visibility="collapsed")

    i = _row("Design pressure  Pa  [MPa]")
    with i:
        Pa = st.number_input("", value=Pa_default, step=0.01, format="%.2f", key="dc007_b_pa", label_visibility="collapsed")

    i = _row("Design temperature  T  [°C]")
    with i:
        T = st.text_input("", value="-29 / +150", key="dc007_b_temp", label_visibility="collapsed")

    i = _row("Corrosion allowance  C/A  [mm]")
    with i:
        CA = st.number_input("", value=3.0, step=0.1, format="%.1f", key="dc007_b_ca", label_visibility="collapsed")

    i = _row("Material")
    with i:
        material = st.text_input("", value="ASTM A350 LF2 CL.1", key="dc007_b_mat", label_visibility="collapsed")

    st.markdown("### BODY  (as per ASME B16.34 – Ed.2020)")

    # Dimensions (green inputs in sheet)
    i = _row("Body inside diameter  [mm]")
    with i:
        body_ID = st.number_input("", value=98.0, step=0.1, format="%.1f", key="dc007_b_bodyID", label_visibility="collapsed")

    i = _row("Diameter of the flow passage  [mm]")
    with i:
        flow_pass_d = st.number_input("", value=51.0, step=0.1, format="%.1f", key="dc007_b_flowpass", label_visibility="collapsed")

    i = _row("Inside diameter at the end flange  [mm]")
    with i:
        end_flange_ID = st.number_input("", value=51.0, step=0.1, format="%.1f", key="dc007_b_endflange", label_visibility="collapsed")

    # Inside diameter d (as on sheet)
    d = body_ID
    i = _row("inside diameter  d =")
    with i: _out_calc("dc007_b_d", f"{d:.1f} mm", "{}")

    # Actual thickness inputs (green)
    i = _row("actual thickness — body t  [mm]")
    with i:
        t_body = st.number_input("", value=43.5, step=0.1, format="%.1f", key="dc007_b_tbody", label_visibility="collapsed")

    i = _row("actual thickness on top mill — body!t  [mm]")
    with i:
        t_body_top = st.number_input("", value=34.0, step=0.1, format="%.1f", key="dc007_b_tbodytop", label_visibility="collapsed")

    # Table lookup for minimum wall thickness
    t_m = B1634_TMIN.get((int(nps), int(asme_class)))
    if t_m is None:
        st.warning("ASME B16.34 table value for this NPS/Class not in local map; using 12.7 mm as placeholder. Extend B1634_TMIN as required.")
        t_m = 12.7

    t_m_ca = t_m + CA

    i = _row("min wall thickness  tₘ  [mm]  (ASME B16.34 §6.1.1 · Table 3A / VI-1)")
    with i: _out_calc("dc007_b_tm", f"{t_m:.1f}", "{}")

    i = _row("min wall thickness + C/A  tₘ + C/A  [mm]")
    with i: _out_calc("dc007_b_tmca", f"{t_m_ca:.1f}", "{}")

    # Checks (same logic as before)
    ok1 = t_body >= t_m
    ok2 = t_body_top >= t_m
    ok_ca1 = t_body >= t_m_ca
    ok_ca2 = t_body_top >= t_m_ca

    # Show OK / NOT OK lines with badges
    i = _row("Check (body t ≥ tₘ)")
    with i:
        st.markdown(f"<span class='badge {'ok' if ok1 else 'bad'}'>{'OK' if ok1 else 'NOT OK'}</span>", unsafe_allow_html=True)

    i = _row("Check (body/t ≥ tₘ)")
    with i:
        st.markdown(f"<span class='badge {'ok' if ok2 else 'bad'}'>{'OK' if ok2 else 'NOT OK'}</span>", unsafe_allow_html=True)

    i = _row("Check incl. C/A (body t ≥ tₘ + C/A)")
    with i:
        st.markdown(f"<span class='badge {'ok' if ok_ca1 else 'bad'}'>{'OK' if ok_ca1 else 'NOT OK'}</span>", unsafe_allow_html=True)

    i = _row("Check incl. C/A (body/t ≥ tₘ + C/A)")
    with i:
        st.markdown(f"<span class='badge {'ok' if ok_ca2 else 'bad'}'>{'OK' if ok_ca2 else 'NOT OK'}</span>", unsafe_allow_html=True)

    # Figure row
    i = _row("Figure")
    _img_dc007(i, 300)

    # Persist to session (useful elsewhere)
    st.session_state["dc007_body"] = {
        "nps_in": int(nps),
        "asme_class": int(asme_class),
        "Pa_MPa": float(Pa),
        "T_C": str(T),
        "CA_mm": float(CA),
        "material": material,
        "body_ID_mm": float(body_ID),
        "flow_pass_d_mm": float(flow_pass_d),
        "end_flange_ID_mm": float(end_flange_ID),
        "t_body_mm": float(t_body),
        "t_body_top_mm": float(t_body_top),
        "t_m_mm": float(t_m),
        "t_m_plus_CA_mm": float(t_m_ca),
        "ok_body_vs_tm": ok1,
        "ok_top_vs_tm": ok2,
        "ok_body_vs_tmCA": ok_ca1,
        "ok_top_vs_tmCA": ok_ca2,
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC007-1 (Body)")

    if not user_id:
        st.info("Log in to save your DC007-1 calculations.")
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
        "Pa_MPa": float(Pa),
        "T_C": str(T),
        "CA_mm": float(CA),
        "material": material,
        "body_ID_mm": float(body_ID),
        "flow_pass_d_mm": float(flow_pass_d),
        "end_flange_ID_mm": float(end_flange_ID),
        "t_body_mm": float(t_body),
        "t_body_top_mm": float(t_body_top),
        "nps_in": int(nps),
        "asme_class": int(asme_class),
    }
    computed_payload: Dict[str, Any] = {
        "t_m_mm": float(t_m),
        "t_m_plus_CA_mm": float(t_m_ca),
        "ok_body_vs_tm": ok1,
        "ok_top_vs_tm": ok2,
        "ok_body_vs_tmCA": ok_ca1,
        "ok_top_vs_tmCA": ok_ca2,
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC007-Body_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc007_b_save_name")
        if st.button("💾 Save DC007-1 (Body)", type="primary", key="dc007_b_btn_save", use_container_width=True):
            try:
                new_id = create_dc007_body_calc(
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
        items_raw = list_dc007_body_calcs(user_id)
        items = _normalize_list(items_raw)
        if not items:
            st.info("No DC007-1 (Body) saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC007-1 (Body) saves", ["-- none --", *label_to_id.keys()], key="dc007_b_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc007_body_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC007-Body')}** • "
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
                    ["NPS [in]", ins_s.get("nps_in")],
                    ["ASME Class", ins_s.get("asme_class")],
                    ["Pa [MPa]", ins_s.get("Pa_MPa")],
                    ["T [°C]", ins_s.get("T_C")],
                    ["C/A [mm]", ins_s.get("CA_mm")],
                    ["Material", ins_s.get("material")],
                    ["Body ID [mm]", ins_s.get("body_ID_mm")],
                    ["Flow passage d [mm]", ins_s.get("flow_pass_d_mm")],
                    ["End flange ID [mm]", ins_s.get("end_flange_ID_mm")],
                    ["t_body [mm]", ins_s.get("t_body_mm")],
                    ["t_body_top [mm]", ins_s.get("t_body_top_mm")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed / Checks**")
                st.table(pd.DataFrame([
                    ["tₘ [mm]", comp_s.get("t_m_mm")],
                    ["tₘ + C/A [mm]", comp_s.get("t_m_plus_CA_mm")],
                    ["Check body t ≥ tₘ", "OK" if comp_s.get("ok_body_vs_tm") else "NOT OK"],
                    ["Check body/t ≥ tₘ", "OK" if comp_s.get("ok_top_vs_tm") else "NOT OK"],
                    ["Check body t ≥ tₘ + C/A", "OK" if comp_s.get("ok_body_vs_tmCA") else "NOT OK"],
                    ["Check body/t ≥ tₘ + C/A", "OK" if comp_s.get("ok_top_vs_tmCA") else "NOT OK"],
                ], columns=["Field", "Value"]))

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC007-Body"), key=f"dc007_b_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc007_b_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc007_body_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc007_b_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc007_body_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc007_b_btn_load_{sel_id}", use_container_width=True):
                        # Inputs back to session
                        st.session_state["dc007_b_nps"]       = ins_s.get("nps_in",       st.session_state.get("dc007_b_nps"))
                        st.session_state["dc007_b_class"]     = ins_s.get("asme_class",   st.session_state.get("dc007_b_class"))
                        st.session_state["dc007_b_pa"]        = ins_s.get("Pa_MPa",       st.session_state.get("dc007_b_pa"))
                        st.session_state["dc007_b_temp"]      = ins_s.get("T_C",          st.session_state.get("dc007_b_temp"))
                        st.session_state["dc007_b_ca"]        = ins_s.get("CA_mm",        st.session_state.get("dc007_b_ca"))
                        st.session_state["dc007_b_mat"]       = ins_s.get("material",     st.session_state.get("dc007_b_mat"))
                        st.session_state["dc007_b_bodyID"]    = ins_s.get("body_ID_mm",   st.session_state.get("dc007_b_bodyID"))
                        st.session_state["dc007_b_flowpass"]  = ins_s.get("flow_pass_d_mm", st.session_state.get("dc007_b_flowpass"))
                        st.session_state["dc007_b_endflange"] = ins_s.get("end_flange_ID_mm", st.session_state.get("dc007_b_endflange"))
                        st.session_state["dc007_b_tbody"]     = ins_s.get("t_body_mm",    st.session_state.get("dc007_b_tbody"))
                        st.session_state["dc007_b_tbodytop"]  = ins_s.get("t_body_top_mm", st.session_state.get("dc007_b_tbodytop"))

                        # base (optional)
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
