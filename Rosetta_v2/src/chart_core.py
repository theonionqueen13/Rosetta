# src/chart_core.py
from drawing_v2 import RenderResult, render_chart, render_chart_with_shapes, render_biwheel_chart, extract_positions
import streamlit as st
import datetime as dt
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, Tuple
import pandas as pd
from toggles_v2 import COMPASS_KEY
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_dataframe, generate_combo_groups
# Import the new geocoding module
from src.geocoding import geocode_city_with_timezone
# Import the core calculation functions from the original calc_v2.py
from calc_v2 import calculate_chart, chart_sect_from_df, build_aspect_edges, \
                    annotate_reception, build_dispositor_tables, \
                    build_conjunction_clusters, plot_dispositor_graph 
from event_lookup_v2 import update_events_html_state
# You'll also need the global constants from the lookup file:
from lookup_v2 import MAJOR_OBJECTS, TOGGLE_ASPECTS, ASPECTS, PLANETS_PLUS
# And the house system selector:
from house_selector_v2 import _selected_house_system


def get_chart_inputs_from_session(suffix: str = "") -> Dict[str, Any]:
    """Extracts all necessary birth data inputs from session state."""
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

def _refresh_chart_figure():
	"""Rebuild the chart figure using the current session-state toggles."""
	# Check if we're in synastry mode
	synastry_mode = st.session_state.get("synastry_mode", False)
	
	if synastry_mode:
		# Synastry/biwheel mode: need both charts
		df_inner = st.session_state.get("last_df")
		df_outer = st.session_state.get("last_df_2")
		
		if df_inner is None or df_outer is None:
			# If we don't have both charts yet, fall back to single chart
			if df_inner is None:
				return
			df_outer = df_inner  # Use same chart for both rings as fallback
		
		house_system = st.session_state.get("house_system", "placidus")
		label_style = st.session_state.get("label_style", "glyph")
		dark_mode = st.session_state.get("dark_mode", False)
		chart_mode = st.session_state.get("chart_mode", "Circuits")
		
		# Compute aspects for Standard Chart mode
		edges_inter_chart = []
		edges_chart1 = []
		edges_chart2 = []
		
		if chart_mode == "Standard Chart":
			# Get positions for both charts
			pos_inner = extract_positions(df_inner)
			pos_outer = extract_positions(df_outer)
			
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
		
		try:
			rr = render_biwheel_chart(
				df_inner,
				df_outer,
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
			# If Compass Rose is toggled, ensure all AC/DC canonical variants are present
			visible_objects = set(rr.visible_objects)
			if st.session_state.get("toggle_compass_rose", False):
				visible_objects.update(["Ascendant", "AC", "Asc", "Descendant", "DC"])
			st.session_state["visible_objects"] = sorted(visible_objects)
			st.session_state["active_shapes"] = []
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = None
			return
		except Exception as e:
			st.error(f"Biwheel chart rendering failed: {e}")
			# Fall through to regular chart rendering
	
	# Regular single-chart mode
	df = st.session_state.get("last_df")
	pos = st.session_state.get("chart_positions")

	# Regular single-chart mode
	df = st.session_state.get("last_df")
	pos = st.session_state.get("chart_positions")

	if df is None or pos is None:
		return

	# ⬇️ START: NEW BLOCK TO PULL CIRCUIT DATA FROM RENDER_RESULT ⬇️
	# Retrieve the circuit data from the stored RenderResult set by calculate_chart_from_session
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

	if df is None or pos is None:
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
		
		# Get all MAJOR_OBJECTS that exist in the chart for display
		major_pos = {name: deg for name, deg in pos.items() if name in MAJOR_OBJECTS}
		
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
			if compass_on:
				for axis in ["Ascendant", "Descendant", "AC", "DC"]:
					if axis in df["Object"].values and axis not in visible_objects:
						visible_objects.append(axis)
			rr = render_chart(
				df,
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
			st.session_state["visible_objects"] = rr.visible_objects
			st.session_state["active_shapes"] = []
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = None
		except Exception as e:
			st.error(f"Standard chart rendering failed: {e}")
			return
	else:
		# Circuits mode: use existing logic
		try:
			fig, visible_objects, active_shapes, cusps, out_text = render_chart_with_shapes(
				pos=pos,
				patterns=patterns,
				pattern_labels=pattern_labels,
				toggles=toggles,
				filaments=filaments,
				house_system=_selected_house_system(),
				combo_toggles=combo_toggles,
				label_style=label_style,
				singleton_map=singleton_map or {},
				df=df,
				dark_mode=resolved_dark_mode,
				shapes=shapes,
				shape_toggles_by_parent=shape_toggles_by_parent,
				singleton_toggles=singleton_toggles,
				major_edges_all=major_edges_all,
			)
		except Exception:
			rr = render_chart(
				df,
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
			st.session_state["active_shapes"] = []
			st.session_state["last_cusps"] = rr.cusps
			st.session_state["ai_text"] = None
		else:
			st.session_state["render_fig"] = fig
			st.session_state["visible_objects"] = sorted(visible_objects)
			st.session_state["active_shapes"] = active_shapes
			st.session_state["last_cusps"] = cusps
			st.session_state["ai_text"] = out_text
			st.session_state["render_result"] = None
			
def calculate_chart_from_session(suffix: str = "") -> bool:
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
    
    # 1. Input Validation and Time Parsing (UNCHANGED)
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
    update_events_html_state(utc_dt)
        
    # 4. Core Calculation (include_aspects=False is intentional for new flow)
    try:
        utc_tz_offset = 0
        (
            df_positions,
            aspect_df_result,
            plot_data
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
        
        house_angles_df = df_positions[df_positions["Object"].str.contains("cusp")].copy()
        chart_data_summary = df_positions 
		
        st.session_state["DISPOSITOR_GRAPH_DATA"] = plot_data
		
    except Exception as e:
        st.error(f"Core astrological calculation failed: {e}")
        return False

    # ------------------------------------------------------------------
    # 5. POST-PROCESSING (All Logic from run_chart is re-added here)
    # ------------------------------------------------------------------
    
    # Aspect Edge Calculation
    include_compass_rose = st.session_state.get("ui_compass_overlay", False) 
    edges_major, edges_minor = build_aspect_edges(
        df_positions, 
        compass_rose=include_compass_rose
    )
    
    # ⬇️ MISSING POST-PROCESSING ADDED ⬇️
    # Annotate Reception
    df_positions = annotate_reception(df_positions, edges_major)
    
    # Chart Sect
    try:
        st.session_state["last_sect"] = chart_sect_from_df(df_positions)
        st.session_state["last_sect_error"] = None
    except Exception as e:
        st.session_state["last_sect"] = None
        st.session_state["last_sect_error"] = str(e)
    
    # Conjunction Clusters
    clusters_rows = build_conjunction_clusters(df_positions, edges_major)
    st.session_state["conj_clusters_rows"] = clusters_rows
    
    # Dispositors (already existed, but ensures order)
    dispositor_summary_rows, dispositor_chains_rows = build_dispositor_tables(df_positions)
    
    # ⬇️ CIRCUIT/SHAPE/SINGLETON DETECTION (CORRECTED SIGNATURE) ⬇️
    try:
        # Corrected call to get all 3 outputs (was butchered in refactor)
        pos_chart, patterns_sets, major_edges_all = prepare_pattern_inputs(df_positions, edges_major)
        
        patterns = [sorted(list(s)) for s in patterns_sets]
        shapes = detect_shapes(pos_chart, patterns_sets, major_edges_all)
        
        # Missing minor links/singletons logic added back
        filaments, singleton_map = detect_minor_links_from_dataframe(df_positions, edges_major)
        combos = generate_combo_groups(filaments)
        
    except Exception as e:
        print(f"Warning: Circuit detection failed: {e}")
        # Defaults remain as empty lists/dicts
        pos_chart = {}
        
    # ------------------------------------------------------------------
    # 6. Store ALL Results in RenderResult Object
    # ------------------------------------------------------------------
    
    # Prepare data for RenderResult
    positions = dict(zip(df_positions['Object'], df_positions['Longitude']))
    cusps = list(house_angles_df['Longitude'])
    visible_objects = st.session_state.get(f"visible_objects{suffix}", [])
    
    # FIX: Corrected list comprehension for edges (from last step)
    drawn_major_edges = [tuple(e) for e in edges_major] 
    drawn_minor_edges = [tuple(e) for e in edges_minor]
    
    fig_placeholder, ax_placeholder = None, None 
    
    render_result = RenderResult( 
        fig=fig_placeholder, ax=ax_placeholder,
        positions=positions, cusps=cusps,
        visible_objects=visible_objects,
        drawn_major_edges=drawn_major_edges,
        drawn_minor_edges=drawn_minor_edges,
        
        # CIRCUIT DATA
        patterns=patterns,
        shapes=shapes,
        singleton_map=singleton_map,
    )
    
    st.session_state["render_result"] = render_result
    
    # ------------------------------------------------------------------
    # 7. Final Session State Keys (for old code compatibility)
    # ------------------------------------------------------------------
    # Restore the large update block from run_chart
    st.session_state.update({
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
        f"house_angles_df{suffix}": house_angles_df,
        f"dispositor_summary_rows{suffix}": dispositor_summary_rows,
        f"dispositor_chains_rows{suffix}": dispositor_chains_rows,
    })

    # 8. Trigger Figure Refresh (MISSING CALL FROM run_chart)
    _refresh_chart_figure()
    
    # 9. UI State Defaults (MISSING BLOCK FROM run_chart)
    for i in range(len(patterns)):
        st.session_state.setdefault(f"toggle_pattern_{i}", False)
        st.session_state.setdefault(f"circuit_name_{i}", f"Circuit {i+1}")

    if singleton_map:
        for planet in singleton_map.keys():
            st.session_state.setdefault(f"singleton_{planet}", False)

    return True