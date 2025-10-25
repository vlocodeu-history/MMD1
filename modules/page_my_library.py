# page_my_library.py
from __future__ import annotations
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import streamlit as st

from auth import require_role, current_user

# Valve designs repo
from valve_repo import (
    list_valve_designs,
    get_valve_design,
    delete_valve_design,
    update_valve_design,
)

# DC001 repo
from dc001_repo import (
    list_dc001_calcs,
    get_dc001_calc,
    update_dc001_calc,
    delete_dc001_calc,
)

# DC001A repo
from dc001a_repo import (
    list_dc001a_calcs,
    get_dc001a_calc,
    update_dc001a_calc,
    delete_dc001a_calc,
)

# DC002 repo
from dc002_repo import (
    list_dc002_calcs,
    get_dc002_calc_with_meta,  # includes meta + data
    update_dc002_calc,
    delete_dc002_calc,
)

# DC002A repo
from dc002a_repo import (
    list_dc002a_calcs,
    get_dc002a_calc,
    update_dc002a_calc,
    delete_dc002a_calc,
)

# DC003 / DC004 / DC005 repos
from dc003_repo import (
    list_dc003_calcs,
    get_dc003_calc,
    update_dc003_calc,
    delete_dc003_calc,
)
from dc004_repo import (
    list_dc004_calcs,
    get_dc004_calc,
    update_dc004_calc,
    delete_dc004_calc,
)
from dc005_repo import (
    list_dc005_calcs,
    get_dc005_calc,
    update_dc005_calc,
    delete_dc005_calc,
)

# DC005A repo
from dc005a_repo import (
    list_dc005a_calcs,
    get_dc005a_calc,
    update_dc005a_calc,
    delete_dc005a_calc,
)

# DC006 repo
from dc006_repo import (
    list_dc006_calcs,
    get_dc006_calc,
    update_dc006_calc,
    delete_dc006_calc,
)

# DC006A repo
from dc006a_repo import (
    list_dc006a_calcs,
    get_dc006a_calc,
    update_dc006a_calc,
    delete_dc006a_calc,
)

# DC007 (body) repo
from dc007_body_repo import (
    list_dc007_body_calcs,
    get_dc007_body_calc,
    update_dc007_body_calc,
    delete_dc007_body_calc,
)

# DC007 (body holes) repo
from dc007_body_holes_repo import (
    list_dc007_body_holes_calcs,
    get_dc007_body_holes_calc,
    update_dc007_body_holes_calc,
    delete_dc007_body_holes_calc,
)

# DC008 repo
from dc008_repo import (
    list_dc008_calcs,
    get_dc008_calc,
    update_dc008_calc,
    delete_dc008_calc,
)

# NEW: DC010 / DC011 / DC012 repos
from dc010_repo import (
    list_dc010_calcs,
    get_dc010_calc,
    update_dc010_calc,
    delete_dc010_calc,
)
from dc011_repo import (
    list_dc011_calcs,
    get_dc011_calc,
    update_dc011_calc,
    delete_dc011_calc,
)
from dc012_repo import (  # make sure this file exists with same API pattern
    list_dc012_calcs,
    get_dc012_calc,
    update_dc012_calc,
    delete_dc012_calc,
)

# ---------------------- small display helpers ----------------------
def _fmt_num(x: Any, digits: int = 2) -> str:
    if x in (None, "", "None"):
        return "—"
    try:
        f = float(x)
        if abs(f - round(f)) < 1e-9:
            return f"{int(round(f))}"
        return f"{f:.{digits}f}"
    except Exception:
        return str(x)

def _kv_table(pairs: List[tuple[str, Any]], *, digits: int = 2):
    rows = []
    for k, v in pairs:
        if isinstance(v, (int, float)) or (
            isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit()
        ):
            rows.append({"Field": k, "Value": _fmt_num(v, digits)})
        else:
            rows.append({"Field": k, "Value": v if v not in (None, "", "None") else "—"})
    df = pd.DataFrame(rows)
    st.table(df)

def _fmt_ts(ts: Optional[Union[str, Any]]) -> str:
    """Display timestamps consistently as 'YYYY-MM-DD HH:MM:SS' when possible."""
    if not ts:
        return "—"
    s = str(ts).strip()
    if len(s) >= 19:
        return s[:19]
    return s

# ---------------------- VALVE: summarize + pretty render ----------------------
def _valve_summarize(data: dict) -> dict:
    return {
        "nps_in": data.get("nps_in"),
        "asme_class": data.get("asme_class"),
        "bore_mm": (data.get("calculated") or {}).get("bore_diameter_mm"),
        "f2f_mm": (data.get("calculated") or {}).get("face_to_face_mm"),
        "t_mm": (data.get("calculated") or {}).get("body_wall_thickness_mm"),
    }

def _valve_render_pretty(data: Dict[str, Any]):
    inputs     = data.get("inputs", {}) or {}
    materials  = inputs.get("materials", {}) or {}
    allow_st   = inputs.get("allowable_stress", {}) or {}
    calc       = data.get("calculated", {}) or {}

    st.markdown("#### Overview")
    _kv_table([
        ("Nominal Pipe Size (NPS) [in]", data.get("nps_in")),
        ("ASME Class", data.get("asme_class")),
        ("Operating Pressure (MPa)", data.get("calc_operating_pressure_mpa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Input Parameters")
        _kv_table([
            ("Internal Bore (Ball/Seat) [mm]", inputs.get("internal_bore_mm")),
            ("Face to Face (F-F) [mm]", inputs.get("face_to_face_mm")),
            ("Design Temperature Min (°C)", inputs.get("temp_min_c")),
            ("Design Temperature Max (°C)", inputs.get("temp_max_c")),
            ("Corrosion Allowance CA [mm]", inputs.get("corrosion_allowance_mm")),
        ])
        st.markdown("#### Allowable Stress")
        _kv_table([
            ("Preset", allow_st.get("preset")),
            ("Allowable Stress S [MPa]", allow_st.get("S_mpa")),
        ])

    with col2:
        st.markdown("#### Materials")
        _kv_table([
            ("Body / Closure", materials.get("body_closure")),
            ("Ball / Seat", materials.get("ball_seat")),
            ("Stem", materials.get("stem_material")),
            ("Insert", materials.get("insert_material")),
            ("Bolts", materials.get("bolts_material")),
            ("Flange Ends", materials.get("flange_ends")),
        ])
        st.markdown("#### Calculated Values")
        _kv_table([
            ("Bore Diameter (mm)", calc.get("bore_diameter_mm")),
            ("Face to Face (mm)", calc.get("face_to_face_mm")),
            ("Body Wall Thickness (mm) — demo", calc.get("body_wall_thickness_mm")),
        ])

# ---------------------- DC001: summarize + pretty render ----------------------
def _dc001_summarize(data: dict) -> dict:
    base = data.get("base", {}) or {}
    ins  = data.get("inputs", {}) or {}
    comp = data.get("computed", {}) or {}

    def g(key, default=None):
        if key in data:
            return data.get(key)
        return default

    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "P_base_MPa":        base.get("operating_pressure_mpa"),
        # inputs
        "Dm_mm":             ins.get("Dm_mm", g("Dm")),
        "c1_N_per_mm":       ins.get("c1_N_per_mm", g("c1")),
        "z":                 ins.get("z", g("z")),
        "P_N":               ins.get("P_N", g("P")),
        "f_mm":              ins.get("f_mm", g("f")),
        "Nma":               ins.get("Nma", g("Nma")),
        "material":          ins.get("material", g("Material")),
        "Y_max_MPa":         ins.get("Y_max_MPa", g("Y_max")),
        "De_mm":             ins.get("De_mm", g("De")),
        "Di_mm":             ins.get("Di_mm", g("Di")),
        "Dc_mm":             ins.get("Dc_mm", g("Dc")),
        "Pa_MPa":            ins.get("Pa_MPa", g("Pa")),
        # computed
        "Fmt_N":                 comp.get("Fmt_N", g("Fmt")),
        "Nm":                    comp.get("Nm", g("Nm")),
        "Pr_N":                  comp.get("Pr_N", g("Pr")),
        "Nmr":                   comp.get("Nmr", g("Nmr")),
        "Fmr_N":                 comp.get("Fmr_N", g("Fmr")),
        "C1_effective_N_per_mm": comp.get("C1_effective_N_per_mm", g("C1effective")),
        "spring_check":          comp.get("spring_check", g("spring_check")),
        "Dcs_mm":                comp.get("Dcs_mm", g("Dcs")),
        "F_N":                   comp.get("F_N", g("F")),
        "Q_MPa":                 comp.get("Q_MPa", g("Q")),
        "result":                comp.get("result", g("result")),
    }

def _dc001_render_pretty(data: Dict[str, Any]):
    s = _dc001_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("P (base) [MPa]",    s.get("P_base_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("#### Spring Load & Count")
        _kv_table([
            ("Seat insert medium dia. Dm [mm]", s.get("Dm_mm")),
            ("c1 [N/mm]", s.get("c1_N_per_mm")),
            ("z [-]", s.get("z")),
            ("Fmt [N]", s.get("Fmt_N")),
            ("Load at theoric packing P [N]", s.get("P_N")),
            ("f [mm]", s.get("f_mm")),
            ("Nma [-]", s.get("Nma")),
        ])
        st.markdown("#### Spring Check")
        _kv_table([
            ("Pr [N]", s.get("Pr_N")),
            ("Fmr [N]", s.get("Fmr_N")),
            ("C1 effective [N/mm]", s.get("C1_effective_N_per_mm")),
            ("Check", s.get("spring_check")),
        ])

    with col2:
        st.markdown("#### Material & Limits")
        _kv_table([
            ("Material", s.get("material")),
            ("Y max [MPa]", s.get("Y_max_MPa")),
        ])
        st.markdown("#### Geometry & Validation")
        _kv_table([
            ("De [mm]", s.get("De_mm")),
            ("Di [mm]", s.get("Di_mm")),
            ("Dcs [mm]", s.get("Dcs_mm")),
            ("Dc [mm]", s.get("Dc_mm")),
            ("Pa [MPa]", s.get("Pa_MPa")),
            ("F [N]", s.get("F_N")),
            ("Q [MPa]", s.get("Q_MPa")),
            ("Result", s.get("result")),
        ])

# ---------------------- DC001A: summarize + pretty render ----------------------
def _dc001a_summarize(data: dict) -> dict:
    base = data.get("base", {}) or {}
    ins  = data.get("inputs", {}) or {}
    comp = data.get("computed", {}) or {}

    return {
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),
        "source_dc001_id":   base.get("source_dc001_id"),
        "source_dc001_name": base.get("source_dc001_name"),

        "Dc_mm":             ins.get("Dc_mm_from_dc001_Dm"),
        "Dts_mm":            ins.get("Dts_mm_from_dc001_Dc"),

        "SR_N":              comp.get("SR_N"),
        "F_molle_N":         comp.get("F_molle_N"),
        "verdict":           comp.get("verdict"),
    }

def _dc001a_render_pretty(data: Dict[str, Any]):
    s = _dc001a_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    st.markdown("#### Sourced from DC001")
    _kv_table([
        ("Source DC001 name", s.get("source_dc001_name")),
        ("Source DC001 ID",   s.get("source_dc001_id")),
        ("Dc [mm] (Dm from DC001)", s.get("Dc_mm")),
        ("Dts [mm] (Dc from DC001)", s.get("Dts_mm")),
    ])

    st.markdown("#### Result")
    _kv_table([
        ("SR [N] (F from DC001)", s.get("SR_N")),
        ("F_molle [N] (Pr from DC001)", s.get("F_molle_N")),
        ("Verdict", s.get("verdict")),
    ])

# ---------------------- DC002: summarize + pretty render ----------------------
def _dc002_summarize(meta: Dict[str, Any]) -> Dict[str, Any]:
    d = (meta.get("data") or {})
    base = d.get("base") or {}
    ins  = d.get("inputs") or {}
    comp = d.get("computed") or {}

    return {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),

        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),

        "G_mm":              ins.get("G_mm"),
        "Pa_MPa":            ins.get("Pa_MPa"),
        "Pe_MPa":            ins.get("Pe_MPa"),
        "bolt_material":     ins.get("bolt_material"),
        "n":                 ins.get("n"),
        "bolt_size":         ins.get("bolt_size"),

        "S_MPa":             comp.get("S_MPa"),
        "H_N":               comp.get("H_N"),
        "Wm1_N":             comp.get("Wm1_N"),
        "Am_mm2":            comp.get("Am_mm2"),
        "a_req_each_mm2":    comp.get("a_req_each_mm2"),
        "a_mm2":             comp.get("a_mm2"),
        "Ab_mm2":            comp.get("Ab_mm2"),
        "Sa_eff_MPa":        comp.get("Sa_eff_MPa"),
        "verdict":           comp.get("verdict"),
    }

def _dc002_render_pretty(meta: Dict[str, Any]):
    s = _dc002_summarize(meta)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Gasket tight diameter G [mm]", s.get("G_mm")),
            ("Design pressure Pa [MPa]", s.get("Pa_MPa")),
            ("Pressure rating Pe [MPa]", s.get("Pe_MPa")),
            ("Bolt material", s.get("bolt_material")),
            ("Bolts number n", s.get("n")),
            ("Bolt size", s.get("bolt_size")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Allowable bolt stress S [MPa]", s.get("S_MPa")),
            ("Total hydrostatic end force H [N]", s.get("H_N")),
            ("Minimum required bolt load Wm1 [N]", s.get("Wm1_N")),
            ("Total required area Am [mm²]", s.get("Am_mm2")),
            ("Req. area per bolt a' [mm²]", s.get("a_req_each_mm2")),
            ("Actual area per bolt a [mm²]", s.get("a_mm2")),
            ("Total area Ab [mm²]", s.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]", s.get("Sa_eff_MPa")),
            ("Check", s.get("verdict")),
        ])

# ---------------------- DC002A: summarize + pretty render ----------------------
def _dc002a_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),
        # inputs
        "G_mm":              ins.get("G_mm"),
        "Pa_test_MPa":       ins.get("Pa_test_MPa"),
        "Pe_MPa":            ins.get("Pe_MPa"),
        "bolt_material":     ins.get("bolt_material"),
        "Syb_MPa":           ins.get("Syb_MPa"),
        "n":                 ins.get("n"),
        "bolt_size":         ins.get("bolt_size"),
        # computed
        "S_MPa":             comp.get("S_MPa"),
        "H_N":               comp.get("H_N"),
        "Wm1_N":             comp.get("Wm1_N"),
        "Am_mm2":            comp.get("Am_mm2"),
        "a_req_each_mm2":    comp.get("a_req_each_mm2"),
        "a_mm2":             comp.get("a_mm2"),
        "Ab_mm2":            comp.get("Ab_mm2"),
        "Sa_eff_MPa":        comp.get("Sa_eff_MPa"),
        "verdict":           comp.get("verdict"),
    }

def _dc002a_render_pretty(data: Dict[str, Any]):
    s = _dc002a_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs (Test condition)")
        _kv_table([
            ("G [mm]", s.get("G_mm")),
            ("Pa_test [MPa]", s.get("Pa_test_MPa")),
            ("Pe [MPa]", s.get("Pe_MPa")),
            ("Bolt material", s.get("bolt_material")),
            ("Syb [MPa]", s.get("Syb_MPa")),
            ("Bolts number n", s.get("n")),
            ("Bolt size", s.get("bolt_size")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("S [MPa] (0.83×Syb)", s.get("S_MPa")),
            ("H [N]", s.get("H_N")),
            ("Wm1 [N]", s.get("Wm1_N")),
            ("Am [mm²]", s.get("Am_mm2")),
            ("a' each req. [mm²]", s.get("a_req_each_mm2")),
            ("a actual [mm²]", s.get("a_mm2")),
            ("Ab [mm²]", s.get("Ab_mm2")),
            ("Sa_eff [MPa]", s.get("Sa_eff_MPa")),
            ("Check", s.get("verdict")),
        ])

# ---------------------- DC003: summarize + pretty render ----------------------
def _dc003_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}
    return {
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),

        "P_MPa":             ins.get("P_MPa", data.get("P_MPa")),
        "Dt_mm":             ins.get("Dt_mm", data.get("Dt_mm")),
        "Db_mm":             ins.get("Db_mm", data.get("Db_mm")),
        "Hb_mm":             ins.get("Hb_mm", data.get("Hb_mm")),
        "MABS_MPa":          ins.get("MABS_MPa", data.get("MABS_MPa")),

        "Sb_mm2":            comp.get("Sb_mm2", data.get("Sb_mm2")),
        "BBS_MPa":           comp.get("BBS_MPa", data.get("BBS_MPa")),
        "verdict":           comp.get("verdict", data.get("verdict")),
    }

def _dc003_render_pretty(data: Dict[str, Any]):
    s = _dc003_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Max rating pressure P [MPa]", s.get("P_MPa")),
            ("Seat seal diameter Dt [mm]", s.get("Dt_mm")),
            ("Bearing diameter Db [mm]", s.get("Db_mm")),
            ("Bearing length Hb [mm]", s.get("Hb_mm")),
            ("Max allowable bearing stress MABS [MPa]", s.get("MABS_MPa")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Design bearing surface Sb [mm²]", s.get("Sb_mm2")),
            ("Bearing stress BBS [MPa]", s.get("BBS_MPa")),
            ("Check", s.get("verdict")),
        ])

# ---------------------- DC004: summarize + pretty render ----------------------
def _dc004_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    thickness_keys = [
        "t_req_mm", "t_min_mm", "t_seat_mm", "seat_thickness_mm",
        "thickness_mm", "t_proposed_mm"
    ]
    t_req = next((comp.get(k) for k in thickness_keys if k in comp), None)

    return {
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),

        "material":          ins.get("material"),
        "geometry_hint":     ins.get("geometry") or ins.get("geom") or None,

        "thickness_mm":      t_req,
        "verdict":           comp.get("verdict"),
    }

def _dc004_render_pretty(data: Dict[str, Any]):
    s = _dc004_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs (key fields)")
        _kv_table([
            ("Material", s.get("material")),
            ("Geometry", s.get("geometry_hint")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Seat thickness [mm] (computed)", s.get("thickness_mm")),
            ("Check", s.get("verdict")),
        ])

# ---------------------- DC005: summarize + pretty render ----------------------
def _dc005_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    def pick(d, key): return d.get(key, data.get(key))

    return {
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),

        # Inputs
        "G_mm":              pick(ins, "G_mm"),
        "Gstem_mm":          pick(ins, "Gstem_mm"),
        "Pa_MPa":            pick(ins, "Pa_MPa"),
        "Pe_MPa":            pick(ins, "Pe_MPa"),
        "bolt_material":     pick(ins, "material") or pick(ins, "bolt_material"),
        "S_MPa":             pick(ins, "S_MPa"),

        # Computed
        "ring_area_mm2":     pick(comp, "ring_area_mm2"),
        "H_N":               pick(comp, "H_N"),
        "Wm1_N":             pick(comp, "Wm1_N"),
        "Am_mm2":            pick(comp, "Am_mm2"),
        "n":                 pick(comp, "n") or pick(ins, "n"),
        "a_req_each_mm2":    pick(comp, "a_req_each_mm2"),
        "bolt_size":         pick(comp, "bolt_size") or pick(ins, "bolt_size"),
        "a_mm2":             pick(comp, "a_mm2"),
        "Ab_mm2":            pick(comp, "Ab_mm2"),
        "Sa_eff_MPa":        pick(comp, "Sa_eff_MPa"),
        "verdict":           pick(comp, "verdict"),
    }

def _dc005_render_pretty(data: Dict[str, Any]):
    s = _dc005_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("G [mm]", s.get("G_mm")),
            ("Gstem [mm]", s.get("Gstem_mm")),
            ("Pa [MPa]", s.get("Pa_MPa")),
            ("Pe [MPa]", s.get("Pe_MPa")),
            ("Bolt material", s.get("bolt_material")),
            ("Allowable S [MPa]", s.get("S_MPa")),
            ("Bolts number n", s.get("n")),
            ("Bolt size", s.get("bolt_size")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Ring area [mm²]", s.get("ring_area_mm2")),
            ("Hydrostatic end force H [N]", s.get("H_N")),
            ("Wm1 [N]", s.get("Wm1_N")),
            ("Total required area Am [mm²]", s.get("Am_mm2")),
            ("Req. area per bolt a' [mm²]", s.get("a_req_each_mm2")),
            ("Actual area per bolt a [mm²]", s.get("a_mm2")),
            ("Total area Ab [mm²]", s.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]", s.get("Sa_eff_MPa")),
            ("Check", s.get("verdict")),
        ])

# ───────────────────────── DC005A: FULL SUMMARY ─────────────────────────

def _dc005a_summarize(data: dict) -> dict:
    """
    Return a flat dict with every field you save in page_dc005a.py:
      Base:    valve_design_id/valve_design_name/nps_in/asme_class/bore_diameter_mm/operating_pressure_mpa
      Inputs:  G_mm/Gstem_mm/Pa_test_MPa/Pe_MPa/material/Syb_MPa/S_MPa/n/bolt_size/a_mm2
      Computed:ring_area_mm2/H_N/Wm1_N/Am_mm2/a_req_each_mm2/Ab_mm2/Sa_eff_MPa/verdict
    """
    base = (data.get("base") or {})
    ins  = (data.get("inputs") or {})
    comp = (data.get("computed") or {})

    return {
        # Base (from Valve Data)
        "valve_design_id":          base.get("valve_design_id"),
        "valve_design_name":        base.get("valve_design_name"),
        "nps_in":                   base.get("nps_in"),
        "asme_class":               base.get("asme_class"),
        "bore_diameter_mm":         base.get("bore_diameter_mm"),
        "operating_pressure_mpa":   base.get("operating_pressure_mpa"),

        # Inputs
        "G_mm":                     ins.get("G_mm"),
        "Gstem_mm":                 ins.get("Gstem_mm"),
        "Pa_test_MPa":              ins.get("Pa_test_MPa"),
        "Pe_MPa":                   ins.get("Pe_MPa"),
        "material":                 ins.get("material"),
        "Syb_MPa":                  ins.get("Syb_MPa"),
        "S_MPa":                    ins.get("S_MPa"),
        "n":                        ins.get("n"),
        "bolt_size":                ins.get("bolt_size"),
        "a_mm2":                    ins.get("a_mm2"),

        # Computed
        "ring_area_mm2":            comp.get("ring_area_mm2"),
        "H_N":                      comp.get("H_N"),
        "Wm1_N":                    comp.get("Wm1_N"),
        "Am_mm2":                   comp.get("Am_mm2"),
        "a_req_each_mm2":           comp.get("a_req_each_mm2"),
        "Ab_mm2":                   comp.get("Ab_mm2"),
        "Sa_eff_MPa":               comp.get("Sa_eff_MPa"),
        "verdict":                  comp.get("verdict"),
    }


def _dc005a_render_pretty(data: Dict[str, Any]):
    s = _dc005a_summarize(data)

    # Base block
    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name",           s.get("valve_design_name")),
        ("Valve design ID",             s.get("valve_design_id")),
        ("NPS [in]",                    s.get("nps_in")),
        ("ASME Class",                  s.get("asme_class")),
        ("Bore (base) [mm]",            s.get("bore_diameter_mm")),
        ("Po (base) [MPa]",             s.get("operating_pressure_mpa")),
    ])

    # Inputs / Computed split
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("G [mm]",                           s.get("G_mm")),
            ("Gstem [mm]",                       s.get("Gstem_mm")),
            ("Pa_test [MPa]",                    s.get("Pa_test_MPa")),
            ("Pe [MPa]",                         s.get("Pe_MPa")),
            ("Bolt material",                    s.get("material")),
            ("Syb (yield) [MPa]",                s.get("Syb_MPa")),
            ("S (allowable, test) [MPa]",        s.get("S_MPa")),
            ("Bolts number n",                   s.get("n")),
            ("Bolt size",                        s.get("bolt_size")),
            ("a (actual per bolt) [mm²]",        s.get("a_mm2")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Ring area [mm²]",                  s.get("ring_area_mm2")),
            ("Hydrostatic end force H [N]",      s.get("H_N")),
            ("Wm1 [N]",                          s.get("Wm1_N")),
            ("Total required area Am [mm²]",     s.get("Am_mm2")),
            ("Required per-bolt a' [mm²]",       s.get("a_req_each_mm2")),
            ("Total area Ab [mm²]",              s.get("Ab_mm2")),
            ("Actual bolt tensile stress Sa_eff [MPa]", s.get("Sa_eff_MPa")),
            ("Check",                             s.get("verdict")),
        ])


# ───────────────────────── DC006: FULL SUMMARY ─────────────────────────

def _dc006_summarize(data: dict) -> dict:
    """
    Flatten every field you persist in page_dc006.py:
      Base:    valve_design_id/valve_design_name/nps_in/asme_class/bore_diameter_mm/operating_pressure_mpa
      Inputs:  Pa_MPa/FT_mm/ISGD_mm/Bcd_mm/ESGD_mm/gasket/m/y_MPa
      Computed:N_mm/b0_mm/b_mm/G_mm/H_N/Hp_N/Wm1_N/Wm2_N/K/Sf1_MPa/Sf2_MPa/Sf_MPa/allow_MPa/verdict
    """
    base = (data.get("base") or {})
    ins  = (data.get("inputs") or {})
    comp = (data.get("computed") or {})

    return {
        # Base (from Valve Data)
        "valve_design_id":        base.get("valve_design_id"),
        "valve_design_name":      base.get("valve_design_name"),
        "nps_in":                 base.get("nps_in"),
        "asme_class":             base.get("asme_class"),
        "bore_diameter_mm":       base.get("bore_diameter_mm"),
        "operating_pressure_mpa": base.get("operating_pressure_mpa"),

        # Inputs
        "Pa_MPa":   ins.get("Pa_MPa"),
        "FT_mm":    ins.get("FT_mm"),
        "ISGD_mm":  ins.get("ISGD_mm"),
        "Bcd_mm":   ins.get("Bcd_mm"),
        "ESGD_mm":  ins.get("ESGD_mm"),
        "gasket":   ins.get("gasket"),
        "m":        ins.get("m"),
        "y_MPa":    ins.get("y_MPa"),

        # Computed
        "N_mm":      comp.get("N_mm"),
        "b0_mm":     comp.get("b0_mm"),
        "b_mm":      comp.get("b_mm"),
        "G_mm":      comp.get("G_mm"),
        "H_N":       comp.get("H_N"),
        "Hp_N":      comp.get("Hp_N"),
        "Wm1_N":     comp.get("Wm1_N"),
        "Wm2_N":     comp.get("Wm2_N"),
        "K":         comp.get("K"),
        "Sf1_MPa":   comp.get("Sf1_MPa"),
        "Sf2_MPa":   comp.get("Sf2_MPa"),
        "Sf_MPa":    comp.get("Sf_MPa"),
        "allow_MPa": comp.get("allow_MPa"),
        "verdict":   comp.get("verdict"),
    }


def _dc006_render_pretty(data: Dict[str, Any]):
    s = _dc006_summarize(data)

    # Base
    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   s.get("operating_pressure_mpa")),
    ])

    # Inputs / Computed
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Pa [MPa]",               s.get("Pa_MPa")),
            ("FT (Flange thickness) [mm]", s.get("FT_mm")),
            ("ISGD [mm]",              s.get("ISGD_mm")),
            ("Bcd [mm]",               s.get("Bcd_mm")),
            ("ESGD [mm]",              s.get("ESGD_mm")),
            ("Gasket",                 s.get("gasket")),
            ("m [-]",                  s.get("m")),
            ("y [MPa]",                s.get("y_MPa")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Gasket width N [mm]",            s.get("N_mm")),
            ("Basic seating width b0 [mm]",    s.get("b0_mm")),
            ("Effective seating width b [mm]", s.get("b_mm")),
            ("Gasket reaction dia G [mm]",     s.get("G_mm")),
            ("Hydrostatic end force H [N]",    s.get("H_N")),
            ("Surface compression Hp [N]",     s.get("Hp_N")),
            ("Bolt load Wm1 [N]",              s.get("Wm1_N")),
            ("Seating load Wm2 [N]",           s.get("Wm2_N")),
            ("K factor [-]",                   s.get("K")),
            ("Sf₁ [MPa]",                      s.get("Sf1_MPa")),
            ("Sf₂ [MPa]",                      s.get("Sf2_MPa")),
            ("Sf (max) [MPa]",                 s.get("Sf_MPa")),
            ("Allowable [MPa]",                s.get("allow_MPa")),
            ("Check",                          s.get("verdict")),
        ])


# ───────────────────────── DC006A: FULL SUMMARY ─────────────────────────

def _dc006a_summarize(data: dict) -> dict:
    """
    Flatten every field you persist in page_dc006a.py:
      Base:    valve_design_id/valve_design_name/nps_in/asme_class/bore_diameter_mm/operating_pressure_mpa
      Inputs:  Pa_test_MPa/FT_mm/ISGD_mm/Bcd_mm/ESGD_mm/gasket/m/y_MPa
      Computed:N_mm/b0_mm/b_mm/G_mm/H_N/Hp_N/Wm1_N/Wm2_N/K/Sf1_MPa/Sf2_MPa/Sf_MPa/allow_MPa/verdict
    """
    base = (data.get("base") or {})
    ins  = (data.get("inputs") or {})
    comp = (data.get("computed") or {})

    return {
        # Base (from Valve Data)
        "valve_design_id":        base.get("valve_design_id"),
        "valve_design_name":      base.get("valve_design_name"),
        "nps_in":                 base.get("nps_in"),
        "asme_class":             base.get("asme_class"),
        "bore_diameter_mm":       base.get("bore_diameter_mm"),
        "operating_pressure_mpa": base.get("operating_pressure_mpa"),

        # Inputs (test condition)
        "Pa_test_MPa": ins.get("Pa_test_MPa"),
        "FT_mm":       ins.get("FT_mm"),
        "ISGD_mm":     ins.get("ISGD_mm"),
        "Bcd_mm":      ins.get("Bcd_mm"),
        "ESGD_mm":     ins.get("ESGD_mm"),
        "gasket":      ins.get("gasket"),
        "m":           ins.get("m"),
        "y_MPa":       ins.get("y_MPa"),

        # Computed
        "N_mm":      comp.get("N_mm"),
        "b0_mm":     comp.get("b0_mm"),
        "b_mm":      comp.get("b_mm"),
        "G_mm":      comp.get("G_mm"),
        "H_N":       comp.get("H_N"),
        "Hp_N":      comp.get("Hp_N"),
        "Wm1_N":     comp.get("Wm1_N"),
        "Wm2_N":     comp.get("Wm2_N"),
        "K":         comp.get("K"),
        "Sf1_MPa":   comp.get("Sf1_MPa"),
        "Sf2_MPa":   comp.get("Sf2_MPa"),
        "Sf_MPa":    comp.get("Sf_MPa"),
        "allow_MPa": comp.get("allow_MPa"),
        "verdict":   comp.get("verdict"),
    }


def _dc006a_render_pretty(data: Dict[str, Any]):
    s = _dc006a_summarize(data)

    # Base
    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   s.get("operating_pressure_mpa")),
    ])

    # Inputs / Computed
    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs (Test condition)")
        _kv_table([
            ("Pa_test [MPa]",             s.get("Pa_test_MPa")),
            ("FT (Flange thickness) [mm]", s.get("FT_mm")),
            ("ISGD [mm]",                 s.get("ISGD_mm")),
            ("Bcd [mm]",                  s.get("Bcd_mm")),
            ("ESGD [mm]",                 s.get("ESGD_mm")),
            ("Gasket",                    s.get("gasket")),
            ("m [-]",                     s.get("m")),
            ("y [MPa]",                   s.get("y_MPa")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Gasket width N [mm]",            s.get("N_mm")),
            ("Basic seating width b0 [mm]",    s.get("b0_mm")),
            ("Effective seating width b [mm]", s.get("b_mm")),
            ("Gasket reaction dia G [mm]",     s.get("G_mm")),
            ("Hydrostatic end force H [N]",    s.get("H_N")),
            ("Surface compression Hp [N]",     s.get("Hp_N")),
            ("Bolt load Wm1 [N]",              s.get("Wm1_N")),
            ("Seating load Wm2 [N]",           s.get("Wm2_N")),
            ("K factor [-]",                   s.get("K")),
            ("Sf₁ [MPa]",                      s.get("Sf1_MPa")),
            ("Sf₂ [MPa]",                      s.get("Sf2_MPa")),
            ("Sf (max) [MPa]",                 s.get("Sf_MPa")),
            ("Allowable [MPa]",                s.get("allow_MPa")),
            ("Check",                          s.get("verdict")),
        ])


# ───────────────────────── DC007-Body: FULL SUMMARY ─────────────────────────

def _dc007_body_summarize(data: dict) -> dict:
    """
    Flatten every field saved by page_dc007_body.py:
      Base:    valve_design_id/valve_design_name/nps_in/asme_class/bore_diameter_mm/operating_pressure_mpa
      Inputs:  nps_in/asme_class/Pa_MPa/T_C/CA_mm/material/body_ID_mm/flow_pass_d_mm/end_flange_ID_mm/t_body_mm/t_body_top_mm
      Computed:t_m_mm/t_m_plus_CA_mm/ok_body_vs_tm/ok_top_vs_tm/ok_body_vs_tmCA/ok_top_vs_tmCA
    """
    base = (data.get("base") or {})
    ins  = (data.get("inputs") or {})
    comp = (data.get("computed") or {})

    return {
        # Base (from Valve Data)
        "valve_design_id":        base.get("valve_design_id"),
        "valve_design_name":      base.get("valve_design_name"),
        "nps_in":                 base.get("nps_in"),
        "asme_class":             base.get("asme_class"),
        "bore_diameter_mm":       base.get("bore_diameter_mm"),
        "operating_pressure_mpa": base.get("operating_pressure_mpa"),

        # Inputs (from DC007 body form)
        "inp_nps_in":           ins.get("nps_in"),
        "inp_asme_class":       ins.get("asme_class"),
        "Pa_MPa":               ins.get("Pa_MPa"),
        "T_C":                  ins.get("T_C"),
        "CA_mm":                ins.get("CA_mm"),
        "material":             ins.get("material"),
        "body_ID_mm":           ins.get("body_ID_mm"),
        "flow_pass_d_mm":       ins.get("flow_pass_d_mm"),
        "end_flange_ID_mm":     ins.get("end_flange_ID_mm"),
        "t_body_mm":            ins.get("t_body_mm"),
        "t_body_top_mm":        ins.get("t_body_top_mm"),

        # Computed / Checks
        "t_m_mm":               comp.get("t_m_mm"),
        "t_m_plus_CA_mm":       comp.get("t_m_plus_CA_mm"),
        "ok_body_vs_tm":        comp.get("ok_body_vs_tm"),
        "ok_top_vs_tm":         comp.get("ok_top_vs_tm"),
        "ok_body_vs_tmCA":      comp.get("ok_body_vs_tmCA"),
        "ok_top_vs_tmCA":       comp.get("ok_top_vs_tmCA"),
    }


def _dc007_body_render_pretty(data: Dict[str, Any]):
    s = _dc007_body_summarize(data)

    # Base
    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   s.get("operating_pressure_mpa")),
    ])

    # Inputs / Computed
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("NPS [in] (input)",            s.get("inp_nps_in")),
            ("ASME Class (input)",          s.get("inp_asme_class")),
            ("Pa [MPa]",                    s.get("Pa_MPa")),
            ("T [°C]",                      s.get("T_C")),
            ("C/A [mm]",                    s.get("CA_mm")),
            ("Material",                    s.get("material")),
            ("Body ID [mm]",                s.get("body_ID_mm")),
            ("Flow passage d [mm]",         s.get("flow_pass_d_mm")),
            ("End flange ID [mm]",          s.get("end_flange_ID_mm")),
            ("t_body [mm]",                 s.get("t_body_mm")),
            ("t_body_top [mm]",             s.get("t_body_top_mm")),
        ])

    with col2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("tₘ [mm] (B16.34 Table)",      s.get("t_m_mm")),
            ("tₘ + C/A [mm]",               s.get("t_m_plus_CA_mm")),
            ("Check body t ≥ tₘ",           "OK" if s.get("ok_body_vs_tm") else "NOT OK"),
            ("Check body/t ≥ tₘ",           "OK" if s.get("ok_top_vs_tm") else "NOT OK"),
            ("Check body t ≥ tₘ + C/A",     "OK" if s.get("ok_body_vs_tmCA") else "NOT OK"),
            ("Check body/t ≥ tₘ + C/A",     "OK" if s.get("ok_top_vs_tmCA") else "NOT OK"),
        ])


# ───────────────────── DC007-Body-Holes: FULL SUMMARY ─────────────────────

def _dc007_body_holes_summarize(data: dict) -> dict:
    """
    Flatten every field saved by page_dc007_body_holes.py:
      Base:    valve_design_id/valve_design_name/nps_in/asme_class/bore_diameter_mm/operating_pressure_mpa
      Inputs:  t_m_mm/f_min_mm/fg_min_mm/e_min_mm
      Computed:req_f_mm/req_fg_mm/req_e_mm/ok_f/ok_fg/ok_e/overall_ok
    """
    base = (data.get("base") or {})
    ins  = (data.get("inputs") or {})
    comp = (data.get("computed") or {})

    return {
        # Base (from Valve Data)
        "valve_design_id":        base.get("valve_design_id"),
        "valve_design_name":      base.get("valve_design_name"),
        "nps_in":                 base.get("nps_in"),
        "asme_class":             base.get("asme_class"),
        "bore_diameter_mm":       base.get("bore_diameter_mm"),
        "operating_pressure_mpa": base.get("operating_pressure_mpa"),

        # Inputs
        "t_m_mm":     ins.get("t_m_mm"),
        "f_min_mm":   ins.get("f_min_mm"),
        "fg_min_mm":  ins.get("fg_min_mm"),
        "e_min_mm":   ins.get("e_min_mm"),

        # Computed / Checks
        "req_f_mm":   comp.get("req_f_mm"),
        "req_fg_mm":  comp.get("req_fg_mm"),
        "req_e_mm":   comp.get("req_e_mm"),
        "ok_f":       comp.get("ok_f"),
        "ok_fg":      comp.get("ok_fg"),
        "ok_e":       comp.get("ok_e"),
        "overall_ok": comp.get("overall_ok"),
    }


def _dc007_body_holes_render_pretty(data: Dict[str, Any]):
    s = _dc007_body_holes_summarize(data)

    # Base
    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   s.get("operating_pressure_mpa")),
    ])

    col1, col2 = st.columns(2, gap="large")

    # Inputs
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("tₘ [mm] (reference)", s.get("t_m_mm")),
            ("f' [mm]",             s.get("f_min_mm")),
            ("f' + g' [mm]",        s.get("fg_min_mm")),
            ("e° [mm]",             s.get("e_min_mm")),
        ])

    # Computed / Checks
    with col2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("Req. f' ≥ 0.25·tₘ [mm]", s.get("req_f_mm")),
            ("Req. f'+g' ≥ tₘ [mm]",   s.get("req_fg_mm")),
            ("Req. e° ≥ 0.25·tₘ [mm]", s.get("req_e_mm")),
            ("Check f'",               "OK" if s.get("ok_f")  else "NOT OK"),
            ("Check f'+g'",            "OK" if s.get("ok_fg") else "NOT OK"),
            ("Check e°",               "OK" if s.get("ok_e")  else "NOT OK"),
            ("Overall",                "ALL REQUIREMENTS MET" if s.get("overall_ok") else "REQUIREMENTS NOT MET"),
        ])


# ───────────────────── DC008: FULL SUMMARY & PRETTY RENDER ─────────────────────

def _dc008_summarize(data: dict) -> dict:
    """
    Matches page_dc008.py payload exactly.

    Base:
      valve_design_id/valve_design_name/nps_in/asme_class/bore_diameter_mm/operating_pressure_mpa
    Inputs:
      Pr_MPa, D_ball_mm, B_mm, alpha_deg, ball_material, Sy_MPa, H_mm
    Computed:
      T_mm, criteria_class_yield, criteria_class_ratio, req_Sy_min, req_DB_min,
      actual_DB, St1a_MPa, allow_23Sy_MPa, check_sy, check_db, verdict
    """
    base = (data.get("base") or {})
    ins  = (data.get("inputs") or {})
    comp = (data.get("computed") or {})

    return {
        # Base (from Valve Data)
        "valve_design_id":        base.get("valve_design_id"),
        "valve_design_name":      base.get("valve_design_name"),
        "nps_in":                 base.get("nps_in"),
        "asme_class":             base.get("asme_class"),
        "bore_diameter_mm":       base.get("bore_diameter_mm"),
        "operating_pressure_mpa": base.get("operating_pressure_mpa"),

        # Inputs
        "Pr_MPa":        ins.get("Pr_MPa"),
        "D_ball_mm":     ins.get("D_ball_mm"),
        "B_mm":          ins.get("B_mm"),
        "alpha_deg":     ins.get("alpha_deg"),
        "ball_material": ins.get("ball_material"),
        "Sy_MPa":        ins.get("Sy_MPa"),
        "H_mm":          ins.get("H_mm"),

        # Computed / Checks
        "T_mm":                 comp.get("T_mm"),
        "criteria_class_yield": comp.get("criteria_class_yield"),
        "criteria_class_ratio": comp.get("criteria_class_ratio"),
        "req_Sy_min":           comp.get("req_Sy_min"),
        "req_DB_min":           comp.get("req_DB_min"),
        "actual_DB":            comp.get("actual_DB"),
        "St1a_MPa":             comp.get("St1a_MPa"),
        "allow_23Sy_MPa":       comp.get("allow_23Sy_MPa"),
        "check_sy":             comp.get("check_sy"),
        "check_db":             comp.get("check_db"),
        "verdict":              comp.get("verdict"),
    }


def _dc008_render_pretty(data: Dict[str, Any]):
    s = _dc008_summarize(data)

    # Base
    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_diameter_mm")),
        ("Po (base) [MPa]",   s.get("operating_pressure_mpa")),
    ])

    col1, col2 = st.columns(2, gap="large")

    # Inputs
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Pr [MPa]",        s.get("Pr_MPa")),
            ("D ball [mm]",     s.get("D_ball_mm")),
            ("B [mm]",          s.get("B_mm")),
            ("α [deg]",         s.get("alpha_deg")),
            ("Ball material",   s.get("ball_material")),
            ("Sy [MPa]",        s.get("Sy_MPa")),
            ("H [mm]",          s.get("H_mm")),
        ])

    # Computed / Checks
    with col2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("T [mm]",                 s.get("T_mm")),
            ("Class (yield)",          s.get("criteria_class_yield")),
            ("Class (ratio)",          s.get("criteria_class_ratio")),
            ("Req. Sy min [MPa]",      s.get("req_Sy_min")),
            ("Req. D/B min",           s.get("req_DB_min")),
            ("Actual D/B",             s.get("actual_DB")),
            ("St1a [MPa]",             s.get("St1a_MPa")),
            ("Allow 2/3 Sy [MPa]",     s.get("allow_23Sy_MPa")),
            ("Check Sy",               "OK" if s.get("check_sy") else "NOT OK"),
            ("Check D/B",              "OK" if s.get("check_db") else "NOT OK"),
            ("Verdict",                s.get("verdict")),
        ])

        
# ---------------------- DC010: summarize + pretty render (NEW) ----------------------
def _dc010_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),
        # inputs
        "Po_MPa_in":         ins.get("Po_MPa"),
        "D_mm":              ins.get("D_mm"),
        "Dc_mm":             ins.get("Dc_mm"),
        "b1_mm":             ins.get("b1_mm"),
        "Dm_mm":             ins.get("Dm_mm"),
        "Db_mm":             ins.get("Db_mm"),
        "Pr_N":              ins.get("Pr_N"),
        "Nma":               ins.get("Nma"),
        "f1":                ins.get("f1"),
        "f2":                ins.get("f2"),
        # computed
        "Fb_N":              comp.get("Fb_N"),
        "Mtb_Nm":            comp.get("Mtb_Nm"),
        "Fm_N":              comp.get("Fm_N"),
        "Mtm_Nm":            comp.get("Mtm_Nm"),
        "Fi_N":              comp.get("Fi_N"),
        "Mti_Nm":            comp.get("Mti_Nm"),
        "Tbb1_Nm":           comp.get("Tbb1_Nm"),
    }

def _dc010_render_pretty(data: Dict[str, Any]):
    s = _dc010_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Po [MPa]", s.get("Po_MPa_in")),
            ("D [mm]", s.get("D_mm")),
            ("Dc [mm]", s.get("Dc_mm")),
            ("b1 [mm]", s.get("b1_mm")),
            ("Dm [mm]", s.get("Dm_mm")),
            ("Db [mm]", s.get("Db_mm")),
            ("Pr [N]", s.get("Pr_N")),
            ("Nma [-]", s.get("Nma")),
            ("f1 [-]", s.get("f1")),
            ("f2 [-]", s.get("f2")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("Fb [N]", s.get("Fb_N")),
            ("Mtb [N·m]", s.get("Mtb_Nm")),
            ("Fm [N]", s.get("Fm_N")),
            ("Mtm [N·m]", s.get("Mtm_Nm")),
            ("Fi [N]", s.get("Fi_N")),
            ("Mti [N·m]", s.get("Mti_Nm")),
            ("Tbb1 [N·m]", s.get("Tbb1_Nm")),
        ])

# ---------------------- DC011: summarize + pretty render (NEW) ----------------------
def _dc011_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),
        # inputs
        "inner_bore_mm":     ins.get("inner_bore_mm"),
        "seat_bore_mm":      ins.get("seat_bore_mm"),
        "beta":              ins.get("beta"),
        "theta_deg":         ins.get("theta_deg"),
        "theta_rad":         ins.get("theta_rad"),
        "taper_len_mm":      ins.get("taper_len_mm"),
        "dn_choice_in":      ins.get("dn_choice_in"),
        "ft":                ins.get("ft"),
        # computed
        "K1":                comp.get("K1"),
        "K2":                comp.get("K2"),
        "K_local":           comp.get("K_local"),
        "K_fric":            comp.get("K_fric"),
        "K_total":           comp.get("K_total"),
        "Cv":                comp.get("Cv_gpm_at_1psi"),
    }

def _dc011_render_pretty(data: Dict[str, Any]):
    s = _dc011_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Inner bore [mm]", s.get("inner_bore_mm")),
            ("Seat bore [mm]", s.get("seat_bore_mm")),
            ("β [-]", s.get("beta")),
            ("θ [deg]", s.get("theta_deg")),
            ("θ [rad]", s.get("theta_rad")),
            ("Taper L [mm]", s.get("taper_len_mm")),
            ("DN [in]", s.get("dn_choice_in")),
            ("fₜ [-]", s.get("ft")),
        ])
    with col2:
        st.markdown("#### Computed")
        _kv_table([
            ("K1 [-]", s.get("K1")),
            ("K2 [-]", s.get("K2")),
            ("K_local [-]", s.get("K_local")),
            ("K_fric [-]", s.get("K_fric")),
            ("K_total [-]", s.get("K_total")),
            ("Cv (gpm @ 1 psi)", s.get("Cv")),
        ])

# ---------------------- DC012: summarize + pretty render (NEW) ----------------------
def _dc012_summarize(data: dict) -> dict:
    base = (data.get("base") or {}) if isinstance(data.get("base"), dict) else {}
    ins  = (data.get("inputs") or {}) if isinstance(data.get("inputs"), dict) else {}
    comp = (data.get("computed") or {}) if isinstance(data.get("computed"), dict) else {}

    # page_dc012 stores results in st.session_state["dc012"] with keys like Es_MPa, Ec_ok, etc.
    # When you build the page's save, map those into inputs/computed accordingly.
    return {
        # base
        "valve_design_id":   base.get("valve_design_id"),
        "valve_design_name": base.get("valve_design_name"),
        "nps_in":            base.get("nps_in"),
        "asme_class":        base.get("asme_class"),
        "bore_mm":           base.get("bore_diameter_mm"),
        "Po_MPa":            base.get("operating_pressure_mpa"),
        # inputs
        "P_kg":              ins.get("P_kg"),
        "thread":            ins.get("thread"),
        "A_mm2":             ins.get("A_mm2"),
        "N":                 ins.get("N"),
        "angle":             ins.get("angle"),
        "F_rated_kg":        ins.get("F_rated_kg"),
        "material":          ins.get("material"),
        # computed
        "per_bolt_kg":       comp.get("per_bolt_kg"),
        "Ec_ok":             comp.get("Ec_ok"),
        "Es_MPa":            comp.get("Es_MPa"),
        "allowable_MPa":     comp.get("allowable_MPa"),
        "stress_ok":         comp.get("stress_ok"),
    }

def _dc012_render_pretty(data: Dict[str, Any]):
    s = _dc012_summarize(data)

    st.markdown("#### Base (from Valve Data)")
    _kv_table([
        ("Valve design name", s.get("valve_design_name")),
        ("Valve design ID",   s.get("valve_design_id")),
        ("NPS [in]",          s.get("nps_in")),
        ("ASME Class",        s.get("asme_class")),
        ("Bore (base) [mm]",  s.get("bore_mm")),
        ("Po (base) [MPa]",   s.get("Po_MPa")),
    ])

    col1, col2 = st.columns(2, gap="large")
    with col1:
        st.markdown("#### Inputs")
        _kv_table([
            ("Valve weight P [kg]", s.get("P_kg")),
            ("Thread", s.get("thread")),
            ("Area A [mm²]", s.get("A_mm2")),
            ("Quantity N [-]", s.get("N")),
            ("Angle", s.get("angle")),
            ("Rated load F [kg]", s.get("F_rated_kg")),
            ("Material", s.get("material")),
        ])
    with col2:
        st.markdown("#### Computed / Checks")
        _kv_table([
            ("Per-bolt weight [kg]", s.get("per_bolt_kg")),
            ("UNI-ISO Load Check (Ec)", "OK" if s.get("Ec_ok") else "NOT OK"),
            ("Es [MPa]", s.get("Es_MPa")),
            ("Allowable [MPa]", s.get("allowable_MPa")),
            ("Final Check (Es ≤ Allowable)", "OK" if s.get("stress_ok") else "NOT OK"),
        ])

# ---------------------- Helpers for unified "All Items Summary" ----------------------
def _norm_list_rows(rows: Any) -> List[Dict[str, Any]]:
    """
    Normalize list_* rows into dicts with id, name, created_at, updated_at.
    Accepts tuples/lists/dicts/strings as already handled elsewhere.
    """
    norm: List[Dict[str, Any]] = []
    if not rows:
        return norm
    for r in rows:
        rid, nm, ca, ua = None, "Untitled", None, None
        if isinstance(r, (list, tuple)):
            if len(r) >= 2:
                rid, nm = r[0], r[1] or "Untitled"
            if len(r) >= 3:
                ca = r[2]
            if len(r) >= 4:
                ua = r[3]
        elif isinstance(r, dict):
            rid = r.get("id") or r.get("calc_id") or r.get("id_") or r.get("design_id")
            nm  = r.get("name") or r.get("title") or "Untitled"
            ca  = r.get("created_at")
            ua  = r.get("updated_at")
        elif isinstance(r, str):
            rid, nm = r, "Untitled"
        if rid:
            norm.append({
                "id": str(rid),
                "name": str(nm),
                "created_at": ca,
                "updated_at": ua,
            })
    return norm

def _kv_str(pairs: List[Tuple[str, Any]], digits: int = 2) -> str:
    """
    Turn a small set of key-values into a concise 'k=v, k=v' string for the unified table.
    """
    buf = []
    for k, v in pairs:
        if v in (None, "", "None"):
            continue
        if isinstance(v, (int, float)) or (
            isinstance(v, str) and v.replace(".", "", 1).replace("-", "", 1).isdigit()
        ):
            buf.append(f"{k}={_fmt_num(v, digits)}")
        else:
            buf.append(f"{k}={v}")
    return ", ".join(buf)

# ---------------------- PAGE ----------------------
def render_my_library():
    require_role(["user", "superadmin"])
    user = current_user()
    if not user:
        st.stop()

    display_name = (f"{user.get('first_name','').strip()} {user.get('last_name','').strip()}").strip() or user.get("username") or "User"
    email_or_username = user.get("username") or "—"
    st.subheader("My Saved Items")
    st.caption(f"Signed in as **{display_name}** • **{email_or_username}**")

    tabs = st.tabs([
        "By Base (Valve Design)",  # NEW first tab
        "Valve Designs",
        "DC001 Calculations",
        "DC001A Calculations",
        "DC002 Calculations",
        "DC002A Calculations",
        "DC003 Calculations",
        "DC004 Calculations",
        "DC005 Calculations",
        "DC005a Calculations",
        "DC006 Calculations",
        "DC006a Calculations",
        "DC007 Calculations",
        "DC007 body Calculations",
        "DC008 Calculations",
        "DC010 Calculations",      # NEW
        "DC011 Calculations",      # NEW
        "DC012 Calculations",      # NEW
        "All Items Summary",       # NEW unified summary tab
    ])

# ==================== TAB 0: BY BASE (VALVE DESIGN) ====================
    with tabs[0]:
        user_id = user["id"]

        # Collect bases starting from valve designs
        vrows = list_valve_designs(user_id, limit=1000) or []
        bases: Dict[str, Dict[str, Any]] = {}  # valve_design_id -> info

        def _ensure_base(_id: Optional[str], _name: Optional[str]):
            if not _id:
                return
            if _id not in bases:
                bases[_id] = {
                    "valve_design_id": _id,
                    "valve_design_name": _name or "Untitled",
                    "counts": {
                        "valve": 0, "dc001": 0, "dc001a": 0,
                        "dc002": 0, "dc002a": 0,
                        "dc003": 0, "dc004": 0, "dc005": 0, "dc005a": 0,
                        "dc006": 0, "dc006a": 0,
                        "dc007_body": 0, "dc007_body_holes": 0,
                        "dc008": 0,
                        "dc010": 0, "dc011": 0, "dc012": 0,
                    },
                }

        # Seed from valve designs
        for r in vrows:
            rid, nm = None, "Untitled"
            if isinstance(r, (list, tuple)) and len(r) >= 2:
                rid, nm = r[0], r[1] or "Untitled"
            elif isinstance(r, dict):
                rid, nm = r.get("id") or r.get("design_id"), (r.get("name") or "Untitled")
            if rid:
                _ensure_base(str(rid), str(nm))
                bases[str(rid)]["counts"]["valve"] += 1

        # Walk DC001..DC005 and DC010..DC012 saves and attach by base.valve_design_id
        # DC001
        for rid, _nm, *_ in (list_dc001_calcs(user_id, limit=1000) or []):
            rec = get_dc001_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc001"] += 1
        # DC001A
        for rid, _nm, *_ in (list_dc001a_calcs(user_id, limit=1000) or []):
            rec = get_dc001a_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc001a"] += 1
        # DC002
        for rid, _nm, *_ in (list_dc002_calcs(user_id, limit=1000) or []):
            meta = get_dc002_calc_with_meta(rid, user_id) or {}
            data = meta.get("data") or {}
            base = data.get("base") or {}
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc002"] += 1
        # DC002A
        for rid, _nm, *_ in (list_dc002a_calcs(user_id, limit=1000) or []):
            rec = get_dc002a_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc002a"] += 1
        # DC003
        for rid, _nm, *_ in (list_dc003_calcs(user_id, limit=1000) or []):
            rec = get_dc003_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc003"] += 1
        # DC004
        for rid, _nm, *_ in (list_dc004_calcs(user_id, limit=1000) or []):
            rec = get_dc004_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc004"] += 1
        # DC005
        for rid, _nm, *_ in (list_dc005_calcs(user_id, limit=1000) or []):
            rec = get_dc005_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc005"] += 1
        # DC005A
        for rid, _nm, *_ in (list_dc005a_calcs(user_id, limit=1000) or []):
            rec = get_dc005a_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc005a"] += 1
        # DC006
        for rid, _nm, *_ in (list_dc006_calcs(user_id, limit=1000) or []):
            rec = get_dc006_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc006"] += 1
        # DC006A
        for rid, _nm, *_ in (list_dc006a_calcs(user_id, limit=1000) or []):
            rec = get_dc006a_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc006a"] += 1
        # DC007 body
        for rid, _nm, *_ in (list_dc007_body_calcs(user_id, limit=1000) or []):
            rec = get_dc007_body_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc007_body"] += 1
        # DC007 body holes
        for rid, _nm, *_ in (list_dc007_body_holes_calcs(user_id, limit=1000) or []):
            rec = get_dc007_body_holes_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc007_body_holes"] += 1
        # DC008
        for rid, _nm, *_ in (list_dc008_calcs(user_id, limit=1000) or []):
            rec = get_dc008_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc008"] += 1
        # DC010
        for rid, _nm, *_ in (list_dc010_calcs(user_id, limit=1000) or []):
            rec = get_dc010_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc010"] += 1
        # DC011
        for rid, _nm, *_ in (list_dc011_calcs(user_id, limit=1000) or []):
            rec = get_dc011_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc011"] += 1
        # DC012
        for rid, _nm, *_ in (list_dc012_calcs(user_id, limit=1000) or []):
            rec = get_dc012_calc(rid, user_id) or {}
            base = (rec.get("base") or {})
            _ensure_base(base.get("valve_design_id"), base.get("valve_design_name"))
            if base.get("valve_design_id"):
                bases[base["valve_design_id"]]["counts"]["dc012"] += 1

        # Table of bases
        if not bases:
            st.info("No base records yet. Save a Valve design or any calculation first.")
        else:
            rows = []
            for vid, info in bases.items():
                rows.append({
                    "valve_design_id": vid,
                    "valve_design_name": info["valve_design_name"],
                    "Valve": info["counts"]["valve"],
                    "DC001": info["counts"]["dc001"],
                    "DC001A": info["counts"]["dc001a"],
                    "DC002": info["counts"]["dc002"],
                    "DC002A": info["counts"]["dc002a"],
                    "DC003": info["counts"]["dc003"],
                    "DC004": info["counts"]["dc004"],
                    "DC005": info["counts"]["dc005"],
                    "DC005A": info["counts"]["dc005a"],
                    "DC006": info["counts"]["dc006"],
                    "DC006A": info["counts"]["dc006a"],
                    "DC007 (Body)": info["counts"]["dc007_body"],
                    "DC007 (Holes)": info["counts"]["dc007_body_holes"],
                    "DC008": info["counts"]["dc008"],
                    "DC010": info["counts"]["dc010"],
                    "DC011": info["counts"]["dc011"],
                    "DC012": info["counts"]["dc012"],
                })
            df = pd.DataFrame(
                rows,
                columns=[
                    "valve_design_id","valve_design_name","Valve",
                    "DC001","DC001A","DC002","DC002A","DC003","DC004","DC005","DC005A",
                    "DC006","DC006A","DC007 (Body)","DC007 (Holes)","DC008",
                    "DC010","DC011","DC012"
                ]
            )
            st.dataframe(df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Inspect one base and its related summaries")

            labels = ["-- select --"] + [f"{r['valve_design_name']} ({r['valve_design_id'][:8]}…)" for r in rows]
            pick = st.selectbox("Pick a Base (valve design)", labels, key="lib_base_pick")
            if pick != "-- select --":
                label_to_id = {f"{r['valve_design_name']} ({r['valve_design_id'][:8]}…)": r["valve_design_id"] for r in rows}
                sel_vid = label_to_id[pick]

                # Base section
                st.markdown("#### Base (Valve Design)")
                try:
                    vdata = get_valve_design(sel_vid, user_id)
                except Exception:
                    vdata = None
                if vdata:
                    _valve_render_pretty(vdata)
                else:
                    st.info("No Valve design record found for this base id (may come only from calcs).")

                # DC001 list for this base
                st.markdown("---")
                st.markdown("#### DC001 linked to this base")
                dc001_items = []
                for rid, nm, *_ in (list_dc001_calcs(user_id, limit=1000) or []):
                    rec = get_dc001_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc001_items.append((rid, nm))
                if not dc001_items:
                    st.caption("No DC001 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc001_items]
                    sel = st.selectbox("Pick a DC001 save", lbls, key=f"lib_base_dc001_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc001_items}[sel]
                        _dc001_render_pretty(get_dc001_calc(rid, user_id) or {})

                # DC001A list
                st.markdown("---")
                st.markdown("#### DC001A linked to this base")
                dc001a_items = []
                for rid, nm, *_ in (list_dc001a_calcs(user_id, limit=1000) or []):
                    rec = get_dc001a_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc001a_items.append((rid, nm))
                if not dc001a_items:
                    st.caption("No DC001A saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc001a_items]
                    sel = st.selectbox("Pick a DC001A save", lbls, key=f"lib_base_dc001a_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc001a_items}[sel]
                        _dc001a_render_pretty(get_dc001a_calc(rid, user_id) or {})

                # DC002 list
                st.markdown("---")
                st.markdown("#### DC002 linked to this base")
                dc002_items = []
                for rid, nm, *_ in (list_dc002_calcs(user_id, limit=1000) or []):
                    meta = get_dc002_calc_with_meta(rid, user_id) or {}
                    base = (meta.get("data") or {}).get("base") or {}
                    if base.get("valve_design_id") == sel_vid:
                        dc002_items.append((rid, meta.get("name") or nm))
                if not dc002_items:
                    st.caption("No DC002 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc002_items]
                    sel = st.selectbox("Pick a DC002 save", lbls, key=f"lib_base_dc002_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc002_items}[sel]
                        _dc002_render_pretty(get_dc002_calc_with_meta(rid, user_id) or {})

                # DC002A list
                st.markdown("---")
                st.markdown("#### DC002A linked to this base")
                dc002a_items = []
                for rid, nm, *_ in (list_dc002a_calcs(user_id, limit=1000) or []):
                    rec = get_dc002a_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc002a_items.append((rid, nm))
                if not dc002a_items:
                    st.caption("No DC002A saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc002a_items]
                    sel = st.selectbox("Pick a DC002A save", lbls, key=f"lib_base_dc002a_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc002a_items}[sel]
                        _dc002a_render_pretty(get_dc002a_calc(rid, user_id) or {})

                # DC003 list
                st.markdown("---")
                st.markdown("#### DC003 linked to this base")
                dc003_items = []
                for rid, nm, *_ in (list_dc003_calcs(user_id, limit=1000) or []):
                    rec = get_dc003_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc003_items.append((rid, nm))
                if not dc003_items:
                    st.caption("No DC003 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc003_items]
                    sel = st.selectbox("Pick a DC003 save", lbls, key=f"lib_base_dc003_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc003_items}[sel]
                        _dc003_render_pretty(get_dc003_calc(rid, user_id) or {})

                # DC004 list
                st.markdown("---")
                st.markdown("#### DC004 linked to this base")
                dc004_items = []
                for rid, nm, *_ in (list_dc004_calcs(user_id, limit=1000) or []):
                    rec = get_dc004_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc004_items.append((rid, nm))
                if not dc004_items:
                    st.caption("No DC004 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc004_items]
                    sel = st.selectbox("Pick a DC004 save", lbls, key=f"lib_base_dc004_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc004_items}[sel]
                        _dc004_render_pretty(get_dc004_calc(rid, user_id) or {})

                # DC005 list
                st.markdown("---")
                st.markdown("#### DC005 linked to this base")
                dc005_items = []
                for rid, nm, *_ in (list_dc005_calcs(user_id, limit=1000) or []):
                    rec = get_dc005_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc005_items.append((rid, nm))
                if not dc005_items:
                    st.caption("No DC005 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc005_items]
                    sel = st.selectbox("Pick a DC005 save", lbls, key=f"lib_base_dc005_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc005_items}[sel]
                        _dc005_render_pretty(get_dc005_calc(rid, user_id) or {})

                # DC005A list
                st.markdown("---")
                st.markdown("#### DC005A linked to this base")
                dc005a_items = []
                for rid, nm, *_ in (list_dc005a_calcs(user_id, limit=1000) or []):
                    rec = get_dc005a_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc005a_items.append((rid, nm))
                if not dc005a_items:
                    st.caption("No DC005A saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc005a_items]
                    sel = st.selectbox("Pick a DC005A save", lbls, key=f"lib_base_dc005a_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc005a_items}[sel]
                        _dc005a_render_pretty(get_dc005a_calc(rid, user_id) or {})

                # DC006 list
                st.markdown("---")
                st.markdown("#### DC006 linked to this base")
                dc006_items = []
                for rid, nm, *_ in (list_dc006_calcs(user_id, limit=1000) or []):
                    rec = get_dc006_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc006_items.append((rid, nm))
                if not dc006_items:
                    st.caption("No DC006 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc006_items]
                    sel = st.selectbox("Pick a DC006 save", lbls, key=f"lib_base_dc006_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc006_items}[sel]
                        _dc006_render_pretty(get_dc006_calc(rid, user_id) or {})

                # DC006A list
                st.markdown("---")
                st.markdown("#### DC006A linked to this base")
                dc006a_items = []
                for rid, nm, *_ in (list_dc006a_calcs(user_id, limit=1000) or []):
                    rec = get_dc006a_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc006a_items.append((rid, nm))
                if not dc006a_items:
                    st.caption("No DC006A saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc006a_items]
                    sel = st.selectbox("Pick a DC006A save", lbls, key=f"lib_base_dc006a_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc006a_items}[sel]
                        _dc006a_render_pretty(get_dc006a_calc(rid, user_id) or {})

                # DC007 Body list
                st.markdown("---")
                st.markdown("#### DC007 (Body) linked to this base")
                dc007b_items = []
                for rid, nm, *_ in (list_dc007_body_calcs(user_id, limit=1000) or []):
                    rec = get_dc007_body_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc007b_items.append((rid, nm))
                if not dc007b_items:
                    st.caption("No DC007 (Body) saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc007b_items]
                    sel = st.selectbox("Pick a DC007 (Body) save", lbls, key=f"lib_base_dc007b_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc007b_items}[sel]
                        _dc007_body_render_pretty(get_dc007_body_calc(rid, user_id) or {})

                # DC007 Body Holes list
                st.markdown("---")
                st.markdown("#### DC007 (Holes) linked to this base")
                dc007h_items = []
                for rid, nm, *_ in (list_dc007_body_holes_calcs(user_id, limit=1000) or []):
                    rec = get_dc007_body_holes_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc007h_items.append((rid, nm))
                if not dc007h_items:
                    st.caption("No DC007 (Holes) saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc007h_items]
                    sel = st.selectbox("Pick a DC007 (Holes) save", lbls, key=f"lib_base_dc007h_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc007h_items}[sel]
                        _dc007_body_holes_render_pretty(get_dc007_body_holes_calc(rid, user_id) or {})

                # DC008 list
                st.markdown("---")
                st.markdown("#### DC008 linked to this base")
                dc008_items = []
                for rid, nm, *_ in (list_dc008_calcs(user_id, limit=1000) or []):
                    rec = get_dc008_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc008_items.append((rid, nm))
                if not dc008_items:
                    st.caption("No DC008 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc008_items]
                    sel = st.selectbox("Pick a DC008 save", lbls, key=f"lib_base_dc008_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc008_items}[sel]
                        _dc008_render_pretty(get_dc008_calc(rid, user_id) or {})

                # DC010 list
                st.markdown("---")
                st.markdown("#### DC010 linked to this base")
                dc010_items = []
                for rid, nm, *_ in (list_dc010_calcs(user_id, limit=1000) or []):
                    rec = get_dc010_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc010_items.append((rid, nm))
                if not dc010_items:
                    st.caption("No DC010 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc010_items]
                    sel = st.selectbox("Pick a DC010 save", lbls, key=f"lib_base_dc010_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc010_items}[sel]
                        _dc010_render_pretty(get_dc010_calc(rid, user_id) or {})

                # DC011 list
                st.markdown("---")
                st.markdown("#### DC011 linked to this base")
                dc011_items = []
                for rid, nm, *_ in (list_dc011_calcs(user_id, limit=1000) or []):
                    rec = get_dc011_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc011_items.append((rid, nm))
                if not dc011_items:
                    st.caption("No DC011 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc011_items]
                    sel = st.selectbox("Pick a DC011 save", lbls, key=f"lib_base_dc011_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc011_items}[sel]
                        _dc011_render_pretty(get_dc011_calc(rid, user_id) or {})

                # DC012 list
                st.markdown("---")
                st.markdown("#### DC012 linked to this base")
                dc012_items = []
                for rid, nm, *_ in (list_dc012_calcs(user_id, limit=1000) or []):
                    rec = get_dc012_calc(rid, user_id) or {}
                    base = (rec.get("base") or {})
                    if base.get("valve_design_id") == sel_vid:
                        dc012_items.append((rid, nm))
                if not dc012_items:
                    st.caption("No DC012 saves for this base.")
                else:
                    lbls = ["-- select --"] + [f"{nm} ({rid[:8]}…)" for rid, nm in dc012_items]
                    sel = st.selectbox("Pick a DC012 save", lbls, key=f"lib_base_dc012_{sel_vid}")
                    if sel != "-- select --":
                        rid = {f"{nm} ({rid[:8]}…)": rid for rid, nm in dc012_items}[sel]
                        _dc012_render_pretty(get_dc012_calc(rid, user_id) or {})

    # ==================== TAB 1: VALVE DESIGNS ====================
    with tabs[1]:
        raw_rows = list_valve_designs(user["id"], limit=500)

        if not raw_rows:
            st.info("You haven't saved any **valve designs** yet. Go to **Valve Data** and click **Save to my library**.")
        else:
            # normalize
            norm: List[tuple[str, str]] = []
            created_map: Dict[str, Any] = {}
            updated_map: Dict[str, Any] = {}

            for r in raw_rows:
                rid: Optional[str] = None
                nm: str = "Untitled"
                created = None
                updated = None

                if isinstance(r, (list, tuple)):
                    if len(r) >= 2:
                        rid = str(r[0]) if r[0] is not None else None
                        nm  = str(r[1]) if r[1] is not None else "Untitled"
                    if len(r) >= 3:
                        created = r[2]
                    if len(r) >= 4:
                        updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("design_id")
                    nm  = r.get("name") or "Untitled"
                    created = r.get("created_at")
                    updated = r.get("updated_at")
                    rid = str(rid) if rid is not None else None
                    nm  = str(nm)
                elif isinstance(r, str):
                    rid = r
                    nm  = "Untitled"

                if rid and rid.strip():
                    norm.append((rid.strip(), nm))
                    created_map[rid.strip()] = created
                    updated_map[rid.strip()] = updated

            if not norm:
                st.info("No valid designs found.")
            else:
                summary_records: List[Dict[str, Any]] = []
                for _id, name in norm:
                    data = get_valve_design(_id, user["id"])  # may be None
                    s = _valve_summarize(data or {})
                    summary_records.append({
                        "id": _id,
                        "name": name,
                        "nps_in": s.get("nps_in"),
                        "asme_class": s.get("asme_class"),
                        "bore_mm": s.get("bore_mm"),
                        "f2f_mm": s.get("f2f_mm"),
                        "t_mm": s.get("t_mm"),
                        "created_at": _fmt_ts(created_map.get(_id)),
                        "updated_at": _fmt_ts(updated_map.get(_id)),
                    })

                v_cols = ["id", "name", "nps_in", "asme_class", "bore_mm", "f2f_mm", "t_mm", "created_at", "updated_at"]
                v_df = pd.DataFrame(summary_records, columns=v_cols)
                for c in ["nps_in", "asme_class", "bore_mm", "f2f_mm", "t_mm"]:
                    v_df[c] = pd.to_numeric(v_df[c], errors="coerce")

                st.dataframe(v_df[v_cols], use_container_width=True, hide_index=True)

                st.markdown("---")
                st.markdown("### Open / Manage a valve design")

                options_v: List[tuple[str, str]] = []
                for row in summary_records:
                    rid = str(row.get("id") or "").strip()
                    nm  = str(row.get("name") or "Untitled")
                    if rid:
                        options_v.append((f"{nm} ({rid[:8]}…)", rid))

                if options_v:
                    labels_v = ["-- select --"] + [lbl for lbl, _ in options_v]
                    sel_v = st.selectbox("Pick a saved valve design", labels_v, key="sel_valve")
                    if sel_v != "-- select --":
                        design_id = dict(options_v)[sel_v]
                        data = get_valve_design(design_id, user["id"])
                        if not data:
                            st.error("Could not load this design.")
                        else:
                            st.caption(
                                f"**Created:** {_fmt_ts(created_map.get(design_id))} • "
                                f"**Updated:** {_fmt_ts(updated_map.get(design_id))}"
                            )
                            _valve_render_pretty(data)

                            st.markdown("---")
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                new_name_default = sel_v.rsplit(" (", 1)[0]
                                new_name = st.text_input("Rename", value=new_name_default, key="rename_valve")
                                if st.button("Save name", key="btn_rename_valve"):
                                    if update_valve_design(design_id, user["id"], name=new_name):
                                        st.success("Renamed.")
                                        st.rerun()
                                    else:
                                        st.error("Rename failed.")
                            with c2:
                                if st.button("🗑️ Delete", key="btn_delete_valve"):
                                    if delete_valve_design(design_id, user["id"]):
                                        st.success("Deleted.")
                                        st.rerun()
                                    else:
                                        st.error("Delete failed.")
                            with c3:
                                st.caption("Tip: to repopulate the Valve page with these values, give each widget a key and set session_state.")
                else:
                    st.warning("No selectable designs (missing IDs).")

    # ==================== TAB 2: DC001 CALCULATIONS ====================
    with tabs[2]:
        rows_dc = list_dc001_calcs(user["id"], limit=500)

        if not rows_dc:
            st.info("You haven't saved any **DC001 calculations** yet. Use **DC001** page and click **Save**.")
        else:
            norm_dc: List[Tuple[str, str]] = []
            created_map: Dict[str, Any] = {}
            updated_map: Dict[str, Any] = {}

            for r in rows_dc:
                rid, nm, created, updated = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2:
                        rid = r[0]
                        nm = r[1] or "Untitled"
                    if len(r) >= 3:
                        created = r[2]
                    if len(r) >= 4:
                        updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id") or r.get("id_")
                    nm  = r.get("name") or r.get("title") or "Untitled"
                    created = r.get("created_at")
                    updated = r.get("updated_at")
                if rid:
                    rid = str(rid)
                    nm = str(nm)
                    norm_dc.append((rid, nm))
                    created_map[rid] = created
                    updated_map[rid] = updated

            records_dc: List[Dict[str, Any]] = []
            for _id, name in norm_dc:
                data = get_dc001_calc(_id, user["id"])  # dict or None
                s = _dc001_summarize(data or {})
                records_dc.append({
                    "id": _id,
                    "name": name,
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "Dm_mm": s.get("Dm_mm"),
                    "P_N": s.get("P_N"),
                    "Fmt_N": s.get("Fmt_N"),
                    "Pr_N": s.get("Pr_N"),
                    "Fmr_N": s.get("Fmr_N"),
                    "Q_MPa": s.get("Q_MPa"),
                    "result": s.get("result"),
                    "created_at": _fmt_ts(created_map.get(_id)),
                    "updated_at": _fmt_ts(updated_map.get(_id)),
                })

            dc_cols = ["id","name","nps_in","asme_class","Dm_mm","P_N","Fmt_N","Pr_N","Fmr_N","Q_MPa","result","created_at","updated_at"]
            df_dc = pd.DataFrame(records_dc, columns=dc_cols)
            for c in ["nps_in","asme_class","Dm_mm","P_N","Fmt_N","Pr_N","Fmr_N","Q_MPa"]:
                df_dc[c] = pd.to_numeric(df_dc[c], errors="coerce")

            st.dataframe(df_dc[dc_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC001 calculation")

            options_d: List[tuple[str, str]] = []
            for row in records_dc:
                rid = str(row.get("id") or "").strip()
                nm  = str(row.get("name") or "Untitled")
                if rid:
                    options_d.append((f"{nm} ({rid[:8]}…)", rid))

            if options_d:
                labels_d = ["-- select --"] + [lbl for lbl, _ in options_d]
                sel_d = st.selectbox("Pick a saved DC001 calculation", labels_d, key="sel_dc001")
                if sel_d != "-- select --":
                    calc_id = dict(options_d)[sel_d]
                    data = get_dc001_calc(calc_id, user["id"])
                    if not data:
                        st.error("Could not load this DC001 record.")
                    else:
                        st.caption(
                            f"**Created:** {_fmt_ts(created_map.get(calc_id))} • "
                            f"**Updated:** {_fmt_ts(updated_map.get(calc_id))}"
                        )
                        _dc001_render_pretty(data)

                        st.markdown("---")
                        c1, c2, _ = st.columns(3)
                        with c1:
                            new_name_default = sel_d.rsplit(" (", 1)[0]
                            new_name = st.text_input("Rename", value=new_name_default, key="rename_dc001")
                            if st.button("Save name", key="btn_rename_dc001"):
                                if update_dc001_calc(calc_id, user["id"], name=new_name):
                                    st.success("Renamed.")
                                    st.rerun()
                                else:
                                    st.error("Rename failed.")
                        with c2:
                            if st.button("🗑️ Delete", key="btn_delete_dc001"):
                                if delete_dc001_calc(calc_id, user["id"]):
                                    st.success("Deleted.")
                                    st.rerun()
                                else:
                                    st.error("Delete failed.")
            else:
                st.warning("No selectable DC001 records (missing IDs).")

    # ==================== TAB 3: DC001A CALCULATIONS ====================
    with tabs[3]:
        rows_dca = list_dc001a_calcs(user["id"], limit=500)

        if not rows_dca:
            st.info("You haven't saved any **DC001A calculations** yet. Use **DC001A** page and click **Save**.")
        else:
            norm_dca: List[Tuple[str, str]] = []
            created_map_a: Dict[str, Any] = {}
            updated_map_a: Dict[str, Any] = {}

            for r in rows_dca:
                rid, nm, created, updated = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2:
                        rid = r[0]
                        nm  = r[1] or "Untitled"
                    if len(r) >= 3:
                        created = r[2]
                    if len(r) >= 4:
                        updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id") or r.get("id_")
                    nm  = r.get("name") or r.get("title") or "Untitled"
                    created = r.get("created_at")
                    updated = r.get("updated_at")
                if rid:
                    rid = str(rid)
                    nm  = str(nm)
                    norm_dca.append((rid, nm))
                    created_map_a[rid] = created
                    updated_map_a[rid] = updated

            records_dca: List[Dict[str, Any]] = []
            for _id, name in norm_dca:
                data = get_dc001a_calc(_id, user["id"]) or {}
                s = _dc001a_summarize(data)
                records_dca.append({
                    "id": _id,
                    "name": name,
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "Dc_mm (Dm from DC001)": s.get("Dc_mm"),
                    "Dts_mm (Dc from DC001)": s.get("Dts_mm"),
                    "SR_N (F from DC001)": s.get("SR_N"),
                    "F_molle_N (Pr from DC001)": s.get("F_molle_N"),
                    "verdict": s.get("verdict"),
                    "source_dc001": s.get("source_dc001_name"),
                    "created_at": _fmt_ts(created_map_a.get(_id)),
                    "updated_at": _fmt_ts(updated_map_a.get(_id)),
                })

            dca_cols = [
                "id","name","nps_in","asme_class",
                "Dc_mm (Dm from DC001)","Dts_mm (Dc from DC001)",
                "SR_N (F from DC001)","F_molle_N (Pr from DC001)",
                "verdict","source_dc001","created_at","updated_at"
            ]
            df_dca = pd.DataFrame(records_dca, columns=dca_cols)
            for c in ["nps_in","asme_class","Dc_mm (Dm from DC001)","Dts_mm (Dc from DC001)",
                      "SR_N (F from DC001)","F_molle_N (Pr from DC001)"]:
                df_dca[c] = pd.to_numeric(df_dca[c], errors="coerce")

            st.dataframe(df_dca[dca_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC001A calculation")

            options_a: List[tuple[str, str]] = []
            for row in records_dca:
                rid = str(row.get("id") or "").strip()
                nm  = str(row.get("name") or "Untitled")
                if rid:
                    options_a.append((f"{nm} ({rid[:8]}…)", rid))

            if options_a:
                labels_a = ["-- select --"] + [lbl for lbl, _ in options_a]
                sel_a = st.selectbox("Pick a saved DC001A calculation", labels_a, key="sel_dc001a")
                if sel_a != "-- select --":
                    calc_id = dict(options_a)[sel_a]
                    data = get_dc001a_calc(calc_id, user["id"])
                    if not data:
                        st.error("Could not load this DC001A record.")
                    else:
                        st.caption(
                            f"**Created:** {_fmt_ts(created_map_a.get(calc_id))} • "
                            f"**Updated:** {_fmt_ts(updated_map_a.get(calc_id))}"
                        )
                        _dc001a_render_pretty(data)

                        st.markdown("---")
                        c1, c2, _ = st.columns(3)
                        with c1:
                            new_name_default = sel_a.rsplit(" (", 1)[0]
                            new_name = st.text_input("Rename", value=new_name_default, key="rename_dc001a")
                            if st.button("Save name", key="btn_rename_dc001a"):
                                if update_dc001a_calc(calc_id, user["id"], name=new_name):
                                    st.success("Renamed.")
                                    st.rerun()
                                else:
                                    st.error("Rename failed.")
                        with c2:
                            if st.button("🗑️ Delete", key="btn_delete_dc001a"):
                                if delete_dc001a_calc(calc_id, user["id"]):
                                    st.success("Deleted.")
                                    st.rerun()
                                else:
                                    st.error("Delete failed.")
            else:
                st.warning("No selectable DC001A records (missing IDs).")

    # ==================== TAB 4: DC002 CALCULATIONS ====================
    with tabs[4]:
        rows_d2 = list_dc002_calcs(user["id"], limit=500)

        if not rows_d2:
            st.info("You haven't saved any **DC002 calculations** yet. Use **DC002** page and click **Save**.")
        else:
            records_d2: List[Dict[str, Any]] = []
            for (_id, nm, _ca, _ua) in rows_d2:
                meta = get_dc002_calc_with_meta(_id, user["id"]) or {}
                s = _dc002_summarize(meta or {})
                records_d2.append({
                    "id": s.get("id"),
                    "name": s.get("name") or nm,
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "G_mm": s.get("G_mm"),
                    "Pa_MPa": s.get("Pa_MPa"),
                    "Wm1_N": s.get("Wm1_N"),
                    "S_MPa": s.get("S_MPa"),
                    "n": s.get("n"),
                    "bolt_size": s.get("bolt_size"),
                    "Sa_eff_MPa": s.get("Sa_eff_MPa"),
                    "verdict": s.get("verdict"),
                    "created_at": _fmt_ts(s.get("created_at")),
                    "updated_at": _fmt_ts(s.get("updated_at")),
                })

            d2_cols = ["id","name","nps_in","asme_class","G_mm","Pa_MPa","Wm1_N","S_MPa","n","bolt_size","Sa_eff_MPa","verdict","created_at","updated_at"]
            df_d2 = pd.DataFrame(records_d2, columns=d2_cols)
            for c in ["nps_in","asme_class","G_mm","Pa_MPa","Wm1_N","S_MPa","n","Sa_eff_MPa"]:
                df_d2[c] = pd.to_numeric(df_d2[c], errors="coerce")

            st.dataframe(df_d2[d2_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC002 calculation")

            options_d2: List[tuple[str, str]] = []
            for row in records_d2:
                rid = str(row.get("id") or "").strip()
                nm  = str(row.get("name") or "Untitled")
                if rid:
                    options_d2.append((f"{nm} ({rid[:8]}…)", rid))

            if options_d2:
                labels_d2 = ["-- select --"] + [lbl for lbl, _ in options_d2]
                sel_d2 = st.selectbox("Pick a saved DC002 calculation", labels_d2, key="sel_dc002")
                if sel_d2 != "-- select --":
                    calc_id = dict(options_d2)[sel_d2]
                    meta = get_dc002_calc_with_meta(calc_id, user["id"])
                    if not meta:
                        st.error("Could not load this DC002 record.")
                    else:
                        st.caption(
                            f"**Name:** {meta.get('name') or '—'} • "
                            f"**Created:** {_fmt_ts(meta.get('created_at'))} • "
                            f"**Updated:** {_fmt_ts(meta.get('updated_at'))}"
                        )
                        _dc002_render_pretty(meta)

                        st.markdown("---")
                        c1, c2, _ = st.columns(3)
                        with c1:
                            new_name_default = sel_d2.rsplit(" (", 1)[0]
                            new_name = st.text_input("Rename", value=new_name_default, key="rename_dc002")
                            if st.button("Save name", key="btn_rename_dc002"):
                                if update_dc002_calc(calc_id, user["id"], name=new_name):
                                    st.success("Renamed.")
                                    st.rerun()
                                else:
                                    st.error("Rename failed.")
                        with c2:
                            if st.button("🗑️ Delete", key="btn_delete_dc002"):
                                if delete_dc002_calc(calc_id, user["id"]):
                                    st.success("Deleted.")
                                    st.rerun()
                                else:
                                    st.error("Delete failed.")
            else:
                st.warning("No selectable DC002 records (missing IDs).")

    # ==================== TAB 5: DC002A CALCULATIONS ====================
    with tabs[5]:
        rows_d2a = list_dc002a_calcs(user["id"], limit=500)

        if not rows_d2a:
            st.info("You haven't saved any **DC002A calculations** yet. Use **DC002A** page and click **Save**.")
        else:
            norm_d2a: List[Tuple[str, str]] = []
            created_map_d2a: Dict[str, Any] = {}
            updated_map_d2a: Dict[str, Any] = {}

            for r in rows_d2a:
                rid, nm, created, updated = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2:
                        rid = r[0]
                        nm  = r[1] or "Untitled"
                    if len(r) >= 3:
                        created = r[2]
                    if len(r) >= 4:
                        updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id") or r.get("id_")
                    nm  = r.get("name") or r.get("title") or "Untitled"
                    created = r.get("created_at")
                    updated = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm_d2a.append((rid, nm))
                    created_map_d2a[rid] = created
                    updated_map_d2a[rid] = updated

            # summary rows
            records_d2a: List[Dict[str, Any]] = []
            for _id, name in norm_d2a:
                data = get_dc002a_calc(_id, user["id"]) or {}
                s = _dc002a_summarize(data)
                records_d2a.append({
                    "id": _id,
                    "name": name,
                    "nps_in": s.get("nps_in"),
                    "asme_class": s.get("asme_class"),
                    "G_mm": s.get("G_mm"),
                    "Pa_test_MPa": s.get("Pa_test_MPa"),
                    "S_MPa": s.get("S_MPa"),
                    "n": s.get("n"),
                    "bolt_size": s.get("bolt_size"),
                    "Sa_eff_MPa": s.get("Sa_eff_MPa"),
                    "verdict": s.get("verdict"),
                    "created_at": _fmt_ts(created_map_d2a.get(_id)),
                    "updated_at": _fmt_ts(updated_map_d2a.get(_id)),
                })

            d2a_cols = ["id","name","nps_in","asme_class","G_mm","Pa_test_MPa","S_MPa","n","bolt_size","Sa_eff_MPa","verdict","created_at","updated_at"]
            df_d2a = pd.DataFrame(records_d2a, columns=d2a_cols)
            for c in ["nps_in","asme_class","G_mm","Pa_test_MPa","S_MPa","n","Sa_eff_MPa"]:
                df_d2a[c] = pd.to_numeric(df_d2a[c], errors="coerce")

            st.dataframe(df_d2a[d2a_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC002A calculation")

            options_d2a: List[tuple[str, str]] = []
            for row in records_d2a:
                rid = str(row.get("id") or "").strip()
                nm  = str(row.get("name") or "Untitled")
                if rid:
                    options_d2a.append((f"{nm} ({rid[:8]}…)", rid))

            if options_d2a:
                labels_d2a = ["-- select --"] + [lbl for lbl, _ in options_d2a]
                sel_d2a = st.selectbox("Pick a saved DC002A calculation", labels_d2a, key="sel_dc002a")
                if sel_d2a != "-- select --":
                    calc_id = dict(options_d2a)[sel_d2a]
                    data = get_dc002a_calc(calc_id, user["id"])
                    if not data:
                        st.error("Could not load this DC002A record.")
                    else:
                        st.caption(
                            f"**Created:** {_fmt_ts(created_map_d2a.get(calc_id))} • "
                            f"**Updated:** {_fmt_ts(updated_map_d2a.get(calc_id))}"
                        )
                        _dc002a_render_pretty(data)

                        st.markdown("---")
                        c1, c2, _ = st.columns(3)
                        with c1:
                            new_name_default = sel_d2a.rsplit(" (", 1)[0]
                            new_name = st.text_input("Rename", value=new_name_default, key="rename_dc002a")
                            if st.button("Save name", key="btn_rename_dc002a"):
                                if update_dc002a_calc(calc_id, user["id"], name=new_name):
                                    st.success("Renamed.")
                                    st.rerun()
                                else:
                                    st.error("Rename failed.")
                        with c2:
                            if st.button("🗑️ Delete", key="btn_delete_dc002a"):
                                if delete_dc002a_calc(calc_id, user["id"]):
                                    st.success("Deleted.")
                                    st.rerun()
                                else:
                                    st.error("Delete failed.")
            else:
                st.warning("No selectable DC002A records (missing IDs).")

    # ==================== TAB 6: DC003 CALCULATIONS ====================
    with tabs[6]:
        rows_d3 = list_dc003_calcs(user["id"], limit=500)
        if not rows_d3:
            st.info("You haven't saved any **DC003 calculations** yet. Use **DC003** page and click **Save**.")
        else:
            created_map_d3: Dict[str, Any] = {}
            updated_map_d3: Dict[str, Any] = {}
            norm_d3: List[Tuple[str, str]] = []
            for r in rows_d3:
                rid, nm, created, updated = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2: rid, nm = r[0], r[1] or "Untitled"
                    if len(r) >= 3: created = r[2]
                    if len(r) >= 4: updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id")
                    nm  = r.get("name") or "Untitled"
                    created = r.get("created_at"); updated = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm_d3.append((rid, nm))
                    created_map_d3[rid] = created; updated_map_d3[rid] = updated

            records_d3: List[Dict[str, Any]] = []
            for _id, name in norm_d3:
                data = get_dc003_calc(_id, user["id"]) or {}
                s = _dc003_summarize(data)
                records_d3.append({
                    "id": _id, "name": name,
                    "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                    "Dt_mm": s.get("Dt_mm"), "Db_mm": s.get("Db_mm"), "Hb_mm": s.get("Hb_mm"),
                    "P_MPa": s.get("P_MPa"), "MABS_MPa": s.get("MABS_MPa"),
                    "BBS_MPa": s.get("BBS_MPa"), "verdict": s.get("verdict"),
                    "created_at": _fmt_ts(created_map_d3.get(_id)), "updated_at": _fmt_ts(updated_map_d3.get(_id)),
                })

            d3_cols = ["id","name","nps_in","asme_class","Dt_mm","Db_mm","Hb_mm","P_MPa","MABS_MPa","BBS_MPa","verdict","created_at","updated_at"]
            df_d3 = pd.DataFrame(records_d3, columns=d3_cols)
            for c in ["nps_in","asme_class","Dt_mm","Db_mm","Hb_mm","P_MPa","MABS_MPa","BBS_MPa"]:
                df_d3[c] = pd.to_numeric(df_d3[c], errors="coerce")

            st.dataframe(df_d3[d3_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC003 calculation")

            options_d3: List[tuple[str, str]] = [(f"{nm} ({rid[:8]}…)", rid) for rid, nm in norm_d3]
            labels_d3 = ["-- select --"] + [lbl for lbl, _ in options_d3]
            sel_d3 = st.selectbox("Pick a saved DC003 calculation", labels_d3, key="sel_dc003")
            if sel_d3 != "-- select --":
                calc_id = dict(options_d3)[sel_d3]
                data = get_dc003_calc(calc_id, user["id"])
                if not data:
                    st.error("Could not load this DC003 record.")
                else:
                    st.caption(f"**Created:** {_fmt_ts(created_map_d3.get(calc_id))} • **Updated:** {_fmt_ts(updated_map_d3.get(calc_id))}")
                    _dc003_render_pretty(data)

                    st.markdown("---")
                    c1, c2, _ = st.columns(3)
                    with c1:
                        new_name_default = sel_d3.rsplit(" (", 1)[0]
                        new_name = st.text_input("Rename", value=new_name_default, key="rename_dc003")
                        if st.button("Save name", key="btn_rename_dc003"):
                            if update_dc003_calc(calc_id, user["id"], name=new_name):
                                st.success("Renamed."); st.rerun()
                            else:
                                st.error("Rename failed.")
                    with c2:
                        if st.button("🗑️ Delete", key="btn_delete_dc003"):
                            if delete_dc003_calc(calc_id, user["id"]):
                                st.success("Deleted."); st.rerun()
                            else:
                                st.error("Delete failed.")

    # ==================== TAB 7: DC004 CALCULATIONS ====================
    with tabs[7]:
        rows_d4 = list_dc004_calcs(user["id"], limit=500)
        if not rows_d4:
            st.info("You haven't saved any **DC004 calculations** yet. Use **DC004** page and click **Save**.")
        else:
            created_map_d4: Dict[str, Any] = {}
            updated_map_d4: Dict[str, Any] = {}
            norm_d4: List[Tuple[str, str]] = []
            for r in rows_d4:
                rid, nm, created, updated = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2: rid, nm = r[0], r[1] or "Untitled"
                    if len(r) >= 3: created = r[2]
                    if len(r) >= 4: updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id"); nm = r.get("name") or "Untitled"
                    created = r.get("created_at"); updated = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm_d4.append((rid, nm))
                    created_map_d4[rid] = created; updated_map_d4[rid] = updated

            records_d4: List[Dict[str, Any]] = []
            for _id, name in norm_d4:
                data = get_dc004_calc(_id, user["id"]) or {}
                s = _dc004_summarize(data)
                records_d4.append({
                    "id": _id, "name": name,
                    "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                    "thickness_mm": s.get("thickness_mm"), "verdict": s.get("verdict"),
                    "created_at": _fmt_ts(created_map_d4.get(_id)), "updated_at": _fmt_ts(updated_map_d4.get(_id)),
                })

            d4_cols = ["id","name","nps_in","asme_class","thickness_mm","verdict","created_at","updated_at"]
            df_d4 = pd.DataFrame(records_d4, columns=d4_cols)
            for c in ["nps_in","asme_class","thickness_mm"]:
                df_d4[c] = pd.to_numeric(df_d4[c], errors="coerce")

            st.dataframe(df_d4[d4_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC004 calculation")

            options_d4: List[tuple[str, str]] = [(f"{nm} ({rid[:8]}…)", rid) for rid, nm in norm_d4]
            labels_d4 = ["-- select --"] + [lbl for lbl, _ in options_d4]
            sel_d4 = st.selectbox("Pick a saved DC004 calculation", labels_d4, key="sel_dc004")
            if sel_d4 != "-- select --":
                calc_id = dict(options_d4)[sel_d4]
                data = get_dc004_calc(calc_id, user["id"])
                if not data:
                    st.error("Could not load this DC004 record.")
                else:
                    st.caption(f"**Created:** {_fmt_ts(created_map_d4.get(calc_id))} • **Updated:** {_fmt_ts(updated_map_d4.get(calc_id))}")
                    _dc004_render_pretty(data)

                    st.markdown("---")
                    c1, c2, _ = st.columns(3)
                    with c1:
                        new_name_default = sel_d4.rsplit(" (", 1)[0]
                        new_name = st.text_input("Rename", value=new_name_default, key="rename_dc004")
                        if st.button("Save name", key="btn_rename_dc004"):
                            if update_dc004_calc(calc_id, user["id"], name=new_name):
                                st.success("Renamed."); st.rerun()
                            else:
                                st.error("Rename failed.")
                    with c2:
                        if st.button("🗑️ Delete", key="btn_delete_dc004"):
                            if delete_dc004_calc(calc_id, user["id"]):
                                st.success("Deleted."); st.rerun()
                            else:
                                st.error("Delete failed.")

    # ==================== TAB 8: DC005 CALCULATIONS ====================
    with tabs[8]:
        rows_d5 = list_dc005_calcs(user["id"], limit=500)
        if not rows_d5:
            st.info("You haven't saved any **DC005 calculations** yet. Use **DC005** page and click **Save**.")
        else:
            created_map_d5: Dict[str, Any] = {}
            updated_map_d5: Dict[str, Any] = {}
            norm_d5: List[Tuple[str, str]] = []
            for r in rows_d5:
                rid, nm, created, updated = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2: rid, nm = r[0], r[1] or "Untitled"
                    if len(r) >= 3: created = r[2]
                    if len(r) >= 4: updated = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id"); nm = r.get("name") or "Untitled"
                    created = r.get("created_at"); updated = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm_d5.append((rid, nm))
                    created_map_d5[rid] = created; updated_map_d5[rid] = updated

            records_d5: List[Dict[str, Any]] = []
            for _id, name in norm_d5:
                data = get_dc005_calc(_id, user["id"]) or {}
                s = _dc005_summarize(data)
                records_d5.append({
                    "id": _id, "name": name,
                    "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                    "G_mm": s.get("G_mm"), "Gstem_mm": s.get("Gstem_mm"),
                    "Pa_MPa": s.get("Pa_MPa"), "n": s.get("n"),
                    "bolt_size": s.get("bolt_size"), "Sa_eff_MPa": s.get("Sa_eff_MPa"),
                    "verdict": s.get("verdict"),
                    "created_at": _fmt_ts(created_map_d5.get(_id)), "updated_at": _fmt_ts(updated_map_d5.get(_id)),
                })

            d5_cols = ["id","name","nps_in","asme_class","G_mm","Gstem_mm","Pa_MPa","n","bolt_size","Sa_eff_MPa","verdict","created_at","updated_at"]
            df_d5 = pd.DataFrame(records_d5, columns=d5_cols)
            for c in ["nps_in","asme_class","G_mm","Gstem_mm","Pa_MPa","n","Sa_eff_MPa"]:
                df_d5[c] = pd.to_numeric(df_d5[c], errors="coerce")

            st.dataframe(df_d5[d5_cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC005 calculation")

            options_d5: List[tuple[str, str]] = [(f"{nm} ({rid[:8]}…)", rid) for rid, nm in norm_d5]
            labels_d5 = ["-- select --"] + [lbl for lbl, _ in options_d5]
            sel_d5 = st.selectbox("Pick a saved DC005 calculation", labels_d5, key="sel_dc005")
            if sel_d5 != "-- select --":
                calc_id = dict(options_d5)[sel_d5]
                data = get_dc005_calc(calc_id, user["id"])
                if not data:
                    st.error("Could not load this DC005 record.")
                else:
                    st.caption(f"**Created:** {_fmt_ts(created_map_d5.get(calc_id))} • **Updated:** {_fmt_ts(updated_map_d5.get(calc_id))}")
                    _dc005_render_pretty(data)

                    st.markdown("---")
                    c1, c2, _ = st.columns(3)
                    with c1:
                        new_name_default = sel_d5.rsplit(" (", 1)[0]
                        new_name = st.text_input("Rename", value=new_name_default, key="rename_dc005")
                        if st.button("Save name", key="btn_rename_dc005"):
                            if update_dc005_calc(calc_id, user["id"], name=new_name):
                                st.success("Renamed."); st.rerun()
                            else:
                                st.error("Rename failed.")
                    with c2:
                        if st.button("🗑️ Delete", key="btn_delete_dc005"):
                            if delete_dc005_calc(calc_id, user["id"]):
                                st.success("Deleted."); st.rerun()
                            else:
                                st.error("Delete failed.")

        # ==================== TAB: DC005a ====================
    with tabs[9]:
        st.header("DC005a Calculations")
        user_id = user["id"]

        rows = list_dc005a_calcs(user_id, limit=1000) or []
        if not rows:
            st.info("No DC005a calculations saved yet.")
        else:
            # Normalize to a table
            table = []
            for it in rows:
                # Accept tuple/list or dict shapes
                if isinstance(it, (list, tuple)):
                    rid = str(it[0]) if len(it) > 0 else ""
                    nm = it[1] if len(it) > 1 else "Untitled"
                    ts = it[2] if len(it) > 2 else ""
                else:
                    rid = str(it.get("id", ""))
                    nm = it.get("name", "Untitled")
                    ts = it.get("updated_at") or it.get("created_at") or ""
                table.append({"id": rid, "name": nm, "updated": ts})

            st.dataframe(
                pd.DataFrame(table, columns=["id", "name", "updated"]),
                use_container_width=True,
                hide_index=True,
            )

            lbls = ["-- select --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in table]
            sel = st.selectbox("Open a saved DC005a", lbls, key="lib_tab_dc005a_open")
            if sel != "-- select --":
                rid = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in table}[sel]
                data = get_dc005a_calc(rid, user_id) or {}
                _dc005a_render_pretty(data)
    
        # ==================== TAB: DC006 ====================
    with tabs[10]:
        st.header("DC006 Calculations")
        user_id = user["id"]

        rows = list_dc006_calcs(user_id, limit=1000) or []
        if not rows:
            st.info("No DC006 calculations saved yet.")
        else:
            table = []
            for it in rows:
                if isinstance(it, (list, tuple)):
                    rid = str(it[0]) if len(it) > 0 else ""
                    nm = it[1] if len(it) > 1 else "Untitled"
                    ts = it[2] if len(it) > 2 else ""
                else:
                    rid = str(it.get("id", ""))
                    nm = it.get("name", "Untitled")
                    ts = it.get("updated_at") or it.get("created_at") or ""
                table.append({"id": rid, "name": nm, "updated": ts})

            st.dataframe(
                pd.DataFrame(table, columns=["id", "name", "updated"]),
                use_container_width=True,
                hide_index=True,
            )

            lbls = ["-- select --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in table]
            sel = st.selectbox("Open a saved DC006", lbls, key="lib_tab_dc006_open")
            if sel != "-- select --":
                rid = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in table}[sel]
                data = get_dc006_calc(rid, user_id) or {}
                _dc006_render_pretty(data)

        # ==================== TAB: DC006a ====================
    with tabs[11]:
        st.header("DC006a Calculations")
        user_id = user["id"]

        rows = list_dc006a_calcs(user_id, limit=1000) or []
        if not rows:
            st.info("No DC006a calculations saved yet.")
        else:
            table = []
            for it in rows:
                if isinstance(it, (list, tuple)):
                    rid = str(it[0]) if len(it) > 0 else ""
                    nm = it[1] if len(it) > 1 else "Untitled"
                    ts = it[2] if len(it) > 2 else ""
                else:
                    rid = str(it.get("id", ""))
                    nm = it.get("name", "Untitled")
                    ts = it.get("updated_at") or it.get("created_at") or ""
                table.append({"id": rid, "name": nm, "updated": ts})

            st.dataframe(
                pd.DataFrame(table, columns=["id", "name", "updated"]),
                use_container_width=True,
                hide_index=True,
            )

            lbls = ["-- select --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in table]
            sel = st.selectbox("Open a saved DC006a", lbls, key="lib_tab_dc006a_open")
            if sel != "-- select --":
                rid = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in table}[sel]
                data = get_dc006a_calc(rid, user_id) or {}
                _dc006a_render_pretty(data)

        # ==================== TAB: DC007 (Combined) ====================
    with tabs[12]:
        st.header("DC007 – Combined (Body & Body Holes)")
        user_id = user["id"]

        # Fetch both lists
        rows_body = list_dc007_body_calcs(user_id, limit=1000) or []
        rows_holes = list_dc007_body_holes_calcs(user_id, limit=1000) or []

        # Build compact tables
        def _norm(rows, kind):
            out = []
            for it in rows:
                if isinstance(it, (list, tuple)):
                    rid = str(it[0]) if len(it) > 0 else ""
                    nm = it[1] if len(it) > 1 else "Untitled"
                    ts = it[2] if len(it) > 2 else ""
                else:
                    rid = str(it.get("id", ""))
                    nm = it.get("name", "Untitled")
                    ts = it.get("updated_at") or it.get("created_at") or ""
                out.append({"id": rid, "name": nm, "updated": ts, "type": kind})
            return out

        table = _norm(rows_body, "Body") + _norm(rows_holes, "Body Holes")

        if not table:
            st.info("No DC007 records (Body or Body Holes) saved yet.")
        else:
            st.dataframe(
                pd.DataFrame(table, columns=["id", "name", "type", "updated"]),
                use_container_width=True,
                hide_index=True,
            )

            lbls = ["-- select --"] + [f"[{r['type']}] {r['name']} ({r['id'][:8]}…)" for r in table]
            sel = st.selectbox("Open a saved DC007 record", lbls, key="lib_tab_dc007_open")
            if sel != "-- select --":
                rid_map = {f"[{r['type']}] {r['name']} ({r['id'][:8]}…)": (r["id"], r["type"]) for r in table}
                rid, kind = rid_map[sel]
                if kind == "Body":
                    data = get_dc007_body_calc(rid, user_id) or {}
                    _dc007_body_render_pretty(data)
                else:
                    data = get_dc007_body_holes_calc(rid, user_id) or {}
                    _dc007_body_holes_render_pretty(data)

        # ==================== TAB: DC007 body ====================
    with tabs[13]:
        st.header("DC007 – Body")
        user_id = user["id"]

        rows = list_dc007_body_calcs(user_id, limit=1000) or []
        if not rows:
            st.info("No DC007 Body calculations saved yet.")
        else:
            table = []
            for it in rows:
                if isinstance(it, (list, tuple)):
                    rid = str(it[0]) if len(it) > 0 else ""
                    nm = it[1] if len(it) > 1 else "Untitled"
                    ts = it[2] if len(it) > 2 else ""
                else:
                    rid = str(it.get("id", ""))
                    nm = it.get("name", "Untitled")
                    ts = it.get("updated_at") or it.get("created_at") or ""
                table.append({"id": rid, "name": nm, "updated": ts})

            st.dataframe(
                pd.DataFrame(table, columns=["id", "name", "updated"]),
                use_container_width=True,
                hide_index=True,
            )

            lbls = ["-- select --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in table]
            sel = st.selectbox("Open a saved DC007 Body", lbls, key="lib_tab_dc007_body_open")
            if sel != "-- select --":
                rid = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in table}[sel]
                data = get_dc007_body_calc(rid, user_id) or {}
                _dc007_body_render_pretty(data)

        # ==================== TAB: DC008 ====================
    with tabs[14]:
        st.header("DC008 Calculations")
        user_id = user["id"]

        rows = list_dc008_calcs(user_id, limit=1000) or []
        if not rows:
            st.info("No DC008 calculations saved yet.")
        else:
            table = []
            for it in rows:
                if isinstance(it, (list, tuple)):
                    rid = str(it[0]) if len(it) > 0 else ""
                    nm = it[1] if len(it) > 1 else "Untitled"
                    ts = it[2] if len(it) > 2 else ""
                else:
                    rid = str(it.get("id", ""))
                    nm = it.get("name", "Untitled")
                    ts = it.get("updated_at") or it.get("created_at") or ""
                table.append({"id": rid, "name": nm, "updated": ts})

            st.dataframe(
                pd.DataFrame(table, columns=["id", "name", "updated"]),
                use_container_width=True,
                hide_index=True,
            )

            lbls = ["-- select --"] + [f"{r['name']} ({r['id'][:8]}…)" for r in table]
            sel = st.selectbox("Open a saved DC008", lbls, key="lib_tab_dc008_open")
            if sel != "-- select --":
                rid = {f"{r['name']} ({r['id'][:8]}…)": r["id"] for r in table}[sel]
                data = get_dc008_calc(rid, user_id) or {}
                _dc008_render_pretty(data)


    # ==================== TAB 9: DC010 CALCULATIONS (NEW) ====================
    with tabs[15]:
        rows_d10 = list_dc010_calcs(user["id"], limit=500)
        if not rows_d10:
            st.info("You haven't saved any **DC010 calculations** yet. Use **DC010** page and click **Save**.")
        else:
            created_map: Dict[str, Any] = {}
            updated_map: Dict[str, Any] = {}
            norm: List[Tuple[str, str]] = []
            for r in rows_d10:
                rid, nm, ca, ua = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2: rid, nm = r[0], r[1] or "Untitled"
                    if len(r) >= 3: ca = r[2]
                    if len(r) >= 4: ua = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id"); nm = r.get("name") or "Untitled"
                    ca = r.get("created_at"); ua = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm.append((rid, nm)); created_map[rid] = ca; updated_map[rid] = ua

            records: List[Dict[str, Any]] = []
            for _id, name in norm:
                data = get_dc010_calc(_id, user["id"]) or {}
                s = _dc010_summarize(data)
                records.append({
                    "id": _id, "name": name,
                    "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                    "Po [MPA]": s.get("Po_MPa_in"), "D [mm]": s.get("D_mm"), "Dc [mm]": s.get("Dc_mm"),
                    "Tbb1 [N·m]": s.get("Tbb1_Nm"),
                    "created_at": _fmt_ts(created_map.get(_id)), "updated_at": _fmt_ts(updated_map.get(_id)),
                })

            cols = ["id","name","nps_in","asme_class","Po [MPA]","D [mm]","Dc [mm]","Tbb1 [N·m]","created_at","updated_at"]
            df = pd.DataFrame(records, columns=cols)
            for c in ["nps_in","asme_class","Po [MPA]","D [mm]","Dc [mm]","Tbb1 [N·m]"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            st.dataframe(df[cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC010 calculation")

            options = [(f"{nm} ({rid[:8]}…)", rid) for rid, nm in norm]
            labels = ["-- select --"] + [lbl for lbl, _ in options]
            sel = st.selectbox("Pick a saved DC010 calculation", labels, key="sel_dc010")
            if sel != "-- select --":
                calc_id = dict(options)[sel]
                data = get_dc010_calc(calc_id, user["id"])
                if not data:
                    st.error("Could not load this DC010 record.")
                else:
                    st.caption(f"**Created:** {_fmt_ts(created_map.get(calc_id))} • **Updated:** {_fmt_ts(updated_map.get(calc_id))}")
                    _dc010_render_pretty(data)

                    st.markdown("---")
                    c1, c2, _ = st.columns(3)
                    with c1:
                        new_name_default = sel.rsplit(" (", 1)[0]
                        new_name = st.text_input("Rename", value=new_name_default, key="rename_dc010")
                        if st.button("Save name", key="btn_rename_dc010"):
                            if update_dc010_calc(calc_id, user["id"], name=new_name):
                                st.success("Renamed."); st.rerun()
                            else:
                                st.error("Rename failed.")
                    with c2:
                        if st.button("🗑️ Delete", key="btn_delete_dc010"):
                            if delete_dc010_calc(calc_id, user["id"]):
                                st.success("Deleted."); st.rerun()
                            else:
                                st.error("Delete failed.")

    # ==================== TAB 10: DC011 CALCULATIONS (NEW) ====================
    with tabs[16]:
        rows_d11 = list_dc011_calcs(user["id"], limit=500)
        if not rows_d11:
            st.info("You haven't saved any **DC011 calculations** yet. Use **DC011** page and click **Save**.")
        else:
            created_map: Dict[str, Any] = {}
            updated_map: Dict[str, Any] = {}
            norm: List[Tuple[str, str]] = []
            for r in rows_d11:
                rid, nm, ca, ua = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2: rid, nm = r[0], r[1] or "Untitled"
                    if len(r) >= 3: ca = r[2]
                    if len(r) >= 4: ua = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id"); nm = r.get("name") or "Untitled"
                    ca = r.get("created_at"); ua = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm.append((rid, nm)); created_map[rid] = ca; updated_map[rid] = ua

            records: List[Dict[str, Any]] = []
            for _id, name in norm:
                data = get_dc011_calc(_id, user["id"]) or {}
                s = _dc011_summarize(data)
                records.append({
                    "id": _id, "name": name,
                    "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                    "Inner [mm]": s.get("inner_bore_mm"), "Seat [mm]:": s.get("seat_bore_mm"),
                    "β [-]": s.get("beta"), "θ [deg]": s.get("theta_deg"),
                    "Cv (gpm @ 1 psi)": s.get("Cv"),
                    "created_at": _fmt_ts(created_map.get(_id)), "updated_at": _fmt_ts(updated_map.get(_id)),
                })

            cols = ["id","name","nps_in","asme_class","Inner [mm]","Seat [mm]:","β [-]","θ [deg]","Cv (gpm @ 1 psi)","created_at","updated_at"]
            df = pd.DataFrame(records, columns=cols)
            for c in ["nps_in","asme_class","Inner [mm]","Seat [mm]:","β [-]","θ [deg]","Cv (gpm @ 1 psi)"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            st.dataframe(df[cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC011 calculation")

            options = [(f"{nm} ({rid[:8]}…)", rid) for rid, nm in norm]
            labels = ["-- select --"] + [lbl for lbl, _ in options]
            sel = st.selectbox("Pick a saved DC011 calculation", labels, key="sel_dc011")
            if sel != "-- select --":
                calc_id = dict(options)[sel]
                data = get_dc011_calc(calc_id, user["id"])
                if not data:
                    st.error("Could not load this DC011 record.")
                else:
                    st.caption(f"**Created:** {_fmt_ts(created_map.get(calc_id))} • **Updated:** {_fmt_ts(updated_map.get(calc_id))}")
                    _dc011_render_pretty(data)

                    st.markdown("---")
                    c1, c2, _ = st.columns(3)
                    with c1:
                        new_name_default = sel.rsplit(" (", 1)[0]
                        new_name = st.text_input("Rename", value=new_name_default, key="rename_dc011")
                        if st.button("Save name", key="btn_rename_dc011"):
                            if update_dc011_calc(calc_id, user["id"], name=new_name):
                                st.success("Renamed."); st.rerun()
                            else:
                                st.error("Rename failed.")
                    with c2:
                        if st.button("🗑️ Delete", key="btn_delete_dc011"):
                            if delete_dc011_calc(calc_id, user["id"]):
                                st.success("Deleted."); st.rerun()
                            else:
                                st.error("Delete failed.")

    # ==================== TAB 11: DC012 CALCULATIONS (NEW) ====================
    with tabs[17]:
        rows_d12 = list_dc012_calcs(user["id"], limit=500)
        if not rows_d12:
            st.info("You haven't saved any **DC012 calculations** yet. Use **DC012** page and click **Save**.")
        else:
            created_map: Dict[str, Any] = {}
            updated_map: Dict[str, Any] = {}
            norm: List[Tuple[str, str]] = []
            for r in rows_d12:
                rid, nm, ca, ua = None, "Untitled", None, None
                if isinstance(r, (list, tuple)):
                    if len(r) >= 2: rid, nm = r[0], r[1] or "Untitled"
                    if len(r) >= 3: ca = r[2]
                    if len(r) >= 4: ua = r[3]
                elif isinstance(r, dict):
                    rid = r.get("id") or r.get("calc_id"); nm = r.get("name") or "Untitled"
                    ca = r.get("created_at"); ua = r.get("updated_at")
                if rid:
                    rid = str(rid); nm = str(nm)
                    norm.append((rid, nm)); created_map[rid] = ca; updated_map[rid] = ua

            records: List[Dict[str, Any]] = []
            for _id, name in norm:
                data = get_dc012_calc(_id, user["id"]) or {}
                s = _dc012_summarize(data)
                records.append({
                    "id": _id, "name": name,
                    "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                    "P [kg]": s.get("P_kg"), "Thread": s.get("thread"),
                    "Es [MPa]": s.get("Es_MPa"), "Allow [MPa]": s.get("allowable_MPa"),
                    "OK": "OK" if s.get("stress_ok") else "NOT OK",
                    "created_at": _fmt_ts(created_map.get(_id)), "updated_at": _fmt_ts(updated_map.get(_id)),
                })

            cols = ["id","name","nps_in","asme_class","P [kg]","Thread","Es [MPa]","Allow [MPa]","OK","created_at","updated_at"]
            df = pd.DataFrame(records, columns=cols)
            for c in ["nps_in","asme_class","P [kg]","Es [MPa]","Allow [MPa]"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")
            st.dataframe(df[cols], use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("### Open / Manage a DC012 calculation")

            options = [(f"{nm} ({rid[:8]}…)", rid) for rid, nm in norm]
            labels = ["-- select --"] + [lbl for lbl, _ in options]
            sel = st.selectbox("Pick a saved DC012 calculation", labels, key="sel_dc012")
            if sel != "-- select --":
                calc_id = dict(options)[sel]
                data = get_dc012_calc(calc_id, user["id"])
                if not data:
                    st.error("Could not load this DC012 record.")
                else:
                    st.caption(f"**Created:** {_fmt_ts(created_map.get(calc_id))} • **Updated:** {_fmt_ts(updated_map.get(calc_id))}")
                    _dc012_render_pretty(data)

                    st.markdown("---")
                    c1, c2, _ = st.columns(3)
                    with c1:
                        new_name_default = sel.rsplit(" (", 1)[0]
                        new_name = st.text_input("Rename", value=new_name_default, key="rename_dc012")
                        if st.button("Save name", key="btn_rename_dc012"):
                            if update_dc012_calc(calc_id, user["id"], name=new_name):
                                st.success("Renamed.")
                                st.rerun()
                            else:
                                st.error("Rename failed.")
                    with c2:
                        if st.button("🗑️ Delete", key="btn_delete_dc012"):
                            if delete_dc012_calc(calc_id, user["id"]):
                                st.success("Deleted.")
                                st.rerun()
                            else:
                                st.error("Delete failed.")

    # ==================== TAB 12: ALL ITEMS SUMMARY (UNIFIED) ====================
    with tabs[18]:
        st.markdown("### All Items Summary")
        user_id = user["id"]

        rows_all: List[Dict[str, Any]] = []

        # Valve designs
        v_rows = _norm_list_rows(list_valve_designs(user_id, limit=1000))
        for r in v_rows:
            data = get_valve_design(r["id"], user_id) or {}
            s = _valve_summarize(data)
            summary = _kv_str([
                ("bore_mm", s.get("bore_mm")),
                ("f2f_mm", s.get("f2f_mm")),
                ("t_mm", s.get("t_mm")),
            ])
            rows_all.append({
                "type": "Valve",
                "id": r["id"],
                "name": r["name"],
                "valve_design_id": r["id"],
                "valve_design_name": data.get("name") or r["name"],
                "nps_in": s.get("nps_in"),
                "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(r["created_at"]),
                "updated_at": _fmt_ts(r["updated_at"]),
            })

        # DC001
        for x in _norm_list_rows(list_dc001_calcs(user_id, limit=1000)):
            rec = get_dc001_calc(x["id"], user_id) or {}
            s = _dc001_summarize(rec)
            summary = _kv_str([
                ("Dm_mm", s.get("Dm_mm")),
                ("Fmt_N", s.get("Fmt_N")),
                ("Pr_N", s.get("Pr_N")),
                ("Q_MPa", s.get("Q_MPa")),
                ("result", s.get("result")),
            ])
            rows_all.append({
                "type": "DC001", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC001A
        for x in _norm_list_rows(list_dc001a_calcs(user_id, limit=1000)):
            rec = get_dc001a_calc(x["id"], user_id) or {}
            s = _dc001a_summarize(rec)
            summary = _kv_str([
                ("Dc_mm", s.get("Dc_mm")),
                ("Dts_mm", s.get("Dts_mm")),
                ("SR_N", s.get("SR_N")),
                ("F_molle_N", s.get("F_molle_N")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC001A", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC002 (meta)
        for (rid, nm, ca, ua) in (list_dc002_calcs(user_id, limit=1000) or []):
            meta = get_dc002_calc_with_meta(rid, user_id) or {}
            s = _dc002_summarize(meta)
            summary = _kv_str([
                ("G_mm", s.get("G_mm")),
                ("Pa_MPa", s.get("Pa_MPa")),
                ("Wm1_N", s.get("Wm1_N")),
                ("Sa_eff_MPa", s.get("Sa_eff_MPa")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC002", "id": s.get("id") or rid, "name": s.get("name") or nm,
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(s.get("created_at") or ca), "updated_at": _fmt_ts(s.get("updated_at") or ua),
            })

        # DC002A
        for x in _norm_list_rows(list_dc002a_calcs(user_id, limit=1000)):
            rec = get_dc002a_calc(x["id"], user_id) or {}
            s = _dc002a_summarize(rec)
            summary = _kv_str([
                ("G_mm", s.get("G_mm")),
                ("Pa_test_MPa", s.get("Pa_test_MPa")),
                ("S_MPa", s.get("S_MPa")),
                ("n", s.get("n")),
                ("Sa_eff_MPa", s.get("Sa_eff_MPa")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC002A", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC003
        for x in _norm_list_rows(list_dc003_calcs(user_id, limit=1000)):
            rec = get_dc003_calc(x["id"], user_id) or {}
            s = _dc003_summarize(rec)
            summary = _kv_str([
                ("Dt_mm", s.get("Dt_mm")),
                ("Db_mm", s.get("Db_mm")),
                ("Hb_mm", s.get("Hb_mm")),
                ("BBS_MPa", s.get("BBS_MPa")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC003", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC004
        for x in _norm_list_rows(list_dc004_calcs(user_id, limit=1000)):
            rec = get_dc004_calc(x["id"], user_id) or {}
            s = _dc004_summarize(rec)
            summary = _kv_str([
                ("material", s.get("material")),
                ("thickness_mm", s.get("thickness_mm")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC004", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC005
        for x in _norm_list_rows(list_dc005_calcs(user_id, limit=1000)):
            rec = get_dc005_calc(x["id"], user_id) or {}
            s = _dc005_summarize(rec)
            summary = _kv_str([
                ("G_mm", s.get("G_mm")),
                ("Gstem_mm", s.get("Gstem_mm")),
                ("Pa_MPa", s.get("Pa_MPa")),
                ("n", s.get("n")),
                ("Sa_eff_MPa", s.get("Sa_eff_MPa")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC005", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })
        # DC005A
        for x in _norm_list_rows(list_dc005a_calcs(user_id, limit=1000)):
            rec = get_dc005a_calc(x["id"], user_id) or {}
            s = _dc005a_summarize(rec)
            summary = _kv_str([
                ("G_mm", s.get("G_mm")), ("Gstem_mm", s.get("Gstem_mm")),
                ("n", s.get("n")), ("bolt_size", s.get("bolt_size")),
                ("Sa_eff_MPa", s.get("Sa_eff_MPa")), ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC005A", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary, "created_at": _fmt_ts(x["created_at"]),
                "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC006
        for x in _norm_list_rows(list_dc006_calcs(user_id, limit=1000)):
            rec = get_dc006_calc(x["id"], user_id) or {}
            s = _dc006_summarize(rec)
            summary = _kv_str([
                ("D_seat_mm", s.get("D_seat_mm")),
                ("t_req_mm", s.get("t_req_mm")), ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC006", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary, "created_at": _fmt_ts(x["created_at"]),
                "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC006A
        for x in _norm_list_rows(list_dc006a_calcs(user_id, limit=1000)):
            rec = get_dc006a_calc(x["id"], user_id) or {}
            s = _dc006a_summarize(rec)
            summary = _kv_str([("D_mm", s.get("D_mm")), ("t_mm", s.get("t_mm")), ("check", s.get("check"))])
            rows_all.append({
                "type": "DC006A", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary, "created_at": _fmt_ts(x["created_at"]),
                "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC007 (Body)
        for x in _norm_list_rows(list_dc007_body_calcs(user_id, limit=1000)):
            rec = get_dc007_body_calc(x["id"], user_id) or {}
            s = _dc007_body_summarize(rec)
            summary = _kv_str([
                ("t_body_mm", s.get("t_body_mm")),
                ("sigma_MPa", s.get("sigma_MPa")),
                ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC007 (Body)", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary, "created_at": _fmt_ts(x["created_at"]),
                "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC007 (Body Holes)
        for x in _norm_list_rows(list_dc007_body_holes_calcs(user_id, limit=1000)):
            rec = get_dc007_body_holes_calc(x["id"], user_id) or {}
            s = _dc007_body_holes_summarize(rec)
            summary = _kv_str([
                ("n_holes", s.get("n_holes")), ("dia_mm", s.get("dia_mm")),
                ("min_lig_mm", s.get("min_lig_mm")), ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC007 (Holes)", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary, "created_at": _fmt_ts(x["created_at"]),
                "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC008
        for x in _norm_list_rows(list_dc008_calcs(user_id, limit=1000)):
            rec = get_dc008_calc(x["id"], user_id) or {}
            s = _dc008_summarize(rec)
            summary = _kv_str([
                ("stem_d_mm", s.get("stem_d_mm")),
                ("tau_MPa", s.get("tau_MPa")), ("verdict", s.get("verdict")),
            ])
            rows_all.append({
                "type": "DC008", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary, "created_at": _fmt_ts(x["created_at"]),
                "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC010
        for x in _norm_list_rows(list_dc010_calcs(user_id, limit=1000)):
            rec = get_dc010_calc(x["id"], user_id) or {}
            s = _dc010_summarize(rec)
            summary = _kv_str([
                ("Po_MPa", s.get("Po_MPa_in")),
                ("D_mm", s.get("D_mm")),
                ("Dc_mm", s.get("Dc_mm")),
                ("Tbb1_Nm", s.get("Tbb1_Nm")),
            ])
            rows_all.append({
                "type": "DC010", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC011
        for x in _norm_list_rows(list_dc011_calcs(user_id, limit=1000)):
            rec = get_dc011_calc(x["id"], user_id) or {}
            s = _dc011_summarize(rec)
            summary = _kv_str([
                ("inner_mm", s.get("inner_bore_mm")),
                ("seat_mm", s.get("seat_bore_mm")),
                ("beta", s.get("beta")),
                ("theta_deg", s.get("theta_deg")),
                ("Cv", s.get("Cv")),
            ])
            rows_all.append({
                "type": "DC011", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        # DC012
        for x in _norm_list_rows(list_dc012_calcs(user_id, limit=1000)):
            rec = get_dc012_calc(x["id"], user_id) or {}
            s = _dc012_summarize(rec)
            summary = _kv_str([
                ("P_kg", s.get("P_kg")),
                ("thread", s.get("thread")),
                ("Es_MPa", s.get("Es_MPa")),
                ("allowable_MPa", s.get("allowable_MPa")),
                ("OK", "OK" if s.get("stress_ok") else "NOT OK"),
            ])
            rows_all.append({
                "type": "DC012", "id": x["id"], "name": x["name"],
                "valve_design_id": s.get("valve_design_id"),
                "valve_design_name": s.get("valve_design_name"),
                "nps_in": s.get("nps_in"), "asme_class": s.get("asme_class"),
                "summary": summary,
                "created_at": _fmt_ts(x["created_at"]), "updated_at": _fmt_ts(x["updated_at"]),
            })

        if not rows_all:
            st.info("No saved items found yet.")
        else:
            all_cols = ["type","id","name","valve_design_id","valve_design_name","nps_in","asme_class","summary","created_at","updated_at"]
            df_all = pd.DataFrame(rows_all, columns=all_cols)
            # Attempt numeric cast where it makes sense
            for c in ["nps_in","asme_class"]:
                df_all[c] = pd.to_numeric(df_all[c], errors="coerce")
            st.dataframe(df_all[all_cols], use_container_width=True, hide_index=True)

            st.caption("Tip: the **summary** column packs key, type-specific highlights for quick scanning.")
