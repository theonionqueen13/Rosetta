import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from itertools import combinations

# MUST be first Streamlit command
st.set_page_config(layout="wide")

# CONSTANTS - All the lookup data in one place
GLYPHS = {
    "Sun": "☉",
    "Moon": "☽",
    "Mercury": "☿",
    "Venus": "♀",
    "Mars": "♂",
    "Jupiter": "♃",
    "Saturn": "♄",
    "Uranus": "♅",
    "Neptune": "♆",
    "Pluto": "♇",
    "Chiron": "⚷",
    "Ceres": "⚳",
    "Pallas": "⚴",
    "Juno": "⚵",
    "Vesta": "⚶",
    "North Node": "☊",
    "South Node": "☋",
    "Part of Fortune": "⊗",
    "Lilith": "⚸",
    "Vertex": "🜊",
    "True Node": "☊",
}

ASPECTS = {
    "Conjunction": {"angle": 0, "orb": 3, "color": "#888888", "style": "solid"},
    "Sextile": {"angle": 60, "orb": 3, "color": "purple", "style": "solid"},
    "Square": {"angle": 90, "orb": 3, "color": "red", "style": "solid"},
    "Trine": {"angle": 120, "orb": 3, "color": "blue", "style": "solid"},
    "Sesquisquare": {"angle": 135, "orb": 2, "color": "orange", "style": "dotted"},
    "Quincunx": {"angle": 150, "orb": 3, "color": "green", "style": "dotted"},
    "Opposition": {"angle": 180, "orb": 3, "color": "red", "style": "solid"},
}

MAJOR_OBJECTS = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "Eris",
    "Chiron",
    "Vesta",
    "Pallas",
    "Ceres",
    "Juno",
    "Psyche",
    "Eros",
    "Part of Fortune",
    "Black Moon Lilith",
    "Lilith",
    "Ascendant",
    "AC",
    "Descendant",
    "DC",
    "Midheaven",
    "MC",
    "IC",
    "North Node",
    "True Node",
    "South Node",
    "Vertex",
]

ZODIAC_SIGNS = ["♈️", "♉️", "♊️", "♋️", "♌️", "♍️", "♎️", "♏️", "♐️", "♑️", "♒️", "♓️"]
ZODIAC_COLORS = ["red", "green", "#DAA520", "blue"] * 3
MODALITIES = ["Cardinal", "Fixed", "Mutable"] * 4
GROUP_COLORS = [
    "crimson",
    "teal",
    "darkorange",
    "slateblue",
    "seagreen",
    "hotpink",
    "gold",
    "deepskyblue",
    "orchid",
]

OBJECT_MEANINGS = {
    "AC": "The mask you wear and how others first see you.",
    "Desc": "What you seek in relationships and partners.",
    "True Node": "Your soul's growth direction in this life.",
    "Sun": "Your core identity, purpose, and life force.",
    "Moon": "Your emotions, inner world, and instinctive needs.",
    "Mercury": "Your mind, communication style, and how you think.",
    "Venus": "How you love, attract, and experience beauty.",
    "Mars": "How you act, assert yourself, and pursue desires.",
    "Jupiter": "Your growth path, optimism, and what expands you.",
    "Saturn": "Your responsibilities, discipline, and long-term lessons.",
    "Uranus": "Your uniqueness, rebellion, and breakthroughs.",
    "Neptune": "Your dreams, illusions, and spiritual longing.",
    "Pluto": "Your power, transformations, and shadow work.",
    "Ceres": "The nurturing instinct and cycles of giving and receiving.",
    "Pallas": "Pattern recognition, creative intelligence, and tactics.",
    "Juno": "What you need in committed partnerships.",
    "Vesta": "Sacred focus, devotion, and spiritual flame.",
    "Lilith": "Your raw feminine power, rebellion, and untamed self.",
    "Chiron": "The deep wound you heal in others by healing yourself.",
    "Vertex": "A fated meeting point — unexpected turning points.",
    "Part of Fortune": "Where you find natural ease and success.",
    # Add more meanings as needed...
}


# HELPER FUNCTIONS
def deg_to_rad(deg, asc_shift=0):
    """Convert degrees to radians for polar chart positioning"""
    return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)


def get_ascendant_degree(df):
    """Find Ascendant degree from CSV data"""
    # Try multiple ways to find Ascendant
    for search_term in ["Ascendant", "ascendant", "AC"]:
        asc_row = df[df["Object"].str.contains(search_term, case=False, na=False)]
        if not asc_row.empty:
            return float(asc_row["Computed Absolute Degree"].values[0])
    return 0


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

    # Create pattern mapping
    pattern_map = {}
    for idx, pattern in enumerate(patterns):
        for planet in pattern:
            pattern_map[planet] = idx

    # Handle singleton planets (not in any pattern)
    all_patterned = set(pattern_map.keys())
    all_placements = set(pos.keys())
    singletons = all_placements - all_patterned
    singleton_index_offset = len(patterns)
    singleton_map = {
        planet: singleton_index_offset + i for i, planet in enumerate(singletons)
    }
    pattern_map.update(singleton_map)

    # Find minor aspect connections
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


def draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode):
    """Draw house cusp lines on the chart"""
    if use_placidus:
        # Use actual house cusp positions from data
        cusp_rows = df[df["Object"].str.match(r"^\d{1,2}H Cusp$", na=False)]
        for i, (_, row) in enumerate(cusp_rows.iterrows()):
            if pd.notna(row["Computed Absolute Degree"]):
                deg = float(row["Computed Absolute Degree"])
                rad = deg_to_rad(deg, asc_deg)
                ax.plot(
                    [rad, rad], [0, 1.0], color="gray", linestyle="dashed", linewidth=1
                )
                ax.text(
                    rad - np.deg2rad(5),
                    0.2,
                    str(i + 1),
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white" if dark_mode else "black",
                )
    else:
        # Use equal houses (30-degree divisions)
        for i in range(12):
            deg = (asc_deg + i * 30) % 360
            rad = deg_to_rad(deg, asc_deg)
            ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="solid", linewidth=1)
            ax.text(
                rad - np.deg2rad(5),
                0.2,
                str(i + 1),
                ha="center",
                va="center",
                fontsize=8,
                color="white" if dark_mode else "black",
            )


def draw_degree_markers(ax, asc_deg, dark_mode):
    """Draw degree markers around the chart"""
    for deg in range(0, 360, 10):
        rad = deg_to_rad(deg, asc_deg)
        ax.plot(
            [rad, rad],
            [1.02, 1.08],
            color="white" if dark_mode else "black",
            linewidth=1,
        )
        ax.text(
            rad,
            1.12,
            f"{deg % 30}°",
            ha="center",
            va="center",
            fontsize=7,
            color="white" if dark_mode else "black",
        )


def draw_zodiac_signs(ax, asc_deg):
    """Draw zodiac sign symbols around the chart"""
    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)
        ax.text(
            rad,
            1.50,
            ZODIAC_SIGNS[i],
            ha="center",
            va="center",
            fontsize=16,
            fontweight="bold",
            color=ZODIAC_COLORS[i],
        )
        ax.text(
            rad,
            1.675,
            MODALITIES[i],
            ha="center",
            va="center",
            fontsize=6,
            color="dimgray",
        )


def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode):
    """Draw planet labels with collision avoidance"""
    # Group planets by proximity to avoid overlap
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

    # Draw labels with vertical spacing for clusters
    for cluster in clustered:
        for i, (name, degree) in enumerate(cluster):
            rad = deg_to_rad(degree, asc_deg)
            offset = 1.30 + i * 0.06  # Base radius + spacing
            label = name if label_style == "Text" else GLYPHS.get(name, name)
            ax.text(
                rad,
                offset,
                label,
                ha="center",
                va="center",
                fontsize=9,
                color="white" if dark_mode else "black",
            )


def draw_aspect_lines(ax, pos, patterns, active_patterns, asc_deg):
    """Draw aspect lines between planets in active patterns"""
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

                # Check for major aspects only
                major_aspects = [
                    "Conjunction",
                    "Sextile",
                    "Square",
                    "Trine",
                    "Opposition",
                ]
                for asp in major_aspects:
                    asp_data = ASPECTS[asp]
                    if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                        r1 = deg_to_rad(pos[p1], asc_deg)
                        r2 = deg_to_rad(pos[p2], asc_deg)

                        line_color = (
                            asp_data["color"]
                            if single_pattern_mode
                            else GROUP_COLORS[idx % len(GROUP_COLORS)]
                        )

                        ax.plot(
                            [r1, r2],
                            [1, 1],
                            linestyle=asp_data["style"],
                            color=line_color,
                            linewidth=2,
                        )
                        break


def draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg):
    """Draw minor aspect (filament) connections"""
    single_pattern_mode = len(active_patterns) == 1

    for p1, p2, asp_name, pat1, pat2 in filaments:
        # Draw if both patterns are active
        if pat1 in active_patterns and pat2 in active_patterns:
            # Skip if single pattern mode and patterns are different
            if single_pattern_mode and pat1 != pat2:
                continue

            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot(
                [r1, r2],
                [1, 1],
                linestyle="dotted",
                color=ASPECTS[asp_name]["color"],
                linewidth=1,
            )


def format_planet_profile(row):
    """Format planet information for display"""
    name = row["Object"]
    meaning = OBJECT_MEANINGS.get(name, "")
    dignity = row.get("Dignity", "")
    retro = row.get("Retrograde", "")
    sabian = row.get("Sabian Symbol", "")
    fixed_star = row.get("Fixed Star Conjunction", "")
    oob = row.get("OOB Status", "")
    sign = row.get("Sign", "")
    lon = row.get("Longitude", "")

    # Build header
    header = f"{GLYPHS.get(name, '')} {name}"
    if str(dignity).strip().lower() not in ["none", "nan", ""]:
        header += f" ({dignity})"
    if str(retro).strip().lower() == "rx":
        header += " Retrograde"

    # Build HTML with custom spacing
    html_parts = [f'<div style="margin-bottom: 8px;">{header}</div>']

    if meaning:
        html_parts.append(
            f'<div style="margin-bottom: 4px;"><strong>{meaning}</strong></div>'
        )

    if sabian and str(sabian).strip().lower() not in ["none", "nan", ""]:
        html_parts.append(
            f'<div style="margin-bottom: 4px; font-style: italic;">"{sabian}"</div>'
        )

    if sign and lon:
        position_line = f"{sign} {lon}"
        if str(retro).strip().lower() == "rx":
            position_line += " Rx"
        html_parts.append(f'<div style="margin-bottom: 6px;">{position_line}</div>')

    # Add technical details with tight spacing
    details = []
    for label, value in [
        ("Out Of Bounds", oob),
        ("Conjunct Fixed Star", fixed_star),
        ("Speed", row.get("Speed", "")),
        ("Latitude", row.get("Latitude", "")),
        ("Declination", row.get("Declination", "")),
    ]:
        if str(value).strip().lower() not in ["none", "nan", "", "no"]:
            details.append(
                f'<div style="margin-bottom: 2px; font-size: 0.9em;">{label}: {value}</div>'
            )

    if details:
        html_parts.extend(details)

    return "".join(html_parts)


# MAIN RENDERING FUNCTION
def render_chart(
    pos,
    patterns,
    pattern_labels,
    toggles,
    filaments,
    combo_toggles,
    label_style,
    singleton_map,
    df,
    use_placidus,
    dark_mode,
):
    """Main function to render the astrology chart"""

    # Get Ascendant degree for proper chart rotation
    asc_deg = get_ascendant_degree(df)

    # Set up the polar plot
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.25)
    ax.axis("off")

    # Draw chart elements
    draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode)
    draw_degree_markers(ax, asc_deg, dark_mode)
    draw_zodiac_signs(ax, asc_deg)
    draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode)

    # Determine which patterns are active
    active_patterns = set(i for i, show in enumerate(toggles) if show)
    visible_objects = set()
    single_pattern_mode = len(active_patterns) == 1

    # Auto-expand for filament-linked singletons
    if not single_pattern_mode:
        for p1, p2, asp_name, pat1, pat2 in filaments:
            if (
                pat1 in active_patterns
                and pat2 not in active_patterns
                and pat2 >= len(patterns)
            ):
                active_patterns.add(pat2)
            elif (
                pat2 in active_patterns
                and pat1 not in active_patterns
                and pat1 >= len(patterns)
            ):
                active_patterns.add(pat1)

    # Add combo toggles
    for group in combo_toggles:
        if combo_toggles[group]:
            active_patterns.update(group)

    # Track visible objects
    for idx in active_patterns:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])

    # Draw aspect lines and filaments
    draw_aspect_lines(ax, pos, patterns, active_patterns, asc_deg)
    draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg)

    return fig, visible_objects


# STREAMLIT UI
st.title("🧭️Rosetta Flight Deck")

uploaded_file = st.file_uploader("Upload natal chart CSV", type=["csv"])
label_style = st.radio("Label Style", ["Text", "Glyph"], index=1, horizontal=True)

if uploaded_file:
    # Load and process data
    df = pd.read_csv(uploaded_file)
    df = df[df["Computed Absolute Degree"].notna()].copy()
    df["abs_deg"] = df["Computed Absolute Degree"].astype(float)

    # Add South Node if only True Node exists
    true_node_row = df[df["Object"].str.lower().str.contains("true node|north node")]
    if not true_node_row.empty and "South Node" not in df["Object"].values:
        sn_deg = (true_node_row["abs_deg"].values[0] + 180) % 360
        sn_row = df.iloc[0].copy()
        sn_row["Object"] = "South Node"
        sn_row["abs_deg"] = sn_deg
        df = pd.concat([df, pd.DataFrame([sn_row])], ignore_index=True)

    # Filter to major objects and create position dictionary
    df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
    pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))

    # Build patterns and connections
    patterns = build_aspect_graph(pos)
    filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
    combos = generate_combo_groups(filaments)

    # ----------------------------
    # Main layout: two columns
    # ----------------------------
    left_col, right_col = st.columns(
        [2, 1]
    )  # wider for patterns, narrower for expansions

    # ----------------------------------
    # Left column: Patterns & Shapes
    # ----------------------------------
    with left_col:
        st.subheader("Patterns")

        toggles = []
        pattern_labels = []
        half = (len(patterns) + 1) // 2

        # Split into two parent columns
        left_patterns, right_patterns = st.columns(2)

        for i, component in enumerate(patterns):
            target_col = left_patterns if i < half else right_patterns
            key_prefix = f"pattern{i}"
            checkbox_key = f"toggle_{key_prefix}_{i}"
            label = f"Pattern {i+1}: {', '.join(component)}"

            with target_col:
                # Checkbox and expander side by side (no nested columns!)
                cbox = st.checkbox("", value=True, key=checkbox_key)
                toggles.append(cbox)
                pattern_labels.append(label)

                with st.expander(label, expanded=False):
                    st.markdown("_(sub-shapes will appear here later)_")

    # ----------------------------------
    # Right column: Expansion Options
    # ----------------------------------
    with right_col:
        st.subheader("Expansion Options")
        st.checkbox("Show Minor Asteroids", value=False)

        st.markdown("#### Harmonics")
        cols = st.columns(6)
        for j, label in enumerate(["5", "7", "9", "10", "11", "12"]):
            cols[j].checkbox(label, value=False, key=f"harmonic_{label}")

    # Chart options
    use_placidus = st.checkbox("Use Placidus House Cusps", value=False)
    dark_mode = st.checkbox("🌙 Dark Mode", value=False)

    # Render chart
    fig, visible_objects = render_chart(
        pos,
        patterns,
        pattern_labels,
        toggles,
        filaments,
        {},
        label_style,
        singleton_map,
        df,
        use_placidus,
        dark_mode,
    )

    st.pyplot(fig, use_container_width=False)

    # Sidebar: Planet profiles
    st.sidebar.subheader("🪐 Planet Profiles in View")
    for obj in sorted(visible_objects):
        matched_rows = df[df["Object"] == obj]
        if not matched_rows.empty:
            row = matched_rows.iloc[0].to_dict()
            profile = format_planet_profile(row)
            safe_profile = profile.encode("utf-16", "surrogatepass").decode("utf-16")
            st.sidebar.markdown(safe_profile, unsafe_allow_html=True)
            st.sidebar.markdown("---")
