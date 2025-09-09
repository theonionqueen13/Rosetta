# rosetta/helpers.py
import sys
import os
import re
import numpy as np
import pandas as pd
import networkx as nx
from itertools import combinations
from rosetta.lookup import (
    GLYPHS,
    ASPECTS,
    ZODIAC_SIGNS,
    ZODIAC_COLORS,
    MODALITIES,
    GROUP_COLORS,
)

print("HELPERS FILE LOADED:", __file__)
sys.stdout.flush()

# -------------------------
# Core math + chart helpers
# -------------------------
import swisseph as swe


def calculate_houses(jd_ut, lat, lon, use_placidus=True):
    if use_placidus:
        # swe.HOUSES_PLACIDUS is default (b'A' or 'P')
        cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b"P")
    else:
        # Equal houses
        cusps, ascmc = swe.houses_ex(jd_ut, lat, lon, b"E")
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
        r"([+-]?\d+)"  # degrees
        r"(?:[°d]\s*(\d+))?"  # optional minutes
        r"(?:[\'m]\s*(\d+(?:\.\d+)?))?"  # optional seconds
        r'(?:["s]?)\s*([NSns]?)'  # optional N/S
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

_STAR_DF_CACHE = None


def load_star_df():
    """Load and cache the fixed star lookup table once."""
    global _STAR_DF_CACHE
    if _STAR_DF_CACHE is None:
        path = os.path.join(
            os.path.dirname(__file__), "..", "2b) Fixed Star Lookup.xlsx"
        )
        df = pd.read_excel(path, sheet_name="Sheet1")
        df.columns = df.columns.str.strip()
        df = df.rename(columns={"Absolute Degree Decimal": "Degree"})
        df = df.dropna(subset=["Degree"])
        df["Degree"] = df["Degree"].astype(float)
        _STAR_DF_CACHE = df
    return _STAR_DF_CACHE


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
                [
                    str(m).strip()
                    for m in close_stars["Meaning"].dropna().astype(str).tolist()
                    if str(m).strip()
                ]
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
        meaning = (
            match["Meaning"].dropna().iloc[0]
            if not match["Meaning"].dropna().empty
            else None
        )
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


def format_dms(value, is_latlon=False, is_decl=False, is_speed=False):
    """Convert decimal degrees (or hours/day for speed) into DMS string with hemispheres."""
    try:
        val = float(value)
    except (TypeError, ValueError):
        return str(value)

    if is_speed:
        deg = int(val)
        minutes = int((val - deg) * 60)
        seconds = int(round(((val - deg) * 60 - minutes) * 60))
        return f"{deg}°{minutes:02d}'{seconds:02d}\""

    sign = ""
    if is_latlon or is_decl:
        sign = "N" if val >= 0 else "S"
        val = abs(val)

    deg = int(val)
    minutes = int((val - deg) * 60)
    seconds = int(round(((val - deg) * 60 - minutes) * 60))
    return f"{deg}°{minutes:02d}'{seconds:02d}\" {sign}".strip()


SIGN_NAMES = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]


def format_longitude(lon):
    """Turn decimal degrees into Sign + degree°minute′ string."""
    sign_index = int(lon // 30)
    deg_in_sign = lon % 30
    deg = int(deg_in_sign)
    minutes = int(round((deg_in_sign - deg) * 60))
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
    oob_threshold = 23 + 26 / 60.0  # 23°26′
    extreme_threshold = 25 + 26 / 60.0  # 25°26′

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
