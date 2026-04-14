"""Chart Manager tab — birth form, profile CRUD, donate dialog."""
from __future__ import annotations

import calendar
import logging
from typing import Any, Callable

from nicegui import ui

from src.core.static_data import MONTH_NAMES
from src.nicegui_state import ensure_state, get_chart_object
from src.ui.auth import get_user_id

_log = logging.getLogger(__name__)


def _handle_unknown_time(is_unknown: bool, form: dict, hour_sel, min_sel, ampm_sel):
    """Toggle time selectors and form values when Unknown Time changes."""
    if is_unknown:
        form["hour_12"]    = "--"
        form["minute_str"] = "--"
        form["ampm"]       = "--"
        hour_sel.value  = "--"
        min_sel.value   = "--"
        ampm_sel.value  = "--"
        hour_sel.disable()
        min_sel.disable()
        ampm_sel.disable()
    else:
        if form.get("hour_12") == "--":
            form["hour_12"] = "12"
            hour_sel.value = "12"
        if form.get("minute_str") == "--":
            form["minute_str"] = "00"
            min_sel.value = "00"
        if form.get("ampm") == "--":
            form["ampm"] = "AM"
            ampm_sel.value = "AM"
        hour_sel.enable()
        min_sel.enable()
        ampm_sel.enable()


def build(
    state: dict,
    form: dict,
    *,
    rerender_active_tab: Callable,
) -> dict[str, Any]:
    """Build the Chart Manager tab panel contents.

    Returns
    -------
    dict with keys:
        ``calc_btn`` – calculate button widget
        ``save_name_input`` – profile name input
        ``is_my_chart_cb`` – "My chart (self)" checkbox
        ``birth_exp`` – birth data expansion
        ``status_label`` – status label for calculator
        ``profile_select`` – profile selector
        ``refresh_profiles`` – callable to reload profiles
    """
    ui.label("Save/Load Chart").classes("text-h6 q-mb-sm")

    birth_exp = ui.expansion("Enter Birth Data", icon="person_add").classes(
        "w-full"
    ).props("default-opened")

    with birth_exp:
        ui.html('<p style="color:#cc0000; font-size:0.78em; margin-bottom:2px;">* required fields</p>')

        unknown_cb = ui.checkbox("Unknown Time").bind_value(form, "unknown_time")

        ui.label("Gender (optional)").classes("text-body2 q-mt-sm")
        ui.radio(
            ["Female", "Male", "Non-binary"],
            value=form.get("gender"),
            on_change=lambda e: form.update(gender=e.value),
        ).props("inline")

        with ui.row().classes("w-full gap-4"):
            with ui.column().classes("col"):
                ui.input("Name *").bind_value(form, "name").classes("w-full")
            with ui.column().classes("col"):
                ui.input("City of Birth *").bind_value(form, "city").classes("w-full")

        with ui.row().classes("w-full gap-4 items-end"):
            with ui.column().classes("col"):
                ui.number("Year *", min=1000, max=3000, step=1, precision=0).bind_value(
                    form, "year",
                    forward=lambda v: int(v) if v else 2000,
                ).classes("w-full")
            with ui.column().classes("col"):
                ui.select(
                    MONTH_NAMES, label="Month *",
                ).bind_value(form, "month_name").classes("w-full")
            with ui.column().classes("col"):
                day_select = ui.select(
                    list(range(1, 32)), label="Day *",
                ).bind_value(form, "day").classes("w-full")

        def _refresh_days():
            """Update the day-of-month selector for the current month/year."""
            month_idx = MONTH_NAMES.index(form.get("month_name", "January")) + 1
            yr = int(form.get("year", 2000))
            try:
                max_day = calendar.monthrange(yr, month_idx)[1]
            except Exception:
                max_day = 31
            day_select.options = list(range(1, max_day + 1))
            day_select.update()
            if form.get("day", 1) > max_day:
                form["day"] = max_day
                day_select.value = max_day

        _refresh_days()

        HOURS   = ["--"] + [f"{h:02d}" for h in range(1, 13)]
        MINUTES = ["--"] + [f"{m:02d}" for m in range(0, 60)]
        AMPMS   = ["--", "AM", "PM"]

        with ui.row().classes("w-full gap-4 items-end"):
            with ui.column().classes("col"):
                hour_sel = ui.select(
                    HOURS, label="Hour",
                ).bind_value(form, "hour_12").classes("w-full")
            with ui.column().classes("col"):
                min_sel = ui.select(
                    MINUTES, label="Minute",
                ).bind_value(form, "minute_str").classes("w-full")
            with ui.column().classes("col"):
                ampm_sel = ui.select(
                    AMPMS, label="AM/PM",
                ).bind_value(form, "ampm").classes("w-full")

        unknown_cb.on_value_change(
            lambda e: _handle_unknown_time(e.value, form, hour_sel, min_sel, ampm_sel)
        )
        if form.get("unknown_time"):
            hour_sel.disable()
            min_sel.disable()
            ampm_sel.disable()

        ui.separator()

        status_label = ui.label("").classes("text-body2")
        status_label.set_visibility(False)

        calc_btn = ui.button(
            "Calculate Chart", icon="auto_awesome",
        ).classes("w-full q-mt-sm").props("color=primary")

    # ── Profile CRUD ──────────────────────────────────────────────
    profile_select = ui.select(
        options=[], label="Saved Profiles",
    ).classes("w-full")

    with ui.row().classes("w-full items-center gap-2 q-mt-sm"):
        save_name_input = ui.input(
            "Profile name to save",
        ).classes("col")
        is_my_chart_cb = ui.checkbox("My chart (self)")

    mgr_status = ui.label("").classes("text-body2")
    mgr_status.set_visibility(False)

    def _mgr_error(msg: str):
        """Show a red error status message."""
        mgr_status.text = msg
        mgr_status.classes(replace="text-body2 text-negative")
        mgr_status.set_visibility(True)

    def _mgr_success(msg: str):
        """Show a green success status message."""
        mgr_status.text = msg
        mgr_status.classes(replace="text-body2 text-positive")
        mgr_status.set_visibility(True)

    def _mgr_clear():
        """Hide the status message label."""
        mgr_status.set_visibility(False)

    def _refresh_profiles():
        """Reload the saved-profiles dropdown from the database."""
        uid = get_user_id()
        if not uid:
            return
        try:
            from src.db.supabase_profiles import load_user_profiles_db
            profiles = load_user_profiles_db(uid)
            names = sorted(profiles.keys())
            profile_select.options = names
            profile_select.update()
        except Exception as exc:
            _log.warning("Failed to refresh profiles: %s", exc)
            ui.notify(
                f"Could not load profiles — {exc}. Try clicking Refresh.",
                type="negative",
                timeout=8000,
            )

    async def _on_load():
        """Load the selected saved profile into the chart form."""
        _mgr_clear()
        uid = get_user_id()
        selected = profile_select.value
        if not uid or not selected:
            _mgr_error("Select a profile to load.")
            return
        try:
            from src.db.supabase_profiles import load_user_profiles_db
            profiles = load_user_profiles_db(uid)
            prof_data = profiles.get(selected)
            if prof_data is None:
                _mgr_error(f"Profile '{selected}' not found.")
                return

            from src.db.profile_helpers import apply_profile
            _state = ensure_state()
            apply_profile(selected, prof_data, _state)

            _chart_obj = _state.pop("last_chart", None)
            if _chart_obj is not None and hasattr(_chart_obj, "to_json"):
                _state["last_chart_json"] = _chart_obj.to_json()

            form["name"] = _state.get("birth_name") or _state.get("name") or selected
            form["city"] = _state.get("city", "")
            form["year"] = _state.get("year", 2000)
            form["month_name"] = _state.get("month_name", "January")
            form["day"] = _state.get("day", 1)
            form["hour_12"] = _state.get("hour_12", "12")
            form["minute_str"] = _state.get("minute_str", "00")
            form["ampm"] = _state.get("ampm", "AM")
            form["unknown_time"] = _state.get("profile_unknown_time", False)
            form["gender"] = _state.get("birth_gender")

            rerender_active_tab()

            save_name_input.value = selected
            is_my_chart_cb.value = _state.get("is_my_chart", False)
            _mgr_success(f"Loaded profile '{selected}'.")
            birth_exp.open()
        except Exception as exc:
            _log.exception("Profile load failed")
            _mgr_error(f"Load failed: {exc}")

    async def _on_save():
        """Save or update the current chart profile to the database."""
        _mgr_clear()
        uid = get_user_id()
        prof_name = (save_name_input.value or "").strip()
        if not uid:
            _mgr_error("Not authenticated.")
            return
        if not prof_name:
            _mgr_error("Enter a profile name.")
            return

        _state = ensure_state()
        chart_obj = get_chart_object(_state)
        if chart_obj is None:
            _mgr_error("Calculate a chart first before saving.")
            return

        try:
            from src.mcp.comprehension_models import PersonProfile as _PP
            from src.db.supabase_profiles import save_user_profile_db

            rel = "self" if is_my_chart_cb.value else "other"
            pp = _PP(
                name=prof_name,
                chart_id=prof_name,
                relationship_to_querent=rel,
                gender=form.get("gender"),
                significant_places=[chart_obj.city] if getattr(chart_obj, "city", None) else [],
                astro_chart=chart_obj,
            )
            save_user_profile_db(uid, prof_name, pp.to_dict())
            _refresh_profiles()
            profile_select.value = prof_name
            _mgr_success(f"Saved profile '{prof_name}'.")
        except Exception as exc:
            _log.exception("Profile save failed")
            _mgr_error(f"Save failed: {exc}")

    async def _on_delete():
        """Delete the selected saved profile from the database."""
        _mgr_clear()
        uid = get_user_id()
        selected = profile_select.value
        if not uid or not selected:
            _mgr_error("Select a profile to delete.")
            return
        try:
            from src.db.supabase_profiles import delete_user_profile_db
            delete_user_profile_db(uid, selected)
            _refresh_profiles()
            profile_select.value = None
            save_name_input.value = ""
            _mgr_success(f"Deleted profile '{selected}'.")
        except Exception as exc:
            _log.exception("Profile delete failed")
            _mgr_error(f"Delete failed: {exc}")

    with ui.row().classes("w-full gap-2 q-mt-sm"):
        load_btn = ui.button("Load", icon="download").props("outline")
        save_btn = ui.button("Save", icon="save").props("outline color=primary")
        delete_btn = ui.button("Delete", icon="delete").props("outline color=negative")
        refresh_btn = ui.button("Refresh List", icon="refresh").props("flat size=sm")

    load_btn.on_click(_on_load)
    save_btn.on_click(_on_save)
    delete_btn.on_click(_on_delete)
    refresh_btn.on_click(lambda: _refresh_profiles())

    ui.timer(0.5, _refresh_profiles, once=True)

    # ── Donate section ─────────────────────────────────────────────
    ui.separator().classes("q-mt-md")
    ui.label("Donate Your Chart to Science").classes("text-subtitle2 q-mt-sm")
    ui.label(
        "Optional: donate a chart profile to the research dataset. "
        "Joylin may study donated charts for app development."
    ).classes("text-caption text-grey")

    with ui.dialog() as donate_dlg, ui.card().style("max-width: 500px"):
        ui.label("Donate Chart to Science").classes("text-h6 q-mb-sm")
        ui.label(
            "This is entirely voluntary. If you choose to donate your "
            "chart, it will only be available to the app admin (Joylin) "
            "for research and development."
        ).classes("text-body2 q-mb-md")
        donate_name_input = ui.input(
            "Name or Event label",
            placeholder="e.g. My Birth Chart",
        ).classes("w-full")
        donate_status = ui.label("").classes("text-body2 q-mt-sm")
        donate_status.set_visibility(False)

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=donate_dlg.close).props("flat")

            def _do_donate():
                """Create a donated copy of the current chart under a new label."""
                label = (donate_name_input.value or "").strip()
                if not label:
                    donate_status.text = "Please give a name."
                    donate_status.classes(replace="text-body2 text-negative")
                    donate_status.set_visibility(True)
                    return
                chart_obj = get_chart_object(state)
                if chart_obj is None:
                    donate_status.text = "No chart loaded."
                    donate_status.classes(replace="text-body2 text-negative")
                    donate_status.set_visibility(True)
                    return
                payload = {
                    "year": state.get("year", 2000),
                    "month": (
                        MONTH_NAMES.index(state.get("month_name", "January")) + 1
                    ),
                    "day": state.get("day", 1),
                    "city": state.get("city", ""),
                    "lat": state.get("current_lat"),
                    "lon": state.get("current_lon"),
                    "tz_name": state.get("current_tz_name"),
                }
                try:
                    from src.db.profile_helpers import community_save
                    uid = get_user_id() or "anon"
                    community_save(label, payload, submitted_by=uid)
                    donate_status.text = f'Thank you! Donated as "{label}".'
                    donate_status.classes(replace="text-body2 text-positive")
                    donate_status.set_visibility(True)
                except Exception as exc:
                    donate_status.text = f"Error: {exc}"
                    donate_status.classes(replace="text-body2 text-negative")
                    donate_status.set_visibility(True)

            ui.button(
                "Donate", icon="volunteer_activism",
                on_click=_do_donate,
            ).props("color=primary")

    donate_btn = ui.button(
        "Donate Chart", icon="volunteer_activism",
    ).props("outline size=sm").classes("q-mt-xs")
    donate_btn.on_click(donate_dlg.open)

    return {
        "calc_btn": calc_btn,
        "save_name_input": save_name_input,
        "is_my_chart_cb": is_my_chart_cb,
        "birth_exp": birth_exp,
        "status_label": status_label,
        "profile_select": profile_select,
        "refresh_profiles": _refresh_profiles,
    }
