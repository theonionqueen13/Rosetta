import streamlit as st
from rosetta.lookup import ALIASES_MEANINGS
# -------------------------
# Guided Question Wizard — data + helpers
# -------------------------

# Normalization helpers: map labels/aliases to whatever the DF actually uses
_REV_ALIASES = {v: k for k, v in ALIASES_MEANINGS.items()}

def _canon_label(name: str) -> str:
    """Prefer the display name your app uses; fall back to alias if needed."""
    if not name:
        return ""
    name = str(name).strip()
    # Pass-through if it's already the display form present on the chart
    return ALIASES_MEANINGS.get(name, name)

def _objects_in_chart(df) -> set:
    return set(df["Object"].astype(str))

def _resolve_present_targets(df, targets: list[str]) -> tuple[list[str], list[str]]:
    """
    Return (present, missing) after normalizing aliases (e.g., 'MC' -> 'Midheaven').
    We keep a max of 6 already by curation, but also dedupe.
    """
    pool = _objects_in_chart(df)
    present, missing = [], []
    for t in targets:
        disp = _canon_label(t)
        if disp in pool:
            present.append(disp)
        else:
            # If display not there, try alias->display->alias flips
            alias = _REV_ALIASES.get(disp, None)
            if alias and alias in pool:
                present.append(alias)
            else:
                missing.append(t)
    # de-dupe while preserving order
    seen = set()
    present = [x for x in present if not (x in seen or seen.add(x))]
    return present, missing

def apply_wizard_targets(df, targets: list[str]):
    """
    Flip the per-object 'singleton_' checkboxes and set focus to the first present target.
    Also ensures the Compass Rose overlay is on for orientation.
    """
    present, missing = _resolve_present_targets(df, targets)
    # Turn on compass by default for beginners
    st.session_state["toggle_compass_rose"] = True

    # Flip singletons (only for those actually in this chart)
    for obj in present:
        st.session_state[f"singleton_{obj}"] = True

    # Set sidebar "Focus a Placement" to the first target if available
    if present:
        st.session_state["focus_select"] = present[0]
        st.session_state["selected_placement"] = present[0]

    # Hand a small status back to the caller
    return present, missing

# Light MVP: a handful of first-tier categories with subtopics,
# each resolving to up to 6 relevant placements/houses.
# (You can extend this dict anytime — same shape.)

WIZARD_TARGETS = {
  "schema_version": "1.0",
  "domains": [
    {
      "name": "Identity & Self",
      "description": "Who you are, how you show up, and your personal growth path",
      "subtopics": [
        {
          "label": "Self-confidence & self-expression",
          "targets": ["Sun", "1st House", "Part of Fortune"]
        },
        {
          "label": "Personal identity & style",
          "targets": ["Ascendant", "1st House", "Sun"]
        },
        {
          "label": "Life direction & soul purpose",
          "refinements": {
            "General": ["North Node", "Sun", "1st House", "MC"],
            "Travel / Philosophy / Higher Learning": ["Jupiter", "9th House", "North Node"]
          }
        },
        {
          "label": "Overcoming self-doubt & past patterns",
          "refinements": {
            "Ancestral / Home related": ["Chiron", "South Node", "IC", "4th House", "Nessus"],
            "Trauma healing": ["Chiron", "Pluto", "Eris", "South Node", "12th House"],
            "Feminine warrior energy": ["Eris", "Sedna", "Black Moon Lilith", "Pallas", "Minerva"]
          }
        },
        {
          "label": "Personal turning points & destiny events",
          "refinements": {
            "Soul expression": ["Vertex", "Sun", "Part of Fortune"],
            "Identity": ["Vertex", "Ascendant", "Sun", "1st House"],
            "Career / Public image": ["MC", "10th House", "Sun"],
            "Moments of conviction": ["Black Moon Lilith", "Saturn"]
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
          "targets": ["Moon", "Ceres", "4th House", "Hygiea"]
        },
        {
          "label": "Family bonds & ancestry",
          "refinements": {
            "General": ["Moon", "IC", "4th House", "Ceres", "Mnemosyne"],
            "Generational Trauma": ["IC", "4th House", "Mnemosyne", "Nessus", "South Node"],
            "Father Wounds": ["Saturn", "IC", "4th House", "Mnemosyne", "Nessus", "South Node"],
            "Mother Wounds": ["Moon", "Ceres", "IC", "4th House", "Nessus", "South Node"]
          }
        },
        {
          "label": "Childhood patterns & inner-child healing",
          "targets": ["Moon", "Chiron", "4th House", "Psyche"],
          "refinements": {
            "Creativity and Play": ["Moon", "Eros", "Uranus", "Zephyr", "Thalia", "5th House"],
            "Childhood Wounds": ["Moon", "Chiron", "4th House", "Psyche", "Nessus", "IC"]
          }
        },
        {
          "label": "Processing grief & loss",
          "targets": ["Ceres", "8th House", "Pluto", "Niobe", "South Node"]
        },
        {
          "label": "Reconnecting to your private self",
          "targets": ["12th House", "Psyche", "Neptune", "Vesta"]
        }
      ]
    },
    {
      "name": "Relationships & Love",
      "description": "Romance, intimacy, chemistry, and partnership",
      "subtopics": [
        {
          "label": "Attracting love & romance",
          "targets": ["Venus", "5th House", "Sun", "Eros", "Freia"]
        },
        {
          "label": "Passion & sexual chemistry",
          "targets": ["Mars", "Eros", "Lilith (Asteroid)", "Black Moon Lilith", "8th House", "Pluto"]
        },
        {
          "label": "Emotional intimacy & vulnerability",
          "targets": ["Psyche", "Moon", "8th House", "Ceres"]
        },
        {
          "label": "Long-term commitment & loyalty",
          "targets": ["Juno", "Saturn", "7th House", "Venus", "Descendant"]
        },
        {
          "label": "Navigating conflict in relationships",
          "targets": ["Mars", "Eris", "7th House", "Pallas", "Mercury"]
        },
        {
          "label": "Fated or karmic connections",
          "targets": ["Vertex", "South Node", "7th House", "North Node"]
        }
      ]
    },
    {
      "name": "Career & Public Life",
      "description": "Your work in the world, ambitions, and legacy",
      "subtopics": [
        {
          "label": "Career path & life calling",
          "targets": ["MC", "10th House", "Sun", "North Node", "Part of Fortune", "Saturn"]
        },
        {
          "label": "Building success & achievement",
          "targets": ["Saturn", "Sun", "10th House", "MC", "Jupiter"]
        },
        {
          "label": "Expanding opportunities",
          "targets": ["Jupiter", "9th House", "10th House", "MC"]
        },
        {
          "label": "Strategic thinking & leadership",
          "targets": ["Pallas", "Mercury", "Saturn", "Sun"]
        },
        {
          "label": "Public reputation & visibility",
          "targets": ["Sun", "MC", "10th House", "Fama", "Apollo"]
        }
      ]
    },
    {
      "name": "Finances & Resources",
      "description": "Money, material security, and managing what you have",
      "subtopics": [
        {
          "label": "Growing income & abundance",
          "targets": ["Jupiter", "Venus", "2nd House", "Part of Fortune"]
        },
        {
          "label": "Managing money & resources",
          "targets": ["Saturn", "Vesta", "2nd House", "8th House"]
        },
        {
          "label": "Self-worth & personal value",
          "targets": ["Venus", "2nd House", "Sun", "Ceres"]
        },
        {
          "label": "Shared finances & debts",
          "targets": ["8th House", "Saturn", "Pluto", "Juno"]
        },
        {
          "label": "Aligning money with purpose",
          "targets": ["North Node", "MC", "Vesta", "10th House", "Part of Fortune", "Venus"]
        }
      ]
    },
    {
      "name": "Creativity & Expression",
      "description": "Art, play, personal projects, and creative joy",
      "subtopics": [
        {
          "label": "Expressing your unique voice",
          "targets": ["Sun", "5th House", "Mercury", "Singer", "Polyhymnia"]
        },
        {
          "label": "Artistic or creative projects",
          "targets": ["Venus", "Mercury", "5th House", "Pallas", "Hephaistos"]
        },
        {
          "label": "Romantic/erotic creative muse energy",
          "targets": ["Eros", "5th House", "Venus", "Mars", "Magdalena"]
        },
        {
          "label": "Problem-solving through art & design",
          "targets": ["Pallas", "Mercury", "Minerva", "Arachne", "5th House"]
        },
        {
          "label": "Reconnecting with fun / playfulness",
          "targets": ["Sun", "5th House", "Thalia", "Euterpe", "Bacchus"]
        }
      ]
    },
    {
      "name": "Spirituality & Imagination",
      "description": "Dreams, mysticism, intuition, and higher meaning",
      "subtopics": [
        {
          "label": "Exploring spirituality & mysticism",
          "targets": ["Neptune", "12th House", "Moon", "Hekate", "9th House"]
        },
        {
          "label": "Trusting intuition",
          "targets": ["Moon", "Psyche", "Neptune", "12th House", "Kassandra"]
        },
        {
          "label": "Connecting with soul purpose",
          "targets": ["North Node", "9th House", "MC", "Part of Fortune", "Jupiter"]
        },
        {
          "label": "Escaping overwhelm or confusion",
          "targets": ["Neptune", "12th House", "Saturn", "Hygiea", "Vesta"]
        },
        {
          "label": "Expanding worldview & beliefs",
          "targets": ["Jupiter", "9th House", "Mercury", "Neptune"]
        }
      ]
    },
    {
      "name": "Change & Transformation",
      "description": "Deep inner change, power, healing, and rebirth",
      "subtopics": [
        {
          "label": "Major life changes & rebirth",
          "targets": ["Pluto", "8th House", "Uranus", "South Node", "12th House"]
        },
        {
          "label": "Breaking free from stuck patterns",
          "targets": ["Uranus", "12th House", "Eris", "Mars", "8th House"]
        },
        {
          "label": "Shadow work & deep healing",
          "targets": ["Pluto", "Chiron", "8th House", "Nessus", "Aletheia"]
        },
        {
          "label": "Facing crises or endings",
          "targets": ["Pluto", "12th House", "Saturn", "8th House", "West"]
        },
        {
          "label": "Standing in your power",
          "targets": ["Pluto", "Eris", "8th House", "Mars", "Orcus"]
        }
      ]
    },
    {
      "name": "Learning & Mind",
      "description": "Thinking, communication, and curiosity",
      "subtopics": [
        {
          "label": "Improving communication",
          "targets": ["Mercury", "3rd House", "Pallas", "Echo", "Veritas"]
        },
        {
          "label": "Learning new skills",
          "targets": ["Mercury", "Jupiter", "3rd House", "9th House", "Pallas"]
        },
        {
          "label": "Expanding education & travel",
          "targets": ["Jupiter", "9th House", "Mercury", "Sun"]
        },
        {
          "label": "Writing, teaching, or sharing ideas",
          "targets": ["Mercury", "3rd House", "Pallas", "Fama", "Apollo"]
        },
        {
          "label": "Mental clarity & focus",
          "targets": ["Mercury", "Pallas", "Vesta", "Hygiea"]
        }
      ]
    },
    {
      "name": "Devotion & Purposeful Service",
      "description": "Health, duty, service, caretaking, sacred focus",
      "subtopics": [
        {
          "label": "Health & wellness routines",
          "targets": ["6th House", "Ceres", "Moon", "Hygiea", "Vesta", "Saturn"]
        },
        {
          "label": "Building discipline & structure",
          "targets": ["Saturn", "6th House", "Vesta", "Pallas", "Lachesis"]
        },
        {
          "label": "Acts of service & helping others",
          "targets": ["Vesta", "Ceres", "6th House", "Neptune", "Panacea"]
        },
        {
          "label": "Daily work & responsibilities",
          "targets": ["6th House", "Saturn", "Mercury", "Pallas", "Hephaistos", "Vesta"]
        },
        {
          "label": "Dedication to a sacred craft",
          "targets": ["Vesta", "Pallas", "Minerva", "Hephaistos", "6th House", "Arachne"]
        }
      ]
    },
    {
      "name": "Community & Future",
      "description": "Friends, social networks, collective vision",
      "subtopics": [
        {
          "label": "Building friendships & community",
          "targets": ["11th House", "Uranus", "Jupiter", "Venus"]
        },
        {
          "label": "Networking & collaboration",
          "targets": ["11th House", "Jupiter", "Pallas", "Koussevitzky", "Fama"]
        },
        {
          "label": "Working toward shared goals",
          "targets": ["11th House", "Saturn", "Jupiter", "Pallas", "MC"]
        },
        {
          "label": "Future dreams & hopes",
          "targets": ["11th House", "Neptune", "North Node", "Part of Fortune", "Jupiter"]
        },
        {
          "label": "Social activism & innovation",
          "targets": ["Uranus", "Eris", "11th House", "Mercury", "Kassandra", "Nemesis"]
        },
        {
          "label": "Co-Parenting",
          "targets": ["8th House", "Saturn", "Pluto", "Juno"]
        }
      ]
    },
    {
      "name": "Conflict & Enemies",
      "description": "Boundaries, disputes, power dynamics, protection, and resolution",
      "subtopics": [
        {
          "label": "Boundary breaches & self-protection",
          "targets": ["Mars", "Black Moon Lilith", "Lilith (Asteroid)", "Saturn", "7th House", "12th House"]
        },
        {
          "label": "Open enemies & direct confrontations",
          "targets": ["Mars", "Eris", "7th House", "Pallas", "3rd House", "Pluto"]
        },
        {
          "label": "Hidden enemies, sabotage & smear",
          "targets": ["12th House", "Neptune", "Pluto", "Nemesis", "Fama", "Kassandra"]
        },
        {
          "label": "Power struggles, coercion & manipulation",
          "targets": ["Pluto", "8th House", "Mars", "Nessus", "Saturn", "Orcus"]
        },
        {
          "label": "Legal conflicts, contracts & justice",
          "targets": ["Juno", "Saturn", "Varuna", "9th House", "7th House", "Orcus"]
        },
        {
          "label": "Workplace or team conflict",
          "targets": ["6th House", "11th House", "Mars", "Pallas", "Mercury", "Saturn"]
        },
        {
          "label": "Public call-outs, reputation attacks",
          "targets": ["10th House", "MC", "Fama", "Mercury", "Eris", "Nemesis"]
        },
        {
          "label": "Truth-telling & dispute clarity",
          "targets": ["Aletheia", "Veritas", "Mercury", "Saturn", "3rd House", "9th House"]
        },
        {
          "label": "De-escalation & conflict strategy",
          "targets": ["Pallas", "Minerva", "Mercury", "Venus", "3rd House", "7th House"]
        },
        {
          "label": "Ending toxic dynamics / cut-offs",
          "targets": ["Pluto", "West", "Saturn", "Orcus", "Black Moon Lilith", "12th House"]
        },
        {
          "label": "Safety planning & red-flag detection",
          "targets": ["Kassandra", "Nessus", "Medusa", "Saturn", "12th House", "Mars"]
        }
      ]
    }
  ]
}

KEYWORDS_LOOKUP = {
  "identity": ["Sun", "Ascendant", "1st House"],
  "self": ["Sun", "Ascendant", "1st House"],
  "confidence": ["Sun", "1st House", "Part of Fortune"],
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

  "love": ["Venus", "5th House", "Sun", "Eros"],
  "romance": ["Venus", "5th House", "Sun", "Eros", "Freia"],
  "dating": ["Venus", "5th House", "Sun", "Eros"],
  "attraction": ["Venus", "Mars", "Eros", "5th House"],
  "sex": ["Mars", "Eros", "Lilith (Asteroid)", "Black Moon Lilith", "8th House", "Pluto"],
  "chemistry": ["Mars", "Eros", "Lilith (Asteroid)", "Black Moon Lilith", "8th House"],
  "intimacy": ["Psyche", "Moon", "8th House", "Ceres"],
  "trust": ["Psyche", "Moon", "8th House", "Eurydike", "Ceres"],
  "commitment": ["Juno", "Saturn", "7th House", "Venus", "Descendant"],
  "marriage": ["Juno", "Saturn", "7th House", "Venus", "Descendant"],
  "partnership": ["7th House", "Descendant", "Juno", "Venus", "Saturn"],
  "breakup": ["Pluto", "Saturn", "7th House", "West", "Orcus"],
  "karmic relationship": ["Vertex", "South Node", "7th House", "North Node"],

  "career": ["MC", "10th House", "Sun", "Saturn", "North Node"],
  "job": ["MC", "10th House", "Saturn", "Mercury"],
  "vocation": ["MC", "10th House", "Sun", "North Node", "Saturn"],
  "promotion": ["Saturn", "Sun", "MC", "Jupiter", "10th House"],
  "leadership": ["Pallas", "Mercury", "Saturn", "Sun"],
  "reputation": ["Sun", "MC", "10th House", "Fama", "Apollo"],
  "public image": ["Sun", "MC", "10th House", "Fama", "Apollo"],
  "opportunity": ["Jupiter", "9th House", "10th House", "MC"],

  "money": ["Jupiter", "Venus", "2nd House", "Part of Fortune"],
  "finances": ["Jupiter", "Venus", "2nd House", "Part of Fortune"],
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

  "creativity": ["Sun", "5th House", "Venus", "Pallas", "Hephaistos"],
  "art": ["Venus", "Mercury", "5th House", "Pallas", "Hephaistos"],
  "music": ["Euterpe", "Singer", "5th House", "Sun", "Mercury"],
  "voice": ["Singer", "Mercury", "Polyhymnia", "Sun", "5th House"],
  "muse": ["Eros", "5th House", "Venus", "Mars", "Magdalena"],
  "design": ["Pallas", "Minerva", "Arachne", "Mercury", "5th House"],
  "fun": ["Sun", "5th House", "Thalia", "Bacchus", "Euterpe"],

  "spirituality": ["Neptune", "12th House", "Moon", "Hekate", "9th House"],
  "intuition": ["Moon", "Psyche", "Neptune", "12th House", "Kassandra"],
  "dreams": ["Neptune", "12th House", "Moon"],
  "meditation": ["Neptune", "12th House", "Vesta", "Moon"],
  "confusion": ["Neptune", "12th House", "Saturn", "Hygiea", "Vesta"],
  "overwhelm": ["Neptune", "12th House", "Saturn", "Hygiea", "Vesta"],
  "beliefs": ["Jupiter", "9th House", "Mercury", "Neptune"],

  "trauma": ["Pluto", "Chiron", "8th House", "Nessus", "Aletheia"],
  "healing": ["Chiron", "Pluto", "8th House", "Panacea", "Vesta"],
  "shadow work": ["Pluto", "Chiron", "8th House", "Nessus", "Aletheia"],
  "rebirth": ["Pluto", "8th House", "Uranus", "South Node", "12th House"],
  "endings": ["Pluto", "West", "Saturn", "12th House", "8th House"],
  "empowerment": ["Pluto", "Eris", "8th House", "Mars", "Orcus"],
  "breakthrough": ["Uranus", "Pluto", "8th House", "12th House"],

  "learning": ["Mercury", "Jupiter", "3rd House", "9th House", "Pallas"],
  "study": ["Mercury", "3rd House", "Pallas", "Jupiter"],
  "education": ["Jupiter", "9th House", "Mercury"],
  "travel (long-distance)": ["Jupiter", "9th House", "Sun"],
  "communication": ["Mercury", "3rd House", "Pallas", "Echo", "Veritas"],
  "writing": ["Mercury", "3rd House", "Pallas", "Fama", "Apollo"],
  "teaching": ["Mercury", "Jupiter", "3rd House", "9th House"],
  "focus": ["Mercury", "Pallas", "Vesta", "Hygiea"],

  "health": ["6th House", "Ceres", "Moon", "Hygiea", "Vesta", "Saturn"],
  "wellness": ["6th House", "Ceres", "Moon", "Hygiea", "Vesta"],
  "routines": ["6th House", "Saturn", "Vesta", "Lachesis"],
  "habits": ["6th House", "Saturn", "Vesta", "Lachesis"],
  "service": ["Vesta", "Ceres", "6th House", "Neptune", "Panacea"],
  "work": ["6th House", "Saturn", "Mercury", "Pallas", "Vesta"],
  "craft": ["Vesta", "Pallas", "Minerva", "Hephaistos", "6th House", "Arachne"],
  "burnout": ["Saturn", "12th House", "Neptune", "Hygiea", "6th House"],

  "community": ["11th House", "Uranus", "Jupiter", "Venus"],
  "friends": ["11th House", "Venus", "Jupiter", "Uranus"],
  "networking": ["11th House", "Jupiter", "Pallas", "Koussevitzky", "Fama"],
  "collaboration": ["11th House", "Jupiter", "Pallas", "Koussevitzky", "Fama"],
  "future": ["11th House", "Neptune", "North Node", "Part of Fortune", "Jupiter"],
  "goals": ["11th House", "Saturn", "Jupiter", "Pallas", "MC"],
  "activism": ["Uranus", "Eris", "11th House", "Mercury", "Kassandra", "Nemesis"],
  "co-parenting": ["8th House", "Saturn", "Pluto", "Juno"],

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
  "safety": ["Kassandra", "Nessus", "Medusa", "Saturn", "12th House", "Mars"]
}
