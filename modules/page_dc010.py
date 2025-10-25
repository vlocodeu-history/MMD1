# page_dc010.py
from __future__ import annotations
import math, os
from typing import Any, Dict, List, Optional, Tuple
from PIL import Image
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Auth + wizard base
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── Repos
from dc010_repo import (
    create_dc010_calc, list_dc010_calcs, get_dc010_calc,
    update_dc010_calc, delete_dc010_calc
)
from dc008_repo import list_dc008_calcs, get_dc008_calc
from dc001_repo import list_dc001_calcs, get_dc001_calc
from dc003_repo import list_dc003_calcs, get_dc003_calc

# ──────────────────────────────────────────────────────────────────────────────
# CSS + layout helpers
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
    s = "" if value is None else fmt.format(value)
    st.session_state[key] = s
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _img_dc010(size_px: int = 300):
    for p in ["dc010_torque.png", "assets/dc010_torque.png", "static/dc010_torque.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                st.image(img, caption="Torque components (schematic)", use_column_width=False)
            except Exception as e:
                st.warning(f"Could not load DC010 diagram ({e}).")
            return
    st.info("Add **dc010_torque.png** (or put it in ./assets/ or ./static/) to show a sketch here.")

# ── tiny casters
def _f(x, default: float) -> float:
    try: return float(x)
    except Exception: return float(default)

def _i(x, default: int) -> int:
    try: return int(x)
    except Exception: return int(default)

# ──────────────────────────────────────────────────────────────────────────────
# Wizard/base seeders
def _normalize_first_pair(rows: List[Any]) -> Tuple[Optional[str], Optional[str]]:
    if not rows: return None, None
    first = rows[0]
    rid, nm = None, "Untitled"
    if isinstance(first, (list, tuple)):
        if len(first) >= 1: rid = first[0]
        if len(first) >= 2 and first[1] not in (None, ""): nm = first[1]
    elif isinstance(first, dict):
        rid = first.get("id") or first.get("design_id") or first.get("calc_id") or first.get("id_")
        nm  = first.get("name") or first.get("title") or nm
    elif isinstance(first, str):
        rid = first
    return (str(rid) if rid else None, str(nm) if nm else None)

def _seed_base_from_valve(user_id: Optional[str]):
    # 1) Wizard lock
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

    # 2) Fallback to latest valve design if still missing essentials
    if all(st.session_state.get(k) not in (None, "", 0) for k in ("valve_nps", "valve_asme_class")):
        return
    if not user_id: return
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
# Pull latest saves from DC008, DC001, DC003 (robust)
def _latest_dc008(user_id: Optional[str]) -> Dict[str, Any]:
    ss = st.session_state.get("dc008") or {}
    fallback = {"D_ball_mm": ss.get("D_ball_mm")}
    if not user_id: return fallback
    try:
        raw = list_dc008_calcs(user_id, limit=1)
        dcid, _ = _normalize_first_pair(raw)
        if not dcid: return fallback
        rec = get_dc008_calc(dcid, user_id) or {}
        ins = (rec.get("inputs") or {})
        comp = (rec.get("computed") or {})
        return {
            "source_id": dcid,
            "D_ball_mm": ins.get("D_ball_mm", fallback.get("D_ball_mm")),
        } | comp
    except Exception:
        return fallback

def _latest_dc001(user_id: Optional[str]) -> Dict[str, Any]:
    ss = st.session_state.get("dc001") or {}
    fallback = {
        "Dm_mm": ss.get("Dm") or (ss.get("inputs") or {}).get("Dm_mm"),
        "Dc_mm": ss.get("Dc") or (ss.get("inputs") or {}).get("Dc_mm"),
        "Pr_N":  ss.get("Pr") or (ss.get("computed") or {}).get("Pr_N"),
        "Nma":   ss.get("Nma") or (ss.get("inputs") or {}).get("Nma"),
        "Fmr_N": (ss.get("Fmr") or (ss.get("computed") or {}).get("Fmr_N")),
    }
    if not user_id: return fallback
    try:
        raw = list_dc001_calcs(user_id, limit=1)
        dcid, _ = _normalize_first_pair(raw)
        if not dcid: return fallback
        rec = get_dc001_calc(dcid, user_id) or {}
        ins = (rec.get("inputs") or {})
        comp = (rec.get("computed") or {})
        return {
            "source_id": dcid,
            "Dm_mm": ins.get("Dm_mm", fallback.get("Dm_mm")),
            "Dc_mm": ins.get("Dc_mm", fallback.get("Dc_mm")),
            "Pr_N":  comp.get("Pr_N",  fallback.get("Pr_N")),
            "Nma":   ins.get("Nma",    fallback.get("Nma")),
            "Fmr_N": comp.get("Fmr_N", fallback.get("Fmr_N")),
        }
    except Exception:
        return fallback

def _latest_dc003(user_id: Optional[str]) -> Dict[str, Any]:
    ss = st.session_state.get("dc003") or {}
    fallback = {"Db_mm": ss.get("Db_mm")}
    if not user_id: return fallback
    try:
        raw = list_dc003_calcs(user_id, limit=1)
        dcid, _ = _normalize_first_pair(raw)
        if not dcid: return fallback
        rec = get_dc003_calc(dcid, user_id) or {}
        ins = (rec.get("inputs") or {})
        return {"source_id": dcid, "Db_mm": ins.get("Db_mm", fallback.get("Db_mm"))}
    except Exception:
        return fallback

# ──────────────────────────────────────────────────────────────────────────────
def render_dc010():
    """
    DC010 — VALVE TORQUE CALCULATION
    Pulls inputs from latest DC008 (D), DC001 (Dc, Dm, Pr, Nma), and DC003 (Db),
    then applies:
      Fb  = (π * Dc² / 4) * Po
      Mtb = Fb * f1 * Db / 2
      Fm  = Pr * Nma
      Mtm = 2 * Fm * f2 * 0.91 * D / 2
      Fi  = (π * (Dc² − Dm²) / 4) * Po
      Mti = Fi * f2 * 0.91 * D / 2
      Tbb1 = (Mtb + Mti + Mtm)
    """
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>VALVE TORQUE CALCULATION</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC010</h4>", unsafe_allow_html=True)
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

    # ---- Pull latest sources
    src008 = _latest_dc008(user_id)
    src001 = _latest_dc001(user_id)
    src003 = _latest_dc003(user_id)

    # ---- Defaults (session → sources → constants)
    valve_class = _i(st.session_state.get("valve_asme_class", 600), 600)
    Po_default  = _f(st.session_state.get("operating_pressure_mpa", 10.21), 10.21)

    D_default   = _f(st.session_state.get("dc010_D",  src008.get("D_ball_mm", 88.95)), 88.95)  # DC008
    Dc_default  = _f(st.session_state.get("dc010_Dc", src001.get("Dc_mm",     71.0 )), 71.0)   # DC001
    Dm_default  = _f(st.session_state.get("dc010_Dm", src001.get("Dm_mm",     62.3 )), 62.3)   # DC001
    Db_default  = _f(st.session_state.get("dc010_Db", src003.get("Db_mm",     40.0 )), 40.0)   # DC003
    Pr_default  = _f(st.session_state.get("dc010_Pr", src001.get("Pr_N",     787.0 )), 787.0)  # DC001 (Pr)
    Nma_default = _i(st.session_state.get("dc010_Nma",src001.get("Nma",         1 )), 1)       # DC001

    st.markdown("### INPUT DATA")

    i = _row("Valve class")
    with i:
        st.text_input("", value=str(valve_class), disabled=True, label_visibility="collapsed")

    i = _row("Operating pressure  Po  [MPa]")
    with i:
        Po = st.number_input("", value=Po_default, step=0.01, format="%.2f",
                             key="dc010_Po", label_visibility="collapsed")

    i = _row("Ball diameter  D  [mm]  ← DC008")
    with i:
        D  = st.number_input("", value=D_default, step=0.01, format="%.2f",
                             key="dc010_D", label_visibility="collapsed")

    i = _row("External seal diameter  Dc  [mm]  ← DC001")
    with i:
        Dc = st.number_input("", value=Dc_default, step=0.1, format="%.1f",
                             key="dc010_Dc", label_visibility="collapsed")

    i = _row("Seat friction radius  b1  [mm]")
    with i:
        b1 = st.number_input("", value=31.74, step=0.01, format="%.2f",
                             key="dc010_b1", label_visibility="collapsed")

    i = _row("Contact diameter  Dm  [mm]  ← DC001")
    with i:
        Dm = st.number_input("", value=Dm_default, step=0.01, format="%.2f",
                             key="dc010_Dm", label_visibility="collapsed")

    i = _row("Internal ball bushing diameter  Db  [mm]  ← DC003")
    with i:
        Db = st.number_input("", value=Db_default, step=0.1, format="%.1f",
                             key="dc010_Db", label_visibility="collapsed")

    i = _row("Spring force per spring  Pr  [N]  ← DC001 (Load at real packing)")
    with i:
        Pr = st.number_input("", value=Pr_default, step=0.1, format="%.1f",
                             key="dc010_Pr", label_visibility="collapsed")

    i = _row("Q.ty of springs  Nma  (for each seat)  ← DC001")
    with i:
        Nma = st.number_input("", value=Nma_default, step=1, min_value=1,
                              key="dc010_Nma", label_visibility="collapsed")

    i = _row("Coeff. of friction between ball and ball bushing  f1")
    with i:
        f1  = st.number_input("", value=0.03, step=0.01, format="%.2f",
                              key="dc010_f1", label_visibility="collapsed")

    i = _row("Coeff. of friction between ball and seat  f2")
    with i:
        f2  = st.number_input("", value=0.15, step=0.01, format="%.2f",
                              key="dc010_f2", label_visibility="collapsed")

    i = _row("Figure")
    with i:
        _img_dc010(300)

    st.markdown("---")
    st.markdown("#### Break to open torque calculation in single piston effect condition  Tbb1")

    # ─────────────────── Calculations (exactly as specified) ───────────────────
    # Fb = (π * Dc^2 / 4) * Po
    Fb = (math.pi * (Dc ** 2) / 4.0) * Po  # N

    # Mtb = Fb * f1 * Db / 2
    # (units N * mm -> N·mm; we display in N·m => /1000)
    Mtb_Nmm = Fb * f1 * (Db / 2.0)
    Mtb_Nm  = Mtb_Nmm / 1000.0

    # Fm = Pr * Nma
    Fm = Pr * Nma  # N

    # Mtm = 2 * Fm * f2 * 0.91 * D / 2
    Mtm_Nmm = 2.0 * Fm * f2 * 0.91 * (D / 2.0)
    Mtm_Nm  = Mtm_Nmm / 1000.0

    # Fi = (π * (Dc^2 − Dm^2) / 4) * Po
    Fi = (math.pi * max(Dc ** 2 - Dm ** 2, 0.0) / 4.0) * Po  # N

    # Mti = Fi * f2 * 0.91 * D / 2
    Mti_Nmm = Fi * f2 * 0.91 * (D / 2.0)
    Mti_Nm  = Mti_Nmm / 1000.0

    # Tbb1 = (Mtb + Mti + Mtm)
    Tbb1_Nm = Mtb_Nm + Mti_Nm + Mtm_Nm

    # ───────────────────────────── Outputs ─────────────────────────────
    i = _row("Pressure load on ball hubs  Fb  [N]")
    with i: _out_calc("dc010_Fb", f"{Fb:,.0f}", "{}")

    i = _row("Torque from total differential pressure  Mtb  [N·m]")
    with i: _out_calc("dc010_Mtb", f"{Mtb_Nm:,.0f}", "{}")

    i = _row("Spring load on each seat  Fm  [N]")
    with i: _out_calc("dc010_Fm", f"{Fm:,.0f}", "{}")

    i = _row("Torque from spring load (two seats)  Mtm  [N·m]")
    with i: _out_calc("dc010_Mtm", f"{Mtm_Nm:,.0f}", "{}")

    i = _row("Piston effect  Fi  [N]")
    with i: _out_calc("dc010_Fi", f"{Fi:,.0f}", "{}")

    i = _row("Torque from piston effect  Mti  [N·m]")
    with i: _out_calc("dc010_Mti", f"{Mti_Nm:,.0f}", "{}")

    i = _row("Total torque  Tbb1  [N·m]  = (Mtb + Mti + Mtm)")
    with i: _out_calc("dc010_Tbb1", f"{Tbb1_Nm:,.0f}", "{}")

    # Save into session for downstream reports/exports
    st.session_state["dc010"] = {
        "valve_class": valve_class, "Po_MPa": Po,
        "D_mm": D, "Dc_mm": Dc, "b1_mm": b1, "Dm_mm": Dm, "Db_mm": Db,
        "Pr_N": Pr, "Nma": int(Nma), "f1": f1, "f2": f2,
        "Fb_N": Fb, "Mtb_Nm": Mtb_Nm, "Fm_N": Fm,
        "Mtm_Nm": Mtm_Nm, "Fi_N": Fi, "Mti_Nm": Mti_Nm,
        "Tbb1_Nm": Tbb1_Nm
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC010")

    if not user_id:
        st.info("Log in to save your DC010 calculations.")
        return

    base_payload: Dict[str, Any] = {
        "valve_design_id":   st.session_state.get("active_design_id"),
        "valve_design_name": st.session_state.get("active_design_name"),
        "nps_in":            st.session_state.get("valve_nps"),
        "asme_class":        st.session_state.get("valve_asme_class"),
        "bore_diameter_mm":  st.session_state.get("bore_diameter_mm"),
        "operating_pressure_mpa": st.session_state.get("operating_pressure_mpa"),
        # helpful traceability
        "source_dc008_id": src008.get("source_id"),
        "source_dc001_id": src001.get("source_id"),
        "source_dc003_id": src003.get("source_id"),
    }
    inputs_payload: Dict[str, Any] = {
        "Po_MPa": Po, "D_mm": D, "Dc_mm": Dc, "b1_mm": b1,
        "Dm_mm": Dm, "Db_mm": Db, "Pr_N": Pr, "Nma": int(Nma),
        "f1": f1, "f2": f2,
    }
    computed_payload: Dict[str, Any] = {
        "Fb_N": Fb, "Mtb_Nm": Mtb_Nm, "Fm_N": Fm,
        "Mtm_Nm": Mtm_Nm, "Fi_N": Fi, "Mti_Nm": Mti_Nm,
        "Tbb1_Nm": Tbb1_Nm,
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC010_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc010_save_name")
        if st.button("💾 Save DC010", type="primary", key="dc010_btn_save", use_container_width=True):
            try:
                new_id = create_dc010_calc(
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
        items_raw = list_dc010_calcs(user_id)
        items = _normalize_list(items_raw)
        if not items:
            st.info("No DC010 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC010 saves", ["-- none --", *label_to_id.keys()], key="dc010_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc010_calc(sel_id, user_id) or {}

                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC010')}** • "
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
                    ["Po [MPa]", ins_s.get("Po_MPa")],
                    ["D [mm]", ins_s.get("D_mm")],
                    ["Dc [mm]", ins_s.get("Dc_mm")],
                    ["b1 [mm]", ins_s.get("b1_mm")],
                    ["Dm [mm]", ins_s.get("Dm_mm")],
                    ["Db [mm]", ins_s.get("Db_mm")],
                    ["Pr [N]", ins_s.get("Pr_N")],
                    ["Nma [-]", ins_s.get("Nma")],
                    ["f1 [-]", ins_s.get("f1")],
                    ["f2 [-]", ins_s.get("f2")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed**")
                st.table(pd.DataFrame([
                    ["Fb [N]", comp_s.get("Fb_N")],
                    ["Mtb [N·m]", comp_s.get("Mtb_Nm")],
                    ["Fm [N]", comp_s.get("Fm_N")],
                    ["Mtm [N·m]", comp_s.get("Mtm_Nm")],
                    ["Fi [N]", comp_s.get("Fi_N")],
                    ["Mti [N·m]", comp_s.get("Mti_Nm")],
                    ["Tbb1 [N·m]", comp_s.get("Tbb1_Nm")],
                ], columns=["Field", "Value"]))

                # ---------- Actions ----------
                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC010"), key=f"dc010_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc010_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc010_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc010_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc010_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc010_btn_load_{sel_id}", use_container_width=True):
                        st.session_state["dc010_Po"]  = ins_s.get("Po_MPa",  st.session_state.get("dc010_Po"))
                        st.session_state["dc010_D"]   = ins_s.get("D_mm",    st.session_state.get("dc010_D"))
                        st.session_state["dc010_Dc"]  = ins_s.get("Dc_mm",   st.session_state.get("dc010_Dc"))
                        st.session_state["dc010_b1"]  = ins_s.get("b1_mm",   st.session_state.get("dc010_b1"))
                        st.session_state["dc010_Dm"]  = ins_s.get("Dm_mm",   st.session_state.get("dc010_Dm"))
                        st.session_state["dc010_Db"]  = ins_s.get("Db_mm",   st.session_state.get("dc010_Db"))
                        st.session_state["dc010_Pr"]  = ins_s.get("Pr_N",    st.session_state.get("dc010_Pr"))
                        st.session_state["dc010_Nma"] = ins_s.get("Nma",     st.session_state.get("dc010_Nma"))
                        st.session_state["dc010_f1"]  = ins_s.get("f1",      st.session_state.get("dc010_f1"))
                        st.session_state["dc010_f2"]  = ins_s.get("f2",      st.session_state.get("dc010_f2"))

                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
