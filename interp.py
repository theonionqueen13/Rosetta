"""
interp.py - MCP (Model Context Protocol) for dynamic chart interpretation

This module provides an interface to generate poetic/technical interpretations
for the currently toggled planets, placements, and aspects in the chart display.

Usage:
    interpreter = ChartInterpreter(chart_state)
    text = interpreter.generate(mode="poetic")
"""

from typing import List, Dict, Any, Optional
import pandas as pd
# Assuming these lookups are dictionaries keyed for quick access
from lookup_v2 import COMPASS_ASPECT_INTERP, HOUSE_AXIS_INTERP, SIGN_AXIS_INTERP 
# Assuming calc_v2 exists in the same environment
try:
    from calc_v2 import build_clustered_aspect_edges, build_conjunction_clusters
except ImportError:
    # Define placeholder functions if calc_v2 is missing to prevent errors
    def build_clustered_aspect_edges(df, edges): return []
    def build_conjunction_clusters(df, edges): return {}, {}, set()

class ChartInterpreter:
    """
    Interprets chart state data (objects and aspects) into narrative text.
    """
    
    # --- Constants for Name Normalization and Axis Grouping ---
    AXIS_MAP = {
        'AC': 'Ascendant', 'DC': 'Descendant', 'Mc': 'MC', 'Ic': 'IC',
        'Ascendant': 'Ascendant', 'Descendant': 'Descendant', 'MC': 'MC', 'IC': 'IC',
        'North Node': 'North Node', 'South Node': 'South Node',
    }
    COMPASS_KEYS = {
        frozenset(['Ascendant', 'Descendant']): 'ACDC',
        frozenset(['MC', 'IC']): 'MCIC',
        frozenset(['North Node', 'South Node']): 'Nodes',
    }

    def __init__(self, chart_state: Dict[str, Any]):
        """
        Initializes the interpreter and normalizes object names for consistent lookup.
        """
        self.state = chart_state
        self.ordered_df: Optional[pd.DataFrame] = chart_state.get('ordered_df')
        self.edges_major: List[tuple] = chart_state.get('edges_major', [])
        self.edges_minor: List[tuple] = chart_state.get('edges_minor', [])
        self.mode: str = chart_state.get('mode', 'poetic')
        self.raw_links: Dict[str, Any] = chart_state.get('raw_links', {})
        self.lookup: Dict[str, Any] = chart_state.get('lookup', {})
        self.missing: List[str] = []  # Track missing data for footnotes
        self.fixed_star_catalog = self.lookup.get('FIXED_STAR_CATALOG')

        # Pre-normalize 'Object' names in the DataFrame once
        if self.ordered_df is not None and not self.ordered_df.empty:
            def normalize_name(x):
                # Ensure it's a string before calling strip/get
                return self.AXIS_MAP.get(str(x).strip(), str(x).strip())
            
            # Create a dedicated normalized object name column for consistent lookups
            self.ordered_df['Object_Normalized'] = self.ordered_df['Object'].apply(normalize_name)


    def _get_object_row(self, obj_name: str) -> Optional[pd.Series]:
        """Find the row for an object using its normalized name, handling variants."""
        if self.ordered_df is None:
            return None
        
        # Use Object_Normalized for lookup (requires initialization fix)
        # Note: self.ordered_df should contain rows for Ascendant/AC, MC/Mc etc.
        # We rely on the name being present either exactly or via self.AXIS_MAP conversion
        variants = [obj_name]
        # Add common abbreviations to variants for lookup
        for key, val in self.AXIS_MAP.items():
            if val == obj_name and key != obj_name:
                variants.append(key)
        
        for variant in variants:
            row = self.ordered_df[self.ordered_df['Object'] == variant]
            if not row.empty:
                return row.iloc[0]
        return None


    def _get_axis_info(self, obj_name: str) -> tuple[Any, Any]:
            """
            Retrieves house and sign information for a given object name.
            Used primarily for aspects/oppositions to determine house/sign axes.
            """
            row = self._get_object_row(obj_name)
            if row is not None:
                house = row.get('Placidus House') or row.get('House') or row.get('Equal House') or row.get('Whole Sign House')
                sign = row.get('Sign')
                return house, sign
            return None, None


    def _interpret_object(self, row: pd.Series) -> str:
        """Generate interpretation for a single planet/object, using all available lookups."""
        obj: str = row.get('Object', '')
        sign: str = row.get('Sign', '')
        dms: str = row.get('DMS', '')
        house: Any = row.get('Placidus House') or row.get('House') or row.get('Equal House') or row.get('Whole Sign House')
        lon_abs: Optional[float] = row.get('Longitude')
        
        # --- House Number & Meaning Lookup ---
        house_num = None
        if house is not None:
            try:
                house_num = int(float(house))
            except Exception:
                house_num = str(house) # Keep non-numeric houses as strings
        
        house_meaning = None
        if house_num is not None:
            house_meanings_dict = self.lookup.get('HOUSE_MEANINGS', {})
            house_meaning = house_meanings_dict.get(house_num)
            if not house_meaning:
                self.missing.append(f"house_meaning:{house_num}")
                house_meaning = f"[No meaning for house {house_num}]"

        # --- Other Lookups & Data Retrieval ---
        glyph: str = self.lookup.get('GLYPHS', {}).get(obj, row.get('Glyph', ''))
        meaning: str = self.lookup.get('OBJECT_MEANINGS', {}).get(obj)
        if not meaning:
            self.missing.append(f"meaning:{obj}")
            meaning = f"[No meaning for {obj}]"
        
        sign_meaning: str = self.lookup.get('SIGN_MEANINGS', {}).get(sign)
        if not sign_meaning:
            self.missing.append(f"sign_meaning:{sign}")
            sign_meaning = f"[No meaning for sign {sign}]"
        
        retrograde: bool = row.get('Retrograde Bool', False)
        dignity: str = row.get('Dignity', '')

        # Consolidate INTERP_FLAGS lookup
        interp_flags: str = self.lookup.get('INTERP_FLAGS', {}).get(obj, '')
        if row.get('INTERP_FLAGS'):
            interp_flags = f"{interp_flags} {row.get('INTERP_FLAGS')}".strip()

        # SABIAN_SYMBOLS (prefer from row, else lookup)
        sabian: str = row.get('Sabian Symbol', '')
        if not sabian and sign and lon_abs is not None:
            # Assumes Sabian symbols are 1-indexed (1 to 30 degrees)
            sabian = self.lookup.get('SABIAN_SYMBOLS', {}).get((sign, int(lon_abs % 30) + 1), '')
        
        # Fixed stars
        fixed_stars = ''
        if self.fixed_star_catalog is not None and lon_abs is not None:
            try:
                find_fixed_star_conjunctions = self.lookup.get('find_fixed_star_conjunctions')
                if find_fixed_star_conjunctions:
                    # Assumes orb is defined or defaulted in the lookup module
                    hits = find_fixed_star_conjunctions(lon_abs, self.fixed_star_catalog, orb=1.0) 
                    if hits:
                        fixed_stars = ', '.join([f"{h['Name']} (orb {h['sep']:.2f}°)" for h in hits])
            except Exception:
                self.missing.append(f"fixedstars:{obj}")

        # --- Compose Text (Removed Redundant Mode Check) ---
        lines = []
        name_line = f"{glyph} **{obj}**"
        if retrograde:
            name_line += " (Rx)"
        if dignity:
            name_line += f" - {dignity}"
        name_line += f" in {sign} {dms}."
        
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
    
    
    def _interpret_axis_pair(self, axis1: str, axis2: str, interp_key: str) -> str:
        """Generates interpretation for a cardinal axis pair (AC/DC, MC/IC, Nodes)."""
        
        # Helper to safely retrieve house/sign info
        def get_row_info(obj_name):
            row = self._get_object_row(obj_name)
            if row is not None:
                house = row.get('Placidus House') or row.get('House') or row.get('Equal House') or row.get('Whole Sign House')
                sign = row.get('Sign')
                return house, sign
            return None, None
            
        # Helper for sorting house numbers for key lookup
        def house_axis_key(val1, val2):
            if val1 is None or val2 is None: return None
            try:
                v1, v2 = int(float(val1)), int(float(val2))
                return f"{min(v1, v2)}-{max(v1, v2)}"
            except Exception:
                return None
        
        # Helper for sorting signs by zodiac order for key lookup
        def sign_axis_key(val1, val2):
            if val1 is None or val2 is None: return None
            zodiac_order = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
            s1, s2 = str(val1).title(), str(val2).title()
            try:
                i1, i2 = zodiac_order.index(s1), zodiac_order.index(s2)
                return f"{zodiac_order[min(i1, i2)]}-{zodiac_order[max(i1, i2)]}"
            except ValueError:
                return f"{min(s1, s2)}-{max(s1, s2)}" # Fallback to alphabetical if non-zodiac signs
        
        # 1. Get Base Interpretation (Compass Aspect)
        interp_text = COMPASS_ASPECT_INTERP.get(interp_key, f"[No axis interpretation for {interp_key}]")
        connector = '↔'
        
        axis_label_map = {
            'Ascendant': ('Ascendant', 'AC'), 'Descendant': ('Descendant', 'DC'),
            'MC': ('Midheaven', 'MC'), 'IC': ('Imum Coeli', 'IC'),
            'North Node': ('North Node', '\u260A'), 'South Node': ('South Node', '\u260B'),
        }

        # 2. Get contextual info
        house_a, sign_a = get_row_info(axis1)
        house_b, sign_b = get_row_info(axis2)
        
        def get_label(axis_name, sign):
            full, abbr = axis_label_map.get(axis_name, (axis_name, axis_name))
            label = f"{full} ({abbr})"
            if sign:
                label += f" in {sign}"
            return label

        label_a = get_label(axis1, sign_a)
        label_b = get_label(axis2, sign_b)
        
        axis_pair_output = [f"**{label_a} {connector} {label_b}**: {interp_text}"]
        
        # 3. Append House Axis Interp
        hkey = house_axis_key(house_a, house_b)
        h_interp = HOUSE_AXIS_INTERP.get(hkey) if hkey else None
        if h_interp:
            axis_pair_output.append(str(h_interp))
        
        # 4. Append Sign Axis Interp
        skey = sign_axis_key(sign_a, sign_b)
        s_interp = SIGN_AXIS_INTERP.get(skey) if skey else None
        if s_interp:
            axis_pair_output.append(str(s_interp))
            
        return '\n'.join(axis_pair_output)


    def _interpret_aspect(self, a: str, b: str, meta: dict) -> str:
        """Generate interpretation for a single aspect."""
        aspect: str = meta.get('aspect', '')
        key: str = aspect.strip().title() if aspect else ''
        
        # 1. Handle axis-to-axis opposition (already covered by _interpret_axis_pair if compass_rose_on)
        # We handle this check implicitly below if the aspect is an Opposition.
        
        # 2. Get Aspect Interpretation (Planet-to-Planet or Planet-to-Axis)
        interp_text = self.lookup.get('ASPECT_INTERP', {}).get(key)
        if not interp_text:
            self.missing.append(f"aspect:{aspect}")
            interp_text = f"[{aspect.title()} aspect]"
            
        connector = 'Opposite' if key == 'Opposition' else key
        out = [f"**{a}** {connector} **{b}**: {interp_text}"]

        # 3. Append House/Sign Axis Interp for all Oppositions
        if key == 'Opposition':
            # This logic is simpler as it reuses the axis pair helpers
            house_a, sign_a = self._get_axis_info(a)
            house_b, sign_b = self._get_axis_info(b)
            
            # --- Re-using Axis Helpers (requires them to be defined inside/accessible) ---
            def house_axis_key(val1, val2):
                if val1 is None or val2 is None: return None
                try:
                    v1, v2 = int(float(val1)), int(float(val2))
                    return f"{min(v1, v2)}-{max(v1, v2)}"
                except Exception:
                    return None
            def sign_axis_key(val1, val2):
                if val1 is None or val2 is None: return None
                zodiac_order = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
                s1, s2 = str(val1).title(), str(val2).title()
                try:
                    i1, i2 = zodiac_order.index(s1), zodiac_order.index(s2)
                    return f"{zodiac_order[min(i1, i2)]}-{zodiac_order[max(i1, i2)]}"
                except ValueError:
                    return f"{min(s1, s2)}-{max(s1, s2)}"
            # --- End Reused Helpers ---

            hkey = house_axis_key(house_a, house_b)
            h_interp = HOUSE_AXIS_INTERP.get(hkey) if hkey else None
            if h_interp:
                out.append(str(h_interp))
                
            skey = sign_axis_key(sign_a, sign_b)
            s_interp = SIGN_AXIS_INTERP.get(skey) if skey else None
            if s_interp:
                out.append(str(s_interp))
                
        return '\n'.join(out)


    def _interpret_circuit(self, objects: List[str], aspects: List[str]) -> str:
        """Synthesize a summary for the whole circuit/cluster."""
        # Placeholder: can be made more sophisticated
        if self.mode == 'poetic':
            return "Together, these forces weave a **unique circuit** of meaning."
        else:
            # Limiting list size for technical summary
            objects_str = ', '.join(objects[:5]) + ('...' if len(objects) > 5 else '')
            aspects_str = ', '.join(list(set(aspects)))
            return f"Circuit summary: Objects **{objects_str}** with aspects **{aspects_str}**."

    def generate(self, mode: Optional[str] = None) -> str:
        """Generate the full interpretation text for the current chart state."""
        if mode:
            self.mode = mode
        if self.ordered_df is None or self.ordered_df.empty:
            return "No objects to interpret."

        output_sections: List[str] = []
        handled_edges: set = set()

        # 1. Interpret objects
        object_texts = [self._interpret_object(row) for _, row in self.ordered_df.iterrows()]
        output_sections.append('## 💫 Object Placements\n' + '\n\n'.join(object_texts))
        
        # 2. Clustered Aspect/Axis Output
        # A. Always check for the three main axis oppositions if compass_rose is on
        if self.state.get('compass_rose_on', False):
            compass_pairs = [
                ('Ascendant', 'Descendant', 'ACDC'),
                ('MC', 'IC', 'MCIC'),
                ('North Node', 'South Node', 'Nodes')
            ]
            axis_texts = []
            for a, b, key in compass_pairs:
                # Only interpret if both axes exist in the DataFrame
                if self._get_object_row(a) is not None and self._get_object_row(b) is not None:
                    axis_texts.append(self._interpret_axis_pair(a, b, key))
                    handled_edges.add(frozenset([a, b]))

            if axis_texts:
                 output_sections.append('## 🧭 Cardinal Axis Interpretations\n' + '\n\n'.join(axis_texts))
        
        # B. Handle Conjunction Clusters (using helper functions from calc_v2)
        clusters, cluster_map, clustered_members = build_conjunction_clusters(self.ordered_df, self.edges_major)
        # Note: Logic to interpret clusters (multi-object groups) needs to be defined
        # For now, we skip individual conjunctions if objects are clustered.
        
        # 3. Individual Aspect Output (Major)
        aspect_texts = []
        for a_orig, b_orig, meta in self.edges_major:
            pair = frozenset([a_orig, b_orig])
            
            # Skip if already handled by axis logic or part of a conjunction cluster
            if pair not in handled_edges and a_orig not in clustered_members and b_orig not in clustered_members:
                aspect_texts.append(self._interpret_aspect(a_orig, b_orig, meta))
        
        if aspect_texts:
            output_sections.append('## ✨ Major Aspects\n' + '\n\n'.join(aspect_texts))
            
        # 4. Synthesize circuit
        objects = list(self.ordered_df['Object'])
        aspects = [meta.get('aspect', '') for _, _, meta in self.edges_major]
        circuit_text = self._interpret_circuit(objects, aspects)
        output_sections.append('## 🌐 Whole Chart Summary\n' + circuit_text)

        # 5. Compose output
        output = '\n\n'.join(output_sections)
        
        # 6. Add missing info footnote
        if self.missing:
            output += f"\n\n---\n**[Data Warnings]** Missing lookups for: {', '.join(self.missing)}"
            
        return output