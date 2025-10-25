# page_dc007_body_holes.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Auth + wizard base (same pattern as other DC pages)
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── Backend repo (PostgreSQL) for DC007-2 Body holes
from dc007_body_holes_repo import (
    create_dc007_body_holes_calc, list_dc007_body_holes_calcs, get_dc007_body_holes_calc,
    update_dc007_body_holes_calc, delete_dc007_body_holes_calc
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
    Disabled text field that always shows the latest computed value.
    """
    s = fmt.format(value) if value is not None else ""
    st.session_state[key] = s  # keep widget synced to current value
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _img_dc007_2(container, size_px: int = 360):
    for p in ["dc007_body_holes.png", "assets/dc007_body_holes.png", "static/dc007_body_holes.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Fig. 2 ASME B16.34 – hole locations/notations", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Could not load DC007-2 diagram ({e}).")
            return
    with container:
        st.info("Add **dc007_body_holes.png** (or put it in ./assets/ or ./static/) to show the figure here.")

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
def render_dc007_body_holes():
    """
    DC007 Sheet 2 of 2 (Body) — Holes requirements (ASME B16.34 §6.1.1, Table 3A & Table VI-1)

    Uses t_m from DC007-1 (preferred: t_m + C/A shown as 15.7 mm in your sheet).
    If not present, falls back to 15.7 mm.
    Checks:
      f'    >= 0.25 * t_m
      f'+g' >= 1.00 * t_m
      e°    >= 0.25 * t_m
    """
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>Body Wall Thickness Calc. in acc. With ASME B16.34</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC 007 Sheet 2 of 2 (Holes requirements)</h4>", unsafe_allow_html=True)
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

    # Header (carry over) — left label / right value
    i = _row("Class rating — ASME")
    with i: _out_calc("dc007_h_hdr_asme", st.session_state.get("valve_asme_class", 600), "{}")

    i = _row("Design pressure  Pa  [MPa]")
    with i: _out_calc("dc007_h_hdr_pa", st.session_state.get("operating_pressure_mpa", 10.21), "{}")

    i = _row("Design temperature  T  [°C]")
    with i: _out_calc("dc007_h_hdr_temp", "-29 / +150", "{}")

    i = _row("Corrosion allowance  C/A  [mm]")
    with i: _out_calc("dc007_h_hdr_ca", "3", "{}")

    st.markdown("### DRILLED AND TAPPED HOLES")

    # Pull t_m from DC007-1 if available (prefer the +C/A number used on your sheet: 15.7 mm)
    tm_from_body = None
    if isinstance(st.session_state.get("dc007_body"), dict):
        tm_from_body = st.session_state["dc007_body"].get("t_m_plus_CA_mm") or st.session_state["dc007_body"].get("t_m_mm")

    t_m = float(tm_from_body) if tm_from_body is not None else 15.7  # your sheet shows 15.7 mm

    # Reference t_m
    i = _row("Minimum wall thickness  tₘ  [mm]")
    with i:
        _out_calc("dc007_h_tm", f"{t_m:.1f} mm", "{}")

    # Inputs (green cells)
    i = _row("Minimum thickness  f'  [mm]")
    with i:
        f_min = st.number_input("", value=14.1, step=0.1, format="%.1f",
                                key="dc007_h_fmin", label_visibility="collapsed")

    i = _row("Minimum thickness  f' + g'  [mm]")
    with i:
        fg_min = st.number_input("", value=27.8, step=0.1, format="%.1f",
                                 key="dc007_h_fgmin", label_visibility="collapsed")

    i = _row("Minimum thickness  e°  [mm]")
    with i:
        e_min = st.number_input("", value=20.7, step=0.1, format="%.1f",
                                key="dc007_h_emin", label_visibility="collapsed")

    # Required limits from §6.1.1
    req_f  = 0.25 * t_m
    req_fg = 1.00 * t_m
    req_e  = 0.25 * t_m

    # Results / checks (each as a row: limit value + badge)
    i = _row("Requirement  f'  ≥ 0.25 · tₘ  → limit [mm]")
    ok_f = f_min >= req_f
    with i:
        _out_calc("dc007_h_req_f", req_f, "{:.2f}")
        st.markdown(
            f"<span class='badge {'ok' if ok_f else 'bad'}' style='margin-left:.5rem;'>{'OK' if ok_f else 'NOT OK'}</span>",
            unsafe_allow_html=True
        )

    i = _row("Requirement  f' + g'  ≥  tₘ  → limit [mm]")
    ok_fg = fg_min >= req_fg
    with i:
        _out_calc("dc007_h_req_fg", req_fg, "{:.2f}")
        st.markdown(
            f"<span class='badge {'ok' if ok_fg else 'bad'}' style='margin-left:.5rem;'>{'OK' if ok_fg else 'NOT OK'}</span>",
            unsafe_allow_html=True
        )

    i = _row("Requirement  e°  ≥  0.25 · tₘ  → limit [mm]")
    ok_e = e_min >= req_e
    with i:
        _out_calc("dc007_h_req_e", req_e, "{:.2f}")
        st.markdown(
            f"<span class='badge {'ok' if ok_e else 'bad'}' style='margin-left:.5rem;'>{'OK' if ok_e else 'NOT OK'}</span>",
            unsafe_allow_html=True
        )

    # Overall verdict
    overall = ok_f and ok_fg and ok_e
    i = _row("Overall")
    with i:
        st.markdown(
            f"<div class='badge {'ok' if overall else 'bad'}'>{'ALL REQUIREMENTS MET' if overall else 'REQUIREMENTS NOT MET'}</div>",
            unsafe_allow_html=True
        )

    # Figure row
    i = _row("Figure")
    _img_dc007_2(i, 360)

    # Persist for downstream use
    st.session_state["dc007_body_holes"] = {
        "t_m_mm": t_m,
        "f_min_mm": float(f_min),
        "fg_min_mm": float(fg_min),
        "e_min_mm": float(e_min),
        "req_f_mm": req_f,
        "req_fg_mm": req_fg,
        "req_e_mm": req_e,
        "ok_f": ok_f, "ok_fg": ok_fg, "ok_e": ok_e, "overall_ok": overall
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC007-2 (Body Holes)")

    if not user_id:
        st.info("Log in to save your DC007-2 calculations.")
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
        "t_m_mm": t_m,
        "f_min_mm": float(f_min),
        "fg_min_mm": float(fg_min),
        "e_min_mm": float(e_min),
    }
    computed_payload: Dict[str, Any] = {
        "req_f_mm": req_f, "req_fg_mm": req_fg, "req_e_mm": req_e,
        "ok_f": ok_f, "ok_fg": ok_fg, "ok_e": ok_e, "overall_ok": overall
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC007-Body-Holes_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc007_h_save_name")
        if st.button("💾 Save DC007-2 (Body Holes)", type="primary", key="dc007_h_btn_save", use_container_width=True):
            try:
                new_id = create_dc007_body_holes_calc(
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
        items_raw = list_dc007_body_holes_calcs(user_id)
        items = _normalize_list(items_raw)
        if not items:
            st.info("No DC007-2 (Body Holes) saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC007-2 (Body Holes) saves", ["-- none --", *label_to_id.keys()], key="dc007_h_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc007_body_holes_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC007-Body-Holes')}** • "
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
                    ["tₘ [mm] (ref.)", ins_s.get("t_m_mm")],
                    ["f' [mm]", ins_s.get("f_min_mm")],
                    ["f' + g' [mm]", ins_s.get("fg_min_mm")],
                    ["e° [mm]", ins_s.get("e_min_mm")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed / Checks**")
                st.table(pd.DataFrame([
                    ["Req. f' ≥ 0.25·tₘ [mm]", comp_s.get("req_f_mm")],
                    ["Req. f'+g' ≥ tₘ [mm]", comp_s.get("req_fg_mm")],
                    ["Req. e° ≥ 0.25·tₘ [mm]", comp_s.get("req_e_mm")],
                    ["Check f'", "OK" if comp_s.get("ok_f") else "NOT OK"],
                    ["Check f'+g'", "OK" if comp_s.get("ok_fg") else "NOT OK"],
                    ["Check e°", "OK" if comp_s.get("ok_e") else "NOT OK"],
                    ["Overall", "ALL REQUIREMENTS MET" if comp_s.get("overall_ok") else "REQUIREMENTS NOT MET"],
                ], columns=["Field", "Value"]))

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC007-Body-Holes"), key=f"dc007_h_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc007_h_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc007_body_holes_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc007_h_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc007_body_holes_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc007_h_btn_load_{sel_id}", use_container_width=True):
                        # Inputs back to session
                        st.session_state["dc007_h_fmin"]  = ins_s.get("f_min_mm",  st.session_state.get("dc007_h_fmin"))
                        st.session_state["dc007_h_fgmin"] = ins_s.get("fg_min_mm", st.session_state.get("dc007_h_fgmin"))
                        st.session_state["dc007_h_emin"]  = ins_s.get("e_min_mm",  st.session_state.get("dc007_h_emin"))

                        # ensure the reference t_m is available for this page and DC007-1 (if absent)
                        tm_saved = ins_s.get("t_m_mm")
                        if tm_saved is not None:
                            # Prefer to publish it under body page’s state if not present
                            if not isinstance(st.session_state.get("dc007_body"), dict):
                                st.session_state["dc007_body"] = {}
                            st.session_state["dc007_body"]["t_m_plus_CA_mm"] = float(tm_saved)

                        # base (optional convenience)
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
