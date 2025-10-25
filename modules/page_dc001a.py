# page_dc001a.py
from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from PIL import Image
import streamlit as st

from auth import require_role, current_user
# Valve base (NPS/Class/Bore/Po)
from valve_repo import list_valve_designs, get_valve_design
# DC001 backend (source values for DC001A)
from dc001_repo import list_dc001_calcs, get_dc001_calc
# DC001A backend (save/load/manage)
from dc001a_repo import (
    create_dc001a_calc, list_dc001a_calcs, get_dc001a_calc,
    update_dc001a_calc, delete_dc001a_calc
)
from wizard_base import get_base, is_locked


# ---------- CSS ----------
ROW_CSS = """
<style>
.row-label{
  flex:0 0 360px; text-align:right;
  height:40px; display:flex; align-items:center; justify-content:flex-end;
  font-weight:600; color:#0f172a; white-space:nowrap; padding:0 .5rem;
}
.stTextInput > div > div > input,
.stNumberInput > div > div > input{ height:40px !important; padding:0 .7rem !important; }
.stSelectbox > div > div{ min-height:40px !important; }
.block-container .stMarkdown{ margin:0; }

/* Equation strip */
.eqbar { display:flex; align-items:center; gap:.5rem; flex-wrap:wrap; font-weight:700; }
.eqbar .lbl { font-style:italic; color:#0f172a; }
.eqbar .cell { padding:.35rem .6rem; border:1px solid rgba(15,23,42,.08); border-radius:.5rem; background:#fffbe6; }
.eqbar .op { margin:0 .2rem; font-weight:700; }
.eqbar .badge { padding:.35rem .6rem; border-radius:.5rem; font-weight:800; letter-spacing:.3px; }
.eqbar .ok  { background:#86efac; }   /* green 300 */
.eqbar .bad { background:#fecaca; }   /* red   300 */
</style>
"""

def _fmt(x: Any, digits: int = 2) -> str:
    if x is None: return "—"
    try:
        f = float(x)
        if abs(f - round(f)) < 1e-6: return f"{int(round(f))}"
        return f"{f:.{digits}f}"
    except Exception:
        return str(x)

def _kv_table(pairs: List[tuple[str, Any]]):
    import pandas as pd
    rows = [{"Field": k, "Value": _fmt(v)} for k, v in pairs]
    st.table(pd.DataFrame(rows))

def _try_show_diagram(size_px: int = 300):
    paths = ["dc001a_diagram.png", "assets/dc001a_diagram.png", "static/dc001a_diagram.png"]
    for p in paths:
        if os.path.exists(p):
            try:
                img = Image.open(p).convert("RGBA").resize((size_px, size_px), Image.LANCZOS)
                st.image(img, caption="Self-relieving seat sketch", use_column_width=False)
            except Exception as e:
                st.warning(f"Couldn't load diagram ({e}).")
            return
    st.info("Add **dc001a_diagram.png** (or put it in ./assets/ or ./static/) to display the sheet diagram here.")

def render_dc001a():
    """
    DC001A — Self Relieving
      SR [N]  :=  F [N]  (Linear Load from DC001 backend)
      Dc [mm] :=  Dm [mm] (seat insert medium dia) from DC001
      Dts[mm] :=  Dc [mm] (seat/closure seal dia) from DC001
      Compare: SR ≥ F_molle (where F_molle := DC001.Pr [N])
    """
    # ---- Access guard & user ----
    require_role(["user", "superadmin"])
    user = current_user() or {}
    user_id = user.get("id")

    st.markdown(ROW_CSS, unsafe_allow_html=True)

    # ---- helpers ----
    def row(label: str):
        lc, rc = st.columns([1.25, 2.25])
        with lc:
            st.markdown(f"<div class='row-label'>{label}</div>", unsafe_allow_html=True)
        return rc

    def out_box(key: str, value, fmt: str = None, disabled: bool = True):
        s = (fmt.format(value) if fmt else ("" if value is None else str(value)))
        st.session_state[key] = s
        st.text_input("", key=key, value=s, disabled=disabled, label_visibility="collapsed")

    # ---- header ----
    st.markdown("<h2 style='margin:0;text-align:center;'>SELF RELIEVING (DC001A)</h2>", unsafe_allow_html=True)
    st.markdown("<h4 style='margin:0;text-align:center;'>Values pulled from your latest <b>DC001</b> save</h4>", unsafe_allow_html=True)
    st.markdown("---")

    # ---- Wizard lock hydration (DON'T change layout) ----
    if is_locked():
        wb = get_base() or {}
        # Preload the same keys used elsewhere so the base is consistent across steps
        st.session_state["valve_nps"] = wb.get("nps_in", st.session_state.get("valve_nps"))
        st.session_state["valve_asme_class"] = wb.get("asme_class", st.session_state.get("valve_asme_class"))
        st.session_state["nps_in"] = wb.get("nps_in", st.session_state.get("nps_in"))
        st.session_state["asme_class"] = wb.get("asme_class", st.session_state.get("asme_class"))
        if wb.get("design_id"):
            st.session_state["active_design_id"] = wb.get("design_id")
        if wb.get("name"):
            st.session_state["active_design_name"] = wb.get("name")

    # ---- resolve base from Valve ----
    def resolve_valve_base():
        nps  = st.session_state.get("valve_nps", st.session_state.get("nps_in"))
        cls  = st.session_state.get("valve_asme_class", st.session_state.get("asme_class"))
        bore = st.session_state.get("bore_diameter_mm")
        Po   = st.session_state.get("operating_pressure_mpa")
        active_id   = st.session_state.get("active_design_id")
        active_name = st.session_state.get("active_design_name")

        # If anything missing, fall back to the latest saved valve design (robust unpack)
        if (nps is None or cls is None or bore is None or Po is None or not active_id) and user_id:
            try:
                raw = list_valve_designs(user_id, limit=1)
                if raw:
                    rid, rname = None, "Untitled"
                    first = raw[0]
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
                        cls   = vdata.get("asme_class", cls)
                        bore  = vcalc.get("bore_diameter_mm", bore)
                        Po    = vcalc.get("operating_pressure_mpa") or vdata.get("calc_operating_pressure_mpa") or Po
                        active_id   = active_id or rid
                        active_name = active_name or rname
                        # prime session for downstream pages
                        st.session_state.setdefault("nps_in", nps)
                        st.session_state.setdefault("asme_class", cls)
                        st.session_state.setdefault("bore_diameter_mm", bore)
                        st.session_state.setdefault("operating_pressure_mpa", Po)
                        st.session_state.setdefault("active_design_id", active_id)
                        st.session_state.setdefault("active_design_name", active_name)
            except Exception:
                pass

        return {
            "valve_design_id":   active_id,
            "valve_design_name": active_name,
            "nps_in":            nps,
            "asme_class":        cls,
            "bore_diameter_mm":  float(bore) if bore is not None else 62.3,
            "operating_pressure_mpa": float(Po) if Po is not None else 10.21,
        }

    base = resolve_valve_base()
    if base["valve_design_id"]:
        st.success(
            f'Base design: {base["valve_design_name"]} • '
            f'NPS { _fmt(base["nps_in"]) } • ASME { _fmt(base["asme_class"]) } • '
            f'Bore { _fmt(base["bore_diameter_mm"]) } mm • Po { _fmt(base["operating_pressure_mpa"]) } MPa'
        )
    else:
        st.info("Using defaults because no active Valve design was found.")

    # ---- pull LATEST DC001 save to source values (robust list handling) ----
    def get_latest_dc001_values() -> Dict[str, Optional[float]]:
        ss = st.session_state.get("dc001") or {}
        # Fallbacks if no saved DC001
        fallback_F   = (ss.get("F") or (ss.get("computed") or {}).get("F_N") or ss.get("Pr"))
        fallback_Dm  = ss.get("Dm")
        fallback_Dc  = ss.get("Dc")
        fallback_Pr  = (ss.get("Pr") or (ss.get("computed") or {}).get("Pr_N"))

        if not user_id:
            return {"source_id": None, "source_name": None,
                    "F_N": fallback_F, "Dm_mm": fallback_Dm, "Dc_mm": fallback_Dc, "Pr_N": fallback_Pr}

        try:
            raw = list_dc001_calcs(user_id, limit=1)  # could be 2- or 3-tuples, dicts, or strings
            if not raw:
                return {"source_id": None, "source_name": None,
                        "F_N": fallback_F, "Dm_mm": fallback_Dm, "Dc_mm": fallback_Dc, "Pr_N": fallback_Pr}

            dc_id, dc_name = None, "Untitled"
            first = raw[0]
            if isinstance(first, (list, tuple)):
                if len(first) >= 1: dc_id = first[0]
                if len(first) >= 2 and first[1] not in (None, ""): dc_name = first[1]
            elif isinstance(first, dict):
                dc_id = first.get("id") or first.get("calc_id") or first.get("id_")
                dc_name = first.get("name") or first.get("title") or dc_name
            elif isinstance(first, str):
                dc_id = first

            if not dc_id:
                return {"source_id": None, "source_name": None,
                        "F_N": fallback_F, "Dm_mm": fallback_Dm, "Dc_mm": fallback_Dc, "Pr_N": fallback_Pr}

            data = get_dc001_calc(dc_id, user_id) or {}
            ins  = (data.get("inputs") or {})
            comp = (data.get("computed") or {})

            F_N = comp.get("F_N", fallback_F)       # Linear Load (SR source)
            Dm  = ins.get("Dm_mm", fallback_Dm)     # seat insert medium dia  -> Dc here
            Dc  = ins.get("Dc_mm", fallback_Dc)     # seat/closure seal dia   -> Dts here
            Pr  = comp.get("Pr_N", fallback_Pr)     # spring force F_molle

            return {"source_id": str(dc_id), "source_name": str(dc_name),
                    "F_N": F_N, "Dm_mm": Dm, "Dc_mm": Dc, "Pr_N": Pr}
        except Exception:
            return {"source_id": None, "source_name": None,
                    "F_N": fallback_F, "Dm_mm": fallback_Dm, "Dc_mm": fallback_Dc, "Pr_N": fallback_Pr}

    dc001_src = get_latest_dc001_values()
    if dc001_src["source_id"]:
        st.info(f'Using latest DC001: **{dc001_src["source_name"]}** (ID {dc001_src["source_id"][:8]}…)')

    # Map as requested:
    SR_from_dc001   = dc001_src.get("F_N")    # SR := F (Linear Load)
    Dc_from_dc001   = dc001_src.get("Dm_mm")  # Dc := Dm (seat insert medium dia)
    Dts_from_dc001  = dc001_src.get("Dc_mm")  # Dts := Dc (seat/closure seal dia)
    Fmolle_from_dc1 = dc001_src.get("Pr_N")   # F_molle := Pr

    # ---- header info (DN / Class / Tag / Rev) ----
    i = row("Valve DN");   dn_display = f'{base["nps_in"]}"' if base["nps_in"] else ""
    with i: st.text_input("", value=dn_display, key="dc001a_dn", label_visibility="collapsed")

    i = row("Class")
    with i: st.text_input("", value=str(base["asme_class"]), key="dc001a_class", disabled=True, label_visibility="collapsed")

    i = row("Tag no")
    with i:
        tag_no = st.text_input("", value=st.session_state.get("tag_no", ""), key="dc001a_tag", label_visibility="collapsed")
        st.session_state["tag_no"] = tag_no

    i = row("Rev.")
    with i:
        rev = st.number_input("", value=int(st.session_state.get("rev_no", 0)), step=1, key="dc001a_rev", label_visibility="collapsed")
        st.session_state["rev_no"] = rev

    st.markdown("---")

    # ---- Inputs shown (locked) from DC001 ----
    _try_show_diagram(size_px=300)

    i = row("ØDc (seat/closure diameter)  [mm]  ← from DC001: Dm")
    with i: out_box("dc001a_Dc_locked", Dc_from_dc001, "{:.3f}", disabled=True)

    i = row("ØDts (relieving seat diameter)  [mm]  ← from DC001: Dc")
    with i: out_box("dc001a_Dts_locked", Dts_from_dc001, "{:.3f}", disabled=True)

    i = row("SR  [N]  ← from DC001: Linear Load F [N]")
    with i: out_box("dc001a_SR_locked", SR_from_dc001, "{:.2f}", disabled=True)

    # ---- Equation strip SR >= F_molle ----
    verdict_ok = (SR_from_dc001 or 0) >= (Fmolle_from_dc1 or 0)
    badge_txt  = "VERIFICATO" if verdict_ok else "NON VERIFICATO"
    badge_cls  = "ok" if verdict_ok else "bad"

    st.markdown(
        f"""
        <div class="eqbar" style="margin-top:.35rem;">
          <span class="lbl">SR =</span>
          <span class="cell">{_fmt(SR_from_dc001, 2)}</span>
          <span class="op">≥</span>
          <span class="lbl">F<sub>Molle</sub> =</span>
          <span class="cell">{_fmt(Fmolle_from_dc1, 1)}</span>
          <span class="badge {badge_cls}">{badge_txt}</span>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.caption("Values above are pulled from your latest saved DC001 and are read-only here.")

    # Save a compact state for downstream pages (if needed)
    st.session_state["dc001a"] = {
        "DN": dn_display, "class": base["asme_class"], "tag_no": tag_no, "rev": rev,
        "Dc_mm": Dc_from_dc001, "Dts_mm": Dts_from_dc001,
        "SR_N": SR_from_dc001, "F_molle_N": Fmolle_from_dc1,
        "source_dc001_id": dc001_src.get("source_id"), "source_dc001_name": dc001_src.get("source_name")
    }

    st.markdown("---")
    st.markdown("### Save / Load (DC001A)")

    # Build payload to persist (base + inputs + computed), including source DC001
    payload: Dict[str, Any] = {
        "base": {
            "valve_design_id":   base["valve_design_id"],
            "valve_design_name": base["valve_design_name"],
            "nps_in":            base["nps_in"],
            "asme_class":        base["asme_class"],
            "bore_diameter_mm":  base["bore_diameter_mm"],
            "operating_pressure_mpa": base["operating_pressure_mpa"],
            "source_dc001_id":   dc001_src.get("source_id"),
            "source_dc001_name": dc001_src.get("source_name"),
        },
        "inputs": {
            "Dc_mm_from_dc001_Dm":  Dc_from_dc001,
            "Dts_mm_from_dc001_Dc": Dts_from_dc001,
        },
        "computed": {
            "SR_N":       SR_from_dc001,    # from DC001.F
            "F_molle_N":  Fmolle_from_dc1,  # from DC001.Pr
            "verdict":    "VERIFICATO" if verdict_ok else "NON VERIFICATO",
        }
    }

    # Save / list / open / rename / delete
    default_name = f"DC001A_from_DC001_{(dc001_src.get('source_id') or '')[:8]}".rstrip("_")
    cL, cR = st.columns([1.2, 1.8], gap="large")

    with cL:
        save_name = st.text_input("Save as name", value=default_name or "DC001A", key="dc001a_save_name")
        if st.button("💾 Save DC001A", type="primary", use_container_width=True, key="btn_dc001a_save"):
            if not user_id:
                st.error("You must be logged in.")
            else:
                try:
                    new_id = create_dc001a_calc(user_id, save_name, payload)
                    st.success(f"Saved ✔ (ID: {new_id[:8]}…)")
                except Exception as e:
                    st.error(f"Save failed: {e}")

    with cR:
        raw_items = list_dc001a_calcs(user_id) if user_id else []
        # Normalize to (id, name) pairs regardless of shape (2/3-tuple, dict, str)
        items: List[tuple[str, str]] = []
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
            st.info("No DC001A saves yet.")
        else:
            label_to_id = {f"{nm} ({_id[:8]}…)" : _id for (_id, nm) in items}
            pick = st.selectbox("My DC001A saves", ["-- none --", *label_to_id.keys()], key="dc001a_pick")
            if pick != "-- none --":
                sel_id = label_to_id[pick]
                data = get_dc001a_calc(sel_id, user_id) or {}

                base_s  = (data.get("base") or {})
                ins_s   = (data.get("inputs") or {})
                comp_s  = (data.get("computed") or {})

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

                st.markdown("**Sourced from DC001**")
                _kv_table([
                    ("Source DC001 name", base_s.get("source_dc001_name")),
                    ("Source DC001 ID",   base_s.get("source_dc001_id")),
                    ("Dc [mm]  (Dm from DC001)",  ins_s.get("Dc_mm_from_dc001_Dm")),
                    ("Dts [mm] (Dc from DC001)",  ins_s.get("Dts_mm_from_dc001_Dc")),
                ])

                st.markdown("**Result**")
                _kv_table([
                    ("SR [N] (F from DC001)", comp_s.get("SR_N")),
                    ("F_molle [N] (Pr from DC001)", comp_s.get("F_molle_N")),
                    ("Verdict", comp_s.get("verdict")),
                ])

                # show equation strip again for clarity
                verdict_ok_saved = (comp_s.get("SR_N") or 0) >= (comp_s.get("F_molle_N") or 0)
                badge_txt_saved  = "VERIFICATO" if verdict_ok_saved else "NON VERIFICATO"
                badge_cls_saved  = "ok" if verdict_ok_saved else "bad"
                st.markdown(
                    f"""
                    <div class="eqbar" style="margin-top:.35rem;">
                      <span class="lbl">SR =</span>
                      <span class="cell">{_fmt(comp_s.get("SR_N"), 2)}</span>
                      <span class="op">≥</span>
                      <span class="lbl">F<sub>Molle</sub> =</span>
                      <span class="cell">{_fmt(comp_s.get("F_molle_N"), 1)}</span>
                      <span class="badge {badge_cls_saved}">{badge_txt_saved}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                d1, d2, d3 = st.columns(3)
                with d1:
                    if st.button("⬅ Load into form", key=f"dc001a_load_{sel_id}", use_container_width=True):
                        st.success("Loaded.")
                        st.rerun()
                with d2:
                    newname = st.text_input("Rename", value=pick.split(" (")[0], key=f"dc001a_rename_{sel_id}")
                    if st.button("💾 Save name", key=f"dc001a_btn_rename_{sel_id}", use_container_width=True):
                        if update_dc001a_calc(sel_id, user_id, name=newname):
                            st.success("Renamed.")
                            st.rerun()
                        else:
                            st.error("Rename failed.")
                with d3:
                    if st.button("🗑️ Delete", key=f"dc001a_btn_delete_{sel_id}", use_container_width=True):
                        if delete_dc001a_calc(sel_id, user_id):
                            st.success("Deleted.")
                            st.rerun()
                        else:
                            st.error("Delete failed.")
