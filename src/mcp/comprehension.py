"""
comprehension.py — Question Decomposition Layer (5W+H Protocol)
================================================================
Decomposes a natural-language question into a structured QuestionGraph
that maps concepts to astrological factors and relationships between them.

The comprehension protocol extracts the full 5W+H:
  WHO   — PersonProfile for each person mentioned
  WHAT  — Topics, StoryObjects, Dilemmas, AnswerAim
  WHEN  — Temporal setting, Transit objects
  WHERE — Location objects
  WHY   — User intent and context
  HOW   — QuerentState (tone, certainty, guidance openness)

Resolution paths
----------------
  1. **LLM path** (required for rich 5W+H extraction):
     Structured-output LLM call with a JSON-schema constraint.
     The LLM can ONLY select astrological factors from a validated
     vocabulary present in the chart — it cannot hallucinate.

  2. **Keyword path** (fallback when no API key):
     Uses ``topic_maps.resolve_factors()`` for keyword extraction +
     heuristic relationship detection. Rich fields (persons, dilemmas,
     querent state, etc.) remain at defaults — LLM is required for those.

After either path, ``_anchor_to_chart()`` validates every factor against
the live chart and maps them to shape_ids in the circuit simulation.

A sufficiency check may return a ``ClarificationRequest`` instead of a
complete graph when the bot doesn't fully understand the question.

Public API
----------
  comprehend(question, chart, api_key=None, ...) → ComprehensionResult
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.mcp.topic_maps import resolve_factors, TopicMatch
from src.mcp.term_registry import load_terms, match_terms, TermIntent
from src.mcp.grammar_parse import parse_grammar, GrammarDiagram, grammar_summary_line
from src.mcp.comprehension_models import (
    AimType, Depth, Urgency, Specificity,
    EmotionalTone, CertaintyLevel, GuidanceOpenness,
    ClarificationCategory,
    PersonProfile, LocationLink, StoryObject, Dilemma, AnswerAim,
    Transit, Location, QuerentState,
    ClarificationRequest, ComprehensionResult,
)

if TYPE_CHECKING:
    from src.core.models_v2 import AstrologicalChart


# ═══════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class QuestionNode:
    """One concept the user is asking about, mapped to astrological factors."""
    label: str                          # human-readable concept name ("health", "career")
    factors: List[str] = field(default_factory=list)   # astrological factors: planet/house/sign names
    source: str = "keyword"             # "keyword" or "llm"


@dataclass
class QuestionEdge:
    """A relationship between two QuestionNodes."""
    node_a: str                         # label of first node
    node_b: str                         # label of second node
    relationship: str = "connection"    # "connection" | "tension" | "support" | "timing"


@dataclass
class QuestionGraph:
    """Structured representation of a decomposed question (5W+H)."""
    # ── Core decomposition ───────────────────────────────────────────
    nodes: List[QuestionNode] = field(default_factory=list)
    edges: List[QuestionEdge] = field(default_factory=list)
    question_type: str = "single_focus"  # "single_focus" | "relationship" | "multi_node" | "open_exploration"

    # ── Post-anchoring (filled by _anchor_to_chart) ──────────────────
    focus_circuits: List[int] = field(default_factory=list)
    all_factors: List[str] = field(default_factory=list)
    anchored: bool = False

    # ── Routing metadata ─────────────────────────────────────────────
    domain: str = ""
    subtopic: str = ""
    confidence: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)
    source: str = "keyword"
    question_intent: str = ""
    paraphrase: str = ""
    comprehension_note: str = ""
    temporal_dimension: str = "natal"
    subject_config: str = "single"

    # ── WHO — People in the querent's story ──────────────────────────
    persons: List[PersonProfile] = field(default_factory=list)

    # ── WHAT — Objects, dilemma, aim ─────────────────────────────────
    story_objects: List[StoryObject] = field(default_factory=list)
    dilemma: Optional[Dilemma] = None
    answer_aim: Optional[AnswerAim] = None

    # ── WHEN — Temporal setting & transit references ─────────────────
    setting_time: Optional[str] = None       # "past" / "present" / "future" / specific date
    transits: List[Transit] = field(default_factory=list)

    # ── WHERE — Locations ────────────────────────────────────────────
    locations: List[Location] = field(default_factory=list)

    # ── WHY — Intent & context ───────────────────────────────────────
    intent_context: Optional[str] = None     # why the user is asking
    desired_input: Optional[str] = None      # what actionable output they want

    # ── HOW — Querent state ──────────────────────────────────────────
    querent_state: Optional[QuerentState] = None

    # ── Step 0 — Grammar diagram ──────────────────────────────────────
    grammar: Optional[GrammarDiagram] = None

    # ── Sufficiency metadata ─────────────────────────────────────────
    comprehension_confidence: float = 0.0    # LLM self-assessed 0.0–1.0
    ambiguities: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "question_type": self.question_type,
            "nodes": [{"label": n.label, "factors": n.factors, "source": n.source} for n in self.nodes],
            "edges": [{"a": e.node_a, "b": e.node_b, "rel": e.relationship} for e in self.edges],
            "focus_circuits": self.focus_circuits,
            "all_factors": self.all_factors,
            "domain": self.domain,
            "subtopic": self.subtopic,
            "confidence": self.confidence,
            "source": self.source,
            "question_intent": self.question_intent,
            "temporal_dimension": self.temporal_dimension,
            "subject_config": self.subject_config,
        }
        if self.paraphrase:
            d["paraphrase"] = self.paraphrase
        # 5W+H rich fields — only include if populated
        if self.persons:
            d["persons"] = [p.to_dict() for p in self.persons]
        if self.story_objects:
            d["story_objects"] = [o.to_dict() for o in self.story_objects]
        if self.dilemma:
            d["dilemma"] = self.dilemma.to_dict()
        if self.answer_aim:
            d["answer_aim"] = self.answer_aim.to_dict()
        if self.setting_time:
            d["setting_time"] = self.setting_time
        if self.transits:
            d["transits"] = [t.to_dict() for t in self.transits]
        if self.locations:
            d["locations"] = [loc.to_dict() for loc in self.locations]
        if self.intent_context:
            d["intent_context"] = self.intent_context
        if self.desired_input:
            d["desired_input"] = self.desired_input
        if self.querent_state:
            d["querent_state"] = self.querent_state.to_dict()
        if self.comprehension_confidence > 0:
            d["comprehension_confidence"] = self.comprehension_confidence
        if self.ambiguities:
            d["ambiguities"] = self.ambiguities
        if self.contradictions:
            d["contradictions"] = self.contradictions
        if self.grammar:
            d["grammar"] = self.grammar.to_dict()
        return d


# ═══════════════════════════════════════════════════════════════════════
# Vocabulary builder — creates the constrained factor list from a chart
# ═══════════════════════════════════════════════════════════════════════

_SIGN_NAMES: Set[str] = {
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
}

_HOUSE_LABELS: List[str] = [f"{i}th House" for i in range(1, 13)]
_HOUSE_LABELS[0] = "1st House"
_HOUSE_LABELS[1] = "2nd House"
_HOUSE_LABELS[2] = "3rd House"


def _build_vocabulary(chart: "AstrologicalChart") -> List[str]:
    """Build the full allowed-factor vocabulary from a live chart."""
    vocab: List[str] = []
    for cobj in chart.objects:
        name = cobj.object_name.name if cobj.object_name else ""
        if name:
            vocab.append(name)
    vocab.extend(sorted(_SIGN_NAMES))
    vocab.extend(_HOUSE_LABELS)
    # Add common aliases
    vocab.extend(["Ascendant", "AC", "Descendant", "DC", "MC", "Midheaven", "IC", "Immum Coeli"])
    return sorted(set(vocab))


# ═══════════════════════════════════════════════════════════════════════
# Relationship-type heuristic (for keyword fallback)
# ═══════════════════════════════════════════════════════════════════════

_REL_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(relat|connect|link|between|affect|influenc|impact|interact)\b", re.I), "connection"),
    (re.compile(r"\b(tension|conflict|struggle|challenge|block|obstacl|friction)\b", re.I), "tension"),
    (re.compile(r"\b(support|help|benefit|strengt|ease|harmon|flow)\b", re.I), "support"),
    (re.compile(r"\b(when|timing|trigger|activat|transit|period|phase)\b", re.I), "timing"),
]


def _detect_relationship_type(question: str) -> str:
    """Scan question for relationship-type cues."""
    for pat, rel_type in _REL_PATTERNS:
        if pat.search(question):
            return rel_type
    return "connection"


# ═══════════════════════════════════════════════════════════════════════
# Temporal & subject detection heuristics
# ═══════════════════════════════════════════════════════════════════════

_TEMPORAL_KEYWORDS: Dict[str, List[str]] = {
    "transit":        ["transit", "transiting", "right now", "currently", "lately",
                       "these days", "at this time", "this week", "this month",
                       "this year", "passing through", "retrograde"],
    "synastry":       ["synastry", "compatibility", "partner", "spouse", "our chart",
                       "we have", "between us", "her chart", "his chart", "their chart"],
    "solar_return":   ["solar return", "birthday chart"],
    "relocation":     ["relocation", "moving to", "astrocartography", "new city",
                       "relocate", "astromap"],
    "cycle":          ["saturn return", "planetary cycle", "progressed", "progression",
                       "life cycle", "nodal return", "chiron return"],
    "timing_predict": ["when will", "when does", "how soon", "what year",
                       "waiting room", "energy shift", "coming up"],
}

_DYADIC_KEYWORDS: List[str] = [
    "my partner", "my spouse", "our synastry", "our chart",
    "between us", " we ", " our ", " us ", "her chart", "his chart",
    "their chart", "with my",
]

_FAMILIAL_KEYWORDS: List[str] = [
    "my parent", "my mother", "my father", "my child",
    "my sibling", "my family", "my ex",
]


def _detect_temporal(question: str) -> str:
    """Return the most likely temporal dimension from question text."""
    ql = question.lower()
    for dim, kws in _TEMPORAL_KEYWORDS.items():
        if any(kw in ql for kw in kws):
            return dim
    return "natal"


def _detect_subject(question: str) -> str:
    """Return subject configuration: 'single', 'dyadic', or 'familial'."""
    ql = question.lower()
    if any(k in ql for k in _DYADIC_KEYWORDS):
        return "dyadic"
    if any(k in ql for k in _FAMILIAL_KEYWORDS):
        return "familial"
    return "single"


# ═══════════════════════════════════════════════════════════════════════
# Concept splitter — detects multi-concept questions
# ═══════════════════════════════════════════════════════════════════════

# Patterns that suggest the question is about a relationship between concepts
_MULTI_CONCEPT_RE = re.compile(
    r"\b(?:how\s+does?|what.s the (?:relationship|connection)|relate|between|"
    r"affect|impact|connect|link)\b",
    re.I,
)

# Conjunction splitter: "health and career", "love vs money"
_CONCEPT_SPLIT_RE = re.compile(
    r"\s+(?:and|&|vs\.?|versus|or|relate\s+to|connect\s+to|affect|impact)\s+",
    re.I,
)


def _split_concepts(question: str, topic: TopicMatch) -> List[Tuple[str, List[str]]]:
    """
    Try to split a question into distinct concept clusters.

    Returns a list of (label, factors) tuples.  Falls back to a single
    cluster if no multi-concept structure is detected.
    """
    # Fast path: if no multi-concept signal, return the whole topic as one node
    if not _MULTI_CONCEPT_RE.search(question):
        return [(topic.domain or topic.subtopic or "focus", topic.factors)]

    # Try to split the question itself into concept phrases.
    # Strip common leading question words.
    stripped = re.sub(r"^(how\s+(does?|do|can|will|is|are)\s+)", "", question, flags=re.I)
    stripped = re.sub(r"^(what.s the\s+(relationship|connection)\s+(between\s+)?)", "", stripped, flags=re.I)
    stripped = re.sub(r"\?$", "", stripped).strip()

    parts = _CONCEPT_SPLIT_RE.split(stripped)
    if len(parts) < 2:
        return [(topic.domain or topic.subtopic or "focus", topic.factors)]

    # Resolve each fragment independently through topic_maps
    clusters: List[Tuple[str, List[str]]] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        sub_topic = resolve_factors(part)
        label = part.lower().strip()[:40]
        factors = sub_topic.factors if sub_topic.factors else topic.factors
        clusters.append((label, factors))

    return clusters if clusters else [(topic.domain or "focus", topic.factors)]


# ═══════════════════════════════════════════════════════════════════════
# Keyword-based comprehension (fallback)
# ═══════════════════════════════════════════════════════════════════════

def _comprehend_keyword(question: str) -> QuestionGraph:
    """Decompose a question using topic_maps keyword matching only.

    Concept nodes are intentionally empty — will be re-implemented in a
    future step.  Only domain/subtopic/confidence from topic_maps are used.
    """
    topic = resolve_factors(question)

    return QuestionGraph(
        nodes=[],            # gutted — will be re-implemented
        edges=[],            # gutted — will be re-implemented
        question_type="single_focus",
        domain=topic.domain,
        subtopic=topic.subtopic,
        confidence=topic.confidence,
        matched_keywords=topic.matched_keywords,
        source="keyword",
        temporal_dimension=_detect_temporal(question),
        subject_config=_detect_subject(question),
    )


# ═══════════════════════════════════════════════════════════════════════
# Grammar-driven deterministic 5W+H extraction (hybrid Step 1)
# ═══════════════════════════════════════════════════════════════════════

# Pronouns / determiners that signal the querent (self)
_SELF_PRONOUNS: Set[str] = {"i", "me", "my", "mine", "myself", "we", "us", "our"}

# Relationship nouns that signal a third-party person
_RELATIONSHIP_NOUNS: Dict[str, str] = {
    "partner": "partner", "spouse": "spouse", "husband": "husband",
    "wife": "wife", "boyfriend": "boyfriend", "girlfriend": "girlfriend",
    "mother": "mother", "mom": "mother", "father": "father", "dad": "father",
    "parent": "parent", "parents": "parent", "brother": "brother",
    "sister": "sister", "sibling": "sibling", "child": "child",
    "son": "son", "daughter": "daughter", "boss": "boss",
    "friend": "friend", "ex": "ex-partner", "coworker": "coworker",
    "colleague": "colleague", "teacher": "teacher", "mentor": "mentor",
}

# Temporal prepositions / adverbs for WHEN extraction
_TEMPORAL_PREPOSITIONS: Set[str] = {
    "in", "during", "after", "before", "since", "until", "by", "within",
    "throughout", "over", "past", "next", "last",
}

# Temporal modifier words
_TEMPORAL_MODIFIERS: Set[str] = {
    "long", "short", "recent", "upcoming", "current", "future", "past",
    "new", "old", "next", "last", "early", "late",
}

# Temporal nouns that signal a time reference (objects of temporal prepositions)
_TEMPORAL_NOUNS: Set[str] = {
    "year", "years", "month", "months", "week", "weeks", "day", "days",
    "term", "time", "period", "season", "decade", "future", "past",
    "present", "moment", "phase", "chapter", "while",
}

# Locational prepositions for WHERE extraction
_LOCATIONAL_PREPOSITIONS: Set[str] = {"in", "at", "to", "from", "near", "around"}

# Conceptual / figurative domain words — NOT physical locations.
# When these appear as the object of a locational preposition (e.g. "in my
# personality"), the phrase describes a topic/domain, not a place.
_CONCEPTUAL_DOMAINS: Set[str] = {
    # personality / self
    "personality", "character", "nature", "temperament", "identity",
    "self", "ego", "psyche", "shadow",
    # mind / emotion
    "mind", "brain", "consciousness", "subconscious", "unconscious",
    "heart", "soul", "spirit", "energy", "aura",
    "emotions", "feelings", "thoughts", "intuition",
    # life areas
    "life", "lifestyle", "existence", "world", "universe",
    "career", "work", "job", "profession", "vocation", "calling",
    "relationship", "relationships", "marriage", "partnership", "love",
    "family", "friendship", "friendships",
    "finances", "money", "wealth", "income",
    "health", "wellbeing", "wellness", "body",
    "education", "learning", "studies", "school",
    "creativity", "art", "expression",
    # astrology-specific
    "chart", "horoscope", "birth", "natal",
    # abstract containers
    "area", "areas", "domain", "sphere", "realm", "zone", "space",
    "field", "aspect", "aspects", "sector", "department",
    # metaphorical journey
    "path", "journey", "direction", "way", "road",
    "situation", "circumstances", "experience", "experiences",
    "story", "narrative", "chapter", "phase",
    # inner states
    "faith", "belief", "beliefs", "values", "purpose", "potential",
    "growth", "development", "evolution", "transformation",
    "pattern", "patterns", "habit", "habits", "behavior", "behaviour",
}


def _extract_5wh_from_grammar(
    grammar: GrammarDiagram,
    question: str,
    *,
    known_persons: Optional[List[PersonProfile]] = None,
    known_locations: Optional[List[Location]] = None,
) -> Dict[str, Any]:
    """Deterministic 5W+H extraction from a parsed grammar diagram.

    Extracts WHO, WHAT, WHEN, WHERE from the sentence structure.
    WHY and HOW require inference and are left for the LLM call.

    Returns a dict with keys: persons, story_objects, setting_time,
    locations, dilemma (all may be empty lists / None).
    """
    result: Dict[str, Any] = {
        "persons": [],
        "story_objects": [],
        "setting_time": None,
        "locations": [],
        "dilemma": None,
    }

    if not grammar or grammar.confidence <= 0:
        return result

    _known_persons = known_persons or []
    _known_locations = known_locations or []

    # ── WHO — scan subject, objects, clauses for person references ──
    _all_text_fields: List[str] = [
        grammar.subject or "",
        grammar.direct_object or "",
        grammar.indirect_object or "",
    ]
    for clause in grammar.clauses:
        _all_text_fields.append(clause.text or "")

    persons: List[PersonProfile] = []
    _seen_person_keys: Set[str] = set()  # lowercase name / relationship
    _mentions_self = False

    for text_field in _all_text_fields:
        words = text_field.lower().split()
        # Check for self-reference
        if any(w in _SELF_PRONOUNS for w in words):
            _mentions_self = True
        # Check for relationship nouns
        for word in words:
            clean = word.strip(".,;:!?'\"")
            if clean in _RELATIONSHIP_NOUNS:
                rel = _RELATIONSHIP_NOUNS[clean]
                if rel not in _seen_person_keys:
                    _seen_person_keys.add(rel)
                    # Try to match against known session persons
                    matched = _match_known_person(rel, _known_persons)
                    if matched:
                        persons.append(matched)
                    else:
                        persons.append(PersonProfile(
                            name=clean,
                            relationship_to_querent=rel,
                        ))

    # If the question explicitly references self, pull up the session self-profile
    if _mentions_self:
        self_profile = _find_self_profile(_known_persons)
        if self_profile and "self" not in _seen_person_keys:
            persons.insert(0, self_profile)
            _seen_person_keys.add("self")

    result["persons"] = persons

    # ── WHAT — direct object + story objects from modifiers/clauses ──
    story_objects: List[StoryObject] = []
    _dobj = (grammar.direct_object or "").strip()
    if _dobj:
        # Filter out pure pronouns / self-references from being story objects
        dobj_words = _dobj.lower().split()
        is_self_only = all(w.strip(".,") in _SELF_PRONOUNS for w in dobj_words)
        is_person_ref = any(w.strip(".,") in _RELATIONSHIP_NOUNS for w in dobj_words)
        if not is_self_only and not is_person_ref:
            # Strip possessive modifiers for the label
            label = _dobj
            for mod in grammar.modifiers:
                if mod.type == "possessive" and mod.modifies and mod.modifies.lower() in _dobj.lower():
                    label = re.sub(r'\b' + re.escape(mod.word) + r'\b', '', label, flags=re.I).strip()
            story_objects.append(StoryObject(
                name=label or _dobj,
                significance="direct object of the question",
            ))

    # Check clauses for additional story objects (e.g., infinitive complements)
    for clause in grammar.clauses:
        if clause.clause_type in ("adverbial", "infinitive", "purpose"):
            # These describe goals/conditions, not separate story objects
            continue

    result["story_objects"] = story_objects

    # ── Dilemma detection from clause structure ─────────────────────
    q_lower = question.lower()
    if re.search(r'\b(should\s+i|whether\s+to|or\s+should|choose\s+between)\b', q_lower):
        # Basic dilemma signal; full details left to LLM
        result["dilemma"] = Dilemma(description="(detected from grammar — details pending)")

    # ── WHEN — verb tense + temporal prepositions + temporal modifiers
    # Map verb tense to broad setting_time
    tense_map: Dict[str, str] = {
        "past": "past", "past_perfect": "past", "past_continuous": "past",
        "present": "present", "present_perfect": "present",
        "present_continuous": "present",
        "future": "future", "future_perfect": "future",
        "conditional": "future",
    }
    setting_time = tense_map.get(grammar.verb_tense or "", None)

    # Scan prepositional phrases for temporal references
    for pp in grammar.prepositional_phrases:
        prep_lower = pp.preposition.lower()
        obj_lower = (pp.object or "").lower()
        obj_words = set(obj_lower.split())
        # If the preposition is temporal AND the object contains a time noun
        if (prep_lower in _TEMPORAL_PREPOSITIONS
                and obj_words & _TEMPORAL_NOUNS):
            # Use the phrase to refine setting_time
            if any(w in obj_words for w in ("future", "next", "upcoming")):
                setting_time = "future"
            elif any(w in obj_words for w in ("past", "last", "previous")):
                setting_time = "past"
            # else keep existing tense-based setting_time

    # Scan modifiers for temporal signals
    for mod in grammar.modifiers:
        if mod.word.lower() in _TEMPORAL_MODIFIERS:
            target = (mod.modifies or "").lower()
            if target in _TEMPORAL_NOUNS:
                # "long term" → future-oriented
                if mod.word.lower() in ("long", "upcoming", "next", "future"):
                    setting_time = setting_time or "future"
                elif mod.word.lower() in ("recent", "past", "last"):
                    setting_time = setting_time or "past"

    result["setting_time"] = setting_time

    # ── WHERE — locational prepositional phrases ────────────────────
    # Conceptual / figurative phrases ("in my personality") are routed
    # to story_objects instead of locations.
    locations: List[Location] = []
    for pp in grammar.prepositional_phrases:
        prep_lower = pp.preposition.lower()
        obj_text = (pp.object or "").strip()
        if not obj_text:
            continue
        obj_words = set(obj_text.lower().split())
        # Skip if not a locational preposition or if it's temporal
        if prep_lower not in _LOCATIONAL_PREPOSITIONS:
            continue
        if obj_words & _TEMPORAL_NOUNS:
            continue

        # Strip possessive pronouns ("my", "your", "their") for lookup
        _stripped_words = [
            w for w in obj_words
            if w not in {"my", "your", "his", "her", "their", "our", "its",
                         "the", "a", "an", "this", "that"}
        ]

        # Check if any core word is a conceptual domain
        if _stripped_words and any(w in _CONCEPTUAL_DOMAINS for w in _stripped_words):
            # Route to story_objects as a contextual domain, not a location
            story_objects.append(StoryObject(
                name=obj_text,
                significance="contextual domain / frame of the question",
            ))
            continue

        # Genuine location — try to match against known locations
        matched_loc = _match_known_location(obj_text, _known_locations)
        if matched_loc:
            locations.append(matched_loc)
        else:
            locations.append(Location(name=obj_text))

    result["locations"] = locations

    return result


def _find_self_profile(
    known_persons: Optional[List[PersonProfile]],
) -> Optional[PersonProfile]:
    """Find the querent's self PersonProfile from session-accumulated profiles."""
    if not known_persons:
        return None
    for p in known_persons:
        if p.relationship_to_querent == "self":
            return p
    return None


def _match_known_person(
    relationship: str,
    known_persons: List[PersonProfile],
) -> Optional[PersonProfile]:
    """Match a relationship noun against accumulated session persons."""
    rel_lower = relationship.lower()
    for p in known_persons:
        if (p.relationship_to_querent or "").lower() == rel_lower:
            return p
        if (p.name or "").lower() == rel_lower:
            return p
    return None


def _match_known_location(
    name: str,
    known_locations: List[Location],
) -> Optional[Location]:
    """Match a location name against accumulated session locations."""
    name_lower = name.lower()
    for loc in known_locations:
        if loc.name.lower() == name_lower:
            return loc
    return None


# ═══════════════════════════════════════════════════════════════════════
# LLM-based comprehension (structured output, two-phase)
# ═══════════════════════════════════════════════════════════════════════

_COMPREHENSION_SYSTEM = """\
You are the comprehension layer of an astrology chatbot.

The sentence has already been grammatically parsed and the WHO, WHAT, WHEN,
and WHERE have been extracted deterministically from the grammar diagram.
Those pre-extracted facts are provided under PRE_EXTRACTED_5WH below.

Your job is to provide ONLY the fields that require human-level inference:

1. WHY — Intent & desired input
   intent_context: why is the user asking? What context did they give?
   desired_input: what actionable output are they hoping to receive?

2. HOW — Querent state (assess the tone and stance of the message)
   emotional_tone: "neutral" | "curious" | "hopeful" | "anxious" |
                   "distressed" | "desperate" | "discouraged" | "excited"
   certainty_level: "unsure" | "somewhat_sure" | "confident"
   guidance_openness: "minimal" | "moderate" | "extensive"
   expressed_feelings: list of emotional statements from their message
   demeanor_notes: your brief observation of their overall presentation

3. Answer aim — what KIND of answer do they need?
   aim_type: "diagnostic" (why?), "advisory" (how?), "predictive" (when?),
             "validating" (is this true?), "exploratory" (tell me about)
   depth: "overview" | "moderate" | "deep_dive"
   urgency: "low" | "moderate" | "high" | "immediate"
   specificity: "broad" | "focused" | "pinpoint"

4. Dilemma enrichment — if PRE_EXTRACTED_5WH flags a dilemma, fill in:
   description, options, stakes, constraints, desired_outcome.
   If no dilemma was detected, omit.

5. Transit references — if the question mentions astrological transits:
   transiting_body, natal_body, aspect_type, timeframe, description.

6. Domain classification — select from DOMAINS list which life-domains apply.

7. Classification metadata
   question_type: "single_focus" | "relationship" | "multi_node" | "open_exploration"
   temporal_dimension: "natal" | "transit" | "synastry" | "solar_return" |
                       "relocation" | "cycle" | "timing_predict". Default "natal".
   subject_config: "single" | "dyadic" | "familial". Default "single".

8. Paraphrase — one sentence restating the question and the pre-extracted
   context in plain language. This should reflect all 5W+H dimensions
   that were found, not just the surface question. No astrology jargon.

9. Self-assessment
   comprehension_confidence: 0.0–1.0 how well you understood the question.
   ambiguities: list of unclear aspects
   contradictions: list of conflicting signals

CRITICAL — STATEMENTS vs QUESTIONS:
If the user's message is a STATEMENT or ANECDOTE with NO clear question or
request for insight, you MUST:
  - Set comprehension_confidence very low (0.1–0.25)
  - Put "no_explicit_question" in the ambiguities list
  - Do NOT fabricate an intent_context or desired_input — leave them empty/null
  - Do NOT guess what the user "probably" wants to know
Examples of statements (NOT questions):
  "I told my brother about my job and he was upset."
  "My Saturn return started last month."
  "I've been feeling restless lately."
These deserve clarification, not assumptions.

RULES:
1. If a RECOGNIZED_TERM is provided, its meaning takes precedence.
2. Omit any optional object/array that would be empty or null.
3. Do NOT re-extract WHO, WHAT, WHEN, WHERE — those come from the grammar.
   Only provide WHY, HOW, answer_aim, domains, paraphrase, and metadata.

Respond with ONLY valid JSON matching this schema:
{
  "intent_context": "string",
  "desired_input": "string",
  "querent_state": {"emotional_tone": "string", "certainty_level": "string",
                    "guidance_openness": "string", "expressed_feelings": ["string"],
                    "demeanor_notes": "string"},
  "answer_aim": {"aim_type": "string", "depth": "string", "urgency": "string",
                 "specificity": "string"},
  "dilemma": {"description": "string", "options": ["string"], "stakes": "string",
              "constraints": ["string"], "desired_outcome": "string"},
  "transits": [{"transiting_body": "string", "natal_body": "string",
                "aspect_type": "string", "timeframe": "string", "description": "string"}],
  "domains": ["string"],
  "question_type": "string",
  "temporal_dimension": "string",
  "subject_config": "string",
  "paraphrase": "string",
  "comprehension_confidence": 0.85,
  "ambiguities": ["string"],
  "contradictions": ["string"]
}
"""


def _comprehend_llm(
    question: str,
    chart: "AstrologicalChart",
    api_key: str,
    model: str = "google/gemini-2.0-flash-001",
    matched_term: Optional["Term"] = None,  # type: ignore[name-defined]
    known_persons: Optional[List[PersonProfile]] = None,
    known_locations: Optional[List[Location]] = None,
    pending_clarification: Optional[str] = None,
    grammar: Optional[GrammarDiagram] = None,
) -> Optional[QuestionGraph]:
    """
    Hybrid comprehension: deterministic 5W+H from grammar + LLM for
    subjective fields (WHY, HOW, aim, paraphrase, domain).

    Phase A: ``_extract_5wh_from_grammar()`` — deterministic WHO/WHAT/WHEN/WHERE
    Phase B: Slimmed LLM call — WHY, HOW, AnswerAim, domain, paraphrase

    Returns None on any failure (caller should fall back to keyword path).
    """
    try:
        import openai
    except ImportError:
        return None

    # ── Phase A: deterministic extraction from grammar ───────────────
    grammar_5wh = _extract_5wh_from_grammar(
        grammar or GrammarDiagram(),
        question,
        known_persons=known_persons,
        known_locations=known_locations,
    )

    # ── Phase B: LLM call for subjective fields ──────────────────────
    from src.mcp.topic_maps import list_domains
    domain_names = [d["name"] for d in list_domains()]

    parts = [
        f"DOMAINS:\n{json.dumps(domain_names)}",
    ]
    if matched_term is not None:
        parts.append(
            f"RECOGNIZED_TERM: \"{matched_term.canonical}\" — {matched_term.description}"
        )
    if pending_clarification:
        parts.append(
            f"USER'S CLARIFICATION (answering a prior follow-up):\n{pending_clarification}"
        )

    # Inject the grammar diagram as structured context
    if grammar and grammar.confidence > 0:
        grammar_ctx = (
            f"GRAMMAR_PARSE (pre-parsed sentence structure):\n"
            f"  Subject: {grammar.subject}\n"
            f"  Verb: {grammar.verb} ({grammar.verb_tense})\n"
            f"  Direct object: {grammar.direct_object or '(none)'}\n"
            f"  Indirect object: {grammar.indirect_object or '(none)'}\n"
            f"  Sentence type: {grammar.sentence_type}"
        )
        if grammar.prepositional_phrases:
            pp_lines = "; ".join(
                f"{pp.preposition} → {pp.object}" for pp in grammar.prepositional_phrases
            )
            grammar_ctx += f"\n  Prep phrases: {pp_lines}"
        if grammar.clauses:
            cl_lines = "; ".join(
                f"[{c.clause_type}] {c.text} ({c.role})" for c in grammar.clauses
            )
            grammar_ctx += f"\n  Clauses: {cl_lines}"
        parts.append(grammar_ctx)

    # Inject the deterministic 5W+H extractions so the LLM can see them
    pre_5wh_summary: Dict[str, Any] = {}
    if grammar_5wh["persons"]:
        pre_5wh_summary["WHO"] = [
            {"name": p.name, "relationship": p.relationship_to_querent}
            for p in grammar_5wh["persons"]
        ]
    if grammar_5wh["story_objects"]:
        pre_5wh_summary["WHAT"] = [
            {"name": o.name, "significance": o.significance}
            for o in grammar_5wh["story_objects"]
        ]
    if grammar_5wh["setting_time"]:
        pre_5wh_summary["WHEN"] = grammar_5wh["setting_time"]
    if grammar_5wh["locations"]:
        pre_5wh_summary["WHERE"] = [loc.name for loc in grammar_5wh["locations"]]
    if grammar_5wh["dilemma"]:
        pre_5wh_summary["DILEMMA_DETECTED"] = True
    if pre_5wh_summary:
        parts.append(
            f"PRE_EXTRACTED_5WH (from grammar — do NOT re-extract these):\n"
            f"{json.dumps(pre_5wh_summary, ensure_ascii=False)}"
        )

    parts.append(f"Question: {question}")
    user_msg = "\n\n".join(parts)

    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/theonionqueen13/Rosetta",
                "X-Title": "Rosetta Astrology",
            },
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _COMPREHENSION_SYSTEM.strip()},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_tokens=1200,
        )
        raw = response.choices[0].message.content or ""
    except Exception:
        return None

    # Strip markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    # ── Parse LLM-only fields ───────────────────────────────────────

    q_type = data.get("question_type", "single_focus")
    if q_type not in {"single_focus", "relationship", "multi_node", "open_exploration"}:
        q_type = "single_focus"

    llm_domains: List[str] = data.get("domains") or []
    domain = ""
    if llm_domains:
        domain = llm_domains[0]
    elif matched_term is not None:
        domain = matched_term.domain

    paraphrase = str(data.get("paraphrase", "")).strip()

    valid_temporal = {"natal", "transit", "synastry", "solar_return", "relocation", "cycle", "timing_predict"}
    valid_subject = {"single", "dyadic", "familial"}
    temporal = data.get("temporal_dimension", "")
    if temporal not in valid_temporal:
        temporal = _detect_temporal(question)
    subject = data.get("subject_config", "")
    if subject not in valid_subject:
        subject = _detect_subject(question)

    # ── WHY — intent context (LLM-only) ────────────────────────────
    intent_context = data.get("intent_context") or None
    desired_input = data.get("desired_input") or None

    # ── HOW — querent state (LLM-only) ─────────────────────────────
    querent_state: Optional[QuerentState] = None
    qs_data = data.get("querent_state")
    if qs_data and isinstance(qs_data, dict):
        _tone_map = {e.value: e for e in EmotionalTone}
        _cert_map = {e.value: e for e in CertaintyLevel}
        _guide_map = {e.value: e for e in GuidanceOpenness}
        querent_state = QuerentState(
            emotional_tone=_tone_map.get(qs_data.get("emotional_tone", ""), EmotionalTone.NEUTRAL),
            certainty_level=_cert_map.get(qs_data.get("certainty_level", ""), CertaintyLevel.SOMEWHAT_SURE),
            guidance_openness=_guide_map.get(qs_data.get("guidance_openness", ""), GuidanceOpenness.MODERATE),
            expressed_feelings=qs_data.get("expressed_feelings", []),
            demeanor_notes=qs_data.get("demeanor_notes"),
        )

    # ── Answer aim (LLM-only) ──────────────────────────────────────
    answer_aim: Optional[AnswerAim] = None
    aim_data = data.get("answer_aim")
    if aim_data and isinstance(aim_data, dict):
        _aim_type_map = {e.value: e for e in AimType}
        _depth_map = {e.value: e for e in Depth}
        _urgency_map = {e.value: e for e in Urgency}
        _specificity_map = {e.value: e for e in Specificity}
        answer_aim = AnswerAim(
            aim_type=_aim_type_map.get(aim_data.get("aim_type", ""), AimType.EXPLORATORY),
            depth=_depth_map.get(aim_data.get("depth", ""), Depth.MODERATE),
            urgency=_urgency_map.get(aim_data.get("urgency", ""), Urgency.MODERATE),
            specificity=_specificity_map.get(aim_data.get("specificity", ""), Specificity.FOCUSED),
        )

    # ── Dilemma enrichment (LLM fills in details if grammar detected one)
    dilemma: Optional[Dilemma] = grammar_5wh.get("dilemma")
    dil_data = data.get("dilemma")
    if dil_data and isinstance(dil_data, dict) and dil_data.get("description"):
        dilemma = Dilemma(
            description=str(dil_data.get("description", "")),
            options=dil_data.get("options", []),
            stakes=dil_data.get("stakes"),
            constraints=dil_data.get("constraints", []),
            desired_outcome=dil_data.get("desired_outcome"),
        )

    # ── Transit references (LLM-only) ──────────────────────────────
    transits: List[Transit] = []
    for tr_data in data.get("transits", []):
        transits.append(Transit(
            transiting_body=tr_data.get("transiting_body"),
            natal_body=tr_data.get("natal_body"),
            aspect_type=tr_data.get("aspect_type"),
            timeframe=tr_data.get("timeframe"),
            description=tr_data.get("description"),
        ))

    # ── Sufficiency metadata ────────────────────────────────────────
    comprehension_confidence = float(data.get("comprehension_confidence", 0.85))
    ambiguities = data.get("ambiguities", [])
    contradictions = data.get("contradictions", [])

    # ── Merge deterministic + LLM results into QuestionGraph ────────
    # Concept nodes are intentionally empty — will be rebuilt in a future step.
    return QuestionGraph(
        nodes=[],            # gutted — will be re-implemented
        edges=[],            # gutted — will be re-implemented
        question_type=q_type,
        domain=domain,
        source="llm",
        confidence=0.85,
        paraphrase=paraphrase,
        temporal_dimension=temporal,
        subject_config=subject,
        # WHO, WHAT, WHERE from grammar (deterministic)
        persons=grammar_5wh["persons"],
        story_objects=grammar_5wh["story_objects"],
        locations=grammar_5wh["locations"],
        # WHEN: prefer grammar-derived, override if LLM disagrees
        setting_time=grammar_5wh["setting_time"],
        # WHY, HOW, aim from LLM (inferential)
        dilemma=dilemma,
        answer_aim=answer_aim,
        transits=transits,
        intent_context=intent_context,
        desired_input=desired_input,
        querent_state=querent_state,
        comprehension_confidence=comprehension_confidence,
        ambiguities=ambiguities,
        contradictions=contradictions,
    )


# ═══════════════════════════════════════════════════════════════════════
# Chart anchoring — validates factors & maps to circuit shapes
# ═══════════════════════════════════════════════════════════════════════

_HOUSE_RE = re.compile(r"^(\d+)\w*\s+[Hh]ouse$")


def _anchor_to_chart(graph: QuestionGraph, chart: "AstrologicalChart") -> None:
    """
    Validate factors against the chart and find focus_circuits.

    Mutates the QuestionGraph in place.

    For each factor, if it matches a chart object name, a sign, or a
    house label, keep it.  Then scan shapes in chart.shapes (and
    circuit_simulation.shape_circuits) to find which shape_ids contain
    the relevant factors.
    """
    # Build lookup of chart object names
    chart_names: Set[str] = set()
    obj_to_house: Dict[str, int] = {}
    for cobj in chart.objects:
        name = cobj.object_name.name if cobj.object_name else ""
        if name:
            chart_names.add(name)
            # map to house number for house-factor expansion
            h = getattr(cobj, "placidus_house", None)
            if h:
                obj_to_house[name] = h.number if hasattr(h, "number") else 0

    # Expand house factors: "6th House" → also include objects in that house
    house_occupants: Dict[int, List[str]] = {}
    for name, h_num in obj_to_house.items():
        house_occupants.setdefault(h_num, []).append(name)

    all_factors: Set[str] = set()
    for node in graph.nodes:
        validated: List[str] = []
        for f in node.factors:
            # Direct match to chart object
            if f in chart_names or f in _SIGN_NAMES:
                validated.append(f)
                continue
            # House label → keep + expand to occupants
            m = _HOUSE_RE.match(f)
            if m:
                h_num = int(m.group(1))
                validated.append(f)
                # Add occupants of that house
                for occ in house_occupants.get(h_num, []):
                    if occ not in validated:
                        validated.append(occ)
                continue
            # Check common aliases
            if f in {"AC", "Ascendant", "DC", "Descendant", "MC", "Midheaven", "IC", "Immum Coeli"}:
                validated.append(f)
        node.factors = validated
        all_factors.update(validated)

    graph.all_factors = sorted(all_factors)

    # Map factors to shape_ids
    focus_circuits: Set[int] = set()
    for shape in (chart.shapes or []):
        # Support DetectedShape dataclass and legacy dict
        if hasattr(shape, "shape_type"):
            members = shape.members
            shape_id = shape.shape_id
        elif isinstance(shape, dict):
            members = shape.get("members", [])
            shape_id = shape.get("id", -1)
        else:
            continue
        if set(members) & all_factors:
            focus_circuits.add(shape_id)

    graph.focus_circuits = sorted(focus_circuits)

    # If LLM path produced no factors at all, enrich from topic_maps —
    # but only when the term registry hasn't already resolved the intent.
    # A known intent (e.g. "potency_ranking") means the reading engine will
    # handle factor selection itself; keyword-enrichment here would only
    # inject spurious topic guesses.
    if not graph.all_factors and graph.source == "llm" and not graph.question_intent:
        kw_graph = _comprehend_keyword(graph.comprehension_note or "general reading")
        for node in kw_graph.nodes:
            graph.nodes.append(node)
        graph.all_factors = sorted(set(f for n in graph.nodes for f in n.factors))

    graph.anchored = True


# ═══════════════════════════════════════════════════════════════════════
# Sufficiency check — decides whether to ask for clarification
# ═══════════════════════════════════════════════════════════════════════

def _check_sufficiency(graph: QuestionGraph) -> Optional[ClarificationRequest]:
    """Examine a populated QuestionGraph and decide if clarification is needed.

    Returns a ClarificationRequest if the bot should ask the user for more
    info, or None if comprehension is sufficient to proceed.
    """
    # Rule 1: no explicit question detected (statement / anecdote)
    # Check this FIRST since it's the most specific signal.
    if graph.ambiguities and "no_explicit_question" in graph.ambiguities:
        return ClarificationRequest(
            reason="The message appears to be a statement rather than a question",
            category=ClarificationCategory.AMBIGUOUS_INTENT,
            best_guesses=[],
            follow_up_question=(
                "Thanks for sharing that with me! I want to make sure I help you "
                "in the right way — is there something specific you'd like me to "
                "look at in your chart about this, or are you just giving me context "
                "for a follow-up question?"
            ),
            partial_graph=graph,
        )

    # Rule 2: very low comprehension confidence from the LLM
    if graph.comprehension_confidence > 0 and graph.comprehension_confidence < 0.4:
        guesses = graph.ambiguities[:3] if graph.ambiguities else []
        if not guesses:
            guesses = [graph.paraphrase] if graph.paraphrase else ["a general chart reading"]
        return ClarificationRequest(
            reason=f"Comprehension confidence is low ({graph.comprehension_confidence:.0%})",
            category=ClarificationCategory.AMBIGUOUS_INTENT,
            best_guesses=guesses,
            follow_up_question=(
                "I want to make sure I understand your question correctly. "
                "Did you mean:\n" +
                "\n".join(f"  {i+1}. {g}" for i, g in enumerate(guesses)) +
                "\n\nOr something else entirely?"
            ),
            partial_graph=graph,
        )

    # Rule 3: contradictions detected by the LLM
    if graph.contradictions:
        return ClarificationRequest(
            reason="Contradictory information detected in the question",
            category=ClarificationCategory.CONTRADICTORY_INFO,
            best_guesses=graph.contradictions[:3],
            follow_up_question=(
                "I noticed some things in your question that seem to "
                "contradict each other — could you help me clarify?\n\n" +
                "\n".join(f"  • {c}" for c in graph.contradictions[:3])
            ),
            partial_graph=graph,
        )

    # All good — no clarification needed
    return None


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def comprehend(
    question: str,
    chart: "AstrologicalChart",
    *,
    api_key: Optional[str] = None,
    llm_model: str = "google/gemini-2.0-flash-001",
    known_persons: Optional[List[PersonProfile]] = None,
    known_locations: Optional[List[Location]] = None,
    pending_clarification: Optional[str] = None,
) -> ComprehensionResult:
    """
    Decompose *question* into a ``QuestionGraph`` anchored to *chart*.

    Returns a ``ComprehensionResult`` that wraps either a complete
    QuestionGraph or a ClarificationRequest (when the bot needs to ask
    the user for more information before proceeding).

    Resolution order
    ----------------
    1. Term registry — always runs first; stamps ``question_intent`` when a
       canonical astrological concept is recognised.
    2. LLM path — full 5W+H extraction (requires ``api_key``).
       Receives any matched term and session context as input.
    3. Term-only fallback — when a term was matched but no API key is
       available, builds a minimal graph from the term without running the
       keyword guesser.  Rich 5W+H fields remain at defaults.
    4. Keyword fallback — only runs when no term matched AND no API key.
       Uses ``topic_maps.resolve_factors()`` for life-domain questions.

    After resolution, a sufficiency check may return a ClarificationRequest.
    Otherwise, anchors to the chart and returns a complete result.

    Parameters
    ----------
    known_persons : list of PersonProfile, optional
        Accumulated person profiles from prior turns in the session.
    known_locations : list of Location, optional
        Accumulated locations from prior turns in the session.
    pending_clarification : str, optional
        The user's answer to a prior ClarificationRequest.
    """
    # ── Step 0: Grammar diagram — always runs first when key avail ──
    grammar_diagram: Optional[GrammarDiagram] = None
    if api_key:
        grammar_diagram = parse_grammar(question, api_key, model=llm_model)

    # ── Step 1: Term registry ─────────────────────────────────────
    _terms = load_terms()
    _matched_term = match_terms(question, _terms)

    graph: Optional[QuestionGraph] = None

    # ── Step 2: LLM path (if key available) ──────────────────────
    if api_key:
        graph = _comprehend_llm(
            question, chart, api_key,
            model=llm_model,
            matched_term=_matched_term,
            known_persons=known_persons,
            known_locations=known_locations,
            pending_clarification=pending_clarification,
            grammar=grammar_diagram,
        )

    # ── Step 3: Term-only fallback (term matched, no API key) ────────
    if graph is None and _matched_term is not None:
        graph = QuestionGraph(
            nodes=[],            # gutted — will be re-implemented
            edges=[],            # gutted — will be re-implemented
            question_type="single_focus",
            domain=_matched_term.domain,
            confidence=0.9,
            source="term_registry",
            paraphrase=f"(term match: {_matched_term.canonical})",
            temporal_dimension=_detect_temporal(question),
            subject_config=_detect_subject(question),
        )

    # ── Step 4: Keyword fallback (no term, no API key) ──────────────
    if graph is None:
        graph = _comprehend_keyword(question)

    # ── Attach grammar diagram to graph ───────────────────────────
    if grammar_diagram is not None:
        graph.grammar = grammar_diagram

    # ── Stamp intent from term registry ───────────────────────────
    if _matched_term:
        graph.question_intent = _matched_term.intent

    # ── Sufficiency check ─────────────────────────────────────────
    clarification = _check_sufficiency(graph)
    if clarification is not None:
        return ComprehensionResult(graph=None, clarification=clarification)

    # ── Anchor to chart (validate factors, find circuit shapes) ──────
    graph.comprehension_note = question  # temp store for _anchor_to_chart
    _anchor_to_chart(graph, chart)

    # ── Final comprehension note for the dev monologue ──────────────
    paraphrase_fragment = f" | understood: \"{graph.paraphrase}\"" if graph.paraphrase and not graph.paraphrase.startswith("(") else ""
    temporal_fragment = f" | temporal: {graph.temporal_dimension}" if graph.temporal_dimension != "natal" else ""
    subject_fragment = f" | subject: {graph.subject_config}" if graph.subject_config != "single" else ""
    aim_fragment = f" | aim: {graph.answer_aim.aim_type.value}" if graph.answer_aim else ""
    tone_fragment = f" | tone: {graph.querent_state.emotional_tone.value}" if graph.querent_state and graph.querent_state.emotional_tone != EmotionalTone.NEUTRAL else ""
    persons_fragment = f" | persons: {[p.name or p.relationship_to_querent for p in graph.persons]}" if graph.persons else ""
    grammar_fragment = ""
    if graph.grammar and graph.grammar.confidence > 0:
        grammar_fragment = f" | grammar: {grammar_summary_line(graph.grammar)}"
    graph.comprehension_note = (
        f"Q: {question} -> {graph.question_type} | "
        f"intent: {graph.question_intent or 'none'} | "
        f"shapes: {graph.focus_circuits} | "
        f"source: {graph.source} | "
        f"conf: {graph.confidence:.0%}"
        + paraphrase_fragment
        + temporal_fragment
        + subject_fragment
        + aim_fragment
        + tone_fragment
        + persons_fragment
        + grammar_fragment
    )

    return ComprehensionResult(graph=graph, clarification=None)
