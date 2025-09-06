# rosetta5.py — full UI + live calculate_chart

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import streamlit.components.v1 as components
from itertools import combinations
import datetime
import swisseph as swe

from rosetta.calc import calculate_chart
from rosetta.lookup import (
    GLYPHS, ASPECTS, MAJOR_OBJECTS, OBJECT_MEANINGS,
    GROUP_COLORS, ASPECT_INTERPRETATIONS
)
from rosetta.helpers import get_ascendant_degree, deg_to_rad
from rosetta.drawing import (
    draw_house_cusps, draw_degree_markers, draw_zodiac_signs,
    draw_planet_labels, draw_aspect_lines, draw_filament_lines,
    draw_shape_edges, draw_minor_edges,
)
from rosetta.patterns import (
    detect_minor_links_with_singletons, generate_combo_groups,
    detect_shapes, internal_minor_edges_for_pattern,
    connected_components_from_edges,
)
import rosetta.patterns
print(">>> patterns.py loaded from:", rosetta.patterns.__file__)

# -------------------------
# Chart Math + Pattern Utils
# -------------------------
import networkx as nx
from itertools import combinations
from rosetta.lookup import GLYPHS, ASPECTS, ZODIAC_SIGNS, ZODIAC_COLORS, MODALITIES, GROUP_COLORS
from rosetta.helpers import deg_to_rad

def build_aspect_graph(pos):
    """Find connected components of planets based on major aspects only."""
    G = nx.Graph()
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2])
        if angle > 180:
            angle = 360 - angle
        for asp in ("Conjunction", "Sextile", "Square", "Trine", "Opposition"):
            asp_data = ASPECTS[asp]
            if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                G.add_edge(p1, p2, aspect=asp)
                break
    return list(nx.connected_components(G))

def detect_minor_links_with_singletons(pos, patterns):
    """Find quincunx/sesquisquare links and track singleton placements."""
    minor_aspects = ["Quincunx", "Sesquisquare"]
    connections = []

    # map planets → parent pattern index
    pattern_map = {}
    for idx, pattern in enumerate(patterns):
        for planet in pattern:
            pattern_map[planet] = idx

    all_patterned = set(pattern_map.keys())
    all_placements = set(pos.keys())
    singletons = all_placements - all_patterned
    singleton_index_offset = len(patterns)
    singleton_map = {
        planet: singleton_index_offset + i for i, planet in enumerate(singletons)
    }
    pattern_map.update(singleton_map)

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
    """Group patterns connected by minor aspects into combos."""
    G = nx.Graph()
    for _, _, _, pat1, pat2 in filaments:
        if pat1 != pat2:
            G.add_edge(pat1, pat2)
    return [sorted(list(g)) for g in nx.connected_components(G) if len(g) > 1]

# -------------------------
# Chart Drawing Functions
# -------------------------

def draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode):
    """Draw house cusp lines (Placidus or Equal)."""
    import pandas as pd
    if use_placidus:
        cusp_rows = df[df["Object"].str.match(r"^\d{1,2}H Cusp$", na=False)]
        for i, (_, row) in enumerate(cusp_rows.iterrows()):
            if pd.notna(row["abs_deg"]):
                deg = float(row["abs_deg"])
                rad = deg_to_rad(deg, asc_deg)
                ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="dashed", linewidth=1)
                ax.text(rad - 0.05, 0.2, str(i+1),
                        ha="center", va="center", fontsize=8,
                        color="white" if dark_mode else "black")
    else:
        for i in range(12):
            deg = (asc_deg + i * 30) % 360
            rad = deg_to_rad(deg, asc_deg)
            ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="solid", linewidth=1)
            ax.text(rad - 0.05, 0.2, str(i+1),
                    ha="center", va="center", fontsize=8,
                    color="white" if dark_mode else "black")

def draw_degree_markers(ax, asc_deg, dark_mode):
    """Draw small tick marks every 10° with labels."""
    for deg in range(0, 360, 10):
        rad = deg_to_rad(deg, asc_deg)
        ax.plot([rad, rad], [1.02, 1.08],
                color="white" if dark_mode else "black", linewidth=1)
        ax.text(rad, 1.12, f"{deg % 30}°",
                ha="center", va="center", fontsize=7,
                color="white" if dark_mode else "black")

def draw_zodiac_signs(ax, asc_deg):
    """Draw zodiac signs + modalities around the wheel."""
    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)
        ax.text(rad, 1.50, ZODIAC_SIGNS[i], ha="center", va="center",
                fontsize=16, fontweight="bold", color=ZODIAC_COLORS[i])
        ax.text(rad, 1.675, MODALITIES[i], ha="center", va="center",
                fontsize=6, color="dimgray")

def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode):
    """Label planets/points, clustered to avoid overlap."""
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
            ax.text(rad, offset, label,
                    ha="center", va="center", fontsize=9,
                    color="white" if dark_mode else "black")

def draw_aspect_lines(ax, pos, patterns, active_patterns, asc_deg,
                      group_colors=None, edges=None):
    """Draw major aspect lines for active patterns."""
    single_pattern_mode = len(active_patterns) == 1
    for idx, pattern in enumerate(patterns):
        if idx not in active_patterns:
            continue
        keys = list(pattern)
        for i1 in range(len(keys)):
            for i2 in range(i1+1, len(keys)):
                p1, p2 = keys[i1], keys[i2]
                angle = abs(pos[p1] - pos[p2])
                if angle > 180:
                    angle = 360 - angle
                for asp in ("Conjunction","Sextile","Square","Trine","Opposition"):
                    asp_data = ASPECTS[asp]
                    if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                        r1 = deg_to_rad(pos[p1], asc_deg)
                        r2 = deg_to_rad(pos[p2], asc_deg)
                        line_color = (asp_data["color"] if single_pattern_mode
                                      else GROUP_COLORS[idx % len(GROUP_COLORS)])
                        ax.plot([r1, r2], [1, 1],
                                linestyle=asp_data["style"],
                                color=line_color, linewidth=2)
                        break

def draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg):
    """Draw dotted lines for minor aspects between active patterns."""
    single_pattern_mode = len(active_patterns) == 1
    for p1, p2, asp_name, pat1, pat2 in filaments:
        if pat1 in active_patterns and pat2 in active_patterns:
            if single_pattern_mode and pat1 != pat2:
                continue
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot([r1, r2], [1, 1], linestyle="dotted",
                    color=ASPECTS[asp_name]["color"], linewidth=1)

# -------------------------
# Init / session management
# -------------------------
if "reset_done" not in st.session_state:
    st.session_state.clear()
    st.session_state["reset_done"] = True

st.set_page_config(layout="wide")
st.markdown(
    """
    <style>
    /* tighten planet profile line spacing */
    .planet-profile div {
        line-height: 1.1;   /* normal single-space */
        margin-bottom: 2px; /* tiny gap only */
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("🧭 Rosetta Flight Deck")

# Choose how to show planet labels
label_style = st.radio(
    "Label Style",
    ["Text", "Glyph"],
    index=1,
    horizontal=True
)

# --- Custom CSS tweaks ---
st.markdown(
    """
    <style>
    /* Force tighter spacing inside planet profile blocks */
    div.planet-profile div {
        line-height: 1.1 !important;
        margin-bottom: 0px !important;
        padding-bottom: 0px !important;
    }
    div.planet-profile {
        margin-bottom: 4px !important;  /* small gap between profiles */
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --------------------------------
# Simple caches to avoid recompute
# --------------------------------
_cache_major_edges = {}
_cache_shapes = {}

def get_major_edges_and_patterns(pos):
    """
    Build master list of major edges from positions, then cluster into patterns.
    """
    pos_items_tuple = tuple(sorted(pos.items()))
    if pos_items_tuple not in _cache_major_edges:
        temp_edges = []
        planets = list(pos.keys())
        for i in range(len(planets)):
            for j in range(i + 1, len(planets)):
                p1, p2 = planets[i], planets[j]
                d1, d2 = pos.get(p1), pos.get(p2)
                if d1 is None or d2 is None:
                    continue
                angle = abs(d1 - d2) % 360
                if angle > 180:
                    angle = 360 - angle
                for aspect in ("Conjunction", "Sextile", "Square", "Trine", "Opposition"):
                    data = ASPECTS[aspect]
                    if abs(angle - data["angle"]) <= data["orb"]:
                        temp_edges.append(((p1, p2), aspect))
                        break
        patterns = connected_components_from_edges(list(pos.keys()), temp_edges)
        _cache_major_edges[pos_items_tuple] = (tuple(temp_edges), patterns)
    return _cache_major_edges[pos_items_tuple]

def get_shapes(pos, patterns, major_edges_all):
    pos_items_tuple = tuple(sorted(pos.items()))
    patterns_key = tuple(tuple(sorted(p)) for p in patterns)
    edges_tuple = tuple(major_edges_all)
    key = (pos_items_tuple, patterns_key, edges_tuple)
    if key not in _cache_shapes:
        _cache_shapes[key] = detect_shapes(pos, patterns, major_edges_all)
    return _cache_shapes[key]

SUBSHAPE_COLORS = [
    "#FF5214", "#FFA600", "#FBFF00", "#87DB00",
    "#00B828", "#049167", "#006EFF", "#1100FF",
    "#6320FF", "#9E0099", "#FF00EA", "#720022",
    "#4B2C06", "#534546", "#C4A5A5", "#5F7066",
]

from rosetta.lookup import GLYPHS

SIGN_NAMES = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
]

def format_longitude(lon):
    """Turn decimal degrees into Sign + degree°minute′ string."""
    sign_index = int(lon // 30)
    deg_in_sign = lon % 30
    deg = int(deg_in_sign)
    minutes = int(round((deg_in_sign - deg) * 60))
    return f"{SIGN_NAMES[sign_index]} {deg}°{minutes:02d}′"

def format_planet_profile(row):
    """Styled planet profile with glyphs, line breaks, and conditional extras."""
    name = row["Object"]
    glyph = GLYPHS.get(name, "")
    sabian = str(row.get("Sabian Symbol", "")).strip()
    lon = row.get("Longitude", "")

    html_parts = []

    # --- Header (glyph + bold name) ---
    header = f"<div style='font-weight:bold; font-size:1.1em;'>{glyph} {name}</div>"
    html_parts.append(header)

    # --- Sabian Symbol (italic, if present) ---
    if sabian and sabian.lower() not in ["none", "nan"]:
        html_parts.append(f"<div style='font-style:italic;'>“{sabian}”</div>")

    # --- Longitude (bold) ---
    if lon != "":
        try:
            lon_f = float(lon)
            formatted = format_longitude(lon_f)
        except Exception:
            formatted = str(lon)
        html_parts.append(f"<div style='font-weight:bold;'>{formatted}</div>")

    # --- Extra details (only if present) ---
    for label, value in [
        ("Speed", row.get("Speed", "")),
        ("Latitude", row.get("Latitude", "")),
        ("Declination", row.get("Declination", "")),
        ("Out of Bounds", row.get("OOB Status", "")),
        ("Conjunct Fixed Star", row.get("Fixed Star Conjunction", "")),
    ]:
        val_str = str(value).strip()
        if not val_str or val_str.lower() in ["none", "nan", "no"]:
            continue
        try:
            if float(val_str) == 0.0:
                continue
        except Exception:
            pass
        html_parts.append(f"<div style='font-size:0.9em;'>{label}: {val_str}</div>")

    # ✅ Force single spacing with line-height here
    return "<div style='line-height:1.1; margin-bottom:6px;'>" + "".join(html_parts) + "</div>"

def draw_zodiac_signs(ax, asc_deg):
    """Draw zodiac sign symbols around the chart"""
    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)
        ax.text(rad, 1.50, ZODIAC_SIGNS[i], ha="center", va="center",
               fontsize=16, fontweight="bold", color=ZODIAC_COLORS[i])
        ax.text(rad, 1.675, MODALITIES[i], ha="center", va="center",
               fontsize=6, color="dimgray")
# --- CHART RENDERER (full)
def render_chart_with_shapes(
    pos, patterns, pattern_labels, toggles,
    filaments, combo_toggles, label_style, singleton_map, df,
    use_placidus, dark_mode, shapes, shape_toggles_by_parent, singleton_toggles,
    major_edges_all
):
    asc_deg = get_ascendant_degree(df)
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.25)
    ax.axis("off")

    # Base wheel
    draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode)
    draw_degree_markers(ax, asc_deg, dark_mode)
    draw_zodiac_signs(ax, asc_deg)
    draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode)

    active_parents = set(i for i, show in enumerate(toggles) if show)
    active_shape_ids = [s['id'] for parent, entries in shape_toggles_by_parent.items()
                        for s in entries if s['on']]
    active_shapes = [s for s in shapes if s["id"] in active_shape_ids]

    # collect active singletons
    active_singletons = {obj for obj, on in singleton_toggles.items() if on}
    visible_objects = set()

    # Build set of edges already claimed by active sub-shapes
    shape_edges = {
        frozenset((u, v))
        for s in active_shapes
        for (u, v), asp in s["edges"]
    }

    # parents first (major edges)
    for idx in active_parents:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])
            if active_parents:
                # draw only edges inside active patterns, using master edge list
                draw_aspect_lines(ax, pos, patterns, active_patterns=active_parents,
                                  asc_deg=asc_deg, group_colors=GROUP_COLORS,
                                  edges=major_edges_all)

                # optional: internal minors for those parents + filaments that connect active endpoints
                for idx in active_parents:
                    _ = internal_minor_edges_for_pattern(pos, list(patterns[idx]))
                    for (p1, p2, asp_name, pat1, pat2) in filaments:
                        # skip if this link is part of a visible sub-shape already
                        if frozenset((p1, p2)) in shape_edges:
                            continue

                        # endpoint visibility logic
                        in_parent1 = any((i in active_parents) and (p1 in patterns[i]) for i in active_parents)
                        in_parent2 = any((i in active_parents) and (p2 in patterns[i]) for i in active_parents)
                        in_shape1 = any(p1 in s["members"] for s in active_shapes)
                        in_shape2 = any(p2 in s["members"] for s in active_shapes)
                        in_singleton1 = p1 in active_singletons
                        in_singleton2 = p2 in active_singletons

                        if (in_parent1 or in_shape1 or in_singleton1) and (in_parent2 or in_shape2 or in_singleton2):
                            r1 = deg_to_rad(pos[p1], asc_deg)
                            r2 = deg_to_rad(pos[p2], asc_deg)
                            ax.plot(
                                [r1, r2], [1, 1],
                                linestyle="dotted",
                                color=ASPECTS[asp_name]["color"],
                                linewidth=1
                            )

    # sub-shapes
    for s in active_shapes:
        visible_objects.update(s["members"])

    # stable colors for sub-shapes
    if "shape_color_map" not in st.session_state:
        st.session_state.shape_color_map = {}
    for s in shapes:
        if s["id"] not in st.session_state.shape_color_map:
            idx = len(st.session_state.shape_color_map) % len(SUBSHAPE_COLORS)
            st.session_state.shape_color_map[s["id"]] = SUBSHAPE_COLORS[idx]

    for s in active_shapes:
        draw_shape_edges(
            ax, pos, s["edges"], asc_deg,
            use_aspect_colors=False,
            override_color=st.session_state.shape_color_map[s["id"]]
        )

    # singletons
    visible_objects.update(active_singletons)

    # connectors (filaments) not already claimed by shapes
    for (p1, p2, asp_name, pat1, pat2) in filaments:
        if frozenset((p1, p2)) in shape_edges:
            continue
        in_parent1 = any((i in active_parents) and (p1 in patterns[i]) for i in active_parents)
        in_parent2 = any((i in active_parents) and (p2 in patterns[i]) for i in active_parents)
        in_shape1 = any(p1 in s["members"] for s in active_shapes)
        in_shape2 = any(p2 in s["members"] for s in active_shapes)
        in_singleton1 = p1 in active_singletons
        in_singleton2 = p2 in active_singletons
        if (in_parent1 or in_shape1 or in_singleton1) and (in_parent2 or in_shape2 or in_singleton2):
            r1 = deg_to_rad(pos[p1], asc_deg); r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot([r1, r2], [1, 1], linestyle="dotted",
                    color=ASPECTS[asp_name]["color"], linewidth=1)

    return fig, visible_objects, active_shapes

from datetime import datetime
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

with st.expander("Enter Birth Data"):
    col1, col2 = st.columns(2)

    # --- Left side: Date & Time ---
    with col1:
        current_year = datetime.now().year
        years = list(range(1900, current_year + 50))
        year = st.number_input("Year", min_value=1000, max_value=3000, value=2000, step=1)
        month = st.selectbox("Month", list(range(1, 13)), index=0)  # July default
        day = st.selectbox("Day", list(range(1, 32)), index=0)     # 29th default
        hour = st.selectbox("Hour", list(range(0, 24)), index=12)
        minute = st.selectbox("Minute", list(range(0, 60)), index=00)

    # --- Right side: Location ---
    with col2:
        city_name = st.text_input("City of Birth", value="")
        lat, lon, tz_name = None, None, None

        if city_name:
            geolocator = Nominatim(user_agent="rosetta")
            try:
                location = geolocator.geocode(city_name)
                if location:
                    st.success(f"Found: {location.address}")
                    lat, lon = location.latitude, location.longitude

                    tf = TimezoneFinder()
                    tz_name = tf.timezone_at(lng=lon, lat=lat)
                    st.write(f"Timezone: {tz_name}")
                else:
                    st.error("City not found. Try a more specific query.")
            except Exception as e:
                st.error(f"Lookup error: {e}")

# ------------------------
# Calculate Chart Button
# ------------------------
if st.button("Calculate Chart"):
    if lat is None or lon is None or tz_name is None:
        st.error("Please enter a valid city and make sure lookup succeeds.")
    else:
        try:
            df = calculate_chart(
                int(year), int(month), int(day),
                int(hour), int(minute),
                0.0,      # dummy tz_offset (real tz handled by tz_name)
                lat, lon,
                input_is_ut=False,
                tz_name=tz_name
            )
            df["abs_deg"] = df["Longitude"].astype(float)

            # positions for chart (major objects only)
            df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
            pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))

            # aspects/patterns/shapes
            major_edges_all, patterns = get_major_edges_and_patterns(pos)
            shapes = get_shapes(pos, patterns, major_edges_all)
            filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
            combos = generate_combo_groups(filaments)

            # --- Save to session for persistence ---
            st.session_state.chart_ready = True
            st.session_state.df = df
            st.session_state.pos = pos
            st.session_state.patterns = patterns
            st.session_state.major_edges_all = major_edges_all 
            st.session_state.shapes = shapes
            st.session_state.filaments = filaments
            st.session_state.singleton_map = singleton_map
            st.session_state.combos = combos

        except Exception as e:
            st.error(f"Chart calculation failed: {e}")
            st.session_state.chart_ready = False

# ------------------------
# If chart data exists, render the chart UI
# ------------------------
if st.session_state.get("chart_ready", False):
    df = st.session_state.df
    pos = st.session_state.pos
    patterns = st.session_state.patterns
    major_edges_all = st.session_state.major_edges_all
    shapes = st.session_state.shapes
    filaments = st.session_state.filaments
    singleton_map = st.session_state.singleton_map
    combos = st.session_state.combos

    # --- UI Layout (restored) ---
    left_col, right_col = st.columns([2, 1])
    with left_col:
        st.subheader("Circuits")

        # Show/Hide all buttons
        col_all1, col_all2 = st.columns([1, 1])
        with col_all1:
            if st.button("Show All"):
                for i in range(len(patterns)):
                    st.session_state[f"toggle_pattern_{i}"] = True
                    for sh in [sh for sh in shapes if sh["parent"] == i]:
                        members_key = "_".join(sorted(str(m) for m in sh["members"]))
                        unique_key = f"shape_{i}_{sh['id']}_{sh['type']}_{members_key}"
                        st.session_state[unique_key] = True
                for planet in singleton_map.keys():
                    st.session_state[f"singleton_{planet}"] = True
        with col_all2:
            if st.button("Hide All"):
                for i in range(len(patterns)):
                    st.session_state[f"toggle_pattern_{i}"] = False
                    for sh in [sh for sh in shapes if sh["parent"] == i]:
                        members_key = "_".join(sorted(str(m) for m in sh["members"]))
                        unique_key = f"shape_{i}_{sh['id']}_{sh['type']}_{members_key}"
                        st.session_state[unique_key] = False
                for planet in singleton_map.keys():
                    st.session_state[f"singleton_{planet}"] = False

        # Pattern checkboxes + expanders
        toggles, pattern_labels = [], []
        half = (len(patterns) + 1) // 2
        left_patterns, right_patterns = st.columns(2)

        for i, component in enumerate(patterns):
            target_col = left_patterns if i < half else right_patterns
            checkbox_key = f"toggle_pattern_{i}"
            label = f"Circuit {i+1}: {', '.join(component)}"

            with target_col:
                cbox = st.checkbox("", key=checkbox_key)
                toggles.append(cbox)
                pattern_labels.append(label)

                with st.expander(label, expanded=False):
                    parent_shapes = [sh for sh in shapes if sh["parent"] == i]
                    if parent_shapes:
                        st.markdown("**Sub-shapes detected:**")
                        shape_entries = []
                        for sh in parent_shapes:
                            members_str = ", ".join(str(m) for m in sh["members"])
                            label_text = f"{sh['type']}: {members_str}"
                            members_key = "_".join(sorted(str(m) for m in sh["members"]))
                            unique_key = f"shape_{i}_{sh['id']}_{sh['type']}_{members_key}"
                            # Only pass value= if Streamlit doesn't already know this key
                            if unique_key not in st.session_state:
                                on = st.checkbox(label_text, value=False, key=unique_key)
                            else:
                                on = st.checkbox(label_text, key=unique_key)

                            shape_entries.append({"id": sh["id"], "on": on})
                    else:
                        st.markdown("_(no sub-shapes found)_")

                    if "shape_toggles_by_parent" not in st.session_state:
                        st.session_state.shape_toggles_by_parent = {}
                    st.session_state.shape_toggles_by_parent[i] = shape_entries

    with right_col:
        st.subheader("Singletons")
        singleton_toggles = {}
        if singleton_map:
            cols_per_row = min(8, max(1, len(singleton_map)))
            cols = st.columns(cols_per_row)
            for j, (planet, _) in enumerate(singleton_map.items()):
                with cols[j % cols_per_row]:
                    key = f"singleton_{planet}"
                    if key not in st.session_state:
                        on = st.checkbox(GLYPHS.get(planet, planet), value=False, key=key)
                    else:
                        on = st.checkbox(GLYPHS.get(planet, planet), key=key)

                    singleton_toggles[planet] = on
        else:
            st.markdown("_(none)_")

        st.subheader("Expansion Options")
        st.checkbox("Show Minor Asteroids", value=False)
        st.markdown("#### Harmonics")
        cols = st.columns(6)
        for j, label in enumerate(["5", "7", "9", "10", "11", "12"]):
            cols[j].checkbox(label, value=False, key=f"harmonic_{label}")

    use_placidus = st.checkbox("Use Placidus House Cusps", value=False)
    dark_mode = st.checkbox("🌙 Dark Mode", value=False)

    shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
    if not singleton_toggles:
        singleton_toggles = {p: st.session_state.get(f"singleton_{p}", False) for p in singleton_map}

    # --- Render the chart ---
    fig, visible_objects, active_shapes = render_chart_with_shapes(
        pos, patterns, pattern_labels=[],
        toggles=[st.session_state.get(f"toggle_pattern_{i}", False) for i in range(len(patterns))],
        filaments=filaments, combo_toggles=combos,
        label_style=label_style, singleton_map=singleton_map, df=df,
        use_placidus=use_placidus, dark_mode=dark_mode,
        shapes=shapes, shape_toggles_by_parent=shape_toggles_by_parent,
        singleton_toggles=singleton_toggles, major_edges_all=major_edges_all
    )

    st.pyplot(fig, use_container_width=False)

    # (keep your Aspect Interpretation Prompt + Sidebar profiles exactly as before)

    # --- Aspect Interpretation Prompt ---
    st.subheader("Aspect Interpretation Prompt")
    st.caption("Paste this prompt into an LLM (like ChatGPT).")

    aspect_blocks = []
    aspect_definitions = set()

    for s in active_shapes:
        lines = []
        for (p1, p2), asp in s["edges"]:
            asp_clean = asp.replace("_approx", "")
            asp_text = ASPECT_INTERPRETATIONS.get(asp_clean, asp_clean)
            lines.append(f"{p1} {asp_clean} {p2}")
            aspect_definitions.add(f"{asp_clean}: {asp_text}")
        if lines:
            aspect_blocks.append(" + ".join(lines))

    import re
    def strip_html_tags(text):
        clean = re.sub(r'<[^>]+>', '', text)
        return clean.strip()

    if aspect_blocks:
        # Character profiles for visible objects
        planet_profiles_texts = []
        for obj in sorted(visible_objects):
            matched_rows = df[df["Object"] == obj]
            if not matched_rows.empty:
                row = matched_rows.iloc[0].to_dict()
                profile_html = format_planet_profile(row)
                profile_text = strip_html_tags(profile_html)
                planet_profiles_texts.append(profile_text)

        planet_profiles_block = (
            "### Character Profiles\n" + "\n\n".join(planet_profiles_texts)
            if planet_profiles_texts else ""
        )

        prompt = (
            "Synthesize accurate poetic interpretations for each of these astrological aspects, "
            "using only the precise method outlined. Do not default to traditional astrology. "
            "For each planet or placement profile or conjunction cluster provided, use the planet/placement "
            "meaning(s), sign, Sabian symbol, fixed star conjunction(s) (if present), Out of Bounds status (if present), "
            "retrograde status or station point (if present), dignity (if present) and rulerships (if present) "
            "to synthesize a personified planet \"character\" profile in one paragraph. "
            "List these one-paragraph character profiles first in your output, under a heading called \"Character Profiles\" \n\n"
            "Then, synthesize each aspect, using the two character profiles of the endpoints and the aspect interpretation provided "
            "below (not traditional astrology definitions) to personify the \"relationship dynamics\" between each combination (aspect) "
            "of two characters. Each aspect synthesis should be a paragraph. List those paragraphs below the Character Profiles, "
            "under a header called \"Aspects\" \n\n"
            "Lastly, synthesize all of the aspects together: Zoom out and use your thinking brain to see how these interplanetary "
            "relationship dynamics become a functioning system with a function when combined into the whole shape provided, and ask "
            "yourself \"what does the whole thing do, as a machine?\" Then write the answer as the final paragraph, under a header "
            "called \"Circuit\"\n\n"
            + planet_profiles_block + "\n\n"
            + "\n\n".join(aspect_blocks) + "\n\n"
            + "\n\n".join(sorted(aspect_definitions))
        ).strip()

        copy_button = f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px;">
                <button id="copy-btn"
                        onclick="navigator.clipboard.writeText(document.getElementById('prompt-box').innerText).then(() => {{
                            var btn = document.getElementById('copy-btn');
                            var oldText = btn.innerHTML;
                            btn.innerHTML = '✅ Copied!';
                            setTimeout(() => btn.innerHTML = oldText, 2000);
                        }})"
                        style="padding:4px 8px; font-size:0.9em; cursor:pointer; background:#333; color:white; border:1px solid #777; border-radius:4px;">
                    📋 Copy
                </button>
            </div>
            <div id="prompt-box" style="white-space:pre-wrap; font-family:monospace; font-size:0.9em; color:white; background:black; border:1px solid #555; padding:8px; border-radius:4px; max-height:600px; overflow:auto;">
                {prompt.replace("\n", "<br>")}
            </div>
        """
        components.html(copy_button, height=700, scrolling=True)
    else:
        st.markdown("_(Select at least 1 sub-shape from a drop-down to view prompt.)_")

    # --- Sidebar planet profiles ---
    st.sidebar.subheader("🪐 Planet Profiles in View")
    for obj in sorted(visible_objects):
        matched_rows = df[df["Object"] == obj]
        if not matched_rows.empty:
            row = matched_rows.iloc[0].to_dict()
            profile = format_planet_profile(row)
            st.sidebar.markdown(profile, unsafe_allow_html=True)
            st.sidebar.markdown("---")