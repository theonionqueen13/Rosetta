# src/chart_core.py
import streamlit as st
import matplotlib.pyplot as plt
import datetime as dt
from zoneinfo import ZoneInfo
from typing import Dict, Any
from drawing_v2 import render_chart, render_chart_with_shapes, render_biwheel_chart, render_biwheel_chart_with_circuits, render_biwheel_connected_circuits
from drawing_v2 import RenderResult as result, group_color_for, shape_color_for
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_chart, generate_combo_groups
from src.geocoding import geocode_city_with_timezone
from event_lookup_v2 import update_events_html_state
from models_v2 import static_db
from src import toggle_state as ts

COMPASS_KEY = "ui_compass_overlay"
COMPASS_KEY_2 = "ui_compass_overlay_2"  # separate overlay toggle for second chart (biwheel)
EPHE_MAJOR_OBJECTS = static_db.EPHE_MAJOR_OBJECTS
ALL_MAJOR_PLACEMENTS = static_db.ALL_MAJOR_PLACEMENTS  # Use this for filtering all major chart placements
MAJOR_OBJECTS = static_db.MAJOR_OBJECTS  # Backward compat (alias to ALL_MAJOR_PLACEMENTS)
TOGGLE_ASPECTS = static_db.TOGGLE_ASPECTS
ASPECTS = static_db.ASPECTS
PLANETS_PLUS = static_db.PLANETS_PLUS

from house_selector_v2 import _selected_house_system
from calc_v2 import calculate_chart, chart_sect_from_chart, build_aspect_edges, \
					annotate_chart, build_dispositor_tables, \
					build_conjunction_clusters
from src.dispositor_graph import plot_dispositor_graph
from circuit_sim import simulate_and_attach
from src.chart_serializer import serialize_chart_for_rendering, serialize_biwheel_for_rendering
from src.components.interactive_chart import st_interactive_chart


def get_chart_inputs_from_session(suffix: str = "") -> Dict[str, Any]:
	"""Extracts all necessary birth data inputs from session state."""
	# Allow a direct override (used by the Now button to bypass widget-key restrictions)
	if not suffix:
		override = st.session_state.get("_now_chart_inputs")
		if override:
			return override

	# This structure mirrors the inputs used in your original file.
	data = {}
	data["year"] = st.session_state.get(f"year{suffix}")
	data["month_name"] = st.session_state.get(f"month_name{suffix}")
	data["day"] = st.session_state.get(f"day{suffix}")
	data["hour_12"] = st.session_state.get(f"hour_12{suffix}")
	data["minute_str"] = st.session_state.get(f"minute_str{suffix}")
	data["ampm"] = st.session_state.get(f"ampm{suffix}")
	data["city"] = st.session_state.get(f"city{suffix}")
	
	# Non-suffixed inputs required for calculation
	data["house_system"] = st.session_state.get("house_system", "placidus")
	
	# Crucial: Get the unknown time flag
	data["unknown_time_flag"] = st.session_state.get(f"profile_unknown_time{suffix}", False)
	
	return data

resolved_dark_mode = False  # NiceGUI: dark mode is passed explicitly at render time

def _positions_from_chart(chart):
	if chart is None:
		return {}
	return {
		obj.object_name.name: obj.longitude
		for obj in chart.objects
		if obj.object_name
	}

def _refresh_chart_figure():
	"""Rebuild the chart figure using the current session-state toggles.
	
	Uses unified toggle state for consistent values across interactive/non-interactive modes.
	"""
	# Check if we're in synastry or transit mode (both use the biwheel renderer).
	# Transit mode only activates the biwheel path in Standard Chart mode so it
	# doesn't interfere with the Circuits-mode biwheel renderers.
	synastry_mode = st.session_state.get("synastry_mode", False)
	transit_mode  = st.session_state.get("transit_mode", False)
	
	if synastry_mode or transit_mode:
		# Synastry/biwheel mode: need both charts
		chart_1 = st.session_state.get("last_chart")
		chart_2 = st.session_state.get("last_chart_2")
		
		if chart_1 is None or chart_2 is None:
			# If we don't have both charts yet, fall back to single chart
			if chart_1 is None:
				return
			chart_2 = chart_1  # Use same chart for both rings as fallback
		
		house_system = st.session_state.get("house_system", "placidus")
		# Use unified state for consistent toggle values
		label_style = ts.get_label_style()
		dark_mode = ts.get_dark_mode()
		chart_mode = ts.get_chart_mode()
		# Prefer the radio widget key (set by Streamlit before script runs) so the
		# correct submode is used on the very first rerun after the user clicks.
		circuit_submode = (
			st.session_state.get("__circuit_submode_radio")
			or ts.get_circuit_submode()
		)
		
		# Compute aspects for Standard Chart mode
		edges_inter_chart = []
		edges_chart1 = []
		edges_chart2 = []
		
		# Handle Circuits mode with Combined Circuits submode
		if chart_mode == "Circuits" and circuit_submode == "Combined Circuits":
			# Combined Circuits: test_calc_v2.py computes all combined data BEFORE this
			# function runs and stores it under these canonical session-state keys.
			# Reading directly from session state guarantees the shapes/patterns used
			# here are *identical* to those used to build the toggle checkboxes —
			# eliminating any chance of ID mismatch from independent recomputation.
			pos_combined            = st.session_state.get("pos_combined", {})
			patterns_combined       = st.session_state.get("patterns_combined", [])
			shapes_combined         = st.session_state.get("shapes_combined", [])
			singleton_map_combined  = st.session_state.get("singleton_map_combined", {})
			combined_edges_formatted = st.session_state.get("combined_edges_formatted", [])
			
			if not patterns_combined:
				# Charts haven't been loaded yet — nothing to draw.
				return
			
			# Get toggle states for circuits from unified state
			toggles = [
				ts.get_pattern_toggle(i)
				for i in range(len(patterns_combined))
			]
			singleton_toggles = {
				planet: ts.get_singleton_toggle(planet)
				for planet in singleton_map_combined
			}
			shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
			
			# Build major_edges_all format for rendering: [((p1, p2), aspect), ...]
			major_edges_all = combined_edges_formatted
			
			# Build filaments (minor aspect links between circuits)
			filaments = []  # For now, keep empty; can be computed later
			
			pattern_labels = [
				ts.get_circuit_name(i)
				for i in range(len(patterns_combined))
			]
			combo_toggles = {}
			
			# ── Interactive Biwheel Circuit Mode ──────────────────────────────
			interactive_mode = ts.get_interactive_chart()
			if interactive_mode:
				try:
					highlights = st.session_state.get("chart_highlights", {})

					biwheel_data = serialize_biwheel_for_rendering(
						chart_1,
						chart_2,
						house_system=house_system,
						dark_mode=dark_mode,
						label_style=label_style,
						compass_on_inner=ts.get_compass_inner(),
						compass_on_outer=ts.get_compass_outer(),
						degree_markers=True,
						edges_inter_chart=[],
						edges_chart1=[],
						edges_chart2=[],
						show_inter=False,
						show_chart1_aspects=False,
						show_chart2_aspects=False,
						highlights=highlights,
						# Circuits mode data
						patterns=patterns_combined,
						shapes=shapes_combined,
						singleton_map=singleton_map_combined,
						toggles=toggles,
						singleton_toggles=singleton_toggles,
						shape_toggles_by_parent=shape_toggles_by_parent,
						pattern_labels=pattern_labels,
						major_edges_all=major_edges_all,
						circuit_mode="combined",
					)

					event = st_interactive_chart(
						biwheel_data,
						highlights=highlights,
						width=1250,
						height=1250,
						key="interactive_biwheel_combined_circuits",
					)
					if event:
						st.session_state["chart_click_event"] = event

					# Build a minimal RenderResult
					positions_inner = {obj.object_name.name: obj.longitude
									   for obj in chart_1.objects if obj.object_name}
					positions_outer = {obj.object_name.name: obj.longitude
									   for obj in chart_2.objects if obj.object_name}
					cusps = [
						float(c.absolute_degree) for c in chart_1.house_cusps
						if (c.house_system or "").strip().lower() == house_system
					]
					rr = result(
						fig=None, ax=None,
						positions={**positions_inner, **{f"{k}_2": v for k, v in positions_outer.items()}},
						cusps=cusps,
						visible_objects=list(positions_inner.keys()) + [f"{k}_2" for k in positions_outer.keys()],
						drawn_major_edges=[],
						drawn_minor_edges=[],
						patterns=patterns_combined,
						shapes=shapes_combined,
						singleton_map=singleton_map_combined,
						plot_data={"chart_1": chart_1, "chart_2": chart_2},
					)
					st.session_state["render_result"] = rr
					st.session_state["visible_objects"] = rr.visible_objects
					st.session_state["active_shapes"] = shapes_combined
					st.session_state["last_cusps"] = cusps
					st.session_state["ai_text"] = None
					return rr
				except Exception as e:
					st.warning(f"Interactive biwheel circuits chart failed, falling back to static: {e}")
					# Fall through to matplotlib renderer
			
			try:
				rr = render_biwheel_chart_with_circuits(
					chart_1,
					chart_2,
					pos_combined=pos_combined,
					patterns=patterns_combined,
					pattern_labels=pattern_labels,
					toggles=toggles,
					filaments=filaments,
					combo_toggles=combo_toggles,
					singleton_map=singleton_map_combined,
					singleton_toggles=singleton_toggles,
					shapes=shapes_combined,
					shape_toggles_by_parent=shape_toggles_by_parent,
					major_edges_all=major_edges_all,
					house_system=house_system,
					dark_mode=dark_mode,
					label_style=label_style,
					figsize=(6.0, 6.0),
					dpi=144,
				)
				st.session_state["render_fig"] = rr.fig
				st.session_state["render_result"] = rr
				st.session_state["visible_objects"] = rr.visible_objects
				st.session_state["active_shapes"] = getattr(rr, "shapes", [])
				st.session_state["last_cusps"] = rr.cusps
				st.session_state["ai_text"] = getattr(rr, "out_text", None)
				return rr
			except Exception as e:
				st.error(f"Combined Circuits biwheel rendering failed: {e}")
				# Fall through to standard biwheel

		# Connected Circuits biwheel mode
		if chart_mode == "Circuits" and circuit_submode == "Connected Circuits":
			pos_1 = _positions_from_chart(chart_1)
			pos_2 = _positions_from_chart(chart_2)

			# render_circuit_toggles() (called before this function) computes the
			# inter-chart aspects and circuit→shape2 mapping every rerun and stores
			# them under these canonical keys.  Reading here guarantees the data used
			# for drawing exactly matches what was used to build the toggle checkboxes.
			edges_inter_chart_cc    = st.session_state.get("edges_inter_chart_cc", [])
			circuit_connected_shapes2 = st.session_state.get("circuit_connected_shapes2", {})

			# Always get these from the chart objects (computed during run_chart)
			patterns_1 = chart_1.aspect_groups
			shapes_1 = chart_1.shapes
			shapes_2 = chart_2.shapes
			major_edges_all_1 = chart_1.major_edges_all
			singleton_map_1 = chart_1.singleton_map
			filaments_1 = chart_1.filaments

			pattern_labels = [
				ts.get_circuit_name(ci)
				for ci in range(len(patterns_1))
			]
			toggles = [
				ts.get_pattern_toggle(ci)
				for ci in range(len(patterns_1))
			]
			singleton_toggles = {
				planet: ts.get_singleton_toggle(planet)
				for planet in singleton_map_1
			}
			shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})

			# ── Interactive Connected Circuits Mode ──────────────────────────────
			interactive_mode = ts.get_interactive_chart()
			if interactive_mode:
				try:
					highlights = st.session_state.get("chart_highlights", {})

					# Pre-filter inter-chart edges & visible Chart 2 objects
					# based on active circuit toggles and cc_shape toggles
					# (mirrors the logic in drawing_v2.render_chart_connected_biwheel)
					_active_circuit_members = set()
					for _idx, _on in enumerate(toggles):
						if _on and _idx < len(patterns_1):
							_active_circuit_members.update(patterns_1[_idx])
					# Include circuits that have an active sub-shape
					for _pidx, _entries in shape_toggles_by_parent.items():
						if any(e.get("on") for e in _entries):
							if _pidx < len(patterns_1):
								_active_circuit_members.update(patterns_1[_pidx])

					# Visible Chart 2 objects: only those whose cc_shape is toggled on
					_visible_chart2_plain = set()
					for _ci in range(len(patterns_1)):
						for _sh2 in circuit_connected_shapes2.get(_ci, []):
							_sh2_id = (_sh2.get("id", "") if isinstance(_sh2, dict)
							           else getattr(_sh2, "shape_id", ""))
							if st.session_state.get(f"cc_shape_{_ci}_{_sh2_id}", False):
								_members = (_sh2.get("members", []) if isinstance(_sh2, dict)
								            else getattr(_sh2, "members", []))
								_visible_chart2_plain.update(_members)

					# Filter: keep only edges where p1 in active circuit & p2 in toggled cc_shape
					filtered_edges_inter = [
						(p1, p2, asp) for (p1, p2, asp) in edges_inter_chart_cc
						if p1 in _active_circuit_members and p2 in _visible_chart2_plain
					]
					# Convert visible Chart 2 names to _2-suffixed set for outer objects
					_visible_outer_objs = {f"{n}_2" for n in _visible_chart2_plain}

					biwheel_data = serialize_biwheel_for_rendering(
						chart_1,
						chart_2,
						house_system=house_system,
						dark_mode=dark_mode,
						label_style=label_style,
						compass_on_inner=ts.get_compass_inner(),
						compass_on_outer=ts.get_compass_outer(),
						degree_markers=True,
						edges_inter_chart=filtered_edges_inter,
						edges_chart1=[],
						edges_chart2=[],
						show_inter=bool(filtered_edges_inter),
						show_chart1_aspects=False,
						show_chart2_aspects=False,
						highlights=highlights,
						# Circuits mode data
						patterns=patterns_1,
						patterns_chart2=chart_2.aspect_groups if hasattr(chart_2, 'aspect_groups') else [],
						shapes=shapes_1,
						shapes_chart2=shapes_2,
						singleton_map=singleton_map_1,
						toggles=toggles,
						singleton_toggles=singleton_toggles,
						shape_toggles_by_parent=shape_toggles_by_parent,
						pattern_labels=pattern_labels,
						major_edges_all=major_edges_all_1,
						circuit_mode="connected",
						visible_objects_outer=_visible_outer_objs,
					)

					event = st_interactive_chart(
						biwheel_data,
						highlights=highlights,
						width=1250,
						height=1250,
						key="interactive_biwheel_connected_circuits",
					)
					if event:
						st.session_state["chart_click_event"] = event

					# Build a minimal RenderResult
					cusps = [
						float(c.absolute_degree) for c in chart_1.house_cusps
						if (c.house_system or "").strip().lower() == house_system
					]
					rr = result(
						fig=None, ax=None,
						positions=pos_1,
						cusps=cusps,
						visible_objects=list(pos_1.keys()) + list(pos_2.keys()),
						drawn_major_edges=[],
						drawn_minor_edges=[],
						patterns=patterns_1,
						shapes=shapes_1,
						singleton_map=singleton_map_1,
						plot_data={"chart_1": chart_1, "chart_2": chart_2},
					)
					st.session_state["render_result"] = rr
					st.session_state["visible_objects"] = rr.visible_objects
					st.session_state["active_shapes"] = shapes_1
					st.session_state["last_cusps"] = cusps
					st.session_state["ai_text"] = None
					return rr
				except Exception as e:
					st.warning(f"Interactive connected circuits chart failed, falling back to static: {e}")
					# Fall through to matplotlib renderer

			try:
				rr = render_biwheel_connected_circuits(
					chart_1,
					chart_2,
					pos_1=pos_1,
					pos_2=pos_2,
					patterns=patterns_1,
					shapes=shapes_1,
					shapes_2=shapes_2,
					circuit_connected_shapes2=circuit_connected_shapes2,
					edges_inter_chart=edges_inter_chart_cc,
					major_edges_all=major_edges_all_1,
					pattern_labels=pattern_labels,
					toggles=toggles,
					singleton_map=singleton_map_1,
					singleton_toggles=singleton_toggles,
					shape_toggles_by_parent=shape_toggles_by_parent,
					filaments=filaments_1,
					house_system=house_system,
					dark_mode=dark_mode,
					label_style=label_style,
					figsize=(6.0, 6.0),
					dpi=144,
				)
				st.session_state["render_fig"] = rr.fig
				st.session_state["render_result"] = rr
				st.session_state["visible_objects"] = rr.visible_objects
				st.session_state["active_shapes"] = getattr(rr, "shapes", [])
				st.session_state["last_cusps"] = rr.cusps
				st.session_state["ai_text"] = getattr(rr, "out_text", None)
				return rr
			except Exception as e:
				st.error(f"Connected Circuits biwheel rendering failed: {e}")
				# Fall through to standard biwheel

		# --- Catch-all biwheel render ---
		# If we are in biwheel mode (synastry or transit) and all mode-specific
		# renderers above either fell through or didn't apply (e.g. Standard Chart
		# with no edges yet), ALWAYS render a plain biwheel here.  This guarantees
		# we never fall through to the single-chart renderer while biwheel is live.
		if chart_mode == "Standard Chart":
			# Get positions for both charts
			pos_1 = _positions_from_chart(chart_1)
			pos_2 = _positions_from_chart(chart_2)
			
			# Get aspect toggles
			aspect_toggles = st.session_state.get("aspect_toggles", {})
			
			# Build list of bodies for aspects: PLANETS_PLUS + enabled TOGGLE_ASPECTS
			aspect_bodies_inner = dict(PLANETS_PLUS)
			aspect_bodies_outer = dict(PLANETS_PLUS)
			
			for body_name, enabled in aspect_toggles.items():
				if enabled and body_name in TOGGLE_ASPECTS:
					aspect_bodies_inner[body_name] = TOGGLE_ASPECTS[body_name]
					aspect_bodies_outer[body_name] = TOGGLE_ASPECTS[body_name]
			
			# Filter positions to aspect-enabled bodies
			inner_pos_filtered = {name: deg for name, deg in pos_1.items() if name in aspect_bodies_inner}
			outer_pos_filtered = {name: deg for name, deg in pos_2.items() if name in aspect_bodies_outer}
			
			# Get synastry aspect group toggles
			show_inter = st.session_state.get("synastry_aspects_inter", True)
			show_chart1 = st.session_state.get("synastry_aspects_chart1", False)
			show_chart2 = st.session_state.get("synastry_aspects_chart2", False)
			
			# Use cached inter-chart aspects if available (computed once per chart pair).
			# Use chart datetime + location as a stable fingerprint — Python id() is
			# unreliable because memory addresses are reused after GC.
			_biwheel_cache_key = (
				chart_1.chart_datetime, chart_1.latitude, chart_1.longitude,
				chart_2.chart_datetime, chart_2.latitude, chart_2.longitude,
				"biwheel_standard",
			)
			_biwheel_cache = st.session_state.get("_biwheel_standard_cache", {})
			
			if _biwheel_cache.get("key") == _biwheel_cache_key:
				# Use cached inter-chart aspects (filter based on current body selection)
				all_inter_aspects = _biwheel_cache["inter_aspects"]
				edges_inter_chart = [
					(p1, p2, asp) for (p1, p2, asp) in all_inter_aspects
					if p1 in inner_pos_filtered and p2 in outer_pos_filtered
				] if show_inter else []
			else:
				# Compute ALL inter-chart aspects (cache for reuse)
				all_inter_aspects = []
				for p1, d1 in pos_1.items():
					for p2, d2 in pos_2.items():
						angle = abs(d1 - d2) % 360
						if angle > 180:
							angle = 360 - angle
						for aspect_name, aspect_data in ASPECTS.items():
							if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
								all_inter_aspects.append((p1, p2, aspect_name))
								break
				
				# Cache the full inter-chart aspects
				st.session_state["_biwheel_standard_cache"] = {
					"key": _biwheel_cache_key,
					"inter_aspects": all_inter_aspects,
				}
				
				# Filter based on current body selection
				edges_inter_chart = [
					(p1, p2, asp) for (p1, p2, asp) in all_inter_aspects
					if p1 in inner_pos_filtered and p2 in outer_pos_filtered
				] if show_inter else []
			
			# Use cached edges from chart objects (already computed in run_chart)
			# and filter based on current body selection
			if show_chart1 and chart_1.edges_major:
				edges_chart1 = [
					(a, b, meta.get("aspect", ""))
					for a, b, meta in chart_1.edges_major
					if a in inner_pos_filtered and b in inner_pos_filtered
				]
			else:
				edges_chart1 = []
			
			if show_chart2 and chart_2.edges_major:
				edges_chart2 = [
					(a, b, meta.get("aspect", ""))
					for a, b, meta in chart_2.edges_major
					if a in outer_pos_filtered and b in outer_pos_filtered
				]
			else:
				edges_chart2 = []

			# ── Interactive Biwheel Chart Mode ──────────────────────────────
			interactive_mode = ts.get_interactive_chart()
			if interactive_mode:
				try:
					highlights = st.session_state.get("chart_highlights", {})

					biwheel_data = serialize_biwheel_for_rendering(
						chart_1,
						chart_2,
						house_system=house_system,
						dark_mode=dark_mode,
						label_style=label_style,
						compass_on_inner=ts.get_compass_inner(),
						compass_on_outer=ts.get_compass_outer(),
						degree_markers=True,
						edges_inter_chart=edges_inter_chart,
						edges_chart1=edges_chart1,
						edges_chart2=edges_chart2,
						show_inter=show_inter,
						show_chart1_aspects=show_chart1,
						show_chart2_aspects=show_chart2,
						highlights=highlights,
					)

					event = st_interactive_chart(
						biwheel_data,
						highlights=highlights,
						width=1250,
						height=1250,
						key="interactive_biwheel_chart",
					)
					# Store event for downstream consumers (chat, detail panel, etc.)
					if event:
						st.session_state["chart_click_event"] = event

					# Build a minimal RenderResult so the rest of the app works
					positions_inner = {obj.object_name.name: obj.longitude
									   for obj in chart_1.objects if obj.object_name}
					positions_outer = {obj.object_name.name: obj.longitude
									   for obj in chart_2.objects if obj.object_name}
					cusps = [
						float(c.absolute_degree) for c in chart_1.house_cusps
						if (c.house_system or "").strip().lower() == house_system
					]
					rr = result(
						fig=None, ax=None,
						positions={**positions_inner},  # Just use inner chart positions as primary
						cusps=cusps,
						visible_objects=list(positions_inner.keys()) + list(positions_outer.keys()),
						drawn_major_edges=[(e[0], e[1], e[2]) for e in edges_inter_chart] if edges_inter_chart else [],
						drawn_minor_edges=[],
						patterns=[],
						shapes=[],
						singleton_map={},
						plot_data={"chart_1": chart_1, "chart_2": chart_2},
					)
					st.session_state["render_result"] = rr
					st.session_state["visible_objects"] = rr.visible_objects
					st.session_state["active_shapes"] = []
					st.session_state["last_cusps"] = cusps
					st.session_state["ai_text"] = None
					return rr
				except Exception as e:
					st.warning(f"Interactive biwheel chart failed, falling back to static: {e}")
					# Fall through to matplotlib renderer
		
		# Determine unknown-time flags for each chart explicitly.
		# unknown_time is now carried on the AstrologicalChart object itself.
		try:
			rr = render_biwheel_chart(
				chart_1,
				chart_2,
				edges_inter_chart=edges_inter_chart,
				edges_chart1=edges_chart1,
				edges_chart2=edges_chart2,
				house_system=house_system,
				dark_mode=dark_mode,
				label_style=label_style,
				figsize=(6.0, 6.0),
				dpi=144,
			)
			st.session_state["render_fig"] = rr.fig
			st.session_state["render_result"] = rr

			# Ensure AC/DC axes are always present when compass rose is toggled
			visible_objects = set(rr.visible_objects)
			if st.session_state.get("toggle_compass_rose", False):
				visible_objects.update(["Ascendant", "AC", "Asc", "Descendant", "DC"])
			st.session_state["visible_objects"] = sorted(visible_objects)
			st.session_state["active_shapes"] = []
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = None
			return rr
		except Exception as e:
			st.error(f"Biwheel chart rendering failed: {e}")
			# This is the last resort — if even render_biwheel_chart fails, return
			# without falling through to single-chart mode.
			return

	# Regular single-chart mode
	chart = st.session_state.get("last_chart")

	if chart is None or not chart.positions:
		return

	pos             = chart.positions
	patterns        = chart.aspect_groups
	shapes          = chart.shapes
	filaments       = chart.filaments
	combos          = chart.combos
	singleton_map   = chart.singleton_map
	major_edges_all = chart.major_edges_all
	edges_major     = chart.edges_major
	edges_minor     = chart.edges_minor

	# Read toggles from unified state for consistency across interactive/non-interactive modes
	pattern_labels = [
		ts.get_circuit_name(i)
		for i in range(len(patterns))
	]
	toggles = [
		ts.get_pattern_toggle(i)
		for i in range(len(patterns))
	]
	singleton_toggles = {
		planet: ts.get_singleton_toggle(planet)
		for planet in singleton_map
	}
	shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
	combo_toggles = st.session_state.get("combo_toggles", {})

	house_system = st.session_state.get("house_system", "placidus")
	# Use unified state for consistent values
	label_style  = ts.get_label_style()
	dark_mode    = ts.get_dark_mode()

	# Check if we're in Standard Chart mode using unified state
	chart_mode = ts.get_chart_mode()

	# ── Interactive Chart Mode ──────────────────────────────────────────────
	interactive_mode = ts.get_interactive_chart()
	if interactive_mode:
		try:
			highlights = st.session_state.get("chart_highlights", {})

			# ── Mirror circuit/shape toggle logic from render_chart_with_shapes ──
			# Determine which circuits, sub-shapes, and singletons are active.
			active_parents = set(i for i, show in enumerate(toggles) if show)
			active_shape_ids = {
				s["id"] for s in (shapes or [])
				if st.session_state.get(f"shape_{s['parent']}_{s['id']}", False)
			}
			active_shapes_list = [s for s in (shapes or []) if s["id"] in active_shape_ids]
			active_toggle_count = len(active_parents) + len(active_shapes_list)
			layered_mode = active_toggle_count > 1
			active_singletons: set[str] = {obj for obj, on in singleton_toggles.items() if on}
			any_active = active_toggle_count > 0 or bool(active_singletons)

			# In Standard Chart mode always show everything; in Circuits mode
			# only show edges/objects for active toggles (matching non-interactive
			# chart behaviour exactly).
			if chart_mode != "Standard Chart" and any_active:
				visible_objs: set[str] = set()
				edge_color_map: dict = {}
				edge_keys: set = set()
				filtered_major: list = []
				filtered_minor: list = []

				# Per-circuit: major edges + internal minor filaments
				for idx in active_parents:
					if idx >= len(patterns):
						continue
					visible_objs.update(patterns[idx])
					color = group_color_for(idx) if layered_mode else None
					for (p1, p2), asp_name in (major_edges_all or []):
						if p1 in patterns[idx] and p2 in patterns[idx]:
							k = (tuple(sorted((p1, p2))), asp_name)
							if k not in edge_keys:
								edge_keys.add(k)
								filtered_major.append((p1, p2, {"aspect": asp_name}))
								if color:
									edge_color_map[(p1, p2, asp_name)] = color
									edge_color_map[(p2, p1, asp_name)] = color
					for item in (filaments or []):
						f1, f2, fasp, pat1, pat2 = item
						if pat1 == idx and pat2 == idx:
							k = (tuple(sorted((f1, f2))), fasp)
							if k not in edge_keys:
								edge_keys.add(k)
								filtered_minor.append((f1, f2, {"aspect": fasp}))
								if color:
									edge_color_map[(f1, f2, fasp)] = color
									edge_color_map[(f2, f1, fasp)] = color

				# Inter-circuit filaments (only when 2+ circuits active)
				if len(active_parents) > 1:
					for item in (filaments or []):
						f1, f2, fasp, pat1, pat2 = item
						if (pat1 != pat2
								and pat1 in active_parents
								and pat2 in active_parents):
							k = (tuple(sorted((f1, f2))), fasp)
							if k not in edge_keys:
								edge_keys.add(k)
								filtered_minor.append((f1, f2, {"aspect": fasp}))

				# Sub-shape edges
				for s in active_shapes_list:
					visible_objs.update(s["members"])
					color = shape_color_for(s["id"]) if layered_mode else None
					for (p1, p2), asp_name in s["edges"]:
						k = (tuple(sorted((p1, p2))), asp_name)
						if k not in edge_keys:
							edge_keys.add(k)
							filtered_major.append((p1, p2, {"aspect": asp_name}))
							if color:
								edge_color_map[(p1, p2, asp_name)] = color
								edge_color_map[(p2, p1, asp_name)] = color

				# Singletons (visible but no extra edges)
				visible_objs.update(active_singletons)

				# Always keep compass axes visible when compass rose is on
				if ts.get_compass_inner():
					for axis in ("Ascendant", "Descendant", "AC", "DC",
								 "Midheaven", "MC", "IC",
								 "North Node", "South Node"):
						visible_objs.add(axis)

				vis_list = list(visible_objs) if visible_objs else None
				final_major = filtered_major
				final_minor = filtered_minor
			else:
					edge_color_map = {}
					active_singletons = set()
					layered_mode = False
					if chart_mode == "Standard Chart":
						# Standard Chart: show all aspects.
						vis_list = None
						final_major = edges_major
						final_minor = edges_minor
					else:
						# Circuits mode, nothing toggled: show nothing except compass axes.
						compass_axes = (
							[ax for ax in ("Ascendant", "Descendant", "AC", "DC",
										  "Midheaven", "MC", "IC",
										  "North Node", "South Node")
							 if ax in pos]
							if ts.get_compass_inner() else []
						)
						vis_list = compass_axes if compass_axes else []
						final_major = []
						final_minor = []

			chart_data = serialize_chart_for_rendering(
				chart,
				house_system=house_system,
				dark_mode=dark_mode,
				label_style=label_style,
				compass_on=ts.get_compass_inner(),
				degree_markers=True,
				edges_major=final_major,
				edges_minor=final_minor,
				shapes=shapes,
				singleton_map=singleton_map,
				patterns=patterns,
				highlights=highlights,
				visible_objects=vis_list,
			)

			event = st_interactive_chart(
				chart_data,
				highlights=highlights,
				width=1250,
				height=1250,
				key="interactive_main_chart",
			)
			# Store event for downstream consumers (chat, detail panel, etc.)
			if event:
				st.session_state["chart_click_event"] = event
			# Still build a minimal RenderResult so the rest of the app works
			positions = {obj.object_name.name: obj.longitude
						 for obj in chart.objects if obj.object_name}
			cusps = [
				float(c.absolute_degree) for c in chart.house_cusps
				if (c.house_system or "").strip().lower() == house_system
			]
			rr = result(
				fig=None, ax=None,
				positions=positions,
				cusps=cusps,
				visible_objects=vis_list or list(positions.keys()),
				drawn_major_edges=[(e[0], e[1], e[2].get("aspect", "") if isinstance(e[2], dict) else str(e[2]))
									for e in final_major] if final_major else [],
				drawn_minor_edges=[(e[0], e[1], e[2].get("aspect", "") if isinstance(e[2], dict) else str(e[2]))
									for e in final_minor] if final_minor else [],
				patterns=patterns,
				shapes=active_shapes_list if any_active else (shapes or []),
				singleton_map=singleton_map,
				plot_data={"chart": chart},
			)
			st.session_state["render_result"] = rr
			st.session_state["visible_objects"] = rr.visible_objects
			st.session_state["active_shapes"] = active_shapes_list if any_active else (shapes or [])
			st.session_state["last_cusps"] = cusps
			st.session_state["ai_text"] = None
			return rr
		except Exception as e:
			st.warning(f"Interactive chart failed, falling back to static: {e}")
			# Fall through to matplotlib renderers

	if chart_mode == "Standard Chart":
		# Standard Chart mode: use cached aspects from chart object, filtered by toggle settings
		
		# Build list of bodies to include: PLANETS_PLUS + selected TOGGLE_ASPECTS
		aspect_bodies = dict(PLANETS_PLUS)
		
		# Get aspect_toggles from session state (will be set by render_circuit_toggles later)
		aspect_toggles = st.session_state.get("aspect_toggles", {})
		
		# Add any TOGGLE_ASPECTS bodies that are enabled
		for body_name, enabled in aspect_toggles.items():
			if enabled and body_name in TOGGLE_ASPECTS:
				aspect_bodies[body_name] = TOGGLE_ASPECTS[body_name]
		
		# Filter positions to only include aspect-enabled bodies
		standard_pos = {name: deg for name, deg in pos.items() if name in aspect_bodies}
		
		# Get all major placements (including AC, DC, IC, MC) that exist in the chart for display
		major_pos = {name: deg for name, deg in pos.items() if name in ALL_MAJOR_PLACEMENTS}
		
		# Use cached edges from chart object (already computed in run_chart)
		# and filter to only include edges between visible bodies
		standard_edges = []
		for edge in edges_major:
			# edges_major format: (obj1, obj2, meta_dict)
			a, b = edge[0], edge[1]
			meta = edge[2] if len(edge) > 2 else {}
			aspect_name = meta.get("aspect", "") if isinstance(meta, dict) else ""
			if a in standard_pos and b in standard_pos:
				standard_edges.append((a, b, aspect_name))
		
		# Use render_chart for standard mode with all MAJOR_OBJECTS visible
		try:
			compass_on = ts.get_compass_inner()
			# Show all MAJOR_OBJECTS that actually exist in the chart
			visible_objects = list(major_pos.keys())
			# Ensure AC and DC are always included when compass rose is toggled
			if compass_on and chart is not None:
				chart_names = {obj.object_name.name for obj in chart.objects if obj.object_name}
				for axis in ["Ascendant", "Descendant", "AC", "DC"]:
					if axis in chart_names and axis not in visible_objects:
						visible_objects.append(axis)
			rr = render_chart(
				chart,
				dark_mode=ts.get_dark_mode(),
				visible_toggle_state=visible_objects,  # Show all MAJOR_OBJECTS
				edges_major=standard_edges,
				edges_minor=[],
				house_system=_selected_house_system(),
				label_style=ts.get_label_style(),
				compass_on=compass_on,
				degree_markers=True,
				zodiac_labels=True,
				figsize=(6.0, 6.0),
				dpi=144,
				patterns=patterns,
				shapes=shapes,
				singleton_map=singleton_map,
			)
			st.session_state["render_fig"] = rr.fig
			st.session_state["render_result"] = rr
			st.session_state["visible_objects"] = rr.visible_objects
			st.session_state["active_shapes"] = []
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = None
			return rr
		except Exception as e:
			st.error(f"Standard chart rendering failed: {e}")
			return
	else:
		# Circuits mode: use existing logic
		try:
			# 1. Call the complex renderer and store as 'rr'
			rr = render_chart_with_shapes(
				pos, patterns, pattern_labels, toggles,
				filaments, combo_toggles, label_style, singleton_map, chart,
				house_system, dark_mode, shapes, shape_toggles_by_parent, 
				singleton_toggles, major_edges_all
			)
			# Store result in session state so sidebar can access visible_objects
			st.session_state["render_fig"] = rr.fig
			st.session_state["render_result"] = rr
			st.session_state["visible_objects"] = rr.visible_objects
			st.session_state["active_shapes"] = getattr(rr, "shapes", [])
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = getattr(rr, "out_text", None)
			return rr
		except Exception as e:
			st.error(f"Complex chart rendering failed: {e}")
			rr = render_chart(
				chart,
				dark_mode=ts.get_dark_mode(),
				visible_toggle_state=None,
				edges_major=edges_major,
				edges_minor=edges_minor,
				house_system=_selected_house_system(),
				label_style=ts.get_label_style(),
				compass_on=ts.get_compass_inner(),
				degree_markers=True,
				zodiac_labels=True,
				figsize=(6.0, 6.0),
				dpi=144,
			)
			st.session_state["render_fig"] = rr.fig
			st.session_state["render_result"] = rr
			st.session_state["visible_objects"] = rr.visible_objects
			st.session_state["active_shapes"] = getattr(rr, "shapes", []) # Use [] if shapes is None
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = getattr(rr, "out_text", None)
			return rr

def run_chart(suffix: str = "") -> bool:
	"""
	Core function to read input data, geocode, calculate the chart, 
	perform post-processing (including circuit detection), and 
	store all results back into session state (with suffix).
	
	Returns True on success, False otherwise.
	"""
	# Initialize variables to prevent scope errors and ensure availability
	utc_dt = None 
	patterns = []
	shapes = []
	singleton_map = {}
	filaments = []
	combos = {}
	major_edges_all = []
	
	# Assuming get_chart_inputs_from_session is defined and returns a dict
	inputs = get_chart_inputs_from_session(suffix)
	city = inputs.get("city")
	chart_unknown_time = inputs.get("unknown_time_flag")

	# Resolve the display name for the chart header (natal chart name / profile title)
	_raw_name = (
		st.session_state.get("current_profile_title")
		or st.session_state.get("current_profile")
		or ""
	)
	if isinstance(_raw_name, str) and _raw_name.startswith("community:"):
		_raw_name = "Community Chart"
	chart_display_name = str(_raw_name)
	
	# 1. Input Validation and Time Parsing
	# When unknown_time is flagged, the form stores "--" placeholders.
	# Default to noon so the chart can still be calculated (houses will
	# be suppressed later by the unknown_time flag).
	if chart_unknown_time:
		inputs["hour_12"] = inputs.get("hour_12") or "12"
		inputs["minute_str"] = inputs.get("minute_str") or "00"
		inputs["ampm"] = inputs.get("ampm") or "PM"
		if inputs["hour_12"] == "--":
			inputs["hour_12"] = "12"
		if inputs["minute_str"] == "--":
			inputs["minute_str"] = "00"
		if inputs["ampm"] == "--":
			inputs["ampm"] = "PM"

	try:
		year = int(inputs.get("year"))
		month = dt.datetime.strptime(inputs.get("month_name"), "%B").month
		day = int(inputs.get("day"))
		hour_12 = int(inputs.get("hour_12"))
		minute = int(inputs.get("minute_str"))
		ampm = inputs.get("ampm", "AM")
		
		# Convert 12-hour time to 24-hour time
		hour_24 = hour_12
		if ampm == "PM" and hour_12 != 12:
			hour_24 += 12
		elif ampm == "AM" and hour_12 == 12: # Midnight
			hour_24 = 0
			
		local_dt = dt.datetime(year, month, day, hour_24, minute)
		
	except Exception:
		return False
		
	# 2. Geocoding and Timezone (UNCHANGED)
	lat, lon, tz_name, _ = geocode_city_with_timezone(city)
	
	if lat is None or lon is None or tz_name is None:
		return False

	# Store location/tz so transit navigator can display times in local tz
	st.session_state["current_lat"]     = lat
	st.session_state["current_lon"]     = lon
	st.session_state["current_tz_name"] = tz_name
		
	# 3. Timezone Conversion (local -> UTC) (UNCHANGED)
	try:
		tz = ZoneInfo(tz_name)
		local_dt_aware = local_dt.replace(tzinfo=tz)
		utc_dt = local_dt_aware.astimezone(dt.timezone.utc).replace(tzinfo=None)
	except Exception:
		return False
		
	# ⬇️ ADDED: OLD RUN_CHART STATE UPDATES (before calc) ⬇️
	st.session_state["chart_dt_utc"] = utc_dt # Store new UTC time
	st.session_state[COMPASS_KEY] = True     # Default Compass Rose On
	st.session_state.setdefault(COMPASS_KEY_2, True)  # also ensure second chart toggle exists
	update_events_html_state(utc_dt)
		
	# 4. Core Calculation (include_aspects=False is intentional for new flow)
	try:
		utc_tz_offset = 0
		(
			df_positions,
			aspect_df_result,
			plot_data,
			chart,
		) = calculate_chart(
			year=utc_dt.year, month=utc_dt.month, day=utc_dt.day,
			hour=utc_dt.hour, minute=utc_dt.minute,
			tz_offset=utc_tz_offset, lat=lat, lon=lon,
			input_is_ut=True, # Corrected input flag
			tz_name=tz_name,
			house_system=inputs["house_system"],
			include_aspects=True, # Calculate edges/aspects separately
			unknown_time=chart_unknown_time,
			display_name=chart_display_name,
			city=city or "",
			display_datetime=local_dt,  # local birth time for header display
		)
		
		chart.plot_data = plot_data
		
	except Exception as e:
		st.error(f"Core astrological calculation failed: {e}")
		return False

	# ------------------------------------------------------------------
	# 5. POST-PROCESSING (All Logic from run_chart is re-added here)
	# ------------------------------------------------------------------
	
	# Aspect Edge Calculation
	include_compass_rose = st.session_state.get("ui_compass_overlay", False) 
	# Ensure chart_state is defined
	if 'chart_state' not in globals():
		globals()['chart_state'] = {}

	# Pass chart_state to build_aspect_edges
	edges_major, edges_minor, _edges_harmonic = build_aspect_edges(
		chart,
		compass_rose=include_compass_rose,
	)
		
	print(f"[DEBUG] edges_major after build_aspect_edges: {edges_major}")
	print(f"[DEBUG] edges_minor after build_aspect_edges: {edges_minor}")

	# ⬇️ MISSING POST-PROCESSING ADDED ⬇️
	# Annotate Reception
	annotate_chart(chart, edges_major)
	
	# Chart Sect
	try:
		chart.sect = chart_sect_from_chart(chart)
		chart.sect_error = None
	except Exception as e:
		chart.sect = None
		chart.sect_error = str(e)
	
	# Conjunction Clusters
	clusters_rows, _, _ = build_conjunction_clusters(chart, edges_major)
	chart.conj_clusters_rows = clusters_rows
	
	# Dispositors (already existed, but ensures order)
	dispositor_summary_rows, dispositor_chains_rows = build_dispositor_tables(chart)
	
	# ⬇️ CIRCUIT/SHAPE/SINGLETON DETECTION (CORRECTED SIGNATURE) ⬇️
	try:
		# prepare_pattern_inputs expects a DataFrame, not an AstrologicalChart
		pos_chart, patterns_sets, major_edges_all = prepare_pattern_inputs(df_positions, edges_major)
		
		patterns = [sorted(list(s)) for s in patterns_sets]
		shapes = detect_shapes(pos_chart, patterns_sets, major_edges_all)
		
		# Missing minor links/singletons logic added back
		filaments, singleton_map = detect_minor_links_from_chart(chart, edges_major)
		combos = generate_combo_groups(filaments)
		
	except Exception as e:
		print(f"Warning: Circuit detection failed: {e}")
		# Defaults remain as empty lists/dicts
		pos_chart = {}
		
	# ------------------------------------------------------------------
	# 6. Store ALL Results in RenderResult Object
	# ------------------------------------------------------------------
	
	# Prepare data for RenderResult
	positions = _positions_from_chart(chart)
	house_system = inputs.get("house_system", "placidus")
	cusps = [
		float(c.absolute_degree) for c in chart.house_cusps
		if (c.house_system or "").strip().lower() == str(house_system).strip().lower()
	]
	visible_objects = st.session_state.get(f"visible_objects{suffix}", [])
	
	# FIX: Corrected list comprehension for edges (from last step)
	drawn_major_edges = [tuple(e) for e in edges_major] 
	drawn_minor_edges = [tuple(e) for e in edges_minor]
	
	fig_placeholder, ax_placeholder = None, None 
	
	render_result = result( 
		fig=fig_placeholder, ax=ax_placeholder,
		positions=positions, cusps=cusps,
		visible_objects=visible_objects,
		drawn_major_edges=drawn_major_edges,
		drawn_minor_edges=drawn_minor_edges,
		
		# CIRCUIT DATA
		patterns=patterns,
		shapes=shapes,
		singleton_map=singleton_map,
		plot_data=plot_data,
	)
	
	st.session_state["render_result"] = render_result
	
	# ------------------------------------------------------------------
	# 7. Store all computed data on the chart object; only the chart
	#    object itself is written to session state.
	# ------------------------------------------------------------------
	chart.df_positions           = df_positions
	chart.aspect_df              = aspect_df_result
	chart.edges_major            = edges_major
	chart.edges_minor            = edges_minor
	chart.aspect_groups          = patterns
	chart.shapes                 = shapes
	# Circuit power simulation — requires both planetary_states AND shapes.
	simulate_and_attach(chart)
	chart.filaments              = filaments
	chart.singleton_map          = singleton_map
	chart.combos                 = combos
	chart.positions              = pos_chart
	chart.major_edges_all        = major_edges_all
	chart.dispositor_summary_rows = dispositor_summary_rows
	chart.dispositor_chains_rows  = dispositor_chains_rows
	chart.utc_datetime           = utc_dt

	st.session_state[f"last_chart{suffix}"] = chart
	# Track whether chart_2 holds synastry data (so transit mode knows to overwrite it)
	if suffix == "_2":
		st.session_state["chart_2_source"] = "synastry"

	# 8. Trigger Figure Refresh (MISSING CALL FROM run_chart)
	_rr = _refresh_chart_figure()
	if _rr is not None and getattr(_rr, 'fig', None) is not None:
		import matplotlib.pyplot as _plt
		_plt.close(_rr.fig)
	
	# 9. UI State Defaults (MISSING BLOCK FROM run_chart)
	for i in range(len(patterns)):
		st.session_state.setdefault(f"toggle_pattern_{i}", False)
		st.session_state.setdefault(f"circuit_name_{i}", f"Circuit {i+1}")

	if singleton_map:
		for planet in singleton_map.keys():
			st.session_state.setdefault(f"singleton_{planet}", False)

	return True


def run_transit_chart() -> bool:
	"""
	Calculate the current planetary positions (transits) and store them
	as Chart 2 (suffix="_2") so the biwheel renderer can use them.

	Uses the user's stored lat/lon/tz from session state.
	Falls back to 0°N 0°E / UTC if no location is stored.
	"""
	import datetime as dt

	# --- Location: prefer what's already stored from the main chart ---
	lat     = st.session_state.get("current_lat")
	lon     = st.session_state.get("current_lon")
	tz_name = st.session_state.get("current_tz_name", "UTC")

	if lat is None or lon is None:
		# Fall back: no location available, use 0/0 so planetary positions
		# are still accurate (houses will just be meaningless).
		lat, lon, tz_name = 0.0, 0.0, "UTC"

	# --- Transit time: use custom datetime if set, else current time ---
	custom_dt = st.session_state.get("transit_dt_utc")
	if custom_dt is not None:
		if isinstance(custom_dt, dt.datetime):
			ut = custom_dt.replace(tzinfo=dt.timezone.utc)
		else:
			ut = dt.datetime.now(dt.timezone.utc)
	else:
		ut = dt.datetime.now(dt.timezone.utc)
		# Store it so the UI shows the time we actually used
		st.session_state["transit_dt_utc"] = ut.replace(tzinfo=None)

	try:
		(
			df_positions,
			aspect_df_result,
			plot_data,
			chart,
		) = calculate_chart(
			year=ut.year, month=ut.month, day=ut.day,
			hour=ut.hour, minute=ut.minute,
			tz_offset=0,
			lat=float(lat), lon=float(lon),
			input_is_ut=True,
			tz_name=tz_name,
			house_system=st.session_state.get("house_system", "placidus"),
			include_aspects=True,
			unknown_time=False,
			display_name="Transits",
			city=st.session_state.get("city", ""),
		)
	except Exception as e:
		st.error(f"Transit chart calculation failed: {e}")
		return False

	# --- Minimal post-processing for Chart 2 ---
	edges_major, edges_minor, _ = build_aspect_edges(chart, compass_rose=False)
	annotate_chart(chart, edges_major)

	# --- Build Chart 2 circuit data and store all on the chart object ---
	try:
		from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_chart
		pos_chart2, patterns_sets2, major_edges_all2 = prepare_pattern_inputs(df_positions, edges_major)
		patterns2 = [sorted(list(s)) for s in patterns_sets2]
		shapes2   = detect_shapes(pos_chart2, patterns_sets2, major_edges_all2)
	except Exception:
		pos_chart2, patterns2, shapes2, major_edges_all2 = {}, [], [], []

	chart.df_positions    = df_positions
	chart.aspect_df       = aspect_df_result
	chart.edges_major     = edges_major
	chart.edges_minor     = edges_minor
	chart.aspect_groups   = patterns2
	chart.shapes          = shapes2
	chart.positions       = pos_chart2
	chart.major_edges_all = major_edges_all2
	chart.utc_datetime    = ut.replace(tzinfo=None)

	st.session_state.update({
		"last_chart_2":   chart,
		"chart_2_source": "transit",
	})
	return True