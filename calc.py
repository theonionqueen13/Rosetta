# calc.py
import swisseph as swe
import datetime
import pandas as pd

from rosetta.lookup import SABIAN_SYMBOLS, DIGNITIES, RULERSHIPS

# --- CONFIG ---
swe.set_ephe_path(r"C:\Users\imcur\Downloads\swisseph")  # adjust to where you put ephemeris files

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

def get_sabian_symbol(sign: str, degree: int) -> str:
    key = (sign, degree)
    return SABIAN_SYMBOLS.get(key, f"No Sabian symbol for {sign} {degree}°")

# --- Special calcs ---
def _calc_vertex(jd, lat, lon):
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
    return ascmc[3], 0.0, 0.0, 0.0  # lon, lat, dist, speed

def _calc_pof(jd, lat, lon):
    cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
    asc = ascmc[0]
    sun_pos, _ = swe.calc_ut(jd, swe.SUN)
    moon_pos, _ = swe.calc_ut(jd, swe.MOON)
    sun = sun_pos[0]
    moon = moon_pos[0]
    # check diurnal / nocturnal
    is_day = (sun > asc and sun < (asc + 180) % 360)
    if is_day:
        pof = (asc + moon - sun) % 360
    else:
        pof = (asc - moon + sun) % 360
    return pof, 0.0, 0.0, 0.0

# --- Object list ---
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
    "Chiron": 2060,
    "True Node": swe.TRUE_NODE,
    "South Node": -1,      # special
    "Lilith (Mean)": swe.MEAN_APOG,
    "Lilith (Asteroid)": 1181,
    "Ceres": 1,
    "Pallas": 2,
    "Juno": 3,
    "Vesta": 4,
    "Pholus": 5145,
    "Eris": 136199,
    "Eros": 433,
    "Psyche": 16,
    "Magdalena": 318,
    "Minerva": 93,
    "Nessus": 7066,
    "Nemesis": 128,
    "Orcus": 90482,
    "Ixion": 28978,
    "Makemake": 136472,
    "Sedna": 90377,
    # Special points
    "Ascendant": "ASC",
    "MC": "MC",
    "Vertex": "VERTEX",
    "Part of Fortune": "POF",
}

# --- Chart calc ---
def calculate_chart(year, month, day, hour, minute, tz_offset, lat, lon):
    # UTC datetime → Julian day
    ut = datetime.datetime(year, month, day, hour, minute) - datetime.timedelta(hours=tz_offset)
    jd = swe.julday(ut.year, ut.month, ut.day, ut.hour + ut.minute / 60.0)

    rows = []

    for name, ident in OBJECTS.items():
        if ident == "ASC":
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
            lon_, lat_, dist, speed = ascmc[0], 0.0, 0.0, 0.0
        elif ident == "MC":
            cusps, ascmc = swe.houses_ex(jd, lat, lon, b'P')
            lon_, lat_, dist, speed = ascmc[1], 0.0, 0.0, 0.0
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
        sabian_symbol = SABIAN_SYMBOLS.get(sabian_index, "")

        # Retrograde
        retro = "Rx" if speed < 0 else ""

        # Declination / OOB
        if ident in ("ASC", "MC", "VERTEX", "POF", -1):
            decl = 0.0
        else:
            eq, _ = swe.calc_ut(jd, ident, flag=swe.FLG_EQUATORIAL)
            decl = eq[1]
        oob = "Yes" if is_out_of_bounds(decl) else "No"

        # dignity & rulerships
        dignity = DIGNITIES.get(sign, "")
        rulership = RULERSHIPS.get(name, {})

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
            "Ruled by (sign)": rulership.get("sign", ""),
            "Ruled by (house)": rulership.get("house", ""),
            "Latitude": round(lat_, 6),
            "Declination": round(decl, 6),
            "Distance": round(dist, 6),
            "Speed": round(speed, 6),
        })

    return pd.DataFrame(rows)

# Example run
if __name__ == "__main__":
    df = calculate_chart(1990, 7, 29, 1, 39, -6, 38.046, -97.345)
    df.to_csv("chart_output.csv", index=False)
    print(df)
