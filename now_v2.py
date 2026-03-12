# now_v2.py

import os
import datetime as dt
import pytz
import streamlit as st
from dateutil.relativedelta import relativedelta


# --- Moon icons directory (relative to this file) ---
MOON_PNG_DIR = os.path.join(os.path.dirname(__file__), "pngs")
COMPASS_KEY = "ui_compass_overlay"

# ---------------------------------------------------------------------------
# Now-mode Date Navigation
# ---------------------------------------------------------------------------

_NOW_DATE_INTERVALS = {
	"1 day":    dt.timedelta(days=1),
	"1 week":   dt.timedelta(weeks=1),
	"1 month":  None,   # handled via relativedelta
	"1 year":   None,   # handled via relativedelta
	"1 decade": None,   # handled via relativedelta
}


def _inject_now_chart_inputs(utc_dt: dt.datetime) -> None:
	"""
	Convert a UTC datetime to the user's local timezone and store it in
	``_now_chart_inputs`` so that run_chart() reads the navigator date
	instead of the birth-data form fields.
	"""
	city = (
		st.session_state.get("profile_city")
		or st.session_state.get("city")
		or ""
	).strip()
	tz_name = st.session_state.get("current_tz_name", "UTC")
	try:
		tz = pytz.timezone(tz_name)
		local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(tz)
	except Exception:
		local_dt = utc_dt

	h = local_dt.hour
	ampm = "PM" if h >= 12 else "AM"
	h12 = h % 12 or 12
	st.session_state["_now_chart_inputs"] = {
		"year":             local_dt.year,
		"month_name":       local_dt.strftime("%B"),
		"day":              local_dt.day,
		"hour_12":          f"{h12:02d}",
		"minute_str":       f"{local_dt.minute:02d}",
		"ampm":             ampm,
		"city":             city,
		"house_system":     st.session_state.get("house_system", "placidus"),
		"unknown_time_flag": False,
	}


def _apply_now_date_offset(direction: int) -> None:
	"""Shift now_chart_dt_utc forward (+1) or backward (-1) by the selected interval."""
	from src.chart_core import run_chart as _run_chart

	current = st.session_state.get("now_chart_dt_utc")
	if current is None:
		current = dt.datetime.utcnow()

	interval_label = st.session_state.get("now_date_nav_interval", "1 day")

	if interval_label == "1 day":
		new_dt = current + dt.timedelta(days=direction)
	elif interval_label == "1 week":
		new_dt = current + dt.timedelta(weeks=direction)
	elif interval_label == "1 month":
		new_dt = current + relativedelta(months=direction)
	elif interval_label == "1 year":
		new_dt = current + relativedelta(years=direction)
	elif interval_label == "1 decade":
		new_dt = current + relativedelta(years=10 * direction)
	else:
		new_dt = current + dt.timedelta(days=direction)

	st.session_state["now_chart_dt_utc"] = new_dt
	_inject_now_chart_inputs(new_dt)
	_run_chart()


def _set_now_date_to_current() -> None:
	"""Reset now_chart_dt_utc to the current moment and recalculate."""
	from src.chart_core import run_chart as _run_chart

	now_utc = dt.datetime.utcnow()
	st.session_state["now_chart_dt_utc"] = now_utc
	_inject_now_chart_inputs(now_utc)
	_run_chart()


def _apply_direct_now_date() -> None:
	"""Apply the direct date/time inputs from the expander and recalculate.

	The user enters date/time in the location's local timezone; convert to UTC
	before storing.
	"""
	from src.chart_core import run_chart as _run_chart

	d = st.session_state.get("now_direct_date")
	t = st.session_state.get("now_direct_time", dt.time(12, 0))
	if d is not None:
		tz_name = st.session_state.get("current_tz_name", "UTC")
		try:
			tz = pytz.timezone(tz_name)
			local_naive = dt.datetime.combine(d, t)
			utc_dt = tz.localize(local_naive).astimezone(pytz.utc).replace(tzinfo=None)
		except Exception:
			utc_dt = dt.datetime.combine(d, t)
		st.session_state["now_chart_dt_utc"] = utc_dt
		_inject_now_chart_inputs(utc_dt)
		_run_chart()


def render_now_date_nav() -> None:
	"""
	Render the single-chart date navigator (mirrors the transit date navigator
	but controls Chart 1 rather than the transit/Chart 2 overlay).
	Only call this when now_mode_active is True and transit/synastry are off.
	"""
	if st.session_state.get("now_chart_dt_utc") is None:
		st.session_state["now_chart_dt_utc"] = dt.datetime.utcnow()

	now_dt_utc = st.session_state["now_chart_dt_utc"]

	# Convert UTC → local timezone for display and input pre-population
	tz_name = st.session_state.get("current_tz_name", "UTC")
	try:
		tz = pytz.timezone(tz_name)
		now_dt = now_dt_utc.replace(tzinfo=pytz.utc).astimezone(tz)
		tz_abbr = now_dt.strftime("%Z")
	except Exception:
		now_dt = now_dt_utc
		tz_abbr = "UTC"

	# Display the current chart datetime (local)
	st.caption(f"Chart date: **{now_dt.strftime('%b %d, %Y  %H:%M')} {tz_abbr}**")

	# --- Forward / Back / Reset buttons + interval dropdown ---
	nav_cols = st.columns([1, 1, 1, 2])

	with nav_cols[0]:
		st.button(
			"◀", key="now_nav_back",
			on_click=_apply_now_date_offset, args=(-1,),
			use_container_width=True,
		)
	with nav_cols[1]:
		st.button(
			"▶", key="now_nav_fwd",
			on_click=_apply_now_date_offset, args=(1,),
			use_container_width=True,
		)
	with nav_cols[2]:
		st.button(
			"Now", key="now_nav_reset",
			on_click=_set_now_date_to_current,
			use_container_width=True,
		)
	with nav_cols[3]:
		st.session_state.setdefault("now_date_nav_interval", "1 day")
		st.selectbox(
			"Step",
			options=list(_NOW_DATE_INTERVALS.keys()),
			key="now_date_nav_interval",
			label_visibility="collapsed",
		)

	# --- Direct date/time input (collapsed expander) ---
	with st.expander("Set date & time directly", expanded=False):
		d_col, t_col = st.columns(2)
		with d_col:
			st.date_input(
				"Date",
				value=now_dt.date(),
				key="now_direct_date",
				min_value=dt.date(1, 1, 1),
				max_value=dt.date(9999, 12, 31),
			)
		with t_col:
			st.time_input(
				f"Time ({tz_abbr})",
				value=now_dt.time().replace(second=0, microsecond=0),
				key="now_direct_time",
			)
		st.button(
			"Apply", key="now_direct_apply",
			on_click=_apply_direct_now_date,
			use_container_width=True,
		)

def _format_time_12h(dt_obj: dt.datetime) -> str:
	h = dt_obj.hour
	m = dt_obj.minute
	ampm = "AM" if h < 12 else "PM"
	h12 = h % 12
	if h12 == 0:
		h12 = 12
	return f"{h12}:{m:02d} {ampm}"

import streamlit as st

def _phase_label_from_delta(delta_deg: float) -> str:
	"""
	Map Sun–Moon elongation to phase using 45°-wide bins (±22.5° orb).
	Bin centers: 0, 45, 90, 135, 180, 225, 270, 315.
	"""
	d = delta_deg % 360.0

	# Halfway boundaries at every 22.5°
	# [337.5, 22.5) New
	if d < 22.5 or d >= 337.5:
		return "New Moon"
	# [22.5, 67.5)
	if d < 67.5:
		return "Waxing Crescent"
	# [67.5, 112.5)
	if d < 112.5:
		return "First Quarter"
	# [112.5, 157.5)
	if d < 157.5:
		return "Waxing Gibbous"
	# [157.5, 202.5)
	if d < 202.5:
		return "Full Moon"
	# [202.5, 247.5)
	if d < 247.5:
		return "Waning Gibbous"
	# [247.5, 292.5)
	if d < 292.5:
		return "Last Quarter"
	# [292.5, 337.5)
	return "Waning Crescent"

def _moon_phase_label_emoji(sun_lon_deg: float, moon_lon_deg: float, *, emoji_size_px: int | None = None):
	"""
	Compute phase from ecliptic longitudes (degrees 0..360).
	Returns:
	  - label (str)
	  - img_html (str) if emoji_size_px is provided (for st.markdown with unsafe_allow_html=True)
	    OR file_path (str) to the PNG if emoji_size_px is None (use st.image(file_path, width=...)).

	PNG files expected in ./pngs relative to this file:
	  moon_full.png, moon_new.png, moon_wax_cres.png, moon_wan_cres.png,
	  moon_wax_gib.png, moon_wan_gib.png, moon_first_quart.png, moon_last_quart.png
	"""
	import os

	phase = (moon_lon_deg - sun_lon_deg) % 360.0

	phase = (moon_lon_deg - sun_lon_deg) % 360.0
	label = _phase_label_from_delta(phase)

	# Map label -> filename
	filename_map = {
		"New Moon":        "moon_new.png",
		"Waxing Crescent": "moon_wax_cres.png",
		"First Quarter":   "moon_first_quart.png",
		"Waxing Gibbous":  "moon_wax_gib.png",
		"Full Moon":       "moon_full.png",
		"Waning Gibbous":  "moon_wan_gib.png",
		"Last Quarter":    "moon_last_quart.png",
		"Waning Crescent": "moon_wan_cres.png",
	}

	# Build path: ./pngs next to this file (matches your Rosetta_v2\pngs layout)
	base_dir = MOON_PNG_DIR
	file_path = os.path.join(base_dir, filename_map[label])

	if emoji_size_px:
		# Return inline HTML <img> so you can drop it into st.markdown(...)
		# Use file:/// URL with forward slashes for reliability on Windows.
		url_path = file_path.replace("\\", "/")
		img_html = (
			f"<img src='file:///{url_path}' "
			f"width='{int(emoji_size_px)}' style='vertical-align:middle'/>"
		)
		return label, img_html

	# Otherwise return the file path for st.image(...)
	return label, file_path

def render_moon_phase_label(sun_lon_deg: float, moon_lon_deg: float, *, emoji_size_px: int = 28):
    """
    Renders the moon phase label + PNG in Streamlit without adding columns.
    """
    import os, base64

    label, moon_png_path = _moon_phase_label_emoji(sun_lon_deg, moon_lon_deg)

    if not os.path.exists(moon_png_path):
        st.error(f"Moon icon not found at: {moon_png_path}")
        st.caption(f"[debug] __file__ = {__file__}")
        return

    # Embed as base64 so it always renders inline
    with open(moon_png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px">
            <img src="data:image/png;base64,{b64}" width="{int(emoji_size_px)}" style="vertical-align:middle" />
            <span>{label}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

def _extract_lon_from_chart(chart, obj_name: str) -> float | None:
	"""
	Returns ecliptic longitude (0..360) for obj_name ("Sun" or "Moon") from a chart
	that is either a pandas DataFrame or a dict-like structure.

	First targets the schema produced by calculate_chart():
	    columns: "Object" and "Longitude"
	Then falls back to other common shapes.
	"""
	try:
		import pandas as pd

		# --- pandas.DataFrame path ---
		if isinstance(chart, pd.DataFrame):
			df = chart

			# 1) Your calculate_chart schema: "Object" + "Longitude"
			if "Object" in df.columns and "Longitude" in df.columns:
				m = df["Object"].astype(str).str.lower() == obj_name.lower()
				if m.any():
					return float(df.loc[m, "Longitude"].iloc[0]) % 360.0

			# 2) Other common column spellings (legacy/elsewhere)
			possible_name_cols = [c for c in ("object", "name") if c in df.columns]
			possible_lon_cols  = [c for c in ("absolute_degree", "lon", "longitude") if c in df.columns]
			if possible_name_cols and possible_lon_cols:
				name_col = possible_name_cols[0]
				lon_col  = possible_lon_cols[0]
				m = df[name_col].astype(str).str.lower() == obj_name.lower()
				if m.any():
					return float(df.loc[m, lon_col].iloc[0]) % 360.0

			return None

		# --- dict-like shapes ---
		if isinstance(chart, dict):
			# Direct mapping: {'Sun': {'Longitude': ...}, 'Moon': {...}}
			node = chart.get(obj_name)
			if isinstance(node, dict):
				for k in ("Longitude", "absolute_degree", "lon", "longitude"):
					if k in node:
						return float(node[k]) % 360.0

			# Nested under 'objects'
			objs = chart.get("objects")
			if isinstance(objs, dict) and obj_name in objs and isinstance(objs[obj_name], dict):
				for k in ("Longitude", "absolute_degree", "lon", "longitude"):
					if k in objs[obj_name]:
						return float(objs[obj_name][k]) % 360.0

			if isinstance(objs, list):
				for n in objs:
					if not isinstance(n, dict):
						continue
					name = str(n.get("Object") or n.get("object") or n.get("name") or "").strip()
					if name.lower() == obj_name.lower():
						for k in ("Longitude", "absolute_degree", "lon", "longitude"):
							if k in n:
								return float(n[k]) % 360.0

		return None
	except Exception:
		return None

def render_moon_phase_from_chart(chart_df_or_dict, *, emoji_size_px: int = 50) -> None:
	"""
	Replicates the existing moon-phase widget but sources Sun/Moon from the CHART DATA,
	NOT the current time. Renders the same PNG + label as `render_moon_phase_label(...)`.
	"""
	sun_lon  = _extract_lon_from_chart(chart_df_or_dict, "Sun")
	moon_lon = _extract_lon_from_chart(chart_df_or_dict, "Moon")

	if sun_lon is None or moon_lon is None:
		st.error("Moon phase unavailable (Sun/Moon not found in chart data).")
		return
	
	render_moon_phase_label(sun_lon, moon_lon, emoji_size_px=emoji_size_px)

def render_now_widget(
	col,
	MONTH_NAMES: list[str],
	run_chart,  # callable: run_chart(lat, lon, tz_name)
	geocode_city_with_timezone,  # callable: geocode_city_with_timezone(city_str) -> (lat, lon, tz_name, formatted)
):
	"""
	Packaged version of the 'Now' column UI and the current time/moon-phase widget.
	Call this from your layout, passing the column container, MONTH_NAMES,
	and your existing run_chart() and _geocode_city_with_timezone() callables.
	"""
	
	C1, C2 = st.columns([1, 1])

	with C1:
		# --- "🌟 Now" button ---
		if st.button("🌟 Now", key="btn_now"):
			stored_lat = st.session_state.get("current_lat")
			stored_lon = st.session_state.get("current_lon")
			stored_tz  = st.session_state.get("current_tz_name")
			city_name  = st.session_state.get("profile_city", "")

			# If we don't have a valid location yet, show the quick field right here
			if not (isinstance(stored_lat, (int, float)) and isinstance(stored_lon, (int, float)) and stored_tz):
				st.error("Enter a city.")
				st.session_state["show_now_city_field"] = True
			else:
				try:
					tz = pytz.timezone(stored_tz)
					now = dt.datetime.now(tz)
					# Seed the navigator with the current UTC moment
					st.session_state["now_chart_dt_utc"] = now.astimezone(pytz.utc).replace(tzinfo=None)

					# update profile_* inputs
					st.session_state["profile_year"]        = now.year
					st.session_state["profile_month_name"]  = MONTH_NAMES[now.month - 1]
					st.session_state["profile_day"]         = now.day
					st.session_state["profile_hour"]        = now.hour
					st.session_state["profile_minute"]      = now.minute
					st.session_state["profile_city"]        = city_name
					if "profile_unknown_time" not in st.session_state:
						st.session_state["profile_unknown_time"] = False

					# Store chart inputs under an override key (widget keys can't be
					# written after widgets are instantiated)
					_h = now.hour
					_ampm = "PM" if _h >= 12 else "AM"
					_h12 = _h % 12 or 12
					st.session_state["_now_chart_inputs"] = {
						"year":             now.year,
						"month_name":       MONTH_NAMES[now.month - 1],
						"day":              now.day,
						"hour_12":          f"{_h12:02d}",
						"minute_str":       f"{now.minute:02d}",
						"ampm":             _ampm,
						"city":             city_name,
						"house_system":     st.session_state.get("house_system", "placidus"),
						"unknown_time_flag": False,
					}

					# ensure current_* cache
					st.session_state["current_lat"]     = stored_lat
					st.session_state["current_lon"]     = stored_lon
					st.session_state["current_tz_name"] = stored_tz

					# compute planets (house system is used later at render)
					run_chart()
					st.session_state.pop("_now_chart_inputs", None)

					st.session_state["chart_ready"] = True
					# Enable the date navigator for this single-chart now view
					st.session_state["now_mode_active"] = True
					st.rerun()
				except Exception as e:
					st.error(f"Chart calculation failed: {e}")
					st.session_state["chart_ready"] = False

		# --- Current Date / Time / Moon Phase (always "now" via Swiss Ephemeris) ---

		# 1) Choose timezone: user-input city (if present) else CST default
		_city_str = (st.session_state.get("profile_city") or "").strip()
		_tz_name  = st.session_state.get("current_tz_name")
		if _city_str and _tz_name:
			tz = pytz.timezone(_tz_name)
			show_cst_default_note = False
		else:
			tz = pytz.timezone("America/Chicago")  # CST region
			show_cst_default_note = True

		now_local = dt.datetime.now(tz)

		# 2) Date & time lines
		date_line = f"{MONTH_NAMES[now_local.month - 1]} {now_local.day}, {now_local.year}"
		time_line = _format_time_12h(now_local)
		if show_cst_default_note:
			time_line += " (CST: default)"

		# 3) Always compute Sun/Moon longitudes for *current* time (Swiss Ephemeris)
		try:
			import swisseph as swe
			ut = now_local.astimezone(pytz.UTC)
			jd_ut = swe.julday(
				ut.year, ut.month, ut.day,
				ut.hour + ut.minute/60.0 + ut.second/3600.0
			)
			# Use the same call signature as in calc_v2.py
			sun_lon  = swe.calc_ut(jd_ut, swe.SUN)[0][0] % 360.0
			moon_lon = swe.calc_ut(jd_ut, swe.MOON)[0][0] % 360.0
		except Exception as e:
			st.error("Moon phase unavailable")
			st.caption(f"[debug] {type(e).__name__}: {e}")
		else:
			# Actually render the PNG (no text path printing)
			render_moon_phase_label(sun_lon, moon_lon, emoji_size_px=50)

	with C2:
		# 4) Render the three lines
		st.markdown(
			f"""
**{date_line}**  
{time_line}  
			""".strip()
		)

	# --- Quick city field — only shows if the guard above failed ---
	if st.session_state.get("show_now_city_field", False):
		st.caption("Quick city entry for Now:")

		# A tiny form prevents duplicated buttons and lets Enter submit
		with st.form("now_city_form", clear_on_submit=True):
			city_str = st.text_input(
				"City (e.g., Denver, CO, USA)",
				key="now_city_temp",
				placeholder="City, State/Province, Country",
			)
			f1, f2 = st.columns([1, 1], gap="small")
			with f1:
				submit_now = st.form_submit_button("Lookup City", use_container_width=True)
			with f2:
				cancel_now = st.form_submit_button("Cancel", use_container_width=True)

		if cancel_now:
			st.session_state["show_now_city_field"] = False
			st.rerun()

		if submit_now:
			city_str = (city_str or "").strip()
			if not city_str:
				st.error("Please type a city.")
			else:

				try:
					lat, lon, tz_name, formatted_address = geocode_city_with_timezone(city_str)

					# Make the location visible to drawing_v2
					if lat is not None and lon is not None:
						st.session_state["chart_lat"] = float(lat)
						st.session_state["chart_lon"] = float(lon)
					else:
						# Explicitly clear if lookup failed, so we fall back to 🌐
						st.session_state["chart_lat"] = None
						st.session_state["chart_lon"] = None

				except Exception as e:
					st.error(f"City lookup failed: {e}")
				else:
					if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and tz_name):
						st.error("City lookup returned invalid results.")
					elif tz_name not in pytz.all_timezones:
						st.error(f"Unrecognized timezone '{tz_name}'.")
					else:
						# Store city + geocode
						st.session_state["profile_city"]    = city_str
						st.session_state["city_input"]      = city_str
						st.session_state["current_lat"]     = lat
						st.session_state["current_lon"]     = lon
						st.session_state["current_tz_name"] = tz_name
						st.session_state["last_location"]   = formatted_address or city_str
						st.session_state["last_timezone"]   = tz_name

						# Compute "Now" in that timezone (3-arg run_chart)
						tz = pytz.timezone(tz_name)
						now = dt.datetime.now(tz)
						st.session_state["profile_year"]        = now.year
						st.session_state["profile_month_name"]  = MONTH_NAMES[now.month - 1]
						st.session_state["profile_day"]         = now.day
						st.session_state["profile_hour"]        = now.hour
						st.session_state["profile_minute"]      = now.minute

						# Store chart inputs under an override key
						_h = now.hour
						_ampm = "PM" if _h >= 12 else "AM"
						_h12 = _h % 12 or 12
						st.session_state["_now_chart_inputs"] = {
							"year":             now.year,
							"month_name":       MONTH_NAMES[now.month - 1],
							"day":              now.day,
							"hour_12":          f"{_h12:02d}",
							"minute_str":       f"{now.minute:02d}",
							"ampm":             _ampm,
							"city":             city_str,
							"house_system":     st.session_state.get("house_system", "placidus"),
							"unknown_time_flag": False,
						}

						try:
							run_chart()
							st.session_state.pop("_now_chart_inputs", None)
							st.session_state["chart_ready"] = True
							st.session_state["show_now_city_field"] = False
							st.rerun()

							# ✅ Force compass back on for a fresh chart
							st.session_state[COMPASS_KEY] = True
						except Exception as e:
							st.error(f"Chart calculation failed: {e}")
							st.session_state["chart_ready"] = False
