"""
comprehension.py — Question Decomposition Layer
================================================
Decomposes a natural-language question into a structured QuestionGraph
that maps concepts to astrological factors and relationships between them.

Two resolution paths
--------------------
  1. **LLM path** (preferred when API key available):
     One cheap, fast structured-output LLM call with a JSON-schema
     constraint.  The LLM can ONLY select from a validated vocabulary
     of astrological factors present in the chart — it cannot hallucinate.

  2. **Keyword path** (fallback when no API key):
     Uses ``topic_maps.resolve_factors()`` for keyword extraction +
     heuristic relationship detection from question text.

After either path, ``_anchor_to_chart()`` validates every factor against
the live chart and maps them to shape_ids in the circuit simulation.

Public API
----------
  comprehend(question, chart, api_key=None) → QuestionGraph
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
    """Structured representation of a decomposed question."""
    # Decomposition
    nodes: List[QuestionNode] = field(default_factory=list)
    edges: List[QuestionEdge] = field(default_factory=list)
    question_type: str = "single_focus"  # "single_focus" | "relationship" | "multi_node" | "open_exploration"

    # Post-anchoring (filled by _anchor_to_chart)
    focus_circuits: List[int] = field(default_factory=list)   # shape_ids containing relevant factors
    all_factors: List[str] = field(default_factory=list)       # deduplicated union of all node factors
    anchored: bool = False                                     # True once _anchor_to_chart has run

    # Metadata
    domain: str = ""
    subtopic: str = ""
    confidence: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)
    source: str = "keyword"             # "keyword" or "llm"
    comprehension_note: str = ""        # one-line log for agent notes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_type": self.question_type,
            "nodes": [{"label": n.label, "factors": n.factors, "source": n.source} for n in self.nodes],
            "edges": [{"a": e.node_a, "b": e.node_b, "rel": e.relationship} for e in self.edges],
            "focus_circuits": self.focus_circuits,
            "all_factors": self.all_factors,
            "domain": self.domain,
            "subtopic": self.subtopic,
            "confidence": self.confidence,
            "source": self.source,
        }


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
    )


# ═══════════════════════════════════════════════════════════════════════
# LLM-based comprehension (structured output)
# ═══════════════════════════════════════════════════════════════════════

_COMPREHENSION_SYSTEM = """\
You decompose astrological questions into structured concept nodes.

RULES:
1. Each concept the user mentions becomes a node with a short label.
2. Each node's "factors" must ONLY contain items from the VALID_FACTORS list.
3. NEVER invent factor names — if unsure, leave factors empty.
4. Detect the relationship between nodes: "connection", "tension", "support", or "timing".
5. question_type is one of: "single_focus", "relationship", "multi_node", "open_exploration".
6. Keep labels short (1-3 words, lowercase).
7. If the question is vague or general, use question_type "open_exploration" with zero nodes.

Respond with ONLY valid JSON matching this schema:
{
  "question_type": "string",
  "nodes": [{"label": "string", "factors": ["string"]}],
  "edges": [{"node_a": "string", "node_b": "string", "relationship": "string"}]
}
"""


def _comprehend_llm(
    question: str,
    chart: "AstrologicalChart",
    api_key: str,
    model: str = "google/gemini-2.0-flash-001",
) -> Optional[QuestionGraph]:
    """
    Use a cheap structured LLM call to decompose the question.

    Returns None on any failure (caller should fall back to keyword path).
    """
    try:
        import openai
    except ImportError:
        return None

    vocab = _build_vocabulary(chart)
    user_msg = (
        f"VALID_FACTORS:\n{json.dumps(vocab)}\n\n"
        f"Question: {question}"
    )

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
            max_tokens=300,
        )
        raw = response.choices[0].message.content or ""
    except Exception:
        return None

    # Parse JSON from the response (strip markdown fences if present)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None

    # Validate against vocabulary
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

    return QuestionGraph(
        nodes=nodes,
        edges=edges,
        question_type=q_type,
        source="llm",
        confidence=0.85,  # LLM decomposition assumed higher base confidence
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

    # If LLM path produced no factors at all, enrich from topic_maps
    if not graph.all_factors and graph.source == "llm":
        kw_graph = _comprehend_keyword(graph.comprehension_note or "general reading")
        for node in kw_graph.nodes:
            graph.nodes.append(node)
        graph.all_factors = sorted(set(f for n in graph.nodes for f in n.factors))

    graph.anchored = True


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def comprehend(
    question: str,
    chart: "AstrologicalChart",
    *,
    api_key: Optional[str] = None,
    llm_model: str = "google/gemini-2.0-flash-001",
) -> QuestionGraph:
    """
    Decompose *question* into a ``QuestionGraph`` anchored to *chart*.

    Uses the LLM path if ``api_key`` is provided, falling back to
    keyword matching.  Always validates against the chart.

    Parameters
    ----------
    question : str
        User's free-text question.
    chart : AstrologicalChart
        A fully computed chart with circuit_simulation populated.
    api_key : str, optional
        OpenRouter API key.  If None, uses keyword fallback only.
    llm_model : str
        Model to use for the comprehension call.
    """
    graph: Optional[QuestionGraph] = None

    # Try LLM path first if key available
    if api_key:
        graph = _comprehend_llm(question, chart, api_key, model=llm_model)

    # Fall back to keyword path
    if graph is None:
        graph = _comprehend_keyword(question)

    # Store original question for agent notes
    graph.comprehension_note = question

    # Anchor to the chart (validate factors, find circuits)
    _anchor_to_chart(graph, chart)

    # Generate agent notes line
    node_labels = [n.label for n in graph.nodes]
    graph.comprehension_note = (
        f"Q: {question} → {graph.question_type} | "
        f"nodes: {node_labels} | "
        f"shapes: {graph.focus_circuits} | "
        f"source: {graph.source} | "
        f"conf: {graph.confidence:.0%}"
    )

    return graph
