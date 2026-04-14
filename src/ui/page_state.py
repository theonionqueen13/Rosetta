# src/ui/page_state.py
"""
PageState dataclass — the shared state bag for all src/ui/ modules.

Every tab builder, chart renderer, and UI helper receives a single
``PageState`` instance instead of closing over dozens of locals inside
``main_page()``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class PageState:
    """Shared state for the Rosetta UI page.

    Attributes are grouped by category.  Containers and widgets are typed
    as ``Any`` because NiceGUI widget classes are not easily importable at
    module scope without triggering side-effects, and we want this file to
    remain import-light.
    """

    # ── Per-user persistent dicts ─────────────────────────────────────
    state: Dict[str, Any] = field(default_factory=dict)
    form: Dict[str, Any] = field(default_factory=dict)

    # ── Identity ──────────────────────────────────────────────────────
    user_id: Optional[str] = None
    email: str = ""

    # ── Tab shell ─────────────────────────────────────────────────────
    tabs: Any = None           # ui.tabs

    # ── Chart containers ──────────────────────────────────────────────
    std_chart_container: Any = None   # ui.column — Standard Chart image
    cir_chart_container: Any = None   # ui.column — Circuits Chart image
    cir_patterns_container: Any = None
    cir_singletons_container: Any = None
    rulers_chart_container: Any = None
    rulers_legend_container: Any = None
    events_container: Any = None      # ui.html — events panel

    # ── Specs containers ──────────────────────────────────────────────
    specs_objects_container: Any = None
    specs_conj_container: Any = None
    specs_aspects_graph_container: Any = None
    specs_aspects_list_container: Any = None

    # ── Chat containers ───────────────────────────────────────────────
    chat_messages_col: Any = None
    chat_examples_container: Any = None
    chat_dev_content: Any = None
    chat_scroll: Any = None
    chat_input: Any = None
    chat_send_btn: Any = None
    chat_spinner: Any = None
    chat_no_chart_notice: Any = None
    chat_clear_btn: Any = None

    # ── Drawer ────────────────────────────────────────────────────────
    drawer: Any = None
    drawer_content: Any = None
    profile_mode_radio: Any = None

    # ── Chart Manager widgets ─────────────────────────────────────────
    profile_select: Any = None
    save_name_input: Any = None
    is_my_chart_cb: Any = None
    mgr_status: Any = None
    birth_exp: Any = None
    status_label: Any = None
    calc_btn: Any = None

    # ── Synastry/Transit widgets ──────────────────────────────────────
    synastry_cb: Any = None
    synastry_row: Any = None
    chart2_profile_sel: Any = None
    transit_cb: Any = None
    transit_nav_row: Any = None
    transit_dt_label: Any = None
    cir_submode_row: Any = None

    # ── Standard Chart tab widgets ────────────────────────────────────
    synastry_aspects_exp: Any = None
    harm_exp: Any = None
    harm_container: Any = None
    harmonic_cbs: Dict[str, Any] = field(default_factory=dict)
    _harm_select_all_ref: list = field(default_factory=list)

    # ── Rulers tab widgets ────────────────────────────────────────────
    rulers_scope_radio: Any = None

    # ── Settings tab widgets ──────────────────────────────────────────
    mode_map_html_container: Any = None

    # ── Day select (Chart Manager) ────────────────────────────────────
    day_select: Any = None
    hour_sel: Any = None
    min_sel: Any = None
    ampm_sel: Any = None

    # ── House select ──────────────────────────────────────────────────
    house_select: Any = None

    # ── Late-bound callbacks ──────────────────────────────────────────
    # These are set after construction so that modules can cross-call
    # without import cycles.  Each is a ``Callable[[], None]`` or similar.
    rerender_active_tab: Callable[[], None] = field(default=lambda: None)
    refresh_drawer: Callable[[], None] = field(default=lambda: None)
    build_circuit_toggles: Callable[[], None] = field(default=lambda: None)
    rerender_circuits_chart_only: Callable[[], None] = field(default=lambda: None)
    refresh_events: Callable[[], None] = field(default=lambda: None)
    refresh_profiles: Callable[[], None] = field(default=lambda: None)
    refresh_chart2_profiles: Callable[[], None] = field(default=lambda: None)
    rebuild_harmonic_expander: Callable[[], None] = field(default=lambda: None)
    render_rulers_graph: Callable[[], None] = field(default=lambda: None)
    refresh_specs_tab: Callable[[], None] = field(default=lambda: None)
    refresh_mode_map: Callable[[], None] = field(default=lambda: None)
    startup_render_with_chart: Callable[[], None] = field(default=lambda: None)
    startup_show_empty: Callable[[], None] = field(default=lambda: None)
    populate_example_prompts: Callable[[], None] = field(default=lambda: None)
