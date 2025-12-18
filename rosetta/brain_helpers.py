"""Utility helpers for brain context building.

The helpers in this module stay free of UI or network concerns so they can be
reused by the context builders and downstream callers. DataFrame parameters are
annotated to describe the columns expected when reading chart data produced by
``calc.py``.
"""

from __future__ import annotations

from typing import Dict, List, Mapping

import pandas as pd

from rosetta.brain_constants import ALIASES_MEANINGS, DIGNITIES, SIGN_NAMES
from rosetta.helpers import format_dms

_DETAIL_FIELD_SOURCES: Mapping[str, tuple[str, ...]] = {
    "Speed": ("Speed",),
    "Latitude": ("Latitude",),
    "Declination": ("Declination",),
    "Out of Bounds": ("OOB Status", "OOB", "Out of Bounds"),
    "Conjunct Fixed Star": ("Fixed Star Conjunction",),
}


def _norm_name(name: str) -> str:
    """Normalize aliases to canonical names (e.g., AC -> Ascendant)."""

    if not name:
        return name
    return ALIASES_MEANINGS.get(name, name)


def _sign_index(longitude_deg: float) -> int:
    """Return the 0..11 sign index from an absolute ecliptic longitude."""

    return int((longitude_deg % 360.0) // 30)


def _deg_in_sign(longitude_deg: float) -> int:
    """Return the 0..29 integer degrees within a sign."""

    return int(longitude_deg % 30.0)


def _degree_for(name: str, pos: Dict[str, float]) -> float | None:
    """
    Find an object's degree from ``pos`` using the given name and any alias keys
    that map to that canonical display.

    Parameters
    ----------
    name:
        Placement name or alias (e.g., ``"MC"``).
    pos:
        Mapping of object name to absolute longitude in degrees.
    """

    if not name:
        return None
    canonical = _norm_name(name)

    for nm in (name, canonical):
        if nm in pos and pos[nm] is not None:
            return pos[nm]

    for alias, display in ALIASES_MEANINGS.items():
        if display == canonical and alias in pos and pos[alias] is not None:
            return pos[alias]

    return None


def _get_row_from_df(name: str, df: pd.DataFrame | None) -> dict | None:
    """
    Pull the data row for ``name`` from the provided DataFrame with alias
    awareness.

    The DataFrame is expected to include at least the ``Object`` column and
    typically comes from ``calc.calculate_chart``. Other consumer columns used by
    downstream helpers include ``Longitude``, ``Sign``, ``House``, and motion
    flags (``Retrograde``, ``Rx``, ``Motion``).
    """

    if df is None or "Object" not in df.columns:
        return None

    canonical = _norm_name(name)
    names_to_try = {name, canonical}

    for alias, display in ALIASES_MEANINGS.items():
        if alias == name:
            names_to_try.add(display)
        if display == canonical:
            names_to_try.add(alias)

    obj_series = df["Object"].astype("string").str.strip()
    hit = df[obj_series.isin([str(n) for n in names_to_try])]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def _resolve_dignity(obj: str, sign: str) -> str:
    """Resolve a dignity string for ``obj`` in ``sign`` from the lookup tables."""

    if not obj or not sign:
        return ""
    try:
        d = DIGNITIES.get(obj)
        if isinstance(d, dict):
            s = d.get(sign)
            if s:
                return s
        d2 = DIGNITIES.get(sign)
        if isinstance(d2, dict):
            s = d2.get(obj)
            if s:
                return s
    except Exception:
        return ""
    return ""


def ensure_profile_detail_strings(row: dict | None) -> dict:
    """Ensure sidebar detail fields are formatted exactly once and cached.

    ``row`` typically originates from a profile DataFrame containing columns such
    as ``Speed``, ``Latitude``, ``Declination``, ``OOB Status``, and ``Fixed Star
    Conjunction``. The function adds ``<Label> Display`` keys with formatted
    strings and returns a ``label -> string`` mapping for any non-empty value.
    """

    if not isinstance(row, dict):
        return {}

    out: dict[str, str] = {}

    for label, keys in _DETAIL_FIELD_SOURCES.items():
        display_key = f"{label} Display"
        existing = row.get(display_key)
        if existing:
            val_str = str(existing).strip()
            if val_str:
                out[label] = val_str
            continue

        raw_val = ""
        for key in keys:
            if key in row and str(row[key]).strip():
                raw_val = row[key]
                break

        val_str = str(raw_val).strip()
        if not val_str or val_str.lower() in {"none", "nan", "no"}:
            row[display_key] = ""
            continue

        numeric_val = None
        try:
            numeric_val = float(val_str)
        except Exception:
            numeric_val = None

        if numeric_val is not None:
            if numeric_val == 0.0:
                row[display_key] = ""
                continue
            if label == "Speed":
                val_str = format_dms(numeric_val, is_speed=True)
            elif label == "Latitude":
                val_str = format_dms(numeric_val, is_latlon=True)
            elif label == "Declination":
                val_str = format_dms(numeric_val, is_decl=True)
        elif label == "Conjunct Fixed Star":
            parts = [p.strip() for p in val_str.split("|||") if p.strip()]
            val_str = ", ".join(parts)

        row[display_key] = val_str
        if val_str:
            out[label] = val_str

    return out


def _extract_cusps_from_df(df: pd.DataFrame | None) -> List[float]:
    """Return the 12 house cusp longitudes from ``df`` or an empty list.

    The DataFrame should contain ``Object`` and ``Longitude`` columns with rows
    labeled ``"<n> H Cusp"`` for houses 1..12. Values are converted to floats and
    returned in house order.
    """

    if df is None or "Object" not in df.columns or "Longitude" not in df.columns:
        return []
    labels = [
        "1 H Cusp",
        "2 H Cusp",
        "3 H Cusp",
        "4 H Cusp",
        "5 H Cusp",
        "6 H Cusp",
        "7 H Cusp",
        "8 H Cusp",
        "9 H Cusp",
        "10 H Cusp",
        "11 H Cusp",
        "12 H Cusp",
    ]
    cusps: List[float] = []
    for lab in labels:
        row = df[df["Object"].astype(str).str.fullmatch(lab, case=False, na=False)]
        if row.empty:
            return []
        try:
            cusps.append(float(row["Longitude"].iloc[0]))
        except Exception:
            return []
    return cusps


def _in_forward_arc(start_deg: float, end_deg: float, x_deg: float) -> bool:
    """True if ``x_deg`` lies on the forward arc from ``start_deg`` to ``end_deg``."""

    span = (end_deg - start_deg) % 360.0
    off = (x_deg - start_deg) % 360.0
    return (off < span) if span != 0 else (off == 0)


def _house_of_degree(deg: float, cusps: List[float]) -> int | None:
    """Given a degree and 12 cusp list, return the house number (1..12)."""

    if not cusps or len(cusps) != 12:
        return None
    for i in range(12):
        a = cusps[i]
        b = cusps[(i + 1) % 12]
        if _in_forward_arc(a, b, deg):
            return i + 1
    return 12


def _angle_sep(a: float, b: float) -> float:
    """Smallest angular separation (0..180)."""

    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d


__all__ = [
    "_angle_sep",
    "_deg_in_sign",
    "_degree_for",
    "_extract_cusps_from_df",
    "_get_row_from_df",
    "_house_of_degree",
    "_in_forward_arc",
    "_norm_name",
    "_resolve_dignity",
    "_sign_index",
    "ensure_profile_detail_strings",
]
