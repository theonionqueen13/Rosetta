# src/chart_adapter.py
"""
Framework-agnostic adapter for chart computation and rendering.

Wraps the existing calc_v2, patterns_v2, and drawing_v2 modules so that
both the NiceGUI and Streamlit entry points can compute and render charts
without touching st.session_state or any UI framework directly.

Usage:
    from src.chart_adapter import ChartInputs, ChartResult, compute_chart, render_chart_image

    inputs = ChartInputs(name="Alice", year=1990, month=6, day=15,
                         hour_24=14, minute=30, city="New York",
                         lat=40.7128, lon=-74.006, tz_name="America/New_York")
    result = compute_chart(inputs)
    png = render_chart_image(result)
"""
from __future__ import annotations

import io
import os
import datetime as dt
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import swisseph as swe


# ---------------------------------------------------------------------------
# Ensure ephemeris path is set  (idempotent)
# ---------------------------------------------------------------------------
_EPHE_PATH = os.environ.get(
    "SE_EPHE_PATH",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ephe")).replace("\\", "/"),
)
os.environ.setdefault("SE_EPHE_PATH", _EPHE_PATH)
swe.set_ephe_path(_EPHE_PATH)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ChartInputs:
    """All the data needed to compute a chart — framework-free."""
    name: str = ""
    year: int = 2000
    month: int = 1
    day: int = 1
    hour_24: int = 12
    minute: int = 0
    city: str = ""
    lat: float = 0.0
    lon: float = 0.0
    tz_name: str = "UTC"
    unknown_time: bool = False
    house_system: str = "placidus"
    gender: Optional[str] = None


@dataclass
class ChartResult:
    """Everything produced by chart computation — framework-free."""
    chart: Any = None                       # AstrologicalChart
    df_positions: Any = None                # pd.DataFrame
    aspect_df: Any = None                   # pd.DataFrame
    plot_data: Dict[str, Any] = field(default_factory=dict)
    edges_major: List[Any] = field(default_factory=list)
    edges_minor: List[Any] = field(default_factory=list)
    patterns: List[List[str]] = field(default_factory=list)
    shapes: List[Dict[str, Any]] = field(default_factory=list)
    singleton_map: Dict[str, Any] = field(default_factory=dict)
    filaments: List[Any] = field(default_factory=list)
    combos: Dict[str, Any] = field(default_factory=dict)
    conj_clusters_rows: List[Any] = field(default_factory=list)
    dispositor_summary_rows: List[Any] = field(default_factory=list)
    dispositor_chains_rows: List[Any] = field(default_factory=list)
    sect: Optional[str] = None
    sect_error: Optional[str] = None
    positions: Dict[str, float] = field(default_factory=dict)
    major_edges_all: List[Any] = field(default_factory=list)
    utc_datetime: Optional[dt.datetime] = None
    local_datetime: Optional[dt.datetime] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Chart computation
# ---------------------------------------------------------------------------

def compute_chart(inputs: ChartInputs) -> ChartResult:
    """Compute a full chart from *inputs*.  Pure data in, pure data out.

    Calls:
      - calc_v2.calculate_chart()       (positions, aspects, house cusps)
      - calc_v2.build_aspect_edges()    (major/minor aspect edges)
      - calc_v2.annotate_chart()        (mutual receptions)
      - calc_v2.chart_sect_from_chart() (sect)
      - calc_v2.build_conjunction_clusters()
      - calc_v2.build_dispositor_tables()
      - patterns_v2.prepare_pattern_inputs / detect_shapes / detect_minor_links_from_chart
      - circuit_sim.simulate_and_attach()
    """
    from calc_v2 import (
        calculate_chart,
        build_aspect_edges,
        annotate_chart,
        chart_sect_from_chart,
        build_conjunction_clusters,
        build_dispositor_tables,
    )
    from patterns_v2 import (
        prepare_pattern_inputs,
        detect_shapes,
        detect_minor_links_from_chart,
        generate_combo_groups,
    )
    from circuit_sim import simulate_and_attach

    result = ChartResult()

    # --- Build local datetime and convert to UTC ---
    try:
        hour = inputs.hour_24
        minute = inputs.minute
        if inputs.unknown_time:
            hour, minute = 12, 0

        local_dt = dt.datetime(inputs.year, inputs.month, inputs.day, hour, minute)
        result.local_datetime = local_dt

        if inputs.unknown_time:
            utc_dt = local_dt  # noon UTC
            tz_offset = 0
            input_is_ut = True
            tz_name_for_calc = None
        else:
            tz = ZoneInfo(inputs.tz_name)
            local_dt_aware = local_dt.replace(tzinfo=tz)
            utc_dt = local_dt_aware.astimezone(dt.timezone.utc).replace(tzinfo=None)
            tz_offset = 0  # we pass UTC directly
            input_is_ut = True
            tz_name_for_calc = inputs.tz_name

        result.utc_datetime = utc_dt
    except Exception as exc:
        result.error = f"Time parsing failed: {exc}"
        return result

    # --- Core calculation ---
    try:
        df_positions, aspect_df, plot_data, chart = calculate_chart(
            year=utc_dt.year,
            month=utc_dt.month,
            day=utc_dt.day,
            hour=utc_dt.hour,
            minute=utc_dt.minute,
            tz_offset=tz_offset,
            lat=inputs.lat,
            lon=inputs.lon,
            input_is_ut=input_is_ut,
            tz_name=tz_name_for_calc,
            house_system=inputs.house_system,
            include_aspects=True,
            unknown_time=inputs.unknown_time,
            display_name=inputs.name,
            city=inputs.city,
            display_datetime=local_dt,
        )
        chart.plot_data = plot_data
        result.chart = chart
        result.df_positions = df_positions
        result.aspect_df = aspect_df
        result.plot_data = plot_data
    except Exception as exc:
        result.error = f"Chart calculation failed: {exc}"
        return result

    # --- Post-processing: aspect edges ---
    try:
        edges_major, edges_minor = build_aspect_edges(chart, compass_rose=False)
        result.edges_major = [tuple(e) for e in edges_major]
        result.edges_minor = [tuple(e) for e in edges_minor]
    except Exception as exc:
        result.error = f"Aspect edge computation failed: {exc}"
        return result

    # --- Annotate mutual receptions ---
    try:
        annotate_chart(chart, edges_major)
    except Exception:
        pass

    # --- Sect ---
    try:
        chart.sect = chart_sect_from_chart(chart)
        chart.sect_error = None
        result.sect = chart.sect
    except Exception as exc:
        chart.sect = None
        chart.sect_error = str(exc)
        result.sect_error = str(exc)

    # --- Conjunction clusters ---
    try:
        clusters_rows, _, _ = build_conjunction_clusters(chart, edges_major)
        chart.conj_clusters_rows = clusters_rows
        result.conj_clusters_rows = clusters_rows
    except Exception:
        pass

    # --- Dispositors ---
    try:
        dispositor_summary_rows, dispositor_chains_rows = build_dispositor_tables(chart)
        result.dispositor_summary_rows = dispositor_summary_rows
        result.dispositor_chains_rows = dispositor_chains_rows
    except Exception:
        pass

    # --- Circuit / shape / singleton detection ---
    try:
        pos_chart, patterns_sets, major_edges_all = prepare_pattern_inputs(
            df_positions, edges_major
        )
        patterns = [sorted(list(s)) for s in patterns_sets]
        shapes = detect_shapes(pos_chart, patterns_sets, major_edges_all)
        filaments, singleton_map = detect_minor_links_from_chart(chart, edges_major)
        combos = generate_combo_groups(filaments)

        result.patterns = patterns
        result.shapes = shapes
        result.singleton_map = singleton_map
        result.filaments = filaments
        result.combos = combos
        result.major_edges_all = major_edges_all
        result.positions = pos_chart

        # Attach to chart object too
        chart.df_positions = df_positions
        chart.aspect_df = aspect_df
        chart.edges_major = result.edges_major
        chart.edges_minor = result.edges_minor
        chart.aspect_groups = patterns
        chart.shapes = shapes
        chart.filaments = filaments
        chart.singleton_map = singleton_map
        chart.combos = combos
        chart.positions = pos_chart
        chart.major_edges_all = major_edges_all
        chart.dispositor_summary_rows = result.dispositor_summary_rows
        chart.dispositor_chains_rows = result.dispositor_chains_rows
        chart.utc_datetime = utc_dt
    except Exception as exc:
        # Circuit detection is non-fatal — the chart is still usable
        result.positions = {}
        import logging
        logging.getLogger(__name__).warning("Circuit detection failed: %s", exc)

    # --- Circuit power simulation ---
    try:
        simulate_and_attach(chart)
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# Transit chart computation
# ---------------------------------------------------------------------------

def compute_transit_chart(
    lat: float,
    lon: float,
    tz_name: str = "UTC",
    city: str = "",
    house_system: str = "placidus",
    transit_utc: Optional[dt.datetime] = None,
) -> ChartResult:
    """Compute a transit chart (current or specified time) at a location.

    This is a lighter version of compute_chart() intended for Chart-2 usage.
    """
    from calc_v2 import (
        calculate_chart,
        build_aspect_edges,
        annotate_chart,
    )
    from patterns_v2 import (
        prepare_pattern_inputs,
        detect_shapes,
    )

    if transit_utc is None:
        transit_utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    elif hasattr(transit_utc, "tzinfo") and transit_utc.tzinfo is not None:
        transit_utc = transit_utc.astimezone(dt.timezone.utc).replace(tzinfo=None)

    result = ChartResult()
    result.utc_datetime = transit_utc
    result.local_datetime = transit_utc  # transit is always UTC-referenced

    try:
        df_positions, aspect_df, plot_data, chart = calculate_chart(
            year=transit_utc.year,
            month=transit_utc.month,
            day=transit_utc.day,
            hour=transit_utc.hour,
            minute=transit_utc.minute,
            tz_offset=0,
            lat=lat,
            lon=lon,
            input_is_ut=True,
            tz_name=tz_name,
            house_system=house_system,
            include_aspects=True,
            unknown_time=False,
            display_name="Transits",
            city=city,
            display_datetime=transit_utc,
        )
        chart.plot_data = plot_data
        result.chart = chart
        result.df_positions = df_positions
        result.aspect_df = aspect_df
        result.plot_data = plot_data
    except Exception as exc:
        result.error = f"Transit chart calculation failed: {exc}"
        return result

    # Aspect edges
    try:
        edges_major, edges_minor = build_aspect_edges(chart, compass_rose=False)
        result.edges_major = [tuple(e) for e in edges_major]
        result.edges_minor = [tuple(e) for e in edges_minor]
    except Exception:
        pass

    # Annotate mutual receptions
    try:
        annotate_chart(chart, edges_major)
    except Exception:
        pass

    # Circuit detection for Chart 2
    try:
        pos_chart2, patterns_sets2, major_edges_all2 = prepare_pattern_inputs(
            df_positions, edges_major
        )
        patterns2 = [sorted(list(s)) for s in patterns_sets2]
        shapes2 = detect_shapes(pos_chart2, patterns_sets2, major_edges_all2)

        chart.df_positions = df_positions
        chart.aspect_df = aspect_df
        chart.edges_major = result.edges_major
        chart.edges_minor = result.edges_minor
        chart.aspect_groups = patterns2
        chart.shapes = shapes2
        chart.positions = pos_chart2
        chart.major_edges_all = major_edges_all2
        chart.utc_datetime = transit_utc

        result.patterns = patterns2
        result.shapes = shapes2
        result.positions = pos_chart2
        result.major_edges_all = major_edges_all2
    except Exception:
        result.positions = {}

    return result


# ---------------------------------------------------------------------------
# Combined circuits computation (biwheel)
# ---------------------------------------------------------------------------

def compute_combined_circuits(chart_1, chart_2):
    """Compute combined circuit data for two charts (biwheel).

    Merges positions from both charts (Chart 2 names get '_2' suffix),
    computes all cross-chart aspects, and detects patterns/shapes.

    Returns a dict with keys:
        pos_combined, patterns_combined, shapes_combined,
        singleton_map_combined, combined_edges
    """
    from models_v2 import static_db
    ASPECTS = {k: v for k, v in static_db.ASPECTS.items()
               if v.get("aspect_type") in ("Major", "Minor")}
    from patterns_v2 import connected_components_from_edges, detect_shapes

    pos_1 = {obj.object_name.name: obj.longitude
             for obj in chart_1.objects if obj.object_name}
    pos_2 = {obj.object_name.name: obj.longitude
             for obj in chart_2.objects if obj.object_name}

    # Merge positions: Chart 1 names plain, Chart 2 names with "_2" suffix
    pos_combined = dict(pos_1)
    for name, deg in pos_2.items():
        pos_combined[f"{name}_2"] = deg

    # Compute ALL pairwise aspects in the merged chart
    bodies = list(pos_combined.keys())
    combined_edges = []
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            p1, p2 = bodies[i], bodies[j]
            ang = abs(pos_combined[p1] - pos_combined[p2]) % 360
            if ang > 180:
                ang = 360 - ang
            for aname, adata in ASPECTS.items():
                if abs(ang - adata["angle"]) <= adata["orb"]:
                    combined_edges.append(((p1, p2), aname))
                    break

    # Detect connected components (combined circuits)
    patterns = connected_components_from_edges(bodies, combined_edges)
    shapes = detect_shapes(pos_combined, patterns, combined_edges)

    # Singletons: bodies not in any aspect
    connected_objs = set()
    for (p1, p2), _ in combined_edges:
        connected_objs.add(p1)
        connected_objs.add(p2)
    singleton_map = {n: {"deg": d} for n, d in pos_combined.items()
                     if n not in connected_objs}

    return {
        "pos_combined": pos_combined,
        "patterns_combined": patterns,
        "shapes_combined": shapes,
        "singleton_map_combined": singleton_map,
        "combined_edges": combined_edges,
    }


# ---------------------------------------------------------------------------
# Inter-chart aspect computation (Standard biwheel)
# ---------------------------------------------------------------------------

def compute_inter_chart_aspects(chart_1, chart_2):
    """Compute inter-chart aspects between two charts.

    Returns list of (planet1, planet2, aspect_name) tuples.
    """
    from models_v2 import static_db
    ASPECTS = {k: v for k, v in static_db.ASPECTS.items()
               if v.get("aspect_type") in ("Major", "Minor")}

    pos_1 = {obj.object_name.name: obj.longitude
             for obj in chart_1.objects if obj.object_name}
    pos_2 = {obj.object_name.name: obj.longitude
             for obj in chart_2.objects if obj.object_name}

    inter_aspects = []
    for p1, d1 in pos_1.items():
        for p2, d2 in pos_2.items():
            angle = abs(d1 - d2) % 360
            if angle > 180:
                angle = 360 - angle
            for aspect_name, aspect_data in ASPECTS.items():
                if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
                    inter_aspects.append((p1, p2, aspect_name))
                    break

    return inter_aspects


# ---------------------------------------------------------------------------
# Chart rendering → PNG bytes
# ---------------------------------------------------------------------------

@dataclass
class RenderToggles:
    """Toggle state for chart rendering — framework-free."""
    compass_inner: bool = True
    compass_outer: bool = True
    chart_mode: str = "Circuits"           # "Standard Chart" or "Circuits"
    # Circuit-mode toggles (all default OFF per plan)
    pattern_toggles: Dict[int, bool] = field(default_factory=dict)
    shape_toggles: Dict[str, bool] = field(default_factory=dict)
    singleton_toggles: Dict[str, bool] = field(default_factory=dict)
    # Standard-mode additional aspect body toggles (all default OFF)
    aspect_toggles: Dict[str, bool] = field(default_factory=dict)
    # Display
    label_style: str = "glyph"             # "glyph" or "text"
    dark_mode: bool = False
    house_system: str = "placidus"
    # Synastry aspect groups (biwheel only)
    synastry_inter: bool = True
    synastry_chart1: bool = False
    synastry_chart2: bool = False
    figsize: tuple = (8.0, 8.0)
    dpi: int = 192


# Bodies included in Standard Chart mode by default (matches PLANETS_PLUS)
_STANDARD_BASE_BODIES = {
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "Black Moon Lilith (Mean)", "Chiron",
}


def render_chart_image(
    chart_result: ChartResult,
    toggles: Optional[RenderToggles] = None,
) -> bytes:
    """Render a chart wheel as a PNG byte buffer.

    Returns raw PNG bytes that can be displayed via ui.image() or st.image().
    """
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend
    import matplotlib.pyplot as plt

    from drawing_v2 import render_chart as _render_chart_standard
    from drawing_v2 import render_chart_with_shapes as _render_chart_circuits

    if toggles is None:
        toggles = RenderToggles()

    chart = chart_result.chart
    if chart is None:
        raise ValueError("ChartResult has no chart object — compute_chart() may have failed")

    house_system = toggles.house_system

    if toggles.chart_mode == "Circuits":
        # Circuit-mode rendering
        pattern_toggles_list = [
            toggles.pattern_toggles.get(i, False)
            for i in range(len(chart_result.patterns))
        ]
        pattern_labels = [
            f"Circuit {i + 1}"
            for i in range(len(chart_result.patterns))
        ]
        singleton_toggles_dict = {
            planet: toggles.singleton_toggles.get(planet, False)
            for planet in chart_result.singleton_map
        }

        rr = _render_chart_circuits(
            pos=chart_result.positions,
            patterns=chart_result.patterns,
            pattern_labels=pattern_labels,
            toggles=pattern_toggles_list,
            filaments=chart_result.filaments,
            combo_toggles={},
            label_style=toggles.label_style,
            singleton_map=chart_result.singleton_map,
            chart=chart,
            house_system=house_system,
            dark_mode=toggles.dark_mode,
            shapes=chart_result.shapes,
            shape_toggles_by_parent=toggles.shape_toggles,
            singleton_toggles=singleton_toggles_dict,
            major_edges_all=chart_result.major_edges_all,
            figsize=toggles.figsize,
            dpi=toggles.dpi,
            compass_on=toggles.compass_inner,
        )
    else:
        # Standard Chart mode rendering
        # Build the set of "aspect-enabled" bodies:
        # base planets + any Additional Aspects the user toggled ON.
        aspect_bodies = set(_STANDARD_BASE_BODIES)
        for body_name, enabled in toggles.aspect_toggles.items():
            if enabled:
                aspect_bodies.add(body_name)

        # Filter edges: only keep edges where BOTH endpoints are aspect-enabled
        filtered_major = [
            e for e in chart_result.edges_major
            if e[0] in aspect_bodies and e[1] in aspect_bodies
        ]
        filtered_minor = [
            e for e in chart_result.edges_minor
            if e[0] in aspect_bodies and e[1] in aspect_bodies
        ]

        rr = _render_chart_standard(
            chart=chart,
            edges_major=filtered_major,
            edges_minor=filtered_minor,
            house_system=house_system,
            dark_mode=toggles.dark_mode,
            label_style=toggles.label_style,
            compass_on=toggles.compass_inner,
            figsize=toggles.figsize,
            dpi=toggles.dpi,
            patterns=chart_result.patterns,
            shapes=chart_result.shapes,
            singleton_map=chart_result.singleton_map,
        )

    # Convert matplotlib figure → PNG bytes
    buf = io.BytesIO()
    try:
        rr.fig.savefig(buf, format="png", bbox_inches="tight",
                       facecolor=rr.fig.get_facecolor(), edgecolor="none")
        buf.seek(0)
        return buf.read()
    finally:
        plt.close(rr.fig)


# ---------------------------------------------------------------------------
# Biwheel (synastry / transit) rendering → PNG bytes
# ---------------------------------------------------------------------------

def render_biwheel_image(
    chart_1,
    chart_2,
    *,
    toggles: Optional[RenderToggles] = None,
    combined_data: Optional[Dict] = None,
    inter_chart_aspects: Optional[List] = None,
) -> bytes:
    """Render a biwheel chart as PNG bytes.

    In Standard mode: renders a standard biwheel with inter-chart + internal aspects.
    In Circuits/Combined mode: renders combined circuits spanning both charts.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from drawing_v2 import (
        render_biwheel_chart as _render_biwheel_standard,
        render_biwheel_chart_with_circuits as _render_biwheel_combined,
    )

    if toggles is None:
        toggles = RenderToggles()

    house_system = toggles.house_system

    if toggles.chart_mode == "Circuits" and combined_data:
        # Combined Circuits biwheel
        patterns = combined_data.get("patterns_combined", [])
        shapes = combined_data.get("shapes_combined", [])
        singleton_map = combined_data.get("singleton_map_combined", {})
        pos_combined = combined_data.get("pos_combined", {})
        combined_edges = combined_data.get("combined_edges", [])

        pattern_toggles_list = [
            toggles.pattern_toggles.get(i, False)
            for i in range(len(patterns))
        ]
        pattern_labels = [
            f"Circuit {i + 1}"
            for i in range(len(patterns))
        ]
        singleton_toggles_dict = {
            planet: toggles.singleton_toggles.get(planet, False)
            for planet in singleton_map
        }

        rr = _render_biwheel_combined(
            chart_1,
            chart_2,
            pos_combined=pos_combined,
            patterns=patterns,
            pattern_labels=pattern_labels,
            toggles=pattern_toggles_list,
            filaments=[],
            combo_toggles={},
            singleton_map=singleton_map,
            singleton_toggles=singleton_toggles_dict,
            shapes=shapes,
            shape_toggles_by_parent=toggles.shape_toggles,
            major_edges_all=combined_edges,
            house_system=house_system,
            dark_mode=toggles.dark_mode,
            label_style=toggles.label_style,
            figsize=toggles.figsize,
            dpi=toggles.dpi,
            compass_inner=toggles.compass_inner,
            compass_outer=toggles.compass_outer,
        )
    else:
        # Standard biwheel with inter-chart aspects
        inter_aspects = inter_chart_aspects or []

        # Build the set of aspect-enabled bodies (same logic as single-chart standard)
        aspect_bodies = set(_STANDARD_BASE_BODIES)
        for body_name, enabled in toggles.aspect_toggles.items():
            if enabled:
                aspect_bodies.add(body_name)

        # Filter inter-chart aspects: both endpoints must be in aspect_bodies
        edges_inter = (
            [e for e in inter_aspects if e[0] in aspect_bodies and e[1] in aspect_bodies]
            if toggles.synastry_inter else []
        )

        edges_chart1 = []
        edges_chart2 = []
        if toggles.synastry_chart1:
            for e in (getattr(chart_1, "edges_major", None) or []):
                a, b = e[0], e[1]
                asp = e[2] if len(e) > 2 else ""
                if isinstance(asp, dict):
                    asp = asp.get("aspect", "")
                if a in aspect_bodies and b in aspect_bodies:
                    edges_chart1.append((a, b, asp))
        if toggles.synastry_chart2:
            for e in (getattr(chart_2, "edges_major", None) or []):
                a, b = e[0], e[1]
                asp = e[2] if len(e) > 2 else ""
                if isinstance(asp, dict):
                    asp = asp.get("aspect", "")
                if a in aspect_bodies and b in aspect_bodies:
                    edges_chart2.append((a, b, asp))

        rr = _render_biwheel_standard(
            chart_1,
            chart_2,
            edges_inter_chart=edges_inter,
            edges_chart1=edges_chart1,
            edges_chart2=edges_chart2,
            house_system=house_system,
            dark_mode=toggles.dark_mode,
            label_style=toggles.label_style,
            figsize=toggles.figsize,
            dpi=toggles.dpi,
            compass_inner=toggles.compass_inner,
            compass_outer=toggles.compass_outer,
        )

    buf = io.BytesIO()
    try:
        rr.fig.savefig(buf, format="png", bbox_inches="tight",
                       facecolor=rr.fig.get_facecolor(), edgecolor="none")
        buf.seek(0)
        return buf.read()
    finally:
        plt.close(rr.fig)
