"""Circuits tab — circuit/shape/singleton toggles, Show/Hide All, compass."""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from nicegui import ui

from src.core.static_data import SHAPE_NODE_COUNTS
from src.nicegui_state import get_chart_object, get_chart_2_object

_log = logging.getLogger(__name__)


def build(
    state: dict,
    _form: dict,
    *,
    rerender_active_tab: Callable,
    rerender_circuits_chart_only: Callable,
    on_transit_toggle: Callable,
) -> dict[str, Any]:
    """Build the Circuits tab panel contents.

    Returns
    -------
    dict with keys:
        ``cir_chart_container`` – ui.column for chart rendering
        ``cir_submode_row`` – ui.row for Combined/Connected radio
        ``build_circuit_toggles`` – callable to rebuild toggle checkboxes
    """
    with ui.row().classes("w-full items-center justify-between q-mb-sm"):
        cir_compass_cb = ui.checkbox(
            "Compass Rose", value=state.get("compass", True)
        )
        cir_transit_cb = ui.checkbox(
            "🌐 Transits", value=state.get("transit_mode", False)
        )

    cir_transit_cb.on_value_change(on_transit_toggle)

    # Circuit submode (visible only in biwheel mode)
    cir_submode_row = ui.row().classes("gap-2 q-mb-sm")
    with cir_submode_row:
        cir_submode_radio = ui.radio(
            ["Combined", "Connected"],
            value=state.get("circuit_submode", "Combined"),
        ).props("inline dense")
    cir_submode_row.set_visibility(False)

    def _on_cir_submode_change(e):
        """Handle circuit sub-mode radio change."""
        state["circuit_submode"] = e.value
        rerender_active_tab()

    cir_submode_radio.on_value_change(_on_cir_submode_change)

    with ui.row().classes("gap-2 q-mb-sm"):
        show_all_btn = ui.button("Show All", icon="visibility").props("outline size=sm")
        hide_all_btn = ui.button("Hide All", icon="visibility_off").props("outline size=sm")

    cir_patterns_container = ui.column().classes("w-full")
    cir_singletons_container = ui.column().classes("w-full q-mt-sm")
    cir_chart_container = ui.column().classes("w-full items-center q-mt-sm")

    # ── Toggle handlers (defined before _build_circuit_toggles) ────────
    def _on_pattern_toggle(idx, e):
        """Toggle visibility of a circuit pattern by index."""
        pt = dict(state.get("pattern_toggles", {}))
        pt[str(idx)] = e.value
        state["pattern_toggles"] = pt
        is_bw = bool(
            (state.get("synastry_mode") or state.get("transit_mode"))
            and state.get("last_chart_2_json")
        )
        if is_bw and state.get("circuit_submode") == "Connected":
            _build_circuit_toggles()
        rerender_circuits_chart_only()

    def _on_shape_toggle(sid, e):
        """Toggle visibility of a shape overlay by ID."""
        st_toggles = dict(state.get("shape_toggles", {}))
        st_toggles[sid] = e.value
        state["shape_toggles"] = st_toggles
        is_bw = bool(
            (state.get("synastry_mode") or state.get("transit_mode"))
            and state.get("last_chart_2_json")
        )
        if is_bw and state.get("circuit_submode") == "Connected":
            _build_circuit_toggles()
        rerender_circuits_chart_only()

    def _on_singleton_toggle(planet, e):
        """Toggle the singleton dot for a planet."""
        sg = dict(state.get("singleton_toggles", {}))
        sg[planet] = e.value
        state["singleton_toggles"] = sg
        rerender_circuits_chart_only()

    def _on_cc_shape_toggle(cc_key, e):
        """Toggle a connected-circuit shape overlay."""
        cc = dict(state.get("cc_shape_toggles", {}))
        cc[cc_key] = e.value
        state["cc_shape_toggles"] = cc
        rerender_circuits_chart_only()

    # ── Connected-circuits helper ──────────────────────────────────────
    def _get_biwheel_connected_data():
        """Compute connected-circuit data for biwheel mode."""
        from src.core.models_v2 import static_db as _sdb
        _ASP = {k: v for k, v in _sdb.ASPECTS.items()
                if v.get("aspect_type") in ("Major", "Minor")}
        chart_obj = get_chart_object(state)
        chart_2_obj = get_chart_2_object(state)
        if chart_obj is None or chart_2_obj is None:
            return {}, []

        pos_inner = getattr(chart_obj, "positions", None) or {}
        pos_outer = getattr(chart_2_obj, "positions", None) or {}
        patterns_1 = getattr(chart_obj, "aspect_groups", None) or []
        shapes_2 = getattr(chart_2_obj, "shapes", None) or []

        edges_inter: list = []
        for ep1, d1 in pos_inner.items():
            for ep2, d2 in pos_outer.items():
                angle = abs(d1 - d2) % 360
                if angle > 180:
                    angle = 360 - angle
                for asp_name, asp_data in _ASP.items():
                    if abs(angle - asp_data["angle"]) <= asp_data["orb"]:
                        edges_inter.append((ep1, ep2, asp_name))
                        break

        circuit_connected_shapes2: dict = {}
        for ci, component in enumerate(patterns_1):
            comp_set = set(component)
            connected_c2_planets = {ep2 for (ep1, ep2, _) in edges_inter if ep1 in comp_set}
            linked_shapes = []
            for sh in shapes_2:
                sh_members = sh.get("members", []) if isinstance(sh, dict) else getattr(sh, "members", [])
                if set(sh_members) & connected_c2_planets:
                    linked_shapes.append(sh)
            covered = set()
            for sh in linked_shapes:
                sh_members = sh.get("members", []) if isinstance(sh, dict) else getattr(sh, "members", [])
                covered.update(sh_members)
            for planet in sorted(connected_c2_planets - covered):
                linked_shapes.append({
                    "type": "Single object",
                    "members": [planet],
                    "id": f"singleton_{ci}_{planet}",
                })
            if linked_shapes:
                circuit_connected_shapes2[ci] = linked_shapes

        return circuit_connected_shapes2, edges_inter

    # ── Main toggle builder ────────────────────────────────────────────
    def _build_circuit_toggles():
        """Build the circuit/pattern toggle UI panel."""
        from src.core.models_v2 import static_db as _sdb2
        _GLYPHS = _sdb2.GLYPHS

        chart_obj = get_chart_object(state)
        if chart_obj is None:
            cir_patterns_container.clear()
            with cir_patterns_container:
                ui.label(
                    "Calculate or load a chart to view circuits here."
                ).classes("text-body2 text-grey q-pa-md")
            cir_singletons_container.clear()
            return

        want_glyphs = state.get("label_style", "glyph") == "glyph"

        def _fmt(name: str) -> str:
            """Format an object name as a glyph or plain text."""
            if want_glyphs:
                return _GLYPHS.get(name, name)
            return name

        def _fmt_list(names) -> str:
            """Join a list of names using glyph-or-text formatting."""
            return ", ".join(_fmt(n) for n in names)

        is_biwheel = bool(
            (state.get("synastry_mode") or state.get("transit_mode"))
            and state.get("last_chart_2_json")
        )
        chart1_name = state.get("current_profile") or "Chart 1"
        chart2_name = "Transits" if state.get("transit_mode") else "Chart 2"
        submode = state.get("circuit_submode", "Combined") if is_biwheel else None

        # ==============================================================
        # COMBINED CIRCUITS (biwheel)
        # ==============================================================
        if is_biwheel and submode == "Combined":
            from src.chart_adapter import compute_combined_circuits
            chart_2_obj = get_chart_2_object(state)
            if chart_2_obj is None:
                cir_patterns_container.clear()
                cir_singletons_container.clear()
                return
            combined = compute_combined_circuits(chart_obj, chart_2_obj)
            shapes_combined = combined.get("shapes_combined", [])
            singleton_map = combined.get("singleton_map_combined", {})

            shapes_by_type: dict = {}
            for sh in shapes_combined:
                s_type = sh.get("type", "Shape") if isinstance(sh, dict) else getattr(sh, "shape_type", "Shape")
                shapes_by_type.setdefault(s_type, []).append(sh)

            sorted_types = sorted(
                shapes_by_type.keys(),
                key=lambda t: (-SHAPE_NODE_COUNTS.get(t, 1), t),
            )

            cir_patterns_container.clear()
            with cir_patterns_container:
                if sorted_types:
                    ui.label("Combined Shapes").classes("text-subtitle2 q-mb-xs")
                    half = (len(sorted_types) + 1) // 2
                    with ui.row().classes("w-full gap-4 items-start"):
                        for col_types in (sorted_types[:half], sorted_types[half:]):
                            with ui.column().classes("flex-1"):
                                for s_type in col_types:
                                    type_shapes = shapes_by_type[s_type]
                                    with ui.expansion(
                                        f"{s_type} – {len(type_shapes)} found"
                                    ).classes("w-full q-mb-xs"):
                                        for sh in type_shapes:
                                            sid = sh.get("id", "") if isinstance(sh, dict) else getattr(sh, "shape_id", "")
                                            s_members = sh.get("members", []) if isinstance(sh, dict) else getattr(sh, "members", [])
                                            s_on = state.get("shape_toggles", {}).get(str(sid), False)
                                            m1 = [m for m in s_members if not str(m).endswith("_2")]
                                            m2 = [str(m)[:-2] for m in s_members if str(m).endswith("_2")]
                                            parts = f"{chart1_name}: {_fmt_list(m1)}"
                                            if m2:
                                                parts += f"; {chart2_name}: {_fmt_list(m2)}"
                                            scb = ui.checkbox(parts, value=s_on)
                                            scb.on_value_change(functools.partial(_on_shape_toggle, str(sid)))
                else:
                    ui.label("No shapes detected in combined charts.").classes("text-body2 text-grey q-pa-md")

            cir_singletons_container.clear()
            with cir_singletons_container:
                if singleton_map:
                    ui.label("Singletons").classes("text-subtitle2 q-mb-xs")
                    with ui.row().classes("gap-4 flex-wrap"):
                        for planet in sorted(singleton_map.keys()):
                            s_on = state.get("singleton_toggles", {}).get(planet, False)
                            lbl = _fmt(planet.replace("_2", "") if planet.endswith("_2") else planet)
                            if planet.endswith("_2"):
                                lbl = f"{lbl} ({chart2_name})"
                            cb = ui.checkbox(lbl, value=s_on)
                            cb.on_value_change(functools.partial(_on_singleton_toggle, planet))
            return  # done with Combined mode

        # ==============================================================
        # SINGLE CHART or CONNECTED CIRCUITS
        # ==============================================================
        patterns = getattr(chart_obj, "aspect_groups", None) or []
        singleton_map = getattr(chart_obj, "singleton_map", None) or {}
        shapes = getattr(chart_obj, "shapes", None) or []

        cc_shapes2 = {}
        cc_edges_inter = []
        if is_biwheel and submode == "Connected":
            cc_shapes2, cc_edges_inter = _get_biwheel_connected_data()
            state["_cc_shapes2"] = cc_shapes2
            state["_cc_edges_inter"] = cc_edges_inter

        def _render_one_circuit(idx):
            """Render toggle controls and info for a single circuit."""
            component = patterns[idx]
            pat_on = state.get("pattern_toggles", {}).get(str(idx), False)

            circuit_name_key = f"circuit_name_{idx}"
            circuit_names = state.get("circuit_names", {})
            circuit_title = circuit_names.get(circuit_name_key, f"Circuit {idx + 1}")
            members_label = _fmt_list(component)

            with ui.card().classes("w-full q-mb-sm").props("bordered"):
                cb = ui.checkbox(circuit_title, value=pat_on)
                cb.on_value_change(functools.partial(_on_pattern_toggle, idx))

                with ui.expansion(members_label).classes("w-full"):
                    name_input = ui.input(
                        "Circuit name",
                        value=circuit_title,
                    ).classes("q-mb-xs").props("dense")

                    def _on_name_change(e, _key=circuit_name_key):
                        """Store the user's custom circuit name."""
                        state.setdefault("circuit_names", {})[_key] = e.value
                    name_input.on("blur", _on_name_change)

                    parent_shapes = [s for s in shapes if s.get("parent") == idx]
                    if parent_shapes:
                        ui.label("Sub-shapes:").classes("text-caption text-bold q-mt-xs")
                        for s in parent_shapes:
                            sid = s.get("id", "")
                            s_type = s.get("type", "Shape")
                            s_members = s.get("members", [])
                            s_on = state.get("shape_toggles", {}).get(str(sid), False)
                            shape_label = f"{s_type}: {_fmt_list(s_members)}"
                            scb = ui.checkbox(shape_label, value=s_on)
                            scb.on_value_change(functools.partial(_on_shape_toggle, str(sid)))

                    # Connected Circuits: Chart 2 connections
                    if is_biwheel and submode == "Connected" and idx in cc_shapes2:
                        any_shape_on = any(
                            state.get("shape_toggles", {}).get(str(s.get("id", "")), False)
                            for s in parent_shapes
                        )
                        if pat_on or any_shape_on:
                            cc2_items = cc_shapes2[idx]

                            if not pat_on and any_shape_on:
                                active_sh1_members = set()
                                for s in parent_shapes:
                                    if state.get("shape_toggles", {}).get(str(s.get("id", "")), False):
                                        active_sh1_members.update(s.get("members", []))
                                connected_to_active = {
                                    ep2 for (ep1, ep2, _) in cc_edges_inter
                                    if ep1 in active_sh1_members
                                }
                                cc2_items = [
                                    sh2 for sh2 in cc2_items
                                    if set(
                                        sh2.get("members", []) if isinstance(sh2, dict)
                                        else getattr(sh2, "members", [])
                                    ) & connected_to_active
                                ]

                            if cc2_items:
                                ui.label(f"Connected in {chart2_name}:").classes(
                                    "text-caption text-bold q-mt-sm"
                                )
                                for sh2 in cc2_items:
                                    sh2_type = sh2.get("type", "Shape") if isinstance(sh2, dict) else getattr(sh2, "shape_type", "Shape")
                                    sh2_members = sh2.get("members", []) if isinstance(sh2, dict) else getattr(sh2, "members", [])
                                    sh2_id = sh2.get("id", f"x_{idx}") if isinstance(sh2, dict) else getattr(sh2, "shape_id", f"x_{idx}")
                                    cc_key = f"cc_shape_{idx}_{sh2_id}"
                                    cc_on = state.get("cc_shape_toggles", {}).get(cc_key, False)
                                    cc_label = f"{sh2_type}: {_fmt_list(sh2_members)}"
                                    cc_cb = ui.checkbox(cc_label, value=cc_on)
                                    cc_cb.on_value_change(functools.partial(_on_cc_shape_toggle, cc_key))

        # Pattern checkboxes (two-column layout)
        cir_patterns_container.clear()
        with cir_patterns_container:
            if patterns:
                mode_label = "Connected Circuits" if (is_biwheel and submode == "Connected") else "Circuits"
                ui.label(mode_label).classes("text-subtitle2 q-mb-xs")
                half = (len(patterns) + 1) // 2
                with ui.row().classes("w-full gap-4 items-start"):
                    with ui.column().classes("flex-1"):
                        for idx in range(half):
                            _render_one_circuit(idx)
                    with ui.column().classes("flex-1"):
                        for idx in range(half, len(patterns)):
                            _render_one_circuit(idx)

        # Singleton checkboxes
        cir_singletons_container.clear()
        with cir_singletons_container:
            if singleton_map:
                ui.label("Singletons").classes("text-subtitle2 q-mb-xs")
                with ui.row().classes("gap-4 flex-wrap"):
                    for planet in sorted(singleton_map.keys()):
                        s_on = state.get("singleton_toggles", {}).get(planet, False)
                        label = _fmt(planet)
                        cb = ui.checkbox(label, value=s_on)
                        cb.on_value_change(
                            functools.partial(_on_singleton_toggle, planet)
                        )

    # ── Show All / Hide All handlers ───────────────────────────────────
    def _on_show_all():
        """Enable all circuit, shape, and singleton toggles."""
        chart_obj = get_chart_object(state)
        if chart_obj is None:
            return
        is_bw = bool(
            (state.get("synastry_mode") or state.get("transit_mode"))
            and state.get("last_chart_2_json")
        )
        submode = state.get("circuit_submode", "Combined") if is_bw else None

        if is_bw and submode == "Combined":
            from src.chart_adapter import compute_combined_circuits
            chart_2_obj = get_chart_2_object(state)
            if chart_2_obj:
                combined = compute_combined_circuits(chart_obj, chart_2_obj)
                shapes_c = combined.get("shapes_combined", [])
                singleton_map_c = combined.get("singleton_map_combined", {})
                state["shape_toggles"] = {
                    str(sh.get("id", "") if isinstance(sh, dict) else getattr(sh, "shape_id", "")): True
                    for sh in shapes_c
                }
                state["singleton_toggles"] = {p: True for p in singleton_map_c}
        elif is_bw and submode == "Connected":
            patterns = getattr(chart_obj, "aspect_groups", None) or []
            singleton_map = getattr(chart_obj, "singleton_map", None) or {}
            state["pattern_toggles"] = {str(i): True for i in range(len(patterns))}
            state["singleton_toggles"] = {p: True for p in singleton_map}
            cc_shapes2, _ = _get_biwheel_connected_data()
            cc_all = {}
            for ci, items in cc_shapes2.items():
                for sh2 in items:
                    sh2_id = sh2.get("id", "") if isinstance(sh2, dict) else getattr(sh2, "shape_id", "")
                    cc_all[f"cc_shape_{ci}_{sh2_id}"] = True
            state["cc_shape_toggles"] = cc_all
        else:
            patterns = getattr(chart_obj, "aspect_groups", None) or []
            singleton_map = getattr(chart_obj, "singleton_map", None) or {}
            state["pattern_toggles"] = {str(i): True for i in range(len(patterns))}
            state["singleton_toggles"] = {p: True for p in singleton_map}

        _build_circuit_toggles()
        rerender_circuits_chart_only()

    def _on_hide_all():
        """Disable all circuit, shape, and singleton toggles."""
        state["pattern_toggles"] = {}
        state["singleton_toggles"] = {}
        state["shape_toggles"] = {}
        state["cc_shape_toggles"] = {}
        _build_circuit_toggles()
        rerender_circuits_chart_only()

    show_all_btn.on_click(_on_show_all)
    hide_all_btn.on_click(_on_hide_all)

    def _on_cir_compass_change(e):
        """Toggle the compass overlay in circuit view."""
        state["compass"] = e.value
        rerender_active_tab()

    cir_compass_cb.on_value_change(_on_cir_compass_change)

    return {
        "cir_chart_container": cir_chart_container,
        "cir_submode_row": cir_submode_row,
        "build_circuit_toggles": _build_circuit_toggles,
    }
