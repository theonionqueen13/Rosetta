from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder
from profiles_v2 import format_object_profile_html
import os, importlib.util, streamlit as st
st.set_page_config(layout="wide")
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_dataframe, generate_combo_groups, edges_from_major_list
from drawing_v2 import render_chart, render_chart_with_shapes

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
            combo_toggles=combo_toggles,
            label_style=label_style,
            singleton_map=singleton_map or {},
            df=df,
            house_system=house_system,
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
            house_system=house_system,
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

# BEFORE you use patterns/shapes in the UI:
patterns = st.session_state.get("patterns", [])
shapes = st.session_state.get("shapes", [])
singleton_map = st.session_state.get("singleton_map", {})

# --- Bottom-of-page popovers ---
df_cached     = st.session_state.get("last_df")
aspect_cached = st.session_state.get("last_aspect_df")
sect_cached   = st.session_state.get("last_sect")
sect_err      = st.session_state.get("last_sect_error")

# Only show the bottom bar after a chart is calculated
if df_cached is not None:
	# ---------- Toggles ----------
	st.subheader("Circuits")

	# ---------- PRE-INIT (so keys exist before any widgets render) ----------
	# patterns & sub-shapes
	for i in range(len(patterns)):
		st.session_state.setdefault(f"toggle_pattern_{i}", False)
		for sh in [sh for sh in shapes if sh["parent"] == i]:
			st.session_state.setdefault(f"shape_{i}_{sh['id']}", False)

	# singleton planets (guard if not present)
	if singleton_map:
		for planet in singleton_map.keys():
			st.session_state.setdefault(f"singleton_{planet}", False)

	# ---------- BULK ACTION HANDLERS (must run BEFORE widgets) ----------
	b1, b2 = st.columns([1, 1])
	with b1:
		if st.button("Show All", key="btn_show_all_main"):
			# flip ON only the circuits (not sub-shapes, not singletons)
			for i in range(len(patterns)):
				st.session_state[f"toggle_pattern_{i}"] = True
			st.rerun()

	with b2:
		if st.button("Hide All", key="btn_hide_all_main"):
			# flip everything OFF
			for i in range(len(patterns)):
				st.session_state[f"toggle_pattern_{i}"] = False
				for sh in [sh for sh in shapes if sh["parent"] == i]:
					st.session_state[f"shape_{i}_{sh['id']}"] = False
			if singleton_map:
				for planet in singleton_map.keys():
					st.session_state[f"singleton_{planet}"] = False
			st.rerun()

	# --- Compass Rose (independent overlay, ON by default) ---
	if "toggle_compass_rose" not in st.session_state:
		st.session_state["toggle_compass_rose"] = True
	st.checkbox("Compass Rose", key="toggle_compass_rose")

	# Pattern checkboxes + expanders
	toggles, pattern_labels = [], []
	half = (len(patterns) + 1) // 2
	left_patterns, right_patterns = st.columns(2)

	for i, component in enumerate(patterns):
		target_col = left_patterns if i < half else right_patterns
		checkbox_key = f"toggle_pattern_{i}"

		# circuit name session key
		circuit_name_key = f"circuit_name_{i}"
		default_label = f"Circuit {i+1}"
		if circuit_name_key not in st.session_state:
			st.session_state[circuit_name_key] = default_label

		# what shows where
		circuit_title  = st.session_state[circuit_name_key]   # shown on checkbox row
		members_label  = ", ".join(component)                  # shown in expander header

		with target_col:
			# checkbox row: [chip] Circuit N
			cbox = st.checkbox(f"{circuit_title}", key=checkbox_key)
			toggles.append(cbox)
			pattern_labels.append(circuit_title)

			# expander shows only the member list on its header
			with st.expander(members_label, expanded=False):
				# rename field
				st.text_input("Circuit name", key=circuit_name_key)

				# --- Auto-save when circuit name changes (your same logic) ---
				if st.session_state.get("current_profile"):
					saved = st.session_state.get("saved_circuit_names", {})
					current_name = st.session_state[circuit_name_key]
					last_saved = saved.get(circuit_name_key, default_label)

					if current_name != last_saved:
						current = {
							f"circuit_name_{j}": st.session_state.get(f"circuit_name_{j}", f"Circuit {j+1}")
							for j in range(len(patterns))
						}
						profile_name = st.session_state["current_profile"]
						payload = saved_profiles.get(profile_name, {}).copy()
						payload["circuit_names"] = current
						save_user_profile_db(current_user_id, profile_name, payload)
						saved_profiles = load_user_profiles_db(current_user_id)
						st.session_state["saved_circuit_names"] = current.copy()

				# --- Sub-shapes (uses callback to safely toggle parent circuit) ---
				parent_shapes = [sh for sh in shapes if sh["parent"] == i]
				shape_entries = []
				if parent_shapes:
					st.markdown("**Sub-shapes detected:**")
					for sh in parent_shapes:
						label_text = f"{sh['type']}: {', '.join(str(m) for m in sh['members'])}"
						unique_key = f"shape_{i}_{sh['id']}"
						on = st.checkbox(
							label_text,
							key=unique_key,
							value=st.session_state.get(unique_key, False),
						)
						shape_entries.append({"id": sh["id"], "on": on})
				else:
					st.markdown("_(no sub-shapes found)_")

				shape_toggle_map = st.session_state.setdefault("shape_toggles_by_parent", {})
				shape_toggle_map[i] = shape_entries

	# --- Save Circuit Names button (only if edits exist) ---
	unsaved_changes = False
	if st.session_state.get("current_profile"):
		saved = st.session_state.get("saved_circuit_names", {})
		current = {
			f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
			for i in range(len(patterns))
		}
		if current != saved:
			unsaved_changes = True

		if unsaved_changes:
			st.markdown("---")
			if st.button("💾 Save Circuit Names"):
				profile_name = st.session_state["current_profile"]
				payload = saved_profiles.get(profile_name, {}).copy()
				payload["circuit_names"] = current
				save_user_profile_db(current_user_id, profile_name, payload)
				saved_profiles = load_user_profiles_db(current_user_id)
				st.session_state["saved_circuit_names"] = current.copy()

	_refresh_chart_figure()

	st.subheader("Chart")
	fig = st.session_state.get("render_fig")
	if fig is not None:
		st.pyplot(fig, clear_figure=False)
	else:
		st.caption("Calculate a chart to render the wheel.")

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
        objs_only = df_cached[~df_cached["Object"].str.contains("cusp", case=False, na=False)]
        blocks = [format_object_profile_html(r, house_label="Placidus") for _, r in objs_only.iterrows()]
        st.markdown("<div class='pf-root'>" + "\n".join(blocks) + "</div>", unsafe_allow_html=True)
    else:
        st.caption("Calculate a chart to see profiles.")
