# rosetta/helpers.py
import os
import re
from functools import lru_cache
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd

from rosetta.lookup import GLYPHS, ASPECTS, ZODIAC_SIGNS, ZODIAC_COLORS, MODALITIES, GROUP_COLORS

# -------------------------
# Core math + chart helpers
# -------------------------
_swe = None


def initialize_swisseph(ephemeris_path: str | None = None):
    """Initialize and cache the Swiss Ephemeris module.

    Heavy imports and path configuration are deferred until this function is
    explicitly called. The configured module is returned and reused on
    subsequent calls.
    """

    global _swe

    if _swe is None:
        import swisseph as swe  # type: ignore

        if ephemeris_path is None:
            ephemeris_path = os.path.join(os.path.dirname(__file__), "ephe")

        swe.set_ephe_path(ephemeris_path)
        _swe = swe
    elif ephemeris_path:
        _swe.set_ephe_path(ephemeris_path)

    return _swe


def _get_swisseph():
    """Lazy Swiss Ephemeris accessor used internally by helper functions."""

    return initialize_swisseph()

def calculate_houses(jd_ut, lat, lon, use_placidus=True):
    if use_placidus:
        # swe.HOUSES_PLACIDUS is default (b'A' or 'P')
        cusps, ascmc = _get_swisseph().houses_ex(jd_ut, lat, lon, b'P')
    else:
        # Equal houses
        cusps, ascmc = _get_swisseph().houses_ex(jd_ut, lat, lon, b'E')
    return cusps, ascmc

def deg_to_rad(deg, asc_shift=0):
    """Convert degrees to radians for polar chart positioning"""
    return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)

def get_ascendant_degree(df):
    """Find Ascendant degree from CSV data"""
    for search_term in ["Ascendant", "ascendant", "AC"]:
        asc_row = df[df["Object"].str.contains(search_term, case=False, na=False)]
        if not asc_row.empty:
            return float(asc_row["abs_deg"].values[0])
    return 0

def parse_declination(decl_str):
    """Parse declination string and return decimal degrees with direction (N/S)"""
    if not decl_str or str(decl_str).strip().lower() in ["none", "nan", ""]:
        return None, None

    decl_str = str(decl_str).strip()
    pattern = (
        r'([+-]?\d+)'                       # degrees
        r'(?:[°d]\s*(\d+))?'                # optional minutes
        r'(?:[\'m]\s*(\d+(?:\.\d+)?))?'     # optional seconds
        r'(?:["s]?)\s*([NSns]?)'            # optional N/S
    )
    match = re.match(pattern, decl_str)
    if match:
        degrees = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = float(match.group(3)) if match.group(3) else 0
        direction = match.group(4).upper() if match.group(4) else None

        decimal_deg = abs(degrees) + minutes / 60.0 + seconds / 3600.0
        if degrees < 0 or direction == "S":
            decimal_deg = -decimal_deg
            direction = "S"
        else:
            direction = "N"
        return decimal_deg, direction

    try:
        decimal_deg = float(decl_str)
        direction = "S" if decimal_deg < 0 else "N"
        return decimal_deg, direction
    except:
        return None, None

# -------------------------
# Fixed star loader (lazy cache)
# -------------------------

@lru_cache(maxsize=1)
def load_star_df():
    """Load and cache the fixed star lookup table once."""

    path = os.path.join(os.path.dirname(__file__), "..", "2b) Fixed Star Lookup.xlsx")
    df = pd.read_excel(path, sheet_name="Sheet1")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={"Absolute Degree Decimal": "Degree"})
    df = df.dropna(subset=["Degree"])
    df["Degree"] = df["Degree"].astype(float)
    return df

def annotate_fixed_stars(df, orb=1.0):
    star_df = load_star_df()
    df["Fixed Star Conjunction"] = ""
    df["Fixed Star Meaning"] = ""
    for i, row in df.iterrows():
        obj_deg = float(row["abs_deg"])
        close_stars = star_df[np.abs(star_df["Degree"] - obj_deg) <= orb]
        if not close_stars.empty:
            star_names = "|||".join(close_stars["Fixed Star"].astype(str).tolist())
            star_meanings = "|||".join(
                [str(m).strip() for m in close_stars["Meaning"].dropna().astype(str).tolist() if str(m).strip()]
            )
            df.at[i, "Fixed Star Conjunction"] = star_names
            df.at[i, "Fixed Star Meaning"] = star_meanings
    return df

def get_fixed_star_meaning(star_name: str):
    star_df = load_star_df()
    if not star_name:
        return None
    match = star_df[star_df["Fixed Star"].str.contains(star_name, case=False, na=False)]
    if not match.empty:
        meaning = match["Meaning"].dropna().iloc[0] if not match["Meaning"].dropna().empty else None
        if isinstance(meaning, str) and meaning.strip():
            return star_name, meaning.strip()
    return None

# -------------------------
# Aspect + formatting utils
# -------------------------

def build_aspect_graph(pos):
    """Find connected components of planets based on major aspects only."""
    G = nx.Graph()
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2])
        if angle > 180:
            angle = 360 - angle
        for asp in ("Conjunction", "Sextile", "Square", "Trine", "Opposition"):
            asp_data = ASPECTS[asp]
            if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                G.add_edge(p1, p2, aspect=asp)
                break
    return list(nx.connected_components(G))

def format_dms(value, is_latlon: bool = False, is_decl: bool = False, is_speed: bool = False):
    """Convert decimal degrees (or hours/day for speed) into DMS string with hemispheres."""
    
    PRIME = "′"
    DOUBLE_PRIME = "″"

    try:
        val = float(value)
    except (TypeError, ValueError):
        return str(value)

    if is_speed:
        is_negative = val < 0
        val = abs(val)

        deg = int(val)
        m_float = (val - deg) * 60
        minutes = int(m_float)
        seconds = int(round((m_float - minutes) * 60))

        # normalize seconds -> minutes, minutes -> degrees
        if seconds >= 60:
            minutes += 1
            seconds -= 60
        if minutes >= 60:
            deg += 1
            minutes -= 60

        body = f"{deg}°{minutes:02d}{PRIME}{seconds:02d}{DOUBLE_PRIME}"
        return f"-{body}" if is_negative else body

    sign = ""
    if is_latlon or is_decl:
        sign = "N" if val >= 0 else "S"
        val = abs(val)

    deg = int(val)
    m_float = (val - deg) * 60
    minutes = int(m_float)
    seconds = int(round((m_float - minutes) * 60))

    # normalize seconds -> minutes, minutes -> degrees
    if seconds >= 60:
        minutes += 1
        seconds -= 60
    if minutes >= 60:
        deg += 1
        minutes -= 60

    return f"{deg}°{minutes:02d}{PRIME}{seconds:02d}{DOUBLE_PRIME} {sign}".strip()

SIGN_NAMES = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
]

def format_longitude(lon):
    """Turn decimal degrees into Sign + degree°minute′ string."""
    sign_index = int(lon // 30)
    deg_in_sign = lon % 30
    deg = int(deg_in_sign)
    minutes = int(round((deg_in_sign - deg) * 60))

    # normalize minutes carry
    if minutes >= 60:
        deg += 1
        minutes -= 60
        if deg >= 30:
            deg -= 30
            sign_index = (sign_index + 1) % 12

    return f"{SIGN_NAMES[sign_index]} {deg}°{minutes:02d}′"

def calculate_oob_status(declination_str):
    """Calculate Out of Bounds status from declination"""
    try:
        decimal_deg, direction = parse_declination(declination_str)
    except Exception:
        return None

    if decimal_deg is None:
        return None

    abs_decl = abs(decimal_deg)
    oob_threshold = 23 + 26/60.0    # 23°26′
    extreme_threshold = 25 + 26/60.0  # 25°26′

    if abs_decl <= oob_threshold:
        return "No"

    if abs_decl >= extreme_threshold:
        diff = abs_decl - extreme_threshold
        diff_deg = int(diff)
        diff_min = int((diff - diff_deg) * 60)
        return f"Extreme OOB by {diff_deg}°{diff_min:02d}′ {direction}"
    else:
        diff = abs_decl - oob_threshold
        diff_deg = int(diff)
        diff_min = int((diff - diff_deg) * 60)
        return f"OOB by {diff_deg}°{diff_min:02d}′ {direction}"
