import streamlit as st
import pandas as pd
import patterns_v2 as _patterns_mod
from typing import Any, Mapping, Collection
import logging


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

def _resolve_visible_from_patterns(toggle_state: Any, chart=None) -> set[str] | None:
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
				result = func(toggle_state, chart=chart)
			except TypeError:
				try:
					result = func(toggle_state)
				except TypeError:
					continue
			if result:
				return set(result)
	return None


def resolve_visible_objects(toggle_state: Any = None, chart=None) -> set[str] | None:
	# Debugging: Log inputs and output of resolve_visible_objects
	print(f"resolve_visible_objects called with toggle_state: {toggle_state}, chart: {chart}")
	via_patterns = _resolve_visible_from_patterns(toggle_state, chart)
	if via_patterns:
		print(f"resolve_visible_objects returning via_patterns: {via_patterns}")
		return via_patterns
	if toggle_state is None:
		print("resolve_visible_objects returning None (toggle_state is None)")
		return None
	if isinstance(toggle_state, Mapping):
		names = {str(name) for name, enabled in toggle_state.items() if enabled}
		print(f"resolve_visible_objects returning names from Mapping: {names}")
		return names or None
	if isinstance(toggle_state, Collection) and not isinstance(toggle_state, (str, bytes)):
		result = {str(name) for name in toggle_state}
		print(f"resolve_visible_objects returning names from Collection: {result}")
		return result


