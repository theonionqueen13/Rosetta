"""
comprehension_models.py — Rich dataclasses for the 5W+H comprehension protocol.
================================================================================

Houses all structured types that the comprehension layer extracts from
a user's question: who is involved, what they're asking about, when,
where, why, and how they're presenting.

These models are consumed by:
  - comprehension.py  (populates them during question analysis)
  - reading_engine.py (forwards them into ReadingPacket)
  - chat_ui.py        (handles ClarificationRequest; persists PersonProfile/Location)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ═══════════════════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════════════════

class AimType(str, Enum):
    """What kind of answer the user needs."""
    DIAGNOSTIC   = "diagnostic"    # "why is X happening?"
    ADVISORY     = "advisory"      # "how should I handle X?"
    PREDICTIVE   = "predictive"    # "when will X happen?"
    VALIDATING   = "validating"    # "is X true?"
    EXPLORATORY  = "exploratory"   # "tell me about X"


class Depth(str, Enum):
    """How deep the user wants the answer to go."""
    OVERVIEW   = "overview"
    MODERATE   = "moderate"
    DEEP_DIVE  = "deep_dive"


class Urgency(str, Enum):
    """How time-sensitive the question feels."""
    LOW       = "low"
    MODERATE  = "moderate"
    HIGH      = "high"
    IMMEDIATE = "immediate"


class Specificity(str, Enum):
    """How broad or narrow the question is."""
    BROAD    = "broad"
    FOCUSED  = "focused"
    PINPOINT = "pinpoint"


class EmotionalTone(str, Enum):
    """The querent's emotional presentation."""
    NEUTRAL     = "neutral"
    CURIOUS     = "curious"
    HOPEFUL     = "hopeful"
    ANXIOUS     = "anxious"
    DISTRESSED  = "distressed"
    DESPERATE   = "desperate"
    DISCOURAGED = "discouraged"
    EXCITED     = "excited"


class CertaintyLevel(str, Enum):
    """How sure the querent sounds about their subject."""
    UNSURE        = "unsure"
    SOMEWHAT_SURE = "somewhat_sure"
    CONFIDENT     = "confident"


class GuidanceOpenness(str, Enum):
    """How much guidance the querent wants."""
    MINIMAL   = "minimal"
    MODERATE  = "moderate"
    EXTENSIVE = "extensive"


class ClarificationCategory(str, Enum):
    """Why the bot needs to ask for clarification."""
    AMBIGUOUS_INTENT   = "ambiguous_intent"
    MISSING_CONTEXT    = "missing_context"
    CONTRADICTORY_INFO = "contradictory_info"
    INCOMPLETE_STORY   = "incomplete_story"


# ═══════════════════════════════════════════════════════════════════════
# WHO — People in the querent's story
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class LocationLink:
    """How a person is connected to a specific place."""
    location_name: str = ""
    connection: str = ""              # e.g. "lives there", "works there", "born there"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"location": self.location_name}
        if self.connection:
            d["connection"] = self.connection
        return d


@dataclass
class PersonProfile:
    """A person relevant to the querent's story.

    When ``relationship_to_querent`` is ``"self"``, this represents the
    querent themselves (the logged-in user).  Otherwise it describes a
    third party mentioned in the querent's question or conversation.
    """
    name: Optional[str] = None                                      # "John", "my partner", etc.
    relationship_to_querent: Optional[str] = None                   # "partner", "mother", "boss", "self"
    gender: Optional[str] = None                                    # "Female", "Male", "Non-binary"
    relationships_to_others: List[str] = field(default_factory=list) # ["married to Sarah"]
    memories: List[str] = field(default_factory=list)               # contextual details mentioned
    significant_places: List[str] = field(default_factory=list)     # place names associated
    chart_id: Optional[str] = None                                  # saved chart name if available
    locations: List[LocationLink] = field(default_factory=list)     # structured place connections
    astro_chart: Optional[Any] = None                               # Optional AstrologicalChart
    group_id: Optional[str] = None                                  # group affiliation when profile is grouped

    # ── Serialisation ─────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.name:
            d["name"] = self.name
        if self.relationship_to_querent:
            d["relationship_to_querent"] = self.relationship_to_querent
        if self.gender:
            d["gender"] = self.gender
        if self.relationships_to_others:
            d["relationships_to_others"] = self.relationships_to_others
        if self.memories:
            d["memories"] = self.memories
        if self.significant_places:
            d["significant_places"] = self.significant_places
        if self.chart_id:
            d["chart_id"] = self.chart_id
        if self.locations:
            d["locations"] = [loc.to_dict() for loc in self.locations]
        if self.group_id:
            d["group_id"] = self.group_id
        if self.astro_chart is not None and hasattr(self.astro_chart, "to_json"):
            d["chart"] = self.astro_chart.to_json()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PersonProfile":
        """Reconstruct a PersonProfile from a dict produced by ``to_dict()``.

        If the dict contains a ``"chart"`` key with an AstrologicalChart
        JSON payload, it will be deserialised via
        ``AstrologicalChart.from_json()``.
        """
        locs = [
            LocationLink(
                location_name=ld.get("location", ""),
                connection=ld.get("connection", ""),
            )
            for ld in d.get("locations", [])
        ]

        astro_chart = None
        chart_raw = d.get("chart")
        if isinstance(chart_raw, dict) and "objects" in chart_raw:
            try:
                from models_v2 import AstrologicalChart as _AC
                astro_chart = _AC.from_json(chart_raw)
            except Exception:
                pass  # leave as None if deserialisation fails

        return cls(
            name=d.get("name"),
            relationship_to_querent=d.get("relationship_to_querent"),
            gender=d.get("gender"),
            relationships_to_others=d.get("relationships_to_others", []),
            memories=d.get("memories", []),
            significant_places=d.get("significant_places", []),
            chart_id=d.get("chart_id"),
            locations=locs,
            astro_chart=astro_chart,
            group_id=d.get("group_id"),
        )


# ═══════════════════════════════════════════════════════════════════════
# WHAT — Objects, dilemmas, and the aim of the question
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class StoryObject:
    """A notable object or concept mentioned in the querent's story.

    Examples: a banjo they need to decide about, a job offer, a house
    they're considering buying, a recurring dream symbol.
    """
    name: str = ""
    description: Optional[str] = None
    significance: Optional[str] = None       # why it matters to the question
    related_persons: List[str] = field(default_factory=list)
    related_locations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.significance:
            d["significance"] = self.significance
        if self.related_persons:
            d["related_persons"] = self.related_persons
        if self.related_locations:
            d["related_locations"] = self.related_locations
        return d


@dataclass
class Dilemma:
    """A decision or fork the querent is facing."""
    description: str = ""
    options: List[str] = field(default_factory=list)    # the choices they're weighing
    stakes: Optional[str] = None                        # what's at risk
    constraints: List[str] = field(default_factory=list) # limitations, deadlines, etc.
    desired_outcome: Optional[str] = None                # what they hope will happen

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"description": self.description}
        if self.options:
            d["options"] = self.options
        if self.stakes:
            d["stakes"] = self.stakes
        if self.constraints:
            d["constraints"] = self.constraints
        if self.desired_outcome:
            d["desired_outcome"] = self.desired_outcome
        return d


@dataclass
class AnswerAim:
    """What kind of answer the user is seeking and how they want it shaped."""
    aim_type: AimType = AimType.EXPLORATORY
    depth: Depth = Depth.MODERATE
    urgency: Urgency = Urgency.MODERATE
    specificity: Specificity = Specificity.FOCUSED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aim_type": self.aim_type.value,
            "depth": self.depth.value,
            "urgency": self.urgency.value,
            "specificity": self.specificity.value,
        }


# ═══════════════════════════════════════════════════════════════════════
# WHEN — Temporal context
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Transit:
    """A specific transit or timing reference mentioned in the question."""
    transiting_body: Optional[str] = None    # "Saturn", "Jupiter"
    natal_body: Optional[str] = None         # "Sun", "Midheaven"
    aspect_type: Optional[str] = None        # "conjunction", "square", "return"
    timeframe: Optional[str] = None          # "this month", "next year", "2026"
    description: Optional[str] = None        # free-text note

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.transiting_body:
            d["transiting_body"] = self.transiting_body
        if self.natal_body:
            d["natal_body"] = self.natal_body
        if self.aspect_type:
            d["aspect_type"] = self.aspect_type
        if self.timeframe:
            d["timeframe"] = self.timeframe
        if self.description:
            d["description"] = self.description
        return d


# ═══════════════════════════════════════════════════════════════════════
# WHERE — Locations in the querent's story
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Location:
    """A place mentioned in the querent's question/story."""
    name: str = ""
    location_type: Optional[str] = None       # "city", "venue", "home", "workplace", "country"
    connected_persons: List[Tuple[str, str]] = field(default_factory=list)
    # ^ [(person_name, connection_description)]  e.g. [("John", "lives there")]
    relevance: Optional[str] = None           # why this place matters to the question
    coordinates: Optional[Tuple[float, float]] = None  # (lat, lon) if determinable

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"name": self.name}
        if self.location_type:
            d["location_type"] = self.location_type
        if self.connected_persons:
            d["connected_persons"] = [
                {"person": p, "connection": c} for p, c in self.connected_persons
            ]
        if self.relevance:
            d["relevance"] = self.relevance
        if self.coordinates:
            d["coordinates"] = list(self.coordinates)
        return d


# ═══════════════════════════════════════════════════════════════════════
# HOW — The querent's emotional & communicative state
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class QuerentState:
    """How the querent is presenting: tone, certainty, openness to guidance."""
    emotional_tone: EmotionalTone = EmotionalTone.NEUTRAL
    certainty_level: CertaintyLevel = CertaintyLevel.SOMEWHAT_SURE
    guidance_openness: GuidanceOpenness = GuidanceOpenness.MODERATE
    expressed_feelings: List[str] = field(default_factory=list)  # direct quotes or paraphrases
    demeanor_notes: Optional[str] = None                         # LLM's free-text observation

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "emotional_tone": self.emotional_tone.value,
            "certainty_level": self.certainty_level.value,
            "guidance_openness": self.guidance_openness.value,
        }
        if self.expressed_feelings:
            d["expressed_feelings"] = self.expressed_feelings
        if self.demeanor_notes:
            d["demeanor_notes"] = self.demeanor_notes
        return d


# ═══════════════════════════════════════════════════════════════════════
# Clarification protocol
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ClarificationRequest:
    """Returned when the bot doesn't fully understand the question."""
    reason: str = ""                          # why clarification is needed
    category: ClarificationCategory = ClarificationCategory.AMBIGUOUS_INTENT
    best_guesses: List[str] = field(default_factory=list)  # 1–3 interpretations
    follow_up_question: str = ""              # what to ask the user
    partial_graph: Optional[Any] = None       # Optional[QuestionGraph] — partial comprehension so far

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "reason": self.reason,
            "category": self.category.value,
            "follow_up_question": self.follow_up_question,
        }
        if self.best_guesses:
            d["best_guesses"] = self.best_guesses
        if self.partial_graph is not None and hasattr(self.partial_graph, "to_dict"):
            d["partial_graph"] = self.partial_graph.to_dict()
        return d


# ═══════════════════════════════════════════════════════════════════════
# ComprehensionResult — the new return wrapper for comprehend()
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ComprehensionResult:
    """Wraps either a complete QuestionGraph or a ClarificationRequest.

    The comprehension layer returns this instead of a bare QuestionGraph,
    so callers can check ``needs_clarification`` before proceeding to
    the reading engine.
    """
    graph: Optional[Any] = None               # Optional[QuestionGraph]
    clarification: Optional[ClarificationRequest] = None

    @property
    def needs_clarification(self) -> bool:
        """True when the bot needs to ask the user for more info."""
        return self.clarification is not None

    @property
    def is_complete(self) -> bool:
        """True when comprehension succeeded and a graph is available."""
        return self.graph is not None and self.clarification is None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "needs_clarification": self.needs_clarification,
            "is_complete": self.is_complete,
        }
        if self.graph is not None and hasattr(self.graph, "to_dict"):
            d["graph"] = self.graph.to_dict()
        if self.clarification is not None:
            d["clarification"] = self.clarification.to_dict()
        return d
