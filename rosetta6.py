import streamlit as st
st.set_page_config(layout="wide")
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import streamlit.components.v1 as components
import swisseph as swe
import re
import os, json, bcrypt, time, hashlib
import streamlit_authenticator as stauth
import datetime as dt
import plotly.tools as tls
from rosetta.calc import calculate_chart
from rosetta.db import supa
from rosetta.auth_reset import request_password_reset, verify_reset_code_and_set_password
from rosetta.authn import get_auth_credentials, get_user_role_cached, ensure_user_row_linked
from rosetta.config import get_gemini_client, get_secret
from rosetta.brain import (
		build_context_for_objects,
		ask_gemini_brain,
		choose_task_instruction,
		load_fixed_star_catalog,
		ensure_profile_detail_strings,
)
from rosetta.users import (
	user_exists, create_user, get_user_role, is_admin,
	verify_password, set_password, delete_user_account,
	load_user_profiles_db, save_user_profile_db, delete_user_profile_db,
	community_list, community_get, community_save, community_delete,
)
from rosetta.helpers import (
	get_ascendant_degree, deg_to_rad, annotate_fixed_stars,
	get_fixed_star_meaning, build_aspect_graph, format_dms, format_longitude,
	SIGN_NAMES,
)
import rosetta.tts as T
from rosetta.drawing import (
	draw_house_cusps, draw_degree_markers, draw_zodiac_signs,
	draw_aspect_lines, draw_filament_lines,
	draw_shape_edges, draw_minor_edges, draw_singleton_dots,
	draw_compass_rose
)
from rosetta.patterns import (
	detect_minor_links_with_singletons, generate_combo_groups,
	detect_shapes, internal_minor_edges_for_pattern,
	connected_components_from_edges, _cluster_conjunctions_for_detection,
)
from rosetta.topics_wizard import WIZARD_TARGETS, apply_wizard_targets
import importlib
_L = importlib.import_module("rosetta.lookup")

def _Lget(name, default=None):
	# default empty dict to avoid NameError when used for lookups
	if default is None:
		default = {}
	return getattr(_L, name, default)

GLYPHS                       = _Lget("GLYPHS")
ASPECTS                      = _Lget("ASPECTS")
MAJOR_OBJECTS                = _Lget("MAJOR_OBJECTS")
OBJECT_MEANINGS              = _Lget("OBJECT_MEANINGS")
GROUP_COLORS                 = _Lget("GROUP_COLORS")
ASPECT_INTERPRETATIONS       = _Lget("ASPECT_INTERPRETATIONS")
INTERPRETATION_FLAGS         = _Lget("INTERPRETATION_FLAGS")
ZODIAC_SIGNS                 = _Lget("ZODIAC_SIGNS")
ZODIAC_COLORS                = _Lget("ZODIAC_COLORS")
MODALITIES                   = _Lget("MODALITIES")
HOUSE_INTERPRETATIONS        = _Lget("HOUSE_INTERPRETATIONS")
HOUSE_SYSTEM_INTERPRETATIONS = _Lget("HOUSE_SYSTEM_INTERPRETATIONS")
PLANETARY_RULERS             = _Lget("PLANETARY_RULERS")
DIGNITIES                    = _Lget("DIGNITIES")
SHAPE_INSTRUCTIONS           = _Lget("SHAPE_INSTRUCTIONS")
OBJECT_INTERPRETATIONS       = _Lget("OBJECT_INTERPRETATIONS")
CATEGORY_MAP                 = _Lget("CATEGORY_MAP")
CATEGORY_INSTRUCTIONS        = _Lget("CATEGORY_INSTRUCTIONS")
ALIASES_MEANINGS             = _Lget("ALIASES_MEANINGS")
SIGN_MEANINGS                = _Lget("SIGN_MEANINGS")
HOUSE_MEANINGS               = _Lget("HOUSE_MEANINGS")
OBJECT_MEANINGS_SHORT        = _Lget("OBJECT_MEANINGS_SHORT")

import streamlit as st, importlib
import importlib, rosetta.drawing
importlib.reload(rosetta.drawing)

@st.cache_resource
def get_lookup():
	return importlib.import_module("rosetta.lookup")

_L = get_lookup()
# same attribute assignments as above...

# --- Load fixed star catalog once ---
STAR_CATALOG = load_fixed_star_catalog("rosetta/2b) Fixed Star Lookup.xlsx")

_CANON_SHAPES = {k.lower(): k for k in SHAPE_INSTRUCTIONS}
_SHAPE_SYNONYMS = {
	"grand_trine": "Grand Trine", "grand-trine": "Grand Trine",
	"tsquare": "T-Square", "t-square": "T-Square",
	"mystic_rectangle": "Mystic Rectangle", "mystic-rectangle": "Mystic Rectangle",
	"yod": "Yod", "kite": "Kite", "wedge": "Wedge",
	"conjunction cluster": "Conjunction Cluster",
	"rhythm wedge": "Rhythm Wedge",
	"ease circuit": "Ease Circuit",
}

def _canonical_shape_name(shape_dict: dict) -> str:
	"""
	Return a canonical SHAPE_INSTRUCTIONS key for this shape, or "".
	Scans many common fields AND all string values, so we don't depend on a single key.
	"""
	if not isinstance(shape_dict, dict):
		return ""

	# 1) Candidate fields you might be using
	candidates = [
		shape_dict.get("type"), shape_dict.get("kind"),
		shape_dict.get("shape"), shape_dict.get("shape_type"),
		shape_dict.get("label"), shape_dict.get("name"),
		shape_dict.get("parent"), shape_dict.get("parent_name"),
		shape_dict.get("title"), shape_dict.get("display"), shape_dict.get("display_name"),
	]

	# 2) Also scan ALL string values (field-agnostic)
	for v in shape_dict.values():
		if isinstance(v, str):
			candidates.append(v)

	def _norm(s: str) -> str:
		s = re.sub(r"\(parent\)", "", s, flags=re.IGNORECASE)
		s = re.split(r"[—:-]", s, maxsplit=1)[0]   # strip adorners
		s = re.sub(r"[_\s]+", " ", s).strip().lower()
		return s

	# Try exact, synonyms, then contains
	for c in candidates:
		if not c or not isinstance(c, str):
			continue
		t = _norm(c)
		if not t:
			continue
		if t in _CANON_SHAPES:
			return _CANON_SHAPES[t]
		if t in _SHAPE_SYNONYMS:
			return _SHAPE_SYNONYMS[t]
		for lk, canon in _CANON_SHAPES.items():
			if lk in t:  # contains
				return canon
	return ""

genai = get_gemini_client()

# -------------------------
# Init / session management
# -------------------------
if "reset_done" not in st.session_state:
	st.session_state.clear()
	st.session_state["reset_done"] = True

if "last_house_system" not in st.session_state:
	st.session_state["last_house_system"] = "equal"

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
st.caption("Mobile users: click » at the top left to login, and to view planet profiles")

def _credentials_from_db():
	sb = supa()
	res = sb.table("users").select("username,name,email,pw_hash").execute()
	users = res.data or []
	return {
		"usernames": {
			u["username"]: {
				"name": u["name"],
				"email": u["email"],
				"password": u["pw_hash"]
			} for u in users
		}
	}

@st.cache_data(ttl=60)
def _credentials_from_db_cached():
	return _credentials_from_db()

@st.cache_data(ttl=600)
def user_exists_in_db(username: str) -> bool:
	sb = supa()
	return bool(sb.table("users").select("username").eq("username", username).limit(1).execute().data)

@st.cache_data(ttl=60)
def load_user_profiles_db_cached(user_id: str) -> dict:
	return load_user_profiles_db(user_id)  # your existing helper


# --- Authentication (admin-gated user management; no public registration) ---
creds = get_auth_credentials()
auth_cfg = st.secrets.get("auth", {})
cookie_name  = auth_cfg.get("cookie_name", "rosetta_auth")
cookie_key   = auth_cfg.get("cookie_key", "change_me")
cookie_days  = int(auth_cfg.get("cookie_expiry_days", 30))

authenticator = stauth.Authenticate(
	credentials=creds,
	cookie_name=cookie_name,
	key=cookie_key,
	cookie_expiry_days=cookie_days
)

# ---- SIDEBAR LOGIN (your shim) ----
with st.sidebar:
	# Version-agnostic login shim (as you have it)
	try:
		out = authenticator.login(location="sidebar", form_name="Login")
	except TypeError:
		try:
			out = authenticator.login("sidebar", "Login")
		except TypeError:
			out = authenticator.login("sidebar", fields={"Form name": "Login"})

	# Normalize return value from streamlit_authenticator (tuple vs dict)
	auth_name = None
	auth_status = None
	auth_user = None
	try:
		# tuple style: (name, auth_status, username)
		auth_name, auth_status, auth_user = out
	except Exception:
		# dict style
		if isinstance(out, dict):
			auth_name = out.get("name")
			auth_status = out.get("authentication_status")
			auth_user = out.get("username")

	st.write("")  # small spacer

	# ------- Forgot Password flow (visible when NOT authenticated) -------
	if auth_status is not True:
		st.markdown("**Forgot password?**")

		# Step toggles in session_state (sidebar-specific keys)
		show_reset = st.session_state.get("sb_show_reset_flow", False)
		if st.button("Start reset"):
			st.session_state["sb_show_reset_flow"] = True
			show_reset = True

		if show_reset:
			st.divider()
			st.subheader("Reset your password")

			ident = st.text_input("Username or email", key="sb_reset_ident")
			if st.button("Email me a reset code", key="sb_btn_sendcode"):
				ok, uname, msg = request_password_reset(ident)
				if not ok:
					st.error(msg)
				else:
					st.session_state["sb_reset_username"] = uname
					st.session_state["sb_show_reset_step2"] = True
					if msg == "sent":
						st.success("If that account exists, a code was sent. Check your email.")
					else:
						# DEV mode: SMTP not configured; show code so the user can proceed
						st.info(f"DEV CODE for **{uname}** (15 min): **{msg}**")

		if st.session_state.get("sb_show_reset_step2"):
			code = st.text_input("6-digit code", key="sb_reset_code")
			npw1 = st.text_input("New password", type="password", key="sb_reset_np1")
			npw2 = st.text_input("Confirm new password", type="password", key="sb_reset_np2")

			if st.button("Set new password", key="sb_btn_setpw"):
				if not npw1 or npw1 != npw2:
					st.error("Passwords don’t match.")
				else:
					uname = st.session_state.get("sb_reset_username", "")
					if verify_reset_code_and_set_password(uname, code, npw1):
						st.success("Password reset. Log in with your new password.")
						# clean up sidebar state
						for k in ["sb_show_reset_flow", "sb_show_reset_step2", "sb_reset_username",
								  "sb_reset_ident", "sb_reset_code", "sb_reset_np1", "sb_reset_np2"]:
							st.session_state.pop(k, None)
					else:
						st.error("Invalid or expired code.")

if isinstance(out, tuple) and len(out) == 3:
	name, auth_status, username = out
else:
	name = st.session_state.get("name")
	auth_status = st.session_state.get("authentication_status")
	username = st.session_state.get("username")

if auth_status is True:
	current_user_id = username

	with st.sidebar:
		role = get_user_role_cached(current_user_id)
		st.caption(f"Logged in as **{name}** ({username}) — role: **{role}**")
		authenticator.logout("Logout", location="sidebar")

	# Ensure a users row exists for THIS login, using the existing password hash from creds
	ok, msg = ensure_user_row_linked(
		current_user_id,
		creds,
		display_name=(name or current_user_id)
	)
	if not ok:
		st.error(msg)
		st.stop()
	elif msg:
		st.success(msg)
		st.rerun()

	admin_flag = is_admin(current_user_id)  # now safe

	with st.sidebar:

		# Self-serve: Change Password (available to everyone)
		with st.expander("Change Password"):
			cur = st.text_input("Current password", type="password")
			new1 = st.text_input("New password", type="password")
			new2 = st.text_input("Repeat new password", type="password")
			if st.button("Update password"):
				if not (cur and new1 and new2):
					st.error("All fields are required.")
				elif new1 != new2:
					st.error("New passwords must match.")
				else:
					# Check against DB hash
					ok_db = verify_password(current_user_id, cur)

					# Also check against the authenticator's in-memory hash (in case of stale cookie)
					ok_db = verify_password(current_user_id, cur)
					if not ok_db:
						st.error("Current password is incorrect.")
					else:
						set_password(current_user_id, new1)
						st.success("Password updated.")
						st.rerun()

		# Admin-only: user management (create users / reset passwords)
		if admin_flag:
			with st.expander("Admin: User Management"):
				st.markdown("**Create user**")
				u = st.text_input("Username", key="admin_new_user")
				full = st.text_input("Full name", key="admin_new_name")
				em = st.text_input("Email", key="admin_new_email")
				role = st.selectbox("Role", ["user", "admin"], index=0, key="admin_new_role")
				temp = st.text_input("Temp password", type="password", key="admin_new_pw")
				if st.button("Create user", key="admin_create_user"):
					if not (u and full and em and temp):
						st.error("All fields are required.")
					elif user_exists(u):
						st.error("Username already exists.")
					else:
						create_user(u, full, em, temp, role=role)
						st.success(f"User '{u}' created with role '{role}'.")

				st.markdown("---")
				st.markdown("**Reset a user's password**")
				target = st.text_input("Username to reset", key="admin_reset_user")
				npw1 = st.text_input("New password", type="password", key="admin_reset_pw1")
				npw2 = st.text_input("Repeat new password", type="password", key="admin_reset_pw2")
				if st.button("Reset password", key="admin_reset_pw_btn"):
					if not (target and npw1 and npw2):
						st.error("All fields are required.")
					elif npw1 != npw2:
						st.error("Passwords must match.")
					elif not user_exists(target):
						st.error("No such username.")
					else:
						set_password(target, npw1)
						st.rerun()  # ✅ causes top-level creds = get_auth_credentials() to refresh
						st.success(f"Password reset for '{target}'.")

				target = st.text_input("Username to delete", key="admin_del_user")
				if st.button("Delete user", key="admin_del_btn"):
					if not target:
						st.error("Enter a username.")
					elif not user_exists(target):
						st.error("No such username.")
					else:
						delete_user_account(target)
						st.success(f"User '{target}' has been deleted.")

elif auth_status is False:
	st.error("Incorrect username or password.")
	st.stop()
else:
	st.info("Please log in to continue.")
	st.stop()

# -------------------------
# Chart Drawing Functions
# -------------------------
def _selected_house_system():
	s = st.session_state.get("house_system_main", "Equal")
	return s.lower().replace(" sign", "")

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
	"""Draw tick marks at 1°, 5°, and 10° intervals, plus a circular outline."""

	base_color = "white" if dark_mode else "black"

	# --- Outer circle outline at r=1.0
	circle_r = 1.0
	circle = plt.Circle((0, 0), circle_r, transform=ax.transData._b, 
						fill=False, color=base_color, linewidth=1)
	ax.add_artist(circle)

	# --- Ticks every 1°
	for deg in range(0, 360, 1):
		r = deg_to_rad(deg, asc_deg)
		ax.plot([r, r], [circle_r, circle_r + 0.015], 
				color=base_color, linewidth=0.5)

	# --- Ticks every 5°
	for deg in range(0, 360, 5):
		r = deg_to_rad(deg, asc_deg)
		ax.plot([r, r], [circle_r, circle_r + 0.03], 
				color=base_color, linewidth=0.8)

	# --- Ticks + labels every 10°
	for deg in range(0, 360, 10):
		r = deg_to_rad(deg, asc_deg)
		ax.plot([r, r], [circle_r, circle_r + 0.05], 
				color=base_color, linewidth=1.2)


import numpy as np  # (already imported near top; keep once)
import numpy as np  # already imported above; keep once

def draw_zodiac_signs(ax, asc_deg):
	"""Draw zodiac signs + modalities around the wheel, with a pastel element ring and black dividers."""

	# Remap requested:
	PASTEL_BLUE   = "#D9EAF7"  # blue
	PASTEL_GREEN  = "#D9EAD3"  # green
	PASTEL_ORANGE = "#FFD1B3"  # orange
	PASTEL_RED    = "#EAD1DC"  # soft red/pink

	# After-remap element → color
	element_color = {
		"fire":  PASTEL_BLUE,    # was orange → blue
		"earth": PASTEL_RED,     # was green  → red
		"air":   PASTEL_GREEN,   # was blue   → green
		"water": PASTEL_ORANGE,  # was red    → orange
	}

	# Aries→Pisces elements
	elements = ["fire", "earth", "air", "water"] * 3

	sector_width = np.deg2rad(30)

	# 🔹 Radii for ring vs. dividers (independent)
	ring_inner, ring_outer = 1.45, 1.58
	divider_inner, divider_outer = 1.457, 1.573

	# Background ring: 12 annular bars (polar-aware, so it's a true circle)
	for i in range(12):
		theta_left = deg_to_rad(i * 30, asc_deg)
		ax.bar(
			theta_left,
			ring_outer - ring_inner,
			width=sector_width,
			bottom=ring_inner,
			align="edge",
			color=element_color[elements[i]],
			edgecolor=None,
			linewidth=0,
			alpha=0.85,
			zorder=0,
		)

	# Glyphs
	for i, base_deg in enumerate(range(0, 360, 30)):
		rad = deg_to_rad(base_deg + 15, asc_deg)
		ax.text(
			rad, 1.50, ZODIAC_SIGNS[i],
			ha="center", va="center",
			fontsize=16, fontweight="bold",
			color=ZODIAC_COLORS[i],
			zorder=1,
		)

	# Black dividers at whole-sign boundaries
	asc_sign_start = int(asc_deg // 30) * 30.0
	cusps = [(asc_sign_start + i * 30.0) % 360.0 for i in range(12)]
	for deg in cusps:
		rad = deg_to_rad(deg, asc_deg)
		ax.plot(
			[rad, rad],
			[divider_inner, divider_outer],
			color="black",
			linestyle="solid",
			linewidth=1,
			zorder=5,  # above ring, below glyphs
		)

def draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode):
	"""Draw planet glyphs/names with degree (no sign), combining cluster fan-out with global spacing."""

	degree_threshold = 3  # how close in degrees to be considered a cluster
	min_spacing = 7       # degrees of minimum separation between clusters

	# ---- group planets into clusters ----
	sorted_pos = sorted(pos.items(), key=lambda x: x[1])
	clusters = []
	for name, degree in sorted_pos:
		placed = False
		for cluster in clusters:
			if abs(degree - cluster[0][1]) <= degree_threshold:
				cluster.append((name, degree))
				placed = True
				break
		if not placed:
			clusters.append([(name, degree)])

	# ---- compute cluster anchor angles ----
	cluster_degrees = [sum(d for _, d in c) / len(c) for c in clusters]

	# ---- enforce global spacing between clusters ----
	for i in range(1, len(cluster_degrees)):
		if cluster_degrees[i] - cluster_degrees[i - 1] < min_spacing:
			cluster_degrees[i] = cluster_degrees[i - 1] + min_spacing

	# wrap-around check (last vs first)
	if (cluster_degrees[0] + 360.0) - cluster_degrees[-1] < min_spacing:
		cluster_degrees[-1] = cluster_degrees[0] + 360.0 - min_spacing

	color = "white" if dark_mode else "black"

	# ---- draw planets within each cluster ----
	for cluster, base_degree in zip(clusters, cluster_degrees):
		n = len(cluster)
		if n == 1:
			items = [(cluster[0][0], cluster[0][1])]  # keep the true degree
		else:
			# Fan-out cluster members around base_degree (for positioning only)
			spread = 3  # degrees per step inside the cluster
			start = base_degree - (spread * (n - 1) / 2)
			items = [(name, start + i * spread) for i, (name, _) in enumerate(cluster)]

		# ---- draw each item ----
		for (name, display_degree), (_, true_degree) in zip(items, cluster):
			# True values (for labels)
			deg_true = true_degree % 360.0
			rad_true = deg_to_rad(display_degree % 360.0, asc_deg)

			# Labels (from true degree, never shifted)
			base_label = GLYPHS.get(name, name) if label_style == "Glyph" else name
			deg_int = int(deg_true % 30)
			deg_label = f"{deg_int}°"

			# Draw glyph
			ax.text(rad_true, 1.35, base_label,
					ha="center", va="center", fontsize=9, color=color)

			# Draw degree
			ax.text(rad_true, 1.27, deg_label,
					ha="center", va="center", fontsize=6, color=color)

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

_HS_LABEL = {"equal": "Equal", "whole": "Whole Sign", "placidus": "Placidus"}

def format_planet_profile(row):
	"""Styled planet profile with glyphs, line breaks, and conditional extras."""
	name = row["Object"]
	canonical = ALIASES_MEANINGS.get(name, name)
	glyph = GLYPHS.get(canonical, "")
	sabian = str(row.get("Sabian Symbol", "")).strip()
	lon = row.get("Longitude", "")

	html_parts = []

	# --- Header (glyph + bold name) ---
	header = f"<div style='font-weight:bold; font-size:1.1em;'>{glyph} {canonical}</div>"
	html_parts.append(header)

	# --- Object Meaning (right after the header) ---
	meaning = OBJECT_MEANINGS.get(name, "")
	if meaning:
		html_parts.append(f"<div style='font-size:0.9em; margin-bottom:4px;'>{meaning}</div>")

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
	detail_strings = ensure_profile_detail_strings(row)
	for label in [
			"Speed",
			"Latitude",
			"Declination",
			"Out of Bounds",
			"Conjunct Fixed Star",
	]:
			val_str = detail_strings.get(label)
			if val_str:
					html_parts.append(f"<div style='font-size:0.9em;'>{label}: {val_str}</div>")

	# Force single spacing with line-height here
	return "<div style='line-height:1.1; margin-bottom:6px;'>" + "".join(html_parts) + "</div>"

from matplotlib.patches import FancyBboxPatch

def _current_chart_header_lines():
	name = (
		st.session_state.get("current_profile_title")
		or st.session_state.get("current_profile")
		or "Untitled Chart"
	)
	if isinstance(name, str) and name.startswith("community:"):
		name = "Community Chart"

	month  = st.session_state.get("profile_month_name", "")
	day    = st.session_state.get("profile_day", "")
	year   = st.session_state.get("profile_year", "")
	hour   = st.session_state.get("profile_hour")
	minute = st.session_state.get("profile_minute")
	city   = st.session_state.get("profile_city", "")

	# 12-hour time
	time_str = ""
	if hour is not None and minute is not None:
		h = int(hour); m = int(minute)
		ampm = "AM" if h < 12 else "PM"
		h12  = 12 if (h % 12 == 0) else (h % 12)
		time_str = f"{h12}:{m:02d} {ampm}"

	date_line = f"{month} {day}, {year}".strip()
	if date_line and time_str:
		date_line = f"{date_line}, {time_str}"
	elif time_str:
		date_line = time_str

	return name, date_line, city
import matplotlib.patheffects as pe

import matplotlib.patheffects as pe

def _draw_header_on_figure(fig, name, date_line, city, dark_mode):
	"""Paint a 3-line header in the figure margin (top-left), never over the wheel."""
	color  = "white" if dark_mode else "black"
	stroke = "black" if dark_mode else "white"
	effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

	y0 = 0.99   # top margin in figure coords
	x0 = 0.00   # left margin

	fig.text(x0, y0, name, ha="left", va="top",
			 fontsize=12, fontweight="bold", color=color, path_effects=effects)
	if date_line:
		fig.text(x0, y0 - 0.035, date_line, ha="left", va="top",
				 fontsize=9, color=color, path_effects=effects)
	if city:
		fig.text(x0, y0 - 0.065, city, ha="left", va="top",
				 fontsize=9, color=color, path_effects=effects)

def _draw_header_on_ax(ax, name, date_line, city, dark_mode, loc="upper left"):
	"""
	Write a compact 3-line header near the top of the chart without covering the wheel.
	Uses a subtle stroke outline for readability instead of a background panel.
	loc: 'upper left' | 'top center' | 'upper right'
	"""
	fg      = "white" if dark_mode else "black"
	stroke  = "black" if dark_mode else "white"
	effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

	# anchor & alignment
	if loc == "upper right":
		x, ha = 0.98, "right"
	elif loc == "top center":
		x, ha = 0.50, "center"
	else:
		x, ha = 0.02, "left"     # upper left (default)

	# y just inside the axes so it doesn't sit on the frame
	y0 = 0.995
	line_h = 0.048   # vertical spacing between lines

	# Name (bold)
	ax.text(
		x, y0, name,
		transform=ax.transAxes, ha=ha, va="top",
		fontsize=11, fontweight="bold", color=fg,
		path_effects=effects, clip_on=False, zorder=10,
	)
	# Date/time
	if date_line:
		ax.text(
			x, y0 - line_h, date_line,
			transform=ax.transAxes, ha=ha, va="top",
			fontsize=9, color=fg,
			path_effects=effects, clip_on=False, zorder=10,
		)
	# City
	if city:
		ax.text(
			x, y0 - 2*line_h, city,
			transform=ax.transAxes, ha=ha, va="top",
			fontsize=9, color=fg,
			path_effects=effects, clip_on=False, zorder=10,
		)

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
	ax.set_rlim(0, 1.60)
	ax.axis("off")

	# 🔑 force the polar axes to be centered and square
	ax.set_anchor("C")  # center anchor
	ax.set_aspect("equal", adjustable="box")

	# Manually set the axes to fill the figure square
	fig.subplots_adjust(left=0, right=0.85, top=0.95, bottom=0.05)

	# Header above the wheel (figure-level, so it won't overlap the plot)
	name, date_line, city = _current_chart_header_lines()
	_draw_header_on_figure(fig, name, date_line, city, dark_mode)

	# --- auto-heal: ensure DF cusps match the selected house system ---
	def _df_house_system(df):
		obj = df["Object"].astype("string")
		mask = obj.str.contains(r"\b(?:house\s*\d{1,2}|\d{1,2}\s*h)\s*cusp\b", case=False, regex=True, na=False)
		mask |= obj.str.match(r"^\s*\d{1,2}\s*H\s*Cusp\s*$", case=False, na=False)
		c = df[mask].copy()
		if c.empty:
			return None  # no cusp rows at all
		if "House System" in c.columns and c["House System"].notna().any():
			return c["House System"].astype("string").str.strip().str.lower().mode().iat[0]
		# if not tagged, assume whatever was last selected
		return st.session_state.get("last_house_system")

	# 1) see what system is actually in the DF (if any)
	_df_sys = _df_house_system(df)

	# 2) if mismatch or missing cusps, recompute once with the selected system
	if (_df_sys != house_system) or (_df_sys is None):
		lat0 = st.session_state.get("calc_lat")
		lon0 = st.session_state.get("calc_lon")
		tz0  = st.session_state.get("calc_tz")
		if None not in (lat0, lon0, tz0):
			run_chart(lat0, lon0, tz0, house_system)
			df = st.session_state.df  # use the freshly computed DF
			st.session_state["last_house_system"] = house_system
		else:
			st.warning("No cached location for recompute; enter a city or load a profile, then toggle again.")

	# Base wheel
	cusps = draw_house_cusps(ax, df, asc_deg, house_system, dark_mode)
	draw_degree_markers(ax, asc_deg, dark_mode)
	draw_zodiac_signs(ax, asc_deg)
	draw_planet_labels(ax, pos, asc_deg, label_style, dark_mode)

	active_parents = set(i for i, show in enumerate(toggles) if show)
	# Read the checkbox states directly from session (avoids the one-run lag)
	active_shape_ids = [
		s["id"]
		for s in shapes
		if st.session_state.get(f"shape_{s['parent']}_{s['id']}", False)
	]
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

	# --- Assemble ASPECTS for interpretation from what is actually drawn (single source of truth) ---
	aspects_for_context = []
	seen = set()  # dedupe by unordered pair + aspect

	def _add_edge(a, aspect, b):
		# normalize
		asp = (aspect or "").replace("_approx", "").strip()
		if not asp:
			return
		# (optional) skip conjunctions if you don't draw them as edges
		if asp.lower() == "conjunction":
			return
		key = (tuple(sorted([a, b])), asp)
		if key in seen:
			return
		seen.add(key)
		aspects_for_context.append({"from": a, "to": b, "aspect": asp})

	# parents first (major edges actually drawn)
	for idx in active_parents:
		if idx < len(patterns):
			visible_objects.update(patterns[idx])

			# majors where both points are inside this parent pattern (these are drawn)
			edges = [((p1, p2), asp_name)
					 for ((p1, p2), asp_name) in major_edges_all
					 if p1 in patterns[idx] and p2 in patterns[idx]]

			# record them for context
			for (p1, p2), asp in edges:
				_add_edge(p1, asp, p2)

			# optional: internal minors (drawn in parent color when layered)
			for p_idx in active_parents:
				if p_idx >= len(patterns):
					continue

				# internal minor edges from filaments (these are drawn)
				minor_edges = [((p1, p2), asp_name)
							   for (p1, p2, asp_name, pat1, pat2) in filaments
							   if pat1 == p_idx and pat2 == p_idx]

				for (p1, p2), asp in minor_edges:
					_add_edge(p1, asp, p2)

			# connectors (filaments) not already claimed by shapes or internal-minor overrides
			for (p1, p2, asp_name, pat1, pat2) in filaments:
				pair_key = frozenset((p1, p2))
				if pair_key in shape_edges:
					continue
				# skip internal minors; those are drawn separately above
				if pat1 == pat2:
					continue
				# also skip any pair we already drew as an internal minor (if that set exists)
				if 'claimed_internal_minors' in locals() and pair_key in claimed_internal_minors:
					continue

				in_parent1 = any((i in active_parents) and (p1 in patterns[i]) for i in active_parents)
				in_parent2 = any((i in active_parents) and (p2 in patterns[i]) for i in active_parents)
				in_shape1 = any(p1 in s["members"] for s in active_shapes)
				in_shape2 = any(p2 in s["members"] for s in active_shapes)
				in_singleton1 = p1 in active_singletons
				in_singleton2 = p2 in active_singletons

				if (in_parent1 or in_shape1 or in_singleton1) and (in_parent2 or in_shape2 or in_singleton2):
					# these dotted connectors are drawn, so include them
					_add_edge(p1, asp_name, p2)

	# sub-shapes: use their own edges list (these are drawn by draw_shape_edges)
	for s in active_shapes:
		visible_objects.update(s["members"])
		for (p1, p2), asp in s["edges"]:
			_add_edge(p1, asp, p2)

	# singletons (always mark them visible if toggled)
	visible_objects.update(active_singletons)

	if st.session_state.get("toggle_compass_rose"):
		visible_objects.update([
			"Ascendant", "Descendant", "MC", "IC",
			"North Node", "South Node",
		])

	# draw singleton dots (twice as wide as aspect lines)
	if active_singletons:
		draw_singleton_dots(ax, pos, active_singletons, shape_edges, asc_deg, line_width=2.0)

	# --- Compass Rose overlay (always independent of circuits/shapes) ---
	if st.session_state.get("toggle_compass_rose", True):
		draw_compass_rose(
			ax, pos, asc_deg,
			colors={"nodal": "purple", "acdc": "#4E83AF", "mcic": "#4E83AF"},
			linewidth_base=2.0,
			zorder=100,
			arrow_mutation_scale=22.0,   # bigger arrowhead
			nodal_width_multiplier=2.0,
			sn_dot_markersize=12.0
		)
		# add the compass axes aspects since they're visually overlaid
		if "South Node" in pos and "North Node" in pos:
			_add_edge("South Node", "Opposition", "North Node")
		if "Ascendant" in pos and "Descendant" in pos:
			_add_edge("Ascendant", "Opposition", "Descendant")
		if "MC" in pos and "IC" in pos:
			_add_edge("MC", "Opposition", "IC")

	# --- Build interpretation context (now includes the drawn edges only) ---
	context = build_context_for_objects(
		targets=list(visible_objects),  # only the toggled/visible ones
		pos=pos,
		df=df,
		active_shapes=active_shapes,
		aspects=aspects_for_context,    # <-- pass the single source of truth
		star_catalog=STAR_CATALOG,
		cusps=cusps, 
		row_cache=enhanced_objects_data,
		profile_rows=enhanced_objects_data, 
	)

	# --- Decide task & get interpretation ---
	task = choose_task_instruction(
		chart_mode="natal",               # placeholder for now
		visible_objects=list(visible_objects),
		active_shapes=active_shapes,
		context=context,
	)
	out_text = ask_gemini_brain(genai, task, context)

	return fig, visible_objects, active_shapes, cusps, out_text


from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder
import pytz

MONTH_NAMES = [
	"January", "February", "March", "April", "May", "June",
	"July", "August", "September", "October", "November", "December"
]

def _coerce_int(v, default=None):
	try:
		if v is None: return default
		return int(v)
	except Exception:
		return default

def _month_to_index(m):
	# Accept int 1-12, or month name like "July"
	if m is None: return None
	if isinstance(m, int):
		return m if 1 <= m <= 12 else None
	s = str(m).strip()
	# maybe it's a number string
	if s.isdigit():
		iv = int(s)
		return iv if 1 <= iv <= 12 else None
	# try name
	try:
		return MONTH_NAMES.index(s) + 1
	except ValueError:
		return None

def normalize_profile(prof: dict) -> dict:
	"""
	Accepts any of:
	  - {'year', 'month', 'day', 'hour', 'minute', 'city', 'lat','lon','tz_name','circuit_names'?}
	  - {'payload': { ...same as above... }}
	  - legacy keys like 'profile_year', 'profile_month_name', etc.
	Returns a dict with canonical keys as above. Missing values fall back to current session defaults.
	"""
	# unwrap payload
	if isinstance(prof, dict) and "payload" in prof and isinstance(prof["payload"], dict):
		prof = prof["payload"]

	# Gather possible sources
	year   = prof.get("year",   prof.get("profile_year"))
	month  = prof.get("month",  prof.get("profile_month", prof.get("month_name", prof.get("profile_month_name"))))
	day    = prof.get("day",    prof.get("profile_day"))
	hour   = prof.get("hour",   prof.get("profile_hour"))
	minute = prof.get("minute", prof.get("profile_minute"))
	city   = prof.get("city",   prof.get("profile_city"))

	# Fallbacks from session (so we don't explode)
	year   = _coerce_int(year,   st.session_state.get("profile_year", 1990))
	day    = _coerce_int(day,    st.session_state.get("profile_day", 1))
	hour   = _coerce_int(hour,   st.session_state.get("profile_hour", 0))
	minute = _coerce_int(minute, st.session_state.get("profile_minute", 0))
	if not city:
		city = st.session_state.get("profile_city", "")

	# Month can be int or name
	m_idx = _month_to_index(month)
	if m_idx is None:
		# try session default
		m_idx = _month_to_index(st.session_state.get("profile_month_name", "July"))
		if m_idx is None:
			m_idx = 7  # July as a last resort

	lat    = prof.get("lat")
	lon    = prof.get("lon")
	tzname = prof.get("tz_name")

	# Optional circuit names
	circuit_names = prof.get("circuit_names", {})

	return {
		"year": year,
		"month": m_idx,                 # 1..12
		"day": day,
		"hour": hour,                   # 0..23
		"minute": minute,               # 0..59
		"city": city,
		"lat": lat,
		"lon": lon,
		"tz_name": tzname,
		"circuit_names": circuit_names,
	}

# -------------------------
# CLEANED SESSION STATE INITIALIZATION
# -------------------------

# Initialize profile defaults (canonical values)
profile_defaults = {
	"profile_year": 1990,
	"profile_month_name": "January",
	"profile_day": 1,
	"profile_hour": 12,       # 24h format
	"profile_minute": 00,
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
# Apply loaded profile if present (robust to legacy/community formats)
if "_loaded_profile" in st.session_state:
	raw_prof = st.session_state["_loaded_profile"]
	prof = normalize_profile(raw_prof)

	# Update canonical profile_* keys
	st.session_state["profile_year"] = prof["year"]
	st.session_state["profile_month_name"] = MONTH_NAMES[prof["month"] - 1]
	st.session_state["profile_day"] = prof["day"]
	st.session_state["profile_hour"] = prof["hour"]
	st.session_state["profile_minute"] = prof["minute"]
	st.session_state["profile_city"] = prof["city"]

	# Update widget-facing keys (year/month_name/day are your input widgets)
	st.session_state["year"] = prof["year"]
	st.session_state["month_name"] = MONTH_NAMES[prof["month"] - 1]
	st.session_state["day"] = prof["day"]

	# Convert 24h to 12h UI widgets
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

	# Helpers some parts of your app expect
	st.session_state["hour_val"] = prof["hour"]
	st.session_state["minute_val"] = prof["minute"]
	st.session_state["city_input"] = prof["city"]
	st.session_state["last_location"] = prof["city"]
	st.session_state["last_timezone"] = prof.get("tz_name")

	# Restore circuit names if present
	if prof.get("circuit_names"):
		for key, val in prof["circuit_names"].items():
			st.session_state.setdefault(key, val)
		st.session_state["saved_circuit_names"] = prof["circuit_names"].copy()
	else:
		st.session_state["saved_circuit_names"] = {}

	st.session_state.pop("_loaded_profile", None)

# --- safe no-op debug hook (prevents NameError if debug calls remain) ---
def _debug_cusps(*args, **kwargs):
	# intentionally does nothing
	return

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
			house_system=house_system,        # <<< use the param, not _selected_house_system()
		)

		# keep numeric conversion benign (don’t drop rows)
		df["abs_deg"] = pd.to_numeric(df["Longitude"], errors="coerce")

		# store exactly what we'll render with
		st.session_state.chart_ready = True
		st.session_state.df = df
		_debug_cusps(st.session_state.df, "in session_state")  # <<< probe 3

		# build the rest as you had
		df_filtered = df[df["Object"].isin(MAJOR_OBJECTS)]
		pos = dict(zip(df_filtered["Object"], df_filtered["abs_deg"]))
		major_edges_all, patterns = get_major_edges_and_patterns(pos)
		shapes = get_shapes(pos, patterns, major_edges_all)
		filaments, singleton_map = detect_minor_links_with_singletons(pos, patterns)
		combos = generate_combo_groups(filaments)

		st.session_state.pos = pos
		st.session_state.patterns = patterns
		st.session_state.major_edges_all = major_edges_all
		st.session_state.shapes = shapes
		st.session_state.filaments = filaments
		st.session_state.singleton_map = singleton_map
		st.session_state.combos = combos

		# cache location for recomputes on radio toggle
		st.session_state["calc_lat"] = lat
		st.session_state["calc_lon"] = lon
		st.session_state["calc_tz"]  = tz_name

	except Exception as e:
		st.error(f"Chart calculation failed: {e}")
		st.session_state.chart_ready = False

# -------------------------
# Outer layout: 3 columns
# -------------------------
col_left, col_mid, col_right = st.columns([2, 2, 2])
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
						# Store location data in session state
						st.session_state["current_lat"] = lat
						st.session_state["current_lon"] = lon
						st.session_state["current_tz_name"] = tz_name
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
				now = dt.datetime.now(tz)

				# ✅ Update only profile_* keys
				st.session_state["profile_year"] = now.year
				st.session_state["profile_month_name"] = MONTH_NAMES[now.month - 1]
				st.session_state["profile_day"] = now.day
				st.session_state["profile_hour"] = now.hour
				st.session_state["profile_minute"] = now.minute
				st.session_state["profile_city"] = city_name
						# Store location data
				st.session_state["current_lat"] = lat
				st.session_state["current_lon"] = lon
				st.session_state["current_tz_name"] = tz_name
				run_chart(lat, lon, tz_name, "Equal")

				# Store location data in session state
				st.session_state["current_lat"] = lat
				st.session_state["current_lon"] = lon
				st.session_state["current_tz_name"] = tz_name
				run_chart(lat, lon, tz_name, "Equal")

				try:
					run_chart(lat, lon, tz_name, _selected_house_system())
					st.session_state["last_house_system"] = _selected_house_system()
					st.rerun()

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
		st.session_state["profile_year"] = st.session_state["year"]
		st.session_state["profile_month_name"] = st.session_state["month_name"]
		st.session_state["profile_day"] = st.session_state["day"]
		st.session_state["profile_hour"] = hour_val
		st.session_state["profile_minute"] = minute_val
		st.session_state["profile_city"] = city_name

		if lat is None or lon is None or tz_name is None:
			st.error("Please enter a valid city and make sure lookup succeeds.")
		else:
			run_chart(lat, lon, tz_name, _selected_house_system())
			# Store location data in session state
			st.session_state["current_lat"] = lat
			st.session_state["current_lon"] = lon
			st.session_state["current_tz_name"] = tz_name
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
		st.session_state["active_profile_tab"] = "Add Profile"

# -------------------------
# Right column: Profile Manager
# -------------------------
with col_right:
	saved_profiles = load_user_profiles_db(current_user_id)

	if "current_profile" not in st.session_state:
		st.session_state["current_profile"] = None
	if "active_profile_tab" not in st.session_state:
		st.session_state["active_profile_tab"] = "Load Profile"

	# Admin gating
	admin_flag = is_admin(current_user_id)

	tab_labels = ["Add Profile", "Load Profile", "Delete Profile"]

	# Pick default index safely
	default_tab = st.session_state["active_profile_tab"]
	if default_tab not in tab_labels:
		default_tab = tab_labels[0]

	active_tab = st.radio(
		"👤 Chart Profile Manager",
		tab_labels,
		index=tab_labels.index(default_tab),
		horizontal=True,
		key="profile_tab_selector"
	)
	st.session_state["active_profile_tab"] = active_tab

	# --- Add ---
	if active_tab == "Add Profile":
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

				# Guard: require a valid geocode before saving
				if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and tz_name):
					st.error("Please enter a valid city (lat/lon/timezone lookup must succeed) before saving the profile.")
					st.stop()

				# Optional: sanity-check timezone string
				import pytz
				if tz_name not in pytz.all_timezones:
					st.error(f"Unrecognized timezone '{tz_name}'. Please refine the city and try again.")
					st.stop()

				profile_data = {
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

			try:
				save_user_profile_db(current_user_id, profile_name, profile_data)
			except Exception as e:
				# If you want finer control, catch postgrest.exceptions.APIError specifically.
				st.error(f"Could not save profile: {e}")
				st.stop()
			else:
				st.success(f"Profile '{profile_name}' saved!")
				# refresh cache
				saved_profiles = load_user_profiles_db(current_user_id)

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

							# Guard run_chart()
							if any(v is None for v in (data.get("lat"), data.get("lon"), data.get("tz_name"))):
								st.error(f"Profile '{name}' is missing location/timezone info. Re-save it after a successful city lookup.")
							else:
								run_chart(data["lat"], data["lon"], data["tz_name"], _selected_house_system())
								st.success(f"Profile '{name}' loaded and chart calculated!")
								st.rerun()

			# === ADD HERE: quick-save circuit names (names only) ===
			if st.session_state.get("current_profile") and "patterns" in st.session_state:
				if st.button("💾 Save Circuit Names to Current Profile", key="save_names_only"):
					# Build latest names from UI/session (fallback to defaults)
					circuit_names = {
						f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
						for i in range(len(st.session_state.patterns))
					}

					# Refresh, update only circuit_names, and save
					profiles = load_user_profiles_db(current_user_id)
					prof_name = st.session_state["current_profile"]
					profile_data = profiles.get(prof_name, {}).copy()

					if not profile_data:
						st.error("No profile data found. Load a profile first.")
					else:
						profile_data["circuit_names"] = circuit_names
						save_user_profile_db(current_user_id, prof_name, profile_data)
						st.session_state["saved_circuit_names"] = circuit_names.copy()
						st.success("Circuit names updated.")

		else:
			st.info("No saved profiles yet.")

	# --- Delete (private, per-user) ---
	elif active_tab == "Delete Profile":
		saved_profiles = load_user_profiles_db(current_user_id)
		if saved_profiles:
			delete_choice = st.selectbox(
				"Select a profile to delete",
				options=sorted(saved_profiles.keys()),
				key="profile_delete"
			)

			# Step 1: ask for confirmation
			if st.button("🗑️ Delete Selected Profile", key="priv_delete_ask"):
				st.session_state["priv_delete_target"] = delete_choice
				st.rerun()

			# Step 2: confirmation panel
			target = st.session_state.get("priv_delete_target")
			if target:
				st.warning(f"Are you sure you want to delete this chart: **{target}**?")
				d1, d2 = st.columns([1, 1], gap="small")
				with d1:
					if st.button("Delete", key="priv_delete_yes", use_container_width=True):
						delete_user_profile_db(current_user_id, target)
						st.session_state.pop("priv_delete_target", None)
						st.success(f"Deleted profile '{target}'.")
						st.rerun()
				with d2:
					if st.button("No!", key="priv_delete_no", use_container_width=True):
						st.session_state.pop("priv_delete_target", None)
						st.info("Delete canceled.")
						st.rerun()
		else:
			st.info("No saved profiles yet.")

	# ===============================
	# 🧪 Donate Your Chart to Science
	# ===============================
	with st.expander("🧪 Donate Your Chart to Science 🧬"):
		st.caption(
			"Optional participation: Donate a chart profile to the research dataset. "
			"Joylin may study donated charts for app development and pattern research."
		)

		# Info-only button (opens the confirm panel without saving anything)
		if st.button("Whaaaat?", key="comm_info_btn"):
			st.session_state["comm_confirm_open"] = True
			st.session_state["comm_confirm_mode"] = "info"
			st.session_state.pop("comm_confirm_payload", None)
			st.session_state.pop("comm_confirm_name", None)

		# --- Donate current inputs (with final confirmation) ---
		comm_name = st.text_input("Name or Event", key="comm_profile_name")
		pub_c1, pub_c2 = st.columns([1, 1], gap="small")

		with pub_c1:
			if st.button("Donate current chart", key="comm_publish_btn"):
				# Preflight validation
				valid = True
				if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and tz_name):
					st.error("Enter a valid city (lat/lon/timezone lookup must succeed) before donating.")
					valid = False
				else:
					import pytz
					if tz_name not in pytz.all_timezones:
						st.error(f"Unrecognized timezone '{tz_name}'. Refine the city and try again.")
						valid = False
				if not comm_name.strip():
					st.error("Please provide a label for the donated chart.")
					valid = False

				if valid:
					circuit_names = {
						f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
						for i in range(len(st.session_state.get("patterns", [])))
					}
					payload = {
						"year":   int(st.session_state.get("profile_year", 1990)),
						"month":  int(MONTH_NAMES.index(st.session_state.get("profile_month_name", "July")) + 1),
						"day":    int(st.session_state.get("profile_day", 1)),
						"hour":   int(st.session_state.get("profile_hour", 0)),
						"minute": int(st.session_state.get("profile_minute", 0)),
						"city":   st.session_state.get("profile_city", ""),
						"lat":    lat,
						"lon":    lon,
						"tz_name": tz_name,
						"circuit_names": circuit_names,
					}
					# Stash for confirm step
					st.session_state["comm_confirm_open"] = True
					st.session_state["comm_confirm_mode"] = "publish"  # <-- important
					st.session_state["comm_confirm_name"] = comm_name.strip()
					st.session_state["comm_confirm_payload"] = payload

		with pub_c2:
			st.info("100% optional!")

		# --- Final confirmation UI (works for 'publish' and 'info' modes) ---
		if st.session_state.get("comm_confirm_open"):
			mode = st.session_state.get("comm_confirm_mode", "info")

			confirm_text_publish = (
				"✨Do you want to donate your chart to Science?💫"
			)
			confirm_text_info = (
				"This is entirely voluntary. If you choose to donate your chart, it will only be available to the app admin (Joylin) for research and development. Joylin will NOT share your chart with others.\n\n"
				"Potential uses:\n\n"
				"• Testing this app's features throughout development to make sure that they work on many charts\n\n"
				"• Studying patterns in astrology for further development of the 'thinking brain' of the app\n\n"
				"• Long-term, as this app is further developed, it will become the foundation for studies with a data scientist to 1) prove that astrology is a legitimate science, 2) hone that science with precision, and 3) use it to decode neurodivergence and unique genetic variants.\n\n"
				"All of this research and development is leading toward those goals, and your chart can be one of the first to inform the early stages of the system.\n\n"
				"Additionally, if you would like to volunteer further information to aid pattern recognition, please reach out."
			)

			st.warning(confirm_text_publish if mode == "publish" else confirm_text_info)

			c_yes, c_no = st.columns([1, 1], gap="small")
			with c_yes:
				if st.button("Donate", key="comm_confirm_yes", use_container_width=True):
					payload = st.session_state.get("comm_confirm_payload")
					name_to_publish = st.session_state.get("comm_confirm_name", "")
					if payload:
						pid = community_save(name_to_publish, payload, submitted_by=current_user_id)
						st.success(f"Thank you! Donated as “{name_to_publish}”.")
					else:
						st.info("This was an info-only view. Click “Donate current chart” first.")
					for k in ("comm_confirm_open", "comm_confirm_mode", "comm_confirm_name", "comm_confirm_payload"):
						st.session_state.pop(k, None)
					st.rerun()

			with c_no:
				if st.button("Cancel", key="comm_confirm_no", use_container_width=True):
					for k in ("comm_confirm_open", "comm_confirm_mode", "comm_confirm_name", "comm_confirm_payload"):
						st.session_state.pop(k, None)
					st.info("No problem—nothing was donated.")
					st.rerun()

		# --- Admin-only browser for donated charts ---
		if is_admin(current_user_id):
			st.markdown("**Browse Donated Charts (admin-only)**")
			rows = community_list(limit=300)

			if not rows:
				st.caption("No donated charts yet.")
			else:
				for r in rows:
					by = r["submitted_by"]
					can_delete = True  # admin can always delete
					confirm_id = st.session_state.get("comm_delete_confirm_id")

					with st.container(border=True):
						st.markdown(f"**{r['profile_name']}** · submitted by **{by}**")

						# First row of buttons
						b1, b2 = st.columns([1, 1], gap="small")
						with b1:
							load_clicked = st.button("Load", key=f"comm_load_{r['id']}", use_container_width=True)

						ask = cancel = really = False
						with b2:
							if confirm_id == r["id"]:
								st.warning("Delete this donated chart?")
							else:
								ask = st.button("Delete", key=f"comm_delete_{r['id']}", use_container_width=True)

						# Confirm row
						if confirm_id == r["id"]:
							cdel1, cdel2 = st.columns([1, 1], gap="small")
							with cdel1:
								really = st.button("Delete", key=f"comm_delete_yes_{r['id']}", use_container_width=True)
							with cdel2:
								cancel = st.button("No!", key=f"comm_delete_no_{r['id']}", use_container_width=True)

					# --- handle clicks ---
					if load_clicked:
						data = r["payload"]
						st.session_state["_loaded_profile"] = data
						st.session_state["current_profile"] = f"community:{r['id']}"
						st.session_state["profile_loaded"] = True
						st.session_state["profile_year"] = data["year"]
						st.session_state["profile_month_name"] = MONTH_NAMES[data["month"] - 1]
						st.session_state["profile_day"] = data["day"]
						st.session_state["profile_hour"] = data["hour"]
						st.session_state["profile_minute"] = data["minute"]
						st.session_state["profile_city"] = data["city"]
						st.session_state["hour_val"] = data["hour"]
						st.session_state["minute_val"] = data["minute"]
						st.session_state["city_input"] = data["city"]
						st.session_state["last_location"] = data["city"]
						st.session_state["last_timezone"] = data.get("tz_name")

						if "circuit_names" in data:
							for key, val in data["circuit_names"].items():
								st.session_state[key] = val
							st.session_state["saved_circuit_names"] = data["circuit_names"].copy()
						else:
							st.session_state["saved_circuit_names"] = {}

						if any(v is None for v in (data.get("lat"), data.get("lon"), data.get("tz_name"))):
							st.error("This donated profile is missing location/timezone info.")
						else:
							run_chart(data["lat"], data["lon"], data["tz_name"], _selected_house_system())
							st.success(f"Loaded donated profile: {r['profile_name']}")
							st.rerun()

					if ask:
						st.session_state["comm_delete_confirm_id"] = r["id"]
						st.rerun()

					if cancel:
						st.session_state.pop("comm_delete_confirm_id", None)
						st.info("Delete canceled.")
						st.rerun()

					if really:
						rec = community_get(r["id"])
						if rec:  # admin-only here
							community_delete(r["id"])
							st.session_state.pop("comm_delete_confirm_id", None)
							st.success(f"Deleted donated profile: {r['profile_name']}")
							st.rerun()
						else:
							st.error("Record not found.")
		# Non-admins see nothing for browsing; they can only donate.

# --- Current Chart Header ---
def _current_chart_title():
	# Prefer explicit title set by loaders; fall back to profile name; else a default
	title = (
		st.session_state.get("current_profile_title")
		or st.session_state.get("current_profile")
		or "Untitled Chart"
	)
	# If it's a community marker like "community:123", don't show that literal
	if isinstance(title, str) and title.startswith("community:"):
		title = "Community Chart"

	month = st.session_state.get("profile_month_name", "")
	day   = st.session_state.get("profile_day", "")
	year  = st.session_state.get("profile_year", "")
	hour  = st.session_state.get("profile_hour", None)
	minute = st.session_state.get("profile_minute", None)
	city  = st.session_state.get("profile_city", "")

	# Format time to 12-hour
	time_str = ""
	if hour is not None and minute is not None:
		h = int(hour); m = int(minute)
		ampm = "AM" if h < 12 else "PM"
		h12 = 12 if h % 12 == 0 else h % 12
		time_str = f"{h12}:{m:02d} {ampm}"

	date_line = f"{month} {day}, {year}" if month and day and year else ""
	if date_line and time_str:
		date_line = f"{date_line}, {time_str}"
	elif time_str:
		date_line = time_str

	st.markdown(
		f"""
		<div style="margin:0.25rem 0 0.75rem 0">
		<div style="font-weight:700; font-size:1.2rem; line-height:1.1">{title}</div>
		<div>{date_line}</div>
		<div>{city}</div>
		</div>
		""",
		unsafe_allow_html=True,
	)

_GLYPH_TO_SIGN = {
	"♈":"Aries","♉":"Taurus","♊":"Gemini","♋":"Cancer",
	"♌":"Leo","♍":"Virgo","♎":"Libra","♏":"Scorpio",
	"♐":"Sagittarius","♑":"Capricorn","♒":"Aquarius","♓":"Pisces",
}
_SIGN_PAT = re.compile(r"(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)", re.IGNORECASE)

def _sign_for_lookup(row: dict) -> str:
	# Try any field you actually have; adjust the list if needed.
	candidates = [
		row.get("Sign"),
		row.get("Zodiac Sign"),
		row.get("Sign Name"),
		row.get("Longitude"),        # e.g. "Capricorn 20°58′"
		row.get("Sign Glyph"),       # e.g. "♑"
	]
	for s in candidates:
		if not s:
			continue
		s = str(s).strip()
		# 1) Glyph
		for g, name in _GLYPH_TO_SIGN.items():
			if g in s:
				return name
		# 2) Word match
		m = _SIGN_PAT.search(s)
		if m:
			return m.group(1).title()
	return ""  # nothing matched; dignity will be omitted

def _resolve_dignity(obj: str, sign_name: str):
	"""
	Your DIGNITIES is keyed by sign name:
		DIGNITIES["Capricorn"]["domicile"] == ["Saturn"]
	Return one of: 'domicile', 'exaltation', 'detriment', 'fall' or None.
	"""
	m = DIGNITIES.get(sign_name)
	if not isinstance(m, dict):
		return None

	# If your row/object includes “(Mean)”, strip those suffixes for matching
	import re
	base_obj = re.sub(r"\s*\(.*?\)\s*$", "", obj).strip()

	for label in ("domicile", "exaltation", "detriment", "fall"):
		lst = m.get(label) or []
		if isinstance(lst, (list, tuple, set)) and base_obj in lst:
			return label
	return None

def _one_full_parent_selected(aspect_blocks):
	"""
	Returns True only when a single *parent* circuit is selected.
	Sub-shapes within that same parent are fine.
	"""
	try:
		import streamlit as st
		# Prefer explicit state if your UI exposes it
		for key in ("active_circuit_ids", "selected_circuits", "active_parents"):
			ids = st.session_state.get(key)
			if isinstance(ids, (list, tuple, set)):
				ids = [i for i in ids if i]
				if len(ids) == 1:
					return True  # parent-only selection (assumes these are parent ids)

		# Fallback: infer from aspect_blocks structure
		parents = set()
		parent_markers = 0
		for b in (aspect_blocks or []):
			# Try common keys for parent/circuit id
			pid = b.get("parent_id") or b.get("circuit_id") or b.get("parent")
			# Try to infer from a path/label like "Parent > Subshape"
			if not pid:
				path = (b.get("path") or b.get("label") or "").strip()
				if ">" in path:
					pid = path.split(">")[0].strip()
			if pid:
				parents.add(pid)

			# Heuristics to detect a parent-level block
			kind = str(b.get("kind") or b.get("type") or "").lower()
			if b.get("is_parent") is True or kind in {"parent", "circuit"} or b.get("level") == 0:
				parent_markers += 1

		return len(parents) == 1 and parent_markers >= 1
	except Exception:
		return False

def ask_gemini(prompt_text: str,
			   model: str = "gemini-1.5-flash",
			   temperature: float = 0.2) -> str:
	generative_model = genai.GenerativeModel(
		model_name=model,
		system_instruction=(
			"You are an astrology interpreter. Use ONLY the data provided by the app. "
			"Do NOT import traditional astrology or outside meanings. If data is missing, say so."
		),
		generation_config={"temperature": temperature},
	)
	response = generative_model.generate_content(prompt_text)

	# Safety handling
	if not response.candidates:
		return "⚠️ Gemini blocked or returned no content."
	return (response.text or "").strip()


_CANON_SHAPES = {s.lower(): s for s in SHAPE_INSTRUCTIONS.keys()}

def _canonical_shape_name(shape_dict):
		"""Map whatever your shape carries to one of SHAPE_INSTRUCTIONS keys."""
		raw = (
				shape_dict.get("type") or shape_dict.get("kind") or
				shape_dict.get("shape") or shape_dict.get("label") or
				shape_dict.get("name") or ""
		)
		txt = str(raw).strip().lower()
		if not txt:
				return ""

		# direct match
		if txt in _CANON_SHAPES:
				return _CANON_SHAPES[txt]

		# fuzzy contains (e.g., "grand_trine", "Grand Trine (parent)")
		for k in _CANON_SHAPES:
				if k.replace(" ", "_") in txt or k in txt:
						return _CANON_SHAPES[k]

		return ""

# ------------------------
# Guided Question Wizard (shared renderer)
# ------------------------
def render_guided_wizard():
		with st.expander("🧙‍♂️ Guided Topics Wizard", expanded=False):
				domains = WIZARD_TARGETS.get("domains", [])
				domain_names = [d.get("name", "") for d in domains]
				domain_lookup = {d.get("name", ""): d for d in domains}
				cat = st.selectbox(
						"What are you here to explore?",
						options=domain_names,
						index=0 if domain_names else None,
						key="wizard_cat",
				)

				domain = domain_lookup.get(cat, {})
				if domain.get("description"):
						st.caption(domain["description"])

				subtopics_list = domain.get("subtopics", [])
				subtopic_names = [s.get("label", "") for s in subtopics_list]
				subtopic_lookup = {s.get("label", ""): s for s in subtopics_list}
				sub = st.selectbox(
						"Narrow it a bit…",
						options=subtopic_names,
						index=0 if subtopic_names else None,
						key="wizard_sub",
				)

				subtopic = subtopic_lookup.get(sub, {})
				refinements = subtopic.get("refinements")
				targets = []
				if refinements:
						ref_names = list(refinements.keys())
						ref = st.selectbox(
								"Any particular angle?",
								options=ref_names,
								index=0 if ref_names else None,
								key="wizard_ref",
						)
						targets = refinements.get(ref, [])
				else:
						targets = subtopic.get("targets", [])

				if targets:
					st.caption("Where to look in your chart:")

				for t in targets:
					meaning = None
					display_name = t

					# Add glyph if available
					glyph = GLYPHS.get(t)
					if glyph:
						display_name = f"{glyph} {t}"

					# Check meaning sources
					if t in OBJECT_MEANINGS_SHORT:
						meaning = OBJECT_MEANINGS_SHORT[t]
					elif t in SIGN_MEANINGS:
						meaning = SIGN_MEANINGS[t]
					elif "House" in t:
						try:
							house_num = int(t.split()[0].replace("st","").replace("nd","").replace("rd","").replace("th",""))
							meaning = HOUSE_MEANINGS.get(house_num)
						except Exception:
							meaning = None

					if meaning:
						st.write(f"{display_name}: {meaning}")
					else:
						st.write(f"{display_name}: [no meaning found]")

# ------------------------
# If chart data exists, render the chart UI
# ------------------------
if not st.session_state.get("chart_ready", True):
	render_guided_wizard()

if st.session_state.get("chart_ready", False):
	df = st.session_state.df
	pos = st.session_state.pos
	patterns = st.session_state.patterns
	major_edges_all = st.session_state.major_edges_all
	shapes = st.session_state.shapes
	filaments = st.session_state.filaments
	singleton_map = st.session_state.singleton_map
	combos = st.session_state.combos

	# --- PRE-SEED circuit toggle keys (must happen before creating checkboxes) ---
	num_patterns = len(patterns)

	# wipe stale toggles from previous charts if indexes no longer exist
	for k in list(st.session_state.keys()):
		if k.startswith("toggle_pattern_"):
			try:
				idx = int(k.rsplit("_", 1)[1])
			except Exception:
				continue
			if idx >= num_patterns:
				del st.session_state[k]

	for i in range(num_patterns):
		key = f"toggle_pattern_{i}"
		if key not in st.session_state:
			st.session_state[key] = False  # set True if you want them on by default

	# --- UI Layout ---
	left_col, right_col = st.columns([2, 1])
	with left_col:
		st.subheader("Instructions")
		with st.expander("Click to Expand Instructions"):
			st.caption(
				"This app is a study tool to allow you to break down your complex astrology chart into "
				"its connected circuits, to break the complex circuits down further into the shapes they " 
				"are made of, and to interpret all of these dynamic parts as the functional energetic " 
				"wiring schematic that they are. " 
			)
			st.caption(
				"View planet profiles on the left sidebar (» on mobile). "
			)
			st.caption(
				"Turn on only one circuit = aspects color-coded "
				"(Trines = Blue; Sextiles = Purple; Squares and Oppositions = Red)"
			)
			st.caption(
				"Turn on multiple circuits = each circuit color-coded. "
				"Expand circuits for sub-shapes. "
			)
			st.caption(
				"Use the Guided Topics Wizard to select the topic you want to look at, then find the "
				"planet(s) or placement(s) that you would like to focus on among your circuits and sub-shapes."
			)
			st.caption(
				"Or, to begin studying your chart from its foundation, begin with the Compass Rose."
			)
			st.caption(
				"Select just one sub-shape or the Compass Rose to start. For best results, do not render very many "
				"layers on the chart when you're generating an interpretation, in order to keep the prompts shorter."
			)
			st.caption(
				"Scroll down. Below the chart, "
				'press "Send to Gemini" to read or listen to the interpretation.'
			)
			st.caption(
				"After studying your Compass Rose, choose one sub-shape from a circuit to study next. "
				"It is recommended to start with the shape or circuit that includes your North and South Node."
			)
			st.caption(
				"After studying the first shape, choose another one to study, "
				"such as the one with your Sun or Moon."
			)
			st.caption(
				"Once you're familiar with multiple shapes, you can turn them on at the same time "
				"to learn about how they connect and interact with each other."
			)
			st.caption(
				"Then, once you are familiar with a whole circuit, you can give it a name, and save that name "
				"to your birth chart profile. "
			)

		st.subheader("Circuits")

		# ---------- PRE-INIT (so keys exist before any widgets render) ----------
		# patterns & sub-shapes
		for i in range(len(patterns)):
			st.session_state.setdefault(f"toggle_pattern_{i}", False)
			for sh in [sh for sh in shapes if sh["parent"] == i]:
				st.session_state.setdefault(f"shape_{i}_{sh['id']}", False)

		# singleton planets (guard if not present)
		if singleton_map:
			for planet in singleton_map.keys():
				st.session_state.setdefault(f"singleton_{planet}", False)

		# ---------- BULK ACTION HANDLERS (must run BEFORE widgets) ----------
		b1, b2 = st.columns([1, 1])
		with b1:
			if st.button("Show All", key="btn_show_all_main"):
				# flip ON only the circuits (not sub-shapes, not singletons)
				for i in range(len(patterns)):
					st.session_state[f"toggle_pattern_{i}"] = True
				st.rerun()

		with b2:
			if st.button("Hide All", key="btn_hide_all_main"):
				# flip everything OFF
				for i in range(len(patterns)):
					st.session_state[f"toggle_pattern_{i}"] = False
					for sh in [sh for sh in shapes if sh["parent"] == i]:
						st.session_state[f"shape_{i}_{sh['id']}"] = False
				if singleton_map:
					for planet in singleton_map.keys():
						st.session_state[f"singleton_{planet}"] = False
				st.rerun()

		# --- Compass Rose (independent overlay, ON by default) ---
		if "toggle_compass_rose" not in st.session_state:
			st.session_state["toggle_compass_rose"] = True
		st.checkbox("Compass Rose", key="toggle_compass_rose")

		# Pattern checkboxes + expanders
		toggles, pattern_labels = [], []
		half = (len(patterns) + 1) // 2
		left_patterns, right_patterns = st.columns(2)

		for i, component in enumerate(patterns):
			target_col = left_patterns if i < half else right_patterns
			checkbox_key = f"toggle_pattern_{i}"

			# circuit name session key
			circuit_name_key = f"circuit_name_{i}"
			default_label = f"Circuit {i+1}"
			if circuit_name_key not in st.session_state:
				st.session_state[circuit_name_key] = default_label

			# what shows where
			circuit_title  = st.session_state[circuit_name_key]   # shown on checkbox row
			members_label  = ", ".join(component)                  # shown in expander header

			# color chip for layered mode
			group_color = GROUP_COLORS[i % len(GROUP_COLORS)]

			with target_col:
				# checkbox row: [chip] Circuit N
				cbox = st.checkbox(f"{circuit_title}", key=checkbox_key)
				toggles.append(cbox)
				pattern_labels.append(circuit_title)

				# expander shows only the member list on its header
				with st.expander(members_label, expanded=False):
					# rename field
					st.text_input("Circuit name", key=circuit_name_key)

					# --- Auto-save when circuit name changes (your same logic) ---
					if st.session_state.get("current_profile"):
						saved = st.session_state.get("saved_circuit_names", {})
						current_name = st.session_state[circuit_name_key]
						last_saved = saved.get(circuit_name_key, default_label)

						if current_name != last_saved:
							current = {
								f"circuit_name_{j}": st.session_state.get(f"circuit_name_{j}", f"Circuit {j+1}")
								for j in range(len(patterns))
							}
							profile_name = st.session_state["current_profile"]
							payload = saved_profiles.get(profile_name, {}).copy()
							payload["circuit_names"] = current
							save_user_profile_db(current_user_id, profile_name, payload)
							saved_profiles = load_user_profiles_db(current_user_id)
							st.session_state["saved_circuit_names"] = current.copy()

					# --- Sub-shapes (uses callback to safely toggle parent circuit) ---
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
								value=st.session_state.get(unique_key, False),
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
				payload = saved_profiles.get(profile_name, {}).copy()
				payload["circuit_names"] = current
				save_user_profile_db(current_user_id, profile_name, payload)
				saved_profiles = load_user_profiles_db(current_user_id)
				st.session_state["saved_circuit_names"] = current.copy()

	with right_col:
		st.subheader("Topics")
		render_guided_wizard()
		st.divider()
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


		c1, c2 = st.columns([2, 2])

		with c1:
			# ✅ real, functional control
			house_choice = st.selectbox(
				"House System",
				["Equal", "Whole Sign", "Placidus"],
				index=0,
				key="house_system_main",
			)
			house_system = house_choice.lower().replace(" sign", "")

			# Recompute chart if the house system changed
			prev = st.session_state.get("last_house_system")
			if st.session_state.get("chart_ready") and house_system != prev:
				# Get stored location data from session state
				stored_lat = st.session_state.get("current_lat")
				stored_lon = st.session_state.get("current_lon")
				stored_tz = st.session_state.get("current_tz_name")

				if stored_lat and stored_lon and stored_tz:
					run_chart(stored_lat, stored_lon, stored_tz, house_system)
					st.session_state["last_house_system"] = house_system
				else:
					st.error("Location data not available. Please recalculate the chart first.")

		with c2:
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

	fig, visible_objects, active_shapes, cusps, interp_text = render_chart_with_shapes(
		pos, patterns, pattern_labels=[],
		toggles=[st.session_state.get(f"toggle_pattern_{i}", False) for i in range(len(patterns))],
		filaments=filaments, combo_toggles=combos,
		label_style=label_style, singleton_map=singleton_map, df=df,
		house_system=house_system,
		dark_mode=dark_mode,
		shapes=shapes, shape_toggles_by_parent=shape_toggles_by_parent,
		singleton_toggles=singleton_toggles, major_edges_all=major_edges_all
	)

	import io

	buf = io.BytesIO()
	fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
	st.image(buf, use_container_width=True)


	def _sign_from_degree(deg):
		# 0=Aries ... 11=Pisces
		idx = int((deg % 360) // 30)
		return SIGN_NAMES[idx]

	def _invert_rulerships(planetary_rulers):
		"""Return {Ruler: set(SignsItRules)}"""
		rev = {}
		for sign, rulers in planetary_rulers.items():
			for r in rulers:
				rev.setdefault(r, set()).add(sign)
		return rev

	def _join_names(seq):
		return ", ".join(seq)

	def _compute_cusp_signs(cusps_list):
		"""Return {house_num: sign_name} for 1..12 using active cusps."""
		return {i+1: _sign_from_degree(cusps_list[i]) for i in range(min(12, len(cusps_list)))}


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
		lookup_names = [obj]
		for alias, display in ALIASES_MEANINGS.items():
			if obj in (alias, display):
				lookup_names.extend({alias, display})
		matched_rows = df[df["Object"].isin(lookup_names)]
		if matched_rows.empty:
			continue

	# --- Compass-only fallback: seed ordered_objects so profiles can build ---
	if not ordered_objects and st.session_state.get("toggle_compass_rose", False):
		# Prefer whatever naming exists in the DF for each compass endpoint
		df_names = set(df["Object"].astype("string").str.strip())

		def pick(*names):
			for n in names:
				if n in df_names:
					return n
			return None

		compass_seed = [
			pick("Ascendant", "ASC", "AC"),
			pick("Descendant", "DSC", "DC"),
			pick("Midheaven", "MC"),
			pick("Imum Coeli", "IC"),
			pick("North Node", "True Node"),
			pick("South Node"),  # South Node usually appears as itself
		]
		ordered_objects = [n for n in compass_seed if n]

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

	# Ensure Sign is set for each visible object
	for obj, row in enhanced_objects_data.items():
		deg_val = None
		for key in ("abs_deg", "Longitude"):
			if key in row and row[key] not in (None, "", "nan"):
				try:
					deg_val = float(row[key])
					break
				except Exception:
					pass
		if deg_val is not None:
			row["Sign"] = _sign_from_degree(deg_val)

	# Ensure Sign Ruler is present in each row (pure lookup; no geometry)
	for obj, row in enhanced_objects_data.items():
		sign = (row.get("Sign") or "").strip()
		rulers = PLANETARY_RULERS.get(sign, [])
		if not isinstance(rulers, (list, tuple)):
			rulers = [rulers] if rulers else []
		row["Sign Ruler"] = rulers

	# Precompute: cusp signs for each house in the CURRENT system,
	# and a reverse map of signs ruled by each ruler
	cusp_signs = _compute_cusp_signs(cusps_list)
	SIGNS_BY_RULER = _invert_rulerships(PLANETARY_RULERS)

	# Precompute which houses each ruler governs (via cusp sign)
	HOUSES_BY_RULER = {
		ruler: {h for h, s in cusp_signs.items() if s in signs}
		for ruler, signs in SIGNS_BY_RULER.items()
	}

	for obj, row in enhanced_objects_data.items():
		try:
			h = int(row.get("House", 0) or 0)
		except Exception:
			h = 0
		if h and h in cusp_signs:
			sign_on_cusp = cusp_signs[h]
			rul = PLANETARY_RULERS.get(sign_on_cusp, [])
			row["House Ruler"] = (
				list(rul) if isinstance(rul, (list, tuple))
				else ([rul] if rul else [])
			)

	for row in enhanced_objects_data.values():
			ensure_profile_detail_strings(row)

	def _build_rulership_html(obj_name, row, enhanced_objects_data, ordered_objects, cusp_signs):
		# --- Rulership BY HOUSE (who rules *this obj* by house it occupies)
		house_num = row.get("House")
		house_rulers = []
		if house_num in cusp_signs:
			house_sign = cusp_signs[house_num]
			house_rulers = PLANETARY_RULERS.get(house_sign, [])

		# --- Rulership BY SIGN (who rules *this obj* by its sign)
		obj_sign = row.get("Sign")
		sign_rulers = PLANETARY_RULERS.get(obj_sign, []) if obj_sign else []

		# --- Which objects does THIS OBJECT rule (two ways)
		signs_this_obj_rules = SIGNS_BY_RULER.get(obj_name, set())
		houses_this_obj_rules = HOUSES_BY_RULER.get(obj_name, set())

		# Keep list order consistent with your sidebar order
		ruled_by_sign = []
		ruled_by_house = []
		for other in ordered_objects:
			if other == obj_name:
				continue
			o_row = enhanced_objects_data.get(other, {})
			# By Sign: object sits in a sign ruled by obj_name
			if o_row.get("Sign") in signs_this_obj_rules:
				ruled_by_sign.append(other)
			# By House: object's HOUSE cusp sign is ruled by obj_name
			h = o_row.get("House")
			if h in houses_this_obj_rules:
				ruled_by_house.append(other)

		# Format lines
		# Example target: "Mars rules Mercury rules Jupiter, Venus"
		house_chain = ""
		if house_rulers:
			left = _join_names(house_rulers)
			house_chain = f"{left} rules {obj_name}"
			if ruled_by_house:
				house_chain += f" rules {_join_names(ruled_by_house)}"

		sign_chain = ""
		if sign_rulers:
			left = _join_names(sign_rulers)
			sign_chain = f"{left} rules {obj_name}"
			if ruled_by_sign:
				sign_chain += f" rules {_join_names(ruled_by_sign)}"

		# Always emit both headers; if no chain, show just the header with nothing?
		# Per your examples, when non-ruler objects exist we still want the shorter entry.
		# If we have no ruler (shouldn't happen), fall back to empty string.
		house_line = house_chain or f"{obj_name}"  # minimal fallback
		sign_line  = sign_chain  or f"{obj_name}"  # minimal fallback

		# HTML block added at end of profile
		return (
			"<div style='margin-top:6px'>"
			"<strong>Rulership by House:</strong><br>"
			f"{house_line}<br>"
			"<strong>Rulership by Sign:</strong><br>"
			f"{sign_line}"
			"</div>"
		)

	# Display profiles using enhanced data
	for obj in ordered_objects:
		if obj not in enhanced_objects_data:
			continue

		row = enhanced_objects_data[obj]
		profile = format_planet_profile(row)

		# Append the two rulership sections
		rulership_html = _build_rulership_html(obj, row, enhanced_objects_data, ordered_objects, cusp_signs)

		# --- Decorate the profile header with Rx / Station, and insert Dignity line after sign/degree ---
		# Extract a simple text header from the formatted HTML so we can modify just the first line.

		# Grab the first non-empty line of the HTML, strip tags
		header_line = ""
		for ln in profile.splitlines():
			if ln.strip():
				header_line = re.sub(r"<[^>]+>", "", ln).strip()
				break

		# Derive flags for this object
		name_for_header = row.get("Display Name") or obj
		motion_raw = " ".join([
			str(row.get("Retrograde", "")),
			str(row.get("Rx", "")),
			str(row.get("Motion", "")),
			str(row.get("Station", "")),
		]).lower()

		rx_flag      = ("rx" in motion_raw) or ("retro" in motion_raw)
		station_flag = ("station" in motion_raw)
		dignity      = _resolve_dignity(name_for_header, row.get("Sign", ""))  # uses your helper

		# Build desired header suffix: "(Stationing Direct)" OR "Rx"
		suffix_bits = []
		if station_flag:
			suffix_bits.append("Stationing Direct")  # or "Stationing" if you prefer shorter
		if rx_flag:
			suffix_bits.append("Rx")
		header_suffix = ""
		if suffix_bits:
			header_suffix = " (" + ", ".join(suffix_bits) + ")"

		# Replace the first occurrence of the plain name in the profile header line with "Name (flags)"
		# Then re-inject that edited header back into the profile HTML
		if name_for_header in header_line:
			new_header_line = header_line.replace(name_for_header, name_for_header + header_suffix, 1)
			# Swap only the first heading line in the HTML (very conservative)
			profile = profile.replace(header_line, new_header_line, 1)

		# Insert Dignity as a standalone line after the zodiac line (e.g., "Scorpio 14°58′")
		if dignity:
			# Find the first occurrence of "Sign <deg>" line in the HTML text
			# We'll add "<br/>Domicile" (or whatever dignity text) right after it.
			sign_deg_line = f"{row.get('Sign','').strip()} {row.get('Degree', '').strip()}"
			# Fallback: sometimes the degree string is part of a combined line; be tolerant
			sign_pattern = re.escape(row.get('Sign','').strip()) + r"\s+\d+°\d+′"
			m = re.search(sign_pattern, re.sub(r"<[^>]+>", "", profile))
			if m:
				plain_sign_line = m.group(0)
				# Inject dignity (escaped into HTML)
				profile = profile.replace(plain_sign_line, plain_sign_line + "<br/>" + dignity, 1)
			else:
				# If we can't find the exact sign-degree text, append dignity near the top
				profile = profile.replace("</div>", f"<br/>{dignity}</div>", 1)

		st.sidebar.markdown(profile + rulership_html, unsafe_allow_html=True)
		st.sidebar.markdown("---")

	# --- Send to Gemini controls (show ONLY when a prompt exists) ---
	colA, colB, colC = st.columns([1, 1, 2])
	with colA:
		run_it = st.button("Send to Gemini", type="primary", key="send_to_gemini")
	with colB:
		creative = st.toggle("Creative mode", value=False)
		temperature = 0.60 if creative else 0.20
	with colC:
		model = st.selectbox("Model", ["gemini-1.5-flash", "gemini-1.5-pro"], index=0, key="gpt_model")

	if run_it:
		try:
			# 1) Only include placements that are actually visible on the chart
			targets = list(visible_objects)

			# 2) Build structured context from YOUR lookups & this chart
			context = build_context_for_objects(
				targets=targets, pos=pos, df=df,
				active_shapes=active_shapes, star_catalog=STAR_CATALOG
			)

			# 3) Get the correct instruction for this chart mode
			chart_mode = st.session_state.get("chart_mode", "natal")
			task = choose_task_instruction(chart_mode, targets, active_shapes, context)

			# 4) Call Gemini via the brain wrapper
			out_text = ask_gemini_brain(
				genai_module=genai,
				prompt_text=task,
				context=context,
				model=model,
				temperature=temperature,
			)

			st.markdown(out_text)

		except Exception as e:
			st.error(f"Gemini error: {e}")

		with st.expander("Interpretation"):
			# 🔊 controls FIRST (so users see them right away)
			T.tts_controls(out_text, key="interpretation")
			# then the text
			st.markdown(out_text)

else:
	# No prompt yet (no chart or no shapes selected)
	st.markdown("_(Calculate or Load a birth chart)_")