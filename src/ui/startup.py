"""Startup logic — auto-load self chart or show empty-state messages."""
from __future__ import annotations

import logging
from typing import Callable

from nicegui import app, ui

from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)


def run_startup(
    state: dict,
    form: dict,
    *,
    std_chart_container,
    cir_chart_container,
    chat_no_chart_notice,
    save_name_input,
    is_my_chart_cb,
    build_circuit_toggles: Callable,
    display_chart_in: Callable,
    render_chart_png: Callable,
    render_rulers_graph: Callable,
    refresh_specs_tab: Callable,
    refresh_events: Callable,
    refresh_drawer: Callable,
    get_user_id: Callable,
) -> None:
    """Execute startup sequence: auto-load chart or show empty state.

    Parameters
    ----------
    state, form : dict
        Per-user app state and birth-form data.
    std_chart_container, cir_chart_container : ui.column
        Chart render containers for Standard and Circuits tabs.
    chat_no_chart_notice : ui element
        Notice shown in Chat tab when no chart is loaded.
    save_name_input : ui.input
        Profile-name input (pre-filled when profile loads).
    is_my_chart_cb : ui.checkbox
        "My chart" checkbox (checked when self-profile loads).
    build_circuit_toggles : callable
        Rebuilds circuit toggle UI.
    display_chart_in : callable(container, png_bytes)
        Renders chart PNG into a container.
    render_chart_png : callable(mode) -> bytes
        Generates chart PNG for a given mode.
    render_rulers_graph : callable
        Renders the rulers/dispositor graph.
    refresh_specs_tab : callable
        Refreshes the specs tab tables.
    refresh_events : callable
        Refreshes the events sidebar.
    refresh_drawer : callable
        Refreshes the drawer content.
    get_user_id : callable
        Returns the current user's ID string.
    """

    def _render_with_chart():
        """Populate every tab's chart area from whatever is currently in state."""
        build_circuit_toggles()
        display_chart_in(std_chart_container, render_chart_png("Standard Chart"))
        display_chart_in(cir_chart_container, render_chart_png("Circuits"))
        render_rulers_graph()
        refresh_specs_tab()
        refresh_events()
        refresh_drawer()
        try:
            chat_no_chart_notice.set_visibility(False)
        except Exception:
            pass

    def _show_empty():
        """Put empty-state messages in every tab's chart area."""
        _NO_CHART_MSG = "Calculate or load a chart to view it here."
        build_circuit_toggles()
        std_chart_container.clear()
        with std_chart_container:
            ui.label(_NO_CHART_MSG).classes("text-body2 text-grey q-pa-md")
        cir_chart_container.clear()
        with cir_chart_container:
            ui.label(_NO_CHART_MSG).classes("text-body2 text-grey q-pa-md")
        render_rulers_graph()
        refresh_specs_tab()
        try:
            chat_no_chart_notice.set_visibility(True)
        except Exception:
            pass

    def _clear_chart_state():
        """Wipe all cached chart data from persistent state."""
        state["last_chart_json"] = None
        state["last_chart_2_json"] = None
        state["chart_ready"] = False
        state["pattern_toggles"] = {}
        state["shape_toggles"] = {}
        state["singleton_toggles"] = {}

    _auto_load = state.get("auto_load_on_startup", True)
    _cached_chart = get_chart_object(state)
    _cached_is_self = state.get("is_my_chart", False)

    # Always clear a non-self chart — we never silently carry over another
    # person's chart to the next session.
    if _cached_chart is not None and not _cached_is_self:
        _clear_chart_state()
        _cached_chart = None

    if not _auto_load:
        _clear_chart_state()
        _show_empty()
    elif _cached_chart is not None:
        # Self chart already in cache — render it, preserving all data.
        # Fix any legacy __-prefixed display_name from older sessions.
        _cached_display = getattr(_cached_chart, "display_name", "") or ""
        if _cached_display.startswith("__"):
            _fixed_name = (
                state.get("birth_name") or state.get("name")
                or app.storage.user.get("birth_form", {}).get("name")
                or ""
            )
            if _fixed_name:
                _cached_chart.display_name = _fixed_name
                state["last_chart_json"] = _cached_chart.to_json()
        _render_with_chart()
    else:
        # Auto-load is on but nothing cached — try loading self profile.
        _uid = get_user_id()
        _self_loaded = False
        if _uid:
            try:
                from src.db.supabase_profiles import load_user_profiles_db
                _profiles = load_user_profiles_db(_uid)
                for _pname, _pdata in (_profiles or {}).items():
                    if _pname.startswith("__"):
                        continue
                    if (_pdata or {}).get("relationship_to_querent") == "self":
                        from src.db.profile_helpers import apply_profile
                        apply_profile(_pname, _pdata, state)
                        _chart_tmp = state.pop("last_chart", None)
                        if _chart_tmp is not None and hasattr(_chart_tmp, "to_json"):
                            state["last_chart_json"] = _chart_tmp.to_json()
                        state["is_my_chart"] = True

                        _real_name = (
                            state.get("birth_name") or state.get("name") or _pname
                        )
                        _chart_fix = get_chart_object(state)
                        if _chart_fix is not None:
                            _chart_fix.display_name = _real_name
                            state["last_chart_json"] = _chart_fix.to_json()

                        form["name"] = _real_name
                        form["city"] = state.get("city", "")
                        form["year"] = state.get("year", 2000)
                        form["month_name"] = state.get("month_name", "January")
                        form["day"] = state.get("day", 1)
                        form["hour_12"] = state.get("hour_12", "12")
                        form["minute_str"] = state.get("minute_str", "00")
                        form["ampm"] = state.get("ampm", "AM")
                        save_name_input.value = _pname
                        is_my_chart_cb.value = True
                        if get_chart_object(state) is not None:
                            _render_with_chart()
                            _self_loaded = True
                        break
            except Exception as _exc:
                _log.warning("Startup auto-load of self chart failed: %s", _exc)
        if not _self_loaded:
            _show_empty()
