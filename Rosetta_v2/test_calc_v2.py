from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder
from profiles_v2 import format_object_profile_html
import os, importlib.util, streamlit as st
st.set_page_config(layout="wide")

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

	# Compute sect and stash it for bottom-of-page rendering
	try:
		st.session_state["last_sect"] = chart_sect_from_df(df)
		st.session_state["last_sect_error"] = None
	except Exception as e:
		st.session_state["last_sect"] = None
		st.session_state["last_sect_error"] = str(e)

	# (optional) keep edges around for later use, without re-building
	st.session_state["edges_major"] = edges_major
	st.session_state["edges_minor"] = edges_minor

	# Save dataframes for bottom-of-page popovers
	st.session_state["last_df"] = df
	st.session_state["last_aspect_df"] = aspect_df
	chains_rows, summary_rows = build_dispositor_tables(df)
	st.session_state["dispositor_summary_rows"] = summary_rows
	# Build once from existing edges (no aspect recalculation)
	clusters_rows = build_conjunction_clusters(df, edges_major)
	st.session_state["conj_clusters_rows"] = clusters_rows


col_left, col_right = st.columns([2, 2])
# -------------------------
# Left column: Birth Data (FORM)
# -------------------------
with col_left:
	with st.expander("Enter Birth Data"):
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

				# Geocode only now (on submit)
				opencage_key = st.secrets["OPENCAGE_API_KEY"]
				geolocator = OpenCage(api_key=opencage_key)
				lat = lon = tz_name = None
				try:
					if city_name:
						location = geolocator.geocode(city_name, timeout=20)
						if location:
							lat, lon = location.latitude, location.longitude
							tf = TimezoneFinder()
							tz_name = tf.timezone_at(lng=lon, lat=lat)
							st.session_state["last_location"] = location.address
							st.session_state["last_timezone"] = tz_name
							st.session_state["current_lat"] = lat
							st.session_state["current_lon"] = lon
							st.session_state["current_tz_name"] = tz_name
						else:
							st.session_state["last_location"] = None
							st.session_state["last_timezone"] = "City not found. Try a more specific query."
				except Exception as e:
					st.session_state["last_location"] = None
					st.session_state["last_timezone"] = f"Lookup error: {e}"

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

				# Location info BELOW, optional
				if st.session_state.get("last_location"):
					st.success(f"Found: {st.session_state['last_location']}")
					if st.session_state.get("last_timezone"):
						st.write(f"Timezone: {st.session_state['last_timezone']}")
				elif st.session_state.get("last_timezone"):
					st.error(st.session_state["last_timezone"])

# --- Bottom-of-page popovers ---
df_cached     = st.session_state.get("last_df")
aspect_cached = st.session_state.get("last_aspect_df")
sect_cached   = st.session_state.get("last_sect")
sect_err      = st.session_state.get("last_sect_error")

# Only show the bottom bar after a chart is calculated
if df_cached is not None:

	if sect_cached:
		st.info(f"Sect: **{sect_cached}**")
	elif sect_err:
		st.warning(f"Sect unavailable: {sect_err}")
	else:
		st.caption("No sect computed yet.")

	with st.popover("Objects", use_container_width=True):
		st.subheader("Calculated Chart")
		st.dataframe(df_cached, use_container_width=True)

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

	with st.popover("Dispositors", use_container_width=True):
		st.subheader("Dispositor Hierarchies")
		st.dataframe(st.session_state.get("dispositor_summary_rows") or [], use_container_width=True)

	with st.popover("Conjunctions", use_container_width=True):
		st.subheader("Conjunction Clusters")
		st.dataframe(st.session_state.get("conj_clusters_rows") or [], use_container_width=True)

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
        objs_only = df_cached[~df_cached["Object"].str.contains("cusp", case=False, na=False)]
        blocks = [format_object_profile_html(r, house_label="Placidus") for _, r in objs_only.iterrows()]
        st.markdown("<div class='pf-root'>" + "\n".join(blocks) + "</div>", unsafe_allow_html=True)
    else:
        st.caption("Calculate a chart to see profiles.")
