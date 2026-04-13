"""
term_registry.py — Canonical Astrological Terms Vocabulary
===========================================================
Defines the managed vocabulary of astrological *terms* — natural-language
concepts that the comprehension layer needs to recognise and route to the
correct reading-engine intent.

A **Term** maps:
  canonical  →  the primary English phrase ("influential planet")
  aliases    →  regex patterns that match rephrasings of the same concept
  factors    →  optional list of astrological factor names (planets / signs
                / houses) associated with this term; may be empty when the
                intent itself drives factor selection
  intent     →  routing key consumed by reading_engine (e.g. "potency_ranking")
  domain     →  loose life-domain grouping; used for agent-notes and debugging
  description→  one-sentence explanation for developers / LLM context

Resolution order
----------------
  1. ``load_terms()`` tries to fetch rows from the ``astrological_terms``
     Postgres table via ``db_access.get_terms()``.
  2. Falls back to ``_BUILTIN_TERMS`` when the DB is unavailable.

Public API
----------
  load_terms(db_conn=None) → List[Term]
  match_terms(question, terms) → Optional[Term]
  assign_potency_tiers(states) → Dict[str, str]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from src.core.dignity_calc import PlanetaryState


# ═══════════════════════════════════════════════════════════════════════
# Intent constants
# ═══════════════════════════════════════════════════════════════════════

class TermIntent:
    """String constants for question_intent values."""
    POTENCY_RANKING       = "potency_ranking"
    RELATIONSHIP_READING  = "relationship_reading"
    TIMING_FORECAST       = "timing_forecast"
    CAREER_PATH           = "career_path"
    CYCLE_GUIDANCE        = "cycle_guidance"
    SPIRITUAL_PURPOSE     = "spiritual_purpose"
    EMOTIONAL_WELLNESS    = "emotional_wellness"
    CHALLENGE_TRANSMUTE   = "challenge_transmutation"
    LIFE_AREA_PRIORITY    = "life_area_priority"
    FAMILY_DYNAMICS       = "family_dynamics"
    RELOCATION            = "relocation"
    COMMUNITY_BELONGING   = "community_belonging"
    FINANCIAL_INSIGHT     = "financial_insight"
    TRAIT_PERCEPTION      = "trait_perception"


# ═══════════════════════════════════════════════════════════════════════
# Term dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Term:
    """One canonical astrological term with its recognition patterns."""
    canonical: str
    aliases: List[str] = field(default_factory=list)   # regex patterns
    factors: List[str] = field(default_factory=list)   # astrological factors (may be empty)
    intent: str = ""                                   # routing key for reading_engine
    domain: str = ""
    description: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Built-in seed data  (potency / influence / strength cluster)
# ═══════════════════════════════════════════════════════════════════════

_BUILTIN_TERMS: List[Term] = [

    # ── "influential planet" and close synonyms ───────────────────────
    Term(
        canonical="influential planet",
        aliases=[
            r"most influential planet",
            r"most influential",
            r"which planet.*most influence",
            r"what.*most influential",
            r"planet.*most influence",
            r"influential planet",
            r"what is.*influential",
            r"most significant planet",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description=(
            "Asks which planet(s) have the greatest overall potency in the chart "
            "per the power index (essential + accidental dignity combined)."
        ),
    ),

    # ── strength / power / dominance ─────────────────────────────────
    Term(
        canonical="strongest planet",
        aliases=[
            r"strongest planet",
            r"most powerful planet",
            r"most potent planet",
            r"dominant planet",
            r"dominant energy",
            r"most dominant",
            r"which planet is strongest",
            r"what.*strongest planet",
            r"planet.*greatest power",
            r"most forceful planet",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description="Asks for the planet with the highest combined power index in the chart.",
    ),

    # ── weakness / low activity ───────────────────────────────────────
    Term(
        canonical="weakest planet",
        aliases=[
            r"weakest planet",
            r"least powerful planet",
            r"least active planet",
            r"least prominent planet",
            r"least influential",
            r"which planet.*weakest",
            r"most inactive planet",
            r"planet.*lowest power",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description="Asks for the planet with the lowest power index in the chart.",
    ),

    # ── essential dignity ─────────────────────────────────────────────
    Term(
        canonical="most dignified planet",
        aliases=[
            r"most dignified",
            r"best dignified",
            r"highest dignity",
            r"greatest dignity",
            r"planet.*most dignified",
            r"which planet.*dignified",
            r"best placed.*dignity",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description=(
            "Asks which planet has the best essential dignity (domicile, exaltation, "
            "triplicity, term, face) in the chart."
        ),
    ),

    # ── affliction / debility ─────────────────────────────────────────
    Term(
        canonical="afflicted planet",
        aliases=[
            r"afflicted planet",
            r"most afflicted",
            r"debilitated planet",
            r"fallen planet",
            r"planet.*in detriment",
            r"planet.*in fall",
            r"which planet.*afflicted",
            r"most debilitated",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description=(
            "Asks about planets with negative dignity (detriment / fall) or poor "
            "accidental dignity (combust, cadent, retrograde)."
        ),
    ),

    # ── general prominence / visibility ──────────────────────────────
    Term(
        canonical="prominent planet",
        aliases=[
            r"prominent planet",
            r"most prominent",
            r"which planet stands out",
            r"planet.*stands out",
            r"well.placed planet",
            r"best placed planet",
            r"planet.*prominent",
            r"angular planet",
            r"which planet.*angular",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description=(
            "Asks for planets that are especially active or visible in the chart — "
            "typically those on angles or with high accidental dignity."
        ),
    ),

    # ── generic planetary power / potency ────────────────────────────
    Term(
        canonical="planet power",
        aliases=[
            r"planet.*power",
            r"power.*planet",
            r"potency of.*planet",
            r"planetary potency",
            r"planetary power",
            r"planetary strength",
            r"strength.*planet",
            r"which planet.*strong",
            r"overall.*planet.*strength",
            r"chart.*power",
        ],
        factors=[],
        intent=TermIntent.POTENCY_RANKING,
        domain="Identity & Self",
        description=(
            "General inquiry about the relative power or strength of planets in "
            "the chart; routed to the full potency-ranking calculation."
        ),
    ),

    # ══════════════════════════════════════════════════════════════════
    # Relationship Reading cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="emotionally unavailable",
        aliases=[r"emotionally unavailable", r"emotionally distant",
                 r"avoidant attachment", r"unavailable partner"],
        factors=[],
        intent=TermIntent.RELATIONSHIP_READING,
        domain="Relationships & Love",
        description="Describes a person who avoids emotional intimacy.",
    ),
    Term(
        canonical="attract",
        aliases=[r"keep attracting", r"always attract", r"draw in",
                 r"why do i attract"],
        factors=[],
        intent=TermIntent.RELATIONSHIP_READING,
        domain="Relationships & Love",
        description="Recurring pattern of attracting a particular type of person.",
    ),
    Term(
        canonical="love language",
        aliases=[r"love language", r"love languages", r"how.*express love",
                 r"how.*show love"],
        factors=["Venus", "Mars"],
        intent=TermIntent.RELATIONSHIP_READING,
        domain="Relationships & Love",
        description="How a person gives and receives affection, mapped to Venus/Mars.",
    ),
    Term(
        canonical="Venus placement",
        aliases=[r"venus placement", r"my venus", r"venus sign",
                 r"venus in"],
        factors=["Venus"],
        intent=TermIntent.RELATIONSHIP_READING,
        domain="Relationships & Love",
        description="Sign and house position of Venus in the birth chart.",
    ),
    Term(
        canonical="Mars placement",
        aliases=[r"mars placement", r"my mars", r"mars sign",
                 r"mars in"],
        factors=["Mars"],
        intent=TermIntent.RELATIONSHIP_READING,
        domain="Relationships & Love",
        description="Sign and house position of Mars in the birth chart.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Career Path cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="hidden professional strengths",
        aliases=[r"hidden.*strengths", r"untapped.*strengths",
                 r"underutiliz.*strengths", r"professional strengths"],
        factors=["MC", "10th House", "Saturn", "Sun"],
        intent=TermIntent.CAREER_PATH,
        domain="Career & Public Life",
        description="Skills and talents not currently being fully used in career.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Spiritual Purpose cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="spiritual lesson",
        aliases=[r"spiritual lesson", r"life lesson", r"soul lesson",
                 r"meant to learn", r"purpose.*this lifetime"],
        factors=["North Node", "South Node", "12th House"],
        intent=TermIntent.SPIRITUAL_PURPOSE,
        domain="Spirituality & Imagination",
        description="Key theme or challenge for spiritual growth in this lifetime.",
    ),
    Term(
        canonical="North Node",
        aliases=[r"north node", r"north node of the moon", r"true node",
                 r"my north node", r"significance.*north node",
                 r"north node.*significance"],
        factors=["North Node"],
        intent=TermIntent.SPIRITUAL_PURPOSE,
        domain="Spirituality & Imagination",
        description="The karmic direction or soul purpose indicator in the chart.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Emotional Wellness cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="anxiety",
        aliases=[r"anxiety", r"anxious", r"worries", r"unease",
                 r"apprehension", r"manage.*anxiety"],
        factors=["Moon", "Mercury", "Saturn", "Neptune"],
        intent=TermIntent.EMOTIONAL_WELLNESS,
        domain="Emotions & Inner World",
        description="State of worry or nervousness; mapped to lunar/mercurial factors.",
    ),
    Term(
        canonical="planetary influences",
        aliases=[r"planetary influences", r"planetary effects",
                 r"astrological influences", r"astrological effects"],
        factors=[],
        intent=TermIntent.EMOTIONAL_WELLNESS,
        domain="Emotions & Inner World",
        description="General impact of planets on a person's life and experiences.",
    ),
    Term(
        canonical="social exhaustion",
        aliases=[r"exhausted after social", r"drained after social",
                 r"social.*exhaust", r"tired after.*gathering",
                 r"social energy"],
        factors=["Moon", "Neptune", "12th House"],
        intent=TermIntent.EMOTIONAL_WELLNESS,
        domain="Emotions & Inner World",
        description="Feeling depleted after social interactions.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Timing Forecast cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="waiting room phase",
        aliases=[r"waiting room.*phase", r"waiting room.*period",
                 r"phase of waiting", r"in a waiting room",
                 r"life.*on pause"],
        factors=[],
        intent=TermIntent.TIMING_FORECAST,
        domain="Change & Transformation",
        description="Period of stagnation or lack of progress in life.",
    ),
    Term(
        canonical="energy shift",
        aliases=[r"energy shift", r"shift in energy", r"energy change",
                 r"when.*energy.*shift", r"when.*shift"],
        factors=[],
        intent=TermIntent.TIMING_FORECAST,
        domain="Change & Transformation",
        description="An anticipated change in circumstances or momentum.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Challenge Transmutation cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="challenging aspect",
        aliases=[r"challenging aspect", r"difficult aspect",
                 r"hard aspect", r"affliction", r"most challenging"],
        factors=[],
        intent=TermIntent.CHALLENGE_TRANSMUTE,
        domain="Identity & Self",
        description="An aspect in a birth chart that presents obstacles.",
    ),
    Term(
        canonical="transmute",
        aliases=[r"transmut", r"transform.*strength",
                 r"turn.*into.*strength", r"convert.*strength"],
        factors=[],
        intent=TermIntent.CHALLENGE_TRANSMUTE,
        domain="Change & Transformation",
        description="Turning difficult chart patterns into constructive energy.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Community Belonging cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="my people",
        aliases=[r"my people", r"my community", r"my tribe",
                 r"find.*community", r"find.*my people"],
        factors=["11th House", "Uranus", "Jupiter", "Venus"],
        intent=TermIntent.COMMUNITY_BELONGING,
        domain="Community & Future",
        description="Finding a sense of belonging or community.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Financial Insight cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="financial volatility",
        aliases=[r"financial.*volatil", r"financial.*instabil",
                 r"unexpected expenses", r"unstable finances"],
        factors=["2nd House", "8th House", "Jupiter", "Saturn"],
        intent=TermIntent.FINANCIAL_INSIGHT,
        domain="Finances & Resources",
        description="Trend of financial instability or surprising expenses.",
    ),
    Term(
        canonical="subconscious blocks",
        aliases=[r"subconscious block", r"mental block",
                 r"limiting belief", r"block.*wealth",
                 r"block.*money", r"block.*abundance"],
        factors=["12th House", "Neptune", "Pluto", "Saturn"],
        intent=TermIntent.FINANCIAL_INSIGHT,
        domain="Finances & Resources",
        description="Hidden psychological barriers to financial growth.",
    ),
    Term(
        canonical="relationship with money",
        aliases=[r"relationship with money", r"attitude.*money",
                 r"money mindset", r"money.*relationship"],
        factors=["Venus", "2nd House", "Jupiter"],
        intent=TermIntent.FINANCIAL_INSIGHT,
        domain="Finances & Resources",
        description="Core beliefs and patterns around earning and spending.",
    ),
    Term(
        canonical="building wealth",
        aliases=[r"building wealth", r"accumulating wealth",
                 r"creating wealth", r"grow.*wealth",
                 r"financial independence"],
        factors=["Jupiter", "Venus", "2nd House", "8th House"],
        intent=TermIntent.FINANCIAL_INSIGHT,
        domain="Finances & Resources",
        description="Long-term wealth creation and financial growth.",
    ),

    # ══════════════════════════════════════════════════════════════════
    # Trait Perception cluster
    # ══════════════════════════════════════════════════════════════════
    Term(
        canonical="intense",
        aliases=[r"described as intense", r"people.*say.*intense",
                 r"come across as intense", r"seen as intense"],
        factors=["Pluto", "Scorpio", "8th House", "Mars"],
        intent=TermIntent.TRAIT_PERCEPTION,
        domain="Identity & Self",
        description="Being perceived as emotionally or energetically intense.",
    ),
    Term(
        canonical="mysterious",
        aliases=[r"described as mysterious", r"people.*say.*mysterious",
                 r"come across as mysterious", r"seen as mysterious"],
        factors=["Pluto", "Scorpio", "12th House", "Neptune"],
        intent=TermIntent.TRAIT_PERCEPTION,
        domain="Identity & Self",
        description="Being perceived as enigmatic or hard to read.",
    ),

# ── END BUILTIN TERMS ────────────────────────────────────────────────────────
]


# ═══════════════════════════════════════════════════════════════════════
# Term loading
# ═══════════════════════════════════════════════════════════════════════

def load_terms(db_conn=None) -> List[Term]:
    """Return all known terms; DB-backed when available, built-in otherwise.

    Parameters
    ----------
    db_conn :
        Unused; present for future signature compatibility when callers
        want to pass an explicit connection.  Currently, the function
        opens its own connection via ``db_access.get_terms()``.
    """
    try:
        from src.db.db_access import get_terms as _db_get_terms  # lazy import
        rows = _db_get_terms()
        if rows:
            result: List[Term] = []
            for r in rows:
                result.append(Term(
                    canonical=r.get("canonical", ""),
                    aliases=r.get("aliases") or [],
                    factors=r.get("factors") or [],
                    intent=r.get("intent", ""),
                    domain=r.get("domain", ""),
                    description=r.get("description", ""),
                ))
            return result
    except Exception:
        pass
    return list(_BUILTIN_TERMS)


# ═══════════════════════════════════════════════════════════════════════
# Term matching
# ═══════════════════════════════════════════════════════════════════════

def match_terms(question: str, terms: List[Term]) -> Optional[Term]:
    """Return the first Term whose canonical or alias patterns match *question*.

    Matching is case-insensitive.  Each alias is treated as a regex;
    invalid patterns fall back to substring containment.

    Returns None if no term matches.
    """
    q = question.lower().strip()
    for term in terms:
        # Try canonical name as a substring first (cheap)
        if term.canonical.lower() in q:
            return term
        # Try each alias pattern
        for alias in term.aliases:
            try:
                if re.search(alias.lower(), q):
                    return term
            except re.error:
                # Malformed regex — fall back to substring
                if alias.lower() in q:
                    return term
    return None


# ═══════════════════════════════════════════════════════════════════════
# Relative potency tier assignment
# ═══════════════════════════════════════════════════════════════════════

# Five tiers, top to bottom.  Proportional bands are computed from the
# chart's own distribution (not a fixed absolute scale).
_TIER_LABELS = [
    "profoundly active",   # top ~20 %
    "highly active",       # next ~20 %
    "actively placed",     # middle ~20 %
    "moderately active",   # next ~20 %
    "quietly present",     # bottom ~20 %
]

_SOLAR_PROXIMITY_OVERRIDES: Dict[str, str] = {
    "Cazimi": "supremely activated (Cazimi — at the heart of the Sun)",
    "Combust": "overshadowed (Combust — too close to the Sun to shine freely)",
}


def assign_potency_tiers(states: Dict[str, "PlanetaryState"]) -> Dict[str, str]:
    """Rank all planets by power_index and assign relative tier labels.

    Labels are determined purely by rank within *this* chart — the same
    raw power index would earn a different label in a different chart.
    This prevents any implication that the numbers are meaningful on an
    absolute scale.

    Special solar-proximity overrides:
    • Cazimi (within 0°17' of Sun) → always top override label
    • Combust (within ~8° of Sun)  → always debility override label

    Parameters
    ----------
    states : Dict[str, PlanetaryState]
        Output from ``dignity_calc.score_chart()`` or
        ``dignity_calc.score_and_attach()``.

    Returns
    -------
    Dict[str, str]
        Mapping of planet name → descriptive tier label string.
        Raw power index values are deliberately NOT included.
    """
    if not states:
        return {}

    # Identify solar-proximity special cases first
    override_map: Dict[str, str] = {}
    for name, ps in states.items():
        prox_label = getattr(ps, "solar_proximity_label", "") or ""
        if prox_label in _SOLAR_PROXIMITY_OVERRIDES:
            override_map[name] = _SOLAR_PROXIMITY_OVERRIDES[prox_label]

    # Sort by power_index descending to determine relative rank
    scored = sorted(
        [(name, getattr(ps, "power_index", 0.0)) for name, ps in states.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    n = len(scored)
    result: Dict[str, str] = {}
    for i, (name, _) in enumerate(scored):
        if name in override_map:
            result[name] = override_map[name]
            continue
        # Map rank → tier index (quintile bands, capped at last tier)
        tier_index = min(int(i * len(_TIER_LABELS) / n), len(_TIER_LABELS) - 1)
        result[name] = _TIER_LABELS[tier_index]

    return result
