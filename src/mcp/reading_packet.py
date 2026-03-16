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

    # ── Pre-baked NatalInterpreter text (for the focused objects) ────
    interp_text: str = ""

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
        return ", ".join(parts) if parts else "empty packet"
