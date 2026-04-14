"""Rulers tab — dispositor graph + legend."""
from __future__ import annotations

import base64
import io
import logging
from typing import Any, Callable

from nicegui import ui

from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)


def build(
    state: dict,
    _form: dict,
) -> dict[str, Any]:
    """Build the Rulers tab inside the current ``ui.tab_panel`` context.

    Returns ``{"render_rulers_graph": callable}``.
    """
    rulers_scope_radio = ui.radio(
        ["By Sign", "By House"],
        value=state.get("dispositor_scope", "By Sign"),
    ).props("inline dense").classes("q-mb-sm")

    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("").style("min-width: 160px; max-width: 200px"):
            rulers_legend_container = ui.html("")
        with ui.column().classes("col"):
            rulers_chart_container = ui.column().classes("w-full items-center")

    # ── Legend ─────────────────────────────────────────────────────────
    def _build_rulers_legend():
        """Build the icon legend for the dispositor graph."""
        import os as _os
        png_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "..", "pngs")
        png_dir = _os.path.normpath(png_dir)

        def _img_b64(filename):
            """Return a base64-encoded image tag for an icon file."""
            path = _os.path.join(png_dir, filename)
            if _os.path.exists(path):
                with open(path, "rb") as f:
                    return base64.b64encode(f.read()).decode()
            return ""

        legend_items = [
            ("green.png", "Sovereign"),
            ("orange.png", "Dual rulership"),
            ("purple.png", "Loop"),
            ("purpleorange.png", "Dual + Loop"),
            ("blue.png", "Standard"),
            ("blue_reception.png", "Has reception (in orb)"),
            ("green_reception.png", "Has reception by sign"),
            ("conjunction.png", "Conjunction"),
            ("sextile.png", "Sextile"),
            ("square.png", "Square"),
            ("trine.png", "Trine"),
            ("opposition.png", "Opposition"),
        ]

        html = (
            '<div style="background-color:#262730;padding:12px;'
            'border-radius:8px;font-size:0.9em;color:white;">'
            '<strong>Legend</strong>'
            '<div style="margin:8px 0 8px 0;border-bottom:1px solid #444;'
            'padding-bottom:8px;">↻ Self-Ruling</div>'
        )
        for i, (img, label) in enumerate(legend_items):
            sep = (
                'margin-top:8px;border-top:1px solid #444;padding-top:8px;'
                if i == 5 else ""
            )
            b64 = _img_b64(img)
            if b64:
                html += (
                    f'<div style="margin-bottom:6px;{sep}">'
                    f'<img src="data:image/png;base64,{b64}" '
                    f'width="18" style="vertical-align:middle;margin-right:6px"/>'
                    f'<span>{label}</span></div>'
                )
        html += "</div>"
        rulers_legend_container.content = html

    # ── Graph ─────────────────────────────────────────────────────────
    def _render_rulers_graph():
        """Render the dispositor graph image and annotations."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        chart_obj = get_chart_object(state)
        if chart_obj is None:
            rulers_chart_container.clear()
            with rulers_chart_container:
                ui.label("Calculate a chart first.").classes("text-body2 text-grey q-pa-md")
            return

        plot_data = getattr(chart_obj, "plot_data", None)
        if plot_data is None:
            try:
                from src.core.calc_v2 import compute_plot_data_from_chart
                plot_data = compute_plot_data_from_chart(chart_obj)
                chart_obj.plot_data = plot_data
            except Exception:
                pass

        if plot_data is None:
            rulers_chart_container.clear()
            with rulers_chart_container:
                ui.label("No dispositor data available.").classes("text-body2 text-grey q-pa-md")
            return

        scope = rulers_scope_radio.value or "By Sign"
        house_sys = (state.get("house_system", "placidus") or "placidus").lower()

        if scope == "By Sign":
            scope_data = plot_data.get("by_sign")
        else:
            house_key_map = {
                "placidus": "Placidus",
                "equal": "Equal",
                "whole sign": "Whole Sign",
                "whole": "Whole Sign",
            }
            plot_data_key = house_key_map.get(house_sys, "Placidus")
            scope_data = plot_data.get(plot_data_key)

        if not scope_data or not scope_data.get("raw_links"):
            rulers_chart_container.clear()
            with rulers_chart_container:
                ui.label("No dispositor graph to display.").classes("text-body2 text-grey q-pa-md")
            return

        try:
            name, date_line, time_line, city, extra_line = chart_obj.header_lines()
            header_info = {
                "name": name, "date_line": date_line,
                "time_line": time_line, "city": city, "extra_line": extra_line,
            }
        except Exception:
            header_info = None

        try:
            from src.rendering.dispositor_graph import plot_dispositor_graph

            fig = plot_dispositor_graph(
                scope_data, chart=chart_obj,
                header_info=header_info, house_system=house_sys,
            )
            if fig is None:
                rulers_chart_container.clear()
                with rulers_chart_container:
                    ui.label("Graph returned empty.").classes("text-body2 text-grey")
                return

            buf = io.BytesIO()
            fig.savefig(
                buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), edgecolor="none",
            )
            plt.close(fig)
            buf.seek(0)
            png_bytes = buf.read()

            b64 = base64.b64encode(png_bytes).decode()
            rulers_chart_container.clear()
            with rulers_chart_container:
                ui.html(
                    f'<img src="data:image/png;base64,{b64}" '
                    f'style="width:100%; max-width:1000px; '
                    f'image-rendering:auto; display:block; margin:0 auto" />'
                )
        except Exception as exc:
            _log.exception("Dispositor graph render failed")
            rulers_chart_container.clear()
            with rulers_chart_container:
                ui.label(f"Render error: {exc}").classes("text-body2 text-negative")

    def _on_rulers_scope_change(e):
        """Handle dispositor scope radio change and re-render."""
        state["dispositor_scope"] = e.value
        _render_rulers_graph()

    rulers_scope_radio.on_value_change(_on_rulers_scope_change)
    _build_rulers_legend()

    return {"render_rulers_graph": _render_rulers_graph}
