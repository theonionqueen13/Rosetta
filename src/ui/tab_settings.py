"""Settings tab — display options, house system, mode map."""
from __future__ import annotations

import logging
from typing import Any, Callable

from nicegui import ui

from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)


def build(
    state: dict,
    _form: dict,
    *,
    rerender_active_tab: Callable,
) -> dict[str, Any]:
    """Build the Settings tab inside the current ``ui.tab_panel`` context.

    Returns a dict with ``refresh_mode_map`` callback.
    """
    ui.label("Settings").classes("text-h5 q-mb-md")

    with ui.row().classes("w-full items-start gap-8"):
        # ---- Left column: display settings ----
        with ui.column().classes("gap-4"):
            ui.label("Display").classes("text-subtitle1 text-weight-medium")

            settings_label_style = ui.radio(
                ["Glyph", "Text"],
                value=("Glyph" if state.get("label_style", "glyph") == "glyph" else "Text"),
            ).props("inline")
            ui.label("Label Style").classes("text-caption text-grey-7 q-mt-n-xs")

            def _on_label_change(e):
                """Switch between glyph and text label styles."""
                state["label_style"] = "glyph" if e.value == "Glyph" else "text"
                rerender_active_tab()

            settings_label_style.on_value_change(_on_label_change)

            settings_dark = ui.switch("Dark Mode", value=state.get("dark_mode", False))

            def _on_dark_change(e):
                """Toggle dark mode for the chart and UI."""
                state["dark_mode"] = e.value
                if e.value:
                    ui.dark_mode().enable()
                else:
                    ui.dark_mode().disable()
                rerender_active_tab()

            settings_dark.on_value_change(_on_dark_change)

            settings_interactive = ui.switch(
                "Interactive Chart", value=state.get("interactive_chart", False),
            )

            def _on_interactive_change(e):
                """Toggle interactive D3 chart mode."""
                state["interactive_chart"] = e.value
                rerender_active_tab()

            settings_interactive.on_value_change(_on_interactive_change)

        # ---- Right column: chart system settings ----
        with ui.column().classes("gap-4"):
            ui.label("House System").classes("text-subtitle1 text-weight-medium")

            settings_house = ui.select(
                ["placidus", "equal", "whole sign"],
                value=state.get("house_system", "placidus"),
            ).classes("w-40")

            def _on_house_change(e):
                """Change the active house system and re-render."""
                state["house_system"] = e.value
                rerender_active_tab()

            settings_house.on_value_change(_on_house_change)

    # ---- Startup settings ----
    ui.separator().classes("q-mt-lg")
    ui.label("Startup").classes("text-subtitle1 text-weight-medium q-mt-sm")
    settings_auto_load = ui.checkbox(
        "Auto-load my chart on startup",
        value=state.get("auto_load_on_startup", True),
    )
    ui.label(
        "When checked, your saved \u2018self\u2019 profile is loaded automatically "
        "each time you sign in.  When unchecked, the app opens with no "
        "chart loaded so you can choose what to view."
    ).classes("text-caption text-grey-7 q-mb-sm")

    def _on_auto_load_change(e):
        """Toggle auto-load of last chart on startup."""
        state["auto_load_on_startup"] = e.value

    settings_auto_load.on_value_change(_on_auto_load_change)

    # ---- Chart Mode Map ----
    ui.separator().classes("q-mt-lg")
    mode_map_exp = ui.expansion(
        "Chart Mode Map", icon="account_tree",
    ).classes("w-full q-mt-sm")
    with mode_map_exp:
        mode_map_html_container = ui.html("").style("width: 100%;")

    def _refresh_mode_map():
        """Re-render the mode-map HTML panel."""
        from src.mode_map_core import render_mode_map_html

        chart_obj = get_chart_object(state)
        patterns = getattr(chart_obj, "aspect_groups", None) or [] if chart_obj else []
        shapes = getattr(chart_obj, "shapes", None) or [] if chart_obj else []
        singleton_map = getattr(chart_obj, "singleton_map", None) or {} if chart_obj else {}

        html = render_mode_map_html(
            chart_mode=state.get("chart_mode", "Circuits"),
            circuit_submode=state.get("circuit_submode", "Combined"),
            has_chart=chart_obj is not None,
            synastry_mode=state.get("synastry_mode", False),
            transit_mode=state.get("transit_mode", False),
            now_mode_active=state.get("now_mode_active", False),
            profile_loaded=state.get("profile_loaded", False),
            aspect_toggles=state.get("aspect_toggles", {}),
            pattern_toggles={int(k): v for k, v in state.get("pattern_toggles", {}).items()},
            singleton_toggles=state.get("singleton_toggles", {}),
            shape_toggles=state.get("shape_toggles", {}),
            synastry_aspects_chart1=state.get("synastry_chart1", False),
            synastry_aspects_inter=state.get("synastry_inter", True),
            synastry_aspects_chart2=state.get("synastry_chart2", False),
            num_patterns=len(patterns),
            num_shapes=len(shapes),
            num_singletons=len(singleton_map),
        )
        mode_map_html_container.content = (
            f'<iframe srcdoc="{html.replace(chr(34), "&quot;")}" '
            f'style="width:100%; height:560px; border:none;"></iframe>'
        )

    mode_map_exp.on_value_change(lambda e: _refresh_mode_map() if e.value else None)

    return {"refresh_mode_map": _refresh_mode_map}
