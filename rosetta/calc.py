
from zoneinfo import ZoneInfo
import os, swisseph as swe

import os, swisseph as swe

import os, swisseph as swe

# Force path to the ephe folder in your repo
EPHE_PATH = os.path.join(os.path.dirname(__file__), "ephe")
EPHE_PATH = EPHE_PATH.replace("\\", "/")
os.environ["SE_EPHE_PATH"] = EPHE_PATH
swe.set_ephe_path(EPHE_PATH)
testfile = os.path.join(EPHE_PATH, "se01181s.se1")

import datetime
import pandas as pd
from rosetta.lookup import SABIAN_SYMBOLS, DIGNITIES, PLANETARY_RULERS

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

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

def calculate_chart(
    year, month, day, hour, minute,
    tz_offset, lat, lon,
    input_is_ut: bool = False,
    tz_name: str | None = None,
    house_system: str = "equal", 
):
    print(f"[DEBUG] calculate_chart called with house_system={house_system}")
    """
    Build the chart using Swiss Ephemeris.
    Adds Descendant, house cusps, and Liliths.
    """

    # -------- Time -> UTC --------
    if input_is_ut:
        utc_dt = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
        tz_used = "UTC (input_is_ut=True)"
    else:
        if tz_name:
            tz = ZoneInfo(tz_name)
            local_dt = datetime.datetime(year, month, day, hour, minute, tzinfo=tz)
            utc_dt = local_dt.astimezone(datetime.timezone.utc)
            tz_used = f"{tz_name} (offset {local_dt.utcoffset()})"
        else:
            tz = datetime.timezone(datetime.timedelta(hours=tz_offset))
            local_dt = datetime.datetime(year, month, day, hour, minute, tzinfo=tz)
            utc_dt = local_dt.astimezone(datetime.timezone.utc)
            tz_used = f"Fixed offset {tz_offset}"

    jd = swe.julday(
        utc_dt.year, utc_dt.month, utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
        swe.GREG_CAL,
    )

    rows = []
    asc_val = None

    # --- Core object list (with Liliths) ---
    OBJECTS = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mercury": swe.MERCURY,
        "Venus": swe.VENUS,
        "Mars": swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO,
        "North Node": swe.TRUE_NODE,
        "South Node": -1,
        "Ascendant": "ASC",
        "MC": "MC",
        "Vertex": "VERTEX",
        "Part of Fortune": "POF",
        "Black Moon Lilith (True)": swe.OSCU_APOG,
        "Black Moon Lilith (Mean)": swe.MEAN_APOG,
        "Lilith (Asteroid)": swe.AST_OFFSET + 1181,
        "Chiron": swe.CHIRON,
        "Ceres": swe.AST_OFFSET + 1,
        "Pallas": swe.AST_OFFSET + 2,
        "Juno": swe.AST_OFFSET + 3,
        "Vesta": swe.AST_OFFSET + 4,
        "Pholus": swe.AST_OFFSET + 5145,
        "Eris": swe.AST_OFFSET + 136199,
        "Eros": swe.AST_OFFSET + 433,
        "Psyche": swe.AST_OFFSET + 16,
    }

    # --- Main loop ---
    for name, ident in OBJECTS.items():
        if ident == "ASC":
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
            lon_, lat_, dist, speed = ascmc[0], 0.0, 0.0, 0.0
            asc_val = lon_

        elif ident == "MC":
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
            lon_, lat_, dist, speed = ascmc[1], 0.0, 0.0, 0.0
            mc_val = lon_

        elif ident == "VERTEX":
            lon_, lat_, dist, speed = _calc_vertex(jd, lat, lon)

        elif ident == "POF":
            lon_, lat_, dist, speed = _calc_pof(jd, lat, lon)

        elif ident == -1:  # South Node
            north_pos, _ = swe.calc_ut(jd, swe.TRUE_NODE)
            lon_ = (north_pos[0] + 180) % 360
            lat_, dist, speed = 0.0, 0.0, 0.0

        else:
            pos, _ = swe.calc_ut(jd, ident)
            lon_, lat_, dist, speed = pos[:4]

        sign, dms, sabian_index = deg_to_sign(lon_)
        sabian_symbol = SABIAN_SYMBOLS.get((sign, int(lon_ % 30) + 1), "")
        retro = "Rx" if speed < 0 else ""
        if ident in ("ASC", "MC", "VERTEX", "POF", -1):
            decl = 0.0
        else:
            eq, _ = swe.calc_ut(jd, ident, swe.FLG_EQUATORIAL)
            decl = eq[1]
        oob = "Yes" if is_out_of_bounds(decl) else "No"
        dignity = DIGNITIES.get(sign, "")
        rulership = PLANETARY_RULERS.get(sign, [])

        rows.append({
            "Object": name,
            "Longitude": round(lon_, 6),
            "Sign": sign,
            "DMS": dms,
            "Sabian Index": sabian_index,
            "Sabian Symbol": sabian_symbol,
            "Retrograde": retro,
            "OOB Status": oob,
            "Dignity": dignity,
            "Ruled by (sign)": ", ".join(rulership),
            "Latitude": round(lat_, 6),
            "Declination": round(decl, 6),
            "Distance": round(dist, 6),
            "Speed": round(speed, 6),
        })

    # --- Add Descendant ---
    if asc_val is not None:
        dc_val = (asc_val + 180.0) % 360.0
        sign, dms, sabian_index = deg_to_sign(dc_val)
        sabian_symbol = SABIAN_SYMBOLS.get((sign, int(dc_val % 30) + 1), "")
        rows.append({
            "Object": "Descendant",
            "Longitude": round(dc_val, 6),
            "Sign": sign,
            "DMS": dms,
            "Sabian Index": sabian_index,
            "Sabian Symbol": sabian_symbol,
            "Retrograde": "",
            "OOB Status": "No",
            "Dignity": "",
            "Ruled by (sign)": "",
            "Latitude": 0.0,
            "Declination": 0.0,
            "Distance": 0.0,
            "Speed": 0.0,
        })

    # ----------------------------
    # House cusps
    # ----------------------------
        # ----------------------------
    # House cusps
    # ----------------------------
    cusp_rows = []

    if house_system == "placidus":
        cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
        if cusps is None or ascmc is None:
            raise ValueError("Swiss Ephemeris could not calculate Placidus houses")
        for i, deg in enumerate(cusps[:12], start=1):
            cusp_rows.append({
                "Object": f"{i}H Cusp",
                "Computed Absolute Degree": round(deg, 6),
            })

    elif house_system == "equal":
        if asc_val is None:
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b'E')
            if ascmc is None:
                raise ValueError("Swiss Ephemeris could not calculate Equal houses")
            asc_val = ascmc[0]
        for i in range(12):
            deg = (asc_val + i * 30.0) % 360.0
            cusp_rows.append({
                "Object": f"{i+1}H Cusp",
                "Computed Absolute Degree": round(deg, 6),
            })

    elif house_system == "whole":
        if asc_val is None:
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
            asc_val = ascmc[0]

        asc_sign = int(asc_val // 30) * 30.0   # snap Asc to start of sign
        for i in range(12):
            deg = (asc_sign + i * 30.0) % 360.0
            cusp_rows.append({
                "Object": f"{i+1}H Cusp",
                "Computed Absolute Degree": round(deg, 6),
            })

    # merge with main planet rows
    cusp_df = pd.DataFrame(cusp_rows)
    base_df = pd.DataFrame(rows)
    return pd.concat([base_df, cusp_df], ignore_index=True)

if __name__ == "__main__":
    try:
        df = calculate_chart(1990, 7, 29, 1, 39, -6, 38.046, -97.345)
        print(df)
        df.to_csv("chart_output.csv", index=False)
    except Exception as e:
        print(f"Chart calculation failed: {e}")
