"""Guided Topics Wizard dialog."""
from __future__ import annotations

import logging
from typing import Callable, Dict, List, Optional

from nicegui import ui

_log = logging.getLogger(__name__)


def build(
    chart_conjunctions_getter: Optional[Callable[[], Dict[str, List[str]]]] = None,
) -> ui.button:
    """Create the wizard dialog and return the button that opens it.

    Parameters
    ----------
    chart_conjunctions_getter:
        Optional zero-argument callable that returns
        ``{planet_name: [star_name, ...]}`` for the currently loaded chart.
        When provided, a 'Fixed stars in your chart' section is rendered
        for any stars relevant to the selected subtopic that the user
        actually has conjunctions to.

    Returns the wizard button widget so the caller can place it in the layout.
    """
    with ui.dialog().classes("w-full") as wizard_dlg, \
            ui.card().style("max-width: 600px; min-width: 400px"):
        ui.label("Guided Topics Wizard").classes("text-h5 q-mb-sm")
        ui.label(
            "Explore topics in your chart with guided questions."
        ).classes("text-body2 text-grey q-mb-md")

        try:
            from src.mcp.topic_maps import WIZARD_TARGETS
            _wizard_domains = WIZARD_TARGETS.get("domains", [])
        except (ImportError, AttributeError) as exc:
            _log.warning("Could not load wizard targets: %s", exc)
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
            """Update the subtopic list when the domain selection changes."""
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
            """Update the target list when the subtopic selection changes."""
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

        def _get_meaning_text(value):
            if isinstance(value, dict):
                return value.get("meaning") or value.get("long_meaning") or ""
            return value

        def _wiz_show_targets(e=None):
            """Display astrological targets for the selected topic/subtopic."""
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
                    from src.core.models_v2 import static_db as _sdb
                    _GLYPHS = getattr(_sdb, "GLYPHS", {})
                    _OBJ_MEANINGS = getattr(
                        _sdb, "OBJECT_MEANINGS_SHORT", {}
                    )
                    _SIGN_MEANINGS = getattr(_sdb, "SIGN_MEANINGS", {})
                    _HOUSE_MEANINGS = getattr(_sdb, "HOUSE_MEANINGS", {})
                    for t in targets:
                        glyph = _GLYPHS.get(t, "")
                        display = f"{glyph} {t}" if glyph else t
                        meaning = _get_meaning_text(
                            _OBJ_MEANINGS.get(t)
                            or _SIGN_MEANINGS.get(t)
                            or ""
                        )
                        if not meaning and "House" in t:
                            try:
                                hnum = int(
                                    t.split()[0]
                                    .replace("st", "").replace("nd", "")
                                    .replace("rd", "").replace("th", "")
                                )
                                meaning = _get_meaning_text(
                                    _HOUSE_MEANINGS.get(hnum, "")
                                )
                            except (ValueError, IndexError) as exc:
                                _log.warning("Could not parse house number from %r: %s", t, exc)
                        label_txt = (
                            f"{display}: {meaning}"
                            if meaning else display
                        )
                        ui.label(label_txt).classes("text-body2")
                else:
                    ui.label("No targets for this selection.").classes(
                        "text-body2 text-grey"
                    )

                # ── Fixed-star conjunctions relevant to this subtopic ──
                _wiz_show_fixed_stars(sub.get("label", ""))

        def _wiz_show_fixed_stars(subtopic_label: str) -> None:
            """Append a 'Fixed stars in your chart' section if applicable."""
            if not subtopic_label or chart_conjunctions_getter is None:
                return
            try:
                from src.mcp.topic_maps import get_stars_for_subtopic
                chart_conj = chart_conjunctions_getter() or {}
                if not chart_conj:
                    return
                # Build reverse map: star_name (lower) -> list of planet names
                star_to_planets: Dict[str, List[str]] = {}
                for planet, star_list in chart_conj.items():
                    for star in (star_list or []):
                        key = star.lower()
                        star_to_planets.setdefault(key, []).append(planet)

                tagged_stars = get_stars_for_subtopic(subtopic_label)
                hits = []
                for star in tagged_stars:
                    planets = star_to_planets.get(star["name"].lower(), [])
                    if planets:
                        hits.append((star, planets))

                if hits:
                    with wiz_targets_container:
                        ui.separator().classes("q-my-sm")
                        ui.label("Fixed stars in your chart:").classes(
                            "text-subtitle2 q-mb-xs"
                        )
                        for star, planets in hits:
                            planet_str = ", ".join(planets)
                            meaning = star["short_meaning"]
                            line = f"\u2605 {star['name']} on {planet_str}"
                            if meaning:
                                line += f" \u2014 {meaning[:120]}"
                            ui.label(line).classes("text-body2")
            except Exception as exc:
                _log.debug("Fixed star wizard section error: %s", exc)

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

    return wizard_btn
