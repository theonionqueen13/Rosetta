"""Global context builders used by the Rosetta brain."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

import networkx as nx
import pandas as pd

from rosetta.brain_constants import (
    HOUSE_MEANINGS,
    OBJECT_MEANINGS,
    PLANETARY_RULERS,
    SHAPE_INSTRUCTIONS,
    SIGN_MEANINGS,
    SIGN_NAMES,
)
from rosetta.brain_helpers import (
    _deg_in_sign,
    _extract_cusps_from_df,
    _house_of_degree,
    _in_forward_arc,
    _norm_name,
    _sign_index,
)


def build_dispositor_context(pos: dict, df: pd.DataFrame | None) -> dict:
    """Map each object to the ruler of its sign and house.

    The ``df`` DataFrame is expected to contain rows for house cusps with
    ``Object`` labels like ``"1 H Cusp"`` and a ``Longitude`` column. Values come
    directly from the chart calculator output.
    """

    cusps = _extract_cusps_from_df(df)
    out = {}

    for obj, deg in pos.items():
        sign_idx = _sign_index(deg)
        sign = SIGN_NAMES[sign_idx]
        sign_ruler = PLANETARY_RULERS.get(sign, "")

        house = _house_of_degree(deg, cusps) if cusps else None
        house_ruler = ""
        if house and cusps and 1 <= house <= 12:
            cusp_deg = cusps[house - 1]
            cusp_sign = SIGN_NAMES[_sign_index(cusp_deg)]
            house_ruler = PLANETARY_RULERS.get(cusp_sign, "")

        out[_norm_name(obj)] = {
            "sign": sign,
            "sign_ruler": sign_ruler,
            "house": int(house) if house else None,
            "house_ruler": house_ruler,
        }

    return {"dispositors": out}


def build_compass_context(pos: Dict[str, float], df: pd.DataFrame | None) -> dict:
    """Attach basic profile data for Compass Rose points.

    The DataFrame mirrors the profile data emitted by ``calc.calculate_chart``.
    When house cusps are present, the function also resolves the house index for
    each compass point.
    """

    compass_points = ["Ascendant", "Descendant", "MC", "IC", "North Node", "South Node"]
    out: Dict[str, Dict[str, Any]] = {}
    for pt in compass_points:
        deg = pos.get(pt)
        if deg is None:
            continue
        sign_idx = _sign_index(deg)
        sign = SIGN_NAMES[sign_idx]
        house = None
        cusps = _extract_cusps_from_df(df)
        if cusps:
            house = _house_of_degree(deg, cusps)

        out[pt] = {
            "absolute_degree": round(deg % 360.0, 2),
            "sign": sign,
            "degree_in_sign": _deg_in_sign(deg),
            "house": house,
            "sign_meaning": SIGN_MEANINGS.get(sign, ""),
            "object_meaning": OBJECT_MEANINGS.get(pt, ""),
        }
    return {"compass": out}


def build_shapes_context(active_shapes: List[str] | None) -> dict:
    """Convert detected shape IDs into human-readable instructions."""

    out = []
    for shape in active_shapes or []:
        instruction = SHAPE_INSTRUCTIONS.get(shape, "")
        out.append({"name": shape, "instruction": instruction})
    return {"shapes": out}


def analyze_dispositors(pos: dict, df: pd.DataFrame | None) -> dict:
    """Summarize sign/house dispositor graphs.

    The calculator DataFrame should include the same cusp rows described in
    :func:`build_dispositor_context`. This function reports dominant rulers,
    final dispositors, sovereign rulers, and loops separately for sign and house
    rulerships.
    """

    cusps = _extract_cusps_from_df(df)
    G_sign = nx.DiGraph()
    G_house = nx.DiGraph()

    def _add_edges(graph: nx.DiGraph, src: str, dsts: Mapping[str, Any] | str | list | tuple | set | None):
        if not dsts:
            graph.add_node(src)
            return

        if isinstance(dsts, str):
            candidates = [dsts]
        elif isinstance(dsts, (list, tuple, set)):
            candidates = list(dsts)
        else:
            candidates = [dsts]

        added = False
        for d in candidates:
            if not d:
                continue
            graph.add_edge(src, d)
            added = True

        if not added:
            graph.add_node(src)

    for obj, deg in pos.items():
        sign = SIGN_NAMES[_sign_index(deg)]
        sign_rulers = PLANETARY_RULERS.get(sign, [])
        _add_edges(G_sign, obj, sign_rulers)

        if cusps:
            h = _house_of_degree(deg, cusps)
            if h:
                cusp_sign = SIGN_NAMES[_sign_index(cusps[h - 1])]
                house_rulers = PLANETARY_RULERS.get(cusp_sign, [])
                _add_edges(G_house, obj, house_rulers)
            else:
                G_house.add_node(obj)
        else:
            G_house.add_node(obj)

    def _summarize(graph: nx.DiGraph) -> dict:
        if graph.number_of_nodes() == 0:
            return {
                "dominant_rulers": [],
                "final_dispositors": [],
                "sovereign": [],
                "loops": [],
            }

        cycles = list(nx.simple_cycles(graph))
        sovereign = sorted([c[0] for c in cycles if len(c) == 1])
        loops = [c for c in cycles if len(c) >= 2]

        dominant = sorted([n for n, outdeg in graph.out_degree() if outdeg >= 3])
        final = sorted([
            n for n in graph.nodes if graph.out_degree(n) == 0 and graph.in_degree(n) >= 1
        ])

        return {
            "dominant_rulers": dominant,
            "final_dispositors": final,
            "sovereign": sovereign,
            "loops": loops,
        }

    return {
        "by_sign": _summarize(G_sign),
        "by_house": _summarize(G_house),
    }


__all__ = [
    "analyze_dispositors",
    "build_compass_context",
    "build_dispositor_context",
    "build_shapes_context",
]
