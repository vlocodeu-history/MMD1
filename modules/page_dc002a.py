# page_dc002a.py
from __future__ import annotations
import os, math
from typing import Optional, Any, List, Tuple, Dict
from PIL import Image
import streamlit as st
from datetime import datetime

# --- auth + repos (for base hydration like DC002) ---
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# --- DC002A backend (save/load/manage) ---
from dc002a_repo import (
    create_dc002a_calc, list_dc002a_calcs, get_dc002a_calc,
    update_dc002a_calc, delete_dc002a_calc
)

# ---------- Tensile-stress areas (mm²) for common bolt sizes (UNC + a few metric)
BOLT_TENSILE_AREAS_MM2 = {
    '1/2" UNC (1/2-13)': 0.1599 * 645.16,   # ≈ 103.2
    '5/8" UNC (5/8-11)': 0.2260 * 645.16,   # ≈ 145.9
    '3/4" UNC (3/4-10)': 0.3340 * 645.16,   # ≈ 215.5
    '7/8" UNC (7/8-9)':  0.4620 * 645.16,   # ≈ 298.1
    '1" UNC (1-8)':      0.6060 * 645.16,   # ≈ 391.0
    'M16 × 2.0': 157.0, 'M20 × 2.5': 245.0, 'M24 × 3.0': 353.0,
}

# ---------- Bolt materials -> yield strength Syb (MPa)
BOLT_YIELD_MPA = {
    "A193 B7M": 550.0,   # sheet note
    "A193 B7":  860.0,
    "A320 L7":  620.0,
    "Custom…":  550.0,
}

# ---------- CSS (keep layout consistent: left labels, right inputs)
ROW_CSS = """
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
.badge{
  padding:.35rem .8rem; border-radius:.5rem; color:#fff; font-weight:800; letter-spacing:.3px; display:inline-block;
}
.badge.ok{ background:#22c55e; }
.badge.bad{ background:#ef4444; }
</style>
"""

# ---------- layout helpers ----------
def _css():
    st.markdown(ROW_CSS, unsafe_allow_html=True)

def _row(label: str):
    lc, rc = st.columns([1.25, 2.25])
    with lc:
        st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
    return rc

def _out(key: str, value, fmt: str | None = None):
    s = fmt.format(value) if fmt else ("" if value is None else str(value))
    st.text_input("", value=s, key=key, disabled=True, label_visibility="collapsed")

def _selectbox_with_state(key: str, options, default_index=0):
    if key in st.session_state:
        return st.selectbox("", options, key=key, label_visibility="collapsed")
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

# ---------- repo-shape helpers (same spirit as dc002) ----------
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

# ---------- base seeding from Valve (wizard-aware + robust, like dc002) ----------
def _seed_base_from_valve(user_id: Optional[str]):
    # 1) Wizard lock hydration
    if is_locked():
        wb = get_base() or {}
        st.session_state.setdefault("nps_in", wb.get("nps_in"))
        st.session_state.setdefault("asme_class", wb.get("asme_class"))
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

# ---------- formatting helpers ----------
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
    if not x: return "—"
    if isinstance(x, datetime):
        return x.strftime("%Y-%m-%d %H:%M")
    if isinstance(x, str):
        # Try common timestamp strings; else trim
        try:
            base = x[:26]  # safe slice
            for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(base, fmt).strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
        except Exception:
            pass
        return x[:16]
    return str(x)

def _kv_table(pairs: List[Tuple[str, Any]]):
    import pandas as pd
    rows = [{"Field": k, "Value": _fmt_num(v) if isinstance(v, (int, float)) else (v if v is not None else "—")} for k, v in pairs]
    st.table(pd.DataFrame(rows))

# ---------- page ----------
def render_dc002a():
    """
    DC002A — Body-Closure Bolts calculation (Pressure × 1.5) — Test condition

    Formulas:
      Pa_test [MPa] = 1.5 × Pa
      H [N]         = 0.785 × G² × Pa_test
      Wm1 [N]       = H
      S [MPa]       = 0.83 × Syb
      Am [mm²]      = Wm1 / S
      a' [mm²]      = Am / n
      Ab [mm²]      = a × n
      Sa_eff [MPa]  = Wm1 / Ab
      Check         : Sa_eff ≤ S  → VERIFIED
    """
    # Access guard + base seeding
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    # ---------- header ----------
    st.markdown("<h2 style='text-align:center;margin:0;'>Body-Closure Bolts calculation (Pressure × 1.5) — Test condition</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC002A</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Small base banner
    if st.session_state.get("active_design_id"):
        base_po = st.session_state.get("operating_pressure_mpa")
        po_txt = f"{base_po:.2f}" if isinstance(base_po, (int, float)) else str(base_po or "—")
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{st.session_state.get("valve_nps","—")}** • '
            f'ASME **{st.session_state.get("valve_asme_class","—")}** • '
            f'Po **{po_txt} MPa**'
        )

    # Header fields (read-only)
    i = _row("NPS")
    with i:
        _out("dc002a_hdr_nps",  st.session_state.get("valve_nps", ""))
    i = _row("ASME")
    with i:
        _out("dc002a_hdr_asme", st.session_state.get("valve_asme_class", ""))

    st.markdown("### INPUT DATA")

    # Defaults from base pressure
    Pa_base = float(st.session_state.get("operating_pressure_mpa", 10.21))

    i = _row("Gasket tight diameter  G  [mm] =")
    with i:
        G = st.number_input("", value=122.7, step=0.1, format="%.1f", key="dc002a_G", label_visibility="collapsed")

    i = _row("Test pressure  Pa [MPa] × 1.5 =")
    with i:
        Pa_test = st.number_input("", value=round(Pa_base * 1.5, 2), step=0.01, format="%.2f",
                                  key="dc002a_Pa_test", label_visibility="collapsed")

    i = _row("Pressure rating – Class designation  Pe  [MPa] =")
    with i:
        Pe = st.number_input("", value=0.0, step=0.01, format="%.2f",
                             key="dc002a_Pe", label_visibility="collapsed")

    # Bolt material / Syb / S
    i = _row("Bolt material =")
    with i:
        mat = _selectbox_with_state("dc002a_mat", list(BOLT_YIELD_MPA.keys()), default_index=0)

    i = _row("Maximum yield stress at ambient temperature (bolting)  Syb  [MPa]")
    with i:
        Syb = st.number_input("", value=float(BOLT_YIELD_MPA[mat]), step=1.0,
                              key="dc002a_Syb", label_visibility="collapsed")

    i = _row("Allowable bolt stress (hydro test)  S = 0.83 × Syb  [MPa]")
    default_S = round(0.83 * float(Syb), 1)
    with i:
        S = st.number_input("", value=default_S, step=0.1, format="%.1f",
                            key=f"dc002a_S_for_{default_S:.1f}", label_visibility="collapsed")

    # Optional figure
    _show_flange_image(size_px=300)

    st.markdown("---")
    st.markdown("### DESIGN LOAD")

    H = 0.785 * (G ** 2) * Pa_test
    Wm1 = H

    i = _row("Total hydrostatic end force  H  [N] = 0.785 × G² × Pa_test")
    with i:
        _out(f"dc002a_out_H_{H:.2f}", H, "{:,.2f}")
    i = _row("Minimum required bolt load for test condition  Wm1  [N]")
    with i:
        _out(f"dc002a_out_Wm1_{Wm1:.2f}", Wm1, "{:,.2f}")

    st.markdown("---")
    st.markdown("### BOLTS SECTION CALCULATION")

    Am = Wm1 / (S if S else 1e-9)  # mm²
    i = _row("Limit Stress used for bolts :  S = Sm for ASME VIII Div.2")
    with i:
        _out(f"dc002a_out_S_repeat_{S:.1f}", S, "{:.1f}")
    i = _row("Total required cross-sectional area of bolts  Am  [mm²] = Wm1 / S")
    with i:
        _out(f"dc002a_out_Am_{Am:.2f}", Am, "{:,.2f}")

    st.markdown("---")
    st.markdown("### BOLTS DESIGN")

    i = _row("Bolts number  n  =")
    with i:
        n = st.number_input("", value=6, min_value=1, step=1, format="%d",
                            key="dc002a_n", label_visibility="collapsed")

    a_req_each = Am / n
    i = _row("Required cross-sectional area of each bolt  a'  [mm²] = Am / n")
    with i:
        _out(f"dc002a_out_areq_{a_req_each:.2f}", a_req_each, "{:,.2f}")

    # Select bolt size (closest ≥ a')
    options = list(BOLT_TENSILE_AREAS_MM2.keys())
    default_idx = 0
    for i_opt, k in enumerate(options):
        if BOLT_TENSILE_AREAS_MM2[k] >= a_req_each:
            default_idx = i_opt
            break

    i = _row("We take the closest bolts having a > a'")
    with i:
        bolt_size = _selectbox_with_state("dc002a_bolt_sel", options, default_index=default_idx)

    a = float(BOLT_TENSILE_AREAS_MM2[bolt_size])
    i = _row("Bolt dimension — Actual tensile stress area  a  [mm²]")
    with i:
        _out(f"dc002a_out_a_{a:.1f}", a, "{:,.1f}")

    st.markdown("---")
    st.markdown("### ACTUAL TENSILE STRESS CALCULATION")

    Ab = a * n
    Sa_eff = Wm1 / (Ab if Ab else 1e-9)

    i = _row("Total bolt tensile stress area  Ab  [mm²] = a × n")
    with i:
        _out(f"dc002a_out_Ab_{Ab:.1f}", Ab, "{:,.1f}")
    i = _row("Actual bolt tensile stress  Sa_eff  [MPa] = Wm1 / Ab")
    with i:
        _out(f"dc002a_out_Saeff_{Sa_eff:.2f}", Sa_eff, "{:,.2f}")

    verdict = "VERIFIED" if Sa_eff <= S else "NOT VERIFIED"
    i = _row("Check  (Sa_eff ≤ S)")
    with i:
        st.markdown(f"<span class='badge {'ok' if verdict=='VERIFIED' else 'bad'}'>{verdict}</span>", unsafe_allow_html=True)

    # ---------- stash for other pages ----------
    st.session_state["dc002a"] = {
        "G_mm": G, "Pa_test_MPa": Pa_test, "Pe_MPa": Pe,
        "bolt_material": mat, "Syb_MPa": Syb, "S_MPa": S,
        "H_N": H, "Wm1_N": Wm1, "Am_mm2": Am,
        "n": n, "a_req_each_mm2": a_req_each,
        "bolt_size": bolt_size, "a_mm2": a, "Ab_mm2": Ab,
        "Sa_eff_MPa": Sa_eff, "verdict": verdict
    }

    # ───────────────── Save / Load (backend) ─────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC002A")

    user = current_user() or {}
    user_id = user.get("id")
    if not user_id:
        st.info("Log in to save your DC002A calculations.")
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
        "G_mm": G, "Pa_test_MPa": Pa_test, "Pe_MPa": Pe,
        "bolt_material": mat, "Syb_MPa": Syb, "n": n, "bolt_size": bolt_size
    }
    computed_payload: Dict[str, Any] = {
        "S_MPa": S, "H_N": H, "Wm1_N": Wm1, "Am_mm2": Am,
        "a_req_each_mm2": a_req_each, "a_mm2": a, "Ab_mm2": Ab,
        "Sa_eff_MPa": Sa_eff, "verdict": verdict
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC002A_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc002a_save_name")
        if st.button("💾 Save DC002A", type="primary", key="dc002a_btn_save", use_container_width=True):
            try:
                new_id = create_dc002a_calc(user_id, save_name, payload)
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    # helper to normalize list results: [(id, name, created_at, updated_at)] or dicts
    def _normalize_dc002a_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
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
        items_raw = list_dc002a_calcs(user_id)
        items = _normalize_dc002a_list(items_raw)
        if not items:
            st.info("No DC002A saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC002A saves", ["-- none --", *label_to_id.keys()], key="dc002a_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc002a_calc(sel_id, user_id) or {}

                # pull sections
                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                # neat meta (some backends return only data; timestamps come from the list)
                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC002A')}** • "
                    f"Created: **{_fmt_dt(created_at)}** • "
                    f"Updated: **{_fmt_dt(updated_at)}**"
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
                    ("G [mm]",                 ins_s.get("G_mm")),
                    ("Pa_test [MPa]",          ins_s.get("Pa_test_MPa")),
                    ("Pe [MPa]",               ins_s.get("Pe_MPa")),
                    ("Bolt material",          ins_s.get("bolt_material")),
                    ("Syb [MPa]",              ins_s.get("Syb_MPa")),
                    ("Bolts number n",         ins_s.get("n")),
                    ("Bolt size",              ins_s.get("bolt_size")),
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
                    newname = st.text_input("Rename", value=(name_guess or "DC002A"), key=f"dc002a_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc002a_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc002a_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc002a_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc002a_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc002a_btn_load_{sel_id}", use_container_width=True):
                        # seed session so reopening shows the same values
                        st.session_state["dc002a_G"] = ins_s.get("G_mm") or st.session_state.get("dc002a_G")
                        st.session_state["dc002a_Pa_test"] = ins_s.get("Pa_test_MPa") or st.session_state.get("dc002a_Pa_test")
                        st.session_state["dc002a_Pe"] = ins_s.get("Pe_MPa") or st.session_state.get("dc002a_Pe")
                        st.session_state["dc002a_mat"] = ins_s.get("bolt_material") or st.session_state.get("dc002a_mat")
                        st.session_state["dc002a_Syb"] = ins_s.get("Syb_MPa") or st.session_state.get("dc002a_Syb")
                        st.session_state["dc002a_n"] = ins_s.get("n") or st.session_state.get("dc002a_n")
                        st.session_state["dc002a_bolt_sel"] = ins_s.get("bolt_size") or st.session_state.get("dc002a_bolt_sel")

                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"] = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"] = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"] = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
