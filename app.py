# app.py
"""
NiceGUI entry point for Rosetta.

Usage:
    python app.py          # local dev  (port 8080)
    PORT=8080 python app.py  # Railway / Docker

Routes:
    /        — main application page (requires auth)
    /login   — email/password sign-in and sign-up
    /health  — JSON health-check for Railway
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi.responses import JSONResponse
from nicegui import app, ui

from src.db.supabase_client import get_supabase
from src.nicegui_state import ensure_state
from src.ui.auth import (
    clear_session, get_user_id,
    session_is_expired, try_refresh_session, do_logout,
    login_page,                 # registers @ui.page("/login")
)
from src.ui.chart_display import (
    render_chart_png, display_chart_in,
    rerender_circuits_chart_only, rerender_active_tab,
    refresh_events,
)


# ---------------------------------------------------------------------------
# Storage secret (for app.storage.user — encrypted browser-side cookie)
# ---------------------------------------------------------------------------
_STORAGE_SECRET = os.environ["NICEGUI_STORAGE_SECRET"]

# ---------------------------------------------------------------------------
# Health-check endpoint (for Railway / container orchestration)
# ---------------------------------------------------------------------------

@app.get("/health")
async def _health():
    """Health-check endpoint returning JSON status."""
    return JSONResponse({"status": "ok", "version": "PHASE_A_TEST_2026"})


# ---------------------------------------------------------------------------
# Static file mounts — MUST come before @ui.page decorators to avoid route shadowing
# ---------------------------------------------------------------------------
app.add_static_files('/pngs', 'pngs')
app.add_static_files('/d3chart', 'src/interactive_chart')


# ---------------------------------------------------------------------------
# / main page  (auth-guarded)
# ---------------------------------------------------------------------------

@ui.page("/")
def main_page():
    """Build and serve the main Rosetta single-page application."""
    # --- Auth guard ---
    user_id = get_user_id()
    if not user_id:
        ui.navigate.to("/login")
        return

    # --- Session refresh ---
    if session_is_expired():
        if not try_refresh_session():
            clear_session()
            ui.navigate.to("/login")
            return

    email = app.storage.user.get("supabase_user_email", "")
    state = ensure_state()

    # --- Apply dark mode immediately on page load (before any tabs are built) ---
    if state.get("dark_mode", False):
        ui.dark_mode().enable()

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
    # LAYOUT — drawer + header bar
    # ===================================================================
    from src.ui.layout import build as _build_layout
    _layout = _build_layout(state, email=email, do_logout=do_logout)
    drawer = _layout["drawer"]
    _refresh_drawer = _layout["refresh_drawer"]

    # ===================================================================
    # MAIN CONTENT
    # ===================================================================
    with ui.column().classes("w-full items-center q-pa-md").style("max-width: 1100px; margin: 0 auto"):

        # ---- Transit / synastry / shared controls ----
        from src.ui.transit_controls import build as _build_transit
        _tc = _build_transit(
            state, form,
            rerender_active_tab=lambda: _rerender_active_tab(),
            build_circuit_toggles=lambda: _build_circuit_toggles(),
            refresh_drawer=_refresh_drawer,
            get_user_id=get_user_id,
        )
        _on_transit_toggle = _tc["on_transit_toggle"]
        events_container = _tc["events_container"]
        _set_late_refs = _tc["set_late_refs"]

        # ===============================================================
        # WIZARD DIALOG
        # ===============================================================
        from src.ui.wizard import build as _build_wizard
        wizard_btn = _build_wizard()

        # ===============================================================
        # TAB SHELL
        # ===============================================================
        # Check admin status (pass user_id to avoid st.session_state)
        _is_admin = False
        try:
            from src.db.supabase_admin import is_admin as _check_admin
            _is_admin = _check_admin(user_id)
        except Exception:
            pass

        with ui.tabs().classes("w-full q-mt-sm") as tabs:
            tab_chartmgr = ui.tab("Chart Manager", icon="folder_open")
            tab_standard = ui.tab("Standard Chart", icon="auto_awesome")
            tab_circuits = ui.tab("Circuits", icon="hub")
            tab_rulers   = ui.tab("Rulers", icon="account_tree")
            tab_chat     = ui.tab("Chat", icon="chat")
            tab_specs    = ui.tab("Specs", icon="data_object")
            tab_settings = ui.tab("Settings", icon="settings")
            if _is_admin:
                tab_admin = ui.tab("Admin", icon="admin_panel_settings")

        # Persist selected tab so toggle handlers always know the active tab
        tabs.on_value_change(lambda e: state.update(active_tab=e.value))

        # Restore last-selected tab (falls back to Circuits for new sessions)
        _tab_lookup = {
            "Chart Manager": tab_chartmgr, "Standard Chart": tab_standard,
            "Circuits": tab_circuits, "Rulers": tab_rulers,
            "Chat": tab_chat, "Specs": tab_specs, "Settings": tab_settings,
        }
        _initial_tab = _tab_lookup.get(state.get("active_tab", "Circuits"), tab_circuits)

        # ===============================================================
        # CHART RENDERING — forward-reference wrappers
        # (Defined before tab builds so they can be passed as callbacks.
        #  They reference local variables assigned by tab builds below —
        #  Python closures resolve them at call time, not definition time.)
        # ===============================================================

        def _render_chart_png(mode: str) -> Optional[bytes]:
            """Render the chart wheel as PNG bytes for the given mode."""
            return render_chart_png(mode, state)

        def _display_chart_in(container, png_bytes, *, show_info=True):
            """Display rendered chart bytes inside a NiceGUI container."""
            return display_chart_in(container, png_bytes, state, form, show_info=show_info)

        def _rerender_circuits_chart_only():
            """Re-render only the circuits chart container."""
            return rerender_circuits_chart_only(state, form, cir_chart_container)

        def _rerender_active_tab():
            """Re-render whichever tab is currently active."""
            return rerender_active_tab(
                state, form,
                tabs=tabs,
                std_chart_container=std_chart_container,
                cir_chart_container=cir_chart_container,
                synastry_aspects_exp=synastry_aspects_exp,
                cir_submode_row=cir_submode_row,
                chat_no_chart_notice=chat_no_chart_notice,
                events_container=events_container,
                rebuild_harmonic_expander=_rebuild_harmonic_expander,
                build_circuit_toggles=_build_circuit_toggles,
                render_rulers_graph=_render_rulers_graph,
                refresh_specs_tab=_refresh_specs_tab,
                refresh_drawer=_refresh_drawer,
            )

        def _refresh_events():
            """Refresh the nearby-events panel."""
            return refresh_events(state, events_container)

        # ===============================================================
        # TAB PANELS — delegated to src.ui.tab_* modules
        # ===============================================================

        with ui.tab_panels(tabs, value=_initial_tab).classes("w-full"):

            # ===========================================================
            # CHART MANAGER TAB
            with ui.tab_panel(tab_chartmgr):
                from src.ui.tab_chart_manager import build as _build_cm
                _cm = _build_cm(state, form, rerender_active_tab=_rerender_active_tab)
                calc_btn = _cm["calc_btn"]
                save_name_input = _cm["save_name_input"]
                is_my_chart_cb = _cm["is_my_chart_cb"]
                birth_exp = _cm["birth_exp"]
                status_label = _cm["status_label"]
                profile_select = _cm["profile_select"]
                _refresh_profiles = _cm["refresh_profiles"]

            # STANDARD CHART TAB
            with ui.tab_panel(tab_standard):
                from src.ui.tab_standard import build as _build_std
                _std = _build_std(
                    state, form,
                    rerender_active_tab=_rerender_active_tab,
                    on_transit_toggle=_on_transit_toggle,
                )
                std_chart_container = _std["std_chart_container"]
                synastry_aspects_exp = _std["synastry_aspects_exp"]
                _rebuild_harmonic_expander = _std["rebuild_harmonic_expander"]
                transit_cb = _std["transit_cb"]

            # ===========================================================
            # CIRCUITS TAB
            # ===========================================================
            with ui.tab_panel(tab_circuits):
                from src.ui.tab_circuits import build as _build_cir
                _cir = _build_cir(
                    state, form,
                    rerender_active_tab=_rerender_active_tab,
                    rerender_circuits_chart_only=_rerender_circuits_chart_only,
                    on_transit_toggle=_on_transit_toggle,
                )
                cir_chart_container = _cir["cir_chart_container"]
                cir_submode_row = _cir["cir_submode_row"]
                _build_circuit_toggles = _cir["build_circuit_toggles"]
            # ===========================================================
            # RULERS TAB
            # ===========================================================
            with ui.tab_panel(tab_rulers):
                from src.ui.tab_rulers import build as _build_rul
                _rul = _build_rul(state, form)
                _render_rulers_graph = _rul["render_rulers_graph"]
            # ===========================================================
            # CHAT TAB
            # ===========================================================
            with ui.tab_panel(tab_chat):
                from src.ui.tab_chat import build as _build_chat
                _chat = _build_chat(state, form)
                chat_no_chart_notice = _chat["chat_no_chart_notice"]
            # ===========================================================
            # SPECS TAB
            # ===========================================================
            with ui.tab_panel(tab_specs):
                from src.ui.tab_specs import build as _build_specs
                _specs = _build_specs(state, form)
                _refresh_specs_tab = _specs["refresh_specs_tab"]
            # ===========================================================
            # SETTINGS TAB
            # ===========================================================
            with ui.tab_panel(tab_settings):
                from src.ui.tab_settings import build as _build_set
                _set = _build_set(state, form, rerender_active_tab=_rerender_active_tab)
                _refresh_mode_map = _set["refresh_mode_map"]
            # ===========================================================
            # ADMIN TAB
            # ===========================================================
            if _is_admin:
                with ui.tab_panel(tab_admin):
                    from src.ui.tab_admin import build as _build_adm
                    _build_adm(state, form)

        # Wire late-bound refs for transit controls (tab builds created these)
        _set_late_refs(
            transit_cb=transit_cb,
            std_chart_container=std_chart_container,
            cir_chart_container=cir_chart_container,
        )

        # Re-render when tab changes
        tabs.on_value_change(lambda _: _rerender_active_tab())

        # ---------------------------------------------------------------
        # Calculate handler
        # ---------------------------------------------------------------
        from src.ui.calculate import on_calculate

        async def _on_calculate():
            """Handle the Calculate button click."""
            await on_calculate(
                state, form,
                status_label=status_label,
                calc_btn=calc_btn,
                birth_exp=birth_exp,
                save_name_input=save_name_input,
                build_circuit_toggles=_build_circuit_toggles,
                rerender_active_tab=_rerender_active_tab,
            )

        calc_btn.on_click(_on_calculate)

        # ---------------------------------------------------------------
        # Startup: auto-load self chart (or show empty-state messages)
        # ---------------------------------------------------------------
        from src.ui.startup import run_startup
        run_startup(
            state, form,
            std_chart_container=std_chart_container,
            cir_chart_container=cir_chart_container,
            chat_no_chart_notice=chat_no_chart_notice,
            save_name_input=save_name_input,
            is_my_chart_cb=is_my_chart_cb,
            build_circuit_toggles=_build_circuit_toggles,
            display_chart_in=_display_chart_in,
            render_chart_png=_render_chart_png,
            render_rulers_graph=_render_rulers_graph,
            refresh_specs_tab=_refresh_specs_tab,
            refresh_events=_refresh_events,
            refresh_drawer=_refresh_drawer,
            get_user_id=get_user_id,
        )

        # ===============================================================
        # FEEDBACK FAB + DIALOG
        # ===============================================================
        from src.ui.feedback import build as _build_feedback
        _build_feedback(state, get_user_id=get_user_id, get_supabase=get_supabase)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ in {"__main__", "__mp_main__"}:
    port = int(os.environ.get("PORT", 8080))
    ui.run(
        port=port,
        title="Rosetta",
        storage_secret=_STORAGE_SECRET,
        reload=False,         # disable reload for Windows compatibility
        show=False,           # don't auto-open browser
    )
