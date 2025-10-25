# page_dc011.py
from __future__ import annotations
import math
import pandas as pd
import streamlit as st
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# --- Auth + Repo
from auth import current_user, require_role
from dc011_repo import (
    create_dc011_calc, list_dc011_calcs, get_dc011_calc,
    update_dc011_calc, delete_dc011_calc
)

# --- Wizard-base + valve design (same pattern as DC010)
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked

# ──────────────────────────────────────────────────────────────────────────────
# Friction factor table (from your sheet)
FT_TABLE = [
    (0.50, 0.027), (0.75, 0.025), (1.00, 0.023), (1.25, 0.022),
    (1.50, 0.021), (2.00, 0.019), (2.50, 0.018), (3.00, 0.018),
    (4.00, 0.017), (5.00, 0.016), (6.00, 0.015), (8.00, 0.014),
    (10.0, 0.014), (12.0, 0.013), (14.0, 0.013), (16.0, 0.013),
    (18.0, 0.012), (20.0, 0.012),
]
DN_OPTIONS = [dn for dn, _ in FT_TABLE]
FT_MAP = dict(FT_TABLE)

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
    """Read-only field that always shows latest value aligned in right column."""
    s = "" if value is None else fmt.format(value)
    st.session_state[key] = s
    st.text_input("", value=s, key=key, disabled=True, label_visibility="collapsed")

# ── small safe-casting helpers
def _is_set(v) -> bool:
    return v not in (None, "", "None")

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
# Wizard hydration helpers (same approach as DC010)
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
    """
    Populate st.session_state with base values using:
    1) wizard_base (locked) if present,
    2) latest valve design if still missing.
    """
    # 1) From locked wizard base
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

    # 2) From user's latest valve design if still missing essentials
    have_essential = all(
        st.session_state.get(k) not in (None, "", 0)
        for k in ("valve_nps", "valve_asme_class")
    )
    if have_essential or not user_id:
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
        # fail quietly if repo not available
        pass

def _default_bore_mm() -> float:
    """Pull from earlier pages when present; fall back to 51 mm."""
    for k in ("bore_diameter_mm", "bore_mm", "internal_bore_mm"):
        if k in st.session_state and st.session_state.get(k) not in (None, "", "None"):
            try:
                return float(st.session_state.get(k))
            except Exception:
                pass
    return 51.0

def _base_banner_from_session():
    nps = st.session_state.get("valve_nps")
    cls = st.session_state.get("valve_asme_class")
    po  = st.session_state.get("operating_pressure_mpa")
    po_txt = f"{po:.2f}" if isinstance(po, (int, float)) else (str(po) if _is_set(po) else "—")
    if st.session_state.get("active_design_id"):
        st.caption(
            f'Base: **{st.session_state.get("active_design_name","—")}** • '
            f'NPS **{nps if _is_set(nps) else "—"}** • '
            f'ASME **{cls if _is_set(cls) else "—"}** • '
            f'Bore **{_default_bore_mm():.2f} mm** • '
            f'Po **{po_txt} MPa**'
        )

# ──────────────────────────────────────────────────────────────────────────────
def render_dc011():
    """
    DC011 — FLOW COEFFICIENT Cv CALCULATION
    """
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    _css()
    _seed_base_from_valve(user_id)

    st.markdown("<h2 style='text-align:center;margin:0;'>FLOW COEFFICIENT CV CALCULATION</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align:center;margin:0;'>DC011</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # Base banner (same UX style as DC010)
    _base_banner_from_session()

    # ── INPUTS (left labels, right fields)
    st.markdown("### INPUT DATA")

    i = _row("Inner Bore  [mm]")
    inner_bore_mm = i.number_input(
        "", value=_default_bore_mm(), step=0.1, format="%.2f",
        key="dc011_inner_bore", label_visibility="collapsed"
    )

    i = _row("Seat Bore  [mm]")
    seat_bore_mm = i.number_input(
        "", value=round(_default_bore_mm(), 2), step=0.01, format="%.2f",
        key="dc011_seat_bore", label_visibility="collapsed"
    )

    # Derived: β
    beta = seat_bore_mm / inner_bore_mm if inner_bore_mm > 0 else float("nan")
    i = _row("Bore ratio  β  = SeatBore / InnerBore")
    with i:
        _out_calc("dc011_beta", f"{beta:.3f}" if beta == beta else "—", "{}")

    # θ (deg and rad)
    i = _row("Tapering angle  θ  [degree]")
    theta_deg = i.number_input(
        "", value=0.0, step=0.1, format="%.1f",
        key="dc011_theta_deg", label_visibility="collapsed"
    )

    theta_rad = math.radians(theta_deg)
    i = _row("Tapering angle  θ  [radians]")
    with i:
        _out_calc("dc011_theta_rad", f"{theta_rad:.6f}", "{}")

    # Taper length (only meaningful if θ>0)
    if theta_deg > 0:
        i = _row("Tapering length  L  [mm]")
        taper_len_mm = i.number_input(
            "", value=0.0, step=0.1, format="%.1f",
            key="dc011_taper_len", label_visibility="collapsed"
        )
    else:
        taper_len_mm = 0.0
        i = _row("Tapering length  L  [mm]")
        with i:
            _out_calc("dc011_taper_len_na", "N.A.", "{}")

    # DN / friction factor f_t
    try:
        dn_default = float(st.session_state.get("valve_nps", 2))
    except Exception:
        dn_default = 2.0

    i = _row("DN (for friction factor  fₜ )")
    dn_choice = i.selectbox(
        "", DN_OPTIONS,
        index=DN_OPTIONS.index(dn_default) if dn_default in DN_OPTIONS else DN_OPTIONS.index(2.00),
        key="dc011_dn_choice", label_visibility="collapsed"
    )

    # Editable f_t — default seeded from table for selected DN
    ft_seed = FT_MAP[dn_choice]
    i = _row("Friction factor  fₜ")
    ft = i.number_input(
        "", value=float(st.session_state.get("dc011_ft_val", ft_seed)),
        step=0.001, format="%.3f",
        key="dc011_ft_val", label_visibility="collapsed"
    )

    # ── RESISTANCE COEFFICIENTS (computed)
    K1 = 3.0 * ft
    i = _row("Resistance coefficient  K1  (= 3 × fₜ)")
    with i:
        _out_calc("dc011_K1", f"{K1:.3f}", "{}")

    beta_safe = beta if (beta == beta and beta > 0) else float("nan")
    one_minus_beta2 = 1.0 - (beta_safe ** 2) if beta_safe == beta_safe else float("nan")

    if beta_safe == beta_safe and theta_rad == theta_rad:
        if theta_rad <= (math.pi / 4.0):
            term = math.sin(theta_rad / 2.0) * (0.8 * one_minus_beta2 + 2.6 * (one_minus_beta2 ** 2))
            K2_num = K1 + term
            K2 = K2_num / (beta_safe ** 4) if beta_safe > 0 else float("nan")
        else:
            inside = math.sin(theta_rad / 2.0) * one_minus_beta2 + (one_minus_beta2 ** 2)
            inside = max(inside, 0.0)
            K2_num = K1 + 0.5 * math.sqrt(inside)
            K2 = K2_num / (beta_safe ** 4) if beta_safe > 0 else float("nan")
    else:
        K2 = float("nan")

    i = _row("Resistance coefficient  K2  (piecewise)")
    with i:
        _out_calc("dc011_K2", f"{K2:.3f}" if K2 == K2 else "—", "{}")

    # Side table (reference)
    i = _row("Friction factor reference table")
    with i:
        df = pd.DataFrame(FT_TABLE, columns=["DN (in)", "fₜ"])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── COMPUTATIONS (Cv from K2, per your formula)
    D_in = inner_bore_mm / 25.4 if inner_bore_mm > 0 else float("nan")
    if (K2 == K2) and (K2 > 0) and (D_in == D_in) and (D_in > 0):
        Cv = 29.9 * (D_in ** 2) / math.sqrt(K2)
    else:
        Cv = float("nan")

    st.markdown("---")
    i = _row("Flow coefficient  Cv  (gpm @ 1 psi)")
    with i:
        _out_calc("dc011_cv", f"{Cv:,.0f}" if Cv == Cv else "—", "{}")

    # Persist to session for other pages/reports
    st.session_state["dc011"] = {
        "inner_bore_mm": float(inner_bore_mm),
        "seat_bore_mm": float(seat_bore_mm),
        "beta": float(beta) if beta == beta else None,
        "theta_deg": float(theta_deg),
        "theta_rad": float(theta_rad),
        "taper_len_mm": float(taper_len_mm),
        "dn_choice_in": float(dn_choice),
        "ft": float(ft),
        "K1": float(K1) if K1 == K1 else None,
        "K2": float(K2) if K2 == K2 else None,
        "Cv_gpm_at_1psi": float(Cv) if Cv == Cv else None,
    }

    # ───────────────────────── Save / Load (backend) ──────────────────────────
    st.markdown("---")
    st.markdown("### Save / Load DC011")

    if not user_id:
        st.info("Sign in to save your DC011 calculations.")
        return

    # Build payload (Base + Inputs + Computed) — mirror DC010 approach
    base_payload: Dict[str, Any] = {
        "valve_design_id":   st.session_state.get("active_design_id"),
        "valve_design_name": st.session_state.get("active_design_name"),
        "nps_in":            st.session_state.get("valve_nps"),
        "asme_class":        st.session_state.get("valve_asme_class"),
        "bore_diameter_mm":  _default_bore_mm(),
        "operating_pressure_mpa": st.session_state.get("operating_pressure_mpa"),
    }
    inputs_payload: Dict[str, Any] = {
        "inner_bore_mm": float(inner_bore_mm),
        "seat_bore_mm": float(seat_bore_mm),
        "beta": float(beta) if beta == beta else None,
        "theta_deg": float(theta_deg),
        "theta_rad": float(theta_rad),
        "taper_len_mm": float(taper_len_mm),
        "dn_choice_in": float(dn_choice),
        "ft": float(ft),
    }
    computed_payload: Dict[str, Any] = {
        "K1": float(K1) if K1 == K1 else None,
        "K2": float(K2) if K2 == K2 else None,
        "Cv_gpm_at_1psi": float(Cv) if Cv == Cv else None,
    }
    payload: Dict[str, Any] = {"base": base_payload, "inputs": inputs_payload, "computed": computed_payload}

    colL, colR = st.columns([1.2, 1.8])
    with colL:
        default_name = f"DC011_{st.session_state.get('active_design_name') or 'calc'}"
        save_name = st.text_input("Save as", value=default_name, key="dc011_save_name")
        if st.button("💾 Save DC011", type="primary", use_container_width=True, key="dc011_btn_save"):
            try:
                new_id = create_dc011_calc(
                    user_id,
                    save_name,
                    payload,
                    design_id=st.session_state.get("active_design_id"),
                )
                st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
            except Exception as e:
                st.error(f"Save failed: {e}")

    # list + view + actions (matched style with DC010)
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
        items_raw = list_dc011_calcs(user_id, limit=500)
        items = _normalize_list(items_raw)
        if not items:
            st.info("No DC011 saves yet.")
        else:
            label_to_id = {
                f"{nm} ({_id[:8]}…) • Created: {_fmt_dt(ca)} • Updated: {_fmt_dt(ua)}": _id
                for (_id, nm, ca, ua) in items
            }
            picked = st.selectbox("My DC011 saves", ["-- none --", *label_to_id.keys()], key="dc011_pick")
            if picked != "-- none --":
                sel_id = label_to_id[picked]
                rec = get_dc011_calc(sel_id, user_id) or {}
                base = rec.get("base") or {}
                ins  = rec.get("inputs") or {}
                comp = rec.get("computed") or {}

                created_at = next((ca for (_i, _n, ca, _u) in items if _i == sel_id), None)
                updated_at = next((ua for (_i, _n, _c, ua) in items if _i == sel_id), None)
                name_guess = next((nm for (_i, nm, _c, _u) in items if _i == sel_id), None)

                st.caption(
                    f"Name: **{(name_guess or 'DC011')}** • "
                    f"Created: **{_fmt_dt(created_at)}** • "
                    f"Updated: **{_fmt_dt(updated_at)}**"
                )

                st.markdown("#### Summary")
                st.table(pd.DataFrame([
                    ["Valve design name", base.get("valve_design_name")],
                    ["Valve design ID",   base.get("valve_design_id")],
                    ["NPS [in]",          base.get("nps_in")],
                    ["ASME Class",        base.get("asme_class")],
                    ["Bore (base) [mm]",  base.get("bore_diameter_mm")],
                    ["Po (base) [MPa]",   base.get("operating_pressure_mpa")],
                ], columns=["Field", "Value"]))

                st.markdown("**Inputs**")
                st.table(pd.DataFrame([
                    ["Inner bore [mm]", ins.get("inner_bore_mm")],
                    ["Seat bore [mm]", ins.get("seat_bore_mm")],
                    ["β", ins.get("beta")],
                    ["θ [deg]", ins.get("theta_deg")],
                    ["θ [rad]", ins.get("theta_rad")],
                    ["Taper L [mm]", ins.get("taper_len_mm")],
                    ["DN (in)", ins.get("dn_choice_in")],
                    ["fₜ", ins.get("ft")],
                ], columns=["Field", "Value"]))

                st.markdown("**Computed**")
                st.table(pd.DataFrame([
                    ["K1", comp.get("K1")],
                    ["K2", comp.get("K2")],
                    ["Cv (gpm @ 1 psi)", comp.get("Cv_gpm_at_1psi")],
                ], columns=["Field", "Value"]))

                c1, c2, c3 = st.columns(3)
                with c1:
                    newname = st.text_input("Rename", value=picked.split(" (", 1)[0], key=f"dc011_rename_{sel_id}")
                    if st.button("Save name", key=f"dc011_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc011_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with c2:
                    if st.button("🗑️ Delete", key=f"dc011_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc011_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
                with c3:
                    if st.button("⬅ Load into page", key=f"dc011_btn_load_{sel_id}", use_container_width=True):
                        st.session_state["dc011_inner_bore"] = ins.get("inner_bore_mm", st.session_state.get("dc011_inner_bore"))
                        st.session_state["dc011_seat_bore"]  = ins.get("seat_bore_mm",  st.session_state.get("dc011_seat_bore"))
                        st.session_state["dc011_theta_deg"]  = ins.get("theta_deg",      st.session_state.get("dc011_theta_deg"))
                        st.session_state["dc011_taper_len"]  = ins.get("taper_len_mm",   st.session_state.get("dc011_taper_len"))
                        st.session_state["dc011_dn_choice"]  = ins.get("dn_choice_in",   st.session_state.get("dc011_dn_choice"))

                        st.session_state["operating_pressure_mpa"] = base.get("operating_pressure_mpa") or st.session_state.get("operating_pressure_mpa")
                        st.session_state["valve_nps"]              = base.get("nps_in") or st.session_state.get("valve_nps")
                        st.session_state["valve_asme_class"]       = base.get("asme_class") or st.session_state.get("valve_asme_class")
                        st.session_state["bore_diameter_mm"]       = base.get("bore_diameter_mm") or st.session_state.get("bore_diameter_mm")
                        st.session_state["active_design_id"]       = base.get("valve_design_id") or st.session_state.get("active_design_id")
                        st.session_state["active_design_name"]     = base.get("valve_design_name") or st.session_state.get("active_design_name")

                        st.success("Loaded into page and base banner refreshed.")
                        st.rerun()
