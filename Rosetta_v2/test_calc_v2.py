# ---- Test stubs to satisfy UI/backend imports ----
# Keep these ABOVE imports of your app modules.
from typing import Dict, Any, List, Optional, Tuple
from house_selector_v2 import _selected_house_system
from donate_v2 import donate_chart
import datetime as dt
from datetime import datetime
from zoneinfo import ZoneInfo
from now_v2 import render_now_widget
import pytz
current_user_id = "test-user"

# In-memory stores used by the stubs
_TEST_PROFILES: Dict[str, Dict[str, Any]] = {}
_TEST_COMMUNITY: Dict[str, Dict[str, Any]] = {}

def save_user_profile_db(user_id: str, name: str, payload: Dict[str, Any]) -> None:
	users = _TEST_PROFILES.setdefault(user_id, {})
	users[name] = payload.copy()

def load_user_profiles_db(user_id: str) -> Dict[str, Any]:
	return _TEST_PROFILES.get(user_id, {}).copy()

def delete_user_profile_db(user_id: str, name: str) -> None:
	if user_id in _TEST_PROFILES and name in _TEST_PROFILES[user_id]:
		del _TEST_PROFILES[user_id][name]

def community_save(profile_name: str, payload: Dict[str, Any], submitted_by: Optional[str] = None) -> str:
	# Return a fake ID like a DB would
	new_id = f"comm_{len(_TEST_COMMUNITY)+1}"
	_TEST_COMMUNITY[new_id] = {
		"id": new_id,
		"profile_name": profile_name,
		"payload": payload.copy(),
		"submitted_by": submitted_by or current_user_id,
	}
	return new_id

def community_list(limit: int = 100) -> List[Dict[str, Any]]:
	return list(_TEST_COMMUNITY.values())[:limit]

# Some parts of your code use community_get; others say community_load.
# Provide both so either name works.
def community_get(comm_id: str) -> Optional[Dict[str, Any]]:
	return _TEST_COMMUNITY.get(comm_id)

def community_delete(comm_id: str) -> None:
	_TEST_COMMUNITY.pop(comm_id, None)

# Back-compat alias if something imports 'community_load'
community_load = community_get

def is_admin(user_id: str) -> bool:
	# In tests, just say yes or no—doesn’t matter unless you assert on it.
	return True
# ---- End stubs ----

from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder
from profiles_v2 import format_object_profile_html, ordered_object_rows
import os, importlib.util, streamlit as st
st.set_page_config(layout="wide")
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_dataframe, generate_combo_groups, edges_from_major_list
from drawing_v2 import render_chart, render_chart_with_shapes
from wizard_v2 import render_guided_wizard
from toggles_v2 import render_circuit_toggles
from profile_manager_v2 import render_profile_manager, ensure_profile_session_defaults


def _geocode_city_with_timezone(city_query: str) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
	"""Return (lat, lon, tz_name, formatted_address) for the provided city query."""
	lat = lon = tz_name = None
	formatted_address = None

	if not city_query:
		return lat, lon, tz_name, formatted_address

	try:
		opencage_key = st.secrets["OPENCAGE_API_KEY"]
	except Exception as exc:
		raise RuntimeError("OpenCage API key missing from Streamlit secrets") from exc

	geolocator = OpenCage(api_key=opencage_key)
	location = geolocator.geocode(city_query, timeout=20)
	if location:
		lat, lon = location.latitude, location.longitude
		formatted_address = location.address
		tz_name = TimezoneFinder().timezone_at(lng=lon, lat=lat)

	return lat, lon, tz_name, formatted_address

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

# Load calc_v2.py from this folder explicitly
CALC_PATH = os.path.join(os.path.dirname(__file__), "calc_v2.py")
spec = importlib.util.spec_from_file_location("calc_v2", CALC_PATH)
calc_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc_mod)

calculate_chart = calc_mod.calculate_chart  # <-- use this below
chart_sect_from_df = calc_mod.chart_sect_from_df
build_aspect_edges = calc_mod.build_aspect_edges
annotate_reception = calc_mod.annotate_reception
build_dispositor_tables = calc_mod.build_dispositor_tables
build_conjunction_clusters = calc_mod.build_conjunction_clusters

MONTH_NAMES = [
	"January","February","March","April","May","June",
	"July","August","September","October","November","December"
]

# --- Default birth data (only set once per app session) ---
if "defaults_loaded" not in st.session_state:
	st.session_state["year"] = 1990
	st.session_state["month_name"] = "July"
	st.session_state["day"] = 29
	st.session_state["hour_12"] = 1
	st.session_state["minute_str"] = "39"
	st.session_state["ampm"] = "AM"
	st.session_state["city"] = "Newton, KS"
	st.session_state["defaults_loaded"] = True

# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)

def _refresh_chart_figure():
	"""Rebuild the chart figure using the current session-state toggles."""
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
			dark_mode=dark_mode,
			shapes=shapes,
			shape_toggles_by_parent=shape_toggles_by_parent,
			singleton_toggles=singleton_toggles,
			major_edges_all=major_edges_all,
		)
	except Exception:
		rr = render_chart(
			df,
			visible_toggle_state=None,
			edges_major=edges_major,
			edges_minor=edges_minor,
			house_system=_selected_house_system(),
			dark_mode=dark_mode,
			label_style=label_style,
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
	Build chart DF, aspects, dispositors, clusters, circuits/shapes—then render
	via drawing_v2.render_chart_with_shapes (fallback to render_chart).
	"""
	# --- Inputs from session ---
	year   = int(st.session_state["profile_year"])
	month  = MONTH_NAMES.index(st.session_state["profile_month_name"]) + 1
	day    = int(st.session_state["profile_day"])
	hour   = int(st.session_state["profile_hour"])   # already 24h
	minute = int(st.session_state["profile_minute"])

	# --- Calculate chart (no tz_offset when tz_name is provided) ---
	result = calculate_chart(
		year=year,
		month=month,
		day=day,
		hour=hour,
		minute=minute,
		tz_offset=0,
		lat=lat,
		lon=lon,
		input_is_ut=False,
		tz_name=tz_name,
		include_aspects=True,
	)

	# Unpack DF(s)
	if isinstance(result, tuple):
		df, aspect_df = result
	else:
		df, aspect_df = result, None

	# --- Aspects (build once) ---
	edges_major, edges_minor = build_aspect_edges(df)

	# --- Reception (uses supplied edges; no recalculation) ---
	df = annotate_reception(df, edges_major)

	# --- Sect (store or error) ---
	try:
		st.session_state["last_sect"] = chart_sect_from_df(df)
		st.session_state["last_sect_error"] = None
	except Exception as e:
		st.session_state["last_sect"] = None
		st.session_state["last_sect_error"] = str(e)

	# --- Dispositors (summary + chains) ---
	chains_rows, summary_rows = build_dispositor_tables(df)
	st.session_state["dispositor_summary_rows"] = summary_rows
	st.session_state["dispositor_chains_rows"] = chains_rows

	# --- Conjunction clusters (from existing edges) ---
	clusters_rows = build_conjunction_clusters(df, edges_major)
	st.session_state["conj_clusters_rows"] = clusters_rows

	# --- Circuits / patterns + shapes (STRICTLY from precomputed edges) ---
	# prepare_pattern_inputs will reuse edges_major if passed
	pos, patterns_sets, major_edges_all = prepare_pattern_inputs(df, edges_major)
	patterns = [sorted(list(s)) for s in patterns_sets]  # UI-friendly lists
	shapes   = detect_shapes(pos, patterns_sets, major_edges_all)

	filaments, singleton_map = detect_minor_links_from_dataframe(df, edges_major)
	combos = generate_combo_groups(filaments)

	# --- Cache everything for UI/popovers ---
	st.session_state["last_df"] = df
	st.session_state["last_aspect_df"] = aspect_df
	st.session_state["edges_major"] = edges_major
	st.session_state["edges_minor"] = edges_minor
	st.session_state["patterns"] = patterns
	st.session_state["shapes"] = shapes
	st.session_state["filaments"] = filaments
	st.session_state["singleton_map"] = singleton_map
	st.session_state["combos"] = combos
	st.session_state["chart_positions"] = pos
	st.session_state["major_edges_all"] = major_edges_all

	# Build the initial wheel immediately so the chart column updates on this run.
	_refresh_chart_figure()

	# Also cache location so render_chart_with_shapes can auto-heal house cusps
	st.session_state["calc_lat"] = lat
	st.session_state["calc_lon"] = lon
	st.session_state["calc_tz"]  = tz_name

	# ---- UI state defaults for the renderer ----
	# Pattern toggles (checkboxes are created later; default False so planets draw but edges/shapes obey UI)
	toggles = []
	for i in range(len(patterns)):
		st.session_state.setdefault(f"toggle_pattern_{i}", False)
		toggles.append(st.session_state[f"toggle_pattern_{i}"])

	# Sub-shape toggles container (your UI fills this later)
	shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})

	# Singleton toggles map
	singleton_toggles = {}
	if singleton_map:
		for planet in singleton_map.keys():
			st.session_state.setdefault(f"singleton_{planet}", False)
			singleton_toggles[planet] = st.session_state[f"singleton_{planet}"]

	# Pattern labels (respect editable names if present)
	pattern_labels = []
	for i in range(len(patterns)):
		st.session_state.setdefault(f"circuit_name_{i}", f"Circuit {i+1}")
		pattern_labels.append(st.session_state[f"circuit_name_{i}"])

	# Combo toggles placeholder (your UI can wire these later)
	combo_toggles = st.session_state.get("combo_toggles", {})

	# UI knobs
	house_system = st.session_state.get("house_system", "placidus")
	label_style  = st.session_state.get("label_style", "glyph")  # "glyph" | "text"
	dark_mode    = st.session_state.get("dark_mode", False)

col_left, col_mid, col_right = st.columns([3, 2, 3])
# -------------------------
# Left column: Birth Data (FORM)
# -------------------------
with col_left:
	with st.expander("📆 Enter Birth Data"):
		with st.form("birth_form", clear_on_submit=False):
			col1, col2 = st.columns([3, 2])

			# --- Left side: Date & Day ---
			with col1:
				year = st.number_input(
					"Year",
					min_value=1000,
					max_value=3000,
					step=1,
					key="year"
				)

				import calendar
				month_name = st.selectbox(
					"Month",
					MONTH_NAMES,
					key="month_name"
				)
				month = MONTH_NAMES.index(month_name) + 1
				days_in_month = calendar.monthrange(year, month)[1]

				day = st.selectbox(
					"Day",
					list(range(1, days_in_month + 1)),
					key="day"
				)

			# --- Right side: Location ---
			with col2:
				city_name = st.text_input(
					"City of Birth",
					value=st.session_state.get("profile_city", ""),
					key="city"
				)

			# --- Time widgets (own row of columns; NOT nested inside col1) ---
			tcol1, tcol2, tcol3 = st.columns(3)
			with tcol1:
				hour_12 = st.selectbox(
					"Birth Time",
					list(range(1, 13)),
					key="hour_12"
				)
			with tcol2:
				minute_str = st.selectbox(
					" ",
					[f"{m:02d}" for m in range(60)],
					key="minute_str"
				)
			with tcol3:
				ampm = st.selectbox(
					" ",
					["AM", "PM"],
					key="ampm"
				)

			# Submit button: only on click do we geocode + calculate
			submitted = st.form_submit_button("Calculate Chart")

			if submitted:
				# Convert to 24h
				if ampm == "PM" and hour_12 != 12:
					hour_val = hour_12 + 12
				elif ampm == "AM" and hour_12 == 12:
					hour_val = 0
				else:
					hour_val = hour_12
				minute_val = int(minute_str)
				st.session_state["hour_val"] = hour_val
				st.session_state["minute_val"] = minute_val

				# Define the query from the text input you already captured
				city_query = (city_name or "").strip()
				# (Optional) keep a copy if other parts of the app look for it
				st.session_state["city_query"] = city_query

				try:
					lat, lon, tz_name, formatted_address = _geocode_city_with_timezone(city_query)

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
						st.session_state["last_location"] = formatted_address or city_name
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
				st.session_state["profile_city"] = city_name

				# Calculate chart only on submit
				if lat is None or lon is None or tz_name is None:
					st.error("Please enter a valid city and make sure lookup succeeds.")
				else:
					run_chart(lat, lon, tz_name)

					chart_dt_local = datetime(
						year, month, day, hour_val, minute_val,
						tzinfo=ZoneInfo(tz_name)
					)
					chart_dt_utc = chart_dt_local.astimezone(ZoneInfo("UTC"))
					st.session_state["chart_dt_utc"] = chart_dt_utc

				# Location info BELOW, optional
				if st.session_state.get("last_location"):
					st.success(f"Found: {st.session_state['last_location']}")
					if st.session_state.get("last_timezone"):
						st.write(f"Timezone: {st.session_state['last_timezone']}")
				elif st.session_state.get("last_timezone"):
					st.error(st.session_state["last_timezone"])

df_cached     = st.session_state.get("last_df")

# --- Quick city UI state defaults & safe-clear ---
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
            _geocode_city_with_timezone,
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
	toggles, pattern_labels, saved_profiles = render_circuit_toggles(
		patterns=patterns,
		shapes=shapes,
		singleton_map=singleton_map,
		saved_profiles=saved_profiles,
		current_user_id=current_user_id,
		save_user_profile_db=save_user_profile_db,
		load_user_profiles_db=load_user_profiles_db,
	)

	_refresh_chart_figure()

	fig = st.session_state.get("render_fig")
	if fig is not None:
		st.pyplot(fig, clear_figure=False)
	else:
		st.caption("Calculate a chart to render the wheel.")

	st.subheader("🤓 Nerdy Chart Specs for Astrologers 📋")
	if sect_cached:
		st.info(f"Sect: **{sect_cached}**")
	elif sect_err:
		st.warning(f"Sect unavailable: {sect_err}")
	else:
		st.caption("No sect computed yet.")

	with st.popover("Objects", use_container_width=True):
		st.subheader("Calculated Chart")
		st.dataframe(df_cached, use_container_width=True)
		
	with st.popover("Dispositors", use_container_width=True):
		st.subheader("Dispositor Hierarchies")
		st.dataframe(st.session_state.get("dispositor_summary_rows") or [], use_container_width=True)
		
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
		rows = ([{"Kind":"Major","A":a,"B":b, **meta} for a,b,meta in edges_major] +
				[{"Kind":"Minor","A":a,"B":b, **meta} for a,b,meta in edges_minor])
		st.dataframe(rows, use_container_width=True)

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
		ordered_rows = ordered_object_rows(
			df_cached,
			visible_objects=visible_objects,
			edges_major=edges_major,
		)
		if not ordered_rows.empty:
			blocks = [
				format_object_profile_html(r, house_label=_selected_house_system)
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
