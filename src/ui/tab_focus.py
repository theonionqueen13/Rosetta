"""Focus tab — focused-planet selector, highlight overlays, scan for connections."""
from __future__ import annotations

import logging
from typing import Any, Callable, List

import traceback as _traceback

from nicegui import ui

from src.nicegui_state import get_chart_object
from src.ui.chart_display import render_chart_png, serialize_chart_for_d3, display_chart_in, display_d3_chart_in
from src.core.calc_v2 import scan_focus_connections, build_aspect_edges, analyze_dispositors
from src.core.patterns_v2 import detect_shapes_from_dataframe

_log = logging.getLogger(__name__)

_MAX_FOCUS = 3        # maximum number of focus planets
_PLACEHOLDER = ""     # empty string = "choose a planet" slot


def _get_chart_object_names(state: dict) -> List[str]:
    """Return sorted list of object names from the current chart."""
    chart_obj = get_chart_object(state)
    if chart_obj is None:
        return []
    names: List[str] = []
    for obj in chart_obj.objects:
        if obj.object_name:
            raw = obj.object_name
            names.append(raw if isinstance(raw, str) else raw.name)
    return sorted(set(names))


def _active_focus_planets(state: dict) -> List[str]:
    """Return only non-empty focus planets (filtering out placeholder slots)."""
    return [p for p in state.get("focus_planets", []) if p]


def build(
    state: dict,
    _form: dict,
    *,
    rerender_active_tab: Callable,
) -> dict[str, Any]:
    """Build the Focus tab panel contents.

    Returns
    -------
    dict with keys:
        ``focus_chart_container`` – ui.column for chart rendering
        ``refresh_focus_tab``     – callable to redraw the chart pane
    """

    # ── top-level column ─────────────────────────────────────────────────
    with ui.column().classes("w-full gap-3"):

        # ── 1. Focus planet selectors ─────────────────────────────────────
        selectors_col = ui.column().classes("w-full gap-2")

        # ── 2. Options expansion ──────────────────────────────────────────
        with ui.expansion("Options").classes("w-full").props("dense"):
            with ui.column().classes("gap-1 q-pl-sm"):
                parent_shape_cb = ui.checkbox(
                    "Show Parent Shape",
                    value=state.get("focus_show_parent_shape", False),
                )
                full_circuit_cb = ui.checkbox(
                    "Show Full Circuit",
                    value=state.get("focus_show_full_circuit", False),
                )

        # ── 3. Scan for Connections row (hidden when < 2 planets) ─────────
        with ui.row().classes("items-center gap-2 w-full q-mt-sm") as scan_row:
            scan_cb = ui.checkbox(
                "Scan for Connections",
                value=state.get("focus_scan_connections", False),
            )

        # ── 4. Results display (below scan checkbox, hidden initially) ────
        with ui.column().classes(
            "gap-1 q-pl-sm w-full border rounded-sm p-3 "
            "bg-blue-50 dark:bg-blue-900 border-blue-200 dark:border-blue-800"
        ) as results_display:
            pass  # populated dynamically

        results_display.visible = False
        scan_row.visible = len(_active_focus_planets(state)) >= 2

        # ── 5. Chart container ────────────────────────────────────────────
        focus_chart_container = ui.column().classes("w-full items-center")

        # ── Function definitions ──────────────────────────────────────────

        def _populate_scan_results():
            """Populate the results display with focus connection information."""
            results_display.clear()
            selected = _active_focus_planets(state)
            
            if len(selected) < 2:
                results_display.visible = False
                return
            
            chart_obj = get_chart_object(state)
            if chart_obj is None:
                with results_display:
                    ui.label("No chart available").classes("text-caption text-grey")
                return
            
            try:
                # Build aspect edges
                edges_major, edges_minor, edges_harmonic = build_aspect_edges(chart_obj)

                # Build dispositor data — extract Placidus cusp degrees via dataclass attrs
                pos = {
                    (obj.object_name if isinstance(obj.object_name, str) else obj.object_name): obj.longitude
                    for obj in chart_obj.objects
                    if obj.object_name
                }
                cusps_placidus = None
                if chart_obj.house_cusps:
                    cusps_placidus = [
                        getattr(c, "absolute_degree", 0)
                        for c in chart_obj.house_cusps
                        if getattr(c, "house_system", "").strip().lower() == "placidus"
                    ][:12] or None
                dispositors = analyze_dispositors(pos, cusps_placidus) if pos else {}

                # Detect shapes
                try:
                    shapes = detect_shapes_from_dataframe(None, edges_major) if edges_major else []
                except Exception:
                    shapes = []

                # Scan for connections
                connection_data = scan_focus_connections(
                    chart=chart_obj,
                    selected_planets=selected,
                    edges_major=edges_major,
                    edges_minor=edges_minor,
                    edges_harmonic=edges_harmonic,
                    shapes=shapes,
                    dispositors_by_sign=dispositors.get("by_sign") if dispositors else None,
                    dispositors_by_house=dispositors.get("by_house") if dispositors else None,
                )

                if not connection_data:
                    with results_display:
                        ui.label("No connections found between selected planets.").classes(
                            "text-caption text-grey"
                        )
                    return

                # Display connections pair by pair
                with results_display:
                    for (p1, p2), conn_info in connection_data.items():
                        direct = conn_info.get("direct_connections", [])
                        indirect = conn_info.get("indirect_connections", [])

                        with ui.column().classes("gap-1 q-mb-md border-b pb-2 w-full"):
                            ui.label(f"{p1} — {p2}").classes("text-weight-medium text-base")

                            # Direct connections
                            if direct:
                                with ui.column().classes("gap-1 q-ml-md"):
                                    for conn in direct:
                                        ctype = conn.get("type", "")
                                        if ctype == "aspect":
                                            asp = conn.get("aspect", "Unknown")
                                            orb = conn.get("orb", 0)
                                            applying = (
                                                "applying"
                                                if conn.get("applying")
                                                else "separating"
                                            )
                                            ui.label(
                                                f"• {asp} ({orb:.2f}°, {applying})"
                                            ).classes("text-caption")
                                        elif ctype == "rulership_sign":
                                            ruler = conn.get("ruler", "")
                                            ruled = conn.get("ruled", "")
                                            ui.label(
                                                f"• {ruler} rules {ruled} by sign"
                                            ).classes("text-caption")
                                        elif ctype == "rulership_house":
                                            ruler = conn.get("ruler", "")
                                            ruled = conn.get("ruled", "")
                                            systems = ", ".join(
                                                sorted(conn.get("systems", []))
                                            )
                                            ui.label(
                                                f"• {ruler} rules {ruled}'s house ({systems})"
                                            ).classes("text-caption")
                                        elif ctype == "reception":
                                            if conn.get("mutual"):
                                                ui.label(
                                                    f"• Mutual reception between {p1} & {p2}"
                                                ).classes("text-caption")
                                            elif conn.get("a_receives_b"):
                                                ui.label(
                                                    f"• {p1} receives {p2}"
                                                ).classes("text-caption")
                                            elif conn.get("b_receives_a"):
                                                ui.label(
                                                    f"• {p2} receives {p1}"
                                                ).classes("text-caption")

                            # Indirect connections
                            if indirect:
                                with ui.column().classes("gap-1 q-ml-md"):
                                    for conn in indirect:
                                        ctype = conn.get("type", "")
                                        if ctype == "circuit":
                                            desc = conn.get("description", "")
                                            ui.label(f"◦ {desc}").classes(
                                                "text-caption text-italic"
                                            )
                                        elif ctype == "rulership_chain":
                                            chain = conn.get("chain", "")
                                            ui.label(
                                                f"◦ Rulership chain: {chain}"
                                            ).classes("text-caption text-italic")

                            if not direct and not indirect:
                                ui.label("  No connections found.").classes(
                                    "text-caption text-grey q-ml-md"
                                )

            except Exception as exc:
                tb = _traceback.format_exc()
                _log.error("Error populating scan results:\n%s", tb)
                with results_display:
                    ui.label(f"Error: {exc}").classes("text-caption text-red-500")
                    for line in tb.splitlines()[-8:]:
                        if line.strip():
                            ui.label(line).classes("text-caption text-grey-7 font-mono")

        def _rebuild_scan_ui():
            """Show/hide the scan row based on how many focus planets are active."""
            selected = _active_focus_planets(state)
            scan_row.visible = len(selected) >= 2
            if len(selected) < 2:
                scan_cb.value = False
                results_display.visible = False
                state["focus_scan_connections"] = False

        def _rebuild_selectors():
            """Rebuild the focus-planet dropdown rows from scratch."""
            selectors_col.clear()
            object_names = _get_chart_object_names(state)
            focus_slots: List[str] = list(state.get("focus_planets", []))
            # Ensure at least one (empty) slot is shown
            if not focus_slots:
                focus_slots = [_PLACEHOLDER]
                state["focus_planets"] = list(focus_slots)

            with selectors_col:
                for idx, slot_value in enumerate(focus_slots):
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.label(f"Focus Planet {idx + 1}:").classes(
                            "text-caption text-weight-medium" + (" w-32" if idx > 0 else " w-32")
                        )

                        sel = ui.select(
                            options=object_names,
                            value=slot_value if slot_value else None,
                            with_input=True,
                            label="Select a planet…",
                        ).classes("flex-1")

                        def _make_on_select(i):
                            def _on_select(e):
                                slots = list(state.get("focus_planets", []))
                                while len(slots) <= i:
                                    slots.append(_PLACEHOLDER)
                                slots[i] = e.value or _PLACEHOLDER
                                state["focus_planets"] = slots
                                state["selected_planets"] = _active_focus_planets(state)
                                _rebuild_scan_ui()
                                rerender_active_tab()
                            return _on_select

                        sel.on_value_change(_make_on_select(idx))

                        if len(focus_slots) > 1:
                            def _make_remove(i):
                                def _remove():
                                    slots = list(state.get("focus_planets", []))
                                    if i < len(slots):
                                        slots.pop(i)
                                    if not slots:
                                        slots = [_PLACEHOLDER]
                                    state["focus_planets"] = slots
                                    state["selected_planets"] = _active_focus_planets(state)
                                    _rebuild_selectors()
                                    _rebuild_scan_ui()
                                    rerender_active_tab()
                                return _remove

                            ui.button(
                                icon="remove_circle_outline",
                                on_click=_make_remove(idx),
                            ).props("flat dense").tooltip("Remove this focus planet")


                if len(focus_slots) < _MAX_FOCUS:
                    add_cb = ui.checkbox("+ Another Focus Planet", value=False)

                    def _on_add(e):
                        if e.value:
                            slots = list(state.get("focus_planets", []))
                            slots.append(_PLACEHOLDER)
                            state["focus_planets"] = slots
                            _rebuild_selectors()
                            _rebuild_scan_ui()

                    add_cb.on_value_change(_on_add)

        # ── Event handlers ────────────────────────────────────────────────

        def _on_parent_shape(e):
            state["focus_show_parent_shape"] = e.value
            rerender_active_tab()

        def _on_full_circuit(e):
            state["focus_show_full_circuit"] = e.value
            rerender_active_tab()

        def _on_scan(e):
            state["focus_scan_connections"] = e.value
            if e.value and len(_active_focus_planets(state)) >= 2:
                results_display.visible = True
                _populate_scan_results()
            else:
                results_display.visible = False

        parent_shape_cb.on_value_change(_on_parent_shape)
        full_circuit_cb.on_value_change(_on_full_circuit)
        scan_cb.on_value_change(_on_scan)

        def _rerender_focus_chart():
            """Redraw the Focus chart pane."""
            state["selected_planets"] = _active_focus_planets(state)

            chart_obj = get_chart_object(state)
            if chart_obj is None:
                focus_chart_container.clear()
                with focus_chart_container:
                    ui.label(
                        "Calculate or load a chart to view it here."
                    ).classes("text-body2 text-grey q-pa-md")
                return

            if state.get("interactive_chart"):
                d3_data = serialize_chart_for_d3("Focus", state)
                display_d3_chart_in(focus_chart_container, d3_data, state, _form)
            else:
                png = render_chart_png("Focus", state)
                display_chart_in(focus_chart_container, png, state, _form)

        # ── Initial builds ────────────────────────────────────────────────
        _rebuild_selectors()
        _rerender_focus_chart()

    return {
        "focus_chart_container": focus_chart_container,
        "refresh_focus_tab": _rerender_focus_chart,
    }

