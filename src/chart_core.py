# src/chart_core.py
import streamlit as st
import matplotlib.pyplot as plt
import datetime as dt
from zoneinfo import ZoneInfo
from typing import Dict, Any
from drawing_v2 import render_chart, render_chart_with_shapes, render_biwheel_chart, render_biwheel_chart_with_circuits, render_biwheel_connected_circuits
from drawing_v2 import RenderResult as result
from toggles_v2 import COMPASS_KEY, COMPASS_KEY_2
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_chart, generate_combo_groups
from src.geocoding import geocode_city_with_timezone
from event_lookup_v2 import update_events_html_state
from models_v2 import static_db

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

resolved_dark_mode=st.session_state.get("dark_mode", False)

def _positions_from_chart(chart):
	if chart is None:
		return {}
	return {
		obj.object_name.name: obj.longitude
		for obj in chart.objects
		if obj.object_name
	}

def _refresh_chart_figure():
	"""Rebuild the chart figure using the current session-state toggles."""
	# Check if we're in synastry or transit mode (both use the biwheel renderer).
	# Transit mode only activates the biwheel path in Standard Chart mode so it
	# doesn't interfere with the Circuits-mode biwheel renderers.
	synastry_mode = st.session_state.get("synastry_mode", False)
	transit_mode  = st.session_state.get("transit_mode", False)
	
	if synastry_mode or transit_mode:
		# Synastry/biwheel mode: need both charts
		chart_inner = st.session_state.get("last_chart")
		chart_outer = st.session_state.get("last_chart_2")
		
		if chart_inner is None or chart_outer is None:
			# If we don't have both charts yet, fall back to single chart
			if chart_inner is None:
				return
			chart_outer = chart_inner  # Use same chart for both rings as fallback
		
		house_system = st.session_state.get("house_system", "placidus")
		label_style = st.session_state.get("label_style", "glyph")
		dark_mode = st.session_state.get("dark_mode", False)
		chart_mode = st.session_state.get("chart_mode", "Circuits")
		# Prefer the radio widget key (set by Streamlit before script runs) so the
		# correct submode is used on the very first rerun after the user clicks.
		circuit_submode = (
			st.session_state.get("__circuit_submode_radio")
			or st.session_state.get("circuit_submode", "Combined Circuits")
		)
		
		# Compute aspects for Standard Chart mode
		edges_inter_chart = []
		edges_chart1 = []
		edges_chart2 = []
		
		# Handle Circuits mode with Combined Circuits submode
		if chart_mode == "Circuits" and circuit_submode == "Combined Circuits":
			# Combined Circuits: merge both charts into one and build circuits
			pos_inner = _positions_from_chart(chart_inner)
			pos_outer = _positions_from_chart(chart_outer)
			
			# Combine positions: Chart 2 objects get "_2" suffix to distinguish
			pos_combined = dict(pos_inner)
			for name, deg in pos_outer.items():
				pos_combined[f"{name}_2"] = deg
			
			# Build all aspect edges across combined positions
			combined_edges_formatted = []  # Format: ((p1, p2), aspect_name)
			bodies_list = list(pos_combined.keys())
			for i in range(len(bodies_list)):
				for j in range(i + 1, len(bodies_list)):
					p1, p2 = bodies_list[i], bodies_list[j]
					d1, d2 = pos_combined[p1], pos_combined[p2]
					angle = abs(d1 - d2) % 360
					if angle > 180:
						angle = 360 - angle
					
					# Check all aspect types
					for aspect_name, aspect_data in ASPECTS.items():
						if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
							combined_edges_formatted.append(((p1, p2), aspect_name))
							break  # Only one aspect per pair
			
			# Find connected patterns/circuits from combined edges
			from patterns_v2 import connected_components_from_edges, detect_shapes
			patterns_combined = connected_components_from_edges(bodies_list, combined_edges_formatted)
			
			# Detect shapes within the combined patterns
			shapes_combined = detect_shapes(pos_combined, patterns_combined, combined_edges_formatted)
			
			# Identify singletons (objects with no aspects)
			connected_objects = set()
			for (p1, p2), _ in combined_edges_formatted:
				connected_objects.add(p1)
				connected_objects.add(p2)
			singleton_map_combined = {
				name: {"deg": deg}
				for name, deg in pos_combined.items()
				if name not in connected_objects
			}
			
			# Store combined circuit data in session state for toggles
			st.session_state["patterns_combined"] = patterns_combined
			st.session_state["shapes_combined"] = shapes_combined
			st.session_state["singleton_map_combined"] = singleton_map_combined
			st.session_state["pos_combined"] = pos_combined
			st.session_state["combined_edges_formatted"] = combined_edges_formatted
			
			# Get toggle states for circuits
			toggles = [
				st.session_state.get(f"toggle_pattern_{i}", False)
				for i in range(len(patterns_combined))
			]
			singleton_toggles = {
				planet: st.session_state.get(f"singleton_{planet}", False)
				for planet in singleton_map_combined
			}
			shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
			
			# Build major_edges_all format for rendering: [((p1, p2), aspect), ...]
			major_edges_all = combined_edges_formatted
			
			# Build filaments (minor aspect links between circuits)
			filaments = []  # For now, keep empty; can be computed later
			
			pattern_labels = [
				st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
				for i in range(len(patterns_combined))
			]
			combo_toggles = {}
			
			# Determine unknown-time flags
			_unknown_time_inner = bool(st.session_state.get("chart_unknown_time", False))
			_unknown_time_outer = bool(st.session_state.get("chart_unknown_time_2", False))
			
			try:
				rr = render_biwheel_chart_with_circuits(
					chart_inner,
					chart_outer,
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
					unknown_time_inner=_unknown_time_inner,
					unknown_time_outer=_unknown_time_outer,
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
			pos_inner = _positions_from_chart(chart_inner)
			pos_outer = _positions_from_chart(chart_outer)

			# Compute ALL inter-chart aspects (no visibility gating).
			# These are used for detecting circuit-to-chart2-shape connections
			# and for drawing filtered aspect lines on the wheel.
			edges_inter_chart_cc: list[tuple[str, str, str]] = []
			for ep1, d1 in pos_inner.items():
				for ep2, d2 in pos_outer.items():
					angle = abs(d1 - d2) % 360
					if angle > 180:
						angle = 360 - angle
					for aspect_name, aspect_data in ASPECTS.items():
						if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
							edges_inter_chart_cc.append((ep1, ep2, aspect_name))
							break

			# Build circuit_connected_shapes2:
			# maps Chart 1 circuit index -> list of Chart 2 shapes whose members
			# are connected to that circuit by at least one inter-chart aspect.
			patterns_1 = st.session_state.get("patterns") or []
			shapes_2 = st.session_state.get("shapes_2") or []
			shapes_1 = st.session_state.get("shapes") or []
			major_edges_all_1 = st.session_state.get("major_edges_all") or []
			singleton_map_1 = st.session_state.get("singleton_map") or {}
			filaments_1 = st.session_state.get("filaments") or []

			circuit_connected_shapes2: dict[int, list] = {}
			for ci, component in enumerate(patterns_1):
				component_set = set(component)
				connected_chart2_bodies: set[str] = set()
				for (ep1, ep2, _) in edges_inter_chart_cc:
					if ep1 in component_set:
						connected_chart2_bodies.add(ep2)
				linked_shapes2 = [
					sh for sh in shapes_2
					if set(sh.get("members", [])) & connected_chart2_bodies
				]
				# Add singleton entries for connected Chart 2 planets not
				# already covered by a linked shape.
				covered = set()
				for sh in linked_shapes2:
					covered.update(sh.get("members", []))
				for planet in sorted(connected_chart2_bodies - covered):
					linked_shapes2.append({
						"type": "Singleton",
						"members": [planet],
						"id": f"singleton_{ci}_{planet}",
					})
				if linked_shapes2:
					circuit_connected_shapes2[ci] = linked_shapes2

			st.session_state["circuit_connected_shapes2"] = circuit_connected_shapes2
			st.session_state["edges_inter_chart_cc"] = edges_inter_chart_cc

			pattern_labels = [
				st.session_state.get(f"circuit_name_{ci}", f"Circuit {ci+1}")
				for ci in range(len(patterns_1))
			]
			toggles = [
				st.session_state.get(f"toggle_pattern_{ci}", False)
				for ci in range(len(patterns_1))
			]
			singleton_toggles = {
				planet: st.session_state.get(f"singleton_{planet}", False)
				for planet in singleton_map_1
			}
			shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})

			_unknown_time_inner = bool(st.session_state.get("chart_unknown_time", False))
			_unknown_time_outer = bool(st.session_state.get("chart_unknown_time_2", False))

			try:
				rr = render_biwheel_connected_circuits(
					chart_inner,
					chart_outer,
					pos_inner=pos_inner,
					pos_outer=pos_outer,
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
					unknown_time_inner=_unknown_time_inner,
					unknown_time_outer=_unknown_time_outer,
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
			pos_inner = _positions_from_chart(chart_inner)
			pos_outer = _positions_from_chart(chart_outer)
			
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
			inner_pos_filtered = {name: deg for name, deg in pos_inner.items() if name in aspect_bodies_inner}
			outer_pos_filtered = {name: deg for name, deg in pos_outer.items() if name in aspect_bodies_outer}
			
			# Get synastry aspect group toggles
			show_inter = st.session_state.get("synastry_aspects_inter", True)
			show_chart1 = st.session_state.get("synastry_aspects_chart1", False)
			show_chart2 = st.session_state.get("synastry_aspects_chart2", False)
			
			# Compute inter-chart aspects (chart 1 to chart 2)
			if show_inter:
				for p1 in inner_pos_filtered:
					for p2 in outer_pos_filtered:
						d1 = inner_pos_filtered[p1]
						d2 = outer_pos_filtered[p2]
						angle = abs(d1 - d2) % 360
						if angle > 180:
							angle = 360 - angle
						
						# Check all aspect types
						for aspect_name, aspect_data in ASPECTS.items():
							if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
								edges_inter_chart.append((p1, p2, aspect_name))
								break  # Only one aspect per pair
			
			# Compute chart 1 internal aspects
			if show_chart1:
				planets_chart1 = list(inner_pos_filtered.keys())
				for i in range(len(planets_chart1)):
					for j in range(i + 1, len(planets_chart1)):
						p1, p2 = planets_chart1[i], planets_chart1[j]
						d1 = inner_pos_filtered[p1]
						d2 = inner_pos_filtered[p2]
						angle = abs(d1 - d2) % 360
						if angle > 180:
							angle = 360 - angle
						
						for aspect_name, aspect_data in ASPECTS.items():
							if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
								edges_chart1.append((p1, p2, aspect_name))
								break
			
			# Compute chart 2 internal aspects
			if show_chart2:
				planets_chart2 = list(outer_pos_filtered.keys())
				for i in range(len(planets_chart2)):
					for j in range(i + 1, len(planets_chart2)):
						p1, p2 = planets_chart2[i], planets_chart2[j]
						d1 = outer_pos_filtered[p1]
						d2 = outer_pos_filtered[p2]
						angle = abs(d1 - d2) % 360
						if angle > 180:
							angle = 360 - angle
						
						for aspect_name, aspect_data in ASPECTS.items():
							if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
								edges_chart2.append((p1, p2, aspect_name))
								break
		
		# Determine unknown-time flags for each chart explicitly.
		# Use only the *calculated* chart_unknown_time keys (set by run_chart)
		# rather than profile_unknown_time which is a live UI widget and may
		# reflect whichever chart the user last edited, not necessarily chart 1.
		_unknown_time_inner = bool(
			st.session_state.get("chart_unknown_time", False)
		)
		_unknown_time_outer = bool(
			st.session_state.get("chart_unknown_time_2", False)
		)
		try:
			rr = render_biwheel_chart(
				chart_inner,
				chart_outer,
				edges_inter_chart=edges_inter_chart,
				edges_chart1=edges_chart1,
				edges_chart2=edges_chart2,
				house_system=house_system,
				dark_mode=dark_mode,
				label_style=label_style,
				figsize=(6.0, 6.0),
				dpi=144,
				unknown_time_inner=_unknown_time_inner,
				unknown_time_outer=_unknown_time_outer,
			)
			st.session_state["render_fig"] = rr.fig
			st.session_state["render_result"] = rr
			# If Compass Rose is toggled, ensure all AC/DC canonical variants are present
			# Debugging: Log visible_objects before updating session state
			print(f"rr.visible_objects: {rr.visible_objects}")
			print(f"toggle_compass_rose: {st.session_state.get('toggle_compass_rose', False)}")

			# Update session state with visible_objects
			visible_objects = set(rr.visible_objects)
			if st.session_state.get("toggle_compass_rose", False):
				visible_objects.update(["Ascendant", "AC", "Asc", "Descendant", "DC"])
			print(f"Updated visible_objects: {visible_objects}")
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
	pos = st.session_state.get("chart_positions")

	if chart is None or pos is None:
		return

	# ⬇️ START: NEW BLOCK TO PULL CIRCUIT DATA FROM RENDER_RESULT ⬇️
	# Retrieve the circuit data from the stored RenderResult set by run_chart
	stored_rr = st.session_state.get("render_result")
	
	# The data is already available in Session State keys, but we use a fallback if needed
	patterns_data = st.session_state.get("patterns") or []
	shapes_data = st.session_state.get("shapes") or []
	singleton_map_data = st.session_state.get("singleton_map") or {}

	# If the new 'render_result' object has been set, prioritize pulling from it
	# This ensures we have the most current calculated state.
	if stored_rr:
		patterns_data = getattr(stored_rr, 'patterns', patterns_data)
		shapes_data = getattr(stored_rr, 'shapes', shapes_data)
		singleton_map_data = getattr(stored_rr, 'singleton_map', singleton_map_data)
	
	# ⬆️ END: NEW BLOCK TO PULL CIRCUIT DATA FROM RENDER_RESULT ⬆️

	patterns = st.session_state.get("patterns") or []
	# ... (rest of the old retrievals continue below)

	if chart is None or pos is None:
		return

	patterns = st.session_state.get("patterns") or []
	shapes = st.session_state.get("shapes") or []
	filaments = st.session_state.get("filaments") or []
	combos = st.session_state.get("combos") or {}
	singleton_map = st.session_state.get("singleton_map") or {}
	major_edges_all = st.session_state.get("major_edges_all") or []

	pattern_labels = [
		st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
		for i in range(len(patterns))
	]
	toggles = [
		st.session_state.get(f"toggle_pattern_{i}", False)
		for i in range(len(patterns))
	]
	singleton_toggles = {
		planet: st.session_state.get(f"singleton_{planet}", False)
		for planet in singleton_map
	}
	shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
	combo_toggles = st.session_state.get("combo_toggles", {})

	house_system = st.session_state.get("house_system", "placidus")
	label_style = st.session_state.get("label_style", "glyph")
	dark_mode = st.session_state.get("dark_mode", False)

	edges_major = st.session_state.get("edges_major") or []
	edges_minor = st.session_state.get("edges_minor") or []

	# Check if we're in Standard Chart mode
	chart_mode = st.session_state.get("chart_mode", "Circuits")
	
	if chart_mode == "Standard Chart":
		# Standard Chart mode: compute aspects for PLANETS_PLUS only
		
		# Build list of bodies to compute aspects for: PLANETS_PLUS + selected TOGGLE_ASPECTS
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
		
		# Debugging: Log standard_pos and ASPECTS
		print(f"[DEBUG] standard_pos: {standard_pos}")
		print(f"[DEBUG] ASPECTS: {ASPECTS}")

		# Compute all aspects between aspect-enabled bodies
		standard_edges = []
		planets_list = list(standard_pos.keys())
		for i in range(len(planets_list)):
			for j in range(i + 1, len(planets_list)):
				p1, p2 = planets_list[i], planets_list[j]
				d1, d2 = standard_pos[p1], standard_pos[p2]
				angle = abs(d1 - d2) % 360
				if angle > 180:
					angle = 360 - angle
				
				# Check all aspect types
				for aspect_name, aspect_data in ASPECTS.items():
					if abs(angle - aspect_data["angle"]) <= aspect_data["orb"]:
						standard_edges.append((p1, p2, aspect_name))
						break  # Only one aspect per pair
		
		# Use render_chart for standard mode with all MAJOR_OBJECTS visible
		try:
			compass_on = st.session_state.get(COMPASS_KEY, True)
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
				dark_mode=resolved_dark_mode,
				visible_toggle_state=visible_objects,  # Show all MAJOR_OBJECTS
				edges_major=standard_edges,
				edges_minor=[],
				house_system=_selected_house_system(),
				label_style=st.session_state.get("label_style", "glyph"),
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
			
			# Debugging: Log visible_objects before updating session state
			print(f"rr.visible_objects: {rr.visible_objects}")
			print(f"toggle_compass_rose: {st.session_state.get('toggle_compass_rose', False)}")

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
				dark_mode=resolved_dark_mode,
				visible_toggle_state=None,
				edges_major=edges_major,
				edges_minor=edges_minor,
				house_system=_selected_house_system(),
				label_style=st.session_state.get("label_style", "glyph"),
				compass_on=st.session_state.get("toggle_compass_rose", True),
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
		)
		
		st.session_state["DISPOSITOR_GRAPH_DATA"] = plot_data
		
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
	edges_major, edges_minor = build_aspect_edges(
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
		st.session_state["last_sect"] = chart_sect_from_chart(chart)
		st.session_state["last_sect_error"] = None
	except Exception as e:
		st.session_state["last_sect"] = None
		st.session_state["last_sect_error"] = str(e)
	
	# Conjunction Clusters
	clusters_rows, _, _ = build_conjunction_clusters(chart, edges_major)
	st.session_state["conj_clusters_rows"] = clusters_rows
	
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
	# 7. Final Session State Keys (for old code compatibility)
	# ------------------------------------------------------------------
	# Restore the large update block from run_chart
	st.session_state.update({
		f"last_chart{suffix}": chart,
		f"last_df{suffix}": df_positions,
		f"last_aspect_df{suffix}": aspect_df_result, # Added back
		f"edges_major{suffix}": edges_major,
		f"edges_minor{suffix}": edges_minor,
		f"patterns{suffix}": patterns,
		f"shapes{suffix}": shapes,
		f"filaments{suffix}": filaments,           # Added back
		f"singleton_map{suffix}": singleton_map,
		f"combos{suffix}": combos,                 # Added back
		f"chart_positions{suffix}": pos_chart,     # Added back (now pos_chart)
		f"major_edges_all{suffix}": major_edges_all, # Added back
		f"chart_dt_utc{suffix}": utc_dt,
		f"chart_unknown_time{suffix}": chart_unknown_time,
		f"house_angles_df{suffix}": None,
		f"dispositor_summary_rows{suffix}": dispositor_summary_rows,
		f"dispositor_chains_rows{suffix}": dispositor_chains_rows,
	})
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
		)
	except Exception as e:
		st.error(f"Transit chart calculation failed: {e}")
		return False

	# --- Minimal post-processing for Chart 2 ---
	edges_major, edges_minor = build_aspect_edges(chart, compass_rose=False)
	annotate_chart(chart, edges_major)

	# --- Store under _2 keys so _refresh_chart_figure picks them up ---
	# Also build Chart 2 circuit data (shapes, positions) so Connected Circuits mode works
	try:
		from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_chart
		pos_chart2, patterns_sets2, major_edges_all2 = prepare_pattern_inputs(df_positions, edges_major)
		patterns2 = [sorted(list(s)) for s in patterns_sets2]
		shapes2   = detect_shapes(pos_chart2, patterns_sets2, major_edges_all2)
	except Exception:
		pos_chart2, patterns2, shapes2 = {}, [], []

	st.session_state.update({
		"last_chart_2":         chart,
		"last_df_2":            df_positions,
		"last_aspect_df_2":     aspect_df_result,
		"edges_major_2":        edges_major,
		"edges_minor_2":        edges_minor,
		"chart_unknown_time_2": False,
		"chart_dt_utc_2":       ut.replace(tzinfo=None),
		"chart_2_source":       "transit",
		# Circuit data for Chart 2 (needed by Connected Circuits mode)
		"chart_positions_2":    pos_chart2,
		"patterns_2":           patterns2,
		"shapes_2":             shapes2,
	})
	return True