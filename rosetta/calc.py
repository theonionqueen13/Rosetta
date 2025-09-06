
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
print("[DEBUG] se01181s.se1 manually exists?", os.path.exists(testfile))
print("[DEBUG] swe.get_library_path():", swe.get_library_path())

# Proper debug
print("[DEBUG] Ephemeris path set to:", EPHE_PATH)
print("[DEBUG] se01181s.se1 exists?", os.path.exists(os.path.join(EPHE_PATH, "se01181s.se1")))

print("[DEBUG] Files in ephe dir:", os.listdir(EPHE_PATH))

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

# --- Object list (restored) ---
OBJECTS = {
    # Luminaries & planets
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

    # Nodes
    "True Node": swe.TRUE_NODE,
    "South Node": -1,   # calculated

    # Angles / points
    "Ascendant": "AS",
    "Descendant": "DS",
    "MC": "MC",
    "Vertex": "VERTEX",
    "Part of Fortune": "POF",

    # Wounds / shadow
    "Chiron": swe.CHIRON,
    "Black Moon Lilith (Mean)": swe.MEAN_APOG,
    "Lilith (Asteroid)": swe.AST_OFFSET + 1181,

    # Core asteroids
    "Ceres": swe.AST_OFFSET + 1,
    "Pallas": swe.AST_OFFSET + 2,
    "Juno": swe.AST_OFFSET + 3,
    "Vesta": swe.AST_OFFSET + 4,
    "Pholus": swe.AST_OFFSET + 5145,
    "Eris": swe.AST_OFFSET + 136199,
    "Eros": swe.AST_OFFSET + 433,
    "Psyche": swe.AST_OFFSET + 16,
    "Magdalena": swe.AST_OFFSET + 318,
    "Minerva": swe.AST_OFFSET + 93,
    "Nessus": swe.AST_OFFSET + 7066,
    "Nemesis": swe.AST_OFFSET + 128,
    "Orcus": swe.AST_OFFSET + 90482,
    "Ixion": swe.AST_OFFSET + 28978,
    "Makemake": swe.AST_OFFSET + 136472,
    "Sedna": swe.AST_OFFSET + 90377,

    # Extended myth/archetype set
    "Apollo": swe.AST_OFFSET + 1862,
    "Osiris": swe.AST_OFFSET + 1923,
    "Isis": swe.AST_OFFSET + 42,
    "Haumea": swe.AST_OFFSET + 136108,
    "Hygiea": swe.AST_OFFSET + 10,
    "Quaoar": swe.AST_OFFSET + 50000,
    "Varuna": swe.AST_OFFSET + 20000,
    "Typhon": swe.AST_OFFSET + 42355,
    "Arachne": swe.AST_OFFSET + 407,
    "Hekate": swe.AST_OFFSET + 100,
    "Medusa": swe.AST_OFFSET + 149,
    "Kaali": swe.AST_OFFSET + 4227,
    "Angel": swe.AST_OFFSET + 11911,
    "Hypnos": swe.AST_OFFSET + 14827,
    "Singer": swe.AST_OFFSET + 10669,
    "Siva": swe.AST_OFFSET + 1170,
    "Hidalgo": swe.AST_OFFSET + 944,
    "Toro": swe.AST_OFFSET + 1685,
    "Freia": swe.AST_OFFSET + 76,
    "Zephyr": swe.AST_OFFSET + 106,
    "Euterpe": swe.AST_OFFSET + 27,
    "Harmonia": swe.AST_OFFSET + 40,
    "Polyhymnia": swe.AST_OFFSET + 33,
    "Echo": swe.AST_OFFSET + 60,
    "Sirene": swe.AST_OFFSET + 1009,
    "Fama": swe.AST_OFFSET + 408,
    "Mnemosyne": swe.AST_OFFSET + 57,
    "Panacea": swe.AST_OFFSET + 2878,
    "Icarus": swe.AST_OFFSET + 1566,
    "Hephaistos": swe.AST_OFFSET + 2212,
    "Pomona": swe.AST_OFFSET + 32,
    "Asclepius": swe.AST_OFFSET + 4581,
    "Odysseus": swe.AST_OFFSET + 1143,
    "Ulysses": swe.AST_OFFSET + 5254,
    "Iris": swe.AST_OFFSET + 7,
    "Anteros": swe.AST_OFFSET + 1943,
    "Aletheia": swe.AST_OFFSET + 259,
    "Justitia": swe.AST_OFFSET + 269,
    "Veritas": swe.AST_OFFSET + 490,
    "Sphinx": swe.AST_OFFSET + 896,
    "Bacchus": swe.AST_OFFSET + 2063,
    "Dionysus": swe.AST_OFFSET + 3671,
    "Thalia": swe.AST_OFFSET + 23,
    "Terpsichore": swe.AST_OFFSET + 81,
    "Lucifer": swe.AST_OFFSET + 1930,
    "Copernicus": swe.AST_OFFSET + 1322,
    "Koussevitzky": swe.AST_OFFSET + 1889,
    "Pamela": swe.AST_OFFSET + 3525,
    "Tezcatlipoca": swe.AST_OFFSET + 1980,
    "Niobe": swe.AST_OFFSET + 71,
    "Lachesis": swe.AST_OFFSET + 120,
    "Kassandra": swe.AST_OFFSET + 114,
    "Eurydike": swe.AST_OFFSET + 75,
    "Orpheus": swe.AST_OFFSET + 3361,
    "West": swe.AST_OFFSET + 2022,
    "Morpheus": swe.AST_OFFSET + 4197,
    "Kafka": swe.AST_OFFSET + 3412,
    "Karma": swe.AST_OFFSET + 3811,
    "Ariadne": swe.AST_OFFSET + 43,
}

def calculate_chart(
    year, month, day, hour, minute,
    tz_offset, lat, lon,
    input_is_ut: bool = False,
    tz_name: str | None = None,
):
    """
    Build the chart using Swiss Ephemeris.
    Adds Descendant and all three Liliths (True, Mean, Asteroid).
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

    # -------- Julian Day --------
    jd = swe.julday(
        utc_dt.year,
        utc_dt.month,
        utc_dt.day,
        utc_dt.hour + utc_dt.minute / 60.0 + utc_dt.second / 3600.0,
        swe.GREG_CAL,
    )

    rows = []
    asc_val = None

    # --- Core object list (with Liliths) ---
    OBJECTS = {
        # Luminaries & planets
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

        # Nodes
        "True Node": swe.TRUE_NODE,
        "South Node": -1,   # calculated

        # Angles / points
        "Ascendant": "ASC",
        "MC": "MC",
        "Vertex": "VERTEX",
        "Part of Fortune": "POF",

        # Wounds / shadow
        "Black Moon Lilith (True)": swe.OSCU_APOG,
        "Black Moon Lilith (Mean)": swe.MEAN_APOG,
        "Lilith (Asteroid)": swe.AST_OFFSET + 1181,

        # Core asteroids (keep your extended list here as before)...
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

    # --- Add Descendant (DC) ---
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
        print(f"[DEBUG] Ascendant = {asc_val:.4f}, Descendant = {dc_val:.4f}")

    return pd.DataFrame(rows)

if __name__ == "__main__":
    try:
        df = calculate_chart(1990, 7, 29, 1, 39, -6, 38.046, -97.345)
        print(df)
        df.to_csv("chart_output.csv", index=False)
    except Exception as e:
        print(f"Chart calculation failed: {e}")
