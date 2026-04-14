"""Chart rendering / display helpers extracted from app.main_page().

All functions receive explicit ``state`` / ``form`` dicts and UI container
references instead of closing over outer-scope variables.
"""
from __future__ import annotations

import base64
import json
import logging
import time
from typing import Any, Optional

from nicegui import ui

from src.core.static_data import STANDARD_BASE_BODIES
from src.nicegui_state import get_chart_object, get_chart_2_object

_log = logging.getLogger(__name__)


# ── pure-data helpers (no UI) ─────────────────────────────────────────────

def render_chart_png(mode: str, state: dict) -> Optional[bytes]:
    """Render the current chart as PNG bytes in the given mode.

    *mode*: ``"Standard Chart"`` or ``"Circuits"``.
    Handles both single-chart and biwheel rendering.
    """
    from src.chart_adapter import (
        render_chart_image, render_biwheel_image,
        RenderToggles, ChartResult,
        compute_combined_circuits, compute_inter_chart_aspects,
    )

    chart_obj = get_chart_object(state)
    if chart_obj is None:
        return None

    # Check for biwheel mode
    is_biwheel = (
        (state.get("synastry_mode") or state.get("transit_mode"))
        and state.get("last_chart_2_json") is not None
    )
    chart_2_obj = get_chart_2_object(state) if is_biwheel else None
    is_biwheel = is_biwheel and chart_2_obj is not None

    # Build toggles from state
    toggles = RenderToggles(
        compass_inner=state.get("compass", True),
        chart_mode=mode,
        pattern_toggles={int(k): v for k, v in state.get("pattern_toggles", {}).items()},
        shape_toggles=state.get("shape_toggles", {}),
        singleton_toggles=state.get("singleton_toggles", {}),
        aspect_toggles=state.get("aspect_toggles", {}),
        harmonic_toggles=state.get("harmonic_toggles", {}),
        label_style=state.get("label_style", "glyph"),
        dark_mode=state.get("dark_mode", False),
        house_system=(state.get("house_system", "placidus") or "placidus").lower(),
        synastry_inter=state.get("synastry_inter", True),
        synastry_chart1=state.get("synastry_chart1", False),
        synastry_chart2=state.get("synastry_chart2", False),
    )

    if is_biwheel:
        try:
            combined_data = None

            if mode == "Circuits":
                submode = state.get("circuit_submode", "Combined")
                if submode == "Combined":
                    combined_data = compute_combined_circuits(chart_obj, chart_2_obj)
                    return render_biwheel_image(
                        chart_obj,
                        chart_2_obj,
                        toggles=toggles,
                        combined_data=combined_data,
                        inter_chart_aspects=None,
                    )
                elif submode == "Connected":
                    import matplotlib
                    matplotlib.use("Agg")
                    import matplotlib.pyplot as plt
                    from src.rendering.drawing_v2 import render_biwheel_connected_circuits

                    pos_1 = getattr(chart_obj, "positions", None) or {}
                    pos_2 = getattr(chart_2_obj, "positions", None) or {}
                    patterns_1 = getattr(chart_obj, "aspect_groups", None) or []
                    shapes_1 = getattr(chart_obj, "shapes", None) or []
                    shapes_2_list = getattr(chart_2_obj, "shapes", None) or []
                    major_edges_1 = getattr(chart_obj, "major_edges_all", None) or []
                    singleton_map_1 = getattr(chart_obj, "singleton_map", None) or {}
                    filaments_1 = getattr(chart_obj, "filaments", None) or []

                    shape_toggles_by_parent = {}
                    for sh in shapes_1:
                        s_id = sh.get("id", "") if isinstance(sh, dict) else getattr(sh, "shape_id", "")
                        shape_toggles_by_parent[str(s_id)] = state.get("shape_toggles", {}).get(str(s_id), False)

                    pattern_toggles_list = [
                        state.get("pattern_toggles", {}).get(str(i), False)
                        for i in range(len(patterns_1))
                    ]
                    pattern_labels = [f"Circuit {i+1}" for i in range(len(patterns_1))]
                    singleton_toggles_dict = {
                        p: state.get("singleton_toggles", {}).get(p, False)
                        for p in singleton_map_1
                    }

                    cc_shapes2 = state.get("_cc_shapes2", {})
                    cc_edges_inter = state.get("_cc_edges_inter", [])
                    cc_shapes2_int = {int(k): v for k, v in cc_shapes2.items()}

                    rr = render_biwheel_connected_circuits(
                        chart_obj,
                        chart_2_obj,
                        pos_1=pos_1,
                        pos_2=pos_2,
                        patterns=patterns_1,
                        shapes=shapes_1,
                        shapes_2=shapes_2_list,
                        circuit_connected_shapes2=cc_shapes2_int,
                        edges_inter_chart=cc_edges_inter,
                        major_edges_all=major_edges_1,
                        pattern_labels=pattern_labels,
                        toggles=pattern_toggles_list,
                        singleton_map=singleton_map_1,
                        singleton_toggles=singleton_toggles_dict,
                        shape_toggles_by_parent=shape_toggles_by_parent,
                        filaments=filaments_1,
                        house_system=toggles.house_system,
                        dark_mode=toggles.dark_mode,
                        label_style=toggles.label_style,
                        figsize=toggles.figsize,
                        dpi=toggles.dpi,
                        compass_inner=toggles.compass_inner,
                        cc_shape_toggles=state.get("cc_shape_toggles", {}),
                    )
                    import io as _io
                    buf = _io.BytesIO()
                    try:
                        rr.fig.savefig(
                            buf, format="png", bbox_inches="tight",
                            facecolor=rr.fig.get_facecolor(), edgecolor="none",
                        )
                        buf.seek(0)
                        return buf.read()
                    finally:
                        plt.close(rr.fig)
            else:
                # Standard biwheel
                inter_aspects = compute_inter_chart_aspects(chart_obj, chart_2_obj)
                return render_biwheel_image(
                    chart_obj,
                    chart_2_obj,
                    toggles=toggles,
                    combined_data=None,
                    inter_chart_aspects=inter_aspects,
                )
        except Exception:
            _log.exception("Biwheel render failed")
            return None

    # Single-chart path
    result = ChartResult(chart=chart_obj)
    result.positions = getattr(chart_obj, "positions", {}) or {}
    result.patterns = getattr(chart_obj, "aspect_groups", None) or []
    result.shapes = getattr(chart_obj, "shapes", None) or []
    result.singleton_map = getattr(chart_obj, "singleton_map", None) or {}
    result.filaments = getattr(chart_obj, "filaments", None) or []
    result.major_edges_all = getattr(chart_obj, "major_edges_all", None) or []
    result.edges_major = getattr(chart_obj, "edges_major", None) or []
    result.edges_minor = getattr(chart_obj, "edges_minor", None) or []
    result.edges_harmonic = getattr(chart_obj, "edges_harmonic", None) or []

    try:
        return render_chart_image(result, toggles)
    except Exception:
        _log.exception("Chart render failed")
        return None


def serialize_chart_for_d3(mode: str, state: dict) -> Optional[dict]:
    """Serialize the current chart to a JSON-safe dict for the D3 renderer.

    *mode*: ``"Standard Chart"`` or ``"Circuits"``.
    """
    from src.rendering.chart_serializer import (
        serialize_chart_for_rendering,
        serialize_biwheel_for_rendering,
    )

    chart_obj = get_chart_object(state)
    if chart_obj is None:
        return None

    is_biwheel = (
        (state.get("synastry_mode") or state.get("transit_mode"))
        and state.get("last_chart_2_json") is not None
    )
    chart_2_obj = get_chart_2_object(state) if is_biwheel else None
    is_biwheel = is_biwheel and chart_2_obj is not None

    hs = (state.get("house_system", "placidus") or "placidus").lower()
    dark = state.get("dark_mode", False)
    label = state.get("label_style", "glyph")
    compass = state.get("compass", True)

    if mode == "Circuits":
        patterns = getattr(chart_obj, "aspect_groups", None) or []
        shapes = getattr(chart_obj, "shapes", None) or []
        singleton_map = getattr(chart_obj, "singleton_map", None) or {}
        filaments = getattr(chart_obj, "filaments", None) or []
        edges_major = getattr(chart_obj, "edges_major", None) or []
        edges_minor = getattr(chart_obj, "edges_minor", None) or []

        pattern_toggles = {int(k): v for k, v in state.get("pattern_toggles", {}).items()}
        shape_toggles = state.get("shape_toggles", {})
        singleton_toggles = state.get("singleton_toggles", {})

        visible = set()
        for i, group in enumerate(patterns):
            if pattern_toggles.get(i, False):
                visible.update(group)

        for planet, _grp in singleton_map.items():
            if singleton_toggles.get(planet, False):
                visible.add(planet)

        if visible:
            for angle in ("AC", "DC", "MC", "IC"):
                visible.add(angle)

        filtered_major = [e for e in edges_major if e[0] in visible and e[1] in visible] if visible else []
        filtered_minor = [e for e in edges_minor if e[0] in visible and e[1] in visible] if visible else []

        filtered_shapes = []
        for sh in shapes:
            parent = getattr(sh, "parent", None)
            if parent is not None and pattern_toggles.get(parent, False):
                s_id = getattr(sh, "shape_id", "")
                key = str(s_id)
                if shape_toggles.get(key, False):
                    filtered_shapes.append(sh)

        filtered_singleton_map = {
            p: grp for p, grp in singleton_map.items()
            if singleton_toggles.get(p, False)
        }

        filtered_patterns = [
            group for i, group in enumerate(patterns)
            if pattern_toggles.get(i, False)
        ]

        visible_list = list(visible) if visible else None

        try:
            if is_biwheel:
                return serialize_biwheel_for_rendering(
                    chart_obj, chart_2_obj,
                    house_system=hs, dark_mode=dark, label_style=label,
                    compass_on_inner=compass,
                    show_inter=state.get("synastry_inter", True),
                    show_chart1_aspects=state.get("synastry_chart1", False),
                    show_chart2_aspects=state.get("synastry_chart2", False),
                )
            else:
                return serialize_chart_for_rendering(
                    chart_obj,
                    house_system=hs, dark_mode=dark, label_style=label,
                    compass_on=compass,
                    visible_objects=visible_list,
                    edges_major=filtered_major,
                    edges_minor=filtered_minor,
                    shapes=filtered_shapes,
                    singleton_map=filtered_singleton_map,
                    patterns=filtered_patterns,
                )
        except Exception:
            _log.exception("D3 Circuits serialize failed")
            return None

    # Standard Chart mode
    else:
        aspect_bodies = set(STANDARD_BASE_BODIES)
        for body_name, enabled in state.get("aspect_toggles", {}).items():
            if enabled:
                aspect_bodies.add(body_name)

        edges_major = getattr(chart_obj, "edges_major", None) or []
        edges_minor = getattr(chart_obj, "edges_minor", None) or []
        edges_harmonic_raw = getattr(chart_obj, "edges_harmonic", None) or []
        filtered_major = [e for e in edges_major if e[0] in aspect_bodies and e[1] in aspect_bodies]
        filtered_minor = [e for e in edges_minor if e[0] in aspect_bodies and e[1] in aspect_bodies]

        _enabled_h = {n for n, on in state.get("harmonic_toggles", {}).items() if on}
        filtered_harmonic = [
            e for e in edges_harmonic_raw
            if e[0] in aspect_bodies and e[1] in aspect_bodies
            and (isinstance(e[2], dict) and e[2].get("aspect") in _enabled_h)
        ]
        combined_minor = filtered_minor + filtered_harmonic

        try:
            if is_biwheel:
                return serialize_biwheel_for_rendering(
                    chart_obj, chart_2_obj,
                    house_system=hs, dark_mode=dark, label_style=label,
                    compass_on_inner=compass,
                    show_inter=state.get("synastry_inter", True),
                    show_chart1_aspects=state.get("synastry_chart1", False),
                    show_chart2_aspects=state.get("synastry_chart2", False),
                )
            else:
                return serialize_chart_for_rendering(
                    chart_obj,
                    house_system=hs, dark_mode=dark, label_style=label,
                    compass_on=compass,
                    edges_major=filtered_major,
                    edges_minor=combined_minor,
                )
        except Exception:
            _log.exception("D3 Standard Chart serialize failed")
            return None


# ── UI display helpers ────────────────────────────────────────────────────

def render_chart_header(state: dict, form: dict) -> None:
    """Emit the chart-info labels (name, date/time, city, Chart 2) into the current UI context."""
    chart_obj = get_chart_object(state)
    chart_2_obj = get_chart_2_object(state)
    if chart_obj is not None:
        loc_dt = getattr(chart_obj, "display_datetime", None)
        name = state.get("name") or form.get("name") or ""
        city = state.get("city") or form.get("city") or ""
        unknown = getattr(chart_obj, "unknown_time", False)
        if loc_dt:
            time_str = "Unknown time" if unknown else f"{loc_dt:%I:%M %p}"
            info = f"{name} — {loc_dt:%B %d, %Y} {time_str} — {city}"
            ui.label(info).classes("text-subtitle1 text-weight-medium q-mb-sm")
    if chart_2_obj is not None and (
        state.get("synastry_mode") or state.get("transit_mode")
    ):
        c2_name = state.get("chart_2_profile_name") or "Transits"
        c2_dt = getattr(chart_2_obj, "display_datetime", None)
        if c2_dt:
            c2_info = f"Chart 2: {c2_name} — {c2_dt:%B %d, %Y %I:%M %p}"
        else:
            c2_info = f"Chart 2: {c2_name}"
        ui.label(c2_info).classes("text-body2 text-grey-7 q-mb-sm")


def display_chart_in(
    container: Any,
    png_bytes: Optional[bytes],
    state: dict,
    form: dict,
    *,
    show_info: bool = True,
) -> None:
    """Display a chart PNG inside *container*."""
    container.clear()
    if png_bytes is None:
        with container:
            ui.label("No chart computed yet.").classes("text-body2 text-grey q-pa-md")
        return
    with container:
        if show_info:
            render_chart_header(state, form)
        b64 = base64.b64encode(png_bytes).decode()
        ui.html(
            f'<img src="data:image/png;base64,{b64}" '
            f'style="width:100%; max-width:720px; '
            f'image-rendering:auto; display:block; margin:0 auto" />'
        )


def display_d3_chart_in(
    container: Any,
    chart_data: Optional[dict],
    state: dict,
    form: dict,
    *,
    show_info: bool = True,
) -> None:
    """Display the interactive D3 chart inside *container*."""
    container.clear()
    if chart_data is None:
        with container:
            ui.label("No chart computed yet.").classes("text-body2 text-grey q-pa-md")
        return
    with container:
        if show_info:
            render_chart_header(state, form)

        json_b64 = base64.b64encode(json.dumps(chart_data).encode()).decode()
        chart_div_id = f"rosetta-d3-{id(container)}"
        is_biwheel = bool(chart_data.get("config", {}).get("is_biwheel"))
        _cache_bust = int(time.time())

        # Load D3 scripts once per page (idempotent check in JS)
        ui.run_javascript(f'''
            if (!window._rosettaD3ScriptsLoaded) {{
                window._rosettaD3ScriptsLoaded = "loading";
                var scripts = ["/d3chart/d3.v7.min.js", "/d3chart/chart_renderer.js?v={_cache_bust}", "/d3chart/tooltip.js?v={_cache_bust}"];
                var loaded = 0;
                scripts.forEach(function(src) {{
                    var s = document.createElement("script");
                    s.src = src;
                    s.onload = function() {{
                        loaded++;
                        console.log("[Rosetta D3] loaded " + src + " (" + loaded + "/" + scripts.length + ")");
                        if (loaded === scripts.length) {{
                            window._rosettaD3ScriptsLoaded = "ready";
                            console.log("[Rosetta D3] all scripts ready");
                            if (window._rosettaD3RenderPending) {{
                                window._rosettaD3RenderPending();
                                window._rosettaD3RenderPending = null;
                            }}
                        }}
                    }};
                    s.onerror = function() {{ console.error("[Rosetta D3] FAILED to load " + src); }};
                    document.head.appendChild(s);
                }});
            }}
        ''')

        # D3 chart stylesheet
        ui.run_javascript(f'''
            if (!document.getElementById("rosetta-d3-css")) {{
                var link = document.createElement("link");
                link.id = "rosetta-d3-css";
                link.rel = "stylesheet";
                link.href = "/d3chart/styles.css?v={_cache_bust}";
                document.head.appendChild(link);
            }}
        ''')

        ui.html(
            f'<div id="{chart_div_id}" '
            f'style="width:100%; max-width:720px; height:640px; '
            f'display:block; margin:0 auto; overflow:hidden;"></div>'
        )

        render_fn = "biwheel" if is_biwheel else "single"
        ui.run_javascript(f'''
            (function() {{
                var b64 = "{json_b64}";
                var data = JSON.parse(atob(b64));
                function doRender() {{
                    var el = document.getElementById("{chart_div_id}");
                    if (!el) {{
                        console.error("[Rosetta D3] container div not found, retrying...");
                        setTimeout(doRender, 200);
                        return;
                    }}
                    try {{
                        if ("{render_fn}" === "biwheel") {{
                            RosettaChart.renderBiwheel(el, data, 680, 620);
                        }} else {{
                            RosettaChart.render(el, data, 680, 620);
                        }}
                        console.log("[Rosetta D3] chart rendered successfully");
                        try {{
                            if (typeof RosettaTooltip !== "undefined") {{
                                var svg = el.querySelector("svg");
                                if (svg) RosettaTooltip.wire(d3.select(svg), data);
                            }}
                        }} catch(te) {{ console.warn("[Rosetta D3] tooltip wiring:", te); }}
                    }} catch(e) {{
                        console.error("[Rosetta D3] render error:", e);
                        el.innerHTML = '<p style="color:red;padding:1em;">Chart render error: ' + e.message + '</p>';
                    }}
                }}
                if (window._rosettaD3ScriptsLoaded === "ready") {{
                    console.log("[Rosetta D3] scripts already loaded, rendering now");
                    doRender();
                }} else {{
                    console.log("[Rosetta D3] scripts still loading, deferring render");
                    window._rosettaD3RenderPending = doRender;
                }}
            }})();
        ''')


# ── composite helpers (use PageState callbacks) ──────────────────────────

def rerender_circuits_chart_only(state: dict, form: dict, cir_chart_container: Any) -> None:
    """Re-render only the Circuits chart image without rebuilding toggles."""
    chart_obj = get_chart_object(state)
    if chart_obj is None:
        return
    if state.get("interactive_chart"):
        d3_data = serialize_chart_for_d3("Circuits", state)
        display_d3_chart_in(cir_chart_container, d3_data, state, form)
    else:
        png = render_chart_png("Circuits", state)
        display_chart_in(cir_chart_container, png, state, form)


def rerender_active_tab(
    state: dict,
    form: dict,
    *,
    tabs: Any,
    std_chart_container: Any,
    cir_chart_container: Any,
    synastry_aspects_exp: Any,
    cir_submode_row: Any,
    chat_no_chart_notice: Any,
    events_container: Any,
    # late-bound callbacks (from PageState or direct refs)
    rebuild_harmonic_expander,
    build_circuit_toggles,
    render_rulers_graph,
    refresh_specs_tab,
    refresh_drawer,
) -> None:
    """Re-render chart in the currently active tab with current toggles."""
    _NO_CHART_MSG = "Calculate or load a chart to view it here."
    active = state.get("active_tab", tabs.value)
    if tabs.value != active:
        tabs.value = active
    chart_obj = get_chart_object(state)

    if chart_obj is None:
        if active == "Standard Chart":
            rebuild_harmonic_expander()
            std_chart_container.clear()
            with std_chart_container:
                ui.label(_NO_CHART_MSG).classes("text-body2 text-grey q-pa-md")
        elif active == "Circuits":
            build_circuit_toggles()
            cir_chart_container.clear()
            with cir_chart_container:
                ui.label(_NO_CHART_MSG).classes("text-body2 text-grey q-pa-md")
        elif active == "Rulers":
            render_rulers_graph()
        elif active == "Specs":
            refresh_specs_tab()
        try:
            chat_no_chart_notice.set_visibility(True)
        except Exception:
            pass
        return

    # Update events panel
    refresh_events(state, events_container)

    # Synastry/biwheel UI visibility
    is_biwheel = (
        (state.get("synastry_mode") or state.get("transit_mode"))
        and state.get("last_chart_2_json") is not None
    )
    synastry_aspects_exp.set_visibility(is_biwheel and active == "Standard Chart")
    cir_submode_row.set_visibility(is_biwheel and active == "Circuits")

    if active == "Standard Chart":
        rebuild_harmonic_expander()
        if state.get("interactive_chart"):
            d3_data = serialize_chart_for_d3("Standard Chart", state)
            display_d3_chart_in(std_chart_container, d3_data, state, form)
        else:
            png = render_chart_png("Standard Chart", state)
            display_chart_in(std_chart_container, png, state, form)
    elif active == "Circuits":
        build_circuit_toggles()
        if state.get("interactive_chart"):
            d3_data = serialize_chart_for_d3("Circuits", state)
            display_d3_chart_in(cir_chart_container, d3_data, state, form)
        else:
            png = render_chart_png("Circuits", state)
            display_chart_in(cir_chart_container, png, state, form)
    elif active == "Rulers":
        render_rulers_graph()
    elif active == "Specs":
        refresh_specs_tab()

    refresh_drawer()
    try:
        chat_no_chart_notice.set_visibility(False)
    except Exception:
        pass


def refresh_events(state: dict, events_container: Any) -> None:
    """Update the events panel with nearby events for the current chart."""
    chart_obj = get_chart_object(state)
    if chart_obj is None:
        events_container.content = ""
        return
    try:
        utc_dt = getattr(chart_obj, "utc_datetime", None)
        if utc_dt is None:
            events_container.content = ""
            return
        from src.core.event_lookup_v2 import build_events_html
        html = build_events_html(utc_dt)
        events_container.content = html
    except Exception:
        events_container.content = ""
