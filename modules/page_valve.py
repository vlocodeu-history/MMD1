# page_valve.py
from __future__ import annotations
import streamlit as st
from auth import require_role, current_user
from valve_repo import (
    create_valve_design,
    list_valve_designs,
    get_valve_design,
    update_valve_design,
    delete_valve_design,
)
from wizard_base import start_wizard, get_base, is_locked


def render_valve():
    # ---- protect page ----
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    # --- CSS: align labels to input height
    st.markdown(
        """
        <style>
        .row-label{
            display:flex; align-items:center; justify-content:flex-end;
            height:38px; padding:0 .5rem; margin:0;
            font-weight:600; color:#0f172a; white-space:nowrap; text-align:right;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ---- constants / demo data ----
    ASME_RATING_MPA = {150: 2.001, 300: 5.17, 400: 6.896, 600: 10.21, 900: 15.519, 1500: 25.869, 2500: 43.115, 4500: 77.607}
    NPS_BORE_MM     = {0.5:15.0, 0.75:20.0, 1.0:25.0, 1.5:40.0, 2.0:51.0, 3.0:78.0, 4.0:102.0, 6.0:154.0, 8.0:202.0, 10.0:254.0, 12.0:303.0}
    F2F_MM          = {(2.0,600):295}

    def calc_operating_pressure_mpa(asme_class: int) -> float:
        return float(ASME_RATING_MPA.get(asme_class, 0.0))

    def calc_bore_diameter_mm(nps: float) -> float:
        return float(NPS_BORE_MM.get(nps, round(nps*25.4, 1)))

    def calc_face_to_face_mm(nps: float, asme_class: int):
        v = F2F_MM.get((nps, asme_class))
        return int(v) if v is not None else None

    def calc_body_wall_thickness_mm(P_mpa: float, D_mm: float, S_mpa: float, CA_mm: float):
        if S_mpa <= 0 or (2*S_mpa - P_mpa) <= 0:
            return None
        t = (P_mpa * D_mm) / (2 * S_mpa - P_mpa) + CA_mm
        return round(float(t), 2)

    ALLOWABLE_STRESS_PRESETS = {
        "ASTM A182 F316": 207,
        "ASTM A182 F44":  300,
        "ASTM A350 LF3 BON": 350,
        "ASTM A182 F6a cl.2": 380,
        "ASTM A479 XM19 (Nitronic 50)": 380,
        "ASTM B564 UNS N06625": 414,
        "Monel K500 Max ": 414,
        "ASTM A694 F60": 414,
        "ASTM A182 F51 ": 448.5,
        "ASTM A182 F53/55": 550,
        "ASTM A182 F6NM": 621,
        "ASTM A564 Gr. 630 H1150+1150 (17.04 PH)": 725,
        "ASTM B637 N07750 Type2 (X 750)": 790,
        "ASTM B381 Gr. F-5": 828,
        "ASTM B637 N07718 (Inconel 718)": 1034,
        "ASTM A182 F304": 207,
        "ASTM A182 F304L": 172,
        "ASTM A182 F316L": 172,
        "ASTM A350 LF1": 207,
        "ASTM A182 F304LN": 207,
        "ASTM A182 F316LN": 207,
        "ASTM A105N": 248,
        "ASTM A350 LF2 CL.1": 248,
    }

    # ----- header -----
    h1, h2 = st.columns([3, 2])
    with h1:
        st.markdown("<h3 style='text-align:center;margin:0;'>VALVE DATA TRUNNION BALL VALVE</h3>", unsafe_allow_html=True)
    with h2:
        st.markdown("<h4 style='text-align:center;margin:0;'>SIDE ENTRY TYPE</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # ----- hydrate from wizard lock (if any) -----
    wb = get_base() if is_locked() else None
    if wb:
        # Pre-set the same keys your widgets use so the defaults stick everywhere.
        st.session_state["valve_nps"] = wb.get("nps_in", st.session_state.get("valve_nps"))
        st.session_state["valve_asme_class"] = wb.get("asme_class", st.session_state.get("valve_asme_class"))
        st.session_state["nps_in"] = wb.get("nps_in")
        st.session_state["asme_class"] = wb.get("asme_class")

    # ----- active design banner (shared base for other pages) -----
    if st.session_state.get("active_design_id"):
        nm = st.session_state.get("active_design_name", "Untitled")
        nps_base = st.session_state.get("nps_in")
        cls_base = st.session_state.get("asme_class")
        st.success(f"Active design: **{nm}**  •  NPS **{nps_base}**  •  ASME Class **{cls_base}**")
    else:
        st.info("No active design selected. Save or load a design, then click **Set as active** to reuse NPS/Class across pages.")

    # ---------- helper to render one row (label left, input right) ----------
    def row(label: str):
        lcol, icol = st.columns([1.1, 2.2])
        with lcol:
            st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
        return icol

    # ---------- top group ----------
    i = row("Nominal Pipe Size (NPS) [in]")
    nps = i.selectbox(
        "", [0.5,0.75,1.0,1.5,2.0,3.0,4.0,6.0,8.0,10.0,12.0],
        index=4, key="valve_nps", label_visibility="collapsed"
    )

    i = row("ASME Class")
    asme_class = i.selectbox(
        "", [150,300,400,600,900,1500,2500,4500],
        index=3, key="valve_asme_class", label_visibility="collapsed"
    )

    i = row("Calculation Pressure P (MPa) — ASME B16.34 at ambient")
    P_mpa = calc_operating_pressure_mpa(asme_class)
    i.text_input(
        "", value=f"{P_mpa:.2f}" if P_mpa else "",
        disabled=True, key="valve_P_mpa_display", label_visibility="collapsed"
    )

    st.markdown("---")

    # ---------- input parameters ----------
    st.markdown("### Input Parameters")

    i = row("Internal Bore (Ball/Seat) [mm]")
    internal_bore_mm = i.number_input(
        "", value=float(calc_bore_diameter_mm(nps)), step=0.1, format="%.1f",
        key="valve_internal_bore_mm", label_visibility="collapsed"
    )

    i = row("Face to Face (F-F) [mm]")
    f2f_default = calc_face_to_face_mm(nps, asme_class)
    face_to_face_mm = i.number_input(
        "", value=int(f2f_default if f2f_default is not None else 295), step=1,
        key="valve_face_to_face_mm", label_visibility="collapsed"
    )

    i = row("Design Temperature Min (°C)")
    temp_min_c = i.number_input(
        "", value=-29, step=1, key="valve_temp_min_c", label_visibility="collapsed"
    )

    i = row("Design Temperature Max (°C)")
    temp_max_c = i.number_input(
        "", value=150, step=1, key="valve_temp_max_c", label_visibility="collapsed"
    )

    i = row("Corrosion Allowance CA [mm]")
    corrosion_allowance_mm = i.number_input(
        "", value=3.0, step=0.1, format="%.1f",
        key="valve_corrosion_allowance_mm", label_visibility="collapsed"
    )

    st.markdown("---")

    # ---------- materials ----------
    st.markdown("### Materials (Inputs)")

    i = row("Body / Closure Material")
    body_closure = i.text_input("", value="ASTM A350 LF2 CL.1", key="valve_body_closure", label_visibility="collapsed")

    i = row("Ball / Seat Material")
    ball_seat = i.text_input("", value="ASTM A479 UNS S31600", key="valve_ball_seat", label_visibility="collapsed")

    i = row("Stem Material")
    stem_material = i.text_input("", value="ASTM A479 UNS S31803", key="valve_stem_material", label_visibility="collapsed")

    i = row("Insert Material")
    insert_material = i.text_input("", value="DELVON V", key="valve_insert_material", label_visibility="collapsed")

    i = row("Bolts Material")
    bolts_material = i.text_input("", value="ASTM A193 B7M / ASTM A194 2HM", key="valve_bolts_material", label_visibility="collapsed")

    i = row("Flange Ends")
    flange_ends = i.text_input("", value="RTJ", key="valve_flange_ends", label_visibility="collapsed")

    st.markdown("---")

    # ---------- allowable stress ----------
    st.markdown("### Allowable Stress (for demo wall thickness calc)")

    i = row("Preset")
    allow_key = i.selectbox(
        "", list(ALLOWABLE_STRESS_PRESETS.keys()), index=0,
        key="valve_allow_preset", label_visibility="collapsed"
    )

    i = row("Allowable Stress S [MPa]")
    allowable_stress_mpa = i.number_input(
        "", value=float(ALLOWABLE_STRESS_PRESETS[allow_key]),
        step=1.0, key="valve_allow_S_mpa", label_visibility="collapsed"
    )

    st.markdown("---")

    # ---------- calculated values ----------
    st.markdown("## Calculated Values")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Operating Pressure (MPa)", f"{P_mpa:.2f}")
    with c2:
        st.metric("Bore Diameter (mm)", f"{internal_bore_mm:.1f}")
    with c3:
        st.metric("Face to Face (mm)", f"{face_to_face_mm:d}")

    c4, _, _ = st.columns(3)
    with c4:
        t_mm = calc_body_wall_thickness_mm(P_mpa, internal_bore_mm, allowable_stress_mpa, corrosion_allowance_mm)
        st.metric("Body Wall Thickness (mm) — demo", f"{t_mm:.2f}" if t_mm is not None else "N/A")

    # ---------- stash a few globals for other pages ----------
    st.session_state["operating_pressure_mpa"] = float(P_mpa)
    st.session_state["bore_diameter_mm"] = float(internal_bore_mm)

    # ---------- SAVE / LOAD ----------
    st.markdown("---")
    st.markdown("### Save / Load")

    # Friendly default name
    default_name = f"NPS{nps:g}_Class{asme_class}_F2F{face_to_face_mm}"

    cL, cR = st.columns([1.2, 1.8])

    # Build the payload to persist (all inputs + calculated)
    payload = {
        "nps_in": float(nps),
        "asme_class": int(asme_class),
        "calc_operating_pressure_mpa": float(P_mpa),
        "inputs": {
            "internal_bore_mm": float(internal_bore_mm),
            "face_to_face_mm": int(face_to_face_mm),
            "temp_min_c": int(temp_min_c),
            "temp_max_c": int(temp_max_c),
            "corrosion_allowance_mm": float(corrosion_allowance_mm),
            "materials": {
                "body_closure": body_closure,
                "ball_seat": ball_seat,
                "stem_material": stem_material,
                "insert_material": insert_material,
                "bolts_material": bolts_material,
                "flange_ends": flange_ends,
            },
            "allowable_stress": {
                "preset": allow_key,
                "S_mpa": float(allowable_stress_mpa),
            },
        },
        "calculated": {
            "operating_pressure_mpa": float(P_mpa),
            "bore_diameter_mm": float(internal_bore_mm),
            "face_to_face_mm": int(face_to_face_mm),
            "body_wall_thickness_mm": float(t_mm) if t_mm is not None else None,
        },
    }

    # ---- left: Save new
    with cL:
        name = st.text_input("Design name", value=default_name, key="valve_design_name")
        if st.button("💾 Save to my library", type="primary", use_container_width=True, key="btn_save_valve"):
            if not user_id:
                st.error("You must be logged in.")
            else:
                try:
                    new_id = create_valve_design(user_id, name, payload)
                    # Set as active base for the multi-step process
                    st.session_state["active_design_id"] = new_id
                    st.session_state["active_design_name"] = name
                    st.session_state["nps_in"] = float(nps)
                    st.session_state["asme_class"] = int(asme_class)
                    st.session_state["design_base"] = {
                        "design_id": new_id,
                        "name": name,
                        "nps_in": float(nps),
                        "asme_class": int(asme_class),
                    }
                    st.success(f"Saved ✔ (ID: {new_id[:8]}…) • Set as active design.")
                    # Lock base for the multi-step wizard
                    start_wizard(st.session_state["design_base"])
                except Exception as e:
                    st.error(f"Save failed: {e}")

    # ---- right: Load / manage existing
    with cR:
        # List recent designs for this user (normalize to (id, name) pairs)
        raw_items = list_valve_designs(user_id) if user_id else []
        items: list[tuple[str, str]] = []
        for r in raw_items:  # ← normalized to (id, name)
            rid, nm = None, "Untitled"
            if isinstance(r, (list, tuple)):
                if len(r) >= 1: rid = r[0]
                if len(r) >= 2 and r[1] not in (None, ""): nm = r[1]
            elif isinstance(r, dict):
                rid = r.get("id") or r.get("design_id") or r.get("id_")
                nm = r.get("name") or r.get("title") or nm
            elif isinstance(r, str):
                rid = r
            if rid:
                items.append((str(rid), str(nm)))

        if not items:
            st.info("No saved designs yet.")
        else:
            label_to_id = {f"{nm}  ({_id[:8]}…)" : _id for (_id, nm) in items}
            pick = st.selectbox("My recent designs", ["-- none --", *label_to_id.keys()], key="valve_recent_pick")
            if pick != "-- none --":
                sel_id = label_to_id[pick]
                data = get_valve_design(sel_id, user_id)

                if data:
                    nm_only = pick.split("  (")[0]
                    st.caption(f"Selected: **{nm_only}**  •  ID `{sel_id}`")

                    # Actions row
                    a1, a2, a3, a4 = st.columns([1,1,1,1], gap="small")
                    with a1:
                        if st.button("⬅ Load into form", key=f"load_into_form_{sel_id}", use_container_width=True):
                            # Repopulate widget state from payload
                            base = data
                            st.session_state["valve_nps"] = float(base.get("nps_in", nps))
                            st.session_state["valve_asme_class"] = int(base.get("asme_class", asme_class))

                            inp = (base.get("inputs") or {})
                            mats = (inp.get("materials") or {})
                            allow = (inp.get("allowable_stress") or {})

                            st.session_state["valve_internal_bore_mm"] = float(inp.get("internal_bore_mm", internal_bore_mm))
                            st.session_state["valve_face_to_face_mm"] = int(inp.get("face_to_face_mm", face_to_face_mm))
                            st.session_state["valve_temp_min_c"] = int(inp.get("temp_min_c", temp_min_c))
                            st.session_state["valve_temp_max_c"] = int(inp.get("temp_max_c", temp_max_c))
                            st.session_state["valve_corrosion_allowance_mm"] = float(inp.get("corrosion_allowance_mm", corrosion_allowance_mm))

                            st.session_state["valve_body_closure"] = mats.get("body_closure", body_closure)
                            st.session_state["valve_ball_seat"] = mats.get("ball_seat", ball_seat)
                            st.session_state["valve_stem_material"] = mats.get("stem_material", stem_material)
                            st.session_state["valve_insert_material"] = mats.get("insert_material", insert_material)
                            st.session_state["valve_bolts_material"] = mats.get("bolts_material", bolts_material)
                            st.session_state["valve_flange_ends"] = mats.get("flange_ends", flange_ends)

                            st.session_state["valve_allow_preset"] = allow.get("preset", st.session_state.get("valve_allow_preset"))
                            st.session_state["valve_allow_S_mpa"] = float(allow.get("S_mpa", allowable_stress_mpa))

                            # also update computed globals for other pages
                            st.session_state["operating_pressure_mpa"] = float(base.get("calc_operating_pressure_mpa", P_mpa))
                            st.session_state["bore_diameter_mm"] = float((base.get("calculated") or {}).get("bore_diameter_mm", internal_bore_mm))

                            st.success("Loaded into form.")
                            st.rerun()

                    with a2:
                        if st.button("⭐ Set as active", key=f"set_active_{sel_id}", use_container_width=True):
                            st.session_state["active_design_id"] = sel_id
                            st.session_state["active_design_name"] = nm_only
                            st.session_state["nps_in"] = float(data.get("nps_in", nps))
                            st.session_state["asme_class"] = int(data.get("asme_class", asme_class))
                            st.session_state["design_base"] = {
                                "design_id": sel_id,
                                "name": nm_only,
                                "nps_in": float(data.get("nps_in", nps)),
                                "asme_class": int(data.get("asme_class", asme_class)),
                            }
                            # Lock base for the multi-step wizard **before** rerun
                            start_wizard(st.session_state["design_base"])
                            st.success("Active design updated.")
                            st.rerun()

                    with a3:
                        newname = st.text_input("Rename to", value=nm_only, key=f"rename_input_{sel_id}")
                        if st.button("💾 Save name", key=f"save_rename_{sel_id}", use_container_width=True):
                            ok = update_valve_design(sel_id, user_id, name=newname)
                            if ok:
                                st.success("Renamed.")
                                st.rerun()
                            else:
                                st.error("Rename failed.")

                    with a4:
                        if st.button("🗑️ Delete", key=f"delete_{sel_id}", use_container_width=True):
                            ok = delete_valve_design(sel_id, user_id)
                            if ok:
                                # If deleting the active one, clear banner
                                if st.session_state.get("active_design_id") == sel_id:
                                    for k in ("active_design_id","active_design_name","design_base"):
                                        st.session_state.pop(k, None)
                                st.success("Deleted.")
                                st.rerun()
                            else:
                                st.error("Delete failed.")
