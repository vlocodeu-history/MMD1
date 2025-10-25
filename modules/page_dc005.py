# page_dc005.py
from __future__ import annotations
import math, os
from typing import List, Any, Tuple, Dict
from PIL import Image
import streamlit as st

# ── auth + valve base (wizard)
from auth import require_role, current_user
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ── DC005 repo (SQLite)
from dc005_repo import (
    create_dc005_calc, list_dc005_calcs, get_dc005_calc,
    update_dc005_calc, delete_dc005_calc
)

# --- Bolting material allowables (MPa) from ASME II Part D Table 3 (typical values) ---
# Sa = Div.1 allowable; Sm = Div.2 allowable. You can extend/adjust easily.
BOLT_ALLOWABLES = {
    "A193 B7":            {"Sa": 172, "Sm": 172},
    "A193 B7M":           {"Sa": 138, "Sm": 138},
    "A320 L7":            {"Sa": 172, "Sm": 172},
    "A193 B16":           {"Sa": 172, "Sm": 172},
    "A320 B8 d<18":       {"Sa": 152, "Sm": 152},
    "A320 B8 20≤d<24":    {"Sa": 159, "Sm": 159},
    "A320 B8 26≤d<30":    {"Sa": 145, "Sm": 145},
    "A320 B8 d≈32":       {"Sa": 138, "Sm": 138},
    "A320 B8M d<18":      {"Sa": 152, "Sm": 152},
    "A320 B8M 20≤d<24":   {"Sa": 152, "Sm": 152},
    "A320 B8M 26≤d<30":   {"Sa": 131, "Sm": 131},
    "A320 B8M d≈32":      {"Sa": 124, "Sm": 124},
    "A453 Gr.660A":       {"Sa": 179, "Sm": 179},
}

# --- Tensile-stress areas a (mm²) for common bolt sizes (coarse metric + UNC where useful) ---
BOLT_TENSILE_AREAS_MM2 = {
    # Metric ISO coarse (approx. At per ISO 898 tables)
    "M10 × 1.5": 58.0,
    "M12 × 1.75": 84.3,     # matches your sheet
    "M16 × 2.0": 157.0,
    "M20 × 2.5": 245.0,
    "M24 × 3.0": 353.0,
    # UNC (approx., using At in² × 645.16)
    '1/2" UNC (1/2-13)': 0.1599 * 645.16,   # ≈103.2
    '5/8" UNC (5/8-11)': 0.2260 * 645.16,   # ≈145.9
    '3/4" UNC (3/4-10)': 0.3340 * 645.16,   # ≈215.5
}

# ──────────────────────────────────────────────────────────────────────────────
# CSS + layout helpers (labels left, fields right) — same pattern as dc003/dc004
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
    st.session_state[key] = s  # keep widget in sync with current value
    st.text_input("", key=key, disabled=True, label_visibility="collapsed")

def _selectbox_with_state(key: str, options: List[str], default_index: int = 0):
    if key in st.session_state:
        return st.selectbox("", options, key=key, label_visibility="collapsed")
    return st.selectbox("", options, index=default_index, key=key, label_visibility="collapsed")

def _show_dc005_image(container, size_px: int = 300):
    for p in ["dc005_gland.png", "assets/dc005_gland.png", "static/dc005_gland.png"]:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                with container:
                    st.image(img, caption="Body/Gland plate flange – bolting", use_column_width=False)
            except Exception as e:
                with container:
                    st.warning(f"Could not load DC005 image ({e}).")
            return
    with container:
        st.info("Add **dc005_gland.png** (or put it in ./assets/ or ./static/) to show the drawing.")

# ── Wizard/base seeding (same style as your other pages; no layout changes)
def _seed_base_from_valve(user_id: str | None):
    # 1) Wizard lock hydration
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

    # already seeded enough?
    if all(st.session_state.get(k) not in (None, "", 0) for k in ("valve_nps", "valve_asme_class")):
        return

    # 2) fallback to latest valve design
    if not user_id:
        return
    try:
        rows = list_valve_designs(user_id, limit=1)
        if not rows:
            return
        # normalize first row
        first = rows[0]
        vid, vname = None, "Untitled"
        if isinstance(first, (list, tuple)):
            vid = first[0] if len(first) >= 1 else None
            if len(first) >= 2 and first[1]:
                vname = first[1]
        elif isinstance(first, dict):
            vid = first.get("id") or first.get("design_id")
            vname = first.get("name") or vname
        elif isinstance(first, str):
            vid = first

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
        pass

# ──────────────────────────────────────────────────────────────────────────────
def render_dc005():
    """
    DC005 — BOLT CALCULATION (Body/Gland plate Flange)

    Formulae:
      H  [N]  = (π/4) × (G² − Gstem²) × Pa       (Pa in MPa = N/mm²)
      Wm1[N]  = H
      Am [mm²]= Wm1 / S
      a' [mm²]= Am / n
      Ab [mm²]= a × n
      Sa_eff [MPa] = Wm1 / Ab
      Check: Sa_eff ≤ S  → VERIFIED
    """
    # Access guard + seed base
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")
    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>BOLT CALCULATION (Body/Gland plate Flange)</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC005</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Header from Valve page (read-only on right) — layout unchanged
    i = _row("NPS")
    with i:
        _out_calc("dc005_hdr_nps", st.session_state.get("valve_nps", ""), "{}")
    i = _row("ASME")
    with i:
        _out_calc("dc005_hdr_asme", st.session_state.get("valve_asme_class", ""), "{}")

    st.markdown("### INPUT DATA")

    # Defaults pulled from session
    Pa_default = float(st.session_state.get("operating_pressure_mpa", 10.21))

    # Inputs (labels left, inputs right) — layout & math unchanged
    i = _row("Gasket tight diameter  G  [mm] =")
    with i:
        G = st.number_input("", value=64.5, step=0.05, format="%.2f",
                            key="dc005_G", label_visibility="collapsed")

    i = _row("Stem seal tight diameter  Gstem  [mm] =")
    with i:
        Gstem = st.number_input("", value=27.85, step=0.05, format="%.2f",
                                key="dc005_Gstem", label_visibility="collapsed")

    i = _row("Design pressure  Pa  [MPa] =")
    with i:
        Pa = st.number_input("", value=Pa_default, step=0.01, format="%.2f",
                             key="dc005_Pa", label_visibility="collapsed")

    i = _row("Pressure rating – Class designation  Pe  [MPa] =")
    with i:
        Pe = st.number_input("", value=0.0, step=0.01, format="%.2f",
                             key="dc005_Pe", label_visibility="collapsed")

    # Material select + S (allowable).
    mats = list(BOLT_ALLOWABLES.keys())
    i = _row("Bolt material =")
    with i:
        mat = _selectbox_with_state("dc005_mat", mats, default_index=1)  # default B7M

    i = _row("Allowable bolt stress, ASME VIII Div.1 App-2 (S) [MPa] =")
    with i:
        default_S = float(BOLT_ALLOWABLES[mat]["Sa"])
        S = st.number_input(
            "",
            value=default_S, step=1.0, format="%.0f",
            key=f"dc005_S_for_{mat}", label_visibility="collapsed"
        )

    # Optional materials table (kept out of main layout)
    with st.expander("Allowable bolt stress table (ASME II Part D – Table 3)"):
        st.write({k: v for k, v in BOLT_ALLOWABLES.items()})

    # Picture (aligned to layout)
    i = _row("Sketch")
    _show_dc005_image(i, size_px=300)

    st.markdown("---")
    st.markdown("### DESIGN LOAD")

    # DESIGN LOAD (unchanged)
    ring_area = (math.pi / 4.0) * max(G**2 - Gstem**2, 0.0)   # mm²
    H = ring_area * Pa                                       # N  (since MPa = N/mm²)
    Wm1 = H

    i = _row("Total hydrostatic end force  H [N] = π/4 × (G² − Gstem²) × Pa =")
    with i:
        _out_calc("dc005_out_H", H, "{:,.2f}")

    i = _row("Minimum required bolt load for operating condition  Wm1 [N] = H =")
    with i:
        _out_calc("dc005_out_Wm1", Wm1, "{:,.2f}")

    st.markdown("---")
    st.markdown("### BOLTS SECTION CALCULATION")

    Am = Wm1 / max(S, 1e-9)  # mm²
    i = _row("Limit Stress used for bolts :  S = Sa for ASME VIII Div.1")
    with i:
        _out_calc("dc005_out_S_repeat", S, "{:.0f}")
    i = _row("Total required cross-sectional area of bolts  Am [mm²] = Wm1 / S =")
    with i:
        _out_calc("dc005_out_Am", Am, "{:,.3f}")

    st.markdown("---")
    st.markdown("### BOLTS DESIGN")

    i = _row("Bolts number  n =")
    with i:
        n = st.number_input("", value=6, min_value=1, step=1, format="%d",
                            key="dc005_n", label_visibility="collapsed")

    a_req = Am / n
    i = _row("Required cross-sectional area of each bolt  a' [mm²] = Am / n =")
    with i:
        _out_calc("dc005_out_a_req", a_req, "{:,.3f}")

    # Choose bolt (closest ≥ a')
    bolt_opts = list(BOLT_TENSILE_AREAS_MM2.keys())
    default_idx = 0
    for i_opt, k in enumerate(bolt_opts):
        if BOLT_TENSILE_AREAS_MM2[k] >= a_req:
            default_idx = i_opt
            break

    i = _row("We take the closest bolts having a > a'")
    with i:
        bolt_size = _selectbox_with_state("dc005_bolt_sel", bolt_opts, default_index=default_idx)

    a = float(BOLT_TENSILE_AREAS_MM2[bolt_size])
    i = _row("Bolt dimension — Actual tensile stress area  a [mm²] =")
    with i:
        _out_calc("dc005_out_a", a, "{:,.1f}")

    st.markdown("---")
    st.markdown("### ACTUAL TENSILE STRESS CALCULATION")

    Ab = a * n
    Sa_eff = Wm1 / max(Ab, 1e-9)

    i = _row("Total bolt tensile stress area  Ab [mm²] = a × n =")
    with i:
        _out_calc("dc005_out_Ab", Ab, "{:,.1f}")

    i = _row("Actual bolt tensile stress  Sa_eff [MPa] = Wm1 / Ab =")
    with i:
        _out_calc("dc005_out_Saeff", Sa_eff, "{:,.2f}")

    verdict = "VERIFIED" if Sa_eff <= S else "NOT VERIFIED"
    i = _row("Check  (Sa_eff ≤ S)")
    with i:
        st.markdown(
            f"<span class='badge {'ok' if verdict=='VERIFIED' else 'bad'}'>{verdict}</span>",
            unsafe_allow_html=True
        )

    # Save to state (unchanged)
    st.session_state["dc005"] = {
        "G_mm": G, "Gstem_mm": Gstem, "Pa_MPa": Pa, "Pe_MPa": Pe,
        "material": mat, "S_MPa": S,
        "ring_area_mm2": ring_area, "H_N": H, "Wm1_N": Wm1,
        "Am_mm2": Am, "n": n, "a_req_each_mm2": a_req,
        "bolt_size": bolt_size, "a_mm2": a, "Ab_mm2": Ab,
        "Sa_eff_MPa": Sa_eff, "verdict": verdict
    }

    # ───────────────── Save / Load (backend) ─────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC005")

    if not user_id:
        st.info("Log in to save your DC005 calculations.")
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
        "G_mm": G, "Gstem_mm": Gstem, "Pa_MPa": Pa, "Pe_MPa": Pe,
        "material": mat, "S_MPa": S, "n": n, "bolt_size": bolt_size
    }
    computed_payload: Dict[str, Any] = {
        "ring_area_mm2": ring_area, "H_N": H, "Wm1_N": Wm1,
        "Am_mm2": Am, "a_req_each_mm2": a_req, "a_mm2": a, "Ab_mm2": Ab,
        "Sa_eff_MPa": Sa_eff, "verdict": verdict
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])

    with colL:
        default_name = f"DC005_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as name", value=default_name, key="dc005_save_name")
        if st.button("💾 Save DC005", type="primary", key="dc005_btn_save", use_container_width=True):
            try:
                new_id = create_dc005_calc(user_id, save_name, payload)
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    def _fmt_dt(x: Any) -> str:
        try:
            return (x or "")[:16]
        except Exception:
            return str(x)

    def _normalize_dc005_list(rows: List[Any]) -> List[Tuple[str, str, Any, Any]]:
        out = []
        for r in rows or []:
            rid, nm, ca, ua = None, "Untitled", None, None
            if isinstance(r, (list, tuple)):
                if len(r) >= 1: rid = r[0]
                if len(r) >= 2 and r[1] not in (None, ""): nm = r[1]
                if len(r) >= 3: ca = r[2]
                if len(r) >= 4: ua = r[3]
            elif isinstance(r, dict):
                rid = r.get("id")
                nm  = r.get("name") or nm
                ca  = r.get("created_at")
                ua  = r.get("updated_at")
            elif isinstance(r, str):
                rid = r
            if rid:
                out.append((str(rid), str(nm), ca, ua))
        return out

    with colR:
        items_raw = list_dc005_calcs(user_id)
        items = _normalize_dc005_list(items_raw)
        if not items:
            st.info("No DC005 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC005 saves", ["-- none --", *label_to_id.keys()], key="dc005_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc005_calc(sel_id, user_id) or {}
                base_s  = rec.get("base") or {}
                ins_s   = rec.get("inputs") or {}
                comp_s  = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC005')}** • "
                    f"Created: **{_fmt_dt(created_at)}** • "
                    f"Updated: **{_fmt_dt(updated_at)}**"
                )

                st.markdown("**Base**")
                st.write(base_s)

                st.markdown("**Inputs**")
                st.write(ins_s)

                st.markdown("**Computed**")
                st.write(comp_s)

                r1, r2, r3 = st.columns(3)
                with r1:
                    newname = st.text_input("Rename", value=(name_guess or "DC005"), key=f"dc005_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc005_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc005_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with r2:
                    if st.button("🗑️ Delete", key=f"dc005_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc005_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with r3:
                    if st.button("⬅ Load (fill session)", key=f"dc005_btn_load_{sel_id}", use_container_width=True):
                        # seed session so reopening shows same values
                        st.session_state["dc005_G"] = ins_s.get("G_mm") or st.session_state.get("dc005_G")
                        st.session_state["dc005_Gstem"] = ins_s.get("Gstem_mm") or st.session_state.get("dc005_Gstem")
                        st.session_state["dc005_Pa"] = ins_s.get("Pa_MPa") or st.session_state.get("dc005_Pa")
                        st.session_state["dc005_Pe"] = ins_s.get("Pe_MPa") or st.session_state.get("dc005_Pe")
                        st.session_state["dc005_mat"] = ins_s.get("material") or st.session_state.get("dc005_mat")
                        st.session_state[f"dc005_S_for_{ins_s.get('material','A193 B7M')}"] = (
                            ins_s.get("S_MPa") or st.session_state.get(f"dc005_S_for_{ins_s.get('material','A193 B7M')}")
                        )
                        st.session_state["dc005_n"] = ins_s.get("n") or st.session_state.get("dc005_n")

                        # base
                        st.session_state["operating_pressure_mpa"] = base_s.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"] = base_s.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"] = base_s.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"] = base_s.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")

                        st.success("Loaded into session.")
                        st.rerun()
