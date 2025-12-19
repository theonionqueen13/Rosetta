import streamlit as st
import pandas as pd
import patterns_v2 as _patterns_mod
from typing import Any, Mapping, Collection


def _selected_house_system():
	s = st.session_state.get("house_system_main", "Equal")
	return s.lower().replace(" sign", "")


def _current_chart_header_lines():
	name = (
		st.session_state.get("current_profile_title")
		or st.session_state.get("current_profile")
		or "Untitled Chart"
	)
	if isinstance(name, str) and name.startswith("community:"):
		name = "Community Chart"

	month  = st.session_state.get("profile_month_name", "")
	day    = st.session_state.get("profile_day", "")
	year   = st.session_state.get("profile_year", "")
	hour   = st.session_state.get("profile_hour")
	minute = st.session_state.get("profile_minute")
	city   = st.session_state.get("profile_city", "")
	unknown_time = bool(
		st.session_state.get("chart_unknown_time")
		or st.session_state.get("profile_unknown_time")
	)

	date_line = f"{month} {day}, {year}".strip()

	if unknown_time:
		# Desired render order:
		# Line 1: AC = Aries 0° (default)
		# Line 2: date_line
		# Line 3: 12:00 PM
		extra_line = ""
		date_line  = "AC = Aries 0° (default)"
		time_line  = f"{month} {day}, {year}".strip()
		city       = "12:00 PM"
	else:
		extra_line = ""
		time_line = ""
		if hour is not None and minute is not None:
			h = int(hour)
			m = int(minute)
			ampm = "AM" if h < 12 else "PM"
			h12 = 12 if (h % 12 == 0) else (h % 12)
			time_line = f"{h12}:{m:02d} {ampm}"

	return name, date_line, time_line, city, extra_line


def _get_profile_lat_lon() -> tuple[float | None, float | None]:
	"""Pull chart/birth lat/lon from session_state."""
	SS = st.session_state

	def f(x):
		try:
			return float(x)
		except Exception:
			return None

	# Highest priority: current chart lookup (city geocode)
	lat = f(SS.get("chart_lat"))
	lon = f(SS.get("chart_lon"))

	# If not present, fall back to stored birth coords
	if lat is None or lon is None:
		lat = f(SS.get("birth_lat"))
		lon = f(SS.get("birth_lon"))

	# If still missing, report unknown
	if lat is None or lon is None:
		return None, None
	return lat, lon

def reset_chart_state():
	"""Clear transient UI keys so each chart loads cleanly."""
	for key in list(st.session_state.keys()):
		if key.startswith("toggle_pattern_"):
			del st.session_state[key]
		if key.startswith("shape_"):
			del st.session_state[key]
		if key.startswith("singleton_"):
			del st.session_state[key]
	st.session_state.pop("shape_toggles_by_parent", None)

def _resolve_visible_from_patterns(toggle_state: Any, df: pd.DataFrame | None) -> set[str] | None:
	if _patterns_mod is None:
		return None
	candidate_funcs = (
		"resolve_visible_objects",
		"visible_objects_from_toggles",
		"visible_object_names",
		"get_visible_objects",
	)
	for func_name in candidate_funcs:
		func = getattr(_patterns_mod, func_name, None)
		if callable(func):
			try:
				result = func(toggle_state, df=df)
			except TypeError:
				try:
					result = func(toggle_state)
				except TypeError:
					continue
			if result:
				return set(result)
	return None


def resolve_visible_objects(toggle_state: Any = None, df: pd.DataFrame | None = None) -> set[str] | None:
	print("[DEBUG] resolve_visible_objects called with toggle_state:", toggle_state)
	via_patterns = _resolve_visible_from_patterns(toggle_state, df)
	if via_patterns:
		return via_patterns
	if toggle_state is None:
		return None
	compass_points = {"AC", "DC", "MC", "IC", "Ascendant", "Descendant", "Midheaven", "Imum Coeli"}
	compass_rose_on = False
	# Check for Compass Rose toggle in Mapping
	if isinstance(toggle_state, Mapping):
		names = {str(name) for name, enabled in toggle_state.items() if enabled}
		# Try to detect Compass Rose toggle
		if "Compass Rose" in toggle_state and toggle_state["Compass Rose"]:
			compass_rose_on = True
		if compass_rose_on:
			names.update(compass_points)
			print("[DEBUG] Compass Rose ON - visible_names:", names)
		return names or None
	if isinstance(toggle_state, Collection) and not isinstance(toggle_state, (str, bytes)):
		names = {str(name) for name in toggle_state}
		# Try to detect Compass Rose toggle
		if "Compass Rose" in names:
			compass_rose_on = True
		if compass_rose_on:
			names.update(compass_points)
			print("[DEBUG] Compass Rose ON - visible_names:", names)
		return names
	return None