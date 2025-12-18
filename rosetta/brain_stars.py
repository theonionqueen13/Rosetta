"""Fixed star catalog helpers."""

from __future__ import annotations

from typing import Dict

import pandas as pd

from rosetta.brain_constants import SIGN_NAMES
from rosetta.brain_helpers import _norm_name


def load_fixed_star_catalog(path: str) -> pd.DataFrame:
    """Load the fixed star Excel catalog.

    Expected columns: ``Name``, ``Sign``, ``Degree``, ``Orb``, and ``Meaning``.
    Columns are normalized to lowercase to simplify downstream access.
    """

    df = pd.read_excel(path)
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def build_fixed_star_context(pos: Dict[str, float], catalog: pd.DataFrame) -> dict:
    """Collect any fixed star conjunctions present in ``pos``.

    The ``catalog`` DataFrame follows the schema documented in
    :func:`load_fixed_star_catalog` with normalized lowercase column names.
    """

    out = {}
    for obj, deg in pos.items():
        matches = []
        for _, row in catalog.iterrows():
            star_name = row.get("name")
            sign = row.get("sign")
            star_deg = row.get("degree")
            orb = row.get("orb", 1.0)
            meaning = row.get("meaning", "")

            if pd.isna(star_name) or pd.isna(sign) or pd.isna(star_deg):
                continue

            sign_idx = SIGN_NAMES.index(sign) if sign in SIGN_NAMES else None
            if sign_idx is None:
                continue
            abs_deg = sign_idx * 30 + float(star_deg)

            sep = abs((deg - abs_deg + 180) % 360 - 180)
            if sep <= orb:
                matches.append({"star": star_name, "orb": round(sep, 2), "meaning": meaning})

        if matches:
            out[_norm_name(obj)] = matches
    return {"fixed_stars": out}


__all__ = ["build_fixed_star_context", "load_fixed_star_catalog"]
