# rosetta/drawing.py
import swisseph as swe
import matplotlib.pyplot as plt
from rosetta.helpers import deg_to_rad
from rosetta.lookup import ASPECTS, GLYPHS, GROUP_COLORS

# -------------------------------
# Chart element drawing
# -------------------------------
def draw_house_cusps(ax, df, asc_deg, house_system, dark_mode,
                     label_r=0.32, label_frac=0.50,  # ← knobs: radius & where along the house arc (0..1)
                     ):
    """
    Draw house cusp lines and numbers. Numbers are placed inside each house,
    at 'label_frac' of the forward arc from cusp i to cusp i+1 (0=at cusp, 0.5=midpoint).
    Returns a list of 12 cusp longitudes (House 1..12) in drawing order.
    """
    import pandas as pd

    def _forward_span(a, b):
        return (b - a) % 360.0

    def _forward_pos(a, b, frac):
        return (a + _forward_span(a, b) * frac) % 360.0

    cusps = []

# --- build cusp list only ---
    if house_system == "placidus":
        # 1) find the degree column robustly
        lower_cols = {c.lower().strip(): c for c in df.columns}
        deg_col = None
        for c in df.columns:
            nm = c.lower().strip()
            if "degree" in nm and ("computed" in nm or "abs" in nm or "absolute" in nm):
                deg_col = c
                break
        if deg_col is None:
            # last resort: accept a plain "longitude" for cusps if present
            if "longitude" in lower_cols:
                deg_col = lower_cols["longitude"]

        # 2) capture all rows that look like house cusps, regardless of exact naming
        #    (tolerates '1H Cusp', '1 H Cusp', 'House 1 Cusp', etc.)
        obj = df["Object"].astype("string")
        mask_cusp = obj.str.contains(r"\b(house\s*\d{1,2}|\d{1,2}\s*h)\s*cusp\b", case=False, regex=True, na=False)
        # also tolerate the exact legacy '1H Cusp' form:
        mask_cusp |= obj.str.match(r"^\s*\d{1,2}\s*H\s*Cusp\s*$", case=False, na=False)

        cusp_rows = df[mask_cusp].copy()

        # 3) if the calc tagged house system on cusp rows, filter to placidus
        if "House System" in cusp_rows.columns and cusp_rows["House System"].notna().any():
            hs = cusp_rows["House System"].astype("string").str.strip().str.lower()
            cusp_rows = cusp_rows[hs == "placidus"]

        # 4) extract the house index robustly (first 1–2 digits anywhere in the label)
        if not cusp_rows.empty:
            cusp_rows["__H"] = cusp_rows["Object"].astype("string").str.extract(r"(\d{1,2})").astype(int)
            cusp_rows = cusp_rows.sort_values("__H")

        # 5) build the list of 12 degrees
        cusps = []
        for _, row in cusp_rows.iterrows():
            val = row.get(deg_col)
            if pd.notna(val):
                try:
                    cusps.append(float(val))
                except Exception:
                    pass

    elif house_system == "equal":
        start = asc_deg % 360.0
        cusps = [ (start + i*30.0) % 360.0 for i in range(12) ]
    elif house_system == "whole":
        asc_sign_start = int(asc_deg // 30) * 30.0
        cusps = [ (asc_sign_start + i*30.0) % 360.0 for i in range(12) ]
    else:
        # fallback: behave like equal
        start = asc_deg % 360.0
        cusps = [ (start + i*30.0) % 360.0 for i in range(12) ]

    # If Placidus rows were missing for some reason, guard:
    if len(cusps) != 12:
        # fill evenly to avoid crashes
        start = asc_deg % 360.0
        cusps = [ (start + i*30.0) % 360.0 for i in range(12) ]

    # --- draw cusp lines ---
    line_color = "lightgray"
    for deg in cusps:
        rad = deg_to_rad(deg, asc_deg)
        ax.plot([rad, rad], [0, 1.45],
                color=line_color, linestyle="solid", linewidth=1,
                zorder=1)   # draw behind everything

    # --- place labels INSIDE each house (away from the line) ---
    lbl_color = "white" if dark_mode else "black"
    for i in range(12):
        a = cusps[i]
        b = cusps[(i + 1) % 12]
        label_deg = _forward_pos(a, b, label_frac)     # e.g., midpoint if 0.50
        label_rad = deg_to_rad(label_deg, asc_deg)
        ax.text(label_rad, label_r, str(i + 1),
                ha="center", va="center", fontsize=8, color=lbl_color,
                zorder=100)  # always on top

    return cusps

def draw_degree_markers(ax, asc_deg, dark_mode):
    """Draw tick marks at 1°, 5°, and 10° intervals, plus a circular outline."""

    base_color = "white" if dark_mode else "black"

    # --- Outer circle outline at r=1.0
    circle_r = 1.0
    circle = plt.Circle((0, 0), circle_r, transform=ax.transData._b, 
                        fill=False, color=base_color, linewidth=1,
                        zorder=5)  # middle layer
    ax.add_artist(circle)

    # --- Ticks every 1°
    for deg in range(0, 360, 1):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [circle_r, circle_r + 0.015], 
                color=base_color, linewidth=0.5, zorder=5)

    # --- Ticks every 5°
    for deg in range(0, 360, 5):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [circle_r, circle_r + 0.03], 
                color=base_color, linewidth=0.8, zorder=5)

    # --- Ticks + labels every 10°
    for deg in range(0, 360, 10):
        r = deg_to_rad(deg, asc_deg)
        ax.plot([r, r], [circle_r, circle_r + 0.05], 
                color=base_color, linewidth=1.2, zorder=5)
        ax.text(r, circle_r + 0.08, f"{deg % 30}°",
                ha="center", va="center", fontsize=7, color=base_color,
                zorder=5)


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

# -------------------------------
# Compass Rose (independent overlay)
# -------------------------------
def draw_compass_rose(
    ax, pos, asc_deg,
    *,
    colors=None,
    linewidth_base=2.0,
    zorder=100,
    arrow_mutation_scale=20.0,   # bigger default head
    nodal_width_multiplier=2.0,
    sn_dot_markersize=8.0,
):
    """
    Draw ONLY the three cardinal axes:
      - South Node → North Node (arrow, thicker, dot at SN)
      - Ascendant ↔ Descendant (line)
      - IC ↔ MC (line)

    Pure overlay: no dependency on circuits/shapes.
    """
    from rosetta.helpers import deg_to_rad

    if colors is None:
        colors = {"nodal": "purple", "acdc": "green", "mcic": "orange"}

    def _get_deg(name):
        return pos.get(name, None)

    # Layering: put simple axes under the nodal arrow.
    z_axes  = zorder + 1
    z_nodal_line = zorder + 2
    z_nodal_top  = zorder + 3  # arrowhead + SN dot

    # --- AC - DC (line, under) ---
    ac = _get_deg("Ascendant"); dc = _get_deg("Descendant")
    if ac is not None and dc is not None:
        r1 = deg_to_rad(ac, asc_deg); r2 = deg_to_rad(dc, asc_deg)
        ax.plot([r1, r2], [1, 1],
                color=colors["acdc"], linewidth=linewidth_base, zorder=z_axes)

    # --- MC - IC (line, under) ---
    mc = _get_deg("MC"); ic = _get_deg("IC")
    if mc is not None and ic is not None:
        r1 = deg_to_rad(mc, asc_deg); r2 = deg_to_rad(ic, asc_deg)
        ax.plot([r1, r2], [1, 1],
                color=colors["mcic"], linewidth=linewidth_base, zorder=z_axes)

    # --- Nodal axis: SN -> NN (on top) ---
    sn = _get_deg("South Node"); nn = _get_deg("North Node")
    if sn is not None and nn is not None:
        import numpy as np

        r_sn = deg_to_rad(sn, asc_deg)
        r_nn = deg_to_rad(nn, asc_deg)

        # Convert to Cartesian so we can trim the base line near NN
        x1, y1 = np.cos(r_sn) * 1.0, np.sin(r_sn) * 1.0
        x2, y2 = np.cos(r_nn) * 1.0, np.sin(r_nn) * 1.0

        vx, vy = (x2 - x1), (y2 - y1)
        # >>> TUNE THIS: fraction of the SN→NN chord to trim from the NN end
        head_trim_frac = 0.05  # try 0.03–0.10 to taste

        x2_trim = x2 - head_trim_frac * vx
        y2_trim = y2 - head_trim_frac * vy

        # Back to polar for plotting the trimmed BASE line
        r2_trim_theta = np.arctan2(y2_trim, x2_trim)
        r2_trim_rad   = np.hypot(x2_trim, y2_trim)

        # Thick base chord, trimmed so the arrow head can cover the end
        ax.plot([r_sn, r2_trim_theta], [1.0, r2_trim_rad],
                color=colors["nodal"],
                linewidth=linewidth_base * nodal_width_multiplier,
                zorder=z_nodal_line)

        # Arrow from SN to NN (no shrink tricks—head naturally covers trimmed end)
        ax.annotate(
            "",
            xy=(r_nn, 1.0), xytext=(r_sn, 1.0),
            arrowprops=dict(
                arrowstyle="-|>",
                mutation_scale=arrow_mutation_scale,  # size knob
                lw=linewidth_base * nodal_width_multiplier,
                color=colors["nodal"],
                shrinkA=0,  # tail flush at SN
                shrinkB=0,  # let head land at NN; base line is already trimmed
            ),
            zorder=z_nodal_top
        )

        # Dot at SN end (above everything)
        ax.plot([r_sn], [1.0], marker="o",
                markersize=sn_dot_markersize,
                color=colors["nodal"],
                zorder=z_nodal_top)

# -------------------------------
# Aspect lines (master truth)
# -------------------------------

def draw_aspect_lines(
    ax,
    pos,
    patterns,
    active_patterns,
    asc_deg,
    group_colors=None,
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
    if group_colors is None:
        group_colors = GROUP_COLORS

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
            
def draw_singleton_dots(ax, pos, active_singletons, shape_edges, asc_deg, line_width=2.0):
    """
    Draw a dot for each active singleton planet IF it has no visible aspect lines.
    """
    for obj in active_singletons:
        if obj not in pos:
            continue

        # Check if this object participates in any drawn aspect edges
        has_edge = any(obj in edge for edge in shape_edges)

        if not has_edge:
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

def draw_minor_edges(ax, pos, edges, asc_deg, group_color=None):
    """
    Draw minor-aspect edges inside a parent pattern (always dotted).
    edges: list of ((p1, p2), aspect_name)
    If group_color is given, use that instead of the aspect default.
    """
    for (p1, p2), asp in edges:
        d1, d2 = pos.get(p1), pos.get(p2)
        if d1 is None or d2 is None:
            continue
        r1 = deg_to_rad(d1, asc_deg)
        r2 = deg_to_rad(d2, asc_deg)

        if group_color is not None:
            color = group_color
        else:
            color = ASPECTS[asp]["color"] if asp in ASPECTS else "gray"

        ax.plot([r1, r2], [1, 1], linestyle="dotted", color=color, linewidth=1)
