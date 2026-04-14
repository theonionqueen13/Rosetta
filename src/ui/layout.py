"""Layout module: left drawer (planet profiles) + top header bar."""
from __future__ import annotations

import logging
from nicegui import ui
from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)

# ---------- Planet profile CSS (matches Streamlit sidebar styling) -----------
_PROFILE_CSS = """
<style>
.pf-root { font-size: 0.92em; line-height: 1.45; }
.pf-block { margin-bottom: 0.7em; }
.pf-block hr.pf-divider { border:none; border-top: 1px solid #ddd; margin-top:0.5em; }
.pf-title { font-size: 1.05em; margin-bottom: 2px; }
.pf-meaning { color: #888; font-size: 0.88em; margin-bottom: 4px; }
.planet-profile-card { scroll-margin-top: 8px; }
</style>
"""


def build(state: dict, *, email: str, do_logout) -> dict:
    """Build the left drawer and top header bar.

    Returns
    -------
    dict with keys:
        drawer        – the ui.left_drawer widget
        refresh_drawer – callable to repopulate planet profiles
    """

    # ===================================================================
    # LEFT DRAWER — Planet Profiles
    # ===================================================================
    drawer = ui.left_drawer(value=False, bordered=True).classes("q-pa-md").style(
        "width: 380px"
    )
    with drawer:
        ui.label("🪐 Planet Profiles in View").classes("text-h6 q-mb-sm")
        profile_mode_radio = ui.radio(
            ["Stats", "Profile", "Full"],
            value=state.get("profile_view_mode", "Stats"),
        ).props("inline dense")
        ui.separator().classes("q-my-sm")
        drawer_content = ui.column().classes("w-full")

    def _refresh_drawer():
        """Re-render planet profile cards in the left drawer."""
        chart_obj = get_chart_object(state)
        if chart_obj is None:
            drawer_content.clear()
            with drawer_content:
                ui.label("No chart loaded.").classes("text-body2 text-grey")
            return

        mode = profile_mode_radio.value or "Stats"
        state["profile_view_mode"] = mode
        house_sys = state.get("house_system", "placidus").title()
        unknown_time = getattr(chart_obj, "unknown_time", False)

        try:
            from src.rendering.profiles_v2 import format_object_profile_html, ordered_objects
            from src.core.planet_profiles import (
                format_planet_profile_html,
                format_full_planet_profile_html,
            )

            ordered_rows = ordered_objects(chart_obj)
            if not ordered_rows:
                drawer_content.clear()
                with drawer_content:
                    ui.label("No objects to display.").classes("text-body2 text-grey")
                return

            blocks = []
            for row in ordered_rows:
                if mode == "Stats":
                    block = format_object_profile_html(
                        row, house_label=house_sys,
                        include_house_data=not unknown_time,
                    )
                elif mode == "Profile":
                    block = format_planet_profile_html(
                        row, chart_obj, ordered_rows, house_system=house_sys,
                    )
                else:
                    block = format_full_planet_profile_html(
                        row, chart_obj, ordered_rows,
                        house_system=house_sys,
                        include_house_data=not unknown_time,
                    )
                planet_name = (
                    row.object_name.name
                    if hasattr(row, "object_name") and row.object_name
                    else "unknown"
                )
                pid = f"rosetta-planet-{planet_name.replace(' ', '-').lower()}"
                blocks.append(f"<div id='{pid}' class='planet-profile-card'>{block}</div>")

            html = _PROFILE_CSS + "<div class='pf-root'>" + "\n".join(blocks) + "</div>"
            drawer_content.clear()
            with drawer_content:
                ui.html(html)
        except Exception as exc:
            _log.exception("Planet profiles render failed")
            drawer_content.clear()
            with drawer_content:
                ui.label(f"Error: {exc}").classes("text-body2 text-negative")

    profile_mode_radio.on_value_change(lambda _: _refresh_drawer())

    # ===================================================================
    # TOP BAR
    # ===================================================================
    with ui.header().classes("items-center justify-between q-px-md").style(
        "background: black !important; border-bottom: 1px solid #333;"
    ):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=drawer.toggle).props("flat round color=white")
            ui.label().style(
                "width: 300px; height: 60px; background-image: url('/pngs/rosetta_banner.png');"
                " background-repeat: no-repeat; background-position: left center; background-size: contain;"
            )
        with ui.row().classes("items-center gap-2"):
            ui.label(f"👤 {email}").classes("text-body2")
            ui.button("Sign Out", on_click=do_logout).props("flat color=white size=sm")

    return {
        "drawer": drawer,
        "refresh_drawer": _refresh_drawer,
    }
