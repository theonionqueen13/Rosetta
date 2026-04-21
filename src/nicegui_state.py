# src/nicegui_state.py
"""
Lightweight per-user state for the NiceGUI entry point.

Stored in ``app.storage.user`` so it survives page refreshes.

Usage:
    from src.nicegui_state import ensure_state
    state = ensure_state()       # inside a @ui.page handler
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from nicegui import app

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Canonical key names — import ``StateKeys`` wherever you reference state
# ---------------------------------------------------------------------------

class StateKeys:
    """Single source of truth for every key stored in per-user state.

    Use these constants instead of bare string literals so typos are
    caught at import time and renames only need to happen in one place.
    """

    # ── Form values ──────────────────────────────────────────────────
    NAME = "name"
    YEAR = "year"
    MONTH_NAME = "month_name"
    DAY = "day"
    HOUR_12 = "hour_12"
    MINUTE_STR = "minute_str"
    AMPM = "ampm"
    CITY = "city"
    UNKNOWN_TIME = "unknown_time"
    GENDER = "gender"
    IS_MY_CHART = "is_my_chart"

    # ── Geocoded location (filled after Calculate) ───────────────────
    CURRENT_LAT = "current_lat"
    CURRENT_LON = "current_lon"
    CURRENT_TZ_NAME = "current_tz_name"
    LAST_LOCATION = "last_location"
    LAST_TIMEZONE = "last_timezone"

    # ── Chart results ────────────────────────────────────────────────
    LAST_CHART_JSON = "last_chart_json"
    LAST_CHART_2_JSON = "last_chart_2_json"
    LAST_CHART_2 = "last_chart_2"
    CHART_2_SOURCE = "chart_2_source"
    CHART_READY = "chart_ready"

    # ── Active tab ───────────────────────────────────────────────────
    ACTIVE_TAB = "active_tab"

    # ── Toggle values ────────────────────────────────────────────────
    COMPASS = "compass"
    CHART_MODE = "chart_mode"
    CIRCUIT_SUBMODE = "circuit_submode"
    PATTERN_TOGGLES = "pattern_toggles"
    SHAPE_TOGGLES = "shape_toggles"
    SINGLETON_TOGGLES = "singleton_toggles"
    ASPECT_TOGGLES = "aspect_toggles"
    LABEL_STYLE = "label_style"
    DARK_MODE = "dark_mode"
    INTERACTIVE_CHART = "interactive_chart"
    HOUSE_SYSTEM = "house_system"

    # ── Synastry / transit ───────────────────────────────────────────
    SYNASTRY_MODE = "synastry_mode"
    TRANSIT_MODE = "transit_mode"
    SYNASTRY_INTER = "synastry_inter"
    SYNASTRY_CHART1 = "synastry_chart1"
    SYNASTRY_CHART2 = "synastry_chart2"
    CHART_2_PROFILE_NAME = "chart_2_profile_name"
    TRANSIT_DT_ISO = "transit_dt_iso"
    TRANSIT_NAV_INTERVAL = "transit_nav_interval"

    # ── Chat ─────────────────────────────────────────────────────────
    MCP_CHAT_HISTORY = "mcp_chat_history"
    MCP_MODEL = "mcp_model"
    MCP_CHAT_MODE = "mcp_chat_mode"
    MCP_VOICE_MODE = "mcp_voice_mode"
    MCP_EQ_BASS = "mcp_eq_bass"
    MCP_EQ_MIDS = "mcp_eq_mids"
    MCP_EQ_TREBLE = "mcp_eq_treble"
    MCP_AGENT_NOTES = "mcp_agent_notes"
    MCP_PENDING_QUESTION = "mcp_pending_question"

    # ── Startup behaviour ────────────────────────────────────────────
    AUTO_LOAD_ON_STARTUP = "auto_load_on_startup"

    # ── Profile management ───────────────────────────────────────────
    CURRENT_PROFILE = "current_profile"
    PROFILE_LOADED = "profile_loaded"
    SAVED_CIRCUIT_NAMES = "saved_circuit_names"
    BIRTH_FORM_OPEN = "birth_form_open"
    EDITING_PROFILE_NAME = "editing_profile_name"
    BIRTH_FORM_MODE = "birth_form_mode"

    # ── Selection / Focus tab ────────────────────────────────────────
    SELECTED_PLANETS = "selected_planets"
    FOCUS_PLANETS = "focus_planets"
    FOCUS_SHOW_PARENT_SHAPE = "focus_show_parent_shape"
    FOCUS_SHOW_FULL_CIRCUIT = "focus_show_full_circuit"
    FOCUS_SCAN_CONNECTIONS = "focus_scan_connections"


# ---------------------------------------------------------------------------
# Default state template  (uses StateKeys so names stay in sync)
# ---------------------------------------------------------------------------

_DEFAULTS: Dict[str, Any] = {
    # ── Form values ──────────────────────────────────────────────────
    StateKeys.NAME: "",
    StateKeys.YEAR: 2000,
    StateKeys.MONTH_NAME: "January",
    StateKeys.DAY: 1,
    StateKeys.HOUR_12: "12",
    StateKeys.MINUTE_STR: "00",
    StateKeys.AMPM: "AM",
    StateKeys.CITY: "",
    StateKeys.UNKNOWN_TIME: False,
    StateKeys.GENDER: None,
    StateKeys.IS_MY_CHART: False,

    # ── Geocoded location (filled after Calculate) ───────────────────
    StateKeys.CURRENT_LAT: None,
    StateKeys.CURRENT_LON: None,
    StateKeys.CURRENT_TZ_NAME: None,
    StateKeys.LAST_LOCATION: "",
    StateKeys.LAST_TIMEZONE: None,

    # ── Chart results ────────────────────────────────────────────────
    # NOTE: NiceGUI user storage is JSON-backed, so we store the chart
    # as its serializable dict (via AstrologicalChart.to_json()).
    # Use get_chart_object() in app.py to reconstruct the Python object.
    StateKeys.LAST_CHART_JSON: None,       # AstrologicalChart.to_json() dict
    StateKeys.LAST_CHART_2_JSON: None,     # outer chart (synastry / transit)
    StateKeys.LAST_CHART_2: None,          # second chart (synastry / transit)
    StateKeys.CHART_2_SOURCE: None,        # "profile" | "transit" | None
    StateKeys.CHART_READY: False,

    # ── Active tab ─────────────────────────────────────────────────
    StateKeys.ACTIVE_TAB: "Circuits",      # persisted across page refreshes

    # ── Toggle values ────────────────────────────────────────────────
    StateKeys.COMPASS: True,
    StateKeys.CHART_MODE: "Circuits",      # "Standard Chart" | "Circuits"
    StateKeys.CIRCUIT_SUBMODE: "Combined",
    StateKeys.PATTERN_TOGGLES: {},         # {int: bool}
    StateKeys.SHAPE_TOGGLES: {},           # {str: bool}
    StateKeys.SINGLETON_TOGGLES: {},       # {str: bool}
    StateKeys.ASPECT_TOGGLES: {},          # {str: bool}
    StateKeys.LABEL_STYLE: "glyph",       # "glyph" | "text"
    StateKeys.DARK_MODE: False,
    StateKeys.INTERACTIVE_CHART: False,
    StateKeys.HOUSE_SYSTEM: "placidus",

    # ── Synastry / transit ──────────────────────────────────────────
    StateKeys.SYNASTRY_MODE: False,
    StateKeys.TRANSIT_MODE: False,
    StateKeys.SYNASTRY_INTER: True,
    StateKeys.SYNASTRY_CHART1: False,
    StateKeys.SYNASTRY_CHART2: False,
    StateKeys.CHART_2_PROFILE_NAME: None,      # name of loaded outer-chart profile
    StateKeys.TRANSIT_DT_ISO: None,            # ISO-8601 string of current transit UTC
    StateKeys.TRANSIT_NAV_INTERVAL: "1 day",   # step size for ◀/▶ buttons

    # ── Chat ─────────────────────────────────────────────────────────
    StateKeys.MCP_CHAT_HISTORY: [],            # [{role, content, caption}]
    StateKeys.MCP_MODEL: "google/gemini-2.0-flash-001",
    StateKeys.MCP_CHAT_MODE: "Query",          # "Query" | "Map" | "Execute"
    StateKeys.MCP_VOICE_MODE: "Plain",         # "Plain" | "Circuit"
    StateKeys.MCP_EQ_BASS: 0.0,
    StateKeys.MCP_EQ_MIDS: 0.0,
    StateKeys.MCP_EQ_TREBLE: 0.0,
    StateKeys.MCP_AGENT_NOTES: "",
    StateKeys.MCP_PENDING_QUESTION: "",

    # ── Startup behaviour ────────────────────────────────────────────
    StateKeys.AUTO_LOAD_ON_STARTUP: True,    # load self chart automatically on sign-in

    # ── Profile management ───────────────────────────────────────────
    StateKeys.CURRENT_PROFILE: None,
    StateKeys.PROFILE_LOADED: False,
    StateKeys.SAVED_CIRCUIT_NAMES: {},
    StateKeys.BIRTH_FORM_OPEN: True,
    StateKeys.EDITING_PROFILE_NAME: None,
    StateKeys.BIRTH_FORM_MODE: "new",      # "new" | "edit"

    # ── Selection / Focus tab ────────────────────────────────────────
    # selected_planets: shared rendering list; highlighted with lime-green circles.
    StateKeys.SELECTED_PLANETS: [],        # list[str] — planet names currently highlighted
    # focus_planets: the Focus tab's dropdown state (max 3).
    StateKeys.FOCUS_PLANETS: [],           # list[str] — planets chosen in Focus tab
    StateKeys.FOCUS_SHOW_PARENT_SHAPE: False,   # future toggle stub
    StateKeys.FOCUS_SHOW_FULL_CIRCUIT: False,   # future toggle stub
    StateKeys.FOCUS_SCAN_CONNECTIONS: False,    # future toggle stub
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
        except (ValueError, TypeError) as exc:
            _log.warning("Could not convert %r to float: %s", x, exc)
            return None

    lat = _f(state.get("current_lat"))
    lon = _f(state.get("current_lon"))
    if lat is None or lon is None:
        return None, None
    return lat, lon


def get_house_system(state: Dict[str, Any]) -> str:
    """Return the active house system as a normalised lowercase string.

    Centralises the ``(state.get("house_system", "placidus") or "placidus").lower()``
    pattern that was previously repeated across ~10 UI modules.
    """
    return (state.get(StateKeys.HOUSE_SYSTEM, "placidus") or "placidus").lower()


def reset_chart_toggles(state: Dict[str, Any]) -> None:
    """Clear transient toggle state so each new chart loads cleanly.

    NiceGUI stores toggles as structured dicts rather than the flat
    ``toggle_pattern_*`` / ``shape_*`` keys used by the old Streamlit UI.
    """
    state["pattern_toggles"] = {}
    state["shape_toggles"] = {}
    state["singleton_toggles"] = {}
    state.pop("shape_toggles_by_parent", None)
