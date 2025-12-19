import os, sys
import swisseph as swe
EPHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "ephe"))
EPHE_PATH = EPHE_PATH.replace("\\", "/")
os.environ["SE_EPHE_PATH"] = EPHE_PATH
swe.set_ephe_path(EPHE_PATH)
from src.ui_utils import apply_custom_css, set_background_for_theme
from src.test_data import apply_test_chart_to_session, MONTH_NAMES
from src.geocoding import geocode_city_with_timezone
from src.chart_core import run_chart, _refresh_chart_figure
from src.state_manager import swap_primary_and_secondary_charts
from src.dispositor_graph import render_dispositor_section
from src.data_stubs import (
	current_user_id, save_user_profile_db, load_user_profiles_db, 
	delete_user_profile_db, community_save, community_list, 
	community_get, community_load, community_delete, is_admin
)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)
from house_selector_v2 import _selected_house_system
from donate_v2 import donate_chart
from now_v2 import render_now_widget
from event_lookup_v2 import update_events_html_state
from datetime import datetime
from profiles_v2 import format_object_profile_html, ordered_object_rows
import os, streamlit as st
import matplotlib.pyplot as plt
from interp import ChartInterpreter
st.set_page_config(layout="wide")
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_dataframe, generate_combo_groups, edges_from_major_list
from wizard_v2 import render_guided_wizard
from toggles_v2 import render_circuit_toggles
from drawing_v2 import RenderResult, render_chart, render_chart_with_shapes
from profile_manager_v2 import render_profile_manager, ensure_profile_session_defaults
from lookup_v2 import SIGNS, PLANETARY_RULERS, PLANETS_PLUS, ASPECTS, MAJOR_OBJECTS, TOGGLE_ASPECTS
from calc_v2 import (
	calculate_chart, chart_sect_from_df, build_aspect_edges, 
	annotate_reception, build_dispositor_tables, 
	build_conjunction_clusters
)

result = st.session_state.get("render_result")
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

import os
from pathlib import Path

# Get the directory where THIS script is running
BASE_DIR = Path(__file__).parent.absolute()

# Construct the path to the images
LIGHT_BG = BASE_DIR / "pngs" / "nebula2.jpg"
if not LIGHT_BG.exists():
    print(f"DEBUG: I'm looking for the background here: {LIGHT_BG}")

DARK_BG = BASE_DIR / "pngs" / "galaxies.jpg"
if not DARK_BG.exists():
    print(f"DEBUG: I'm looking for the background here: {DARK_BG}")

LIGHT_OVERLAY = 0.20
DARK_OVERLAY  = 0.45

resolved_dark_mode = set_background_for_theme(
	light_image_path=LIGHT_BG,
	dark_image_path=DARK_BG,
	light_overlay=LIGHT_OVERLAY,
	dark_overlay=DARK_OVERLAY,
	dark_mode=st.session_state.get("dark_mode", False),
)

st.session_state["dark_mode"] = resolved_dark_mode

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
	if run_chart():
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
			if run_chart(suffix="_2"):
				st.success(f"Chart 2 loaded: {st.session_state.get('city_2')}")
			else:
				st.error(f"Failed to calculate Chart 2. Check date/time/location inputs.")
		else:
			st.error(f"Error: Could not find test chart data for {test_chart_2}")

	elif test_chart_2 == "Custom":
		st.session_state["last_test_chart_2"] = "Custom"

# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)

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
			
			# ... (Birth form inputs above this line) ...

			#             # Persist normalized values if you need them elsewhere - NOT NEEDED, done inside calc_chart_from_session!
			#             st.session_state["profile_birth_hour_24"] = birth_hour_24
			#             st.session_state["profile_birth_minute"]  = birth_minute

			submitted = st.form_submit_button("Calculate Chart")

			if submitted:
				# Trigger the calculation for Chart 1 (no suffix).
				# This function now handles everything: Geocoding, Time Parsing, Core Calc, Post-Processing, and State Saving.
				success = run_chart(suffix="")

				if success:
					st.success(f"Chart successfully calculated for {st.session_state.get('city')}.")

					# Use st.rerun() to immediately display the chart if needed
					st.rerun() # Using rerun to see the result immediately
				else:
					# This message appears if geocoding failed or date/time parsing failed
					st.error(f"Calculation failed! Please ensure all date/time fields are valid and the city lookup succeeds.")


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

	rr = _refresh_chart_figure()
	if rr.fig is not None:
		st.pyplot(rr.fig, clear_figure=True)
		plt.close(rr.fig)

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
	from profiles_v2 import STAR_CATALOG, find_fixed_star_conjunctions

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
	render_dispositor_section(st, df_cached)

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
