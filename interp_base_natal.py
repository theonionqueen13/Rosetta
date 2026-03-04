"""
interp_base_natal.py - New natal chart interpreter for Rosetta v2

This module replaces the legacy interp_v2.py with a cleaner, more extensible
architecture. The NatalInterpreter class supports two modes:

  - "default": Concise 6-line profile per object (sign placement + house placement)
  - "focus": Detailed multi-block output for a single specified object

The interpreter pulls all interpretive text from pre-populated ObjectSign and
ObjectHouse dataclasses in the static database, avoiding costly lookups and
keeping the code minimal.

Usage::

    from drawing_v2 import RenderResult
    from interp_base_natal import NatalInterpreter

    # Default mode: all objects, concise format
    interp = NatalInterpreter(result)
    text = interp.generate()

    # Focus mode: single object, detailed format
    interp = NatalInterpreter(result, mode="focus", object_name="Sun")
    text = interp.generate()
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import re

import pandas as pd

from models_v2 import static_db, ObjectSign, ObjectHouse
from profiles_v2 import (
    ordered_object_rows,
    _canon,
    glyph_for,
)
from drawing_v2 import RenderResult


# --- constants ------------------------------------------------------------
AXIS_MAP: Dict[str, str] = {
    "AC": "Ascendant",
    "DC": "Descendant",
    "Mc": "MC",
    "Ic": "IC",
    "Ascendant": "Ascendant",
    "Descendant": "Descendant",
    "MC": "MC",
    "IC": "IC",
    "North Node": "North Node",
    "South Node": "South Node",
    "NorthNode": "North Node",  # Variant without space
    "SouthNode": "South Node",  # Variant without space
}


# --- axis display formatting -----------------------------------------------
AXIS_FULL_NAMES = {
    "AC": "Ascendant",
    "DC": "Descendant",
    "MC": "Midheaven",
    "IC": "Immum Coeli",
}

AXIS_ABBREVIATIONS = {v: k for k, v in AXIS_FULL_NAMES.items()}
AXIS_ABBREVIATIONS.update({k: k for k in AXIS_FULL_NAMES.keys()})  # Add abbrev -> abbrev


def _format_axis_for_display(obj_name: str) -> str:
    """Format axis object name as 'Full Name (Abbreviation)'.
    
    Handles all forms: "AC", "Ascendant", "AC Ascendant", etc.
    Returns "Ascendant (AC)", "Descendant (DC)", etc.
    For non-axis objects, returns the name unchanged.
    """
    # Map of all known axis forms to their canonical (abbrev, full_name) pair
    axis_mapping = {
        # Abbreviations
        "AC": ("AC", "Ascendant"),
        "DC": ("DC", "Descendant"),
        "MC": ("MC", "Midheaven"),
        "IC": ("IC", "Immum Coeli"),
        # Full names
        "Ascendant": ("AC", "Ascendant"),
        "Descendant": ("DC", "Descendant"),
        "Midheaven": ("MC", "Midheaven"),
        "Immum Coeli": ("IC", "Immum Coeli"),
    }
    
    # Try exact match first
    if obj_name in axis_mapping:
        abbrev, full_name = axis_mapping[obj_name]
        return f"{full_name} ({abbrev})"
    
    # Handle hybrid forms by splitting on space
    # e.g., "AC Ascendant" -> ["AC", "Ascendant"]
    parts = obj_name.split()
    if len(parts) >= 2:
        # Check if first part is a 2-letter axis abbreviation
        potential_abbrev = parts[0]
        if potential_abbrev in ("AC", "DC", "MC", "IC"):
            # The rest is the full name
            full_name = " ".join(parts[1:])
            return f"{full_name} ({potential_abbrev})"
    
    # Not an axis - return as-is
    return obj_name



def _format_house_label(house_num: float | int | str | None) -> str:
    """Format a house number as ordinal (e.g., '1st House', '2nd House')."""
    if house_num is None:
        return ""
    try:
        h = int(float(house_num))
    except (ValueError, TypeError):
        h = int(house_num)

    ordinals = {
        1: "1st",
        2: "2nd",
        3: "3rd",
        4: "4th",
        5: "5th",
        6: "6th",
        7: "7th",
        8: "8th",
        9: "9th",
        10: "10th",
        11: "11th",
        12: "12th",
    }
    suffix = ordinals.get(h, f"{h}th")
    return f"{suffix} House"



# ---------------------------------------------------------------------------
class NatalInterpreter:
    """Generate natal chart interpretation text in default or focus mode.

    ``result`` should be the ``RenderResult`` from :mod:`drawing_v2`.
    The object must contain at least ``visible_objects``, ``drawn_major_edges``,
    and a ``plot_data`` mapping with an ``'ordered_df'`` key.

    ``mode`` is either "default" (concise, all objects) or "focus" (detailed,
    single object). For focus mode, ``object_name`` must be specified.

    ``lookup`` allows overrides to the standard static database; if omitted,
    defaults are pulled from :mod:`models_v2.static_db`.
    """

    def __init__(
        self,
        result: RenderResult,
        mode: str = "default",
        object_name: Optional[str] = None,
        lookup: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.result = result
        self.mode = mode
        self.object_name = object_name
        self.lookup = lookup or self._default_lookup()
        self.missing: List[str] = []

        # visible_objects list from result
        self.visible_objects: List[str] = getattr(result, "visible_objects", []) or []

        # edges drawn during rendering
        self.drawn_major_edges: List[Tuple[str, str, Any]] = getattr(
            result, "drawn_major_edges", []
        ) or []

        # build ordered_df using the same helper as elsewhere in the application
        raw_df: Optional[pd.DataFrame] = None
        if result.plot_data:
            raw_df = result.plot_data.get("ordered_df")

        # fallback to Streamlit session state if available (UI callers only)
        if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
            try:
                import streamlit as st  # type: ignore
                last = st.session_state.get("last_df")
                if last is not None and isinstance(last, pd.DataFrame):
                    raw_df = last
            except Exception:
                pass

        if raw_df is not None and not raw_df.empty:
            self.ordered_df = ordered_object_rows(
                raw_df,
                visible_objects=self.visible_objects,
                edges_major=self.drawn_major_edges,
            )
            if self.ordered_df is not None:
                active = set(self.ordered_df["Object"].tolist())
                self.drawn_major_edges = [
                    e for e in self.drawn_major_edges
                    if e[0] in active and e[1] in active
                ]
        else:
            self.ordered_df = None

    # internal helpers -------------------------------------------------------

    def _default_lookup(self) -> Dict[str, Any]:
        """Return the standard lookup dictionary from ``static_db``."""
        return {
            "object_sign_combos": getattr(static_db, "object_sign_combos", {}),
            "object_house_combos": getattr(static_db, "object_house_combos", {}),
        }

    def _get_object_row(self, obj_name: str) -> Optional[pd.Series]:
        """Locate the DataFrame row for ``obj_name`` (handles AXIS_MAP variants)."""
        if self.ordered_df is None:
            return None

        # build variant set including AXIS_MAP mappings
        variants = {obj_name}
        for key, val in AXIS_MAP.items():
            if val == obj_name:
                variants.add(key)

        canon_variants = {_canon(v) for v in variants}

        for _, row in self.ordered_df.iterrows():
            if _canon(row.get("Object", "")) in canon_variants:
                return row
        return None

    def _normalize_obj_name_for_combo(self, obj_name: str) -> str:
        """Return an object name suitable for combo dictionary keys.

        The static database keys normally use concise identifiers:
        
        * Axes use two-letter abbreviations ("AC", "DC", "IC", "MC").
        * Lunar nodes and other multi-word objects drop spaces ("NorthNode").
        * Some objects use shortened names (e.g., "Lilith" for "Black Moon Lilith (Mean)").

        The chart dataframe (and user inputs) may supply more human-readable
        names such as "Ascendant" or "North Node", so we translate those here.
        """
        # explicit mapping for known variants
        mapping = {
            # Axes
            "Ascendant": "AC",
            "Descendant": "DC",
            "Midheaven": "MC",
            "Immum Coeli": "IC",
            # Lunar nodes
            "North Node": "NorthNode",
            "South Node": "SouthNode",
            # Special shortened names
            "Black Moon Lilith (Mean)": "Lilith",
            "Black Moon Lilith (True)": "Lilith",
            "Part of Fortune": "PartOfFortune",
            "Vertex": "Vertex",  # May not have combos, but handle it anyway
            # keep the abbreviations and direct names intact
            "AC": "AC",
            "DC": "DC",
            "MC": "MC",
            "IC": "IC",
            "NorthNode": "NorthNode",
            "SouthNode": "SouthNode",
            "Lilith": "Lilith",
            "PartOfFortune": "PartOfFortune",
        }
        if obj_name in mapping:
            return mapping[obj_name]
        # default: just remove spaces (Sun -> Sun, "Some Object" -> "SomeObject")
        return obj_name.replace(" ", "")

    def _get_object_sign_combo(
        self, obj_name: str, sign_name: str
    ) -> Optional[ObjectSign]:
        """Fetch ObjectSign combo from static lookup."""
        combos_dict = self.lookup.get("object_sign_combos", {})
        # normalize the object name so it matches keys like "AC_Aries" or
        # "NorthNode_Leo".
        norm_name = self._normalize_obj_name_for_combo(obj_name)
        key = f"{norm_name}_{sign_name}"
        return combos_dict.get(key)

    def _get_object_house_combo(
        self, obj_name: str, house_num: int
    ) -> Optional[ObjectHouse]:
        """Fetch ObjectHouse combo from static lookup."""
        combos_dict = self.lookup.get("object_house_combos", {})
        # normalize the object name so it matches table keys like
        # "IC_House_4" or "NorthNode_House_1".
        norm_name = self._normalize_obj_name_for_combo(obj_name)
        key = f"{norm_name}_House_{house_num}"
        return combos_dict.get(key)

    def _format_first_line(self, row: pd.Series) -> str:
        """Format the first line: [glyph] [object] (Rx) in [sign] [DMS]"""
        obj = row.get("Object", "")
        sign = row.get("Sign", "")
        dms = row.get("DMS", "")
        retrograde = row.get("Retrograde Bool", False)

        glyph = glyph_for(obj)
        line = f"{glyph} {obj}"

        if retrograde:
            line += " (Rx)"

        line += f" in {sign} {dms}"
        return line

    def _extract_house_num(self, row: pd.Series) -> Optional[int]:
        """Extract house number from row, handling multiple house field options."""
        house = (
            row.get("Placidus House")
            or row.get("House")
            or row.get("Equal House")
            or row.get("Whole Sign House")
        )
        if house is None:
            return None
        try:
            return int(float(house))
        except (ValueError, TypeError):
            return None

    def _format_default_object(self, row: pd.Series) -> str:
        """
        Format object interpretation in default mode (6-line concise format).

        Lines:
        1. [glyph] [object] (Rx) in [sign]: [short_meaning] (ObjectSign)
        2. [dignity]: [object_name] [dignity_interp]  (only if dignity exists)
        3. [behavioral_style]
        4. 𑁋   # mini‑divider
        5. [sign] [DMS]
        6. Sabian Symbol: [symbol]
        7. Sabian Symbol Meaning: [short_meaning]
        8. Fixed star conjunction(s): [star names]
        9. 𑁋   # mini‑divider
        10. [object_name] in the [house_number]: [short_meaning] (ObjectHouse)
        11. Environmental Impact: [environmental_impact]
        12. Concrete Manifestations: [concrete_manifestation]

        """
        lines: List[str] = []

        obj_name = row.get("Object", "")
        display_name = _format_axis_for_display(obj_name)
        sign_name = row.get("Sign", "")
        house_num = self._extract_house_num(row)

        # Line 1: glyph/object/retrograde in sign, plus short meaning if available
        obj_sign_combo = self._get_object_sign_combo(obj_name, sign_name)
        glyph = glyph_for(obj_name)
        
        # For axes, don't include the glyph since it's just a text abbreviation and we're already
        # including the abbreviation in the display format (e.g., "Ascendant (AC)")
        is_axis = obj_name in {"Ascendant", "Descendant", "Midheaven", "Immum Coeli", "MC", "IC", "AC", "DC"}
        first_line = f"{display_name}" if is_axis else f"{glyph} {display_name}"
        if row.get("Retrograde Bool", False):
            first_line += " (Rx)"
        first_line += f" in {sign_name}"
        if obj_sign_combo and obj_sign_combo.short_meaning:
            first_line += f": {obj_sign_combo.short_meaning}"
        else:
            # record missing meaning so it can be logged elsewhere
            self.missing.append(f"object_sign_combo:{obj_name}_{sign_name}")
        lines.append(first_line)

        # Line 2: Dignity (only if it exists)
        if obj_sign_combo and obj_sign_combo.dignity:
            dignity_line = f"{obj_sign_combo.dignity}: {display_name}"
            if obj_sign_combo.dignity_interp:
                dignity_line += f" {obj_sign_combo.dignity_interp}"
            lines.append(dignity_line)

        # Line 3: Behavioral style
        if obj_sign_combo and obj_sign_combo.behavioral_style:
            lines.append(obj_sign_combo.behavioral_style)

        # Before house info, insert any Sabian/fixed-star details separated by a divider
        # sabian logic: either computed from degree or supplied manually
        manual_sabian = row.get("Sabian Symbol")
        degree_in_sign = row.get("Degree In Sign")
        sabian_obj = None
        if degree_in_sign is not None:
            try:
                sabian_obj = static_db.sabian_symbols.get(sign_name, {}).get(int(float(degree_in_sign)) + 1)
            except (TypeError, ValueError):
                pass

        fixed_star = row.get("Fixed Star Conj") or row.get("Fixed Star Conjunctions")
        if manual_sabian or sabian_obj or fixed_star:
            lines.append("𑁋")
            # always show sign+dms line when any sabian info exists
            dms = row.get("DMS", "")
            lines.append(f"{sign_name} {dms}")
            # symbol text: prefer manual if provided
            if manual_sabian:
                lines.append(f"Sabian Symbol: {manual_sabian}")
            elif sabian_obj and sabian_obj.symbol:
                lines.append(f"Sabian Symbol: {sabian_obj.symbol}")
            # meaning (only from lookup; manual intent is usually just symbol)
            if sabian_obj and sabian_obj.short_meaning:
                lines.append(f"Sabian Symbol Meaning: {sabian_obj.short_meaning}")
            # Fixed star line
            if fixed_star:
                lines.append(f"Fixed star conjunction(s): {fixed_star}")

        # Lines 5-7: Combined house line with short meaning + additional house details
        # Format: [object_name] in the [house_number]: [short_meaning]
        # Do not show a house section for AC/DC; those are implicitly 1st/7th and add
        # no extra interpretive text. Avoid printing a dangling divider in that case.
        is_acdc = self._normalize_obj_name_for_combo(obj_name) in {"AC", "DC"}
        if house_num is not None and not is_acdc:
            # separator before house section
            lines.append("𑁋")
            obj_house_combo = self._get_object_house_combo(obj_name, house_num)
            if obj_house_combo and obj_house_combo.short_meaning:
                house_label = _format_house_label(house_num)
                house_line = f"{display_name} in the {house_label}: {obj_house_combo.short_meaning}"
                lines.append(house_line)
            else:
                self.missing.append(f"object_house_combo:{obj_name}_House_{house_num}")
            
            # Line 6: Environmental Impact (if exists)
            if obj_house_combo and obj_house_combo.environmental_impact:
                lines.append(f"Environmental Impact: {obj_house_combo.environmental_impact}")
            
            # Line 7: Concrete Manifestations (if exists)
            if obj_house_combo and obj_house_combo.concrete_manifestation:
                lines.append(f"Concrete Manifestations: {obj_house_combo.concrete_manifestation}")


        return "\n".join([line for line in lines if line])

    def _format_focus_object(self) -> str:
        """
        Format object interpretation in focus mode (detailed multi-block format).

        Block 1 (Sign Placement):
        - Line 1: [glyph] [object] (Rx) in [sign]: [short_meaning] (ObjectSign)
        - Line 2: Dignity: [dignity]: [object_name] [dignity_interp]  (if exists)
        - Line 4: Style: [behavioral_style]
        - Line 5: Strengths: [strengths]
        - Line 6: Challenges: [challenges]
        - Line 7: Somatic Signature: [somatic_signature]
        - Line 8: Shadow Expression: [shadow_expression]

        Block 2 (House Placement):
        - Line 1: [object_name] in [house_number]
        - Line 2: [short_meaning] (ObjectHouse)
        - Line 3: Environmental Impact: [environmental_impact]
        - Line 4: Concrete Manifestations: [concrete_manifestation]
        - Line 5: Strengths: [strengths]
        - Line 6: Challenges: [challenges]
        - Line 7: Objective: [objective]
        """
        if self.object_name is None:
            return "Focus mode requires object_name to be specified."

        row = self._get_object_row(self.object_name)
        if row is None:
            return f"Object '{self.object_name}' not found in chart."

        obj_name = row.get("Object", "")
        display_name = _format_axis_for_display(obj_name)
        sign_name = row.get("Sign", "")
        house_num = self._extract_house_num(row)

        blocks: List[str] = []

        # ===== BLOCK 1: Sign Placement =====
        sign_lines: List[str] = []

        # Sign Block Line 1: combine glyph/object/(Rx)/sign and short meaning
        obj_sign_combo = self._get_object_sign_combo(obj_name, sign_name)
        glyph = glyph_for(obj_name)
        
        # For axes, don't include the glyph since it's just a text abbreviation and we're already
        # including the abbreviation in the display format (e.g., "Ascendant (AC)")
        is_axis = obj_name in {"Ascendant", "Descendant", "Midheaven", "Immum Coeli", "MC", "IC", "AC", "DC"}
        first = f"{display_name}" if is_axis else f"{glyph} {display_name}"
        if row.get("Retrograde Bool", False):
            first += " (Rx)"
        first += f" in {sign_name}"
        if obj_sign_combo and obj_sign_combo.short_meaning:
            first += f": {obj_sign_combo.short_meaning}"
        else:
            self.missing.append(f"object_sign_combo:{obj_name}_{sign_name}")
        sign_lines.append(first)

        # Sign Block Line 3: Dignity (only if exists)
        if obj_sign_combo and obj_sign_combo.dignity:
            dignity_line = f"Dignity: {obj_sign_combo.dignity}: {display_name}"
            if obj_sign_combo.dignity_interp:
                dignity_line += f" {obj_sign_combo.dignity_interp}"
            sign_lines.append(dignity_line)

        # Sign Block Line 4: Style
        if obj_sign_combo and obj_sign_combo.behavioral_style:
            sign_lines.append(f"Style: {obj_sign_combo.behavioral_style}")

        # Sign Block Line 5: Strengths
        if obj_sign_combo and obj_sign_combo.strengths:
            sign_lines.append(f"Strengths: {obj_sign_combo.strengths}")

        # Sign Block Line 6: Challenges
        if obj_sign_combo and obj_sign_combo.challenges:
            sign_lines.append(f"Challenges: {obj_sign_combo.challenges}")

        # Sign Block Line 7: Somatic Signature
        if obj_sign_combo and obj_sign_combo.somatic_signature:
            sign_lines.append(f"Somatic Signature: {obj_sign_combo.somatic_signature}")

        # Sign Block Line 8: Shadow Expression
        if obj_sign_combo and obj_sign_combo.shadow_expression:
            sign_lines.append(f"Shadow Expression: {obj_sign_combo.shadow_expression}")

        blocks.append("\n".join([line for line in sign_lines if line]))

        # ===== BLOCK 2: House Placement =====
        # skip the house block for AC/DC since those are implicitly 1st/7th and we
        # don't want to display redundant/empty information
        is_acdc = self._normalize_obj_name_for_combo(obj_name) in {"AC", "DC"}
        if house_num is not None and not is_acdc:
            house_lines: List[str] = []

            # House Block Line 1
            house_lines.append(f"{display_name} in {_format_house_label(house_num)}")

            # House Block Line 2: short_meaning
            obj_house_combo = self._get_object_house_combo(obj_name, house_num)
            if obj_house_combo and obj_house_combo.short_meaning:
                house_lines.append(obj_house_combo.short_meaning)

            # House Block Line 3: Environmental Impact
            if obj_house_combo and obj_house_combo.environmental_impact:
                house_lines.append(
                    f"Environmental Impact: {obj_house_combo.environmental_impact}"
                )

            # House Block Line 4: Concrete Manifestations
            if obj_house_combo and obj_house_combo.concrete_manifestation:
                house_lines.append(
                    f"Concrete Manifestations: {obj_house_combo.concrete_manifestation}"
                )

            # House Block Line 5: Strengths
            if obj_house_combo and obj_house_combo.strengths:
                house_lines.append(f"Strengths: {obj_house_combo.strengths}")

            # House Block Line 6: Challenges
            if obj_house_combo and obj_house_combo.challenges:
                house_lines.append(f"Challenges: {obj_house_combo.challenges}")

            # House Block Line 7: Objective
            if obj_house_combo and obj_house_combo.objective:
                house_lines.append(f"Objective: {obj_house_combo.objective}")

            blocks.append("\n".join([line for line in house_lines if line]))

        return "\n\n".join(blocks)

    # public ----------------------------------------------------------------

    def generate(self) -> str:
        """Generate interpretation text in the configured mode."""
        if self.mode == "focus":
            return self._format_focus_object()

        # Default mode
        if self.ordered_df is None or self.ordered_df.empty:
            return "No active objects selected to interpret."

        obj_texts: List[str] = []
        for _, row in self.ordered_df.iterrows():
            text = self._format_default_object(row)
            if text:
                # collapse excessive blank lines
                text = re.sub(r"\n{3,}", "\n\n", text.strip())
                obj_texts.append(text)

        # Build body with divider lines between profiles
        divider = "─" * 50
        body = f"\n{divider}\n".join(obj_texts)

        # Final pass to collapse any excessive blank lines
        body = re.sub(r"\n{3,}", "\n\n", body)
        return body


# expose for backwards compatibility
__all__ = ["NatalInterpreter"]
