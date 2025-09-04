import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from itertools import combinations

# MUST be first Streamlit command
st.set_page_config(layout="wide")

from rosetta.lookup import GLYPHS, ASPECTS, MAJOR_OBJECTS, OBJECT_MEANINGS, GROUP_COLORS
from rosetta.helpers import deg_to_rad, get_ascendant_degree
from rosetta.drawing import (
    draw_house_cusps,
    draw_degree_markers,
    draw_zodiac_signs,
    draw_planet_labels,
    draw_aspect_lines,
    draw_filament_lines,
    draw_shape_edges,
    draw_minor_edges,
)
from rosetta.patterns import (
    build_aspect_graph,
    detect_minor_links_with_singletons,
    generate_combo_groups,
    detect_shapes,
    internal_minor_edges_for_pattern,
)
import rosetta.patterns
print(">>> patterns.py loaded from:", rosetta.patterns.__file__)

# Distinct palette for sub-shapes (avoids parent red/blue/purple clashes)
SUBSHAPE_COLORS = [
    "#FF7F50",  # coral (orange-pink)
    "#FFD700",  # gold
    "#90EE90",  # light green
    "#20B2AA",  # teal
    "#FF69B4",  # hot pink
    "#8B4513",  # saddle brown
    "#B8860B",  # dark goldenrod
    "#708090",  # slate gray
    "#FF8C00",  # dark orange
    "#DA70D6",  # orchid (lavender)
    "#CD5C5C",  # indian red (muted burgundy)
    "#00CED1",  # dark turquoise
]

# --- FORMATTER (unchanged) ---
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

# --- CHART RENDERER ---
def render_chart(pos, patterns, pattern_labels, toggles, filaments, combo_toggles,
                label_style, singleton_map, df, use_placidus, dark_mode):
    asc_deg = get_ascendant_degree(df)

    fig, ax = plt.subplots(figsize=(5, 5), dpi=100, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.25)
    ax.axis("off")

    draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode)
    draw_degree_markers(ax, asc_deg, dark_mode)
    draw_zodiac_signs(ax, asc_deg)
    draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode)

    active_patterns = set(i for i, show in enumerate(toggles) if show)
    visible_objects = set()
    single_pattern_mode = len(active_patterns) == 1

    if not single_pattern_mode:
        for p1, p2, asp_name, pat1, pat2 in filaments:
            if (pat1 in active_patterns and pat2 not in active_patterns and pat2 >= len(patterns)):
                active_patterns.add(pat2)
            elif (pat2 in active_patterns and pat1 not in active_patterns and pat1 >= len(patterns)):
                active_patterns.add(pat1)

    for group in combo_toggles:
        if all(idx in active_patterns for idx in group):
            active_patterns.update(group)

    for idx in active_patterns:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])
        else:
            for planet, s_idx in singleton_map.items():
                if s_idx == idx:
                    visible_objects.add(planet)

    draw_aspect_lines(ax, pos, patterns, active_patterns, asc_deg, GROUP_COLORS)
    draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg)

    return fig, visible_objects

# --- sub-shape aware renderer ---
def render_chart_with_shapes(
    pos, patterns, pattern_labels, toggles,
    filaments, combo_toggles, label_style, singleton_map, df,
    use_placidus, dark_mode, shapes, shape_toggles_by_parent, singleton_toggles
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

    # parents first
    for idx in active_parents:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])
    if active_parents:
        draw_aspect_lines(ax, pos, patterns, active_parents, asc_deg, GROUP_COLORS)
        for idx in active_parents:
            minors = internal_minor_edges_for_pattern(pos, list(patterns[idx]))
            draw_minor_edges(ax, pos, minors, asc_deg)

    # sub-shapes next
    for s in active_shapes:
        visible_objects.update(s["members"])

    if len(active_shapes) > 1:
        color_map = {s["id"]: SUBSHAPE_COLORS[i % len(SUBSHAPE_COLORS)]
                     for i, s in enumerate(active_shapes)}
        for s in active_shapes:
            draw_shape_edges(ax, pos, s["edges"], asc_deg,
                             use_aspect_colors=False,
                             override_color=color_map[s["id"]])
    elif len(active_shapes) == 1:
        s = active_shapes[0]
        draw_shape_edges(ax, pos, s["edges"], asc_deg,
                         use_aspect_colors=False,
                         override_color=SUBSHAPE_COLORS[0])

    # add visible singletons
    visible_objects.update(active_singletons)

    # connectors
    for (p1, p2, asp_name, pat1, pat2) in filaments:
        in_parent1 = any((idx in active_parents) and (p1 in patterns[idx]) for idx in active_parents)
        in_parent2 = any((idx in active_parents) and (p2 in patterns[idx]) for idx in active_parents)
        in_shape1 = any(p1 in s["members"] for s in active_shapes)
        in_shape2 = any(p2 in s["members"] for s in active_shapes)
        in_singleton1 = p1 in active_singletons
        in_singleton2 = p2 in active_singletons

        if (in_parent1 or in_shape1 or in_singleton1) and (in_parent2 or in_shape2 or in_singleton2):
            r1 = deg_to_rad(pos[p1], asc_deg); r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot([r1, r2], [1, 1], linestyle="dotted",
                    color=ASPECTS[asp_name]["color"], linewidth=1)

    # fail-safe: draw isolated singletons as colored dots
    color_idx = 0
    for planet in active_singletons:
        involved = any(
            planet in (p1, p2) for (p1, p2, _, _, _) in filaments
        )
        if not involved:
            r = deg_to_rad(pos[planet], asc_deg)
            color = SUBSHAPE_COLORS[color_idx % len(SUBSHAPE_COLORS)]
            ax.plot([r], [1], marker="o", markersize=6,
                    color=color, linewidth=2)
            color_idx += 1
    return fig, visible_objects

# --- UI ---
st.title("🧭️Rosetta Flight Deck")
uploaded_file = st.file_uploader("Upload natal chart CSV", type=["csv"])
label_style = st.radio("Label Style", ["Text", "Glyph"], index=1, horizontal=True)

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df = df[df["Computed Absolute Degree"].notna()].copy()
    df["abs_deg"] = df["Computed Absolute Degree"].astype(float)

    true_node_row = df[df["Object"].str.lower().str.contains("true node|north node")]
    if not true_node_row.empty and "South Node" not in df["Object"].values:
        sn_deg = (true_node_row["abs_deg"].values[0] + 180) % 360
        sn_row = df.iloc[0].copy()
        sn_row["Object"] = "South Node"
        sn_row["abs_deg"] = sn_deg
        df = pd.concat([df, pd.DataFrame([sn_row])], ignore_index=True)

    df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
    pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))

    # Build patterns and also get the aspect graph G
    patterns, G = build_aspect_graph(pos, return_graph=True)

    filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
    combos = generate_combo_groups(filaments)

    # Pass G into detect_shapes now
    shapes = detect_shapes(pos, patterns, G)

    left_col, right_col = st.columns([2, 1])
    with left_col:
        st.subheader("Patterns")
        toggles = []
        pattern_labels = []
        half = (len(patterns) + 1) // 2
        left_patterns, right_patterns = st.columns(2)

        for i, component in enumerate(patterns):
            target_col = left_patterns if i < half else right_patterns
            key_prefix = f"pattern{i}"
            checkbox_key = f"toggle_{key_prefix}_{i}"
            label = f"Pattern {i+1}: {', '.join(component)}"

            with target_col:
                cbox = st.checkbox("", value=True, key=checkbox_key)
                toggles.append(cbox)
                pattern_labels.append(label)

                with st.expander(label, expanded=False):
                    parent_shapes = [s for s in shapes if s["parent"] == i]
                    shape_entries = []
                    if parent_shapes:
                        st.markdown("**Sub-shapes detected:**")

                        # --- Sorting logic ---
                        def default_sort_key(s):
                            # Larger shapes first, then type as tiebreaker
                            return -len(s["members"]), s["type"]

                        if any(s["type"] == "Envelope" for s in parent_shapes):
                            order = ["Envelope", "Mystic Rectangle", "Sextile Wedge", "Grand Trine"]

                            envelope_cluster = [s for s in parent_shapes if s["type"] in order]
                            rest = [s for s in parent_shapes if s["type"] not in order]

                            # Envelope cluster fixed order
                            envelope_cluster.sort(key=lambda s: order.index(s["type"]))
                            # Rest sorted by size
                            rest.sort(key=default_sort_key)

                            parent_shapes = envelope_cluster + rest
                        else:
                            parent_shapes.sort(key=default_sort_key)
                        # --- End sorting logic ---

                        for s in parent_shapes:
                            shape_name = s["type"]
                            if s.get("approx"):
                                shape_name = f"({shape_name})"
                            label_text = f"{shape_name} ({', '.join(s['members'])})"

                            on = st.checkbox(
                                label_text,
                                value=False,
                                key=f"shape_{i}_{s['id']}"
                            )
                            shape_entries.append({"id": s["id"], "on": on})
                    else:
                        st.markdown("_(no closed/open sub-shapes found in this pattern)_")

                    if "shape_toggles_by_parent" not in st.session_state:
                        st.session_state.shape_toggles_by_parent = {}
                    st.session_state.shape_toggles_by_parent[i] = shape_entries

    with right_col:
        st.subheader("Singletons")
        singleton_toggles = {}
        if singleton_map:
            cols = st.columns(len(singleton_map))
            for j, (planet, idx) in enumerate(singleton_map.items()):
                with cols[j]:
                    key = f"singleton_{planet}"
                    on = st.checkbox(GLYPHS.get(planet, planet), value=False, key=key)
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
    fig, visible_objects = render_chart_with_shapes(
        pos, patterns, pattern_labels, toggles, filaments, combos,
        label_style, singleton_map, df, use_placidus, dark_mode,
        shapes, shape_toggles_by_parent, singleton_toggles
    )

    st.pyplot(fig, use_container_width=False)

    st.sidebar.subheader("🪐 Planet Profiles in View")
    for obj in sorted(visible_objects):
        matched_rows = df[df["Object"] == obj]
        if not matched_rows.empty:
            row = matched_rows.iloc[0].to_dict()
            profile = format_planet_profile(row)
            safe_profile = profile.encode("utf-16", "surrogatepass").decode("utf-16")
            st.sidebar.markdown(profile, unsafe_allow_html=True)
            st.sidebar.markdown("---")

else:
    st.info("👆 Upload a natal chart CSV to generate your chart.")
