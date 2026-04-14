# src/ui/auth.py
"""
Authentication helpers and login page for Rosetta.

Extracted from app.py — contains:
  - Session management (store, clear, refresh, get_user_id, is_expired)
  - login_page() with email/password, sign-up, magic link, Google OAuth
  - _do_logout() handler
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from nicegui import app, ui

from config import get_secret
from src.db.supabase_client import get_supabase

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def store_session_nicegui(auth_response) -> str:
    """Persist Supabase session into app.storage.user. Returns user_id."""
    session = auth_response.session
    user = auth_response.user
    app.storage.user["supabase_session"] = {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expires_at": session.expires_at,
    }
    app.storage.user["supabase_user_id"] = str(user.id)
    app.storage.user["supabase_user_email"] = user.email
    return str(user.id)


def clear_session():
    """Wipe auth state and sign out from Supabase."""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in ("supabase_session", "supabase_user_id", "supabase_user_email"):
        app.storage.user.pop(key, None)


def get_user_id() -> Optional[str]:
    """Return the current user_id from storage, or None if not authenticated."""
    return app.storage.user.get("supabase_user_id")


def session_is_expired() -> bool:
    """Check whether the stored access token has expired."""
    session = app.storage.user.get("supabase_session")
    if not session:
        return True
    expires_at = session.get("expires_at")
    if not expires_at:
        return True
    return time.time() >= (expires_at - 60)


def try_refresh_session() -> bool:
    """Attempt to refresh the Supabase session using the stored refresh token.

    Returns True if the session was refreshed successfully, False otherwise.
    """
    session = app.storage.user.get("supabase_session")
    if not session or not session.get("refresh_token"):
        return False
    try:
        resp = get_supabase().auth.refresh_session(session["refresh_token"])
        if resp and resp.session:
            store_session_nicegui(resp)
            return True
    except Exception as exc:
        _log.warning("Session refresh failed: %s", exc)
    return False


async def do_logout():
    """Sign out and redirect to login."""
    clear_session()
    ui.navigate.to("/login")


# ---------------------------------------------------------------------------
# /login page
# ---------------------------------------------------------------------------

@ui.page("/login")
async def login_page():
    """Full login page with email/password, sign-up, magic link, Google OAuth."""
    if get_user_id() and not session_is_expired():
        ui.navigate.to("/")
        return

    # --- Handle OAuth callback (?code= query param) ---
    try:
        code = await ui.run_javascript(
            "new URLSearchParams(window.location.search).get('code')",
            timeout=3.0,
        )
    except Exception:
        code = None
    if code:
        try:
            resp = get_supabase().auth.exchange_code_for_session({"auth_code": code})
            store_session_nicegui(resp)
            await ui.run_javascript("history.replaceState(null, '', '/login')")
            ui.navigate.to("/")
            return
        except Exception as exc:
            _log.warning("OAuth code exchange failed: %s", exc)

    ui.add_head_html("""
<style>
:root {
    --rosetta-tan: #867557;
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

                with ui.tabs().classes("w-full login-tab") as tabs:
                    tab_signin = ui.tab("Sign In").classes("login-tan")
                    tab_signup = ui.tab("Create Account").classes("login-tan")
                    tab_magic  = ui.tab("Magic Link").classes("login-tan")
                    tab_google = ui.tab("Google").classes("login-tan")

                signin_email = {"value": ""}
                signin_password = {"value": ""}
                signup_email = {"value": ""}
                signup_password = {"value": ""}
                magic_email = {"value": ""}

                status_container = ui.column().classes("w-full")

                def _show_error(msg: str):
                    """Display a red error message in the status area."""
                    status_container.clear()
                    with status_container:
                        ui.label(msg).classes("text-negative text-body2")

                def _show_success(msg: str):
                    """Display a green success message in the status area."""
                    status_container.clear()
                    with status_container:
                        ui.label(msg).classes("text-positive text-body2")

                def _clear_status():
                    """Clear any status messages from the login form."""
                    status_container.clear()

                async def _do_sign_in():
                    """Authenticate the user with email and password."""
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
                        store_session_nicegui(resp)
                        ui.navigate.to("/")
                    except Exception as e:
                        _show_error(f"Sign in failed: {e}")

                async def _do_sign_up():
                    """Register a new account with email, password, and confirmation."""
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

                async def _do_magic_link():
                    """Send a passwordless magic-link email to the user."""
                    _clear_status()
                    email = magic_email["value"].strip()
                    if not email:
                        _show_error("Please enter your email.")
                        return
                    try:
                        get_supabase().auth.sign_in_with_otp(
                            {"email": email, "options": {"should_create_user": True}}
                        )
                        _show_success(
                            f"Magic link sent to {email}. "
                            "Click the link in the email to sign in."
                        )
                    except Exception as e:
                        _show_error(f"Failed to send magic link: {e}")

                async def _do_google_oauth():
                    """Initiate Google OAuth sign-in flow."""
                    _clear_status()
                    redirect_url = get_secret(
                        "auth", "redirect_url", default="http://localhost:8080"
                    )
                    try:
                        resp = get_supabase().auth.sign_in_with_oauth(
                            {
                                "provider": "google",
                                "options": {
                                    "redirect_to": redirect_url,
                                    "query_params": {
                                        "access_type": "offline",
                                        "prompt": "consent",
                                    },
                                },
                            }
                        )
                        await ui.run_javascript(
                            f'window.location.href = "{resp.url}"'
                        )
                    except Exception as e:
                        _show_error(f"Google sign-in unavailable: {e}")

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

                    with ui.tab_panel(tab_magic).classes("login-tab-panel"):
                        ui.label("Passwordless sign-in").classes("text-subtitle2 q-mb-sm login-tan")
                        ui.label(
                            "Enter your email and we'll send a one-click sign-in link. "
                            "No password needed."
                        ).classes("text-caption login-tan q-mb-sm")
                        magic_input = ui.input("Email").classes("w-full login-input").on(
                            "update:model-value", lambda e: magic_email.update(value=e.args)
                        )
                        magic_input.on("keydown.enter", _do_magic_link)
                        ui.button("Send Magic Link", on_click=_do_magic_link).classes("w-full q-mt-md rosetta-button")

                    with ui.tab_panel(tab_google).classes("login-tab-panel"):
                        ui.label("Sign in with Google").classes("text-subtitle2 q-mb-sm login-tan")
                        ui.label(
                            "You'll be taken to Google to sign in, then returned here automatically."
                        ).classes("text-caption login-tan q-mb-sm")
                        ui.button(
                            "Sign in with Google", icon="login",
                            on_click=_do_google_oauth,
                        ).classes("w-full q-mt-md rosetta-button")
