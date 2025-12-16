import numpy as np
import os
import matplotlib.patheffects as pe
from now_v2 import _moon_phase_label_emoji
from lookup_v2 import GROUP_COLORS, GROUP_COLORS_LIGHT, SUBSHAPE_COLORS, SUBSHAPE_COLORS_LIGHT
from src.ui_state_helpers import _get_profile_lat_lon
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.collections import LineCollection
from matplotlib.colors import to_rgba, to_hex
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
import matplotlib.image as mpimg

def deg_to_rad(deg: float, asc_shift: float = 0.0) -> float:
	"""Convert an absolute degree into the polar coordinate used for plotting."""
	return np.deg2rad((360 - (deg - asc_shift + 180) % 360 + 90) % 360)


def _segment_points(theta1: float, theta2: float, radius: float = 1.0, steps: int = 48) -> tuple[np.ndarray, np.ndarray]:
	"""Return theta/r arrays describing the straight chord between two polar points."""

	x1, y1 = radius * np.cos(theta1), radius * np.sin(theta1)
	x2, y2 = radius * np.cos(theta2), radius * np.sin(theta2)
	xs = np.linspace(x1, x2, steps)
	ys = np.linspace(y1, y2, steps)
	thetas = np.unwrap(np.arctan2(ys, xs))
	radii = np.hypot(xs, ys)
	return thetas, radii

def _draw_gradient_line(
	ax,
	theta1: float,
	theta2: float,
	color_start: str,
	color_end: str,
	linewidth: float,
	linestyle: str,
	radius: float = 1.0,
) -> None:
	"""
	Draw a chord between two polar angles with either:
	  - SOLID (with gradient if colors differ), or
	  - DOTTED/DASHED/DASHDOT (simulated using many short solid segments),
	so that we can keep a smooth color gradient AND a visible pattern.
	"""
	def _vec(th):
		return np.cos(th) * radius, np.sin(th) * radius

	def _interp_xy(t):
		x = (1.0 - t) * x1 + t * x2
		y = (1.0 - t) * y1 + t * y2
		return x, y

	def _xy_to_polar(x, y):
		return np.arctan2(y, x), np.hypot(x, y)

	# endpoints in Cartesian on the unit ring
	x1, y1 = _vec(theta1)
	x2, y2 = _vec(theta2)
	chord_len = float(np.hypot(x2 - x1, y2 - y1))  # ~[0, 2]

	style = (linestyle or "solid").lower()
	wants_pattern = style in ("dotted", "dashed", "dashdot")

	# ---------- PATTERNED (dotted/dashed) with GRADIENT ----------
	if wants_pattern:
		# Choose segment (dash) length and gap ratio that read well on screen.
		# Scale lengths by chord_len so visuals are consistent across spans.
		if style == "dotted":
			# lots of short "dots"
			seg_len = 0.02 * max(1.0, chord_len)     # length of a dot (in chord units)
			gap_ratio = 1.8                          # gap ~1.8x segment -> clear dots
		elif style == "dashdot":
			seg_len = 0.05 * max(1.0, chord_len)
			gap_ratio = 0.9
		else:  # dashed
			seg_len = 0.06 * max(1.0, chord_len)
			gap_ratio = 0.7

		# Number of dashes; clamp for stability
		step = seg_len * (1.0 + gap_ratio)
		n = max(6, int(np.ceil(chord_len / max(1e-6, step))))
		# How much of each cycle is "ink"
		fill = seg_len / max(1e-6, step)             # (0,1)

		# Build tiny solid segments and color each by the gradient at its midpoint
		seg_points = []
		seg_colors = []

		c0 = np.array(to_rgba(color_start))
		c1 = np.array(to_rgba(color_end))

		for i in range(n):
			t0 = i / n
			t1 = min(t0 + fill / n, 1.0)             # shorten to leave a gap
			if t1 <= t0:
				continue

			xm0, ym0 = _interp_xy(t0)
			xm1, ym1 = _interp_xy(t1)
			th0, r0 = _xy_to_polar(xm0, ym0)
			th1, r1 = _xy_to_polar(xm1, ym1)
			seg_points.append([[th0, r0], [th1, r1]])

			tm = 0.5 * (t0 + t1)
			rgba = (1.0 - tm) * c0 + tm * c1
			seg_colors.append(tuple(rgba))

		if not seg_points:
			return

		lc = LineCollection(
			np.array(seg_points),
			colors=seg_colors,
			linewidth=linewidth,
			linestyle="solid",           # each short segment is solid; spacing makes the pattern
			capstyle="round",
			joinstyle="round",
		)
		ax.add_collection(lc)
		return

	# ---------- SOLID ----------
	# Build a single polyline; if colors differ, use a gradient LineCollection.
	steps = max(16, int(64 * chord_len))
	thetas, radii = _segment_points(theta1, theta2, radius=radius, steps=steps)

	if color_start == color_end:
		ax.plot(thetas, radii, color=color_start, linewidth=linewidth, linestyle="solid")
		return

	pts = np.column_stack([thetas, radii])
	segs = np.stack([pts[:-1], pts[1:]], axis=1)

	c0 = np.array(to_rgba(color_start))
	c1 = np.array(to_rgba(color_end))
	cols = [tuple((1.0 - t) * c0 + t * c1) for t in np.linspace(0, 1, len(segs))]

	lc = LineCollection(segs, colors=cols, linewidth=linewidth)
	lc.set_linestyle("solid")
	lc.set_capstyle("round")
	lc.set_joinstyle("round")
	ax.add_collection(lc)
	
def _light_variant_for(color: str) -> str:
	"""Return a lighter + less-opaque variant of `color`.
	1) If `color` is in GROUP_COLORS or SUBSHAPE_COLORS, return the matching *_LIGHT entry.
	2) Otherwise, blend the RGB toward white and scale alpha down.
	"""
	# 1) Exact palette matches first
	try:
		idx = GROUP_COLORS.index(color)
		if idx < len(GROUP_COLORS_LIGHT):
			return GROUP_COLORS_LIGHT[idx]
	except ValueError:
		pass

	try:
		idx = SUBSHAPE_COLORS.index(color)
		if idx < len(SUBSHAPE_COLORS_LIGHT):
			return SUBSHAPE_COLORS_LIGHT[idx]
	except ValueError:
		pass

	# 2) Generic fallback: lighten + reduce opacity
	# Tune these two knobs if you want a different feel:
	BLEND_TOWARD_WHITE = 0.35  # 0..1 (higher = lighter)
	ALPHA_SCALE = 0.6          # 0..1 (lower = more transparent)

	r, g, b, a = to_rgba(color)

	# Lighten toward white
	r = r + (1.0 - r) * BLEND_TOWARD_WHITE
	g = g + (1.0 - g) * BLEND_TOWARD_WHITE
	b = b + (1.0 - b) * BLEND_TOWARD_WHITE

	# Reduce opacity (respect any existing alpha)
	a = a * ALPHA_SCALE

	return to_hex((r, g, b, a), keep_alpha=True)

def _lighten_color(color: str, blend: float = 0.5) -> str:
	"""Blend ``color`` toward white by ``blend`` (0..1)."""

	blend = max(0.0, min(1.0, blend))
	r, g, b, a = to_rgba(color)
	r = r + (1.0 - r) * blend
	g = g + (1.0 - g) * blend
	b = b + (1.0 - b) * blend
	return to_hex((r, g, b, a), keep_alpha=True)


def _draw_header_on_figure(fig, name, date_line, time_line, city, extra_line, dark_mode):
	"""Paint header in the figure margin (top-left), with extra_line on same line as name (non-bold)."""

	color  = "white" if dark_mode else "black"
	stroke = "black" if dark_mode else "white"
	effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

	y0 = 0.99   # top margin in figure coords
	x0 = 0.00   # left margin

	# 1) Bold chart name (left)
	name_text = fig.text(
		x0, y0, name,
		ha="left", va="top",
		fontsize=12, fontweight="bold",
		color=color, path_effects=effects
	)

	# 2) Optional extra line on SAME TOP LINE, normal size, right after name
	if extra_line:
		# Force a draw so we can measure the name's pixel width reliably
		fig.canvas.draw()
		renderer = fig.canvas.get_renderer()

		name_bbox = name_text.get_window_extent(renderer=renderer)
		fig_bbox  = fig.get_window_extent(renderer=renderer)

		# Convert the name's pixel width to figure-coordinate width
		dx = name_bbox.width / fig_bbox.width

		# Small horizontal padding in figure coords
		pad = 0.01

		fig.text(
			x0 + dx + pad, y0, extra_line,
			ha="left", va="top",
			fontsize=9, fontweight=None,
			color=color, path_effects=effects
		)

	# 3) Stack the remaining lines below
	lines = []
	if date_line:
		lines.append(date_line)
	if time_line:
		lines.append(time_line)
	if city:
		lines.append(city)

	for idx, line in enumerate(lines, start=1):
		fig.text(
			x0,
			y0 - 0.035 * idx,
			line,
			ha="left",
			va="top",
			fontsize=9,
			color=color,
			path_effects=effects,
		)

def _draw_header_on_figure_right(fig, name, date_line, time_line, city, extra_line, dark_mode):
	"""Paint header in the figure margin (top-right), with maroon color for chart 2."""

	color  = "#6D0000"  # Maroon color for chart 2
	stroke = "black" if dark_mode else "white"
	effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

	y0 = 0.99   # top margin in figure coords
	x0 = 0.98   # right side positioning (closer to edge but within bounds)

	# 1) Bold chart name (right-aligned)
	name_text = fig.text(
		x0, y0, name,
		ha="right", va="top",
		fontsize=12, fontweight="bold",
		color=color, path_effects=effects
	)

	# 2) Optional extra line on SAME TOP LINE, normal size, before name
	if extra_line:
		# Force a draw so we can measure the name's pixel width reliably
		fig.canvas.draw()
		renderer = fig.canvas.get_renderer()

		name_bbox = name_text.get_window_extent(renderer=renderer)
		fig_bbox  = fig.get_window_extent(renderer=renderer)

		# Convert the name's pixel width to figure-coordinate width
		dx = name_bbox.width / fig_bbox.width

		# Small horizontal padding in figure coords
		pad = 0.01

		fig.text(
			x0 - dx - pad, y0, extra_line,
			ha="right", va="top",
			fontsize=9, fontweight=None,
			color=color, path_effects=effects
		)

	# 3) Stack the remaining lines below
	lines = []
	if date_line:
		lines.append(date_line)
	if time_line:
		lines.append(time_line)
	if city:
		lines.append(city)

	for idx, line in enumerate(lines, start=1):
		fig.text(
			x0,
			y0 - 0.035 * idx,
			line,
			ha="right",
			va="top",
			fontsize=9,
			color=color,
			path_effects=effects,
		)


def _draw_moon_phase_on_axes(ax, df, dark_mode: bool, icon_frac: float = 0.10) -> None:
	"""
	Draw the chart-based moon phase (icon + label) INSIDE the main chart axes,
	anchored at the upper-right corner. This does NOT change the figure/frame size.
	icon_frac = width/height of inset as a fraction of the parent axes.
	"""
	try:
		if df is None or "Object" not in df or "Longitude" not in df:
			return

		sun_row  = df[df["Object"].astype(str).str.lower() == "sun"].head(1)
		moon_row = df[df["Object"].astype(str).str.lower() == "moon"].head(1)
		if sun_row.empty or moon_row.empty:
			return

		sun_lon  = float(sun_row["Longitude"].iloc[0]) % 360.0
		moon_lon = float(moon_row["Longitude"].iloc[0]) % 360.0

		# Reuse your existing mapping to get label + PNG path
		label, icon_path = _moon_phase_label_emoji(sun_lon, moon_lon, emoji_size_px=None)
		if not os.path.exists(icon_path):
			return

		# --- ICON inset inside the axes (upper-right) ---
		icon_ax = inset_axes(
			ax,
			width=f"{int(icon_frac * 100)}%",
			height=f"{int(icon_frac * 100)}%",
			loc="upper right",
			bbox_to_anchor=(0.0, 0.075, 1.0, 1.0),   # <<< push the icon a bit DOWN
			bbox_transform=ax.transAxes,
			borderpad=0.0,
		)

		icon_ax.set_axis_off()
		try:
			img = mpimg.imread(icon_path)
			icon_ax.imshow(img)
		except Exception:
			pass

		# --- LABEL just to the left of the icon (still inside axes) ---
		color  = "white" if dark_mode else "black"
		stroke = "black" if dark_mode else "white"
		effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

		ax.text(
			0.89, 1.078, label,                 # <<< y almost at 1.0 (top); x near right edge
			transform=ax.transAxes,
			ha="right", va="top",
			fontsize=10, color=color, path_effects=effects, zorder=10,
		)

	except Exception:
		# decorative only; fail silently
		return


def _earth_emoji_for_region(lat: float | None, lon: float | None) -> str:
	"""
	Region mapping requested:
	  - Africa, Europe, Middle East: 🌍
	  - The Americas: 🌎
	  - Asia and Australia: 🌏
	  - Any other obscure locations: 🌎
	  - Unknown chart location: 🌐
	"""
	if lat is None or lon is None:
		# If location isn’t known yet, reserve the 'unknown' globe
		return "🌐"

	# Normalize longitude to [-180, 180]
	try:
		lon = ((lon + 180.0) % 360.0) - 180.0
	except Exception:
		return "🌎"

	# Coarse, readable bands by longitude:
	# Americas: roughly [-170, -30]
	if -170.0 <= lon <= -30.0:
		return "🌎"  # Americas

	# Europe / Africa / Middle East: roughly [-30, +60]
	if -30.0 < lon <= 60.0:
		return "🌍"

	# Asia / Australia: roughly (+60, +180]
	if 60.0 < lon <= 180.0:
		return "🌏"

	# Wraparound edge cases (e.g., extreme Pacific longitudes near -180/+180)
	# Treat as Asia/Australia band first; if you prefer Americas, swap this.
	if lon < -170.0 or lon > 180.0:
		return "🌏"

	# Fallback for anything weird/obscure
	return "🌎"



def draw_center_earth(ax, *, size: float = 0.22, zorder: int = 10_000) -> None:
	"""
	Draw a region-appropriate Earth PNG at the chart center.
	"""
	lat, lon = _get_profile_lat_lon()
	emoji = _earth_emoji_for_region(lat, lon)

	# Map emoji → filename
	mapping = {
		"🌍": "earth_africa.png",
		"🌎": "earth_americas.png",
		"🌏": "earth_asia.png",
		"🌐": "earth_americas.png",
	}
	fname = mapping.get(emoji, "earth_unknown.png")

	# Your folder: Rosetta_v2/pngs/<files>
	img_path = os.path.join(os.path.dirname(__file__), "pngs", fname)
	if not os.path.exists(img_path):
		return  # fail gracefully if file missing

	arr_img = mpimg.imread(img_path)
	imagebox = OffsetImage(arr_img, zoom=size)
	ab = AnnotationBbox(imagebox, (0, 0), frameon=False, zorder=zorder)
	ax.add_artist(ab)