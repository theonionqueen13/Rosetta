"""
reading_packet.py — Structured astrological facts for LLM consumption.

A ReadingPacket is the output of the ReadingEngine: a bundle of typed,
pre-validated astrological facts that have been evaluated by the app's
hard-coded logic.  The LLM never computes anything — it only receives
these facts and weaves them into prose.

Design goals
  • Minimal token footprint — every field serializes to a compact dict.
  • Zero hallucination surface — every fact is computed, not inferred.
  • Typed & serializable — dataclasses with `.to_dict()` for JSON/prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════
# Individual fact types
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PlacementFact:
    """One object's sign + house placement."""
    object_name: str
    glyph: str
    sign: str
    sign_element: str          # Fire / Earth / Air / Water
    sign_modality: str         # Cardinal / Fixed / Mutable
    house: int                 # house number (1-12)
    degree: str                # formatted DMS, e.g. "15°24'Ar"
    retrograde: bool = False
    dignity: str = ""          # Domicile / Exaltation / Detriment / Fall / ""
    oob: str = ""              # "Yes" / "Extreme" / ""
    object_type: str = ""      # "Planet", "Luminary", "Asteroid", etc.
    narrative_role: str = ""   # from Object.narrative_role
    short_meaning: str = ""    # Object's short_meaning field

    # Pre-baked interpretation from static combo data
    sign_combo_text: str = ""  # ObjectSign combo interpretation
    house_combo_text: str = "" # ObjectHouse combo interpretation

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "obj": self.object_name,
            "sign": self.sign,
            "house": self.house,
            "deg": self.degree,
        }
        if self.retrograde:
            d["Rx"] = True
        if self.dignity:
            d["dignity"] = self.dignity
        if self.oob:
            d["oob"] = self.oob
        if self.sign_combo_text:
            d["sign_interp"] = self.sign_combo_text
        if self.house_combo_text:
            d["house_interp"] = self.house_combo_text
        return d


@dataclass
class AspectFact:
    """One aspect between two objects."""
    object1: str
    object2: str
    aspect_name: str           # "Conjunction", "Trine", etc.
    aspect_glyph: str
    angle: int
    orb: float
    applying: bool
    mutual_reception: bool = False
    # interpretation data from Aspect dataclass
    aspect_meaning: str = ""   # sentence_meaning
    aspect_polarity: str = ""  # "Harmonious" / "Tense" / ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "pair": f"{self.object1} {self.aspect_glyph} {self.object2}",
            "aspect": self.aspect_name,
            "orb": round(self.orb, 1),
        }
        if self.applying:
            d["applying"] = True
        if self.mutual_reception:
            d["mutual_reception"] = True
        if self.aspect_meaning:
            d["meaning"] = self.aspect_meaning
        return d


@dataclass
class PatternFact:
    """A detected geometric pattern (Grand Trine, T-Square, Yod, etc.)."""
    pattern_type: str          # "Grand Trine", "T-Square", "Yod", "Kite", etc.
    members: List[str]         # object names involved
    meaning: str = ""          # pre-baked interpretation from patterns_v2

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "type": self.pattern_type,
            "members": self.members,
        }
        if self.meaning:
            d["meaning"] = self.meaning
        return d


@dataclass
class SwitchPointFact:
    """A switch point — the missing vertex of an incomplete resonant shape.

    When occupied by transit, synastry, or a deliberate keystone,
    the incomplete shape completes into a full resonant membrane.
    """
    source_shape: str              # e.g. "T-Square"
    source_members: List[str]      # planets in the incomplete shape
    completes_to: str              # e.g. "Grand Cross"
    membrane_class: str            # "drum_head", "resonant_membrane", or ""
    switch_sign: str               # e.g. "Scorpio"
    switch_degree: int             # 1–30 (Sabian convention)
    switch_dms: str                # formatted position string
    activation_range: str          # e.g. "14°–16° Scorpio"
    switch_house: int = 0          # which natal house the switch point falls in
    sabian_symbol: str = ""        # Sabian symbol text
    sabian_meaning: str = ""       # short meaning of the Sabian symbol
    saturn_guidance: str = ""      # Saturn-informed keystone selection guidance
    description: str = ""          # shape completion narrative

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "source_shape": self.source_shape,
            "source_members": self.source_members,
            "completes_to": self.completes_to,
            "membrane_class": self.membrane_class,
            "switch_point": {
                "sign": self.switch_sign,
                "degree": self.switch_degree,
                "dms": self.switch_dms,
                "range": self.activation_range,
            },
        }
        if self.switch_house:
            d["switch_point"]["house"] = self.switch_house
        if self.sabian_symbol:
            d["sabian"] = {
                "symbol": self.sabian_symbol,
                "meaning": self.sabian_meaning,
            }
        if self.saturn_guidance:
            d["keystone_guidance"] = self.saturn_guidance
        if self.description:
            d["description"] = self.description
        return d


@dataclass
class DispositorFact:
    """One row from the dispositor chain analysis."""
    object_name: str
    ruled_by: str              # the sign ruler (dispositor)
    chain: List[str]           # full chain of rulership
    is_final_dispositor: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "obj": self.object_name,
            "ruler": self.ruled_by,
        }
        if self.is_final_dispositor:
            d["final_dispositor"] = True
        if self.chain:
            d["chain"] = " → ".join(self.chain)
        return d


@dataclass
class DignityFact:
    """Dignity status for an object (domicile, exaltation, detriment, fall)."""
    object_name: str
    dignity_type: str          # "Domicile", "Exaltation", "Detriment", "Fall"
    sign: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "obj": self.object_name,
            "status": self.dignity_type,
            "sign": self.sign,
        }


@dataclass
class SectFact:
    """Chart sect (diurnal vs. nocturnal)."""
    sect: str                  # "Diurnal" or "Nocturnal"
    sect_light: str            # "Sun" or "Moon"
    benefic_of_sect: str       # "Jupiter" or "Venus"
    malefic_of_sect: str       # "Saturn" or "Mars"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sect": self.sect,
            "light": self.sect_light,
            "benefic": self.benefic_of_sect,
            "malefic": self.malefic_of_sect,
        }


@dataclass
class HouseOverview:
    """Summary of a house's occupants and ruler."""
    house_number: int
    sign_on_cusp: str
    ruler: str                 # planet that rules this sign
    occupants: List[str]       # objects in this house
    meaning: str = ""          # from House.short_meaning

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "house": self.house_number,
            "cusp_sign": self.sign_on_cusp,
            "ruler": self.ruler,
        }
        if self.occupants:
            d["occupants"] = self.occupants
        if self.meaning:
            d["meaning"] = self.meaning
        return d


@dataclass
class SabianFact:
    """Sabian symbol for an object's degree."""
    object_name: str
    degree_index: int          # 1–360
    symbol_text: str
    keynote: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "obj": self.object_name,
            "sabian": self.symbol_text,
        }
        if self.keynote:
            d["keynote"] = self.keynote
        return d


# ═══════════════════════════════════════════════════════════════════════
# Circuit-aware fact types (populated by circuit_query.py)
# ═══════════════════════════════════════════════════════════════════════

# ── Qualitative tier helpers (internal scores → comparative language) ──

def _qualify_resonance(v: float) -> str:
    """Map a 0-1 resonance score to a qualitative tier label."""
    if v >= 0.85:
        return "deeply resonant"
    if v >= 0.70:
        return "strongly resonant"
    if v >= 0.50:
        return "moderately resonant"
    if v >= 0.30:
        return "mildly resonant"
    return "weakly resonant"


def _qualify_friction(v: float) -> str:
    """Map a 0-1 friction score to a qualitative tier label."""
    if v >= 0.80:
        return "very high friction"
    if v >= 0.60:
        return "significant friction"
    if v >= 0.40:
        return "moderate friction"
    if v >= 0.20:
        return "mild friction"
    return "low friction"


def _qualify_conductance(v: float) -> str:
    """Map a 0-1 conductance to a qualitative tier label."""
    if v >= 0.90:
        return "near-seamless"
    if v >= 0.70:
        return "strong"
    if v >= 0.50:
        return "moderate"
    if v >= 0.30:
        return "strained"
    return "very weak"


def _qualify_throughput(v: float) -> str:
    """Map throughput to a qualitative label."""
    if v >= 8.0:
        return "very high"
    if v >= 5.0:
        return "high"
    if v >= 3.0:
        return "moderate"
    if v >= 1.0:
        return "low"
    return "minimal"


@dataclass
class CircuitFlowFact:
    """One shape circuit's power-flow summary."""
    shape_type: str             # "Grand Trine", "T-Square", etc.
    shape_id: str               # unique id
    members: List[str]          # planet names
    resonance: float            # 0.0–1.0
    friction: float             # 0.0–1.0
    throughput: float
    flow_characterization: str  # e.g. "Effortless resonance loop"
    dominant_node: str = ""
    bottleneck_node: str = ""
    # Membrane classification — "drum_head", "resonant_membrane", or ""
    membrane_class: str = ""
    # Element/modality span of shape members (e.g. ["Fire", "Earth", "Air", "Water"])
    element_span: List[str] = field(default_factory=list)
    modality_span: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "shape": self.shape_type,
            "members": self.members,
            "resonance": _qualify_resonance(self.resonance),
            "friction": _qualify_friction(self.friction),
            "throughput": _qualify_throughput(self.throughput),
            "flow": self.flow_characterization,
        }
        if self.dominant_node:
            d["dominant"] = self.dominant_node
        if self.bottleneck_node:
            d["bottleneck"] = self.bottleneck_node
        if self.membrane_class:
            d["membrane_class"] = self.membrane_class
        if self.element_span:
            d["element_span"] = self.element_span
        if self.modality_span:
            d["modality_span"] = self.modality_span
        return d


@dataclass
class PowerNodeFact:
    """One planet's power stats from the circuit simulation."""
    planet_name: str
    power_index: float
    effective_power: float
    friction_load: float = 0.0
    received_power: float = 0.0
    is_source: bool = False     # South Node
    is_sink: bool = False       # North Node
    is_mutual_reception: bool = False
    role_note: str = ""         # e.g. "dominant", "bottleneck"
    # Relative tier label assigned by term_registry.assign_potency_tiers().
    # When set, raw numerical scores are suppressed from to_dict() so the LLM
    # never sees the underlying numbers.
    tier_label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"planet": self.planet_name}
        if self.tier_label:
            # Potency-ranking mode: expose only relative tier, no raw scores
            d["potency"] = self.tier_label
        else:
            d["power"] = round(self.power_index, 2)
            d["effective"] = round(self.effective_power, 2)
            if self.friction_load > 0.01:
                d["friction"] = round(self.friction_load, 2)
            if self.received_power > 0.01:
                d["received"] = round(self.received_power, 2)
        if self.is_source:
            d["role"] = "source (South Node)"
        elif self.is_sink:
            d["role"] = "sink (North Node)"
        if self.is_mutual_reception:
            d["mutual_reception"] = True
        if self.role_note:
            d["note"] = self.role_note
        return d


@dataclass
class CircuitPathFact:
    """A traced conductive path between two concept clusters."""
    from_concept: str
    to_concept: str
    path_planets: List[str] = field(default_factory=list)
    path_aspects: List[str] = field(default_factory=list)
    total_conductance: float = 0.0
    connection_quality: str = ""   # "direct_shape", "bridged"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "from": self.from_concept,
            "to": self.to_concept,
            "quality": self.connection_quality,
        }
        if self.path_planets:
            d["path"] = " → ".join(self.path_planets)
        if self.path_aspects:
            d["aspects"] = self.path_aspects
        if self.total_conductance:
            d["conductance"] = _qualify_conductance(self.total_conductance)
        return d



# ═══════════════════════════════════════════════════════════════════════
# Top-level ReadingPacket
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ReadingPacket:
    """Complete structured reading data for one question + chart.

    This is the *only* object the LLM prompt builder ever touches.
    Every field was computed by deterministic, hard-coded logic.
    """

    # ── Context ──────────────────────────────────────────────────────
    question: str = ""
    domain: str = ""
    subtopic: str = ""
    confidence: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)

    # ── Chart metadata ───────────────────────────────────────────────
    chart_name: str = ""
    chart_date: str = ""
    chart_time: str = ""
    chart_city: str = ""
    unknown_time: bool = False

    # ── Facts (filtered to question-relevant factors) ────────────────
    placements: List[PlacementFact] = field(default_factory=list)
    aspects: List[AspectFact] = field(default_factory=list)
    patterns: List[PatternFact] = field(default_factory=list)
    switch_points: List[SwitchPointFact] = field(default_factory=list)
    dispositors: List[DispositorFact] = field(default_factory=list)
    dignities: List[DignityFact] = field(default_factory=list)
    houses: List[HouseOverview] = field(default_factory=list)
    sabians: List[SabianFact] = field(default_factory=list)
    sect: Optional[SectFact] = None

    # ── Circuit-aware facts (from circuit_query.py) ──────────────────
    circuit_flows: List[CircuitFlowFact] = field(default_factory=list)
    power_nodes: List[PowerNodeFact] = field(default_factory=list)
    circuit_paths: List[CircuitPathFact] = field(default_factory=list)
    narrative_seeds: List[str] = field(default_factory=list)
    power_summary: Dict[str, Any] = field(default_factory=dict)
    sn_nn_relevance: str = ""

    # ── Question comprehension metadata ──────────────────────────────
    question_type: str = ""          # "single_focus" / "relationship" / etc.
    question_intent: str = ""        # routing intent (e.g. "potency_ranking")
    paraphrase: str = ""             # one-sentence plain-language restatement
    comprehension_note: str = ""     # LLM comprehension explanation
    temporal_dimension: str = "natal"  # temporal frame: natal / transit / synastry / etc.
    subject_config: str = "single"     # subject scope: single / dyadic / familial
    needs_chart_b: bool = False        # True when dyadic question detected but no second chart loaded

    # ── Agent notes (accumulated across conversation) ────────────────
    agent_notes: str = ""

    # ── 5W+H rich comprehension data ────────────────────────────────
    # Pre-serialized dicts from comprehension_models dataclasses.
    persons: List[Dict[str, Any]] = field(default_factory=list)       # PersonProfile dicts
    story_objects: List[Dict[str, Any]] = field(default_factory=list) # StoryObject dicts
    locations: List[Dict[str, Any]] = field(default_factory=list)     # Location dicts
    dilemma: Optional[Dict[str, Any]] = None                          # Dilemma dict
    transits: List[Dict[str, Any]] = field(default_factory=list)      # Transit dicts
    answer_aim: Optional[Dict[str, Any]] = None                       # AnswerAim dict
    querent_state: Optional[Dict[str, Any]] = None                    # QuerentState dict
    setting_time: Optional[str] = None                                # past/present/future/date
    intent_context: Optional[str] = None                              # why user is asking
    desired_input: Optional[str] = None                               # what output they want

    # ── Clarification (only set when comprehension needs follow-up) ──
    _clarification: Dict[str, Any] = field(default_factory=dict)

    # ── Pre-baked NatalInterpreter text (for the focused objects) ────
    interp_text: str = ""

    # ── Currently-visible objects from the live chart drawing ───────────
    # Populated from RenderResult.visible_objects when a render exists.
    # Tells the LLM exactly which planets/points are toggled on right now.
    visible_objects: List[str] = field(default_factory=list)

    # ── Full chart context — always populated regardless of active toggles ──
    # Compact placement summary for EVERY object in AstrologicalChart,
    # irrespective of what the user has toggled on or what the question
    # asked about.  The LLM must consult this for any chart-wide question.
    full_chart_placements: List[PlacementFact] = field(default_factory=list)

    # ── Debug / dev-mode fields (never sent to LLM) ─────────────────────────
    # Populated by build_reading() for the dev inner-monologue expander.
    debug_q_graph: Dict[str, Any] = field(default_factory=dict)     # QuestionGraph.to_dict()
    debug_comprehension_source: str = ""                             # "keyword" | "llm"
    debug_relevant_factors: List[str] = field(default_factory=list) # merged factors list
    debug_relevant_objects: List[str] = field(default_factory=list) # object names selected
    debug_circuit_summary: Dict[str, Any] = field(default_factory=dict)  # circuit stats

    # ── Second chart in biwheel mode ────────────────────────────────────────
    # Populated when the app has a second chart loaded (synastry / transits).
    chart_b_name: str = ""
    chart_b_date: str = ""
    chart_b_city: str = ""
    chart_b_full_placements: List[PlacementFact] = field(default_factory=list)
    # Full parity fact sets for chart_b
    chart_b_aspects: List[AspectFact] = field(default_factory=list)
    chart_b_patterns: List[PatternFact] = field(default_factory=list)
    chart_b_dignities: List[DignityFact] = field(default_factory=list)
    chart_b_dispositors: List[DispositorFact] = field(default_factory=list)
    chart_b_sect: Optional[SectFact] = None
    # Cross-chart aspects — list of {"planet_1": str, "planet_2": str, "aspect": str}
    inter_chart_aspects: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Compact serialization for prompt building.

        Only non-empty sections are included to save tokens.
        """
        d: Dict[str, Any] = {}

        # Context
        if self.question:
            d["question"] = self.question
        if self.domain:
            d["domain"] = self.domain
        if self.subtopic:
            d["subtopic"] = self.subtopic

        # Chart header
        header: Dict[str, str] = {}
        if self.chart_name:
            header["name"] = self.chart_name
        if self.chart_date:
            header["date"] = self.chart_date
        if self.chart_city:
            header["city"] = self.chart_city
        if self.unknown_time:
            header["note"] = "Unknown birth time — houses approximate"
        if header:
            d["chart"] = header

        # Fact sections — only include if non-empty
        if self.placements:
            d["placements"] = [p.to_dict() for p in self.placements]
        if self.aspects:
            d["aspects"] = [a.to_dict() for a in self.aspects]
        if self.patterns:
            # Deduplicate: skip patterns already covered by circuit_flows
            # (circuit_flows is the richer version with resonance/friction data)
            _cf_keys = {
                (cf.shape_type, frozenset(cf.members))
                for cf in self.circuit_flows
            } if self.circuit_flows else set()
            _deduped = [
                p for p in self.patterns
                if (p.pattern_type, frozenset(p.members)) not in _cf_keys
            ]
            if _deduped:
                d["patterns"] = [p.to_dict() for p in _deduped]
        if self.switch_points:
            d["switch_points"] = [sp.to_dict() for sp in self.switch_points]
        if self.dispositors:
            d["dispositors"] = [ds.to_dict() for ds in self.dispositors]
        if self.dignities:
            d["dignities"] = [dg.to_dict() for dg in self.dignities]
        if self.houses:
            d["houses"] = [h.to_dict() for h in self.houses]
        if self.sabians:
            d["sabians"] = [s.to_dict() for s in self.sabians]
        if self.sect:
            d["sect"] = self.sect.to_dict()
        if self.interp_text:
            d["interpretation"] = self.interp_text
        if self.visible_objects:
            d["visible_on_chart"] = self.visible_objects

        # Full chart context — always-available map of every planet/point
        # (no combo text to keep tokens compact)
        if self.full_chart_placements:
            d["full_chart_context"] = [
                {k: v for k, v in p.to_dict().items()
                 if k not in ("sign_interp", "house_interp")}
                for p in self.full_chart_placements
            ]

        # Biwheel second chart
        if self.chart_b_full_placements or self.inter_chart_aspects:
            b_header: Dict[str, str] = {}
            if self.chart_b_name:
                b_header["name"] = self.chart_b_name
            if self.chart_b_date:
                b_header["date"] = self.chart_b_date
            if self.chart_b_city:
                b_header["city"] = self.chart_b_city
            b_ctx: Dict[str, Any] = {"header": b_header}
            if self.chart_b_full_placements:
                b_ctx["placements"] = [
                    {k: v for k, v in p.to_dict().items()
                     if k not in ("sign_interp", "house_interp")}
                    for p in self.chart_b_full_placements
                ]
            if self.chart_b_aspects:
                b_ctx["aspects"] = [a.to_dict() for a in self.chart_b_aspects]
            if self.chart_b_patterns:
                b_ctx["patterns"] = [p.to_dict() for p in self.chart_b_patterns]
            if self.chart_b_dignities:
                b_ctx["dignities"] = [dg.to_dict() for dg in self.chart_b_dignities]
            if self.chart_b_dispositors:
                b_ctx["dispositors"] = [ds.to_dict() for ds in self.chart_b_dispositors]
            if self.chart_b_sect:
                b_ctx["sect"] = self.chart_b_sect.to_dict()
            if self.inter_chart_aspects:
                b_ctx["inter_chart_aspects"] = self.inter_chart_aspects
            d["chart_b_context"] = b_ctx

        # Circuit-aware sections
        if self.circuit_flows:
            d["circuit_flows"] = [cf.to_dict() for cf in self.circuit_flows]
        if self.power_nodes:
            d["power_nodes"] = [pn.to_dict() for pn in self.power_nodes]
        if self.circuit_paths:
            d["circuit_paths"] = [cp.to_dict() for cp in self.circuit_paths]
        if self.narrative_seeds:
            d["narrative_seeds"] = self.narrative_seeds
        if self.power_summary:
            d["power_summary"] = self.power_summary
        if self.sn_nn_relevance:
            d["sn_nn"] = self.sn_nn_relevance
        if self.question_type:
            d["question_type"] = self.question_type
        if self.question_intent:
            d["question_intent"] = self.question_intent
        if self.paraphrase:
            d["paraphrase"] = self.paraphrase
        if self.temporal_dimension and self.temporal_dimension != "natal":
            d["temporal_dimension"] = self.temporal_dimension
        if self.subject_config and self.subject_config != "single":
            d["subject_config"] = self.subject_config
        if self.agent_notes:
            d["agent_notes"] = self.agent_notes

        # 5W+H rich comprehension sections — only include if populated
        if self.persons:
            d["persons"] = self.persons
        if self.story_objects:
            d["story_objects"] = self.story_objects
        if self.locations:
            d["locations_mentioned"] = self.locations
        if self.dilemma:
            d["dilemma"] = self.dilemma
        if self.transits:
            d["transits_mentioned"] = self.transits
        if self.answer_aim:
            d["answer_aim"] = self.answer_aim
        if self.querent_state:
            d["querent_state"] = self.querent_state
        if self.setting_time:
            d["setting_time"] = self.setting_time
        if self.intent_context:
            d["intent_context"] = self.intent_context
        if self.desired_input:
            d["desired_input"] = self.desired_input

        return d

    def token_estimate(self) -> int:
        """Rough token count estimate (~4 chars per token)."""
        import json
        text = json.dumps(self.to_dict(), ensure_ascii=False)
        return len(text) // 4

    def summary_line(self) -> str:
        """One-liner for logging: e.g. '5 placements, 3 aspects, 1 pattern'"""
        parts = []
        if self.placements:
            parts.append(f"{len(self.placements)} placements")
        if self.aspects:
            parts.append(f"{len(self.aspects)} aspects")
        if self.patterns:
            parts.append(f"{len(self.patterns)} patterns")
        if self.switch_points:
            parts.append(f"{len(self.switch_points)} switch points")
        if self.dispositors:
            parts.append(f"{len(self.dispositors)} dispositors")
        if self.dignities:
            parts.append(f"{len(self.dignities)} dignities")
        if self.houses:
            parts.append(f"{len(self.houses)} houses")
        if self.circuit_flows:
            parts.append(f"{len(self.circuit_flows)} circuits")
        if self.power_nodes:
            parts.append(f"{len(self.power_nodes)} power nodes")
        if self.circuit_paths:
            parts.append(f"{len(self.circuit_paths)} paths")
        return ", ".join(parts) if parts else "empty packet"
