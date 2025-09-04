# rosetta/helpers.py
import numpy as np
import pandas as pd
import networkx as nx
from itertools import combinations
from rosetta.lookup import ASPECTS, GROUP_COLORS, GLYPHS, OBJECT_MEANINGS

# -------------------------------
# Basic math + angle helpers
# -------------------------------
def deg_to_rad(deg, asc_shift=0):
    """Convert degrees to radians for polar chart positioning"""
    return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)

def get_ascendant_degree(df):
    """Find Ascendant degree from CSV data"""
    for search_term in ["Ascendant", "ascendant", "AC"]:
        asc_row = df[df["Object"].str.contains(search_term, case=False, na=False)]
        if not asc_row.empty:
            return float(asc_row["Computed Absolute Degree"].values[0])
    return 0

# -------------------------------
# Graph construction
# -------------------------------
def build_aspect_graph(pos):
    """Find connected components of planets based on major aspects"""
    G = nx.Graph()
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2])
        if angle > 180:
            angle = 360 - angle

        # Only check major aspects for patterns
        major_aspects = ["Conjunction", "Sextile", "Square", "Trine", "Opposition"]
        for asp in major_aspects:
            if abs(ASPECTS[asp]["angle"] - angle) <= ASPECTS[asp]["orb"]:
                G.add_edge(p1, p2, aspect=asp)
                break
    return list(nx.connected_components(G))

def detect_minor_links_with_singletons(pos, patterns):
    """Find minor aspect connections and map singletons"""
    minor_aspects = ["Quincunx", "Sesquisquare"]
    connections = []

    # Map planet → pattern index
    pattern_map = {}
    for idx, pattern in enumerate(patterns):
        for planet in pattern:
            pattern_map[planet] = idx

    # Singletons = placements not in any pattern
    all_patterned = set(pattern_map.keys())
    all_placements = set(pos.keys())
    singletons = all_placements - all_patterned
    singleton_index_offset = len(patterns)
    singleton_map = {
        planet: singleton_index_offset + i for i, planet in enumerate(singletons)
    }
    pattern_map.update(singleton_map)

    # Find minor aspect links
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2])
        if angle > 180:
            angle = 360 - angle

        for asp in minor_aspects:
            if abs(ASPECTS[asp]["angle"] - angle) <= ASPECTS[asp]["orb"]:
                pat1 = pattern_map.get(p1)
                pat2 = pattern_map.get(p2)
                if pat1 is not None and pat2 is not None:
                    connections.append((p1, p2, asp, pat1, pat2))
                break
    return connections, singleton_map

def generate_combo_groups(filaments):
    """Generate combination groups from filament connections"""
    G = nx.Graph()
    for _, _, _, pat1, pat2 in filaments:
        if pat1 != pat2:
            G.add_edge(pat1, pat2)
    return [sorted(list(g)) for g in nx.connected_components(G) if len(g) > 1]

# -------------------------------
# Drawing helpers
# -------------------------------
def draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode):
    """Draw house cusp lines on the chart"""
    if use_placidus:
        cusp_rows = df[df["Object"].str.match(r"^\d{1,2}H Cusp$", na=False)]
        for i, (_, row) in enumerate(cusp_rows.iterrows()):
            if pd.notna(row["Computed Absolute Degree"]):
                deg = float(row["Computed Absolute Degree"])
                rad = deg_to_rad(deg, asc_deg)
                ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="dashed", linewidth=1)
                ax.text(rad - np.deg2rad(5), 0.2, str(i + 1), ha="center", va="center",
                       fontsize=8, color="white" if dark_mode else "black")
    else:
        for i in range(12):
            deg = (asc_deg + i * 30) % 360
            rad = deg_to_rad(deg, asc_deg)
            ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="solid", linewidth=1)
            ax.text(rad - np.deg2rad(5), 0.2, str(i + 1), ha="center", va="center",
                   fontsize=8, color="white" if dark_mode else "black")

def draw_degree_markers(ax, asc_deg, dark_mode):
    for deg in range(0, 360, 10):
        rad = deg_to_rad(deg, asc_deg)
        ax.plot([rad, rad], [1.02, 1.08], color="white" if dark_mode else "black", linewidth=1)
        ax.text(rad, 1.12, f"{deg % 30}°", ha="center", va="center", fontsize=7,
               color="white" if dark_mode else "black")

def draw_zodiac_signs(ax, asc_deg):
    from rosetta.lookup import ZODIAC_SIGNS, ZODIAC_COLORS, MODALITIES
    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)
        ax.text(rad, 1.50, ZODIAC_SIGNS[i], ha="center", va="center",
               fontsize=16, fontweight="bold", color=ZODIAC_COLORS[i])
        ax.text(rad, 1.675, MODALITIES[i], ha="center", va="center",
               fontsize=6, color="dimgray")

def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode):
    degree_threshold = 3
    sorted_pos = sorted(pos.items(), key=lambda x: x[1])
    clustered = []
    for name, degree in sorted_pos:
        placed = False
        for cluster in clustered:
            if abs(degree - cluster[0][1]) <= degree_threshold:
                cluster.append((name, degree))
                placed = True
                break
        if not placed:
            clustered.append([(name, degree)])
    for cluster in clustered:
        for i, (name, degree) in enumerate(cluster):
            rad = deg_to_rad(degree, asc_deg)
            offset = 1.30 + i * 0.06
            label = name if label_style == "Text" else GLYPHS.get(name, name)
            ax.text(rad, offset, label, ha="center", va="center", fontsize=9,
                   color="white" if dark_mode else "black")

def draw_aspect_lines(ax, pos, patterns, active_patterns, asc_deg, group_colors=GROUP_COLORS):
    single_pattern_mode = len(active_patterns) == 1
    for idx, pattern in enumerate(patterns):
        if idx not in active_patterns:
            continue
        keys = list(pattern)
        for i1 in range(len(keys)):
            for i2 in range(i1 + 1, len(keys)):
                p1, p2 = keys[i1], keys[i2]
                angle = abs(pos[p1] - pos[p2])
                if angle > 180:
                    angle = 360 - angle
                for asp in ["Conjunction", "Sextile", "Square", "Trine", "Opposition"]:
                    asp_data = ASPECTS[asp]
                    if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                        r1 = deg_to_rad(pos[p1], asc_deg)
                        r2 = deg_to_rad(pos[p2], asc_deg)
                        line_color = asp_data["color"] if single_pattern_mode else group_colors[idx % len(group_colors)]
                        ax.plot([r1, r2], [1, 1], linestyle=asp_data["style"], color=line_color, linewidth=2)
                        break

def draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg):
    single_pattern_mode = len(active_patterns) == 1
    for p1, p2, asp_name, pat1, pat2 in filaments:
        if pat1 in active_patterns and pat2 in active_patterns:
            if single_pattern_mode and pat1 != pat2:
                continue
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot([r1, r2], [1, 1], linestyle="dotted",
                   color=ASPECTS[asp_name]["color"], linewidth=1)

# -------------------------------
# Profiles
# -------------------------------
def format_planet_profile(row):
    name = row["Object"]
    meaning = OBJECT_MEANINGS.get(name, "")
    dignity = row.get("Dignity", "")
    retro = row.get("Retrograde", "")
    sabian = row.get("Sabian Symbol", "")
    fixed_star = row.get("Fixed Star Conjunction", "")
    oob = row.get("OOB Status", "")
    sign = row.get("Sign", "")
    lon = row.get("Longitude", "")

    header = f"{GLYPHS.get(name, '')} {name}"
    if str(dignity).strip().lower() not in ["none", "nan", ""]:
        header += f" ({dignity})"
    if str(retro).strip().lower() == "rx":
        header += " Retrograde"

    html_parts = [f'<div style="margin-bottom: 8px;">{header}</div>']
    if meaning:
        html_parts.append(f'<div style="margin-bottom: 4px;"><strong>{meaning}</strong></div>')
    if sabian and str(sabian).strip().lower() not in ["none", "nan", ""]:
        html_parts.append(f'<div style="margin-bottom: 4px; font-style: italic;">"{sabian}"</div>')
    if sign and lon:
        pos_line = f"{sign} {lon}"
        if str(retro).strip().lower() == "rx":
            pos_line += " Rx"
        html_parts.append(f'<div style="margin-bottom: 6px;">{pos_line}</div>')

    details = []
    for label, value in [
        ("Out Of Bounds", oob),
        ("Conjunct Fixed Star", fixed_star),
        ("Speed", row.get("Speed", "")),
        ("Latitude", row.get("Latitude", "")),
        ("Declination", row.get("Declination", "")),
    ]:
        if str(value).strip().lower() not in ["none", "nan", "", "no"]:
            details.append(f'<div style="margin-bottom: 2px; font-size: 0.9em;">{label}: {value}</div>')
    if details:
        html_parts.extend(details)

    return ''.join(html_parts)
