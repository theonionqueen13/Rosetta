from zoneinfo import ZoneInfo
import os, swisseph as swe
import networkx as nx
from profiles_v2 import sabian_for, find_fixed_star_conjunctions, STAR_CATALOG, glyph_for
from lookup_v2 import SIGNS, PLANETARY_RULERS
# Force path to the ephe folder in your repo
EPHE_PATH = os.path.join(os.path.dirname(__file__), "ephe")
EPHE_PATH = EPHE_PATH.replace("\\", "/")
os.environ["SE_EPHE_PATH"] = EPHE_PATH
swe.set_ephe_path(EPHE_PATH)

import datetime
import pandas as pd

OOB_LIMIT = 23.44  # degrees declination

def is_out_of_bounds(declination: float) -> bool:
	return abs(declination) > OOB_LIMIT

def deg_to_sign(lon):
	sign_index = int(lon // 30)
	degree = lon % 30
	sign = SIGNS[sign_index]
	d = int(degree)
	m = int((degree - d) * 60)
	s = int(((degree - d) * 60 - m) * 60)
	# sabian index = 1–360
	sabian_index = sign_index * 30 + int(degree) + 1
	return sign, f"{d}°{m:02d}'{s:02d}\"", sabian_index

def _sign_index(deg: float) -> int:
	"""0..11 index of the sign for ecliptic longitude deg."""
	return int((deg % 360.0) // 30)

def _sign_from_degree(deg: float) -> str:
	"""Return sign name from absolute degree."""
	return SIGNS[_sign_index(deg)]

def _calc_vertex(jd, lat, lon):
	cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
	if cusps is None or ascmc is None:      
		raise ValueError("Swiss Ephemeris could not calculate Placidus houses")

	return ascmc[3], 0.0, 0.0, 0.0  # lon, lat, dist, speed

def _calc_pof(jd, lat, lon):
	# Asc & Desc from Swiss Ephemeris
	cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
	asc = ascmc[0] % 360.0
	desc = (asc + 180.0) % 360.0

	# Sun & Moon ecliptic longitudes
	sun = swe.calc_ut(jd, swe.SUN)[0][0] % 360.0
	moon = swe.calc_ut(jd, swe.MOON)[0][0] % 360.0

	def on_arc(start, end, x):
		"""True if x lies on the circular arc going CCW from start to end."""
		start %= 360.0; end %= 360.0; x %= 360.0
		if start <= end:
			return start <= x <= end
		else:
			return x >= start or x <= end

	# Above horizon is the arc Desc -> Asc
	is_day = on_arc(desc, asc, sun)

	# Day: Asc + Moon − Sun ; Night: Asc − Moon + Sun
	if is_day:
		pof = (asc + moon - sun) % 360.0
	else:
		pof = (asc - moon + sun) % 360.0

	return pof, 0.0, 0.0, 0.0

def get_utc_datetime(year, month, day, hour, minute, input_is_ut, tz_offset, tz_name):
	"""Return a UTC-aware datetime for the given local inputs."""
	if input_is_ut:
		return datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
	if tz_name:
		tz = ZoneInfo(tz_name)
		local_dt = datetime.datetime(year, month, day, hour, minute, tzinfo=tz)
		return local_dt.astimezone(datetime.timezone.utc)
	tz = datetime.timezone(datetime.timedelta(hours=tz_offset))
	local_dt = datetime.datetime(year, month, day, hour, minute, tzinfo=tz)
	return local_dt.astimezone(datetime.timezone.utc)

def calculate_house_cusps(jd, lat, lon, asc_val, house_system=None):
	"""
	Return house cusp rows.

	- If house_system in {"placidus","equal","whole"}: returns 12 rows for that system.
	- If house_system is None or "all": returns 36 rows (Placidus, Equal, Whole), each labeled.
	"""
	def _one_system_rows(sys: str) -> list[dict]:
		rows = []
		sys_lc = sys.lower()

		if sys_lc == "placidus":
			cusps, _ = swe.houses_ex(jd, lat, lon, b'P')
			if cusps is None:
				raise ValueError("Swiss Ephemeris could not calculate Placidus houses")
			for i, deg in enumerate(cusps[:12], start=1):
				rows.append({
					"Object": f"{i}H Cusp",
					"Computed Absolute Degree": round(deg % 360.0, 6),
					"House System": "placidus",
				})

		elif sys_lc == "equal":
			asc_for_equal = asc_val
			if asc_for_equal is None:
				_, ascmc = swe.houses_ex(jd, lat, lon, b'E')
				if ascmc is None:
					raise ValueError("Swiss Ephemeris could not calculate Equal houses")
				asc_for_equal = ascmc[0]
			for i in range(12):
				deg = (asc_for_equal + i * 30.0) % 360.0
				rows.append({
					"Object": f"{i+1}H Cusp",
					"Computed Absolute Degree": round(deg, 6),
					"House System": "equal",
				})

		elif sys_lc == "whole":
			asc_for_whole = asc_val
			if asc_for_whole is None:
				_, ascmc = swe.houses_ex(jd, lat, lon, b'P')
				if ascmc is None:
					raise ValueError("Swiss Ephemeris could not calculate Placidus houses (for Whole sign ASC)")
				asc_for_whole = ascmc[0]
			asc_sign = int(asc_for_whole // 30) * 30.0
			for i in range(12):
				deg = (asc_sign + i * 30.0) % 360.0
				rows.append({
					"Object": f"{i+1}H Cusp",
					"Computed Absolute Degree": round(deg, 6),
					"House System": "whole",
				})

		else:
			raise ValueError(f"Unknown house system: {sys}")
		return rows

	# All systems
	if house_system is None or str(house_system).lower() in ("all", "*"):
		out = []
		for sys in ("placidus", "equal", "whole"):
			out.extend(_one_system_rows(sys))
		return out

	# Single system
	return _one_system_rows(str(house_system).lower())

def calculate_chart(
	year, month, day, hour, minute,
	tz_offset, lat, lon,
	input_is_ut: bool = False,
	tz_name: str | None = None,
	# house_system kept for back-compat but ignored
	house_system: str | None = None,
	include_aspects: bool = False,   # <-- NEW
	unknown_time: bool = False,
):
	# ---- Lazy import of lookup tables from the SAME FOLDER as this file ----
	# This avoids package/sys.path headaches (Rosetta_v2 vs rosetta, etc.)
	global DIGNITIES, PLANETARY_RULERS, MAJOR_OBJECTS, SIGNS
	import importlib.util, pathlib

	here = pathlib.Path(__file__).resolve()
	lookup_path = here.with_name("lookup_v2.py")

	spec = importlib.util.spec_from_file_location("lookup_v2_local", str(lookup_path))
	mod = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(mod)

	DIGNITIES = mod.DIGNITIES
	PLANETARY_RULERS = mod.PLANETARY_RULERS
	MAJOR_OBJECTS = mod.MAJOR_OBJECTS
	SIGNS = mod.SIGNS

	"""
	Build the chart using Swiss Ephemeris.

	- Computes object rows.
	- Computes house cusps for ALL systems (Placidus, Equal, Whole) and appends all cusp rows.
	- Assigns per-object House / House Sign / House Rulers for EACH system in separate columns.
	- Returns a single DataFrame.
	"""

	# -------- Time -> UTC --------
	calc_hour = hour
	calc_minute = minute
	calc_tz_offset = tz_offset
	calc_tz_name = tz_name
	calc_input_is_ut = input_is_ut
	if unknown_time:
		calc_hour = 12
		calc_minute = 0
		calc_tz_offset = 0
		calc_tz_name = None
		calc_input_is_ut = True

	utc_dt = get_utc_datetime(
		year,
		month,
		day,
		calc_hour,
		calc_minute,
		calc_input_is_ut,
		calc_tz_offset,
		calc_tz_name,
	)

	jd = swe.julday(
		utc_dt.year, utc_dt.month, utc_dt.day,
		utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
		swe.GREG_CAL,
	)

	# -------- Precompute ASC & MC (Placidus) --------
	asc_val = mc_val = None
	cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
	if ascmc and not unknown_time:
		asc_val = ascmc[0]
		mc_val = ascmc[1]

	# -------- Precompute Descendant & IC --------
	extra_objects = {}
	if not unknown_time and asc_val is not None:
		dc_val = (asc_val + 180.0) % 360.0
		extra_objects["DC"] = {
			"name": "Descendant",
			"lon": dc_val,
			"lat": 0.0,
			"dist": 0.0,
			"speed": 0.0,
			"decl": 0.0,
		}

	if not unknown_time and mc_val is not None:
		ic_val = (mc_val + 180.0) % 360.0
		extra_objects["IC"] = {
			"name": "IC",
			"lon": ic_val,
			"lat": 0.0,
			"dist": 0.0,
			"speed": 0.0,
			"decl": 0.0,
		}

	# -------- Combine MAJOR_OBJECTS with extras --------
	base_objects = MAJOR_OBJECTS
	if unknown_time:
		base_objects = {
			name: ident
			for name, ident in MAJOR_OBJECTS.items()
			if name not in {"AC", "MC", "Part of Fortune", "Vertex"}
		}

	loop_objects = list(base_objects.items()) + list(extra_objects.items())

	rows = []
	pos_for_dispositors = {}  # object -> longitude (exclude cusps)
	print(pos_for_dispositors.keys())

	# --- Main loop (object rows) ---
	for name, ident in loop_objects:
		# --- handle each type ---
		if ident == "ASC":
			lon_, lat_, dist, speed = asc_val, 0.0, 0.0, 0.0
			decl = 0.0
		elif ident == "MC":
			lon_, lat_, dist, speed = mc_val, 0.0, 0.0, 0.0
			decl = 0.0
		elif ident == "VERTEX":
			lon_, lat_, dist, speed = _calc_vertex(jd, lat, lon)
			decl = 0.0
		elif ident == "POF":
			lon_, lat_, dist, speed = _calc_pof(jd, lat, lon)
			decl = 0.0
		elif ident == -1:  # South Node
			north_pos, _ = swe.calc_ut(jd, swe.TRUE_NODE)
			lon_ = (north_pos[0] + 180) % 360
			lat_, dist, speed = 0.0, 0.0, 0.0
			decl = 0.0
		elif name in ("DC", "IC"):
			obj = extra_objects[name]
			lon_, lat_, dist, speed, decl = obj["lon"], obj["lat"], obj["dist"], obj["speed"], obj["decl"]
		else:
			pos, _ = swe.calc_ut(jd, ident)
			lon_, lat_, dist, speed = pos[:4]
			eq, _ = swe.calc_ut(jd, ident, swe.FLG_EQUATORIAL)
			decl = eq[1]

		# --- common calculations ---
		glyph = glyph_for(name)
		sign, dms, sabian_index = deg_to_sign(lon_)
		sabian_symbol = sabian_for(sign, lon_)
		star_hits = find_fixed_star_conjunctions(lon_, STAR_CATALOG, orb=1.0)
		star_names = ", ".join(h["Name"] for h in star_hits)
		degree_in_sign = int(lon_ % 30)
		minute_in_sign = int(((lon_ % 30) - degree_in_sign) * 60)
		second_in_sign = int(((((lon_ % 30) - degree_in_sign) * 60) - minute_in_sign) * 60)
		retro_bool = (speed < 0)
		retro = "Rx" if retro_bool else ""
		oob_bool = is_out_of_bounds(decl)
		oob = "Yes" if oob_bool else "No"
		dignity = _resolve_dignity(name, sign)
		sign_rulers_list = lookup_sign_rulers(sign, PLANETARY_RULERS)
		sign_rulers_str = ", ".join(sign_rulers_list)
		pos_for_dispositors[name] = lon_

		rows.append({
			"Glyph": glyph,
			"Object": name,
			"Dignity": dignity,         # filled later
			"Reception": "",       
			"Ruled by (sign)": sign_rulers_str,
			"Longitude": round(lon_, 6),
			"Sign": sign,
			"Sign Index": _sign_index(lon_),
			"Degree In Sign": degree_in_sign,
			"Minute In Sign": minute_in_sign,
			"Second In Sign": second_in_sign,
			"DMS": dms,
			"Sabian Index": sabian_index,
			"Sabian Symbol": sabian_symbol,
			"Fixed Star Conj": star_names,
			"Retrograde Bool": retro_bool,
			"OOB Status": oob,
			"Latitude": round(lat_, 6),
			"Declination": round(decl, 6),
			"Distance": round(dist, 6),
			"Speed": round(speed, 6),

			# Per-system House fields will be filled after cusps are computed
			"Placidus House": None,
			"Placidus House Rulers": None,
			"Equal House": None,
			"Equal House Rulers": None,
			"Whole Sign House": None,
			"Whole Sign House Rulers": None,
		})

	# --- House cusps (ALL systems appended to DF) ---
	systems = ("placidus", "equal", "whole")
	# Note the exact labels to match your reference sheet
	system_label = {"placidus": "Placidus", "equal": "Equal", "whole": "Whole Sign"}

	cusps_by_system: dict[str, list[float]] = {}
	all_cusp_rows: list[dict] = []

	import re

	for sys in systems:
		rows_sys = calculate_house_cusps(jd, lat, lon, asc_val, sys)
		lbl = system_label[sys]

		# Normalize cusp rows:
		# - "Object" -> "<System Label> #H cusp"
		# - Move "Computed Absolute Degree" -> "Longitude"
		# - DROP "House System" and "Computed Absolute Degree"
		normalized = []
		for r in rows_sys:
			obj = str(r.get("Object", ""))  # e.g., "1H Cusp"
			m = re.match(r"^\s*(\d+)\s*H", obj, flags=re.IGNORECASE)
			if m:
				num = m.group(1)
				new_obj = f"{lbl} {num}H cusp"
			else:
				new_obj = f"{lbl} {obj}".replace("Cusp", "cusp")

			r2 = {}
			r2["Object"] = new_obj
			cad = r.get("Computed Absolute Degree")
			if cad is not None:
				r2["Longitude"] = round(cad, 6)  # keep your 6-dec rounding

			# Intentionally NOT copying "House System" (dropped)

			normalized.append(r2)

		all_cusp_rows.extend(normalized)

		# keep raw degrees for per-system lookups
		cusps_by_system[sys] = [row["Computed Absolute Degree"] for row in rows_sys]

	# --- Enrich object rows with per-system House / Sign / Rulers ---
	cusp_signs_maps = {sys: _compute_cusp_signs(cusps_by_system[sys]) for sys in systems}

	for r in rows:
		lon_ = r.get("Longitude")
		if lon_ is None:
			continue
		for sys in systems:
			cusps = cusps_by_system.get(sys)
			if not cusps or len(cusps) < 12:
				continue
			h = _house_of_degree(lon_, cusps)
			if not h:
				continue
			sys_lbl = system_label[sys]   # "Placidus", "Equal", "Whole Sign"
			r[f"{sys_lbl} House"] = h
			house_sign = cusp_signs_maps[sys].get(h)
			if house_sign:
				hr_list = lookup_sign_rulers(house_sign, PLANETARY_RULERS)
				r[f"{sys_lbl} House Rulers"] = ", ".join(hr_list)

	# --- Dispositor graphs & membership flags (SIGN + per-HOUSE-SYSTEM) ---

	# 1) SIGN-based dispositor graph (no cusps)
	disp_sign_only = analyze_dispositors(pos_for_dispositors, None)
	by_sign = disp_sign_only.get("by_sign", {})

	sign_dominant  = set(by_sign.get("dominant_rulers", []) or [])
	sign_final     = set(by_sign.get("final_dispositors", []) or [])
	sign_sovereign = set(by_sign.get("sovereign", []) or [])

	sign_loops = set()
	for cyc in (by_sign.get("loops") or []):
		for n in cyc:
			sign_loops.add(n)

	# Fill SIGN flags on object rows
	for r in rows:
		obj = r["Object"]
		r["Sign: Dominant Ruler"]   = (obj in sign_dominant)
		r["Sign: Final Dispositor"] = (obj in sign_final)
		r["Sign: Sovereign"]        = (obj in sign_sovereign)
		r["Sign: In Loop"]          = (obj in sign_loops)

	# 2) HOUSE-based dispositor graphs for EACH system
	#    Uses the cusps we already computed per system above: cusps_by_system
	house_flags_by_system: dict[str, dict[str, set]] = {}
	house_dispositor_data: dict[str, dict] = {}  # Store full dispositor analysis for plotting

	for sys in systems:  # systems = ("placidus", "equal", "whole")
		cusps = cusps_by_system.get(sys, [])  # 12 cusp degrees for this system
		print(f"\n🏠 Calculating dispositors for {sys.upper()} house system...")
		disp_sys = analyze_dispositors(pos_for_dispositors, cusps)
		by_house = disp_sys.get("by_house", {})
		
		print(f"\n🔍 DEBUG house dispositor analysis for {sys}:")
		print(f"   cusps count: {len(cusps)}")
		print(f"   by_house keys: {list(by_house.keys())}")
		print(f"   raw_links: {by_house.get('raw_links', [])}")
		print(f"   sovereigns: {by_house.get('sovereigns', [])}")

		dom   = set(by_house.get("dominant_rulers", []) or [])
		final = set(by_house.get("final_dispositors", []) or [])
		sov   = set(by_house.get("sovereign", []) or [])

		loops_set = set()
		for cyc in (by_house.get("loops") or []):
			for n in cyc:
				loops_set.add(n)

		sys_lbl = system_label[sys]  # "Placidus", "Equal", "Whole Sign"
		house_flags_by_system[sys_lbl] = {
			"dom":   dom,
			"final": final,
			"sov":   sov,
			"loop":  loops_set,
		}
		# Store full dispositor data for plotting
		house_dispositor_data[sys_lbl] = by_house

	# Fill HOUSE flags per system on object rows
	for r in rows:
		obj = r["Object"]
		for sys_lbl, flags in house_flags_by_system.items():
			r[f"{sys_lbl} House: Dominant Ruler"]   = (obj in flags["dom"])
			r[f"{sys_lbl} House: Final Dispositor"] = (obj in flags["final"])
			r[f"{sys_lbl} House: Sovereign"]        = (obj in flags["sov"])
			r[f"{sys_lbl} House: In Loop"]          = (obj in flags["loop"])

	# --- Build final DataFrame (objects + all cusps) ---
	base_df = pd.DataFrame(rows)
	cusp_df = pd.DataFrame(all_cusp_rows)
	combined_df = pd.concat([base_df, cusp_df], ignore_index=True)

	# --- REMOVE redundant Sign: and House: columns ---
	cols_to_keep = [
		c for c in combined_df.columns
		if not (
			c.startswith("Sign:") or
			re.match(r"^(Placidus|Equal|Whole Sign) House:", c)
		)
	]

	combined_df = combined_df[cols_to_keep]

	aspect_df = build_aspect_table(combined_df)

	# --- Build ruler → children map from analyze_dispositors ---
	ruler_map = {}
	raw_chains_list = by_sign.get("chains", []) or []  # list of chains, each as ["A", "B", "C"]

	for chain in raw_chains_list:
		for i in range(len(chain)-1):
			parent, child = chain[i], chain[i+1]
			ruler_map.setdefault(parent, set()).add(child)
		# ensure last node exists
		ruler_map.setdefault(chain[-1], set())

	# --- Generate all paths from every object down to final dispositors ---
	def build_paths(node, path, visited):
		if node in visited:
			return []
		visited.add(node)
		paths = []
		children = ruler_map.get(node, set())
		if not children:  # leaf
			paths.append(path + [node])
		else:
			for child in children:
				# deduplicate children in the same branch
				if child not in path:
					paths.extend(build_paths(child, path + [node], visited.copy()))
				else:
					# add the final loop node once at the end
					paths.append(path + [node, child])
		return paths

	all_paths = []
	for obj in pos_for_dispositors.keys():
		all_paths.extend(build_paths(obj, [], set()))

	# --- Convert paths to strings for plotting ---
	raw_chains = [" → ".join(p) for p in all_paths]

	# --- Build plot_data dict with all scopes ---
	# Store dispositor data for sign-based and each house system
	plot_data = {
		"by_sign": {
			"raw_links": disp_sign_only.get("by_sign", {}).get("raw_links", []),
			"sovereigns": list(sign_sovereign),
			"self_ruling": disp_sign_only.get("by_sign", {}).get("self_ruling", [])
		}
	}
	
	# Add house-based dispositor data for each system (already calculated above)
	for sys_lbl, by_house in house_dispositor_data.items():
		plot_data[sys_lbl] = {
			"raw_links": by_house.get("raw_links", []),
			"sovereigns": by_house.get("sovereigns", []),
			"self_ruling": by_house.get("self_ruling", [])
		}
	
	print(f"\n🔍 DEBUG plot_data structure:")
	for key, data in plot_data.items():
		print(f"   [{key}]:")
		print(f"      raw_links count: {len(data.get('raw_links', []))}")
		print(f"      sovereigns: {data.get('sovereigns', [])}")
		print(f"      self_ruling: {data.get('self_ruling', [])}")

	# --- Return values ---
	if include_aspects:
		aspect_df = build_aspect_table(combined_df)
		return combined_df, aspect_df, plot_data

	# If aspects not included, return combined_df and plot_data
	return combined_df, None, plot_data


import matplotlib.pyplot as plt
import networkx as nx

def chart_sect_from_df(df) -> str:
	"""
	Return 'Diurnal' or 'Nocturnal' based on Sun relative to horizon.
	Requires both 'Sun' and 'AC' rows. If either is missing (e.g., Unknown Time),
	raise ValueError('time unknown') so the caller can present a friendly message.
	"""
	sun_series = df.loc[df["Object"] == "Sun", "Longitude"]
	ac_series  = df.loc[df["Object"] == "AC",  "Longitude"]

	if sun_series.empty or ac_series.empty:
		# Unknown time charts typically omit AC/DC (no house cusps)
		raise ValueError("time unknown")

	sun = float(sun_series.iloc[0]) % 360.0
	ac  = float(ac_series.iloc[0])  % 360.0
	dc  = (ac + 180.0) % 360.0

	return "Diurnal" if _in_forward_arc(dc, ac, sun) else "Nocturnal"

def _house_of_degree(deg: float, cusps: list[float]) -> int | None:
	"""
	Given absolute degree and a 12-cusp list (1..12), return the house number (1..12).
	Uses forward-arc logic cusp[i] -> cusp[(i+1)%12].
	"""
	if not cusps or len(cusps) < 12:
		return None
	for i in range(12):
		start = cusps[i]
		end   = cusps[(i + 1) % 12]
		if _in_forward_arc(start, end, deg):
			return i + 1
	return 12  # fallback for exact equality/rounding edges

def _compute_cusp_signs(cusps_list):
	"""Return {house_num: sign_name} for 1..12 using active cusps."""
	return {i+1: _sign_from_degree(cusps_list[i]) for i in range(min(12, len(cusps_list)))}

def _in_forward_arc(start_deg, end_deg, x_deg):
	"""True if x lies on the forward arc from start->end (mod 360)."""
	span = (end_deg - start_deg) % 360.0
	off  = (x_deg   - start_deg) % 360.0
	return off < span if span != 0 else off == 0

def lookup_sign_rulers(sign, planetary_rulers):
	"""
	Return a list of rulers for a given zodiac sign.

	Parameters
	----------
	sign : str
		e.g., "Leo"
	planetary_rulers : dict
		Your PLANETARY_RULERS mapping {sign -> ruler or [rulers]}

	Returns
	-------
	list[str]
		Always a list (may be empty).
	"""
	s = (sign or "").strip()
	rulers = planetary_rulers.get(s, [])
	if isinstance(rulers, (list, tuple)):
		return list(rulers)
	return [rulers] if rulers else []

def house_rulers_from_cusps(cusps_list, planetary_rulers, compute_cusp_signs_fn):
	"""
	Compute house rulers for a *single* house system.

	Parameters
	----------
	cusps_list : list[float] or tuple[float]
		The 12 house cusp longitudes for the current system (1..12).
	planetary_rulers : dict
		Your PLANETARY_RULERS mapping {sign -> ruler or [rulers]}.
	compute_cusp_signs_fn : callable
		A function like your existing `_compute_cusp_signs(cusps_list)` that returns:
		{house_number (1..12) -> sign string}

	Returns
	-------
	dict[int, list[str]]
		{house_number -> [rulers]} for the given system.
	"""
	cusp_signs = compute_cusp_signs_fn(cusps_list)  # expects {1:'Aries', 2:'Taurus', ...}
	house_rulers = {}
	for h, sign_on_cusp in cusp_signs.items():
		house_rulers[h] = lookup_sign_rulers(sign_on_cusp, planetary_rulers)
	return house_rulers

def house_rulers_across_systems(cusps_by_system, planetary_rulers, compute_cusp_signs_fn):
	"""
	Compute house rulers for *all* requested house systems.

	Parameters
	----------
	cusps_by_system : dict[str, list[float] | tuple[float]]
		{system_key -> cusps_list}. Example keys: "Placidus", "Equal", "Whole".
		Each value is the 12-cusp sequence for that system.
	planetary_rulers : dict
		Your PLANETARY_RULERS mapping {sign -> ruler or [rulers]}.
	compute_cusp_signs_fn : callable
		Typically your `_compute_cusp_signs`.

	Returns
	-------
	dict[str, dict[int, list[str]]]
		{system_key -> {house_number -> [rulers]}}
	"""
	out = {}
	for system_key, cusps_list in cusps_by_system.items():
		out[system_key] = house_rulers_from_cusps(
			cusps_list=cusps_list,
			planetary_rulers=planetary_rulers,
			compute_cusp_signs_fn=compute_cusp_signs_fn,
		)
	return out

def analyze_dispositors(pos: dict, cusps: list[float] = None) -> dict:
	"""
	Analyze planetary rulerships and return structured data for plotting.
	
	Output format (for each scope: by_sign/by_house):
	{
		"raw_links": [(parent, child), ...],
		"sovereigns": [...],       # planets with no other ruler
		"self_ruling": [...],      # planets that rule themselves (even if co-ruled)
	}
	"""
	import networkx as nx

	def _ensure_list(x):
		if x is None:
			return []
		if isinstance(x, (list, tuple, set)):
			return list(x)
		return [x]

	def _build_scope(cusps_scope=None, debug_label=""):
		edges = []
		mode = "HOUSE-BASED" if cusps_scope else "SIGN-BASED"
		print(f"\n🔍 _build_scope {debug_label} - Mode: {mode}")
		for obj, deg in pos.items():
			# Use house rulership if cusps provided, else sign rulership
			if cusps_scope:
				h = _house_of_degree(deg, cusps_scope)
				if h:
					cusp_sign = SIGNS[_sign_index(cusps_scope[h - 1])]
					rulers = _ensure_list(PLANETARY_RULERS.get(cusp_sign, []))
					print(f"   {obj} @ {deg:.2f}° → House {h} → Cusp sign {cusp_sign} → Rulers: {rulers}")
				else:
					rulers = []
					print(f"   {obj} @ {deg:.2f}° → No house found → No rulers")
			else:
				sign = SIGNS[_sign_index(deg)]
				rulers = _ensure_list(PLANETARY_RULERS.get(sign, []))
				print(f"   {obj} @ {deg:.2f}° → Sign {sign} → Rulers: {rulers}")

			# Add edges
			# Edge direction: (ruler, ruled) means "ruler -> ruled"
			# In the graph: ruler is PARENT, ruled is CHILD
			if rulers:
				for r in rulers:
					if r in pos:
						edges.append((r, obj))  # ruler rules obj: ruler -> obj
			else:
				edges.append((obj, obj))  # self-ruler

		# Build graph
		G = nx.DiGraph()
		G.add_nodes_from(pos.keys())
		G.add_edges_from(edges)

		# Self-ruling
		self_ruling = sorted([n for n in G.nodes if G.has_edge(n, n)])

		# Sovereigns = planets with no other ruler (including self-rulers)
		sovereigns = sorted([n for n in G.nodes if not [u for u, v in G.in_edges(n) if u != n]])

		# Raw links = parent -> child ignoring self-loops
		raw_links = [(u, v) for u, v in G.edges if u != v]

		# Find cycles for loops and sovereign
		cycles = list(nx.simple_cycles(G))
		loops = [c for c in cycles if len(c) >= 2]

		# Dominant rulers: out-degree >= 3
		dominant_rulers = sorted([n for n, outdeg in G.out_degree() if outdeg >= 3])

		# Final dispositors: in-degree >= 1 and out-degree == 0
		final_dispositors = sorted([
			n for n in G.nodes
			if G.out_degree(n) == 0 and G.in_degree(n) >= 1
		])

		return {
			"raw_links": raw_links,
			"sovereigns": sovereigns,
			"self_ruling": self_ruling,
			"dominant_rulers": dominant_rulers,
			"final_dispositors": final_dispositors,
			"sovereign": sovereigns,  # alias for compatibility
			"loops": loops,
		}

	by_sign_result = _build_scope(None, debug_label="[BY_SIGN]")
	by_house_result = _build_scope(cusps if cusps and len(cusps) == 12 else None, 
	                                debug_label=f"[BY_HOUSE - {len(cusps) if cusps else 0} cusps]")
	
	print(f"\n📊 analyze_dispositors returning:")
	print(f"   by_sign raw_links count: {len(by_sign_result.get('raw_links', []))}")
	print(f"   by_house raw_links count: {len(by_house_result.get('raw_links', []))}")
	
	# Check for any Saturn edges
	saturn_edges_sign = [(p, c) for p, c in by_sign_result.get('raw_links', []) if 'Saturn' in (p, c)]
	saturn_edges_house = [(p, c) for p, c in by_house_result.get('raw_links', []) if 'Saturn' in (p, c)]
	print(f"   🔍 Saturn edges in by_sign: {saturn_edges_sign}")
	print(f"   🔍 Saturn edges in by_house: {saturn_edges_house}")
	
	return {
		"by_sign": by_sign_result,
		"by_house": by_house_result,
	}

def plot_dispositor_graph(plot_data):
	"""
	Plot dispositor trees in a vertical family-tree style.

	Rules:
	- Sovereign planets are roots of their own trees.
	- Each generation (distance from root) is a horizontal layer.
	- A planet may appear multiple times under different rulers if dual-ruled.
	- Never repeat the same parent->child edge.
	"""
	import matplotlib.pyplot as plt
	import networkx as nx
	from lookup_v2 import ABREVIATED_PLANET_NAMES

	raw_links = plot_data.get("raw_links", [])
	sovereigns = plot_data.get("sovereigns", [])
	self_ruling = plot_data.get("self_ruling", [])
	
	# Detect mutual reception loops (2+ planets in a rulership cycle)
	def find_mutual_reception_loops(links):
		"""Find all planets involved in mutual reception loops of 2 or more."""
		# Build adjacency list
		graph = {}
		for parent, child in links:
			if parent != child:  # Exclude self-ruling
				graph.setdefault(parent, []).append(child)
		
		# Find all cycles using DFS
		loop_members = set()
		
		def dfs_find_cycles(node, path, visited_in_path):
			if node in visited_in_path:
				# Found a cycle - add all nodes from cycle start to current
				cycle_start = path.index(node)
				cycle = path[cycle_start:]
				if len(cycle) >= 2:  # Only loops of 2+
					loop_members.update(cycle)
				return
			
			if node not in graph:
				return
			
			visited_in_path.add(node)
			path.append(node)
			
			for neighbor in graph[node]:
				dfs_find_cycles(neighbor, path[:], visited_in_path.copy())
		
		# Start DFS from each node
		for node in graph:
			dfs_find_cycles(node, [], set())
		
		return loop_members
	
	mutual_reception_loops = find_mutual_reception_loops(raw_links)
	print(f"🔮 Mutual reception loops detected: {sorted(mutual_reception_loops)}")
	
	# Detect planets that appear multiple times (dual rulership)
	# We'll count occurrences as we build the trees, then identify duplicates
	planet_occurrences = {}  # planet_name -> count
	
	# Helper function to get abbreviated name if available
	def get_display_name(name):
		return ABREVIATED_PLANET_NAMES.get(name, name)

	# Convert raw_links to a lookup for children by parent (preserve order)
	children_by_parent = {}
	for parent, child in raw_links:
		children_by_parent.setdefault(parent, []).append(child)

	# Build parent lookup (child -> parents)
	parents_by_child = {}
	for parent, child in raw_links:
		parents_by_child.setdefault(child, []).append(parent)

	# Track edges drawn globally so each parent->child is drawn once
	drawn_edges = set()

	# Create figure (one column per sovereign)
	# --- Determine roots dynamically using a phased approach ---
	all_nodes = set(children_by_parent.keys())
	for v in children_by_parent.values():
		all_nodes.update(v)

	roots = []
	accounted_for = set()  # Track all nodes already included in a tree
	all_trees = []  # Track the actual node sets for each tree

	def find_root_by_following_parents(start_node):
		"""Follow parents upward until hitting a self-ruling node or cycle. Returns the root node."""
		visited = set()
		current = start_node
		path = []
		
		while True:
			if current in visited:
				# Hit a cycle - return the node with most children in the cycle
				cycle_start_idx = path.index(current)
				cycle_nodes = path[cycle_start_idx:]
				# Pick the node in the cycle with the most children
				best = max(cycle_nodes, key=lambda n: len(children_by_parent.get(n, [])))
				return best
			
			visited.add(current)
			path.append(current)
			
			# Get parents (rulers) of current node
			parents = parents_by_child.get(current, [])
			
			# Filter out self-loops
			parents = [p for p in parents if p != current]
			
			if not parents:
				# No parents - this is a self-ruling node or true root
				return current
			
			# Continue following the first parent
			current = parents[0]

	def collect_tree_downward(start_node):
		"""Collect all nodes reachable downward from start_node."""
		component = set()
		queue = [start_node]
		while queue:
			n = queue.pop(0)
			if n in component:
				continue
			component.add(n)
			queue.extend(children_by_parent.get(n, []))
		return component
	
	def collect_connected_component(start_node):
		"""Collect all nodes connected to start_node (both upward and downward in the graph)."""
		# Build a bidirectional graph from parent->child relationships
		neighbors = {}
		for parent, child in raw_links:
			neighbors.setdefault(parent, []).append(child)
			neighbors.setdefault(child, []).append(parent)
		
		# BFS to find all connected nodes
		component = set()
		queue = [start_node]
		while queue:
			n = queue.pop(0)
			if n in component:
				continue
			component.add(n)
			queue.extend(neighbors.get(n, []))
		return component

	# === PHASE 1: Find roots by following parents upward from all nodes ===
	print("\n🔵 PHASE 1: Finding roots by following parents upward...")
	potential_roots = set()
	for node in all_nodes:
		root = find_root_by_following_parents(node)
		potential_roots.add(root)
		print(f"   {node} → root: {root}")
	
	print(f"\n   Potential roots found: {sorted(potential_roots)}")
	
	# For each root, collect its full tree using DOWNWARD traversal only (not bidirectional)
	for root in sorted(potential_roots):
		if root in accounted_for:
			continue
		
		tree_nodes = collect_tree_downward(root)
		all_trees.append(tree_nodes)
		accounted_for.update(tree_nodes)
		roots.append(root)
		print(f"   ✅ Root: {root} → tree size: {len(tree_nodes)}")

	# === OLD PHASE 1: Sovereign trees ===
	print("\n🔵 OLD PHASE 1: Building sovereign trees...")
	print(f"   All sovereigns: {sovereigns}")
	sovereign_parents = [s for s in sovereigns if s in children_by_parent and len(children_by_parent.get(s, [])) > 0]
	print(f"   Sovereign parents (have children): {sovereign_parents}")
	print(f"   Children counts: {[(s, len(children_by_parent.get(s, []))) for s in sovereign_parents]}")
	
	# Sort sovereigns by most children (most dominant first)
	sovereign_parents.sort(key=lambda s: (-len(children_by_parent.get(s, [])), s))
	print(f"   After sorting (most children first): {sovereign_parents}")
	
	for sov in sovereign_parents:
		# Check if this sovereign is already in any existing tree
		if any(sov in tree for tree in all_trees):
			print(f"   ⏭️  Skipping {sov} (already in another tree)")
			continue
		
		tree_nodes = collect_tree_downward(sov)
		print(f"   Tree nodes for {sov}: {tree_nodes}")
		all_trees.append(tree_nodes)
		accounted_for.update(tree_nodes)
		roots.append(sov)
		print(f"   ✅ Sovereign root: {sov} → tree size: {len(tree_nodes)}")
		print(f"   Total accounted for so far: {len(accounted_for)} nodes")

	# === PHASE 2: Self-ruling trees (not yet accounted for) ===
	print("\n🟡 PHASE 2: Building self-ruling trees...")
	self_ruling_parents = [s for s in self_ruling 
	                       if s in children_by_parent 
	                       and len(children_by_parent.get(s, [])) > 0
	                       and s not in accounted_for]
	
	# Sort self-ruling by most children (most dominant), then alphabetical
	self_ruling_parents.sort(key=lambda s: (-len(children_by_parent.get(s, [])), s))
	
	for sr in self_ruling_parents:
		# Check if this self-ruling planet is already in any existing tree
		if any(sr in tree for tree in all_trees):
			print(f"   ⏭️  Skipping {sr} (already in another tree)")
			continue
		
		tree_nodes = collect_tree_downward(sr)
		all_trees.append(tree_nodes)
		accounted_for.update(tree_nodes)
		roots.append(sr)
		print(f"   ✅ Self-ruling root: {sr} → tree size: {len(tree_nodes)}")

	# === PHASE 3: Fallback for any remaining unaccounted nodes ===
	print("\n⚪ PHASE 3: Handling remaining nodes...")
	remaining_nodes = list(all_nodes - accounted_for)
	
	print(f"   Remaining nodes ({len(remaining_nodes)}): {remaining_nodes}")
	
	# Group remaining nodes into connected components
	processed_in_phase3 = set()
	
	while remaining_nodes:
		# Pick the first unprocessed node as a starting point
		start_node = remaining_nodes[0]
		
		if start_node in processed_in_phase3:
			remaining_nodes.pop(0)
			continue
		
		# Find ALL nodes connected to this one (bidirectionally), not just unaccounted ones
		full_component = collect_connected_component(start_node)
		
		# Filter to only unaccounted nodes
		component_unaccounted = full_component - accounted_for
		
		if not component_unaccounted:
			remaining_nodes.pop(0)
			continue
		
		print(f"   Found connected component with {len(component_unaccounted)} unaccounted nodes: {component_unaccounted}")
		
		# Choose the best root for this component from the unaccounted nodes:
		# 1. Prefer nodes with children (parents) over childless nodes
		# 2. Among parents, prefer those with most children
		# 3. Tie-break alphabetically
		candidates = sorted(
			component_unaccounted,
			key=lambda n: (
				0 if n in children_by_parent and len(children_by_parent.get(n, [])) > 0 else 1,
				-len(children_by_parent.get(n, [])),
				n
			)
		)
		
		best_root = candidates[0]
		print(f"   Chose root: {best_root} (has {len(children_by_parent.get(best_root, []))} children)")
		
		# Store this tree with ALL unaccounted nodes in the component
		all_trees.append(component_unaccounted)
		accounted_for.update(component_unaccounted)
		roots.append(best_root)
		processed_in_phase3.update(component_unaccounted)
		
		# Remove all nodes in this component from remaining_nodes
		remaining_nodes = [n for n in remaining_nodes if n not in component_unaccounted]
		
		print(f"   ✅ Fallback root: {best_root} → tree size: {len(component_unaccounted)}")
		print(f"   Total accounted: {len(accounted_for)}/{len(all_nodes)}")

	# === VALIDATION: Ensure all nodes are accounted for ===
	missing_nodes = all_nodes - accounted_for
	if missing_nodes:
		print(f"\n⚠️  WARNING: {len(missing_nodes)} nodes not accounted for: {missing_nodes}")
		print("   Adding them as individual trees...")
		for node in sorted(missing_nodes):
			roots.append(node)
			all_trees.append({node})
			accounted_for.add(node)
	else:
		print(f"\n✅ All {len(all_nodes)} nodes accounted for in {len(roots)} tree(s)")


	# --- Guard in case no roots found ---
	if not roots:
		print("No roots found. Cannot plot trees.")
		return None

	n = len(roots)
	
	# PHASE 0: Count nodes in each tree to calculate scaling factors
	print(f"\n📊 Counting nodes in {n} tree(s)...")
	tree_node_counts = []
	for tree_idx, root in enumerate(roots):
		tree_nodes = all_trees[tree_idx]
		tree_node_counts.append(len(tree_nodes))
	
	max_nodes = max(tree_node_counts) if tree_node_counts else 1
	print(f"   Tree node counts: {tree_node_counts}, max: {max_nodes}")
	
	# PHASE 1: Position all trees and calculate their extents
	all_tree_data = []
	
	for tree_idx, root in enumerate(roots):
		# Get the set of nodes that should be in this tree
		tree_nodes = all_trees[tree_idx]
		
		# Build a parent->children map ONLY for nodes in this tree
		tree_children_map = {}
		for parent, child in raw_links:
			if parent in tree_nodes and child in tree_nodes:
				tree_children_map.setdefault(parent, []).append(child)
		
		# Also build a reverse map (child->parents) to handle mutual reception
		tree_parents_map = {}
		for parent, child in raw_links:
			if parent in tree_nodes and child in tree_nodes:
				tree_parents_map.setdefault(child, []).append(parent)
		
		nodes = []          # list of tuples (name, node_id)
		edges = []          # list of tuples (parent_id, child_id)
		level_nodes = {}    # level -> ordered list of node_ids (no duplicates)
		queue = [(root, f"{root}_0", 0)]  # (name, unique_id, level)

		visited_names = set([root])  # track which planet NAMES we've added
		visited_ids = set([f"{root}_0"])  # track unique node IDs to prevent infinite loops
		processed_pairs = set()  # track (parent_name, child_name) pairs to prevent reprocessing

		while queue:
			parent_name, parent_id, level = queue.pop(0)

			nodes.append((parent_name, parent_id))
			level_nodes.setdefault(level, [])
			if parent_id not in level_nodes[level]:
				level_nodes[level].append(parent_id)

			# Process children (downward edges)
			children = tree_children_map.get(parent_name, [])
			for i, child in enumerate(children):
				# Skip if we've already processed this parent->child relationship
				if (parent_name, child) in processed_pairs:
					continue
				processed_pairs.add((parent_name, child))
				
				child_id = f"{child}_{level+1}_{i}"

				# Prevent infinite recursion while still allowing repeats at different levels
				if child_id in visited_ids:
					continue
				visited_ids.add(child_id)
				visited_names.add(child)

				edges.append((parent_id, child_id))
				queue.append((child, child_id, level+1))
				level_nodes.setdefault(level+1, [])
				if child_id not in level_nodes[level+1]:
					level_nodes[level+1].append(child_id)

		if not nodes:
			continue

		# Calculate dynamic spacing based on tree size relative to largest tree
		num_nodes = len(tree_nodes)  # Use tree_nodes (actual count) not nodes (includes duplicates)
		# Gentler scaling: interpolate between 0.85 and 1.0
		raw_scale = num_nodes / max_nodes
		scale_factor = 0.85 + (0.15 * raw_scale)  # Scale ranges from 0.85 to 1.0
		
		# Scale spacing
		min_spacing = 5.0 * scale_factor
		vertical_gap = 2.0 * scale_factor
		
		# Simple node-count-based sizing (like original code)
		if num_nodes <= 5:
			label_fontsize = 9
			symbol_fontsize = 12
			circle_size = 2000
		elif num_nodes <= 15:
			label_fontsize = 11
			symbol_fontsize = 13
			circle_size = 2000
		elif num_nodes <= 20:
			label_fontsize = 12
			symbol_fontsize = 14
			circle_size = 3000
		elif num_nodes <= 25:
			label_fontsize = 11
			symbol_fontsize = 13
			circle_size = 3000
		else:
			label_fontsize = 8
			symbol_fontsize = 10
			circle_size = 900
		
		print(f"   Tree {tree_idx} ({root}): {num_nodes} nodes, scale={scale_factor:.3f}")
		print(f"      min_spacing={min_spacing:.3f}, vertical_gap={vertical_gap:.3f}")
		print(f"      circle_size={circle_size:.0f}, label_fontsize={label_fontsize}")
		
		subtree_gap = -min_spacing * 1  # Negative gap to bring siblings closer
		
		# Build parent->children map for this tree
		tree_edges = {}
		for parent_id, child_id in edges:
			tree_edges.setdefault(parent_id, []).append(child_id)
		
		# Position nodes level by level, centering children under parents
		pos = {}
		next_x_by_level = {}  # track next available x position per level
		
		def position_subtree(node_id, parent_x=None):
			"""Position node and its descendants, returning the node's final x position."""
			level = next(lev for lev, ids in level_nodes.items() if node_id in ids)
			children = tree_edges.get(node_id, [])
			
			if not children:
				# Leaf node: place at next available position
				x = next_x_by_level.get(level, 0.0)
				pos[node_id] = (x, -level * vertical_gap)
				next_x_by_level[level] = x + min_spacing
				return x
			else:
				# Internal node: position children one by one
				child_positions = []
				for child in children:
					# Position this child subtree
					child_x = position_subtree(child, parent_x=None)
					child_positions.append(child_x)
					
					# After positioning child, find rightmost node in its subtree and update tracker
					def update_tracker_for_subtree(nid):
						if nid in pos:
							node_level = next(lev for lev, ids in level_nodes.items() if nid in ids)
							node_x = pos[nid][0]
							next_x_by_level[node_level] = max(
								next_x_by_level.get(node_level, -float('inf')),
								node_x + min_spacing
							)
						for c in tree_edges.get(nid, []):
							update_tracker_for_subtree(c)
					
					# Update tracker based on final positions in this child's subtree
					update_tracker_for_subtree(child)
				
				# Parent centers over its children's actual final positions
				leftmost_child = min(child_positions)
				rightmost_child = max(child_positions)
				x = (leftmost_child + rightmost_child) / 2.0
				
				# Ensure parent doesn't collide with other nodes at its level
				min_x = next_x_by_level.get(level, -float('inf'))
				if x < min_x:
					# Need to shift: calculate how much and shift the whole subtree
					shift = min_x - x
					x = min_x
					
					# Shift all descendants that were already positioned
					def shift_subtree(nid, dx):
						if nid in pos:
							old_x, old_y = pos[nid]
							pos[nid] = (old_x + dx, old_y)
						for c in tree_edges.get(nid, []):
							shift_subtree(c, dx)
					
					for child in children:
						shift_subtree(child, shift)
					
					# After shifting, update tracker again for all children
					for child in children:
						update_tracker_for_subtree(child)
				
				pos[node_id] = (x, -level * vertical_gap)
				
				# Add extra spacing after parent nodes to separate subtree groups
				next_x_by_level[level] = x + min_spacing + subtree_gap
				return x
		
		# Start positioning from root
		root_id = f"{root}_0"
		position_subtree(root_id)

		root_id = f"{root}_0"
		if root_id not in pos:
			pos[root_id] = (0.0, 0.0)
		
		# COMPACTION PHASE: Pack childless siblings into gaps between parent siblings
		# For each parent node, compact its direct children
		def compact_children(parent_id):
			"""Reposition childless children to fill gaps between parent children."""
			children = tree_edges.get(parent_id, [])
			if len(children) <= 1:
				return  # nothing to compact
			
			# Separate children into parents (have their own children) and leaves (no children)
			parent_children = [cid for cid in children if tree_edges.get(cid)]
			leaf_children = [cid for cid in children if not tree_edges.get(cid)]
			
			if not parent_children or not leaf_children:
				return  # need both types to compact
			
			# Sort parent children by x position
			parent_children.sort(key=lambda cid: pos[cid][0])
			
			# Sort leaf children by current x position to maintain relative order
			leaf_children.sort(key=lambda cid: pos[cid][0])
			
			# Get the level of these children (all siblings are at same level)
			child_level = next(lev for lev, ids in level_nodes.items() if children[0] in ids)
			
			# Collect ALL nodes at this level to check for collisions
			all_nodes_at_level = [(nid, pos[nid][0]) for nid in level_nodes.get(child_level, []) if nid in pos]
			all_nodes_at_level.sort(key=lambda x: x[1])  # sort by x position
			
			# Calculate total gap space between all parent children
			gaps = []
			total_gap_space = 0
			for i in range(len(parent_children) - 1):
				left_child = parent_children[i]
				right_child = parent_children[i + 1]
				left_x = pos[left_child][0]
				right_x = pos[right_child][0]
				gap_size = right_x - left_x - min_spacing
				# Only use gaps that can fit at least one leaf with proper spacing
				if gap_size >= min_spacing * 1.5:  # Relaxed threshold
					gaps.append({
						'left_x': left_x,
						'right_x': right_x,
						'size': gap_size
					})
					total_gap_space += gap_size
			
			if not gaps:
				return  # no gaps to fill
			
			# Distribute leaves evenly across all gaps
			num_leaves = len(leaf_children)
			leaf_idx = 0
			
			for gap in gaps:
				# Calculate how many leaves should go in this gap (proportional to gap size)
				gap_proportion = gap['size'] / total_gap_space
				leaves_for_gap = max(1, round(num_leaves * gap_proportion))
				
				# Don't exceed remaining leaves
				leaves_for_gap = min(leaves_for_gap, num_leaves - leaf_idx)
				
				if leaves_for_gap == 0:
					continue
				
				# Evenly space the leaves in this gap
				gap_start = gap['left_x'] + min_spacing
				gap_end = gap['right_x']
				available_space = gap_end - gap_start
				
				# Ensure we have enough space for the leaves with minimum spacing
				required_space = leaves_for_gap * min_spacing
				if available_space < required_space:
					# Adjust number of leaves to fit
					leaves_for_gap = max(1, int(available_space / min_spacing))
				
				spacing = available_space / (leaves_for_gap + 1)
				# Don't let spacing go below min_spacing
				spacing = max(spacing, min_spacing * 0.8)
				
				for i in range(leaves_for_gap):
					if leaf_idx >= num_leaves:
						break
					leaf_id = leaf_children[leaf_idx]
					new_x = gap_start + spacing * (i + 1)
					
					# CRITICAL: Check if this position would overlap with any existing node
					collision = False
					for other_id, other_x in all_nodes_at_level:
						if other_id != leaf_id and abs(new_x - other_x) < min_spacing * 0.9:
							collision = True
							break
					
					if not collision:
						old_x, y = pos[leaf_id]
						pos[leaf_id] = (new_x, y)
					# If collision, keep original position
					
					leaf_idx += 1
				
				if leaf_idx >= num_leaves:
					break
		
		# COMPACTION PHASE: Pack childless siblings into gaps between parent siblings
		# Always apply compaction, but respect min_spacing
		for node_id in pos.keys():
			if tree_edges.get(node_id):  # is a parent
				compact_children(node_id)

		# Calculate tree extent
		x_coords = [p[0] for p in pos.values()]
		y_coords = [p[1] for p in pos.values()]
		tree_width = max(x_coords) - min(x_coords) if x_coords else 0
		tree_height = max(y_coords) - min(y_coords) if y_coords else 0
		
		# Store all data for this tree
		all_tree_data.append({
			'root': root,
			'nodes': nodes,
			'edges': edges,
			'pos': pos,
			'label_fontsize': label_fontsize,
			'symbol_fontsize': symbol_fontsize,
			'circle_size': circle_size,
			'width': tree_width,
			'height': tree_height
		})
	
	# Count planet occurrences across all trees to detect duplicates (dual rulership)
	for tree_data in all_tree_data:
		for name, node_id in tree_data['nodes']:
			planet_occurrences[name] = planet_occurrences.get(name, 0) + 1
	
	# Identify planets that appear more than once
	duplicated_planets = {name for name, count in planet_occurrences.items() if count > 1}
	print(f"🔶 Duplicated planets (dual rulership): {sorted(duplicated_planets)}")
	
	# PHASE 2: Create figure with proper size based on actual tree extents
	tree_widths = [td['width'] for td in all_tree_data]
	tree_heights = [td['height'] for td in all_tree_data]
	
	print(f"\n📐 Tree extents: widths={[f'{w:.1f}' for w in tree_widths]}, heights={[f'{h:.1f}' for h in tree_heights]}")
	
	# Use a fixed, reasonable figure size that's not based on data width
	# Data widths can be large due to spacing, but we don't want huge figures
	fig_width = 8 * n  # 8 inches per tree - reasonable and consistent
	fig_height = 10     # 10 inches tall
	
	print(f"   Calculated figure size: {fig_width:.1f}\" × {fig_height:.1f}\"")
	
	# Use GridSpec to control subplot widths proportionally
	import matplotlib.gridspec as gridspec
	
	# Calculate width ratios based on tree widths
	max_width = max(tree_widths) if tree_widths else 1
	width_ratios = [w / max_width for w in tree_widths]
	print(f"   Width ratios: {[f'{w:.2f}' for w in width_ratios]}")
	
	fig = plt.figure(figsize=(fig_width, fig_height))
	gs = gridspec.GridSpec(1, n, figure=fig, width_ratios=width_ratios, wspace=0.15)
	axes = [fig.add_subplot(gs[0, i]) for i in range(n)]
	
	# PHASE 3: Render all trees
	# First, calculate the maximum y-range needed across all trees
	max_height = max(tree_heights) if tree_heights else 10
	
	for ax, tree_data in zip(axes, all_tree_data):
		nodes = tree_data['nodes']
		edges = tree_data['edges']
		pos = tree_data['pos']
		label_fontsize = tree_data['label_fontsize']
		symbol_fontsize = tree_data['symbol_fontsize']
		circle_size = tree_data['circle_size']
		
		for name, node_id in nodes:
			xy = pos.get(node_id)
			if xy is None:
				xy = (0.0, 0.0)
				pos[node_id] = xy
			
			# Color logic with support for dual colors (orange + purple)
			is_sovereign = name in sovereigns
			is_duplicated = name in duplicated_planets
			is_in_loop = name in mutual_reception_loops
			
			# Determine color(s)
			if is_sovereign:
				color = "#59A54A"
				ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
			elif is_duplicated and is_in_loop:
				# Both orange and purple - draw concentric circles
				# Outer circle (orange) at full size
				ax.scatter(xy[0], xy[1], s=circle_size, c="#FF8656", zorder=2)
				# Inner circle (purple) at 60% size
				ax.scatter(xy[0], xy[1], s=circle_size * 0.6, c="#B386D8", zorder=3)
			elif is_duplicated:
				color = "#FF8656"
				ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
			elif is_in_loop:
				color = "#B386D8"
				ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
			else:
				color = "#5F6FFF"
				ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
			
			display_name = get_display_name(name)
			ax.text(xy[0], xy[1], display_name, ha='center', va='center', fontsize=label_fontsize, fontweight="bold", zorder=4)
			
			# Add circular arrow symbol below the planet name for self-ruling planets
			if name in self_ruling or name in sovereigns:
				# Position arrow directly below the text, tucked close
				ax.text(xy[0], xy[1] - 0.08, "↻", ha='center', va='top', 
				        fontsize=symbol_fontsize, color='black', zorder=3)

		for parent_id, child_id in edges:
			start = pos.get(parent_id)
			end = pos.get(child_id)
			if start is None or end is None:
				continue
			ax.annotate(
				"",
				xy=end,
				xytext=start,
				arrowprops=dict(arrowstyle="-|>", color="black", lw=1.8),
				zorder=1
			)

		# Set axis limits - shared y-scale for consistent sizing
		if pos:
			x_coords = [p[0] for p in pos.values()]
			y_coords = [p[1] for p in pos.values()]
			x_min, x_max = min(x_coords), max(x_coords)
			y_min, y_max = min(y_coords), max(y_coords)
			
			# X-axis: use this tree's actual width
			x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
			ax.set_xlim(x_min - x_pad, x_max + x_pad)
			
			# Y-axis: use SHARED scale based on largest tree
			# Align all trees to the top (max y) instead of centering
			y_range = max_height
			ax.set_ylim(y_max - y_range - 1, y_max + 1)

		ax.axis("off")

	# Remove tight_layout which creates excessive margins
	# Use subplots_adjust to minimize whitespace
	plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02, wspace=0.1)
	return fig

def build_dispositor_tables(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
	"""
	Returns two UI-ready tables:
	  chains_rows  : (unused, kept for API compatibility)
	  summary_rows : [{"Scope":"...", "Final":"...", "Dominant":"...", "Sovereign":"...", "Loops":"...", "Chains":"..."}, ...]
	"""
	# objects → longitude (exclude cusps)
	objs = df[~df["Object"].str.contains("cusp", case=False, na=False)]
	pos = dict(zip(objs["Object"], objs["Longitude"]))

	def _cusps(label: str) -> list[float]:
		vals = []
		for h in range(1, 13):
			m = df.loc[df["Object"] == f"{label} {h}H cusp", "Longitude"]
			if not m.empty:
				vals.append(float(m.iloc[0]) % 360.0)
		return vals if len(vals) == 12 else []

	scopes = [
		("Sign", []),
		("Placidus", _cusps("Placidus")),
		("Equal", _cusps("Equal")),
		("Whole Sign", _cusps("Whole Sign")),
	]

	chains_rows: list[dict] = []
	summary_rows: list[dict] = []

	for name, cusps in scopes:
		res   = analyze_dispositors(pos, cusps)
		scope = res["by_sign"] if name == "Sign" else res["by_house"]

		# Loops: list[list[str]] → "A → B → C | X → Y"
		loops_list = scope.get("loops", []) or []
		loops_fmt  = " | ".join(" → ".join(loop) for loop in loops_list)

		# Chains: list[str] with "A rules B rules C" → "A → B → C | ..."
		chains_list = scope.get("chains", []) or []
		chains_fmt = " | ".join(" → ".join(s) for s in chains_list)

		summary_rows.append({
			"Scope": name,
			"Final": ", ".join(scope.get("final_dispositors", []) or []),
			"Dominant": ", ".join(scope.get("dominant_rulers", []) or []),
			"Sovereign": ", ".join(scope.get("sovereign", []) or []),
			"Loops": loops_fmt,
			"Chains": chains_fmt,   # <-- NEW
		})

	return chains_rows, summary_rows

import networkx as nx

def build_dispositor_trees(disp_data):
	"""
	Build clean, deduped trees for each final dispositor.
	disp_data: dict returned by analyze_dispositors(pos, cusps)
	Returns: dict mapping final_dispositor name → networkx.DiGraph
	"""

	# Grab the final dispositors from the "by_sign" key
	final_dispositors = disp_data.get("by_sign", {}).get("final_dispositors", [])
	chains = disp_data.get("by_sign", {}).get("chains", [])

	# Build a ruler → children mapping
	ruler_map = {}
	for chain in chains:
		# convert "A rules B rules C" → ["A", "B", "C"]
		nodes = [n.strip() for n in chain.split("rules")]
		for i in range(len(nodes)-1):
			parent, child = nodes[i], nodes[i+1]
			ruler_map.setdefault(parent, set()).add(child)
		# ensure last node exists in ruler_map
		ruler_map.setdefault(nodes[-1], set())

	# ---- DEBUG: Check the parent → children mapping ----
	print("RULER MAP:", ruler_map)

	trees = {}

	def add_children(G, node, visited):
		"""Recursively add children of node into graph G, following your rules"""
		if node in visited:
			return
		visited.add(node)

		children = ruler_map.get(node, set())
		for child in children:
			G.add_edge(node, child)
			# recurse, but only iterate each child once per tree
			add_children(G, child, visited)

	# Build a tree per final dispositor
	for root in final_dispositors:
		G = nx.DiGraph()
		G.add_node(root)
		# self-loop if node rules itself
		if root in ruler_map.get(root, set()):
			G.add_edge(root, root)
		add_children(G, root, visited=set())
		trees[root] = G

	return trees

def _resolve_dignity(obj: str, sign_name: str):
	"""
	Your DIGNITIES is keyed by sign name:
		DIGNITIES["Capricorn"]["domicile"] == ["Saturn"]
	Return one of: 'domicile', 'exaltation', 'detriment', 'fall' or None.
	"""
	m = DIGNITIES.get(sign_name)
	if not isinstance(m, dict):
		return None

	# If your row/object includes “(Mean)”, strip those suffixes for matching
	import re
	base_obj = re.sub(r"\s*\(.*?\)\s*$", "", obj).strip()

	for label in ("domicile", "exaltation", "detriment", "fall"):
		lst = m.get(label) or []
		if isinstance(lst, (list, tuple, set)) and base_obj in lst:
			return label
	return None

# === Aspect helpers & builders ===
_SEPTILE  = 51 + 26/60
_BISEPT   = 102 + 52/60
_TRISEPT  = 154 + 17/60

_ASPECTS_MAJOR = {
	"Conjunction":   {"angle": 0,   "orb": 4},  # minor, kept here for unified scan; we'll sort into minors later
	"Sextile":       {"angle": 60,  "orb": 3},
	"Square":        {"angle": 90,  "orb": 3},
	"Trine":         {"angle": 120, "orb": 3},
	"Opposition":    {"angle": 180, "orb": 3},
}

# Minor-only set (we'll classify major vs minor after detection)
_ASPECTS_MINOR = {
	"Sesquisquare":  {"angle": 135, "orb": 2},   # 135°
	"Quincunx":      {"angle": 150, "orb": 3},
	"Semi-square":   {"angle": 45,   "orb": 2},
	"Quintile":      {"angle": 72,   "orb": 2},
	"Biquintile":    {"angle": 144,  "orb": 2},
	"Septile":       {"angle": _SEPTILE,  "orb": 2},
	"Biseptile":     {"angle": _BISEPT,   "orb": 2},
	"Triseptile":    {"angle": _TRISEPT,  "orb": 2},
	"Semisextile":  {"angle": 30,  "orb": 2}, 
}

# One combined lookup for detection pass
_ASPECTS_ALL = {**_ASPECTS_MAJOR, **_ASPECTS_MINOR}

# Which names count as "major" for output bucketing
_MAJOR_NAMES = {"Conjunction", "Sextile", "Square", "Trine", "Opposition"}
_MINOR_NAMES = set(_ASPECTS_ALL.keys()) - _MAJOR_NAMES

def _norm360(x: float) -> float:
	"""Normalize degrees to [0, 360)."""
	return x % 360.0

def _sep_deg(a: float, b: float) -> float:
	"""Unsigned separation 0..180 (smallest arc)."""
	d = abs(_norm360(a) - _norm360(b)) % 360.0
	return d if d <= 180.0 else 360.0 - d

def _distance_to_target(a: float, b: float, target: float) -> float:
	"""Unsigned distance from the pair separation to the target aspect angle."""
	return abs(_sep_deg(a, b) - target)

def _within_orb(a: float, b: float, target: float, orb: float) -> tuple[bool, float]:
	"""Return (hit?, orb_delta) where orb_delta >= 0 is the absolute difference from exact."""
	delta = _distance_to_target(a, b, target)
	return (delta <= orb, delta)

def _fmt_orb(delta: float) -> str:
	# Keep one decimal by default; adjust if you prefer integer rounding
	return f"{delta:.1f}°"

def _applying_or_separating(
	lon1: float, speed1: float,
	lon2: float, speed2: float,
	target: float
) -> str:
	"""
	Heuristic: look one day ahead using current speeds (already in deg/day)
	and see whether the distance-to-target decreases (Applying) or increases (Separating).
	Speeds are used internally only (not added to the table).
	"""
	now = _distance_to_target(lon1, lon2, target)
	# Predict a simple next-step separation using linear motion
	lon1_next = _norm360(lon1 + speed1)   # ~1 day
	lon2_next = _norm360(lon2 + speed2)
	nxt = _distance_to_target(lon1_next, lon2_next, target)
	return "Applying" if nxt < now else "Separating"

def _extract_object_rows(df: pd.DataFrame) -> pd.DataFrame:
	"""
	Return only the rows that represent objects (no cusps).
	We treat anything with 'cusp' in the Object name as a cusp row.
	"""
	objs = df[~df["Object"].str.contains("cusp", case=False, na=False)].copy()
	return objs

def build_aspect_table(df: pd.DataFrame) -> pd.DataFrame:
	"""
	Build a top-left triangular aspect matrix:
	  - Rows & columns are the object names (no cusps)
	  - (row == col) shows 'X'
	  - Only the TOP-LEFT half is filled; the BOTTOM-RIGHT half is blank
		so the last/bottom row has only the very first cell filled, and
		the last/far-right column has only the top cell filled.

	Cells show: "<AspectName> (<orb°>)" or blank if no aspect in orb.
	Applying/separating is not printed here to keep the matrix compact.
	"""
	objs = _extract_object_rows(df)
	names = list(objs["Object"])
	lons  = dict(zip(objs["Object"], objs["Longitude"]))
	spds  = dict(zip(objs["Object"], objs["Speed"]))  # for edges helper

	n = len(names)
	data = []

	# We'll fill only cells where (j <= n - i - 1) in 0-based indexing
	# (i.e., upper-left triangle relative to the anti-diagonal).
	for i, rname in enumerate(names):
		row_vals = []
		for j, cname in enumerate(names):
			# "X" on diagonal only if we're inside the filled half; otherwise blank
			if i == j:
				# Check anti-diagonal rule: j <= n - i - 1
				if j <= (n - i - 1):
					row_vals.append("X")
				else:
					row_vals.append("")
				continue

			# Enforce top-left half fill:
			if j > (n - i - 1):
				row_vals.append("")  # bottom-right kept blank
				continue

			A = lons[rname]
			B = lons[cname]
			best_hit = ""
			best_delta = None
			best_name = None

			# Scan all aspects & pick the closest that lands within its orb
			for name, spec in _ASPECTS_ALL.items():
				target = spec["angle"]
				orb    = spec["orb"]
				hit, delta = _within_orb(A, B, target, orb)
				if not hit:
					continue
				if best_delta is None or delta < best_delta:
					best_delta = delta
					best_name  = name

			if best_name is None:
				row_vals.append("")
			else:
				row_vals.append(f"{best_name} ({_fmt_orb(best_delta)})")

		data.append(row_vals)

	return pd.DataFrame(data, index=names, columns=names)

def build_aspect_edges(df: pd.DataFrame) -> tuple[list[tuple], list[tuple]]:
	"""
	Return (edges_major, edges_minor), each as a list of tuples:
	  (obj1, obj2, {
		  "aspect": <name>,
		  "orb": <float>,                 # absolute orb (deg)
		  "appsep": "Applying"|"Separating",
		  "applying": bool,               # NEW: True if applying
		  "decl_diff": <float|None>,      # NEW: |decl1 - decl2| in deg
	  })
	Pairs are de-duplicated (A,B) only once (A < B by index).
	"""
	objs  = _extract_object_rows(df)
	names = list(objs["Object"])
	lons  = dict(zip(objs["Object"], objs["Longitude"]))
	spds  = dict(zip(objs["Object"], objs["Speed"]))
	decls = dict(zip(objs["Object"], objs["Declination"]))  # for decl_diff

	edges_major: list[tuple] = []
	edges_minor: list[tuple] = []

	for i in range(len(names)):
		for j in range(i + 1, len(names)):  # de-duplicate: only upper pairs
			a = names[i]; b = names[j]
			A, B   = lons[a], lons[b]
			sA, sB = spds[a], spds[b]

			best_delta = None
			best_name  = None
			best_target = None

			for name, spec in _ASPECTS_ALL.items():
				hit, delta = _within_orb(A, B, spec["angle"], spec["orb"])
				if not hit:
					continue
				if best_delta is None or delta < best_delta:
					best_delta  = delta
					best_name   = name
					best_target = spec["angle"]

			if best_name is None:
				continue

			appsep = _applying_or_separating(A, sA, B, sB, best_target)

			# Declination difference (absolute degrees), if both present
			dA = decls.get(a); dB = decls.get(b)
			decl_diff = float(f"{abs(float(dA) - float(dB)):.3f}") if dA is not None and dB is not None else None

			meta = {
				"aspect": best_name,
				"orb": float(f"{best_delta:.3f}"),
				"appsep": appsep,                        # "Applying" or "Separating"
				"applying": (appsep == "Applying"),     # NEW boolean
				"decl_diff": decl_diff,                 # NEW declination difference
			}
			record = (a, b, meta)

			if best_name in _MAJOR_NAMES:
				edges_major.append(record)
			else:
				edges_minor.append(record)

	return edges_major, edges_minor

def _sign_to_index(sign_name: str) -> int | None:
	"""Return 0..11 for Aries..Pisces using your SIGNS list."""
	try:
		return SIGNS.index(sign_name)
	except Exception:
		return None

# Reception aspects we consider (the five mapped by sign-distance)
_RECEPTION_ASPECTS = {
	"Conjunction": 0,
	"Sextile": 60,
	"Square": 90,
	"Trine": 120,
	"Opposition": 180,
}
_RECEPTION_ASPECT_NAMES = set(_RECEPTION_ASPECTS.keys())

def _aspect_name_for_sign_distance(d: int) -> str | None:
	"""
	Sign-distance mapping (0..6) → name.
	  0 -> Conjunction
	  2 -> Sextile
	  3 -> Square
	  4 -> Trine
	  6 -> Opposition
	"""
	return {
		0: "Conjunction",
		2: "Sextile",
		3: "Square",
		4: "Trine",
		6: "Opposition",
	}.get(d)

def _sign_distance(i: int, j: int) -> int:
	"""
	Modular distance on 12-sign circle (0..6).
	"""
	d = abs(i - j)
	return d if d <= 6 else 12 - d

def annotate_reception(df: pd.DataFrame, edges_major: list[tuple]) -> pd.DataFrame:
	"""
	Sign-only Reception (no house reception).
	Uses supplied edges_major (no aspect recalculation).

	Outputs all matching receptions to all rulers, e.g.:
	  "Opposite Mars, Conjunct Pluto"
	For sign-distance fallback, appends " (by sign)" per item.
	Suppresses self-conjunction (planet conjunct itself in domicile).
	"""
	out = df.copy()

	# Objects only & quick lookups
	objs_only = out[~out["Object"].str.contains("cusp", case=False, na=False)].copy()
	name_to_sign = dict(zip(objs_only["Object"], objs_only["Sign"]))
	name_set = set(name_to_sign.keys())

	# Aspect display mapping for wording tweaks
	_DISPLAY = {"Conjunction": "Conjunct", "Opposition": "Opposite"}
	def _disp(aspect_name: str) -> str:
		return _DISPLAY.get(aspect_name, aspect_name)

	# Build lookup from supplied edges_major
	pair_to_aspect = {}
	for a, b, meta in edges_major:
		asp = meta.get("aspect")
		if asp in _RECEPTION_ASPECT_NAMES:  # {"Conjunction","Sextile","Square","Trine","Opposition"}
			pair_to_aspect[tuple(sorted((a, b)))] = asp

	results = []
	for _, row in out.iterrows():
		obj = row.get("Object", "")
		if "cusp" in str(obj).lower():
			results.append("")
			continue

		sign = row.get("Sign", "")
		rulers = lookup_sign_rulers(sign, PLANETARY_RULERS) or []

		# Collect *all* receptions across all rulers
		found_items = []
		for ruler in rulers:
			if ruler not in name_set:
				continue  # ruler not present among objects

			# --- by ORB (preferred) using supplied edges ---
			key = tuple(sorted((obj, ruler)))
			aspname = pair_to_aspect.get(key)
			if aspname in _RECEPTION_ASPECT_NAMES:
				# suppress self-conjunction
				if obj == ruler and aspname == "Conjunction":
					pass  # skip
				else:
					found_items.append(f"{_disp(aspname)} {ruler}")
				continue  # don't also add a by-sign fallback for this ruler

			# --- by SIGN (fallback) using modular sign distance ---
			obj_si = _sign_to_index(sign)
			ruler_sign = name_to_sign.get(ruler, "")
			rul_si = _sign_to_index(ruler_sign)
			if obj_si is None or rul_si is None:
				continue

			dist = _sign_distance(obj_si, rul_si)  # 0..6
			sign_aspect = _aspect_name_for_sign_distance(dist)
			if sign_aspect is not None:
				# suppress self-conjunction
				if obj == ruler and sign_aspect == "Conjunction":
					pass  # skip
				else:
					found_items.append(f"{_disp(sign_aspect)} {ruler} (by sign)")

		results.append(", ".join(found_items) if found_items else "")

	out["Reception"] = results
	return out

def build_conjunction_clusters(df: pd.DataFrame, edges_major: list[tuple]) -> list[dict]:
	"""
	Build conjunction clusters using *existing* edges_major (no recomputation).
	Returns a UI-ready list of rows: [{"Cluster": "Sun, South Node, IC"}, ...]
	- Clusters are undirected connected components formed only by 'Conjunction' edges.
	- Members are ordered by the objects' order in the DF (not by longitude).
	- Singletons (size 1) are ignored.
	"""
	# Objects in DF order
	objs = _extract_object_rows(df)
	names = list(objs["Object"])
	order_ix = {name: i for i, name in enumerate(names)}

	# Build undirected adjacency from conjunction pairs
	from collections import defaultdict, deque
	adj = defaultdict(set)
	for a, b, meta in edges_major or []:
		if meta.get("aspect") == "Conjunction":
			adj[a].add(b)
			adj[b].add(a)

	# Find connected components (size >= 2)
	visited = set()
	clusters = []
	for n in list(adj.keys()):
		if n in visited:
			continue
		comp = []
		q = deque([n])
		visited.add(n)
		while q:
			u = q.popleft()
			comp.append(u)
			for v in adj[u]:
				if v not in visited:
					visited.add(v)
					q.append(v)

		if len(comp) >= 2:
			comp_sorted = sorted(comp, key=lambda x: order_ix.get(x, 10**9))
			clusters.append({
				"Cluster": ", ".join(comp_sorted),
				"Size": len(comp_sorted),
			})


	# Sort clusters by the first member’s DF order (stable)
	clusters.sort(
		key=lambda row: order_ix.get(row["Members"][0], 10**9) if row.get("Members") else 10**9
	)
	return clusters
