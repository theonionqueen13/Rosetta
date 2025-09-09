import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import streamlit.components.v1 as components
import datetime
import swisseph as swe
import re

from rosetta.calc import calculate_chart
from rosetta.lookup import (
    GLYPHS, ASPECTS, MAJOR_OBJECTS, OBJECT_MEANINGS,
    GROUP_COLORS, ASPECT_INTERPRETATIONS, INTERPRETATION_FLAGS, ZODIAC_SIGNS, ZODIAC_COLORS, MODALITIES, HOUSE_SYSTEM_INTERPRETATIONS
)
from rosetta.helpers import get_ascendant_degree, deg_to_rad, annotate_fixed_stars, get_fixed_star_meaning, build_aspect_graph, format_dms, format_longitude
from rosetta.drawing import (
    draw_house_cusps, draw_degree_markers, draw_zodiac_signs,
    draw_planet_labels, draw_aspect_lines, draw_filament_lines,
    draw_shape_edges, draw_minor_edges, draw_singleton_dots
)
from rosetta.patterns import (
    detect_minor_links_with_singletons, generate_combo_groups,
    detect_shapes, internal_minor_edges_for_pattern,
    connected_components_from_edges, _cluster_conjunctions_for_detection, 
)

# -------------------------
# Chart Drawing Functions
# -------------------------
def _in_forward_arc(start_deg, end_deg, x_deg):
    """True if x lies on the forward arc from start->end (mod 360)."""
    span = (end_deg - start_deg) % 360.0
    off  = (x_deg   - start_deg) % 360.0
    return off < span if span != 0 else off == 0

def _house_of_degree(deg, cusps):
    """Given a degree and a 12-length cusp list (House 1..12), return 1..12."""
    if not cusps or len(cusps) != 12:
        return None
    for i in range(12):
        a = cusps[i]
        b = cusps[(i + 1) % 12]
        if _in_forward_arc(a, b, deg):
            return i + 1
    return 12

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
            
def reset_chart_state():
    """Clear transient UI keys so each chart loads cleanly."""
    for key in list(st.session_state.keys()):
        if key.startswith("toggle_pattern_"):
            del st.session_state[key]
        if key.startswith("shape_"):
            del st.session_state[key]
        if key.startswith("singleton_"):
            del st.session_state[key]
    if "shape_toggles_by_parent" in st.session_state:
        del st.session_state["shape_toggles_by_parent"]
            
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

        # --- House (always show if available) ---
    h = row.get("House", None)
    try:
        if h is not None and int(h) >= 1:
            html_parts.append(f"<div style='font-size:0.9em;'>House: {int(h)}</div>")
    except Exception:
        pass

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
            fval = float(val_str)
            if fval == 0.0:
                continue
        except Exception:
            fval = None

        # Apply special DMS formatting
        if label == "Speed" and fval is not None:
            val_str = format_dms(fval, is_speed=True)
        elif label == "Latitude" and fval is not None:
            val_str = format_dms(fval, is_latlon=True)
        elif label == "Declination" and fval is not None:
            val_str = format_dms(fval, is_decl=True)
        elif label == "Conjunct Fixed Star":
            # Convert internal multi-star delimiter to commas
            parts = [p.strip() for p in val_str.split("|||") if p.strip()]
            val_str = ", ".join(parts)

        html_parts.append(f"<div style='font-size:0.9em;'>{label}: {val_str}</div>")

    # Force single spacing with line-height here
    return "<div style='line-height:1.1; margin-bottom:6px;'>" + "".join(html_parts) + "</div>"

# --- CHART RENDERER (full)
def render_chart_with_shapes(
    pos, patterns, pattern_labels, toggles,
    filaments, combo_toggles, label_style, singleton_map, df,
    house_system, dark_mode, shapes, shape_toggles_by_parent, singleton_toggles,
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
    cusps = draw_house_cusps(ax, df, asc_deg, house_system, dark_mode)
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
                draw_aspect_lines(
                    ax, pos, patterns,
                    active_patterns=active_parents,
                    asc_deg=asc_deg,
                    group_colors=GROUP_COLORS,
                    edges=major_edges_all
                )

                # optional: internal minors + filaments
                for idx in active_parents:
                    _ = internal_minor_edges_for_pattern(pos, list(patterns[idx]))
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

    # singletons (always mark them visible if toggled)
    visible_objects.update(active_singletons)

    # draw singleton dots (twice as wide as aspect lines)
    if active_singletons:
        draw_singleton_dots(ax, pos, active_singletons, shape_edges, asc_deg, line_width=2.0)

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

    return fig, visible_objects, active_shapes, cusps

from datetime import datetime
from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder
import pytz

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

# -------------------------
# CLEANED SESSION STATE INITIALIZATION
# -------------------------

# Initialize profile defaults (canonical values)
profile_defaults = {
    "profile_year": 1990,
    "profile_month_name": "July",
    "profile_day": 29,
    "profile_hour": 1,       # 24h format
    "profile_minute": 39,
    "profile_city": "",
    "profile_loaded": False,
    "current_profile": None,
}

for k, v in profile_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Derive widget-friendly values from profile
_profile_hour_24 = int(st.session_state["profile_hour"])
if _profile_hour_24 == 0:
    _ui_hour_12, _ui_ampm = 12, "AM"
elif _profile_hour_24 == 12:
    _ui_hour_12, _ui_ampm = 12, "PM"
elif _profile_hour_24 > 12:
    _ui_hour_12, _ui_ampm = _profile_hour_24 - 12, "PM"
else:
    _ui_hour_12, _ui_ampm = _profile_hour_24, "AM"

_ui_minute_str = f"{int(st.session_state['profile_minute']):02d}"

# Initialize widget keys only if missing (no conflicts with value/index params)
widget_defaults = {
    "year": st.session_state["profile_year"],
    "month_name": st.session_state["profile_month_name"],
    "day": st.session_state["profile_day"],
    "hour_12": _ui_hour_12,
    "minute_str": _ui_minute_str,
    "ampm": _ui_ampm,
    "city": st.session_state["profile_city"],
}

for k, v in widget_defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Apply loaded profile if present
if "_loaded_profile" in st.session_state:
    prof = st.session_state["_loaded_profile"]
    
    # Update profile keys
    st.session_state["profile_year"] = prof["year"]
    st.session_state["profile_month_name"] = MONTH_NAMES[prof["month"] - 1]
    st.session_state["profile_day"] = prof["day"]
    st.session_state["profile_hour"] = prof["hour"]
    st.session_state["profile_minute"] = prof["minute"]
    st.session_state["profile_city"] = prof["city"]
    
    # Update widget keys to match
    st.session_state["year"] = prof["year"]
    st.session_state["month_name"] = MONTH_NAMES[prof["month"] - 1]
    st.session_state["day"] = prof["day"]
    
    # Convert 24h to 12h for widget keys
    hour_24 = prof["hour"]
    if hour_24 == 0:
        st.session_state["hour_12"] = 12
        st.session_state["ampm"] = "AM"
    elif hour_24 == 12:
        st.session_state["hour_12"] = 12
        st.session_state["ampm"] = "PM"
    elif hour_24 > 12:
        st.session_state["hour_12"] = hour_24 - 12
        st.session_state["ampm"] = "PM"
    else:
        st.session_state["hour_12"] = hour_24
        st.session_state["ampm"] = "AM"
    
    st.session_state["minute_str"] = f"{prof['minute']:02d}"
    
    # Cleanup
    del st.session_state["_loaded_profile"]

if "active_profile_tab" not in st.session_state:
    st.session_state["active_profile_tab"] = "Load Profile"  # default

# -------------------------
# Outer layout: 3 columns
# -------------------------
col_left, col_mid, col_right = st.columns([2, 2, 2])

def run_chart(lat, lon, tz_name, house_system):
    reset_chart_state()
    _cache_major_edges.clear()
    _cache_shapes.clear()

    try:
        df = calculate_chart(
            int(st.session_state["profile_year"]),
            int(MONTH_NAMES.index(st.session_state["profile_month_name"]) + 1),
            int(st.session_state["profile_day"]),
            int(st.session_state["profile_hour"]),
            int(st.session_state["profile_minute"]),
            0.0, lat, lon,
            input_is_ut=False,
            tz_name=tz_name,
            house_system=house_system, 
        )

        df["abs_deg"] = df["Longitude"].astype(float)
        df = annotate_fixed_stars(df)
        df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
        pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))
        major_edges_all, patterns = get_major_edges_and_patterns(pos)
        shapes = get_shapes(pos, patterns, major_edges_all)
        filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
        combos = generate_combo_groups(filaments)

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

# -------------------------
# Left column: Birth Data
# -------------------------
with col_left:
    with st.expander("Enter Birth Data"):
        col1, col2 = st.columns([3, 2])

        # --- Left side: Date & Time ---
        with col1:
            # Year widget
            year = st.number_input(
                "Year",
                min_value=1000,
                max_value=3000,
                step=1,
                key="year"
            )

            # Month widget
            import calendar
            month_name = st.selectbox(
                "Month",
                MONTH_NAMES,
                key="month_name"
            )
            month = MONTH_NAMES.index(month_name) + 1
            days_in_month = calendar.monthrange(year, month)[1]

        # Time widgets
        time_cols = st.columns(3)
        with time_cols[0]:
            hour_12 = st.selectbox(
                "Birth Time",
                list(range(1, 13)),
                key="hour_12"
            )
        with time_cols[1]:
            minute_str = st.selectbox(
                " ",
                [f"{m:02d}" for m in range(60)],
                key="minute_str"
            )
        with time_cols[2]:
            ampm = st.selectbox(
                " ",
                ["AM", "PM"],
                key="ampm"
            )

        # Convert to 24h (helpers only, not widget keys)
        if ampm == "PM" and hour_12 != 12:
            hour_val = hour_12 + 12
        elif ampm == "AM" and hour_12 == 12:
            hour_val = 0
        else:
            hour_val = hour_12
        minute_val = int(minute_str)

        st.session_state["hour_val"] = hour_val
        st.session_state["minute_val"] = minute_val

        # --- Right side: Location ---
        with col2:
            opencage_key = st.secrets["OPENCAGE_API_KEY"]
            geolocator = OpenCage(api_key=opencage_key)

            city_name = st.text_input(
                "City of Birth",
                value=st.session_state.get("profile_city", ""),
                key="city"   # you can just reuse profile_city as the widget key
            )

            lat, lon, tz_name = None, None, None
            if city_name:
                try:
                    location = geolocator.geocode(city_name, timeout=20)
                    if location:
                        lat, lon = location.latitude, location.longitude
                        tf = TimezoneFinder()
                        tz_name = tf.timezone_at(lng=lon, lat=lat)
                        st.session_state["last_location"] = location.address
                        st.session_state["last_timezone"] = tz_name
                    else:
                        st.session_state["last_location"] = None
                        st.session_state["last_timezone"] = "City not found. Try a more specific query."
                except Exception as e:
                    st.session_state["last_location"] = None
                    st.session_state["last_timezone"] = f"Lookup error: {e}"
            # Day widget
            day = st.selectbox(
                "Day",
                list(range(1, days_in_month + 1)),
                key="day"
            )
# -------------------------
# Middle column: Now + Calculate Chart buttons
# -------------------------
with col_mid:
    col_now1, col_now2 = st.columns([1, 3])

    with col_now1:
        if st.button("🌟 Now"):
            if lat is None or lon is None or tz_name is None:
                st.error("Enter a valid city first to use the Now button.")
            else:
                tz = pytz.timezone(tz_name)
                now = datetime.now(tz)

                # ✅ Update only profile_* keys
                st.session_state["profile_year"] = now.year
                st.session_state["profile_month_name"] = MONTH_NAMES[now.month - 1]
                st.session_state["profile_day"] = now.day
                st.session_state["profile_hour"] = now.hour
                st.session_state["profile_minute"] = now.minute
                st.session_state["profile_city"] = city_name
                

                try:
                    df = calculate_chart(
                        now.year, now.month, now.day,
                        now.hour, now.minute,
                        0.0, lat, lon,
                        input_is_ut=False,
                        tz_name=tz_name,
                        house_system="Equal",
                    )
                    df["abs_deg"] = df["Longitude"].astype(float)
                    df = annotate_fixed_stars(df)
                    df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
                    pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))
                    major_edges_all, patterns = get_major_edges_and_patterns(pos)
                    shapes = get_shapes(pos, patterns, major_edges_all)
                    filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
                    combos = generate_combo_groups(filaments)

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

                st.rerun()

    if st.button("Calculate Chart"):
        if lat is None or lon is None or tz_name is None:
            st.error("Please enter a valid city and make sure lookup succeeds.")
        else:
            run_chart(lat, lon, tz_name, "Equal")

        # Location info BELOW buttons
        location_info = st.container()
        if st.session_state.get("last_location"):
            location_info.success(f"Found: {st.session_state['last_location']}")
            if st.session_state.get("last_timezone"):
                location_info.write(f"Timezone: {st.session_state['last_timezone']}")
        elif st.session_state.get("last_timezone"):
            location_info.error(st.session_state["last_timezone"])
        
        # user calculated a new chart manually
        st.session_state["active_profile_tab"] = "Add / Update Profile"

# -------------------------
# Right column: Profile Manager
# -------------------------
with col_right:
    import json, os
    DATA_FILE = "saved_birth_data.json"

    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            saved_profiles = json.load(f)
    else:
        saved_profiles = {}

    if "current_profile" not in st.session_state:
        st.session_state["current_profile"] = None

    # Track which tab is active
    if "active_profile_tab" not in st.session_state:
        st.session_state["active_profile_tab"] = "Load Profile"

    st.subheader("👤 Birth Profile Manager")

    tab_labels = ["Add / Update Profile", "Load Profile", "Delete Profile"]

    active_tab = st.radio(
        "Profile Manager Tabs",
        tab_labels,
        index=tab_labels.index(st.session_state["active_profile_tab"]),
        horizontal=True,
        key="profile_tab_selector"
    )

    st.session_state["active_profile_tab"] = active_tab  # keep synced

    if active_tab == "Add / Update Profile":
        profile_name = st.text_input("Profile Name (unique)", value="", key="profile_name_input")
        if st.button("💾 Save / Update Profile"):
            if profile_name.strip() == "":
                st.error("Please enter a name for the profile.")
            else:
                # If updating existing profile, keep current circuit names
                if profile_name in saved_profiles and "patterns" in st.session_state:
                    circuit_names = {
                        f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                        for i in range(len(st.session_state.patterns))
                    }
                # If brand new profile, reset to defaults
                elif "patterns" in st.session_state:
                    circuit_names = {
                        f"circuit_name_{i}": f"Circuit {i+1}"
                        for i in range(len(st.session_state.patterns))
                    }
                else:
                    circuit_names = {}

                saved_profiles[profile_name] = {
                    "year": int(st.session_state.get("profile_year", 1990)),
                    "month": int(MONTH_NAMES.index(st.session_state.get("profile_month_name", "July")) + 1),
                    "day": int(st.session_state.get("profile_day", 1)),
                    "hour": int(st.session_state.get("profile_hour", 0)),
                    "minute": int(st.session_state.get("profile_minute", 0)),
                    "city": st.session_state.get("profile_city", ""),
                    "lat": lat,
                    "lon": lon,
                    "tz_name": tz_name,
                    "circuit_names": circuit_names,
                }

                with open(DATA_FILE, "w") as f:
                    json.dump(saved_profiles, f, indent=2)

                st.success(f"Profile '{profile_name}' saved!")

    # --- Load ---
    elif active_tab == "Load Profile":
        if saved_profiles:
            with st.expander("Saved Profiles", expanded=False):
                cols = st.columns(2)
                for i, (name, data) in enumerate(saved_profiles.items()):
                    col = cols[i % 2]
                    with col:
                        if st.button(name, key=f"load_{name}"):
                            # Restore into session
                            st.session_state["_loaded_profile"] = data
                            st.session_state["current_profile"] = name
                            st.session_state["profile_loaded"] = True

                            # Update canonical keys
                            st.session_state["profile_year"] = data["year"]
                            st.session_state["profile_month_name"] = MONTH_NAMES[data["month"] - 1]
                            st.session_state["profile_day"] = data["day"]
                            st.session_state["profile_hour"] = data["hour"]
                            st.session_state["profile_minute"] = data["minute"]
                            st.session_state["profile_city"] = data["city"]

                            # Helpers
                            st.session_state["hour_val"] = data["hour"]
                            st.session_state["minute_val"] = data["minute"]
                            st.session_state["city_input"] = data["city"]

                            st.session_state["last_location"] = data["city"]
                            st.session_state["last_timezone"] = data.get("tz_name")

                            # Restore circuit names
                            if "circuit_names" in data:
                                for key, val in data["circuit_names"].items():
                                    st.session_state[key] = val
                                st.session_state["saved_circuit_names"] = data["circuit_names"].copy()
                            else:
                                st.session_state["saved_circuit_names"] = {}

                            # Calculate chart
                            run_chart(
                                data["lat"],
                                data["lon"],
                                data["tz_name"],
                                "Equal"
                            )
                            st.success(f"Profile '{name}' loaded and chart calculated!")
                            st.rerun()
        else:
            st.info("No saved profiles yet.")

    # --- Delete ---
    elif active_tab == "Delete Profile":
        if saved_profiles:
            delete_choice = st.selectbox("Select a profile to delete", list(saved_profiles.keys()), key="profile_delete")
            if st.button("🗑️ Delete Selected Profile"):
                del saved_profiles[delete_choice]
                with open(DATA_FILE, "w") as f:
                    json.dump(saved_profiles, f, indent=2)
                st.success(f"Profile '{delete_choice}' deleted!")
        else:
            st.info("No saved profiles yet.")

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

    # --- UI Layout ---
    left_col, right_col = st.columns([2, 1])
    with left_col:
        st.subheader("Circuits")
        st.caption("One Circuit = aspects color-coded. Multiple Circuits = each circuit color-coded. "
                   "Expand circuits to see their sub-shapes. View planet profiles on the left sidebar. "
                   "Below the chart, copy the prompt into your GPT for an aspect interpretation.")

        # Show/Hide all buttons
        col_all1, col_all2 = st.columns([1, 1])
        with col_all1:
            if st.button("Show All"):
                for i in range(len(patterns)):
                    st.session_state[f"toggle_pattern_{i}"] = True
                    for sh in [sh for sh in shapes if sh["parent"] == i]:
                        st.session_state[f"shape_{i}_{sh['id']}"] = True
                for planet in singleton_map.keys():
                    st.session_state[f"singleton_{planet}"] = True
        with col_all2:
            if st.button("Hide All"):
                for i in range(len(patterns)):
                    st.session_state[f"toggle_pattern_{i}"] = False
                    for sh in [sh for sh in shapes if sh["parent"] == i]:
                        st.session_state[f"shape_{i}_{sh['id']}"] = False
                for planet in singleton_map.keys():
                    st.session_state[f"singleton_{planet}"] = False

        # Pattern checkboxes + expanders
        toggles, pattern_labels = [], []
        half = (len(patterns) + 1) // 2
        left_patterns, right_patterns = st.columns(2)

        for i, component in enumerate(patterns):
            target_col = left_patterns if i < half else right_patterns
            checkbox_key = f"toggle_pattern_{i}"

            # Session key for circuit name
            circuit_name_key = f"circuit_name_{i}"
            default_label = f"Circuit {i+1}"
            if circuit_name_key not in st.session_state:
                st.session_state[circuit_name_key] = default_label

            # Ensure circuit name exists in session
            if circuit_name_key not in st.session_state:
                st.session_state[circuit_name_key] = default_label

            expander_label = f"{st.session_state[circuit_name_key]}: {', '.join(component)}"

            with target_col:
                cbox = st.checkbox("", key=checkbox_key)
                toggles.append(cbox)
                pattern_labels.append(expander_label)

                with st.expander(expander_label, expanded=False):
                    # Editable name inside expander
                    st.text_input(
                        f"Rename {default_label}",
                        key=circuit_name_key
                    )

                    # --- Auto-save when circuit name changes ---
                    if st.session_state.get("current_profile"):
                        saved = st.session_state.get("saved_circuit_names", {})
                        current_name = st.session_state[circuit_name_key]
                        last_saved = saved.get(circuit_name_key, default_label)

                        if current_name != last_saved:
                            # Build updated set of circuit names
                            current = {
                                f"circuit_name_{j}": st.session_state.get(f"circuit_name_{j}", f"Circuit {j+1}")
                                for j in range(len(patterns))
                            }
                            profile_name = st.session_state["current_profile"]
                            saved_profiles[profile_name]["circuit_names"] = current
                            with open(DATA_FILE, "w") as f:
                                json.dump(saved_profiles, f, indent=2)
                            st.session_state["saved_circuit_names"] = current.copy()
                            st.success(f"Circuit names auto-saved for profile '{profile_name}'!")

                    # Sub-shapes
                    parent_shapes = [sh for sh in shapes if sh["parent"] == i]
                    shape_entries = []
                    if parent_shapes:
                        st.markdown("**Sub-shapes detected:**")
                        for sh in parent_shapes:
                            label_text = f"{sh['type']}: {', '.join(str(m) for m in sh['members'])}"
                            unique_key = f"shape_{i}_{sh['id']}"
                            on = st.checkbox(
                                label_text,
                                key=unique_key,
                                value=st.session_state.get(unique_key, False)
                            )
                            shape_entries.append({"id": sh["id"], "on": on})
                    else:
                        st.markdown("_(no sub-shapes found)_")

                    if "shape_toggles_by_parent" not in st.session_state:
                        st.session_state.shape_toggles_by_parent = {}
                    st.session_state.shape_toggles_by_parent[i] = shape_entries

        # --- Save Circuit Names button (only if edits exist) ---
        unsaved_changes = False
        if st.session_state.get("current_profile"):
            saved = st.session_state.get("saved_circuit_names", {})
            current = {
                f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                for i in range(len(patterns))
            }
            if current != saved:
                unsaved_changes = True

        if unsaved_changes:
            st.markdown("---")
            if st.button("💾 Save Circuit Names"):
                profile_name = st.session_state["current_profile"]
                saved_profiles[profile_name]["circuit_names"] = current
                with open(DATA_FILE, "w") as f:
                    json.dump(saved_profiles, f, indent=2)
                st.session_state["saved_circuit_names"] = current.copy()
                st.success("Circuit names updated!")

    with right_col:
        st.subheader("Single Placements")
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

        with st.expander("Expansion Options (Coming Soon)"):
            st.caption("(These buttons don't do anything yet)")
            st.checkbox("Show Minor Asteroids", value=False)
            st.markdown("#### Harmonics")
            cols = st.columns(6)
            for j, label in enumerate(["5", "7", "9", "10", "11", "12"]):
                cols[j].checkbox(label, value=False, key=f"harmonic_{label}")

    left_col, right_col = st.columns([2, 1])
    with left_col:
        choice = st.radio(
            "House System",
            ["Equal", "Whole Sign", "Placidus",],
            index=0,
            key="house_system"
        )

        # Normalize into a separate variable
        house_system = choice.lower().replace(" sign", "")
    
    with right_col:
        # Choose how to show planet labels
        label_style = st.radio(
            "Label Style",
            ["Text", "Glyph"],
            index=1,
            horizontal=True
        )
        
        dark_mode = st.checkbox("🌙 Dark Mode", value=False)

    shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
    if not singleton_toggles:
        singleton_toggles = {p: st.session_state.get(f"singleton_{p}", False) for p in singleton_map}

    # --- Render the chart ---
    fig, visible_objects, active_shapes, cusps = render_chart_with_shapes(
        pos, patterns, pattern_labels=[],
        toggles=[st.session_state.get(f"toggle_pattern_{i}", False) for i in range(len(patterns))],
        filaments=filaments, combo_toggles=combos,
        label_style=label_style, singleton_map=singleton_map, df=df,
        house_system=house_system, 
        dark_mode=dark_mode,
        shapes=shapes, shape_toggles_by_parent=shape_toggles_by_parent,
        singleton_toggles=singleton_toggles, major_edges_all=major_edges_all
    )

    st.pyplot(fig, use_container_width=False)

    # --- Sidebar planet profiles ---
    st.sidebar.subheader("🪐 Planet Profiles in View")

    cusps_list = cusps

    # Apply conjunction clustering to determine display order
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(visible_objects))

    # Create ordered list: cluster representatives first (sorted), then their members, then singletons
    ordered_objects = []
    processed = set()

    # First, add cluster representatives and their members in cluster order
    for rep in sorted(rep_pos.keys(), key=lambda r: rep_pos[r]):
        cluster = rep_map[rep]
        # Add all cluster members in position order
        cluster_sorted = sorted(cluster, key=lambda m: pos[m])
        for obj in cluster_sorted:
            if obj in visible_objects and obj not in processed:
                ordered_objects.append(obj)
                processed.add(obj)

    # Add any remaining objects that weren't part of clusters (shouldn't happen, but safety)
    for obj in sorted(visible_objects):
        if obj not in processed:
            ordered_objects.append(obj)

    # Display profiles in the new clustered order
    for obj in ordered_objects:
        matched_rows = df[df["Object"] == obj]
        if matched_rows.empty:
            continue

        # Calculate houses once for all visible objects (single source of truth)
    enhanced_objects_data = {}
    for obj in ordered_objects:
        matched_rows = df[df["Object"] == obj]
        if not matched_rows.empty:
            row = matched_rows.iloc[0].to_dict()
            
            # Calculate house using the cusps from chart rendering
            deg_val = None
            for key in ("abs_deg", "Longitude"):
                if key in row and row[key] not in (None, "", "nan"):
                    try:
                        deg_val = float(row[key])
                        break
                    except Exception:
                        pass

            if deg_val is not None and cusps_list:
                house_num = _house_of_degree(deg_val, cusps_list)
                if house_num:
                    row["House"] = int(house_num)
            
            enhanced_objects_data[obj] = row

    # Display profiles using enhanced data
    for obj in ordered_objects:
        if obj not in enhanced_objects_data:
            continue
        
        row = enhanced_objects_data[obj]
        profile = format_planet_profile(row)
        st.sidebar.markdown(profile, unsafe_allow_html=True)
        st.sidebar.markdown("---")

    # --- Aspect Interpretation Prompt ---
    with st.expander("Aspect Interpretation Prompt"):
        st.caption("Paste this prompt into an LLM (like ChatGPT).")

        aspect_blocks = []
        aspect_definitions = set()

                # Add conjunction aspects from clusters first
        rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(visible_objects))
        
        for rep, cluster in rep_map.items():
            if len(cluster) >= 2:  # Only clusters with 2+ members have conjunctions
                # Generate all pairwise conjunctions within the cluster
                cluster_lines = []
                for i in range(len(cluster)):
                    for j in range(i + 1, len(cluster)):
                        p1, p2 = cluster[i], cluster[j]
                        cluster_lines.append(f"{p1} Conjunction {p2}")
                        aspect_definitions.add("Conjunction: " + ASPECT_INTERPRETATIONS.get("Conjunction", "Conjunction"))
                
                if cluster_lines:
                    aspect_blocks.append(" + ".join(cluster_lines))

        for s in active_shapes:
            lines = []
            for (p1, p2), asp in s["edges"]:
                asp_clean = asp.replace("_approx", "")
                asp_text = ASPECT_INTERPRETATIONS.get(asp_clean, asp_clean)
                lines.append(f"{p1} {asp_clean} {p2}")
                aspect_definitions.add(f"{asp_clean}: {asp_text}")
            if lines:
                aspect_blocks.append(" + ".join(lines))

        # --- Conjunction clusters using the SAME logic as patterns.py (no re-implementation) ---
        # Feed it the current positions and exactly the set of objects that are currently visible.
        rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(visible_objects))

        # rep_map is {representative: [cluster_members...]}
        _conj_clusters = list(rep_map.values())

        # Conjunction clusters trigger the special note.
        num_conj_clusters = sum(1 for c in _conj_clusters if len(c) >= 2)

        import re
        def strip_html_tags(text):
            # Replace divs and <br> with spaces
            text = re.sub(r'</div>|<br\s*/?>', ' ', text)
            text = re.sub(r'<div[^>]*>', '', text)
            # Remove any other HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            # Collapse multiple spaces
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        if aspect_blocks:
            planet_profiles_texts = []
            interpretation_flags = set()
            fixed_star_meanings = {}

            for obj in ordered_objects:  # Use the same ordering as sidebar
                if obj in enhanced_objects_data:
                    row = enhanced_objects_data[obj]  # Use pre-calculated data
                    profile_html = format_planet_profile(row)
                    profile_text = strip_html_tags(profile_html)
        
                    # Add additional prompt-only details here
                    additional_details = []
        
                    # Future: Add rulership details when ready
                    # if row.get("Rulership by House"):
                    #     additional_details.append(f"Rulership by House: {row['Rulership by House']}")
                    # if row.get("Rulership by Sign"):
                    #     additional_details.append(f"Rulership by Sign: {row['Rulership by Sign']}")
        
                    # Combine profile text with additional details
                    if additional_details:
                        profile_text += " | " + " | ".join(additional_details)

                    planet_profiles_texts.append(profile_text)

                    # ---- Out of Bounds check (separate) ----
                    if str(row.get("OOB Status", "")).lower() == "yes":
                        interpretation_flags.add("Out of Bounds")

                    # ---- Retrograde / Station checks ----
                    retro_val = str(row.get("Retrograde", "")).lower()
                    if "station" in retro_val:
                        interpretation_flags.add("Station Point")
                    if "rx" in retro_val:
                        interpretation_flags.add("Retrograde")

                    # ---- Fixed Stars check (independent) ----
                    if row.get("Fixed Star Meaning"):
                        stars = row["Fixed Star Conjunction"].split("|||")
                        meanings = row["Fixed Star Meaning"].split("|||")
                        for star, meaning in zip(stars, meanings):
                            star, meaning = star.strip(), meaning.strip()
                            if meaning:
                                fixed_star_meanings[star] = meaning

            planet_profiles_block = (
                "Character Profiles:\n" + "\n\n".join(planet_profiles_texts)
                if planet_profiles_texts else ""
            )

            # --- Build interpretation notes ---
            from rosetta.lookup import INTERPRETATION_FLAGS, HOUSE_INTERPRETATIONS

            # --- Build interpretation notes ---
            interpretation_notes = []
            if interpretation_flags or fixed_star_meanings or num_conj_clusters > 0:
                interpretation_notes.append("Interpretation Notes:")

            # Conjunction cluster rule (singular vs plural)
            if num_conj_clusters >= 1:
                if num_conj_clusters == 1:
                    interpretation_notes.append(
                        '- When more than 1 planet are clustered in conjunction together, do not synthesize individual interpretations for each conjunction. Instead, synthesize one conjunction cluster interpretation as a Combined Character Profile, listed under a separate header, "Combined Character Profile."'
                    )
                elif num_conj_clusters >= 2:
                    interpretation_notes.append(
                        '- When more than 1 planet are clustered in conjunction together, do not synthesize individual interpretations for each conjunction. Instead, synthesize one conjunction cluster interpretation as a Combined Character Profile, listed under a separate header, "Combined Character Profiles."'
                    )

            # General flags (each only once)
            for flag in sorted(interpretation_flags):
                meaning = INTERPRETATION_FLAGS.get(flag)
                if meaning:
                    interpretation_notes.append(f"- {meaning}")

            # Fixed Star note (general rule once, then list specifics)
            if fixed_star_meanings:
                general_star_note = INTERPRETATION_FLAGS.get("Fixed Star")
                if general_star_note:
                    interpretation_notes.append(f"- {general_star_note}")
                for star, meaning in fixed_star_meanings.items():
                    interpretation_notes.append(f"- {star}: {meaning}")
                    
            # House system interpretation
            house_system_meaning = HOUSE_SYSTEM_INTERPRETATIONS.get(house_system)
            if house_system_meaning:
                interpretation_notes.append(f"- House System ({house_system.title()}): {house_system_meaning}")

            # House interpretations (collect unique houses from enhanced_objects_data)
            present_houses = set()
            for obj in ordered_objects:
                if obj in enhanced_objects_data:
                    row = enhanced_objects_data[obj]
                    if row.get("House"):
                        present_houses.add(int(row["House"]))
            
            # Add house interpretation notes for each present house (sorted order)
            for house_num in sorted(present_houses):
                house_meaning = HOUSE_INTERPRETATIONS.get(house_num)
                if house_meaning:
                    interpretation_notes.append(f"- House {house_num}: {house_meaning}")

            # Collapse into single block for prompt
            interpretation_notes_block = "\n\n".join(interpretation_notes) if interpretation_notes else ""

            # --- Final prompt assembly ---
            import textwrap

            instructions = textwrap.dedent("""
            Synthesize accurate poetic interpretations for each of these astrological aspects, using only the precise method outlined. Do not default to traditional astrology. For each planet or placement profile or conjunction cluster provided, use all information provided to synthesize a personified planet "character" profile in one paragraph. Use only the interpretation instructions provided for each item. List these one-paragraph character profiles first in your output, under a heading called "Character Profiles."

            Then, synthesize each aspect, using the two character profiles of the endpoints and the aspect interpretation provided below (not traditional astrology definitions) to personify the "relationship dynamics" between each combination (aspect) of two characters. Each aspect synthesis should be a paragraph. List those paragraphs below the Character Profiles, under a header called "Aspects."

            Lastly, synthesize all of the aspects together: Zoom out and use your thinking brain to see how these interplanetary relationship dynamics become a functioning system with a function when combined into the whole shape provided, and ask yourself "what does the whole thing do when you put it together?" Describe the function, and suggest a name for the circuit. Output this synthesis under a header called "Circuit."
            """).strip()

            sections = [
                instructions,
                interpretation_notes_block.strip() if interpretation_notes_block else "",
                planet_profiles_block.strip() if planet_profiles_block else "",
                ("Aspects\n\n" + "\n\n".join(aspect_blocks)).strip() if aspect_blocks else "",
                "\n\n".join(sorted(aspect_definitions)).strip() if aspect_definitions else "",
            ]

            # filter out empties and join with two line breaks
            prompt = "\n\n".join([s for s in sections if s]).strip()

            copy_button = f"""
                <div style="display:flex; flex-direction:column; align-items:stretch;">
                    <div style="display:flex; justify-content:flex-end; margin-bottom:5px;">
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
                    <div id="prompt-box"
                        style="white-space:pre-wrap; font-family:monospace; font-size:0.9em;
                                color:white; background:black; border:1px solid #555;
                                padding:8px; border-radius:4px; max-height:600px; overflow:auto;">{prompt.strip().replace("\n", "<br>")}
                    </div>
                </div>
            """

            components.html(copy_button, height=700, scrolling=True)
        else:
            st.markdown("_(Select at least 1 sub-shape from a drop-down to view prompt.)_")