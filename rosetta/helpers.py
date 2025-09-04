import sys
print("HELPERS FILE LOADED:", __file__)
sys.stdout.flush()

# rosetta/helpers.py
import numpy as np
import re
import pandas as pd  # for get_ascendant_degree

def deg_to_rad(deg, asc_shift=0):
    """Convert degrees to radians for polar chart positioning"""
    return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)


def get_ascendant_degree(df):
    """Find Ascendant degree from CSV data"""
    # Try multiple ways to find Ascendant
    for search_term in ["Ascendant", "ascendant", "AC"]:
        asc_row = df[df["Object"].str.contains(search_term, case=False, na=False)]
        if not asc_row.empty:
            return float(asc_row["Computed Absolute Degree"].values[0])
    return 0

def parse_declination(decl_str):
    """Parse declination string and return decimal degrees with direction (N/S)"""
    if not decl_str or str(decl_str).strip().lower() in ["none", "nan", ""]:
        return None, None

    decl_str = str(decl_str).strip()

    # Regex handles degrees, optional minutes, optional seconds, and optional N/S
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

        # Convert to decimal degrees
        decimal_deg = abs(degrees) + minutes / 60.0 + seconds / 3600.0

        # Apply sign
        if degrees < 0 or direction == "S":
            decimal_deg = -decimal_deg
            direction = "S"
        else:
            direction = "N"

        return decimal_deg, direction

    # Fallback: plain decimal string
    try:
        decimal_deg = float(decl_str)
        direction = "S" if decimal_deg < 0 else "N"
        return decimal_deg, direction
    except:
        return None, None


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
