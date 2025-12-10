import os
# --- Set Swiss Ephemeris path before any other imports ---
import swisseph as swe
EPHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "ephe"))
EPHE_PATH = EPHE_PATH.replace("\\", "/")
os.environ["SE_EPHE_PATH"] = EPHE_PATH
swe.set_ephe_path(EPHE_PATH)

from typing import Dict, Any, List, Optional, Tuple
from src.data_stubs import (
	current_user_id, save_user_profile_db, load_user_profiles_db, 
	delete_user_profile_db, community_save, community_list, 
	community_get, community_load, community_delete, is_admin
)
from src.ui_utils import apply_custom_css, set_background_for_theme
from src.test_data import apply_test_chart_to_session, MONTH_NAMES
from src.geocoding import geocode_city_with_timezone
from src.chart_core import calculate_chart_from_session
from src.state_manager import swap_primary_and_secondary_charts
import sys

# Add the Rosetta project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)

from typing import Dict, Any, List, Optional, Tuple
from house_selector_v2 import _selected_house_system
from donate_v2 import donate_chart
from now_v2 import render_now_widget
from event_lookup_v2 import update_events_html_state
import datetime as dt
from datetime import datetime
from zoneinfo import ZoneInfo
import pytz
from profiles_v2 import format_object_profile_html, ordered_object_rows
import os, importlib.util, streamlit as st
from interp import ChartInterpreter
st.set_page_config(layout="wide")
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_dataframe, generate_combo_groups, edges_from_major_list
from drawing_v2 import render_chart, render_chart_with_shapes, render_biwheel_chart, extract_positions
from wizard_v2 import render_guided_wizard
from toggles_v2 import render_circuit_toggles
from profile_manager_v2 import render_profile_manager, ensure_profile_session_defaults
from calc_v2 import (
    calculate_chart, chart_sect_from_df, build_aspect_edges, 
    annotate_reception, build_dispositor_tables, 
    build_conjunction_clusters, plot_dispositor_graph, analyze_dispositors
)
from lookup_v2 import SIGNS, PLANETARY_RULERS, PLANETS_PLUS, ASPECTS, MAJOR_OBJECTS, TOGGLE_ASPECTS

# Key initialization:
st.session_state.setdefault("last_test_chart", None)
st.session_state.setdefault("last_test_chart_2", None)

# Initialize birth data defaults for Chart 1
st.session_state.setdefault("year", datetime.now().year)
st.session_state.setdefault("month_name", "January")
st.session_state.setdefault("day", 1)
st.session_state.setdefault("hour_12", "12")
st.session_state.setdefault("minute_str", "00")
st.session_state.setdefault("ampm", "PM")
st.session_state.setdefault("city", "New York, NY")
st.session_state.setdefault("chart_dt_utc", None)
st.session_state.setdefault("defaults_loaded", False)

# Initialize birth data defaults for Chart 2 (if synastry is on)
st.session_state.setdefault("test_chart_2", "Custom")

apply_custom_css() # Call the imported CSS function

current_user_id = "test-user"

COMPASS_KEY = "ui_compass_overlay"

# --- Pick backgrounds for each theme and apply ---
LIGHT_BG = "Rosetta_v2/pngs/nebula2.jpg"
DARK_BG  = "Rosetta_v2/pngs/galaxies.jpg"
LIGHT_OVERLAY = 0.20
DARK_OVERLAY  = 0.45

resolved_dark_mode = set_background_for_theme(
	light_image_path=LIGHT_BG,
	dark_image_path=DARK_BG,
	light_overlay=LIGHT_OVERLAY,
	dark_overlay=DARK_OVERLAY,
	dark_mode=st.session_state.get("dark_mode", False),
)

# --- Sidebar profile styling (single-space lines + thin separators) ---
st.sidebar.markdown("""
<style>
/* Wrap each profile in .profile-card when rendering below */
.profile-card {
  line-height: 1.05;               /* keeps your single-spacing feel */
  white-space: pre-wrap;            /* preserves your <br> line breaks */
  border-bottom: 1px solid rgba(255,255,255,0.18);  /* thin divider */
  padding-bottom: 10px;
  margin-bottom: 10px;
}
.profile-card:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

# --- Handle pending chart swap BEFORE any widgets are created ---
# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)

# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)

# --- Handle pending chart swap BEFORE any widgets are created ---
if st.session_state.get("__pending_swap_charts__"):
    swap_primary_and_secondary_charts()

synastry_mode = st.checkbox("Synastry Mode", key="synastry_mode")

# Primary chart selector
test_chart = st.radio(
	"Test Charts" if not synastry_mode else "Chart 1 (Inner)",
	["Custom", "Wildhorse", "Joylin", "Terra", "Jessica"],
	horizontal=True,
	key="test_chart_radio",
	label_visibility="collapsed"
)

# Only apply test chart data if the selection changed (not on every rerun)
if test_chart != st.session_state["last_test_chart"] and test_chart != "Custom":
    st.session_state["last_test_chart"] = test_chart

    # 1. Apply data
    apply_test_chart_to_session(test_chart)

    # 2. Trigger calculation for Chart 1 (no suffix)
    if calculate_chart_from_session():
        st.success(f"Chart 1 loaded: {st.session_state.get('city')}")
    else:
        st.error(f"Failed to calculate Chart 1. Check date/time/location inputs.")

elif test_chart == "Custom":
    st.session_state["last_test_chart"] = "Custom"

# Secondary chart selector (only visible in synastry mode)
if synastry_mode:
	test_chart_2 = st.radio(
		"Chart 2 (Outer)",
		["Custom", "Wildhorse", "Joylin", "Terra", "Jessica"],
		horizontal=True,
		key="test_chart_2",
		label_visibility="collapsed"
	)
	# Show what charts are currently loaded
	df2_city = st.session_state.get("city_2", "Not set")
	st.caption(f"Chart 2 data: {df2_city}, DF exists: {st.session_state.get('last_df_2') is not None}")
else:
	test_chart_2 = None

# Handle second chart selection (for synastry mode)
if synastry_mode and test_chart_2:
    # Calculate if: (1) chart changed OR (2) chart is selected but df doesn't exist
    chart_changed = test_chart_2 != st.session_state["last_test_chart_2"]
    df_missing = st.session_state.get("last_df_2") is None

    should_calculate = chart_changed and test_chart_2 != "Custom"

    # Also calculate if a non-Custom chart is selected but no data exists yet
    if test_chart_2 != "Custom" and df_missing:
        should_calculate = True

    if should_calculate:
        st.session_state["last_test_chart_2"] = test_chart_2

        # 1. Apply data for Chart 2
        success_apply = apply_test_chart_to_session(test_chart_2, suffix="_2")

        if success_apply:
            # 2. Trigger calculation for Chart 2 (with suffix)
            if calculate_chart_from_session(suffix="_2"):
                st.success(f"Chart 2 loaded: {st.session_state.get('city_2')}")
            else:
                st.error(f"Failed to calculate Chart 2. Check date/time/location inputs.")
        else:
            st.error(f"Error: Could not find test chart data for {test_chart_2}")

    elif test_chart_2 == "Custom":
        st.session_state["last_test_chart_2"] = "Custom"

# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)

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

def run_chart(lat, lon, tz_name):
	"""
	Build chart DF, aspects, dispositors, clusters, circuits/shapes—then render.
	"""
	# --- Inputs from session ---
	year   = int(st.session_state["profile_year"])
	month  = MONTH_NAMES.index(st.session_state["profile_month_name"]) + 1
	day    = int(st.session_state["profile_day"])
	hour   = int(st.session_state["profile_hour"])
	minute = int(st.session_state["profile_minute"])
	unknown_time = bool(st.session_state.get("profile_unknown_time"))

	# --- Determine UTC chart datetime ---
	new_chart_dt_utc = None
	try:
		tzinfo = ZoneInfo(tz_name) if tz_name else None
	except Exception:
		tzinfo = None

	if tzinfo:
		try:
			chart_dt_local = datetime(year, month, day, hour, minute, tzinfo=tzinfo)
			new_chart_dt_utc = chart_dt_local.astimezone(ZoneInfo("UTC"))
		except Exception:
			new_chart_dt_utc = None

	st.session_state["chart_dt_utc"] = new_chart_dt_utc
	st.session_state[COMPASS_KEY] = True
	update_events_html_state(new_chart_dt_utc)

	# --- Calculate chart ---
	combined_df, aspect_df, raw_plot_data = calculate_chart(
		year=year, month=month, day=day, hour=hour, minute=minute,
		tz_offset=0, lat=lat, lon=lon, input_is_ut=False,
		tz_name=tz_name, include_aspects=True, unknown_time=unknown_time
	)

	st.session_state["chart_unknown_time"] = unknown_time
	df = combined_df
	st.session_state["dispositor_summary_rows"] = df.to_dict("records")

	# --- Use the plot_data returned from calculate_chart ---
	st.session_state["plot_data"] = raw_plot_data

	# Optional: keep summary tables for UI
	chains_rows, summary_rows = build_dispositor_tables(df)
	st.session_state["dispositor_summary_rows"] = summary_rows
	st.session_state["dispositor_chains_rows"] = chains_rows

	# --- Build aspects / reception / clusters / patterns ---
	compass_rose = st.session_state.get("ui_compass_overlay", False)
	edges_major, edges_minor = build_aspect_edges(df, compass_rose=compass_rose)
	df = annotate_reception(df, edges_major)

	try:
		st.session_state["last_sect"] = chart_sect_from_df(df)
		st.session_state["last_sect_error"] = None
	except Exception as e:
		st.session_state["last_sect"] = None
		st.session_state["last_sect_error"] = str(e)

	clusters_rows = build_conjunction_clusters(df, edges_major)
	st.session_state["conj_clusters_rows"] = clusters_rows

	pos_chart, patterns_sets, major_edges_all = prepare_pattern_inputs(df, edges_major)
	patterns = [sorted(list(s)) for s in patterns_sets]
	shapes   = detect_shapes(pos_chart, patterns_sets, major_edges_all)
	filaments, singleton_map = detect_minor_links_from_dataframe(df, edges_major)
	combos = generate_combo_groups(filaments)

	st.session_state.update({
		"last_df": df,
		"last_aspect_df": aspect_df,
		"edges_major": edges_major,
		"edges_minor": edges_minor,
		"patterns": patterns,
		"shapes": shapes,
		"filaments": filaments,
		"singleton_map": singleton_map,
		"combos": combos,
		"chart_positions": pos_chart,
		"major_edges_all": major_edges_all
	})

	# --- Build chart figure ---
	_refresh_chart_figure()
	st.session_state.update({
		"calc_lat": lat,
		"calc_lon": lon,
		"calc_tz": tz_name
	})

	# --- UI state defaults ---
	for i in range(len(patterns)):
		st.session_state.setdefault(f"toggle_pattern_{i}", False)
		st.session_state.setdefault(f"circuit_name_{i}", f"Circuit {i+1}")

	if singleton_map:
		for planet in singleton_map.keys():
			st.session_state.setdefault(f"singleton_{planet}", False)

col_left, col_mid, col_right = st.columns([3, 2, 3])
# -------------------------
# Left column: Birth Data (FORM)
# -------------------------
with col_left:
	with st.expander("📆 Enter Birth Data", expanded=True):
		# --- Unknown Time (live) OUTSIDE the form ---
		# Model/state keys used by the rest of your app
		st.session_state.setdefault("profile_unknown_time", False)
		st.session_state.setdefault("hour_12", "12")
		st.session_state.setdefault("minute_str", "00")
		st.session_state.setdefault("ampm", "AM")

		# UI widget gets its OWN key to avoid collisions with any other widget/modules
		st.session_state.setdefault("unknown_time_ui", st.session_state["profile_unknown_time"])

		def _apply_unknown_time():
			ut = st.session_state["unknown_time_ui"]  # read the UI widget
			st.session_state["profile_unknown_time"] = ut  # sync canonical state
			if ut:
				st.session_state["hour_12"]    = "--"
				st.session_state["minute_str"] = "--"
				st.session_state["ampm"]       = "--"
			else:
				# restore defaults only if placeholders were in use
				if st.session_state["hour_12"] == "--":
					st.session_state["hour_12"] = "12"
				if st.session_state["minute_str"] == "--":
					st.session_state["minute_str"] = "00"
				if st.session_state["ampm"] == "--":
					st.session_state["ampm"] = "AM"

		# --- Unknown Time (live) OUTSIDE the form ---
		st.session_state.setdefault("profile_unknown_time", False)
		st.session_state.setdefault("hour_12", "12")
		st.session_state.setdefault("minute_str", "00")
		st.session_state.setdefault("ampm", "AM")

		def _apply_unknown_time():
			if st.session_state["profile_unknown_time"]:
				st.session_state["hour_12"]    = "--"
				st.session_state["minute_str"] = "--"
				st.session_state["ampm"]       = "--"
			else:
				if st.session_state["hour_12"] == "--":    st.session_state["hour_12"] = "12"
				if st.session_state["minute_str"] == "--":  st.session_state["minute_str"] = "00"
				if st.session_state["ampm"] == "--":        st.session_state["ampm"] = "AM"

		st.checkbox(
			"Unknown Time",
			key="profile_unknown_time",
			on_change=_apply_unknown_time,
		)
		
		with st.form("birth_form", clear_on_submit=False):
			# --- Two columns: Date/Day (left) and City (right) ---
			col1, col2 = st.columns([3, 2])

			# Left: Date & Day
			with col1:
				year = st.number_input(
					"Year",
					min_value=1000,
					max_value=3000,
					step=1,
					key="year",
				)

				import calendar
				month_name = st.selectbox(
					"Month",
					MONTH_NAMES,
					key="month_name",
				)
				month = MONTH_NAMES.index(month_name) + 1
				days_in_month = calendar.monthrange(year, month)[1]

				day = st.selectbox(
					"Day",
					list(range(1, days_in_month + 1)),
					key="day",
				)

			# Right: City of Birth (restored)
			with col2:
				st.text_input("City of Birth", key="city")

			# --- Time widgets row ---
			unknown_time = st.session_state["profile_unknown_time"]

			HOURS   = ["--"] + [f"{h:02d}" for h in range(1, 13)]
			MINUTES = ["--"] + [f"{m:02d}" for m in range(0, 60)]
			AMPMS   = ["--", "AM", "PM"]

			tcol1, tcol2, tcol3 = st.columns(3)
			with tcol1:
				st.selectbox("Birth Time", options=HOURS,   key="hour_12",    disabled=unknown_time)
			with tcol2:
				st.selectbox(" ",          options=MINUTES, key="minute_str", disabled=unknown_time)
			with tcol3:
				st.selectbox(" ",          options=AMPMS,   key="ampm",       disabled=unknown_time)

			# Read + normalize once
			hour_12    = st.session_state["hour_12"]
			minute_str = st.session_state["minute_str"]
			ampm       = st.session_state["ampm"]

			if unknown_time or hour_12 == "--" or minute_str == "--" or ampm == "--":
				birth_hour_24 = None
				birth_minute  = None
			else:
				h12 = int(hour_12)
				birth_minute = int(minute_str)
				birth_hour_24 = (0 if h12 == 12 else h12) if ampm == "AM" else (12 if h12 == 12 else h12 + 12)

			# Persist normalized values if you need them elsewhere
			st.session_state["profile_birth_hour_24"] = birth_hour_24
			st.session_state["profile_birth_minute"]  = birth_minute
			
			submitted = st.form_submit_button("Calculate Chart")

			if submitted:
				# Trigger the calculation for Chart 1 (no suffix).
				# This reads all inputs from st.session_state (which were populated by the form's key values).
				success = calculate_chart_from_session(suffix="")
				
				if success:
					st.success(f"Chart successfully calculated for {st.session_state.get('city')}.")
					# Clear the render_fig state to force the chart to be redrawn
					st.session_state["render_fig"] = None
					# Use st.rerun() to immediately display the chart if needed, 
					# otherwise the chart will display on the next Streamlit run.
					# st.rerun() 
				else:
					# This message appears if geocoding failed or date/time parsing failed
					st.error(f"Calculation failed! Please ensure all date/time fields are valid and the city lookup succeeds.")
			
			if submitted:
				if unknown_time:
					# Your policy for unknown time (noon chart is common)
					hour_val   = 12
					minute_val = 0
				else:
					hour_val   = birth_hour_24
					minute_val = birth_minute

				st.session_state["hour_val"] = hour_val
				st.session_state["minute_val"] = minute_val

				# City text comes from key="city"
				city_query = (st.session_state.get("city") or "").strip()
				st.session_state["city_query"] = city_query

				try:
					lat, lon, tz_name, formatted_address = geocode_city_with_timezone(
						city_query
					)
					# Make the location visible to drawing_v2
					if lat is not None and lon is not None:
						st.session_state["chart_lat"] = float(lat)
						st.session_state["chart_lon"] = float(lon)
					else:
						# Explicitly clear if lookup failed, so we fall back to 🌐
						st.session_state["chart_lat"] = None
						st.session_state["chart_lon"] = None

				except Exception as e:
					st.session_state["last_location"] = None
					st.session_state["last_timezone"] = f"Lookup error: {e}"
					lat = lon = tz_name = None
				else:
					if lat is not None and lon is not None and tz_name:
						st.session_state["last_location"] = formatted_address or city_query
						st.session_state["last_timezone"] = tz_name
						st.session_state["current_lat"] = lat
						st.session_state["current_lon"] = lon
						st.session_state["current_tz_name"] = tz_name
					else:
						st.session_state["last_location"] = None
						st.session_state["last_timezone"] = "City not found. Try a more specific query."

				# Persist “profile_*” used by run_chart
				st.session_state["profile_year"] = year
				st.session_state["profile_month_name"] = month_name
				st.session_state["profile_day"] = day
				st.session_state["profile_hour"] = hour_val
				st.session_state["profile_minute"] = minute_val
				st.session_state["profile_city"] = city_query

				# Calculate chart only on submit
				if lat is None or lon is None or tz_name is None:
					st.error("Please enter a valid city and make sure lookup succeeds.")
				else:
					run_chart(lat, lon, tz_name)

				# --- Build chart datetime safely (handles Unknown Time + string widgets) ---
				year  = int(st.session_state["year"])
				month = MONTH_NAMES.index(st.session_state["month_name"]) + 1
				day   = int(st.session_state["day"])

				unknown_time = st.session_state.get("profile_unknown_time", False)
				h_str = st.session_state.get("hour_12", "--")      # "--" or "01".."12"
				m_str = st.session_state.get("minute_str", "--")   # "--" or "00".."59"
				ap    = st.session_state.get("ampm", "--")         # "--" or "AM"/"PM"

				chart_dt_local = None
				chart_dt_utc   = None

				if not (unknown_time or h_str == "--" or m_str == "--" or ap == "--"):
					h12    = int(h_str)
					minute = int(m_str)
					if ap == "AM":
						hour24 = 0 if h12 == 12 else h12
					else:
						hour24 = 12 if h12 == 12 else h12 + 12

					if tz_name:
						tzinfo = ZoneInfo(tz_name)
						chart_dt_local = datetime(year, month, day, hour24, minute, tzinfo=tzinfo)
						chart_dt_utc   = chart_dt_local.astimezone(ZoneInfo("UTC"))
					else:
						chart_dt_local = datetime(year, month, day, hour24, minute)
						chart_dt_utc   = None

				st.session_state["chart_dt_local"] = chart_dt_local
				st.session_state["chart_dt_utc"]   = chart_dt_utc

				# Location info BELOW, optional
				if st.session_state.get("last_location"):
					st.success(f"Found: {st.session_state['last_location']}")
					if st.session_state.get("last_timezone"):
						st.write(f"Timezone: {st.session_state['last_timezone']}")
			elif st.session_state.get("last_timezone"):
				st.error(st.session_state["last_timezone"])


df_cached     = st.session_state.get("last_df")# --- Quick city UI state defaults & safe-clear ---
st.session_state.setdefault("show_now_city_field", False)
st.session_state.setdefault("now_city_temp", "")
st.session_state.setdefault("__clear_now_city_temp__", False)
st.session_state.setdefault("__now_city_submit__", False)  # <- fire on Enter

# Clear the quick-city field safely BEFORE any widgets are instantiated here
if st.session_state.get("__clear_now_city_temp__", False):
	st.session_state.pop("now_city_temp", None)
	st.session_state["__clear_now_city_temp__"] = False

# Enter key callback (no-arg fn)
def _mark_now_city_entered():
	st.session_state["__now_city_submit__"] = True

# Optional geocoder hook: define to avoid NameError in this file
# Replace this later with: from your_module import lookup_city as geocode_city
try:
	geocode_city  # type: ignore  # if not defined, NameError
except NameError:
	geocode_city = None

with col_mid:
	with st.container():
		render_now_widget(
			col_mid,
			MONTH_NAMES,
			run_chart,
			geocode_city_with_timezone,
		)


with col_right:
	from profile_manager_v2 import ensure_profile_session_defaults, render_profile_manager

	# Make sure the session keys exist before rendering any widgets in this panel
	ensure_profile_session_defaults(MONTH_NAMES)
	with st.expander("📂 Chart Profile Manager"):
		saved_profiles = render_profile_manager(
			MONTH_NAMES=MONTH_NAMES,
			current_user_id=current_user_id,
			run_chart=run_chart,
			_selected_house_system=_selected_house_system,
			save_user_profile_db=save_user_profile_db,
			load_user_profiles_db=load_user_profiles_db,
			delete_user_profile_db=delete_user_profile_db,
			community_save=community_save,
			community_list=community_list,
			community_get=community_get,
			community_delete=community_delete,
			is_admin=is_admin,
			# optional live geocode inputs; omit if you prefer all from session_state
			lat=st.session_state.get("current_lat"),
			lon=st.session_state.get("current_lon"),
			tz_name=st.session_state.get("current_tz_name"),
			hour_val=st.session_state.get("hour_val"),
			minute_val=st.session_state.get("minute_val"),
			city_name=st.session_state.get("profile_city", ""),
			chart_ready=st.session_state.get("chart_ready", False),
		)

	if df_cached is not None:
		# Call donate UI OUTSIDE the profile manager expander to avoid nesting
		donate_chart(
			MONTH_NAMES=MONTH_NAMES,
			current_user_id=current_user_id,
			is_admin=is_admin,
			community_save=community_save,
			community_list=community_list,
			community_get=community_get,
			community_delete=community_delete,
			run_chart=run_chart,
			chart_ready=st.session_state.get("chart_ready", False),
		)
	
# BEFORE you use patterns/shapes in the UI:
patterns = st.session_state.get("patterns", [])
shapes = st.session_state.get("shapes", [])
singleton_map = st.session_state.get("singleton_map", {})

# --- Bottom-of-page popovers ---
df_cached     = st.session_state.get("last_df")
aspect_cached = st.session_state.get("last_aspect_df")
sect_cached   = st.session_state.get("last_sect")
sect_err      = st.session_state.get("last_sect_error")

st.markdown(
	"""
	<style>
	.thick-divider {
		border-top: 5px solid #333; /* Adjust thickness and color as needed */
		margin-top: 20px; /* Adjust spacing above the line */
		margin-bottom: 20px; /* Adjust spacing below the line */
	}
	</style>
	<div class="thick-divider"></div>
	""",
	unsafe_allow_html=True
)

# Only show the bottom bar after a chart is calculated
if df_cached is not None:
	col_a, col_b, col_c = st.columns([1, 3, 1])
	# -------------------------
	# Wizard
	# -------------------------
	with col_a:
		st.caption("🧙‍♀️💭 What can I help you find? →")
	with col_b:
		render_guided_wizard()
	with col_c:
		st.caption("← Chart features by topic 📜🔍")
	
	st.markdown(
		"""
		<style>
		.thick-divider {
			border-top: 5px solid #333; /* Adjust thickness and color as needed */
			margin-top: 20px; /* Adjust spacing above the line */
			margin-bottom: 20px; /* Adjust spacing below the line */
		}
		</style>
		<div class="thick-divider"></div>
		""",
		unsafe_allow_html=True
	)

	# ---------- Toggles (moved to toggles_v2) ----------
	# prepare saved_profiles for the call
	saved_profiles = load_user_profiles_db(current_user_id)
	
	# Safety check: ensure patterns, shapes, singleton_map exist
	patterns = patterns or []
	shapes = shapes or []
	singleton_map = singleton_map or {}
	
	toggles, pattern_labels, saved_profiles, chart_mode, aspect_toggles = render_circuit_toggles(
		patterns=patterns,
		shapes=shapes,
		singleton_map=singleton_map,
		saved_profiles=saved_profiles,
		current_user_id=current_user_id,
		save_user_profile_db=save_user_profile_db,
		load_user_profiles_db=load_user_profiles_db,
	)

	# Store aspect toggles to session state so _refresh_chart_figure can access them
	st.session_state["aspect_toggles"] = aspect_toggles
	col_1, col_2 = st.columns([2, 1])
	with col_1:
		st.write("")  # just a spacer
	with col_2:
		# --- Transits Checkbox and Controls (Standard Chart mode only) ---
		if chart_mode == "Standard Chart":
			st.session_state.setdefault("transit_mode", False)
			transit_mode = st.checkbox("Transits", key="transit_mode")

			if transit_mode:
				st.markdown("**Transits Controls**")
				tcol1, tcol2 = st.columns([1, 1])
				with tcol1:
					if st.button("Previous", key="transit_prev"):
						st.session_state["transit_date_offset"] = st.session_state.get("transit_date_offset", 0) - 1
				with tcol2:
					if st.button("Next", key="transit_next"):
						st.session_state["transit_date_offset"] = st.session_state.get("transit_date_offset", 0) + 1

				with st.expander("Transit Date"):
					st.session_state.setdefault("transit_year", st.session_state.get("year", 2025))
					st.session_state.setdefault("transit_month_name", st.session_state.get("month_name", "December"))
					st.session_state.setdefault("transit_day", st.session_state.get("day", 2))
					st.session_state.setdefault("transit_hour_12", "12")
					st.session_state.setdefault("transit_minute_str", "00")
					st.session_state.setdefault("transit_ampm", "AM")

					t_year = st.number_input(
						"Year",
						min_value=1000,
						max_value=3000,
						step=1,
						key="transit_year",
					)
					import calendar
					t_month_name = st.selectbox(
						"Month",
						MONTH_NAMES,
						key="transit_month_name",
					)
					t_month = MONTH_NAMES.index(t_month_name) + 1
					t_days_in_month = calendar.monthrange(t_year, t_month)[1]
					t_day = st.selectbox(
						"Day",
						list(range(1, t_days_in_month + 1)),
						key="transit_day",
					)
					HOURS   = ["--"] + [f"{h:02d}" for h in range(1, 13)]
					MINUTES = ["--"] + [f"{m:02d}" for m in range(0, 60)]
					AMPMS   = ["--", "AM", "PM"]
					tcol1, tcol2, tcol3 = st.columns(3)
					with tcol1:
						st.selectbox("Transit Time", options=HOURS,   key="transit_hour_12")
					with tcol2:
						st.selectbox(" ",          options=MINUTES, key="transit_minute_str")
					with tcol3:
						st.selectbox(" ",          options=AMPMS,   key="transit_ampm")

	_refresh_chart_figure()


	fig = st.session_state.get("render_fig")
	if fig is not None:
		st.pyplot(fig, clear_figure=True, use_container_width=True)
	else:
		st.caption("Calculate a chart to render the wheel.")

	# --- MCP Interpretation Output Section ---
	st.markdown("<div id='mcp-interpretation'></div>", unsafe_allow_html=True)
	st.markdown("**Interpretation**", unsafe_allow_html=True)
	interp_mode = st.radio(
		"Interpretation Mode",
		["poetic", "technical"],
		horizontal=True,
		key="interp_mode_radio",
		index=0
	)
	# Prepare chart state for MCP
	# Filter objects and aspects to only those currently visible
	visible_objects = st.session_state.get('visible_objects', [])
	last_df = st.session_state.get('last_df')
	edges_major = st.session_state.get('edges_major', [])
	# Filter DataFrame rows to visible objects
	if last_df is not None and not last_df.empty and visible_objects:
		from profiles_v2 import ordered_object_rows
		filtered_df = ordered_object_rows(last_df, visible_objects=visible_objects, edges_major=edges_major)
	else:
		filtered_df = last_df
	# Filter aspects to only those between visible objects
	visible_set = set(visible_objects)
	filtered_edges_major = [e for e in edges_major if e[0] in visible_set and e[1] in visible_set]
	# Import all needed lookups from lookup_v2 and profiles_v2
	import lookup_v2
	import profiles_v2
	try:
		from Rosetta_v2.profiles_v2 import STAR_CATALOG, find_fixed_star_conjunctions
	except ImportError:
		STAR_CATALOG = None
		find_fixed_star_conjunctions = None

	chart_state = {
		'ordered_df': filtered_df,
		'edges_major': filtered_edges_major,
		'edges_minor': st.session_state.get('edges_minor', []),
		'mode': interp_mode,
		'raw_links': st.session_state.get('plot_data', {}),
		'lookup': {
			'GLYPHS': getattr(lookup_v2, 'GLYPHS', {}),
			'OBJECT_MEANINGS': getattr(lookup_v2, 'OBJECT_MEANINGS', {}),
			'SIGN_MEANINGS': getattr(lookup_v2, 'SIGN_MEANINGS', {}),
			'HOUSE_MEANINGS': getattr(lookup_v2, 'HOUSE_MEANINGS', {}),
			'INTERP_FLAGS': getattr(lookup_v2, 'INTERP_FLAGS', {}),
			'SABIAN_SYMBOLS': getattr(lookup_v2, 'SABIAN_SYMBOLS', {}),
			'ASPECT_INTERP': getattr(lookup_v2, 'ASPECT_INTERP', {}),
			'FIXED_STAR_CATALOG': STAR_CATALOG,
			'find_fixed_star_conjunctions': find_fixed_star_conjunctions,
		},
		'compass_rose_on': st.session_state.get('ui_compass_overlay', False),
	}
	interp = ChartInterpreter(chart_state)
	interp_output = interp.generate()
	st.markdown(f"<div style='background:#222;padding:1em;border-radius:8px;white-space:pre-wrap;color:#fff'>{interp_output}</div>", unsafe_allow_html=True)

	# --- Dispositor Graph (moved from popover) ---
	import matplotlib.pyplot as plt
	import networkx as nx
	from house_selector_v2 import render_house_system_selector
	
	# Add anchor for jump button
	st.markdown('<div id="ruler-hierarchies"></div>', unsafe_allow_html=True)
	
	header_col, toggle_col, house_col = st.columns([2, 2, 1])
	
	with header_col:
		st.subheader("Ruler Hierarchies")
	
	with house_col:
		render_house_system_selector()
	
	with toggle_col:
		# House system selector (always render, but only relevant for "By House")
		# Dispositor scope toggle
		st.session_state.setdefault("dispositor_scope", "By Sign")
		disp_scope = st.radio(
			"Scope",
			["By Sign", "By House"],
			horizontal=True,
			key="dispositor_scope",
			label_visibility="collapsed"
		)
	
	plot_data = st.session_state.get("plot_data")
	if plot_data is not None:
		# Determine which scope to use
		if disp_scope == "By Sign":
			scope_data = plot_data.get("by_sign")
		else:  # By House
			# Map lowercase session state keys to plot_data keys
			house_key_map = {
				"placidus": "Placidus",
				"equal": "Equal",
				"whole": "Whole Sign"
			}
			selected_house = st.session_state.get("house_system", "placidus")
			plot_data_key = house_key_map.get(selected_house, "Placidus")
			scope_data = plot_data.get(plot_data_key)

		if scope_data and scope_data.get("raw_links"):
			# Get header info from _current_chart_header_lines
			from drawing_v2 import _current_chart_header_lines
			name, date_line, time_line, city, extra_line = _current_chart_header_lines()
			header_info = {
				'name': name,
				'date_line': date_line,
				'time_line': time_line,
				'city': city,
				'extra_line': extra_line
			}
			disp_fig = plot_dispositor_graph(scope_data, header_info=header_info)
			if disp_fig is not None:
				# Create columns for legend and graph
				legend_col, graph_col = st.columns([1, 5])
				
			with legend_col:
				import os
				import base64
				png_dir = os.path.join(os.path.dirname(__file__), "pngs")
				
				# Load and encode images as base64
				def img_to_b64(filename):
					path = os.path.join(png_dir, filename)
					if os.path.exists(path):
						with open(path, "rb") as f:
							return base64.b64encode(f.read()).decode()
					return ""
				
				# Create legend with dark background
				st.markdown("""
					<div style="background-color: #262730; padding: 15px; border-radius: 8px;">
						<strong style="color: white;">Legend</strong>
					</div>
				""", unsafe_allow_html=True)
				
				legend_items = [
					("green.png", "Sovereign"),
					("orange.png", "Dual rulership"),
					("purple.png", "Loop"),
					("purpleorange.png", "Dual + Loop"),
					("blue.png", "Standard"),
				]
				
				# Wrap all legend items in the dark background
				legend_html = '<div style="background-color: #262730; padding: 15px; border-radius: 8px; margin-top: -15px;">'
				for img_file, label in legend_items:
					b64 = img_to_b64(img_file)
					if b64:
						legend_html += f'<div style="margin-bottom: 8px;"><img src="data:image/png;base64,{b64}" width="20" style="vertical-align:middle;margin-right:5px"/><span style="color: white;">{label}</span></div>'
				legend_html += '<div style="color: white; margin-top: 8px;">↻ Self-Ruling</div>'
				legend_html += '</div>'
				st.markdown(legend_html, unsafe_allow_html=True)
				
			with graph_col:
				st.pyplot(disp_fig, use_container_width=True)
		else:
			st.info("No dispositor graph to display.")
	else:
		st.info("Calculate a chart first.")

	st.subheader("🤓 Nerdy Chart Specs 📋")
	unknown_time_chart = bool(
		st.session_state.get("chart_unknown_time")
		or st.session_state.get("profile_unknown_time")
	)

	if sect_cached:
		st.info(f"Sect: **{sect_cached}**")
	elif unknown_time_chart:
		# Your preferred wording and punctuation
		st.warning("Sect unavailable; time unknown")
	elif sect_err:
		# Other errors (if any) keep their message
		st.warning(f"Sect unavailable: {sect_err}")
	else:
		st.caption("No sect computed yet.")

	with st.popover("Objects", use_container_width=True):
		st.subheader("Calculated Chart")
		st.dataframe(df_cached, use_container_width=True)

	with st.popover("Conjunctions", use_container_width=True):
		st.subheader("Conjunction Clusters")
		st.dataframe(st.session_state.get("conj_clusters_rows") or [], use_container_width=True)

	with st.popover("Aspects Graph", use_container_width=True):
		if aspect_cached is not None:
			st.subheader("Aspect Graph")
			st.dataframe(aspect_cached, use_container_width=True)
		else:
			st.caption("No aspect table available yet.")

	with st.popover("Aspects List", use_container_width=True):
		st.subheader("Aspect Lists")
		edges_major = st.session_state.get("edges_major") or []
		edges_minor = st.session_state.get("edges_minor") or []
		df_cached = st.session_state.get("last_df")
		# Use the new clustered aspect edge builder
		from calc_v2 import build_clustered_aspect_edges
		if df_cached is not None:
			clustered_edges = build_clustered_aspect_edges(df_cached, edges_major)
			# For debugging, show both the cluster names and the original A/B
			rows = []
			for a, b, meta in clustered_edges:
				row = {"Kind": "Major", "Cluster A": a, "Cluster B": b, **meta}
				rows.append(row)
			for a, b, meta in edges_minor:
				row = {"Kind": "Minor", "A": a, "B": b, **meta}
				rows.append(row)
			st.dataframe(rows, use_container_width=True)
		else:
			st.caption("No aspect data available.")
		
# --- Left sidebar: Planet Profiles ---
with st.sidebar:
	st.subheader("🪐 Planet Profiles in View")

	# 1) Inject tight CSS once
	st.markdown("""
		<style>
		/* Compact, single-spaced profile blocks */
		.pf-root, .pf-root * { line-height: 1.12; }
		.pf-root p { margin: 0; line-height: 1.12; }  /* safety if any <p> slips in */
		.pf-root div { margin: 0; padding: 0; }

		.pf-root .pf-title {
			font-weight: 700;
			font-size: 1.05rem;
			line-height: 1.1;
			margin: 0 0 2px 0;
		}
		.pf-root .pf-divider {
			border: 0;
			border-top: 1px solid rgba(128,128,128,0.35);
			margin: 6px 0 10px 0;   /* space between profiles */
		}
		</style>
	""", unsafe_allow_html=True)

	# 2) Render all profiles inside one wrapper so the CSS applies uniformly
	if df_cached is not None:
		visible_objects = st.session_state.get("visible_objects")
		edges_major = st.session_state.get("edges_major") or []
		unknown_time_chart = bool(
			st.session_state.get("chart_unknown_time")
			or st.session_state.get("profile_unknown_time")
		)
		ordered_rows = ordered_object_rows(
			df_cached,
			visible_objects=visible_objects,
			edges_major=edges_major,
		)
		print("[DEBUG] Sidebar visible_objects:", visible_objects)
		print("[DEBUG] Sidebar ordered_rows objects:", list(ordered_rows["Object"]) if not ordered_rows.empty else [])
		if not ordered_rows.empty:
			blocks = [
				format_object_profile_html(
					r,
					house_label=_selected_house_system,
					include_house_data=not unknown_time_chart,
				)
				for _, r in ordered_rows.iterrows()
			]
			st.markdown(
				"<div class='pf-root'>" + "\n".join(blocks) + "</div>",
				unsafe_allow_html=True,
			)
		else:
			st.caption("No objects currently visible with the selected toggles.")
	else:
		st.caption("Calculate a chart to see profiles.")
