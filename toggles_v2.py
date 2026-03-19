import datetime as dt
from dateutil.relativedelta import relativedelta
import pytz
import streamlit as st
from event_lookup_v2 import update_events_html_state
from models_v2 import static_db, DetectedShape
from src.state_manager import swap_primary_and_secondary_charts
from src import toggle_state as ts

GLYPHS = static_db.GLYPHS
TOGGLE_ASPECTS = static_db.TOGGLE_ASPECTS
ASPECTS = static_db.ASPECTS

COMPASS_KEY = "ui_compass_overlay"
COMPASS_KEY_2 = "ui_compass_overlay_2"  # separate overlay toggle for second chart (biwheel)


# ---------------------------------------------------------------------------
# Optimized callback functions for toggle state management
# ---------------------------------------------------------------------------

def _on_compass_inner_change():
    """Sync inner compass toggle to unified state."""
    ts.set_compass_inner(st.session_state.get(COMPASS_KEY, True))

def _on_compass_outer_change():
    """Sync outer compass toggle to unified state."""
    ts.set_compass_outer(st.session_state.get(COMPASS_KEY_2, True))

def _on_chart_mode_change():
    """Sync chart mode to unified state."""
    mode = st.session_state.get("__chart_mode_radio", "Circuits")
    ts.set_chart_mode(mode)
    st.session_state["chart_mode"] = mode

def _on_circuit_submode_change():
    """Sync circuit submode to unified state."""
    submode = st.session_state.get("__circuit_submode_radio", "Combined Circuits")
    ts.set_circuit_submode(submode)
    st.session_state["circuit_submode"] = submode

def _on_dark_mode_change():
    """Sync dark mode to unified state."""
    ts.set_dark_mode(st.session_state.get("dark_mode", False))

def _on_interactive_chart_change():
    """Sync interactive chart mode to unified state - NO toggle resets."""
    ts.set_interactive_chart(st.session_state.get("interactive_chart", False))

def _on_label_style_change():
    """Sync label style to unified state."""
    style = st.session_state.get("__label_style_choice_main", "Glyph").lower()
    ts.set_label_style(style)
    st.session_state["label_style"] = style

def _on_synastry_inter_change():
    """Sync synastry inter-chart aspects toggle."""
    ts.set_synastry_aspects_inter(st.session_state.get("synastry_aspects_inter", True))

def _on_synastry_chart1_change():
    """Sync synastry chart 1 aspects toggle."""
    ts.set_synastry_aspects_chart1(st.session_state.get("synastry_aspects_chart1", False))

def _on_synastry_chart2_change():
    """Sync synastry chart 2 aspects toggle."""
    ts.set_synastry_aspects_chart2(st.session_state.get("synastry_aspects_chart2", False))

# ---------------------------------------------------------------------------
# Transit Date Navigation Intervals
# ---------------------------------------------------------------------------

_TRANSIT_INTERVALS = {
	"1 day":    dt.timedelta(days=1),
	"1 week":   dt.timedelta(weeks=1),
	"1 month":  None,   # handled via relativedelta
	"1 year":   None,   # handled via relativedelta
	"1 decade": None,   # handled via relativedelta
}

def _apply_transit_offset(direction: int):
	"""Shift transit_dt_utc forward (+1) or backward (-1) by the selected interval."""
	from src.chart_core import run_transit_chart

	current = st.session_state.get("transit_dt_utc")
	if current is None:
		current = dt.datetime.utcnow()

	interval_label = st.session_state.get("transit_nav_interval", "1 day")

	if interval_label == "1 day":
		delta = dt.timedelta(days=1)
		new_dt = current + (delta if direction > 0 else -delta)
	elif interval_label == "1 week":
		delta = dt.timedelta(weeks=1)
		new_dt = current + (delta if direction > 0 else -delta)
	elif interval_label == "1 month":
		new_dt = current + relativedelta(months=direction)
	elif interval_label == "1 year":
		new_dt = current + relativedelta(years=direction)
	elif interval_label == "1 decade":
		new_dt = current + relativedelta(years=10 * direction)
	else:
		new_dt = current + dt.timedelta(days=direction)

	st.session_state["transit_dt_utc"] = new_dt
	run_transit_chart()


def _set_transit_now():
	"""Reset transit time to the current moment and recalculate."""
	from src.chart_core import run_transit_chart
	st.session_state["transit_dt_utc"] = dt.datetime.utcnow()
	run_transit_chart()


def _apply_direct_transit_date():
	"""Apply the direct date/time inputs from the expander to transit_dt_utc.

	The user enters date/time in the location's local timezone; convert to UTC
	before storing.
	"""
	from src.chart_core import run_transit_chart

	d = st.session_state.get("transit_direct_date")
	t = st.session_state.get("transit_direct_time", dt.time(12, 0))
	if d is not None:
		tz_name = st.session_state.get("current_tz_name", "UTC")
		try:
			tz = pytz.timezone(tz_name)
			local_naive = dt.datetime.combine(d, t)
			utc_dt = tz.localize(local_naive).astimezone(pytz.utc).replace(tzinfo=None)
		except Exception:
			utc_dt = dt.datetime.combine(d, t)
		st.session_state["transit_dt_utc"] = utc_dt
		run_transit_chart()


def _render_transit_date_nav():
	"""Render the transit date navigator: fwd/back buttons, interval dropdown, date display, and direct input expander."""
	# Ensure a transit datetime exists
	if st.session_state.get("transit_dt_utc") is None:
		st.session_state["transit_dt_utc"] = dt.datetime.utcnow()

	transit_dt_utc = st.session_state["transit_dt_utc"]

	# Convert UTC → local timezone for display and input pre-population
	tz_name = st.session_state.get("current_tz_name", "UTC")
	try:
		tz = pytz.timezone(tz_name)
		transit_dt = transit_dt_utc.replace(tzinfo=pytz.utc).astimezone(tz)
		tz_abbr = transit_dt.strftime("%Z")
	except Exception:
		transit_dt = transit_dt_utc
		tz_abbr = "UTC"

	# Display current transit date/time (local)
	st.caption(f"Transit: **{transit_dt.strftime('%b %d, %Y  %H:%M')} {tz_abbr}**")

	# --- Forward / Back buttons + Interval dropdown ---
	nav_cols = st.columns([1, 1, 1, 2])

	with nav_cols[0]:
		st.button("◀", key="transit_nav_back",
				  on_click=_apply_transit_offset, args=(-1,),
				  use_container_width=True)
	with nav_cols[1]:
		st.button("▶", key="transit_nav_fwd",
				  on_click=_apply_transit_offset, args=(1,),
				  use_container_width=True)
	with nav_cols[2]:
		st.button("Now", key="transit_nav_now",
				  on_click=_set_transit_now,
				  use_container_width=True)
	with nav_cols[3]:
		st.session_state.setdefault("transit_nav_interval", "1 day")
		st.selectbox(
			"Step",
			options=list(_TRANSIT_INTERVALS.keys()),
			key="transit_nav_interval",
			label_visibility="collapsed",
		)

	# --- Direct date/time input (collapsed expander) ---
	with st.expander("Set date & time directly", expanded=False):
		d_col, t_col = st.columns(2)
		with d_col:
			st.date_input(
				"Date",
				value=transit_dt.date(),
				key="transit_direct_date",
				min_value=dt.date(1, 1, 1),
				max_value=dt.date(9999, 12, 31),
			)
		with t_col:
			st.time_input(
				f"Time ({tz_abbr})",
				value=transit_dt.time().replace(second=0, microsecond=0),
				key="transit_direct_time",
			)
		st.button("Apply", key="transit_direct_apply",
				  on_click=_apply_direct_transit_date,
				  use_container_width=True)


def render_circuit_toggles(
	patterns,
	shapes,
	singleton_map,
	saved_profiles,
	current_user_id,
	save_user_profile_db,
	load_user_profiles_db,
):
	"""
	Renders the Circuits UI (checkboxes, expanders, bulk buttons, compass rose, sub-shapes)
	and handles saving circuit names.

	Uses unified toggle state to preserve values across Interactive Chart mode toggling.

	Returns:
		toggles (list[bool]), pattern_labels (list[str]), saved_profiles (dict)
	"""
	# --- SYNC FROM UNIFIED STATE (preserves values across mode switches) ---
	# Migrate any existing legacy keys to unified state on first run
	ts.sync_from_legacy_keys()
	
	st.session_state.pop("events_block", None)
	# guards
	patterns = patterns or []
	shapes = shapes or []
	singleton_map = singleton_map or {}
	toggles: list[bool] = []
	pattern_labels: list[str] = []

	# --- PRE-INIT using unified state (batch initialization for speed) ---
	# Patterns: ensure keys exist, preserve existing values
	for i in range(len(patterns)):
		key = f"toggle_pattern_{i}"
		existing = ts.get_pattern_toggle(i)
		st.session_state.setdefault(key, existing)
		# Also sync to shapes for this pattern
		for sh in [sh for sh in shapes if sh.parent == i]:
			shape_key = f"shape_{i}_{sh.shape_id}"
			existing_shape = ts.get_shape_toggle(i, sh.shape_id)
			st.session_state.setdefault(shape_key, existing_shape)
	
	# Singletons: ensure keys exist, preserve existing values
	if singleton_map:
		for planet in singleton_map.keys():
			key = f"singleton_{planet}"
			existing = ts.get_singleton_toggle(planet)
			st.session_state.setdefault(key, existing)

	# Pre-init Connected Circuits Chart 2 shape toggle keys.
	_biwheel_cc = (
		(st.session_state.get("synastry_mode") or st.session_state.get("transit_mode", False))
		and ts.get_circuit_submode() == "Connected Circuits"
	)
	if _biwheel_cc:
		_cc_shapes2_init = st.session_state.get("circuit_connected_shapes2", {})
		for _ci in range(len(patterns)):
			for _sh2 in _cc_shapes2_init.get(_ci, []):
				_sh2_id = _sh2.shape_id if hasattr(_sh2, "shape_id") else _sh2.get("id", f"x_{_ci}")
				key = f"cc_shape_{_ci}_{_sh2_id}"
				existing = ts.get_cc_shape_toggle(_ci, _sh2_id)
				st.session_state.setdefault(key, existing)

	# Compass keys from unified state
	st.session_state.setdefault(COMPASS_KEY, ts.get_compass_inner())
	st.session_state.setdefault(COMPASS_KEY_2, ts.get_compass_outer())
	# Track previous checkbox values for delayed rerun
	st.session_state.setdefault("_last_compass_value", st.session_state.get(COMPASS_KEY, True))
	st.session_state.setdefault("_last_compass_value_2", st.session_state.get(COMPASS_KEY_2, True))

	# --- Chart Mode Selector ---
	# Use unified state as source of truth
	_current_mode = ts.get_chart_mode()
	st.session_state.setdefault("chart_mode", _current_mode)
	mode_col1, mode_col2 = st.columns([1, 5])
	with mode_col1:
		chart_mode = st.radio(
			"Chart Mode",
			["Standard Chart", "Circuits"],
			index=0 if _current_mode == "Standard Chart" else 1,
			key="__chart_mode_radio",
			horizontal=False,
			on_change=_on_chart_mode_change,
		)
		# Sync both the derived key and unified state
		ts.set_chart_mode(chart_mode)
		st.session_state["chart_mode"] = chart_mode

	# --- Handle pending "Hide All" (from previous run) safely ---
	if st.session_state.get("__pending_hide_all__"):
		# Use unified state for hide all
		ts.hide_all(len(patterns), shapes, list(singleton_map.keys()))
		# Also update legacy session keys for widgets
		updates = {}
		for i in range(len(patterns)):
			updates[f"toggle_pattern_{i}"] = False
			ts.set_pattern_toggle(i, False)
		for sh in shapes:
			updates[f"shape_{sh.parent}_{sh.shape_id}"] = False
			ts.set_shape_toggle(sh.parent, sh.shape_id, False)
		if singleton_map:
			for planet in singleton_map.keys():
				updates[f"singleton_{planet}"] = False
				ts.set_singleton_toggle(planet, False)
		updates[COMPASS_KEY] = False
		updates[COMPASS_KEY_2] = False
		st.session_state.update(updates)
		st.session_state["__pending_hide_all__"] = False
		st.rerun()
	
	# --- Handle pending "Show All" (from previous run) safely ---
	if st.session_state.get("__pending_show_all__"):
		# Use unified state for show all
		ts.show_all(len(patterns), list(singleton_map.keys()))
		# Also update legacy session keys for widgets
		updates = {}
		for i in range(len(patterns)):
			updates[f"toggle_pattern_{i}"] = True
			ts.set_pattern_toggle(i, True)
		if singleton_map:
			for planet in singleton_map.keys():
				updates[f"singleton_{planet}"] = True
				ts.set_singleton_toggle(planet, True)
		updates[COMPASS_KEY] = True
		updates[COMPASS_KEY_2] = True
		st.session_state.update(updates)
		st.session_state["__pending_show_all__"] = False
		st.rerun()

	# ---------- Header + events panel ----------
	
	# Adjust header based on chart mode
	chart_mode = st.session_state.get("chart_mode", "Circuits")
	header_text = "🗺️Circuits" if chart_mode == "Circuits" else "Standard Chart"

	header_col, events_col, jump_col = st.columns([1, 6, 2])
	with header_col:
		st.subheader(header_text)
	with jump_col:
		if st.session_state.get("synastry_mode", False):
			st.button("🔄 Swap Charts", key="swap_chart_wheels", on_click=swap_primary_and_secondary_charts, use_container_width=True)
		st.markdown(
			'<a href="#ruler-hierarchies" style="display:inline-block;padding:0.25rem 0.75rem;background-color:#ff4b4b;color:white;text-decoration:none;border-radius:0.25rem;text-align:center;width:100%;">Jump to Houses & Rulers</a>',
			unsafe_allow_html=True
		)
	with events_col:
		# Reserve a dedicated spot for the events block so we can reliably
		# clear any prior render when a new chart is calculated.
		events_placeholder = st.empty()

		# Always compute and blank/overwrite first on every rerun
		_chart_for_events = st.session_state.get("last_chart")
		update_events_html_state(
				_chart_for_events.utc_datetime if _chart_for_events else None,
				events_path="events.jsonl",
				show_no_events=False,   # flip True if you want a soft message on no results
		)

		# Single, fixed render point. When there is no HTML, explicitly
		# empty the placeholder so stale content never lingers.
		html = st.session_state.get("events_lookup_html", "")
		if html:
				events_placeholder.markdown(html, unsafe_allow_html=True)
		else:
				events_placeholder.empty()
						
	st.divider()
	
	# ---------- Circuits Mode-Specific UI ----------
	if chart_mode == "Circuits":
		# Only offer Combined / Connected sub-modes when a second chart exists.
		_synastry_now = st.session_state.get("synastry_mode", False) or st.session_state.get("transit_mode", False)
		if _synastry_now:
			# Force submode to Combined Circuits whenever we enter biwheel from single-chart
			_current_submode = ts.get_circuit_submode()
			if _current_submode == "single":
				ts.set_circuit_submode("Combined Circuits")
				_current_submode = "Combined Circuits"
			st.session_state.setdefault("circuit_submode", _current_submode)
			submode = st.radio(
				"Circuit View Mode",
				["Combined Circuits", "Connected Circuits"],
				index=0 if _current_submode == "Combined Circuits" else 1,
				key="__circuit_submode_radio",
				horizontal=False,
				on_change=_on_circuit_submode_change,
			)
			# Sync to both unified state and session state
			ts.set_circuit_submode(submode)
			st.session_state["circuit_submode"] = submode
		else:
			# Single-chart: always use normal circuit view; clear any stale submode
			ts.set_circuit_submode("single")
			st.session_state["circuit_submode"] = "single"

		c1, c2, c3, c4 = st.columns([2, 1, 1, 2])

		with c1:
			synastry_mode = st.session_state.get("synastry_mode", False)
			biwheel_active = synastry_mode or st.session_state.get("transit_mode", False)
			# chart names from loaded chart objects
			_c1 = st.session_state.get("last_chart")
			chart1_name = (_c1.display_name if _c1 and _c1.display_name else None) or st.session_state.get("current_profile") or "Chart 1"
			unknown_time1 = bool(
				(_c1.unknown_time if _c1 else False)
				or st.session_state.get("profile_unknown_time")
			)
			label1 = f"{chart1_name} {'Compass Needle' if unknown_time1 else 'Compass Rose'}"
			new_value = st.checkbox(label1, key=COMPASS_KEY, on_change=_on_compass_inner_change)

			# second chart toggle if biwheel is active
			if biwheel_active:
				if synastry_mode:
					_c2 = st.session_state.get("last_chart_2")
					chart2_name = (_c2.display_name if _c2 and _c2.display_name else None) or "Chart 2"
				else:
					chart2_name = "Transits"
					_c2 = st.session_state.get("last_chart_2")
				unknown_time2 = bool(_c2.unknown_time if _c2 else False)
				label2 = f"{chart2_name} {'Compass Needle' if unknown_time2 else 'Compass Rose'}"
				new_value2 = st.checkbox(label2, key=COMPASS_KEY_2, on_change=_on_compass_outer_change)

		# Track compass value change and sync to unified state
		prev_value = st.session_state.get("_last_compass_value")
		if new_value != prev_value:
			ts.set_compass_inner(new_value)
			st.session_state["_last_compass_value"] = new_value
			st.session_state["_pending_compass_rerun"] = True
		# track second
		if biwheel_active:
			prev2 = st.session_state.get("_last_compass_value_2")
			if new_value2 != prev2:
				ts.set_compass_outer(new_value2)
				st.session_state["_last_compass_value_2"] = new_value2
				st.session_state["_pending_compass_rerun"] = True

		with c2:
			if st.button("Show All", key="btn_show_all_main"):
				st.session_state["__pending_show_all__"] = True
				st.rerun()

		with c3:
			if st.button("Hide All", key="btn_hide_all_main"):
				# store desired state for next run instead of mutating live widget state
				st.session_state["__pending_hide_all__"] = True
				st.rerun()

		# Use unified state for label style
		_current_label_style = ts.get_label_style()
		st.session_state.setdefault("label_style", _current_label_style)
		with c4:
			st.subheader("Single Placements")

			# --- ensure label style is fully synced before rendering ---
			old_style = st.session_state.get("label_style", "glyph")
			# The radio button writes to this key; read its current choice
			new_style = st.session_state.get("__label_style_choice", old_style)
			st.session_state["label_style"] = new_style.lower()

			# now use the up-to-date label style
			label_style = st.session_state["label_style"]
			want_glyphs = label_style == "glyph"

			if singleton_map:
				cols_per_row = min(8, max(1, len(singleton_map)))
				cols = st.columns(cols_per_row)
				for j, (planet, _) in enumerate(singleton_map.items()):
					with cols[j % cols_per_row]:
						key = f"singleton_{planet}"
						label_text = GLYPHS.get(planet, planet) if want_glyphs else planet
						if key not in st.session_state:
							st.checkbox(label_text, value=False, key=key)
						else:
							st.checkbox(label_text, key=key)
			else:
				st.markdown("_(none)_")
	else:
		# ---------- Standard Chart Mode UI ----------
		synastry_mode = st.session_state.get("synastry_mode", False)
		
		with st.container():
			# chart names from loaded chart objects
			_c1 = st.session_state.get("last_chart")
			chart1_name = (_c1.display_name if _c1 and _c1.display_name else None) or st.session_state.get("current_profile") or "Chart 1"
			unknown_time1 = bool(
				(_c1.unknown_time if _c1 else False)
				or st.session_state.get("profile_unknown_time")
			)
			label1 = f"{chart1_name} {'Compass Needle' if unknown_time1 else 'Compass Rose'}"
			new_value = st.checkbox(label1, key=COMPASS_KEY, on_change=_on_compass_inner_change)

			# optionally show second chart toggle
			synastry_mode = st.session_state.get("synastry_mode", False)
			biwheel_active = synastry_mode or st.session_state.get("transit_mode", False)
			if biwheel_active:
				if synastry_mode:
					_c2 = st.session_state.get("last_chart_2")
					chart2_name = (_c2.display_name if _c2 and _c2.display_name else None) or "Chart 2"
				else:
					chart2_name = "Transits"
					_c2 = st.session_state.get("last_chart_2")
				unknown_time2 = bool(_c2.unknown_time if _c2 else False)
				label2 = f"{chart2_name} {'Compass Needle' if unknown_time2 else 'Compass Rose'}"
				new_value2 = st.checkbox(label2, key=COMPASS_KEY_2, on_change=_on_compass_outer_change)

			# Track compass value change and sync to unified state
			prev_value = st.session_state.get("_last_compass_value")
			if new_value != prev_value:
				ts.set_compass_inner(new_value)
				st.session_state["_last_compass_value"] = new_value
				st.session_state["_pending_compass_rerun"] = True
			# second
			if biwheel_active:
				prev2 = st.session_state.get("_last_compass_value_2")
				if new_value2 != prev2:
					ts.set_compass_outer(new_value2)
					st.session_state["_last_compass_value_2"] = new_value2
					st.session_state["_pending_compass_rerun"] = True
		st.markdown("---")

	circuits_col, spacer_col, options_col = st.columns([3, 1, 2])
	
	# Add Standard Chart aspect toggles in left column
	if chart_mode == "Standard Chart":
		with circuits_col:
			# Check if we're in biwheel mode (synastry or transits)
			synastry_mode = st.session_state.get("synastry_mode", False)
			biwheel_active = synastry_mode or st.session_state.get("transit_mode", False)

			if biwheel_active:
				# Biwheel mode: show aspect group toggles
				st.subheader("Aspect Groups")

				# Get chart names from loaded chart objects
				_c1 = st.session_state.get("last_chart")
				chart1_name = (_c1.display_name if _c1 and _c1.display_name else None) or st.session_state.get("current_profile") or "Chart 1"
				if synastry_mode:
					_c2 = st.session_state.get("last_chart_2")
					chart2_name = (_c2.display_name if _c2 and _c2.display_name else None) or "Chart 2"
				else:
					chart2_name = "Transits"

				# Initialize synastry aspect group toggles from unified state
				st.session_state.setdefault("synastry_aspects_inter", ts.get_synastry_aspects_inter())
				st.session_state.setdefault("synastry_aspects_chart1", ts.get_synastry_aspects_chart1())
				st.session_state.setdefault("synastry_aspects_chart2", ts.get_synastry_aspects_chart2())

				# Aspect group toggles with on_change callbacks
				st.checkbox(f"{chart1_name} ↔ {chart2_name}", key="synastry_aspects_inter", on_change=_on_synastry_inter_change)
				st.checkbox(f"{chart1_name} Aspects", key="synastry_aspects_chart1", on_change=_on_synastry_chart1_change)
				st.checkbox(f"{chart2_name} Aspects", key="synastry_aspects_chart2", on_change=_on_synastry_chart2_change)

				st.markdown("---")
			with st.expander("Additional Aspects"):
				
				# Get current label style
				label_style = ts.get_label_style()
				want_glyphs = label_style == "glyph"
				
				# Select All checkbox
				select_all_key = "aspect_toggle_select_all"
				st.session_state.setdefault(select_all_key, False)
				select_all = st.checkbox("Select All", key=select_all_key)
				
				# If select all state changed, update all toggles
				if select_all != st.session_state.get("_last_select_all_state", False):
					for body_name in TOGGLE_ASPECTS.keys():
						st.session_state[f"aspect_toggle_{body_name}"] = select_all
					st.session_state["_last_select_all_state"] = select_all
				
				# Create checkboxes for TOGGLE_ASPECTS in a grid
				toggle_bodies = list(TOGGLE_ASPECTS.keys())
				cols_per_row = 4
				cols = st.columns(cols_per_row)
				
				for j, body_name in enumerate(toggle_bodies):
					with cols[j % cols_per_row]:
						key = f"aspect_toggle_{body_name}"
						label_text = GLYPHS.get(body_name, body_name) if want_glyphs else body_name
						st.session_state.setdefault(key, False)
						st.checkbox(label_text, key=key)

	with spacer_col:
		st.write("")  # just a spacer

	with circuits_col:
		# Get synastry and circuit mode state
		synastry_mode = st.session_state.get("synastry_mode", False)
		biwheel_active = synastry_mode or st.session_state.get("transit_mode", False)
		circuit_submode = st.session_state.get("circuit_submode", "Combined Circuits")

		# Combined Circuits mode in biwheel (synastry or transits): show only shapes, grouped by type
		if chart_mode == "Circuits" and biwheel_active and circuit_submode == "Combined Circuits":
			# Get current label style
			label_style = st.session_state.get("label_style", "glyph")
			want_glyphs = label_style == "glyph"
			
			if shapes:
				st.subheader("Combined Shapes")
				
				# Group shapes by type
				shapes_by_type: dict[str, list] = {}
				for sh in shapes:
					shape_type = sh.shape_type
					if shape_type not in shapes_by_type:
						shapes_by_type[shape_type] = []
					shapes_by_type[shape_type].append(sh)
				
				# Node counts from patterns_v2.py shape detection:
				# - Envelope: combinations(R, 5) → 5 nodes
				# - Grand Cross, Mystic Rectangle, Cradle, Kite: combinations(R, 4) → 4 nodes
				# - Lightning Bolt: [q1, q2, r1, r2] → 4 nodes
				# - Grand Trine, T-Square, Wedge, Sextile Wedge: combinations(R, 3) → 3 nodes
				# - Yod, Wide Yod, Unnamed: [a, b, c] → 3 nodes
				SHAPE_NODE_COUNTS = {
					"Envelope": 5,
					"Grand Cross": 4,
					"Mystic Rectangle": 4,
					"Cradle": 4,
					"Kite": 4,
					"Lightning Bolt": 4,
					"Grand Trine": 3,
					"T-Square": 3,
					"Wedge": 3,
					"Sextile Wedge": 3,
					"Yod": 3,
					"Wide Yod": 3,
					"Unnamed": 3,
					"Remainder": 2,  # variable, but listed last
				}
				
				# Sort shape types by node count (descending), then alphabetically
				sorted_types = sorted(
					shapes_by_type.keys(),
					key=lambda t: (-SHAPE_NODE_COUNTS.get(t, 1), t)
				)
				
				# Render shapes grouped by type in two columns of expanders
				half = (len(sorted_types) + 1) // 2
				col_left, col_right = st.columns(2)
				for idx, shape_type in enumerate(sorted_types):
					type_shapes = shapes_by_type[shape_type]
					node_count = SHAPE_NODE_COUNTS.get(shape_type, len(type_shapes[0].members) if type_shapes else 2)
					# choose column
					target_col = col_left if idx < half else col_right
					with target_col:
						with st.expander(f"**{shape_type}** – {len(type_shapes)} found", expanded=False):
							# resolve chart names once per expander
							_c1 = st.session_state.get("last_chart")
							chart1_name = (_c1.display_name if _c1 and _c1.display_name else None) or st.session_state.get("current_profile") or "Chart 1"
							_c2 = st.session_state.get("last_chart_2")
							chart2_name = (_c2.display_name if _c2 and _c2.display_name else None) or "Chart 2"
							for sh in type_shapes:
								members = sh.members
								members1 = [m for m in members if not m.endswith("_2")]
								members2 = [m[:-2] for m in members if m.endswith("_2")]

								def fmt_list(lst):
									if want_glyphs:
										return ", ".join(GLYPHS.get(m, m) for m in lst)
									else:
										return ", ".join(lst)

								members_label = f"{chart1_name}: {fmt_list(members1)}"
								if members2:
									members_label += f"; {chart2_name}: {fmt_list(members2)}"
								parent = sh.parent
								shape_id = sh.shape_id
								unique_key = f"shape_{parent}_{shape_id}"
								st.session_state.setdefault(unique_key, False)
								st.checkbox(
									members_label,
									key=unique_key,
									value=st.session_state.get(unique_key, False),
								)
				
				# Build shape toggle map fresh each rerun (not setdefault/append,
				# which would accumulate stale entries across Streamlit reruns)
				shape_toggle_map: dict = {}
				for sh in shapes:
					parent = sh.parent
					if parent not in shape_toggle_map:
						shape_toggle_map[parent] = []
					unique_key = f"shape_{parent}_{sh.shape_id}"
					shape_toggle_map[parent].append({
						"id": sh.shape_id,
						"on": st.session_state.get(unique_key, False)
					})
				st.session_state["shape_toggles_by_parent"] = shape_toggle_map
			else:
				st.info("No shapes detected in combined charts.")
			
			# Empty toggles/pattern_labels for Combined Circuits mode
			toggles = []
			pattern_labels = []
		
		# Regular Circuits mode (single chart or Connected Circuits in synastry)
		elif chart_mode == "Circuits":
			# Compute circuit_connected_shapes2 fresh here so it is always ready
			# when the expander loop runs below.  Reading it from session state
			# would be stale because _refresh_chart_figure runs AFTER this function.
			circuit_connected_shapes2: dict[int, list] = {}
			if (synastry_mode or st.session_state.get("transit_mode", False)) and circuit_submode == "Connected Circuits":
				_cc_chart_1 = st.session_state.get("last_chart")
				_cc_chart_2 = st.session_state.get("last_chart_2")
				_pos_inner = (_cc_chart_1.positions if _cc_chart_1 else {}) or {}
				_pos_outer = (_cc_chart_2.positions if _cc_chart_2 else {}) or {}
				_shapes_2  = (_cc_chart_2.shapes if _cc_chart_2 else []) or []
				# Build all inter-chart aspects (Chart 1 × Chart 2 bodies)
				_edges_inter: list[tuple[str, str, str]] = []
				for _ep1, _d1 in _pos_inner.items():
					for _ep2, _d2 in _pos_outer.items():
						_angle = abs(_d1 - _d2) % 360
						if _angle > 180:
							_angle = 360 - _angle
						for _asp_name, _asp_data in ASPECTS.items():
							if abs(_angle - _asp_data["angle"]) <= _asp_data["orb"]:
								_edges_inter.append((_ep1, _ep2, _asp_name))
								break
				for _ci, _component in enumerate(patterns):
					_comp_set = set(_component)
					_connected = {_ep2 for (_ep1, _ep2, _) in _edges_inter if _ep1 in _comp_set}
					_linked = [sh for sh in _shapes_2 if set(sh.members) & _connected]
					# Also add singleton entries for connected Chart 2 planets
					# that aren't already covered by a linked shape.
					_covered = set()
					for sh in _linked:
						_covered.update(sh.members)
					for _planet in sorted(_connected - _covered):
						_linked.append({
							"type": "Single object",
							"members": [_planet],
							"id": f"singleton_{_ci}_{_planet}",
						})
					if _linked:
						circuit_connected_shapes2[_ci] = _linked
				# Persist for the drawing function in _refresh_chart_figure
				st.session_state["circuit_connected_shapes2"] = circuit_connected_shapes2
				st.session_state["edges_inter_chart_cc"] = _edges_inter

			# Pattern checkboxes + expanders
			half = (len(patterns) + 1) // 2
			left_patterns, right_patterns = st.columns(2)

			# Get current label style
			label_style = st.session_state.get("label_style", "glyph")
			want_glyphs = label_style == "glyph"

			for i, component in enumerate(patterns):
				target_col = left_patterns if i < half else right_patterns
				checkbox_key = f"toggle_pattern_{i}"

				# circuit name session key
				circuit_name_key = f"circuit_name_{i}"
				default_label = f"Circuit {i+1}"
				st.session_state.setdefault(circuit_name_key, default_label)

				circuit_title = st.session_state[circuit_name_key]  # shown on checkbox row
				# Apply glyph/text style to planet names in expander header
				if want_glyphs:
					members_label = ", ".join(GLYPHS.get(planet, planet) for planet in component)
				else:
					members_label = ", ".join(component)

				with target_col:
					cbox = st.checkbox(f"{circuit_title}", key=checkbox_key)
					toggles.append(cbox)
					pattern_labels.append(circuit_title)

					with st.expander(members_label, expanded=False):
						st.text_input("Circuit name", key=circuit_name_key)

						# Auto-save when circuit name changes (only when a profile is active)
						if st.session_state.get("current_profile"):
							saved = st.session_state.get("saved_circuit_names", {})
							current_name = st.session_state[circuit_name_key]
							last_saved = saved.get(circuit_name_key, default_label)
							if current_name != last_saved:
								current = {
									f"circuit_name_{j}": st.session_state.get(
										f"circuit_name_{j}", f"Circuit {j+1}"
									)
									for j in range(len(patterns))
								}
								profile_name = st.session_state["current_profile"]
								payload = saved_profiles.get(profile_name, {}).copy()
								payload["circuit_names"] = current
								save_user_profile_db(current_user_id, profile_name, payload)
								# Update local dict (cache was already cleared by save)
								saved_profiles[profile_name] = payload
								st.session_state["saved_circuit_names"] = current.copy()

						# Sub-shapes (always visible, not gated on profile)
						parent_shapes = [sh for sh in shapes if sh.parent == i]
						shape_entries = []
						if parent_shapes:
							st.markdown("**Sub-shapes:**")
							for sh in parent_shapes:
								label_text = f"{sh.shape_type}: {', '.join(str(m) for m in sh.members)}"
								unique_key = f"shape_{i}_{sh.shape_id}"
								on = st.checkbox(
									label_text,
									key=unique_key,
									value=st.session_state.get(unique_key, False),
								)
								shape_entries.append({"id": sh.shape_id, "on": on})

						shape_toggle_map = st.session_state.setdefault(
							"shape_toggles_by_parent", {}
						)
						shape_toggle_map[i] = shape_entries

						# ---------- Chart 2 Connections (Connected Circuits + synastry only) ----------
						# Show connections when the circuit itself OR any of its sub-shapes is active.
						any_shape_on = any(e["on"] for e in shape_entries)
						if (synastry_mode or st.session_state.get("transit_mode", False)) and circuit_submode == "Connected Circuits" and (cbox or any_shape_on) and i in circuit_connected_shapes2:
							cc2_items = circuit_connected_shapes2[i]

							# When only sub-shapes are active (not the whole circuit),
							# narrow down to Chart 2 shapes directly connected to
							# the active sub-shape members via inter-chart aspects.
							if not cbox and any_shape_on:
								_active_sh1_ids = {e["id"] for e in shape_entries if e["on"]}
								_active_sh1_members = set()
								for _sh1 in parent_shapes:
									if _sh1.shape_id in _active_sh1_ids:
										_active_sh1_members.update(_sh1.members)
								_inter = st.session_state.get("edges_inter_chart_cc", [])
								_connected_to_active = {
									ep2 for (ep1, ep2, _) in _inter
									if ep1 in _active_sh1_members
								}
								cc2_items = [
									sh2 for sh2 in cc2_items
									if set(
										sh2.get("members", []) if isinstance(sh2, dict)
										else getattr(sh2, "members", [])
									) & _connected_to_active
								]

							if cc2_items:
								st.markdown("**Connected in Chart 2:**")
								for sh2 in cc2_items:
									sh2_type = (sh2.get("type", "Shape") if hasattr(sh2, "get")
												else getattr(sh2, "shape_type", "Shape"))
									sh2_members = (sh2.get("members", []) if hasattr(sh2, "get")
												  else getattr(sh2, "members", []))
									sh2_id = (sh2.get("id", f"x_{i}") if hasattr(sh2, "get")
											  else getattr(sh2, "shape_id", f"x_{i}"))
									if want_glyphs:
										members_text = ", ".join(GLYPHS.get(m, m) for m in sh2_members)
									else:
										members_text = ", ".join(str(m) for m in sh2_members)
									cc_key = f"cc_shape_{i}_{sh2_id}"
									st.session_state.setdefault(cc_key, False)
									st.checkbox(f"{sh2_type}: {members_text}", key=cc_key)

			# Save Circuit Names (only if edits exist)
			if st.session_state.get("current_profile"):
				saved = st.session_state.get("saved_circuit_names", {})
				current = {
					f"circuit_name_{i}": st.session_state.get(
						f"circuit_name_{i}", f"Circuit {i+1}"
					)
					for i in range(len(patterns))
				}
				if current != saved:
					if st.button("💾 Save Circuit Names"):
						profile_name = st.session_state["current_profile"]
						payload = saved_profiles.get(profile_name, {}).copy()
						payload["circuit_names"] = current
						save_user_profile_db(current_user_id, profile_name, payload)
						# Update local dict (cache was already cleared by save)
						saved_profiles[profile_name] = payload
						st.session_state["saved_circuit_names"] = current.copy()

	# ---------- RIGHT: house system / label style / dark mode ----------
	with options_col:
		# Only show these after a chart exists
		if st.session_state.get("last_chart") is not None:
			# House selector moved to dispositor graph section
			# from house_selector_v2 import render_house_system_selector
			# render_house_system_selector()

			# --- Label Style (keep visual location, fix instant sync) ---
			_current_label_style = ts.get_label_style()
			st.session_state.setdefault("label_style", _current_label_style)
			label_default_is_glyph = _current_label_style == "glyph"

			label_choice = st.radio(
				"Label Style",
				["Text", "Glyph"],
				index=(1 if label_default_is_glyph else 0),
				horizontal=True,
				key="__label_style_choice_main",
				on_change=_on_label_style_change,
			)
			new_style = label_choice.lower()

			# Sync to both unified state and session state
			ts.set_label_style(new_style)
			st.session_state["label_style"] = new_style

			# Dark mode → persist to session and unified state
			_current_dark_mode = ts.get_dark_mode()
			st.session_state.setdefault("dark_mode", _current_dark_mode)
			st.checkbox("🌙 Dark Mode", key="dark_mode", on_change=_on_dark_mode_change)

			# Interactive D3 chart toggle - uses on_change to preserve other toggles
			_current_interactive = ts.get_interactive_chart()
			st.session_state.setdefault("interactive_chart", _current_interactive)
			st.checkbox("✨ Interactive Chart", key="interactive_chart",
						on_change=_on_interactive_chart_change,
						help="Switch to the interactive D3.js/SVG chart with hover tooltips and click events")

			# Transits toggle — visible whenever a chart is loaded and synastry is off
			_synastry_now = st.session_state.get("synastry_mode", False)
			if not _synastry_now:
				def _on_transit_toggle():
					from src.chart_core import run_transit_chart
					if st.session_state.get("transit_mode", False):
						# Just activated — start from current time
						st.session_state["transit_dt_utc"] = dt.datetime.utcnow()
						run_transit_chart()
					else:
						# Just deactivated — clear stale Chart 2 so next activation recalculates
						st.session_state.pop("last_chart_2", None)
						st.session_state.pop("transit_dt_utc", None)
						st.session_state.pop("chart_2_source", None)

				st.session_state.setdefault("transit_mode", False)
				st.checkbox(
					"🌐 Transits",
					key="transit_mode",
					on_change=_on_transit_toggle,
				)

				# --- Transit date navigator (only when transits are active) ---
				if st.session_state.get("transit_mode", False):
					_render_transit_date_nav()

				# --- Now-mode date navigator (single chart, Now button was used) ---
				if (
					st.session_state.get("now_mode_active", False)
					and not st.session_state.get("transit_mode", False)
				):
					from now_v2 import render_now_date_nav
					render_now_date_nav()

	# If compass value changed, trigger a single safe rerun *after* all widgets exist
	if st.session_state.get("_pending_compass_rerun"):
		st.session_state["_pending_compass_rerun"] = False
		st.rerun()

	# --- SYNC back to unified state and legacy keys before return ---
	# This ensures all toggle values are preserved across mode switches
	
	# Sync pattern toggles to unified state
	for i in range(len(patterns)):
		key = f"toggle_pattern_{i}"
		val = st.session_state.get(key, False)
		ts.set_pattern_toggle(i, val)
	
	# Sync singleton toggles to unified state
	for planet in singleton_map.keys():
		key = f"singleton_{planet}"
		val = st.session_state.get(key, False)
		ts.set_singleton_toggle(planet, val)
	
	# Sync shape toggles to unified state
	for sh in shapes:
		key = f"shape_{sh.parent}_{sh.shape_id}"
		val = st.session_state.get(key, False)
		ts.set_shape_toggle(sh.parent, sh.shape_id, val)
	
	# return AFTER both columns render
	chart_mode = ts.get_chart_mode()
	circuit_submode = ts.get_circuit_submode()
	
	# Collect aspect toggles for Standard Chart mode (from unified state)
	aspect_toggles = {}
	if chart_mode == "Standard Chart":
		for body_name in TOGGLE_ASPECTS.keys():
			key = f"aspect_toggle_{body_name}"
			val = st.session_state.get(key, False)
			aspect_toggles[body_name] = val
			ts.set_aspect_toggle(body_name, val)
	
	return toggles, pattern_labels, saved_profiles, chart_mode, aspect_toggles, circuit_submode

