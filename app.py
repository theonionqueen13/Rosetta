# app.py
"""
NiceGUI entry point for Rosetta.

Runs alongside the Streamlit entry (test_calc_v2.py) — both coexist in the
repo but never run in the same process.

Usage:
    python app.py          # local dev  (port 8080)
    PORT=8080 python app.py  # Railway / Docker

Routes:
    /        — main application page (requires auth)
    /login   — email/password sign-in and sign-up
    /health  — JSON health-check for Railway
"""
from __future__ import annotations

import base64
import calendar
import datetime as _dt
import functools
import io
import json
import os
import time
import logging
from typing import Optional

from dateutil.relativedelta import relativedelta

from fastapi.responses import JSONResponse
from nicegui import app, run, ui

from config import get_secret
from supabase_client import get_supabase
from src.nicegui_state import ensure_state, get_chart_object, get_chart_2_object

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-session chat data (non-JSON-serializable objects keyed by user_id)
# ---------------------------------------------------------------------------
_CHAT_MEMORY: dict = {}     # uid -> AgentMemory
_CHAT_DEV_TRACE: dict = {}  # uid -> dict (last dev trace)
_CHAT_PERSONS: dict = {}    # uid -> list[dict]  (known persons)
_CHAT_LOCATIONS: dict = {}  # uid -> list[dict]  (known locations)


def _merge_chat_persons(uid: str, new_persons) -> None:
    """Merge new person dicts into per-session known persons."""
    existing = _CHAT_PERSONS.setdefault(uid, [])
    names = {p.get("name", "").lower() for p in existing}
    self_names = {
        p.get("name", "").lower()
        for p in existing
        if p.get("relationship_to_querent") == "self"
    }
    for p in new_persons:
        d = p if isinstance(p, dict) else (p.to_dict() if hasattr(p, "to_dict") else {})
        key = (d.get("name") or "").lower()
        if not key or key in names or key in self_names:
            continue
        existing.append(d)
        names.add(key)


def _merge_chat_locations(uid: str, new_locations) -> None:
    """Merge new location dicts into per-session known locations."""
    existing = _CHAT_LOCATIONS.setdefault(uid, [])
    names = {loc.get("name", "").lower() for loc in existing}
    for loc in new_locations:
        d = loc if isinstance(loc, dict) else (loc.to_dict() if hasattr(loc, "to_dict") else {})
        key = (d.get("name") or "").lower()
        if key and key not in names:
            existing.append(d)
            names.add(key)


# ---------------------------------------------------------------------------
# Month list (mirrors src/test_data.py MONTH_NAMES)
# ---------------------------------------------------------------------------
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# ---------------------------------------------------------------------------
# Storage secret (for app.storage.user — encrypted browser-side cookie)
# ---------------------------------------------------------------------------
_STORAGE_SECRET = os.environ.get("NICEGUI_STORAGE_SECRET", "rosetta-dev-secret-change-me")

# ---------------------------------------------------------------------------
# Health-check endpoint (for Railway / container orchestration)
# ---------------------------------------------------------------------------

@app.get("/health")
async def _health():
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Auth helpers  (NiceGUI equivalents of auth_ui.py helpers)
# ---------------------------------------------------------------------------

def _store_session_nicegui(auth_response) -> str:
    """Persist Supabase session into app.storage.user. Returns user_id."""
    session = auth_response.session
    user = auth_response.user
    app.storage.user["supabase_session"] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,  # Unix timestamp
    }
    app.storage.user["supabase_user_id"] = str(user.id)
    app.storage.user["supabase_user_email"] = user.email
    return str(user.id)


def _clear_session():
    """Wipe auth state and sign out from Supabase."""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in ("supabase_session", "supabase_user_id", "supabase_user_email"):
        app.storage.user.pop(key, None)


def _get_user_id() -> Optional[str]:
    """Return the current user_id from storage, or None if not authenticated."""
    return app.storage.user.get("supabase_user_id")


def _session_is_expired() -> bool:
    """Check whether the stored access token has expired."""
    session = app.storage.user.get("supabase_session")
    if not session:
        return True
    expires_at = session.get("expires_at")
    if not expires_at:
        return True
    # Treat as expired if within 60 seconds of expiry
    return time.time() >= (expires_at - 60)


def _try_refresh_session() -> bool:
    """Attempt to refresh the Supabase session using the stored refresh token.

    Returns True if the session was refreshed successfully, False otherwise.
    """
    session = app.storage.user.get("supabase_session")
    if not session or not session.get("refresh_token"):
        return False
    try:
        resp = get_supabase().auth.refresh_session(session["refresh_token"])
        if resp and resp.session:
            _store_session_nicegui(resp)
            return True
    except Exception as exc:
        _log.warning("Session refresh failed: %s", exc)
    return False


# ---------------------------------------------------------------------------
# /login page
# ---------------------------------------------------------------------------

@ui.page("/login")
def login_page():
    # If already authenticated, go straight to main page
    if _get_user_id() and not _session_is_expired():
        ui.navigate.to("/")
        return

    ui.add_head_html("""
<style>
:root {
    --rosetta-tan: #867557; /* Change this value to your exact tan shade */
}
body, .q-layout, .q-page-container, .q-page {
    background: black !important;
    padding: 0 !important;
    margin: 0 !important;
    min-height: 100vh !important;
}
.q-page {
    display: flex !important;
    flex-direction: row !important;
    align-items: stretch !important;
}
.login-tan {
    color: var(--rosetta-tan) !important;
}
.login-input .q-field__control {
    background: #1f1b14 !important;
    color: var(--rosetta-tan) !important;
}
.login-input .q-field__input {
    color: var(--rosetta-tan) !important;
}
.login-input .q-field__native {
    background: #1f1b14 !important;
    color: var(--rosetta-tan) !important;
}
.login-card {
    background: rgba(30, 26, 19, 0.95) !important;
    border: 1px solid #3e3524 !important;
}
.login-divider {
    background-color: var(--rosetta-tan) !important;
}
.login-tab-panel {
    background: rgba(237, 224, 196, 0.45) !important;
    border-radius: 8px;
    padding: 0.9rem !important;
}
.login-input .q-field__control {
    background: rgba(237, 224, 196, 0.42) !important;
    color: var(--rosetta-tan) !important;
}
.login-input .q-field__append .q-icon,
.login-input .q-field__append .q-btn {
    background: var(--rosetta-tan) !important;
    color: #2e1e0f !important;
    border-radius: 2px !important;
}
.q-btn.rosetta-button {
    background: #41301c !important;
    background-color: #41301c !important;
    color: #ffffff !important;
}
.q-btn.rosetta-button .q-btn__wrapper {
    background: #41301c !important;
    color: #ffffff !important;
}
.q-btn.rosetta-button:hover,
.q-btn.rosetta-button:focus {
    background: #5a3f25 !important;
    background-color: #5a3f25 !important;
}
    .login-tab .q-tab__label,
.login-tab .q-tab--active .q-tab__label {
    color: var(--rosetta-tan) !important;
}
</style>
""")

    with ui.row().style("width: 100vw; min-height: 100vh; background: black; margin: 0; padding: 0; flex-wrap: nowrap;"):
        with ui.column().classes("items-center justify-center").style(
            "flex: 1; background: black; padding: 0; height: 100vh; overflow: hidden;"
        ):
            ui.label().classes("q-pa-none q-ma-none").style(
                "width: 100%; height: 100%; background-image: url('/pngs/rosetta_vert.png'); background-repeat: no-repeat; background-position: center center; background-size: contain;"
            )

        with ui.column().classes("items-center justify-center").style("flex: 1; background: black; padding: 2rem;"):
            with ui.card().classes("q-pa-xl login-card").style("width: 360px;"):
                with ui.column().classes("items-center gap-4"):
                    ui.label().style(
                        "width: 260px; height: 72px; background-image: url('/pngs/rosetta_banner.png');"
                        " background-repeat: no-repeat; background-position: center center; background-size: contain;"
                    )
                    ui.label("Please sign in to continue.").classes("text-subtitle1 login-tan")
                    ui.separator().classes("login-divider")

                # --- Tabs: Sign In / Create Account ---
                with ui.tabs().classes("w-full login-tab") as tabs:
                    tab_signin = ui.tab("Sign In").classes("login-tan")
                    tab_signup = ui.tab("Create Account").classes("login-tan")

                # Shared state for form inputs
                signin_email = {"value": ""}
                signin_password = {"value": ""}
                signup_email = {"value": ""}
                signup_password = {"value": ""}

                # Status message container
                status_container = ui.column().classes("w-full")

                def _show_error(msg: str):
                    status_container.clear()
                    with status_container:
                        ui.label(msg).classes("text-negative text-body2")

                def _show_success(msg: str):
                    status_container.clear()
                    with status_container:
                        ui.label(msg).classes("text-positive text-body2")

                def _clear_status():
                    status_container.clear()

                # --- Sign In ---
                async def _do_sign_in():
                    _clear_status()
                    email = signin_email["value"].strip()
                    password = signin_password["value"]
                    if not email or not password:
                        _show_error("Please enter your email and password.")
                        return
                    try:
                        resp = get_supabase().auth.sign_in_with_password(
                            {"email": email, "password": password}
                        )
                        _store_session_nicegui(resp)
                        ui.navigate.to("/")
                    except Exception as e:
                        _show_error(f"Sign in failed: {e}")

                # --- Sign Up ---
                async def _do_sign_up():
                    _clear_status()
                    email = signup_email["value"].strip()
                    password = signup_password["value"]
                    if not email or not password:
                        _show_error("Please fill in both fields.")
                        return
                    if len(password) < 6:
                        _show_error("Password must be at least 6 characters.")
                        return
                    try:
                        resp = get_supabase().auth.sign_up(
                            {"email": email, "password": password}
                        )
                        if resp.user:
                            _show_success(
                                "Account created! Check your email to confirm, then sign in."
                            )
                        else:
                            _show_error("Sign up failed — please try again.")
                    except Exception as e:
                        _show_error(f"Sign up failed: {e}")

                # --- Tab panels ---
                with ui.tab_panels(tabs, value=tab_signin).classes("w-full login-tab-panels"):
                    with ui.tab_panel(tab_signin).classes("login-tab-panel"):
                        ui.label("Sign in with email & password").classes("text-subtitle2 q-mb-sm login-tan")
                        email_in = ui.input("Email").classes("w-full login-input").on(
                            "update:model-value", lambda e: signin_email.update(value=e.args)
                        )
                        pass_in = ui.input("Password", password=True, password_toggle_button=True).classes("w-full login-input").on(
                            "update:model-value", lambda e: signin_password.update(value=e.args)
                        )
                        pass_in.on("keydown.enter", _do_sign_in)
                        ui.button("Sign In", on_click=_do_sign_in).classes("w-full q-mt-md rosetta-button")

                    with ui.tab_panel(tab_signup).classes("login-tab-panel"):
                        ui.label("Create a new account").classes("text-subtitle2 q-mb-sm login-tan")
                        ui.input("Email").classes("w-full login-input").on(
                            "update:model-value", lambda e: signup_email.update(value=e.args)
                        )
                        pw_input = ui.input("Password (min 6 chars)", password=True, password_toggle_button=True).classes("w-full login-input").on(
                            "update:model-value", lambda e: signup_password.update(value=e.args)
                        )
                        pw_input.on("keydown.enter", _do_sign_up)
                        ui.button("Create Account", on_click=_do_sign_up).classes("w-full q-mt-md rosetta-button")


# ---------------------------------------------------------------------------
# / main page  (auth-guarded)
# ---------------------------------------------------------------------------

# ---------- TOGGLE_ASPECTS names (NiceGUI only needs the names, not SWE ids) -
TOGGLE_ASPECT_NAMES = [
    "North Node", "South Node", "AC", "MC", "Vertex", "Part of Fortune",
    "Ceres", "Pallas", "Juno", "Vesta", "Eris", "Eros", "Psyche",
]

# ---------- Planet profile CSS (matches Streamlit sidebar styling) -----------
_PROFILE_CSS = """
<style>
.pf-root { font-size: 0.92em; line-height: 1.45; }
.pf-block { margin-bottom: 0.7em; }
.pf-block hr.pf-divider { border:none; border-top: 1px solid #ddd; margin-top:0.5em; }
.pf-title { font-size: 1.05em; margin-bottom: 2px; }
.pf-meaning { color: #888; font-size: 0.88em; margin-bottom: 4px; }
.planet-profile-card { scroll-margin-top: 8px; }
</style>
"""

@ui.page("/")
def main_page():
    # --- Auth guard ---
    user_id = _get_user_id()
    if not user_id:
        ui.navigate.to("/login")
        return

    # --- Session refresh ---
    if _session_is_expired():
        if not _try_refresh_session():
            _clear_session()
            ui.navigate.to("/login")
            return

    email = app.storage.user.get("supabase_user_email", "")
    state = ensure_state()

    # --- Background images (light: nebula2.jpg, dark: galaxies.jpg) ---
    # Quasar adds body.body--dark when dark mode is enabled, so we use that
    # selector to swap the background automatically — no extra JS needed.
    ui.add_head_html("""
<style>
body {
    background-image:
        linear-gradient(rgba(0,0,0,0.20), rgba(0,0,0,0.20)),
        url('/pngs/nebula2.jpg');
    background-size: cover;
    background-position: center center;
    background-repeat: no-repeat;
    background-attachment: fixed;
}
body.body--dark {
    background-image:
        linear-gradient(rgba(0,0,0,0.45), rgba(0,0,0,0.45)),
        url('/pngs/galaxies.jpg');
}
/* Let Quasar layout be transparent so the background shows through */
.q-layout,
.q-page-container,
.q-page {
    background: transparent !important;
}
</style>
""")

    # --- Per-user form state (survives page refresh via app.storage.user) ---
    form = app.storage.user.setdefault("birth_form", {
        "name": "",
        "city": "",
        "year": 2000,
        "month_name": "January",
        "day": 1,
        "hour_12": "12",
        "minute_str": "00",
        "ampm": "AM",
        "unknown_time": False,
        "gender": None,
    })

    # ===================================================================
    # LEFT DRAWER — Planet Profiles
    # ===================================================================
    drawer = ui.left_drawer(value=False, bordered=True).classes("q-pa-md").style(
        "width: 380px"
    )
    with drawer:
        ui.label("🪐 Planet Profiles in View").classes("text-h6 q-mb-sm")
        profile_mode_radio = ui.radio(
            ["Stats", "Profile", "Full"],
            value=state.get("profile_view_mode", "Stats"),
        ).props("inline dense")
        ui.separator().classes("q-my-sm")
        drawer_content = ui.column().classes("w-full")

    def _refresh_drawer():
        """Re-render planet profile cards in the left drawer."""
        chart_obj = get_chart_object(state)
        if chart_obj is None:
            drawer_content.clear()
            with drawer_content:
                ui.label("No chart loaded.").classes("text-body2 text-grey")
            return

        mode = profile_mode_radio.value or "Stats"
        state["profile_view_mode"] = mode
        house_sys = state.get("house_system", "placidus").title()
        unknown_time = getattr(chart_obj, "unknown_time", False)

        try:
            from profiles_v2 import format_object_profile_html, ordered_objects
            from planet_profiles import (
                format_planet_profile_html,
                format_full_planet_profile_html,
            )

            ordered_rows = ordered_objects(chart_obj)
            if not ordered_rows:
                drawer_content.clear()
                with drawer_content:
                    ui.label("No objects to display.").classes("text-body2 text-grey")
                return

            blocks = []
            for row in ordered_rows:
                if mode == "Stats":
                    block = format_object_profile_html(
                        row, house_label=house_sys,
                        include_house_data=not unknown_time,
                    )
                elif mode == "Profile":
                    block = format_planet_profile_html(
                        row, chart_obj, ordered_rows, house_system=house_sys,
                    )
                else:
                    block = format_full_planet_profile_html(
                        row, chart_obj, ordered_rows,
                        house_system=house_sys,
                        include_house_data=not unknown_time,
                    )
                planet_name = (
                    row.object_name.name
                    if hasattr(row, "object_name") and row.object_name
                    else "unknown"
                )
                pid = f"rosetta-planet-{planet_name.replace(' ', '-').lower()}"
                blocks.append(f"<div id='{pid}' class='planet-profile-card'>{block}</div>")

            html = _PROFILE_CSS + "<div class='pf-root'>" + "\n".join(blocks) + "</div>"
            drawer_content.clear()
            with drawer_content:
                ui.html(html)
        except Exception as exc:
            _log.exception("Planet profiles render failed")
            drawer_content.clear()
            with drawer_content:
                ui.label(f"Error: {exc}").classes("text-body2 text-negative")

    profile_mode_radio.on_value_change(lambda _: _refresh_drawer())

    # ===================================================================
    # TOP BAR
    # ===================================================================
    with ui.header().classes("items-center justify-between q-px-md").style("background: black !important; border-bottom: 1px solid #333;"):
        with ui.row().classes("items-center gap-2"):
            ui.button(icon="menu", on_click=drawer.toggle).props("flat round color=white")
            ui.label().style(
                "width: 300px; height: 60px; background-image: url('/pngs/rosetta_banner.png');"
                " background-repeat: no-repeat; background-position: left center; background-size: contain;"
            )
        with ui.row().classes("items-center gap-2"):
            ui.label(f"👤 {email}").classes("text-body2")
            ui.button("Sign Out", on_click=_do_logout).props("flat color=white size=sm")

    # ===================================================================
    # MAIN CONTENT
    # ===================================================================
    with ui.column().classes("w-full items-center q-pa-md").style("max-width: 1100px; margin: 0 auto"):

        # ---------------------------------------------------------------
        # Birth-data form in a collapsible expansion
        # ---------------------------------------------------------------
        birth_exp = ui.expansion("Enter Birth Data", icon="person_add").classes(
            "w-full"
        ).props("default-opened")

        with birth_exp:
            ui.html('<p style="color:#cc0000; font-size:0.78em; margin-bottom:2px;">* required fields</p>')

            # --- Unknown Time checkbox ---
            unknown_cb = ui.checkbox("Unknown Time").bind_value(form, "unknown_time")

            # --- Gender (optional) ---
            ui.label("Gender (optional)").classes("text-body2 q-mt-sm")
            ui.radio(
                ["Female", "Male", "Non-binary"],
                value=form.get("gender"),
                on_change=lambda e: form.update(gender=e.value),
            ).props("inline")

            # --- Name & City ---
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("col"):
                    ui.input("Name *").bind_value(form, "name").classes("w-full")
                with ui.column().classes("col"):
                    ui.input("City of Birth *").bind_value(form, "city").classes("w-full")

            # --- Date selectors ---
            with ui.row().classes("w-full gap-4 items-end"):
                with ui.column().classes("col"):
                    ui.number("Year *", min=1000, max=3000, step=1, precision=0).bind_value(
                        form, "year",
                        forward=lambda v: int(v) if v else 2000,
                    ).classes("w-full")
                with ui.column().classes("col"):
                    ui.select(
                        MONTH_NAMES, label="Month *",
                    ).bind_value(form, "month_name").classes("w-full")
                with ui.column().classes("col"):
                    # Day list is rebuilt whenever month/year changes
                    day_select = ui.select(
                        list(range(1, 32)), label="Day *",
                    ).bind_value(form, "day").classes("w-full")

            def _refresh_days():
                month_idx = MONTH_NAMES.index(form.get("month_name", "January")) + 1
                yr = int(form.get("year", 2000))
                try:
                    max_day = calendar.monthrange(yr, month_idx)[1]
                except Exception:
                    max_day = 31
                day_select.options = list(range(1, max_day + 1))
                day_select.update()
                if form.get("day", 1) > max_day:
                    form["day"] = max_day
                    day_select.value = max_day

            # Watch for month/year changes and rebuild days
            _refresh_days()

            # --- Time selectors ---
            HOURS   = ["--"] + [f"{h:02d}" for h in range(1, 13)]
            MINUTES = ["--"] + [f"{m:02d}" for m in range(0, 60)]
            AMPMS   = ["--", "AM", "PM"]

            with ui.row().classes("w-full gap-4 items-end"):
                with ui.column().classes("col"):
                    hour_sel = ui.select(
                        HOURS, label="Hour",
                    ).bind_value(form, "hour_12").classes("w-full")
                with ui.column().classes("col"):
                    min_sel = ui.select(
                        MINUTES, label="Minute",
                    ).bind_value(form, "minute_str").classes("w-full")
                with ui.column().classes("col"):
                    ampm_sel = ui.select(
                        AMPMS, label="AM/PM",
                    ).bind_value(form, "ampm").classes("w-full")

            # Disable time selectors when unknown_time is checked
            unknown_cb.on_value_change(
                lambda e: _handle_unknown_time(e.value, form, hour_sel, min_sel, ampm_sel)
            )
            # Apply initial state
            if form.get("unknown_time"):
                hour_sel.disable()
                min_sel.disable()
                ampm_sel.disable()

            ui.separator()

            # --- Status / error area ---
            status_label = ui.label("").classes("text-body2")
            status_label.set_visibility(False)

            # --- Calculate button ---
            calc_btn = ui.button(
                "Calculate Chart", icon="auto_awesome",
            ).classes("w-full q-mt-sm").props("color=primary")

        # ---------------------------------------------------------------
        # Chart Manager (profile load / save / delete)
        # ---------------------------------------------------------------
        chart_mgr_exp = ui.expansion("Chart Manager", icon="folder_open").classes(
            "w-full q-mt-md"
        )

        with chart_mgr_exp:
            # Profile selector
            profile_select = ui.select(
                options=[], label="Saved Profiles",
            ).classes("w-full")

            # Save row: name input + "Is my chart" checkbox
            with ui.row().classes("w-full items-center gap-2 q-mt-sm"):
                save_name_input = ui.input(
                    "Profile name to save",
                ).classes("col")
                is_my_chart_cb = ui.checkbox("My chart (self)")

            # Action buttons
            mgr_status = ui.label("").classes("text-body2")
            mgr_status.set_visibility(False)

            with ui.row().classes("w-full gap-2 q-mt-sm"):
                load_btn = ui.button("Load", icon="download").props("outline")
                save_btn = ui.button("Save", icon="save").props("outline color=primary")
                delete_btn = ui.button("Delete", icon="delete").props("outline color=negative")
                refresh_btn = ui.button("Refresh List", icon="refresh").props("flat size=sm")

            # ---- Donate Chart to Science (Step 11) ----
            ui.separator().classes("q-mt-md")
            ui.label("Donate Your Chart to Science").classes(
                "text-subtitle2 q-mt-sm"
            )
            ui.label(
                "Optional: donate a chart profile to the research dataset. "
                "Joylin may study donated charts for app development."
            ).classes("text-caption text-grey")

            with ui.dialog() as donate_dlg, ui.card().style("max-width: 500px"):
                ui.label("Donate Chart to Science").classes("text-h6 q-mb-sm")
                ui.label(
                    "This is entirely voluntary. If you choose to donate your "
                    "chart, it will only be available to the app admin (Joylin) "
                    "for research and development."
                ).classes("text-body2 q-mb-md")
                donate_name_input = ui.input(
                    "Name or Event label",
                    placeholder="e.g. My Birth Chart",
                ).classes("w-full")
                donate_status = ui.label("").classes("text-body2 q-mt-sm")
                donate_status.set_visibility(False)

                with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                    ui.button("Cancel", on_click=donate_dlg.close).props("flat")

                    def _do_donate():
                        label = (donate_name_input.value or "").strip()
                        if not label:
                            donate_status.text = "Please give a name."
                            donate_status.classes(
                                replace="text-body2 text-negative"
                            )
                            donate_status.set_visibility(True)
                            return
                        chart_obj = get_chart_object(state)
                        if chart_obj is None:
                            donate_status.text = "No chart loaded."
                            donate_status.classes(
                                replace="text-body2 text-negative"
                            )
                            donate_status.set_visibility(True)
                            return
                        payload = {
                            "year": state.get("year", 2000),
                            "month": (
                                MONTH_NAMES.index(
                                    state.get("month_name", "January")
                                ) + 1
                            ),
                            "day": state.get("day", 1),
                            "city": state.get("city", ""),
                            "lat": state.get("current_lat"),
                            "lon": state.get("current_lon"),
                            "tz_name": state.get("current_tz_name"),
                        }
                        try:
                            from src.data_stubs import community_save
                            uid = _get_user_id() or "anon"
                            community_save(label, payload, submitted_by=uid)
                            donate_status.text = (
                                f'Thank you! Donated as "{label}".'
                            )
                            donate_status.classes(
                                replace="text-body2 text-positive"
                            )
                            donate_status.set_visibility(True)
                        except Exception as exc:
                            donate_status.text = f"Error: {exc}"
                            donate_status.classes(
                                replace="text-body2 text-negative"
                            )
                            donate_status.set_visibility(True)

                    ui.button(
                        "Donate", icon="volunteer_activism",
                        on_click=_do_donate,
                    ).props("color=primary")

            donate_btn = ui.button(
                "Donate Chart", icon="volunteer_activism",
            ).props("outline size=sm").classes("q-mt-xs")
            donate_btn.on_click(donate_dlg.open)

            def _mgr_error(msg: str):
                mgr_status.text = msg
                mgr_status.classes(replace="text-body2 text-negative")
                mgr_status.set_visibility(True)

            def _mgr_success(msg: str):
                mgr_status.text = msg
                mgr_status.classes(replace="text-body2 text-positive")
                mgr_status.set_visibility(True)

            def _mgr_clear():
                mgr_status.set_visibility(False)

            # ---- Refresh profile list ----
            def _refresh_profiles():
                """Reload the profile list from Supabase and update the selector."""
                uid = _get_user_id()
                if not uid:
                    return
                try:
                    from supabase_profiles import load_user_profiles_db
                    profiles = load_user_profiles_db(uid)
                    names = sorted(profiles.keys())
                    profile_select.options = names
                    profile_select.update()
                except Exception as exc:
                    _log.warning("Failed to refresh profiles: %s", exc)

            # ---- Load ----
            async def _on_load():
                _mgr_clear()
                uid = _get_user_id()
                selected = profile_select.value
                if not uid or not selected:
                    _mgr_error("Select a profile to load.")
                    return
                try:
                    from supabase_profiles import load_user_profiles_db
                    profiles = load_user_profiles_db(uid)
                    prof_data = profiles.get(selected)
                    if prof_data is None:
                        _mgr_error(f"Profile '{selected}' not found.")
                        return

                    # Apply profile to NiceGUI state
                    from src.profile_helpers import apply_profile
                    state = ensure_state()
                    apply_profile(selected, prof_data, state)

                    # Convert the in-memory chart object to serializable JSON
                    _chart_obj = state.pop("last_chart", None)
                    if _chart_obj is not None and hasattr(_chart_obj, "to_json"):
                        state["last_chart_json"] = _chart_obj.to_json()

                    # Sync form dict from state so UI widgets update
                    form["name"] = state.get("birth_name") or state.get("name") or selected
                    form["city"] = state.get("city", "")
                    form["year"] = state.get("year", 2000)
                    form["month_name"] = state.get("month_name", "January")
                    form["day"] = state.get("day", 1)
                    form["hour_12"] = state.get("hour_12", "12")
                    form["minute_str"] = state.get("minute_str", "00")
                    form["ampm"] = state.get("ampm", "AM")
                    form["unknown_time"] = state.get("profile_unknown_time", False)
                    form["gender"] = state.get("birth_gender")

                    # Re-render chart in current tab
                    _rerender_active_tab()

                    save_name_input.value = selected
                    is_my_chart_cb.value = state.get("is_my_chart", False)
                    _mgr_success(f"Loaded profile '{selected}'.")
                    # Open birth form so user can see pre-filled data
                    birth_exp.open()

                except Exception as exc:
                    _log.exception("Profile load failed")
                    _mgr_error(f"Load failed: {exc}")

            # ---- Save ----
            async def _on_save():
                _mgr_clear()
                uid = _get_user_id()
                prof_name = (save_name_input.value or "").strip()
                if not uid:
                    _mgr_error("Not authenticated.")
                    return
                if not prof_name:
                    _mgr_error("Enter a profile name.")
                    return

                state = ensure_state()
                chart_obj = get_chart_object(state)
                if chart_obj is None:
                    _mgr_error("Calculate a chart first before saving.")
                    return

                try:
                    from src.mcp.comprehension_models import PersonProfile as _PP
                    from supabase_profiles import save_user_profile_db

                    rel = "self" if is_my_chart_cb.value else "other"
                    pp = _PP(
                        name=prof_name,
                        chart_id=prof_name,
                        relationship_to_querent=rel,
                        gender=form.get("gender"),
                        significant_places=[chart_obj.city] if getattr(chart_obj, "city", None) else [],
                        astro_chart=chart_obj,
                    )
                    save_user_profile_db(uid, prof_name, pp.to_dict())
                    _refresh_profiles()
                    profile_select.value = prof_name
                    _mgr_success(f"Saved profile '{prof_name}'.")
                except Exception as exc:
                    _log.exception("Profile save failed")
                    _mgr_error(f"Save failed: {exc}")

            # ---- Delete ----
            async def _on_delete():
                _mgr_clear()
                uid = _get_user_id()
                selected = profile_select.value
                if not uid or not selected:
                    _mgr_error("Select a profile to delete.")
                    return
                try:
                    from supabase_profiles import delete_user_profile_db
                    delete_user_profile_db(uid, selected)
                    _refresh_profiles()
                    profile_select.value = None
                    save_name_input.value = ""
                    _mgr_success(f"Deleted profile '{selected}'.")
                except Exception as exc:
                    _log.exception("Profile delete failed")
                    _mgr_error(f"Delete failed: {exc}")

            load_btn.on_click(_on_load)
            save_btn.on_click(_on_save)
            delete_btn.on_click(_on_delete)
            refresh_btn.on_click(lambda: _refresh_profiles())

            # Populate profile list on page load
            _refresh_profiles()

        # ===============================================================
        # SHARED CONTROLS  (visible when a chart exists)
        # ===============================================================
        shared_row = ui.row().classes("w-full items-center gap-4 q-mt-md")
        with shared_row:
            house_select = ui.select(
                ["Placidus", "Whole Sign", "Equal", "Koch",
                 "Campanus", "Regiomontanus", "Porphyry"],
                label="House System",
                value=(state.get("house_system", "placidus") or "placidus").title(),
            ).classes("w-48")

            # --- "Now" quick-city button (Step 11) ---
            now_btn = ui.button("Now", icon="schedule").props(
                "outline dense size=sm"
            )

            async def _on_now_click():
                """Set the birth form to current time at the stored city."""
                import pytz
                lat = state.get("current_lat")
                lon = state.get("current_lon")
                tz_name = state.get("current_tz_name")
                city_val = state.get("city") or form.get("city") or ""

                if not (isinstance(lat, (int, float))
                        and isinstance(lon, (int, float))
                        and tz_name):
                    # No valid location — prompt user
                    ui.notify(
                        "Enter a city and calculate a chart first, then "
                        "click Now to use the current time.",
                        type="warning",
                    )
                    return

                try:
                    tz = pytz.timezone(tz_name)
                except Exception:
                    ui.notify(f"Unknown timezone: {tz_name}", type="negative")
                    return

                import datetime as _dtm
                now = _dtm.datetime.now(tz)
                h24 = now.hour
                _ampm = "PM" if h24 >= 12 else "AM"
                _h12 = h24 % 12 or 12

                # Push into form dict
                form["year"] = now.year
                form["month_name"] = MONTH_NAMES[now.month - 1]
                form["day"] = now.day
                form["hour_12"] = f"{_h12:02d}"
                form["minute_str"] = f"{now.minute:02d}"
                form["ampm"] = _ampm
                form["city"] = city_val
                form["unknown_time"] = False

                # Recalculate chart with those inputs
                # (Reuse the _on_calculate handler logic)
                from src.chart_adapter import ChartInputs, compute_chart
                month_idx = MONTH_NAMES.index(form["month_name"]) + 1
                inputs = ChartInputs(
                    name=state.get("name") or form.get("name") or "",
                    year=now.year, month=month_idx, day=now.day,
                    hour_24=h24, minute=now.minute,
                    city=city_val,
                    lat=lat, lon=lon, tz_name=tz_name,
                    unknown_time=False,
                    house_system=(
                        state.get("house_system", "placidus") or "placidus"
                    ).lower(),
                    gender=form.get("gender"),
                )
                try:
                    result = compute_chart(inputs)
                    if result.error:
                        ui.notify(f"Chart error: {result.error}", type="negative")
                        return
                    state["last_chart_json"] = (
                        result.chart.to_json() if result.chart else None
                    )
                    state["chart_ready"] = True
                    state["year"] = now.year
                    state["month_name"] = MONTH_NAMES[now.month - 1]
                    state["day"] = now.day
                    state["city"] = city_val
                    _build_circuit_toggles()
                    _rerender_active_tab()
                    ui.notify(
                        f"Chart set to now: {now:%B %d, %Y %I:%M %p}",
                        type="positive",
                    )
                except Exception as exc:
                    ui.notify(f"Chart calculation failed: {exc}", type="negative")

            now_btn.on_click(_on_now_click)

            events_container = ui.html("").classes("text-body2")

        def _on_house_system_change(e):
            state["house_system"] = (e.value or "placidus").lower()
            _rerender_active_tab()
            _refresh_drawer()

        house_select.on_value_change(_on_house_system_change)

        # ---------------------------------------------------------------
        # Transit / Synastry controls
        # ---------------------------------------------------------------
        transit_row = ui.row().classes("w-full items-center gap-3 q-mt-sm")

        with transit_row:
            transit_cb = ui.checkbox(
                "🌐 Transits",
                value=state.get("transit_mode", False),
            )

        # --- Transit date navigation (hidden until transit_mode is on) ---
        transit_nav_row = ui.row().classes("w-full items-center gap-2 q-mt-xs")
        transit_nav_row.set_visibility(state.get("transit_mode", False))

        with transit_nav_row:
            transit_back_btn = ui.button("◀").props("flat dense size=sm")
            transit_now_btn = ui.button("Now").props("outline dense size=sm")
            transit_fwd_btn = ui.button("▶").props("flat dense size=sm")
            _INTERVAL_OPTS = ["1 day", "1 week", "1 month", "1 year", "1 decade"]
            _stored_interval = state.get("transit_nav_interval", "1 day")
            if _stored_interval not in _INTERVAL_OPTS:
                _stored_interval = "1 day"
                state["transit_nav_interval"] = _stored_interval
            transit_interval_sel = ui.select(
                _INTERVAL_OPTS,
                value=_stored_interval,
            ).props("dense").classes("w-28")
            transit_dt_label = ui.label("").classes("text-body2 text-grey-7")
            swap_btn = ui.button("Swap Charts", icon="swap_horiz").props(
                "outline dense size=sm"
            )

        # --- Chart 2 profile selector (synastry) ---
        synastry_row = ui.row().classes("w-full items-center gap-3 q-mt-xs")
        with synastry_row:
            chart2_label = ui.label("Chart 2:").classes("text-body2")
            chart2_profile_sel = ui.select(
                options=[], label="Select profile for Chart 2",
            ).classes("w-56")
            chart2_load_btn = ui.button("Load Chart 2", icon="download").props(
                "outline dense size=sm"
            )
            chart2_clear_btn = ui.button("Clear Chart 2", icon="clear").props(
                "flat dense size=sm color=negative"
            )
        synastry_row.set_visibility(False)  # shown when we have profiles

        def _refresh_chart2_profiles():
            """Populate the Chart 2 profile selector."""
            uid = _get_user_id()
            if not uid:
                return
            try:
                from supabase_profiles import load_user_profiles_db
                profiles = load_user_profiles_db(uid)
                names = sorted(profiles.keys())
                chart2_profile_sel.options = names
                chart2_profile_sel.update()
                synastry_row.set_visibility(bool(names))
            except Exception:
                pass

        def _update_transit_label():
            """Show the current transit datetime in the label."""
            iso = state.get("transit_dt_iso")
            if iso:
                try:
                    utc = _dt.datetime.fromisoformat(iso)
                    tz_name = state.get("current_tz_name", "UTC")
                    from zoneinfo import ZoneInfo
                    local = utc.replace(tzinfo=_dt.timezone.utc).astimezone(ZoneInfo(tz_name))
                    transit_dt_label.text = f"Chart date: {local:%b %d, %Y  %H:%M} {tz_name}"
                except Exception:
                    transit_dt_label.text = f"Transit: {iso[:16]}"
            else:
                transit_dt_label.text = ""

        def _compute_and_store_transit(utc: _dt.datetime):
            """Compute a transit chart at the given UTC time and store it."""
            from src.chart_adapter import compute_transit_chart
            lat = state.get("current_lat")
            lon = state.get("current_lon")
            tz_name = state.get("current_tz_name", "UTC")
            city = state.get("city", "")
            house_sys = (state.get("house_system", "placidus") or "placidus").lower()

            if lat is None or lon is None:
                return

            result = compute_transit_chart(
                lat=lat, lon=lon, tz_name=tz_name,
                city=city, house_system=house_sys,
                transit_utc=utc,
            )
            if result.chart is not None:
                state["last_chart_2_json"] = result.chart.to_json()
                state["transit_dt_iso"] = utc.isoformat()
                state["transit_mode"] = True
                state["synastry_mode"] = False
                _update_transit_label()
                _rerender_active_tab()

        def _on_transit_toggle(e):
            state["transit_mode"] = e.value
            transit_nav_row.set_visibility(e.value)
            if e.value:
                # If no transit chart yet, compute "Now"
                if not state.get("last_chart_2_json"):
                    now_utc = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
                    _compute_and_store_transit(now_utc)
                else:
                    _rerender_active_tab()
            else:
                # Turn off transit — back to single chart
                _rerender_active_tab()

        transit_cb.on_value_change(_on_transit_toggle)

        def _on_transit_now():
            now_utc = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
            _compute_and_store_transit(now_utc)

        transit_now_btn.on_click(_on_transit_now)

        def _nav_transit(direction: int):
            iso = state.get("transit_dt_iso")
            if not iso:
                now_utc = _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
            else:
                now_utc = _dt.datetime.fromisoformat(iso)

            interval = state.get("transit_nav_interval", "1 day")
            if interval == "1 day":
                new_dt = now_utc + _dt.timedelta(days=direction)
            elif interval == "1 week":
                new_dt = now_utc + _dt.timedelta(weeks=direction)
            elif interval == "1 month":
                new_dt = now_utc + relativedelta(months=direction)
            elif interval == "1 year":
                new_dt = now_utc + relativedelta(years=direction)
            elif interval == "1 decade":
                new_dt = now_utc + relativedelta(years=10 * direction)
            else:
                new_dt = now_utc + _dt.timedelta(days=direction)

            _compute_and_store_transit(new_dt)

        transit_back_btn.on_click(lambda: _nav_transit(-1))
        transit_fwd_btn.on_click(lambda: _nav_transit(1))
        transit_interval_sel.on_value_change(
            lambda e: state.update(transit_nav_interval=e.value)
        )

        def _on_swap_charts():
            """Swap Chart 1 ↔ Chart 2 data."""
            c1_json = state.get("last_chart_json")
            c2_json = state.get("last_chart_2_json")
            if c1_json and c2_json:
                state["last_chart_json"] = c2_json
                state["last_chart_2_json"] = c1_json
                _rerender_active_tab()
                _refresh_drawer()

        swap_btn.on_click(_on_swap_charts)

        def _on_load_chart2():
            """Load selected profile as Chart 2 (synastry mode)."""
            uid = _get_user_id()
            selected = chart2_profile_sel.value
            if not uid or not selected:
                return
            try:
                from supabase_profiles import load_user_profiles_db
                from src.profile_helpers import apply_profile
                profiles = load_user_profiles_db(uid)
                prof_data = profiles.get(selected)
                if prof_data is None:
                    return

                # Apply profile to a temp state to get chart object
                temp = {}
                apply_profile(selected, prof_data, temp)
                chart2_obj = temp.pop("last_chart", None)
                if chart2_obj is not None and hasattr(chart2_obj, "to_json"):
                    state["last_chart_2_json"] = chart2_obj.to_json()
                    state["synastry_mode"] = True
                    state["transit_mode"] = False
                    state["chart_2_profile_name"] = selected
                    transit_cb.value = False
                    transit_nav_row.set_visibility(False)
                    _rerender_active_tab()
            except Exception as exc:
                _log.exception("Chart 2 load failed")

        chart2_load_btn.on_click(_on_load_chart2)

        def _on_clear_chart2():
            """Clear Chart 2 and exit synastry/transit mode."""
            state["last_chart_2_json"] = None
            state["synastry_mode"] = False
            state["transit_mode"] = False
            state["chart_2_profile_name"] = None
            state["transit_dt_iso"] = None
            transit_cb.value = False
            transit_nav_row.set_visibility(False)
            _rerender_active_tab()

        chart2_clear_btn.on_click(_on_clear_chart2)

        # Populate Chart 2 profiles on page load
        _refresh_chart2_profiles()

        # ===============================================================
        # WIZARD DIALOG  (Step 11)
        # ===============================================================
        with ui.dialog().classes("w-full") as wizard_dlg, \
                ui.card().style("max-width: 600px; min-width: 400px"):
            ui.label("Guided Topics Wizard").classes("text-h5 q-mb-sm")
            ui.label(
                "Explore topics in your chart with guided questions."
            ).classes("text-body2 text-grey q-mb-md")

            try:
                from src.mcp.topic_maps import WIZARD_TARGETS
                _wizard_domains = WIZARD_TARGETS.get("domains", [])
            except Exception:
                _wizard_domains = []

            _domain_names = [d.get("name", "") for d in _wizard_domains]
            _domain_lookup = {d.get("name", ""): d for d in _wizard_domains}

            wiz_domain_sel = ui.select(
                _domain_names,
                label="What are you here to explore?",
                value=_domain_names[0] if _domain_names else None,
            ).classes("w-full")

            wiz_domain_desc = ui.label("").classes(
                "text-caption text-grey q-mb-sm"
            )
            wiz_sub_sel = ui.select(
                [], label="Narrow it a bit\u2026",
            ).classes("w-full")

            wiz_ref_sel = ui.select(
                [], label="Any particular angle?",
            ).classes("w-full")
            wiz_ref_sel.set_visibility(False)

            wiz_targets_container = ui.column().classes("w-full q-mt-sm")

            def _wiz_update_domain(e=None):
                domain_name = wiz_domain_sel.value
                domain = _domain_lookup.get(domain_name, {})
                wiz_domain_desc.text = domain.get("description", "")
                subs = domain.get("subtopics", [])
                sub_names = [s.get("label", "") for s in subs]
                wiz_sub_sel.options = sub_names
                wiz_sub_sel.value = sub_names[0] if sub_names else None
                wiz_sub_sel.update()
                _wiz_update_subtopic()

            def _wiz_update_subtopic(e=None):
                domain_name = wiz_domain_sel.value
                domain = _domain_lookup.get(domain_name, {})
                subs = domain.get("subtopics", [])
                sub_lookup = {s.get("label", ""): s for s in subs}
                sub = sub_lookup.get(wiz_sub_sel.value, {})
                refinements = sub.get("refinements")
                if refinements:
                    ref_names = list(refinements.keys())
                    wiz_ref_sel.options = ref_names
                    wiz_ref_sel.value = ref_names[0] if ref_names else None
                    wiz_ref_sel.set_visibility(True)
                    wiz_ref_sel.update()
                else:
                    wiz_ref_sel.set_visibility(False)
                    wiz_ref_sel.options = []
                    wiz_ref_sel.update()
                _wiz_show_targets()

            def _wiz_show_targets(e=None):
                domain_name = wiz_domain_sel.value
                domain = _domain_lookup.get(domain_name, {})
                subs = domain.get("subtopics", [])
                sub_lookup = {s.get("label", ""): s for s in subs}
                sub = sub_lookup.get(wiz_sub_sel.value, {})
                refinements = sub.get("refinements")
                if refinements and wiz_ref_sel.value:
                    targets = refinements.get(wiz_ref_sel.value, [])
                else:
                    targets = sub.get("targets", [])

                wiz_targets_container.clear()
                with wiz_targets_container:
                    if targets:
                        ui.label("Where to look in your chart:").classes(
                            "text-subtitle2 q-mb-xs"
                        )
                        from models_v2 import static_db as _sdb
                        _GLYPHS = getattr(_sdb, "GLYPHS", {})
                        _OBJ_MEANINGS = getattr(
                            _sdb, "OBJECT_MEANINGS_SHORT", {}
                        )
                        _SIGN_MEANINGS = getattr(_sdb, "SIGN_MEANINGS", {})
                        _HOUSE_MEANINGS = getattr(_sdb, "HOUSE_MEANINGS", {})
                        for t in targets:
                            glyph = _GLYPHS.get(t, "")
                            display = f"{glyph} {t}" if glyph else t
                            meaning = (_OBJ_MEANINGS.get(t)
                                       or _SIGN_MEANINGS.get(t)
                                       or "")
                            if not meaning and "House" in t:
                                try:
                                    hnum = int(
                                        t.split()[0]
                                        .replace("st", "").replace("nd", "")
                                        .replace("rd", "").replace("th", "")
                                    )
                                    meaning = _HOUSE_MEANINGS.get(hnum, "")
                                except Exception:
                                    pass
                            label_txt = (
                                f"{display}: {meaning}"
                                if meaning else display
                            )
                            ui.label(label_txt).classes("text-body2")
                    else:
                        ui.label("No targets for this selection.").classes(
                            "text-body2 text-grey"
                        )

            wiz_domain_sel.on_value_change(_wiz_update_domain)
            wiz_sub_sel.on_value_change(_wiz_update_subtopic)
            wiz_ref_sel.on_value_change(_wiz_show_targets)

            # Initial population
            if _domain_names:
                _wiz_update_domain()

            with ui.row().classes("w-full justify-end q-mt-md"):
                ui.button("Close", on_click=wizard_dlg.close).props("flat")

        # Wizard button placed just above the tabs
        wizard_btn = ui.button(
            "Guided Wizard", icon="auto_fix_high",
            on_click=wizard_dlg.open,
        ).props("outline size=sm").classes("q-mt-sm")

        # ===============================================================
        # TAB SHELL
        # ===============================================================
        # Check admin status (pass user_id to avoid st.session_state)
        _is_admin = False
        try:
            from supabase_admin import is_admin as _check_admin
            _is_admin = _check_admin(user_id)
        except Exception:
            pass

        with ui.tabs().classes("w-full q-mt-sm") as tabs:
            tab_standard = ui.tab("Standard Chart", icon="auto_awesome")
            tab_circuits = ui.tab("Circuits", icon="hub")
            tab_rulers   = ui.tab("Rulers", icon="account_tree")
            tab_chat     = ui.tab("Chat", icon="chat")
            tab_specs    = ui.tab("Specs", icon="data_object")
            tab_settings = ui.tab("Settings", icon="settings")
            if _is_admin:
                tab_admin = ui.tab("Admin", icon="admin_panel_settings")

        with ui.tab_panels(tabs, value=tab_circuits).classes("w-full"):

            # ===========================================================
            # STANDARD CHART TAB
            # ===========================================================
            with ui.tab_panel(tab_standard):
                std_compass_cb = ui.checkbox(
                    "Compass Rose", value=state.get("compass", True),
                ).classes("q-mb-sm")

                std_chart_container = ui.column().classes("w-full items-center")

                # --- Additional Aspects expansion ---
                with ui.expansion("Additional Aspects").classes("w-full q-mt-sm"):
                    # Select All checkbox
                    std_select_all = ui.checkbox("Select All", value=False)

                    # 4-column grid of aspect body checkboxes
                    aspect_cbs: dict[str, ui.checkbox] = {}
                    with ui.grid(columns=4).classes("w-full gap-2"):
                        for asp_name in TOGGLE_ASPECT_NAMES:
                            cb = ui.checkbox(
                                asp_name,
                                value=state.get("aspect_toggles", {}).get(asp_name, False),
                            )
                            aspect_cbs[asp_name] = cb

                    def _on_select_all(e):
                        for name, cb in aspect_cbs.items():
                            cb.value = e.value
                            state.setdefault("aspect_toggles", {})[name] = e.value
                        _rerender_active_tab()

                    std_select_all.on_value_change(_on_select_all)

                    def _on_aspect_toggle(name, e):
                        state.setdefault("aspect_toggles", {})[name] = e.value
                        _rerender_active_tab()

                    for name, cb in aspect_cbs.items():
                        cb.on_value_change(functools.partial(_on_aspect_toggle, name))

                # --- Synastry aspect group checkboxes (biwheel only) ---
                synastry_aspects_exp = ui.expansion(
                    "Synastry Aspect Groups"
                ).classes("w-full q-mt-sm")
                synastry_aspects_exp.set_visibility(False)

                with synastry_aspects_exp:
                    syn_inter_cb = ui.checkbox(
                        "Inter-chart aspects",
                        value=state.get("synastry_inter", True),
                    )
                    syn_chart1_cb = ui.checkbox(
                        "Chart 1 internal aspects",
                        value=state.get("synastry_chart1", False),
                    )
                    syn_chart2_cb = ui.checkbox(
                        "Chart 2 internal aspects",
                        value=state.get("synastry_chart2", False),
                    )

                    def _on_syn_inter(e):
                        state["synastry_inter"] = e.value
                        _rerender_active_tab()

                    def _on_syn_chart1(e):
                        state["synastry_chart1"] = e.value
                        _rerender_active_tab()

                    def _on_syn_chart2(e):
                        state["synastry_chart2"] = e.value
                        _rerender_active_tab()

                    syn_inter_cb.on_value_change(_on_syn_inter)
                    syn_chart1_cb.on_value_change(_on_syn_chart1)
                    syn_chart2_cb.on_value_change(_on_syn_chart2)

                def _on_std_compass_change(e):
                    state["compass"] = e.value
                    _rerender_active_tab()

                std_compass_cb.on_value_change(_on_std_compass_change)

            # ===========================================================
            # CIRCUITS TAB
            # ===========================================================
            with ui.tab_panel(tab_circuits):
                cir_compass_cb = ui.checkbox(
                    "Compass Rose", value=state.get("compass", True),
                ).classes("q-mb-sm")

                # Circuit submode (visible only in biwheel mode)
                cir_submode_row = ui.row().classes("gap-2 q-mb-sm")
                with cir_submode_row:
                    cir_submode_radio = ui.radio(
                        ["Combined", "Connected"],
                        value=state.get("circuit_submode", "Combined"),
                    ).props("inline dense")
                cir_submode_row.set_visibility(False)

                def _on_cir_submode_change(e):
                    state["circuit_submode"] = e.value
                    _rerender_active_tab()

                cir_submode_radio.on_value_change(_on_cir_submode_change)

                with ui.row().classes("gap-2 q-mb-sm"):
                    show_all_btn = ui.button("Show All", icon="visibility").props("outline size=sm")
                    hide_all_btn = ui.button("Hide All", icon="visibility_off").props("outline size=sm")

                # Circuit pattern checkboxes (populated after chart computation)
                cir_patterns_container = ui.column().classes("w-full")
                # Singleton checkboxes
                cir_singletons_container = ui.column().classes("w-full q-mt-sm")

                cir_chart_container = ui.column().classes("w-full items-center q-mt-sm")

                def _build_circuit_toggles():
                    """Build circuit pattern + singleton checkboxes from current chart data."""
                    from lookup_v2 import GLYPHS as _GLYPHS

                    chart_obj = get_chart_object(state)
                    if chart_obj is None:
                        return

                    patterns = getattr(chart_obj, "aspect_groups", None) or []
                    singleton_map = getattr(chart_obj, "singleton_map", None) or {}
                    shapes = getattr(chart_obj, "shapes", None) or []

                    want_glyphs = state.get("label_style", "glyph") == "glyph"

                    def _fmt(name: str) -> str:
                        """Format a planet/point name using glyph or text per user setting."""
                        if want_glyphs:
                            return _GLYPHS.get(name, name)
                        return name

                    def _fmt_list(names) -> str:
                        return ", ".join(_fmt(n) for n in names)

                    # Detect biwheel and resolve chart names
                    biwheel = bool(state.get("synastry_mode") or state.get("transit_mode"))
                    chart1_name = state.get("current_profile") or "Chart 1"
                    chart2_name = "Transits" if state.get("transit_mode") else "Chart 2"

                    def _render_one_circuit(idx):
                        """Render a single circuit card (checkbox + expander with shapes)."""
                        component = patterns[idx]
                        pat_on = state.get("pattern_toggles", {}).get(str(idx), False)

                        # Circuit name (editable, stored in state)
                        circuit_name_key = f"circuit_name_{idx}"
                        circuit_names = state.get("circuit_names", {})
                        circuit_title = circuit_names.get(circuit_name_key, f"Circuit {idx + 1}")

                        # Members label for expander header
                        members_label = _fmt_list(component)

                        with ui.card().classes("w-full q-mb-sm").props("bordered"):
                            # Top-level circuit checkbox
                            cb = ui.checkbox(circuit_title, value=pat_on)
                            cb.on_value_change(functools.partial(_on_pattern_toggle, idx))

                            # Expander: members + sub-shapes
                            with ui.expansion(members_label).classes("w-full"):
                                # Editable circuit name
                                name_input = ui.input(
                                    "Circuit name",
                                    value=circuit_title,
                                ).classes("q-mb-xs").props("dense")

                                def _on_name_change(e, _key=circuit_name_key):
                                    state.setdefault("circuit_names", {})[_key] = e.value

                                name_input.on("blur", _on_name_change)

                                # Sub-shapes for this circuit
                                parent_shapes = [s for s in shapes if s.get("parent") == idx]
                                if parent_shapes:
                                    ui.label("Sub-shapes:").classes("text-caption text-bold q-mt-xs")
                                    for s in parent_shapes:
                                        sid = s.get("id", "")
                                        s_type = s.get("type", "Shape")
                                        s_members = s.get("members", [])
                                        s_on = state.get("shape_toggles", {}).get(str(sid), False)

                                        # Format shape label like Streamlit:
                                        # "Grand Trine: Sun, Moon, Jupiter"
                                        # In biwheel: "Grand Trine: Chart1: Sun, Moon; Chart2: Jupiter"
                                        if biwheel:
                                            m1 = [m for m in s_members if not str(m).endswith("_2")]
                                            m2 = [str(m)[:-2] for m in s_members if str(m).endswith("_2")]
                                            parts = f"{chart1_name}: {_fmt_list(m1)}"
                                            if m2:
                                                parts += f"; {chart2_name}: {_fmt_list(m2)}"
                                            shape_label = f"{s_type}: {parts}"
                                        else:
                                            shape_label = f"{s_type}: {_fmt_list(s_members)}"

                                        scb = ui.checkbox(shape_label, value=s_on)
                                        scb.on_value_change(functools.partial(_on_shape_toggle, str(sid)))

                    # --- Pattern checkboxes (two-column layout with bordered cards) ---
                    cir_patterns_container.clear()
                    with cir_patterns_container:
                        if patterns:
                            ui.label("Circuits").classes("text-subtitle2 q-mb-xs")
                            half = (len(patterns) + 1) // 2
                            with ui.row().classes("w-full gap-4 items-start"):
                                with ui.column().classes("flex-1"):
                                    for idx in range(half):
                                        _render_one_circuit(idx)
                                with ui.column().classes("flex-1"):
                                    for idx in range(half, len(patterns)):
                                        _render_one_circuit(idx)

                    # --- Singleton checkboxes (horizontal row, glyphs or text) ---
                    cir_singletons_container.clear()
                    with cir_singletons_container:
                        if singleton_map:
                            ui.label("Singletons").classes("text-subtitle2 q-mb-xs")
                            with ui.row().classes("gap-4 flex-wrap"):
                                for planet in sorted(singleton_map.keys()):
                                    s_on = state.get("singleton_toggles", {}).get(planet, False)
                                    label = _fmt(planet)
                                    cb = ui.checkbox(label, value=s_on)
                                    cb.on_value_change(
                                        functools.partial(_on_singleton_toggle, planet)
                                    )

                def _on_pattern_toggle(idx, e):
                    state.setdefault("pattern_toggles", {})[str(idx)] = e.value
                    _rerender_active_tab()

                def _on_shape_toggle(sid, e):
                    state.setdefault("shape_toggles", {})[sid] = e.value
                    _rerender_active_tab()

                def _on_singleton_toggle(planet, e):
                    state.setdefault("singleton_toggles", {})[planet] = e.value
                    _rerender_active_tab()

                def _on_show_all():
                    chart_obj = get_chart_object(state)
                    if chart_obj is None:
                        return
                    patterns = getattr(chart_obj, "aspect_groups", None) or []
                    singleton_map = getattr(chart_obj, "singleton_map", None) or {}
                    for idx in range(len(patterns)):
                        state.setdefault("pattern_toggles", {})[str(idx)] = True
                    for planet in singleton_map:
                        state.setdefault("singleton_toggles", {})[planet] = True
                    _build_circuit_toggles()
                    _rerender_active_tab()

                def _on_hide_all():
                    state["pattern_toggles"] = {}
                    state["singleton_toggles"] = {}
                    state["shape_toggles"] = {}
                    _build_circuit_toggles()
                    _rerender_active_tab()

                show_all_btn.on_click(_on_show_all)
                hide_all_btn.on_click(_on_hide_all)

                def _on_cir_compass_change(e):
                    state["compass"] = e.value
                    _rerender_active_tab()

                cir_compass_cb.on_value_change(_on_cir_compass_change)

            # ===========================================================
            # RULERS TAB
            # ===========================================================
            with ui.tab_panel(tab_rulers):
                rulers_scope_radio = ui.radio(
                    ["By Sign", "By House"],
                    value=state.get("dispositor_scope", "By Sign"),
                ).props("inline dense").classes("q-mb-sm")

                with ui.row().classes("w-full gap-4"):
                    # --- Legend column (narrow) ---
                    with ui.column().classes("").style("min-width: 160px; max-width: 200px"):
                        rulers_legend_container = ui.html("")

                    # --- Graph column (wide) ---
                    with ui.column().classes("col"):
                        rulers_chart_container = ui.column().classes(
                            "w-full items-center"
                        )

                def _build_rulers_legend():
                    """Build the legend HTML from PNG icons."""
                    import os as _os
                    png_dir = _os.path.join(
                        _os.path.dirname(_os.path.abspath(__file__)), "pngs"
                    )

                    def _img_b64(filename):
                        path = _os.path.join(png_dir, filename)
                        if _os.path.exists(path):
                            with open(path, "rb") as f:
                                return base64.b64encode(f.read()).decode()
                        return ""

                    legend_items = [
                        ("green.png", "Sovereign"),
                        ("orange.png", "Dual rulership"),
                        ("purple.png", "Loop"),
                        ("purpleorange.png", "Dual + Loop"),
                        ("blue.png", "Standard"),
                        ("blue_reception.png", "Has reception (in orb)"),
                        ("green_reception.png", "Has reception by sign"),
                        ("conjunction.png", "Conjunction"),
                        ("sextile.png", "Sextile"),
                        ("square.png", "Square"),
                        ("trine.png", "Trine"),
                        ("opposition.png", "Opposition"),
                    ]

                    html = (
                        '<div style="background-color:#262730;padding:12px;'
                        'border-radius:8px;font-size:0.9em;color:white;">'
                        '<strong>Legend</strong>'
                        '<div style="margin:8px 0 8px 0;border-bottom:1px solid #444;'
                        'padding-bottom:8px;">↻ Self-Ruling</div>'
                    )
                    for i, (img, label) in enumerate(legend_items):
                        sep = (
                            'margin-top:8px;border-top:1px solid #444;padding-top:8px;'
                            if i == 5 else ""
                        )
                        b64 = _img_b64(img)
                        if b64:
                            html += (
                                f'<div style="margin-bottom:6px;{sep}">'
                                f'<img src="data:image/png;base64,{b64}" '
                                f'width="18" style="vertical-align:middle;'
                                f'margin-right:6px"/>'
                                f'<span>{label}</span></div>'
                            )
                    html += "</div>"
                    rulers_legend_container.content = html

                def _render_rulers_graph():
                    """Render the dispositor graph into the rulers tab."""
                    import matplotlib
                    matplotlib.use("Agg")
                    import matplotlib.pyplot as plt

                    chart_obj = get_chart_object(state)
                    if chart_obj is None:
                        rulers_chart_container.clear()
                        with rulers_chart_container:
                            ui.label("Calculate a chart first.").classes(
                                "text-body2 text-grey q-pa-md"
                            )
                        return

                    # Get or regenerate plot_data
                    plot_data = getattr(chart_obj, "plot_data", None)
                    if plot_data is None:
                        try:
                            from calc_v2 import compute_plot_data_from_chart
                            plot_data = compute_plot_data_from_chart(chart_obj)
                            chart_obj.plot_data = plot_data
                        except Exception:
                            pass

                    if plot_data is None:
                        rulers_chart_container.clear()
                        with rulers_chart_container:
                            ui.label("No dispositor data available.").classes(
                                "text-body2 text-grey q-pa-md"
                            )
                        return

                    scope = rulers_scope_radio.value or "By Sign"
                    house_sys = (
                        state.get("house_system", "placidus") or "placidus"
                    ).lower()

                    if scope == "By Sign":
                        scope_data = plot_data.get("by_sign")
                    else:
                        house_key_map = {
                            "placidus": "Placidus",
                            "equal": "Equal",
                            "whole sign": "Whole Sign",
                            "whole": "Whole Sign",
                        }
                        plot_data_key = house_key_map.get(house_sys, "Placidus")
                        scope_data = plot_data.get(plot_data_key)

                    if not scope_data or not scope_data.get("raw_links"):
                        rulers_chart_container.clear()
                        with rulers_chart_container:
                            ui.label(
                                "No dispositor graph to display."
                            ).classes("text-body2 text-grey q-pa-md")
                        return

                    # Build header info
                    try:
                        name, date_line, time_line, city, extra_line = (
                            chart_obj.header_lines()
                        )
                        header_info = {
                            "name": name,
                            "date_line": date_line,
                            "time_line": time_line,
                            "city": city,
                            "extra_line": extra_line,
                        }
                    except Exception:
                        header_info = None

                    try:
                        from src.dispositor_graph import plot_dispositor_graph

                        fig = plot_dispositor_graph(
                            scope_data,
                            chart=chart_obj,
                            header_info=header_info,
                            house_system=house_sys,
                        )
                        if fig is None:
                            rulers_chart_container.clear()
                            with rulers_chart_container:
                                ui.label("Graph returned empty.").classes(
                                    "text-body2 text-grey"
                                )
                            return

                        buf = io.BytesIO()
                        fig.savefig(
                            buf, format="png", bbox_inches="tight",
                            facecolor=fig.get_facecolor(), edgecolor="none",
                        )
                        plt.close(fig)
                        buf.seek(0)
                        png_bytes = buf.read()

                        b64 = base64.b64encode(png_bytes).decode()
                        rulers_chart_container.clear()
                        with rulers_chart_container:
                            ui.html(
                                f'<img src="data:image/png;base64,{b64}" '
                                f'style="width:100%; max-width:1000px; '
                                f'image-rendering:auto; display:block; '
                                f'margin:0 auto" />'
                            )
                    except Exception as exc:
                        _log.exception("Dispositor graph render failed")
                        rulers_chart_container.clear()
                        with rulers_chart_container:
                            ui.label(f"Render error: {exc}").classes(
                                "text-body2 text-negative"
                            )

                def _on_rulers_scope_change(e):
                    state["dispositor_scope"] = e.value
                    _render_rulers_graph()

                rulers_scope_radio.on_value_change(_on_rulers_scope_change)

                # Build legend on page load
                _build_rulers_legend()

            # ===========================================================
            # CHAT TAB
            # ===========================================================
            with ui.tab_panel(tab_chat):

                # ── Constants ──────────────────────────────────────────
                _OPENROUTER_MODELS = [
                    "google/gemini-2.0-flash-001",
                    "google/gemini-2.5-pro-preview",
                    "anthropic/claude-sonnet-4-5",
                    "anthropic/claude-3-5-haiku",
                    "openai/gpt-4o-mini",
                    "openai/gpt-4o",
                    "meta-llama/llama-4-scout",
                    "mistralai/mistral-large",
                ]
                _CHAT_MODES = ["Query", "Map", "Execute"]
                _VOICE_MODES = ["Plain", "Circuit"]
                _EXAMPLE_PROMPTS = {
                    "natal": [
                        "What are the main power planets of my chart, and how do they drive my motivations?",
                        "Where do I have the most internal 'friction' in my personality?",
                        "How can I best structure my career to be sustainable and fulfilling?",
                    ],
                    "synastry": [
                        "Which parts of my personality get amplified most when we are together?",
                        "Where do our communication styles naturally sync up or short-circuit?",
                        "What is our biggest relationship challenge?",
                    ],
                    "transit": [
                        "Which areas of my life are under the most 'cosmic pressure' right now?",
                        "I feel a shift in my energy lately — is a current planet poking a sensitive spot?",
                        "Is this a better time to push forward or to sit back and recalibrate?",
                    ],
                }

                # ── Two-column layout: chat (wide) + controls (narrow) ─
                with ui.row().classes("w-full gap-4 items-start"):

                    # ── LEFT: Chat column ──────────────────────────────
                    with ui.column().classes("col-grow"):

                        # Header row
                        with ui.row().classes("w-full items-center justify-between"):
                            ui.label("Ask your chart").classes("text-h6")
                            chat_clear_btn = ui.button(
                                icon="delete", color="grey",
                            ).props("flat dense size=sm").tooltip("Clear chat history")

                        # Scrollable message area
                        chat_scroll = ui.scroll_area().classes(
                            "w-full border rounded q-pa-sm"
                        ).style("height: 55vh; background: #0e1117;")
                        with chat_scroll:
                            chat_messages_col = ui.column().classes("w-full gap-2")

                        # ── Example prompts (shown when empty) ─────────
                        chat_examples_container = ui.column().classes("w-full gap-1 q-mt-xs")

                        def _populate_example_prompts():
                            chat_examples_container.clear()
                            history = state.get("mcp_chat_history", [])
                            if history:
                                chat_examples_container.set_visibility(False)
                                return
                            chat_examples_container.set_visibility(True)
                            syn = state.get("synastry_mode", False)
                            tran = state.get("transit_mode", False)
                            mode_key = "synastry" if syn else ("transit" if tran else "natal")
                            prompts = _EXAMPLE_PROMPTS.get(mode_key, _EXAMPLE_PROMPTS["natal"])
                            with chat_examples_container:
                                ui.label("Try asking…").classes("text-caption text-grey-6")
                                for q in prompts:
                                    _q = q  # closure capture
                                    ui.button(
                                        _q, on_click=lambda _q=_q: _send_chat_message(_q),
                                    ).props("flat dense no-caps align=left").classes(
                                        "text-body2 text-left w-full"
                                    )

                        # ── Input row ──────────────────────────────────
                        with ui.row().classes("w-full items-center gap-2 q-mt-xs"):
                            chat_input = ui.input(
                                placeholder="Ask your chart anything…",
                            ).classes("col-grow").props('outlined dense')
                            chat_send_btn = ui.button(
                                icon="send", color="primary",
                            ).props("flat dense")
                            chat_spinner = ui.spinner("dots", size="sm")
                            chat_spinner.set_visibility(False)

                    # ── RIGHT: Controls column ─────────────────────────
                    with ui.column().classes("w-64 gap-3"):

                        # Model picker
                        chat_model_sel = ui.select(
                            _OPENROUTER_MODELS,
                            label="Model",
                            value=state.get("mcp_model", _OPENROUTER_MODELS[0]),
                        ).props("dense outlined").classes("w-full")
                        chat_model_sel.on_value_change(
                            lambda e: state.update(mcp_model=e.value)
                        )

                        # Mode picker
                        chat_mode_radio = ui.radio(
                            _CHAT_MODES,
                            value=state.get("mcp_chat_mode", "Query"),
                        ).props("dense inline")
                        chat_mode_radio.on_value_change(
                            lambda e: state.update(mcp_chat_mode=e.value)
                        )

                        # Voice picker
                        chat_voice_radio = ui.radio(
                            _VOICE_MODES,
                            value=state.get("mcp_voice_mode", "Plain"),
                        ).props("dense inline")
                        chat_voice_radio.on_value_change(
                            lambda e: state.update(mcp_voice_mode=e.value)
                        )

                        # EQ sliders
                        ui.separator()
                        ui.label("Voice EQ").classes("text-caption text-grey-6")
                        with ui.column().classes("w-full gap-1"):
                            ui.label("Bass").classes("text-caption")
                            chat_eq_bass = ui.slider(
                                min=-20, max=20, step=2,
                                value=state.get("mcp_eq_bass", 0.0),
                            ).props("dense label-always")
                            chat_eq_bass.on_value_change(
                                lambda e: state.update(mcp_eq_bass=e.value)
                            )

                            ui.label("Mids").classes("text-caption")
                            chat_eq_mids = ui.slider(
                                min=-20, max=20, step=2,
                                value=state.get("mcp_eq_mids", 0.0),
                            ).props("dense label-always")
                            chat_eq_mids.on_value_change(
                                lambda e: state.update(mcp_eq_mids=e.value)
                            )

                            ui.label("Treble").classes("text-caption")
                            chat_eq_treble = ui.slider(
                                min=-20, max=20, step=2,
                                value=state.get("mcp_eq_treble", 0.0),
                            ).props("dense label-always")
                            chat_eq_treble.on_value_change(
                                lambda e: state.update(mcp_eq_treble=e.value)
                            )

                        # Dev trace
                        ui.separator()
                        chat_dev_exp = ui.expansion(
                            "Dev Trace", icon="science",
                        ).classes("w-full").props("dense")
                        with chat_dev_exp:
                            chat_dev_content = ui.html("").classes(
                                "text-caption"
                            ).style("max-height: 30vh; overflow-y: auto;")

                # ────────────────────────────────────────────────────────
                # Chat helpers & handlers
                # ────────────────────────────────────────────────────────

                def _render_chat_history():
                    """Rebuild the message bubbles from state history."""
                    chat_messages_col.clear()
                    history = state.get("mcp_chat_history", [])
                    with chat_messages_col:
                        for msg in history:
                            role = msg.get("role", "user")
                            sent = role == "user"
                            ui.chat_message(
                                text=msg.get("content", ""),
                                name="You" if sent else "Rosetta",
                                sent=sent,
                                stamp=msg.get("caption", ""),
                            ).classes("w-full")

                def _append_chat_bubble(role: str, text: str, caption: str = ""):
                    """Add one message bubble to the live UI."""
                    with chat_messages_col:
                        sent = role == "user"
                        ui.chat_message(
                            text=text,
                            name="You" if sent else "Rosetta",
                            sent=sent,
                            stamp=caption,
                        ).classes("w-full")

                def _build_caption(meta: dict) -> str:
                    """Build a compact caption string from response meta."""
                    parts = []
                    if meta.get("model"):
                        parts.append(meta["model"].split("/")[-1])
                    if meta.get("total_tokens"):
                        parts.append(f"{meta['total_tokens']} tok")
                    if meta.get("domain"):
                        parts.append(meta["domain"])
                    if meta.get("confidence") is not None:
                        parts.append(f"{meta['confidence']:.0%}")
                    if meta.get("voice"):
                        parts.append(meta["voice"])
                    return " · ".join(parts)

                def _render_dev_trace(trace: dict):
                    """Render the dev inner-monologue into the expansion."""
                    if not trace:
                        chat_dev_content.content = "<em>No trace yet.</em>"
                        return
                    import html as _html_mod
                    esc = _html_mod.escape
                    parts = []
                    q = trace.get("question", "")
                    if q:
                        parts.append(f"<b>Question:</b> {esc(q)}")
                    s1 = trace.get("step1_comprehension", {})
                    if s1:
                        parts.append(f"<b>Domain:</b> {esc(str(s1.get('domain', '')))} "
                                     f"/ {esc(str(s1.get('subtopic', '')))}")
                        parts.append(f"<b>Type:</b> {esc(str(s1.get('question_type', '')))}")
                        parts.append(f"<b>Confidence:</b> {s1.get('confidence', 0):.0%}")
                        para = s1.get("paraphrase", "")
                        if para:
                            parts.append(f"<b>Understood as:</b> <em>{esc(para)}</em>")
                    s2 = trace.get("step2_factor_resolution", {})
                    if s2:
                        mf = s2.get("merged_factors", [])
                        ro = s2.get("relevant_objects", [])
                        if mf:
                            parts.append(f"<b>Factors:</b> {esc(', '.join(str(f) for f in mf))}")
                        if ro:
                            parts.append(f"<b>Objects:</b> {esc(', '.join(str(o) for o in ro))}")
                    s3 = trace.get("step3_circuit", {})
                    if s3:
                        parts.append(f"<b>Shapes:</b> {s3.get('shapes_count', 0)}")
                        seeds = s3.get("narrative_seeds", [])
                        if seeds:
                            parts.append("<b>Seeds:</b><ul>" + "".join(
                                f"<li>{esc(str(s))}</li>" for s in seeds[:5]
                            ) + "</ul>")
                    s5 = trace.get("step5_synthesis", {})
                    if s5:
                        parts.append(f"<b>Synthesis:</b> {esc(str(s5.get('model', '')))} "
                                     f"({s5.get('prompt_tokens', 0)}+{s5.get('completion_tokens', 0)} tok)")
                    chat_dev_content.content = "<br>".join(parts) if parts else "<em>Empty trace.</em>"

                def _get_api_key() -> str:
                    """Read OpenRouter API key."""
                    from config import get_secret
                    key = get_secret("openrouter", "api_key", default="")
                    if key and key != "PASTE_YOUR_KEY_HERE":
                        return key
                    return ""

                def _run_pipeline(
                    question: str, chart, chart_b, house_system: str,
                    *,
                    uid: str,
                    api_key: str,
                    model: str,
                    mode: str,
                    voice: str,
                    agent_notes: str,
                    pending_q: str,
                ):
                    """Blocking call — run from io_bound thread.

                    All NiceGUI state values are passed as arguments so that
                    this function never touches ``app.storage.user``.
                    Returns ``(response_text, meta, state_updates)`` where
                    *state_updates* is a dict of keys to write back.
                    """
                    from src.mcp.reading_engine import build_reading
                    from src.mcp.prose_synthesizer import synthesize, SynthesisResult
                    from src.mcp.agent_memory import AgentMemory
                    from src.mcp.comprehension_models import PersonProfile, Location, LocationLink

                    state_updates: dict = {}

                    # Resolve per-session memory objects
                    mem = _CHAT_MEMORY.get(uid)
                    if mem is None:
                        mem = AgentMemory()
                        _CHAT_MEMORY[uid] = mem
                    known_persons = _CHAT_PERSONS.get(uid, [])
                    known_locations = _CHAT_LOCATIONS.get(uid, [])

                    # Convert dicts → dataclass instances
                    _persons = None
                    if known_persons:
                        _persons = []
                        for pd in known_persons:
                            locs = [LocationLink(
                                location_name=ld.get("location", ""),
                                connection=ld.get("connection", ""))
                                for ld in pd.get("locations", [])]
                            _persons.append(PersonProfile(
                                name=pd.get("name"),
                                relationship_to_querent=pd.get("relationship_to_querent"),
                                relationships_to_others=pd.get("relationships_to_others", []),
                                memories=pd.get("memories", []),
                                significant_places=pd.get("significant_places", []),
                                chart_id=pd.get("chart_id"),
                                locations=locs,
                            ))
                    _locations = None
                    if known_locations:
                        _locations = []
                        for ld in known_locations:
                            conn = [(cp.get("person", ""), cp.get("connection", ""))
                                    for cp in ld.get("connected_persons", [])]
                            _locations.append(Location(
                                name=ld.get("name", ""),
                                location_type=ld.get("location_type"),
                                connected_persons=conn,
                                relevance=ld.get("relevance"),
                            ))

                    pending_clar = None
                    actual_question = question
                    if pending_q:
                        pending_clar = question
                        actual_question = pending_q
                        state_updates["mcp_pending_question"] = ""
                        mem.answer_all_pending_bot_questions(question)

                    meta = {"mode": mode, "voice": voice}

                    try:
                        packet = build_reading(
                            actual_question, chart,
                            house_system=house_system,
                            include_sabians=False,
                            include_interp_text=True,
                            max_aspects=12,
                            api_key=api_key,
                            agent_notes=agent_notes,
                            chart_b=chart_b,
                            known_persons=_persons,
                            known_locations=_locations,
                            pending_clarification=pending_clar,
                            agent_memory=mem,
                        )

                        # Clarification request
                        if packet._clarification:
                            clar = packet._clarification
                            state_updates["mcp_pending_question"] = actual_question
                            follow_up = clar.get(
                                "follow_up_question",
                                "Could you tell me more about what you'd like to know?",
                            )
                            meta["_is_clarification"] = True
                            return follow_up, meta, state_updates

                        meta["domain"] = packet.domain
                        meta["subtopic"] = packet.subtopic
                        meta["confidence"] = packet.confidence
                        meta["question_type"] = packet.question_type
                        meta["comprehension_note"] = packet.comprehension_note

                        # Accumulate persons & locations
                        if packet.persons:
                            _merge_chat_persons(uid, packet.persons)
                        if packet.locations:
                            _merge_chat_locations(uid, packet.locations)

                        # Accumulate agent notes
                        turn_note = meta.get("comprehension_note", "")
                        if turn_note:
                            existing = agent_notes or ""
                            state_updates["mcp_agent_notes"] = (
                                (existing + "\n" if existing else "") + turn_note
                            )

                        # Dev trace
                        _dev = {
                            "question": actual_question,
                            "step1_comprehension": {
                                "domain": packet.domain,
                                "subtopic": packet.subtopic,
                                "confidence": packet.confidence,
                                "question_type": packet.question_type,
                                "paraphrase": packet.paraphrase or "",
                            },
                            "step2_factor_resolution": {
                                "merged_factors": getattr(packet, "debug_relevant_factors", []),
                                "relevant_objects": getattr(packet, "debug_relevant_objects", []),
                            },
                            "step3_circuit": getattr(packet, "debug_circuit_summary", {}),
                            "step5_synthesis": {},
                        }

                    except Exception as exc:
                        return (
                            f"Failed to build reading: {exc}",
                            meta,
                            state_updates,
                        )

                    # Synthesis mode detection
                    _td = packet.temporal_dimension or "natal"
                    if _td == "synastry" or (
                        packet.subject_config == "dyadic"
                        and packet.chart_b_full_placements
                    ):
                        _synth_mode = "synastry"
                    elif _td in ("transit", "cycle", "timing_predict", "solar_return"):
                        _synth_mode = "transit"
                    else:
                        _synth_mode = "natal"

                    if not api_key:
                        meta.update(backend="fallback", model="none")
                        return (
                            "No OpenRouter API key configured. "
                            "Set OPENROUTER_API_KEY in .env to enable chat.",
                            meta,
                            state_updates,
                        )

                    try:
                        result: SynthesisResult = synthesize(
                            packet,
                            backend="openrouter",
                            model=model,
                            mode=_synth_mode,
                            voice=voice.lower(),
                            api_key=api_key,
                            agent_memory=mem,
                        )
                        meta.update(
                            model=result.model,
                            backend=result.backend,
                            prompt_tokens=result.prompt_tokens,
                            completion_tokens=result.completion_tokens,
                            total_tokens=result.total_tokens,
                        )
                        _dev["step5_synthesis"] = {
                            "model": result.model,
                            "backend": result.backend,
                            "prompt_tokens": result.prompt_tokens,
                            "completion_tokens": result.completion_tokens,
                        }
                        _CHAT_DEV_TRACE[uid] = _dev
                        return result.text, meta, state_updates

                    except Exception as exc:
                        meta.update(backend="fallback", model="none", llm_error=str(exc))
                        _CHAT_DEV_TRACE[uid] = _dev
                        return (
                            f"OpenRouter call failed: {exc}\n\n"
                            "Check API key and model availability.",
                            meta,
                            state_updates,
                        )

                async def _send_chat_message(text: str | None = None):
                    """Handle sending a chat message (user-typed or starter prompt)."""
                    prompt = text or chat_input.value
                    if not prompt or not prompt.strip():
                        return
                    prompt = prompt.strip()

                    # Clear input
                    chat_input.value = ""
                    chat_examples_container.set_visibility(False)

                    # Check chart
                    chart_obj = get_chart_object(state)
                    if chart_obj is None:
                        _append_chat_bubble("user", prompt)
                        err_msg = ("No chart loaded yet. Please calculate a "
                                   "chart first using the birth data form above.")
                        _append_chat_bubble("assistant", err_msg)
                        history = state.get("mcp_chat_history", [])
                        history.append({"role": "user", "content": prompt, "caption": ""})
                        history.append({"role": "assistant", "content": err_msg, "caption": ""})
                        state["mcp_chat_history"] = history
                        return

                    # Show user message
                    _append_chat_bubble("user", prompt)
                    history = state.get("mcp_chat_history", [])
                    history.append({"role": "user", "content": prompt, "caption": ""})

                    # Show spinner
                    chat_spinner.set_visibility(True)
                    chat_send_btn.disable()

                    # Get chart_b if in biwheel mode
                    chart_b = get_chart_2_object(state) if (
                        state.get("synastry_mode") or state.get("transit_mode")
                    ) else None
                    hs = state.get("house_system", "placidus")

                    # Extract ALL state values here (UI context) so
                    # _run_pipeline never touches app.storage.user.
                    uid = _get_user_id() or "anon"
                    _api_key = _get_api_key()
                    _model = state.get("mcp_model", "google/gemini-2.0-flash-001")
                    _mode = state.get("mcp_chat_mode", "Query")
                    _voice = state.get("mcp_voice_mode", "Plain")
                    _agent_notes = state.get("mcp_agent_notes", "")
                    _pending_q = state.get("mcp_pending_question", "")

                    try:
                        response_text, meta, state_updates = await run.io_bound(
                            _run_pipeline, prompt, chart_obj, chart_b, hs,
                            uid=uid,
                            api_key=_api_key,
                            model=_model,
                            mode=_mode,
                            voice=_voice,
                            agent_notes=_agent_notes,
                            pending_q=_pending_q,
                        )
                    except Exception as exc:
                        response_text = f"Error: {exc}"
                        meta = {}
                        state_updates = {}

                    # Apply any state updates returned from the pipeline
                    for k, v in state_updates.items():
                        state[k] = v

                    # Build caption and show response
                    caption = _build_caption(meta)
                    _append_chat_bubble("assistant", response_text, caption)
                    history.append({
                        "role": "assistant",
                        "content": response_text,
                        "caption": caption,
                    })
                    state["mcp_chat_history"] = history

                    # Update dev trace
                    _render_dev_trace(_CHAT_DEV_TRACE.get(uid, {}))

                    # Hide spinner
                    chat_spinner.set_visibility(False)
                    chat_send_btn.enable()

                    # Scroll to bottom
                    chat_scroll.scroll_to(percent=100)

                # Wire send button and Enter key
                chat_send_btn.on_click(lambda: _send_chat_message())
                chat_input.on("keydown.enter", lambda: _send_chat_message())

                # Wire clear button
                def _clear_chat():
                    state["mcp_chat_history"] = []
                    state["mcp_agent_notes"] = ""
                    state["mcp_pending_question"] = ""
                    uid = _get_user_id() or "anon"
                    _CHAT_MEMORY.pop(uid, None)
                    _CHAT_DEV_TRACE.pop(uid, None)
                    _CHAT_PERSONS.pop(uid, None)
                    _CHAT_LOCATIONS.pop(uid, None)
                    chat_messages_col.clear()
                    chat_dev_content.content = ""
                    _populate_example_prompts()

                chat_clear_btn.on_click(_clear_chat)

                # Render existing history on page load
                _render_chat_history()
                _populate_example_prompts()

                # Render any existing dev trace
                uid_init = _get_user_id() or "anon"
                _render_dev_trace(_CHAT_DEV_TRACE.get(uid_init, {}))

            # ===========================================================
            # SPECS TAB  (Step 10)
            # ===========================================================
            with ui.tab_panel(tab_specs):
                ui.label("Chart Specs").classes("text-h5 q-mb-md")

                # -- Objects (chart DataFrame) --
                with ui.expansion("Objects", icon="table_chart").classes("w-full"):
                    specs_objects_container = ui.column().classes("w-full")

                # -- Conjunctions --
                with ui.expansion("Conjunctions", icon="group_work").classes("w-full"):
                    specs_conj_container = ui.column().classes("w-full")

                # -- Aspects Graph --
                with ui.expansion("Aspects Graph", icon="grid_on").classes("w-full"):
                    specs_aspects_graph_container = ui.column().classes("w-full")

                # -- Aspects List --
                with ui.expansion("Aspects List", icon="list").classes("w-full"):
                    specs_aspects_list_container = ui.column().classes("w-full")

                def _refresh_specs_tab():
                    """Populate all four specs expansions from the current chart."""
                    import pandas as pd
                    chart_obj = get_chart_object(state)

                    # ---- Objects table ----
                    specs_objects_container.clear()
                    with specs_objects_container:
                        if chart_obj is None:
                            ui.label("No chart loaded.").classes("text-body2 text-grey")
                        else:
                            try:
                                df = chart_obj.to_dataframe()
                                cols = [
                                    {"name": c, "label": c, "field": c, "sortable": True,
                                     "align": "left"}
                                    for c in df.columns
                                ]
                                rows = df.fillna("").astype(str).to_dict("records")
                                ui.table(
                                    columns=cols, rows=rows, row_key="Object",
                                    pagination={"rowsPerPage": 50},
                                ).classes("w-full").props("dense flat")
                            except Exception as exc:
                                ui.label(f"Error: {exc}").classes("text-negative")

                    # ---- Conjunctions table ----
                    specs_conj_container.clear()
                    with specs_conj_container:
                        if chart_obj is None:
                            ui.label("No chart loaded.").classes("text-body2 text-grey")
                        else:
                            conj_rows = getattr(chart_obj, "conj_clusters_rows", None) or []
                            if not conj_rows:
                                ui.label("No conjunction clusters found.").classes(
                                    "text-body2 text-grey"
                                )
                            else:
                                if isinstance(conj_rows[0], dict):
                                    col_names = list(conj_rows[0].keys())
                                else:
                                    col_names = [f"Col{i}" for i in range(len(conj_rows[0]))]
                                cols = [
                                    {"name": c, "label": c, "field": c,
                                     "sortable": True, "align": "left"}
                                    for c in col_names
                                ]
                                rows = [
                                    (r if isinstance(r, dict) else dict(zip(col_names, r)))
                                    for r in conj_rows
                                ]
                                # Stringify values
                                rows = [{k: str(v) for k, v in r.items()} for r in rows]
                                ui.table(
                                    columns=cols, rows=rows,
                                    pagination={"rowsPerPage": 50},
                                ).classes("w-full").props("dense flat")

                    # ---- Aspects Graph table ----
                    specs_aspects_graph_container.clear()
                    with specs_aspects_graph_container:
                        if chart_obj is None:
                            ui.label("No chart loaded.").classes("text-body2 text-grey")
                        else:
                            a_df = getattr(chart_obj, "aspect_df", None)
                            if a_df is None or (isinstance(a_df, pd.DataFrame) and a_df.empty):
                                ui.label("No aspect graph available.").classes(
                                    "text-body2 text-grey"
                                )
                            else:
                                if isinstance(a_df, pd.DataFrame):
                                    # Reset index so the object axis becomes a column
                                    if a_df.index.name or not all(
                                        isinstance(i, int) for i in a_df.index
                                    ):
                                        a_df = a_df.reset_index()
                                    cols = [
                                        {"name": c, "label": c, "field": c,
                                         "sortable": True, "align": "left"}
                                        for c in a_df.columns
                                    ]
                                    rows = a_df.fillna("").astype(str).to_dict("records")
                                else:
                                    # list-of-dicts fallback
                                    col_names = list(a_df[0].keys()) if a_df else []
                                    cols = [
                                        {"name": c, "label": c, "field": c,
                                         "sortable": True, "align": "left"}
                                        for c in col_names
                                    ]
                                    rows = [{k: str(v) for k, v in r.items()} for r in a_df]
                                ui.table(
                                    columns=cols, rows=rows,
                                    pagination={"rowsPerPage": 50},
                                ).classes("w-full").props("dense flat")

                    # ---- Aspects List (clustered) ----
                    specs_aspects_list_container.clear()
                    with specs_aspects_list_container:
                        if chart_obj is None:
                            ui.label("No chart loaded.").classes("text-body2 text-grey")
                        else:
                            edges_major = getattr(chart_obj, "edges_major", None) or []
                            edges_minor = getattr(chart_obj, "edges_minor", None) or []
                            if not edges_major and not edges_minor:
                                ui.label("No aspect data available.").classes(
                                    "text-body2 text-grey"
                                )
                            else:
                                try:
                                    from calc_v2 import build_clustered_aspect_edges
                                    clustered = build_clustered_aspect_edges(
                                        chart_obj, edges_major,
                                    )
                                    rows = []
                                    for a, b, meta in clustered:
                                        row = {"Kind": "Major", "Cluster A": str(a),
                                               "Cluster B": str(b)}
                                        for k, v in meta.items():
                                            row[k] = str(v)
                                        rows.append(row)
                                    for a, b, meta in edges_minor:
                                        row = {"Kind": "Minor", "A": str(a),
                                               "B": str(b)}
                                        for k, v in meta.items():
                                            row[k] = str(v)
                                        rows.append(row)
                                    if rows:
                                        all_keys: list[str] = []
                                        for r in rows:
                                            for k in r:
                                                if k not in all_keys:
                                                    all_keys.append(k)
                                        cols = [
                                            {"name": k, "label": k, "field": k,
                                             "sortable": True, "align": "left"}
                                            for k in all_keys
                                        ]
                                        ui.table(
                                            columns=cols, rows=rows,
                                            pagination={"rowsPerPage": 50},
                                        ).classes("w-full").props("dense flat")
                                    else:
                                        ui.label("No clustered aspects.").classes(
                                            "text-body2 text-grey"
                                        )
                                except Exception as exc:
                                    ui.label(f"Error building aspects list: {exc}").classes(
                                        "text-negative"
                                    )

            # ===========================================================
            # SETTINGS TAB  (Step 10)
            # ===========================================================
            with ui.tab_panel(tab_settings):
                ui.label("Settings").classes("text-h5 q-mb-md")

                with ui.row().classes("w-full items-start gap-8"):
                    # ---- Left column: display settings ----
                    with ui.column().classes("gap-4"):
                        ui.label("Display").classes("text-subtitle1 text-weight-medium")

                        # Label Style
                        settings_label_style = ui.radio(
                            ["Glyph", "Text"],
                            value=("Glyph" if state.get("label_style", "glyph") == "glyph"
                                   else "Text"),
                        ).props("inline")
                        ui.label("Label Style").classes("text-caption text-grey-7 q-mt-n-xs")

                        def _on_label_change(e):
                            new_val = "glyph" if e.value == "Glyph" else "text"
                            state["label_style"] = new_val
                            _rerender_active_tab()

                        settings_label_style.on_value_change(_on_label_change)

                        # Dark Mode
                        settings_dark = ui.switch(
                            "Dark Mode",
                            value=state.get("dark_mode", False),
                        )

                        def _on_dark_change(e):
                            state["dark_mode"] = e.value
                            if e.value:
                                ui.dark_mode().enable()
                            else:
                                ui.dark_mode().disable()
                            _rerender_active_tab()

                        settings_dark.on_value_change(_on_dark_change)

                    # ---- Right column: chart system settings ----
                    with ui.column().classes("gap-4"):
                        ui.label("House System").classes("text-subtitle1 text-weight-medium")

                        settings_house = ui.select(
                            ["placidus", "equal", "whole"],
                            value=state.get("house_system", "placidus"),
                        ).classes("w-40")

                        def _on_house_change(e):
                            state["house_system"] = e.value
                            _rerender_active_tab()

                        settings_house.on_value_change(_on_house_change)

                # Apply dark mode on page load if saved
                if state.get("dark_mode", False):
                    ui.dark_mode().enable()

            # ===========================================================
            # ADMIN TAB  (Step 10)
            # ===========================================================
            if _is_admin:
                with ui.tab_panel(tab_admin):
                    ui.label("Admin — Feedback Reports").classes("text-h5 q-mb-md")

                    admin_status_label = ui.label("").classes("text-body2 text-grey q-mb-sm")
                    admin_reports_container = ui.column().classes("w-full gap-4")

                    def _fetch_admin_reports() -> list:
                        """Fetch feedback reports from Supabase."""
                        try:
                            client = get_supabase()
                            result = (
                                client.table("user_feedback")
                                .select("*")
                                .order("created_at", desc=True)
                                .limit(50)
                                .execute()
                            )
                            return result.data or []
                        except Exception as exc:
                            _log.warning("Failed to fetch admin reports: %s", exc)
                            return []

                    def _mark_viewed(report_id: str):
                        """Mark a single report as viewed."""
                        try:
                            client = get_supabase()
                            client.table("user_feedback").update(
                                {"admin_viewed": True}
                            ).eq("id", report_id).execute()
                        except Exception:
                            pass
                        _load_admin_reports()

                    def _load_admin_reports():
                        """Load and render all reports."""
                        reports = _fetch_admin_reports()
                        new_count = sum(
                            1 for r in reports if not r.get("admin_viewed", False)
                        )
                        admin_status_label.text = (
                            f"{len(reports)} reports ({new_count} new)"
                            if reports else "No reports found."
                        )
                        admin_reports_container.clear()
                        if not reports:
                            with admin_reports_container:
                                ui.label("No feedback reports found.").classes(
                                    "text-body2 text-grey"
                                )
                            return

                        with admin_reports_container:
                            for idx, report in enumerate(reports):
                                _render_admin_report(report, idx)

                    def _render_admin_report(report: dict, index: int):
                        """Render a single feedback report card."""
                        rid = report.get("id", "unknown")
                        created = report.get("created_at", "")
                        email = report.get("user_email", "Unknown")
                        problem_types = report.get("problem_types", [])
                        description = report.get("description", "No description")
                        affected = report.get("affected_features", [])
                        still_having = report.get("still_having_problem", "Unknown")
                        blocking = report.get("blocking_issue", "Unknown")
                        viewed = report.get("admin_viewed", False)

                        status = "\u2705" if viewed else "\U0001F195"  # check / NEW
                        with ui.card().classes("w-full q-pa-sm"):
                            with ui.row().classes("w-full items-center justify-between"):
                                ui.label(
                                    f"{status} Report #{index + 1}"
                                ).classes("text-subtitle2 text-weight-bold")
                                ui.label(f"From: {email}").classes("text-caption text-grey")
                                ui.label(
                                    f"{created[:16] if created else 'Unknown date'}"
                                ).classes("text-caption text-grey")

                            if problem_types:
                                with ui.row().classes("gap-1 q-mt-xs"):
                                    for pt in problem_types:
                                        ui.badge(pt, color="orange").props("outline")

                            ui.label("Description:").classes(
                                "text-caption text-weight-medium q-mt-xs"
                            )
                            ui.label(description).classes("text-body2")

                            if affected:
                                ui.label(
                                    "Affected: " + ", ".join(affected)
                                ).classes("text-caption text-grey q-mt-xs")

                            with ui.row().classes("gap-4 q-mt-xs"):
                                ui.label(
                                    f"Still having problem: {still_having}"
                                ).classes("text-caption")
                                ui.label(
                                    f"Blocking: {blocking}"
                                ).classes("text-caption")

                            # Optional fields
                            suggestions = report.get("suggestions")
                            love = report.get("love_feedback")
                            other = report.get("other_feedback")
                            if suggestions:
                                ui.label(f"Suggestions: {suggestions}").classes(
                                    "text-body2 q-mt-xs"
                                )
                            if love:
                                ui.label(f"What they love: {love}").classes(
                                    "text-body2 q-mt-xs"
                                )
                            if other:
                                ui.label(f"Other: {other}").classes(
                                    "text-body2 q-mt-xs"
                                )

                            # ---- Attachments expansion ----
                            attachments = report.get("attachments", {})
                            if attachments:
                                with ui.expansion(
                                    "Attachments", icon="attach_file"
                                ).classes("w-full q-mt-xs"):
                                    if "chat_history" in attachments:
                                        ui.label("Chat History:").classes(
                                            "text-caption text-weight-medium"
                                        )
                                        try:
                                            chat = json.loads(
                                                attachments["chat_history"]
                                            )
                                            for msg in chat:
                                                role = msg.get("role", "?")
                                                content = msg.get("content", "")
                                                ui.label(
                                                    f"{role}: {content[:500]}"
                                                ).classes("text-body2")
                                        except Exception:
                                            ui.label(
                                                attachments["chat_history"][:2000]
                                            ).classes("text-body2")

                                    if "chart_image" in attachments:
                                        ui.label("Chart Image:").classes(
                                            "text-caption text-weight-medium q-mt-xs"
                                        )
                                        try:
                                            ui.image(
                                                f"data:image/png;base64,"
                                                f"{attachments['chart_image']}"
                                            ).classes("w-64")
                                        except Exception as exc:
                                            ui.label(
                                                f"Could not decode: {exc}"
                                            ).classes("text-negative")

                                    if "screenshot" in attachments:
                                        ui.label("Screenshot:").classes(
                                            "text-caption text-weight-medium q-mt-xs"
                                        )
                                        try:
                                            ui.image(
                                                f"data:image/png;base64,"
                                                f"{attachments['screenshot']}"
                                            ).classes("w-64")
                                        except Exception as exc:
                                            ui.label(
                                                f"Could not decode: {exc}"
                                            ).classes("text-negative")

                                    if "error_messages" in attachments:
                                        ui.label("Error Messages:").classes(
                                            "text-caption text-weight-medium q-mt-xs"
                                        )
                                        ui.code(
                                            attachments["error_messages"]
                                        ).classes("w-full")

                                    if "copypaste_text" in attachments:
                                        ui.label("Copy/Pasted Text:").classes(
                                            "text-caption text-weight-medium q-mt-xs"
                                        )
                                        ui.label(
                                            attachments["copypaste_text"]
                                        ).classes("text-body2")

                            # ---- App state snapshot expansion ----
                            app_state = report.get("app_state_snapshot", {})
                            if app_state:
                                with ui.expansion(
                                    "App State Snapshot", icon="data_object"
                                ).classes("w-full q-mt-xs"):
                                    ui.code(
                                        json.dumps(app_state, indent=2, default=str)
                                    ).classes("w-full")

                            # ---- Mark as Viewed button ----
                            if not viewed:
                                ui.button(
                                    "Mark as Viewed",
                                    icon="check",
                                    on_click=lambda _rid=rid: _mark_viewed(_rid),
                                ).props("flat dense color=primary").classes("q-mt-xs")

                    # Refresh button + initial load
                    with ui.row().classes("gap-2 q-mb-sm"):
                        ui.button(
                            "Refresh Reports",
                            icon="refresh",
                            on_click=lambda: _load_admin_reports(),
                        ).props("flat")

                    _load_admin_reports()

        # ===============================================================
        # CHART RENDERING HELPERS
        # ===============================================================

        def _render_chart_png(mode: str) -> Optional[bytes]:
            """Render the current chart as PNG bytes in the given mode.

            mode: "Standard Chart" or "Circuits"
            Handles both single-chart and biwheel rendering.
            """
            from src.chart_adapter import (
                render_chart_image, render_biwheel_image,
                RenderToggles, ChartResult,
                compute_combined_circuits, compute_inter_chart_aspects,
            )

            chart_obj = get_chart_object(state)
            if chart_obj is None:
                return None

            # Check for biwheel mode
            is_biwheel = (
                (state.get("synastry_mode") or state.get("transit_mode"))
                and state.get("last_chart_2_json") is not None
            )
            chart_2_obj = get_chart_2_object(state) if is_biwheel else None
            is_biwheel = is_biwheel and chart_2_obj is not None

            # Build toggles from state
            toggles = RenderToggles(
                compass_inner=state.get("compass", True),
                chart_mode=mode,
                pattern_toggles={int(k): v for k, v in state.get("pattern_toggles", {}).items()},
                shape_toggles=state.get("shape_toggles", {}),
                singleton_toggles=state.get("singleton_toggles", {}),
                aspect_toggles=state.get("aspect_toggles", {}),
                label_style=state.get("label_style", "glyph"),
                dark_mode=state.get("dark_mode", False),
                house_system=(state.get("house_system", "placidus") or "placidus").lower(),
                synastry_inter=state.get("synastry_inter", True),
                synastry_chart1=state.get("synastry_chart1", False),
                synastry_chart2=state.get("synastry_chart2", False),
            )

            if is_biwheel:
                try:
                    combined_data = None
                    inter_aspects = None

                    if mode == "Circuits":
                        submode = state.get("circuit_submode", "Combined")
                        if submode == "Combined":
                            combined_data = compute_combined_circuits(chart_obj, chart_2_obj)
                        # For "Connected" submode we'd need render_biwheel_connected_circuits
                        # which is a more complex feature — leave as Combined for now
                    else:
                        # Standard biwheel — compute inter-chart aspects
                        inter_aspects = compute_inter_chart_aspects(chart_obj, chart_2_obj)

                    return render_biwheel_image(
                        chart_obj,
                        chart_2_obj,
                        toggles=toggles,
                        combined_data=combined_data,
                        inter_chart_aspects=inter_aspects,
                    )
                except Exception as exc:
                    _log.exception("Biwheel render failed")
                    return None

            # Single-chart path
            result = ChartResult(chart=chart_obj)
            result.positions = getattr(chart_obj, "positions", {}) or {}
            result.patterns = getattr(chart_obj, "aspect_groups", None) or []
            result.shapes = getattr(chart_obj, "shapes", None) or []
            result.singleton_map = getattr(chart_obj, "singleton_map", None) or {}
            result.filaments = getattr(chart_obj, "filaments", None) or []
            result.major_edges_all = getattr(chart_obj, "major_edges_all", None) or []
            result.edges_major = getattr(chart_obj, "edges_major", None) or []
            result.edges_minor = getattr(chart_obj, "edges_minor", None) or []

            try:
                return render_chart_image(result, toggles)
            except Exception as exc:
                _log.exception("Chart render failed")
                return None

        def _display_chart_in(container, png_bytes: Optional[bytes], *, show_info: bool = True):
            """Display a chart PNG inside the given container."""
            container.clear()
            if png_bytes is None:
                with container:
                    ui.label("No chart computed yet.").classes("text-body2 text-grey q-pa-md")
                return
            with container:
                if show_info:
                    chart_obj = get_chart_object(state)
                    chart_2_obj = get_chart_2_object(state)
                    if chart_obj is not None:
                        loc_dt = getattr(chart_obj, "display_datetime", None)
                        name = state.get("name") or form.get("name") or ""
                        city = state.get("city") or form.get("city") or ""
                        unknown = getattr(chart_obj, "unknown_time", False)
                        if loc_dt:
                            time_str = "Unknown time" if unknown else f"{loc_dt:%I:%M %p}"
                            info = f"{name} — {loc_dt:%B %d, %Y} {time_str} — {city}"
                            ui.label(info).classes(
                                "text-subtitle1 text-weight-medium q-mb-sm"
                            )

                    # Show Chart 2 info if biwheel
                    if chart_2_obj is not None and (
                        state.get("synastry_mode") or state.get("transit_mode")
                    ):
                        c2_name = state.get("chart_2_profile_name") or "Transits"
                        c2_dt = getattr(chart_2_obj, "display_datetime", None)
                        if c2_dt:
                            c2_info = f"Chart 2: {c2_name} — {c2_dt:%B %d, %Y %I:%M %p}"
                        else:
                            c2_info = f"Chart 2: {c2_name}"
                        ui.label(c2_info).classes(
                            "text-body2 text-grey-7 q-mb-sm"
                        )

                b64 = base64.b64encode(png_bytes).decode()
                ui.html(
                    f'<img src="data:image/png;base64,{b64}" '
                    f'style="width:100%; max-width:720px; '
                    f'image-rendering:auto; display:block; margin:0 auto" />'
                )

        def _rerender_active_tab():
            """Re-render chart in the currently active tab with current toggles."""
            active = tabs.value
            chart_obj = get_chart_object(state)
            if chart_obj is None:
                return

            # Update events panel
            _refresh_events()

            # Update synastry/biwheel UI visibility
            is_biwheel = (
                (state.get("synastry_mode") or state.get("transit_mode"))
                and state.get("last_chart_2_json") is not None
            )
            synastry_aspects_exp.set_visibility(is_biwheel and active == "Standard Chart")
            cir_submode_row.set_visibility(is_biwheel and active == "Circuits")

            if active == "Standard Chart":
                png = _render_chart_png("Standard Chart")
                _display_chart_in(std_chart_container, png)
            elif active == "Circuits":
                # Rebuild circuit toggle checkboxes so they reflect current chart
                _build_circuit_toggles()
                png = _render_chart_png("Circuits")
                _display_chart_in(cir_chart_container, png)
            elif active == "Rulers":
                _render_rulers_graph()
            elif active == "Specs":
                _refresh_specs_tab()

            # Refresh planet profiles drawer
            _refresh_drawer()

        def _refresh_events():
            """Update the events panel with nearby events for the current chart."""
            chart_obj = get_chart_object(state)
            if chart_obj is None:
                events_container.content = ""
                return
            try:
                utc_dt = getattr(chart_obj, "utc_datetime", None)
                if utc_dt is None:
                    events_container.content = ""
                    return
                from event_lookup_v2 import build_events_html
                html = build_events_html(utc_dt)
                events_container.content = html
            except Exception:
                events_container.content = ""

        # Re-render when tab changes
        def _on_tab_change(e):
            _rerender_active_tab()

        tabs.on_value_change(_on_tab_change)

        # ---------------------------------------------------------------
        # Calculate handler
        # ---------------------------------------------------------------
        async def _on_calculate():
            status_label.set_visibility(False)

            # Validate required fields
            name = (form.get("name") or "").strip()
            city = (form.get("city") or "").strip()
            if not name:
                status_label.text = "Name is required."
                status_label.classes(replace="text-body2 text-negative")
                status_label.set_visibility(True)
                return
            if not city:
                status_label.text = "City of Birth is required."
                status_label.classes(replace="text-body2 text-negative")
                status_label.set_visibility(True)
                return

            # Parse time
            unknown_time = form.get("unknown_time", False)
            hour_12_val   = form.get("hour_12", "--")
            minute_str_val = form.get("minute_str", "--")
            ampm_val       = form.get("ampm", "--")

            if unknown_time or hour_12_val == "--" or minute_str_val == "--" or ampm_val == "--":
                birth_hour_24 = 12
                birth_minute  = 0
                is_unknown    = True
            else:
                h12 = int(hour_12_val)
                birth_minute = int(minute_str_val)
                birth_hour_24 = (0 if h12 == 12 else h12) if ampm_val == "AM" else (12 if h12 == 12 else h12 + 12)
                is_unknown = False

            month_idx = MONTH_NAMES.index(form.get("month_name", "January")) + 1
            year = int(form.get("year", 2000))
            day  = int(form.get("day", 1))

            # Show progress
            status_label.text = "Geocoding city…"
            status_label.classes(replace="text-body2 text-grey-7")
            status_label.set_visibility(True)
            calc_btn.disable()

            try:
                # --- Geocode ---
                from src.geocoding import geocode_city_with_timezone
                lat, lon, tz_name, formatted = geocode_city_with_timezone(city)
                if lat is None or lon is None or tz_name is None:
                    status_label.text = f"Could not geocode '{city}'. Please try a more specific city name."
                    status_label.classes(replace="text-body2 text-negative")
                    status_label.set_visibility(True)
                    calc_btn.enable()
                    return

                status_label.text = "Computing chart…"
                await ui.run_javascript("")  # flush UI update

                # --- Compute chart ---
                from src.chart_adapter import ChartInputs, compute_chart

                inputs = ChartInputs(
                    name=name,
                    year=year, month=month_idx, day=day,
                    hour_24=birth_hour_24, minute=birth_minute,
                    city=city,
                    lat=lat, lon=lon, tz_name=tz_name,
                    unknown_time=is_unknown,
                    house_system=(state.get("house_system", "placidus") or "placidus").lower(),
                    gender=form.get("gender"),
                )
                result = compute_chart(inputs)

                if result.error:
                    status_label.text = f"Calculation error: {result.error}"
                    status_label.classes(replace="text-body2 text-negative")
                    status_label.set_visibility(True)
                    calc_btn.enable()
                    return

                status_label.text = "Rendering chart…"
                await ui.run_javascript("")  # flush UI update

                # --- Store result in per-user state ---
                state["last_chart_json"] = result.chart.to_json() if result.chart else None
                state["chart_ready"] = True
                state["name"] = name
                state["city"] = city
                state["year"] = year
                state["month_name"] = MONTH_NAMES[month_idx - 1]
                state["day"] = day
                state["current_lat"] = lat
                state["current_lon"] = lon
                state["current_tz_name"] = tz_name

                # Reset circuit toggles for the new chart
                state["pattern_toggles"] = {}
                state["shape_toggles"] = {}
                state["singleton_toggles"] = {}

                # Build circuit toggles UI
                _build_circuit_toggles()

                # Render chart in the active tab
                _rerender_active_tab()

                # Collapse form after successful chart
                birth_exp.close()
                status_label.set_visibility(False)
                # Pre-fill save name so user can quickly save
                save_name_input.value = name

            except Exception as exc:
                _log.exception("Chart calculation failed")
                status_label.text = f"Unexpected error: {exc}"
                status_label.classes(replace="text-body2 text-negative")
                status_label.set_visibility(True)
            finally:
                calc_btn.enable()

        calc_btn.on_click(_on_calculate)

        # ---------------------------------------------------------------
        # Initial render — if chart already in state from previous session
        # ---------------------------------------------------------------
        if get_chart_object(state) is not None:
            _build_circuit_toggles()
            _rerender_active_tab()

        # ===============================================================
        # FEEDBACK FAB + DIALOG  (Step 11)
        # ===============================================================
        # The floating action button sits at bottom-right of every tab.
        _PROBLEM_TYPES = [
            "The chat said something ridiculous",
            "Unable to use a feature",
            "Got an error message",
            "Login problem",
            "Problem with saving chart data",
            "Other",
        ]
        _AFFECTED_FEATURES = [
            "Single chart", "Synastry chart", "Transit chart",
            "Interactive Chart", "Regular Read-Only Chart",
            "Standard Chart Mode", "Circuits Mode",
            "Circuit/Shape Toggles", "Ruler Chains",
            "Profiles (save/load/delete)", "Birth Data Entry",
            "Login/Account/Password", "Now Button", "Chatbot",
        ]

        with ui.dialog().classes("w-full") as feedback_dlg, \
                ui.card().classes("w-full").style("max-width: 700px"):
            ui.label("Bug Report / Feedback").classes("text-h5 q-mb-sm")
            ui.label(
                "Help us improve Rosetta! Report bugs, share feedback, "
                "or suggest features."
            ).classes("text-body2 text-grey q-mb-md")

            fb_email = ui.input(
                "Your email",
                value=state.get("supabase_user_email", "") or "",
            ).classes("w-full")

            ui.label("What type of problem is this?").classes(
                "text-subtitle2 q-mt-md"
            )
            fb_problems: dict[str, ui.checkbox] = {}
            with ui.row().classes("w-full flex-wrap gap-x-4"):
                for pt in _PROBLEM_TYPES:
                    fb_problems[pt] = ui.checkbox(pt)

            fb_description = ui.textarea(
                "Describe the problem",
                placeholder=(
                    "Please describe what happened, what you expected, "
                    "and any steps to reproduce…"
                ),
            ).classes("w-full q-mt-sm")

            ui.label("Affected features").classes("text-subtitle2 q-mt-md")
            fb_features: dict[str, ui.checkbox] = {}
            with ui.row().classes("w-full flex-wrap gap-x-4"):
                for feat in _AFFECTED_FEATURES:
                    fb_features[feat] = ui.checkbox(feat)

            with ui.row().classes("w-full gap-4 q-mt-sm"):
                fb_still = ui.radio(
                    ["Yes", "No", "Not sure"],
                    value="Not sure",
                ).props("inline")
                ui.label("Still having the problem?").classes(
                    "text-caption text-grey self-center"
                )

            with ui.row().classes("w-full gap-4"):
                fb_blocking = ui.radio(
                    ["Yes", "No", "Somewhat"],
                    value="No",
                ).props("inline")
                ui.label("Blocking you from using the app?").classes(
                    "text-caption text-grey self-center"
                )

            fb_suggestions = ui.textarea(
                "Suggestions for future features",
                placeholder="Any features you wish the app had?",
            ).classes("w-full q-mt-sm")

            fb_love = ui.textarea(
                "Anything you love about the app?",
                placeholder="Let us know what's working well!",
            ).classes("w-full q-mt-sm")

            fb_other = ui.textarea(
                "Other feedback",
                placeholder="Anything else you'd like to share…",
            ).classes("w-full q-mt-sm")

            fb_status_label = ui.label("").classes("text-body2")
            fb_status_label.set_visibility(False)

            with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
                ui.button("Cancel", on_click=feedback_dlg.close).props("flat")

                async def _submit_feedback():
                    email = fb_email.value or ""
                    if not email.strip():
                        fb_status_label.text = "Please enter your email."
                        fb_status_label.classes(replace="text-body2 text-negative")
                        fb_status_label.set_visibility(True)
                        return
                    sel_problems = [p for p, cb in fb_problems.items() if cb.value]
                    if not sel_problems:
                        fb_status_label.text = "Select at least one problem type."
                        fb_status_label.classes(replace="text-body2 text-negative")
                        fb_status_label.set_visibility(True)
                        return
                    desc = (fb_description.value or "").strip()
                    if not desc:
                        fb_status_label.text = "Please describe the problem."
                        fb_status_label.classes(replace="text-body2 text-negative")
                        fb_status_label.set_visibility(True)
                        return

                    sel_features = [f for f, cb in fb_features.items() if cb.value]
                    import datetime as _dtm
                    payload = {
                        "user_email": email.strip(),
                        "user_id": _get_user_id(),
                        "problem_types": sel_problems,
                        "description": desc,
                        "affected_features": sel_features,
                        "attachments": {},
                        "still_having_problem": fb_still.value,
                        "blocking_issue": fb_blocking.value,
                        "suggestions": (fb_suggestions.value or "").strip() or None,
                        "love_feedback": (fb_love.value or "").strip() or None,
                        "other_feedback": (fb_other.value or "").strip() or None,
                        "app_state_snapshot": {},
                        "admin_viewed": False,
                        "created_at": _dtm.datetime.utcnow().isoformat(),
                    }
                    try:
                        client = get_supabase()
                        result = client.table("user_feedback").insert(payload).execute()
                        if result.data:
                            fb_status_label.text = (
                                "Feedback submitted! Thank you for helping "
                                "improve Rosetta."
                            )
                            fb_status_label.classes(
                                replace="text-body2 text-positive"
                            )
                            fb_status_label.set_visibility(True)
                            await ui.run_javascript("", timeout=1.5)
                            feedback_dlg.close()
                        else:
                            fb_status_label.text = "Submission failed."
                            fb_status_label.classes(
                                replace="text-body2 text-negative"
                            )
                            fb_status_label.set_visibility(True)
                    except Exception as exc:
                        fb_status_label.text = f"Submission failed: {exc}"
                        fb_status_label.classes(
                            replace="text-body2 text-negative"
                        )
                        fb_status_label.set_visibility(True)

                ui.button(
                    "Submit Feedback", icon="send",
                    on_click=_submit_feedback,
                ).props("color=primary")

        # Floating action button — always visible
        ui.button(
            icon="bug_report",
            on_click=feedback_dlg.open,
        ).props(
            "fab color=orange"
        ).classes("fixed-bottom-right").style(
            "position: fixed; bottom: 24px; right: 24px; z-index: 9999"
        )


def _handle_unknown_time(is_unknown: bool, form: dict, hour_sel, min_sel, ampm_sel):
    """Toggle time selectors and form values when Unknown Time changes."""
    if is_unknown:
        form["hour_12"]    = "--"
        form["minute_str"] = "--"
        form["ampm"]       = "--"
        hour_sel.value  = "--"
        min_sel.value   = "--"
        ampm_sel.value  = "--"
        hour_sel.disable()
        min_sel.disable()
        ampm_sel.disable()
    else:
        if form.get("hour_12") == "--":
            form["hour_12"] = "12"
            hour_sel.value = "12"
        if form.get("minute_str") == "--":
            form["minute_str"] = "00"
            min_sel.value = "00"
        if form.get("ampm") == "--":
            form["ampm"] = "AM"
            ampm_sel.value = "AM"
        hour_sel.enable()
        min_sel.enable()
        ampm_sel.enable()


async def _do_logout():
    _clear_session()
    ui.navigate.to("/login")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    # Serve the pngs/ directory so background images are reachable at /pngs/...
    app.add_static_files('/pngs', 'pngs')
    port = int(os.environ.get("PORT", 8080))
    ui.run(
        port=port,
        title="Rosetta",
        storage_secret=_STORAGE_SECRET,
        reload=False,         # disable reload for Windows compatibility
        show=False,           # don't auto-open browser
    )
