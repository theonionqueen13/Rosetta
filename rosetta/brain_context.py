"""Context builders for chart objects and aspects."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

import pandas as pd

from rosetta.brain_constants import (
    ALIASES_MEANINGS,
    GLYPHS,
    HOUSE_MEANINGS,
    OBJECT_INTERPRETATIONS,
    OBJECT_MEANINGS,
    OBJECT_MEANINGS_SHORT,
    SIGN_MEANINGS,
    SIGN_NAMES,
)
from rosetta.brain_helpers import (
    _deg_in_sign,
    _degree_for,
    _get_row_from_df,
    _norm_name,
    _sign_index,
    ensure_profile_detail_strings,
)
from rosetta.patterns import _cluster_conjunctions_for_detection


def _clean_detail(val: Any) -> str:
    return val.strip() if isinstance(val, str) else ""


def build_object_context(
    name: str,
    pos: Dict[str, float],
    df: pd.DataFrame | None,
    profile_rows: dict | None = None,
) -> dict:
    """Build the per-object context from position data and profile rows.

    Parameters
    ----------
    name:
        Name or alias of the placement to resolve.
    pos:
        Mapping of object names to absolute longitude values.
    df:
        Profile DataFrame produced by the calculator. Expected columns include
        ``Object``, ``Longitude``, ``Sign``, ``House``, ``Retrograde``/``Rx``/``Motion``/``Station``,
        ``OOB Status``/``OOB``/``Out of Bounds``, ``Sabian Symbol``, and optional detail
        columns such as ``Speed``, ``Latitude``, and ``Declination``.
    profile_rows:
        Optional pre-built mapping of object name to enriched row data, used instead
        of reading directly from ``df``.
    """
    canonical = _norm_name(name)
    abs_deg = _degree_for(name, pos)
    if abs_deg is None:
        return {"object": canonical, "available": False, "reason": f"No position for {name!r} in pos"}

    row = {}
    if profile_rows and name in profile_rows:
        row = profile_rows[name]
    elif profile_rows and canonical in profile_rows:
        row = profile_rows[canonical]
    else:
        row = _get_row_from_df(name, df) or {}

    sign_name = (row.get("Sign") or "").strip()
    if not sign_name:
        sign_name = SIGN_NAMES[_sign_index(abs_deg)]
    deg_in = _deg_in_sign(abs_deg)

    house = None
    if "House" in row and str(row["House"]).strip():
        try:
            house = int(row["House"])
        except Exception:
            house = None

    motion_raw = " ".join(str(row.get(k, "")) for k in ["Retrograde", "Rx", "Motion", "Station"]).lower()
    rx_flag = ("rx" in motion_raw) or ("retro" in motion_raw)
    station_flag = "station" in motion_raw
    oob_raw = str(row.get("OOB Status", "") or row.get("OOB", "") or row.get("Out of Bounds", "")).strip().lower()
    oob_flag = oob_raw in ("yes", "true", "y", "1")

    _d = row.get("Dignity")
    dignity = _d.strip() if isinstance(_d, str) else ""

    details = ensure_profile_detail_strings(row)

    def _as_list(x: Any) -> list:
        if isinstance(x, (list, tuple)):
            return list(x)
        return [x] if x else []

    sign_ruler = _as_list(row.get("Sign Ruler"))
    house_ruler = _as_list(row.get("House Ruler"))

    declination = _clean_detail(row.get("Declination Display") or details.get("Declination"))
    latitude = _clean_detail(row.get("Latitude Display") or details.get("Latitude"))
    speed = _clean_detail(row.get("Speed Display") or details.get("Speed"))

    display_name = (row.get("Display Name") or canonical).strip()
    sabian = (row.get("Sabian Symbol") or row.get("Sabian") or "").strip()

    ctx = {
        "object": canonical,
        "display_name": display_name,
        "glyph": GLYPHS.get(canonical, ""),
        "absolute_degree": round(abs_deg % 360.0, 2),
        "sign": sign_name,
        "degree_in_sign": int(deg_in),
        "house": int(house) if house else None,
        "house_meaning": HOUSE_MEANINGS.get(int(house), "") if house else "",
        "sign_meaning": SIGN_MEANINGS.get(sign_name, ""),
        "object_meaning": OBJECT_MEANINGS.get(canonical) or OBJECT_INTERPRETATIONS.get(canonical, ""),
        "object_meaning_short": OBJECT_MEANINGS_SHORT.get(canonical, ""),
        "sabian_symbol": sabian,
        "retrograde": bool(rx_flag),
        "station": bool(station_flag),
        "oob": bool(oob_flag),
        "declination": declination,
        "latitude": latitude,
        "speed": speed,
        "dignity": dignity,
        "sign_ruler": sign_ruler,
        "house_ruler": house_ruler,
    }
    return ctx


def _collapse_aspects_by_clusters(
    aspects: List[Dict[str, str]],
    visible: List[str],
    pos: Dict[str, float],
) -> List[Dict[str, Any]]:
    if not aspects:
        return []

    vis = [o for o in visible if o in pos]
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, vis)

    def members_for(obj: str) -> List[str]:
        if obj not in rep_anchor:
            return [obj]
        rep = rep_anchor[obj]
        cluster = rep_map.get(rep, [obj])
        return sorted(cluster, key=lambda m: pos.get(m, 9999.0))

    seen = set()
    out: List[Dict[str, Any]] = []
    for e in aspects:
        a = e.get("from")
        b = e.get("to")
        asp = e.get("aspect")
        if not a or not b or not asp:
            continue
        L = members_for(a)
        R = members_for(b)
        if set(L) == set(R):
            continue

        key = (frozenset(L), asp, frozenset(R))
        rkey = (frozenset(R), asp, frozenset(L))
        if key in seen or rkey in seen:
            continue
        seen.add(key)

        out.append({"left": L, "aspect": asp, "right": R})

    return out


def build_context_for_objects(
    targets: List[str],
    pos: Dict[str, float],
    df: pd.DataFrame | None,
    active_shapes: List[Any] | None = None,
    aspects: List[Dict[str, str]] | None = None,
    star_catalog: pd.DataFrame | None = None,
    profile_rows: dict | None = None,
) -> Dict[str, Any]:
    """Build the main interpretation context using precomputed lookups.

    The ``df`` argument is the chart DataFrame returned by ``calc.calculate_chart``
    and should include at minimum ``Object`` and ``Longitude`` columns plus house
    cusp rows for computing ruler chains. When provided, ``star_catalog`` should
    follow the schema documented in :func:`rosetta.brain_stars.load_fixed_star_catalog`.
    """

    out_objects = [build_object_context(t, pos, df, profile_rows=profile_rows) for t in targets]

    context: Dict[str, Any] = {
        "version": "brain.v1",
        "objects": out_objects,
        "shapes": [],
        "aspects": [],
        "notes": {
            "protocol": (
                "Profiles cover only the selected objects. "
                "Use global context (compass, dispositors summary) for orientation, "
                "but do not output those as full profiles unless relevant."
            )
        },
        "global": {},
    }

    if aspects:
        context["aspects"] = _collapse_aspects_by_clusters(aspects, targets, pos)

    from rosetta.brain_global import analyze_dispositors, build_compass_context, build_shapes_context
    from rosetta.brain_stars import build_fixed_star_context

    context["global"].update(build_compass_context(pos, df))
    context.update(build_shapes_context(active_shapes))
    context["global"]["dispositor_graph"] = analyze_dispositors(pos, df)

    if star_catalog is not None:
        context.update(build_fixed_star_context(pos, star_catalog))

    return context


__all__ = [
    "build_context_for_objects",
    "build_object_context",
]
