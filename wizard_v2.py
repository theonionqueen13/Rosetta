
from typing import List, Tuple

import streamlit as st
from lookup_v2 import ALIASES_MEANINGS, GLYPHS, OBJECT_MEANINGS_SHORT, SIGN_MEANINGS, HOUSE_MEANINGS
# ------------------------
# Guided Question Wizard (shared renderer)
# ------------------------
def render_guided_wizard():
		with st.expander("🧙‍♂️ Guided Topics Wizard", expanded=False):
				domains = WIZARD_TARGETS.get("domains", [])
				domain_names = [d.get("name", "") for d in domains]
				domain_lookup = {d.get("name", ""): d for d in domains}
				cat = st.selectbox(
						"What are you here to explore?",
						options=domain_names,
						index=0 if domain_names else None,
						key="wizard_cat",
				)

				domain = domain_lookup.get(cat, {})
				if domain.get("description"):
						st.caption(domain["description"])

				subtopics_list = domain.get("subtopics", [])
				subtopic_names = [s.get("label", "") for s in subtopics_list]
				subtopic_lookup = {s.get("label", ""): s for s in subtopics_list}
				sub = st.selectbox(
						"Narrow it a bit…",
						options=subtopic_names,
						index=0 if subtopic_names else None,
						key="wizard_sub",
				)

				subtopic = subtopic_lookup.get(sub, {})
				refinements = subtopic.get("refinements")
				targets = []
				if refinements:
						ref_names = list(refinements.keys())
						ref = st.selectbox(
								"Any particular angle?",
								options=ref_names,
								index=0 if ref_names else None,
								key="wizard_ref",
						)
						targets = refinements.get(ref, [])
				else:
						targets = subtopic.get("targets", [])

				if targets:
					st.caption("Where to look in your chart:")

				for t in targets:
					meaning = None
					display_name = t

					# Add glyph if available
					glyph = GLYPHS.get(t)
					if glyph:
						display_name = f"{glyph} {t}"

					# Check meaning sources
					if t in OBJECT_MEANINGS_SHORT:
						meaning = OBJECT_MEANINGS_SHORT[t]
					elif t in SIGN_MEANINGS:
						meaning = SIGN_MEANINGS[t]
					elif "House" in t:
						try:
							house_num = int(t.split()[0].replace("st","").replace("nd","").replace("rd","").replace("th",""))
							meaning = HOUSE_MEANINGS.get(house_num)
						except Exception:
							meaning = None

					if meaning:
						st.write(f"{display_name}: {meaning}")
					else:
						st.write(f"{display_name}: [no meaning found]")

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

def _resolve_present_targets(df, targets: List[str]) -> Tuple[List[str], List[str]]:
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

def apply_wizard_targets(df, targets: List[str]):
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
