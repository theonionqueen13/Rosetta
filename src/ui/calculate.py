"""Calculate handler — validates form, geocodes, computes chart, renders."""
from __future__ import annotations

import logging
from typing import Any, Callable

from nicegui import ui

from src.core.static_data import MONTH_NAMES

_log = logging.getLogger(__name__)


async def on_calculate(
    state: dict,
    form: dict,
    *,
    status_label,
    calc_btn,
    birth_exp,
    save_name_input,
    build_circuit_toggles: Callable,
    rerender_active_tab: Callable,
) -> None:
    """Run chart calculation: validate → geocode → compute → render.

    Parameters
    ----------
    state, form : dict
        Per-user app state and birth-form data.
    status_label : ui.label
        Status feedback label in the chart manager tab.
    calc_btn : ui.button
        The calculate button (disabled during computation).
    birth_exp : ui.expansion
        Birth-form expansion (collapsed on success).
    save_name_input : ui.input
        Profile-name input (pre-filled on success).
    build_circuit_toggles : callable
        Rebuilds circuit toggle UI from current chart.
    rerender_active_tab : callable
        Re-renders whichever tab is visible.
    """
    status_label.set_visibility(False)

    # Validate required fields
    name = (form.get("name") or "").strip()
    city = (form.get("city") or "").strip()
    if not name:
        status_label.text = "Name is required."
        status_label.classes(replace="text-body2 text-negative")
        status_label.set_visibility(True)
        return
    if not city:
        status_label.text = "City of Birth is required."
        status_label.classes(replace="text-body2 text-negative")
        status_label.set_visibility(True)
        return

    # Parse time
    unknown_time = form.get("unknown_time", False)
    hour_12_val = form.get("hour_12", "--")
    minute_str_val = form.get("minute_str", "--")
    ampm_val = form.get("ampm", "--")

    if unknown_time or hour_12_val == "--" or minute_str_val == "--" or ampm_val == "--":
        birth_hour_24 = 12
        birth_minute = 0
        is_unknown = True
    else:
        h12 = int(hour_12_val)
        birth_minute = int(minute_str_val)
        birth_hour_24 = (0 if h12 == 12 else h12) if ampm_val == "AM" else (12 if h12 == 12 else h12 + 12)
        is_unknown = False

    month_idx = MONTH_NAMES.index(form.get("month_name", "January")) + 1
    year = int(form.get("year", 2000))
    day = int(form.get("day", 1))

    # Show progress
    status_label.text = "Geocoding city…"
    status_label.classes(replace="text-body2 text-grey-7")
    status_label.set_visibility(True)
    calc_btn.disable()

    try:
        # --- Geocode ---
        from src.core.geocoding import geocode_city_with_timezone
        lat, lon, tz_name, formatted = geocode_city_with_timezone(city)
        if lat is None or lon is None or tz_name is None:
            status_label.text = f"Could not geocode '{city}'. Please try a more specific city name."
            status_label.classes(replace="text-body2 text-negative")
            status_label.set_visibility(True)
            calc_btn.enable()
            return

        status_label.text = "Computing chart…"
        await ui.run_javascript("")  # flush UI update

        # --- Compute chart ---
        from src.chart_adapter import ChartInputs, compute_chart

        inputs = ChartInputs(
            name=name,
            year=year, month=month_idx, day=day,
            hour_24=birth_hour_24, minute=birth_minute,
            city=city,
            lat=lat, lon=lon, tz_name=tz_name,
            unknown_time=is_unknown,
            house_system=(state.get("house_system", "placidus") or "placidus").lower(),
            gender=form.get("gender"),
        )
        result = compute_chart(inputs)

        if result.error:
            status_label.text = f"Calculation error: {result.error}"
            status_label.classes(replace="text-body2 text-negative")
            status_label.set_visibility(True)
            calc_btn.enable()
            return

        status_label.text = "Rendering chart…"
        await ui.run_javascript("")  # flush UI update

        # --- Store result in per-user state ---
        state["last_chart_json"] = result.chart.to_json() if result.chart else None
        state["chart_ready"] = True
        state["name"] = name
        state["city"] = city
        state["year"] = year
        state["month_name"] = MONTH_NAMES[month_idx - 1]
        state["day"] = day
        state["current_lat"] = lat
        state["current_lon"] = lon
        state["current_tz_name"] = tz_name

        # Reset circuit toggles for the new chart
        state["pattern_toggles"] = {}
        state["shape_toggles"] = {}
        state["singleton_toggles"] = {}

        # Build circuit toggles UI
        build_circuit_toggles()

        # Render chart in the active tab
        rerender_active_tab()

        # Collapse form after successful chart
        birth_exp.close()
        status_label.set_visibility(False)
        # Pre-fill save name so user can quickly save
        save_name_input.value = name

    except Exception as exc:
        _log.exception("Chart calculation failed")
        status_label.text = f"Unexpected error: {exc}"
        status_label.classes(replace="text-body2 text-negative")
        status_label.set_visibility(True)
    finally:
        calc_btn.enable()
