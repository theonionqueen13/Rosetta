"""
reading_engine.py — Deterministic chart → ReadingPacket orchestrator.

Takes a free-text question and an AstrologicalChart, and produces a
ReadingPacket containing *only* pre-computed, hard-coded astrological
facts.  No LLM is involved at this stage.

Pipeline:
  1. Route the question via topic_maps → relevant factors
  2. Filter the chart to those factors
  3. Collect placements, aspects, patterns, dignities, dispositors
  4. Optionally run NatalInterpreter for pre-baked prose
  5. Pack everything into a ReadingPacket
"""

from __future__ import annotations

import re
import sys
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Path management: ensure the project root is importable so that we can
# reach models_v2, calc_v2, interp_base_natal, etc. from any working dir.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.mcp.topic_maps import resolve_factors, TopicMatch
from src.mcp.reading_packet import (
    AspectFact,
    DignityFact,
    DispositorFact,
    HouseOverview,
    PatternFact,
    PlacementFact,
    ReadingPacket,
    SabianFact,
    SectFact,
)

if TYPE_CHECKING:
    from models_v2 import AstrologicalChart, ChartObject, StaticLookup

# Lazy import of heavy modules — only pulled in when actually needed.
_static_db: Any = None


def _get_static_db() -> Any:
    global _static_db
    if _static_db is None:
        from models_v2 import static_db
        _static_db = static_db
    return _static_db


# ═══════════════════════════════════════════════════════════════════════
# Factor classification helpers
# ═══════════════════════════════════════════════════════════════════════

# Canonical sign names (for recognizing "Aries" in the factors list)
_SIGN_NAMES: Set[str] = {
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
}

# House pattern (e.g., "1st House", "10th House")
_HOUSE_RE = re.compile(r"^(\d+)\w*\s+[Hh]ouse$")


def _classify_factors(factors: List[str]):
    """Split a mixed factor list into (object_names, sign_names, house_numbers)."""
    objects: List[str] = []
    signs: List[str] = []
    houses: List[int] = []
    for f in factors:
        if f in _SIGN_NAMES:
            signs.append(f)
        else:
            m = _HOUSE_RE.match(f)
            if m:
                houses.append(int(m.group(1)))
            else:
                objects.append(f)
    return objects, signs, houses


# ═══════════════════════════════════════════════════════════════════════
# Combo-key normalization (mirrors interp_base_natal logic)
# ═══════════════════════════════════════════════════════════════════════

_COMBO_NAME_MAP: Dict[str, str] = {
    "Ascendant": "AC",
    "Descendant": "DC",
    "Midheaven": "MC",
    "Immum Coeli": "IC",
    "North Node": "NorthNode",
    "South Node": "SouthNode",
    "Black Moon Lilith (Mean)": "Lilith",
    "Black Moon Lilith (True)": "Lilith",
    "Black Moon Lilith": "Lilith",
    "Part of Fortune": "PartOfFortune",
}


def _combo_key(obj_name: str) -> str:
    """Normalize an object name for combo dictionary keys."""
    if obj_name in _COMBO_NAME_MAP:
        return _COMBO_NAME_MAP[obj_name]
    return obj_name.replace(" ", "")


# ═══════════════════════════════════════════════════════════════════════
# Core engine
# ═══════════════════════════════════════════════════════════════════════

def build_reading(
    question: str,
    chart: "AstrologicalChart",
    *,
    house_system: str = "placidus",
    include_sabians: bool = False,
    include_interp_text: bool = True,
    max_aspects: int = 20,
) -> ReadingPacket:
    """Produce a ReadingPacket for *question* against *chart*.

    Parameters
    ----------
    question : str
        Free-text user question (e.g. "Tell me about my career").
    chart : AstrologicalChart
        A fully computed chart (objects, aspects, patterns populated).
    house_system : str
        Which house system to use for house assignments.
    include_sabians : bool
        If True, include Sabian symbols in the packet.
    include_interp_text : bool
        If True, run NatalInterpreter and embed its output.
    max_aspects : int
        Cap the number of aspect facts to include.

    Returns
    -------
    ReadingPacket
    """
    static = _get_static_db()

    # ── 1. Route the question ────────────────────────────────────────
    topic: TopicMatch = resolve_factors(question)
    obj_names, sign_names, house_numbers = _classify_factors(topic.factors)

    # ── 2. Identify matching chart objects ───────────────────────────
    # We match objects by name, objects in requested signs, and objects
    # in requested houses.
    relevant_objects: List["ChartObject"] = []
    relevant_names: Set[str] = set()

    for cobj in chart.objects:
        name = cobj.object_name.name if cobj.object_name else ""
        sign = cobj.sign.name if cobj.sign else ""
        house_num = _house_number(cobj, house_system)

        hit = False
        if name in obj_names:
            hit = True
        if sign in sign_names:
            hit = True
        if house_num in house_numbers:
            hit = True

        if hit:
            relevant_objects.append(cobj)
            relevant_names.add(name)

    # If topic routing returned house numbers but no objects matched,
    # still include the house overviews (handled below).

    # ── 3. Build placement facts ─────────────────────────────────────
    placements = _build_placements(relevant_objects, house_system, static)

    # ── 4. Build aspect facts ────────────────────────────────────────
    aspects = _build_aspects(chart, relevant_names, max_aspects)

    # ── 5. Build pattern facts ───────────────────────────────────────
    patterns = _build_patterns(chart, relevant_names)

    # ── 6. Build dignity facts ───────────────────────────────────────
    dignities = _build_dignities(relevant_objects)

    # ── 7. Build dispositor facts ────────────────────────────────────
    dispositors = _build_dispositors(chart, relevant_names)

    # ── 8. Build house overviews ─────────────────────────────────────
    houses = _build_house_overviews(chart, house_numbers, house_system, static)

    # ── 9. Sabian symbols (optional) ─────────────────────────────────
    sabians: List[SabianFact] = []
    if include_sabians:
        sabians = _build_sabians(relevant_objects)

    # ── 10. Sect ──────────────────────────────────────────────────────
    sect_fact = _build_sect(chart)

    # ── 11. Optional NatalInterpreter text ────────────────────────────
    interp_text = ""
    if include_interp_text and relevant_names:
        interp_text = _run_interp(chart, relevant_names, house_system)

    # ── 12. Pack it ──────────────────────────────────────────────────
    # Chart header
    hdr = chart.header_lines() if hasattr(chart, "header_lines") else ("", "", "", "", "")
    chart_name = hdr[0] if hdr else ""
    chart_date = hdr[1] if len(hdr) > 1 else ""
    chart_time = hdr[2] if len(hdr) > 2 else ""
    chart_city = hdr[3] if len(hdr) > 3 else ""

    return ReadingPacket(
        question=question,
        domain=topic.domain,
        subtopic=topic.subtopic,
        confidence=topic.confidence,
        matched_keywords=topic.matched_keywords,
        chart_name=chart_name,
        chart_date=chart_date,
        chart_time=chart_time,
        chart_city=chart_city,
        unknown_time=bool(chart.unknown_time),
        placements=placements,
        aspects=aspects,
        patterns=patterns,
        dispositors=dispositors,
        dignities=dignities,
        houses=houses,
        sabians=sabians,
        sect=sect_fact,
        interp_text=interp_text,
    )


# ═══════════════════════════════════════════════════════════════════════
# Builder helpers
# ═══════════════════════════════════════════════════════════════════════

def _house_number(cobj: "ChartObject", system: str) -> int:
    """Get the house number for a ChartObject under the given system."""
    system = system.lower().strip()
    if system == "equal":
        h = cobj.equal_house
    elif system == "whole":
        h = cobj.whole_sign_house
    else:
        h = cobj.placidus_house
    return h.number if h else 0


def _build_placements(
    objects: List["ChartObject"],
    house_system: str,
    static: Any,
) -> List[PlacementFact]:
    """Build PlacementFact list from chart objects."""
    combo_signs = getattr(static, "object_sign_combos", {})
    combo_houses = getattr(static, "object_house_combos", {})
    out: List[PlacementFact] = []

    for cobj in objects:
        name = cobj.object_name.name if cobj.object_name else ""
        sign = cobj.sign.name if cobj.sign else ""
        house_num = _house_number(cobj, house_system)

        # Sign combo text
        sign_text = ""
        ck = _combo_key(name)
        sc = combo_signs.get(f"{ck}_{sign}")
        if sc:
            sign_text = getattr(sc, "interpretation", "") or getattr(sc, "meaning", "") or ""

        # House combo text
        house_text = ""
        hc = combo_houses.get(f"{ck}_House_{house_num}")
        if hc:
            house_text = getattr(hc, "interpretation", "") or getattr(hc, "meaning", "") or ""

        dignity_str = ""
        if cobj.dignity:
            dignity_str = cobj.dignity if isinstance(cobj.dignity, str) else cobj.dignity.name

        out.append(PlacementFact(
            object_name=name,
            glyph=cobj.glyph or "",
            sign=sign,
            sign_element=cobj.sign.element if cobj.sign else "",
            sign_modality=cobj.sign.modality if cobj.sign else "",
            house=house_num,
            degree=cobj.dms or "",
            retrograde=bool(cobj.retrograde),
            dignity=dignity_str,
            oob=cobj.oob_status or "",
            object_type=cobj.object_name.object_type if cobj.object_name else "",
            narrative_role=cobj.object_name.narrative_role if cobj.object_name else "",
            short_meaning=cobj.object_name.short_meaning if cobj.object_name else "",
            sign_combo_text=sign_text,
            house_combo_text=house_text,
        ))
    return out


def _build_aspects(
    chart: "AstrologicalChart",
    relevant_names: Set[str],
    max_count: int,
) -> List[AspectFact]:
    """Collect aspects involving relevant objects, limited to *max_count*."""
    out: List[AspectFact] = []

    # edges_major is a list of tuples (obj1_name, obj2_name, aspect_type_str)
    # or a list of ChartAspect objects — handle both shapes.
    edges = list(chart.edges_major or []) + list(chart.edges_minor or [])

    for edge in edges:
        # Handle ChartAspect dataclass
        if hasattr(edge, "object1"):
            o1 = edge.object1.object_name.name if edge.object1 and edge.object1.object_name else ""
            o2 = edge.object2.object_name.name if edge.object2 and edge.object2.object_name else ""
            if o1 not in relevant_names and o2 not in relevant_names:
                continue
            asp = edge.aspect_type
            out.append(AspectFact(
                object1=o1,
                object2=o2,
                aspect_name=asp.name if asp else "",
                aspect_glyph=asp.glyph if asp else "",
                angle=asp.angle if asp else 0,
                orb=float(edge.orb) if edge.orb else 0.0,
                applying=bool(edge.applying),
                mutual_reception=bool(edge.mutual_reception),
                aspect_meaning=asp.sentence_meaning if asp else "",
                aspect_polarity=asp.polarity if asp else "",
            ))
        # Handle tuple form (name1, name2, aspect_str)
        elif isinstance(edge, (list, tuple)) and len(edge) >= 3:
            o1, o2 = str(edge[0]), str(edge[1])
            if o1 not in relevant_names and o2 not in relevant_names:
                continue
            asp_str = str(edge[2]) if len(edge) > 2 else ""
            out.append(AspectFact(
                object1=o1,
                object2=o2,
                aspect_name=asp_str,
                aspect_glyph="",
                angle=0,
                orb=0.0,
                applying=False,
            ))

        if len(out) >= max_count:
            break

    return out


def _build_patterns(
    chart: "AstrologicalChart",
    relevant_names: Set[str],
) -> List[PatternFact]:
    """Extract patterns (shapes) involving relevant objects."""
    out: List[PatternFact] = []
    for shape in (chart.shapes or []):
        # Shapes have varying structures but all have a `name` attr
        shape_name = getattr(shape, "name", type(shape).__name__)
        # Collect member names from node_* attrs
        members: List[str] = []
        for attr in dir(shape):
            if attr.startswith("node_") or attr in ("apex", "base_1", "base_2"):
                node = getattr(shape, attr, None)
                if node and hasattr(node, "name"):
                    members.append(node.name)
                elif node and hasattr(node, "object_name"):
                    n = node.object_name
                    members.append(n.name if hasattr(n, "name") else str(n))
        # Only include if at least one member is relevant
        if members and (relevant_names & set(members)):
            meaning = getattr(shape, "meaning", "")
            out.append(PatternFact(
                pattern_type=shape_name,
                members=members,
                meaning=meaning or "",
            ))
    return out


def _build_dignities(objects: List["ChartObject"]) -> List[DignityFact]:
    """Build DignityFact list from chart objects that have a dignity."""
    out: List[DignityFact] = []
    for cobj in objects:
        if cobj.dignity:
            dtype = cobj.dignity if isinstance(cobj.dignity, str) else cobj.dignity.name
            if dtype and dtype.lower() not in ("", "none"):
                out.append(DignityFact(
                    object_name=cobj.object_name.name if cobj.object_name else "",
                    dignity_type=dtype,
                    sign=cobj.sign.name if cobj.sign else "",
                ))
    return out


def _build_dispositors(
    chart: "AstrologicalChart",
    relevant_names: Set[str],
) -> List[DispositorFact]:
    """Build dispositor facts from chart.dispositor_chains_rows."""
    out: List[DispositorFact] = []
    for row in (chart.dispositor_chains_rows or []):
        # Each row is typically a dict or list with object/ruler info
        if isinstance(row, dict):
            obj = row.get("object", row.get("planet", ""))
            ruler = row.get("ruler", row.get("dispositor", ""))
            chain = row.get("chain", [])
            if isinstance(chain, str):
                chain = [s.strip() for s in chain.split("→")]
            is_final = bool(row.get("final_dispositor", False))
            if obj in relevant_names or ruler in relevant_names:
                out.append(DispositorFact(
                    object_name=obj,
                    ruled_by=ruler,
                    chain=chain,
                    is_final_dispositor=is_final,
                ))
    return out


def _build_house_overviews(
    chart: "AstrologicalChart",
    house_numbers: List[int],
    house_system: str,
    static: Any,
) -> List[HouseOverview]:
    """Build HouseOverview facts for requested house numbers."""
    if not house_numbers:
        return []

    out: List[HouseOverview] = []
    houses_static = getattr(static, "houses", {})

    for h_num in sorted(set(house_numbers)):
        # Find cusp sign from chart.house_cusps
        cusp_sign = ""
        ruler = ""
        for cusp in (chart.house_cusps or []):
            hs = getattr(cusp, "house_system", "")
            if str(hs).lower().strip() == house_system.lower().strip():
                if getattr(cusp, "house_number", 0) == h_num:
                    cusp_sign = getattr(cusp, "sign", "")
                    if hasattr(cusp_sign, "name"):
                        cusp_sign = cusp_sign.name
                    # ruler from sign's rulers
                    signs_db = getattr(static, "signs", {})
                    sign_obj = signs_db.get(str(cusp_sign))
                    if sign_obj and sign_obj.rulers:
                        ruler = sign_obj.rulers[0]
                    break

        # Objects in this house
        occupants: List[str] = []
        for cobj in chart.objects:
            if _house_number(cobj, house_system) == h_num:
                occupants.append(cobj.object_name.name if cobj.object_name else "")

        # House meaning from static lookup
        meaning = ""
        h_static = houses_static.get(h_num)
        if h_static:
            meaning = getattr(h_static, "short_meaning", "")

        out.append(HouseOverview(
            house_number=h_num,
            sign_on_cusp=str(cusp_sign),
            ruler=ruler,
            occupants=[o for o in occupants if o],
            meaning=meaning,
        ))
    return out


def _build_sabians(objects: List["ChartObject"]) -> List[SabianFact]:
    """Build Sabian symbols for the given objects."""
    out: List[SabianFact] = []
    for cobj in objects:
        sab = cobj.sabian_symbol
        if sab:
            name = cobj.object_name.name if cobj.object_name else ""
            text = getattr(sab, "symbol", "") or getattr(sab, "text", "")
            keynote = getattr(sab, "keynote", "")
            out.append(SabianFact(
                object_name=name,
                degree_index=cobj.sabian_index or 0,
                symbol_text=str(text),
                keynote=str(keynote) if keynote else "",
            ))
    return out


def _build_sect(chart: "AstrologicalChart") -> Optional[SectFact]:
    """Build sect fact from chart.sect string."""
    sect_str = chart.sect
    if not sect_str:
        return None
    # chart.sect is something like "Day Sect" or "Night Sect" or "Diurnal" / "Nocturnal"
    # Normalize
    s = str(sect_str).strip().lower()
    if "day" in s or "diurnal" in s:
        return SectFact(
            sect="Diurnal",
            sect_light="Sun",
            benefic_of_sect="Jupiter",
            malefic_of_sect="Saturn",
        )
    elif "night" in s or "nocturnal" in s:
        return SectFact(
            sect="Nocturnal",
            sect_light="Moon",
            benefic_of_sect="Venus",
            malefic_of_sect="Mars",
        )
    return None


def _run_interp(
    chart: "AstrologicalChart",
    relevant_names: Set[str],
    house_system: str,
) -> str:
    """Run NatalInterpreter in focus mode for each relevant object.

    Returns combined text (may be empty if interp module unavailable).
    """
    try:
        from interp_base_natal import NatalInterpreter
        from drawing_v2 import RenderResult

        # Build a minimal RenderResult so the interpreter has what it needs.
        positions = chart.positions or {}
        cusps_list: List[float] = []
        for c in (chart.house_cusps or []):
            hs = getattr(c, "house_system", "")
            if str(hs).lower().strip() == house_system.lower().strip():
                cusps_list.append(float(getattr(c, "absolute_degree", 0)))

        # We need edges as tuples
        major_edges = [tuple(e) if isinstance(e, (list, tuple)) else e
                       for e in (chart.edges_major or [])]
        minor_edges = [tuple(e) if isinstance(e, (list, tuple)) else e
                       for e in (chart.edges_minor or [])]

        rr = RenderResult(
            fig=None, ax=None,
            positions=positions,
            cusps=cusps_list,
            visible_objects=list(relevant_names),
            drawn_major_edges=major_edges,
            drawn_minor_edges=minor_edges,
            patterns=chart.aspect_groups or [],
            shapes=chart.shapes or [],
            singleton_map=chart.singleton_map or {},
        )

        parts: List[str] = []
        for obj_name in sorted(relevant_names):
            try:
                interp = NatalInterpreter(
                    render_result=rr,
                    mode="focus",
                    object_name=obj_name,
                    chart=chart,
                )
                text = interp.generate()
                if text:
                    parts.append(text.strip())
            except Exception:
                continue

        return "\n\n".join(parts)
    except Exception:
        return ""
