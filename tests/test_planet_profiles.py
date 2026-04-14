"""Tests for src/core/planet_profiles.py — formatting helpers + dataclasses."""
import pytest

from src.core.planet_profiles import (
    _dms_abs,
    _fmt_speed_per_day,
    _fmt_lat,
    _fmt_decl,
    _fmt_distance_au_km,
    _format_house_label,
    _format_axis_for_display,
    _normalize_for_combo,
    _canon,
    _format_reception_links,
)


# ═══════════════════════════════════════════════════════════════════════
# _dms_abs
# ═══════════════════════════════════════════════════════════════════════

class TestDmsAbs:
    def test_zero(self):
        assert _dms_abs(0) == "0°00′00″"

    def test_integer_degree(self):
        result = _dms_abs(15)
        assert result.startswith("15°")

    def test_fractional(self):
        # 23.5° = 23°30'00"
        result = _dms_abs(23.5)
        assert "23°" in result
        assert "30" in result

    def test_negative_uses_abs(self):
        result = _dms_abs(-10.25)
        assert result == _dms_abs(10.25)

    def test_none(self):
        assert _dms_abs(None) == ""


# ═══════════════════════════════════════════════════════════════════════
# _fmt_speed_per_day
# ═══════════════════════════════════════════════════════════════════════

class TestFmtSpeedPerDay:
    def test_positive_speed(self):
        result = _fmt_speed_per_day(1.0)
        assert "/day" in result

    def test_none(self):
        assert _fmt_speed_per_day(None) == ""


# ═══════════════════════════════════════════════════════════════════════
# _fmt_lat / _fmt_decl
# ═══════════════════════════════════════════════════════════════════════

class TestFmtLat:
    def test_north(self):
        result = _fmt_lat(5.5)
        assert "N" in result

    def test_south(self):
        result = _fmt_lat(-3.2)
        assert "S" in result

    def test_none(self):
        assert _fmt_lat(None) == ""


class TestFmtDecl:
    def test_north(self):
        result = _fmt_decl(23.44)
        assert "N" in result

    def test_south(self):
        result = _fmt_decl(-23.44)
        assert "S" in result

    def test_none(self):
        assert _fmt_decl(None) == ""


# ═══════════════════════════════════════════════════════════════════════
# _fmt_distance_au_km
# ═══════════════════════════════════════════════════════════════════════

class TestFmtDistanceAuKm:
    def test_earth_sun(self):
        result = _fmt_distance_au_km(1.0)
        assert "1.000000 AU" in result
        assert "million km" in result

    def test_small_distance(self):
        result = _fmt_distance_au_km(0.002)  # ~300k km (Moon-ish)
        assert "AU" in result

    def test_none(self):
        assert _fmt_distance_au_km(None) == ""


# ═══════════════════════════════════════════════════════════════════════
# _format_house_label
# ═══════════════════════════════════════════════════════════════════════

class TestFormatHouseLabel:
    def test_ordinals(self):
        assert _format_house_label(1) == "1st House"
        assert _format_house_label(2) == "2nd House"
        assert _format_house_label(3) == "3rd House"
        assert _format_house_label(10) == "10th House"

    def test_none(self):
        assert _format_house_label(None) == ""

    def test_float_input(self):
        assert _format_house_label(4.0) == "4th House"


# ═══════════════════════════════════════════════════════════════════════
# _format_axis_for_display
# ═══════════════════════════════════════════════════════════════════════

class TestFormatAxisForDisplay:
    def test_ac(self):
        result = _format_axis_for_display("AC")
        assert "Ascendant" in result
        assert "AC" in result

    def test_mc(self):
        result = _format_axis_for_display("MC")
        assert "Midheaven" in result

    def test_non_axis(self):
        result = _format_axis_for_display("Sun")
        assert result == "Sun"


# ═══════════════════════════════════════════════════════════════════════
# _normalize_for_combo
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizeForCombo:
    def test_known_mappings(self):
        assert _normalize_for_combo("Ascendant") == "AC"
        assert _normalize_for_combo("Descendant") == "DC"
        assert _normalize_for_combo("North Node") == "NorthNode"

    def test_plain_planet(self):
        assert _normalize_for_combo("Sun") == "Sun"

    def test_multi_word(self):
        assert _normalize_for_combo("Part of Fortune") == "PartOfFortune"


# ═══════════════════════════════════════════════════════════════════════
# _canon
# ═══════════════════════════════════════════════════════════════════════

class TestCanon:
    def test_basic(self):
        assert _canon("Sun") == "sun"
        assert _canon("North Node") == "northnode"

    def test_empty(self):
        assert _canon("") == ""


# ═══════════════════════════════════════════════════════════════════════
# _format_reception_links
# ═══════════════════════════════════════════════════════════════════════

class TestFormatReceptionLinks:
    def test_empty(self):
        assert _format_reception_links([]) == ""
        assert _format_reception_links(None) == ""

    def test_with_mock_link(self):
        class MockAspect:
            name = "Trine"

        class MockOther:
            name = "Jupiter"

        class MockLink:
            other = MockOther()
            aspect = MockAspect()
            mode = "sign"

        result = _format_reception_links([MockLink()])
        assert "Trine" in result
        assert "Jupiter" in result
        assert "by sign" in result
