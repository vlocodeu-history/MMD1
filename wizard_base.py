# wizard_base.py
from __future__ import annotations
from typing import Optional, Dict, Any
import streamlit as st

# Internal session keys
_WIZ_BASE_KEY = "wizard_base"
_WIZ_LOCK_KEY = "wizard_lock"
_WIZ_STEP_KEY = "wizard_step"
_WIZ_TOTAL_STEPS_KEY = "wizard_total_steps"

# Common cross-page session keys used throughout the app
_SESSION_MIRROR_KEYS = {
    "design_id": "active_design_id",
    "name": "active_design_name",
    "nps_in": "nps_in",
    "asme_class": "asme_class",
    # Optional but very handy to mirror when available:
    "bore_diameter_mm": "bore_diameter_mm",
    "operating_pressure_mpa": "operating_pressure_mpa",
}

def _normalize_base(base: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a sanitized wizard base with consistent keys."""
    base = dict(base or {})
    # Accept some common aliases just in case
    if "id" in base and "design_id" not in base:
        base["design_id"] = base.get("id")
    if "title" in base and "name" not in base:
        base["name"] = base.get("title")
    # Only keep known keys + pass through any extras (non-destructive)
    normalized = {
        "design_id": base.get("design_id"),
        "name": base.get("name"),
        "nps_in": base.get("nps_in"),
        "asme_class": base.get("asme_class"),
        # Optional helpful context
        "bore_diameter_mm": base.get("bore_diameter_mm"),
        "operating_pressure_mpa": base.get("operating_pressure_mpa"),
    }
    # Attach any extra keys without clobbering normalized ones
    for k, v in base.items():
        if k not in normalized:
            normalized[k] = v
    return normalized

def _mirror_to_session(base: Dict[str, Any]) -> None:
    """Mirror selected base fields to the commonly used session keys."""
    for src, dst in _SESSION_MIRROR_KEYS.items():
        val = base.get(src)
        if val is not None:
            st.session_state[dst] = val

# ───────────────────────── Public (backward-compatible) API ─────────────────────────

def start_wizard(base: Dict[str, Any], *, total_steps: int = 17, force_reset_step: bool = True) -> None:
    """
    Lock base (NPS/Class/name/id) as the shared default across all steps.
    Also mirrors common fields into session for convenience.
    """
    norm = _normalize_base(base)
    st.session_state[_WIZ_BASE_KEY] = norm
    st.session_state[_WIZ_LOCK_KEY] = True
    _mirror_to_session(norm)

    # Initialize step counter if desired
    if force_reset_step or _WIZ_STEP_KEY not in st.session_state:
        st.session_state[_WIZ_STEP_KEY] = 1
    st.session_state[_WIZ_TOTAL_STEPS_KEY] = int(total_steps)

def get_base() -> Optional[Dict[str, Any]]:
    """Return the current locked base (normalized), if any."""
    base = st.session_state.get(_WIZ_BASE_KEY)
    return dict(base) if base else None

def is_locked() -> bool:
    """Whether the wizard base is locked."""
    return bool(st.session_state.get(_WIZ_LOCK_KEY, False))

def finish_wizard() -> None:
    """Call on the final step to clear the lock and step tracking."""
    st.session_state.pop(_WIZ_BASE_KEY, None)
    st.session_state.pop(_WIZ_LOCK_KEY, None)
    st.session_state.pop(_WIZ_STEP_KEY, None)
    st.session_state.pop(_WIZ_TOTAL_STEPS_KEY, None)

# ───────────────────────── Optional convenience utilities ─────────────────────────

def update_wizard_base(**fields: Any) -> None:
    """
    Safely update the locked base with new fields (e.g., when later pages
    learn bore/Po and want them persisted for subsequent steps).
    """
    if not is_locked():
        return
    base = get_base() or {}
    base.update(fields)
    base = _normalize_base(base)
    st.session_state[_WIZ_BASE_KEY] = base
    _mirror_to_session(base)

def hydrate_session_from_base() -> None:
    """
    If locked, mirror base into the standard session keys.
    Useful for pages that need to 'self-heal' session state on reruns.
    """
    if not is_locked():
        return
    base = get_base()
    if base:
        _mirror_to_session(base)

def ensure_base_fields(*required_keys: str) -> bool:
    """
    Quick check for required base keys; returns True if all exist and non-None.
    Example: ensure_base_fields("nps_in", "asme_class")
    """
    base = get_base() or {}
    for k in required_keys:
        if base.get(k) is None:
            return False
    return True

def get_step() -> int:
    """Return current wizard step (defaults to 1)."""
    return int(st.session_state.get(_WIZ_STEP_KEY, 1))

def get_total_steps() -> int:
    """Return total wizard steps (defaults to 17)."""
    return int(st.session_state.get(_WIZ_TOTAL_STEPS_KEY, 17))

def set_step(step: int) -> None:
    """Set current wizard step (clamped to [1, total_steps])."""
    total = get_total_steps()
    st.session_state[_WIZ_STEP_KEY] = max(1, min(int(step), total))

def advance_step(delta: int = 1) -> None:
    """Advance (or go back with negative delta) the wizard step."""
    set_step(get_step() + int(delta))
