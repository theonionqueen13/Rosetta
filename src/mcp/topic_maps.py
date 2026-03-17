"""
topic_maps.py — Shared astrological topic maps and intent routing.

Extracted from wizard_v2.py so that both the Streamlit guided-wizard UI
**and** the MCP reading engine can consume the same curated data.

Three complementary data structures:
  1. WIZARD_TARGETS — hierarchical  (domain → subtopic → refinement → targets)
  2. KEYWORDS_LOOKUP — flat keyword  (keyword → [factors])
  3. resolve_factors() — combined intent router that returns deduplicated factors

No Streamlit dependency.  No LLM dependency.  Pure Python + regex.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

# ═══════════════════════════════════════════════════════════════════════
# Data structures returned by the routing functions
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class TopicMatch:
    """Result of intent routing."""
    domain: str = ""
    subtopic: str = ""
    refinement: str = ""
    factors: List[str] = field(default_factory=list)
    confidence: float = 0.0            # 0.0 – 1.0
    matched_keywords: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.factors


# ═══════════════════════════════════════════════════════════════════════
# 1.  WIZARD_TARGETS  (hierarchical topic map)
# ═══════════════════════════════════════════════════════════════════════

WIZARD_TARGETS: dict = {
  "schema_version": "1.0",
  "domains": [
    {
      "name": "Identity & Self",
      "description": "Who you are, how you show up, and your personal growth path",
      "subtopics": [
        {
          "label": "Self-confidence & self-expression",
          "targets": ["Sun", "Mars", "Mercury", "Venus", "Eris", "South Node", "Leo", "5th House"]
        },
        {
          "label": "Personal identity & style",
          "targets": ["Sun", "Ascendant", "1st House", "Aries"]
        },
        {
          "label": "Life direction & soul purpose",
          "refinements": {
            "General": ["Sun", "North Node", "MC", "Saturn", "Capricorn"],
            "Travel / Philosophy / Higher Learning": ["Jupiter", "Mercury", "North Node", "9th House", "Sagittarius"]
          }
        },
        {
          "label": "Overcoming self-doubt & past patterns",
          "refinements": {
            "Ancestral / Home related": ["Moon", "Chiron", "South Node", "IC", "4th House", "Cancer"],
            "Trauma healing": ["Pluto", "Chiron", "Eris", "South Node", "12th House", "Pisces", "Scorpio"],
            "Feminine warrior energy": ["Eris", "Black Moon Lilith", "Pallas"]
          }
        },
        {
          "label": "Personal turning points & destiny events",
          "refinements": {
            "Soul expression": ["Sun", "Part of Fortune", "Vertex", "North Node"],
            "Identity": ["Sun", "Ascendant", "Vertex", "1st House", "North Node"],
            "Career / Public image": ["Sun", "MC", "10th House", "Capricorn"],
            "Moments of conviction": ["Saturn", "Black Moon Lilith", "Scorpio"]
          }
        }
      ]
    },
    {
      "name": "Emotions & Inner World",
      "description": "Feelings, emotional needs, family, and your inner life",
      "subtopics": [
        {
          "label": "Emotional needs & self-care",
          "targets": ["Moon", "Ceres", "4th House", "Cancer"]
        },
        {
          "label": "Family bonds & ancestry",
          "refinements": {
            "General": ["Moon", "Ceres", "IC", "4th House", "Cancer"],
            "Generational Trauma": ["Pluto", "South Node", "IC", "4th House", "Cancer"],
            "Father Wounds": ["Saturn", "Sun", "South Node", "IC", "4th House", "Cancer"],
            "Mother Wounds": ["Moon", "Ceres", "South Node", "IC", "4th House", "Cancer"]
          }
        },
        {
          "label": "Childhood patterns & inner-child healing",
          "targets": ["Moon", "Pluto", "Psyche", "South Node", "IC", "4th House", "Cancer"],
          "refinements": {
            "Creativity and Play": ["Moon", "Uranus", "Eros", "5th House", "Leo"],
            "Childhood Wounds": ["Moon", "Pluto", "Psyche", "South Node", "IC", "4th House", "Cancer"]
          }
        },
        {
          "label": "Processing grief & loss",
          "targets": ["Pluto", "Moon", "Ceres", "South Node", "8th House", "Scorpio"]
        },
        {
          "label": "Reconnecting to your private self",
          "targets": ["Neptune", "Vesta", "Psyche", "12th House", "Pisces"]
        }
      ]
    },
    {
      "name": "Relationships & Love",
      "description": "Romance, intimacy, chemistry, and partnership",
      "subtopics": [
        {
          "label": "Attracting love & romance",
          "targets": ["Venus", "Sun", "Eros", "5th House", "Libra", "Leo"]
        },
        {
          "label": "Passion & sexual chemistry",
          "targets": ["Mars", "Pluto", "Eros", "Black Moon Lilith", "8th House", "Scorpio"]
        },
        {
          "label": "Emotional intimacy & vulnerability",
          "targets": ["Moon", "Psyche", "Ceres", "8th House", "Cancer", "Scorpio"]
        },
        {
          "label": "Long-term commitment & loyalty",
          "targets": ["Saturn", "Venus", "Juno", "7th House", "Descendant", "Capricorn", "Libra"]
        },
        {
          "label": "Navigating conflict in relationships",
          "targets": ["Mars", "Mercury", "Eris", "Pallas", "7th House", "Aries", "Libra"]
        },
        {
          "label": "Fated or karmic connections",
          "targets": ["Vertex", "North Node", "South Node", "7th House", "Libra", "Scorpio"]
        },
        {
          "label": "Co-habiting with a romantic partner",
          "targets": ["Venus", "Mercury", "Moon", "Ceres", "4th House", "IC", "Cancer", "Taurus"]
        },
        {
          "label": "Shared ventures with a partner",
          "targets": ["Venus", "Mercury", "Saturn", "Juno", "8th House", "10th House", "MC", "Libra", "Capricorn", "Taurus"]
        }
      ]
    },
    {
      "name": "Career & Public Life",
      "description": "Your work in the world, ambitions, and legacy",
      "subtopics": [
        {
          "label": "Career path & life calling",
          "targets": ["Sun", "Saturn", "North Node", "Part of Fortune", "MC", "10th House", "Capricorn"]
        },
        {
          "label": "Building success & achievement",
          "targets": ["Saturn", "Sun", "Jupiter", "MC", "10th House", "Capricorn"]
        },
        {
          "label": "Expanding opportunities",
          "targets": ["Jupiter", "MC", "10th House", "9th House", "Sagittarius"]
        },
        {
          "label": "Strategic thinking & leadership",
          "targets": ["Sun", "Saturn", "Mercury", "Pallas", "Aries", "Leo"]
        },
        {
          "label": "Public reputation & visibility",
          "targets": ["Sun", "MC", "10th House", "Capricorn", "Leo"]
        },
        {
          "label": "Work / Life Balance",
          "targets": ["Sun", "Moon", "6th House", "10th House", "MC", "Virgo", "Pisces"]
        }
      ]
    },
    {
      "name": "Finances & Resources",
      "description": "Money, material security, and managing what you have",
      "subtopics": [
        {
          "label": "Growing income & abundance",
          "targets": ["Venus", "Jupiter", "Sun", "Part of Fortune", "2nd House", "Taurus"]
        },
        {
          "label": "Managing money & resources",
          "targets": ["Saturn", "Mercury", "Vesta", "2nd House", "8th House", "Capricorn", "Taurus"]
        },
        {
          "label": "Self-worth & personal value",
          "targets": ["Venus", "Sun", "Ceres", "2nd House", "Taurus", "Leo"]
        },
        {
          "label": "Shared finances & debts",
          "targets": ["Pluto", "Saturn", "Juno", "8th House", "Scorpio", "North Node", "South Node"]
        },
        {
          "label": "Aligning money with purpose",
          "targets": ["North Node", "MC", "10th House", "Part of Fortune", "Venus", "Vesta", "Capricorn", "Taurus"]
        },
        {
          "label": "Financial independence & sovereignty",
          "targets": ["Uranus", "Eris", "Venus", "Saturn", "2nd House", "8th House", "Aquarius", "Taurus"]
        }
      ]
    },
    {
      "name": "Creativity & Expression",
      "description": "Art, play, personal projects, and creative joy",
      "subtopics": [
        {
          "label": "Expressing your unique voice",
          "targets": ["Sun", "Mercury", "Moon", "5th House", "Leo"]
        },
        {
          "label": "Artistic or creative projects",
          "targets": ["Venus", "Mercury", "Pallas", "5th House", "Leo", "Libra"]
        },
        {
          "label": "Romantic/erotic creative muse energy",
          "targets": ["Mars", "Venus", "Eros", "5th House", "Leo", "Scorpio"]
        },
        {
          "label": "Problem-solving through art & design",
          "targets": ["Mercury", "Saturn", "Pallas", "5th House", "Virgo"]
        },
        {
          "label": "Reconnecting with fun / playfulness",
          "targets": ["Sun", "Moon", "Jupiter", "5th House", "Leo"]
        },
        {
          "label": "Performance & stage presence",
          "targets": ["Sun", "Venus", "Mars", "MC", "5th House", "Leo", "Libra"]
        }
      ]
    },
    {
      "name": "Spirituality & Imagination",
      "description": "Dreams, mysticism, intuition, and higher meaning",
      "subtopics": [
        {
          "label": "Exploring spirituality & mysticism",
          "targets": ["Neptune", "Moon", "12th House", "9th House", "Pisces", "Sagittarius"]
        },
        {
          "label": "Trusting intuition",
          "targets": ["Moon", "Neptune", "Psyche", "12th House", "Pisces"]
        },
        {
          "label": "Connecting with soul purpose",
          "targets": ["North Node", "Jupiter", "MC", "Part of Fortune", "9th House", "Sagittarius", "Capricorn"]
        },
        {
          "label": "Escaping overwhelm or confusion",
          "targets": ["Neptune", "Saturn", "Vesta", "12th House", "Pisces", "Virgo"]
        },
        {
          "label": "Expanding worldview & beliefs",
          "targets": ["Jupiter", "Mercury", "Neptune", "9th House", "Sagittarius"]
        },
        {
          "label": "Dreams & symbolic imagination",
          "targets": ["Moon", "Neptune", "Psyche", "12th House", "Pisces"]
        }
      ]
    },
    {
      "name": "Change & Transformation",
      "description": "Deep inner change, power, healing, and rebirth",
      "subtopics": [
        {
          "label": "Major life changes & rebirth",
          "targets": ["Pluto", "Uranus", "South Node", "8th House", "12th House", "Scorpio", "Pisces"]
        },
        {
          "label": "Breaking free from stuck patterns",
          "targets": ["Uranus", "Eris", "Mars", "12th House", "8th House", "Aquarius", "Aries"]
        },
        {
          "label": "Shadow work & deep healing",
          "targets": ["Pluto", "Chiron", "8th House", "Scorpio", "Pisces"]
        },
        {
          "label": "Facing crises or endings",
          "targets": ["Pluto", "Saturn", "12th House", "8th House", "Scorpio", "Capricorn"]
        },
        {
          "label": "Standing in your power",
          "targets": ["Pluto", "Eris", "Mars", "8th House", "Scorpio", "Aries"]
        },
        {
          "label": "Phoenix moments / regeneration",
          "targets": ["Pluto", "Sun", "Part of Fortune", "8th House", "Scorpio"]
        }
      ]
    },
    {
      "name": "Learning & Mind",
      "description": "Thinking, communication, and curiosity",
      "subtopics": [
        {
          "label": "Improving communication",
          "targets": ["Mercury", "Pallas", "3rd House", "Gemini", "Virgo"]
        },
        {
          "label": "Learning new skills",
          "targets": ["Mercury", "Jupiter", "Pallas", "3rd House", "9th House", "Gemini", "Sagittarius"]
        },
        {
          "label": "Expanding education & travel",
          "targets": ["Jupiter", "Mercury", "Sun", "9th House", "Sagittarius", "Gemini"]
        },
        {
          "label": "Writing, teaching, or sharing ideas",
          "targets": ["Mercury", "Pallas", "3rd House", "Gemini", "Virgo"]
        },
        {
          "label": "Mental clarity & focus",
          "targets": ["Mercury", "Pallas", "Vesta", "Virgo"]
        },
        {
          "label": "Critical thinking & discernment",
          "targets": ["Mercury", "Saturn", "Pallas", "Virgo", "Aquarius"]
        }
      ]
    },
    {
      "name": "Devotion & Purposeful Service",
      "description": "Health, duty, service, caretaking, sacred focus",
      "subtopics": [
        {
          "label": "Health & wellness routines",
          "targets": ["Moon", "Ceres", "Vesta", "Saturn", "6th House", "Virgo", "Pisces"]
        },
        {
          "label": "Building discipline & structure",
          "targets": ["Saturn", "Vesta", "Pallas", "6th House", "Capricorn", "Virgo"]
        },
        {
          "label": "Acts of service & helping others",
          "targets": ["Vesta", "Ceres", "Neptune", "6th House", "Pisces"]
        },
        {
          "label": "Daily work & responsibilities",
          "targets": ["Saturn", "Mercury", "Pallas", "Vesta", "6th House", "Virgo"]
        },
        {
          "label": "Dedication to a sacred craft",
          "targets": ["Vesta", "Pallas", "6th House", "Virgo", "Capricorn"]
        },
        {
          "label": "Healing through service",
          "targets": ["Moon", "Neptune", "Ceres", "6th House", "Pisces", "Virgo"]
        },
        {
          "label": "Boundaries in service",
          "targets": ["Saturn", "Vesta", "Neptune", "6th House", "Virgo", "Pisces"]
        }
      ]
    },
    {
      "name": "Community & Future",
      "description": "Friends, social networks, collective vision",
      "subtopics": [
        {
          "label": "Building friendships & community",
          "targets": ["Uranus", "Jupiter", "Venus", "11th House", "Aquarius"]
        },
        {
          "label": "Networking & collaboration",
          "targets": ["Mercury", "Jupiter", "Pallas", "11th House", "Aquarius"]
        },
        {
          "label": "Working toward shared goals",
          "targets": ["Saturn", "Jupiter", "Pallas", "MC", "11th House", "Aquarius", "Capricorn"]
        },
        {
          "label": "Future dreams & hopes",
          "targets": ["Neptune", "Jupiter", "North Node", "Part of Fortune", "11th House", "Aquarius", "Sagittarius"]
        },
        {
          "label": "Social activism & innovation",
          "targets": ["Uranus", "Eris", "Mercury", "11th House", "Aquarius", "Aries"]
        },
        {
          "label": "Co-Parenting",
          "targets": ["Saturn", "Pluto", "Juno", "8th House", "4th House", "Cancer"]
        }
      ]
    },
    {
      "name": "Conflict & Enemies",
      "description": "Boundaries, disputes, power dynamics, protection, and resolution",
      "subtopics": [
        {
          "label": "Boundary breaches & self-protection",
          "targets": ["Mars", "Saturn", "Black Moon Lilith", "7th House", "12th House", "Aries", "Libra"]
        },
        {
          "label": "Open enemies & direct confrontations",
          "targets": ["Mars", "Eris", "Pluto", "Pallas", "7th House", "3rd House", "Aries", "Libra"]
        },
        {
          "label": "Hidden enemies, sabotage & smear",
          "targets": ["Neptune", "Pluto", "12th House", "Pisces", "Scorpio"]
        },
        {
          "label": "Power struggles, coercion & manipulation",
          "targets": ["Pluto", "Mars", "Saturn", "8th House", "Scorpio", "Capricorn"]
        },
        {
          "label": "Legal conflicts, contracts & justice",
          "targets": ["Saturn", "Juno", "9th House", "7th House", "Libra", "Sagittarius"]
        },
        {
          "label": "Workplace or team conflict",
          "targets": ["Mars", "Mercury", "Saturn", "Pallas", "6th House", "11th House", "Virgo", "Aquarius"]
        },
        {
          "label": "Public call-outs, reputation attacks",
          "targets": ["Mercury", "Eris", "MC", "10th House", "Capricorn", "Leo"]
        },
        {
          "label": "Truth-telling & dispute clarity",
          "targets": ["Mercury", "Saturn", "Eris", "Libra", "Aquarius"]
        },
        {
          "label": "De-escalation & conflict strategy",
          "targets": ["Mercury", "Venus", "Ceres", "Pallas", "Libra", "Virgo"]
        },
        {
          "label": "Ending toxic dynamics / cut-offs",
          "targets": ["Pluto", "Saturn", "Black Moon Lilith", "12th House", "Scorpio", "Capricorn"]
        },
        {
          "label": "Safety planning & red-flag detection",
          "targets": ["Mars", "Saturn", "12th House", "Scorpio", "Pisces"]
        }
      ]
    }
  ]
}


# ═══════════════════════════════════════════════════════════════════════
# 2.  KEYWORDS_LOOKUP  (flat keyword → factors)
# ═══════════════════════════════════════════════════════════════════════

KEYWORDS_LOOKUP: Dict[str, List[str]] = {
  # --- Identity ---
  "identity": ["Sun", "Ascendant", "1st House"],
  "self": ["Sun", "Ascendant", "1st House"],
  "confidence": ["Sun", "1st House", "Part of Fortune"],
  "intense": ["Pluto", "Scorpio", "8th House", "Mars"],
  "mysterious": ["Pluto", "Scorpio", "12th House", "Neptune"],
  "perception": ["Ascendant", "1st House", "Sun", "MC"],
  "quality of life": ["Sun", "Moon", "Ascendant", "Part of Fortune"],
  "self-confidence": ["Sun", "1st House", "Part of Fortune"],
  "style": ["Ascendant", "1st House", "Sun"],
  "appearance": ["Ascendant", "1st House", "Sun"],
  "purpose": ["North Node", "Sun", "MC", "1st House"],
  "life direction": ["North Node", "Sun", "MC", "1st House"],
  "calling": ["MC", "10th House", "Sun", "North Node", "Saturn"],
  "travel": ["Jupiter", "9th House", "North Node"],
  "philosophy": ["Jupiter", "9th House", "Mercury", "Neptune"],
  "higher learning": ["Jupiter", "9th House", "Mercury"],
  "destiny": ["North Node", "Vertex", "Part of Fortune", "Sun"],
  "turning point": ["Vertex", "Sun", "Part of Fortune"],
  "relocation": ["MC", "IC", "Ascendant", "4th House", "10th House"],
  "moving": ["MC", "IC", "4th House", "Moon"],

  # --- Emotions / Family ---
  "family": ["Moon", "IC", "4th House", "Ceres", "Mnemosyne"],
  "ancestry": ["Moon", "IC", "4th House", "Ceres", "Mnemosyne"],
  "generational trauma": ["IC", "4th House", "Mnemosyne", "Nessus", "South Node"],
  "father wound": ["Saturn", "IC", "4th House", "Mnemosyne", "Nessus", "South Node"],
  "mother wound": ["Moon", "Ceres", "IC", "4th House", "Nessus", "South Node"],
  "home": ["IC", "4th House", "Moon", "Ceres"],
  "childhood": ["Moon", "Chiron", "4th House", "Psyche"],
  "inner child": ["Moon", "Chiron", "4th House", "Psyche"],
  "play": ["Sun", "5th House", "Thalia", "Euterpe", "Bacchus"],
  "grief": ["Ceres", "8th House", "Pluto", "Niobe", "South Node"],
  "loss": ["Ceres", "8th House", "Pluto", "Niobe", "South Node"],
  "self-care": ["Moon", "Ceres", "4th House", "Hygiea"],
  "parent": ["Moon", "Saturn", "IC", "4th House", "Ceres"],

  # --- Love / Relationships ---
  "love": ["Venus", "5th House", "Sun", "Eros"],
  "romance": ["Venus", "5th House", "Sun", "Eros", "Freia"],
  "dating": ["Venus", "5th House", "Sun", "Eros"],
  "attraction": ["Venus", "Mars", "Eros", "5th House"],
  "attracting": ["Venus", "Mars", "Eros", "5th House", "7th House"],
  "emotionally unavailable": ["Venus", "Moon", "7th House", "Chiron"],
  "partner": ["7th House", "Descendant", "Juno", "Venus"],
  "spouse": ["7th House", "Descendant", "Juno", "Saturn"],
  "synastry": ["7th House", "Descendant", "Venus", "Mars"],
  "love language": ["Venus", "Mars", "Moon", "5th House"],
  "long-term potential": ["Saturn", "Juno", "7th House", "Venus"],
  "relationship": ["7th House", "Descendant", "Venus", "Juno"],
  "sex": ["Mars", "Eros", "Lilith (Asteroid)", "Black Moon Lilith", "8th House", "Pluto"],
  "chemistry": ["Mars", "Eros", "Lilith (Asteroid)", "Black Moon Lilith", "8th House"],
  "intimacy": ["Psyche", "Moon", "8th House", "Ceres"],
  "trust": ["Psyche", "Moon", "8th House", "Eurydike", "Ceres"],
  "commitment": ["Juno", "Saturn", "7th House", "Venus", "Descendant"],
  "marriage": ["Juno", "Saturn", "7th House", "Venus", "Descendant"],
  "partnership": ["7th House", "Descendant", "Juno", "Venus", "Saturn"],
  "breakup": ["Pluto", "Saturn", "7th House", "West", "Orcus"],
  "karmic relationship": ["Vertex", "South Node", "7th House", "North Node"],

  # --- Career ---
  "career": ["MC", "10th House", "Sun", "Saturn", "North Node"],
  "job": ["MC", "10th House", "Saturn", "Mercury"],
  "vocation": ["MC", "10th House", "Sun", "North Node", "Saturn"],
  "promotion": ["Saturn", "Sun", "MC", "Jupiter", "10th House"],
  "leadership": ["Pallas", "Mercury", "Saturn", "Sun"],
  "midheaven": ["MC", "10th House"],
  "business": ["MC", "10th House", "Jupiter", "Saturn"],
  "job offer": ["MC", "10th House", "Saturn", "Mercury"],
  "professional": ["MC", "10th House", "Saturn", "Sun"],
  "stagnation": ["Saturn", "MC", "10th House"],
  "stagnant": ["Saturn", "MC", "10th House"],
  "work environment": ["6th House", "MC", "10th House", "Moon"],
  "reputation": ["Sun", "MC", "10th House", "Fama", "Apollo"],
  "public image": ["Sun", "MC", "10th House", "Fama", "Apollo"],
  "opportunity": ["Jupiter", "9th House", "10th House", "MC"],

  # --- Finances ---
  "money": ["Jupiter", "Venus", "2nd House", "Part of Fortune"],
  "finances": ["Jupiter", "Venus", "2nd House", "Part of Fortune"],
  "expenses": ["2nd House", "Saturn", "Jupiter", "Venus"],
  "purchase": ["2nd House", "Venus", "Jupiter", "Saturn"],
  "wealth": ["Jupiter", "Venus", "2nd House", "8th House", "Part of Fortune"],
  "income": ["Jupiter", "Venus", "2nd House", "Part of Fortune"],
  "salary": ["Jupiter", "Venus", "2nd House"],
  "savings": ["Saturn", "Vesta", "2nd House"],
  "budget": ["Saturn", "Vesta", "2nd House"],
  "debt": ["8th House", "Saturn", "Pluto", "Juno"],
  "taxes": ["8th House", "Saturn", "Pluto"],
  "inheritance": ["8th House", "Pluto", "Saturn"],
  "self-worth": ["Venus", "2nd House", "Sun", "Ceres"],
  "right livelihood": ["North Node", "MC", "Vesta", "10th House", "Part of Fortune", "Venus"],
  "purpose & money": ["North Node", "MC", "Vesta", "10th House", "Part of Fortune", "Venus"],

  # --- Creativity ---
  "creativity": ["Sun", "5th House", "Venus", "Pallas", "Hephaistos"],
  "art": ["Venus", "Mercury", "5th House", "Pallas", "Hephaistos"],
  "music": ["Euterpe", "Singer", "5th House", "Sun", "Mercury"],
  "voice": ["Singer", "Mercury", "Polyhymnia", "Sun", "5th House"],
  "muse": ["Eros", "5th House", "Venus", "Mars", "Magdalena"],
  "design": ["Pallas", "Minerva", "Arachne", "Mercury", "5th House"],
  "fun": ["Sun", "5th House", "Thalia", "Bacchus", "Euterpe"],

  # --- Spirituality ---
  "spirituality": ["Neptune", "12th House", "Moon", "Hekate", "9th House"],
  "spiritual": ["Neptune", "12th House", "Jupiter", "9th House"],
  "north node": ["North Node", "South Node", "12th House"],
  "intuition": ["Moon", "Psyche", "Neptune", "12th House", "Kassandra"],
  "dreams": ["Neptune", "12th House", "Moon"],
  "meditation": ["Neptune", "12th House", "Vesta", "Moon"],
  "confusion": ["Neptune", "12th House", "Saturn", "Hygiea", "Vesta"],
  "overwhelm": ["Neptune", "12th House", "Saturn", "Hygiea", "Vesta"],
  "beliefs": ["Jupiter", "9th House", "Mercury", "Neptune"],

  # --- Transformation ---
  "saturn return": ["Saturn", "1st House", "10th House"],
  "falling apart": ["Pluto", "Saturn", "8th House", "12th House"],
  "major shift": ["Pluto", "Uranus", "Saturn", "8th House"],
  "transits": ["Saturn", "Pluto", "Uranus", "Jupiter", "8th House"],
  "challenging": ["Saturn", "Pluto", "Mars", "8th House"],
  "patterns": ["Pluto", "Saturn", "South Node", "12th House"],
  "waiting room": ["Saturn", "Neptune", "12th House"],
  "energy shift": ["Pluto", "Uranus", "Saturn", "8th House"],
  "trauma": ["Pluto", "Chiron", "8th House", "Nessus", "Aletheia"],
  "healing": ["Chiron", "Pluto", "8th House", "Panacea", "Vesta"],
  "shadow work": ["Pluto", "Chiron", "8th House", "Nessus", "Aletheia"],
  "rebirth": ["Pluto", "8th House", "Uranus", "South Node", "12th House"],
  "endings": ["Pluto", "West", "Saturn", "12th House", "8th House"],
  "empowerment": ["Pluto", "Eris", "8th House", "Mars", "Orcus"],
  "strength": ["Sun", "Mars", "Pluto", "1st House"],
  "strengths": ["Sun", "Mars", "Pluto", "1st House"],
  "breakthrough": ["Uranus", "Pluto", "8th House", "12th House"],

  # --- Learning ---
  "learning": ["Mercury", "Jupiter", "3rd House", "9th House", "Pallas"],
  "study": ["Mercury", "3rd House", "Pallas", "Jupiter"],
  "education": ["Jupiter", "9th House", "Mercury"],
  "travel (long-distance)": ["Jupiter", "9th House", "Sun"],
  "communication": ["Mercury", "3rd House", "Pallas", "Echo", "Veritas"],
  "writing": ["Mercury", "3rd House", "Pallas", "Fama", "Apollo"],
  "teaching": ["Mercury", "Jupiter", "3rd House", "9th House"],
  "focus": ["Mercury", "Pallas", "Vesta", "Hygiea"],

  # --- Health / Service ---
  "health": ["6th House", "Ceres", "Moon", "Hygiea", "Vesta", "Saturn"],
  "wellness": ["6th House", "Ceres", "Moon", "Hygiea", "Vesta"],
  "anxiety": ["Moon", "Mercury", "Saturn", "Neptune", "6th House"],
  "anxious": ["Moon", "Mercury", "Saturn", "Neptune", "6th House"],
  "exhausted": ["Moon", "Neptune", "12th House", "6th House"],
  "exhaustion": ["Moon", "Neptune", "12th House", "6th House"],
  "routines": ["6th House", "Saturn", "Vesta", "Lachesis"],
  "habits": ["6th House", "Saturn", "Vesta", "Lachesis"],
  "service": ["Vesta", "Ceres", "6th House", "Neptune", "Panacea"],
  "work": ["6th House", "Saturn", "Mercury", "Pallas", "Vesta"],
  "craft": ["Vesta", "Pallas", "Minerva", "Hephaistos", "6th House", "Arachne"],
  "burnout": ["Saturn", "12th House", "Neptune", "Hygiea", "6th House"],

  # --- Community ---
  "community": ["11th House", "Uranus", "Jupiter", "Venus"],
  "friends": ["11th House", "Venus", "Jupiter", "Uranus"],
  "networking": ["11th House", "Jupiter", "Pallas", "Koussevitzky", "Fama"],
  "collaboration": ["11th House", "Jupiter", "Pallas", "Koussevitzky", "Fama"],
  "future": ["11th House", "Neptune", "North Node", "Part of Fortune", "Jupiter"],
  "my people": ["11th House", "Venus", "Jupiter", "Uranus"],
  "goals": ["11th House", "Saturn", "Jupiter", "Pallas", "MC"],
  "activism": ["Uranus", "Eris", "11th House", "Mercury", "Kassandra", "Nemesis"],
  "co-parenting": ["8th House", "Saturn", "Pluto", "Juno"],

  # --- Conflict ---
  "boundaries": ["Mars", "Black Moon Lilith", "Lilith (Asteroid)", "Saturn", "7th House", "12th House"],
  "conflict": ["Mars", "Eris", "7th House", "Pallas", "3rd House", "Pluto"],
  "enemies": ["Mars", "Eris", "7th House", "12th House", "Pluto"],
  "open enemies": ["Mars", "Eris", "7th House", "Pallas", "3rd House", "Pluto"],
  "hidden enemies": ["12th House", "Neptune", "Pluto", "Nemesis", "Fama", "Kassandra"],
  "sabotage": ["12th House", "Neptune", "Nemesis", "Pluto", "Fama"],
  "smear": ["12th House", "Neptune", "Fama", "Nemesis", "Pluto"],
  "power struggle": ["Pluto", "8th House", "Mars", "Nessus", "Saturn", "Orcus"],
  "coercion": ["Pluto", "8th House", "Nessus", "Saturn", "Mars"],
  "manipulation": ["Pluto", "8th House", "Nessus", "Saturn", "Mars"],
  "legal": ["Juno", "Saturn", "Varuna", "9th House", "7th House", "Orcus"],
  "lawsuit": ["Juno", "Saturn", "Varuna", "9th House", "7th House", "Orcus"],
  "contracts": ["Juno", "Saturn", "Varuna", "7th House", "Orcus"],
  "workplace conflict": ["6th House", "11th House", "Mars", "Pallas", "Mercury", "Saturn"],
  "reputation attack": ["10th House", "MC", "Fama", "Mercury", "Eris", "Nemesis"],
  "truth": ["Aletheia", "Veritas", "Mercury", "Saturn", "3rd House", "9th House"],
  "clarity": ["Aletheia", "Veritas", "Mercury", "Saturn", "3rd House", "9th House"],
  "de-escalation": ["Pallas", "Minerva", "Mercury", "Venus", "3rd House", "7th House"],
  "cut-off": ["Pluto", "West", "Saturn", "Orcus", "Black Moon Lilith", "12th House"],
  "safety": ["Kassandra", "Nessus", "Medusa", "Saturn", "12th House", "Mars"],
}


# ═══════════════════════════════════════════════════════════════════════
# 2b. KEYWORD_DOMAIN_HINTS  (keyword → domain name)
#     Bridges KEYWORDS_LOOKUP entries to the correct WIZARD_TARGETS domain.
#     Used by resolve_factors() when subtopic_match fails.
# ═══════════════════════════════════════════════════════════════════════

KEYWORD_DOMAIN_HINTS: Dict[str, str] = {
    # --- Identity & Self ---
    "identity": "Identity & Self",
    "self": "Identity & Self",
    "confidence": "Identity & Self",
    "intense": "Identity & Self",
    "mysterious": "Identity & Self",
    "perception": "Identity & Self",
    "quality of life": "Identity & Self",
    "self-confidence": "Identity & Self",
    "style": "Identity & Self",
    "appearance": "Identity & Self",
    "purpose": "Identity & Self",
    "life direction": "Identity & Self",
    "calling": "Identity & Self",
    "travel": "Identity & Self",
    "philosophy": "Identity & Self",
    "higher learning": "Identity & Self",
    "destiny": "Identity & Self",
    "turning point": "Identity & Self",
    "relocation": "Identity & Self",
    "moving": "Identity & Self",

    # --- Emotions & Inner World ---
    "family": "Emotions & Inner World",
    "ancestry": "Emotions & Inner World",
    "generational trauma": "Emotions & Inner World",
    "father wound": "Emotions & Inner World",
    "mother wound": "Emotions & Inner World",
    "home": "Emotions & Inner World",
    "childhood": "Emotions & Inner World",
    "inner child": "Emotions & Inner World",
    "play": "Emotions & Inner World",
    "grief": "Emotions & Inner World",
    "loss": "Emotions & Inner World",
    "self-care": "Emotions & Inner World",
    "parent": "Emotions & Inner World",

    # --- Relationships & Love ---
    "love": "Relationships & Love",
    "romance": "Relationships & Love",
    "dating": "Relationships & Love",
    "attraction": "Relationships & Love",
    "attracting": "Relationships & Love",
    "emotionally unavailable": "Relationships & Love",
    "partner": "Relationships & Love",
    "spouse": "Relationships & Love",
    "synastry": "Relationships & Love",
    "love language": "Relationships & Love",
    "long-term potential": "Relationships & Love",
    # Note: "relationship" deliberately omitted — too ambiguous (romantic / familial / financial).
    "sex": "Relationships & Love",
    "chemistry": "Relationships & Love",
    "intimacy": "Relationships & Love",
    "trust": "Relationships & Love",
    "commitment": "Relationships & Love",
    "marriage": "Relationships & Love",
    "partnership": "Relationships & Love",
    "breakup": "Relationships & Love",
    "karmic relationship": "Relationships & Love",

    # --- Career & Public Life ---
    "career": "Career & Public Life",
    "job": "Career & Public Life",
    "vocation": "Career & Public Life",
    "promotion": "Career & Public Life",
    "leadership": "Career & Public Life",
    "midheaven": "Career & Public Life",
    "business": "Career & Public Life",
    "job offer": "Career & Public Life",
    "professional": "Career & Public Life",
    "stagnation": "Career & Public Life",
    "stagnant": "Career & Public Life",
    "work environment": "Career & Public Life",
    "reputation": "Career & Public Life",
    "public image": "Career & Public Life",
    "opportunity": "Career & Public Life",

    # --- Finances & Resources ---
    "money": "Finances & Resources",
    "finances": "Finances & Resources",
    "expenses": "Finances & Resources",
    "purchase": "Finances & Resources",
    "wealth": "Finances & Resources",
    "income": "Finances & Resources",
    "salary": "Finances & Resources",
    "savings": "Finances & Resources",
    "budget": "Finances & Resources",
    "debt": "Finances & Resources",
    "taxes": "Finances & Resources",
    "inheritance": "Finances & Resources",
    "self-worth": "Finances & Resources",
    "right livelihood": "Finances & Resources",
    "purpose & money": "Finances & Resources",

    # --- Creativity & Expression ---
    "creativity": "Creativity & Expression",
    "art": "Creativity & Expression",
    "music": "Creativity & Expression",
    "voice": "Creativity & Expression",
    "muse": "Creativity & Expression",
    "design": "Creativity & Expression",
    "fun": "Creativity & Expression",

    # --- Spirituality & Imagination ---
    "spirituality": "Spirituality & Imagination",
    "spiritual": "Spirituality & Imagination",
    "north node": "Spirituality & Imagination",
    "intuition": "Spirituality & Imagination",
    "dreams": "Spirituality & Imagination",
    "meditation": "Spirituality & Imagination",
    "confusion": "Spirituality & Imagination",
    "overwhelm": "Spirituality & Imagination",
    "beliefs": "Spirituality & Imagination",

    # --- Change & Transformation ---
    "saturn return": "Change & Transformation",
    "falling apart": "Change & Transformation",
    "major shift": "Change & Transformation",
    "transits": "Change & Transformation",
    "challenging": "Change & Transformation",
    "patterns": "Change & Transformation",
    "waiting room": "Change & Transformation",
    "energy shift": "Change & Transformation",
    "trauma": "Change & Transformation",
    "healing": "Change & Transformation",
    "shadow work": "Change & Transformation",
    "rebirth": "Change & Transformation",
    "endings": "Change & Transformation",
    "empowerment": "Change & Transformation",
    "strength": "Change & Transformation",
    "strengths": "Change & Transformation",
    "breakthrough": "Change & Transformation",

    # --- Learning & Mind ---
    "learning": "Learning & Mind",
    "study": "Learning & Mind",
    "education": "Learning & Mind",
    "travel (long-distance)": "Learning & Mind",
    "communication": "Learning & Mind",
    "writing": "Learning & Mind",
    "teaching": "Learning & Mind",
    "focus": "Learning & Mind",

    # --- Devotion & Purposeful Service ---
    "health": "Devotion & Purposeful Service",
    "wellness": "Devotion & Purposeful Service",
    "anxiety": "Devotion & Purposeful Service",
    "anxious": "Devotion & Purposeful Service",
    "exhausted": "Devotion & Purposeful Service",
    "exhaustion": "Devotion & Purposeful Service",
    "routines": "Devotion & Purposeful Service",
    "habits": "Devotion & Purposeful Service",
    "service": "Devotion & Purposeful Service",
    "work": "Devotion & Purposeful Service",
    "craft": "Devotion & Purposeful Service",
    "burnout": "Devotion & Purposeful Service",

    # --- Community & Future ---
    "community": "Community & Future",
    "friends": "Community & Future",
    "networking": "Community & Future",
    "collaboration": "Community & Future",
    "future": "Community & Future",
    "my people": "Community & Future",
    "goals": "Community & Future",
    "activism": "Community & Future",
    "co-parenting": "Community & Future",

    # --- Conflict & Enemies ---
    "boundaries": "Conflict & Enemies",
    "conflict": "Conflict & Enemies",
    "enemies": "Conflict & Enemies",
    "open enemies": "Conflict & Enemies",
    "hidden enemies": "Conflict & Enemies",
    "sabotage": "Conflict & Enemies",
    "smear": "Conflict & Enemies",
    "power struggle": "Conflict & Enemies",
    "coercion": "Conflict & Enemies",
    "manipulation": "Conflict & Enemies",
    "legal": "Conflict & Enemies",
    "lawsuit": "Conflict & Enemies",
    "contracts": "Conflict & Enemies",
    "workplace conflict": "Conflict & Enemies",
    "reputation attack": "Conflict & Enemies",
    "truth": "Conflict & Enemies",
    "clarity": "Conflict & Enemies",
    "de-escalation": "Conflict & Enemies",
    "cut-off": "Conflict & Enemies",
    "safety": "Conflict & Enemies",
}


# ═══════════════════════════════════════════════════════════════════════
# 3.  Derived index — built once at import time
# ═══════════════════════════════════════════════════════════════════════

# Pre-compiled patterns for multi-word keywords (longest first so "shadow work"
# matches before "work").
_KEYWORD_PATTERNS: List[Tuple[re.Pattern, str]] = sorted(
    [(re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE), kw)
     for kw in KEYWORDS_LOOKUP],
    key=lambda pair: -len(pair[1]),
)

# Subtopic label → (domain_name, subtopic_dict) for fast subtopic matching.
_SUBTOPIC_INDEX: Dict[str, Tuple[str, dict]] = {}
for _dom in WIZARD_TARGETS["domains"]:
    for _sub in _dom["subtopics"]:
        _SUBTOPIC_INDEX[_sub["label"].lower()] = (_dom["name"], _sub)

# Domain description words → domain name (lightweight fuzzy matching)
# Stopwords that appear in domain descriptions but carry no domain signal.
_DOMAIN_STOP_WORDS: set = {
    "what", "your", "have", "does", "about", "from", "with", "this",
    "that", "they", "them", "their", "been", "will", "were", "more",
    "some", "into", "show", "managing", "life", "needs", "thinking",
}
_DOMAIN_KEYWORDS: Dict[str, str] = {}
for _dom in WIZARD_TARGETS["domains"]:
    for w in re.findall(r"\w+", (_dom["name"] + " " + _dom.get("description", "")).lower()):
        if len(w) > 3 and w not in _DOMAIN_STOP_WORDS:
            _DOMAIN_KEYWORDS[w] = _dom["name"]


# ═══════════════════════════════════════════════════════════════════════
# 4.  Routing functions
# ═══════════════════════════════════════════════════════════════════════

def keyword_match(text: str) -> Tuple[List[str], List[str]]:
    """Return (matched_factors, matched_keywords) from KEYWORDS_LOOKUP.

    Scans *text* for every keyword in the flat lookup and collects the
    associated factor lists.  Multi-word keywords are matched first.
    """
    matched_kws: List[str] = []
    factors: List[str] = []
    for pat, kw in _KEYWORD_PATTERNS:
        if pat.search(text):
            matched_kws.append(kw)
            factors.extend(KEYWORDS_LOOKUP[kw])
    return _dedup(factors), matched_kws


def subtopic_match(text: str) -> Optional[Tuple[str, str, List[str]]]:
    """Try to match against subtopic labels.

    Returns (domain_name, subtopic_label, targets) or None.
    """
    text_lower = text.lower()
    best: Optional[Tuple[str, str, List[str]]] = None
    best_score = 0.0
    for label, (domain_name, sub_dict) in _SUBTOPIC_INDEX.items():
        score = _fuzzy_overlap(text_lower, label)
        if score > best_score:
            best_score = score
            targets = sub_dict.get("targets", [])
            # If subtopic has refinements but no top-level targets, collect all refinement targets
            if not targets and sub_dict.get("refinements"):
                targets = []
                for ref_targets in sub_dict["refinements"].values():
                    targets.extend(ref_targets)
            best = (domain_name, sub_dict["label"], _dedup(targets))
    if best and best_score >= 0.4:
        return best
    return None


def domain_match(text: str) -> Optional[str]:
    """Return the best matching domain name, or None."""
    text_lower = text.lower()
    words = set(re.findall(r"\w+", text_lower))
    scores: Dict[str, int] = {}
    for w in words:
        dom = _DOMAIN_KEYWORDS.get(w)
        if dom:
            scores[dom] = scores.get(dom, 0) + 1
    if scores:
        return max(scores, key=scores.get)
    return None


def resolve_factors(question: str) -> TopicMatch:
    """Full intent routing: question -> TopicMatch.

    Strategy (layered, from most specific to broadest):
      1. Exact keyword hits from KEYWORDS_LOOKUP  (factors + kws)
      2. Subtopic label fuzzy match from WIZARD_TARGETS  (domain + subtopic)
      3. Keyword-domain hints from KEYWORD_DOMAIN_HINTS  (domain from kw signal)
      4. Domain-level keyword match from domain names/descriptions
      5. Fallback: return the "big 3" (Sun, Moon, Ascendant) with low confidence.
    """
    factors: List[str] = []
    matched_kws: List[str] = []
    domain = ""
    subtopic = ""
    refinement = ""
    confidence = 0.0

    # Layer 1: flat keyword scan
    kw_factors, kw_hits = keyword_match(question)
    if kw_factors:
        factors.extend(kw_factors)
        matched_kws.extend(kw_hits)
        confidence = min(0.5 + 0.1 * len(kw_hits), 0.85)

    # Layer 2: subtopic match (most specific domain signal)
    sub_result = subtopic_match(question)
    if sub_result:
        domain, subtopic, sub_factors = sub_result
        factors.extend(sub_factors)
        confidence = max(confidence, 0.7)

    # Layer 3: keyword → domain hints (explicit curated mapping)
    if not domain and matched_kws:
        _votes: Dict[str, int] = {}
        for kw in matched_kws:
            hint = KEYWORD_DOMAIN_HINTS.get(kw)
            if hint:
                _votes[hint] = _votes.get(hint, 0) + 1
        if _votes:
            domain = max(_votes, key=_votes.get)
            confidence = max(confidence, 0.55)

    # Layer 4: domain name / description word match
    if not domain:
        domain = domain_match(question) or ""
        if domain and not factors:
            # Pull all factors from that domain's first subtopic as a fallback
            for dom_obj in WIZARD_TARGETS["domains"]:
                if dom_obj["name"] == domain:
                    first_sub = dom_obj["subtopics"][0] if dom_obj["subtopics"] else {}
                    factors.extend(first_sub.get("targets", []))
                    subtopic = first_sub.get("label", "")
                    confidence = max(confidence, 0.4)
                    break

    # Layer 5: absolute fallback -- the "big 3"
    if not factors:
        factors = ["Sun", "Moon", "Ascendant"]
        confidence = 0.15
        domain = "General"
        subtopic = "Core placements"

    return TopicMatch(
        domain=domain,
        subtopic=subtopic,
        refinement=refinement,
        factors=_dedup(factors),
        confidence=confidence,
        matched_keywords=matched_kws,
    )


def all_factors_for_domain(domain_name: str) -> List[str]:
    """Collect every unique factor mentioned in a domain's subtopics."""
    for dom in WIZARD_TARGETS["domains"]:
        if dom["name"] == domain_name:
            out: List[str] = []
            for sub in dom["subtopics"]:
                out.extend(sub.get("targets", []))
                for ref_targets in (sub.get("refinements") or {}).values():
                    out.extend(ref_targets)
            return _dedup(out)
    return []


def list_domains() -> List[Dict[str, str]]:
    """Return [{name, description}, …] for every domain."""
    return [
        {"name": d["name"], "description": d.get("description", "")}
        for d in WIZARD_TARGETS["domains"]
    ]


def list_subtopics(domain_name: str) -> List[str]:
    """Return subtopic labels for a given domain."""
    for dom in WIZARD_TARGETS["domains"]:
        if dom["name"] == domain_name:
            return [s["label"] for s in dom["subtopics"]]
    return []


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _dedup(seq: Sequence[str]) -> List[str]:
    """De-duplicate while preserving order."""
    seen: set = set()
    out: List[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


_FUZZY_STOP: set = {
    "a", "an", "the", "to", "of", "in", "on", "or", "and", "is", "it",
    "at", "by", "for", "do", "if", "am", "no", "up", "so", "my", "me",
    "we", "he", "be", "i",
}


def _fuzzy_overlap(text: str, label: str) -> float:
    """Word-overlap ratio between *text* and *label*, ignoring stopwords."""
    label_words = set(re.findall(r"\w+", label.lower())) - _FUZZY_STOP
    text_words = set(re.findall(r"\w+", text.lower())) - _FUZZY_STOP
    if not label_words:
        return 0.0
    return len(label_words & text_words) / len(label_words)
