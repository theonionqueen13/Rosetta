from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder
import os, importlib.util, streamlit as st
st.set_page_config(layout="wide")

# Load calc_v2.py from this folder explicitly
CALC_PATH = os.path.join(os.path.dirname(__file__), "calc_v2.py")
spec = importlib.util.spec_from_file_location("calc_v2", CALC_PATH)
calc_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calc_mod)

calculate_chart = calc_mod.calculate_chart  # <-- use this below
chart_sect_from_df = calc_mod.chart_sect_from_df
build_aspect_edges = calc_mod.build_aspect_edges
annotate_reception = calc_mod.annotate_reception

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

col_left, col_right = st.columns([2, 2])
# -------------------------
# Left column: Birth Data
# -------------------------
with col_left:
	with st.expander("Enter Birth Data"):
		col1, col2 = st.columns([3, 2])

		# --- Left side: Date & Time ---
		with col1:
			# Year widget
			year = st.number_input(
				"Year",
				min_value=1000,
				max_value=3000,
				step=1,
				key="year"
			)

			# Month widget
			import calendar
			month_name = st.selectbox(
				"Month",
				MONTH_NAMES,
				key="month_name"
			)
			month = MONTH_NAMES.index(month_name) + 1
			days_in_month = calendar.monthrange(year, month)[1]

		# Time widgets
		time_cols = st.columns(3)
		with time_cols[0]:
			hour_12 = st.selectbox(
				"Birth Time",
				list(range(1, 13)),
				key="hour_12"
			)
		with time_cols[1]:
			minute_str = st.selectbox(
				" ",
				[f"{m:02d}" for m in range(60)],
				key="minute_str"
			)
		with time_cols[2]:
			ampm = st.selectbox(
				" ",
				["AM", "PM"],
				key="ampm"
			)

		# Convert to 24h (helpers only, not widget keys)
		if ampm == "PM" and hour_12 != 12:
			hour_val = hour_12 + 12
		elif ampm == "AM" and hour_12 == 12:
			hour_val = 0
		else:
			hour_val = hour_12
		minute_val = int(minute_str)

		st.session_state["hour_val"] = hour_val
		st.session_state["minute_val"] = minute_val

		# --- Right side: Location ---
		with col2:
			opencage_key = st.secrets["OPENCAGE_API_KEY"]
			geolocator = OpenCage(api_key=opencage_key)

			city_name = st.text_input(
				"City of Birth",
				value=st.session_state.get("profile_city", ""),
				key="city"   # you can just reuse profile_city as the widget key
			)

			lat, lon, tz_name = None, None, None
			if city_name:
				try:
					location = geolocator.geocode(city_name, timeout=20)
					if location:
						lat, lon = location.latitude, location.longitude
						tf = TimezoneFinder()
						tz_name = tf.timezone_at(lng=lon, lat=lat)
						st.session_state["last_location"] = location.address
						st.session_state["last_timezone"] = tz_name
						# Store location data in session state
						st.session_state["current_lat"] = lat
						st.session_state["current_lon"] = lon
						st.session_state["current_tz_name"] = tz_name
					else:
						st.session_state["last_location"] = None
						st.session_state["last_timezone"] = "City not found. Try a more specific query."
				except Exception as e:
					st.session_state["last_location"] = None
					st.session_state["last_timezone"] = f"Lookup error: {e}"
			# Day widget
			day = st.selectbox(
				"Day",
				list(range(1, days_in_month + 1)),
				key="day"
			)

def run_chart(lat, lon, tz_name):
	"""
	Pull values from session state, call calculate_chart (which returns a single DataFrame),
	and display the DataFrame.
	"""
	year   = int(st.session_state["profile_year"])
	month  = MONTH_NAMES.index(st.session_state["profile_month_name"]) + 1
	day    = int(st.session_state["profile_day"])
	hour   = int(st.session_state["profile_hour"])   # already 24h
	minute = int(st.session_state["profile_minute"])

	# tz_offset isn't used when tz_name is provided; pass 0
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
		include_aspects=True,   # <-- NEW FLAG
	)

	# Handle either a single DF or the tuple of (objects_df, aspects_df)
	if isinstance(result, tuple):
		df, aspect_df = result
	else:
		df = result
		aspect_df = None

	# Build edges ONCE (no recalculation inside annotate_reception)
	edges_major, edges_minor = build_aspect_edges(df)

	# Annotate sign-only reception using supplied edges_major
	df = annotate_reception(df, edges_major)

	# Keep it around if you want to reference later
	st.session_state["last_df"] = df

	# === Sect info stays visible ===
	try:
		sect = chart_sect_from_df(df)
		st.info(f"Sect: **{sect}**")
	except Exception as e:
		st.warning(f"Sect unavailable: {e}")

	# === Popover triggers ===
	with st.popover("🪐", use_container_width=True):
		st.subheader("Calculated Chart")
		st.dataframe(df, use_container_width=True)

	with st.popover("📐", use_container_width=True):
		if aspect_df is not None:
			st.subheader("Aspect Graph")
			st.dataframe(aspect_df, use_container_width=True)

	# (optional) keep edges around for later use, without re-building
	st.session_state["edges_major"] = edges_major
	st.session_state["edges_minor"] = edges_minor

with col_right:
	if st.button("Calculate Chart"):
		st.session_state["profile_year"] = st.session_state["year"]
		st.session_state["profile_month_name"] = st.session_state["month_name"]
		st.session_state["profile_day"] = st.session_state["day"]
		st.session_state["profile_hour"] = hour_val
		st.session_state["profile_minute"] = minute_val
		st.session_state["profile_city"] = city_name

		if lat is None or lon is None or tz_name is None:
			st.error("Please enter a valid city and make sure lookup succeeds.")
		else:
			run_chart(lat, lon, tz_name)
			# Store location data in session state
			st.session_state["current_lat"] = lat
			st.session_state["current_lon"] = lon
			st.session_state["current_tz_name"] = tz_name

		# Location info BELOW buttons
		location_info = st.container()
		if st.session_state.get("last_location"):
			location_info.success(f"Found: {st.session_state['last_location']}")
			if st.session_state.get("last_timezone"):
				location_info.write(f"Timezone: {st.session_state['last_timezone']}")
		elif st.session_state.get("last_timezone"):
			location_info.error(st.session_state["last_timezone"])

		# user calculated a new chart manually
		st.session_state["active_profile_tab"] = "Add Profile"
