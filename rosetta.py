import datetime as dt
import json
import os
import re
import sqlite3

import bcrypt
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import streamlit_authenticator as stauth
import swisseph as swe

from rosetta.calc import calculate_chart
from rosetta.drawing import (
    draw_aspect_lines,
    draw_degree_markers,
    draw_filament_lines,
    draw_house_cusps,
    draw_minor_edges,
    draw_planet_labels,
    draw_shape_edges,
    draw_singleton_dots,
    draw_zodiac_signs,
)
from rosetta.helpers import (
    annotate_fixed_stars,
    build_aspect_graph,
    deg_to_rad,
    format_dms,
    format_longitude,
    get_ascendant_degree,
    get_fixed_star_meaning,
)
from rosetta.lookup import (
    ASPECT_INTERPRETATIONS,
    ASPECTS,
    GLYPHS,
    GROUP_COLORS,
    HOUSE_INTERPRETATIONS,
    HOUSE_SYSTEM_INTERPRETATIONS,
    INTERPRETATION_FLAGS,
    MAJOR_OBJECTS,
    MODALITIES,
    OBJECT_MEANINGS,
    PLANETARY_RULERS,
    ZODIAC_COLORS,
    ZODIAC_SIGNS,
)
from rosetta.patterns import (
    _cluster_conjunctions_for_detection,
    connected_components_from_edges,
    detect_minor_links_with_singletons,
    detect_shapes,
    generate_combo_groups,
    internal_minor_edges_for_pattern,
)

# -------------------------
# Init / session management
# -------------------------
if "reset_done" not in st.session_state:
    st.session_state.clear()
    st.session_state["reset_done"] = True

if "last_house_system" not in st.session_state:
    st.session_state["last_house_system"] = "equal"

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
    unsafe_allow_html=True,
)

st.title("🧭 Rosetta Flight Deck")

# ---- DB bootstrap & helpers (put this ONCE, above auth) ----
BASE_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "profiles.db")


def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)

    # users table (with role)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            email    TEXT NOT NULL,
            pw_hash  TEXT NOT NULL,
            role     TEXT NOT NULL DEFAULT 'user'
        )
    """
    )

    # migrate 'role' if missing (for older DBs)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(users)")]
    if "role" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        conn.commit()

    # private, per-user profiles
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            user_id      TEXT NOT NULL,
            profile_name TEXT NOT NULL,
            payload      TEXT NOT NULL,
            PRIMARY KEY (user_id, profile_name),
            FOREIGN KEY (user_id) REFERENCES users(username)
        )
    """
    )

    # community profiles table (opt-in, shared)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS community_profiles (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_name TEXT NOT NULL,
            payload      TEXT NOT NULL,
            submitted_by TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """
    )

    return conn


def _credentials_from_db():
    conn = _db()
    rows = conn.execute("SELECT username, name, email, pw_hash FROM users").fetchall()
    return {
        "usernames": {
            u: {"name": n, "email": e, "password": h} for (u, n, e, h) in rows
        }
    }


def user_exists(username: str) -> bool:
    conn = _db()
    return (
        conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        is not None
    )


def create_user(
    username: str, name: str, email: str, plain_password: str, role: str = "user"
) -> None:
    conn = _db()
    pw_hash = bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )
    conn.execute(
        "INSERT OR REPLACE INTO users (username, name, email, pw_hash, role) VALUES (?, ?, ?, ?, ?)",
        (username, name, email, pw_hash, role),
    )
    conn.commit()


def get_user_role(username: str) -> str:
    conn = _db()
    row = conn.execute(
        "SELECT role FROM users WHERE username = ?", (username,)
    ).fetchone()
    return row[0] if row else "user"


def is_admin(username: str) -> bool:
    return get_user_role(username) == "admin"


def verify_password(username: str, candidate_password: str) -> bool:
    conn = _db()
    row = conn.execute(
        "SELECT pw_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if not row:
        return False
    return bcrypt.checkpw(
        candidate_password.encode("utf-8"),
        row[0].encode() if isinstance(row[0], str) else row[0],
    )


def set_password(username: str, new_plain_password: str) -> None:
    conn = _db()
    pw_hash = bcrypt.hashpw(
        new_plain_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    conn.execute("UPDATE users SET pw_hash = ? WHERE username = ?", (pw_hash, username))
    conn.commit()


def load_user_profiles_db(user_id: str) -> dict:
    conn = _db()
    rows = conn.execute(
        "SELECT profile_name, payload FROM profiles WHERE user_id = ?", (user_id,)
    ).fetchall()
    return {name: json.loads(payload) for (name, payload) in rows}


def save_user_profile_db(user_id: str, profile_name: str, payload: dict) -> None:
    conn = _db()
    conn.execute(
        "INSERT OR REPLACE INTO profiles (user_id, profile_name, payload) VALUES (?, ?, ?)",
        (user_id, profile_name, json.dumps(payload)),
    )
    conn.commit()


def delete_user_profile_db(user_id: str, profile_name: str) -> None:
    conn = _db()
    conn.execute(
        "DELETE FROM profiles WHERE user_id = ? AND profile_name = ?",
        (user_id, profile_name),
    )
    conn.commit()


# --- Community helpers ---
def community_list(limit: int = 200) -> list[dict]:
    conn = _db()
    rows = conn.execute(
        "SELECT id, profile_name, payload, submitted_by, created_at, updated_at "
        "FROM community_profiles ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    out = []
    for id_, name, payload, by, c_at, u_at in rows:
        out.append(
            {
                "id": id_,
                "profile_name": name,
                "payload": json.loads(payload),
                "submitted_by": by,
                "created_at": c_at,
                "updated_at": u_at,
            }
        )
    return out


def community_get(pid: int) -> dict | None:
    conn = _db()
    row = conn.execute(
        "SELECT id, profile_name, payload, submitted_by, created_at, updated_at "
        "FROM community_profiles WHERE id = ?",
        (pid,),
    ).fetchone()
    if not row:
        return None
    id_, name, payload, by, c_at, u_at = row
    return {
        "id": id_,
        "profile_name": name,
        "payload": json.loads(payload),
        "submitted_by": by,
        "created_at": c_at,
        "updated_at": u_at,
    }


def community_save(profile_name: str, payload: dict, submitted_by: str) -> int:
    conn = _db()
    ts = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    cur = conn.execute(
        "INSERT INTO community_profiles (profile_name, payload, submitted_by, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (profile_name, json.dumps(payload), submitted_by, ts, ts),
    )
    conn.commit()
    return cur.lastrowid


def community_delete(pid: int) -> None:
    conn = _db()
    conn.execute("DELETE FROM community_profiles WHERE id = ?", (pid,))
    conn.commit()


# --- Authentication (admin-gated user management; no public registration) ---
creds = _credentials_from_db()
auth_cfg = st.secrets.get("auth", {})
cookie_name = auth_cfg.get("cookie_name", "rosetta_auth")
cookie_key = auth_cfg.get("cookie_key", "change_me")
cookie_days = int(auth_cfg.get("cookie_expiry_days", 30))

authenticator = stauth.Authenticate(
    credentials=creds,
    cookie_name=cookie_name,
    key=cookie_key,
    cookie_expiry_days=cookie_days,
)

# Version-agnostic login shim
try:
    out = authenticator.login(location="sidebar", form_name="Login")
except TypeError:
    try:
        out = authenticator.login("sidebar", "Login")
    except TypeError:
        out = authenticator.login("sidebar", fields={"Form name": "Login"})

if isinstance(out, tuple) and len(out) == 3:
    name, auth_status, username = out
else:
    name = st.session_state.get("name")
    auth_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")

if auth_status is True:
    current_user_id = username
    admin_flag = is_admin(current_user_id)  # <- role check

    with st.sidebar:
        st.caption(
            f"Logged in as **{name}** ({username}) — role: **{get_user_role(current_user_id)}**"
        )
        authenticator.logout("Logout", location="sidebar")

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
                elif not verify_password(current_user_id, cur):
                    st.error("Current password is incorrect.")
                else:
                    set_password(current_user_id, new1)
                    st.success("Password updated.")

        # Admin-only: user management (create users / reset passwords)
        if admin_flag:
            with st.expander("Admin: User Management"):
                st.markdown("**Create user**")
                u = st.text_input("Username", key="admin_new_user")
                full = st.text_input("Full name", key="admin_new_name")
                em = st.text_input("Email", key="admin_new_email")
                role = st.selectbox(
                    "Role", ["user", "admin"], index=0, key="admin_new_role"
                )
                temp = st.text_input(
                    "Temp password", type="password", key="admin_new_pw"
                )
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
                npw1 = st.text_input(
                    "New password", type="password", key="admin_reset_pw1"
                )
                npw2 = st.text_input(
                    "Repeat new password", type="password", key="admin_reset_pw2"
                )
                if st.button("Reset password", key="admin_reset_pw_btn"):
                    if not (target and npw1 and npw2):
                        st.error("All fields are required.")
                    elif npw1 != npw2:
                        st.error("Passwords must match.")
                    elif not user_exists(target):
                        st.error("No such username.")
                    else:
                        set_password(target, npw1)
                        st.success(f"Password reset for '{target}'.")

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
    off = (x_deg - start_deg) % 360.0
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
    """Draw zodiac signs + modalities around the wheel."""
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
            ax.text(
                rad,
                offset,
                label,
                ha="center",
                va="center",
                fontsize=9,
                color="white" if dark_mode else "black",
            )


def draw_aspect_lines(
    ax, pos, patterns, active_patterns, asc_deg, group_colors=None, edges=None
):
    single_pattern_mode = len(active_patterns) == 1
    if edges:
        # only draw edges where both nodes sit inside one active pattern
        active_sets = [set(patterns[i]) for i in active_patterns]
        for (p1, p2), asp in edges:
            if any((p1 in s and p2 in s) for s in active_sets):
                r1 = deg_to_rad(pos[p1], asc_deg)
                r2 = deg_to_rad(pos[p2], asc_deg)
                color = (
                    ASPECTS[asp]["color"]
                    if single_pattern_mode
                    else GROUP_COLORS[list(active_patterns)[0] % len(GROUP_COLORS)]
                )
                ax.plot(
                    [r1, r2],
                    [1, 1],
                    linestyle=ASPECTS[asp]["style"],
                    color=color,
                    linewidth=2,
                )
        return
    # fallback: current recompute path ...


def draw_filament_lines(ax, pos, filaments, active_patterns, asc_deg):
    """Draw dotted lines for minor aspects between active patterns."""
    single_pattern_mode = len(active_patterns) == 1
    for p1, p2, asp_name, pat1, pat2 in filaments:
        if pat1 in active_patterns and pat2 in active_patterns:
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
    unsafe_allow_html=True,
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
                for aspect in (
                    "Conjunction",
                    "Sextile",
                    "Square",
                    "Trine",
                    "Opposition",
                ):
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
    "#FF5214",
    "#FFA600",
    "#FBFF00",
    "#87DB00",
    "#00B828",
    "#049167",
    "#006EFF",
    "#1100FF",
    "#6320FF",
    "#9E0099",
    "#FF00EA",
    "#720022",
    "#4B2C06",
    "#534546",
    "#C4A5A5",
    "#5F7066",
]

_HS_LABEL = {"equal": "Equal", "whole": "Whole Sign", "placidus": "Placidus"}


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
    return (
        "<div style='line-height:1.1; margin-bottom:6px;'>"
        + "".join(html_parts)
        + "</div>"
    )


from matplotlib.patches import FancyBboxPatch


def _current_chart_header_lines():
    name = (
        st.session_state.get("current_profile_title")
        or st.session_state.get("current_profile")
        or "Untitled Chart"
    )
    if isinstance(name, str) and name.startswith("community:"):
        name = "Community Chart"

    month = st.session_state.get("profile_month_name", "")
    day = st.session_state.get("profile_day", "")
    year = st.session_state.get("profile_year", "")
    hour = st.session_state.get("profile_hour")
    minute = st.session_state.get("profile_minute")
    city = st.session_state.get("profile_city", "")

    # 12-hour time
    time_str = ""
    if hour is not None and minute is not None:
        h = int(hour)
        m = int(minute)
        ampm = "AM" if h < 12 else "PM"
        h12 = 12 if (h % 12 == 0) else (h % 12)
        time_str = f"{h12}:{m:02d} {ampm}"

    date_line = f"{month} {day}, {year}".strip()
    if date_line and time_str:
        date_line = f"{date_line}, {time_str}"
    elif time_str:
        date_line = time_str

    return name, date_line, city


import matplotlib.patheffects as pe


def _draw_header_on_figure(fig, name, date_line, city, dark_mode):
    """Paint a 3-line header in the figure margin (top-left), never over the wheel."""
    color = "white" if dark_mode else "black"
    stroke = "black" if dark_mode else "white"
    effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

    y0 = 0.99  # top margin in figure coords
    x0 = 0.00  # left margin

    fig.text(
        x0,
        y0,
        name,
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        color=color,
        path_effects=effects,
    )
    if date_line:
        fig.text(
            x0,
            y0 - 0.035,
            date_line,
            ha="left",
            va="top",
            fontsize=9,
            color=color,
            path_effects=effects,
        )
    if city:
        fig.text(
            x0,
            y0 - 0.065,
            city,
            ha="left",
            va="top",
            fontsize=9,
            color=color,
            path_effects=effects,
        )


def _draw_header_on_ax(ax, name, date_line, city, dark_mode, loc="upper left"):
    """
    Write a compact 3-line header near the top of the chart without covering the wheel.
    Uses a subtle stroke outline for readability instead of a background panel.
    loc: 'upper left' | 'top center' | 'upper right'
    """
    fg = "white" if dark_mode else "black"
    stroke = "black" if dark_mode else "white"
    effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]

    # anchor & alignment
    if loc == "upper right":
        x, ha = 0.98, "right"
    elif loc == "top center":
        x, ha = 0.50, "center"
    else:
        x, ha = 0.02, "left"  # upper left (default)

    # y just inside the axes so it doesn't sit on the frame
    y0 = 0.995
    line_h = 0.048  # vertical spacing between lines

    # Name (bold)
    ax.text(
        x,
        y0,
        name,
        transform=ax.transAxes,
        ha=ha,
        va="top",
        fontsize=11,
        fontweight="bold",
        color=fg,
        path_effects=effects,
        clip_on=False,
        zorder=10,
    )
    # Date/time
    if date_line:
        ax.text(
            x,
            y0 - line_h,
            date_line,
            transform=ax.transAxes,
            ha=ha,
            va="top",
            fontsize=9,
            color=fg,
            path_effects=effects,
            clip_on=False,
            zorder=10,
        )
    # City
    if city:
        ax.text(
            x,
            y0 - 2 * line_h,
            city,
            transform=ax.transAxes,
            ha=ha,
            va="top",
            fontsize=9,
            color=fg,
            path_effects=effects,
            clip_on=False,
            zorder=10,
        )


# --- CHART RENDERER (full)
def render_chart_with_shapes(
    pos,
    patterns,
    pattern_labels,
    toggles,
    filaments,
    combo_toggles,
    label_style,
    singleton_map,
    df,
    house_system,
    dark_mode,
    shapes,
    shape_toggles_by_parent,
    singleton_toggles,
    major_edges_all,
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
        mask = obj.str.contains(
            r"\b(house\s*\d{1,2}|\d{1,2}\s*h)\s*cusp\b",
            case=False,
            regex=True,
            na=False,
        )
        mask |= obj.str.match(r"^\s*\d{1,2}\s*H\s*Cusp\s*$", case=False, na=False)
        c = df[mask].copy()
        if c.empty:
            return None  # no cusp rows at all
        if "House System" in c.columns and c["House System"].notna().any():
            return (
                c["House System"].astype("string").str.strip().str.lower().mode().iat[0]
            )
        # if not tagged, assume whatever was last selected
        return st.session_state.get("last_house_system")

    # 1) see what system is actually in the DF (if any)
    _df_sys = _df_house_system(df)

    # 2) if mismatch or missing cusps, recompute once with the selected system
    if (_df_sys != house_system) or (_df_sys is None):
        lat0 = st.session_state.get("calc_lat")
        lon0 = st.session_state.get("calc_lon")
        tz0 = st.session_state.get("calc_tz")
        if None not in (lat0, lon0, tz0):
            run_chart(lat0, lon0, tz0, house_system)
            df = st.session_state.df  # use the freshly computed DF
            st.session_state["last_house_system"] = house_system
        else:
            st.warning(
                "No cached location for recompute; enter a city or load a profile, then toggle again."
            )

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
        frozenset((u, v)) for s in active_shapes for (u, v), asp in s["edges"]
    }

    # parents first (major edges)
    for idx in active_parents:
        if idx < len(patterns):
            visible_objects.update(patterns[idx])
            if active_parents:
                # draw only edges inside active patterns, using master edge list
                draw_aspect_lines(
                    ax,
                    pos,
                    patterns,
                    active_patterns=active_parents,
                    asc_deg=asc_deg,
                    group_colors=GROUP_COLORS,
                    edges=major_edges_all,
                )

                # optional: internal minors + filaments
                for idx in active_parents:
                    _ = internal_minor_edges_for_pattern(pos, list(patterns[idx]))
                    for p1, p2, asp_name, pat1, pat2 in filaments:
                        if frozenset((p1, p2)) in shape_edges:
                            continue

                        in_parent1 = any(
                            (i in active_parents) and (p1 in patterns[i])
                            for i in active_parents
                        )
                        in_parent2 = any(
                            (i in active_parents) and (p2 in patterns[i])
                            for i in active_parents
                        )
                        in_shape1 = any(p1 in s["members"] for s in active_shapes)
                        in_shape2 = any(p2 in s["members"] for s in active_shapes)
                        in_singleton1 = p1 in active_singletons
                        in_singleton2 = p2 in active_singletons

                        if (in_parent1 or in_shape1 or in_singleton1) and (
                            in_parent2 or in_shape2 or in_singleton2
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
            ax,
            pos,
            s["edges"],
            asc_deg,
            use_aspect_colors=False,
            override_color=st.session_state.shape_color_map[s["id"]],
        )

    # singletons (always mark them visible if toggled)
    visible_objects.update(active_singletons)

    # draw singleton dots (twice as wide as aspect lines)
    if active_singletons:
        draw_singleton_dots(
            ax, pos, active_singletons, shape_edges, asc_deg, line_width=2.0
        )

    # connectors (filaments) not already claimed by shapes
    for p1, p2, asp_name, pat1, pat2 in filaments:
        if frozenset((p1, p2)) in shape_edges:
            continue
        in_parent1 = any(
            (i in active_parents) and (p1 in patterns[i]) for i in active_parents
        )
        in_parent2 = any(
            (i in active_parents) and (p2 in patterns[i]) for i in active_parents
        )
        in_shape1 = any(p1 in s["members"] for s in active_shapes)
        in_shape2 = any(p2 in s["members"] for s in active_shapes)
        in_singleton1 = p1 in active_singletons
        in_singleton2 = p2 in active_singletons
        if (in_parent1 or in_shape1 or in_singleton1) and (
            in_parent2 or in_shape2 or in_singleton2
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

    return fig, visible_objects, active_shapes, cusps


import pytz
from geopy.geocoders import OpenCage
from timezonefinder import TimezoneFinder

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def _coerce_int(v, default=None):
    try:
        if v is None:
            return default
        return int(v)
    except Exception:
        return default


def _month_to_index(m):
    # Accept int 1-12, or month name like "July"
    if m is None:
        return None
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
    if (
        isinstance(prof, dict)
        and "payload" in prof
        and isinstance(prof["payload"], dict)
    ):
        prof = prof["payload"]

    # Gather possible sources
    year = prof.get("year", prof.get("profile_year"))
    month = prof.get(
        "month",
        prof.get(
            "profile_month", prof.get("month_name", prof.get("profile_month_name"))
        ),
    )
    day = prof.get("day", prof.get("profile_day"))
    hour = prof.get("hour", prof.get("profile_hour"))
    minute = prof.get("minute", prof.get("profile_minute"))
    city = prof.get("city", prof.get("profile_city"))

    # Fallbacks from session (so we don't explode)
    year = _coerce_int(year, st.session_state.get("profile_year", 1990))
    day = _coerce_int(day, st.session_state.get("profile_day", 1))
    hour = _coerce_int(hour, st.session_state.get("profile_hour", 0))
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

    lat = prof.get("lat")
    lon = prof.get("lon")
    tzname = prof.get("tz_name")

    # Optional circuit names
    circuit_names = prof.get("circuit_names", {})

    return {
        "year": year,
        "month": m_idx,  # 1..12
        "day": day,
        "hour": hour,  # 0..23
        "minute": minute,  # 0..59
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
    "profile_hour": 12,  # 24h format
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
            st.session_state[key] = val
        st.session_state["saved_circuit_names"] = prof["circuit_names"].copy()
    else:
        st.session_state["saved_circuit_names"] = {}


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
            0.0,
            lat,
            lon,
            input_is_ut=False,
            tz_name=tz_name,
            house_system=house_system,  # <<< use the param, not _selected_house_system()
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
        st.session_state["calc_tz"] = tz_name

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
                "Year", min_value=1000, max_value=3000, step=1, key="year"
            )

            # Month widget
            import calendar

            month_name = st.selectbox("Month", MONTH_NAMES, key="month_name")
            month = MONTH_NAMES.index(month_name) + 1
            days_in_month = calendar.monthrange(year, month)[1]

        # Time widgets
        time_cols = st.columns(3)
        with time_cols[0]:
            hour_12 = st.selectbox("Birth Time", list(range(1, 13)), key="hour_12")
        with time_cols[1]:
            minute_str = st.selectbox(
                " ", [f"{m:02d}" for m in range(60)], key="minute_str"
            )
        with time_cols[2]:
            ampm = st.selectbox(" ", ["AM", "PM"], key="ampm")

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
                key="city",  # you can just reuse profile_city as the widget key
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
                        st.session_state["last_timezone"] = (
                            "City not found. Try a more specific query."
                        )
                except Exception as e:
                    st.session_state["last_location"] = None
                    st.session_state["last_timezone"] = f"Lookup error: {e}"
            # Day widget
            day = st.selectbox("Day", list(range(1, days_in_month + 1)), key="day")

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
                    filaments, singleton_map = detect_minor_links_with_singletons(
                        pos, patterns
                    )
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
        st.session_state["active_profile_tab"] = "Add / Update Profile"

st.caption("(Synastry and Transit readings coming soon-ish)")

# -------------------------
# Right column: Profile Manager
# -------------------------
with col_right:
    saved_profiles = load_user_profiles_db(current_user_id)

    if "current_profile" not in st.session_state:
        st.session_state["current_profile"] = None
    if "active_profile_tab" not in st.session_state:
        st.session_state["active_profile_tab"] = "Load Profile"

    st.subheader("👤 Chart Profile Manager")

    # Admin gating
    admin_flag = is_admin(current_user_id)

    if admin_flag:
        tab_labels = ["Add / Update Profile", "Load Profile", "Delete Profile"]
    else:
        tab_labels = ["Load Profile", "Delete Profile"]

    # Pick default index safely
    default_tab = st.session_state["active_profile_tab"]
    if default_tab not in tab_labels:
        default_tab = tab_labels[0]

    active_tab = st.radio(
        "Profile Manager Tabs",
        tab_labels,
        index=tab_labels.index(default_tab),
        horizontal=True,
        key="profile_tab_selector",
    )
    st.session_state["active_profile_tab"] = active_tab

    # --- Add / Update ---
    if active_tab == "Add / Update Profile":
        if not admin_flag:
            st.warning("Only admins can create or update profiles during beta.")
            st.stop()

        profile_name = st.text_input(
            "Profile Name (unique)", value="", key="profile_name_input"
        )

        if st.button("💾 Save / Update Profile"):
            if profile_name.strip() == "":
                st.error("Please enter a name for the profile.")
            else:
                # If updating existing profile, keep current circuit names
                if profile_name in saved_profiles and "patterns" in st.session_state:
                    circuit_names = {
                        f"circuit_name_{i}": st.session_state.get(
                            f"circuit_name_{i}", f"Circuit {i+1}"
                        )
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
                if not (
                    isinstance(lat, (int, float))
                    and isinstance(lon, (int, float))
                    and tz_name
                ):
                    st.error(
                        "Please enter a valid city (lat/lon/timezone lookup must succeed) before saving the profile."
                    )
                    st.stop()

                # Optional: sanity-check timezone string
                import pytz

                if tz_name not in pytz.all_timezones:
                    st.error(
                        f"Unrecognized timezone '{tz_name}'. Please refine the city and try again."
                    )
                    st.stop()

                profile_data = {
                    "year": int(st.session_state.get("profile_year", 1990)),
                    "month": int(
                        MONTH_NAMES.index(
                            st.session_state.get("profile_month_name", "July")
                        )
                        + 1
                    ),
                    "day": int(st.session_state.get("profile_day", 1)),
                    "hour": int(st.session_state.get("profile_hour", 0)),
                    "minute": int(st.session_state.get("profile_minute", 0)),
                    "city": st.session_state.get("profile_city", ""),
                    "lat": lat,
                    "lon": lon,
                    "tz_name": tz_name,
                    "circuit_names": circuit_names,
                }

                # Save to DB for this logged-in user
                save_user_profile_db(current_user_id, profile_name, profile_data)
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
                            st.session_state["profile_month_name"] = MONTH_NAMES[
                                data["month"] - 1
                            ]
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
                                st.session_state["saved_circuit_names"] = data[
                                    "circuit_names"
                                ].copy()
                            else:
                                st.session_state["saved_circuit_names"] = {}

                            # Guard run_chart()
                            if any(
                                v is None
                                for v in (
                                    data.get("lat"),
                                    data.get("lon"),
                                    data.get("tz_name"),
                                )
                            ):
                                st.error(
                                    f"Profile '{name}' is missing location/timezone info. Re-save it after a successful city lookup."
                                )
                            else:
                                run_chart(
                                    data["lat"],
                                    data["lon"],
                                    data["tz_name"],
                                    _selected_house_system(),
                                )
                                st.success(
                                    f"Profile '{name}' loaded and chart calculated!"
                                )
                                st.rerun()
        else:
            st.info("No saved profiles yet.")

    # --- Delete (private, per-user) ---
    elif active_tab == "Delete Profile":
        saved_profiles = load_user_profiles_db(current_user_id)
        if saved_profiles:
            delete_choice = st.selectbox(
                "Select a profile to delete",
                options=sorted(saved_profiles.keys()),
                key="profile_delete",
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
                    if st.button(
                        "Delete", key="priv_delete_yes", use_container_width=True
                    ):
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
                if not (
                    isinstance(lat, (int, float))
                    and isinstance(lon, (int, float))
                    and tz_name
                ):
                    st.error(
                        "Enter a valid city (lat/lon/timezone lookup must succeed) before donating."
                    )
                    valid = False
                else:
                    import pytz

                    if tz_name not in pytz.all_timezones:
                        st.error(
                            f"Unrecognized timezone '{tz_name}'. Refine the city and try again."
                        )
                        valid = False
                if not comm_name.strip():
                    st.error("Please provide a label for the donated chart.")
                    valid = False

                if valid:
                    circuit_names = {
                        f"circuit_name_{i}": st.session_state.get(
                            f"circuit_name_{i}", f"Circuit {i+1}"
                        )
                        for i in range(len(st.session_state.get("patterns", [])))
                    }
                    payload = {
                        "year": int(st.session_state.get("profile_year", 1990)),
                        "month": int(
                            MONTH_NAMES.index(
                                st.session_state.get("profile_month_name", "July")
                            )
                            + 1
                        ),
                        "day": int(st.session_state.get("profile_day", 1)),
                        "hour": int(st.session_state.get("profile_hour", 0)),
                        "minute": int(st.session_state.get("profile_minute", 0)),
                        "city": st.session_state.get("profile_city", ""),
                        "lat": lat,
                        "lon": lon,
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

            confirm_text_publish = "✨Do you want to donate your chart to Science?💫"
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
                if st.button(
                    "Donate", key="comm_confirm_yes", use_container_width=True
                ):
                    payload = st.session_state.get("comm_confirm_payload")
                    name_to_publish = st.session_state.get("comm_confirm_name", "")
                    if payload:
                        pid = community_save(
                            name_to_publish, payload, submitted_by=current_user_id
                        )
                        st.success(f"Thank you! Donated as “{name_to_publish}”.")
                    else:
                        st.info(
                            "This was an info-only view. Click “Donate current chart” first."
                        )
                    for k in (
                        "comm_confirm_open",
                        "comm_confirm_mode",
                        "comm_confirm_name",
                        "comm_confirm_payload",
                    ):
                        st.session_state.pop(k, None)
                    st.rerun()

            with c_no:
                if st.button("Cancel", key="comm_confirm_no", use_container_width=True):
                    for k in (
                        "comm_confirm_open",
                        "comm_confirm_mode",
                        "comm_confirm_name",
                        "comm_confirm_payload",
                    ):
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
                            load_clicked = st.button(
                                "Load",
                                key=f"comm_load_{r['id']}",
                                use_container_width=True,
                            )

                        ask = cancel = really = False
                        with b2:
                            if confirm_id == r["id"]:
                                st.warning("Delete this donated chart?")
                            else:
                                ask = st.button(
                                    "Delete",
                                    key=f"comm_delete_{r['id']}",
                                    use_container_width=True,
                                )

                        # Confirm row
                        if confirm_id == r["id"]:
                            cdel1, cdel2 = st.columns([1, 1], gap="small")
                            with cdel1:
                                really = st.button(
                                    "Delete",
                                    key=f"comm_delete_yes_{r['id']}",
                                    use_container_width=True,
                                )
                            with cdel2:
                                cancel = st.button(
                                    "No!",
                                    key=f"comm_delete_no_{r['id']}",
                                    use_container_width=True,
                                )

                    # --- handle clicks ---
                    if load_clicked:
                        data = r["payload"]
                        st.session_state["_loaded_profile"] = data
                        st.session_state["current_profile"] = f"community:{r['id']}"
                        st.session_state["profile_loaded"] = True
                        st.session_state["profile_year"] = data["year"]
                        st.session_state["profile_month_name"] = MONTH_NAMES[
                            data["month"] - 1
                        ]
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
                            st.session_state["saved_circuit_names"] = data[
                                "circuit_names"
                            ].copy()
                        else:
                            st.session_state["saved_circuit_names"] = {}

                        if any(
                            v is None
                            for v in (
                                data.get("lat"),
                                data.get("lon"),
                                data.get("tz_name"),
                            )
                        ):
                            st.error(
                                "This donated profile is missing location/timezone info."
                            )
                        else:
                            run_chart(
                                data["lat"],
                                data["lon"],
                                data["tz_name"],
                                _selected_house_system(),
                            )
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
    day = st.session_state.get("profile_day", "")
    year = st.session_state.get("profile_year", "")
    hour = st.session_state.get("profile_hour", None)
    minute = st.session_state.get("profile_minute", None)
    city = st.session_state.get("profile_city", "")

    # Format time to 12-hour
    time_str = ""
    if hour is not None and minute is not None:
        h = int(hour)
        m = int(minute)
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
        st.caption(
            "One Circuit = aspects color-coded. Multiple Circuits = each circuit color-coded. "
            "Expand circuits for sub-shapes. View planet profiles on the left sidebar (» on mobile). "
            "Below the chart, copy the prompt into your GPT for an aspect interpretation."
        )

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

            expander_label = (
                f"{st.session_state[circuit_name_key]}: {', '.join(component)}"
            )

            with target_col:
                cbox = st.checkbox("", key=checkbox_key)
                toggles.append(cbox)
                pattern_labels.append(expander_label)

                with st.expander(expander_label, expanded=False):
                    # Editable name inside expander
                    st.text_input(f"Rename {default_label}", key=circuit_name_key)

                    # --- Auto-save when circuit name changes ---
                    if st.session_state.get("current_profile"):
                        saved = st.session_state.get("saved_circuit_names", {})
                        current_name = st.session_state[circuit_name_key]
                        last_saved = saved.get(circuit_name_key, default_label)

                        if current_name != last_saved:
                            # Build updated set of circuit names
                            current = {
                                f"circuit_name_{j}": st.session_state.get(
                                    f"circuit_name_{j}", f"Circuit {j+1}"
                                )
                                for j in range(len(patterns))
                            }
                            profile_name = st.session_state["current_profile"]
                            payload = saved_profiles.get(profile_name, {}).copy()
                            payload["circuit_names"] = current
                            save_user_profile_db(current_user_id, profile_name, payload)
                            # refresh cache
                            saved_profiles = load_user_profiles_db(current_user_id)
                            st.session_state["saved_circuit_names"] = current.copy()

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
                f"circuit_name_{i}": st.session_state.get(
                    f"circuit_name_{i}", f"Circuit {i+1}"
                )
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
        st.subheader("Single Placements")
        singleton_toggles = {}
        if singleton_map:
            cols_per_row = min(8, max(1, len(singleton_map)))
            cols = st.columns(cols_per_row)
            for j, (planet, _) in enumerate(singleton_map.items()):
                with cols[j % cols_per_row]:
                    key = f"singleton_{planet}"
                    if key not in st.session_state:
                        on = st.checkbox(
                            GLYPHS.get(planet, planet), value=False, key=key
                        )
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
                    st.error(
                        "Location data not available. Please recalculate the chart first."
                    )

            # 🚧 placeholder group 1 (does nothing)
            st.radio(
                "(Coming soon)",
                ["Campanus", "Koch", "Regiomontanus"],
                index=0,
                key="house_system_placeholder_a",
                disabled=True,
            )
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
                "Label Style", ["Text", "Glyph"], index=1, horizontal=True
            )

            dark_mode = st.checkbox("🌙 Dark Mode", value=False)

            # 🚧 placeholder group 1 (does nothing)
            st.radio(
                "(Coming soon)",
                ["Porphyry", "Topocentric", "Alcabitius"],
                index=0,
                key="house_system_placeholder_b",
                disabled=True,
            )

            if st.button("Hide All"):
                for i in range(len(patterns)):
                    st.session_state[f"toggle_pattern_{i}"] = False
                    for sh in [sh for sh in shapes if sh["parent"] == i]:
                        st.session_state[f"shape_{i}_{sh['id']}"] = False
                for planet in singleton_map.keys():
                    st.session_state[f"singleton_{planet}"] = False

    shape_toggles_by_parent = st.session_state.get("shape_toggles_by_parent", {})
    if not singleton_toggles:
        singleton_toggles = {
            p: st.session_state.get(f"singleton_{p}", False) for p in singleton_map
        }

    # --- Render the chart ---
    fig, visible_objects, active_shapes, cusps = render_chart_with_shapes(
        pos,
        patterns,
        pattern_labels=[],
        toggles=[
            st.session_state.get(f"toggle_pattern_{i}", False)
            for i in range(len(patterns))
        ],
        filaments=filaments,
        combo_toggles=combos,
        label_style=label_style,
        singleton_map=singleton_map,
        df=df,
        house_system=house_system,
        dark_mode=dark_mode,
        shapes=shapes,
        shape_toggles_by_parent=shape_toggles_by_parent,
        singleton_toggles=singleton_toggles,
        major_edges_all=major_edges_all,
    )

    st.pyplot(fig, use_container_width=False)

    def _sign_from_degree(deg):
        # 0=Aries ... 11=Pisces
        idx = int((deg % 360) // 30)
        return ZODIAC_SIGNS[idx]

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
        return {
            i + 1: _sign_from_degree(cusps_list[i])
            for i in range(min(12, len(cusps_list)))
        }

    # --- Sidebar planet profiles ---
    st.sidebar.subheader("🪐 Planet Profiles in View")

    cusps_list = cusps

    # Apply conjunction clustering to determine display order
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(
        pos, list(visible_objects)
    )

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

    # Ensure Sign is set for each visible object
    for obj, row in enhanced_objects_data.items():
        # Prefer existing 'Sign' if present; otherwise derive from degree
        if "Sign" not in row or not row["Sign"]:
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

    def _build_rulership_html(
        obj_name, row, enhanced_objects_data, ordered_objects, cusp_signs
    ):
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
        sign_line = sign_chain or f"{obj_name}"  # minimal fallback

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
        rulership_html = _build_rulership_html(
            obj, row, enhanced_objects_data, ordered_objects, cusp_signs
        )
        st.sidebar.markdown(profile + rulership_html, unsafe_allow_html=True)
        st.sidebar.markdown("---")

    # --- Aspect Interpretation Prompt ---
    with st.expander("Aspect Interpretation Prompt"):
        st.caption(
            "Paste this prompt into an LLM (like ChatGPT). Start with studying one subshape at a time, then add connections as you learn them."
        )
        st.caption(
            "Curently, all interpretation prompts are for natal charts. Event interpretation prompts coming soon."
        )

        aspect_blocks = []
        aspect_definitions = set()

        # Add conjunction aspects from clusters first
        rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(
            pos, list(visible_objects)
        )

        for rep, cluster in rep_map.items():
            if len(cluster) >= 2:  # Only clusters with 2+ members have conjunctions
                # Generate all pairwise conjunctions within the cluster
                cluster_lines = []
                for i in range(len(cluster)):
                    for j in range(i + 1, len(cluster)):
                        p1, p2 = cluster[i], cluster[j]
                        cluster_lines.append(f"{p1} Conjunction {p2}")
                        aspect_definitions.add(
                            "Conjunction: "
                            + ASPECT_INTERPRETATIONS.get("Conjunction", "Conjunction")
                        )

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

        def strip_html_tags(text):
            # Replace divs and <br> with spaces
            text = re.sub(r"</div>|<br\s*/?>", " ", text)
            text = re.sub(r"<div[^>]*>", "", text)
            # Remove any other HTML tags
            text = re.sub(r"<[^>]+>", "", text)
            # Collapse multiple spaces
            text = re.sub(r"\s+", " ", text)
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
                if planet_profiles_texts
                else ""
            )

            rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(
                pos, list(visible_objects)
            )

            # rep_map is {representative: [cluster_members...]}
            _conj_clusters = list(rep_map.values())

            # Conjunction clusters trigger the special note.
            num_conj_clusters = sum(1 for c in _conj_clusters if len(c) >= 2)

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
                interpretation_notes.append(
                    f"- House System ({_HS_LABEL.get(house_system, house_system.title())}): {house_system_meaning}"
                )

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
            interpretation_notes_block = (
                "\n\n".join(interpretation_notes) if interpretation_notes else ""
            )

            # --- Final prompt assembly ---
            import textwrap

            instructions = textwrap.dedent(
                """
            Synthesize accurate poetic interpretations for each of these astrological aspects, using only the precise method outlined. Do not default to traditional astrology. For each planet or placement profile or conjunction cluster provided, use all information provided to synthesize a personified planet "character" profile in one paragraph. Use only the interpretation instructions provided for each item. List these one-paragraph character profiles first in your output, under a heading called "Character Profiles."

            Then, synthesize each aspect, using the two character profiles of the endpoints and the aspect interpretation provided below (not traditional astrology definitions) to personify the "relationship dynamics" between each combination (aspect) of two characters. Each aspect synthesis should be a paragraph. List those paragraphs below the Character Profiles, under a header called "Aspects."

            Lastly, synthesize all of the aspects together: Zoom out and use your thinking brain to see how these interplanetary relationship dynamics become a functioning system with a function when combined into the whole shape provided, and ask yourself "what does the whole thing do when you put it together?" Describe the function, and suggest a name for the circuit. Output this synthesis under a header called "Circuit."
            """
            ).strip()

            sections = [
                instructions,
                (
                    interpretation_notes_block.strip()
                    if interpretation_notes_block
                    else ""
                ),
                planet_profiles_block.strip() if planet_profiles_block else "",
                (
                    ("Aspects\n\n" + "\n\n".join(aspect_blocks)).strip()
                    if aspect_blocks
                    else ""
                ),
                (
                    "\n\n".join(sorted(aspect_definitions)).strip()
                    if aspect_definitions
                    else ""
                ),
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
            st.markdown(
                "_(Select at least 1 sub-shape from a drop-down to view prompt.)_"
            )
