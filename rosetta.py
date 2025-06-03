import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from itertools import combinations

# Glyph constants for glyph mode

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
}


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
    # Pull Ascendant degree from CSV for correct rotation
    asc_row = df[df["Object"].str.contains("Ascendant", case=False, na=False)]
    asc_deg = (
        float(asc_row["Computed Absolute Degree"].values[0]) if not asc_row.empty else 0
    )
    # Pull Ascendant degree from CSV for correct rotation
    asc_row = df[df["Object"].str.lower().str.contains("ascendant")]
    asc_deg = (
        float(asc_row["Computed Absolute Degree"].values[0]) if not asc_row.empty else 0
    )
    # Get Ascendant degree from row labeled 'AC'
    asc_row = df[df["Object"].str.contains("AC", case=False, na=False)]
    asc_deg = (
        float(asc_row["Computed Absolute Degree"].values[0]) if not asc_row.empty else 0
    )
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.25)
    ax.axis("off")

    # Draw house cusps based on toggle
    if use_placidus:
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
        pass  # Needed to satisfy 'for' block before conditional injection
    # Draw house cusps
    if use_placidus:
        cusp_rows = df[df["Object"].str.match(r"^\d{1,2}H Cusp$", na=False)]
        for _, row in cusp_rows.iterrows():
            if pd.notna(row["Computed Absolute Degree"]):
                deg = float(row["Computed Absolute Degree"])
                rad = deg_to_rad(deg, asc_deg)
                ax.plot(
                    [rad, rad], [0, 1.0], color="gray", linestyle="dashed", linewidth=1
                )
    else:
        for i in range(12):
            deg = (asc_deg + i * 30) % 360
            rad = deg_to_rad(deg, asc_deg)
            ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="solid", linewidth=1)
    # Draw house cusps
    if use_placidus:
        cusp_rows = df[df["Object"].str.match(r"^\d{1,2}H Cusp$", na=False)]
        for _, row in cusp_rows.iterrows():
            if pd.notna(row["Computed Absolute Degree"]):
                deg = float(row["Computed Absolute Degree"])
                rad = deg_to_rad(deg, asc_deg)
                ax.plot(
                    [rad, rad], [0, 1.0], color="gray", linestyle="dashed", linewidth=1
                )
    else:
        for i in range(12):
            deg = (asc_deg + i * 30) % 360
            rad = deg_to_rad(deg, asc_deg)
            ax.plot([rad, rad], [0, 1.0], color="gray", linestyle="solid", linewidth=1)
        rad = deg_to_rad(base_deg + 15, asc_deg)

    for name, degree in pos.items():
        rad = deg_to_rad(degree, asc_deg)
        label = name if label_style == "Text" else GLYPHS.get(name, name)
    # Group positions by proximity to space tight conjunctions
    degree_threshold = 3  # degrees within which to separate labels
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
    # Now render with spacing
    for cluster in clustered:
        for i, (name, degree) in enumerate(cluster):
            rad = deg_to_rad(degree, asc_deg)
            offset = 1.30 + i * 0.06  # base radius + spacing
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

    active_patterns = set(i for i, show in enumerate(toggles) if show)
    visible_objects = set()
    single_pattern_mode = len(active_patterns) == 1
    # Auto-expand active_patterns to include filament-linked singletons only
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
    for group in combo_toggles:
        if combo_toggles[group]:
            active_patterns.update(group)

    for idx, pattern in enumerate(patterns):
        if idx in active_patterns:
            visible_objects.update(pattern)
        if idx not in active_patterns:
            continue
        keys = list(pattern)
        for i1 in range(len(keys)):
            for i2 in range(i1 + 1, len(keys)):
                p1, p2 = keys[i1], keys[i2]
                angle = abs(pos[p1] - pos[p2])
                if angle > 180:
                    angle = 360 - angle
                for asp, asp_data in ASPECTS.items():
                    if asp not in ["Quincunx", "Sesquisquare"]:
                        if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                            r1 = deg_to_rad(pos[p1], asc_deg)
                            r2 = deg_to_rad(pos[p2], asc_deg)
                            line_color = (
                                asp_data["color"]
                                if single_pattern_mode
                                else GROUP_COLORS[idx % len(GROUP_COLORS)]
                            )
                            line_style = asp_data["style"]
                            ax.plot(
                                [r1, r2],
                                [1, 1],
                                linestyle=line_style,
                                color=line_color,
                                linewidth=2,
                            )

    for p1, p2, asp_name, pat1, pat2 in filaments:
        if (
            not single_pattern_mode
            and pat1 in active_patterns
            and pat2 in active_patterns
        ):
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot(
                [r1, r2],
                [1, 1],
                linestyle="dotted",
                color=ASPECTS[asp_name]["color"],
                linewidth=1,
            )
        elif single_pattern_mode and pat1 == pat2 and pat1 in active_patterns:
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot(
                [r1, r2],
                [1, 1],
                linestyle="dotted",
                color=ASPECTS[asp_name]["color"],
                linewidth=1,
            )
        if (
            pat1 in active_patterns
            and pat2 in active_patterns
            and not single_pattern_mode
        ):
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot(
                [r1, r2],
                [1, 1],
                linestyle="dotted",
                color=ASPECTS[asp_name]["color"],
                linewidth=1,
            )

    return fig, visible_objects


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

ZODIAC_SIGNS = ["♈︎", "♉︎", "♊︎", "♋︎", "♌︎", "♍︎", "♎︎", "♏︎", "♐︎", "♑︎", "♒︎", "♓︎"]
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


def deg_to_rad(deg, asc_shift=0):
    return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)


def build_aspect_graph(pos):
    G = nx.Graph()
    for p1, p2 in combinations(pos.keys(), 2):
        angle = abs(pos[p1] - pos[p2])
        if angle > 180:
            angle = 360 - angle
        for asp in ["Conjunction", "Sextile", "Square", "Trine", "Opposition"]:
            if abs(ASPECTS[asp]["angle"] - angle) <= ASPECTS[asp]["orb"]:
                G.add_edge(p1, p2, aspect=asp)
    return list(nx.connected_components(G))


def detect_minor_links_with_singletons(pos, patterns):
    minor_aspects = ["Quincunx", "Sesquisquare"]
    connections = []
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
    G = nx.Graph()
    for _, _, _, pat1, pat2 in filaments:
        if pat1 != pat2:
            G.add_edge(pat1, pat2)
    return [sorted(list(g)) for g in nx.connected_components(G) if len(g) > 1]

    for deg in range(0, 360, 10):
        rad = deg_to_rad(deg, asc_deg)
        ax.plot(
            [rad, rad],
            [1.02, 1.08],
            color="white" if dark_mode else "black",
            linewidth=1,
        )

    for i, base_deg in enumerate(range(0, 360, 30)):
        rad = deg_to_rad(base_deg + 15, asc_deg)

    for name, degree in pos.items():
        rad = deg_to_rad(degree, asc_deg)
        label = name if label_style == "Text" else GLYPHS.get(name, name)

    active_patterns = set(i for i, show in enumerate(toggles) if show)
    for group in combo_toggles:
        if combo_toggles[group]:
            active_patterns.update(group)

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
                for asp, asp_data in ASPECTS.items():
                    if asp not in ["Quincunx", "Sesquisquare"]:
                        if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                            r1 = deg_to_rad(pos[p1], asc_deg)
                            r2 = deg_to_rad(pos[p2], asc_deg)
                            ax.plot(
                                [r1, r2],
                                [1, 1],
                                linestyle=asp_data["style"],
                                color=GROUP_COLORS[idx % len(GROUP_COLORS)],
                                linewidth=2,
                            )

    for p1, p2, asp_name, pat1, pat2 in filaments:
        if (
            pat1 in active_patterns
            and pat2 in active_patterns
            and not single_pattern_mode
        ):
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot(
                [r1, r2],
                [1, 1],
                linestyle="dotted",
                color=ASPECTS[asp_name]["color"],
                linewidth=1,
            )

    return fig


OBJECT_MEANINGS = {
    "Sun": "Your core identity, purpose, and life force.",
    "Moon": "Your emotions, inner world, and instinctive needs.",
    "Mercury": "Your mind, communication style, and how you think.",
    "Venus": "How you love, attract, and experience beauty.",
    "Mars": "How you act, assert yourself, and pursue desires.",
    "Jupiter": "Your growth path, optimism, and what expands you.",
    "Saturn": "Your responsibilities, discipline, and long-term lessons.",
    # Add more as needed
}


def format_planet_profile(row):
    glyphs = {
        "Sun": "\u2609",
        "Moon": "\u263d",
        "Mercury": "\u263f",
        "Venus": "\u2640\ufe0e",
        "Mars": "\u2642\ufe0e",
        "Jupiter": "\u2643",
        "Saturn": "\u2644",
        "Uranus": "\u2645",
        "Neptune": "\u2646",
        "Pluto": "\u2647",
        "Chiron": "\u26b7",
        "Ceres": "\u26b3",
        "Pallas": "\u26b4",
        "Juno": "\u26b5",
        "Vesta": "\u26b6",
        "North Node": "\u260a",
        "South Node": "\u260b",
        "Part of Fortune": "\u2297",
        "Lilith": "\u26b8",
        "Vertex": "\ud83d\udf0a",
        "True Node": "\u260a",
    }

    def safe(val):
        return str(val).strip() if val is not None else ""

    name = safe(row.get("Object", ""))
    meaning = OBJECT_MEANINGS.get(name, "")
    dignity = safe(row.get("Dignity", ""))
    retro = safe(row.get("Retrograde", ""))
    station = safe(row.get("Station", ""))
    sabian = safe(row.get("Sabian Symbol", ""))
    fixed_star = safe(row.get("Fixed Star Conjunction", ""))
    oob = safe(row.get("OOB Status", ""))
    sign = safe(row.get("Sign", ""))
    lon = safe(row.get("Longitude", ""))
    ruled_by_sign = safe(row.get("Ruled by (sign)", ""))
    ruled_by_house = safe(row.get("Ruled by (house)", ""))
    rules_sign = safe(row.get("Rules sign", ""))
    rules_house = safe(row.get("Rules house", ""))
    speed = safe(row.get("Speed", ""))
    lat = safe(row.get("Latitude", ""))
    dec = safe(row.get("Declination", ""))

    # === Header Construction ===
    glyph = glyphs.get(name, "")
    header = f"{glyph} {name}"
    if retro == "Rx":
        header += " Retrograde"
    if dignity and dignity.lower() != "none":
        header += f" (In {dignity})"

    lines = [f"### {header}"]

    # === Sabian Symbol ===
    if sabian and sabian.lower() not in ["none", "nan", ""]:
        lines.append(f"“{sabian}”")

    # === Add Meaning ===
    if meaning:
        lines.append(f"{meaning}")

    # === Main Info Line ===
    if sign and lon:
        pos_line = f"{sign} {lon}"
        if retro == "Rx":
            pos_line += " Rx"
        lines.append(pos_line)

    # === Additional Data ===
    if oob.lower().startswith("oob"):
        lines.append(f"Out Of Bounds {oob[3:].strip()}")
    if station.lower().startswith("station"):
        lines.append(station)
    if fixed_star.lower() not in ["none", "nan", ""]:
        lines.append(f"Conjunct Fixed Star: {fixed_star}")
    if ruled_by_sign.lower() not in ["none", "nan", ""]:
        lines.append(f"Ruled by (sign): {ruled_by_sign}")
    if ruled_by_house.lower() not in ["none", "nan", ""]:
        lines.append(f"Ruled by (house): {ruled_by_house}")
    if rules_sign.lower() not in ["none", "nan", ""]:
        lines.append(f"Rules sign: {rules_sign}")
    if rules_house.lower() not in ["none", "nan", ""]:
        lines.append(f"Rules house: {rules_house}")
    if speed.lower() not in ["none", "nan", ""]:
        lines.append(f"Speed: {speed}")
    if lat.lower() not in ["none", "nan", ""]:
        lines.append(f"Latitude: {lat}")
    if dec.lower() not in ["none", "nan", ""]:
        lines.append(f"Declination: {dec}")

    return "\n\n".join(lines).strip()


st.set_page_config(layout="wide")
st.title("🧭️Rosetta Flight Deck")

uploaded_file = st.file_uploader("Upload natal chart CSV", type=["csv"])
label_style = st.radio("Label Style", ["Text", "Glyph"], index=1, horizontal=True)

if uploaded_file:
    df = pd.read_csv(uploaded_file)

    # Validate and extract Computed Absolute Degree
    if "Computed Absolute Degree" in df.columns:
        df = df[df["Computed Absolute Degree"].notna()].copy()
        df["abs_deg"] = df["Computed Absolute Degree"]
    else:
        st.error("❌ The CSV is missing the 'Computed Absolute Degree' column.")
        st.stop()
    df = df[df["Computed Absolute Degree"].notna()].copy()
    df["abs_deg"] = df["Computed Absolute Degree"].astype(float)

    asc_row = df[df["Object"].str.lower().str.contains("asc")]

    true_node_row = df[df["Object"].str.lower().str.contains("true node|north node")]
    if not true_node_row.empty and "South Node" not in df["Object"].values:
        sn_deg = (true_node_row["abs_deg"].values[0] + 180) % 360
        sn_row = df.iloc[0].copy()
        sn_row["Object"] = "South Node"
        sn_row["abs_deg"] = sn_deg
        df = pd.concat([df, pd.DataFrame([sn_row])], ignore_index=True)

    df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
    pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))

    patterns = build_aspect_graph(pos)
    filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
    combos = generate_combo_groups(filaments)

    toggles = []
    pattern_labels = []
    left_col, right_col = st.columns(2)
    half = (len(patterns) + 1) // 2
    for i in range(len(patterns)):
        key_prefix = "left" if i < half else "right"
        target_col = left_col if i < half else right_col
        with target_col:
            row = st.columns([0.5, 2.5])
            checkbox_key = f"toggle_{key_prefix}_{i}"
            textinput_key = f"label_{key_prefix}_{i}"
            toggles.append(row[0].checkbox("", value=True, key=checkbox_key))
            pattern_labels.append(
                row[1].text_input("", f"Pattern {i+1}", key=textinput_key)
            )

    use_placidus = st.checkbox("Use Placidus House Cusps", value=False)
    dark_mode = st.checkbox("🌙 Dark Mode", value=False)
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

    st.sidebar.subheader("🪐 Planet Profiles in View")
    for obj in sorted(visible_objects):
        matched_rows = df[df["Object"] == obj]
        st.sidebar.write(f"🔍 Processing {obj}")
        if not matched_rows.empty:
            try:
                row = matched_rows.iloc[0].to_dict()
                profile = format_planet_profile(row)
                safe_profile = profile.encode("utf-16", "surrogatepass").decode(
                    "utf-16"
                )
                st.sidebar.markdown(safe_profile)
                st.sidebar.markdown("---")
            except Exception as e:
                st.sidebar.error(f"❌ Error processing {obj}: {e}")

    st.success(
        "Chart with full pattern fusion + singleton filament combo toggles rendered."
    )

    # Determine active patterns
    if uploaded_file:
        st.sidebar.subheader("🪐 Planet Profiles in View")
        for obj in sorted(visible_objects):
            matched_rows = df[df["Object"] == obj]
            if not matched_rows.empty:
                row = matched_rows.iloc[0].to_dict()
                profile = format_planet_profile(row)
                safe_profile = profile.encode("utf-16", "surrogatepass").decode(
                    "utf-16"
                )
                st.sidebar.markdown(safe_profile)
                st.sidebar.markdown("---")
