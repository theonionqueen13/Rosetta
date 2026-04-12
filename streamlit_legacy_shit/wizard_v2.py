
from typing import List, Tuple

import streamlit as st
from models_v2 import static_db
from src.mcp.topic_maps import WIZARD_TARGETS, KEYWORDS_LOOKUP  # shared topic data

ALIASES_MEANINGS = static_db.ALIASES_MEANINGS
GLYPHS = static_db.GLYPHS
OBJECT_MEANINGS_SHORT = static_db.OBJECT_MEANINGS_SHORT
SIGN_MEANINGS = static_db.SIGN_MEANINGS
HOUSE_MEANINGS = static_db.HOUSE_MEANINGS
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

# WIZARD_TARGETS and KEYWORDS_LOOKUP are now imported from src.mcp.topic_maps
# (single source of truth shared by both the Streamlit wizard and the MCP server)
