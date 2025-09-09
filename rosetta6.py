# rosetta6.py
import streamlit as st

st.set_page_config(layout="wide")

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
from itertools import combinations

# Import shared constants
from rosetta.lookup import (
    GLYPHS,
    ASPECTS,
    MAJOR_OBJECTS,
    OBJECT_MEANINGS,
    GROUP_COLORS,
)

# Import helpers (everything else lives in helpers.py now)
from rosetta.helpers import (
    deg_to_rad,
    get_ascendant_degree,
    build_aspect_graph,
    detect_minor_links_with_singletons,
    generate_combo_groups,
    draw_house_cusps,
    draw_degree_markers,
    draw_zodiac_signs,
    draw_planet_labels,
    draw_aspect_lines,
    draw_filament_lines,
    format_planet_profile,
)
from rosetta.patterns import detect_shapes


# -------------------------------
# Format planet profiles
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
        html_parts.append(
            f'<div style="margin-bottom: 4px;"><strong>{meaning}</strong></div>'
        )
    if sabian and str(sabian).strip().lower() not in ["none", "nan", ""]:
        html_parts.append(
            f'<div style="margin-bottom: 4px; font-style: italic;">"{sabian}"</div>'
        )
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
            details.append(
                f'<div style="margin-bottom: 2px; font-size: 0.9em;">{label}: {value}</div>'
            )

    if details:
        html_parts.extend(details)

    return "".join(html_parts)


# -------------------------------
# Main renderer
# -------------------------------
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
    asc_deg = get_ascendant_degree(df)

    # Setup polar plot
    fig, ax = plt.subplots(figsize=(5, 5), dpi=100, subplot_kw={"projection": "polar"})
    if dark_mode:
        ax.set_facecolor("black")
        fig.patch.set_facecolor("black")

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_rlim(0, 1.25)
    ax.axis("off")

    # Base chart
    draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode)
    draw_degree_markers(ax, asc_deg, dark_mode)
    draw_zodiac_signs(ax, asc_deg)
    draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode)

    # Active parents
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

    # Combo toggles (future expansion)
    for group in combo_toggles:
        if combo_toggles[group]:
            active_patterns.update(group)

    # Track visible objects
    for idx in active_patterns:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])

    # Draw lines
    draw_aspect_lines(ax, pos, patterns, active_patterns, asc_deg, GROUP_COLORS)
    draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg)

    return fig, visible_objects


# -------------------------------
# Streamlit UI
# -------------------------------
st.title("🧭️ Rosetta Flight Deck")

uploaded_file = st.file_uploader("Upload natal chart CSV", type=["csv"])
label_style = st.radio("Label Style", ["Text", "Glyph"], index=1, horizontal=True)

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    df = df[df["Computed Absolute Degree"].notna()].copy()
    df["abs_deg"] = df["Computed Absolute Degree"].astype(float)

    # Auto-generate South Node if needed
    true_node_row = df[df["Object"].str.lower().str.contains("true node|north node")]
    if not true_node_row.empty and "South Node" not in df["Object"].values:
        sn_deg = (true_node_row["abs_deg"].values[0] + 180) % 360
        sn_row = df.iloc[0].copy()
        sn_row["Object"] = "South Node"
        sn_row["abs_deg"] = sn_deg
        df = pd.concat([df, pd.DataFrame([sn_row])], ignore_index=True)

    # Positions
    df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
    pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))

    # Patterns + extras
    patterns = build_aspect_graph(pos)
    filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
    combos = generate_combo_groups(filaments)
    shapes = detect_shapes(pos, patterns)  # NEW!

    # Layout
    left_col, right_col = st.columns([2, 1])

    with left_col:
        st.subheader("Patterns")

        toggles = []
        pattern_labels = []
        half = (len(patterns) + 1) // 2
        left_patterns, right_patterns = st.columns(2)

        # inside the Patterns loop in rosetta6.py

        for i, component in enumerate(patterns):
            target_col = left_patterns if i < half else right_patterns
            checkbox_key = f"toggle_pattern{i}_{i}"
            label = f"Pattern {i+1}: {', '.join(component)}"

            with target_col:
                # ✅ FIX: give the checkbox its label instead of ""
                cbox = st.checkbox(label, value=True, key=checkbox_key)
                toggles.append(cbox)
                pattern_labels.append(label)

                with st.expander("Sub-shapes", expanded=False):
                    parent_shapes = [s for s in shapes if s["parent"] == i]
                    if parent_shapes:
                        st.markdown("**Detected:**")
                        for s in parent_shapes:
                            st.markdown(f"- {s['type']} ({', '.join(s['members'])})")
                    else:
                        st.markdown("_(none found)_")

    with right_col:
        st.subheader("Expansion Options")
        st.checkbox("Show Minor Asteroids", value=False)

        st.markdown("#### Harmonics")
        cols = st.columns(6)
        for j, label in enumerate(["5", "7", "9", "10", "11", "12"]):
            cols[j].checkbox(label, value=False, key=f"harmonic_{label}")

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

    # Sidebar: Planet Profiles
    st.sidebar.subheader("🪐 Planet Profiles in View")
    for obj in sorted(visible_objects):
        matched_rows = df[df["Object"] == obj]
        if not matched_rows.empty:
            row = matched_rows.iloc[0].to_dict()
            profile = format_planet_profile(row)
            safe_profile = profile.encode("utf-16", "surrogatepass").decode("utf-16")
            st.sidebar.markdown(safe_profile, unsafe_allow_html=True)
            st.sidebar.markdown("---")
