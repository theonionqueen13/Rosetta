"""Utilities for rendering the Rosetta v2 chart wheel using precomputed data."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping, Sequence
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import matplotlib.image as mpimg
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba, to_hex
import os, re, math
import numpy as np
import streamlit as st
from patterns_v2 import detect_shapes, connected_components_from_edges
from now_v2 import _moon_phase_label_emoji
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

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

GROUP_COLORS = [
  	"#008CFF", "#FFAE00", "#B80303","#6321CE",
	"#FF5100", "#53B800", "#1D1FC5", "#440101",
]
GROUP_COLORS_LIGHT = [
  	"#008Cff63", "#EED29463", "#C7717163", "#A98ED363",
	"#F5A98658", "#9DD17263", "#9394EC63", "#85686863",
]
SUBSHAPE_COLORS = [
	"#FF5214", "#FFA600", "#FBFF00", "#87DB00",
	"#00B828", "#049167", "#006EFF", "#1100FF",
	"#6320FF", "#9E0099", "#FF00EA", "#720022",
	"#4B2C06", "#534546", "#C4A5A5", "#5F7066",
]
SUBSHAPE_COLORS_LIGHT = [
	"#FF521449", "#FFA60049", "#FBFF0049", "#87DB0049",
	"#00B82849", "#04916749", "#006EFF49", "#1100FF49",
	"#6320FF49", "#9E009949", "#FF00EA49", "#72002249",
	"#4B2C0649", "#53454675", "#C4A5A549", "#5F706649",
]

LUMINARIES_AND_PLANETS = {
	"sun", "moon", "mercury", "venus", "mars",
	"jupiter", "saturn", "uranus", "neptune", "pluto",
}


def _is_luminary_or_planet(name: str) -> bool:
	return _canonical_name(name) in LUMINARIES_AND_PLANETS


def _light_variant_for(color: str) -> str:
	"""Return a lighter + less-opaque variant of `color`.
	1) If `color` is in GROUP_COLORS or SUBSHAPE_COLORS, return the matching *_LIGHT entry.
	2) Otherwise, blend the RGB toward white and scale alpha down.
	"""
	# 1) Exact palette matches first
	try:
		idx = GROUP_COLORS.index(color)
		if idx < len(GROUP_COLORS_LIGHT):
			return GROUP_COLORS_LIGHT[idx]
	except ValueError:
		pass

	try:
		idx = SUBSHAPE_COLORS.index(color)
		if idx < len(SUBSHAPE_COLORS_LIGHT):
			return SUBSHAPE_COLORS_LIGHT[idx]
	except ValueError:
		pass

	# 2) Generic fallback: lighten + reduce opacity
	# Tune these two knobs if you want a different feel:
	BLEND_TOWARD_WHITE = 0.35  # 0..1 (higher = lighter)
	ALPHA_SCALE = 0.6          # 0..1 (lower = more transparent)

	r, g, b, a = to_rgba(color)

	# Lighten toward white
	r = r + (1.0 - r) * BLEND_TOWARD_WHITE
	g = g + (1.0 - g) * BLEND_TOWARD_WHITE
	b = b + (1.0 - b) * BLEND_TOWARD_WHITE

	# Reduce opacity (respect any existing alpha)
	a = a * ALPHA_SCALE

	return to_hex((r, g, b, a), keep_alpha=True)

def _lighten_color(color: str, blend: float = 0.5) -> str:
	"""Blend ``color`` toward white by ``blend`` (0..1)."""

	blend = max(0.0, min(1.0, blend))
	r, g, b, a = to_rgba(color)
	r = r + (1.0 - r) * blend
	g = g + (1.0 - g) * blend
	b = b + (1.0 - b) * blend
	return to_hex((r, g, b, a), keep_alpha=True)


def _normalise_aspect(aspect: Any) -> tuple[str, bool]:
	"""Return (clean_name, is_approx) for an aspect label."""

	if aspect is None:
		return "", False
	name = str(aspect).strip()
	if not name:
		return "", False
	approx = False
	if name.endswith("_approx"):
		approx = True
		name = name[:-7]
	return name, approx


def _segment_points(theta1: float, theta2: float, radius: float = 1.0, steps: int = 48) -> tuple[np.ndarray, np.ndarray]:
	"""Return theta/r arrays describing the straight chord between two polar points."""

	x1, y1 = radius * np.cos(theta1), radius * np.sin(theta1)
	x2, y2 = radius * np.cos(theta2), radius * np.sin(theta2)
	xs = np.linspace(x1, x2, steps)
	ys = np.linspace(y1, y2, steps)
	thetas = np.unwrap(np.arctan2(ys, xs))
	radii = np.hypot(xs, ys)
	return thetas, radii

def _draw_gradient_line(
    ax,
    theta1: float,
    theta2: float,
    color_start: str,
    color_end: str,
    linewidth: float,
    linestyle: str,
    radius: float = 1.0,
) -> None:
    """
    Draw a chord between two polar angles with either:
      - SOLID (with gradient if colors differ), or
      - DOTTED/DASHED/DASHDOT (simulated using many short solid segments),
    so that we can keep a smooth color gradient AND a visible pattern.
    """
    def _vec(th):
        return np.cos(th) * radius, np.sin(th) * radius

    def _interp_xy(t):
        x = (1.0 - t) * x1 + t * x2
        y = (1.0 - t) * y1 + t * y2
        return x, y

    def _xy_to_polar(x, y):
        return np.arctan2(y, x), np.hypot(x, y)

    # endpoints in Cartesian on the unit ring
    x1, y1 = _vec(theta1)
    x2, y2 = _vec(theta2)
    chord_len = float(np.hypot(x2 - x1, y2 - y1))  # ~[0, 2]

    style = (linestyle or "solid").lower()
    wants_pattern = style in ("dotted", "dashed", "dashdot")

    # ---------- PATTERNED (dotted/dashed) with GRADIENT ----------
    if wants_pattern:
        # Choose segment (dash) length and gap ratio that read well on screen.
        # Scale lengths by chord_len so visuals are consistent across spans.
        if style == "dotted":
            # lots of short "dots"
            seg_len = 0.02 * max(1.0, chord_len)     # length of a dot (in chord units)
            gap_ratio = 1.8                          # gap ~1.8x segment -> clear dots
        elif style == "dashdot":
            seg_len = 0.05 * max(1.0, chord_len)
            gap_ratio = 0.9
        else:  # dashed
            seg_len = 0.06 * max(1.0, chord_len)
            gap_ratio = 0.7

        # Number of dashes; clamp for stability
        step = seg_len * (1.0 + gap_ratio)
        n = max(6, int(np.ceil(chord_len / max(1e-6, step))))
        # How much of each cycle is "ink"
        fill = seg_len / max(1e-6, step)             # (0,1)

        # Build tiny solid segments and color each by the gradient at its midpoint
        seg_points = []
        seg_colors = []

        c0 = np.array(to_rgba(color_start))
        c1 = np.array(to_rgba(color_end))

        for i in range(n):
            t0 = i / n
            t1 = min(t0 + fill / n, 1.0)             # shorten to leave a gap
            if t1 <= t0:
                continue

            xm0, ym0 = _interp_xy(t0)
            xm1, ym1 = _interp_xy(t1)
            th0, r0 = _xy_to_polar(xm0, ym0)
            th1, r1 = _xy_to_polar(xm1, ym1)
            seg_points.append([[th0, r0], [th1, r1]])

            tm = 0.5 * (t0 + t1)
            rgba = (1.0 - tm) * c0 + tm * c1
            seg_colors.append(tuple(rgba))

        if not seg_points:
            return

        lc = LineCollection(
            np.array(seg_points),
            colors=seg_colors,
            linewidth=linewidth,
            linestyle="solid",           # each short segment is solid; spacing makes the pattern
            capstyle="round",
            joinstyle="round",
        )
        ax.add_collection(lc)
        return

    # ---------- SOLID ----------
    # Build a single polyline; if colors differ, use a gradient LineCollection.
    steps = max(16, int(64 * chord_len))
    thetas, radii = _segment_points(theta1, theta2, radius=radius, steps=steps)

    if color_start == color_end:
        ax.plot(thetas, radii, color=color_start, linewidth=linewidth, linestyle="solid")
        return

    pts = np.column_stack([thetas, radii])
    segs = np.stack([pts[:-1], pts[1:]], axis=1)

    c0 = np.array(to_rgba(color_start))
    c1 = np.array(to_rgba(color_end))
    cols = [tuple((1.0 - t) * c0 + t * c1) for t in np.linspace(0, 1, len(segs))]

    lc = LineCollection(segs, colors=cols, linewidth=linewidth)
    lc.set_linestyle("solid")
    lc.set_capstyle("round")
    lc.set_joinstyle("round")
    ax.add_collection(lc)


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
	unknown_time = bool(
		st.session_state.get("chart_unknown_time")
		or st.session_state.get("profile_unknown_time")
	)

	date_line = f"{month} {day}, {year}".strip()

	if unknown_time:
		# Desired render order:
		# Line 1: AC = Aries 0° (default)
		# Line 2: date_line
		# Line 3: 12:00 PM
		extra_line = ""
		date_line  = "AC = Aries 0° (default)"
		time_line  = f"{month} {day}, {year}".strip()
		city       = "12:00 PM"
	else:
		extra_line = ""
		time_line = ""
		if hour is not None and minute is not None:
			h = int(hour)
			m = int(minute)
			ampm = "AM" if h < 12 else "PM"
			h12 = 12 if (h % 12 == 0) else (h % 12)
			time_line = f"{h12}:{m:02d} {ampm}"

	return name, date_line, time_line, city, extra_line

import matplotlib.patheffects as pe

def _draw_header_on_figure(fig, name, date_line, time_line, city, extra_line, dark_mode):
	"""Paint header in the figure margin (top-left), with extra_line on same line as name (non-bold)."""
	import matplotlib.patheffects as pe

	color  = "white" if dark_mode else "black"
	stroke = "black" if dark_mode else "white"
	effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

	y0 = 0.99   # top margin in figure coords
	x0 = 0.00   # left margin

	# 1) Bold chart name (left)
	name_text = fig.text(
		x0, y0, name,
		ha="left", va="top",
		fontsize=12, fontweight="bold",
		color=color, path_effects=effects
	)

	# 2) Optional extra line on SAME TOP LINE, normal size, right after name
	if extra_line:
		# Force a draw so we can measure the name's pixel width reliably
		fig.canvas.draw()
		renderer = fig.canvas.get_renderer()

		name_bbox = name_text.get_window_extent(renderer=renderer)
		fig_bbox  = fig.get_window_extent(renderer=renderer)

		# Convert the name's pixel width to figure-coordinate width
		dx = name_bbox.width / fig_bbox.width

		# Small horizontal padding in figure coords
		pad = 0.01

		fig.text(
			x0 + dx + pad, y0, extra_line,
			ha="left", va="top",
			fontsize=9, fontweight=None,
			color=color, path_effects=effects
		)

	# 3) Stack the remaining lines below
	lines = []
	if date_line:
		lines.append(date_line)
	if time_line:
		lines.append(time_line)
	if city:
		lines.append(city)

	for idx, line in enumerate(lines, start=1):
		fig.text(
			x0,
			y0 - 0.035 * idx,
			line,
			ha="left",
			va="top",
			fontsize=9,
			color=color,
			path_effects=effects,
		)


def _draw_moon_phase_on_axes(ax, df, dark_mode: bool, icon_frac: float = 0.10) -> None:
	"""
	Draw the chart-based moon phase (icon + label) INSIDE the main chart axes,
	anchored at the upper-right corner. This does NOT change the figure/frame size.
	icon_frac = width/height of inset as a fraction of the parent axes.
	"""
	try:
		if df is None or "Object" not in df or "Longitude" not in df:
			return

		sun_row  = df[df["Object"].astype(str).str.lower() == "sun"].head(1)
		moon_row = df[df["Object"].astype(str).str.lower() == "moon"].head(1)
		if sun_row.empty or moon_row.empty:
			return

		sun_lon  = float(sun_row["Longitude"].iloc[0]) % 360.0
		moon_lon = float(moon_row["Longitude"].iloc[0]) % 360.0

		# Reuse your existing mapping to get label + PNG path
		label, icon_path = _moon_phase_label_emoji(sun_lon, moon_lon, emoji_size_px=None)
		if not os.path.exists(icon_path):
			return

		# --- ICON inset inside the axes (upper-right) ---
		icon_ax = inset_axes(
			ax,
			width=f"{int(icon_frac * 100)}%",
			height=f"{int(icon_frac * 100)}%",
			loc="upper right",
			bbox_to_anchor=(0.0, 0.075, 1.0, 1.0),   # <<< push the icon a bit DOWN
			bbox_transform=ax.transAxes,
			borderpad=0.0,
		)

		icon_ax.set_axis_off()
		try:
			img = mpimg.imread(icon_path)
			icon_ax.imshow(img)
		except Exception:
			pass

		# --- LABEL just to the left of the icon (still inside axes) ---
		import matplotlib.patheffects as pe
		color  = "white" if dark_mode else "black"
		stroke = "black" if dark_mode else "white"
		effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

		ax.text(
			0.89, 1.078, label,                 # <<< y almost at 1.0 (top); x near right edge
			transform=ax.transAxes,
			ha="right", va="top",
			fontsize=10, color=color, path_effects=effects, zorder=10,
		)

	except Exception:
		# decorative only; fail silently
		return

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

# Import ASPECTS from lookup_v2 - use the same source as test_calc_v2.py
try:
	from lookup_v2 import ASPECTS
except ImportError:
	ASPECTS = {
		"Conjunction": {"angle": 0, "orb": 3, "color": "#888888", "style": "solid"},
		"Sextile": {"angle": 60, "orb": 3, "color": "#6321CE", "style": "solid"},
		"Square": {"angle": 90, "orb": 3, "color": "#F70000", "style": "solid"},
		"Trine": {"angle": 120, "orb": 3, "color": "#0011FF", "style": "solid"},
		"Sesquisquare": {"angle": 135, "orb": 2, "color": "#FF5100", "style": "dotted"},
		"Quincunx": {"angle": 150, "orb": 3, "color": "#439400", "style": "dotted"},
		"Opposition": {"angle": 180, "orb": 3, "color": "#F70000", "style": "solid"},
		"Semisextile": {"angle": 30, "orb": 2, "color": "#C51DA1", "style": "dotted"},
	}

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
		"#AED581", "#FFD54F", "#C77700", "#A1887F",
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
	label_frac: float = 0.9,
	*,
	draw_lines: bool = True,
	draw_labels: bool = True,
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

	print("HOUSE CUSPS:", "dark_mode =", dark_mode, "draw_lines =", draw_lines)

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

	if draw_lines:
		line_color = "#A0A0A0" if not dark_mode else "#333333"
		for deg in cusps:
			rad = deg_to_rad(deg, asc_deg)
			ax.plot(
				[rad, rad],
				[0, 1.45],  # full radius of the wheel
				color=line_color,
				linestyle="solid",
				linewidth=1.2,
				zorder=0.5,  # slightly above background, but below zodiac bars (which are zorder=0)
				solid_capstyle="butt",
				antialiased=True,
			)

	if draw_labels:
		lbl_color = "white" if dark_mode else "black"
		for i in range(12):
			a = cusps[i]
			b = cusps[(i + 1) % 12]
			span = (b - a) % 360.0
			label_deg = (a + span * label_frac) % 360.0
			label_rad = deg_to_rad(label_deg, asc_deg)
			ax.text(
				label_rad,
				label_r,
				str(i + 1),
				ha="center",
				va="center",
				fontsize=8,
				color=lbl_color,
				zorder=100,
			)

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

def draw_zodiac_signs(ax, asc_deg, dark_mode):
    """Draw zodiac wheel with colored element bands and zodiac glyphs."""

    # --- Define element colors based on dark_mode ---
    if dark_mode:
        PASTEL_BLUE   = "#1567A5FF"  # blue
        PASTEL_GREEN  = "#366E21FF"  # green
        PASTEL_ORANGE = "#946D19FF"  # orange
        PASTEL_RED    = "#6D2424FF"  # soft red/pink
    else:
        PASTEL_BLUE   = "#6D9EC4FF"  # blue
        PASTEL_GREEN  = "#7CAF6AFF"  # green
        PASTEL_ORANGE = "#D8B873FF"  # orange
        PASTEL_RED    = "#CE7878FF"  # soft red/pink

    # --- Constants that are always needed ---
    element_color = {
        "fire":  PASTEL_BLUE,
        "earth": PASTEL_RED,
        "air":   PASTEL_GREEN,
        "water": PASTEL_ORANGE,
    }
    elements = ["fire", "earth", "air", "water"] * 3
    sector_width = np.deg2rad(30)  # each zodiac occupies 30 degrees

    ring_inner, ring_outer = 1.45, 1.58
    divider_inner, divider_outer = 1.457, 1.573

    # --- Draw colored element bands ---
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

    # --- Draw zodiac glyphs ---
    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)
        ax.text(
            rad, 1.50, ZODIAC_SIGNS[i],
            ha="center", va="center",
            fontsize=16, fontweight="bold",
            color=ZODIAC_COLORS[i],
            zorder=1,
        )

    # --- Draw dividers for each house cusp ---
    asc_sign_start = int(asc_deg // 30) * 30.0
    cusps = [(asc_sign_start + i * 30.0) % 360.0 for i in range(12)]
    for deg in cusps:
        rad = deg_to_rad(deg, asc_deg)
        ax.plot([rad, rad], [divider_inner, divider_outer],
                color="black", linestyle="solid", linewidth=1, zorder=5)


def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode, df=None):
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

	# Helper to check retrograde status
	def is_retrograde(obj_name):
		if df is None or "Object" not in df or "Speed" not in df:
			return False
		try:
			canon_name = _canonical_name(obj_name)
			for _, row in df.iterrows():
				row_canon = _canonical_name(str(row.get("Object", "")))
				if row_canon == canon_name:
					speed = row.get("Speed")
					if speed is not None and float(speed) < 0:
						return True
			return False
		except Exception:
			return False

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
			
			# Add retrograde indicator
			if is_retrograde(name):
				deg_label += " Rx"

			ax.text(rad_true, 1.35, label, ha="center", va="center", fontsize=9, color=color)
			ax.text(rad_true, 1.27, deg_label, ha="center", va="center", fontsize=6, color=color)

def draw_filament_lines(
	ax,
	pos,
	filaments,
	active_patterns,
	asc_deg,
	drawn_keys: set[tuple[frozenset[str], str]] | None = None,
):
	"""Draw dotted gradient lines for active filament (minor) connections."""

	edges: list[tuple[tuple[str, str], str]] = []
	single_pattern_mode = len(active_patterns) == 1

	for p1, p2, asp_name, pat1, pat2 in filaments:
		if pat1 not in active_patterns or pat2 not in active_patterns:
			continue
		# Internal minors (pat1 == pat2) are handled in draw_minor_edges for each circuit.
		if pat1 == pat2:
			continue
		if single_pattern_mode and pat1 != pat2:
			continue
		if p1 not in pos or p2 not in pos:
			continue
		edges.append(((p1, p2), asp_name))

	if not edges:
		return []

	return draw_minor_edges(
		ax,
		pos,
		edges,
		asc_deg,
		linewidth_minor=1.0,
		drawn_keys=drawn_keys,
	)

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
def _resolve_aspect(aspect: Any) -> tuple[str, bool, Mapping[str, Any]]:
	"""Return (canon_name, is_approx, spec) with case-insensitive lookup."""
	name, approx = _normalise_aspect(aspect)
	if not name:
		return "", approx, {}
	# case-insensitive match against ASPECTS keys
	for k in ASPECTS.keys():
		if k.lower() == name.lower():
			return k, approx, ASPECTS[k]
	return name, approx, {}  # unknown aspect -> empty spec

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

def draw_aspect_lines(
	ax,
	pos,
	edges,
	asc_deg,
	visible_canon=None,
	linewidth_major=2.0,
	color_override: str | None = None,
	drawn_keys: set[tuple[frozenset[str], str]] | None = None,
	radius: float = 1.0,
):    
	drawn = []
	if not edges:
		return drawn

	if drawn_keys is None:
		drawn_keys = set()

	for record in edges:
		a, b, aspect = _edge_record_to_components(record)
		if not a or not b or not aspect:
			continue

		canon_a = _canonical_name(a); canon_b = _canonical_name(b)
		if visible_canon is not None and (canon_a not in visible_canon or canon_b not in visible_canon):
			continue

		canon_aspect, is_approx, spec = _resolve_aspect(aspect)
		if not canon_aspect:
			continue

		key = (frozenset((canon_a, canon_b)), canon_aspect)
		if key in drawn_keys:
			continue

		d1 = pos.get(a); d2 = pos.get(b)
		if d1 is None or d2 is None:
			continue

		r1 = deg_to_rad(d1, asc_deg); r2 = deg_to_rad(d2, asc_deg)

		base_color = color_override or spec.get("color", "gray")
		if is_approx:
			base_color = _lighten_color(base_color, blend=0.35)

		style = spec.get("style", "solid")   # quincunx/sesquisquare -> dotted from table
		lw = linewidth_major if canon_aspect not in ("Quincunx", "Sesquisquare") else 1.0

		light_color = _light_variant_for(base_color)
		if is_approx:
			light_color = _lighten_color(light_color, blend=0.35)

		start_color = base_color if _is_luminary_or_planet(a) else light_color
		end_color   = base_color if _is_luminary_or_planet(b) else light_color

		_draw_gradient_line(ax, r1, r2, start_color, end_color, lw, style, radius=radius)
		drawn_keys.add(key)
		drawn.append((a, b, str(canon_aspect) + ("_approx" if is_approx else "")))

	return drawn


def draw_minor_edges(
	ax,
	pos,
	edges,
	asc_deg,
	visible_canon=None,
	linewidth_minor=1.0,
	color_override: str | None = None,
	drawn_keys: set[tuple[frozenset[str], str]] | None = None,
	radius: float = 1.0,
):
	drawn: list[tuple[str, str, str]] = []
	if not edges:
		return drawn

	if drawn_keys is None:
		drawn_keys = set()

	for record in edges:
		a, b, aspect = _edge_record_to_components(record)
		if not a or not b or not aspect:
			continue
		canon_a = _canonical_name(a); canon_b = _canonical_name(b)
		if visible_canon is not None and (canon_a not in visible_canon or canon_b not in visible_canon):
			continue

		canon_aspect, _is_approx, spec = _resolve_aspect(aspect)
		if not canon_aspect:
			continue

		key = (frozenset((canon_a, canon_b)), canon_aspect)
		if key in drawn_keys:
			continue

		d1 = pos.get(a); d2 = pos.get(b)
		if d1 is None or d2 is None:
			continue

		r1 = deg_to_rad(d1, asc_deg); r2 = deg_to_rad(d2, asc_deg)
		base_color = color_override or spec.get("color", "gray")
		light_color = _light_variant_for(base_color)
		start_color = base_color if _is_luminary_or_planet(a) else light_color
		end_color   = base_color if _is_luminary_or_planet(b) else light_color

		_draw_gradient_line(ax, r1, r2, start_color, end_color, linewidth_minor, "dotted", radius=radius)
		drawn_keys.add(key)
		drawn.append((a, b, canon_aspect))

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
	include_axes: bool = True,
) -> None:
	"""Draw the compass overlay, optionally suppressing horizon/meridian axes."""
	if colors is None:
		colors = {"nodal": "purple", "acdc": "#4E83AF", "mcic": "#4E83AF"}

	def _get_deg(label: str) -> float | None:
		deg = _degree_for_label(pos, label)
		if deg is not None:
			return deg
		for alias in _COMPASS_ALIAS_MAP.get(label, []):
			if alias == label:
				continue
			alias_deg = _degree_for_label(pos, alias)
			if alias_deg is not None:
				return alias_deg
		return None

	sn = _degree_for_label(pos, "South Node")
	nn = _degree_for_label(pos, "North Node")
	if sn is None or nn is None:
		return
	
	z_axes = zorder + 1
	z_nodal_line = zorder + 2
	z_nodal_top = zorder + 3

	if include_axes:
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

	sn_rad = deg_to_rad(sn, asc_deg)
	nn_rad = deg_to_rad(nn, asc_deg)
	x1, y1 = math.cos(sn_rad) * 1.0, math.sin(sn_rad) * 1.0
	x2, y2 = math.cos(nn_rad) * 1.0, math.sin(nn_rad) * 1.0
	vx, vy = (x2 - x1), (y2 - y1)
	head_trim_frac = 0.05
	x2_trim = x2 - head_trim_frac * vx
	y2_trim = y2 - head_trim_frac * vy
	r2_trim_theta = math.atan2(y2_trim, x2_trim)
	r2_trim_rad = math.hypot(x2_trim, y2_trim)

	ax.plot(
		[sn_rad, r2_trim_theta],
		[1.0, r2_trim_rad],
		color=colors.get("nodal", "purple"),
		linewidth=linewidth_base * nodal_width_multiplier,
		zorder=z_nodal_line,
	)
	ax.annotate(
		"",
		xy=(nn_rad, 1.0),
		xytext=(sn_rad, 1.0),
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
	ax.plot(
		[sn_rad],
		[1.0],
		marker="o",
		markersize=sn_dot_markersize,
		color=colors.get("nodal", "purple"),
		zorder=z_nodal_top,
	)

def _get_profile_lat_lon() -> tuple[float | None, float | None]:
	"""Pull chart/birth lat/lon from session_state."""
	SS = st.session_state

	def f(x):
		try:
			return float(x)
		except Exception:
			return None

	# Highest priority: current chart lookup (city geocode)
	lat = f(SS.get("chart_lat"))
	lon = f(SS.get("chart_lon"))

	# If not present, fall back to stored birth coords
	if lat is None or lon is None:
		lat = f(SS.get("birth_lat"))
		lon = f(SS.get("birth_lon"))

	# If still missing, report unknown
	if lat is None or lon is None:
		return None, None
	return lat, lon

def _earth_emoji_for_region(lat: float | None, lon: float | None) -> str:
	"""
	Region mapping requested:
	  - Africa, Europe, Middle East: 🌍
	  - The Americas: 🌎
	  - Asia and Australia: 🌏
	  - Any other obscure locations: 🌎
	  - Unknown chart location: 🌐
	"""
	if lat is None or lon is None:
		# If location isn’t known yet, reserve the 'unknown' globe
		return "🌐"

	# Normalize longitude to [-180, 180]
	try:
		lon = ((lon + 180.0) % 360.0) - 180.0
	except Exception:
		return "🌎"

	# Coarse, readable bands by longitude:
	# Americas: roughly [-170, -30]
	if -170.0 <= lon <= -30.0:
		return "🌎"  # Americas

	# Europe / Africa / Middle East: roughly [-30, +60]
	if -30.0 < lon <= 60.0:
		return "🌍"

	# Asia / Australia: roughly (+60, +180]
	if 60.0 < lon <= 180.0:
		return "🌏"

	# Wraparound edge cases (e.g., extreme Pacific longitudes near -180/+180)
	# Treat as Asia/Australia band first; if you prefer Americas, swap this.
	if lon < -170.0 or lon > 180.0:
		return "🌏"

	# Fallback for anything weird/obscure
	return "🌎"

def draw_center_earth(ax, *, size: float = 0.22, zorder: int = 10_000) -> None:
	"""
	Draw a region-appropriate Earth PNG at the chart center.
	"""
	lat, lon = _get_profile_lat_lon()
	emoji = _earth_emoji_for_region(lat, lon)

	# Map emoji → filename
	mapping = {
		"🌍": "earth_africa.png",
		"🌎": "earth_americas.png",
		"🌏": "earth_asia.png",
		"🌐": "earth_unknown.png",
	}
	fname = mapping.get(emoji, "earth_unknown.png")

	# Your folder: Rosetta_v2/pngs/<files>
	img_path = os.path.join(os.path.dirname(__file__), "pngs", fname)
	if not os.path.exists(img_path):
		return  # fail gracefully if file missing

	arr_img = mpimg.imread(img_path)
	imagebox = OffsetImage(arr_img, zoom=size)
	ab = AnnotationBbox(imagebox, (0, 0), frameon=False, zorder=zorder)
	ax.add_artist(ab)

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
	unknown_time_chart = bool(
		st.session_state.get("chart_unknown_time")
		or st.session_state.get("profile_unknown_time")
	)
	asc_deg = get_ascendant_degree(df)
	if unknown_time_chart:
		asc_deg = 0.0
	visible_names = resolve_visible_objects(visible_toggle_state, df)
	positions = extract_positions(df, visible_names)
	visible_canon = _expand_visible_canon(visible_names)

	fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"})
	if dark_mode:
		ax.set_facecolor("black")
		fig.patch.set_facecolor("black")

	ax.set_theta_zero_location("N")
	ax.set_theta_direction(-1)
	ax.set_rlim(0, 1.60)  # Match render_chart_with_shapes
	ax.axis("off")

	# Center and fill - match render_chart_with_shapes
	ax.set_anchor("C")
	ax.set_aspect("equal", adjustable="box")
	fig.subplots_adjust(left=0, right=0.85, top=0.95, bottom=0.05)

	# Header and moon phase
	try:
		name, date_line, time_line, city, extra_line = _current_chart_header_lines()
		_draw_header_on_figure(fig, name, date_line, time_line, city, extra_line, dark_mode)
		_draw_moon_phase_on_axes(ax, df, dark_mode, icon_frac=0.10)
	except Exception:
		pass

	cusps: list[float] = []
	if not unknown_time_chart:
		cusps = draw_house_cusps(ax, df, asc_deg, house_system, dark_mode)
	if degree_markers:
		draw_degree_markers(ax, asc_deg, dark_mode)
	if zodiac_labels:
		draw_zodiac_signs(ax, asc_deg, dark_mode)

	draw_planet_labels(ax, positions, asc_deg, label_style=label_style, dark_mode=dark_mode, df=df)

	edge_keys: set[tuple[frozenset[str], str]] = set()

	major_edges_drawn = draw_aspect_lines(
		ax,
		positions,
		edges_major or [],
		asc_deg,
		visible_canon=visible_canon,
		linewidth_major=2.0,
		drawn_keys=edge_keys,
	)
	minor_edges_drawn = draw_minor_edges(
		ax,
		positions,
		edges_minor or [],
		asc_deg,
		visible_canon=visible_canon,
		linewidth_minor=1.0,
		drawn_keys=edge_keys,
	)

	if compass_on:
		compass_positions = extract_compass_positions(df, visible_names)
		draw_compass_rose(
			ax,
			compass_positions,
			asc_deg,
			include_axes=not unknown_time_chart,
		)
	
	draw_center_earth(ax)

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
	unknown_time_chart = bool(
		st.session_state.get("chart_unknown_time")
		or st.session_state.get("profile_unknown_time")
	)
	asc_deg = get_ascendant_degree(df)
	if unknown_time_chart:
		asc_deg = 0.0
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
		name, date_line, time_line, city, extra_line = _current_chart_header_lines()  # type: ignore
		_draw_header_on_figure(fig, name, date_line, time_line, city, extra_line, dark_mode)  # type: ignore
		_draw_moon_phase_on_axes(ax, df, dark_mode, icon_frac=0.10)
	except Exception:
		pass

	# Base wheel
	cusps: list[float] = []
	if not unknown_time_chart:
		cusps = draw_house_cusps(ax, df, asc_deg, house_system, dark_mode)
	draw_degree_markers(ax, asc_deg, dark_mode)
	draw_zodiac_signs(ax, asc_deg, dark_mode)
	draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode, df=df)

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
	edge_keys: set[tuple[frozenset[str], str]] = set()

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
			draw_aspect_lines(
				ax,
				pos,
				edges,
				asc_deg,
				color_override=color,
				drawn_keys=edge_keys,
			)

			for (p1, p2), asp in edges:
				_add_edge(p1, asp, p2)

			# internal minors for this circuit in same color
			internal_minors = [((p1, p2), asp_name)
							for (p1, p2, asp_name, pat1, pat2) in filaments
							if pat1 == idx and pat2 == idx]
			draw_minor_edges(
				ax,
				pos,
				internal_minors,
				asc_deg,
				color_override=color,
				drawn_keys=edge_keys,
			)
			
			for (p1, p2), asp in internal_minors:
				_add_edge(p1, asp, p2)

	# Inter-parent filaments (dotted connectors)
	if active_parents:
		draw_filament_lines(
			ax,
			pos,
			filaments,
			active_parents,
			asc_deg,
			drawn_keys=edge_keys,
		)
		for (p1, p2, asp_name, pat1, pat2) in filaments:
			if pat1 == pat2:
				continue
			if pat1 in active_parents and pat2 in active_parents and frozenset((p1, p2)) not in shape_edges:
				_add_edge(p1, asp_name, p2)

	# Sub-shapes edges
	for s in active_shapes:
		visible_objects.update(s["members"])
		color = shape_color_for(s["id"]) if layered_mode else None
		draw_aspect_lines(
			ax,
			pos,
			s["edges"],
			asc_deg,
			color_override=color,
			drawn_keys=edge_keys,
		)
		for (p1, p2), asp in s["edges"]:
			_add_edge(p1, asp, p2)

	# Singletons
	visible_objects.update(active_singletons)
	if active_singletons:
		draw_singleton_dots(ax, pos, active_singletons, shape_edges, asc_deg, line_width=2.0)

	# Compass
	if st.session_state.get("ui_compass_overlay", True):
		compass_positions = extract_compass_positions(df)
		compass_source = compass_positions or pos
		draw_compass_rose(
			ax,
			compass_source,
			asc_deg,
			colors={"nodal": "purple"},
			linewidth_base=2.0,
			zorder=100,
			arrow_mutation_scale=22.0,
			nodal_width_multiplier=2.0,
			sn_dot_markersize=12.0,
			include_axes=not unknown_time_chart,
		)
		visible_objects.update({"North Node", "South Node"})
		if not unknown_time_chart:
			visible_objects.update({"Ascendant", "Descendant", "MC", "IC"})
		for names in (
			_COMPASS_ALIAS_MAP["North Node"],
			_COMPASS_ALIAS_MAP["South Node"],
		):
			row = _find_row(df, names)
			if row is not None:
				obj_name = str(row.get("Object"))
				if obj_name:
					visible_objects.add(obj_name)

		sn = _degree_for_label(compass_source, "South Node")
		nn = _degree_for_label(compass_source, "North Node")
		if sn is not None and nn is not None:            
			_add_edge("South Node", "Opposition", "North Node")
		if not unknown_time_chart:
			ac = _degree_for_label(compass_source, "Ascendant")
			dc = _degree_for_label(compass_source, "Descendant")
			if ac is not None and dc is not None:
				_add_edge("Ascendant", "Opposition", "Descendant")
			mc = _degree_for_label(compass_source, "MC")
			ic = _degree_for_label(compass_source, "IC")
			if mc is not None and ic is not None:
				_add_edge("MC", "Opposition", "IC")

	draw_center_earth(ax)

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

# ---------------------------------------------------------------------------
# Bi-wheel (synastry/transit) renderer
# ---------------------------------------------------------------------------

def render_biwheel_chart(
	df_inner: pd.DataFrame,
	df_outer: pd.DataFrame,
	*,
	edges_inter_chart: Sequence[Any] | None = None,
	house_system: str = "placidus",
	dark_mode: bool = False,
	label_style: str = "glyph",
	figsize: tuple[float, float] = (6.0, 6.0),
	dpi: int = 144,
):
	"""
	Render a bi-wheel chart with two concentric rings:
	- Inner chart: df_inner (between the two degree circles)
	- Outer chart: df_outer (outside the outer degree circle)
	- edges_inter_chart: Aspects between inner and outer chart planets
	"""
	# Get ascendant for inner chart (rotation reference)
	unknown_time_inner = bool(
		st.session_state.get("chart_unknown_time")
		or st.session_state.get("profile_unknown_time")
	)
	asc_deg_inner = get_ascendant_degree(df_inner)
	if unknown_time_inner:
		asc_deg_inner = 0.0

	# Extract positions for both charts
	pos_inner = extract_positions(df_inner)
	pos_outer = extract_positions(df_outer)

	# Setup figure
	fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"})
	if dark_mode:
		ax.set_facecolor("black")
		fig.patch.set_facecolor("black")

	ax.set_theta_zero_location("N")
	ax.set_theta_direction(-1)
	ax.set_rlim(0, 1.70)  # Slightly larger to accommodate outer ring
	ax.axis("off")
	ax.set_anchor("C")
	ax.set_aspect("equal", adjustable="box")
	fig.subplots_adjust(left=0, right=0.85, top=0.95, bottom=0.05)

	# Draw zodiac signs (outermost ring - unchanged)
	draw_zodiac_signs(ax, asc_deg_inner, dark_mode)

	# --- KEY RADIUS CONTROLS FOR BIWHEEL LAYOUT ---
	# Adjust these values independently to control spacing:
	
	# Degree circles (the black rings with tick marks):
	INNER_CIRCLE_R = 0.9     # Inner degree circle (fixed)
	OUTER_CIRCLE_R = 1.2     # Outer degree circle (move this to adjust circle position)
	
	# Planet label positions (independent from circles):
	INNER_LABEL_R = 1.1      # Inner chart planet glyphs
	INNER_DEGREE_R = 1.0     # Inner chart degree numbers
	OUTER_LABEL_R = 1.4      # Outer chart planet glyphs (adjust if overlapping circle)
	OUTER_DEGREE_R = 1.31     # Outer chart degree numbers
	
	# House cusp zones:
	OUTER_CUSP_R = 1.45       # Where outer house cusps end (before zodiac)

	# Draw TWO degree marker circles
	base_color = "white" if dark_mode else "black"
	
	# Inner degree circle
	circle_inner = plt.Circle((0, 0), INNER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_inner)
	
	# Draw ticks on inner circle
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_inner)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_inner)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_inner)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Outer degree circle
	circle_outer = plt.Circle((0, 0), OUTER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_outer)
	
	# Draw ticks on outer circle
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_inner)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_inner)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_inner)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Draw inner chart house cusps (between inner and outer circles)
	if not unknown_time_inner:
		cusps_inner = draw_house_cusps_biwheel(
			ax, df_inner, asc_deg_inner, house_system, dark_mode,
			r_inner=INNER_CIRCLE_R, r_outer=OUTER_CIRCLE_R, draw_labels=True, label_frac=0.50
		)
	else:
		cusps_inner = []

	# Draw outer chart house cusps (between outer circle and zodiac)
	unknown_time_outer = False  # For now, assume outer chart has time
	asc_deg_outer = get_ascendant_degree(df_outer)
	if not unknown_time_outer:
		cusps_outer = draw_house_cusps_biwheel(
			ax, df_outer, asc_deg_inner, house_system, dark_mode,
			r_inner=OUTER_CIRCLE_R, r_outer=OUTER_CUSP_R, draw_labels=True, label_frac=0.50
		)
	else:
		cusps_outer = []

	# Draw planet labels for inner chart (between the circles)
	draw_planet_labels_biwheel(
		ax, pos_inner, asc_deg_inner, label_style, dark_mode, df_inner,
		label_r=INNER_LABEL_R, degree_r=INNER_DEGREE_R
	)

	# Draw planet labels for outer chart (outside outer circle)
	draw_planet_labels_biwheel(
		ax, pos_outer, asc_deg_inner, label_style, dark_mode, df_outer,
		label_r=OUTER_LABEL_R, degree_r=OUTER_DEGREE_R
	)

	# Draw inter-chart aspects (between inner and outer wheels)
	if edges_inter_chart:
		# DON'T combine positions - inner and outer planets have same names!
		# We need to look them up separately based on which chart they're from
		edge_keys: set[tuple[frozenset[str], str]] = set()
		
		for record in edges_inter_chart:
			if isinstance(record, (list, tuple)) and len(record) == 3:
				p1, p2, aspect = record
			else:
				continue
			
			# p1 is from inner chart, p2 is from outer chart
			d1 = pos_inner.get(p1)
			d2 = pos_outer.get(p2)
			
			if d1 is None or d2 is None:
				continue
			
			# Resolve aspect colors/styles
			canon_aspect, is_approx, spec = _resolve_aspect(aspect)
			if not canon_aspect:
				continue
			
			r1 = deg_to_rad(d1, asc_deg_inner)
			r2 = deg_to_rad(d2, asc_deg_inner)
			
			base_color = spec.get("color", "gray")
			if is_approx:
				base_color = _lighten_color(base_color, blend=0.35)
			
			style = spec.get("style", "solid")
			lw = 2.0 if canon_aspect not in ("Quincunx", "Sesquisquare") else 1.0
			
			light_color = _light_variant_for(base_color)
			if is_approx:
				light_color = _lighten_color(light_color, blend=0.35)
			
			start_color = base_color if _is_luminary_or_planet(p1) else light_color
			end_color   = base_color if _is_luminary_or_planet(p2) else light_color
			
			_draw_gradient_line(ax, r1, r2, start_color, end_color, lw, style, radius=INNER_CIRCLE_R)

	# Draw center earth
	draw_center_earth(ax, size=0.18)

	return RenderResult(
		fig=fig,
		ax=ax,
		positions=pos_inner,  # Return inner positions as primary
		cusps=cusps_inner,
		visible_objects=sorted(pos_inner.keys()),
		drawn_major_edges=[],
		drawn_minor_edges=[],
	)

# Helper functions for biwheel

def draw_house_cusps_biwheel(
	ax, df, asc_deg, house_system, dark_mode,
	r_inner, r_outer, draw_labels=False, label_frac=0.50
):
	"""Draw house cusps between two radii for biwheel charts."""
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

	# Draw cusp lines
	line_color = "#A0A0A0" if not dark_mode else "#333333"
	for deg in cusps:
		rad = deg_to_rad(deg, asc_deg)
		ax.plot(
			[rad, rad],
			[r_inner, r_outer],
			color=line_color,
			linestyle="solid",
			linewidth=1.0,
			zorder=0.5,
			solid_capstyle="butt",
			antialiased=True,
		)

	# Draw house number labels if requested
	if draw_labels:
		# Use gray color matching house cusp lines for biwheel
		lbl_color = "#A0A0A0" if not dark_mode else "#333333"
		# Position labels just inside the outer radius, closer to cusp lines
		label_r = r_outer - 0.05
		# Angle offset in degrees - adjust this to rotate labels around the circle
		angle_offset = -13  # positive = clockwise, negative = counter-clockwise
		for i in range(12):
			a = cusps[i]
			b = cusps[(i + 1) % 12]
			span = (b - a) % 360.0
			label_deg = (a + span * label_frac + angle_offset) % 360.0
			label_rad = deg_to_rad(label_deg, asc_deg)
			ax.text(
				label_rad,
				label_r,
				str(i + 1),
				ha="center",
				va="center",
				fontsize=8,
				color=lbl_color,
				zorder=0.5,
			)

	return cusps

def draw_planet_labels_biwheel(
	ax, pos, asc_deg, label_style, dark_mode, df,
	label_r, degree_r
):
	"""Draw planet labels at specified radius for biwheel charts."""
	if not pos:
		return

	degree_threshold = 3
	min_spacing = 7

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

	# Retrograde checker
	def is_retrograde(obj_name):
		if df is None or "Object" not in df or "Speed" not in df:
			return False
		try:
			canon_name = _canonical_name(obj_name)
			for _, row in df.iterrows():
				row_canon = _canonical_name(str(row.get("Object", "")))
				if row_canon == canon_name:
					speed = row.get("Speed")
					if speed is not None and float(speed) < 0:
						return True
			return False
		except Exception:
			return False

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
			
			if is_retrograde(name):
				deg_label += " Rx"

			ax.text(rad_true, label_r, label, ha="center", va="center", fontsize=9, color=color)
			ax.text(rad_true, degree_r, deg_label, ha="center", va="center", fontsize=6, color=color)

__all__ = [
	"RenderResult",
	"render_chart",
	"render_chart_with_shapes",
	"render_biwheel_chart",
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

