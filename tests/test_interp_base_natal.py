"""Tests for src.rendering.interp_base_natal — interpretation text."""
from __future__ import annotations

from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Pure formatting helpers
# ---------------------------------------------------------------------------
class TestFormatAxisForDisplay:
    """Tests for _format_axis_for_display()."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.interp_base_natal import _format_axis_for_display
        self.fn = _format_axis_for_display

    def test_abbreviation_ac(self):
        assert self.fn("AC") == "Ascendant (AC)"

    def test_abbreviation_mc(self):
        assert self.fn("MC") == "Midheaven (MC)"

    def test_abbreviation_dc(self):
        assert self.fn("DC") == "Descendant (DC)"

    def test_abbreviation_ic(self):
        assert self.fn("IC") == "Immum Coeli (IC)"

    def test_full_name_ascendant(self):
        assert self.fn("Ascendant") == "Ascendant (AC)"

    def test_full_name_midheaven(self):
        assert self.fn("Midheaven") == "Midheaven (MC)"

    def test_hybrid_form(self):
        result = self.fn("AC Ascendant")
        assert "Ascendant" in result and "AC" in result

    def test_non_axis(self):
        assert self.fn("Sun") == "Sun"

    def test_non_axis_planet(self):
        assert self.fn("Mars") == "Mars"


class TestAspectDisplayName:
    """Tests for _aspect_display_name()."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.interp_base_natal import _aspect_display_name
        self.fn = _aspect_display_name

    def test_ascendant_becomes_ac(self):
        assert self.fn("Ascendant") == "AC"

    def test_mc_stays_mc(self):
        assert self.fn("MC") == "MC"

    def test_planet_unchanged(self):
        assert self.fn("Mars") == "Mars"
        assert self.fn("Venus") == "Venus"


class TestFormatHouseLabel:
    """Tests for _format_house_label()."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.interp_base_natal import _format_house_label
        self.fn = _format_house_label

    @pytest.mark.parametrize(
        "num, expected",
        [
            (1, "1st House"),
            (2, "2nd House"),
            (3, "3rd House"),
            (4, "4th House"),
            (5, "5th House"),
            (6, "6th House"),
            (7, "7th House"),
            (8, "8th House"),
            (9, "9th House"),
            (10, "10th House"),
            (11, "11th House"),
            (12, "12th House"),
        ],
    )
    def test_all_houses(self, num, expected):
        assert self.fn(num) == expected

    def test_none_returns_empty(self):
        assert self.fn(None) == ""

    def test_float_input(self):
        assert self.fn(3.0) == "3rd House"

    def test_string_input(self):
        assert self.fn("7") == "7th House"


# ---------------------------------------------------------------------------
# NormalizeObjNameForCombo (via NatalInterpreter instance)
# ---------------------------------------------------------------------------
class TestNormalizeObjNameForCombo:
    """Tests for NatalInterpreter._normalize_obj_name_for_combo()."""

    @pytest.fixture()
    def interpreter(self, render_result):
        with patch("src.rendering.interp_base_natal._selected_house_system", return_value="placidus"):
            from src.rendering.interp_base_natal import NatalInterpreter
            return NatalInterpreter(render_result)

    def test_ascendant_to_ac(self, interpreter):
        assert interpreter._normalize_obj_name_for_combo("Ascendant") == "AC"

    def test_north_node(self, interpreter):
        assert interpreter._normalize_obj_name_for_combo("North Node") == "NorthNode"

    def test_sun_unchanged(self, interpreter):
        assert interpreter._normalize_obj_name_for_combo("Sun") == "Sun"

    def test_black_moon_lilith(self, interpreter):
        assert interpreter._normalize_obj_name_for_combo("Black Moon Lilith (Mean)") == "Lilith"

    def test_ac_stays_ac(self, interpreter):
        assert interpreter._normalize_obj_name_for_combo("AC") == "AC"


# ---------------------------------------------------------------------------
# NatalInterpreter.generate()
# ---------------------------------------------------------------------------
class TestNatalInterpreterGenerate:
    """Integration-level tests for NatalInterpreter.generate()."""

    def test_generate_returns_string(self, render_result):
        with patch("src.rendering.interp_base_natal._selected_house_system", return_value="placidus"):
            from src.rendering.interp_base_natal import NatalInterpreter

            interp = NatalInterpreter(render_result)
            text = interp.generate()
            assert isinstance(text, str)
            assert len(text) > 0

    def test_generate_contains_object_name(self, render_result):
        with patch("src.rendering.interp_base_natal._selected_house_system", return_value="placidus"):
            from src.rendering.interp_base_natal import NatalInterpreter

            interp = NatalInterpreter(render_result)
            text = interp.generate()
            # Should mention at least one celestial object
            found = any(name in text for name in ("Sun", "Moon", "Mercury", "Venus", "Mars"))
            assert found, "Generated text should mention at least one planet"

    def test_generate_focus_mode_sun(self, render_result):
        with patch("src.rendering.interp_base_natal._selected_house_system", return_value="placidus"):
            from src.rendering.interp_base_natal import NatalInterpreter

            interp = NatalInterpreter(render_result, mode="focus", object_name="Sun")
            text = interp.generate()
            assert isinstance(text, str)
            assert len(text) > 0

    def test_generate_focus_mode_missing_object(self, render_result):
        with patch("src.rendering.interp_base_natal._selected_house_system", return_value="placidus"):
            from src.rendering.interp_base_natal import NatalInterpreter

            interp = NatalInterpreter(render_result, mode="focus", object_name="Nonexistent999")
            text = interp.generate()
            assert "not found" in text.lower()

    def test_generate_empty_result(self):
        """An empty RenderResult should return 'no active objects' message."""
        with patch("src.rendering.interp_base_natal._selected_house_system", return_value="placidus"):
            from src.rendering.interp_base_natal import NatalInterpreter
            from src.rendering.drawing_v2 import RenderResult

            empty = RenderResult(
                fig=None,
                ax=None,
                positions={},
                cusps=[0.0] * 12,
                visible_objects=[],
                drawn_major_edges=[],
                drawn_minor_edges=[],
                plot_data={},
            )
            interp = NatalInterpreter(empty)
            text = interp.generate()
            assert "no active objects" in text.lower()
