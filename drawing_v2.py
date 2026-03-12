from __future__ import annotations
import re, math
import numpy as np
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import data_helpers as _dh
from dataclasses import dataclass
from typing import Any, Collection, Iterable, Mapping, Sequence, List, Dict, Optional
from models_v2 import static_db

# migrate legacy constants to module namespace for backwards compatibility
SYNASTRY_COLORS_1 = static_db.SYNASTRY_COLORS_1
SYNASTRY_COLORS_2 = static_db.SYNASTRY_COLORS_2
ZODIAC_SIGNS = static_db.ZODIAC_SIGNS
ZODIAC_COLORS = static_db.ZODIAC_COLORS
ASPECTS = static_db.ASPECTS
GROUP_COLORS = static_db.GROUP_COLORS
SUBSHAPE_COLORS = static_db.SUBSHAPE_COLORS
LUMINARIES_AND_PLANETS = static_db.LUMINARIES_AND_PLANETS
GLYPHS = static_db.GLYPHS
from profiles_v2 import glyph_for
from patterns_v2 import detect_shapes
from src.ui_state_helpers import (
	_selected_house_system,
	reset_chart_state, resolve_visible_objects,
)
from src.drawing_primitives import (
	deg_to_rad, _draw_gradient_line, draw_center_earth, 
	_draw_header_on_figure, _draw_header_on_figure_right, _draw_moon_phase_on_axes, _light_variant_for,
	_lighten_color,
)
from data_helpers import (
	_degree_for_label,
	_COMPASS_ALIAS_MAP,
	_expand_visible_canon,
	_edge_record_to_components,
	_resolve_aspect,
	_is_luminary_or_planet,
	_canonical_name,
)
from models_v2 import AstrologicalChart
_cache_shapes = {}

def _object_map(chart: AstrologicalChart) -> dict[str, Any]:
	if chart is None:
		return {}
	return {obj.object_name.name: obj for obj in chart.objects if obj.object_name}

def _chart_positions(chart: AstrologicalChart, visible_names: Collection[str] | None = None) -> dict[str, float]:
	if chart is None:
		return {}
	visible_canon = _expand_visible_canon(visible_names)
	positions: dict[str, float] = {}
	for obj in chart.objects:
		if not obj.object_name:
			continue
		name = obj.object_name.name
		if visible_canon is not None and _canonical_name(name) not in visible_canon:
			continue
		try:
			positions[name] = float(obj.longitude)
		except Exception:
			continue
	return positions

def _chart_compass_positions(
	chart: AstrologicalChart,
	visible_names: Collection[str] | None = None,
) -> dict[str, float]:
	if chart is None:
		return {}
	visible_canon = _expand_visible_canon(visible_names)
	obj_map = _object_map(chart)
	out: dict[str, float] = {}
	for label, names in _COMPASS_ALIAS_MAP.items():
		for name in names:
			target = obj_map.get(name)
			if target is None:
				continue
			target_group = {_canonical_name(n) for n in names}
			if visible_canon is not None and target_group.isdisjoint(visible_canon):
				continue
			try:
				out[label] = float(target.longitude)
			except Exception:
				pass
			break
	return out

def _get_ascendant_degree(chart: AstrologicalChart) -> float:
	obj_map = _object_map(chart)
	for name in ("AC", "Ascendant", "Asc", "Ac"):
		obj = obj_map.get(name)
		if obj is None:
			continue
		try:
			return float(obj.longitude)
		except Exception:
			return 0.0
	return 0.0

# Backward-compatible wrappers (legacy dataframe usage)
def extract_positions(df: pd.DataFrame, visible_names: Collection[str] | None = None) -> dict[str, float]:
	return _dh.extract_positions(df, visible_names)

def get_ascendant_degree(df: pd.DataFrame) -> float:
	return _dh.get_ascendant_degree(df)
def get_shapes(pos, patterns, major_edges_all):
	pos_items_tuple = tuple(sorted(pos.items()))
	patterns_key = tuple(tuple(sorted(p)) for p in patterns)
	edges_tuple = tuple(major_edges_all)
	key = (pos_items_tuple, patterns_key, edges_tuple)
	if key not in _cache_shapes:
		_cache_shapes[key] = detect_shapes(pos, patterns, major_edges_all)
	return _cache_shapes[key]

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

def group_color_for(idx: int) -> str:
	"""Return a deterministic colour for the given circuit index."""

	if not GROUP_COLORS:
		return "teal"
	try:
		return GROUP_COLORS[idx % len(GROUP_COLORS)]
	except Exception:
		return "teal"


def draw_house_cusps(
	ax,
	chart: AstrologicalChart,
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

	cusps: list[float] = []
	if chart is not None:
		system_key = sys_key.replace(" ", "")
		cusp_rows = [
			c for c in chart.house_cusps
			if (c.house_system or "").strip().lower().replace(" ", "") == system_key
		]
		cusp_rows.sort(key=lambda c: c.cusp_number)
		cusps = [float(c.absolute_degree) for c in cusp_rows if c is not None]

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

def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode, chart: AstrologicalChart | None = None):
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
		if chart is None:
			return False
		try:
			target = _canonical_name(obj_name)
			for obj in chart.objects:
				if not obj.object_name:
					continue
				if _canonical_name(obj.object_name.name) == target:
					return bool(obj.retrograde)
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

# ---------------------------------------------------------------------------
# Aspect drawing (shared)
# ---------------------------------------------------------------------------

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

		canon_a = _dh._canonical_name(a); canon_b = _dh._canonical_name(b)
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
		canon_a = _dh._canonical_name(a); canon_b = _dh._canonical_name(b)
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
	radius: float = 1.0,
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
				[radius, radius],
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
				[radius, radius],
				color=colors.get("mcic", "#4E83AF"),
				linewidth=linewidth_base,
				zorder=z_axes,
			)

	sn_rad = deg_to_rad(sn, asc_deg)
	nn_rad = deg_to_rad(nn, asc_deg)
	x1, y1 = math.cos(sn_rad) * radius, math.sin(sn_rad) * radius
	x2, y2 = math.cos(nn_rad) * radius, math.sin(nn_rad) * radius
	vx, vy = (x2 - x1), (y2 - y1)
	head_trim_frac = 0.05
	x2_trim = x2 - head_trim_frac * vx
	y2_trim = y2 - head_trim_frac * vy
	r2_trim_theta = math.atan2(y2_trim, x2_trim)
	r2_trim_rad = math.hypot(x2_trim, y2_trim)

	ax.plot(
		[sn_rad, r2_trim_theta],
		[radius, r2_trim_rad],
		color=colors.get("nodal", "purple"),
		linewidth=linewidth_base * nodal_width_multiplier,
		zorder=z_nodal_line,
	)
	ax.annotate(
		"",
		xy=(nn_rad, radius),
		xytext=(sn_rad, radius),
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
		[radius],
		marker="o",
		markersize=sn_dot_markersize,
		color=colors.get("nodal", "purple"),
		zorder=z_nodal_top,
	)

# ---------------------------------------------------------------------------
# High-level renderer
# ---------------------------------------------------------------------------
@dataclass
class RenderResult:
	# Existing Chart Drawing Fields
	fig: Any
	ax: Any
	positions: dict[str, float]
	cusps: list[float]
	visible_objects: list[str]
	drawn_major_edges: list[tuple[str, str, str]]
	drawn_minor_edges: list[tuple[str, str, str]]
	
	# ⬇️ Optional fields with defaults ⬇️
	patterns: List[List[str]] = None
	shapes: List[Dict[str, Any]] = None
	singleton_map: Dict[str, Any] = None
	plot_data: Dict[str, Any] = None
	out_text: str = ""

	# ⬇️ ADDED FIELDS FOR FLEXIBILITY (Bi-Wheel and Text Output) ⬇️
	# Text output from the rendering process (e.g., from shape summary)
	out_text: Optional[str] = None

	# Bi-Wheel specific data (for the outer chart)
	outer_positions: Optional[Dict[str, float]] = None
	outer_cusps: Optional[List[float]] = None

def render_chart(
	chart: AstrologicalChart,
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
	patterns: List[List[str]] = None,
	shapes: List[Dict[str, Any]] = None,
	singleton_map: Dict[str, Any] = None,
):
	# Set safe defaults immediately inside the function
	patterns = patterns or []
	shapes = shapes or []
	singleton_map = singleton_map or {}
	"""Render the chart wheel using already-curated data."""
	unknown_time_chart = chart.unknown_time
	asc_deg = _get_ascendant_degree(chart)
	if unknown_time_chart:
		asc_deg = 0.0
	visible_names = resolve_visible_objects(visible_toggle_state, chart=chart)
	positions = _chart_positions(chart, visible_names)
	visible_canon = _expand_visible_canon(visible_names)

	st.session_state["resolved_visible_objects"] = visible_names

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
		name, date_line, time_line, city, extra_line = chart.header_lines()
		_draw_header_on_figure(fig, name, date_line, time_line, city, extra_line, dark_mode)
		_draw_moon_phase_on_axes(ax, chart, dark_mode, icon_frac=0.10)
	except Exception:
		pass

	cusps: list[float] = []
	if not unknown_time_chart:
		cusps = draw_house_cusps(ax, chart, asc_deg, house_system, dark_mode)
	if degree_markers:
		draw_degree_markers(ax, asc_deg, dark_mode)
	if zodiac_labels:
		draw_zodiac_signs(ax, asc_deg, dark_mode)

	draw_planet_labels(ax, positions, asc_deg, label_style=label_style, dark_mode=dark_mode, chart=chart)

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
		compass_positions = _chart_compass_positions(chart, visible_names)
		draw_compass_rose(
			ax,
			compass_positions,
			asc_deg,
			include_axes=not unknown_time_chart,
		)
		# Add compass edges to major_edges_drawn if both endpoints exist
		compass_edges = []
		ac = compass_positions.get("Ascendant")
		dc = compass_positions.get("Descendant")
		if ac is not None and dc is not None:
			compass_edges.append(("Ascendant", "Descendant", "Opposition"))
		mc = compass_positions.get("MC")
		ic = compass_positions.get("IC")
		if mc is not None and ic is not None:
			compass_edges.append(("MC", "IC", "Opposition"))
		nn = compass_positions.get("North Node")
		sn = compass_positions.get("South Node")
		if nn is not None and sn is not None:
			compass_edges.append(("North Node", "South Node", "Opposition"))
		# Add to major_edges_drawn if not already present
		for edge in compass_edges:
			if edge not in major_edges_drawn:
				major_edges_drawn.append(edge)
		# Also add to visible_objects if not present
		for obj in ["Ascendant", "Descendant", "MC", "IC", "North Node", "South Node"]:
			if obj in compass_positions and obj not in positions:
				positions[obj] = compass_positions[obj]
	
	draw_center_earth(ax)

	return RenderResult(
		fig=fig,
		ax=ax,
		positions=positions,
		cusps=cusps,
		visible_objects=visible_names or [],
		drawn_major_edges=major_edges_drawn,
		drawn_minor_edges=minor_edges_drawn,
		patterns=patterns,
		shapes=shapes,
		singleton_map=singleton_map,
		plot_data={"chart": chart},
	)

# --- CHART RENDERER (full; calls your new helpers) -------------------------
def render_chart_with_shapes(
	pos, patterns, pattern_labels, toggles,
	filaments, combo_toggles, label_style, singleton_map, chart: AstrologicalChart,
	house_system, dark_mode, shapes, shape_toggles_by_parent, singleton_toggles,
	major_edges_all,
	figsize=(5.0, 5.0),  # Add this
	dpi=144
):
	plt.close('all')  # Kill any background figures before starting
	fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"})
	unknown_time_chart = chart.unknown_time
	asc_deg = _get_ascendant_degree(chart)
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

	# Header and moon phase
	try:
		name, date_line, time_line, city, extra_line = chart.header_lines()
		_draw_header_on_figure(fig, name, date_line, time_line, city, extra_line, dark_mode)
		_draw_moon_phase_on_axes(ax, chart, dark_mode, icon_frac=0.10)
	except Exception:
		pass

	# Base wheel
	cusps: list[float] = []
	if not unknown_time_chart:
		cusps = draw_house_cusps(ax, chart, asc_deg, house_system, dark_mode)
	draw_degree_markers(ax, asc_deg, dark_mode)
	draw_zodiac_signs(ax, asc_deg, dark_mode)
	draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode, chart=chart)

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
		compass_positions = _chart_compass_positions(chart)
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
			df=None,
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
	# Return the standardized result
	return RenderResult(
		fig=fig,
		ax=ax,
		positions=pos,
		cusps=cusps,
		visible_objects=list(visible_objects), # Ensure it's a list
		drawn_major_edges=[
			(p1, p2, asp_name)
			for (p1, p2), asp_name in major_edges_all
			if isinstance(asp_name, str) and asp_name.lower() == "conjunction"
			and p1 in visible_objects and p2 in visible_objects
		],
		drawn_minor_edges=[
			(item["from"], item["to"], {"aspect": item["aspect"]})
			for item in aspects_for_context
		],
		patterns=patterns,
		shapes=active_shapes,
		singleton_map=singleton_map,
		out_text=out_text, # Added this to the dataclass above
		plot_data={"chart": chart},
	)

# ---------------------------------------------------------------------------
# Bi-wheel (synastry/transit) renderer
# ---------------------------------------------------------------------------

def render_biwheel_chart(
	chart_1: AstrologicalChart,
	chart_2: AstrologicalChart,
	*,
	edges_inter_chart: Sequence[Any] | None = None,
	edges_chart1: Sequence[Any] | None = None,
	edges_chart2: Sequence[Any] | None = None,
	house_system: str = "placidus",
	dark_mode: bool = False,
	label_style: str = "glyph",
	figsize: tuple[float, float] = (5.0, 5.0),
	dpi: int = 144,
):
	"""
	Render a bi-wheel chart with two concentric rings:
	- Inner chart: chart_1 (between the two degree circles)
	- Outer chart: chart_2 (outside the outer degree circle)
	- edges_inter_chart: Aspects between inner and outer chart planets
	- edges_chart1: Internal aspects within inner chart
	- edges_chart2: Internal aspects within outer chart
	"""
	unknown_time_1 = chart_1.unknown_time
	unknown_time_2 = chart_2.unknown_time

	# Rotation is always based on Chart 1 (inner) ascendant
	asc_deg_1 = _get_ascendant_degree(chart_1)
	if unknown_time_1:
		asc_deg_1 = 0.0

	# Extract positions for both charts
	pos_1 = _chart_positions(chart_1)
	pos_2 = _chart_positions(chart_2)

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
	fig.subplots_adjust(left=0, right=1.0, top=0.95, bottom=0.05)

	# Draw zodiac signs (outermost ring - unchanged)
	draw_zodiac_signs(ax, asc_deg_1, dark_mode)

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
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Outer degree circle
	circle_outer = plt.Circle((0, 0), OUTER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_outer)
	
	# Draw ticks on outer circle
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Draw inner chart house cusps (between inner and outer circles)
	if not unknown_time_1:
		cusps_1 = draw_house_cusps_biwheel(
			ax, chart_1, asc_deg_1, house_system, dark_mode,
			r_inner=INNER_CIRCLE_R, r_outer=OUTER_CIRCLE_R, draw_labels=True, label_frac=0.50
		)
	else:
		cusps_1 = []

	# Draw outer chart house cusps (between outer circle and zodiac)
	asc_deg_2 = _get_ascendant_degree(chart_2)
	if not unknown_time_2:
		cusps_2 = draw_house_cusps_biwheel(
			ax, chart_2, asc_deg_1, house_system, dark_mode,
			r_inner=OUTER_CIRCLE_R, r_outer=OUTER_CUSP_R, draw_labels=True, label_frac=0.50
		)
	else:
		cusps_2 = []

	# Draw planet labels for inner chart (between the circles)
	draw_planet_labels_biwheel(
		ax, pos_1, asc_deg_1, label_style, dark_mode, chart_1,
		label_r=INNER_LABEL_R, degree_r=INNER_DEGREE_R, is_outer_chart=False
	)

	# Draw planet labels for outer chart (outside outer circle)
	draw_planet_labels_biwheel(
		ax, pos_2, asc_deg_1, label_style, dark_mode, chart_2,
		label_r=OUTER_LABEL_R, degree_r=OUTER_DEGREE_R, is_outer_chart=True
	)

	# Determine coloring mode based on how many aspect groups are enabled
	show_inter = bool(edges_inter_chart)
	show_chart1 = bool(edges_chart1)
	show_chart2 = bool(edges_chart2)
	num_groups_enabled = sum([show_inter, show_chart1, show_chart2])
	use_group_colors = num_groups_enabled >= 2
	
	# Draw chart 1 internal aspects first (bottom layer)
	if show_chart1:
		# Use group color if multiple groups enabled, otherwise standard colors
		chart1_color = SYNASTRY_COLORS_1[0] if use_group_colors else None
		
		for record in edges_chart1:
			if isinstance(record, (list, tuple)) and len(record) == 3:
				p1, p2, aspect = record
			else:
				continue
			
			d1 = pos_1.get(p1)
			d2 = pos_1.get(p2)
			
			if d1 is None or d2 is None:
				continue
			
			# Resolve aspect
			canon_aspect, is_approx, spec = _resolve_aspect(aspect)
			if not canon_aspect:
				continue
			
			r1 = deg_to_rad(d1, asc_deg_1)
			r2 = deg_to_rad(d2, asc_deg_1)
			
			# Use group color or standard color
			if chart1_color:
				base_color = chart1_color
			else:
				base_color = spec.get("color", "gray")
				if is_approx:
					base_color = _lighten_color(base_color, blend=0.35)
			
			style = spec.get("style", "solid")
			lw = 2.0 if canon_aspect not in ("Quincunx", "Sesquisquare") else 1.0
			
			_draw_gradient_line(ax, r1, r2, base_color, base_color, lw, style, radius=INNER_CIRCLE_R)
	
	# Draw chart 2 internal aspects
	if show_chart2:
		# Use group color if multiple groups enabled, otherwise standard colors
		chart2_color = SYNASTRY_COLORS_2[0] if use_group_colors else None
		
		for record in edges_chart2:
			if isinstance(record, (list, tuple)) and len(record) == 3:
				p1, p2, aspect = record
			else:
				continue
			
			d1 = pos_2.get(p1)
			d2 = pos_2.get(p2)
			
			if d1 is None or d2 is None:
				continue
			
			# Resolve aspect
			canon_aspect, is_approx, spec = _resolve_aspect(aspect)
			if not canon_aspect:
				continue
			
			r1 = deg_to_rad(d1, asc_deg_1)
			r2 = deg_to_rad(d2, asc_deg_1)
			
			# Use group color or standard color
			if chart2_color:
				base_color = chart2_color
			else:
				base_color = spec.get("color", "gray")
				if is_approx:
					base_color = _lighten_color(base_color, blend=0.35)
			
			style = spec.get("style", "solid")
			lw = 2.0 if canon_aspect not in ("Quincunx", "Sesquisquare") else 1.0
			
			_draw_gradient_line(ax, r1, r2, base_color, base_color, lw, style, radius=INNER_CIRCLE_R)
	
	# Draw inter-chart aspects last (top layer - foreground)
	if show_inter:
		for record in edges_inter_chart:
			if isinstance(record, (list, tuple)) and len(record) == 3:
				p1, p2, aspect = record
			else:
				continue
			
			# p1 is from inner chart, p2 is from outer chart
			d1 = pos_1.get(p1)
			d2 = pos_2.get(p2)
			
			if d1 is None or d2 is None:
				continue
			
			# Resolve aspect colors/styles
			canon_aspect, is_approx, spec = _resolve_aspect(aspect)
			if not canon_aspect:
				continue
			
			r1 = deg_to_rad(d1, asc_deg_1)
			r2 = deg_to_rad(d2, asc_deg_1)
			
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

	# Draw compass overlays if requested
	# inner chart uses normal colors, outer gets darker variants
	compass_inner = st.session_state.get("ui_compass_overlay", True)
	compass_outer = st.session_state.get("ui_compass_overlay_2", True)
	if compass_inner:
		compass_positions = _chart_compass_positions(chart_1)
		# same orientation as everything else (based on inner ascendant)
		draw_compass_rose(
			ax,
			compass_positions,
			asc_deg_1,
			radius=INNER_CIRCLE_R,
			include_axes=not unknown_time_1,
		)
	if compass_outer:
		compass_positions2 = _chart_compass_positions(chart_2)
		# darker color scheme for outer compass lines
		draw_compass_rose(
			ax,
			compass_positions2,
			asc_deg_1,
			radius=INNER_CIRCLE_R,
			include_axes=not unknown_time_2,
			colors={
				"nodal": "#4B0082",     # dark indigo
				"acdc": "#203A59",      # deep blue
				"mcic": "#203A59",
			},
		)

	# Draw center earth
	draw_center_earth(ax, size=0.18)

	# Draw chart headers for both charts
	# Chart headers read directly from AstrologicalChart.header_lines()
	name1, date_line1, time_line1, city1, extra_line1 = chart_1.header_lines()
	_draw_header_on_figure(fig, name1, date_line1, time_line1, city1, extra_line1, dark_mode)

	name2, date_line2, time_line2, city2, extra_line2 = chart_2.header_lines()
	_draw_header_on_figure_right(fig, name2, date_line2, time_line2, city2, extra_line2, dark_mode)

	return RenderResult(
		fig=fig,
		ax=ax,
		positions=pos_1,  # Return inner positions as primary
		cusps=cusps_1,
		visible_objects=sorted(pos_1.keys()),
		drawn_major_edges=[],
		drawn_minor_edges=[],
	)


# ---------------------------------------------------------------------------
# Bi-wheel Combined Circuits renderer
# ---------------------------------------------------------------------------

def render_biwheel_chart_with_circuits(
	chart_1: AstrologicalChart,
	chart_2: AstrologicalChart,
	*,
	pos_combined: dict[str, float],
	patterns: list[set[str]],
	pattern_labels: list[str],
	toggles: list[bool],
	filaments: list,
	combo_toggles: dict,
	singleton_map: dict,
	singleton_toggles: dict,
	shapes: list,
	shape_toggles_by_parent: dict,
	major_edges_all: list,
	house_system: str = "placidus",
	dark_mode: bool = False,
	label_style: str = "glyph",
	figsize: tuple[float, float] = (5.0, 5.0),
	dpi: int = 144,
):
	"""
	Render a bi-wheel chart with Combined Circuits mode:
	- Inner chart objects: chart_1 (no suffix)
	- Outer chart objects: chart_2 (with "_2" suffix in pos_combined)
	- Circuits connect objects across both charts based on all aspects
	"""
	plt.close('all')  # Clean up any lingering figures
	unknown_time_1 = chart_1.unknown_time
	unknown_time_2 = chart_2.unknown_time

	# Rotation is always based on Chart 1 (inner) ascendant
	asc_deg_1 = _get_ascendant_degree(chart_1)
	if unknown_time_1:
		asc_deg_1 = 0.0

	# Extract positions for both charts (for label drawing)
	pos_1 = _chart_positions(chart_1)
	pos_2 = _chart_positions(chart_2)

	# Setup figure
	fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"})
	if dark_mode:
		ax.set_facecolor("black")
		fig.patch.set_facecolor("black")

	ax.set_theta_zero_location("N")
	ax.set_theta_direction(-1)
	ax.set_rlim(0, 1.70)
	ax.axis("off")
	ax.set_anchor("C")
	ax.set_aspect("equal", adjustable="box")
	fig.subplots_adjust(left=0, right=1.0, top=0.95, bottom=0.05)

	# Draw zodiac signs
	draw_zodiac_signs(ax, asc_deg_1, dark_mode)

	# --- KEY RADIUS CONTROLS FOR BIWHEEL LAYOUT ---
	INNER_CIRCLE_R = 0.9
	OUTER_CIRCLE_R = 1.2
	INNER_LABEL_R = 1.1
	INNER_DEGREE_R = 1.0
	OUTER_LABEL_R = 1.4
	OUTER_DEGREE_R = 1.31
	OUTER_CUSP_R = 1.45

	# Draw degree marker circles
	base_color = "white" if dark_mode else "black"
	
	# Inner degree circle
	circle_inner = plt.Circle((0, 0), INNER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_inner)
	
	# Draw ticks on inner circle
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Outer degree circle
	circle_outer = plt.Circle((0, 0), OUTER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_outer)
	
	# Draw ticks on outer circle
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Draw house cusps
	cusps_1 = []
	if not unknown_time_1:
		cusps_1 = draw_house_cusps_biwheel(
			ax, chart_1, asc_deg_1, house_system, dark_mode,
			r_inner=INNER_CIRCLE_R, r_outer=OUTER_CIRCLE_R, draw_labels=True, label_frac=0.50
		)
	
	if not unknown_time_2:
		draw_house_cusps_biwheel(
			ax, chart_2, asc_deg_1, house_system, dark_mode,
			r_inner=OUTER_CIRCLE_R, r_outer=OUTER_CUSP_R, draw_labels=True, label_frac=0.50
		)

	# Draw planet labels for both charts
	draw_planet_labels_biwheel(
		ax, pos_1, asc_deg_1, label_style, dark_mode, chart_1,
		label_r=INNER_LABEL_R, degree_r=INNER_DEGREE_R, is_outer_chart=False
	)
	draw_planet_labels_biwheel(
		ax, pos_2, asc_deg_1, label_style, dark_mode, chart_2,
		label_r=OUTER_LABEL_R, degree_r=OUTER_DEGREE_R, is_outer_chart=True
	)

	# --- CIRCUIT DRAWING LOGIC ---
	# Determine which circuits are toggled on
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
		for (u, v), asp in s.get("edges", [])
	}
	
	edge_keys: set[tuple[frozenset[str], str]] = set()

	# Draw circuit edges - for biwheel, we draw all aspect lines to INNER_CIRCLE_R
	for idx in active_parents:
		if idx < len(patterns):
			visible_objects.update(patterns[idx])

			# Get edges within this circuit
			edges = [((p1, p2), asp_name)
					for ((p1, p2), asp_name) in major_edges_all
					if p1 in patterns[idx] and p2 in patterns[idx]]

			color = group_color_for(idx) if layered_mode else None
			
			# Draw major edges in this circuit's color
			draw_aspect_lines(
				ax,
				pos_combined,  # Use combined positions
				edges,
				asc_deg_1,
				color_override=color,
				drawn_keys=edge_keys,
				radius=INNER_CIRCLE_R,
			)

	# Draw sub-shapes edges
	for s in active_shapes:
		visible_objects.update(s.get("members", []))
		color = shape_color_for(s["id"]) if layered_mode else None
		draw_aspect_lines(
			ax,
			pos_combined,
			s.get("edges", []),
			asc_deg_1,
			color_override=color,
			drawn_keys=edge_keys,
			radius=INNER_CIRCLE_R,
		)

	# Draw singletons
	visible_objects.update(active_singletons)
	if active_singletons:
		draw_singleton_dots(ax, pos_combined, active_singletons, shape_edges, asc_deg_1, line_width=2.0)

	# Draw compass overlays if requested
	compass_inner = st.session_state.get("ui_compass_overlay", True)
	compass_outer = st.session_state.get("ui_compass_overlay_2", True)
	
	if compass_inner:
		compass_positions = _chart_compass_positions(chart_1)
		draw_compass_rose(
			ax,
			compass_positions,
			asc_deg_1,
			radius=INNER_CIRCLE_R,
			include_axes=not unknown_time_1,
		)
	
	if compass_outer:
		compass_positions2 = _chart_compass_positions(chart_2)
		draw_compass_rose(
			ax,
			compass_positions2,
			asc_deg_1,
			radius=INNER_CIRCLE_R,
			include_axes=not unknown_time_2,
			colors={
				"nodal": "#4B0082",  # dark indigo
				"acdc": "#203A59",   # deep blue
				"mcic": "#203A59",
			},
		)

	# Draw center earth
	draw_center_earth(ax, size=0.18)

	# Draw chart headers
	# Chart headers read directly from AstrologicalChart.header_lines()
	name1, date_line1, time_line1, city1, extra_line1 = chart_1.header_lines()
	_draw_header_on_figure(fig, name1, date_line1, time_line1, city1, extra_line1, dark_mode)

	name2, date_line2, time_line2, city2, extra_line2 = chart_2.header_lines()
	_draw_header_on_figure_right(fig, name2, date_line2, time_line2, city2, extra_line2, dark_mode)

	return RenderResult(
		fig=fig,
		ax=ax,
		positions=pos_combined,
		cusps=cusps_1,
		visible_objects=list(visible_objects),
		drawn_major_edges=[],
		drawn_minor_edges=[],
		patterns=patterns,
		shapes=active_shapes,
		singleton_map=singleton_map,
		plot_data={"chart": chart_1, "chart_2": chart_2},
	)


# ---------------------------------------------------------------------------
# Bi-wheel Connected Circuits renderer
# ---------------------------------------------------------------------------

def render_biwheel_connected_circuits(
	chart_1: AstrologicalChart,
	chart_2: AstrologicalChart,
	*,
	pos_1: dict[str, float],
	pos_2: dict[str, float],
	patterns: list[set[str]],
	shapes: list,
	shapes_2: list,
	circuit_connected_shapes2: dict[int, list],
	edges_inter_chart: list,
	major_edges_all: list,
	pattern_labels: list[str],
	toggles: list[bool],
	singleton_map: dict,
	singleton_toggles: dict,
	shape_toggles_by_parent: dict,
	filaments: list,
	house_system: str = "placidus",
	dark_mode: bool = False,
	label_style: str = "glyph",
	figsize: tuple[float, float] = (5.0, 5.0),
	dpi: int = 144,
):
	"""
	Render a bi-wheel chart in Connected Circuits mode.

	Chart 1 (inner) circuits are drawn exactly as in single-chart Circuits mode.
	When a Chart 1 circuit is toggled on, any Chart 2 shapes whose members are
	connected to that circuit via inter-chart aspects can be further toggled on
	(via cc_shape_{i}_{shape2_id} session keys).  When active, those Chart 2
	shape edges and the filtered inter-chart lines (only the pairs linking that
	circuit to that Chart 2 shape) are drawn — all inside the inner circle,
	exactly like every other edge on the wheel.

	Color-coding follows the existing layered_mode scheme: all edges belonging
	to circuit i (including its Chart 2 connections) share the same circuit color.
	"""
	plt.close('all')

	unknown_time_1 = chart_1.unknown_time
	unknown_time_2 = chart_2.unknown_time

	asc_deg_1 = _get_ascendant_degree(chart_1)
	if unknown_time_1:
		asc_deg_1 = 0.0

	# Chart 2 positions are stored under names with a "_2" suffix so that
	# bodies sharing a name with Chart 1 (e.g. "Sun") don't collide.
	# This mirrors exactly how Combined Circuits mode handles pos_combined.
	pos_outer_2 = {f"{k}_2": v for k, v in pos_2.items()}
	pos_draw = {**pos_1, **pos_outer_2}

	# Setup figure identical to the other biwheel functions
	fig, ax = plt.subplots(figsize=figsize, dpi=dpi, subplot_kw={"projection": "polar"})
	if dark_mode:
		ax.set_facecolor("black")
		fig.patch.set_facecolor("black")

	ax.set_theta_zero_location("N")
	ax.set_theta_direction(-1)
	ax.set_rlim(0, 1.70)
	ax.axis("off")
	ax.set_anchor("C")
	ax.set_aspect("equal", adjustable="box")
	fig.subplots_adjust(left=0, right=1.0, top=0.95, bottom=0.05)

	draw_zodiac_signs(ax, asc_deg_1, dark_mode)

	INNER_CIRCLE_R = 0.9
	OUTER_CIRCLE_R = 1.2
	INNER_LABEL_R = 1.1
	INNER_DEGREE_R = 1.0
	OUTER_LABEL_R = 1.4
	OUTER_DEGREE_R = 1.31
	OUTER_CUSP_R = 1.45

	base_color = "white" if dark_mode else "black"

	# Inner degree circle + ticks
	circle_inner = plt.Circle((0, 0), INNER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_inner)
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [INNER_CIRCLE_R, INNER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# Outer degree circle + ticks
	circle_outer = plt.Circle((0, 0), OUTER_CIRCLE_R, transform=ax.transData._b,
							  fill=False, color=base_color, linewidth=1.5)
	ax.add_artist(circle_outer)
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.015], color=base_color, linewidth=0.5)
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.03], color=base_color, linewidth=0.8)
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg_1)
		ax.plot([r, r], [OUTER_CIRCLE_R, OUTER_CIRCLE_R + 0.05], color=base_color, linewidth=1.2)

	# House cusps
	cusps_1 = []
	if not unknown_time_1:
		cusps_1 = draw_house_cusps_biwheel(
			ax, chart_1, asc_deg_1, house_system, dark_mode,
			r_inner=INNER_CIRCLE_R, r_outer=OUTER_CIRCLE_R, draw_labels=True, label_frac=0.50
		)
	if not unknown_time_2:
		draw_house_cusps_biwheel(
			ax, chart_2, asc_deg_1, house_system, dark_mode,
			r_inner=OUTER_CIRCLE_R, r_outer=OUTER_CUSP_R, draw_labels=True, label_frac=0.50
		)

	# Planet labels: Chart 1 at inner ring, Chart 2 at outer ring
	draw_planet_labels_biwheel(
		ax, pos_1, asc_deg_1, label_style, dark_mode, chart_1,
		label_r=INNER_LABEL_R, degree_r=INNER_DEGREE_R, is_outer_chart=False
	)
	draw_planet_labels_biwheel(
		ax, pos_2, asc_deg_1, label_style, dark_mode, chart_2,
		label_r=OUTER_LABEL_R, degree_r=OUTER_DEGREE_R, is_outer_chart=True
	)

	# --- CONNECTED CIRCUITS DRAWING ---
	active_parents = {i for i, show in enumerate(toggles) if show}

	# Chart 1 sub-shapes toggled on independently
	active_shapes_1 = [
		s for s in shapes
		if st.session_state.get(f"shape_{s['parent']}_{s['id']}", False)
	]
	# circuits that have at least one sub-shape active (even without the full circuit on)
	circuits_with_active_shapes = {s["parent"] for s in active_shapes_1}
	shape_edges_1 = {
		frozenset((u, v))
		for s in active_shapes_1
		for (u, v), _ in s.get("edges", [])
	}

	# Count everything for layered_mode threshold
	num_active_cc = sum(
		1
		for i in (active_parents | circuits_with_active_shapes)
		for sh2 in circuit_connected_shapes2.get(i, [])
		if st.session_state.get(f"cc_shape_{i}_{sh2['id']}", False)
	)
	active_toggle_count = len(active_parents) + len(active_shapes_1) + num_active_cc
	layered_mode = active_toggle_count > 1

	active_singletons = {obj for obj, on in singleton_toggles.items() if on}
	visible_objects: set[str] = set()
	edge_keys: set[tuple[frozenset[str], str]] = set()

	# Draw each active Chart 1 circuit and its selected Chart 2 connections.
	# Also iterate over circuits where only a sub-shape is on (for Chart 2 connections).
	for idx in sorted(active_parents | circuits_with_active_shapes):
		if idx >= len(patterns):
			continue
		circuit_members = set(patterns[idx])
		color = group_color_for(idx) if layered_mode else None

		if idx in active_parents:
			visible_objects.update(circuit_members)
			# Chart 1 internal circuit edges
			circuit_edges = [
				((p1, p2), asp)
				for ((p1, p2), asp) in major_edges_all
				if p1 in circuit_members and p2 in circuit_members
			]
			draw_aspect_lines(
				ax, pos_draw, circuit_edges, asc_deg_1,
				color_override=color, drawn_keys=edge_keys, radius=INNER_CIRCLE_R,
			)

		# Chart 2 shape connections for this circuit
		for sh2 in circuit_connected_shapes2.get(idx, []):
			cc_key = f"cc_shape_{idx}_{sh2['id']}"
			if not st.session_state.get(cc_key, False):
				continue

			# Chart 2 member names need _2 suffix to match pos_draw keys.
			# shapes_2 stores members under plain names (no suffix) because
			# they were detected from Chart 2's internal aspects in isolation.
			sh2_members_plain = sh2.get("members", [])
			sh2_members_2 = {f"{m}_2" for m in sh2_members_plain}
			visible_objects.update(sh2_members_2)

			# Chart 2 shape internal edges: suffix both endpoints
			sh2_edges_2 = [
				((f"{p1}_2", f"{p2}_2"), asp)
				for ((p1, p2), asp) in sh2.get("edges", [])
			]
			draw_aspect_lines(
				ax, pos_draw, sh2_edges_2, asc_deg_1,
				color_override=color, drawn_keys=edge_keys, radius=INNER_CIRCLE_R,
			)

			# Inter-chart lines: p1 is Chart 1 (plain), p2 is Chart 2 (needs _2).
			# edges_inter_chart stores p2 with plain names so suffix here.
			inter_edges = [
				(p1, f"{p2}_2", asp)
				for (p1, p2, asp) in edges_inter_chart
				if p1 in circuit_members and f"{p2}_2" in sh2_members_2
			]
			draw_aspect_lines(
				ax, pos_draw, inter_edges, asc_deg_1,
				color_override=color, drawn_keys=edge_keys, radius=INNER_CIRCLE_R,
			)

	# Chart 1 sub-shapes
	for s in active_shapes_1:
		visible_objects.update(s.get("members", []))
		color = shape_color_for(s["id"]) if layered_mode else None
		draw_aspect_lines(
			ax, pos_draw, s.get("edges", []), asc_deg_1,
			color_override=color, drawn_keys=edge_keys, radius=INNER_CIRCLE_R,
		)

	# Chart 1 singletons
	visible_objects.update(active_singletons)
	if active_singletons:
		draw_singleton_dots(ax, pos_draw, active_singletons, shape_edges_1, asc_deg_1, line_width=2.0)

	# Compass overlays
	compass_inner = st.session_state.get("ui_compass_overlay", True)
	compass_outer = st.session_state.get("ui_compass_overlay_2", True)
	if compass_inner:
		draw_compass_rose(
			ax, _chart_compass_positions(chart_1), asc_deg_1,
			radius=INNER_CIRCLE_R, include_axes=not unknown_time_1,
		)
	if compass_outer:
		draw_compass_rose(
			ax, _chart_compass_positions(chart_2), asc_deg_1,
			radius=INNER_CIRCLE_R, include_axes=not unknown_time_2,
			colors={"nodal": "#4B0082", "acdc": "#203A59", "mcic": "#203A59"},
		)

	draw_center_earth(ax, size=0.18)

	# Chart headers read directly from AstrologicalChart.header_lines()
	name1, date_line1, time_line1, city1, extra_line1 = chart_1.header_lines()
	_draw_header_on_figure(fig, name1, date_line1, time_line1, city1, extra_line1, dark_mode)

	name2, date_line2, time_line2, city2, extra_line2 = chart_2.header_lines()
	_draw_header_on_figure_right(fig, name2, date_line2, time_line2, city2, extra_line2, dark_mode)

	return RenderResult(
		fig=fig,
		ax=ax,
		positions=pos_draw,
		cusps=cusps_1,
		visible_objects=list(visible_objects),
		drawn_major_edges=[],
		drawn_minor_edges=[],
		patterns=patterns,
		shapes=active_shapes_1,
		singleton_map=singleton_map,
		plot_data={"chart": chart_1, "chart_2": chart_2},
	)


# Helper functions for biwheel

def draw_house_cusps_biwheel(
	ax, chart: AstrologicalChart, asc_deg, house_system, dark_mode,
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
	if chart is not None:
		system_key = sys_key.replace(" ", "")
		cusp_rows = [
			c for c in chart.house_cusps
			if (c.house_system or "").strip().lower().replace(" ", "") == system_key
		]
		cusp_rows.sort(key=lambda c: c.cusp_number)
		cusps = [float(c.absolute_degree) for c in cusp_rows if c is not None]

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
	ax, pos, asc_deg, label_style, dark_mode, chart: AstrologicalChart,
	label_r, degree_r, is_outer_chart=False
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

	# Use maroon color for outer chart labels, black/white for inner chart
	if is_outer_chart:
		color = "#6D0000"
	else:
		color = "white" if dark_mode else "black"
	want_glyphs = str(label_style).lower() == "glyph"

	# Retrograde checker
	def is_retrograde(obj_name):
		if chart is None:
			return False
		try:
			target = _canonical_name(obj_name)
			for obj in chart.objects:
				if not obj.object_name:
					continue
				if _canonical_name(obj.object_name.name) == target:
					return bool(obj.retrograde)
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
	"render_biwheel_chart_with_circuits",
	"render_biwheel_connected_circuits",
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