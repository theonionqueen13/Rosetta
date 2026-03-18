"""
reading_engine.py — Circuit-driven chart → ReadingPacket orchestrator.

Pipeline:
  1. Comprehend the question → QuestionGraph (LLM or keyword fallback)
  2. Query the circuit simulation → CircuitReading (subgraph extraction)
  3. Collect classical facts (placements, aspects, patterns, dignities,
     dispositors, houses, sect, sabians) filtered to relevant factors
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
from src.mcp.comprehension import comprehend, QuestionGraph
from src.mcp.comprehension_models import ComprehensionResult, PersonProfile, Location
from src.mcp.circuit_query import query_circuit, CircuitReading
from src.mcp.term_registry import TermIntent, assign_potency_tiers
from src.mcp.agent_memory import AgentMemory
from src.mcp.reading_packet import (
    AspectFact,
    CircuitFlowFact,
    CircuitPathFact,
    DignityFact,
    DispositorFact,
    HouseOverview,
    PatternFact,
    PlacementFact,
    PowerNodeFact,
    ReadingPacket,
    SabianFact,
    SectFact,
    SwitchPointFact,
)

if TYPE_CHECKING:
    from models_v2 import AstrologicalChart, ChartObject, StaticLookup

# Lazy imports of heavy modules — only pulled in when actually needed.
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
    api_key: Optional[str] = None,
    agent_notes: str = "",
    render_result: Optional[Any] = None,
    chart_b: Optional["AstrologicalChart"] = None,
    edges_inter_chart: Optional[List] = None,
    known_persons: Optional[List[PersonProfile]] = None,
    known_locations: Optional[List[Location]] = None,
    pending_clarification: Optional[str] = None,
    agent_memory: Optional[AgentMemory] = None,
) -> ReadingPacket:
    """Produce a ReadingPacket for *question* against *chart*.

    Pipeline:
      1. Comprehend → ComprehensionResult (structured LLM or keyword fallback)
         - If clarification needed, return a special packet signalling that.
      2. Query circuit → CircuitReading (subgraph extraction)
      3. Classical facts (placements, aspects, patterns, etc.)
      4. Optional NatalInterpreter text
      5. Pack into ReadingPacket

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
    api_key : str, optional
        OpenRouter API key for the comprehension LLM call.
    agent_notes : str
        Accumulated agent notes from the conversation.
    chart_b : AstrologicalChart, optional
        Second chart when in biwheel mode (synastry / transits).
    known_persons : list of PersonProfile, optional
        Accumulated person profiles from prior turns in the session.
    known_locations : list of Location, optional
        Accumulated locations from prior turns in the session.
    pending_clarification : str, optional
        User's answer to a prior ClarificationRequest.

    Returns
    -------
    ReadingPacket
    """
    static = _get_static_db()

    # ── 0. Log the user's question in agent memory ───────────────────
    _uq_id: Optional[str] = None
    if agent_memory is not None:
        _uq = agent_memory.add_user_question(text=question)
        _uq_id = _uq.id

    # ── 1. Comprehend the question ───────────────────────────────────
    comp_result: ComprehensionResult = comprehend(
        question, chart, api_key=api_key,
        known_persons=known_persons,
        known_locations=known_locations,
        pending_clarification=pending_clarification,
    )

    # ── 1a. Handle clarification request ─────────────────────────────
    if comp_result.needs_clarification:
        clar = comp_result.clarification
        follow_up = clar.follow_up_question if clar else ""

        # Log a BotQuestion blocking the reading todo in agent memory
        if agent_memory is not None and follow_up:
            _todo = agent_memory.add_todo(
                description=f"Build reading for: {question[:120]}",
                source="pipeline",
            )
            agent_memory.add_bot_question(
                text=follow_up,
                prerequisite_for=[_todo.id],
            )

        return ReadingPacket(
            question=question,
            comprehension_note=f"CLARIFICATION_NEEDED: {follow_up}" if clar else "",
            agent_notes=agent_notes,
            # Store serialized clarification for the UI to detect
            _clarification=clar.to_dict() if clar else {},
        )

    q_graph: QuestionGraph = comp_result.graph  # type: ignore[assignment]
    # ── 1b. Potency-ranking branch ──────────────────────────
    # When the question is about planetary power / influence, bypass the
    # circuit-focus filter and instead rank ALL chart planets by their
    # dignity_calc power index, returning tier labels only (no raw numbers).
    _potency_nodes: Optional[List[PowerNodeFact]] = None
    if q_graph.question_intent == TermIntent.POTENCY_RANKING:
        _ps = getattr(chart, "planetary_states", None)
        if not _ps:
            try:
                from dignity_calc import score_and_attach
                score_and_attach(chart)
                _ps = getattr(chart, "planetary_states", None)
            except Exception:
                pass
        if _ps:
            _tier_map = assign_potency_tiers(_ps)
            _sorted_ps = sorted(
                _ps.items(),
                key=lambda kv: getattr(kv[1], "power_index", 0.0),
                reverse=True,
            )
            _potency_nodes = [
                PowerNodeFact(
                    planet_name=pname,
                    power_index=getattr(ps, "power_index", 0.0),
                    effective_power=getattr(ps, "power_index", 0.0),
                    is_mutual_reception=bool(
                        getattr(ps, "mutual_reception", False)
                    ),
                    tier_label=_tier_map.get(pname, ""),
                )
                for pname, ps in _sorted_ps
            ]
    # ── 2. Query the circuit simulation ──────────────────────────────
    circuit_reading: CircuitReading = query_circuit(q_graph, chart)

    # ── 3. Determine relevant factors for classical fact collection ──
    # When the question intent is already resolved (e.g. potency_ranking),
    # the reading engine handles factor selection internally — injecting
    # legacy topic_maps factors here would only add noise.  For all other
    # questions, merge comprehension factors with topic_maps as a fallback.
    all_factors = list(q_graph.all_factors)
    if not q_graph.question_intent:
        # Legacy topic_maps fallback: run only when intent is unresolved
        topic: TopicMatch = resolve_factors(question)
        legacy_factors = topic.factors or []
        merged_factors = list(dict.fromkeys(all_factors + legacy_factors))
    else:
        # Intent-resolved: trust the comprehension layer, skip keyword guessing
        topic = resolve_factors.__wrapped__(question) if hasattr(resolve_factors, "__wrapped__") else type(
            "_T", (), {"domain": q_graph.domain, "subtopic": q_graph.subtopic,
                       "factors": [], "matched_keywords": [], "confidence": q_graph.confidence})()
        legacy_factors = []
        merged_factors = list(all_factors)

    obj_names, sign_names, house_numbers = _classify_factors(merged_factors)

    # ── 4. Identify matching chart objects ───────────────────────────
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

    # Also include planets that appear in focus_nodes from circuit query
    for node in circuit_reading.focus_nodes:
        pname = node.planet_name
        if pname not in relevant_names:
            for cobj in chart.objects:
                n = cobj.object_name.name if cobj.object_name else ""
                if n == pname:
                    relevant_objects.append(cobj)
                    relevant_names.add(n)
                    break

    # ── 5. Build classical facts ─────────────────────────────────────
    placements = _build_placements(relevant_objects, house_system, static)
    aspects = _build_aspects(chart, relevant_names, max_aspects)
    patterns = _build_patterns(chart, relevant_names, render_result=render_result)
    dignities = _build_dignities(relevant_objects)
    dispositors = _build_dispositors(chart, relevant_names)
    houses = _build_house_overviews(chart, house_numbers, house_system, static)

    sabians: List[SabianFact] = []
    if include_sabians:
        sabians = _build_sabians(relevant_objects)

    sect_fact = _build_sect(chart)
    switch_points = _build_switch_points(chart, house_system)

    # ── Optional NatalInterpreter text ────────────────────────────
    interp_text = ""
    if include_interp_text and relevant_names:
        interp_text = _run_interp(chart, relevant_names, house_system)

    # ── Modular planet profiles (PlanetStats + PlanetProfile) ────────
    _planet_stats_list: List[Dict[str, Any]] = []
    _planet_profiles_list: List[Dict[str, Any]] = []
    try:
        from planet_profiles import PlanetStats, PlanetProfile, PlanetStatsReader
        for _robj in relevant_objects:
            try:
                _ps = PlanetStats.from_chart_object(_robj, house_system=house_system)
                _planet_stats_list.append(_ps.to_dict())
            except Exception:
                pass
            try:
                _pp = PlanetProfile.from_chart_object(
                    _robj,
                    house_system=house_system,
                    lookup=None,
                    chart_objects=list(chart.objects),
                    chart=chart,
                )
                _planet_profiles_list.append(_pp.to_dict())
            except Exception:
                pass
    except ImportError:
        pass

    # ── Visible objects from current render state ─────────────────────────
    visible_objects: List[str] = []
    if render_result and hasattr(render_result, "visible_objects"):
        visible_objects = list(render_result.visible_objects or [])
    # ── Full chart context — ALL objects, always included ─────────────────
    # This gives the LLM complete chart awareness regardless of what the
    # user has toggled on or what the question's relevance filter captured.
    full_chart_placements = _build_full_placements(chart, house_system)

    # ── Second chart (biwheel) full placements + full parity facts ────────────
    chart_b_name = ""
    chart_b_date = ""
    chart_b_city = ""
    chart_b_full_placements: List[PlacementFact] = []
    chart_b_aspects: List[AspectFact] = []
    chart_b_patterns: List[PatternFact] = []
    chart_b_dignities: List[DignityFact] = []
    chart_b_dispositors: List[DispositorFact] = []
    chart_b_sect: Optional[SectFact] = None
    if chart_b is not None:
        chart_b_full_placements = _build_full_placements(chart_b, house_system)
        b_hdr = chart_b.header_lines() if hasattr(chart_b, "header_lines") else ("", "", "", "", "")
        chart_b_name = b_hdr[0] if b_hdr else ""
        chart_b_date = b_hdr[1] if len(b_hdr) > 1 else ""
        chart_b_city = b_hdr[3] if len(b_hdr) > 3 else ""
        # Build full parity classical facts for chart_b
        _b_all_names: Set[str] = {
            cobj.object_name.name
            for cobj in chart_b.objects
            if cobj.object_name
        }
        chart_b_aspects = _build_aspects(chart_b, _b_all_names, max_aspects)
        chart_b_patterns = _build_patterns(chart_b, _b_all_names)
        chart_b_dignities = _build_dignities(list(chart_b.objects))
        chart_b_dispositors = _build_dispositors(chart_b, _b_all_names)
        chart_b_sect = _build_sect(chart_b)

    # Convert pre-computed inter-chart aspect tuples → serialisable dicts
    inter_chart_aspects_raw: List[Dict[str, str]] = []
    for _record in (edges_inter_chart or []):
        if isinstance(_record, (list, tuple)) and len(_record) >= 3:
            inter_chart_aspects_raw.append({
                "planet_1": str(_record[0]),
                "planet_2": str(_record[1]),
                "aspect": str(_record[2]),
            })

    # Soft gate: flag when a dyadic question was asked but no second chart loaded
    _needs_chart_b = (
        q_graph.subject_config == "dyadic"
        and chart_b is None
    )

    # ── 7. Convert circuit reading to packet fact types ──────────────
    circuit_flows = _circuit_reading_to_flows(circuit_reading, chart)
    # Use tier-labelled potency nodes for potency_ranking questions;
    # fall back to plain circuit-derived nodes otherwise.
    power_nodes = _potency_nodes if _potency_nodes is not None else _circuit_reading_to_power_nodes(circuit_reading)
    circuit_paths = _circuit_reading_to_paths(circuit_reading)

    # ── 8. Pack it ───────────────────────────────────────────────────
    hdr = chart.header_lines() if hasattr(chart, "header_lines") else ("", "", "", "", "")
    chart_name = hdr[0] if hdr else ""
    chart_date = hdr[1] if len(hdr) > 1 else ""
    chart_time = hdr[2] if len(hdr) > 2 else ""
    chart_city = hdr[3] if len(hdr) > 3 else ""

    # ── Debug summary for the dev inner-monologue panel ────────────
    _circuit_debug: Dict[str, Any] = {
        "shapes_count": len(circuit_reading.relevant_shapes),
        "focus_nodes": [getattr(n, "planet_name", str(n)) for n in circuit_reading.focus_nodes],
        "sn_nn_relevance": circuit_reading.sn_nn_relevance or "",
        "narrative_seeds": list(circuit_reading.narrative_seeds or []),
        "power_summary": dict(circuit_reading.power_summary or {}),
    }

    # ── 9. Update agent memory cross-tags & mark question answered ───
    if agent_memory is not None and _uq_id is not None:
        _shape_refs = [
            getattr(cf, "shape_type", "") or getattr(cf, "name", "")
            for cf in (circuit_flows or [])
        ]
        _circuit_refs = [
            str(getattr(cp, "from_domain", "") or "") + "→" + str(getattr(cp, "to_domain", "") or "")
            for cp in (circuit_paths or [])
            if getattr(cp, "from_domain", None) or getattr(cp, "to_domain", None)
        ]
        for _uq in agent_memory.user_questions:
            if _uq.id == _uq_id:
                _uq.chart_object_refs = sorted(relevant_names)
                _uq.shape_refs = [s for s in _shape_refs if s]
                _uq.circuit_refs = [c for c in _circuit_refs if c]
                _uq.memory_node_refs = list(merged_factors[:10])
                break
        # Answer text is the packet summary line (built after packing, so
        # we store a placeholder now and patch it after the packet is built).
        # We store the id on a local var; the actual answer is set below.

    _packet = ReadingPacket(
        question=question,
        domain=q_graph.domain or (topic.domain if not q_graph.question_intent else ""),
        subtopic=q_graph.subtopic or (topic.subtopic if not q_graph.question_intent else ""),
        confidence=q_graph.confidence,
        matched_keywords=topic.matched_keywords if hasattr(topic, "matched_keywords") else [],
        chart_name=chart_name,
        chart_date=chart_date,
        chart_time=chart_time,
        chart_city=chart_city,
        unknown_time=bool(chart.unknown_time),
        placements=placements,
        aspects=aspects,
        patterns=patterns,
        switch_points=switch_points,
        dispositors=dispositors,
        dignities=dignities,
        houses=houses,
        sabians=sabians,
        sect=sect_fact,
        circuit_flows=circuit_flows,
        power_nodes=power_nodes,
        circuit_paths=circuit_paths,
        narrative_seeds=circuit_reading.narrative_seeds,
        power_summary=circuit_reading.power_summary,
        sn_nn_relevance=circuit_reading.sn_nn_relevance,
        question_type=q_graph.question_type,
        question_intent=q_graph.question_intent,
        paraphrase=q_graph.paraphrase,
        comprehension_note=q_graph.comprehension_note,
        temporal_dimension=q_graph.temporal_dimension,
        subject_config=q_graph.subject_config,
        needs_chart_b=_needs_chart_b,
        agent_notes=agent_notes,
        interp_text=interp_text,
        planet_stats=_planet_stats_list,
        planet_profiles=_planet_profiles_list,
        visible_objects=visible_objects,
        full_chart_placements=full_chart_placements,
        chart_b_name=chart_b_name,
        chart_b_date=chart_b_date,
        chart_b_city=chart_b_city,
        chart_b_full_placements=chart_b_full_placements,
        chart_b_aspects=chart_b_aspects,
        chart_b_patterns=chart_b_patterns,
        chart_b_dignities=chart_b_dignities,
        chart_b_dispositors=chart_b_dispositors,
        chart_b_sect=chart_b_sect,
        inter_chart_aspects=inter_chart_aspects_raw,
        # ── 5W+H rich comprehension fields ──
        persons=[p.to_dict() for p in q_graph.persons] if q_graph.persons else [],
        story_objects=[o.to_dict() for o in q_graph.story_objects] if q_graph.story_objects else [],
        locations=[loc.to_dict() for loc in q_graph.locations] if q_graph.locations else [],
        dilemma=q_graph.dilemma.to_dict() if q_graph.dilemma else None,
        transits=[t.to_dict() for t in q_graph.transits] if q_graph.transits else [],
        answer_aim=q_graph.answer_aim.to_dict() if q_graph.answer_aim else None,
        querent_state=q_graph.querent_state.to_dict() if q_graph.querent_state else None,
        setting_time=q_graph.setting_time,
        intent_context=q_graph.intent_context,
        desired_input=q_graph.desired_input,
        # ── Dev debug fields ──
        debug_q_graph=q_graph.to_dict(),
        debug_comprehension_source=q_graph.source,
        debug_relevant_factors=merged_factors,
        debug_relevant_objects=sorted(relevant_names),
        debug_circuit_summary=_circuit_debug,
    )

    # ── Mark UserQuestion answered now that we have the summary line ─
    if agent_memory is not None and _uq_id is not None:
        agent_memory.answer_user_question(_uq_id, _packet.summary_line())

    return _packet


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


def _build_full_placements(
    chart: "AstrologicalChart",
    house_system: str,
) -> List[PlacementFact]:
    """Build a compact PlacementFact for **every** object in *chart*.

    Unlike :func:`_build_placements`, this covers the full chart regardless
    of question relevance.  Combo text is intentionally omitted to keep
    the token footprint small.  The result is always serialised into
    ``ReadingPacket.full_chart_placements`` so the LLM can answer any
    question about a placement that the relevance filter might have missed.
    """
    out: List[PlacementFact] = []
    for cobj in chart.objects:
        name = cobj.object_name.name if cobj.object_name else ""
        if not name:
            continue
        sign = cobj.sign.name if cobj.sign else ""
        house_num = _house_number(cobj, house_system)
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
            # No combo text — keeps full_chart_context compact
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


def _build_switch_points(
    chart: "AstrologicalChart",
    house_system: str,
) -> List[SwitchPointFact]:
    """Detect switch points (incomplete drum heads / membranes) and convert
    them to SwitchPointFact instances for the ReadingPacket.
    """
    try:
        from switch_points import find_switch_points
    except ImportError:
        return []

    raw = find_switch_points(chart, house_system=house_system)
    out: List[SwitchPointFact] = []
    for sp in raw:
        out.append(SwitchPointFact(
            source_shape=sp.source_shape_type,
            source_members=sp.source_members,
            completes_to=sp.completes_to,
            membrane_class=sp.membrane_class,
            switch_sign=sp.sign,
            switch_degree=sp.degree_in_sign,
            switch_dms=sp.dms,
            activation_range=sp.range_description,
            switch_house=sp.switch_point_house,
            sabian_symbol=sp.sabian_symbol,
            sabian_meaning=sp.sabian_meaning,
            saturn_guidance=sp.saturn_summary,
            description=sp.description,
        ))
    return out


def _build_patterns(
    chart: "AstrologicalChart",
    relevant_names: Set[str],
    render_result: Optional[Any] = None,
) -> List[PatternFact]:
    """Extract shape/pattern facts from the chart.

    Uses ``render_result.shapes`` when available (reflects the currently-visible
    chart state); falls back to ``chart.shapes``.  **All** detected shapes are
    included — no relevance filter — so the LLM always has full pattern
    visibility regardless of query scope.
    """
    out: List[PatternFact] = []
    # Prefer the live render state: it mirrors chart.shapes but confirms
    # exactly what is displayed to the user right now.
    source = (
        getattr(render_result, "shapes", None)
        or chart.shapes
        or []
    )
    for shape in source:
        # DetectedShape dataclass (current format)
        if hasattr(shape, "shape_type"):
            shape_name = shape.shape_type
            members = list(shape.members)
        # Legacy dict safety net (cached charts from before migration)
        elif isinstance(shape, dict):
            shape_name = shape.get("type", "Unknown")
            members = list(shape.get("members", []))
        else:
            continue
        if members:
            out.append(PatternFact(
                pattern_type=shape_name,
                members=members,
                meaning="",
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
            plot_data={"chart": chart},
        )

        parts: List[str] = []
        for obj_name in sorted(relevant_names):
            try:
                interp = NatalInterpreter(
                    rr,
                    mode="focus",
                    object_name=obj_name,
                )
                text = interp.generate()
                if text:
                    parts.append(text.strip())
            except Exception:
                continue

        return "\n\n".join(parts)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════
# Circuit Reading → Packet Fact converters
# ═══════════════════════════════════════════════════════════════════════

def _circuit_reading_to_flows(
    cr: CircuitReading,
    chart: "AstrologicalChart | None" = None,
) -> List[CircuitFlowFact]:
    """Convert CircuitReading.relevant_shapes → list of CircuitFlowFact.

    When *chart* is provided, element and modality span are computed for
    each shape from the chart's planet sign data.
    """
    out: List[CircuitFlowFact] = []
    for sc in (cr.relevant_shapes or []):
        members = [n.planet_name for n in sc.nodes]

        # ── Compute element & modality span from chart data ──────
        element_span: list[str] = []
        modality_span: list[str] = []
        if chart is not None:
            elements_seen: set[str] = set()
            modalities_seen: set[str] = set()
            for name in members:
                cobj = chart.get_object(name) if hasattr(chart, "get_object") else None
                if cobj and getattr(cobj, "sign", None):
                    el = getattr(cobj.sign, "element", None)
                    mod = getattr(cobj.sign, "modality", None)
                    if el:
                        el_name = getattr(el, "name", None) or str(el)
                        elements_seen.add(el_name)
                    if mod:
                        mod_name = getattr(mod, "name", None) or str(mod)
                        modalities_seen.add(mod_name)
            # Canonical ordering
            _EL_ORDER = ["Fire", "Earth", "Air", "Water"]
            _MOD_ORDER = ["Cardinal", "Fixed", "Mutable"]
            element_span = [e for e in _EL_ORDER if e in elements_seen]
            modality_span = [m for m in _MOD_ORDER if m in modalities_seen]

        out.append(CircuitFlowFact(
            shape_type=sc.shape_type,
            shape_id=sc.shape_id,
            members=members,
            resonance=sc.resonance_score,
            friction=sc.friction_score,
            throughput=sc.total_throughput,
            flow_characterization=sc.flow_characterization,
            dominant_node=sc.dominant_node or "",
            bottleneck_node=sc.bottleneck_node or "",
            membrane_class=getattr(sc, "membrane_class", "") or "",
            element_span=element_span,
            modality_span=modality_span,
        ))
    return out


def _circuit_reading_to_power_nodes(cr: CircuitReading) -> List[PowerNodeFact]:
    """Convert CircuitReading.focus_nodes → list of PowerNodeFact."""
    out: List[PowerNodeFact] = []
    for node in (cr.focus_nodes or []):
        out.append(PowerNodeFact(
            planet_name=node.planet_name,
            power_index=node.power_index,
            effective_power=node.effective_power,
            friction_load=node.friction_load,
            received_power=node.received_power,
            is_source=node.is_source,
            is_sink=node.is_sink,
            is_mutual_reception=node.is_mutual_reception,
        ))
    return out


def _circuit_reading_to_paths(cr: CircuitReading) -> List[CircuitPathFact]:
    """Convert CircuitReading.connecting_paths → list of CircuitPathFact."""
    out: List[CircuitPathFact] = []
    for path in (cr.connecting_paths or []):
        out.append(CircuitPathFact(
            from_concept=path.from_concept,
            to_concept=path.to_concept,
            path_planets=path.path_planets,
            path_aspects=path.path_aspects,
            total_conductance=path.total_conductance,
            connection_quality=path.connection_quality,
        ))
    return out



