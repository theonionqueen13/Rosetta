# auth_ui.py
"""
Supabase authentication gate for Streamlit.

Usage (at the top of your page, after st.set_page_config):
    from auth_ui import render_auth_gate
    current_user_id = render_auth_gate()
    # everything below only runs when the user is signed in

Features:
  - Email + Password sign-in / sign-up
  - Magic Link (passwordless email)
  - Google OAuth (one-click; requires Google provider enabled in Supabase dashboard)
  - Auto-detects the OAuth callback (?code=... in URL)
  - Logout button shown in the sidebar when authenticated
"""
from __future__ import annotations
import socket
import streamlit as st
from supabase_client import get_supabase


def _format_network_error(exc: Exception) -> str:
    """Format helpful guidance for network/DNS failures."""
    if isinstance(exc, socket.gaierror):
        host = st.secrets.get("supabase", {}).get("url", "").split("//")[-1].split("/")[0]
        return (
            f"Network/DNS error connecting to Supabase host '{host}'. "
            "This usually means your machine cannot resolve the hostname or has no internet access. "
            "Try running `nslookup {host}` or `ping {host}` from a terminal, and check your VPN/proxy settings."
        )
    return str(exc)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _store_session(auth_response) -> str:
    """Persist session tokens and user info to st.session_state. Returns user_id."""
    session = auth_response.session
    user    = auth_response.user
    st.session_state["supabase_session"] = {
        "access_token":  session.access_token,
        "refresh_token": session.refresh_token,
    }
    st.session_state["supabase_user_id"]    = str(user.id)
    st.session_state["supabase_user_email"] = user.email
    return str(user.id)


def _logout() -> None:
    """Signs the user out and wipes session state."""
    try:
        get_supabase().auth.sign_out()
    except Exception:
        pass
    for key in ("supabase_session", "supabase_user_id", "supabase_user_email"):
        st.session_state.pop(key, None)


def _sidebar_logout() -> None:
    """Renders the logout button + user info in the sidebar."""
    email = st.session_state.get("supabase_user_email", "")
    with st.sidebar:
        st.markdown(f"👤 **{email}**")
        if st.button("Sign Out", key="auth_signout_btn"):
            _logout()
            st.rerun()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_auth_gate() -> str:
    """
    Checks authentication state. Returns the user_id string when authenticated.
    If the user is NOT authenticated, renders the login UI and calls st.stop(),
    so nothing below this call renders.

    Google OAuth note: you must add http://localhost:8501 (and your deployed URL)
    to the *Redirect URLs* allow-list in Supabase → Authentication → URL Configuration.
    The redirect_url value is read from st.secrets['auth']['redirect_url'].
    """

    # ------------------------------------------------------------------
    # 1. Handle OAuth callback code arriving in the URL
    # ------------------------------------------------------------------
    code = st.query_params.get("code", None)
    if code and not st.session_state.get("supabase_user_id"):
        try:
            response = get_supabase().auth.exchange_code_for_session({"auth_code": code})
            _store_session(response)
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            st.error(f"OAuth sign-in failed: {e}")
            st.query_params.clear()

    # ------------------------------------------------------------------
    # 2. Already authenticated
    # ------------------------------------------------------------------
    if st.session_state.get("supabase_user_id"):
        _sidebar_logout()
        return st.session_state["supabase_user_id"]

    # ------------------------------------------------------------------
    # 3. Show login UI
    # ------------------------------------------------------------------
    _render_login_ui()
    st.stop()
    return ""  # unreachable; satisfies type-checker


def _render_login_ui() -> None:
    """Renders the full sign-in / sign-up / magic-link / Google UI."""
    st.markdown("## 🌙 Rosetta")
    st.markdown("Please sign in to continue.")
    st.markdown("---")

    tab_signin, tab_signup, tab_magic, tab_google = st.tabs(
        ["Sign In", "Create Account", "Magic Link", "Google"]
    )

    # ------------------------------------------------------------------
    # Sign In
    # ------------------------------------------------------------------
    with tab_signin:
        st.markdown("#### Sign in with email & password")
        email    = st.text_input("Email",    key="signin_email")
        password = st.text_input("Password", type="password", key="signin_password")
        if st.button("Sign In", key="btn_signin", use_container_width=True):
            if not email or not password:
                st.error("Please enter your email and password.")
            else:
                try:
                    resp = get_supabase().auth.sign_in_with_password(
                        {"email": email, "password": password}
                    )
                    _store_session(resp)
                    st.rerun()
                except Exception as e:
                    st.error(f"Sign in failed: {_format_network_error(e)}")

    # ------------------------------------------------------------------
    # Sign Up
    # ------------------------------------------------------------------
    with tab_signup:
        st.markdown("#### Create a new account")
        email_su    = st.text_input("Email",                    key="signup_email")
        password_su = st.text_input("Password (min 6 chars)",   type="password", key="signup_password")
        if st.button("Create Account", key="btn_signup", use_container_width=True):
            if not email_su or not password_su:
                st.error("Please fill in both fields.")
            elif len(password_su) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    resp = get_supabase().auth.sign_up(
                        {"email": email_su, "password": password_su}
                    )
                    if resp.user:
                        st.success(
                            "Account created! Check your email to confirm, then sign in here."
                        )
                    else:
                        st.error("Sign up failed — please try again.")
                except Exception as e:
                    st.error(f"Sign up failed: {_format_network_error(e)}")

    # ------------------------------------------------------------------
    # Magic Link (passwordless)
    # ------------------------------------------------------------------
    with tab_magic:
        st.markdown("#### Passwordless sign-in")
        st.caption(
            "Enter your email and we'll send a one-click sign-in link. "
            "No password needed — just click the link in the email."
        )
        email_ml = st.text_input("Email", key="magic_email")
        if st.button("Send Magic Link", key="btn_magic", use_container_width=True):
            if not email_ml:
                st.error("Please enter your email.")
            else:
                try:
                    get_supabase().auth.sign_in_with_otp(
                        {"email": email_ml, "options": {"should_create_user": True}}
                    )
                    st.success(
                        f"Magic link sent to **{email_ml}**. "
                        "Click the link in the email — this page will sign you in automatically."
                    )
                except Exception as e:
                    st.error(f"Failed to send magic link: {_format_network_error(e)}")

    # ------------------------------------------------------------------
    # Google OAuth
    # ------------------------------------------------------------------
    with tab_google:
        st.markdown("#### Sign in with Google")
        st.caption(
            "You'll be taken to Google to sign in, then returned here automatically. "
            "*(Requires Google provider to be enabled in your Supabase project.)*"
        )

        # Determine the redirect URL (where Supabase sends the user back after OAuth)
        redirect_url = (
            st.secrets.get("auth", {}).get("redirect_url", "http://localhost:8501")
        )

        if st.button("🔴 Sign in with Google", key="btn_google", use_container_width=True):
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
                # Redirect the browser to Google's sign-in page
                st.markdown(
                    f'<meta http-equiv="refresh" content="0; url={resp.url}">',
                    unsafe_allow_html=True,
                )
                st.info("Redirecting to Google… if nothing happens, click the link below.")
                st.markdown(f"[Open Google Sign-In]({resp.url})")
                st.stop()
            except Exception as e:
                st.error(f"Google sign-in unavailable: {e}")
                st.caption(
                    "Make sure the Google provider is enabled in "
                    "Supabase → Authentication → Providers."
                )
