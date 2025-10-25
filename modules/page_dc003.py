# modules/page_dc003.py
from __future__ import annotations
import math, os
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
# Auth + wizard base (same pattern as DC002A)
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# Backend repo for DC003 saves  (PostgreSQL via your dc003_repo.py)
from dc003_repo import (
    create_dc003_calc, list_dc003_calcs, get_dc003_calc,
    update_dc003_calc, delete_dc003_calc
)

# ──────────────────────────────────────────────────────────────────────────────
# Reference table (as in your sheet image)
# Columns: BASE METAL BEARING MATERIAL | MAXIMUM STATIC LOAD (MPa) | MAXIMUM DYNAMIC LOAD (MPa) | MAXIMUM TEMPERATURE (°C)
BEARING_TABLE = [
    {"BASE METAL BEARING  MATERIAL": "SS316 + FRICTION COATED",       "MAXIMUM STATIC LOAD (MPa)": 420, "MAXIMUM DYNAMIC LOAD (MPa)": 140, "MAXIMUM TEMPERATURE (°C)": 150},
    {"BASE METAL BEARING  MATERIAL": "INCONEL 625 + FRICTION COATED", "MAXIMUM STATIC LOAD (MPa)": 240, "MAXIMUM DYNAMIC LOAD (MPa)": 140, "MAXIMUM TEMPERATURE (°C)": 150},
    {"BASE METAL BEARING  MATERIAL": "MILD STEEL + FRICTION COATED",  "MAXIMUM STATIC LOAD (MPa)": 210, "MAXIMUM DYNAMIC LOAD (MPa)": 140, "MAXIMUM TEMPERATURE (°C)": 150},
    {"BASE METAL BEARING  MATERIAL": "INCONEL 625 HT",                "MAXIMUM STATIC LOAD (MPa)": 280, "MAXIMUM DYNAMIC LOAD (MPa)": 140, "MAXIMUM TEMPERATURE (°C)": 300},
    {"BASE METAL BEARING  MATERIAL": "SS316 HT",                      "MAXIMUM STATIC LOAD (MPa)": 240, "MAXIMUM DYNAMIC LOAD (MPa)": 140, "MAXIMUM TEMPERATURE (°C)": 300},
]

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
    Render a disabled text field that ALWAYS reflects the latest computed value.
    We write the formatted value into session_state before drawing the widget.
    """
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s  # force widget to the latest value
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _show_dc003_image(container, size_px: int = 300):
    # Show sketch in the RIGHT column to preserve layout
    for p in ["dc003_bearing.png", "assets/dc003_bearing.png", "static/dc003_bearing.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Bearing sketch", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Couldn't load bearing diagram ({e}).")
            return
    with container:
        st.info("Add **dc003_bearing.png** (or put it in ./assets/ or ./static/) to show the diagram here.")

# ──────────────────────────────────────────────────────────────────────────────
# Wizard hydration helpers (no layout change)
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
    # 1) Wizard lock hydration (pull from wizard_base)
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

    # Already have enough?
    have_essential = all(
        st.session_state.get(k) not in (None, "", 0)
        for k in ("valve_nps", "valve_asme_class")
    )
    if have_essential:
        return

    # 2) Fallback to latest valve design
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
        pass  # quiet

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
def render_dc003():
    """
    DC003 — Bearing Stress Calculation

    Sheet formulas (mapped to cells for clarity):
      Sb  [mm²] = π × Db × Hb                →  PI() * H34 * J34
      BBS [MPa] = (π × P × Dt²) / (8 × Sb)   →  (PI() * D34 * F34^2) / (8 * L34)
    """
    # ── Access guard + base hydration (NO layout or math changes)
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")
    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>Bearing Stress Calculation</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC003</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Base banner (if Valve base present in session)
    if st.session_state.get("active_design_id"):
        po = st.session_state.get("operating_pressure_mpa")
        po_txt = f"{po:.2f}" if isinstance(po, (int, float)) else str(po or "—")
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{st.session_state.get("valve_nps","—")}** • '
            f'ASME **{st.session_state.get("valve_asme_class","—")}** • '
            f'Po **{po_txt} MPa**'
        )

    # Read-only headers (use _out_calc so they also update if base changes)
    i = _row("Nominal Diameter  NPS [in]")
    with i:
        _out_calc("dc003_hdr_nps", st.session_state.get("valve_nps", ""), "{}")
    i = _row("Ansi Class  CLASS")
    with i:
        _out_calc("dc003_hdr_asme", st.session_state.get("valve_asme_class", ""), "{}")

    st.markdown("### INPUT DATA")

    # Defaults from session
    P_default  = float(st.session_state.get("operating_pressure_mpa", 10.21))  # D34
    Dt_default = None
    dca = st.session_state.get("dc001a")
    if isinstance(dca, dict):
        Dt_default = dca.get("Dts_mm")  # prefer DC001A seat seal diameter
    if Dt_default is None:
        Dt_default = 71.0  # F34

    # Inputs (right side)  ———  (NO layout changes)
    i = _row("Max rating pressure  P  [MPa]")          # D34
    with i:
        P = st.number_input("", value=P_default, step=0.01, format="%.2f",
                            key="dc003_P", label_visibility="collapsed")

    i = _row("Seat seal diameter  Dt  [mm]")           # F34
    with i:
        Dt = st.number_input("", value=float(Dt_default), step=0.1, format="%.1f",
                             key="dc003_Dt", label_visibility="collapsed")

    i = _row("Bearing diameter  Db  [mm]")             # H34
    with i:
        Db = st.number_input("", value=40.0, step=0.1, format="%.1f",
                             key="dc003_Db", label_visibility="collapsed")

    i = _row("Bearing length  Hb  [mm]")               # J34
    with i:
        Hb = st.number_input("", value=7.0, step=0.1, format="%.1f",
                             key="dc003_Hb", label_visibility="collapsed")

    # Material reference table (visual only); user will enter MABS manually
    st.markdown("### MATERIALS")
    i = _row("Material Reference Table")
    with i:
        st.table(pd.DataFrame(BEARING_TABLE))

    i = _row("Maximum allowable bearing stress  MABS  [MPa]")  # user enters after seeing table
    with i:
        MABS = st.number_input("", value=140.0, step=1.0, format="%.0f",
                               key="dc003_MABS", label_visibility="collapsed")

    # Sketch (also right column)
    i = _row("Sketch")
    _show_dc003_image(i, size_px=300)

    st.markdown("---")
    st.markdown("### CALCULATIONS")

    # ── Exact sheet formulas (UNCHANGED)
    Sb  = math.pi * Db * Hb
    BBS = (math.pi * P * (Dt ** 2)) / (8.0 * max(Sb, 1e-9))

    i = _row("Design bearing surface  Sb  [mm²] = π × Db × Hb")
    with i:
        _out_calc("dc003_out_Sb", Sb, "{:.4f}")  # L34

    i = _row("Bearing stress (1)  BBS  [MPa] = (π × P × Dt²) / (8 × Sb)")
    with i:
        _out_calc("dc003_out_BBS", BBS, "{:.2f}")  # sheet formula

    i = _row("Maximum allowable bearing stress  MABS  [MPa]")
    with i:
        _out_calc("dc003_out_MABS", MABS, "{:.0f}")

    verdict = "VERIFIED" if BBS <= MABS else "NOT VERIFIED"
    i = _row("Check  (BBS ≤ MABS)")
    with i:
        st.markdown(
            f"<span class='badge {'ok' if verdict=='VERIFIED' else 'bad'}'>{verdict}</span>",
            unsafe_allow_html=True
        )

    # Persist to session (for later steps/pages)
    st.session_state["dc003"] = {
        "P_MPa": P, "Dt_mm": Dt, "Db_mm": Db, "Hb_mm": Hb,
        "Sb_mm2": Sb, "BBS_MPa": BBS, "MABS_MPa": MABS,
        "verdict": verdict
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC003")

    if not user_id:
        st.info("Log in to save your DC003 calculations.")
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
        "P_MPa": P, "Dt_mm": Dt, "Db_mm": Db, "Hb_mm": Hb, "MABS_MPa": MABS
    }
    computed_payload: Dict[str, Any] = {
        "Sb_mm2": Sb, "BBS_MPa": BBS, "verdict": verdict
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC003_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc003_save_name")
        if st.button("💾 Save DC003", type="primary", key="dc003_btn_save", use_container_width=True):
            try:
                new_id = create_dc003_calc(user_id, save_name, payload)
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    def _normalize_dc003_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
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
        items_raw = list_dc003_calcs(user_id)
        items = _normalize_dc003_list(items_raw)

        # Optional: small table to visualize PG-backed history
        if items:
            hist_df = pd.DataFrame(
                [{"ID": _id, "Name": nm, "Created": _fmt_dt(ca), "Updated": _fmt_dt(ua)} for (_id, nm, ca, ua) in items]
            )
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

        if not items:
            st.info("No DC003 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC003 saves", ["-- none --", *label_to_id.keys()], key="dc003_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc003_calc(sel_id, user_id) or {}

                # pull sections
                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                # neat meta (some backends return only data; timestamps come from the list)
                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC003')}** • "
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
                    ["P [MPa]", ins_s.get("P_MPa")],
                    ["Dt [mm]", ins_s.get("Dt_mm")],
                    ["Db [mm]", ins_s.get("Db_mm")],
                    ["Hb [mm]", ins_s.get("Hb_mm")],
                    ["MABS [MPa]", ins_s.get("MABS_MPa")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed**")
                st.table(pd.DataFrame([
                    ["Sb [mm²]", comp_s.get("Sb_mm2")],
                    ["BBS [MPa]", comp_s.get("BBS_MPa")],
                    ["Check", comp_s.get("verdict")],
                ], columns=["Field", "Value"]))

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC003"), key=f"dc003_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc003_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc003_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc003_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc003_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc003_btn_load_{sel_id}", use_container_width=True):
                        # seed session so reopening shows the same values
                        st.session_state["dc003_P"]  = ins_s.get("P_MPa")  or st.session_state.get("dc003_P")
                        st.session_state["dc003_Dt"] = ins_s.get("Dt_mm")  or st.session_state.get("dc003_Dt")
                        st.session_state["dc003_Db"] = ins_s.get("Db_mm")  or st.session_state.get("dc003_Db")
                        st.session_state["dc003_Hb"] = ins_s.get("Hb_mm")  or st.session_state.get("dc003_Hb")
                        st.session_state["dc003_MABS"] = ins_s.get("MABS_MPa") or st.session_state.get("dc003_MABS")

                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"] = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"] = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"] = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
