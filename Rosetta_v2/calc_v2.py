from zoneinfo import ZoneInfo
import os, swisseph as swe
import networkx as nx
from profiles_v2 import sabian_for, find_fixed_star_conjunctions, STAR_CATALOG, glyph_for
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
	utc_dt = get_utc_datetime(year, month, day, hour, minute, input_is_ut, tz_offset, tz_name)

	jd = swe.julday(
		utc_dt.year, utc_dt.month, utc_dt.day,
		utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
		swe.GREG_CAL,
	)

	# -------- Precompute ASC & MC (Placidus) --------
	asc_val = mc_val = None
	cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
	if ascmc:
		asc_val = ascmc[0]
		mc_val = ascmc[1]

	# -------- Precompute Descendant & IC --------
	extra_objects = {}
	if asc_val is not None:
		dc_val = (asc_val + 180.0) % 360.0
		extra_objects["DC"] = {
			"name": "Descendant",
			"lon": dc_val,
			"lat": 0.0,
			"dist": 0.0,
			"speed": 0.0,
			"decl": 0.0,
		}

	if mc_val is not None:
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
	loop_objects = list(MAJOR_OBJECTS.items()) + list(extra_objects.items())

	rows = []
	pos_for_dispositors = {}  # object -> longitude (exclude cusps)

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
	disp_sign_only = analyze_dispositors(pos_for_dispositors, [])
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

	for sys in systems:  # systems = ("placidus", "equal", "whole")
		cusps = cusps_by_system.get(sys, [])  # 12 cusp degrees for this system
		disp_sys = analyze_dispositors(pos_for_dispositors, cusps)
		by_house = disp_sys.get("by_house", {})

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

	if include_aspects:
		aspect_df = build_aspect_table(combined_df)
		return combined_df, aspect_df  # two DFs when requested

	return combined_df

def chart_sect_from_df(df) -> str:
	# exact object names from your DF: "Sun" and "AC"
	sun = float(df.loc[df["Object"] == "Sun", "Longitude"].iloc[0]) % 360.0
	ac  = float(df.loc[df["Object"] == "AC",  "Longitude"].iloc[0]) % 360.0
	dc  = (ac + 180.0) % 360.0
	# Above the horizon = DC → AC arc
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

def analyze_dispositors(pos: dict, cusps: list[float]) -> dict:
    """
    Build rulership (dispositor) graphs in two scopes and return BOTH:
      1) Raw, directional connections (edges) and chain listings
      2) Summaries: dominant rulers, final dispositors, sovereigns (self-rulers), and loops

    Input
    -----
    pos   : {object_name -> absolute longitude in degrees}
    cusps : 12 house cusp longitudes for ONE house system (pass [] or None for sign-only)

    Returns
    -------
    {
      "by_sign": {
        "edges": [(src, dst), ...],
        "chains": ["A rules B rules C", ...],
        "dominant_rulers": [...],
        "final_dispositors": [...],
        "sovereign": [...],
        "loops": [[...], ...],
      },
      "by_house": { ...same keys... }
    }
    """
    import networkx as nx

    def _ensure_list(x):
        if x is None:
            return []
        if isinstance(x, (list, tuple, set)):
            return list(x)
        return [x]

    names = list(pos.keys())
    name_set = set(names)

    def _edges_sign() -> list[tuple[str, str]]:
        edges = []
        for obj, deg in pos.items():
            sign = SIGNS[_sign_index(deg)]
            rulers = _ensure_list(PLANETARY_RULERS.get(sign, []))
            if rulers:
                for r in rulers:
                    if r in name_set:
                        edges.append((obj, r))
            else:
                edges.append((obj, obj))  # self-node if no valid rulers
        return edges

    def _edges_house() -> list[tuple[str, str]]:
        if not cusps or len(cusps) < 12:
            return []
        edges = []
        for obj, deg in pos.items():
            h = _house_of_degree(deg, cusps)
            if not h:
                edges.append((obj, obj))
                continue
            cusp_sign = SIGNS[_sign_index(cusps[h - 1])]
            rulers = _ensure_list(PLANETARY_RULERS.get(cusp_sign, []))
            if rulers:
                for r in rulers:
                    if r in name_set:
                        edges.append((obj, r))
            else:
                edges.append((obj, obj))
        return edges

    def _summarize(edges: list[tuple[str, str]]) -> dict:
        G = nx.DiGraph()
        G.add_nodes_from(names)
        G.add_edges_from(edges)

        # Sovereign = self-rulers
        sovereign = sorted([n for n in G.nodes if G.has_edge(n, n)])

        # Loops = cycles length >= 2
        loops = [cycle for cycle in nx.simple_cycles(G) if len(cycle) >= 2]

        # Dominant = max in-degree from others
        indeg = {n: 0 for n in G.nodes}
        for u, v in G.edges:
            if u != v:
                indeg[v] += 1
        max_in = max(indeg.values()) if indeg else 0
        dominant = sorted([n for n, c in indeg.items() if c == max_in and c > 0])

        # Final dispositors = sovereign with no outgoing edges to others
        finals = sorted([
            n for n in sovereign
            if set(G.successors(n)) - {n} == set()
        ])

        # Chains = readable rulership hierarchies
        def _all_chains_from(start: str, max_depth: int = 16) -> list[list[str]]:
            results = []
            def dfs(node: str, path: list[str], seen: set[str]):
                if len(path) >= max_depth:
                    results.append(path[:])
                    return
                nexts = list(G.successors(node))
                if not nexts:
                    results.append(path[:])
                    return
                for nxt in nexts:
                    if nxt in seen:
                        # loop closure
                        results.append(path + [nxt])
                    else:
                        dfs(nxt, path + [nxt], seen | {nxt})
            dfs(start, [start], {start})
            return results

        chain_strs = []
        for n in G.nodes:
            chains = _all_chains_from(n)
            for path in chains:
                chain_strs.append(" rules ".join(path))

        # de-duplicate & sort
        chain_strs = sorted(set(chain_strs))

        return {
            "edges": edges,
            "chains": chain_strs,
            "dominant_rulers": dominant,
            "final_dispositors": finals,
            "sovereign": sovereign,
            "loops": loops,
        }

    edges_s = _edges_sign()
    by_sign = _summarize(edges_s)

    edges_h = _edges_house()
    by_house = _summarize(edges_h) if edges_h else {
        "edges": [],
        "chains": [],
        "dominant_rulers": [],
        "final_dispositors": [],
        "sovereign": [],
        "loops": [],
    }

    return {"by_sign": by_sign, "by_house": by_house}

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
        chains_fmt  = " | ".join(s.replace(" rules ", " → ") for s in chains_list)

        summary_rows.append({
            "Scope": name,
            "Final": ", ".join(scope.get("final_dispositors", []) or []),
            "Dominant": ", ".join(scope.get("dominant_rulers", []) or []),
            "Sovereign": ", ".join(scope.get("sovereign", []) or []),
            "Loops": loops_fmt,
            "Chains": chains_fmt,   # <-- NEW
        })

    return chains_rows, summary_rows

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
	"Conjunction":   {"angle": 0,   "orb": 4},
	"Semi-sextile":  {"angle": 30,  "orb": 2},   # minor, kept here for unified scan; we'll sort into minors later
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
                "Members": comp_sorted,
                "Size": len(comp_sorted),
            })

    # Sort clusters by the first member’s DF order (stable)
    clusters.sort(
        key=lambda row: order_ix.get(row["Members"][0], 10**9) if row.get("Members") else 10**9
    )
    return clusters
