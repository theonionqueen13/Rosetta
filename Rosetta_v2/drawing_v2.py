"""Utilities for rendering the Rosetta v2 chart wheel using precomputed data."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping, Sequence
import math
import re
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st  # used by _selected_house_system/reset_chart_state/render_chart_with_shapes

try:  # Pandas is part of the calculation pipeline; import defensively.
    import pandas as pd
except Exception:  # pragma: no cover - pandas is expected to be present.
    pd = None  # type: ignore

# ---------------------------------------------------------------------------
# Lookup tables (glyphs, aspect metadata, colours)
# ---------------------------------------------------------------------------

def _import_lookup_attr(name: str, default: Any) -> Any:
    """Attempt to import ``name`` from lookup_v2, falling back to legacy data."""
    try:
        import lookup_v2 as _lookup  # type: ignore
    except Exception:  # pragma: no cover - fallback if module absent
        _lookup = None

    if _lookup is not None and hasattr(_lookup, name):
        return getattr(_lookup, name)

    try:  # legacy fallback (original package)
        from rosetta.lookup import __dict__ as _legacy_lookup  # type: ignore
    except Exception:  # pragma: no cover - last resort
        _legacy_lookup = {}

    return _legacy_lookup.get(name, default)

GLYPHS: Mapping[str, str] = _import_lookup_attr("GLYPHS", {})

try:  # Glyph resolver from profiles_v2 (handles aliases)
    from profiles_v2 import glyph_for  # type: ignore
except Exception:  # pragma: no cover - optional fallback
    glyph_for = None  # type: ignore

try:  # Optional helper to resolve toggle selections directly
    import patterns_v2 as _patterns_mod  # type: ignore
except Exception:  # pragma: no cover - patterns module optional
    _patterns_mod = None

# ---------------------------------------------------------------------------
# Chart Drawing helpers (NEW ones you pasted — kept)
# ---------------------------------------------------------------------------

def _selected_house_system():
    s = st.session_state.get("house_system_main", "Equal")
    return s.lower().replace(" sign", "")

def _in_forward_arc(start_deg, end_deg, x_deg):
    """True if x lies on the forward arc from start->end (mod 360)."""
    span = (end_deg - start_deg) % 360.0
    off  = (x_deg   - start_deg) % 360.0
    return off < span if span != 0 else off == 0

def _house_of_degree(deg, cusps):
    """Given a degree and a 12-length cusp list (House 1..12), return 1..12."""
    if not cusps or len(cusps) != 12:
        return None
    for i in range(12):
        a = cusps[i]
        b = cusps[(i + 1) % 12]
        if _in_forward_arc(a, b, deg):
            return i + 1
    return 12

# ---------------------------------------------------------------------------
# Basic math helpers & canonicalisation
# ---------------------------------------------------------------------------

def deg_to_rad(deg: float, asc_shift: float = 0.0) -> float:
    """Convert an absolute degree into the polar coordinate used for plotting."""
    return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)

_CANON_RE = re.compile(r"[^a-z0-9]+")

def _canonical_name(name: Any) -> str:
    if name is None:
        return ""
    return _CANON_RE.sub("", str(name).lower())

_ALIAS_GROUPS = [
    {"ac", "ascendant"},
    {"dc", "descendant"},
    {"mc", "midheaven"},
    {"ic", "imumcoeli"},
    {"northnode", "truenode"},
    {"southnode"},
    {"partoffortune", "pof"},
    {"blackmoonlilithmean", "blackmoonlilith", "lilith"},
]

_ALIAS_LOOKUP: dict[str, set[str]] = {}
for group in _ALIAS_GROUPS:
    canon_group = {_canonical_name(name) for name in group}
    for entry in canon_group:
        _ALIAS_LOOKUP[entry] = canon_group

_COMPASS_ALIAS_MAP: dict[str, list[str]] = {
    "Ascendant": ["AC", "Ascendant"],
    "Descendant": ["DC", "Descendant"],
    "MC": ["MC", "Midheaven"],
    "IC": ["IC", "Imum Coeli"],
    "North Node": ["North Node", "True Node"],
    "South Node": ["South Node"],
}

_cache_major_edges = {}
_cache_shapes = {}

def get_major_edges_and_patterns(pos):
	"""
	Build master list of major edges from positions, then cluster into patterns.
	"""
	pos_items_tuple = tuple(sorted(pos.items()))
	if pos_items_tuple not in _cache_major_edges:
		temp_edges = []
		planets = list(pos.keys())
		for i in range(len(planets)):
			for j in range(i + 1, len(planets)):
				p1, p2 = planets[i], planets[j]
				d1, d2 = pos.get(p1), pos.get(p2)
				if d1 is None or d2 is None:
					continue
				angle = abs(d1 - d2) % 360
				if angle > 180:
					angle = 360 - angle
				for aspect in ("Conjunction", "Sextile", "Square", "Trine", "Opposition"):
					data = ASPECTS[aspect]
					if abs(angle - data["angle"]) <= data["orb"]:
						temp_edges.append(((p1, p2), aspect))
						break
		patterns = connected_components_from_edges(list(pos.keys()), temp_edges)
		_cache_major_edges[pos_items_tuple] = (tuple(temp_edges), patterns)
	return _cache_major_edges[pos_items_tuple]

def get_shapes(pos, patterns, major_edges_all):
	pos_items_tuple = tuple(sorted(pos.items()))
	patterns_key = tuple(tuple(sorted(p)) for p in patterns)
	edges_tuple = tuple(major_edges_all)
	key = (pos_items_tuple, patterns_key, edges_tuple)
	if key not in _cache_shapes:
		_cache_shapes[key] = detect_shapes(pos, patterns, major_edges_all)
	return _cache_shapes[key]

SUBSHAPE_COLORS = [
	"#FF5214", "#FFA600", "#FBFF00", "#87DB00",
	"#00B828", "#049167", "#006EFF", "#1100FF",
	"#6320FF", "#9E0099", "#FF00EA", "#720022",
	"#4B2C06", "#534546", "#C4A5A5", "#5F7066",
]

def shape_color_for(shape_id: Any) -> str:
    """Return a stable solid colour for the given shape identifier."""

    palette: Sequence[str] = SUBSHAPE_COLORS or ("teal",)
    key = "_shape_color_map_v2"
    try:
        color_map = st.session_state.setdefault(key, {})
    except Exception:
        color_map = {}
    if shape_id not in color_map:
        idx = len(color_map) % len(palette)
        color_map[shape_id] = palette[idx]
        try:
            st.session_state[key] = color_map
        except Exception:
            pass
    return color_map[shape_id]

_HS_LABEL = {"equal": "Equal", "whole": "Whole Sign", "placidus": "Placidus"}


def _current_chart_header_lines():
	name = (
		st.session_state.get("current_profile_title")
		or st.session_state.get("current_profile")
		or "Untitled Chart"
	)
	if isinstance(name, str) and name.startswith("community:"):
		name = "Community Chart"

	month  = st.session_state.get("profile_month_name", "")
	day    = st.session_state.get("profile_day", "")
	year   = st.session_state.get("profile_year", "")
	hour   = st.session_state.get("profile_hour")
	minute = st.session_state.get("profile_minute")
	city   = st.session_state.get("profile_city", "")

	# 12-hour time
	time_str = ""
	if hour is not None and minute is not None:
		h = int(hour); m = int(minute)
		ampm = "AM" if h < 12 else "PM"
		h12  = 12 if (h % 12 == 0) else (h % 12)
		time_str = f"{h12}:{m:02d} {ampm}"

	date_line = f"{month} {day}, {year}".strip()
	if date_line and time_str:
		date_line = f"{date_line}, {time_str}"
	elif time_str:
		date_line = time_str

	return name, date_line, city
import matplotlib.patheffects as pe

import matplotlib.patheffects as pe

def _draw_header_on_figure(fig, name, date_line, city, dark_mode):
	"""Paint a 3-line header in the figure margin (top-left), never over the wheel."""
	color  = "white" if dark_mode else "black"
	stroke = "black" if dark_mode else "white"
	effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

	y0 = 0.99   # top margin in figure coords
	x0 = 0.00   # left margin

	fig.text(x0, y0, name, ha="left", va="top",
			 fontsize=12, fontweight="bold", color=color, path_effects=effects)
	if date_line:
		fig.text(x0, y0 - 0.035, date_line, ha="left", va="top",
				 fontsize=9, color=color, path_effects=effects)
	if city:
		fig.text(x0, y0 - 0.065, city, ha="left", va="top",
				 fontsize=9, color=color, path_effects=effects)

def _degree_for_label(pos: Mapping[str, float] | None, name: str) -> float | None:
    if not pos:
        return None
    value = pos.get(name)
    if value is not None:
        try:
            return float(value) % 360.0
        except Exception:
            return None
    canon = _canonical_name(name)
    aliases = _ALIAS_LOOKUP.get(canon, {canon})
    for key, val in pos.items():
        if val is None:
            continue
        try:
            deg = float(val) % 360.0
        except Exception:
            continue
        if _canonical_name(key) in aliases:
            return deg
    return None

_COMPASS_ALIAS_MAP: dict[str, list[str]] = {
    "Ascendant": ["AC", "Ascendant"],
    "Descendant": ["DC", "Descendant"],
    "MC": ["MC", "Midheaven"],
    "IC": ["IC", "Imum Coeli"],
    "North Node": ["North Node", "True Node"],
    "South Node": ["South Node"],
}

ASPECTS = _import_lookup_attr(
    "ASPECTS",
    {
        "Conjunction": {"angle": 0, "orb": 3, "color": "#888888", "style": "solid"},
        "Sextile": {"angle": 60, "orb": 3, "color": "purple",  "style": "solid"},
        "Square": {"angle": 90, "orb": 3, "color": "red",     "style": "solid"},
        "Trine": {"angle": 120, "orb": 3, "color": "blue",    "style": "solid"},
        "Sesquisquare": {"angle": 135, "orb": 2, "color": "orange", "style": "dotted"},
        "Quincunx": {"angle": 150, "orb": 3, "color": "green", "style": "dotted"},
        "Opposition": {"angle": 180, "orb": 3, "color": "red", "style": "solid"},
    },
)

GROUP_COLORS = _import_lookup_attr(
    "GROUP_COLORS",
    (
        "crimson","teal","darkorange","slateblue","seagreen",
        "hotpink","gold","deepskyblue","orchid",
    ),
)

def group_color_for(idx: int) -> str:
    """Return a deterministic colour for the given circuit index."""

    if not GROUP_COLORS:
        return "teal"
    try:
        return GROUP_COLORS[idx % len(GROUP_COLORS)]
    except Exception:
        return "teal"


ZODIAC_SIGNS = _import_lookup_attr(
    "ZODIAC_SIGNS",
    ("♈️","♉️","♊️","♋️","♌️","♍️","♎️","♏️","♐️","♑️","♒️","♓️"),
)

# NEW: add a safe default palette for sign colors
ZODIAC_COLORS = _import_lookup_attr(
    "ZODIAC_COLORS",
    (
        "#E57373", "#F06292", "#BA68C8", "#9575CD",
        "#64B5F6", "#4FC3F7", "#4DD0E1", "#81C784",
        "#AED581", "#FFD54F", "#FFB74D", "#A1887F",
    ),
)

def _degree_for_label(pos: Mapping[str, float] | None, name: str) -> float | None:
    if not pos:
        return None
    value = pos.get(name)
    if value is not None:
        try:
            return float(value) % 360.0
        except Exception:
            return None
    canon = _canonical_name(name)
    aliases = _ALIAS_LOOKUP.get(canon, {canon})
    for key, val in pos.items():
        if val is None:
            continue
        try:
            deg = float(val) % 360.0
        except Exception:
            continue
        if _canonical_name(key) in aliases:
            return deg
    return None

def _expand_visible_canon(names: Collection[str] | None) -> set[str] | None:
    if not names:
        return None
    expanded: set[str] = set()
    for name in names:
        canon = _canonical_name(name)
        expanded.update(_ALIAS_LOOKUP.get(canon, {canon}))
    return expanded

def _object_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or "Object" not in df:
        return pd.DataFrame(columns=["Object", "Longitude"])
    obj_series = df["Object"].astype("string")
    mask = ~obj_series.str.contains("cusp", case=False, na=False)
    return df.loc[mask].copy()

def _canonical_series(df: pd.DataFrame) -> pd.Series:
    obj_series = df["Object"].astype("string")
    return obj_series.map(_canonical_name)

def _find_row(df: pd.DataFrame, names: Iterable[str]) -> pd.Series | None:
    if df is None or "Object" not in df:
        return None
    canon_series = _canonical_series(df)
    for candidate in names:
        canon = _canonical_name(candidate)
        target = _ALIAS_LOOKUP.get(canon, {canon})
        mask = canon_series.isin(target)
        if mask.any():
            return df.loc[mask].iloc[0]
    return None

def get_ascendant_degree(df: pd.DataFrame) -> float:
    row = _find_row(df, ["AC", "Ascendant", "Asc"])
    if row is None:
        return 0.0
    try:
        return float(row.get("Longitude", 0.0))
    except Exception:
        return 0.0

def _resolve_visible_from_patterns(toggle_state: Any, df: pd.DataFrame | None) -> set[str] | None:
    if _patterns_mod is None:
        return None
    candidate_funcs = (
        "resolve_visible_objects",
        "visible_objects_from_toggles",
        "visible_object_names",
        "get_visible_objects",
    )
    for func_name in candidate_funcs:
        func = getattr(_patterns_mod, func_name, None)
        if callable(func):
            try:
                result = func(toggle_state, df=df)
            except TypeError:
                try:
                    result = func(toggle_state)
                except TypeError:
                    continue
            if result:
                return set(result)
    return None

def resolve_visible_objects(toggle_state: Any = None, df: pd.DataFrame | None = None) -> set[str] | None:
    via_patterns = _resolve_visible_from_patterns(toggle_state, df)
    if via_patterns:
        return via_patterns
    if toggle_state is None:
        return None
    if isinstance(toggle_state, Mapping):
        names = {str(name) for name, enabled in toggle_state.items() if enabled}
        return names or None
    if isinstance(toggle_state, Collection) and not isinstance(toggle_state, (str, bytes)):
        return {str(name) for name in toggle_state}
    return None

def extract_positions(df: pd.DataFrame, visible_names: Collection[str] | None = None) -> dict[str, float]:
    objs = _object_rows(df)
    if objs.empty:
        return {}
    visible_canon = _expand_visible_canon(visible_names)
    canon_series = _canonical_series(objs)
    positions: dict[str, float] = {}
    for (_, row), canon in zip(objs.iterrows(), canon_series):
        if visible_canon is not None and canon not in visible_canon:
            continue
        lon = row.get("Longitude")
        if lon is None or (pd.isna(lon) if pd is not None else False):
            continue
        positions[str(row.get("Object"))] = float(lon)
    return positions

def extract_compass_positions(
    df: pd.DataFrame,
    visible_names: Collection[str] | None = None,
) -> dict[str, float]:
    visible_canon = _expand_visible_canon(visible_names)
    out: dict[str, float] = {}
    for label, names in _COMPASS_ALIAS_MAP.items():
        row = _find_row(df, names)
        if row is None:
            continue
        target_group: set[str] = set()
        for n in names:
            target_group.update(_ALIAS_LOOKUP.get(_canonical_name(n), {_canonical_name(n)}))
        if visible_canon is not None and target_group.isdisjoint(visible_canon):
            continue
        lon = row.get("Longitude")
        if lon is None or (pd.isna(lon) if pd is not None else False):
            continue
        out[label] = float(lon)
    return out

# ---------------------------------------------------------------------------
# Drawing primitives (NEW versions kept; old duplicates removed)
# ---------------------------------------------------------------------------

def draw_house_cusps(
    ax,
    df: pd.DataFrame,
    asc_deg: float,
    house_system: str = "placidus",
    dark_mode: bool = False,
    label_r: float = 0.32,
    label_frac: float = 0.50,
) -> list[float]:
    system_map = {
        "placidus": "Placidus",
        "equal": "Equal",
        "equal house": "Equal",
        "whole": "Whole Sign",
        "wholesign": "Whole Sign",
    }
    sys_key = (house_system or "placidus").strip().lower()
    sys_label = system_map.get(sys_key, system_map["placidus"])

    cusps: list[float] = []
    if df is not None and "Object" in df and "Longitude" in df:
        obj_series = df["Object"].astype("string")
        pattern = rf"^\s*{re.escape(sys_label)}\s*(\d+)H\s*cusp\s*$"
        mask = obj_series.str.match(pattern, case=False, na=False)
        cusp_rows = df.loc[mask].copy()
        if not cusp_rows.empty:
            cusp_rows["__H"] = cusp_rows["Object"].astype("string").str.extract(r"(\d+)").astype(int)
            cusp_rows = cusp_rows.sort_values("__H")
            cusps = [float(v) for v in cusp_rows.get("Longitude", []) if not pd.isna(v)]

    if len(cusps) != 12:
        start = asc_deg % 360.0
        cusps = [(start + i * 30.0) % 360.0 for i in range(12)]

    line_color = "lightgray"
    for deg in cusps:
        rad = deg_to_rad(deg, asc_deg)
        ax.plot([rad, rad], [0, 1.45], color=line_color, linestyle="solid", linewidth=1, zorder=1)

    lbl_color = "white" if dark_mode else "black"
    for i in range(12):
        a = cusps[i]
        b = cusps[(i + 1) % 12]
        span = (b - a) % 360.0
        label_deg = (a + span * label_frac) % 360.0
        label_rad = deg_to_rad(label_deg, asc_deg)
        ax.text(label_rad, label_r, str(i + 1), ha="center", va="center", fontsize=8, color=lbl_color, zorder=100)

    return cusps

def draw_degree_markers(ax, asc_deg, dark_mode):
    """Draw tick marks at 1°, 5°, and 10° intervals, plus a circular outline."""
    base_color = "white" if dark_mode else "black"
    circle_r = 1.0
    circle = plt.Circle((0, 0), circle_r, transform=ax.transData._b,
                        fill=False, color=base_color, linewidth=1)
    ax.add_artist(circle)

    for deg in range(0, 360, 1):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [circle_r, circle_r + 0.015],
                color=base_color, linewidth=0.5)

    for deg in range(0, 360, 5):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [circle_r, circle_r + 0.03],
                color=base_color, linewidth=0.8)

    for deg in range(0, 360, 10):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [circle_r, circle_r + 0.05],
                color=base_color, linewidth=1.2)

def draw_zodiac_signs(ax, asc_deg):
    """Zodiac ring with pastel element bands and black dividers."""
    PASTEL_BLUE   = "#D9EAF7"  # blue
    PASTEL_GREEN  = "#D9EAD3"  # green
    PASTEL_ORANGE = "#FFD1B3"  # orange
    PASTEL_RED    = "#EAD1DC"  # soft red/pink

    element_color = {
        "fire":  PASTEL_BLUE,   # remapped per your note
        "earth": PASTEL_RED,
        "air":   PASTEL_GREEN,
        "water": PASTEL_ORANGE,
    }
    elements = ["fire", "earth", "air", "water"] * 3
    sector_width = np.deg2rad(30)

    ring_inner, ring_outer = 1.45, 1.58
    divider_inner, divider_outer = 1.457, 1.573

    for i in range(12):
        theta_left = deg_to_rad(i * 30, asc_deg)
        ax.bar(
            theta_left,
            ring_outer - ring_inner,
            width=sector_width,
            bottom=ring_inner,
            align="edge",
            color=element_color[elements[i]],
            edgecolor=None,
            linewidth=0,
            alpha=0.85,
            zorder=0,
        )

    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)
        ax.text(
            rad, 1.50, ZODIAC_SIGNS[i],
            ha="center", va="center",
            fontsize=16, fontweight="bold",
            color=ZODIAC_COLORS[i],
            zorder=1,
        )

    asc_sign_start = int(asc_deg // 30) * 30.0
    cusps = [(asc_sign_start + i * 30.0) % 360.0 for i in range(12)]
    for deg in cusps:
        rad = deg_to_rad(deg, asc_deg)
        ax.plot([rad, rad], [divider_inner, divider_outer],
                color="black", linestyle="solid", linewidth=1, zorder=5)

def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode):
    """Planet glyphs/names with degree (no sign), cluster fan-out + global spacing."""
    if not pos:
        return

    degree_threshold = 3  # cluster proximity
    min_spacing = 7       # minimum separation between cluster anchors

    sorted_pos = sorted(pos.items(), key=lambda x: x[1])
    clusters: list[list[tuple[str, float]]] = []
    for name, degree in sorted_pos:
        for cluster in clusters:
            if abs(degree - cluster[0][1]) <= degree_threshold:
                cluster.append((name, degree))
                break
        else:
            clusters.append([(name, degree)])

    cluster_degrees = [sum(d for _, d in c) / len(c) for c in clusters]

    for i in range(1, len(cluster_degrees)):
        if cluster_degrees[i] - cluster_degrees[i - 1] < min_spacing:
            cluster_degrees[i] = cluster_degrees[i - 1] + min_spacing

    if (cluster_degrees and
        (cluster_degrees[0] + 360.0) - cluster_degrees[-1] < min_spacing):
        cluster_degrees[-1] = cluster_degrees[0] + 360.0 - min_spacing

    color = "white" if dark_mode else "black"
    want_glyphs = str(label_style).lower() == "glyph"

    for cluster, base_degree in zip(clusters, cluster_degrees):
        n = len(cluster)
        if n == 1:
            items = [(cluster[0][0], cluster[0][1])]
        else:
            spread = 3
            start = base_degree - (spread * (n - 1) / 2)
            items = [(name, start + i * spread) for i, (name, _) in enumerate(cluster)]

        for (name, display_degree), (_, true_degree) in zip(items, cluster):
            deg_true = true_degree % 360.0
            rad_true = deg_to_rad(display_degree % 360.0, asc_deg)

            label = (glyph_for(name) if glyph_for else GLYPHS.get(name)) if want_glyphs else name
            if not label:
                label = name

            deg_int = int(deg_true % 30)
            deg_label = f"{deg_int}°"

            ax.text(rad_true, 1.35, label, ha="center", va="center", fontsize=9, color=color)
            ax.text(rad_true, 1.27, deg_label, ha="center", va="center", fontsize=6, color=color)

def draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg):
    """Draw dotted lines for minor aspects between active patterns."""
    single_pattern_mode = len(active_patterns) == 1
    for p1, p2, asp_name, pat1, pat2 in filaments:
        if pat1 in active_patterns and pat2 in active_patterns:
            if single_pattern_mode and pat1 != pat2:
                continue
            r1 = deg_to_rad(pos.get(p1, 0.0), asc_deg)
            r2 = deg_to_rad(pos.get(p2, 0.0), asc_deg)
            ax.plot([r1, r2], [1, 1], linestyle="dotted",
                    color=ASPECTS.get(asp_name, {}).get("color", "gray"), linewidth=1)

def reset_chart_state():
    """Clear transient UI keys so each chart loads cleanly."""
    for key in list(st.session_state.keys()):
        if key.startswith("toggle_pattern_"):
            del st.session_state[key]
        if key.startswith("shape_"):
            del st.session_state[key]
        if key.startswith("singleton_"):
            del st.session_state[key]
    st.session_state.pop("shape_toggles_by_parent", None)

# ---------------------------------------------------------------------------
# Aspect drawing (shared)
# ---------------------------------------------------------------------------

def _edge_record_to_components(record: Any):
    if isinstance(record, (list, tuple)):
        if len(record) == 3:
            a, b, meta = record
            aspect = meta.get("aspect") if isinstance(meta, Mapping) else meta
            return str(a), str(b), aspect
        if len(record) == 2:
            (a, b), meta = record
            aspect = meta.get("aspect") if isinstance(meta, Mapping) else meta
            return str(a), str(b), aspect
    return None, None, None

def draw_aspect_lines(ax, pos, edges, asc_deg, visible_canon=None, linewidth_major=2.0, color_override: str | None = None):
    drawn = []
    if not edges:
        return drawn
    for record in edges:
        a, b, aspect = _edge_record_to_components(record)
        if not a or not b or not aspect:
            continue
        canon_a = _canonical_name(a); canon_b = _canonical_name(b)
        if visible_canon is not None and (canon_a not in visible_canon or canon_b not in visible_canon):
            continue
        d1 = pos.get(a); d2 = pos.get(b)
        if d1 is None or d2 is None:
            continue
        r1 = deg_to_rad(d1, asc_deg); r2 = deg_to_rad(d2, asc_deg)
        spec = ASPECTS.get(aspect, {})
        color = color_override or spec.get("color", "gray")
        style = spec.get("style", "solid")
        lw = linewidth_major if aspect not in ("Quincunx", "Sesquisquare") else 1.0
        ax.plot([r1, r2], [1, 1], linestyle=style, color=color, linewidth=lw)
        drawn.append((a, b, aspect))
    return drawn

def draw_minor_edges(ax, pos, edges, asc_deg, visible_canon=None, linewidth_minor=1.0, color_override: str | None = None):
    drawn = []
    if not edges:
        return drawn
    for record in edges:
        a, b, aspect = _edge_record_to_components(record)
        if not a or not b or not aspect:
            continue
        canon_a = _canonical_name(a); canon_b = _canonical_name(b)
        if visible_canon is not None and (canon_a not in visible_canon or canon_b not in visible_canon):
            continue
        d1 = pos.get(a); d2 = pos.get(b)
        if d1 is None or d2 is None:
            continue
        r1 = deg_to_rad(d1, asc_deg); r2 = deg_to_rad(d2, asc_deg)
        color = color_override or ASPECTS.get(aspect, {}).get("color", "gray")
        ax.plot([r1, r2], [1, 1], linestyle="dotted", color=color, linewidth=linewidth_minor)
        drawn.append((a, b, aspect))
    return drawn

def draw_singleton_dots(
    ax,
    pos: Mapping[str, float],
    singletons: Iterable[str],
    shape_edges: Collection[tuple[str, str]] | None,
    asc_deg: float,
    line_width: float = 2.0,
) -> None:
    shape_edge_set = {frozenset(edge) for edge in (shape_edges or [])}
    for obj in singletons:
        if obj not in pos:
            continue
        has_edge = any(frozenset((obj, other)) in shape_edge_set for other in pos.keys())
        if not has_edge:
            r = deg_to_rad(pos[obj], asc_deg)
            ax.plot([r], [1], "o", color="red", markersize=6, linewidth=line_width)

def draw_compass_rose(
    ax,
    pos: Mapping[str, float],
    asc_deg: float,
    *,
    colors: Mapping[str, str] | None = None,
    linewidth_base: float = 2.0,
    zorder: int = 100,
    arrow_mutation_scale: float = 20.0,
    nodal_width_multiplier: float = 2.0,
    sn_dot_markersize: float = 8.0,
) -> None:
    if colors is None:
        colors = {"nodal": "purple", "acdc": "green", "mcic": "orange"}

    def _get_deg(name: str) -> float | None:
        return _degree_for_label(pos, name)

    z_axes = zorder + 1
    z_nodal_line = zorder + 2
    z_nodal_top = zorder + 3

    ac = _get_deg("Ascendant")
    dc = _get_deg("Descendant")
    if ac is not None and dc is None:
        dc = (ac + 180.0) % 360.0
    elif dc is not None and ac is None:
        ac = (dc + 180.0) % 360.0
    if ac is not None and dc is not None:
        r1 = deg_to_rad(ac, asc_deg)
        r2 = deg_to_rad(dc, asc_deg)
    ax.plot(
            [r1, r2],
            [1, 1],
            color=colors.get("acdc", "#4E83AF"),
            linewidth=linewidth_base,
            zorder=z_axes,
        )
    mc = _get_deg("MC")
    ic = _get_deg("IC")
    if mc is not None and ic is None:
        ic = (mc + 180.0) % 360.0
    elif ic is not None and mc is None:
        mc = (ic + 180.0) % 360.0
    if mc is not None and ic is not None:
        r1 = deg_to_rad(mc, asc_deg)
        r2 = deg_to_rad(ic, asc_deg)
        ax.plot(
            [r1, r2],
            [1, 1],
            color=colors.get("mcic", "#4E83AF"),
            linewidth=linewidth_base,
            zorder=z_axes,
        )
    sn = _get_deg("South Node")
    nn = _get_deg("North Node")
    if sn is not None and nn is not None:
        x1, y1 = math.cos(deg_to_rad(sn, asc_deg)) * 1.0, math.sin(deg_to_rad(sn, asc_deg)) * 1.0
        x2, y2 = math.cos(deg_to_rad(nn, asc_deg)) * 1.0, math.sin(deg_to_rad(nn, asc_deg)) * 1.0
        vx, vy = (x2 - x1), (y2 - y1)
        head_trim_frac = 0.05
        x2_trim = x2 - head_trim_frac * vx
        y2_trim = y2 - head_trim_frac * vy
        r2_trim_theta = math.atan2(y2_trim, x2_trim)
        r2_trim_rad = math.hypot(x2_trim, y2_trim)
        ax.plot([deg_to_rad(sn, asc_deg), r2_trim_theta], [1.0, r2_trim_rad],
                color=colors["nodal"], linewidth=linewidth_base * nodal_width_multiplier, zorder=z_nodal_line)
        ax.annotate(
            "",
            xy=(deg_to_rad(nn, asc_deg), 1.0),
            xytext=(deg_to_rad(sn, asc_deg), 1.0),
            arrowprops=dict(
                arrowstyle="-|>",
                mutation_scale=arrow_mutation_scale,
                lw=linewidth_base * nodal_width_multiplier,
                color=colors.get("nodal", "purple"),
                shrinkA=0,
                shrinkB=0,
            ),
            zorder=z_nodal_top,
        )
        ax.plot([deg_to_rad(sn, asc_deg)], [1.0], marker="o", markersize=sn_dot_markersize,
                color=colors["nodal"], zorder=z_nodal_top)

# ---------------------------------------------------------------------------
# High-level renderer
# ---------------------------------------------------------------------------

@dataclass
class RenderResult:
    fig: Any
    ax: Any
    positions: dict[str, float]
    cusps: list[float]
    visible_objects: list[str]
    drawn_major_edges: list[tuple[str, str, str]]
    drawn_minor_edges: list[tuple[str, str, str]]

def render_chart(
    df: pd.DataFrame,
    *,
    visible_toggle_state: Any = None,
    edges_major: Sequence[Any] | None = None,
    edges_minor: Sequence[Any] | None = None,
    house_system: str = "placidus",
    dark_mode: bool = False,
    label_style: str = "glyph",
    compass_on: bool = True,
    degree_markers: bool = True,
    zodiac_labels: bool = True,
    figsize: tuple[float, float] = (5.0, 5.0),
    dpi: int = 144,
):
    """Render the chart wheel using already-curated data."""
    asc_deg = get_ascendant_degree(df)
    visible_names = resolve_visible_objects(visible_toggle_state, df)
    positions = extract_positions(df, visible_names)
    visible_canon = _expand_visible_canon(visible_names)

    fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.25)
    ax.axis("off")

    fig.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.95)

    cusps = draw_house_cusps(ax, df, asc_deg, house_system, dark_mode)
    if degree_markers:
        draw_degree_markers(ax, asc_deg, dark_mode)
    if zodiac_labels:
        draw_zodiac_signs(ax, asc_deg)

    draw_planet_labels(ax, positions, asc_deg, label_style=label_style, dark_mode=dark_mode)

    major_edges_drawn = draw_aspect_lines(
        ax,
        positions,
        edges_major or [],
        asc_deg,
        visible_canon=visible_canon,
        linewidth_major=2.0,
    )
    minor_edges_drawn = draw_minor_edges(
        ax,
        positions,
        edges_minor or [],
        asc_deg,
        visible_canon=visible_canon,
        linewidth_minor=1.0,
    )

    if compass_on:
        compass_positions = extract_compass_positions(df, visible_names)
        draw_compass_rose(ax, compass_positions, asc_deg)

    return RenderResult(
        fig=fig,
        ax=ax,
        positions=positions,
        cusps=cusps,
        visible_objects=sorted(positions.keys()),
        drawn_major_edges=major_edges_drawn,
        drawn_minor_edges=minor_edges_drawn,
    )

# --- CHART RENDERER (full; calls your new helpers) -------------------------
def render_chart_with_shapes(
    pos, patterns, pattern_labels, toggles,
    filaments, combo_toggles, label_style, singleton_map, df,
    house_system, dark_mode, shapes, shape_toggles_by_parent, singleton_toggles,
    major_edges_all
):
    asc_deg = get_ascendant_degree(df)
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.60)
    ax.axis("off")

    # Center and fill
    ax.set_anchor("C")
    ax.set_aspect("equal", adjustable="box")
    fig.subplots_adjust(left=0, right=0.85, top=0.95, bottom=0.05)

    # Header helpers (no-ops if not present elsewhere)
    try:
        name, date_line, city = _current_chart_header_lines()  # type: ignore
        _draw_header_on_figure(fig, name, date_line, city, dark_mode)  # type: ignore
    except Exception:
        pass

    # Base wheel
    cusps = draw_house_cusps(ax, df, asc_deg, house_system, dark_mode)
    draw_degree_markers(ax, asc_deg, dark_mode)
    draw_zodiac_signs(ax, asc_deg)
    draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode)

    active_parents = set(i for i, show in enumerate(toggles) if show)
    active_shape_ids = [
        s["id"] for s in shapes if st.session_state.get(f"shape_{s['parent']}_{s['id']}", False)
    ]
    active_shapes = [s for s in shapes if s["id"] in active_shape_ids]

    active_toggle_count = len(active_parents) + len(active_shapes)
    layered_mode = active_toggle_count > 1

    active_singletons = {obj for obj, on in singleton_toggles.items() if on}
    visible_objects = set()

    shape_edges = {
        frozenset((u, v))
        for s in active_shapes
        for (u, v), asp in s["edges"]
    }

    # Assemble context aspects (what we actually draw)
    aspects_for_context = []
    seen = set()

    def _add_edge(a, aspect, b):
        asp = (aspect or "").replace("_approx", "").strip()
        if not asp or asp.lower() == "conjunction":
            return
        key = (tuple(sorted([a, b])), asp)
        if key in seen:
            return
        seen.add(key)
        aspects_for_context.append({"from": a, "to": b, "aspect": asp})

    # Per-parent major edges + internal minors
    for idx in active_parents:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])

            edges = [((p1, p2), asp_name)
                    for ((p1, p2), asp_name) in major_edges_all
                    if p1 in patterns[idx] and p2 in patterns[idx]]

            color = group_color_for(idx) if layered_mode else None
            # major edges in this circuit’s color
            draw_aspect_lines(ax, pos, edges, asc_deg, color_override=color)
            for (p1, p2), asp in edges:
                _add_edge(p1, asp, p2)

            # internal minors for this circuit in same color
            internal_minors = [((p1, p2), asp_name)
                            for (p1, p2, asp_name, pat1, pat2) in filaments
                            if pat1 == idx and pat2 == idx]
            draw_minor_edges(ax, pos, internal_minors, asc_deg, color_override=color)
            for (p1, p2), asp in internal_minors:
                _add_edge(p1, asp, p2)

    # Inter-parent filaments (dotted connectors)
    if active_parents:
        draw_filament_lines(ax, pos, filaments, active_parents, asc_deg)
        for (p1, p2, asp_name, pat1, pat2) in filaments:
            if pat1 in active_parents and pat2 in active_parents and frozenset((p1, p2)) not in shape_edges:
                _add_edge(p1, asp_name, p2)

    # Sub-shapes edges
    for s in active_shapes:
        visible_objects.update(s["members"])
        color = shape_color_for(s["id"]) if layered_mode else None
        draw_aspect_lines(ax, pos, s["edges"], asc_deg, color_override=color)
        for (p1, p2), asp in s["edges"]:
            _add_edge(p1, asp, p2)

    # Singletons
    visible_objects.update(active_singletons)
    if active_singletons:
        draw_singleton_dots(ax, pos, active_singletons, shape_edges, asc_deg, line_width=2.0)

    # Compass
    if st.session_state.get("toggle_compass_rose", True):
        compass_positions = extract_compass_positions(df)
        compass_source = compass_positions or pos
        draw_compass_rose(
            ax, compass_source, asc_deg,
            colors={"nodal": "purple", "acdc": "#4E83AF", "mcic": "#4E83AF"},
            linewidth_base=2.0, zorder=100, arrow_mutation_scale=22.0,
            nodal_width_multiplier=2.0, sn_dot_markersize=12.0
        )
        visible_objects.update({"Ascendant", "Descendant", "MC", "IC", "North Node", "South Node"})
        for names in _COMPASS_ALIAS_MAP.values():
            row = _find_row(df, names)
            if row is not None:
                obj_name = str(row.get("Object"))
                if obj_name:
                    visible_objects.add(obj_name)

        sn = _degree_for_label(compass_source, "South Node")
        nn = _degree_for_label(compass_source, "North Node")
        if sn is not None and nn is not None:
            _add_edge("South Node", "Opposition", "North Node")

        ac_val = _degree_for_label(compass_source, "Ascendant")
        dc_val = _degree_for_label(compass_source, "Descendant")
        if ac_val is not None and dc_val is None:
            dc_val = (ac_val + 180.0) % 360.0
        elif dc_val is not None and ac_val is None:
            ac_val = (dc_val + 180.0) % 360.0
        if ac_val is not None and dc_val is not None:
            _add_edge("Ascendant", "Opposition", "Descendant")

        mc_val = _degree_for_label(compass_source, "MC")
        ic_val = _degree_for_label(compass_source, "IC")
        if mc_val is not None and ic_val is None:
            ic_val = (mc_val + 180.0) % 360.0
        elif ic_val is not None and mc_val is None:
            mc_val = (ic_val + 180.0) % 360.0
        if mc_val is not None and ic_val is not None:
            _add_edge("MC", "Opposition", "IC")

    # Interpretation (best-effort: skip if those helpers aren’t wired yet)
    out_text = None
    try:
        context = build_context_for_objects(  # type: ignore
            targets=list(visible_objects),
            pos=pos,
            df=df,
            active_shapes=active_shapes,
            aspects=aspects_for_context,
            star_catalog=STAR_CATALOG,          # type: ignore
            cusps=cusps,
            row_cache=enhanced_objects_data,    # type: ignore
            profile_rows=enhanced_objects_data, # type: ignore
        )
        task = choose_task_instruction(  # type: ignore
            chart_mode="natal",
            visible_objects=list(visible_objects),
            active_shapes=active_shapes,
            context=context,
        )
        out_text = ask_gemini_brain(genai, task, context)  # type: ignore
    except Exception:
        pass

    return fig, visible_objects, active_shapes, cusps, out_text

__all__ = [
    "RenderResult",
    "render_chart",
    "render_chart_with_shapes",
    "group_color_for",
    "draw_house_cusps",
    "draw_degree_markers",
    "draw_zodiac_signs",
    "draw_planet_labels",
    "draw_aspect_lines",
    "draw_minor_edges",
    "draw_singleton_dots",
    "draw_filament_lines",
    "draw_compass_rose",
    "deg_to_rad",
    "get_ascendant_degree",
    "extract_positions",
    "resolve_visible_objects",
    "_selected_house_system",
    "reset_chart_state",
]
