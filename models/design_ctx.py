# models/design_ctx.py
from __future__ import annotations
from typing import Optional, Dict, Any
import streamlit as st

BASE_KEY = "active_design_base"     # nps_in, asme_class, name, design_id
BADGE_KEY = "active_design_badge"   # internal flag

def set_base(*, nps_in: float, asme_class: int, name: str = "", design_id: Optional[str] = None):
    st.session_state[BASE_KEY] = {
        "nps_in": float(nps_in),
        "asme_class": int(asme_class),
        "name": name or f"NPS{nps_in}_CL{asme_class}",
        "design_id": design_id,     # may be None until first save
    }

def get_base() -> Optional[Dict[str, Any]]:
    return st.session_state.get(BASE_KEY)

def set_design_id(design_id: str):
    b = get_base() or {}
    b["design_id"] = design_id
    st.session_state[BASE_KEY] = b

def require_base():
    """Stop rendering page if there is no active base."""
    b = get_base()
    if not b:
        import streamlit as st
        st.error("No active design. Please set NPS and ASME Class on **Valve Data** first.")
        st.stop()
    return b

def render_badge():
    """Draw a small sticky badge with current design context (safe to call every page)."""
    b = get_base()
    if not b:
        return
    name = b.get("name") or ""
    nps = b.get("nps_in")
    cls = b.get("asme_class")
    did = b.get("design_id")
    did_short = f"{did[:8]}…" if did else "unsaved"

    st.markdown(
        f"""
        <div style="
            position: sticky; top: 0; z-index: 5; 
            padding:.5rem .75rem; margin-bottom:.5rem; 
            border:1px solid #e5e7eb; background:rgba(255,255,255,.6);
            backdrop-filter: blur(6px); border-radius:.6rem; font-size:.9rem;">
            <b>Design:</b> {name} &nbsp; • &nbsp;
            <b>NPS:</b> {nps} &nbsp; • &nbsp; <b>ASME:</b> {cls} &nbsp; • &nbsp;
            <b>ID:</b> {did_short}
        </div>
        """,
        unsafe_allow_html=True,
    )
