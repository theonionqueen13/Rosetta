# rosetta/drawing.py
import matplotlib.pyplot as plt
from rosetta.helpers import deg_to_rad
from rosetta.lookup import ASPECTS, GLYPHS

# -------------------------------
# Chart element drawing
# -------------------------------

def draw_house_cusps(ax, df, asc_deg, use_placidus, dark_mode):
    """Draw house cusp lines on the chart"""
    if use_placidus:
        cusp_rows = df[df["Object"].str.match(r"^\d{1,2}H Cusp$", na=False)]
        for i, (_, row) in enumerate(cusp_rows.iterrows()):
            if row.get("Computed Absolute Degree") is not None:
                deg = float(row["Computed Absolute Degree"])
                r = deg_to_rad(deg, asc_deg)
                ax.plot([r, r], [0, 1], color="gray", linestyle="dashed", linewidth=1)
                ax.text(r, 0.2, str(i + 1), ha="center", va="center",
                        fontsize=8, color="white" if dark_mode else "black")
    else:
        # Equal houses
        for i in range(12):
            deg = (asc_deg + i * 30) % 360
            r = deg_to_rad(deg, asc_deg)
            ax.plot([r, r], [0, 1], color="gray", linestyle="solid", linewidth=1)
            ax.text(r, 0.2, str(i + 1), ha="center", va="center",
                    fontsize=8, color="white" if dark_mode else "black")


def draw_degree_markers(ax, asc_deg, dark_mode):
    """Draw tick marks every 10° around the chart."""
    for deg in range(0, 360, 10):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [1.02, 1.08],
                color="white" if dark_mode else "black", linewidth=1)
        ax.text(r, 1.12, f"{deg % 30}°",
                ha="center", va="center", fontsize=7,
                color="white" if dark_mode else "black")


def draw_zodiac_signs(ax, asc_deg):
    """Draw zodiac glyphs around the wheel."""
    glyphs = [
        "♈️","♉️","♊️","♋️","♌️","♍️",
        "♎️","♏️","♐️","♑️","♒️","♓️"
    ]
    for i, glyph in enumerate(glyphs):
        r = deg_to_rad(i * 30 + 15, asc_deg)
        ax.text(r, 1.5, glyph,
                ha="center", va="center", fontsize=16, fontweight="bold")


def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode):
    """Draw planet glyphs or names around the wheel."""
    for planet, deg in pos.items():
        r = deg_to_rad(deg, asc_deg)
        label = GLYPHS.get(planet, planet) if label_style == "Glyph" else planet
        ax.text(r, 1.3, label,
                ha="center", va="center", fontsize=9,
                color="white" if dark_mode else "black")

# -------------------------------
# Aspect lines (master truth)
# -------------------------------

def draw_aspect_lines(
    ax,
    pos,
    patterns,
    active_patterns,
    asc_deg,
    group_colors,
    return_edges=False,
    edges=None,
):
    """
    Single source of truth for major aspect edges.

    - If edges is None: compute them fresh from pos for the active patterns.
    - If edges is provided: just use that (no recalculation).
    - If ax is not None: draw them.
    - If return_edges: return the edge list.
    """
    single_pattern_mode = len(active_patterns) == 1

    if edges is None:
        edges = []
        for idx, pattern in enumerate(patterns):
            if idx not in active_patterns:
                continue
            keys = list(pattern)
            for i1 in range(len(keys)):
                for i2 in range(i1 + 1, len(keys)):
                    p1, p2 = keys[i1], keys[i2]
                    d1, d2 = pos.get(p1), pos.get(p2)
                    if d1 is None or d2 is None:
                        continue
                    angle = abs(d1 - d2)
                    if angle > 180:
                        angle = 360 - angle
                    for asp, asp_data in ASPECTS.items():
                        if asp not in ["Quincunx", "Sesquisquare"]:  # majors only
                            if abs(asp_data["angle"] - angle) <= asp_data["orb"]:
                                edges.append(((p1, p2), asp))
                                break  # stop at first match

    if ax is not None:
        parent_of = {}
        for idx, pattern in enumerate(patterns):
            if idx in active_patterns:
                for p in pattern:
                    parent_of[p] = idx

        for ((p1, p2), aspect) in edges:
            i1 = parent_of.get(p1)
            i2 = parent_of.get(p2)
            if i1 is None or i2 is None or i1 != i2:
                continue
            d1, d2 = pos.get(p1), pos.get(p2)
            if d1 is None or d2 is None:
                continue
            r1 = deg_to_rad(d1, asc_deg)
            r2 = deg_to_rad(d2, asc_deg)
            asp_data = ASPECTS[aspect]
            color = asp_data["color"] if single_pattern_mode else group_colors[i1 % len(group_colors)]
            ax.plot([r1, r2], [1, 1], linestyle=asp_data["style"], color=color, linewidth=2)

    if return_edges:
        return edges

# -------------------------------
# Filaments (minors)
# -------------------------------

def draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg):
    """Draw minor aspect (filament) connections"""
    single_pattern_mode = len(active_patterns) == 1
    for p1, p2, asp_name, pat1, pat2 in filaments:
        if pat1 in active_patterns and pat2 in active_patterns:
            if single_pattern_mode and pat1 != pat2:
                continue
            r1 = deg_to_rad(pos[p1], asc_deg)
            r2 = deg_to_rad(pos[p2], asc_deg)
            ax.plot([r1, r2], [1, 1], linestyle="dotted",
                   color=ASPECTS[asp_name]["color"], linewidth=1)
            
def draw_singleton_dots(ax, pos, active_objects, visible_objects, asc_deg, line_width=2.0):
    for obj in active_objects:
        # skip only if object is already "claimed" by another aspect line
        if obj in visible_objects and len(visible_objects) > len(active_objects):
            continue  

        if obj in pos:
            r = deg_to_rad(pos[obj], asc_deg)
            ax.plot([r], [1], 'o', color="red", markersize=6, linewidth=line_width)

# -------------------------------
# Shape drawing
# -------------------------------

def draw_shape_edges(ax, pos, edges, asc_deg,
                     use_aspect_colors=True, override_color=None):
    """
    Draw edges of a detected shape.
    edges: list of ((p1, p2), aspect_name)
    """
    for (p1, p2), asp in edges:
        d1, d2 = pos.get(p1), pos.get(p2)
        if d1 is None or d2 is None:
            continue
        r1 = deg_to_rad(d1, asc_deg)
        r2 = deg_to_rad(d2, asc_deg)

        # Handle approx edges
        is_approx = asp.endswith("_approx")
        asp_clean = asp.replace("_approx", "")

        style = ASPECTS[asp_clean]["style"] if asp_clean in ASPECTS else "dotted"

        if use_aspect_colors and asp_clean in ASPECTS:
            base_color = ASPECTS[asp_clean]["color"]
        else:
            base_color = override_color or "gray"

        if is_approx:
            # fade the color (lighter version)
            import matplotlib.colors as mcolors
            rgb = mcolors.to_rgb(base_color)
            faded = tuple(min(1, c + 0.5 * (1 - c)) for c in rgb)
            color = faded
        else:
            color = base_color

        # 🔑 Thickness: majors thick, minors thin
        if asp_clean in ("Quincunx", "Sesquisquare"):
            lw = 1   # minors → thin
        else:
            lw = 2   # majors → thick

        ax.plot([r1, r2], [1, 1], linestyle=style, color=color, linewidth=lw)


def draw_minor_edges(ax, pos, edges, asc_deg):
    """
    Draw minor-aspect edges inside a parent pattern (always dotted).
    edges: list of ((p1, p2), aspect_name)
    """
    for (p1, p2), asp in edges:
        d1, d2 = pos.get(p1), pos.get(p2)
        if d1 is None or d2 is None:
            continue
        r1 = deg_to_rad(d1, asc_deg)
        r2 = deg_to_rad(d2, asc_deg)

        color = ASPECTS[asp]["color"] if asp in ASPECTS else "gray"
        ax.plot([r1, r2], [1, 1], linestyle="dotted", color=color, linewidth=1)
