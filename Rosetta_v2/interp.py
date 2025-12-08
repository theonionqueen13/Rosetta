"""
interp.py - MCP (Model Context Protocol) for dynamic chart interpretation

This module provides an interface to generate poetic/technical interpretations
for the currently toggled planets, placements, and aspects in the chart display.

Usage:
    interp = Interp(chart_state)
    text = interp.generate(mode="poetic")
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from lookup_v2 import COMPASS_ASPECT_INTERP

class Interp:
    def __init__(self, chart_state: Dict[str, Any]):
        """
        chart_state: dict containing at least:
            - 'ordered_df': pd.DataFrame of visible objects (planet rows)
            - 'edges_major': list of (A, B, meta) for major aspects
            - 'edges_minor': list of (A, B, meta) for minor aspects
            - 'mode': 'poetic', 'technical', etc.
            - 'raw_links': rulership/dispositor info (optional)
            - 'lookup': dicts from lookup_v2.py (GLYPHS, OBJECT_MEANINGS, etc.)
        """
        self.state = chart_state
        self.ordered_df = chart_state.get('ordered_df')
        self.edges_major = chart_state.get('edges_major', [])
        self.edges_minor = chart_state.get('edges_minor', [])
        self.mode = chart_state.get('mode', 'poetic')
        self.raw_links = chart_state.get('raw_links', {})
        self.lookup = chart_state.get('lookup', {})
        self.missing = []  # Track missing data for footnotes
        # Try to load fixed star catalog if provided
        self.fixed_star_catalog = self.lookup.get('FIXED_STAR_CATALOG')

    def _interpret_object(self, row: pd.Series) -> str:
        """Generate interpretation for a single planet/object, using all available lookups."""
        obj = row.get('Object', '')
        sign = row.get('Sign', '')
        dms = row.get('DMS', '')
        house = row.get('Placidus House') or row.get('House') or row.get('Equal House') or row.get('Whole Sign House')
        # Convert house to plain integer if possible
        house_num = None
        if house is not None:
            try:
                house_num = int(float(house))
            except Exception:
                house_num = house
        lon_abs = row.get('Longitude')
        sabian = row.get('Sabian Symbol', '')
        # Lookups
        glyph = self.lookup.get('GLYPHS', {}).get(obj, row.get('Glyph', ''))
        meaning = self.lookup.get('OBJECT_MEANINGS', {}).get(obj)
        if not meaning:
            self.missing.append(f"meaning:{obj}")
            meaning = f"[No meaning for {obj}]"
        sign_meaning = self.lookup.get('SIGN_MEANINGS', {}).get(sign)
        if not sign_meaning:
            self.missing.append(f"sign_meaning:{sign}")
            sign_meaning = f"[No meaning for sign {sign}]"
        # Retrograde and dignity
        retrograde = row.get('Retrograde Bool', False)
        dignity = row.get('Dignity', '')
        # INTERP_FLAGS (optional)
        interp_flags = self.lookup.get('INTERP_FLAGS', {}).get(obj, '')
        if row.get('INTERP_FLAGS'):
            interp_flags = f"{interp_flags} {row.get('INTERP_FLAGS')}".strip()
        house_meaning = None
        if house_num is not None:
            house_meanings_dict = self.lookup.get('HOUSE_MEANINGS', {})
            house_meaning = house_meanings_dict.get(house_num)
            if not house_meaning:
                self.missing.append(f"house_meaning:{house_num}")
                house_meaning = f"[No meaning for house {house_num}]"
        # INTERP_FLAGS (optional)
        interp_flags = self.lookup.get('INTERP_FLAGS', {}).get(obj, '')
        # SABIAN_SYMBOLS (prefer from row, else lookup)
        if not sabian and sign and lon_abs is not None:
            sabian = self.lookup.get('SABIAN_SYMBOLS', {}).get((sign, int(lon_abs % 30) + 1), '')
        # Fixed stars
        fixed_stars = ''
        if self.fixed_star_catalog is not None and lon_abs is not None:
            try:
                find_fixed_star_conjunctions = self.lookup.get('find_fixed_star_conjunctions')
                if find_fixed_star_conjunctions:
                    hits = find_fixed_star_conjunctions(lon_abs, self.fixed_star_catalog, orb=1.0)
                    if hits:
                        fixed_stars = ', '.join([f"{h['Name']} (orb {h['sep']:.2f}°)" for h in hits])
            except Exception:
                self.missing.append(f"fixedstars:{obj}")
        # Compose text
        lines = []
        # Compose name line with dignity and retrograde
        name_line = f"{glyph} {obj}"
        if retrograde:
            name_line += " (Rx)"
        if dignity:
            name_line += f" - {dignity}"
        name_line += f" in {sign} {dms}."
        if self.mode == 'poetic':
            lines.append(name_line)
            lines.append(meaning)
            lines.append(f"Sign meaning: {sign_meaning}")
            if house_meaning and house_num is not None:
                lines.append(f"House {house_num}: {house_meaning}")
            if interp_flags:
                lines.append(f"Flags: {interp_flags}")
            if sabian:
                lines.append(f"Sabian: {sabian}")
            if fixed_stars:
                lines.append(f"Fixed Stars: {fixed_stars}")
        else:
            lines.append(name_line)
            lines.append(meaning)
            lines.append(f"Sign meaning: {sign_meaning}")
            if house_meaning and house_num is not None:
                lines.append(f"House {house_num}: {house_meaning}")
            if interp_flags:
                lines.append(f"Flags: {interp_flags}")
            if sabian:
                lines.append(f"Sabian: {sabian}")
            if fixed_stars:
                lines.append(f"Fixed Stars: {fixed_stars}")
        return '\n'.join([l for l in lines if l])

    def _interpret_aspect(self, a: str, b: str, meta: dict) -> str:
        """Generate interpretation for a single aspect using ASPECT_INTERP or COMPASS_ASPECT_INTERP."""
        aspect = meta.get('aspect', '')
        compass_rose_on = self.state.get('compass_rose_on', False)
        key = aspect.strip().title() if aspect else ''

        # DEBUG: Log every call
        print(f"[DEBUG] _interpret_aspect called with a={a!r}, b={b!r}, aspect={aspect!r}, compass_rose_on={compass_rose_on}")

        # Normalize names for axis detection
        def norm(x):
            return x.strip().replace('AC', 'Ascendant').replace('DC', 'Descendant').replace('Mc', 'MC').replace('Ic', 'IC')

        a_norm = norm(a)
        b_norm = norm(b)
        print(f"[DEBUG] Normalized: a_norm={a_norm!r}, b_norm={b_norm!r}")
        axis_pairs = [
            (('Ascendant', 'Descendant'), 'ACDC'),
            (('MC', 'IC'), 'MCIC'),
            (('North Node', 'South Node'), 'Nodes'),
        ]

        if compass_rose_on:
            # Always match axis pairs regardless of order or case
            for (axis1, axis2), interp_key in axis_pairs:
                names = {a_norm, b_norm}
                print(f"[DEBUG] Checking axis pair: {axis1}, {axis2} against names={names}")
                if {axis1, axis2} == names:
                    interp_text = COMPASS_ASPECT_INTERP.get(interp_key)
                    connector = 'Opposition'
                    label_a = axis1
                    label_b = axis2
                    if interp_text:
                        print(f"[DEBUG] Axis pair found: {label_a} {connector} {label_b}: {interp_text}")
                        return f"{label_a} {connector} {label_b}: {interp_text}"
            # If not an axis pair, do not interpret
            print(f"[DEBUG] Not an axis pair: a={a}, b={b}, names={{a_norm, b_norm}}={ {a_norm, b_norm} }")
            return ""

        # ...existing code for non-compass rose mode...
        # Helper: identify compass axes in a cluster label
        COMPASS_NAMES = {'Ascendant', 'Descendant', 'AC', 'DC', 'MC', 'IC', 'North Node', 'South Node'}
        COMPASS_KEYS = {
            frozenset(['Ascendant', 'Descendant']): 'ACDC',
            frozenset(['AC', 'DC']): 'ACDC',
            frozenset(['MC', 'IC']): 'MCIC',
            frozenset(['North Node', 'South Node']): 'Nodes',
        }

        def get_compass_axes(names):
            axes = []
            if any(n in names for n in ['Ascendant', 'AC', 'Descendant', 'DC']):
                if 'Ascendant' in names or 'AC' in names:
                    axes.append('Ascendant' if 'Ascendant' in names else 'AC')
                if 'Descendant' in names or 'DC' in names:
                    axes.append('Descendant' if 'Descendant' in names else 'DC')
            if 'MC' in names:
                axes.append('MC')
            if 'IC' in names:
                axes.append('IC')
            if 'North Node' in names:
                axes.append('North Node')
            if 'South Node' in names:
                axes.append('South Node')
            return axes

        def split_names(x):
            return [n.strip() for n in x.replace(' and ', ',').split(',')]

        names_a = split_names(a)
        names_b = split_names(b)
        axes_a = get_compass_axes(names_a)
        axes_b = get_compass_axes(names_b)
        all_axes = axes_a + [ax for ax in axes_b if ax not in axes_a]
        non_axes_a = [n for n in names_a if n not in COMPASS_NAMES]
        non_axes_b = [n for n in names_b if n not in COMPASS_NAMES]
        label_a = ', '.join(axes_a + non_axes_a) if axes_a else a
        label_b = ', '.join(axes_b + non_axes_b) if axes_b else b

        compass_aspect_keys = []
        cluster_has_axes = bool(axes_a or axes_b)
        for axis_set, keyname in COMPASS_KEYS.items():
            if axis_set.issubset(set(all_axes)):
                compass_aspect_keys.append(keyname)
        interp_texts = []
        if cluster_has_axes and compass_aspect_keys:
            compass_aspect_keys_sorted = sorted(compass_aspect_keys, key=lambda k: 1 if k == 'Nodes' else 0)
            for compass_aspect_key in compass_aspect_keys_sorted:
                interp_text = COMPASS_ASPECT_INTERP.get(compass_aspect_key)
                if interp_text is not None:
                    if isinstance(interp_text, (tuple, list)) and len(interp_text) > 0:
                        interp_text = str(interp_text[0])
                    else:
                        interp_text = str(interp_text)
                else:
                    self.missing.append(f"compass_aspect:{aspect}")
                    interp_text = f"[{compass_aspect_key} axis]"
                interp_texts.append(interp_text)
            connector = 'Conjunction' if key == 'Conjunction' else 'Opposite' if key == 'Opposition' else key
            joined_text = '\n'.join([f"{label_a} {connector} {label_b}: {txt}" for txt in interp_texts])
            return joined_text
        interp_text = self.lookup.get('ASPECT_INTERP', {}).get(key)
        if not interp_text:
            self.missing.append(f"aspect:{aspect}")
            interp_text = f"[{aspect.title()} aspect]"
        connector = 'Opposite' if key == 'Opposition' else key
        return f"{a} {connector} {b}: {interp_text}"

    def _interpret_circuit(self, objects: List[str], aspects: List[str]) -> str:
        """Synthesize a summary for the whole circuit."""
        # Placeholder: can be made more sophisticated
        if self.mode == 'poetic':
            return f"Together, these forces weave a unique circuit of meaning."
        else:
            return f"Circuit summary: {', '.join(objects)} with aspects {', '.join(aspects)}."

    def generate(self, mode: Optional[str] = None) -> str:
        """Generate the full interpretation text for the current chart state."""
        if mode:
            self.mode = mode
        if self.ordered_df is None or self.ordered_df.empty:
            return "No objects to interpret."
        # 1. Interpret objects
        object_texts = [self._interpret_object(row) for _, row in self.ordered_df.iterrows()]
        # 2. Interpret clustered aspects and collect cluster members
        aspect_texts = []
        clustered_pairs = set()
        clustered_members = set()
        compass_rose_on = self.state.get('compass_rose_on', False)
        forced_acdc_done = False
        try:
            from calc_v2 import build_clustered_aspect_edges, build_conjunction_clusters
            # If ONLY compass rose is toggled (no other objects), skip clusters for AC/DC
            only_compass = False
            visible_objs = set(self.ordered_df['Object']) if self.ordered_df is not None else set()
            compass_set = {'Ascendant', 'Descendant', 'MC', 'IC', 'North Node', 'South Node'}
            if compass_rose_on and visible_objs.issubset(compass_set):
                only_compass = True
            clustered_edges = build_clustered_aspect_edges(self.ordered_df, self.edges_major)
            clusters, cluster_map, cluster_sets = build_conjunction_clusters(self.ordered_df, self.edges_major)
            for s in cluster_sets:
                clustered_members.update(s)
            for a, b, meta in clustered_edges:
                # If only compass rose is on, skip any cluster involving AC or DC for aspect output
                if only_compass and (('Ascendant' in a or 'Descendant' in a or 'Ascendant' in b or 'Descendant' in b) and (',' in a or ',' in b)):
                    continue
                aspect_texts.append(self._interpret_aspect(a, b, meta))
                clustered_pairs.add(frozenset([a, b]))
        except Exception as e:
            aspect_texts.append(f"[Error in clustered aspect logic: {e}]")
        print(f"[DEBUG] Clustered members: {clustered_members}")
        print(f"[DEBUG] Clustered pairs: {clustered_pairs}")
        print(f"[DEBUG] All edges_major: {[(a, b) for a, b, _ in self.edges_major]}")
        # 3. Add aspects between objects not in any cluster (i.e., both a and b are not in clustered_members)
        for a, b, meta in self.edges_major:
            if (a not in clustered_members) and (b not in clustered_members):
                # Only add if not already included as a clustered aspect
                if frozenset([a, b]) not in clustered_pairs:
                    print(f"[DEBUG] Adding non-clustered aspect: {a}, {b}, {meta.get('aspect')}")
                    aspect_texts.append(self._interpret_aspect(a, b, meta))
        # 3b. If compass_rose_on, always append all three axis aspects, no cluster checks
        if compass_rose_on:
            compass_edges = [
                ('Ascendant', 'Descendant', {'aspect': 'AcDc'}),
                ('MC', 'IC', {'aspect': 'McIc'}),
                ('North Node', 'South Node', {'aspect': 'Nodes'})
            ]
            for a, b, meta in compass_edges:
                aspect_texts.append(self._interpret_aspect(a, b, meta))
        # 4. Synthesize circuit
        objects = list(self.ordered_df['Object'])
        aspects = [meta.get('aspect', '') for _, _, meta in self.edges_major]
        circuit_text = self._interpret_circuit(objects, aspects)
        # 5. Compose output
        output = '\n\n'.join(object_texts + aspect_texts + [circuit_text])
        # 6. Add missing info footnote
        if self.missing:
            output += f"\n\n[Missing: {', '.join(self.missing)}]"
        return output
# interp.py
# This module encapsulates the MCP logic for generating chart interpretations.

from typing import Dict, List, Any
import pandas as pd
from lookup_v2 import (
    GLYPHS, OBJECT_MEANINGS, OBJECT_MEANINGS_SHORT, INTERP_FLAGS,
    ORDERED_OBJECTS_FOCUS, CATEGORY_MAP, CATEGORY_INSTRUCTIONS,
    SIGN_MEANINGS, HOUSE_MEANINGS, ASPECT_INTERP, HOUSE_SYSTEM_INTERP,
    HOUSE_INTERP
)

class ChartInterpreter:
    def __init__(self):
        self.chart_state = {}
        self.interpretation_data = {}

    def query_chart_state(self, session_state: Dict[str, Any]):
        """
        Query the current chart state from Streamlit session state.
        """
        self.chart_state = {
            "visible_objects": session_state.get("visible_objects", []),
            "edges_major": session_state.get("edges_major", []),
            "edges_minor": session_state.get("edges_minor", []),
            "raw_links": session_state.get("raw_links", {}),
            "last_df": session_state.get("last_df"),
            "last_df_2": session_state.get("last_df_2"),
            "compass_rose_on": session_state.get("ui_compass_overlay", False),
        }

    def fetch_interpretation_data(self):
        """
        Fetch interpretation data from lookup_v2.py and other sources.
        """
        self.interpretation_data = {
            "glyphs": GLYPHS,
            "meanings": OBJECT_MEANINGS,
            "short_meanings": OBJECT_MEANINGS_SHORT,
            "sign_meanings": SIGN_MEANINGS,
            "house_meanings": HOUSE_MEANINGS,
            "aspect_interpretations": ASPECT_INTERP,
            "house_system_interp": HOUSE_SYSTEM_INTERP,
            "house_interp": HOUSE_INTERP,
        }

    def generate_interpretation(self, mode: str = "poetic") -> str:
        """
        Generate a text interpretation based on the current chart state and mode.
        """
        # Placeholder for interpretation logic
        interpretation = ""

        # Example: Iterate over visible objects and generate interpretations
        for obj in self.chart_state.get("visible_objects", []):
            glyph = self.interpretation_data["glyphs"].get(obj, "")
            meaning = self.interpretation_data["meanings"].get(obj, "No interpretation available.")
            interpretation += f"{glyph} {obj}: {meaning}\n"

        # Add logic for aspects, circuits, and modes
        # TODO: Implement detailed interpretation rules

        return interpretation

    def synthesize_circuit(self) -> str:
        """
        Synthesize an interpretation for the entire circuit.
        """
        # Placeholder for circuit synthesis logic
        return "Circuit interpretation not implemented yet."

# Example usage
# interpreter = ChartInterpreter()
# interpreter.query_chart_state(st.session_state)
# interpreter.fetch_interpretation_data()
# interpretation = interpreter.generate_interpretation(mode="poetic")
# st.text(interpretation)