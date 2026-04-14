# src/nicegui_state.py
"""
Lightweight per-user state for the NiceGUI entry point.

Stored in ``app.storage.user`` so it survives page refreshes.

Usage:
    from src.nicegui_state import ensure_state
    state = ensure_state()       # inside a @ui.page handler
"""
from __future__ import annotations

from typing import Any, Dict

from nicegui import app


# ---------------------------------------------------------------------------
# Default state template
# ---------------------------------------------------------------------------

_DEFAULTS: Dict[str, Any] = {
    # ── Form values ──────────────────────────────────────────────────
    "name": "",
    "year": 2000,
    "month_name": "January",
    "day": 1,
    "hour_12": "12",
    "minute_str": "00",
    "ampm": "AM",
    "city": "",
    "unknown_time": False,
    "gender": None,
    "is_my_chart": False,

    # ── Geocoded location (filled after Calculate) ───────────────────
    "current_lat": None,
    "current_lon": None,
    "current_tz_name": None,
    "last_location": "",
    "last_timezone": None,

    # ── Chart results ────────────────────────────────────────────────
    # NOTE: NiceGUI user storage is JSON-backed, so we store the chart
    # as its serializable dict (via AstrologicalChart.to_json()).
    # Use get_chart_object() in app.py to reconstruct the Python object.
    "last_chart_json": None,       # AstrologicalChart.to_json() dict
    "last_chart_2_json": None,     # outer chart (synastry / transit)
    "last_chart_2": None,          # second chart (synastry / transit)
    "chart_2_source": None,        # "profile" | "transit" | None
    "chart_ready": False,

    # ── Active tab ─────────────────────────────────────────────────
    "active_tab": "Circuits",      # persisted across page refreshes

    # ── Toggle values ────────────────────────────────────────────────
    "compass": True,
    "chart_mode": "Circuits",      # "Standard Chart" | "Circuits"
    "circuit_submode": "Combined",
    "pattern_toggles": {},         # {int: bool}
    "shape_toggles": {},           # {str: bool}
    "singleton_toggles": {},       # {str: bool}
    "aspect_toggles": {},          # {str: bool}
    "label_style": "glyph",       # "glyph" | "text"
    "dark_mode": False,
    "interactive_chart": False,
    "house_system": "placidus",

    # ── Synastry / transit ──────────────────────────────────────────
    "synastry_mode": False,
    "transit_mode": False,
    "synastry_inter": True,
    "synastry_chart1": False,
    "synastry_chart2": False,
    "chart_2_profile_name": None,      # name of loaded outer-chart profile
    "transit_dt_iso": None,            # ISO-8601 string of current transit UTC
    "transit_nav_interval": "1 day",   # step size for ◀/▶ buttons

    # ── Chat ─────────────────────────────────────────────────────────
    "mcp_chat_history": [],            # [{role, content, caption}]
    "mcp_model": "google/gemini-2.0-flash-001",
    "mcp_chat_mode": "Query",          # "Query" | "Map" | "Execute"
    "mcp_voice_mode": "Plain",         # "Plain" | "Circuit"
    "mcp_eq_bass": 0.0,
    "mcp_eq_mids": 0.0,
    "mcp_eq_treble": 0.0,
    "mcp_agent_notes": "",
    "mcp_pending_question": "",

    # ── Startup behaviour ────────────────────────────────────────────
    "auto_load_on_startup": True,    # load self chart automatically on sign-in

    # ── Profile management ───────────────────────────────────────────
    "current_profile": None,
    "profile_loaded": False,
    "saved_circuit_names": {},
    "birth_form_open": True,
    "editing_profile_name": None,
    "birth_form_mode": "new",      # "new" | "edit"
}


def ensure_state() -> Dict[str, Any]:
    """Return (and lazily initialise) the per-user NiceGUI state dict.

    Merges any missing keys from ``_DEFAULTS`` so the state schema can
    evolve without breaking existing sessions.
    """
    state = app.storage.user.setdefault("rosetta_state", {})
    for key, default in _DEFAULTS.items():
        state.setdefault(key, default)
    return state


def get_chart_object(state: Dict[str, Any]):
    """Reconstruct an AstrologicalChart from the stored JSON dict, or None.

    The chart is stored as ``state["last_chart_json"]`` (a plain dict from
    ``AstrologicalChart.to_json()``).  This helper deserialises it back into
    a live Python object on demand.
    """
    raw = state.get("last_chart_json")
    if raw is None or not isinstance(raw, dict):
        return None
    from src.core.models_v2 import AstrologicalChart
    return AstrologicalChart.from_json(raw)


def get_chart_2_object(state: Dict[str, Any]):
    """Reconstruct the second (outer / transit) AstrologicalChart, or None."""
    raw = state.get("last_chart_2_json")
    if raw is None or not isinstance(raw, dict):
        return None
    from src.core.models_v2 import AstrologicalChart
    return AstrologicalChart.from_json(raw)


def get_profile_lat_lon(state: Dict[str, Any]) -> tuple[float | None, float | None]:
    """Return (lat, lon) from the NiceGUI state dict, or (None, None) if absent.

    Reads ``state["current_lat"]`` / ``state["current_lon"]`` which are
    populated by the geocoder after the user clicks Calculate.
    """
    def _f(x: Any) -> float | None:
        """Try to convert *x* to float, returning None on failure."""
        try:
            return float(x)
        except Exception:
            return None

    lat = _f(state.get("current_lat"))
    lon = _f(state.get("current_lon"))
    if lat is None or lon is None:
        return None, None
    return lat, lon


def reset_chart_toggles(state: Dict[str, Any]) -> None:
    """Clear transient toggle state so each new chart loads cleanly.

    NiceGUI stores toggles as structured dicts rather than the flat
    ``toggle_pattern_*`` / ``shape_*`` keys used by the old Streamlit UI.
    """
    state["pattern_toggles"] = {}
    state["shape_toggles"] = {}
    state["singleton_toggles"] = {}
    state.pop("shape_toggles_by_parent", None)
