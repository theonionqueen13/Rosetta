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
from rosetta.calc import calculate_chart
from rosetta.db import supa
from rosetta.auth_reset import request_password_reset, verify_reset_code_and_set_password
from rosetta.authn import get_auth_credentials, get_user_role_cached, ensure_user_row_linked
from rosetta.config import get_openai_client, get_secret
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
	draw_planet_labels, draw_aspect_lines, draw_filament_lines,
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
COLOR_EMOJI                  = _Lget("COLOR_EMOJI")
SHAPE_INSTRUCTIONS           = _Lget("SHAPE_INSTRUCTIONS")
OBJECT_INTERPRETATIONS       = _Lget("OBJECT_INTERPRETATIONS")
CATEGORY_MAP                 = _Lget("CATEGORY_MAP")
CATEGORY_INSTRUCTIONS        = _Lget("CATEGORY_INSTRUCTIONS")
ALIASES_MEANINGS             = _Lget("ALIASES_MEANINGS")
SIGN_MEANINGS                = _Lget("SIGN_MEANINGS")
HOUSE_MEANINGS               = _Lget("HOUSE_MEANINGS")
OBJECT_MEANINGS_SHORT        = _Lget("OBJECT_MEANINGS_SHORT")

import streamlit as st, importlib

@st.cache_resource
def get_lookup():
	return importlib.import_module("rosetta.lookup")

_L = get_lookup()
# same attribute assignments as above...

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

client = get_openai_client()
if client is None:
	import streamlit as st
	st.error("Missing OPENAI_API_KEY. Set it as env var or in Streamlit Secrets.")
	st.stop()

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
	ax.set_rlim(0, 1.25)
	ax.axis("off")

	# carve a little headroom for the figure-level header
	fig.subplots_adjust(top=0.86)  # tweak 0.82–0.90 to taste

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

	if st.session_state.get("toggle_compass_rose"):
		visible_objects.update([
			"Ascendant", "Descendant", "MC", "IC",
			"North Node", "South Node",
		])

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

	# --- Compass Rose overlay (always independent of circuits/shapes) ---
	if st.session_state.get("toggle_compass_rose", True):
		draw_compass_rose(
			ax, pos, asc_deg,
			colors={"nodal": "purple", "acdc": "green", "mcic": "orange"},
			linewidth_base=2.0,
			zorder=100,
			arrow_mutation_scale=22.0,   # bigger arrowhead
			nodal_width_multiplier=2.0,
			sn_dot_markersize=12.0
		)

	return fig, visible_objects, active_shapes, cusps

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

def ask_gpt(prompt_text: str, model: str = "gpt-4o-mini", temperature: float = 0.2) -> str:
	"""Send your already-built Astroneurology prompt as-is. No extra magic."""
	r = client.chat.completions.create(
		model=model,
		temperature=temperature,
		messages=[
			{"role": "system", "content": (
				"You are an Astroneurology interpreter. Use ONLY the data provided by the app. "
				"Do NOT import traditional astrology or outside meanings. If data is missing, say so."
			)},
			{"role": "user", "content": prompt_text},
		],
	)
	return r.choices[0].message.content.strip()


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
				'press "Send to GPT" to see (or listen to) the interpretation.'
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
			chip = COLOR_EMOJI.get(group_color, "⬛")

			with target_col:
				# checkbox row: [chip] Circuit N
				cbox = st.checkbox(f"{chip} {circuit_title}", key=checkbox_key)
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
			house_choice = st.radio(
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

			if st.button("Show All"):
				for i in range(len(patterns)):
					st.session_state[f"toggle_pattern_{i}"] = True
					for sh in [sh for sh in shapes if sh["parent"] == i]:
						st.session_state[f"shape_{i}_{sh['id']}"] = True
				for planet in singleton_map.keys():
					st.session_state[f"singleton_{planet}"] = True
		with c2:
			# Choose how to show planet labels
			label_style = st.radio(
				"Label Style",
				["Text", "Glyph"],
				index=1,
				horizontal=True
			)

			dark_mode = st.checkbox("🌙 Dark Mode", value=False)

			if st.button("Hide All"):
				for i in range(len(patterns)):
					st.session_state[f"toggle_pattern_{i}"] = False
					for sh in [sh for sh in shapes if sh["parent"] == i]:
						st.session_state[f"shape_{i}_{sh['id']}"] = False
				for planet in singleton_map.keys():
					st.session_state[f"singleton_{planet}"] = False

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

	# Precompute: cusp signs for each house in the CURRENT system,
	# and a reverse map of signs ruled by each ruler
	cusp_signs = _compute_cusp_signs(cusps_list)
	SIGNS_BY_RULER = _invert_rulerships(PLANETARY_RULERS)

	# Precompute which houses each ruler governs (via cusp sign)
	HOUSES_BY_RULER = {
		ruler: {h for h, s in cusp_signs.items() if s in signs}
		for ruler, signs in SIGNS_BY_RULER.items()
	}

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
		st.sidebar.markdown(profile + rulership_html, unsafe_allow_html=True)
		st.sidebar.markdown("---")

	# --- Interpretation Prompt ---
	with st.expander("Interpretation Prompt"):
		st.caption("Paste this prompt into an LLM (like ChatGPT). Start with studying one subshape at a time, then add connections as you learn them.")
		st.caption("Curently, all interpretation prompts are for natal charts. Event interpretation prompts coming soon.")

		aspect_blocks = []
		present_aspects = set()  # which aspect TYPES are present
		prompt = ""
		compass_on = st.session_state.get("toggle_compass_rose", False)

		# --- Conjunction clusters first (pairwise inside each cluster) ---
		rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, list(visible_objects))
		for rep, cluster in rep_map.items():
			if len(cluster) >= 2:
				present_aspects.add("Conjunction")

		# Build lookup: obj -> "Cluster Label" (e.g., "Sun, IC, South Node")
		cluster_lookup = {}
		for rep, cluster in rep_map.items():
			if len(cluster) >= 2:
				label = ", ".join(sorted(
					cluster,
					key=lambda x: ordered_objects.index(x) if x in ordered_objects else 999
				))
				for m in cluster:
					cluster_lookup[m] = label

		# Collect non-conjunction edges across all active shapes
		raw_edges = []
		# Build lookup: obj -> "Cluster Label" (e.g., "Sun, IC, South Node")
		cluster_lookup = {}
		for rep, cluster in rep_map.items():
			if len(cluster) >= 2:
				label = ", ".join(sorted(
					cluster,
					key=lambda x: ordered_objects.index(x) if x in ordered_objects else 999
				))
				for m in cluster:
					cluster_lookup[m] = label

		# Collect non-conjunction edges across all active shapes
		raw_edges = []
		for s in active_shapes:
			for (p1, p2), asp in s["edges"]:
				asp_clean = asp.replace("_approx", "")
				if asp_clean == "Conjunction":
					continue  # conjunctions already handled
				raw_edges.append((p1, asp_clean, p2))
				present_aspects.add(asp_clean)

		from collections import OrderedDict, defaultdict

		def label_of(obj):
			return cluster_lookup.get(obj, obj)

		# Group by (left_label, aspect) => list of right labels (dedup, preserve order)
		appearance = OrderedDict()
		group_right = defaultdict(list)

		for p1, asp, p2 in raw_edges:
			L = label_of(p1)
			R = label_of(p2)
			if L == R:
				continue  # skip self-aspects created by cluster substitution
			key = (L, asp)
			if key not in appearance:
				appearance[key] = None
			if R not in group_right[key]:
				group_right[key].append(R)

		# Build bulleted "Aspects" (slash-joined conjunction clusters in parentheses)
		import re
		_aspect_rx = re.compile(r"^(.*?)\s+(Opposition|Trine|Sextile|Square|Quincunx)\s+(.*)$", re.IGNORECASE)

		def _fmt_side(label: str) -> str:
			label = label.strip()
			if ", " in label:
				# turn "Sun, IC, South Node" -> "(Sun/IC/South Node)"
				return "(" + label.replace(", ", "/") + ")"
			return label

		_bullets = []
		for (L, asp) in appearance.keys():
			for R in group_right[(L, asp)]:
				left = _fmt_side(L)
				right = _fmt_side(R)
				_bullets.append(f"• {left} {asp} {right}")

		# If Compass Rose is on, append its three axes to the Aspects bullets.
		# This does NOT touch circuits/subshape detection — prompt-only overlay.
		if compass_on:
			def _label(obj):
				return _fmt_side(label_of(obj))

			# Ensure Opposition definition is included
			present_aspects.add("Opposition")

			# Nodal axis
			if "South Node" in pos and "North Node" in pos:
				_bullets.append(f"• {_label('South Node')} Opposition {_label('North Node')}")

			# AC–DC axis
			if "Ascendant" in pos and "Descendant" in pos:
				_bullets.append(f"• {_label('Ascendant')} Opposition {_label('Descendant')}")

			# MC–IC axis
			if "MC" in pos and "IC" in pos:
				_bullets.append(f"• {_label('MC')} Opposition {_label('IC')}")

		aspects_bulleted_block = ("Aspects\n\n" + "\n".join(_bullets)).strip() if _bullets else ""
		if _bullets:
			# Keep this truthy so downstream gates that check `if aspect_blocks:` still run.
			# (Content here is not used in the final prompt after step #2.)
			aspect_blocks.append("_")

		def strip_html_tags(text):
			# Preserve line breaks for header parsing
			text = re.sub(r'</div>|<br\s*/?>', '\n', text)
			text = re.sub(r'<div[^>]*>', '', text)
			text = re.sub(r'<[^>]+>', '', text)
			# Collapse spaces/tabs but keep newlines
			text = re.sub(r'[ \t]+', ' ', text)
			# Normalize multiple blank lines
			text = re.sub(r'\n\s*\n+', '\n', text)
			return text.strip()

		# --- Prompt gating flags ---
		has_shapes = bool(active_shapes)
		compass_on = st.session_state.get("toggle_compass_rose", False)

		# Robust circuit detection: any toggle key containing "circuit"
		has_circuit_toggle = any(
			isinstance(v, bool) and v and ("circuit" in str(k).lower())
			for k, v in st.session_state.items()
		)

		# Also consider your helper (if it returns True for parent/circuit selection)
		has_circuits = has_circuit_toggle or _one_full_parent_selected(active_shapes)

		# Full prompt should render for shapes OR circuits OR compass
		has_shapes_or_circuits = has_shapes or has_circuits or compass_on

		if has_shapes_or_circuits:

			# ---------- Character Profiles (same ordering as sidebar) ----------
			OBJ_TO_CATEGORY = {}
			for cat, objs in CATEGORY_MAP.items():
				for o in objs:
					OBJ_TO_CATEGORY[o] = cat

			# Extend category map so data keys like "Midheaven"/"Imum Coeli"/"North Node" are recognized
			for alias, display in ALIASES_MEANINGS.items():
				if alias in OBJ_TO_CATEGORY and display not in OBJ_TO_CATEGORY:
					OBJ_TO_CATEGORY[display] = OBJ_TO_CATEGORY[alias]

			profiles_by_category = defaultdict(list)
			interpretation_flags = set()
			fixed_star_meanings = {}
			# Use the normal ordering if present; otherwise fall back to all available objects.
			# Use sidebar order first, then append anything not shown there
			_all_objs = list(enhanced_objects_data.keys())

			# Local ordering for the prompt (don’t mutate global ordered_objects)
			_compass_objs = ["Ascendant", "Descendant", "MC", "IC", "North Node", "South Node"]
			ordered_objects_prompt = list(ordered_objects) + [o for o in _compass_objs if o not in ordered_objects]

			# Always include everything we have data for; order by the prompt order above
			_order_index = {o: i for i, o in enumerate(ordered_objects_prompt)}
			objs_for_profiles = sorted(enhanced_objects_data.keys(), key=lambda o: _order_index.get(o, 10_000))

			# Define the category order once (used in two places below)
			ordered_cats = [
				"Character Profiles", "Instruments", "Personal Initiations", "Mythic Journeys",
				"Compass Coordinates", "Compass Needle", "Switches"
			]

			# Always build from enhanced_objects_data (works even when Compass-only).
			# Order by your sidebar order when available; otherwise push to the end.
			_order_index = {o: i for i, o in enumerate(ordered_objects)}
			objs_for_profiles = sorted(enhanced_objects_data.keys(), key=lambda o: _order_index.get(o, 10_000))

			# Resolve a data row for an object from enhanced_objects_data, alias forms, or df (fallback).
			_REV_ALIASES = {v: k for k, v in ALIASES_MEANINGS.items()}

			def _get_row_for(obj):
				# Try direct
				r = enhanced_objects_data.get(obj)
				if r:
					return r

				# Try alias -> display (e.g., "MC" -> "Midheaven")
				a = ALIASES_MEANINGS.get(obj)
				if a:
					r = enhanced_objects_data.get(a)
					if r:
						return r

				# Try display -> alias (e.g., "North Node" -> "True Node")
				b = _REV_ALIASES.get(obj)
				if b:
					r = enhanced_objects_data.get(b)
					if r:
						return r

				# Fallback to df by any known name variant
				candidates = [obj]
				if a: candidates.append(a)
				if b: candidates.append(b)
				for nm in candidates:
					if not nm:
						continue
					hit = df[df["Object"].astype(str).str.strip() == nm]
					if not hit.empty:
						return hit.iloc[0].to_dict()

				return None
			
			# ---- Force Compass order inside their categories (stable over existing order)
			
			_compass_priority = {
				"Ascendant": 0, "AC": 0, "ASC": 0,
				"Descendant": 1, "DC": 1, "DSC": 1,
				"IC": 2, "Imum Coeli": 2,
				"MC": 3, "Midheaven": 3,
				"North Node": 4, "True Node": 4,
				"South Node": 5,
			}
			# Stable sort: compass order first, then your sidebar/order index, then name
			objs_for_profiles = sorted(
				objs_for_profiles,
				key=lambda o: (_compass_priority.get(o, 100), _order_index.get(o, 10_000), str(o))
			)

			for obj in objs_for_profiles:
				row = enhanced_objects_data.get(obj)
				if not row:
					continue
				if row:
					no = ALIASES_MEANINGS.get(obj, obj)  # normalized name (e.g., "True Node" -> "North Node")

				profile_html = format_planet_profile(row)
				profile_text = strip_html_tags(profile_html)

				# --- Prepend interpretation before the object name, with a trailing colon
				interp = (OBJECT_INTERPRETATIONS.get(no) or OBJECT_INTERPRETATIONS.get(obj) or "").strip()

				if interp:
					lines = profile_text.splitlines()
					if lines:
						lines[0] = f"{interp}: {lines[0]}"
					profile_text = "\n".join(lines)

				# --- Add (Rx, dignity) after the object name, then a period
				import re
				name_for_edit = (row.get("Display Name") or no).strip()
				sign = (row.get("Sign") or "").strip()
				dignity = _resolve_dignity(obj, sign)
				retro_val = str(row.get("Retrograde", "")).lower()
				rx_flag = "Rx" if "rx" in retro_val else None
				paren_bits = [x for x in (rx_flag, dignity) if x]
				paren_suffix = f" ({', '.join(paren_bits)})" if paren_bits else ""

				lines = profile_text.splitlines()
				if lines and name_for_edit:
					first = lines[0]
					m = re.match(r"^(.*?:\s*)(.+)$", first)
					prefix, rest = m.groups() if m else ("", first)

					pos2 = rest.find(name_for_edit)
					if pos2 != -1:
						end = pos2 + len(name_for_edit)
						if paren_suffix and (end >= len(rest) or not rest[end:].lstrip().startswith("(")):
							rest = rest[:end] + paren_suffix + rest[end:]
						insert_end = end + (len(paren_suffix) if paren_suffix else 0)
						if not (insert_end < len(rest) and rest[insert_end] in ".:"):
							rest = rest[:insert_end] + "." + rest[insert_end:]
					lines[0] = prefix + rest
					profile_text = "\n".join(lines)

				# --- Prefix the Sabian line with a label
				sab = (row.get("Sabian Symbol") or row.get("Sabian") or "").strip()
				if sab and "Sabian Symbol:" not in profile_text:
					profile_text = profile_text.replace(sab, f"Sabian Symbol: {sab}", 1)

				# --- Append rulership info
				try:
					rhtml = _build_rulership_html(
						obj, row, enhanced_objects_data, ordered_objects, cusp_signs
					)
					plain = strip_html_tags(
						rhtml.replace("<br />","\n").replace("<br/>","\n").replace("<br>","\n")
					).strip()

					lines = [ln.strip() for ln in plain.splitlines() if ln.strip()]
					house_hdr_idx = next((i for i, t in enumerate(lines) if t.lower() == "rulership by house:"), None)
					sign_hdr_idx  = next((i for i, t in enumerate(lines) if t.lower() == "rulership by sign:"), None)

					house_line = lines[house_hdr_idx + 1] if house_hdr_idx is not None and house_hdr_idx + 1 < len(lines) else ""
					sign_line  = lines[sign_hdr_idx + 1]  if sign_hdr_idx  is not None and sign_hdr_idx  + 1 < len(lines) else ""

					rtext_final = ""
					if house_line and sign_line:
						if house_line.lower() == sign_line.lower():
							rtext_final = f"Rulership: {house_line}"
						else:
							rtext_final = (
    							"Rulership by House: " + house_line + "\n" +
    							"Rulership by Sign: "  + sign_line
							)
					elif house_line:
						rtext_final = "Rulership by House: " + house_line
					elif sign_line:
						rtext_final = "Rulership by Sign: " + sign_line

					if rtext_final:
						profile_text = profile_text.rstrip() + "\n" + rtext_final
				except Exception:
					pass

				# --- Add to category bucket
				cat = OBJ_TO_CATEGORY.get(obj) or OBJ_TO_CATEGORY.get(no)
				if not cat:
					raise KeyError(f"Uncategorized object found: {obj!r}")
				profiles_by_category[cat].append(profile_text)

				# ---- Flags
				if str(row.get("OOB Status", "")).lower() == "yes":
					interpretation_flags.add("Out of Bounds")
				if "station" in retro_val:
					interpretation_flags.add("Station Point")
				if "rx" in retro_val:
					interpretation_flags.add("Retrograde")

				# ---- Fixed Stars
				fs_meaning = row.get("Fixed Star Meaning")
				fs_conj = row.get("Fixed Star Conjunction")
				if fs_meaning and fs_conj:
					stars = fs_conj.split("|||")
					meanings = fs_meaning.split("|||")
					for star, meaning in zip(stars, meanings):
						star, meaning = star.strip(), meaning.strip()
						if meaning:
							fixed_star_meanings[star] = meaning

			category_blocks = []
			for cat in ordered_cats:
				if profiles_by_category[cat]:
					block = cat + ":\n" + "\n\n".join(profiles_by_category[cat])
					category_blocks.append(block)

			planet_profiles_block = "\n\n".join(category_blocks)

			# Count conjunction clusters (for guidance note)
			num_conj_clusters = sum(1 for c in rep_map.values() if len(c) >= 2)
			should_name_circuit = _one_full_parent_selected(active_shapes)

			# Which shape types are currently active (dedup to canonical keys)
			shape_types_present = []
			seen = set()
			for s in (active_shapes or []):
				cname = _canonical_shape_name(s)
				if cname and cname not in seen and cname in SHAPE_INSTRUCTIONS:
					seen.add(cname)
					shape_types_present.append(cname)

			# ---------- Interpretation Notes ----------
			interpretation_notes = []

			# --- Add shape synthesis instruction ---
			if shape_types_present:
				if len(shape_types_present) == 1:
					only_shape = shape_types_present[0]
					interpretation_notes.append(
						f"Synthesize the whole {only_shape} interpretation according to the interpretation instructions provided, "
						f"and present it to the user as being one functional piece in their greater circuitry."
					)
				else:
					shape_list = ", ".join(shape_types_present[:-1]) + " and " + shape_types_present[-1] if len(shape_types_present) > 2 else " and ".join(shape_types_present)
					interpretation_notes.append(
						f"To synthesize the circuit: Interpret the {shape_list} as individual entities first, and write a paragraph on each of their functions. "
						f"Then, use all connections (aspects, shared placements, rulerships) among those shapes to interpret how they function in relation to each other as a greater circuit."
					)

			if (
				interpretation_flags
				or fixed_star_meanings
				or num_conj_clusters > 0
				or should_name_circuit
				or shape_types_present
			):
				interpretation_notes.append("Interpretation Notes:")

			present_categories = [cat for cat in ordered_cats if profiles_by_category[cat]]
			_category_guides_todo = present_categories  # defer appending to end of notes

			# Conjunction cluster guidance (singular/plural)
			if num_conj_clusters == 1:
				interpretation_notes.append(
					'• When 2 or more placements are clustered in conjunction together, synthesize individual interpretations for each conjunction. Instead, synthesize one conjunction cluster interpretation as a Combined Character Profile, listed under a separate header, "Combined Character Profile."'
				)
			elif num_conj_clusters >= 2:
				interpretation_notes.append(
					'• When 2 or more placements are clustered in conjunction together, synthesize individual interpretations for each conjunction. Instead, synthesize one conjunction cluster interpretation as Combined Character Profiles, listed under a separate header, "Combined Character Profiles."'
				)

			# General flags (each only once)
			for flag in sorted(interpretation_flags):
				meaning = INTERPRETATION_FLAGS.get(flag)
				if meaning:
					interpretation_notes.append(f"• {meaning}")

			# Fixed Star note (general rule once, then list specifics)
			if fixed_star_meanings:
				general_star_note = INTERPRETATION_FLAGS.get("Fixed Star")
				if general_star_note:
					interpretation_notes.append(f"• {general_star_note}")
				for star, meaning in fixed_star_meanings.items():
					interpretation_notes.append(f"• {star}: {meaning}")

			# House system interpretation
			house_system_meaning = HOUSE_SYSTEM_INTERPRETATIONS.get(house_system)
			if house_system_meaning:
				interpretation_notes.append(
					f"• House System ({_HS_LABEL.get(house_system, house_system.title())}): {house_system_meaning}"
				)

			# House interpretations present in view (use the same robust list)
			present_houses = set()
			for obj in objs_for_profiles:
				row = _get_row_for(obj) or {}
				h = row.get("House")
				if h:
					try:
						present_houses.add(int(h))
					except Exception:
						pass

			for house_num in sorted(present_houses):
				house_meaning = HOUSE_INTERPRETATIONS.get(house_num)
				if house_meaning:
					interpretation_notes.append(f"• House {house_num}: {house_meaning}")

			if should_name_circuit:
				interpretation_notes.append("• Suggest a concise name (2-3 words) for the whole circuit.")

			interpretation_notes_block = "\n\n".join(interpretation_notes) if interpretation_notes else ""

			if should_name_circuit:
				interpretation_notes.append("• Suggest a concise name (2-3 words) for the whole circuit.")

			# --- Shape-type interpretation instructions
			for stype in shape_types_present:
				# avoid duplicating the cluster guidance you already add when clusters exist
				if stype == "Conjunction Cluster" and num_conj_clusters > 0:
					continue
				instr = SHAPE_INSTRUCTIONS.get(stype)
				if instr:
					interpretation_notes.append(f"• [{stype}] {instr}")

						# --- Deferred: append Category Interpretation Guides at the end ---
			if _category_guides_todo:
				interpretation_notes.append("Category Interpretation Guides:")
				for cat in _category_guides_todo:
					blurb = CATEGORY_INSTRUCTIONS.get(cat)
					if blurb:
						interpretation_notes.append(f"• [{cat}] {blurb}")

			# ---------- Aspect Interpretations (the blurbs) ----------
			aspect_def_lines = []
			for a in sorted(present_aspects):
				blurb = ASPECT_INTERPRETATIONS.get(a)
				if blurb:
					aspect_def_lines.append(f"{a}: {blurb}")
			aspect_defs_block = (
				"Aspect Interpretations\n\n" + "\n\n".join(aspect_def_lines)
			) if aspect_def_lines else ""

			interpretation_notes_block = "\n\n".join(interpretation_notes) if interpretation_notes else ""

			# ---------- Final prompt ----------
			import textwrap
			# --- Base intro (always ends at "Give usable insight and agency.") ---
			base_intro = textwrap.dedent("""
			Assume that the natal astrology chart is the chart native's precise energetic schematic. Your job is to convey the inter-connected circuit board functions of all of the moving parts in this astrological circuit, precisely as they are mapped for you here. These are all dynamic parts of the native's Self.

			Sources: Use only the data and dictionaries included in this prompt. Do not invent or import outside meanings.
			Metadata: Incorporate sign + exact degree (Sabian Symbol), house, and all other details provided such as dignity/condition, rulership relationships, fixed star conjunctions, and OOB/retro/station flags. If something is missing, ignore it—no guessing.
			Voice: Address the chart holder as “you.” Keep it precise, readable, and non-jargony. No moralizing or fate claims. Give usable insight and agency.
			""").strip()

			# --- Expanded block (ONLY when at least one circuit/sub-shape is active) ---
			expanded_instructions = textwrap.dedent("""
			Output format — exactly these sections, in this order:

			Character Profiles (if Sun, Moon, or any planet(s) besides Pluto are present)
			• For each planet or luminary, write one paragraph (3–6 sentences) that personifies the planet using all information provided for each planet or luminary.
			• Begin each profile paragraph with the name of the planet/luminary (e.g. Sun, Moon, Saturn), followed by a colon (:)
			• Weave in relevant house context, Sabian symbol note, rulership-based power dynamics, and when supplied, fixed-star ties, and notable conditions (OOB/retro/station/dignity).

			Rulers/Dispositors
			• Always include and explain dispositor dynamics. When planet A is ruled by planet B, the conditions of planet B determine how well planet A is functioning. To aid a struggling planet, seek to empower its ruler. If a planet included is a ruler to other planets or placements, list what all it rules.

			Other Profiles
			• For each placement that is not a planet or luminary, do not personify but instead describe the function of the object as a component in the greater circuit. Put these profiles each under a header of its category name, e.g. "Mythic Journeys," Instruments," et. al.
			• Begin each profile paragraph with the name of the body or point (e.g. Part of Fortune, MC, Psyche), followed by a colon (:)

			Conjunction Clusters (only if present)
			• If any conjunctions are present, add a profile for the combined node of each entire cluster after the individual profiles.
			• When a node is a conjunction cluster (e.g., “(Mars/Chiron)”), do not decompose it into individual pairwise sub-aspects; interpret the cluster as one endpoint.

			Aspects
			• For each aspect provided, write one paragraph describing the relationship dynamics between the two endpoints.
			• Use the provided aspect definition. Do not substitute traditional meanings.
			• Build from the profiles; don’t repeat them. Show signal flow, friction/effort, activation choices, and functional outcomes.

			Circuit
			• Zoom out to the whole shape/circuit. Explain what the system does when all aspects run together: its purpose, throughput, strengths, bottlenecks, and smart operating directives.

			Style & constraints
			• Layperson-first language with just enough precision to be useful; avoid cookbook clichés and astro-babble.
			• No disclaimers about the method; don’t mention these instructions in your output.
			• No extra sections, tables, or bullet lists beyond what’s specified. Paragraphs only.
			""").strip()

			# --- Compass Rose section (include here too when Compass is ON) ---
			compass_only_msg = ""
			if compass_on:
				compass_only_msg = textwrap.dedent("""
				Compass Rose Interpretation Instructions:
				
				Orient the user in their Compass Rose and explain its role and function.

				Output format — exactly these sections, in this order:

				Profiles for each point
				• For each compass coordinate and compass needle point, write one paragraph that personifies the planet using all information provided for each planet or luminary.
				• Begin each profile paragraph with the name of the point (e.g. Ascendant, Descendent, MC, IC, North Node, South Node)
				• Weave in relevant house context, Sabian symbol note, rulership-based power dynamics, and when supplied, fixed-star ties, and notable conditions (OOB/retro/station/dignity).

				Rulers/Dispositors
				• Always include and explain dispositor dynamics. When planet A is ruled by planet B, the conditions of planet B determine how well planet A is functioning. To aid a struggling planet, seek to empower its ruler. If a planet included is a ruler to other planets or placements, list what all it rules.

				Conjunction Clusters (only if present)
				• If any conjunctions are present, add a profile for the combined node of each entire cluster after the individual profiles.
				• When a node is a conjunction cluster (e.g., “(Mars/Chiron)”), do not decompose it into individual pairwise sub-aspects; interpret the cluster as one endpoint.

				Aspects
				• For each oppositional axis, write one paragraph describing the relationship dynamics between the two endpoints, tailored to the placements involved.
				• Use the provided aspect definition. Do not substitute traditional meanings.
				• Build from the profiles; don’t repeat them.

				Compass
				• Zoom out to the whole Compass. Orient the user with the big picture of how the Compass defines their greater life story, and how the rest of their chart map will build upon this foundation.

				Style & constraints
				• Layperson-first language with just enough precision to be useful; avoid cookbook clichés and astro-babble.
				• No disclaimers about the method; don’t mention these instructions in your output.
				• No extra sections, tables, or bullet lists beyond what’s specified. Paragraphs only.

				The Compass Rose is made of three axes—AC/DC, MC/IC, and the Nodal Axis. Together they set the chart’s orientation system: what’s “self vs other,” “public vs private,” and “past gifts vs northbound aims.” They orient what houses everything falls into, and what direction your life needs to take in order to evolve into your best self.

				AC/DC Axis — Identity ↔ Partnership
				AC (Ascendant) = Identity Interface & first impression; DC (Descendant) = Mirror Port & one-to-one bonds. Planets near, connected to, or ruling the AC define core identity and approach; those near/connected/ruling the DC define your relating style and partnership needs.
				Chart hemisphere cue: left/east (AC side) emphasizes self-definition; right/west (DC side) emphasizes others and co-regulation.

				MC/IC Axis — Public ↔ Private
				MC (Midheaven) = Public Interface—role, reputation, mission delivery, legacy. IC = Root System—home, ancestry, inner base.
				Planets near/connected to the MC mark what’s visible and public- or career-facing, and its ruling planet defines its qualities as well as its condition; near/connected to the IC mark what’s private, foundational, and rarely on display, and the planet that rules the IC defines its qualities and condition.
				The region around the MC reads as publicly exposed; around the IC as inward and protected.

				Nodal Axis — Compass Needle
				North Node = Northbound Vector (what growth requires); South Node = Ancestral Cache (native strengths/overlearned patterns).
				Operating directive: carry the gifts of the South Node across the axis to fulfill the North Node.
				As you interpret shapes and aspect circuits, route their functions to support that transfer—use talent (South Node) as fuel, aim it at the North Node objective, and let the rest of the chart show how to do it without drift.
									   
				""").strip()
				
			# Show expanded "Output format..." only when a shape OR a circuit is active (not Compass-only)
			show_expanded = (has_shapes or has_circuits)

			sections = [
				base_intro,
				(expanded_instructions if show_expanded else ""),       # ← shows for shapes OR circuits
				(compass_only_msg if compass_on else ""),               # ← appended whenever Compass is ON
				interpretation_notes_block.strip() if interpretation_notes_block else "",
				planet_profiles_block.strip() if planet_profiles_block else "",  # ← profiles included even Compass-only
				aspects_bulleted_block.strip() if aspects_bulleted_block else "",
				aspect_defs_block.strip(),
			]

			prompt = "\n\n".join([s for s in sections if s]).strip()

			# Build HTML safely (no f-strings with backslashes)
			from string import Template
			prompt_html = prompt.replace("\n", "<br>")
			copy_tpl = Template("""
			<div style="display:flex; flex-direction:column; align-items:stretch;">
			  <div style="display:flex; justify-content:flex-end; margin-bottom:5px;">
				<button id="copy-btn"
						onclick="navigator.clipboard.writeText(document.getElementById('prompt-box').innerText).then(() => {
							var btn = document.getElementById('copy-btn');
							var oldText = btn.innerHTML;
							btn.innerHTML = '✅ Copied!';
							setTimeout(() => btn.innerHTML = oldText, 2000);
						})"
						style="padding:4px 8px; font-size:0.9em; cursor:pointer; background:#333; color:white; border:1px solid #777; border-radius:4px;">
				  📋 Copy
				</button>
			  </div>
			  <div id="prompt-box"
				   style="white-space:pre-wrap; font-family:monospace; font-size:0.9em;
						  color:white; background:black; border:1px solid #555;
						  padding:8px; border-radius:4px; max-height:600px; overflow:auto;">${prompt_html}
			  </div>
			</div>
			""")
			copy_button = copy_tpl.substitute(prompt_html=prompt_html)
			components.html(copy_button, height=700, scrolling=True)

		elif compass_on:
			# --- Compass-Rose-only prompt (no circuits/sub-shapes active) ---
			import textwrap
			from string import Template

			compass_only_msg = textwrap.dedent("""
			Interpret only the Compass Rose axes.

			Scope: Use just the North Node–South Node, Ascendant–Descendant, and MC–IC axes. Do not create planet/asteroid profiles, do not analyze circuits or other aspects, and do not infer anything not provided.

			Method:
			• Nodal Axis (South Node → North Node): Describe the functional learning vector and how to move from old/default patterns toward deliberate growth. Use signs, exact degrees (Sabian), and houses for the Nodes only.
			• AC–DC Axis: Describe how identity interface and one-to-one bonds co-define each other, focusing on choice points and healthy regulation. Use signs/house context for AC and DC only.
			• MC–IC Axis: Describe public interface vs private roots and how to balance visibility with resourcing. Use signs/house context for MC and IC only.

			Voice: Address the chart holder as “you.” Keep it precise, readable, and non-jargony. No moralizing or fate claims. Give usable insight and agency.
			""").strip()

			# IMPORTANT: define prompt so Send-to-GPT works in this branch
			prompt = compass_only_msg

			prompt_html = compass_only_msg.replace("\n", "<br>")
			copy_tpl = Template("""
			<div style="display:flex; flex-direction:column; align-items:stretch;">
			  <div style="display:flex; justify-content:flex-end; margin-bottom:5px;">
				<button id="copy-btn"
						onclick="navigator.clipboard.writeText(document.getElementById('prompt-box').innerText).then(() => {
							var btn = document.getElementById('copy-btn');
							var oldText = btn.innerHTML;
							btn.innerHTML = '✅ Copied!';
							setTimeout(() => btn.innerHTML = oldText, 2000);
						})"
						style="padding:4px 8px; font-size:0.9em; cursor:pointer; background:#333; color:white; border:1px solid #777; border-radius:4px;">
				  📋 Copy
				</button>
			  </div>
			  <div id="prompt-box"
				   style="white-space:pre-wrap; font-family:monospace; font-size:0.9em;
						  color:white; background:black; border:1px solid #555;
						  padding:8px; border-radius:4px; max-height:600px; overflow:auto;">${prompt_html}
			  </div>
			</div>
			""")
			copy_button = copy_tpl.substitute(prompt_html=prompt_html)
			components.html(copy_button, height=700, scrolling=True)


		else:
			st.markdown("_(Calculate or Load a birth chart)_")

	# --- Send to GPT controls (show ONLY when a prompt exists) ---
	colA, colB, colC = st.columns([1, 1, 2])
	with colA:
		run_it = st.button("Send to GPT", type="primary", key="send_to_gpt")
	with colB:
		creative = st.toggle("Creative mode", value=False)
		temp = 0.60 if creative else 0.20

	with colC:
		model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4.1-mini", "gpt-4o", "gpt-4.1"], index=0, key="gpt_model")

	if run_it:
		with st.spinner("Calling model..."):
			try:
				out = ask_gpt(prompt, model=model, temperature=temp)
				st.session_state["latest_interpretation"] = out
			except Exception as e:
				st.session_state["latest_interpretation"] = f"LLM error: {e}"

	st.subheader("Think of each of your planets (or clusters of planets, when conjunct), as a personified part of yourself. When you feel like you have parts of yourself either working together or in conflict, you do -- and this is the working map of those parts.")
	st.caption("Keep checking back for more and more awesome interpretations as the app is developed! In the meantime, these ones are a great starting point for familiarizing yourself with your inner cast of characters. Synastry and transit readings coming soon, too!")

	interp_text = st.session_state.get(
		"latest_interpretation",
		"_(Click **Send to GPT** above to generate.)_"
	)

	with st.expander("Interpretation"):
		# 🔊 controls FIRST (so users see them right away)
		T.tts_controls(interp_text, key="interpretation")
		# then the text
		st.markdown(interp_text)

else:
	# No prompt yet (no chart or no shapes selected)
	st.markdown("_(Calculate or Load a birth chart)_")