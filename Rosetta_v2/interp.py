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
from lookup_v2 import COMPASS_ASPECT_INTERP, HOUSE_AXIS_INTERP, SIGN_AXIS_INTERP

class ChartInterpreter:

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
    # Define COMPASS_NAMES and COMPASS_KEYS for axis logic
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
            print(f"[DEBUG] get_compass_axes: input={names}, output={axes}")
            return axes
            # DEBUG: Show available axis interp keys
        print("[DEBUG] HOUSE_AXIS_INTERP keys:", list(HOUSE_AXIS_INTERP.keys()))
        print("[DEBUG] SIGN_AXIS_INTERP keys:", list(SIGN_AXIS_INTERP.keys()))
        """Generate interpretation for a single aspect using ASPECT_INTERP or COMPASS_ASPECT_INTERP."""
        aspect = meta.get('aspect', '')
        compass_rose_on = self.state.get('compass_rose_on', False)
        key = aspect.strip().title() if aspect else ''
        # Use directly imported axis interp dicts
        house_axis_interp = HOUSE_AXIS_INTERP
        sign_axis_interp = SIGN_AXIS_INTERP

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

        axis_pair_found = False
        axis_pair_output = None
        if compass_rose_on:
            for (axis1, axis2), interp_key in axis_pairs:
                names = {a_norm, b_norm}
                if {axis1, axis2} == names:
                    interp_text = COMPASS_ASPECT_INTERP.get(interp_key)
                    connector = '↔'
                    axis_label_map = {
                        'Ascendant': ('Ascendant', 'AC'),
                        'Descendant': ('Descendant', 'DC'),
                        'MC': ('Midheaven', 'MC'),
                        'IC': ('Imum Coeli', 'IC'),
                        'North Node': ('North Node', '\u260A'),  # ☊
                        'South Node': ('South Node', '\u260B'),  # ☋
                    }
                    def get_sign_for_axis(axis_name):
                        if hasattr(self, 'ordered_df') and self.ordered_df is not None:
                            df = self.ordered_df
                            axis_variants = [axis_name]
                            if axis_name == 'Ascendant':
                                axis_variants.append('AC')
                            elif axis_name == 'Descendant':
                                axis_variants.append('DC')
                            elif axis_name == 'MC':
                                axis_variants.append('Mc')
                            elif axis_name == 'IC':
                                axis_variants.append('Ic')
                            for variant in axis_variants:
                                row = df[df['Object'] == variant]
                                if not row.empty:
                                    sign = row.iloc[0].get('Sign')
                                    if sign:
                                        full, abbr = axis_label_map.get(axis_name, (axis_name, axis_name))
                                        return f"{full} ({abbr}) in {sign}"
                        full, abbr = axis_label_map.get(axis_name, (axis_name, axis_name))
                        return f"{full} ({abbr})"
                    label_a = get_sign_for_axis(axis1)
                    label_b = get_sign_for_axis(axis2)
                    axis_pair_output = f"{label_a} {connector} {label_b}: {interp_text}"
                    axis_pair_found = True
                    # Now, append HOUSE_AXIS_INTERP and SIGN_AXIS_INTERP
                    # Get house and sign for both axes
                    def get_row_info(obj_name):
                        if hasattr(self, 'ordered_df') and self.ordered_df is not None:
                            df = self.ordered_df
                            variants = [obj_name]
                            if obj_name == 'Ascendant':
                                variants.append('AC')
                            elif obj_name == 'Descendant':
                                variants.append('DC')
                            elif obj_name == 'MC':
                                variants.append('Mc')
                            elif obj_name == 'IC':
                                variants.append('Ic')
                            for variant in variants:
                                row = df[df['Object'] == variant]
                                if not row.empty:
                                    house = row.iloc[0].get('Placidus House') or row.iloc[0].get('House') or row.iloc[0].get('Equal House') or row.iloc[0].get('Whole Sign House')
                                    sign = row.iloc[0].get('Sign')
                                    return house, sign
                        return None, None
                    house_a, sign_a = get_row_info(axis1)
                    house_b, sign_b = get_row_info(axis2)
                    def house_axis_key(val1, val2):
                        if val1 is None or val2 is None:
                            return None
                        try:
                            v1 = int(float(val1))
                            v2 = int(float(val2))
                            k1, k2 = sorted([v1, v2])
                            key = f"{k1}-{k2}"
                            return key
                        except Exception:
                            k1, k2 = sorted([str(val1), str(val2)])
                            if k1 == 'None' or k2 == 'None':
                                return None
                            key = f"{k1}-{k2}"
                            return key
                    def sign_axis_key(val1, val2):
                        if val1 is None or val2 is None:
                            return None
                        zodiac_order = [
                            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
                        ]
                        s1 = str(val1).title()
                        s2 = str(val2).title()
                        try:
                            i1 = zodiac_order.index(s1)
                            i2 = zodiac_order.index(s2)
                            if i1 < i2:
                                key = f"{s1}-{s2}"
                            else:
                                key = f"{s2}-{s1}"
                            return key
                        except ValueError:
                            key = f"{s1}-{s2}"
                            return key
                    extra_axis_texts = []
                    hkey = house_axis_key(house_a, house_b)
                    if hkey:
                        h_interp = house_axis_interp.get(hkey)
                        if h_interp:
                            extra_axis_texts.append(str(h_interp))
                    skey = sign_axis_key(sign_a, sign_b)
                    if skey:
                        s_interp = sign_axis_interp.get(skey)
                        if s_interp:
                            extra_axis_texts.append(str(s_interp))
                    # Compose final output for axis pair
                    if extra_axis_texts:
                        axis_pair_output += '\n' + '\n'.join(extra_axis_texts)
                    return axis_pair_output

        # Call get_compass_axes and continue with axis interp logic
        def split_names(x):
            return [n.strip() for n in x.replace(' and ', ',').split(',')]

        print(f"[DEBUG] About to split names for a: {a}")
        names_a = split_names(a)
        print(f"[DEBUG] names_a: {names_a}")
        print(f"[DEBUG] About to split names for b: {b}")
        names_b = split_names(b)
        print(f"[DEBUG] names_b: {names_b}")
        print(f"[DEBUG] About to call get_compass_axes for names_a: {names_a}")
        axes_a = get_compass_axes(names_a)
        print(f"[DEBUG] axes_a: {axes_a}")
        print(f"[DEBUG] About to call get_compass_axes for names_b: {names_b}")
        axes_b = get_compass_axes(names_b)
        print(f"[DEBUG] axes_b: {axes_b}")


        # --- Axis/Nodal cluster logic ---
        # If this is a conjunction between nodal axis and MC/IC or AC/DC, output all four as a unit
        aspect_type = meta.get('aspect', '').lower()
        def norm_axis(x):
            return x.replace('AC', 'Ascendant').replace('DC', 'Descendant').replace('Mc', 'MC').replace('Ic', 'IC')
        a_norm = norm_axis(a)
        b_norm = norm_axis(b)
        nodal_set = {'North Node', 'South Node'}
        mcic_set = {'MC', 'IC'}
        acdc_set = {'Ascendant', 'Descendant'}
        chart_objs = set(self.ordered_df['Object']) if self.ordered_df is not None else set()
        chart_axes = set([norm_axis(x) for x in chart_objs])
        # Only cluster for conjunctions
        if aspect_type == 'conjunction':
            # MC/IC + Nodal
            if ((a_norm in nodal_set and b_norm in mcic_set) or (b_norm in nodal_set and a_norm in mcic_set)):
                full_set = (mcic_set | nodal_set) & chart_axes
            # AC/DC + Nodal
            elif ((a_norm in nodal_set and b_norm in acdc_set) or (b_norm in nodal_set and a_norm in acdc_set)):
                full_set = (acdc_set | nodal_set) & chart_axes
            else:
                full_set = None
            if full_set and len(full_set) == 4:
                full_list = sorted(full_set)
                axis_label_map = {
                    'Ascendant': ('Ascendant', 'AC'),
                    'Descendant': ('Descendant', 'DC'),
                    'MC': ('Midheaven', 'MC'),
                    'IC': ('Imum Coeli', 'IC'),
                    'North Node': ('North Node', '\u260A'),
                    'South Node': ('South Node', '\u260B'),
                }
                def get_sign(obj_name):
                    df = self.ordered_df
                    row = df[df['Object'] == obj_name]
                    if not row.empty:
                        return row.iloc[0].get('Sign')
                    return None
                axis_labels = []
                axis_interp_texts = []
                # Output all axis pairs among the four
                for i, axis1 in enumerate(full_list):
                    for axis2 in full_list[i+1:]:
                        sign1 = get_sign(axis1)
                        sign2 = get_sign(axis2)
                        label_a = f"{axis_label_map.get(axis1, (axis1, axis1))[0]} ({axis_label_map.get(axis1, (axis1, axis1))[1]})"
                        if sign1:
                            label_a += f" in {sign1}"
                        label_b = f"{axis_label_map.get(axis2, (axis2, axis2))[0]} ({axis_label_map.get(axis2, (axis2, axis2))[1]})"
                        if sign2:
                            label_b += f" in {sign2}"
                        axis_labels.append(f"{label_a} \u2194 {label_b}")
                        # Use original meta for aspect type
                        axis_interp_texts.append(self.lookup.get('COMPASS_ASPECT_INTERP', {}).get('MCIC' if {axis1, axis2} <= mcic_set else 'Nodes' if {axis1, axis2} <= nodal_set else 'ACDC', '[Axis aspect]'))
                label = "; ".join(axis_labels)
                aspect_text = f"{label}:\n" + "\n\n".join([str(x) for x in axis_interp_texts])
                return aspect_text
        # ...existing code...

        # Only print h_interp after it is assigned, inside the block below
        def split_names(x):
            return [n.strip() for n in x.replace(' and ', ',').split(',')]

        print(f"[DEBUG] About to split names for a: {a}")
        names_a = split_names(a)
        print(f"[DEBUG] names_a: {names_a}")
        print(f"[DEBUG] About to split names for b: {b}")
        names_b = split_names(b)
        print(f"[DEBUG] names_b: {names_b}")
        print(f"[DEBUG] About to call get_compass_axes for names_a: {names_a}")
        axes_a = get_compass_axes(names_a)
        print(f"[DEBUG] axes_a: {axes_a}")
        print(f"[DEBUG] About to call get_compass_axes for names_b: {names_b}")
        axes_b = get_compass_axes(names_b)
        print(f"[DEBUG] axes_b: {axes_b}")
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

        # For all oppositions, append HOUSE_AXIS_INTERP and SIGN_AXIS_INTERP
        extra_axis_texts = []
        if key == 'Opposition':
            # Try to get house and sign for both a and b from the DataFrame, handling abbreviations
            def get_row_info(obj_name):
                if hasattr(self, 'ordered_df') and self.ordered_df is not None:
                    df = self.ordered_df
                    # Try both the name and common abbreviations for axes
                    variants = [obj_name]
                    if obj_name == 'Ascendant':
                        variants.append('AC')
                    elif obj_name == 'Descendant':
                        variants.append('DC')
                    elif obj_name == 'MC':
                        variants.append('Mc')
                    elif obj_name == 'IC':
                        variants.append('Ic')
                    for variant in variants:
                        row = df[df['Object'] == variant]
                        if not row.empty:
                            house = row.iloc[0].get('Placidus House') or row.iloc[0].get('House') or row.iloc[0].get('Equal House') or row.iloc[0].get('Whole Sign House')
                            sign = row.iloc[0].get('Sign')
                            return house, sign
                return None, None
            house_a, sign_a = get_row_info(a)
            house_b, sign_b = get_row_info(b)
            print(f"[DEBUG] get_row_info: a={a}, house_a={house_a}, sign_a={sign_a}; b={b}, house_b={house_b}, sign_b={sign_b}")
            # Compose axis keys for house and sign
            def house_axis_key(val1, val2):
                # Always order as (smaller, larger) for key, skip if None
                if val1 is None or val2 is None:
                    print(f"[DEBUG] house_axis_key: val1={val1}, val2={val2} (None detected)")
                    return None
                try:
                    v1 = int(float(val1))
                    v2 = int(float(val2))
                    k1, k2 = sorted([v1, v2])
                    key = f"{k1}-{k2}"
                    print(f"[DEBUG] house_axis_key: sorted ints {k1}, {k2} -> key={key}")
                    return key
                except Exception:
                    k1, k2 = sorted([str(val1), str(val2)])
                    if k1 == 'None' or k2 == 'None':
                        print(f"[DEBUG] house_axis_key: k1 or k2 is 'None' -> skip")
                        return None
                    key = f"{k1}-{k2}"
                    print(f"[DEBUG] house_axis_key: sorted strings {k1}, {k2} -> key={key}")
                    return key
            def sign_axis_key(val1, val2):
                # Normalize to title case and sort by zodiac order
                if val1 is None or val2 is None:
                    print(f"[DEBUG] sign_axis_key: val1={val1}, val2={val2} (None detected)")
                    return None
                zodiac_order = [
                    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
                ]
                s1 = str(val1).title()
                s2 = str(val2).title()
                try:
                    i1 = zodiac_order.index(s1)
                    i2 = zodiac_order.index(s2)
                    if i1 < i2:
                        key = f"{s1}-{s2}"
                    else:
                        key = f"{s2}-{s1}"
                    print(f"[DEBUG] sign_axis_key: sorted by zodiac {s1}, {s2} -> key={key}")
                    return key
                except ValueError:
                    key = f"{s1}-{s2}"
                    print(f"[DEBUG] sign_axis_key: ValueError, fallback to key={key}")
                    return key
            # House axis interp
            hkey = house_axis_key(house_a, house_b)
            print(f"[DEBUG] HOUSE_AXIS_INTERP keys: {list(house_axis_interp.keys())}")
            print(f"[DEBUG] Generated house axis key: {hkey}")
            if hkey:
                print(f"[DEBUG] HOUSE_AXIS_INTERP found: {hkey in house_axis_interp}")
                h_interp = house_axis_interp.get(hkey)
                print(f"[DEBUG] HOUSE_AXIS_INTERP lookup result: {h_interp}")
                if h_interp:
                    extra_axis_texts.append(str(h_interp))
            # Sign axis interp
            skey = sign_axis_key(sign_a, sign_b)
            print(f"[DEBUG] SIGN_AXIS_INTERP keys: {list(sign_axis_interp.keys())}")
            print(f"[DEBUG] Generated sign axis key: {skey}")
            if skey:
                print(f"[DEBUG] SIGN_AXIS_INTERP found: {skey in sign_axis_interp}")
                s_interp = sign_axis_interp.get(skey)
                print(f"[DEBUG] SIGN_AXIS_INTERP lookup result: {s_interp}")
                if s_interp:
                    extra_axis_texts.append(str(s_interp))
        # Compose output
        out = f"{a} {connector} {b}: {interp_text}"
        if extra_axis_texts:
            out += '\n' + '\n'.join(extra_axis_texts)
        return out

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
        # 2. Clustered aspect output: output only one entry per cluster (axis pair + conjuncts), no redundant aspects for cluster members
        aspect_texts = []
        clustered_pairs = set()
        clustered_members = set()
        compass_rose_on = self.state.get('compass_rose_on', False)
        try:
            from calc_v2 import build_clustered_aspect_edges, build_conjunction_clusters
            only_compass = False
            visible_objs = set(self.ordered_df['Object']) if self.ordered_df is not None else set()
            compass_set = {'Ascendant', 'Descendant', 'MC', 'IC', 'North Node', 'South Node'}
            if compass_rose_on and visible_objs.issubset(compass_set):
                only_compass = True
            clustered_edges = build_clustered_aspect_edges(self.ordered_df, self.edges_major)
            clusters, cluster_map, cluster_sets = build_conjunction_clusters(self.ordered_df, self.edges_major)
            print("[DEBUG] clusters:", clusters)
            print("[DEBUG] cluster_map:", cluster_map)
            print("[DEBUG] cluster_sets:", cluster_sets)
            # Track all cluster members
            for s in cluster_sets:
                clustered_members.update(s)
        except Exception as e:
            aspect_texts.append(f"[Error in clustered aspect logic: {e}]")
        # 3. Add aspects between objects not in any cluster (i.e., both a and b are not in clustered_members)
        for a, b, meta in self.edges_major:
            if (a not in clustered_members) and (b not in clustered_members):
                if frozenset([a, b]) not in clustered_pairs:
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
