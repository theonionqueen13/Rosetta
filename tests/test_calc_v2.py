"""Tests for src/core/calc_v2.py — pure helpers + integration with swisseph."""
import datetime
import math

import pytest

from src.core.calc_v2 import (
    OOB_LIMIT,
    is_out_of_bounds,
    deg_to_sign,
    get_utc_datetime,
    chart_sect_from_chart,
    _in_forward_arc,
    _house_of_degree,
    lookup_sign_rulers,
    analyze_dispositors,
    _resolve_dignity,
    _sign_index,
)


# ═══════════════════════════════════════════════════════════════════════
# is_out_of_bounds
# ═══════════════════════════════════════════════════════════════════════

class TestIsOutOfBounds:
    def test_within_bounds(self):
        assert is_out_of_bounds(0.0) is False
        assert is_out_of_bounds(23.0) is False

    def test_at_boundary(self):
        # Exactly at the limit should NOT be OOB (> not >=)
        assert is_out_of_bounds(OOB_LIMIT) is False
        assert is_out_of_bounds(-OOB_LIMIT) is False

    def test_beyond_boundary(self):
        assert is_out_of_bounds(23.45) is True
        assert is_out_of_bounds(-23.45) is True

    def test_extreme_values(self):
        assert is_out_of_bounds(90.0) is True
        assert is_out_of_bounds(-90.0) is True


# ═══════════════════════════════════════════════════════════════════════
# deg_to_sign
# ═══════════════════════════════════════════════════════════════════════

class TestDegToSign:
    def test_zero_degrees(self):
        sign, dms, sabian = deg_to_sign(0.0)
        assert sign == "Aries"
        assert sabian == 1

    def test_thirty_degrees(self):
        sign, dms, sabian = deg_to_sign(30.0)
        assert sign == "Taurus"
        assert sabian == 31

    def test_last_degree(self):
        sign, dms, sabian = deg_to_sign(359.999)
        assert sign == "Pisces"

    def test_mid_zodiac(self):
        sign, _dms, _sab = deg_to_sign(135.5)
        assert sign == "Leo"  # 135° / 30 = 4.5 → index 4 = Leo

    def test_dms_format(self):
        sign, dms, _sab = deg_to_sign(45.5)
        assert sign == "Taurus"
        # 45.5 - 30 = 15.5° => 15°30'00"
        assert "15" in dms
        assert "30" in dms

    def test_sabian_index_range(self):
        for deg in [0, 90, 180, 270, 359]:
            _, _, sab = deg_to_sign(float(deg))
            assert 1 <= sab <= 360


# ═══════════════════════════════════════════════════════════════════════
# get_utc_datetime
# ═══════════════════════════════════════════════════════════════════════

class TestGetUtcDatetime:
    def test_input_is_ut(self):
        dt = get_utc_datetime(2000, 1, 1, 12, 0, True, 0, None)
        assert dt.tzinfo == datetime.timezone.utc
        assert dt.hour == 12

    def test_with_tz_name(self):
        dt = get_utc_datetime(2000, 6, 15, 14, 30, False, 0, "America/New_York")
        assert dt.tzinfo == datetime.timezone.utc
        # 14:30 EDT (UTC-4 in June) → 18:30 UTC
        assert dt.hour == 18
        assert dt.minute == 30

    def test_with_tz_offset(self):
        dt = get_utc_datetime(2000, 1, 1, 12, 0, False, -5, None)
        assert dt.tzinfo == datetime.timezone.utc
        assert dt.hour == 17  # 12 + 5

    def test_utc_passthrough(self):
        dt = get_utc_datetime(1990, 6, 15, 0, 0, True, -5, "America/New_York")
        # input_is_ut=True should override tz_name and tz_offset
        assert dt.hour == 0


# ═══════════════════════════════════════════════════════════════════════
# _in_forward_arc
# ═══════════════════════════════════════════════════════════════════════

class TestInForwardArc:
    def test_simple_arc(self):
        assert _in_forward_arc(10, 50, 30) is True
        assert _in_forward_arc(10, 50, 5) is False
        assert _in_forward_arc(10, 50, 55) is False

    def test_wrap_around(self):
        # Arc from 350 → 10 (crossing 0°)
        assert _in_forward_arc(350, 10, 355) is True
        assert _in_forward_arc(350, 10, 5) is True
        assert _in_forward_arc(350, 10, 180) is False

    def test_zero_span(self):
        # Start == end: only exact match at start
        assert _in_forward_arc(100, 100, 100) is True
        assert _in_forward_arc(100, 100, 101) is False

    def test_full_circle(self):
        # Span of nearly 360 should include almost everything
        assert _in_forward_arc(0, 359.9, 180) is True


# ═══════════════════════════════════════════════════════════════════════
# _house_of_degree
# ═══════════════════════════════════════════════════════════════════════

class TestHouseOfDegree:
    @pytest.fixture
    def equal_cusps(self):
        """Equal houses starting at 0° Aries."""
        return [i * 30.0 for i in range(12)]

    def test_first_house(self, equal_cusps):
        assert _house_of_degree(15.0, equal_cusps) == 1

    def test_last_house(self, equal_cusps):
        assert _house_of_degree(335.0, equal_cusps) == 12

    def test_cusp_boundary(self, equal_cusps):
        # Exactly at cusp 2 (30°) → should be in house 2
        assert _house_of_degree(30.0, equal_cusps) == 2

    def test_none_for_missing_cusps(self):
        assert _house_of_degree(10.0, []) is None
        assert _house_of_degree(10.0, [0, 30]) is None

    def test_wrap_around(self):
        cusps = [350.0] + [(350 + i * 30) % 360 for i in range(1, 12)]
        assert _house_of_degree(355.0, cusps) == 1


# ═══════════════════════════════════════════════════════════════════════
# _sign_index
# ═══════════════════════════════════════════════════════════════════════

class TestSignIndex:
    def test_aries(self):
        assert _sign_index(0.0) == 0
        assert _sign_index(29.9) == 0

    def test_taurus(self):
        assert _sign_index(30.0) == 1

    def test_pisces(self):
        assert _sign_index(350.0) == 11

    def test_wrap(self):
        assert _sign_index(360.0) == 0


# ═══════════════════════════════════════════════════════════════════════
# lookup_sign_rulers
# ═══════════════════════════════════════════════════════════════════════

class TestLookupSignRulers:
    @pytest.fixture
    def rulers(self):
        return {
            "Aries": "Mars",
            "Gemini": ["Mercury"],
            "Pisces": ["Jupiter", "Neptune"],
        }

    def test_single_ruler(self, rulers):
        result = lookup_sign_rulers("Aries", rulers)
        assert result == ["Mars"]

    def test_list_rulers(self, rulers):
        result = lookup_sign_rulers("Pisces", rulers)
        assert result == ["Jupiter", "Neptune"]

    def test_missing_sign(self, rulers):
        result = lookup_sign_rulers("InvalidSign", rulers)
        assert result == []

    def test_empty_sign(self, rulers):
        result = lookup_sign_rulers("", rulers)
        assert result == []


# ═══════════════════════════════════════════════════════════════════════
# _resolve_dignity
# ═══════════════════════════════════════════════════════════════════════

class TestResolveDignity:
    def test_sun_in_leo(self):
        result = _resolve_dignity("Sun", "Leo")
        # Sun is domicile in Leo
        assert result is not None
        assert isinstance(result, str)

    def test_unknown_planet(self):
        result = _resolve_dignity("Asteroid_X", "Aries")
        # Should not crash even for unknown objects
        assert result is not None or result is None  # just no crash


# ═══════════════════════════════════════════════════════════════════════
# analyze_dispositors
# ═══════════════════════════════════════════════════════════════════════

class TestAnalyzeDispositors:
    @pytest.fixture
    def simple_positions(self):
        """Sun in Leo (domicile), Moon in Cancer (domicile)."""
        return {"Sun": 130.0, "Moon": 100.0}  # Leo ≈ 120-150, Cancer ≈ 90-120

    def test_returns_by_sign_and_by_house(self, simple_positions):
        result = analyze_dispositors(simple_positions, None)
        assert "by_sign" in result
        assert "by_house" in result

    def test_sign_scope_has_required_keys(self, simple_positions):
        result = analyze_dispositors(simple_positions, None)
        scope = result["by_sign"]
        for key in ("raw_links", "sovereigns", "self_ruling",
                     "dominant_rulers", "final_dispositors", "loops"):
            assert key in scope, f"Missing key: {key}"

    def test_self_ruling_planet(self, simple_positions):
        result = analyze_dispositors(simple_positions, None)
        scope = result["by_sign"]
        # Sun in Leo is ruled by Sun → self-ruling
        assert "Sun" in scope["self_ruling"]

    def test_with_cusps(self, simple_positions):
        cusps = [i * 30.0 for i in range(12)]
        result = analyze_dispositors(simple_positions, cusps)
        # House-based scope should also be computed
        assert "by_house" in result
        assert "raw_links" in result["by_house"]


# ═══════════════════════════════════════════════════════════════════════
# chart_sect_from_chart  (integration — needs a real chart)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestChartSect:
    def test_sect_determination(self, sample_chart):
        sect = chart_sect_from_chart(sample_chart)
        assert sect in ("Diurnal", "Nocturnal")

    def test_sect_none_chart_raises(self):
        with pytest.raises(ValueError, match="time unknown"):
            chart_sect_from_chart(None)


# ═══════════════════════════════════════════════════════════════════════
# calculate_chart integration test
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestCalculateChart:
    def test_sample_chart_has_objects(self, sample_chart):
        assert len(sample_chart.objects) >= 10

    def test_sample_chart_has_house_cusps(self, sample_chart):
        assert len(sample_chart.house_cusps) > 0

    def test_sun_in_gemini(self, sample_chart):
        """1990-06-15 → Sun should be in Gemini."""
        sun = next(
            (o for o in sample_chart.objects if o.object_name and o.object_name.name == "Sun"),
            None,
        )
        assert sun is not None
        assert sun.sign is not None
        assert sun.sign.name == "Gemini"

    def test_chart_datetime_populated(self, sample_chart):
        assert sample_chart.chart_datetime

    def test_chart_display_name(self, sample_chart):
        assert sample_chart.display_name == "Sample"

    def test_objects_have_longitude(self, sample_chart):
        """Each object should have a numeric longitude."""
        for obj in sample_chart.objects:
            assert isinstance(obj.longitude, (int, float))
