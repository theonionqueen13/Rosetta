"""
chart_serializer.py
~~~~~~~~~~~~~~~~~~~
Converts an AstrologicalChart (with circuit simulation, planetary states,
shapes, etc.) into a flat JSON-safe dictionary suitable for the interactive
D3.js/SVG chart component.

This is the **single source of truth** contract between the Python backend
and the JavaScript renderer.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

from models_v2 import (
    AstrologicalChart,
    CircuitEdge,
    CircuitNode,
    CircuitSimulation,
    DetectedShape,
    PlanetaryState,
    ShapeCircuit,
    static_db,
)

# ---------------------------------------------------------------------------
# Constants pulled from static_db / lookup_v2
# ---------------------------------------------------------------------------
GLYPHS = static_db.GLYPHS
ZODIAC_SIGNS = static_db.ZODIAC_SIGNS
ZODIAC_COLORS = static_db.ZODIAC_COLORS
ASPECTS = static_db.ASPECTS
GROUP_COLORS = static_db.GROUP_COLORS
SUBSHAPE_COLORS = static_db.SUBSHAPE_COLORS
LUMINARIES_AND_PLANETS = static_db.LUMINARIES_AND_PLANETS
OBJECT_MEANINGS = static_db.OBJECT_MEANINGS
OBJECT_MEANINGS_SHORT = static_db.OBJECT_MEANINGS_SHORT
SIGN_MEANINGS = static_db.SIGN_MEANINGS
HOUSE_MEANINGS = static_db.HOUSE_MEANINGS
ELEMENT = static_db.ELEMENT

# Element-band colours (same as drawing_v2.draw_zodiac_signs)
ELEMENT_COLORS_DARK = {
    "fire": "#1567A5FF",
    "earth": "#6D2424FF",
    "air": "#366E21FF",
    "water": "#946D19FF",
}
ELEMENT_COLORS_LIGHT = {
    "fire": "#6D9EC4FF",
    "earth": "#CE7878FF",
    "air": "#7CAF6AFF",
    "water": "#D8B873FF",
}

SIGN_ELEMENTS = [
    "fire", "earth", "air", "water",
    "fire", "earth", "air", "water",
    "fire", "earth", "air", "water",
]

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v: Any, default: float = 0.0) -> float:
    if v is None:
        return default
    try:
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return default
        return round(f, 6)
    except (TypeError, ValueError):
        return default


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def _house_number(house_obj: Any) -> Optional[int]:
    if house_obj is None:
        return None
    if hasattr(house_obj, "number"):
        return house_obj.number
    try:
        return int(house_obj)
    except (TypeError, ValueError):
        return None


def _object_map(chart: AstrologicalChart) -> dict[str, Any]:
    """Name → ChartObject for quick lookup."""
    return {
        obj.object_name.name: obj
        for obj in chart.objects
        if obj.object_name
    }


# ---------------------------------------------------------------------------
# Serialise a single ChartObject
# ---------------------------------------------------------------------------

def _serialize_object(obj: Any, house_system: str, chart: AstrologicalChart) -> dict:
    """Convert a models_v2.ChartObject to a JSON-safe dict."""
    name = obj.object_name.name if obj.object_name else ""
    glyph = GLYPHS.get(name, obj.glyph or "")
    sign_name = obj.sign.name if obj.sign else ""
    
    # House number for the active house system
    house_num = None
    hs = (house_system or "placidus").lower().strip()
    if hs in ("placidus",):
        house_num = _house_number(obj.placidus_house)
    elif hs in ("equal", "equal house"):
        house_num = _house_number(obj.equal_house)
    elif hs in ("whole", "wholesign", "whole sign"):
        house_num = _house_number(obj.whole_sign_house)
    else:
        house_num = _house_number(obj.placidus_house)

    # Degree within sign
    deg_in_sign = int(obj.longitude % 30) if obj.longitude is not None else 0
    min_in_sign = int((obj.longitude % 1) * 60) if obj.longitude is not None else 0

    # Planetary state (from dignity_calc)
    ps: Optional[PlanetaryState] = obj.planetary_state
    state_data = {}
    if ps:
        ed = ps.essential_dignity
        state_data = {
            "essential_dignity": {
                "domicile": getattr(ed, "domicile", False),
                "exaltation": getattr(ed, "exaltation", False),
                "triplicity": getattr(ed, "triplicity", False),
                "term": getattr(ed, "term", False),
                "face": getattr(ed, "face", False),
                "detriment": getattr(ed, "detriment", False),
                "fall": getattr(ed, "fall", False),
                "peregrine": getattr(ed, "peregrine", False),
                "primary_dignity": getattr(ed, "primary_dignity", None),
            } if ed else {},
            "raw_authority": _safe_float(ps.raw_authority),
            "quality_index": _safe_float(ps.quality_index),
            "house_score": _safe_float(ps.house_score),
            "motion_score": _safe_float(ps.motion_score),
            "motion_label": _safe_str(ps.motion_label),
            "solar_proximity_score": _safe_float(ps.solar_proximity_score),
            "solar_proximity_label": _safe_str(ps.solar_proximity_label),
            "solar_distance": _safe_float(ps.solar_distance) if ps.solar_distance is not None else None,
            "potency_score": _safe_float(ps.potency_score),
            "power_index": _safe_float(ps.power_index),
            "fixed_star_bonus": _safe_float(ps.fixed_star_bonus),
            "asteroid_bonus": _safe_float(ps.asteroid_bonus),
            "conjunction_contributors": list(ps.conjunction_contributors) if ps.conjunction_contributors else [],
            "cluster_id": ps.cluster_id,
            "cluster_potency": _safe_float(ps.cluster_potency),
            "cluster_members": list(ps.cluster_members) if ps.cluster_members else [],
        }

    # Circuit node data (from circuit_sim)
    circuit_data = {}
    sim: Optional[CircuitSimulation] = getattr(chart, "circuit_simulation", None)
    if sim and sim.node_map:
        node: Optional[CircuitNode] = sim.node_map.get(name)
        if node:
            circuit_data = {
                "effective_power": _safe_float(node.effective_power),
                "received_power": _safe_float(node.received_power),
                "emitted_power": _safe_float(node.emitted_power),
                "friction_load": _safe_float(node.friction_load),
                "is_source": node.is_source,
                "is_sink": node.is_sink,
                "is_mutual_reception": node.is_mutual_reception,
            }

    # Object meanings
    meaning_short = ""
    meaning_long = ""
    obj_type = ""
    narrative_role = ""
    keywords = []
    if obj.object_name:
        o = obj.object_name
        meaning_short = _safe_str(getattr(o, "short_meaning", ""))
        meaning_long = _safe_str(getattr(o, "long_meaning", ""))
        obj_type = _safe_str(getattr(o, "object_type", ""))
        narrative_role = _safe_str(getattr(o, "narrative_role", ""))
        keywords = list(getattr(o, "keywords", []) or [])

    return {
        "name": name,
        "glyph": glyph,
        "longitude": _safe_float(obj.longitude),
        "sign": sign_name,
        "house": house_num,
        "degree_in_sign": deg_in_sign,
        "minute_in_sign": min_in_sign,
        "dms": _safe_str(obj.dms),
        "retrograde": bool(obj.retrograde),
        "station": _safe_str(obj.station) if obj.station else None,
        "speed": _safe_float(obj.speed),
        "oob_status": _safe_str(obj.oob_status),
        # Sabian
        "sabian_symbol": obj.sabian_symbol.symbol if hasattr(obj.sabian_symbol, "symbol") else _safe_str(obj.sabian_symbol),
        "sabian_index": obj.sabian_index or 0,
        # Meaning
        "meaning_short": meaning_short,
        "meaning_long": meaning_long,
        "object_type": obj_type,
        "narrative_role": narrative_role,
        "keywords": keywords,
        # Strength
        "planetary_state": state_data,
        # Circuit
        "circuit_node": circuit_data,
    }


# ---------------------------------------------------------------------------
# Serialise aspects (edges)
# ---------------------------------------------------------------------------

def _serialize_aspect_edge(
    a_name: str,
    b_name: str,
    aspect_name: str,
    is_major: bool,
    chart: AstrologicalChart,
) -> dict:
    """Build a JSON-safe aspect record enriched with circuit data."""
    # Resolve aspect spec from static lookup
    clean_name = aspect_name.replace("_approx", "").strip()
    is_approx = "_approx" in aspect_name
    spec = ASPECTS.get(clean_name, {})

    result = {
        "obj_a": a_name,
        "obj_b": b_name,
        "aspect": clean_name,
        "angle": spec.get("angle", 0),
        "orb": spec.get("orb", 0),
        "color": spec.get("color", "gray"),
        "style": spec.get("style", "solid"),
        "is_major": is_major,
        "is_approx": is_approx,
    }

    # Enrich with circuit edge data
    sim: Optional[CircuitSimulation] = getattr(chart, "circuit_simulation", None)
    if sim:
        for sc in sim.shape_circuits:
            for edge in sc.edges:
                if _edge_matches(edge, a_name, b_name, clean_name):
                    result["conductance"] = _safe_float(edge.conductance)
                    result["transmitted_power"] = _safe_float(edge.transmitted_power)
                    result["friction_heat"] = _safe_float(edge.friction_heat)
                    result["flow_direction"] = edge.flow_direction
                    result["is_arc_hazard"] = edge.is_arc_hazard
                    result["is_rerouted"] = edge.is_rerouted
                    result["reroute_path"] = list(edge.reroute_path) if edge.reroute_path else []
                    result["is_open_arc"] = edge.is_open_arc
                    break
            else:
                continue
            break

    return result


def _edge_matches(edge: CircuitEdge, a: str, b: str, aspect: str) -> bool:
    """Check if a CircuitEdge matches a pair of names and aspect type."""
    pair = {edge.node_a, edge.node_b}
    return pair == {a, b} and edge.aspect_type == aspect


# ---------------------------------------------------------------------------
# Serialise house cusps
# ---------------------------------------------------------------------------

def _serialize_houses(chart: AstrologicalChart, house_system: str) -> list[dict]:
    """Serialize house cusps for the active system."""
    hs = (house_system or "placidus").strip().lower().replace(" ", "")
    cusp_rows = [
        c for c in chart.house_cusps
        if (c.house_system or "").strip().lower().replace(" ", "") == hs
    ]
    cusp_rows.sort(key=lambda c: c.cusp_number)

    houses = []
    for c in cusp_rows:
        num = c.cusp_number
        deg = _safe_float(c.absolute_degree)
        sign_idx = int(deg // 30) % 12
        sign_name = SIGN_NAMES[sign_idx]
        deg_in_sign = int(deg % 30)

        # House meaning from static
        h_meaning = HOUSE_MEANINGS.get(num, {})

        houses.append({
            "number": num,
            "cusp_degree": deg,
            "sign": sign_name,
            "degree_in_sign": deg_in_sign,
            "life_domain": h_meaning.get("life_domain", "") if isinstance(h_meaning, dict) else _safe_str(h_meaning),
            "short_meaning": h_meaning.get("short_meaning", "") if isinstance(h_meaning, dict) else "",
            "keywords": h_meaning.get("keywords", []) if isinstance(h_meaning, dict) else [],
        })

    # Fallback: generate equal houses from ascendant
    if len(houses) != 12:
        asc_deg = 0.0
        for obj in chart.objects:
            if obj.object_name and obj.object_name.name in ("AC", "Ascendant"):
                asc_deg = _safe_float(obj.longitude)
                break
        houses = []
        for i in range(12):
            deg = (asc_deg + i * 30.0) % 360.0
            sign_idx = int(deg // 30) % 12
            houses.append({
                "number": i + 1,
                "cusp_degree": round(deg, 6),
                "sign": SIGN_NAMES[sign_idx],
                "degree_in_sign": int(deg % 30),
                "life_domain": "",
                "short_meaning": "",
                "keywords": [],
            })

    return houses


# ---------------------------------------------------------------------------
# Serialise zodiac sign ring
# ---------------------------------------------------------------------------

def _serialize_signs(dark_mode: bool) -> list[dict]:
    """Zodiac signs with element color for the band."""
    colors = ELEMENT_COLORS_DARK if dark_mode else ELEMENT_COLORS_LIGHT
    signs = []
    for i in range(12):
        element = SIGN_ELEMENTS[i]
        signs.append({
            "index": i,
            "name": SIGN_NAMES[i],
            "glyph": ZODIAC_SIGNS[i],
            "glyph_color": ZODIAC_COLORS[i],
            "element": element,
            "band_color": colors[element],
            "start_degree": i * 30,
        })
    return signs


# ---------------------------------------------------------------------------
# Serialise shapes (detected patterns)
# ---------------------------------------------------------------------------

def _serialize_shapes(chart: AstrologicalChart) -> list[dict]:
    """Serialize all detected shapes and their circuit simulation data."""
    shapes = chart.shapes or []
    sim: Optional[CircuitSimulation] = getattr(chart, "circuit_simulation", None)

    result = []
    for s in shapes:
        # Support both dict-like and dataclass shapes
        if isinstance(s, dict):
            sid = s.get("id", 0)
            stype = s.get("type", "")
            parent = s.get("parent", 0)
            members = s.get("members", [])
            edges = s.get("edges", [])
        else:
            sid = getattr(s, "shape_id", 0)
            stype = getattr(s, "shape_type", "")
            parent = getattr(s, "parent", 0)
            members = getattr(s, "members", [])
            edges = getattr(s, "edges", [])

        shape_data = {
            "id": sid,
            "type": stype,
            "parent": parent,
            "members": list(members),
            "edges": [
                {
                    "obj_a": e[0][0] if isinstance(e[0], (list, tuple)) else e[0],
                    "obj_b": e[0][1] if isinstance(e[0], (list, tuple)) else "",
                    "aspect": e[1] if len(e) > 1 else "",
                }
                for e in edges
            ],
        }

        # Enrich with circuit simulation data for this shape
        if sim:
            for sc in sim.shape_circuits:
                if sc.shape_id == sid:
                    shape_data["circuit"] = {
                        "total_throughput": _safe_float(sc.total_throughput),
                        "total_friction": _safe_float(sc.total_friction),
                        "dominant_node": sc.dominant_node,
                        "bottleneck_node": sc.bottleneck_node,
                        "resonance_score": _safe_float(sc.resonance_score),
                        "friction_score": _safe_float(sc.friction_score),
                        "flow_characterization": sc.flow_characterization,
                    }
                    break

        result.append(shape_data)

    return result


# ---------------------------------------------------------------------------
# Ascendant degree helper
# ---------------------------------------------------------------------------

def _get_asc_degree(chart: AstrologicalChart) -> float:
    for obj in chart.objects:
        if obj.object_name and obj.object_name.name in ("AC", "Ascendant", "Asc"):
            return _safe_float(obj.longitude)
    return 0.0


# ---------------------------------------------------------------------------
# Top-level serialise function
# ---------------------------------------------------------------------------

def serialize_chart_for_rendering(
    chart: AstrologicalChart,
    *,
    house_system: str = "placidus",
    dark_mode: bool = False,
    label_style: str = "glyph",
    compass_on: bool = True,
    degree_markers: bool = True,
    visible_objects: Optional[List[str]] = None,
    edges_major: Optional[Sequence] = None,
    edges_minor: Optional[Sequence] = None,
    shapes: Optional[list] = None,
    singleton_map: Optional[dict] = None,
    patterns: Optional[list] = None,
    highlights: Optional[dict] = None,
) -> dict:
    """
    Convert a fully-computed AstrologicalChart into a flat JSON-safe
    dictionary for the interactive D3.js chart component.

    Parameters
    ----------
    chart : AstrologicalChart
        The chart object with all post-processing already done (dignity,
        patterns, shapes, circuit simulation).
    house_system : str
        Active house system name.
    dark_mode : bool
        Colour scheme.
    label_style : str
        "glyph" or "text".
    compass_on : bool
        Whether to draw the compass rose.
    degree_markers : bool
        Whether to draw tick marks.
    visible_objects : list[str] | None
        Object names to render.  None = all.
    edges_major / edges_minor : list | None
        Pre-filtered aspect edges.  If None uses chart.edges_major/minor.
    shapes : list | None
        Override shapes list.
    singleton_map : dict | None
        Override singleton map.
    patterns : list | None
        Override aspect group patterns.
    highlights : dict | None
        Elements to highlight: {"objects": [...], "aspects": [...],
        "houses": [...], "shapes": [...]}

    Returns
    -------
    dict
        JSON-safe payload for the interactive chart component.
    """
    unknown_time = getattr(chart, "unknown_time", False)
    asc_deg = _get_asc_degree(chart) if not unknown_time else 0.0

    # --- Objects ---
    obj_map = _object_map(chart)
    objects_data = []
    for obj in chart.objects:
        if not obj.object_name:
            continue
        name = obj.object_name.name
        if visible_objects and name not in visible_objects:
            continue
        objects_data.append(_serialize_object(obj, house_system, chart))

    # --- Aspects ---
    major = edges_major if edges_major is not None else (chart.edges_major or [])
    minor = edges_minor if edges_minor is not None else (chart.edges_minor or [])

    aspects_data = []
    for edge in major:
        a, b = edge[0], edge[1]
        meta = edge[2] if len(edge) > 2 else {}
        asp = meta.get("aspect", "") if isinstance(meta, dict) else str(meta)
        aspects_data.append(_serialize_aspect_edge(a, b, asp, True, chart))

    for edge in minor:
        a, b = edge[0], edge[1]
        meta = edge[2] if len(edge) > 2 else {}
        asp = meta.get("aspect", "") if isinstance(meta, dict) else str(meta)
        aspects_data.append(_serialize_aspect_edge(a, b, asp, False, chart))

    # --- Houses ---
    houses_data = _serialize_houses(chart, house_system)

    # --- Signs ---
    signs_data = _serialize_signs(dark_mode)

    # --- Shapes ---
    if shapes is not None:
        # Use provided shapes (could differ from chart.shapes for combined views)
        chart_copy_shapes = chart.shapes
        chart.shapes = shapes
        shapes_data = _serialize_shapes(chart)
        chart.shapes = chart_copy_shapes
    else:
        shapes_data = _serialize_shapes(chart)

    # --- Singleton map ---
    singleton_data = {}
    sm = singleton_map if singleton_map is not None else getattr(chart, "singleton_map", {}) or {}
    for planet, info in sm.items():
        singleton_data[planet] = True if isinstance(info, bool) else info

    # --- Circuit simulation summary ---
    sim: Optional[CircuitSimulation] = getattr(chart, "circuit_simulation", None)
    circuit_summary = {}
    if sim:
        circuit_summary = {
            "sn_nn_path": list(sim.sn_nn_path) if sim.sn_nn_path else [],
            "singletons": list(sim.singletons) if sim.singletons else [],
            "mutual_receptions": [
                list(mr) if isinstance(mr, (list, tuple)) else [str(mr)]
                for mr in (sim.mutual_receptions or [])
            ],
            "shape_circuit_count": len(sim.shape_circuits),
        }

    # --- Aspect groups (connected components / "circuits") ---
    pats = patterns if patterns is not None else getattr(chart, "aspect_groups", []) or []
    patterns_data = [list(p) for p in pats]

    # --- Config ---
    config = {
        "asc_degree": asc_deg,
        "unknown_time": unknown_time,
        "dark_mode": dark_mode,
        "label_style": label_style,
        "compass_on": compass_on,
        "degree_markers": degree_markers,
        "house_system": house_system,
    }

    # --- Color palettes (for JS to use directly) ---
    colors = {
        "group_colors": list(GROUP_COLORS),
        "subshape_colors": list(SUBSHAPE_COLORS),
        "zodiac_colors": list(ZODIAC_COLORS),
        "element_band_colors": ELEMENT_COLORS_DARK if dark_mode else ELEMENT_COLORS_LIGHT,
    }

    # --- Highlights ---
    hl = highlights or {}

    return {
        "objects": objects_data,
        "aspects": aspects_data,
        "houses": houses_data,
        "signs": signs_data,
        "shapes": shapes_data,
        "singletons": singleton_data,
        "circuit_summary": circuit_summary,
        "patterns": patterns_data,
        "config": config,
        "colors": colors,
        "highlights": hl,
    }
