# page_dc001.py
from __future__ import annotations
import math
import pandas as pd
import streamlit as st

from auth import require_role, current_user
from dc001_repo import (
    create_dc001_calc,
    list_dc001_calcs,
    get_dc001_calc,
    update_dc001_calc,
    delete_dc001_calc,
)
# Fallback to latest Valve design for base values
from valve_repo import list_valve_designs, get_valve_design
from wizard_base import get_base, is_locked


def render_dc001():
    """
    DC001 — Seat insert & spring calculation
    """

    # ---- access guard ----
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    # ---------- CSS ----------
    st.markdown(
        """
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
        """,
        unsafe_allow_html=True,
    )

    # ---------- helpers ----------
    def row(label: str):
        lc, rc = st.columns([1.25, 2.25])
        with lc:
            st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
        return rc

    def out_box(key: str, value, fmt: str = None):
        s = (fmt.format(value) if fmt else str(value))
        st.session_state[key] = s
        st.text_input("", key=key, disabled=True, label_visibility="collapsed")

    def _fmt(v):
        if v is None:
            return "—"
        try:
            f = float(v)
            if abs(f - round(f)) < 1e-9:
                return f"{int(round(f))}"
            return f"{f:.4f}"
        except Exception:
            return str(v)

    def kv_table(pairs):
        # Pairs: [(label, value), ...]
        rows = []
        for k, v in pairs:
            if isinstance(v, (dict, list, tuple)):
                v = str(v)
            rows.append({"Field": k, "Value": _fmt(v)})
        df = pd.DataFrame(rows)
        st.table(df)

    # ---------- header ----------
    st.markdown("<h2 style='margin:0;text-align:center;'>Seat insert and spring calculation</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin:0;text-align:center;'>DC001</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # — Hydrate base defaults from the wizard lock (if present) —
    wb = get_base() if is_locked() else None
    if wb:
        # Ensure the same widget keys are pre-populated
        st.session_state["valve_nps"] = wb.get("nps_in", st.session_state.get("valve_nps"))
        st.session_state["valve_asme_class"] = wb.get("asme_class", st.session_state.get("valve_asme_class"))
        st.session_state["nps_in"] = wb.get("nps_in")
        st.session_state["asme_class"] = wb.get("asme_class")
        # Also set active id/name so the banner shows & carries across pages
        if wb.get("design_id"):
            st.session_state["active_design_id"] = wb.get("design_id")
        if wb.get("name"):
            st.session_state["active_design_name"] = wb.get("name")

    # ---------- resolve base (robust) ----------
    def _resolve_base_for_dc001():
        # 1) Prefer explicit “active” (if valve page set these)
        active_design_id   = st.session_state.get("active_design_id")
        active_design_name = st.session_state.get("active_design_name")
        nps                = st.session_state.get("nps_in")
        asme               = st.session_state.get("asme_class")
        bore               = st.session_state.get("bore_diameter_mm")
        op_mpa             = st.session_state.get("operating_pressure_mpa")

        # 2) Fall back to valve page widget keys
        if nps is None:
            nps = st.session_state.get("valve_nps")
        if asme is None:
            asme = st.session_state.get("valve_asme_class")

        # 3) If still missing, pull user's latest saved valve design (robust unpack)
        if (nps is None or asme is None or bore is None or op_mpa is None) and user_id:
            try:
                recents = list_valve_designs(user_id, limit=1)  # may return (id, name) or (id, name, created)
                if recents:
                    rid, rname = None, "Untitled"
                    first = recents[0]
                    if isinstance(first, (list, tuple)):
                        if len(first) >= 1: rid = first[0]
                        if len(first) >= 2 and first[1] not in (None, ""): rname = first[1]
                    elif isinstance(first, dict):
                        rid = first.get("id") or first.get("design_id")
                        rname = first.get("name") or rname
                    elif isinstance(first, str):
                        rid = first
                    if rid:
                        vdata = get_valve_design(rid, user_id) or {}
                        vcalc = vdata.get("calculated") or {}
                        nps   = vdata.get("nps_in", nps)
                        asme  = vdata.get("asme_class", asme)
                        bore  = vcalc.get("bore_diameter_mm", bore)
                        # prefer calculated operating pressure if present, otherwise legacy top-level
                        op_mpa = vcalc.get("operating_pressure_mpa", vdata.get("calc_operating_pressure_mpa", op_mpa))
                        active_design_id = active_design_id or rid
                        active_design_name = active_design_name or rname
                        # also prime session for the next pages
                        st.session_state.setdefault("nps_in", nps)
                        st.session_state.setdefault("asme_class", asme)
                        st.session_state.setdefault("bore_diameter_mm", bore)
                        st.session_state.setdefault("operating_pressure_mpa", op_mpa)
                        st.session_state.setdefault("active_design_id", active_design_id)
                        st.session_state.setdefault("active_design_name", active_design_name)
            except Exception:
                pass

        return {
            "active_design_id": active_design_id,
            "active_design_name": active_design_name,
            "nps_in": nps,
            "asme_class": asme,
            "bore_diameter_mm": bore if bore is not None else 62.30,
            "operating_pressure_mpa": op_mpa if op_mpa is not None else 10.21,
        }

    base = _resolve_base_for_dc001()

    if base["active_design_id"]:
        st.success(
            f"Base design: **{base['active_design_name']}** • "
            f"NPS **{_fmt(base['nps_in'])}** • ASME **{_fmt(base['asme_class'])}**  "
            f"• Bore **{_fmt(base['bore_diameter_mm'])} mm** • P **{_fmt(base['operating_pressure_mpa'])} MPa**"
        )
    else:
        st.info(
            "Using defaults because no active Valve design was found. "
            "Tip: Save a Valve design and set it active to carry values across steps."
        )

    # ==========================================================
    # A) SPRING LOAD
    # ==========================================================
    st.subheader("Spring load calculation", anchor=False)

    i = row("Seat insert medium dia. (Ball/seat seal diameter)  Dm  [mm]")
    Dm = i.number_input(
        "",
        value=round(float(base["bore_diameter_mm"]), 2),
        step=0.01, format="%.2f",
        key="dc001_dm", label_visibility="collapsed"
    )

    i = row("Load · length unit  c1  [N/mm]")
    c1 = i.number_input("", value=2.50, step=0.10, format="%.2f",
                        key="dc001_c1", label_visibility="collapsed")

    i = row("Correction factor  z  [-]")
    z = i.number_input("", value=1.00, step=0.01, format="%.2f",
                       key="dc001_z", label_visibility="collapsed")

    Fmt = math.pi * max(Dm, 0.0) * max(c1, 0.0) * max(z, 0.0)
    i = row("Theoric load spring  Fmt  [N]")
    with i:
        out_box("dc001_out_Fmt", Fmt, "{:.6f}")

    st.markdown("")

    # ==========================================================
    # B) Nº OF SPRINGS
    # ==========================================================
    st.subheader("N° of springs calculation", anchor=False)

    i = row("Load at theoric packing  P  [N]")
    P = i.number_input("", value=1020.0, step=1.0, format="%.3f",
                       key="dc001_P", label_visibility="collapsed")

    Nm = Fmt / (P if P else 1e-9)
    i = row("N° of springs request  Nm = Fmt / P  [-]")
    with i:
        out_box("dc001_out_Nm", Nm, "{:.8f}")

    i = row("Theoric spring arrow  f  [mm]")
    f = i.number_input("", value=2.19, step=0.01, format="%.2f",
                       key="dc001_f", label_visibility="collapsed")

    Pr = P * (f - 0.5) / (f if f else 1e-9)
    i = row("Load at real packing  Pr = P × (f − 0.5) / f  [N]")
    with i:
        out_box("dc001_out_Pr", Pr, "{:.6f}")

    Nmr = Fmt / (Pr if Pr else 1e-9)
    i = row("N° of springs real  Nmr = Fmt / Pr  [-]")
    with i:
        out_box("dc001_out_Nmr", Nmr, "{:.8f}")

    Nma_default = max(1, int(math.ceil(max(Nmr, 0.0))))
    i = row("N° of springs in the project  Nma  [-]")
    Nma = i.number_input("", value=Nma_default, step=1, min_value=1,
                         key="dc001_Nma", label_visibility="collapsed")

    st.markdown("")

    # ==========================================================
    # C) SPRING CHECK
    # ==========================================================
    st.subheader("SPRING CHECK", anchor=False)

    Fmr = float(Nma) * float(Pr)
    i = row("Total load of springs  Fmr = Nma × Pr  [N]")
    with i:
        out_box("dc001_out_Fmr", Fmr, "{:.6f}")

    C1effective = Fmr / (math.pi * (Dm if Dm else 1e-9))
    i = row("C1 effective = Fmr / (π × Dm)  [N/mm]")
    with i:
        out_box("dc001_out_C1", C1effective, "{:.6f}")

    spring_check = "VERIFIED" if Fmr >= Fmt else "NOT VERIFIED"
    i = row("Check")
    with i:
        out_box("dc001_out_check", spring_check)

    st.markdown("")

    # ==========================================================
    # D) SEAT INSERT MATERIAL
    # ==========================================================
    st.subheader("SEAT INSERT MATERIAL", anchor=False)
    st.caption("Y = Max. Seat Insert Stress")

    materials = [
        ("PTFE", 9.0),
        ("PTFE Reinforced", 12.0),
        ("NYLON 12 G", 60.0),
        ("PCTFE (KELF)", 60.0),
        ("PEEK", 90.0),
        ("DELVON V", 60.0),
    ]
    mat_names = [m[0] for m in materials]
    Y_lookup = dict(materials)

    i = row("Material")
    mat_choice = i.selectbox("", options=mat_names, index=0,
                             key="dc001_mat", label_visibility="collapsed")

    Y_max = float(Y_lookup[mat_choice])
    i = row("Y max  [MPa] (catalogue)")
    with i:
        out_box("dc001_out_Ymax", Y_max, "{:.3f}")

    st.markdown("")

    # ==========================================================
    # E) SEAT INSERT VALIDATION
    # ==========================================================
    st.subheader("Seat Insert validation", anchor=False)

    i = row("External seat insert diameter  De  [mm]")
    De = i.number_input("", value=66.74, step=0.01, format="%.2f",
                        key="dc001_De", label_visibility="collapsed")

    i = row("Internal seat insert diameter  Di  [mm]")
    Di = i.number_input("", value=57.86, step=0.01, format="%.2f",
                        key="dc001_Di", label_visibility="collapsed")

    Dcs = (De + 2.0 * Di) / 3.0
    i = row("Seat insert medium dia.  Dcs  [mm]")
    with i:
        out_box("dc001_out_Dcs", Dcs, "{:.2f}")

    i = row("Seat/Closure seal diameter  Dc  [mm]")
    Dc = i.number_input("", value=round(float(Dm), 2), step=0.01, format="%.2f",
                        key="dc001_Dc", label_visibility="collapsed")

    i = row("Rating pressure  Pa  [MPa]")
    Pa = i.number_input("", value=float(base["operating_pressure_mpa"]),
                        step=0.01, format="%.2f",
                        key="dc001_Pa", label_visibility="collapsed")

    DeDi_mean = (De + Di) / 2.0
    pressure_term = (Dc**2 - DeDi_mean**2) * 1.1 * Pa * (math.pi / 4.0)   # N
    F = pressure_term + Fmr
    i = row("Linear Load  F = (Dc² − ((De+Di)/2)²) · 1.1 · Pa · π/4 + Fmr  [N]")
    with i:
        out_box("dc001_out_F", F, "{:.2f}")

    denom_area = (De**2 - Di**2) * math.pi
    Q = F * 4.0 / (denom_area if denom_area else 1e-9)  # MPa
    i = row("Insert resistance  Q = F · 4 / ((De² − Di²) · π)  [MPa]")
    with i:
        out_box("dc001_out_Q", Q, "{:.2f}")

    result = "OK (Q < Y max)" if Q < Y_max else "NOT OK (Q ≥ Y max)"
    i = row("Result")
    with i:
        out_box("dc001_out_result", result)

    # ---------- stash for other pages ----------
    st.session_state["dc001"] = {
        "Dm": Dm, "c1": c1, "z": z, "P": P, "f": f, "Nma": int(Nma),
        "Fmt": Fmt, "Nm": Nm, "Pr": Pr, "Nmr": Nmr,
        "Fmr": Fmr, "C1effective": C1effective, "spring_check": spring_check,
        "Material": mat_choice, "Y_max": Y_max,
        "De": De, "Di": Di, "Dcs": Dcs, "Dc": Dc, "Pa": Pa,
        "F": F, "Q": Q, "result": result,
    }

    # ---------------- SAVE / LOAD (DC001) ----------------
    st.markdown("---")
    st.markdown("### Save / Load (DC001)")

    # Build payload with base + inputs + computed values
    payload = {
        "base": {
            "valve_design_id": base["active_design_id"],
            "valve_design_name": base["active_design_name"],
            "nps_in": base["nps_in"],
            "asme_class": base["asme_class"],
            "bore_diameter_mm": float(base["bore_diameter_mm"]) if base["bore_diameter_mm"] is not None else None,
            "operating_pressure_mpa": float(base["operating_pressure_mpa"]) if base["operating_pressure_mpa"] is not None else None,
        },
        "inputs": {
            "Dm_mm": float(Dm),
            "c1_N_per_mm": float(c1),
            "z": float(z),
            "P_N": float(P),
            "f_mm": float(f),
            "Nma": int(Nma),
            "material": mat_choice,
            "Y_max_MPa": float(Y_max),
            "De_mm": float(De),
            "Di_mm": float(Di),
            "Dc_mm": float(Dc),
            "Pa_MPa": float(Pa),
        },
        "computed": {
            "Fmt_N": float(Fmt),
            "Nm": float(Nm),
            "Pr_N": float(Pr),
            "Nmr": float(Nmr),
            "Fmr_N": float(Fmr),
            "C1_effective_N_per_mm": float(C1effective),
            "spring_check": spring_check,
            "Dcs_mm": float(Dcs),
            "F_N": float(F),
            "Q_MPa": float(Q),
            "result": result,
        }
    }

    default_name = f"DC001_Dm{Dm:.2f}_Nma{int(Nma)}_Pa{Pa:.2f}"

    cL, cR = st.columns([1.2, 1.8], gap="large")
    with cL:
        design_name = st.text_input("Save as name", value=default_name, key="dc001_save_name")
        if st.button("💾 Save DC001", type="primary", use_container_width=True, key="btn_dc001_save"):
            if not user_id:
                st.error("You must be logged in.")
            else:
                try:
                    new_id = create_dc001_calc(user_id, design_name, payload)
                    st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
                except Exception as e:
                    st.error(f"Save failed: {e}")

    with cR:
        raw_items = list_dc001_calcs(user_id) if user_id else []
        # Normalize results to a list of (id, name) pairs (handles 2/3-tuples, dicts, or strings)
        items: list[tuple[str, str]] = []
        for r in raw_items:
            rid, nm = None, "Untitled"
            if isinstance(r, (list, tuple)):
                if len(r) >= 1: rid = r[0]
                if len(r) >= 2 and r[1] not in (None, ""): nm = r[1]
            elif isinstance(r, dict):
                rid = r.get("id") or r.get("calc_id") or r.get("id_")
                nm = r.get("name") or r.get("title") or nm
            elif isinstance(r, str):
                rid = r
            if rid:
                items.append((str(rid), str(nm)))

        if not items:
            st.info("No DC001 saves yet.")
        else:
            label_to_id = {f"{nm} ({_id[:8]}…)" : _id for (_id, nm) in items}
            pick = st.selectbox("My DC001 saves", ["-- none --", *label_to_id.keys()], key="dc001_pick")
            if pick != "-- none --":
                sel_id = label_to_id[pick]
                data = get_dc001_calc(sel_id, user_id) or {}

                # ---------- Pretty Summary (expanded)
                st.markdown("#### Summary")

                base_saved = data.get("base") or {}
                # If older save without base, derive it now so the table isn't blank.
                base_display = {
                    "Valve design name": base_saved.get("valve_design_name") or base["active_design_name"],
                    "Valve design ID":   base_saved.get("valve_design_id")   or base["active_design_id"],
                    "NPS [in]":          base_saved.get("nps_in")            or base["nps_in"],
                    "ASME Class":        base_saved.get("asme_class")        or base["asme_class"],
                    "Bore (base) [mm]":  base_saved.get("bore_diameter_mm")  or base["bore_diameter_mm"],
                    "P (base) [MPa]":    base_saved.get("operating_pressure_mpa") or base["operating_pressure_mpa"],
                }

                ins   = data.get("inputs", {}) or {}
                comp  = data.get("computed", {}) or {}

                st.markdown("**Base (from Valve Data)**")
                kv_table(list(base_display.items()))

                st.markdown("**Overview**")
                kv_table([
                    ("Dm [mm]", ins.get("Dm_mm")),
                    ("N° springs (Nma)", ins.get("Nma")),
                    ("Rating pressure Pa [MPa]", ins.get("Pa_MPa")),
                    ("Material", ins.get("material")),
                    ("Y max [MPa]", ins.get("Y_max_MPa")),
                ])

                st.markdown("**Forces & Counts**")
                kv_table([
                    ("Fmt [N]", comp.get("Fmt_N")),
                    ("Nm [-]",  comp.get("Nm")),
                    ("Pr [N]",  comp.get("Pr_N")),
                    ("Nmr [-]", comp.get("Nmr")),
                    ("Fmr [N]", comp.get("Fmr_N")),
                    ("C1 effective [N/mm]", comp.get("C1_effective_N_per_mm")),
                    ("Spring check", comp.get("spring_check")),
                ])

                st.markdown("**Geometry & Validation**")
                kv_table([
                    ("De [mm]", ins.get("De_mm")),
                    ("Di [mm]", ins.get("Di_mm")),
                    ("Dc [mm]", ins.get("Dc_mm")),
                    ("Dcs [mm]", comp.get("Dcs_mm")),
                    ("F [N]", comp.get("F_N")),
                    ("Q [MPa]", comp.get("Q_MPa")),
                    ("Result", comp.get("result")),
                ])

                # ---------- Detailed (all fields present) ----------
                def flatten_for_table(d: dict, prefix: str):
                    rows = []
                    for k, v in d.items():
                        label = f"{prefix}.{k}"
                        rows.append((label, v))
                    return rows

                with st.expander("Detailed (all fields saved)", expanded=False):
                    all_pairs = []
                    # show sections in a consistent order if present
                    for sect, prefix in [
                        (data.get("base") or {}, "base"),
                        (data.get("inputs") or {}, "inputs"),
                        (data.get("computed") or {}, "computed"),
                        (data.get("calculated") or {}, "calculated"),
                        (data.get("geometry") or {}, "geometry"),
                    ]:
                        if sect:
                            all_pairs.extend(flatten_for_table(sect, prefix))
                    # any other top-level keys that aren't dicts
                    for k, v in data.items():
                        if k not in ("base", "inputs", "computed", "calculated", "geometry"):
                            all_pairs.append((k, v))
                    kv_table(all_pairs)

                # Raw JSON (always handy for debugging)
                with st.expander("Raw JSON", expanded=False):
                    st.json(data)

                # ---------- Actions ----------
                d1, d2, d3 = st.columns(3)
                with d1:
                    if st.button("⬅ Load into form", key=f"dc001_load_{sel_id}", use_container_width=True):
                        st.session_state["dc001_dm"] = float(ins.get("Dm_mm", Dm))
                        st.session_state["dc001_c1"] = float(ins.get("c1_N_per_mm", c1))
                        st.session_state["dc001_z"]  = float(ins.get("z", 1.0))
                        st.session_state["dc001_P"]  = float(ins.get("P_N", 1020.0))
                        st.session_state["dc001_f"]  = float(ins.get("f_mm", 2.19))
                        st.session_state["dc001_Nma"] = int(ins.get("Nma", 1))
                        st.session_state["dc001_mat"] = ins.get("material", "PTFE")
                        st.session_state["dc001_De"]  = float(ins.get("De_mm", 66.74))
                        st.session_state["dc001_Di"]  = float(ins.get("Di_mm", 57.86))
                        st.session_state["dc001_Dc"]  = float(ins.get("Dc_mm", st.session_state.get("dc001_dm", Dm)))
                        st.session_state["dc001_Pa"]  = float(ins.get("Pa_MPa", base["operating_pressure_mpa"]))
                        st.success("Loaded into form.")
                        st.rerun()

                with d2:
                    newname = st.text_input("Rename", value=pick.split(" (")[0], key=f"dc001_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc001_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc001_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")

                with d3:
                    if st.button("🗑️ Delete", key=f"dc001_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc001_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")

    # ---------------- NEXT PAGE BUTTON ----------------
    st.markdown("")
    _, _, _, col_next = st.columns([1,1,1,1])
    with col_next:
        if st.button("Next → DC001A", use_container_width=True):
            st.session_state.active_page = "DC001A (Self relieving)"
            st.rerun()
