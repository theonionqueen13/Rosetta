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

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "shape": self.shape_type,
            "members": self.members,
            "resonance": round(self.resonance, 2),
            "friction": round(self.friction, 2),
            "throughput": round(self.throughput, 2),
            "flow": self.flow_characterization,
        }
        if self.dominant_node:
            d["dominant"] = self.dominant_node
        if self.bottleneck_node:
            d["bottleneck"] = self.bottleneck_node
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
    role_note: str = ""         # e.g. "dominant", "bottleneck", "isolated"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "planet": self.planet_name,
            "power": round(self.power_index, 2),
            "effective": round(self.effective_power, 2),
        }
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
    connection_quality: str = ""   # "direct_shape", "bridged", "isolated"

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
            d["conductance"] = round(self.total_conductance, 3)
        return d


@dataclass
class IsolationFact:
    """Documents when queried factors are electrically isolated."""
    concept_a: str
    concept_b: str
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "between": f"{self.concept_a} ↔ {self.concept_b}",
            "note": self.note,
        }


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
    dispositors: List[DispositorFact] = field(default_factory=list)
    dignities: List[DignityFact] = field(default_factory=list)
    houses: List[HouseOverview] = field(default_factory=list)
    sabians: List[SabianFact] = field(default_factory=list)
    sect: Optional[SectFact] = None

    # ── Circuit-aware facts (from circuit_query.py) ──────────────────
    circuit_flows: List[CircuitFlowFact] = field(default_factory=list)
    power_nodes: List[PowerNodeFact] = field(default_factory=list)
    circuit_paths: List[CircuitPathFact] = field(default_factory=list)
    isolations: List[IsolationFact] = field(default_factory=list)
    narrative_seeds: List[str] = field(default_factory=list)
    power_summary: Dict[str, Any] = field(default_factory=dict)
    sn_nn_relevance: str = ""

    # ── Question comprehension metadata ──────────────────────────────
    question_type: str = ""          # "single_focus" / "relationship" / etc.
    comprehension_note: str = ""     # LLM comprehension explanation

    # ── Agent notes (accumulated across conversation) ────────────────
    agent_notes: str = ""

    # ── Pre-baked NatalInterpreter text (for the focused objects) ────
    interp_text: str = ""

    # ── Currently-visible objects from the live chart drawing ───────────
    # Populated from RenderResult.visible_objects when a render exists.
    # Tells the LLM exactly which planets/points are toggled on right now.
    visible_objects: List[str] = field(default_factory=list)

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
            d["patterns"] = [p.to_dict() for p in self.patterns]
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

        # Circuit-aware sections
        if self.circuit_flows:
            d["circuit_flows"] = [cf.to_dict() for cf in self.circuit_flows]
        if self.power_nodes:
            d["power_nodes"] = [pn.to_dict() for pn in self.power_nodes]
        if self.circuit_paths:
            d["circuit_paths"] = [cp.to_dict() for cp in self.circuit_paths]
        if self.isolations:
            d["isolations"] = [iso.to_dict() for iso in self.isolations]
        if self.narrative_seeds:
            d["narrative_seeds"] = self.narrative_seeds
        if self.power_summary:
            d["power_summary"] = self.power_summary
        if self.sn_nn_relevance:
            d["sn_nn"] = self.sn_nn_relevance
        if self.question_type:
            d["question_type"] = self.question_type
        if self.agent_notes:
            d["agent_notes"] = self.agent_notes

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
        if self.isolations:
            parts.append(f"{len(self.isolations)} isolations")
        return ", ".join(parts) if parts else "empty packet"
