# now_v2.py
# --- Moon icons directory (ABSOLUTE) ---
MOON_PNG_DIR = r"C:\Users\imcur\Desktop\Rosetta Back-End\Rosetta\Rosetta_v2\pngs"
COMPASS_KEY = "ui_compass_overlay"

import datetime as dt
import pytz
import streamlit as st

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

					# update only the profile_* inputs
					st.session_state["profile_year"]        = now.year
					st.session_state["profile_month_name"]  = MONTH_NAMES[now.month - 1]
					st.session_state["profile_day"]         = now.day
					st.session_state["profile_hour"]        = now.hour
					st.session_state["profile_minute"]      = now.minute
					st.session_state["profile_city"]        = city_name
					st.session_state["profile_unknown_time"] = False

					# ensure current_* cache
					st.session_state["current_lat"]     = stored_lat
					st.session_state["current_lon"]     = stored_lon
					st.session_state["current_tz_name"] = stored_tz

					# compute planets (house system is used later at render)
					run_chart(stored_lat, stored_lon, stored_tz)

					st.session_state["chart_ready"] = True
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
					# NOTE: Fixed original NameError: use city_str here.
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

						try:
							run_chart(lat, lon, tz_name)
							st.session_state["chart_ready"] = True
							st.session_state["show_now_city_field"] = False
							st.rerun()
							# after a successful chart compute:
							st.session_state["last_df"] = df  # (your existing assignment)
							st.session_state["chart_dt_utc"] = jd_dt  # or whatever you already set

							# ✅ Force compass back on for a fresh chart
							st.session_state[COMPASS_KEY] = True
						except Exception as e:
							st.error(f"Chart calculation failed: {e}")
							st.session_state["chart_ready"] = False
