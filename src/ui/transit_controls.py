"""Transit / synastry controls — date nav, chart-2 loading, swap, synastry toggle."""
from __future__ import annotations

import datetime as _dt
import logging
from typing import Any, Callable, Optional

import pytz
from dateutil.relativedelta import relativedelta
from nicegui import ui

from src.core.static_data import MONTH_NAMES
from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)


def build(
    state: dict,
    form: dict,
    *,
    rerender_active_tab: Callable,
    build_circuit_toggles: Callable,
    refresh_drawer: Callable,
    get_user_id: Callable,
) -> dict[str, Any]:
    """Build synastry toggle, shared controls row, and transit date-nav.

    Parameters
    ----------
    rerender_active_tab, build_circuit_toggles, refresh_drawer
        Forward-reference wrappers (closures resolved at call time).
    get_user_id
        Returns the current user's ID string.

    Returns
    -------
    dict with keys:
        ``on_transit_toggle`` — callback for standard/circuits tab transit checkbox
        ``transit_nav_row``   — row widget (show/hide from outside)
        ``events_container``  — HTML widget for events sidebar
        ``shared_row``        — row widget for house select + Now button
        ``set_late_refs``     — callable(transit_cb, std_container, cir_container)
                                to bind widgets created later by tab builds
    """
    # Mutable container for widgets assigned AFTER build() returns.
    # Tab builds create transit_cb, std_chart_container, cir_chart_container
    # and hand them back via set_late_refs().
    _late: dict[str, Any] = {}

    def set_late_refs(*, transit_cb=None, std_chart_container=None, cir_chart_container=None):
        """Register late-bound UI references for transit callbacks."""
        if transit_cb is not None:
            _late["transit_cb"] = transit_cb
        if std_chart_container is not None:
            _late["std_chart_container"] = std_chart_container
        if cir_chart_container is not None:
            _late["cir_chart_container"] = cir_chart_container

    # ---- Synastry toggle + Chart 2 selector ----
    ui.separator().classes("q-mt-sm")
    synastry_cb = ui.checkbox(
        "👭 Synastry", value=state.get("synastry_mode", False)
    ).classes("q-mt-xs")

    synastry_row = ui.row().classes("w-full items-center gap-3 q-mt-xs")
    with synastry_row:
        ui.label("Chart 2:").classes("text-body2")
        chart2_profile_sel = ui.select(
            options=[], label="Select profile for Chart 2",
        ).classes("w-56")
        chart2_load_btn = ui.button("Load Chart 2", icon="download").props(
            "outline dense size=sm"
        )
        chart2_clear_btn = ui.button("Clear Chart 2", icon="clear").props(
            "flat dense size=sm color=negative"
        )
    synastry_row.set_visibility(False)

    # ---- SHARED CONTROLS (visible when a chart exists) ----
    shared_row = ui.row().classes("w-full items-center gap-4 q-mt-md")
    with shared_row:
        house_select = ui.select(
            ["Placidus", "Whole Sign", "Equal", "Koch",
             "Campanus", "Regiomontanus", "Porphyry"],
            label="House System",
            value=(state.get("house_system", "placidus") or "placidus").title(),
        ).classes("w-48")

        # --- "Now" quick-city button ---
        now_btn = ui.button("Now", icon="schedule").props(
            "outline dense size=sm"
        )

        async def _on_now_click():
            """Set the birth form to current time at the stored city."""
            lat = state.get("current_lat")
            lon = state.get("current_lon")
            tz_name = state.get("current_tz_name")
            city_val = state.get("city") or form.get("city") or ""

            if not (isinstance(lat, (int, float))
                    and isinstance(lon, (int, float))
                    and tz_name):
                ui.notify(
                    "Enter a city and calculate a chart first, then "
                    "click Now to use the current time.",
                    type="warning",
                )
                return

            try:
                tz = pytz.timezone(tz_name)
            except Exception:
                ui.notify(f"Unknown timezone: {tz_name}", type="negative")
                return

            now = _dt.datetime.now(tz)
            h24 = now.hour
            _ampm = "PM" if h24 >= 12 else "AM"
            _h12 = h24 % 12 or 12

            form["year"] = now.year
            form["month_name"] = MONTH_NAMES[now.month - 1]
            form["day"] = now.day
            form["hour_12"] = f"{_h12:02d}"
            form["minute_str"] = f"{now.minute:02d}"
            form["ampm"] = _ampm
            form["city"] = city_val
            form["unknown_time"] = False

            from src.chart_adapter import ChartInputs, compute_chart
            month_idx = MONTH_NAMES.index(form["month_name"]) + 1
            inputs = ChartInputs(
                name=state.get("name") or form.get("name") or "",
                year=now.year, month=month_idx, day=now.day,
                hour_24=h24, minute=now.minute,
                city=city_val,
                lat=lat, lon=lon, tz_name=tz_name,
                unknown_time=False,
                house_system=(
                    state.get("house_system", "placidus") or "placidus"
                ).lower(),
                gender=form.get("gender"),
            )
            try:
                result = compute_chart(inputs)
                if result.error:
                    ui.notify(f"Chart error: {result.error}", type="negative")
                    return
                state["last_chart_json"] = (
                    result.chart.to_json() if result.chart else None
                )
                state["chart_ready"] = True
                state["year"] = now.year
                state["month_name"] = MONTH_NAMES[now.month - 1]
                state["day"] = now.day
                state["city"] = city_val
                build_circuit_toggles()
                rerender_active_tab()
                ui.notify(
                    f"Chart set to now: {now:%B %d, %Y %I:%M %p}",
                    type="positive",
                )
            except Exception as exc:
                ui.notify(f"Chart calculation failed: {exc}", type="negative")

        now_btn.on_click(_on_now_click)

        events_container = ui.html("").classes("text-body2")

    def _on_house_system_change(e):
        """Change the house system from the transit controls."""
        state["house_system"] = (e.value or "placidus").lower()
        rerender_active_tab()
        refresh_drawer()

    house_select.on_value_change(_on_house_system_change)

    # ---- Transit / synastry controls ----
    transit_nav_row = ui.row().classes("w-full items-center gap-2 q-mt-xs")
    transit_nav_row.set_visibility(state.get("transit_mode", False))

    with transit_nav_row:
        transit_back_btn = ui.button("◀").props("flat dense size=sm")
        transit_now_btn = ui.button("Now").props("outline dense size=sm")
        transit_fwd_btn = ui.button("▶").props("flat dense size=sm")
        _INTERVAL_OPTS = ["1 day", "1 week", "1 month", "1 year", "1 decade"]
        _stored_interval = state.get("transit_nav_interval", "1 day")
        if _stored_interval not in _INTERVAL_OPTS:
            _stored_interval = "1 day"
            state["transit_nav_interval"] = _stored_interval
        transit_interval_sel = ui.select(
            _INTERVAL_OPTS,
            value=_stored_interval,
        ).props("dense").classes("w-28")
        transit_dt_label = ui.label("").classes("text-body2 text-grey-7")
        swap_btn = ui.button("Swap Charts", icon="swap_horiz").props(
            "outline dense size=sm"
        )

    def _refresh_chart2_profiles():
        """Reload the chart-2 profile dropdown."""
        uid = get_user_id()
        if not uid:
            return
        try:
            from src.db.supabase_profiles import load_user_profiles_db
            profiles = load_user_profiles_db(uid)
            names = sorted(profiles.keys())
            chart2_profile_sel.options = names
            chart2_profile_sel.update()
        except Exception as exc:
            _log.warning("Failed to refresh chart 2 profiles: %s", exc)
            ui.notify(
                f"Could not load profiles — {exc}. Try clicking Refresh.",
                type="negative", timeout=8000,
            )

    def _update_transit_label():
        """Update the transit date/time display label."""
        iso = state.get("transit_dt_iso")
        if iso:
            try:
                utc = _dt.datetime.fromisoformat(iso)
                tz_name = state.get("current_tz_name", "UTC")
                from zoneinfo import ZoneInfo
                local = utc.replace(tzinfo=_dt.timezone.utc).astimezone(ZoneInfo(tz_name))
                transit_dt_label.text = f"Chart date: {local:%b %d, %Y  %H:%M} {tz_name}"
            except Exception:
                transit_dt_label.text = f"Transit: {iso[:16]}"
        else:
            transit_dt_label.text = ""

    def _compute_and_store_transit(utc: _dt.datetime):
        """Compute a transit chart for *utc* and store it in state."""
        from src.chart_adapter import compute_transit_chart
        lat = state.get("current_lat")
        lon = state.get("current_lon")
        tz_name = state.get("current_tz_name", "UTC")
        city = state.get("city", "")
        house_sys = (state.get("house_system", "placidus") or "placidus").lower()

        if lat is None or lon is None:
            return

        result = compute_transit_chart(
            lat=lat, lon=lon, tz_name=tz_name,
            city=city, house_system=house_sys,
            transit_utc=utc,
        )
        if result.chart is not None:
            state["last_chart_2_json"] = result.chart.to_json()
            state["transit_dt_iso"] = utc.isoformat()
            state["transit_mode"] = True
            state["synastry_mode"] = False
            _update_transit_label()
            rerender_active_tab()

    def on_transit_toggle(e):
        """Enable or disable transit overlay mode."""
        state["transit_mode"] = e.value
        transit_nav_row.set_visibility(e.value)
        if e.value:
            if not state.get("last_chart_2_json"):
                now_utc = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
                _compute_and_store_transit(now_utc)
            else:
                rerender_active_tab()
        else:
            rerender_active_tab()

    def _on_transit_now():
        """Set the transit time to the current UTC moment."""
        now_utc = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
        _compute_and_store_transit(now_utc)

    transit_now_btn.on_click(_on_transit_now)

    def _nav_transit(direction: int):
        """Step the transit time forward or backward by one day."""
        iso = state.get("transit_dt_iso")
        if not iso:
            now_utc = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
        else:
            now_utc = _dt.datetime.fromisoformat(iso)

        interval = state.get("transit_nav_interval", "1 day")
        if interval == "1 day":
            new_dt = now_utc + _dt.timedelta(days=direction)
        elif interval == "1 week":
            new_dt = now_utc + _dt.timedelta(weeks=direction)
        elif interval == "1 month":
            new_dt = now_utc + relativedelta(months=direction)
        elif interval == "1 year":
            new_dt = now_utc + relativedelta(years=direction)
        elif interval == "1 decade":
            new_dt = now_utc + relativedelta(years=10 * direction)
        else:
            new_dt = now_utc + _dt.timedelta(days=direction)

        _compute_and_store_transit(new_dt)

    transit_back_btn.on_click(lambda: _nav_transit(-1))
    transit_fwd_btn.on_click(lambda: _nav_transit(1))
    transit_interval_sel.on_value_change(
        lambda e: state.update(transit_nav_interval=e.value)
    )

    def _on_swap_charts():
        """Swap chart-1 and chart-2 data in synastry mode."""
        c1_json = state.get("last_chart_json")
        c2_json = state.get("last_chart_2_json")
        if c1_json and c2_json:
            state["last_chart_json"] = c2_json
            state["last_chart_2_json"] = c1_json
            rerender_active_tab()
            refresh_drawer()

    swap_btn.on_click(_on_swap_charts)

    def _on_load_chart2():
        """Load a second chart profile for synastry comparison."""
        uid = get_user_id()
        selected = chart2_profile_sel.value
        if not uid or not selected:
            return
        try:
            from src.db.supabase_profiles import load_user_profiles_db
            from src.db.profile_helpers import apply_profile
            profiles = load_user_profiles_db(uid)
            prof_data = profiles.get(selected)
            if prof_data is None:
                return

            temp: dict = {}
            apply_profile(selected, prof_data, temp)
            chart2_obj = temp.pop("last_chart", None)
            if chart2_obj is not None and hasattr(chart2_obj, "to_json"):
                state["last_chart_2_json"] = chart2_obj.to_json()
                state["synastry_mode"] = True
                state["transit_mode"] = False
                state["chart_2_profile_name"] = selected
                tcb = _late.get("transit_cb")
                if tcb is not None:
                    tcb.value = False
                transit_nav_row.set_visibility(False)
                rerender_active_tab()
                try:
                    sc = _late.get("std_chart_container")
                    cc = _late.get("cir_chart_container")
                    if sc:
                        sc.update()
                    if cc:
                        cc.update()
                except Exception:
                    pass
        except Exception:
            _log.exception("Chart 2 load failed")

    chart2_load_btn.on_click(_on_load_chart2)

    def _on_clear_chart2():
        """Clear the second chart and exit synastry mode."""
        state["last_chart_2_json"] = None
        state["synastry_mode"] = False
        state["transit_mode"] = False
        state["chart_2_profile_name"] = None
        state["transit_dt_iso"] = None
        tcb = _late.get("transit_cb")
        if tcb is not None:
            tcb.value = False
        transit_nav_row.set_visibility(False)
        rerender_active_tab()
        try:
            sc = _late.get("std_chart_container")
            cc = _late.get("cir_chart_container")
            if sc:
                sc.update()
            if cc:
                cc.update()
        except Exception:
            pass

    chart2_clear_btn.on_click(_on_clear_chart2)

    def _on_synastry_toggle(e):
        """Toggle synastry mode on or off."""
        if e.value:
            state["synastry_mode"] = True
            _refresh_chart2_profiles()
            synastry_row.set_visibility(True)
            if state.get("last_chart_2_json"):
                rerender_active_tab()
                try:
                    sc = _late.get("std_chart_container")
                    cc = _late.get("cir_chart_container")
                    if sc:
                        sc.update()
                    if cc:
                        cc.update()
                except Exception:
                    pass
        else:
            synastry_row.set_visibility(False)
            _on_clear_chart2()

    synastry_cb.on_value_change(_on_synastry_toggle)

    # Restore Chart 2 selector if synastry was already active (page reload)
    if state.get("synastry_mode", False):
        ui.timer(0.5, _refresh_chart2_profiles, once=True)
        synastry_row.set_visibility(True)

    return {
        "on_transit_toggle": on_transit_toggle,
        "transit_nav_row": transit_nav_row,
        "events_container": events_container,
        "shared_row": shared_row,
        "set_late_refs": set_late_refs,
    }
