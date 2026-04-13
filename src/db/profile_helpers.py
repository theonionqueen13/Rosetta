# src/profile_helpers.py
"""
Framework-agnostic profile helpers.

Extracted from test_calc_v2.py so both Streamlit (via st.session_state) and
NiceGUI (via its own state dict) can load/apply profile data using the same
logic.

Usage:
    # Streamlit
    from src.profile_helpers import apply_profile, birth_data_from_chart
    apply_profile("Alice", prof_data, st.session_state)

    # NiceGUI
    apply_profile("Alice", prof_data, nicegui_state_dict)
"""
from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, Optional, Tuple

# Month names list (same as src/test_data.MONTH_NAMES)
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def birth_data_from_chart(chart) -> Tuple[
    Optional[int],   # year
    Optional[int],   # month
    Optional[int],   # day
    Optional[int],   # hour_24
    Optional[int],   # minute
    str,             # city
]:
    """Parse local-time birth data from a chart's display_datetime / fields.

    Returns (year, month, day, hour_24, minute, city).
    Any field may be None if the chart has no datetime.
    """
    dt = getattr(chart, "display_datetime", None)
    if dt is None:
        raw = getattr(chart, "chart_datetime", None)
        if raw:
            try:
                dt = _dt.datetime.fromisoformat(raw)
            except (ValueError, TypeError):
                dt = None
    if dt:
        return dt.year, dt.month, dt.day, dt.hour, dt.minute, getattr(chart, "city", "") or ""
    return None, None, None, None, None, getattr(chart, "city", "") or ""


def apply_profile(
    prof_name: str,
    prof_data: Dict[str, Any],
    state: Dict[str, Any],
) -> bool:
    """Populate form/session keys in *state* from a profile dict.

    Works identically to the former ``_apply_profile_to_session`` in
    test_calc_v2.py but writes to the supplied *state* dict instead of
    ``st.session_state``.

    Returns ``True`` if the profile uses the new PersonProfile format,
    ``False`` for old-format dicts.
    """
    from src.mcp.comprehension_models import PersonProfile as _PP

    _pp = _PP.from_dict(prof_data)
    _loaded_chart = _pp.astro_chart

    if _loaded_chart is not None:
        # ── New PersonProfile format ──────────────────────────────────
        _loaded_chart.display_name = prof_name
        _yr, _mo, _dy, _hr24, _mn, _ct = birth_data_from_chart(_loaded_chart)

        # Set profile-bound keys
        if _yr is not None:
            state["profile_year"] = _yr
            state["profile_month_name"] = MONTH_NAMES[_mo - 1]
            state["profile_day"] = _dy
            state["profile_hour"] = _hr24
            state["profile_minute"] = _mn
            state["profile_city"] = _ct

            # Set form-widget-bound keys
            state["year"] = _yr
            state["month_name"] = MONTH_NAMES[_mo - 1]
            state["day"] = _dy
            state["city"] = _ct
            _load_h12 = _hr24 % 12 or 12
            _load_ampm = "AM" if _hr24 < 12 else "PM"
            state["hour_12"]    = f"{_load_h12:02d}"
            state["minute_str"] = f"{_mn:02d}"
            state["ampm"]       = _load_ampm

            state["hour_val"] = _hr24
            state["minute_val"] = _mn
            state["city_input"] = _ct

        # Restore unknown time flag + time slots
        _chart_unknown_time = bool(getattr(_loaded_chart, "unknown_time", False))
        state["profile_unknown_time"] = _chart_unknown_time
        if _chart_unknown_time:
            state["hour_12"]    = "--"
            state["minute_str"] = "--"
            state["ampm"]       = "--"

        # Geocode from chart
        state["current_lat"]     = _loaded_chart.latitude
        state["current_lon"]     = _loaded_chart.longitude
        state["current_tz_name"] = _loaded_chart.timezone

        state["last_location"] = _loaded_chart.city or ""
        state["last_timezone"] = _loaded_chart.timezone

        # Restore name, gender, and self-flag
        state["birth_name"]  = _pp.name or prof_name
        state["birth_gender"] = _pp.gender  # None if not stored
        state["is_my_chart"] = (_pp.relationship_to_querent == "self")

        # Restore circuit names from chart object
        _circuit_names = getattr(_loaded_chart, "circuit_names", None) or {}
        if _circuit_names:
            for key, val in _circuit_names.items():
                state[key] = val
            state["saved_circuit_names"] = _circuit_names.copy()
        else:
            state["saved_circuit_names"] = {}

        state["last_chart"] = _loaded_chart
        state["chart_ready"] = True
        return True  # new-format success
    else:
        # ── Old-format fallback ───────────────────────────────────────
        # Set profile-bound keys (not widget-bound)
        state["profile_year"] = prof_data["year"]
        state["profile_month_name"] = MONTH_NAMES[prof_data["month"] - 1]
        state["profile_day"] = prof_data["day"]
        state["profile_hour"] = prof_data["hour"]
        state["profile_minute"] = prof_data["minute"]
        state["profile_city"] = prof_data["city"]

        # Set form-widget-bound keys
        state["year"] = prof_data["year"]
        state["month_name"] = MONTH_NAMES[prof_data["month"] - 1]
        state["day"] = prof_data["day"]
        state["city"] = prof_data["city"]
        _load_h24 = prof_data["hour"]
        _load_h12 = _load_h24 % 12 or 12
        _load_ampm = "AM" if _load_h24 < 12 else "PM"
        state["hour_12"]    = f"{_load_h12:02d}"
        state["minute_str"] = f"{prof_data['minute']:02d}"
        state["ampm"]       = _load_ampm

        state["current_lat"]     = prof_data.get("lat")
        state["current_lon"]     = prof_data.get("lon")
        state["current_tz_name"] = prof_data.get("tz_name")

        state["hour_val"] = prof_data["hour"]
        state["minute_val"] = prof_data["minute"]
        state["city_input"] = prof_data["city"]

        state["last_location"] = prof_data["city"]
        state["last_timezone"] = prof_data.get("tz_name")

        # Restore name, gender, unknown-time, and self-flag (old format)
        state["birth_name"] = prof_data.get("name") or prof_name
        state["birth_gender"] = prof_data.get("gender")  # None if not stored
        _unk = bool(prof_data.get("unknown_time", False))
        state["profile_unknown_time"] = _unk
        if _unk:
            state["hour_12"]    = "--"
            state["minute_str"] = "--"
            state["ampm"]       = "--"
        state["is_my_chart"] = (prof_data.get("relationship_to_querent") == "self")

        # Restore circuit names (old format: top-level key)
        if "circuit_names" in prof_data:
            for key, val in prof_data["circuit_names"].items():
                state[key] = val
            state["saved_circuit_names"] = prof_data["circuit_names"].copy()
        else:
            state["saved_circuit_names"] = {}

        # Try loading chart from old-format raw dict
        _stored_chart_raw = prof_data.get("chart")
        if isinstance(_stored_chart_raw, dict):
            from src.core.models_v2 import AstrologicalChart
            _stored_chart = AstrologicalChart.from_json(_stored_chart_raw)
            _stored_chart.display_name = prof_name
            state["last_chart"] = _stored_chart
            state["chart_ready"] = True
        elif any(v is None for v in (prof_data.get("lat"), prof_data.get("lon"), prof_data.get("tz_name"))):
            state["__profile_load_error__"] = (
                f"Profile '{prof_name}' is missing location/timezone info. "
                f"Re-save it after a successful city lookup."
            )
        # else: will recalculate when run_chart() is called
        return False  # old-format path
