# page_dc002.py
from __future__ import annotations
import math
import os
from typing import Optional, Any, Dict, List, Tuple
from PIL import Image
import streamlit as st
from datetime import datetime

# ---- auth + repos ----
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from dc002_repo import (
    create_dc002_calc, list_dc002_calcs, get_dc002_calc,
    update_dc002_calc, delete_dc002_calc
)
# ---- wizard lock (READ-ONLY hydration) ----
from wizard_base import get_base, is_locked

# Tensile stress areas for common bolts (UNC + a few metric) in mm²
BOLT_TENSILE_AREAS_MM2 = {
    'M5 x 0,5': 16.1, 'M6 x 1': 20.1, 'M6 x 0,75': 22, 'M8 x 1,25': 36.6, 'M8 x 1': 39.2,
    'M10 x 1,5': 58, 'M10 x 1,25': 61.2, 'M12 x 1,75': 84.3, 'M12 x 1,25': 92.1, 'M14 x 2': 115,
    'M14 x 1,5': 125, 'M16 x 2': 157, 'M16 x 1,5': 167, 'M18 x 2,5': 192, 'M18 x 1,5': 216,
    'M20 x 2,5': 245, 'M20 x 1,5': 272, 'M22 x 2,5': 303, 'M22 x 1,5': 333, 'M24 x 3': 353,
    'M24 x 2': 384, 'M27 x 3': 459, 'M27 x 2': 496, 'M30 x 3,5': 561, 'M30 x 2': 621,
    'M33 x 3,5': 694, 'M33 x 2': 761, 'M36 x 4': 817, 'M36 x 3': 865, 'M39 x 4': 976, 'M39 x 3': 1030,
    'M42 x 4,5': 1120, 'M42 x 3': 1210, 'M45 x 4,5': 1310, 'M45 x 3': 1400, 'M48 x 5': 1470,
    'M48 x 3': 1600, 'M52 x 5': 1760, 'M52 x 3': 1900, 'M56 x 5,5': 2030, 'M56 x 4': 2140,
    'M60 x 5,5': 2360, 'M60 x 4': 2480, 'M64 x 6': 2680, 'M64 x 4': 2850, 'M68 x 6': 3060,
    'M68 x 4': 3240, 'M72 x 6': 3460, 'M72 x 4': 3660, 'M76 x 6': 3890, 'M76x4': 4100,
    'M80 x 6': 4340, 'M80 x 4': 4570, 'M85 x 4': 5180, 'M95 x 4': 6540, 'M100 x 4': 7280,
    'M105 x 4': 8050, 'M110 x 4': 8870, 'M115 x 4': 9720, 'M120 x 4': 10600, 'M125 x 4': 11500,
    'M130 x 4': 12550, 'M135 x 4': 13529, 'M140 x 4': 14580, 'M145 x 4': 15669, 'M150 x 4': 16500,
    '1/4" UNC': 20.5, '5/16" UNC': 33.8, '3/8" UNC': 49.9, '7/16" UNC': 68.6, '1/2" UNC': 91.5,
    '9/16" UNC': 117.4, '5/8" UNC': 145.8, '3/4" UNC': 215.5, '7/8" UNC': 298, '1" UNC': 391,
    '1-1/8" UN': 509.7, '1-1/4" UN': 645.2, '1-3/8" UN': 795.5, '1-1/2" UN': 962.6, '1-5/8" UN': 1148.4,
    '1-3/4" UN': 1342, '1-7/8" UN': 1555, '2" UN': 1787, '2-1/4" UN': 2297, '2-1/2" UN': 2864.5,
    '2-3/4 UN': 3503, '3" UN': 4200, '3-1/4" UN': 4961, '3-1/2" UN': 5780, '3-3/4" UN': 6671,
    '4" UN': 7619, '4-1/2" UN': 9742, '5" UN': 12064, '5-1/2" UN': 14645, '6" UN': 17484
}

# Allowable bolt stress presets, MPa (N/mm²)
ALLOWABLE_S_BY_MATERIAL = {
    "A193 B7": 172.4,   "A193 B7 DIV.2": 241.2, "A193 B7M": 138, "A193 B7M DIV.2": 182.0,
    "A320 L7": 172.4,   "A320 L7M": 137.9,     "A193 B16": 172.4,
    "A320 B8 d<=18": 172.4, "A320 B8 20<d<=24": 137.9, "A320 B8 26<d<=30": 111.7, "A320 B8 d>=32": 86.2,
    "A320 B8M d<=18": 151.7, "A320 B8M 20<d<=24": 137.9, "A320 B8M 26<d<=30": 111.7, "A320 B8M d>=32": 86.2,
    "A453 Gr.660 A": 179.0,
}

# ---------- helpers (layout preserved) ----------
def _css():
    st.markdown("""
    <style>
      .row-wrap { display:flex; align-items:center; gap:12px; margin:2px 0; }
      .row-label {
        flex:0 0 360px; text-align:right; height:40px;
        display:flex; align-items:center; justify-content:flex-end;
        font-weight:600; color:#0f172a; white-space:nowrap; padding:0 .5rem;
      }
      .row-input { flex:1 1 auto; display:flex; align-items:center; }
      .stTextInput > div > div > input,
      .stNumberInput > div > div > input { height:40px !important; padding:0 .7rem !important; }
      .stSelectbox > div > div { min-height:40px !important; }
      .row-input > div { margin:0 !important; }
    </style>
    """, unsafe_allow_html=True)

def _row(label: str):
    c1, c2 = st.columns([1.25, 2.25])
    with c1:
        st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
    return c2

def _out(value, fmt=None, key=None):
    s = fmt.format(value) if fmt else ("" if value is None else str(value))
    st.text_input(label="", value=s, key=key, disabled=True, label_visibility="collapsed")

def _selectbox_with_state(key: str, options, default_index=0):
    if key in st.session_state:
        return st.selectbox("", options, key=key, label_visibility="collapsed")
    else:
        return st.selectbox("", options, index=default_index, key=key, label_visibility="collapsed")

def _show_flange_image(size_px: int = 300):
    for p in ["dc002_flange.png", "assets/dc002_flange.png", "static/dc002_flange.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                st.image(img, caption="Body-Closure with bolting", use_column_width=False)
            except Exception as e:
                st.warning(f"Could not load flange image ({e}).")
            return
    st.info("Add **dc002_flange.png** (or put it in ./assets/ or ./static/) to show the picture here.")

# ---------- pretty formatting helpers ----------
def _fmt_num(x: Any, digits: int = 2) -> str:
    if x is None: return "—"
    try:
        f = float(x)
        if abs(f - round(f)) < 1e-9:
            return f"{int(round(f))}"
        return f"{f:.{digits}f}"
    except Exception:
        return str(x)

def _fmt_dt(x: Any) -> str:
    # Handles datetime, ISO strings, or anything else → neat "YYYY-MM-DD HH:MM"
    if not x: return "—"
    if isinstance(x, datetime):
        return x.strftime("%Y-%m-%d %H:%M")
    if isinstance(x, str):
        # Try a few common formats
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(x[:26], fmt[:len(x[:26])]) if "%f" in fmt else datetime.strptime(x[:19], fmt[:len(x[:19])])
                return dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                continue
        # fallback: trim
        return x[:16]
    return str(x)

def _kv_table(pairs: List[Tuple[str, Any]]):
    import pandas as pd
    rows = [{"Field": k, "Value": _fmt_num(v) if isinstance(v, (int, float)) else (v if v is not None else "—")} for k, v in pairs]
    st.table(pd.DataFrame(rows))

# ---- robust helpers for repo shapes ----
def _normalize_first_pair(rows: List[Any]) -> Tuple[Optional[str], Optional[str]]:
    if not rows:
        return None, None
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

def _normalize_dc002_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
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
            nm = r.get("name") or nm
            ca = r.get("created_at")
            ua = r.get("updated_at")
        elif isinstance(r, str):
            rid = r
        if rid:
            out.append((str(rid), str(nm), ca, ua))
    return out

# ---- base seeding from Valve (wizard-aware + robust) ----
def _seed_base_from_valve(user_id: Optional[str]):
    # 1) Wizard lock hydration
    if is_locked():
        wb = get_base() or {}
        st.session_state.setdefault("nps_in", wb.get("nps_in"))
        st.session_state.setdefault("asme_class", wb.get("asme_class"))
        st.session_state.setdefault("valve_nps", wb.get("nps_in"))
        st.session_state.setdefault("valve_asme_class", wb.get("asme_class"))
        if wb.get("design_id"):
            st.session_state.setdefault("active_design_id", wb.get("design_id"))
        if wb.get("name"):
            st.session_state.setdefault("active_design_name", wb.get("name"))

    # Already have enough?
    have_essential = all(
        st.session_state.get(k) not in (None, "", 0)
        for k in ("valve_nps", "valve_asme_class")
    )
    if have_essential:
        return

    # 2) Latest valve design fallback
    if not user_id:
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
        pass  # quiet fallback

def render_dc002():
    # ---- auth + base seed ----
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>Body-Closure Bolts calculation</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC002</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # (Optional) small base banner
    if st.session_state.get("active_design_id"):
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{st.session_state.get("valve_nps","—")}** • '
            f'ASME **{st.session_state.get("valve_asme_class","—")}** • '
            f'Po **{_fmt_num(st.session_state.get("operating_pressure_mpa"), 2)} MPa**'
        )

    # Header (unchanged)
    i = _row("NPS")
    with i: _out(st.session_state.get("valve_nps", ""), key="dc002_hdr_nps")
    i = _row("ASME")
    with i: _out(st.session_state.get("valve_asme_class", ""), key="dc002_hdr_asme")

    st.markdown("### INPUT DATA")

    Pa_default = float(st.session_state.get("operating_pressure_mpa", 10.21))  # MPa (N/mm²)

    i = _row("Gasket tight diameter  G  [mm] =")
    G = i.number_input("", value=122.7, step=0.1, format="%.1f",
                       key="dc002_G", label_visibility="collapsed")

    i = _row("Design pressure  Pa  [MPa] =")
    Pa = i.number_input("", value=Pa_default, step=0.01, format="%.2f",
                        key="dc002_Pa", label_visibility="collapsed")

    i = _row("Pressure rating – Class designation  Pe  [MPa] =")
    Pe = i.number_input("", value=0.0, step=0.01, format="%.2f",
                        key="dc002_Pe", label_visibility="collapsed")

    # Bolt material (drives S)
    i = _row("Bolt material =")
    with i:
        bolt_mat = _selectbox_with_state("dc002_mat", list(ALLOWABLE_S_BY_MATERIAL.keys()), default_index=0)

    # S (derived) — dynamic key so it refreshes visually when material changes
    S = float(ALLOWABLE_S_BY_MATERIAL[bolt_mat])
    i = _row("Allowable bolt stress  S  [MPa] (ASME VIII Div.1 App.2)")
    with i: _out(S, "{:.1f}", key=f"dc002_out_S_{S:.1f}")   # dynamic key

    # Optional figure
    _show_flange_image(size_px=300)

    st.markdown("---")
    st.markdown("### DESIGN LOAD")

    H = 0.785 * (G ** 2) * Pa
    Wm1 = H
    i = _row("Total hydrostatic end force  H  [N] = 0.785 × G² × Pa")
    with i: _out(H, "{:,.2f}", key=f"dc002_out_H_{H:.2f}")
    i = _row("Minimum required bolt load for operating condition  Wm1  [N]")
    with i: _out(Wm1, "{:,.2f}", key=f"dc002_out_Wm1_{Wm1:.2f}")

    st.markdown("---")
    st.markdown("### BOLTS SECTION CALCULATION")

    Am = Wm1 / (S if S else 1e-9)  # mm²
    i = _row("Limit stress used for bolts :  S = Sa for ASME VIII Div.1")
    with i: _out(S, "{:.1f}", key=f"dc002_out_S_repeat_{S:.1f}")
    i = _row("Total required cross-sectional area of bolts  Am  [mm²] = Wm1 / S")
    with i: _out(Am, "{:,.2f}", key=f"dc002_out_Am_{Am:.2f}")

    st.markdown("---")
    st.markdown("### BOLTS DESIGN")

    i = _row("Bolts number  n  =")
    n = i.number_input("", value=6, min_value=1, step=1, format="%d",
                       key="dc002_n", label_visibility="collapsed")

    a_req_each = Am / n
    i = _row("Required cross-sectional area of each bolt  a'  [mm²] = Am / n")
    with i: _out(a_req_each, "{:,.2f}", key=f"dc002_out_areq_{a_req_each:.2f}")

    # Bolt size (drives 'a')
    bolt_options = list(BOLT_TENSILE_AREAS_MM2.keys())
    i = _row("Selected bolt size")
    with i:
        bolt_size = _selectbox_with_state("dc002_bolt_sel", bolt_options, default_index=0)

    # a (derived) — dynamic key so it refreshes when size changes
    a = float(BOLT_TENSILE_AREAS_MM2[bolt_size])
    i = _row("Actual tensile-stress area  a  [mm²] (from size)")
    with i: _out(a, "{:.1f}", key=f"dc002_out_a_{a:.1f}")

    st.markdown("---")
    st.markdown("### ACTUAL TENSILE STRESS CALCULATION")

    Ab = a * n
    Sa_eff = Wm1 / (Ab if Ab else 1e-9)

    i = _row("Total bolt tensile stress area  Ab  [mm²] = a × n")
    with i: _out(Ab, "{:,.1f}", key=f"dc002_out_Ab_{Ab:.1f}")
    i = _row("Actual bolt tensile stress  Sa_eff  [MPa] = Wm1 / Ab")
    with i: _out(Sa_eff, "{:,.2f}", key=f"dc002_out_Saeff_{Sa_eff:.2f}")

    verdict = "VERIFIED" if Sa_eff <= S else "NOT VERIFIED"
    i = _row("Check  (Sa_eff ≤ S)")
    with i:
        color = "#22c55e" if verdict == "VERIFIED" else "#ef4444"
        st.markdown(
            f"<div style='padding:.35rem .9rem;border-radius:.45rem;"
            f"background:{color};color:#fff;font-weight:700;display:inline-block;'>{verdict}</div>",
            unsafe_allow_html=True,
        )

    # Save (unchanged)
    st.session_state["dc002"] = {
        "G_mm": G, "Pa_MPa": Pa, "Pe_MPa": Pe, "bolt_material": bolt_mat, "S_MPa": S,
        "H_N": H, "Wm1_N": Wm1, "Am_mm2": Am, "n": n, "a_req_each_mm2": a_req_each,
        "bolt_size": bolt_size, "a_mm2": a, "Ab_mm2": Ab, "Sa_eff_MPa": Sa_eff, "verdict": verdict
    }

    # ───────────────── Save / Load (backend) ─────────────────
    if not user_id:
        st.info("Log in to save your DC002 calculations.")
        return

    base_payload = {
        "valve_design_id":   st.session_state.get("active_design_id"),
        "valve_design_name": st.session_state.get("active_design_name"),
        "nps_in":            st.session_state.get("valve_nps"),
        "asme_class":        st.session_state.get("valve_asme_class"),
        "bore_diameter_mm":  st.session_state.get("bore_diameter_mm"),
        "operating_pressure_mpa": st.session_state.get("operating_pressure_mpa"),
    }
    inputs_payload = {
        "G_mm": G, "Pa_MPa": Pa, "Pe_MPa": Pe,
        "bolt_material": bolt_mat, "n": n, "bolt_size": bolt_size
    }
    computed_payload = {
        "S_MPa": S, "H_N": H, "Wm1_N": Wm1, "Am_mm2": Am,
        "a_req_each_mm2": a_req_each, "a_mm2": a, "Ab_mm2": Ab,
        "Sa_eff_MPa": Sa_eff, "verdict": verdict
    }
    payload = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    st.markdown("---")
    st.markdown("### Save / Load DC002")

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC002_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc002_save_name")
        if st.button("💾 Save DC002", type="primary", key="dc002_btn_save", use_container_width=True):
            try:
                new_id = create_dc002_calc(user_id, save_name, payload)
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    with colR:
        raw_items = list_dc002_calcs(user_id)  # flexible shapes
        items = _normalize_dc002_list(raw_items)
        if not items:
            st.info("No DC002 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC002 saves", ["-- none --", *label_to_id.keys()], key="dc002_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc002_calc(sel_id, user_id) or {}

                # Meta + sections
                meta = {
                    "id": rec.get("id") or sel_id,
                    "name": rec.get("name"),
                    "created_at": rec.get("created_at"),
                    "updated_at": rec.get("updated_at"),
                }
                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                # Header meta with neat timestamps
                st.caption(
                    f"Name: **{(meta.get('name') or 'DC002')}** • "
                    f"Created: **{_fmt_dt(meta.get('created_at'))}** • "
                    f"Updated: **{_fmt_dt(meta.get('updated_at'))}**"
                )

                # --------- Summary (Prettified) ----------
                st.markdown("#### Summary (Prettified)")
                st.markdown("**Base (from Valve Data)**")
                _kv_table([
                    ("Valve design name", base_s.get("valve_design_name")),
                    ("Valve design ID",   base_s.get("valve_design_id")),
                    ("NPS [in]",          base_s.get("nps_in")),
                    ("ASME Class",        base_s.get("asme_class")),
                    ("Bore (base) [mm]",  base_s.get("bore_diameter_mm")),
                    ("Po (base) [MPa]",   base_s.get("operating_pressure_mpa")),
                ])

                st.markdown("**Inputs**")
                _kv_table([
                    ("G [mm]",               ins_s.get("G_mm")),
                    ("Pa [MPa]",             ins_s.get("Pa_MPa")),
                    ("Pe [MPa]",             ins_s.get("Pe_MPa")),
                    ("Bolt material",        ins_s.get("bolt_material")),
                    ("Bolts number n",       ins_s.get("n")),
                    ("Bolt size",            ins_s.get("bolt_size")),
                ])

                st.markdown("**Computed**")
                _kv_table([
                    ("S [MPa]",               comp_s.get("S_MPa")),
                    ("H [N]",                 comp_s.get("H_N")),
                    ("Wm1 [N]",               comp_s.get("Wm1_N")),
                    ("Am [mm²]",              comp_s.get("Am_mm2")),
                    ("a' each req. [mm²]",    comp_s.get("a_req_each_mm2")),
                    ("a actual [mm²]",        comp_s.get("a_mm2")),
                    ("Ab [mm²]",              comp_s.get("Ab_mm2")),
                    ("Sa_eff [MPa]",          comp_s.get("Sa_eff_MPa")),
                    ("Check",                 comp_s.get("verdict")),
                ])

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(meta.get("name") or "DC002"), key=f"dc002_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc002_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc002_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc002_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc002_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc002_btn_load_{sel_id}", use_container_width=True):
                        # seed session so reopening shows the same values
                        st.session_state["dc002_G"] = (ins_s.get("G_mm") or st.session_state.get("dc002_G"))
                        st.session_state["dc002_Pa"] = (ins_s.get("Pa_MPa") or st.session_state.get("dc002_Pa"))
                        st.session_state["dc002_Pe"] = (ins_s.get("Pe_MPa") or st.session_state.get("dc002_Pe"))
                        st.session_state["dc002_mat"] = (ins_s.get("bolt_material") or st.session_state.get("dc002_mat"))
                        st.session_state["dc002_n"] = (ins_s.get("n") or st.session_state.get("dc002_n"))
                        st.session_state["dc002_bolt_sel"] = (ins_s.get("bolt_size") or st.session_state.get("dc002_bolt_sel"))

                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"] = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"] = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"] = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
