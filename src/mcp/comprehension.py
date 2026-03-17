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
from src.mcp.comprehension_models import (
    AimType, Depth, Urgency, Specificity,
    EmotionalTone, CertaintyLevel, GuidanceOpenness,
    ClarificationCategory,
    PersonProfile, LocationLink, StoryObject, Dilemma, AnswerAim,
    Transit, Location, QuerentState,
    ClarificationRequest, ComprehensionResult,
)

if TYPE_CHECKING:
    from models_v2 import AstrologicalChart


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
    """Decompose a question using topic_maps keyword matching only."""
    topic = resolve_factors(question)
    clusters = _split_concepts(question, topic)

    nodes: List[QuestionNode] = []
    for label, factors in clusters:
        nodes.append(QuestionNode(label=label, factors=factors, source="keyword"))

    # Determine question type
    if len(nodes) == 0:
        q_type = "open_exploration"
    elif len(nodes) == 1:
        q_type = "single_focus"
    elif len(nodes) == 2:
        q_type = "relationship"
    else:
        q_type = "multi_node"

    # Build edges
    edges: List[QuestionEdge] = []
    if len(nodes) >= 2:
        rel_type = _detect_relationship_type(question)
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                edges.append(QuestionEdge(
                    node_a=nodes[i].label,
                    node_b=nodes[j].label,
                    relationship=rel_type,
                ))

    return QuestionGraph(
        nodes=nodes,
        edges=edges,
        question_type=q_type,
        domain=topic.domain,
        subtopic=topic.subtopic,
        confidence=topic.confidence,
        matched_keywords=topic.matched_keywords,
        source="keyword",
        temporal_dimension=_detect_temporal(question),
        subject_config=_detect_subject(question),
    )


# ═══════════════════════════════════════════════════════════════════════
# LLM-based comprehension (structured output, two-phase)
# ═══════════════════════════════════════════════════════════════════════

_COMPREHENSION_SYSTEM = """\
You are the comprehension layer of an astrology chatbot. Your job is to
deeply understand what the user is genuinely asking BEFORE you touch any
astrology.  Extract the full 5W+H from their question or story.

Work in two phases:

--- PHASE 1: ACTIVE LISTENING --- understand the human question ---
Restate the user's question in one plain sentence. No astrology yet.
Ask yourself: what does this person actually want to know?

Extract the full context:

WHO:
  - Is it just the querent, or are other people involved?
  - For each person mentioned (besides the user), record:
    name (or label like "partner"), relationship_to_querent,
    any locations they're connected to (with how: "lives there", etc.)

WHAT:
  - Topics of the question
  - Story objects: any notable things mentioned (job offer, house, instrument, etc.)
  - Dilemma: if the user faces a decision, capture: description, options, stakes,
    constraints, desired_outcome
  - Answer aim: what KIND of answer do they need?
    aim_type: "diagnostic" (why?), "advisory" (how?), "predictive" (when?),
              "validating" (is this true?), "exploratory" (tell me about)
    depth: "overview" | "moderate" | "deep_dive"
    urgency: "low" | "moderate" | "high" | "immediate"
    specificity: "broad" | "focused" | "pinpoint"

WHEN:
  - setting_time: "past" | "present" | "future" | specific date/period
  - Any transits mentioned: transiting_body, natal_body, aspect_type, timeframe
  - temporal_dimension: "natal" | "transit" | "synastry" | "solar_return" |
    "relocation" | "cycle" | "timing_predict"

WHERE:
  - Locations mentioned: name, type (city/venue/home/workplace/country),
    connected persons, relevance

WHY:
  - intent_context: why is the user asking? What context did they give?
  - desired_input: what actionable output are they hoping to receive?

HOW:
  - How did they ask? Assess the querent's state:
    emotional_tone: "neutral" | "curious" | "hopeful" | "anxious" |
                    "distressed" | "desperate" | "discouraged" | "excited"
    certainty_level: "unsure" | "somewhat_sure" | "confident"
    guidance_openness: "minimal" | "moderate" | "extensive"
    expressed_feelings: list of emotional statements from their message
    demeanor_notes: your brief observation of their overall presentation

Identify which DOMAINS from the DOMAINS list genuinely apply.
Also self-assess your comprehension_confidence (0.0\u20131.0).
Flag any ambiguities or contradictions in the question.

CRITICAL — STATEMENTS vs QUESTIONS:
If the user's message is a STATEMENT or ANECDOTE with NO clear question or
request for insight, you MUST:
  - Set comprehension_confidence very low (0.1–0.25)
  - Put "no_explicit_question" in the ambiguities list
  - Do NOT fabricate an intent_context or desired_input — leave them empty/null
  - Do NOT guess what the user "probably" wants to know
  - The user may just be sharing context for a follow-up question
Examples of statements (NOT questions):
  "I told my brother about my job and he was upset."
  "My Saturn return started last month."
  "I've been feeling restless lately."
These deserve clarification, not assumptions.

--- PHASE 2: ASTROLOGICAL MAPPING ---
Given your Phase 1 understanding, select specific planets, signs, or houses
from VALID_FACTORS that a skilled astrologer would use to answer this question.
If the question is about a structural concept (e.g. "which planet is strongest"),
factors MUST be empty \u2014 the engine will handle factor selection itself.
NEVER invent factor names outside VALID_FACTORS.

RULES:
1. paraphrase: one sentence in plain language, no jargon.
2. domains: list of matching domain names from DOMAINS; may be empty.
3. question_type: "single_focus" | "relationship" | "multi_node" | "open_exploration".
4. temporal_dimension: one of the values listed above. Default "natal".
5. subject_config: "single" | "dyadic" | "familial". Default "single".
6. nodes: each concept the user mentions. label is 1-3 words lowercase.
7. factors in each node: ONLY items from VALID_FACTORS, or empty list.
8. NEVER guess or hallucinate factor names.
9. If a RECOGNIZED_TERM is provided, its meaning takes precedence.
10. comprehension_confidence: 0.0\u20131.0 how well you understood the question.
11. Omit any optional object/array that would be empty or null.

Respond with ONLY valid JSON matching this schema:
{
  "paraphrase": "string",
  "domains": ["string"],
  "question_type": "string",
  "temporal_dimension": "string",
  "subject_config": "string",
  "nodes": [{"label": "string", "factors": ["string"]}],
  "edges": [{"node_a": "string", "node_b": "string", "relationship": "string"}],
  "persons": [{"name": "string", "relationship_to_querent": "string",
               "locations": [{"location_name": "string", "connection": "string"}]}],
  "story_objects": [{"name": "string", "description": "string", "significance": "string",
                     "related_persons": ["string"], "related_locations": ["string"]}],
  "dilemma": {"description": "string", "options": ["string"], "stakes": "string",
              "constraints": ["string"], "desired_outcome": "string"},
  "answer_aim": {"aim_type": "string", "depth": "string", "urgency": "string",
                 "specificity": "string"},
  "setting_time": "string",
  "transits": [{"transiting_body": "string", "natal_body": "string",
                "aspect_type": "string", "timeframe": "string", "description": "string"}],
  "locations": [{"name": "string", "location_type": "string",
                 "connected_persons": [{"person": "string", "connection": "string"}],
                 "relevance": "string"}],
  "intent_context": "string",
  "desired_input": "string",
  "querent_state": {"emotional_tone": "string", "certainty_level": "string",
                    "guidance_openness": "string", "expressed_feelings": ["string"],
                    "demeanor_notes": "string"},
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
) -> Optional[QuestionGraph]:
    """
    Two-phase LLM comprehension with full 5W+H extraction.

    Returns None on any failure (caller should fall back to keyword path).
    """
    try:
        import openai
    except ImportError:
        return None

    from src.mcp.topic_maps import list_domains
    domain_names = [d["name"] for d in list_domains()]

    vocab = _build_vocabulary(chart)
    parts = [
        f"DOMAINS:\n{json.dumps(domain_names)}",
        f"VALID_FACTORS:\n{json.dumps(vocab)}",
    ]
    if matched_term is not None:
        parts.append(
            f"RECOGNIZED_TERM: \"{matched_term.canonical}\" — {matched_term.description}"
        )
    if known_persons:
        parts.append(
            f"KNOWN_PERSONS (from prior turns):\n{json.dumps([p.to_dict() for p in known_persons], ensure_ascii=False)}"
        )
    if known_locations:
        parts.append(
            f"KNOWN_LOCATIONS (from prior turns):\n{json.dumps([loc.to_dict() for loc in known_locations], ensure_ascii=False)}"
        )
    if pending_clarification:
        parts.append(
            f"USER'S CLARIFICATION (answering a prior follow-up):\n{pending_clarification}"
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

    # ── Parse core fields (same as before) ──────────────────────────
    valid_set = set(vocab)
    nodes: List[QuestionNode] = []
    for nd in data.get("nodes", []):
        label = str(nd.get("label", "")).strip().lower()
        factors = [f for f in nd.get("factors", []) if f in valid_set]
        if label:
            nodes.append(QuestionNode(label=label, factors=factors, source="llm"))

    edges: List[QuestionEdge] = []
    valid_rels = {"connection", "tension", "support", "timing"}
    for ed in data.get("edges", []):
        rel = ed.get("relationship", "connection")
        if rel not in valid_rels:
            rel = "connection"
        edges.append(QuestionEdge(
            node_a=str(ed.get("node_a", "")),
            node_b=str(ed.get("node_b", "")),
            relationship=rel,
        ))

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

    # ── Parse WHO — persons ─────────────────────────────────────────
    persons: List[PersonProfile] = []
    for p_data in data.get("persons", []):
        locs: List[LocationLink] = []
        for loc_d in p_data.get("locations", []):
            locs.append(LocationLink(
                location_name=str(loc_d.get("location_name", "")),
                connection=str(loc_d.get("connection", "")),
            ))
        persons.append(PersonProfile(
            name=p_data.get("name"),
            relationship_to_querent=p_data.get("relationship_to_querent"),
            relationships_to_others=p_data.get("relationships_to_others", []),
            memories=p_data.get("memories", []),
            significant_places=p_data.get("significant_places", []),
            locations=locs,
        ))

    # ── Parse WHAT — story objects, dilemma, aim ────────────────────
    story_objects: List[StoryObject] = []
    for so_data in data.get("story_objects", []):
        story_objects.append(StoryObject(
            name=str(so_data.get("name", "")),
            description=so_data.get("description"),
            significance=so_data.get("significance"),
            related_persons=so_data.get("related_persons", []),
            related_locations=so_data.get("related_locations", []),
        ))

    dilemma: Optional[Dilemma] = None
    dil_data = data.get("dilemma")
    if dil_data and isinstance(dil_data, dict) and dil_data.get("description"):
        dilemma = Dilemma(
            description=str(dil_data.get("description", "")),
            options=dil_data.get("options", []),
            stakes=dil_data.get("stakes"),
            constraints=dil_data.get("constraints", []),
            desired_outcome=dil_data.get("desired_outcome"),
        )

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

    # ── Parse WHEN — setting, transits ──────────────────────────────
    setting_time = data.get("setting_time") or None

    transits: List[Transit] = []
    for tr_data in data.get("transits", []):
        transits.append(Transit(
            transiting_body=tr_data.get("transiting_body"),
            natal_body=tr_data.get("natal_body"),
            aspect_type=tr_data.get("aspect_type"),
            timeframe=tr_data.get("timeframe"),
            description=tr_data.get("description"),
        ))

    # ── Parse WHERE — locations ─────────────────────────────────────
    locations: List[Location] = []
    for loc_data in data.get("locations", []):
        conn_persons: List[Tuple[str, str]] = []
        for cp in loc_data.get("connected_persons", []):
            if isinstance(cp, dict):
                conn_persons.append((
                    str(cp.get("person", "")),
                    str(cp.get("connection", "")),
                ))
        locations.append(Location(
            name=str(loc_data.get("name", "")),
            location_type=loc_data.get("location_type"),
            connected_persons=conn_persons,
            relevance=loc_data.get("relevance"),
        ))

    # ── Parse WHY — intent context ──────────────────────────────────
    intent_context = data.get("intent_context") or None
    desired_input = data.get("desired_input") or None

    # ── Parse HOW — querent state ───────────────────────────────────
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

    # ── Parse sufficiency metadata ──────────────────────────────────
    comprehension_confidence = float(data.get("comprehension_confidence", 0.85))
    ambiguities = data.get("ambiguities", [])
    contradictions = data.get("contradictions", [])

    return QuestionGraph(
        nodes=nodes,
        edges=edges,
        question_type=q_type,
        domain=domain,
        source="llm",
        confidence=0.85,
        paraphrase=paraphrase,
        temporal_dimension=temporal,
        subject_config=subject,
        # 5W+H rich fields
        persons=persons,
        story_objects=story_objects,
        dilemma=dilemma,
        answer_aim=answer_aim,
        setting_time=setting_time,
        transits=transits,
        locations=locations,
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
    # ── Step 1: Term registry — always runs first ──────────────────
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
        )

    # ── Step 3: Term-only fallback (term matched, no API key) ────────
    if graph is None and _matched_term is not None:
        graph = QuestionGraph(
            nodes=[QuestionNode(
                label=_matched_term.canonical,
                factors=list(_matched_term.factors),
                source="term_registry",
            )],
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

    # ── Stamp intent from term registry ───────────────────────────
    if _matched_term:
        graph.question_intent = _matched_term.intent
        if _matched_term.factors and graph.nodes:
            for f in _matched_term.factors:
                if f not in graph.nodes[0].factors:
                    graph.nodes[0].factors.append(f)

    # ── Sufficiency check ─────────────────────────────────────────
    clarification = _check_sufficiency(graph)
    if clarification is not None:
        return ComprehensionResult(graph=None, clarification=clarification)

    # ── Anchor to chart (validate factors, find circuit shapes) ──────
    graph.comprehension_note = question  # temp store for _anchor_to_chart
    _anchor_to_chart(graph, chart)

    # ── Final comprehension note for the dev monologue ──────────────
    node_labels = [n.label for n in graph.nodes]
    paraphrase_fragment = f" | understood: \"{graph.paraphrase}\"" if graph.paraphrase and not graph.paraphrase.startswith("(") else ""
    temporal_fragment = f" | temporal: {graph.temporal_dimension}" if graph.temporal_dimension != "natal" else ""
    subject_fragment = f" | subject: {graph.subject_config}" if graph.subject_config != "single" else ""
    aim_fragment = f" | aim: {graph.answer_aim.aim_type.value}" if graph.answer_aim else ""
    tone_fragment = f" | tone: {graph.querent_state.emotional_tone.value}" if graph.querent_state and graph.querent_state.emotional_tone != EmotionalTone.NEUTRAL else ""
    persons_fragment = f" | persons: {[p.name or p.relationship_to_querent for p in graph.persons]}" if graph.persons else ""
    graph.comprehension_note = (
        f"Q: {question} -> {graph.question_type} | "
        f"intent: {graph.question_intent or 'none'} | "
        f"nodes: {node_labels} | "
        f"shapes: {graph.focus_circuits} | "
        f"source: {graph.source} | "
        f"conf: {graph.confidence:.0%}"
        + paraphrase_fragment
        + temporal_fragment
        + subject_fragment
        + aim_fragment
        + tone_fragment
        + persons_fragment
    )

    return ComprehensionResult(graph=graph, clarification=None)
