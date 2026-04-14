"""Standard Chart tab — aspect/harmonic toggles, compass, synastry groups."""
from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from nicegui import ui

from src.core.static_data import STANDARD_BASE_BODIES
from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)

# Names offered in the "Aspects to Additional Objects" grid.
TOGGLE_ASPECT_NAMES = [
    "North Node", "South Node", "AC", "MC", "Vertex", "Part of Fortune",
    "Ceres", "Pallas", "Juno", "Vesta", "Eris", "Eros", "Psyche",
]


def build(
    state: dict,
    _form: dict,
    *,
    rerender_active_tab: Callable,
    on_transit_toggle: Callable,
) -> dict[str, Any]:
    """Build the Standard Chart tab panel contents.

    Returns
    -------
    dict with keys:
        ``std_chart_container`` – ui.column for chart rendering
        ``synastry_aspects_exp`` – expansion for synastry aspect groups
        ``rebuild_harmonic_expander`` – callable to rebuild harmonic toggles
        ``transit_cb`` – the transit checkbox widget
    """
    with ui.row().classes("w-full items-center justify-between q-mb-sm"):
        std_compass_cb = ui.checkbox(
            "Compass Rose", value=state.get("compass", True)
        )
        transit_cb = ui.checkbox(
            "🌐 Transits", value=state.get("transit_mode", False)
        )

    # --- Additional Aspects expansion ---
    with ui.expansion("Aspects to Additional Objects").classes("w-full q-mt-sm"):
        std_select_all = ui.checkbox("Select All", value=False)
        aspect_cbs: dict[str, ui.checkbox] = {}
        with ui.grid(columns=4).classes("w-full gap-2"):
            for asp_name in TOGGLE_ASPECT_NAMES:
                cb = ui.checkbox(
                    asp_name,
                    value=state.get("aspect_toggles", {}).get(asp_name, False),
                )
                aspect_cbs[asp_name] = cb

        def _on_select_all(e):
            """Toggle all major-aspect checkboxes on or off."""
            at = dict(state.get("aspect_toggles", {}))
            for name, cb in aspect_cbs.items():
                cb.value = e.value
                at[name] = e.value
            state["aspect_toggles"] = at
            rerender_active_tab()

        std_select_all.on_value_change(_on_select_all)

        def _on_aspect_toggle(name, e):
            """Toggle a single major-aspect checkbox."""
            at = dict(state.get("aspect_toggles", {}))
            at[name] = e.value
            state["aspect_toggles"] = at
            rerender_active_tab()

        for name, cb in aspect_cbs.items():
            cb.on_value_change(functools.partial(_on_aspect_toggle, name))

    # --- Additional Minor (Harmonic) Aspects expansion ---
    from src.core.calc_v2 import HARMONIC_BY_NUMBER
    from src.core.models_v2 import static_db as _sd

    _HARMONIC_FAMILY_LABELS = {
        5: "H5 — Quintile Family",
        7: "H7 — Septile Family",
        8: "H8 — Semi-square",
        9: "H9 — Novile Family",
        10: "H10 — Decile Family",
        11: "H11 — Undecile Family",
        24: "H24 — Fine Divisions",
    }

    harm_exp = ui.expansion("Additional Minor Aspects").classes("w-full q-mt-sm")
    harm_exp.set_visibility(False)
    with harm_exp:
        harm_container = ui.column().classes("w-full")

    harmonic_cbs: dict[str, ui.checkbox] = {}
    _harm_select_all_ref: list = []

    def _rebuild_harmonic_expander():
        """Rebuild the harmonic-aspect expander with current toggles."""
        nonlocal harmonic_cbs
        harmonic_cbs = {}
        _harm_select_all_ref.clear()

        chart_obj = get_chart_object(state)
        raw_edges = (getattr(chart_obj, "edges_harmonic", None) or []) if chart_obj else []

        aspect_bodies = set(STANDARD_BASE_BODIES)
        for body_name, enabled in state.get("aspect_toggles", {}).items():
            if enabled:
                aspect_bodies.add(body_name)

        present_aspects: set[str] = set()
        for edge in raw_edges:
            if edge[0] in aspect_bodies and edge[1] in aspect_bodies:
                meta = edge[2] if len(edge) > 2 else {}
                asp = meta.get("aspect") if isinstance(meta, dict) else None
                if asp:
                    present_aspects.add(asp)

        harm_container.clear()
        if not present_aspects:
            harm_exp.set_visibility(False)
            return
        harm_exp.set_visibility(True)

        with harm_container:
            sel_all = ui.checkbox("Select All", value=False)
            _harm_select_all_ref.append(sel_all)
            with ui.row().classes("w-full gap-4"):
                cols = [ui.column().classes("col") for _ in range(4)]

            col_index = 0
            for h_num in sorted(HARMONIC_BY_NUMBER.keys()):
                all_names = HARMONIC_BY_NUMBER[h_num]
                visible = [n for n in all_names if n in present_aspects]
                if not visible:
                    continue
                target_col = cols[col_index % len(cols)]
                col_index += 1
                with target_col:
                    family_label = _HARMONIC_FAMILY_LABELS.get(h_num, f"H{h_num}")
                    h_color = _sd.ASPECTS.get(visible[0], {}).get("color", "grey")
                    ui.label(family_label).classes("text-weight-bold q-mt-sm").style(
                        f"color: {h_color}"
                    )
                    with ui.grid(columns=2).classes("w-full gap-2"):
                        for asp_name in visible:
                            cb = ui.checkbox(
                                asp_name,
                                value=state.get("harmonic_toggles", {}).get(asp_name, False),
                            )
                            harmonic_cbs[asp_name] = cb

            def _on_harm_select_all(e):
                """Toggle all harmonic-aspect checkboxes on or off."""
                ht = dict(state.get("harmonic_toggles", {}))
                for name, cb in harmonic_cbs.items():
                    cb.value = e.value
                    ht[name] = e.value
                state["harmonic_toggles"] = ht
                rerender_active_tab()

            sel_all.on_value_change(_on_harm_select_all)

            def _on_harmonic_toggle(name, e):
                """Toggle a single harmonic-aspect checkbox."""
                ht = dict(state.get("harmonic_toggles", {}))
                ht[name] = e.value
                state["harmonic_toggles"] = ht
                rerender_active_tab()

            for name, cb in harmonic_cbs.items():
                cb.on_value_change(functools.partial(_on_harmonic_toggle, name))

    _rebuild_harmonic_expander()

    std_chart_container = ui.column().classes("w-full items-center")

    # --- Synastry aspect group checkboxes (biwheel only) ---
    synastry_aspects_exp = ui.expansion(
        "Synastry Aspect Groups"
    ).classes("w-full q-mt-sm")
    synastry_aspects_exp.set_visibility(False)

    with synastry_aspects_exp:
        syn_inter_cb = ui.checkbox(
            "Inter-chart aspects",
            value=state.get("synastry_inter", True),
        )
        syn_chart1_cb = ui.checkbox(
            "Chart 1 internal aspects",
            value=state.get("synastry_chart1", False),
        )
        syn_chart2_cb = ui.checkbox(
            "Chart 2 internal aspects",
            value=state.get("synastry_chart2", False),
        )

        def _on_syn_inter(e):
            """Toggle inter-chart aspect visibility."""
            state["synastry_inter"] = e.value
            rerender_active_tab()

        def _on_syn_chart1(e):
            """Toggle chart-1 intra-aspects in synastry mode."""
            state["synastry_chart1"] = e.value
            rerender_active_tab()

        def _on_syn_chart2(e):
            """Toggle chart-2 intra-aspects in synastry mode."""
            state["synastry_chart2"] = e.value
            rerender_active_tab()

        syn_inter_cb.on_value_change(_on_syn_inter)
        syn_chart1_cb.on_value_change(_on_syn_chart1)
        syn_chart2_cb.on_value_change(_on_syn_chart2)

    def _on_std_compass_change(e):
        """Toggle the compass overlay in standard view."""
        state["compass"] = e.value
        rerender_active_tab()

    std_compass_cb.on_value_change(_on_std_compass_change)

    if transit_cb is not None:
        transit_cb.on_value_change(on_transit_toggle)

    return {
        "std_chart_container": std_chart_container,
        "synastry_aspects_exp": synastry_aspects_exp,
        "rebuild_harmonic_expander": _rebuild_harmonic_expander,
        "transit_cb": transit_cb,
    }
