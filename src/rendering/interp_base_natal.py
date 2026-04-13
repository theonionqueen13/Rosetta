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

from src.core.models_v2 import static_db, ObjectSign, ObjectHouse
from src.core.planet_profiles import (
    PlanetProfile,
    PlanetProfileReader,
    AspectProfile,
    AspectProfileReader,
)
from .profiles_v2 import (
    ordered_object_rows,
    ordered_objects,
    _canon,
    _extract_aspect,
    glyph_for,
)
from .drawing_v2 import RenderResult


def _selected_house_system() -> str:
    """Return the active house system from NiceGUI per-user storage.

    Falls back to ``"placidus"`` when called outside a NiceGUI request
    context (e.g. unit tests, MCP server, CLI scripts).
    """
    try:
        from nicegui import app as _ngapp
        return (_ngapp.storage.user.get("house_system") or "placidus").lower()
    except Exception:
        return "placidus"


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



_AXIS_TO_ABBREV: dict[str, str] = {
    "Ascendant": "AC",
    "Descendant": "DC",
    "Midheaven": "MC",
    "Immum Coeli": "IC",
    "AC": "AC",
    "DC": "DC",
    "MC": "MC",
    "IC": "IC",
}


def _aspect_display_name(name: str) -> str:
    """Return axis abbreviation for aspect lines; other objects unchanged."""
    return _AXIS_TO_ABBREV.get(name, name)


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
    The result should contain the AstrologicalChart in result.plot_data['chart'].

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
        self.drawn_minor_edges: List[Tuple[str, str, Any]] = getattr(
            result, "drawn_minor_edges", []
        ) or []

        # Get the AstrologicalChart from result.plot_data
        self.chart: Optional[Any] = None
        if result.plot_data and "chart" in result.plot_data:
            self.chart = result.plot_data["chart"]
        
        # Fallback to session state if chart not in RenderResult
        if self.chart is None:
            try:
                import streamlit as st  # type: ignore
                self.chart = st.session_state.get("last_chart")
            except Exception:
                pass
        
        # Build ordered list of ChartObject instances filtered to visible objects.
        # Use ordered_objects() so AC/DC pinning and cluster ordering match the sidebar.
        self.chart_objects: List[Any] = []
        if self.chart and hasattr(self.chart, "objects"):
            self.chart_objects = ordered_objects(
                self.chart,
                visible_objects=self.visible_objects or None,
                edges_major=self.drawn_major_edges or None,
            )

        # Build DataFrame for reference/display (not primary source)
        # This is for convenience in finding objects by name for house lookups
        raw_df: Optional[pd.DataFrame] = None
        if result.plot_data:
            raw_df = result.plot_data.get("ordered_df")

        # fallback to Streamlit session state if available (UI callers only)
        if raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty):
            try:
                import streamlit as st  # type: ignore
                last_chart = st.session_state.get("last_chart")
                if last_chart is not None and last_chart.df_positions is not None:
                    raw_df = last_chart.df_positions
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
                self.drawn_minor_edges = [
                    e for e in self.drawn_minor_edges
                    if e[0] in active and e[1] in active
                ]
        else:
            self.ordered_df = None

        # If we don't have a proper chart but we do have an ordered dataframe,
        # create ChartObject instances via ChartObject.from_dict() so that
        # rulership data and all other fields are properly populated from the static database.
        # This makes the class usable in unit tests and any other context where only the
        # dataframe is available.
        if not self.chart_objects and self.ordered_df is not None:
            # import here to avoid circular imports
            from src.core.models_v2 import ChartObject
            # iterate rows and convert using the proper from_dict method
            self.chart_objects = [
                ChartObject.from_dict(row.to_dict(), static_db) 
                for _, row in self.ordered_df.iterrows()
            ]

    # internal helpers -------------------------------------------------------

    def _default_lookup(self) -> Dict[str, Any]:
        """Return the standard lookup dictionary from ``static_db``."""
        return {
            "object_sign_combos": getattr(static_db, "object_sign_combos", {}),
            "object_house_combos": getattr(static_db, "object_house_combos", {}),
        }

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

    def _format_other_stats(self, chart_obj: Any) -> List[str]:
        """Format the 'Other stats' section with OOB, Reception, Rules, and Ruled by.
        
        Returns a list of strings to append to the output.
        """
        lines: List[str] = []
        
        obj_name = self._get_object_name(chart_obj)
        display_name = _format_axis_for_display(obj_name)
        
        # Check if there's anything to show at all
        has_oob = chart_obj.oob_status and chart_obj.oob_status != "No"
        has_reception = bool(chart_obj.reception and len(chart_obj.reception) > 0)
        has_rules = bool((chart_obj.rules_signs and len(chart_obj.rules_signs) > 0) or 
                        (chart_obj.rules_houses and len(chart_obj.rules_houses) > 0))
        
        # For ruled_by, we need to format the reception list into a string
        has_ruled_by_sign = bool(chart_obj.sign_ruler and len(chart_obj.sign_ruler) > 0)
        has_ruled_by_house = bool(
            (chart_obj.house_ruler_placidus and len(chart_obj.house_ruler_placidus) > 0) or
            (chart_obj.house_ruler_equal and len(chart_obj.house_ruler_equal) > 0) or
            (chart_obj.house_ruler_whole and len(chart_obj.house_ruler_whole) > 0)
        )
        
        if not (has_oob or has_reception or has_rules or has_ruled_by_sign or has_ruled_by_house):
            return []
        
        # Add divider and header
        lines.append("𑁋")
        lines.append("Other stats:")
        
        # Out of bounds
        if has_oob:
            lines.append(f"Out of bounds: {chart_obj.oob_status}")
        
        # Reception - format the ReceptionLink list into a readable string
        if has_reception:
            reception_strs = []
            for reception_link in chart_obj.reception:
                if reception_link and reception_link.other and reception_link.aspect:
                    aspect_verb = {
                        "Conjunction": "Conjunct",
                        "Opposition": "Opposite",
                        "Trine": "Trine",
                        "Square": "Square",
                        "Sextile": "Sextile",
                    }.get(reception_link.aspect.name, reception_link.aspect.name)
                    mode_suffix = " (by orb)" if reception_link.mode == "orb" else " (by sign)"
                    reception_strs.append(f"{aspect_verb} {reception_link.other.name}{mode_suffix}")
            if reception_strs:
                lines.append(f"Reception: {', '.join(reception_strs)}")
        
        # Rules (signs and houses)
        if has_rules:
            rules_parts = []
            
            # Rules by sign
            if chart_obj.rules_signs:
                sign_rules: List[str] = []
                for sign in chart_obj.rules_signs:
                    sign_name = sign.name if hasattr(sign, "name") else str(sign)
                    
                    # Try to use chart_signs if available (more efficient)
                    objs_in_sign = []
                    if self.chart and hasattr(self.chart, "chart_signs") and self.chart.chart_signs:
                        # Find matching ChartSign
                        for chart_sign in self.chart.chart_signs:
                            if chart_sign.name.name == sign_name:
                                objs_in_sign = [
                                    self._get_object_name(o) for o in chart_sign.contains
                                ]
                                break
                    
                    # Fallback to searching through objects if chart_signs not populated
                    if not objs_in_sign:
                        objs_in_sign = [
                            self._get_object_name(o) for o in self.chart_objects
                            if hasattr(o, "sign") and (o.sign.name if hasattr(o.sign, "name") else str(o.sign)) == sign_name
                        ]
                    
                    if objs_in_sign:
                        objs_str = ", ".join(objs_in_sign)
                        sign_rules.append(f'{sign_name} ({objs_str})')
                    else:
                        # still include the sign name even if no objects are present
                        sign_rules.append(f'{sign_name}')
                if sign_rules:
                    rules_parts.append("; ".join(sign_rules))
            
            # Rules by house
            if chart_obj.rules_houses:
                house_rules: List[str] = []
                for house in chart_obj.rules_houses:
                    house_num = house.number if hasattr(house, "number") else int(house)
                    house_label = _format_house_label(house_num)
                    
                    # Try to use chart_houses if available (more efficient)
                    objs_in_house: List[str] = []
                    if self.chart and hasattr(self.chart, "chart_houses") and self.chart.chart_houses:
                        # Find matching ChartHouse
                        for chart_house in self.chart.chart_houses:
                            if hasattr(chart_house.number, "number") and chart_house.number.number == house_num:
                                objs_in_house = [
                                    self._get_object_name(o) for o in chart_house.contains
                                ]
                                break
                    
                    # Fallback to searching through objects if chart_houses not populated
                    if not objs_in_house:
                        for obj in self.chart_objects:
                            obj_house = None
                            if hasattr(obj, "placidus_house"):
                                house_obj = obj.placidus_house
                                obj_house = house_obj.number if hasattr(house_obj, "number") else int(house_obj)
                            if obj_house == house_num:
                                objs_in_house.append(self._get_object_name(obj))
                    
                    if objs_in_house:
                        objs_str = ", ".join(objs_in_house)
                        house_rules.append(f'{house_label} ({objs_str})')
                    else:
                        # still include the house label on its own
                        house_rules.append(f'{house_label}')
                if house_rules:
                    rules_parts.append("; ".join(house_rules))
            
            if rules_parts:
                rules_line = f"Rules: {'; '.join(rules_parts)}"
                lines.append(rules_line)
        
        # Ruled by (by sign)
        if has_ruled_by_sign:
            ruler_names = [r.name if hasattr(r, "name") else str(r) for r in chart_obj.sign_ruler]
            if ruler_names:
                lines.append(f'Ruled by (by sign): {", ".join(ruler_names)}')
        
        # Ruled by (by house system)
        if has_ruled_by_house:
            # Determine which house system to use
            house_system = _selected_house_system()
            if house_system == "placidus":
                house_rulers = chart_obj.house_ruler_placidus
            elif house_system == "whole":
                house_rulers = chart_obj.house_ruler_whole
            else:  # equal or default
                house_rulers = chart_obj.house_ruler_equal
            
            if house_rulers:
                ruler_names = [r.name if hasattr(r, "name") else str(r) for r in house_rulers]
                if ruler_names:
                    lines.append(f'Ruled by (by house): {", ".join(ruler_names)}')
        
        return lines

    def _get_object_name(self, chart_obj: Any) -> str:
        """Extract the object name from a ChartObject."""
        if hasattr(chart_obj, "object_name"):
            obj = chart_obj.object_name
            return obj.name if hasattr(obj, "name") else str(obj)
        return ""

    def _format_default_object(self, chart_obj: Any) -> str:
        """Format object interpretation in default mode.

        Delegates to :class:`~planet_profiles.PlanetProfileReader` so the
        same rendering logic is available to sidebar, MCP, and any future
        callers.
        """
        obj_name = self._get_object_name(chart_obj)
        sign_name = chart_obj.sign.name if hasattr(chart_obj.sign, "name") else str(chart_obj.sign)

        profile = PlanetProfile.from_chart_object(
            chart_obj,
            house_system=_selected_house_system(),
            lookup=self.lookup,
            chart_objects=self.chart_objects,
            chart=self.chart,
        )

        # Track missing combos for diagnostics
        if not profile.sign_short_meaning:
            self.missing.append(f"object_sign_combo:{obj_name}_{sign_name}")
        if profile.house_num is not None and not profile.house_short_meaning:
            self.missing.append(f"object_house_combo:{obj_name}_House_{profile.house_num}")

        return PlanetProfileReader(profile).format_text(mode="default")

    def _format_focus_object(self) -> str:
        """Format object interpretation in focus mode (detailed multi-block).

        Delegates to :class:`~planet_profiles.PlanetProfileReader` in focus
        mode so the same logic is available to MCP and any future callers.
        """
        if self.object_name is None:
            return "Focus mode requires object_name to be specified."

        chart_obj = None
        for obj in self.chart_objects:
            if self._get_object_name(obj) == self.object_name:
                chart_obj = obj
                break

        if chart_obj is None:
            return f"Object '{self.object_name}' not found in chart."

        obj_name = self._get_object_name(chart_obj)
        sign_name = chart_obj.sign.name if hasattr(chart_obj.sign, "name") else str(chart_obj.sign)

        profile = PlanetProfile.from_chart_object(
            chart_obj,
            house_system=_selected_house_system(),
            lookup=self.lookup,
            chart_objects=self.chart_objects,
            chart=self.chart,
        )

        # Track missing combos
        if not profile.sign_short_meaning:
            self.missing.append(f"object_sign_combo:{obj_name}_{sign_name}")

        return PlanetProfileReader(profile).format_text(mode="focus")

    def _build_conjunction_cluster_map(self) -> dict[str, list[str]]:
        """Return a mapping of canon-root -> [ordered object names] for conjunction clusters.

        Only clusters with ≥2 members (among the visible chart objects) are included.
        Members are listed in the same order they appear in self.chart_objects.
        """
        obj_names = [
            (obj.object_name.name if hasattr(obj.object_name, "name") else str(obj.object_name))
            for obj in self.chart_objects
        ]
        canon_of = {name: _canon(name) for name in obj_names}
        canon_set = set(canon_of.values())

        # Union-find
        parent: dict[str, str] = {}

        def _find(x: str) -> str:
            while parent.get(x, x) != x:
                parent[x] = parent.get(parent.get(x, x), parent.get(x, x))
                x = parent.get(x, x)
            return x

        for edge in (self.drawn_major_edges or []):
            try:
                a, b, meta = edge
            except ValueError:
                continue
            aspect = _extract_aspect(meta)
            if not isinstance(aspect, str) or aspect.lower() != "conjunction":
                continue
            ca, cb = _canon(a), _canon(b)
            if ca in canon_set and cb in canon_set:
                ra, rb = _find(ca), _find(cb)
                if ra != rb:
                    parent[rb] = ra

        # Group names by root, preserving chart_objects order
        root_to_names: dict[str, list[str]] = {}
        for name in obj_names:
            root = _find(canon_of[name])
            root_to_names.setdefault(root, []).append(name)

        # Only return groups with ≥2 members
        return {root: names for root, names in root_to_names.items() if len(names) >= 2}

    def _format_aspects_section(
        self,
        cluster_map: dict[str, list[str]],
        canon_to_root: dict[str, str],
    ) -> str:
        """Format the aspects section listing all drawn major and minor edges.

        Delegates to :class:`~planet_profiles.AspectProfileReader` for rendering
        each individual aspect line.
        """
        all_edges = list(self.drawn_major_edges or []) + list(self.drawn_minor_edges or [])
        if not all_edges:
            return ""

        divider = "─" * 50
        aspect_lines: list[str] = []
        seen_edges: set[tuple] = set()

        _COMPASS_OPP_PAIRS = {
            frozenset({"AC", "DC"}),
            frozenset({"MC", "IC"}),
            frozenset({"North Node", "South Node"}),
        }

        for edge in all_edges:
            try:
                a, b, meta = edge
            except (ValueError, TypeError):
                continue

            aspect = _extract_aspect(meta)
            if not aspect:
                continue
            if aspect.lower() == "conjunction":
                continue

            # Build profile (handles cluster label substitution)
            profile = AspectProfile.from_edge(a, b, meta, cluster_map=cluster_map)

            dedup_key = (frozenset({profile.obj_a_display, profile.obj_b_display}), aspect)
            if dedup_key in seen_edges:
                continue
            seen_edges.add(dedup_key)

            # Skip bare compass-rose axis oppositions unless one node is a cluster
            if (
                aspect.lower() == "opposition"
                and not profile.is_cluster_edge
                and frozenset({profile.obj_a_display, profile.obj_b_display}) in _COMPASS_OPP_PAIRS
            ):
                continue

            reader = AspectProfileReader(profile)
            aspect_lines.append(reader.format_text())
            aspect_lines.append(divider)

        if not aspect_lines:
            return ""

        return f"\n{divider}\nAspects:\n{divider}\n" + "\n".join(aspect_lines)

    # public ----------------------------------------------------------------

    def generate(self) -> str:
        """Generate interpretation text in the configured mode."""
        if self.mode == "focus":
            return self._format_focus_object()

        # Default mode - use chart_objects as primary source
        if not self.chart_objects:
            return "No active objects selected to interpret."

        # Pre-build conjunction cluster map: canon-root -> ordered names list
        cluster_map = self._build_conjunction_cluster_map()
        # canon -> root (for fast lookup per object)
        canon_to_root: dict[str, str] = {}
        for root, names in cluster_map.items():
            for name in names:
                canon_to_root[_canon(name)] = root
        # Track which cluster roots have already had their header emitted
        emitted_roots: set[str] = set()

        obj_texts: List[str] = []
        divider = "─" * 50

        for chart_obj in self.chart_objects:
            obj_name = (
                chart_obj.object_name.name
                if hasattr(chart_obj.object_name, "name")
                else str(chart_obj.object_name)
            )
            root = canon_to_root.get(_canon(obj_name))
            if root is not None and root not in emitted_roots:
                emitted_roots.add(root)
                members = cluster_map[root]
                header = f"Conjunction: {', '.join(members)}"
                # Insert divider + header as its own block so it sits between dividers
                obj_texts.append(header)

            text = self._format_default_object(chart_obj)
            if text:
                text = re.sub(r"\n{3,}", "\n\n", text.strip())
                obj_texts.append(text)

        body = f"\n{divider}\n".join(obj_texts)
        body = re.sub(r"\n{3,}", "\n\n", body)

        # Append aspects section after all object profiles
        aspects_section = self._format_aspects_section(cluster_map, canon_to_root)
        if aspects_section:
            body += aspects_section

        return body


# expose for backwards compatibility
__all__ = ["NatalInterpreter"]
