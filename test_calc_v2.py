import os, sys
import json
import streamlit.components.v1 as components
import swisseph as swe
EPHE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "ephe"))
EPHE_PATH = EPHE_PATH.replace("\\", "/")
os.environ["SE_EPHE_PATH"] = EPHE_PATH
swe.set_ephe_path(EPHE_PATH)
from src.ui_utils import apply_custom_css, set_background_for_theme
from src.test_data import MONTH_NAMES
from src.geocoding import geocode_city_with_timezone
from src.chart_core import run_chart, _refresh_chart_figure
from src.state_manager import swap_primary_and_secondary_charts
from src.dispositor_graph import render_dispositor_section
from src.data_stubs import (
	community_save, community_list,
	community_get, community_load, community_delete,
)
from supabase_admin import is_admin
from supabase_profiles import (
	save_user_profile_db, load_user_profiles_db, delete_user_profile_db,
	save_user_profile_group_db, load_user_profile_groups_db,
	load_user_profiles_by_group_db, delete_user_profile_group_db,
	load_self_profile_db,
)
from beta_feedback import render_feedback_expander, render_admin_alert, render_admin_report_viewer
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_ROOT)
from house_selector_v2 import _selected_house_system
from donate_v2 import donate_chart
from now_v2 import render_now_widget
from event_lookup_v2 import update_events_html_state
from datetime import datetime
from profiles_v2 import (
    format_object_profile_html,
    ordered_objects,
)
from planet_profiles import (
    format_planet_profile_html,
    format_full_planet_profile_html,
)
import os, streamlit as st
import matplotlib.pyplot as plt
from interp_base_natal import NatalInterpreter
st.set_page_config(layout="wide")

# --- Auth gate: shows login UI and stops if user is not authenticated ---
from auth_ui import render_auth_gate
current_user_id = render_auth_gate()

# --- Auto-seed self-profile into chat memory (once per session) -----------
if not st.session_state.get("__self_seeded__"):
	_self_payload = load_self_profile_db(current_user_id)
	if _self_payload is not None:
		# Build a lightweight dict (name + relationship) for the chat agent
		_seed = {
			"name": _self_payload.get("name", "Me"),
			"relationship_to_querent": "self",
		}
		_persons = st.session_state.get("mcp_known_persons", [])
		# Only prepend if not already present
		if not any(p.get("relationship_to_querent") == "self" for p in _persons):
			_persons.insert(0, _seed)
			st.session_state["mcp_known_persons"] = _persons
	st.session_state["__self_seeded__"] = True

# --- Beta Feedback: Admin alert banner (shows only for admins with unread reports) ---
render_admin_alert()

# --- Beta Feedback: Report/Feedback form at top of app ---
render_feedback_expander(auth_page=False)

from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_chart, generate_combo_groups, edges_from_major_list
from wizard_v2 import render_guided_wizard
from src.mcp.chat_ui import render_chat_widget
from toggles_v2 import render_circuit_toggles
from drawing_v2 import RenderResult, render_chart, render_chart_with_shapes
from profile_manager_v2 import render_profile_manager, ensure_profile_session_defaults
from models_v2 import static_db

SIGNS = static_db.SIGNS
PLANETARY_RULERS = static_db.PLANETARY_RULERS
PLANETS_PLUS = static_db.PLANETS_PLUS
ASPECTS = static_db.ASPECTS
MAJOR_OBJECTS = static_db.MAJOR_OBJECTS
TOGGLE_ASPECTS = static_db.TOGGLE_ASPECTS
from calc_v2 import (
	calculate_chart, chart_sect_from_df, build_aspect_edges, 
	annotate_reception, build_dispositor_tables, 
	build_conjunction_clusters
)

result = st.session_state.get("render_result")
# Key initialization:
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
st.session_state.setdefault("birth_name", "")
st.session_state.setdefault("is_my_chart", False)
st.session_state.setdefault("birth_gender", None)
st.session_state.setdefault("birth_form_mode", "new")    # "new" | "edit"
st.session_state.setdefault("birth_form_open", True)
st.session_state.setdefault("editing_profile_name", None)
st.session_state.setdefault("editing_profile_data", {})
# (test_chart_2 selector removed; Chart 2 loaded via profile manager synastry slot)

# current_user_id is now set by render_auth_gate() at startup (the logged-in user's UUID)
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

# Apply UI CSS once we know the resolved light/dark mode
apply_custom_css(dark_mode=resolved_dark_mode)

# (scroll handler is now done via components.html at the scroll target site)

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

/* Distinct separator between full profile blocks */
.planet-profile-card {
  border-bottom: 2px solid rgba(255,255,255,0.35);
  padding-bottom: 12px;
  margin-bottom: 12px;
}
.planet-profile-card:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)

# --- Handle pending chart swap BEFORE any widgets are created ---
# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)
if st.session_state.get("__pending_swap_charts__"):
	swap_primary_and_secondary_charts()
	st.rerun()  # not in an on_click callback, so explicit rerun needed

# --- Handle pending Calculate (deferred so preset data is applied BEFORE widgets) ---
_pending_calc = st.session_state.pop("__pending_calculate__", None)
if _pending_calc:
	_syn              = _pending_calc["synastry"]
	_custom2_snapshot = _pending_calc.get("custom2_snapshot")

	# Chart 1 — always from current form / profile data
	run_chart(suffix="")

	# --- Auto-close the birth data form after any calculation ---
	st.session_state["birth_form_open"] = False

	# --- Profile update (Edit Chart flow) --- overwrite saved profile with new chart ---
	_update_prof_name = _pending_calc.get("update_profile_name")
	if _update_prof_name:
		_chart_obj = st.session_state.get("last_chart")
		if _chart_obj is not None:
			from src.mcp.comprehension_models import PersonProfile as _PP
			# Preserve existing metadata (relationship, gender, etc.) if available
			_orig_edit_data = st.session_state.pop("editing_profile_data", {}) or {}
			if _orig_edit_data:
				_upd_pp = _PP.from_dict(_orig_edit_data)
				_upd_pp.astro_chart = _chart_obj
				if _pending_calc.get("birth_gender"):
					_upd_pp.gender = _pending_calc["birth_gender"]
			else:
				_upd_pp = _PP(
					name=_update_prof_name,
					chart_id=_update_prof_name,
					relationship_to_querent="other",
					gender=_pending_calc.get("birth_gender"),
					significant_places=[_chart_obj.city] if _chart_obj.city else [],
					astro_chart=_chart_obj,
				)
			save_user_profile_db(current_user_id, _update_prof_name, _upd_pp.to_dict())
		# Reset edit mode
		st.session_state["birth_form_mode"] = "new"
		st.session_state["editing_profile_name"] = None
	if _pending_calc.get("is_my_chart"):
		_self_existing = load_self_profile_db(current_user_id)
		if _self_existing is None:
			_chart_obj = st.session_state.get("last_chart")
			if _chart_obj is not None:
				from src.mcp.comprehension_models import PersonProfile as _PP
				_self_name = (_pending_calc.get("birth_name") or "").strip() or "User"
				# Save a single profile with relationship_to_querent="self" —
				# no hidden duplicate needed; load_self_profile_db scans by that field.
				_self_pp = _PP(
					name=_self_name,
					chart_id=_self_name,
					relationship_to_querent="self",
					gender=_pending_calc.get("birth_gender"),
					significant_places=[_chart_obj.city] if _chart_obj.city else [],
					astro_chart=_chart_obj,
				)
				save_user_profile_db(current_user_id, _self_name, _self_pp.to_dict())

	# Chart 2 (synastry only) — only recalculate if no chart object loaded
	if _syn and st.session_state.get("last_chart_2") is None:
		if _custom2_snapshot:
			for _k, _v in _custom2_snapshot.items():
				st.session_state[_k] = _v
		run_chart(suffix="_2")



# --- Handle pending Chart 2 profile load (outer / synastry chart) ---
_pending_profile_2 = st.session_state.pop("__pending_profile_load_2__", None)
if _pending_profile_2:
	_prof_name_2 = _pending_profile_2["profile_name"]
	_prof_data_2 = _pending_profile_2["profile_data"]

	# Reconstruct PersonProfile (handles both old-format and new-format payloads)
	from src.mcp.comprehension_models import PersonProfile as _PP2
	_pp2 = _PP2.from_dict(_prof_data_2)
	_chart2 = _pp2.astro_chart

	if _chart2 is not None:
		_chart2.display_name = _prof_name_2
		st.session_state["last_chart_2"] = _chart2
		st.session_state["chart_2_source"] = "synastry"
		st.session_state["last_test_chart_2"] = _prof_name_2
		st.success(f"\u2705 Outer chart '{_prof_name_2}' loaded for Synastry.")
	else:
		# Old-format fallback: try raw chart dict or flat birth keys
		_stored_chart_raw_2 = _prof_data_2.get("chart")
		if isinstance(_stored_chart_raw_2, dict):
			from models_v2 import AstrologicalChart
			_stored_chart_2 = AstrologicalChart.from_json(_stored_chart_raw_2)
			_stored_chart_2.display_name = _prof_name_2
			st.session_state["last_chart_2"] = _stored_chart_2
			st.session_state["chart_2_source"] = "synastry"
			st.session_state["last_test_chart_2"] = _prof_name_2
			st.success(f"\u2705 Outer chart '{_prof_name_2}' loaded for Synastry.")
		elif any(v is None for v in (_prof_data_2.get("lat"), _prof_data_2.get("lon"), _prof_data_2.get("tz_name"))):
			st.error(f"Profile '{_prof_name_2}' is missing location/timezone data. Re-save it after a city lookup.")
		else:
			for _k2, _v2 in [
				("year_2", _prof_data_2["year"]),
				("month_name_2", MONTH_NAMES[_prof_data_2["month"] - 1]),
				("day_2", _prof_data_2["day"]),
				("city_2", _prof_data_2["city"]),
				("current_lat_2", _prof_data_2.get("lat")),
				("current_lon_2", _prof_data_2.get("lon")),
				("current_tz_name_2", _prof_data_2.get("tz_name")),
			]:
				st.session_state[_k2] = _v2
			_h24_2 = _prof_data_2["hour"]
			_h12_2 = _h24_2 % 12 or 12
			_ampm_2 = "AM" if _h24_2 < 12 else "PM"
			st.session_state["hour_12_2"] = f"{_h12_2:02d}"
			st.session_state["minute_str_2"] = f"{_prof_data_2['minute']:02d}"
			st.session_state["ampm_2"] = _ampm_2
			st.session_state["chart_2_source"] = "synastry"
			if run_chart(suffix="_2"):
				if st.session_state.get("last_chart_2"):
					st.session_state["last_chart_2"].display_name = _prof_name_2
				st.success(f"\u2705 Outer chart '{_prof_name_2}' calculated for Synastry.")
			else:
				st.error(f"Failed to calculate outer chart for '{_prof_name_2}'.")

# ── Shared helper: apply profile data to session state ───────────────────────────────
def _birth_data_from_chart(chart):
	"""Parse local-time birth data from chart's display_datetime / fields."""
	import datetime as _dt
	dt = chart.display_datetime
	if dt is None and chart.chart_datetime:
		try:
			dt = _dt.datetime.fromisoformat(chart.chart_datetime)
		except (ValueError, TypeError):
			dt = None
	if dt:
		return dt.year, dt.month, dt.day, dt.hour, dt.minute, chart.city or ""
	return None, None, None, None, None, chart.city or ""

def _apply_profile_to_session(prof_name, prof_data):
	"""Populate all form/session keys from a profile dict. Used by load and edit flows."""
	from src.mcp.comprehension_models import PersonProfile as _PP
	_pp = _PP.from_dict(prof_data)
	_loaded_chart = _pp.astro_chart

	if _loaded_chart is not None:
		_loaded_chart.display_name = prof_name
		_yr, _mo, _dy, _hr24, _mn, _ct = _birth_data_from_chart(_loaded_chart)

		# Set profile-bound keys
		if _yr is not None:
			st.session_state["profile_year"] = _yr
			st.session_state["profile_month_name"] = MONTH_NAMES[_mo - 1]
			st.session_state["profile_day"] = _dy
			st.session_state["profile_hour"] = _hr24
			st.session_state["profile_minute"] = _mn
			st.session_state["profile_city"] = _ct

			# Set form-widget-bound keys
			st.session_state["year"] = _yr
			st.session_state["month_name"] = MONTH_NAMES[_mo - 1]
			st.session_state["day"] = _dy
			st.session_state["city"] = _ct
			_load_h12 = _hr24 % 12 or 12
			_load_ampm = "AM" if _hr24 < 12 else "PM"
			st.session_state["hour_12"]    = f"{_load_h12:02d}"
			st.session_state["minute_str"] = f"{_mn:02d}"
			st.session_state["ampm"]       = _load_ampm

			st.session_state["hour_val"] = _hr24
			st.session_state["minute_val"] = _mn
			st.session_state["city_input"] = _ct

		# Restore unknown time flag + time slots
		_chart_unknown_time = bool(getattr(_loaded_chart, "unknown_time", False))
		st.session_state["profile_unknown_time"] = _chart_unknown_time
		if _chart_unknown_time:
			st.session_state["hour_12"]    = "--"
			st.session_state["minute_str"] = "--"
			st.session_state["ampm"]       = "--"

		# Geocode from chart
		st.session_state["current_lat"]     = _loaded_chart.latitude
		st.session_state["current_lon"]     = _loaded_chart.longitude
		st.session_state["current_tz_name"] = _loaded_chart.timezone

		st.session_state["last_location"] = _loaded_chart.city or ""
		st.session_state["last_timezone"] = _loaded_chart.timezone

		# Restore name, gender, and self-flag
		st.session_state["birth_name"]  = _pp.name or prof_name
		st.session_state["birth_gender"] = _pp.gender  # None if not stored
		st.session_state["is_my_chart"] = (_pp.relationship_to_querent == "self")

		# Restore circuit names from chart object
		_circuit_names = getattr(_loaded_chart, "circuit_names", None) or {}
		if _circuit_names:
			for key, val in _circuit_names.items():
				st.session_state[key] = val
			st.session_state["saved_circuit_names"] = _circuit_names.copy()
		else:
			st.session_state["saved_circuit_names"] = {}

		st.session_state["last_chart"] = _loaded_chart
		st.session_state["chart_ready"] = True
		return True  # new-format success
	else:
		# ── Old-format fallback ───────────────────────────────────────
		# Set profile-bound keys (not widget-bound)
		st.session_state["profile_year"] = prof_data["year"]
		st.session_state["profile_month_name"] = MONTH_NAMES[prof_data["month"] - 1]
		st.session_state["profile_day"] = prof_data["day"]
		st.session_state["profile_hour"] = prof_data["hour"]
		st.session_state["profile_minute"] = prof_data["minute"]
		st.session_state["profile_city"] = prof_data["city"]

		# Set form-widget-bound keys
		st.session_state["year"] = prof_data["year"]
		st.session_state["month_name"] = MONTH_NAMES[prof_data["month"] - 1]
		st.session_state["day"] = prof_data["day"]
		st.session_state["city"] = prof_data["city"]
		_load_h24 = prof_data["hour"]
		_load_h12 = _load_h24 % 12 or 12
		_load_ampm = "AM" if _load_h24 < 12 else "PM"
		st.session_state["hour_12"]    = f"{_load_h12:02d}"
		st.session_state["minute_str"] = f"{prof_data['minute']:02d}"
		st.session_state["ampm"]       = _load_ampm

		st.session_state["current_lat"]     = prof_data.get("lat")
		st.session_state["current_lon"]     = prof_data.get("lon")
		st.session_state["current_tz_name"] = prof_data.get("tz_name")

		st.session_state["hour_val"] = prof_data["hour"]
		st.session_state["minute_val"] = prof_data["minute"]
		st.session_state["city_input"] = prof_data["city"]

		st.session_state["last_location"] = prof_data["city"]
		st.session_state["last_timezone"] = prof_data.get("tz_name")

		# Restore name, gender, unknown-time, and self-flag (old format)
		st.session_state["birth_name"] = prof_data.get("name") or prof_name
		st.session_state["birth_gender"] = prof_data.get("gender")  # None if not stored
		_unk = bool(prof_data.get("unknown_time", False))
		st.session_state["profile_unknown_time"] = _unk
		if _unk:
			st.session_state["hour_12"]    = "--"
			st.session_state["minute_str"] = "--"
			st.session_state["ampm"]       = "--"
		st.session_state["is_my_chart"] = (prof_data.get("relationship_to_querent") == "self")

		# Restore circuit names (old format: top-level key)
		if "circuit_names" in prof_data:
			for key, val in prof_data["circuit_names"].items():
				st.session_state[key] = val
			st.session_state["saved_circuit_names"] = prof_data["circuit_names"].copy()
		else:
			st.session_state["saved_circuit_names"] = {}

		# Try loading chart from old-format raw dict
		_stored_chart_raw = prof_data.get("chart")
		if isinstance(_stored_chart_raw, dict):
			from models_v2 import AstrologicalChart
			_stored_chart = AstrologicalChart.from_json(_stored_chart_raw)
			_stored_chart.display_name = prof_name
			st.session_state["last_chart"] = _stored_chart
			st.session_state["chart_ready"] = True
		elif any(v is None for v in (prof_data.get("lat"), prof_data.get("lon"), prof_data.get("tz_name"))):
			st.session_state["__profile_load_error__"] = f"Profile '{prof_name}' is missing location/timezone info. Re-save it after a successful city lookup."
		# else: will recalculate when run_chart() is called
		return False  # old-format path

# --- Handle pending Edit Chart (pre-fills form and switches to edit mode) ---
_pending_edit = st.session_state.pop("__pending_edit_chart__", None)
if _pending_edit:
	_edit_name = _pending_edit["profile_name"]
	_edit_data = _pending_edit["profile_data"]

	st.session_state["_loaded_profile"] = _edit_data
	st.session_state["current_profile"] = _edit_name
	st.session_state["profile_loaded"] = True

	_apply_profile_to_session(_edit_name, _edit_data)

	# Switch form to edit mode; store original data to preserve metadata on save
	st.session_state["birth_form_mode"] = "edit"
	st.session_state["editing_profile_name"] = _edit_name
	st.session_state["editing_profile_data"] = _edit_data
	st.session_state["birth_form_open"] = True

# --- Handle pending profile load (deferred until before form widgets are created) ---
_pending_profile = st.session_state.pop("__pending_profile_load__", None)
if _pending_profile:
	_prof_name = _pending_profile["profile_name"]
	_prof_data = _pending_profile["profile_data"]
	
	st.session_state["_loaded_profile"] = _prof_data
	st.session_state["current_profile"] = _prof_name
	st.session_state["profile_loaded"] = True

	_apply_profile_to_session(_prof_name, _prof_data)

# Track the most recent chart figure so the wheel column can always render.
st.session_state.setdefault("render_fig", None)

col_left, col_mid, col_right = st.columns([3, 2, 3])
# -------------------------
# Left column: Birth Data (FORM)
# -------------------------
with col_left:
	_form_title = "✏️ Edit Birth Data" if st.session_state.get("birth_form_mode") == "edit" else "📆 Enter Birth Data"
	with st.expander(_form_title, expanded=st.session_state.get("birth_form_open", True)):
		# --- Unknown Time (live) OUTSIDE the form ---
		st.session_state.setdefault("profile_unknown_time", False)
		st.session_state.setdefault("hour_12", "12")
		st.session_state.setdefault("minute_str", "00")
		st.session_state.setdefault("ampm", "AM")

		st.markdown('<p style="color:#cc0000; font-size:0.78em; margin-bottom:2px;">* required fields</p>', unsafe_allow_html=True)

		def _apply_unknown_time():
			if st.session_state.get("profile_unknown_time", False):
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

		# Optional gender selector
		st.radio(
			"Gender (optional):",
			["Female", "Male", "Non-binary"],
			key="birth_gender",
			horizontal=True,
			index=None,
		)

		# Only show "This is my chart" if no self-profile saved yet
		if load_self_profile_db(current_user_id) is None:
			st.checkbox(
				"This is my chart",
				key="is_my_chart",
			)
		
		with st.form("birth_form", clear_on_submit=False):
			# --- Two columns: Date/Day (left) and City (right) ---
			col1, col2 = st.columns([3, 2])

			# Left: Date & Day
			with col1:
				st.text_input("Name :red[*]", key="birth_name")

				year = st.number_input(
					"Year :red[*]",
					min_value=1000,
					max_value=3000,
					step=1,
					key="year",
				)

				import calendar
				month_name = st.selectbox(
					"Month :red[*]",
					MONTH_NAMES,
					key="month_name",
				)
				month = MONTH_NAMES.index(month_name) + 1
				days_in_month = calendar.monthrange(year, month)[1]

				day = st.selectbox(
					"Day :red[*]",
					list(range(1, days_in_month + 1)),
					key="day",
				)

			# Right: City of Birth (restored)
			with col2:
				st.text_input("City of Birth :red[*]", key="city")

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

			_is_edit_mode = st.session_state.get("birth_form_mode") == "edit"
			_submit_label = "Update Chart" if _is_edit_mode else "Calculate Chart"
			submitted = st.form_submit_button(_submit_label)

			if submitted:
				# Defer the actual calculation to the NEXT rerun so that
				# preset data can be written to session state BEFORE the
				# form widgets are instantiated (Streamlit forbids writing
				# to a widget-bound key after the widget exists).
				_syn = st.session_state.get("synastry_mode", False)

				# Snapshot form values for Chart 2 position (only needed when
				# synastry is on and no Chart 2 profile has been loaded yet).
				_custom2_snap = None
				if _syn and st.session_state.get("last_chart_2") is None:
					_custom2_snap = {}
					for _key in ["year", "month_name", "day", "hour_12",
								 "minute_str", "ampm", "city"]:
						_custom2_snap[f"{_key}_2"] = st.session_state.get(_key)
					_custom2_snap["profile_unknown_time_2"] = st.session_state.get(
						"profile_unknown_time", False
					)

				st.session_state["__pending_calculate__"] = {
					"synastry": _syn,
					"custom2_snapshot": _custom2_snap,
					"is_my_chart": st.session_state.get("is_my_chart", False),
					"birth_name": st.session_state.get("birth_name", ""),
					"birth_gender": st.session_state.get("birth_gender"),
					"update_profile_name": st.session_state.get("editing_profile_name") if _is_edit_mode else None,
				}
				st.rerun()


chart_cached = st.session_state.get("last_chart")
df_cached     = chart_cached.to_dataframe() if chart_cached is not None else None# --- Quick city UI state defaults & safe-clear ---
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
	st.write("Enter birth data on the left to calculate a chart. Use the Chart Manager on the right to save/load charts.") 
	st.write("Once a chart is calculated, scroll down to ask the chat your astrology questions.")


with col_right:
	# Make sure the session keys exist before rendering any widgets in this panel
	ensure_profile_session_defaults(MONTH_NAMES)
	with st.expander("📂 Chart Manager"):
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
			# Group management functions
			save_user_profile_group_db=save_user_profile_group_db,
			load_user_profile_groups_db=load_user_profile_groups_db,
			load_user_profiles_by_group_db=load_user_profiles_by_group_db,
			delete_user_profile_group_db=delete_user_profile_group_db,
		)

	if chart_cached is not None:
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
# the chart_core version of run_chart stores circuit data under
# plain keys ("patterns", "shapes", "singleton_map") with an
# optional suffix of "_2" for the second wheel when synastry mode
# is active.  derive that suffix here rather than reaching for
# "last_df" which belonged to the old DataFrame-centric API.
synastry_mode = st.session_state.get("synastry_mode", False)
chart_mode = st.session_state.get("chart_mode", "Circuits")
# Read circuit_submode from the radio widget key first — Streamlit sets widget
# keys before the script runs, so this is always current even on the very first
# rerun after the user clicks a new submode.  The derived "circuit_submode" key
# is only written inside render_circuit_toggles (which hasn't run yet at this
# point), so it would be one rerun stale without this workaround.
circuit_submode = (
	st.session_state.get("__circuit_submode_radio")
	or st.session_state.get("circuit_submode", "Combined Circuits")
)

# Ensure transit chart (Chart 2) is always populated when transit mode is on.
# Recalculate if chart_2 is missing or holds stale synastry data (not transit).
_transit_mode = st.session_state.get("transit_mode", False)
_chart2_is_transit = st.session_state.get("chart_2_source") == "transit"
if _transit_mode and (st.session_state.get("last_chart_2") is None or not _chart2_is_transit):
	from src.chart_core import run_transit_chart
	run_transit_chart()

# When transit (or synastry) mode activates from a single-chart run, circuit_submode
# is still "single" — force it to Combined Circuits before the patterns branch below.
if (synastry_mode or _transit_mode) and circuit_submode == "single":
	st.session_state["circuit_submode"] = "Combined Circuits"
	circuit_submode = "Combined Circuits"
_chart_1 = st.session_state.get("last_chart")
_chart_2 = st.session_state.get("last_chart_2")
if (synastry_mode or _transit_mode) and chart_mode == "Circuits" and circuit_submode == "Combined Circuits":
	# Compute combined data eagerly so it is available on the FIRST rerun
	# (previously it only existed after _refresh_chart_figure ran, which is too late).
	from src.chart_core import _positions_from_chart
	from patterns_v2 import connected_components_from_edges, detect_shapes as _detect_shapes
	if _chart_1 is not None and _chart_2 is not None:
		_pos_inner = _positions_from_chart(_chart_1)
		_pos_outer = _positions_from_chart(_chart_2)
		_pos_comb = dict(_pos_inner)
		for _n, _d in _pos_outer.items():
			_pos_comb[f"{_n}_2"] = _d
		_comb_edges = []
		_bodies = list(_pos_comb.keys())
		for _i in range(len(_bodies)):
			for _j in range(_i + 1, len(_bodies)):
				_p1, _p2 = _bodies[_i], _bodies[_j]
				_ang = abs(_pos_comb[_p1] - _pos_comb[_p2]) % 360
				if _ang > 180:
					_ang = 360 - _ang
				for _aname, _adata in ASPECTS.items():
					if abs(_ang - _adata["angle"]) <= _adata["orb"]:
						_comb_edges.append(((_p1, _p2), _aname))
						break
		patterns = connected_components_from_edges(_bodies, _comb_edges)
		shapes = _detect_shapes(_pos_comb, patterns, _comb_edges)
		_conn_objs = set()
		for (_p1, _p2), _ in _comb_edges:
			_conn_objs.add(_p1)
			_conn_objs.add(_p2)
		singleton_map = {n: {"deg": d} for n, d in _pos_comb.items() if n not in _conn_objs}
		# Persist so _refresh_chart_figure and toggles stay in sync
		st.session_state["patterns_combined"] = patterns
		st.session_state["shapes_combined"] = shapes
		st.session_state["singleton_map_combined"] = singleton_map
		st.session_state["pos_combined"] = _pos_comb
		st.session_state["combined_edges_formatted"] = _comb_edges
	else:
		patterns = st.session_state.get("patterns_combined", []) or []
		shapes = st.session_state.get("shapes_combined", []) or []
		singleton_map = st.session_state.get("singleton_map_combined", {}) or {}
else:
	# Connected Circuits (synastry) and single-chart mode both use Chart 1 data.
	# Chart 1 is always stored without a suffix. Never use _2 here — the Chart 2
	# connection data is surfaced separately inside the circuit expanders.
	patterns = (_chart_1.aspect_groups if _chart_1 else []) or []
	shapes = (_chart_1.shapes if _chart_1 else []) or []
	singleton_map = (_chart_1.singleton_map if _chart_1 else {}) or {}

# --- Bottom-of-page popovers ---
chart_cached = st.session_state.get("last_chart")
# compute a DataFrame only when we need to display it later
if chart_cached is not None:
	df_cached = chart_cached.to_dataframe()
else:
	df_cached = None
aspect_cached = chart_cached.aspect_df if chart_cached else None
sect_cached   = chart_cached.sect if chart_cached else None
sect_err      = chart_cached.sect_error if chart_cached else None

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
# now base the test on the chart object rather than the derived DataFrame
if chart_cached is not None:
	# ---------- Toggles (moved to toggles_v2) ----------
	# Reuse cached profiles from profile manager (avoids redundant DB call)
	# Safety check: ensure patterns, shapes, singleton_map exist
	patterns = patterns or []
	shapes = shapes or []
	singleton_map = singleton_map or {}
	
	toggles, pattern_labels, saved_profiles, chart_mode, aspect_toggles, circuit_submode = render_circuit_toggles(
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

	rr = _refresh_chart_figure()
	if rr is not None and rr.fig is not None:
		st.pyplot(rr.fig, clear_figure=True)
		plt.close(rr.fig)

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

	# ── AI Chat widget ──────────────────────────────────────────────────
	render_chat_widget()
		
	# --- Dispositor Graph (moved from popover) ---
	render_dispositor_section(st, chart_cached)

	st.subheader("🤓 Nerdy Chart Specs 📋")
	unknown_time_chart = bool(
		(chart_cached.unknown_time if chart_cached else False)
		or st.session_state.get("profile_unknown_time")
	)

	with st.popover("Objects", use_container_width=True):
		st.subheader("Calculated Chart")
		# show underlying DataFrame for debugging/transition
		if df_cached is not None:
			st.dataframe(df_cached, use_container_width=True)

	with st.popover("Conjunctions", use_container_width=True):
		st.subheader("Conjunction Clusters")
		st.dataframe((chart_cached.conj_clusters_rows if chart_cached else []) or [], use_container_width=True)

	with st.popover("Aspects Graph", use_container_width=True):
		if aspect_cached is not None:
			st.subheader("Aspect Graph")
			st.dataframe(aspect_cached, use_container_width=True)
		else:
			st.caption("No aspect table available yet.")

	with st.popover("Aspects List", use_container_width=True):
		st.subheader("Aspect Lists")
		edges_major = chart_cached.edges_major if chart_cached else []
		edges_minor = chart_cached.edges_minor if chart_cached else []
		chart_cached = st.session_state.get("last_chart")
		# Use the new clustered aspect edge builder
		from calc_v2 import build_clustered_aspect_edges
		if chart_cached is not None:
			clustered_edges = build_clustered_aspect_edges(chart_cached, edges_major)
			# For debugging, show both the cluster names and the original A/B
			rows = []
			for a, b, meta in clustered_edges:
				row = {"Kind": "Major", "Cluster A": a, "Cluster B": b, **meta}
				rows.append(row)
			for a, b, meta in edges_minor:
				row = {"Kind": "Minor", "A": a, "B": b, **meta}
				st.dataframe(rows, use_container_width=True)
		else:
			st.caption("No aspect data available.")

# --- Left sidebar: Planet Profiles ---
with st.sidebar:
	st.subheader("🪐 Planet Profiles in View")

	# Choose rendering mode for the profile cards
	interactive_chart = st.session_state.get("interactive_chart", False)

	# Create the radio widget (let it manage its own state via the key)
	profile_mode = st.radio(
		"Profile view",
		["Stats", "Profile", "Full"],
		index=["Stats", "Profile", "Full"].index(
			st.session_state.get("profile_view_mode", "Stats")
		),
		key="profile_view_mode",
		horizontal=True,
	)

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
	if chart_cached is not None:
		# Track which planet was just clicked for scrolling
		if st.session_state.get("interactive_chart", False):
			chart_click_event = st.session_state.get("chart_click_event")
			if chart_click_event:
				if chart_click_event.get("type") == "click" and chart_click_event.get("element_type") == "object":
					target_planet = chart_click_event.get("element")
					if target_planet:
						st.session_state["_scroll_to_planet"] = target_planet
		
		# Get visible_objects from render_result, with fallback to session state
		rr = st.session_state.get("render_result")
		visible_objects = (rr.visible_objects if rr and hasattr(rr, "visible_objects") else None) or st.session_state.get("visible_objects", [])
		edges_major = chart_cached.edges_major if chart_cached else []
		unknown_time_chart = bool(
			(chart_cached.unknown_time if chart_cached else False)
			or st.session_state.get("profile_unknown_time")
		)

		# --- Sidebar HTML cache ---
		# Build a cache key from everything that affects the sidebar output.
		# If nothing changed, skip all the expensive profile formatting.
		_house_sys = _selected_house_system()
		_sidebar_cache_key = (
			chart_cached.chart_datetime, chart_cached.latitude, chart_cached.longitude,
			tuple(sorted(visible_objects)) if visible_objects else (),
			profile_mode,
			_house_sys,
			unknown_time_chart,
		)
		_prev_sidebar = st.session_state.get("_sidebar_cache", {})

		if _prev_sidebar.get("key") == _sidebar_cache_key:
			# Cache hit — reuse pre-built HTML
			html_content = _prev_sidebar["html"]
		else:
			# Cache miss — rebuild
			ordered_rows = ordered_objects(
				chart_cached,
				visible_objects=visible_objects,
				edges_major=edges_major,
			)
			if ordered_rows:
				if profile_mode == "Stats":
					formatter = lambda r: format_object_profile_html(
						r,
						house_label=_house_sys,
						include_house_data=not unknown_time_chart,
					)
				elif profile_mode == "Profile":
					formatter = lambda r: format_planet_profile_html(
						r,
						chart_cached,
						ordered_rows,
						house_system=_house_sys,
					)
				else:  # Full
					formatter = lambda r: format_full_planet_profile_html(
						r,
						chart_cached,
						ordered_rows,
						house_system=_house_sys,
						include_house_data=not unknown_time_chart,
					)

				try:
					blocks = []
					for i, r in enumerate(ordered_rows):
						try:
							block = formatter(r)
							planet_name = r.object_name.name if hasattr(r, 'object_name') and r.object_name else "unknown"
							planet_id = f"rosetta-planet-{planet_name.replace(' ', '-').lower()}"
							wrapped_block = f"<div id='{planet_id}' class='planet-profile-card'>{block}</div>"
							blocks.append(wrapped_block)
						except Exception as e:
							st.error(f"Error formatting {r.object_name.name if hasattr(r, 'object_name') else 'unknown'}: {e}")
							import traceback
							traceback.print_exc()

					html_content = "<div class='pf-root'>" + "\n".join(blocks) + "</div>"
				except Exception as e:
					st.error(f"Error rendering profiles: {e}")
					import traceback
					traceback.print_exc()
					html_content = ""
			else:
				html_content = ""

			# Store in cache
			st.session_state["_sidebar_cache"] = {
				"key": _sidebar_cache_key,
				"html": html_content,
			}

		# Render the HTML (cached or freshly built)
		if html_content:
			st.markdown(html_content, unsafe_allow_html=True)
		else:
			st.caption("No objects currently visible with the selected toggles.")

		# Check if we need to scroll to a specific planet (interactive chart)
		target_planet = st.session_state.get("_scroll_to_planet")
		if target_planet and st.session_state.get("interactive_chart", False):
			planet_id = f"rosetta-planet-{target_planet.replace(' ', '-').lower()}"
			components.html(f"""
			<script>
			(function() {{
				const el = window.parent.document.getElementById('{planet_id}');
				if (!el) return;
				let best = null, bestRange = 0, p = el.parentElement;
				while (p) {{
					const r = p.scrollHeight - p.clientHeight;
					if (r > bestRange) {{ bestRange = r; best = p; }}
					p = p.parentElement;
				}}
				if (best && bestRange > 0) {{
					const elRect = el.getBoundingClientRect();
					const containerRect = best.getBoundingClientRect();
					best.scrollTop += elRect.top - containerRect.top;
				}}
				el.style.transition = 'background-color 0.4s ease';
				el.style.backgroundColor = 'rgba(100, 200, 255, 0.35)';
				setTimeout(() => {{ el.style.backgroundColor = ''; }}, 1500);
			}})();
			</script>
			""", height=0)
			st.session_state["_scroll_to_planet"] = None
	else:
		st.caption("Calculate a chart to see profiles.")

# ---------------------------------------------------------------------------
# Admin Report Viewer (at very bottom of page)
# ---------------------------------------------------------------------------
render_admin_report_viewer()
