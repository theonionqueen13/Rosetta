"""Tests for src/core/switch_points.py — degree helpers, SwitchPoint, shape analysis."""
import math
import pytest

from src.core.switch_points import (
    _normalize_deg,
    _sign_from_longitude,
    _degree_in_sign,
    _opposite_longitude,
    _format_dms,
    _find_t_square_apex,
    _find_wedge_non_opposition_planet,
    _compute_activation_range,
    _build_saturn_summary,
    SwitchPoint,
    SHAPE_COMPLETIONS,
)


# ═══════════════════════════════════════════════════════════════════════
# _normalize_deg
# ═══════════════════════════════════════════════════════════════════════

class TestNormalizeDeg:
    def test_within_range(self):
        assert _normalize_deg(180.0) == 180.0

    def test_negative(self):
        assert _normalize_deg(-30.0) == pytest.approx(330.0)

    def test_over_360(self):
        assert _normalize_deg(400.0) == pytest.approx(40.0)

    def test_zero(self):
        assert _normalize_deg(0.0) == 0.0

    def test_exactly_360(self):
        assert _normalize_deg(360.0) == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════
# _sign_from_longitude
# ═══════════════════════════════════════════════════════════════════════

class TestSignFromLongitude:
    def test_aries(self):
        assert _sign_from_longitude(0.0) == "Aries"
        assert _sign_from_longitude(29.9) == "Aries"

    def test_taurus(self):
        assert _sign_from_longitude(30.0) == "Taurus"

    def test_pisces(self):
        assert _sign_from_longitude(350.0) == "Pisces"

    def test_scorpio(self):
        # Scorpio = 210-240
        assert _sign_from_longitude(225.0) == "Scorpio"


# ═══════════════════════════════════════════════════════════════════════
# _degree_in_sign
# ═══════════════════════════════════════════════════════════════════════

class TestDegreeInSign:
    def test_first_degree(self):
        # 0.5° → ceil(0.5) = 1
        assert _degree_in_sign(0.5) == 1

    def test_exact_zero_returns_1(self):
        # 0° in sign → 1 (Sabian convention)
        assert _degree_in_sign(0.0) == 1

    def test_last_degree(self):
        # 29.5° → ceil(29.5) = 30
        assert _degree_in_sign(29.5) == 30

    def test_mid_sign(self):
        # 45° → 45 % 30 = 15 → ceil(15) = 15
        assert _degree_in_sign(45.0) == 15


# ═══════════════════════════════════════════════════════════════════════
# _opposite_longitude
# ═══════════════════════════════════════════════════════════════════════

class TestOppositeLongitude:
    def test_simple(self):
        assert _opposite_longitude(0.0) == pytest.approx(180.0)

    def test_wrap_around(self):
        assert _opposite_longitude(200.0) == pytest.approx(20.0)

    def test_exact_half(self):
        assert _opposite_longitude(180.0) == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════
# _format_dms
# ═══════════════════════════════════════════════════════════════════════

class TestFormatDms:
    def test_basic(self):
        result = _format_dms(45.5)
        # 45.5° → Taurus (30-60), degree in sign = 15.5
        assert "15°" in result
        assert "30'" in result
        assert "Tau" in result

    def test_zero(self):
        result = _format_dms(0.0)
        assert "Ari" in result

    def test_at_sign_boundary(self):
        result = _format_dms(90.0)
        assert "Can" in result  # 90° = Cancer


# ═══════════════════════════════════════════════════════════════════════
# _find_t_square_apex
# ═══════════════════════════════════════════════════════════════════════

class TestFindTSquareApex:
    def test_basic_t_square(self):
        members = ["Mars", "Jupiter", "Saturn"]
        edges = [
            (("Mars", "Jupiter"), "Opposition"),
            (("Mars", "Saturn"), "Square"),
            (("Jupiter", "Saturn"), "Square"),
        ]
        apex = _find_t_square_apex(members, edges)
        # Saturn has 2 squares and is not in the opposition
        assert apex == "Saturn"

    def test_with_approx_suffix(self):
        members = ["A", "B", "C"]
        edges = [
            (("A", "B"), "Opposition"),
            (("A", "C"), "Square_approx"),
            (("B", "C"), "Square"),
        ]
        apex = _find_t_square_apex(members, edges)
        assert apex == "C"

    def test_no_opposition(self):
        members = ["A", "B", "C"]
        edges = [
            (("A", "B"), "Square"),
            (("B", "C"), "Square"),
        ]
        apex = _find_t_square_apex(members, edges)
        assert apex is None


# ═══════════════════════════════════════════════════════════════════════
# _find_wedge_non_opposition_planet
# ═══════════════════════════════════════════════════════════════════════

class TestFindWedgeNonOppositionPlanet:
    def test_basic_wedge(self):
        members = ["Sun", "Moon", "Venus"]
        edges = [
            (("Sun", "Moon"), "Opposition"),
            (("Sun", "Venus"), "Trine"),
            (("Moon", "Venus"), "Sextile"),
        ]
        result = _find_wedge_non_opposition_planet(members, edges)
        assert result == "Venus"

    def test_no_opposition(self):
        members = ["A", "B", "C"]
        edges = [
            (("A", "B"), "Trine"),
            (("B", "C"), "Sextile"),
        ]
        result = _find_wedge_non_opposition_planet(members, edges)
        # All members are "non-opposition" — returns first
        assert result == "A"


# ═══════════════════════════════════════════════════════════════════════
# _compute_activation_range
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActivationRange:
    def test_fallback_no_members(self):
        low, high, desc = _compute_activation_range(45.0, [], {})
        assert low < high
        assert "°" in desc

    def test_with_members(self):
        positions = {"Sun": 42.0, "Moon": 48.0}
        low, high, desc = _compute_activation_range(
            45.0, ["Sun", "Moon"], positions,
        )
        assert low < high
        assert isinstance(desc, str)


# ═══════════════════════════════════════════════════════════════════════
# _build_saturn_summary
# ═══════════════════════════════════════════════════════════════════════

class TestBuildSaturnSummary:
    def test_fire_sign(self):
        result = _build_saturn_summary("Aries", 1)
        assert "Saturn in Aries" in result
        assert "bold action" in result

    def test_earth_sign(self):
        result = _build_saturn_summary("Taurus", 2)
        assert "tangible routine" in result

    def test_air_sign(self):
        result = _build_saturn_summary("Gemini", 3)
        assert "intellectual systems" in result

    def test_water_sign(self):
        result = _build_saturn_summary("Cancer", 4)
        assert "emotional depth" in result

    def test_with_house(self):
        result = _build_saturn_summary("Leo", 5)
        assert "(house 5)" in result

    def test_empty_sign(self):
        assert _build_saturn_summary("", 0) == ""

    def test_no_house(self):
        result = _build_saturn_summary("Aries", 0)
        assert "(house" not in result


# ═══════════════════════════════════════════════════════════════════════
# SwitchPoint dataclass
# ═══════════════════════════════════════════════════════════════════════

class TestSwitchPoint:
    @pytest.fixture
    def sample_sp(self):
        return SwitchPoint(
            source_shape_type="T-Square",
            source_members=["Mars", "Jupiter", "Saturn"],
            completes_to="Grand Cross",
            membrane_class="drum_head",
            longitude=225.0,
            sign="Scorpio",
            degree_in_sign=15,
            dms="15°00'00\"Sco",
            range_low=222.0,
            range_high=228.0,
            range_description="12°–18° Scorpio",
            sabian_symbol="Test Symbol",
            sabian_meaning="Test meaning",
            saturn_sign="Capricorn",
            saturn_house=10,
            saturn_summary="Saturn in Capricorn (house 10); builds through tangible routine.",
            switch_point_house=8,
            description="The T-Square is a Grand Cross with one corner missing.",
        )

    def test_to_dict_structure(self, sample_sp):
        d = sample_sp.to_dict()
        assert d["source_shape"] == "T-Square"
        assert d["completes_to"] == "Grand Cross"
        assert "switch_point" in d
        assert d["switch_point"]["sign"] == "Scorpio"
        assert d["switch_point"]["degree"] == 15
        assert d["switch_point"]["house"] == 8

    def test_to_dict_sabian(self, sample_sp):
        d = sample_sp.to_dict()
        assert "sabian" in d
        assert d["sabian"]["symbol"] == "Test Symbol"

    def test_to_dict_saturn_context(self, sample_sp):
        d = sample_sp.to_dict()
        assert "saturn_context" in d
        assert d["saturn_context"]["sign"] == "Capricorn"

    def test_to_dict_no_optional_fields(self):
        sp = SwitchPoint(
            source_shape_type="T-Square",
            source_members=["A", "B", "C"],
            completes_to="Grand Cross",
            membrane_class="drum_head",
            longitude=90.0,
            sign="Cancer",
            degree_in_sign=1,
            dms="0°00'00\"Can",
            range_low=87.0,
            range_high=93.0,
            range_description="27°–3° Cancer",
        )
        d = sp.to_dict()
        assert "sabian" not in d
        assert "saturn_context" not in d
        assert "house" not in d["switch_point"]


# ═══════════════════════════════════════════════════════════════════════
# SHAPE_COMPLETIONS constant
# ═══════════════════════════════════════════════════════════════════════

class TestShapeCompletions:
    def test_expected_shapes(self):
        assert "T-Square" in SHAPE_COMPLETIONS
        assert "Wedge" in SHAPE_COMPLETIONS
        assert "Envelope" in SHAPE_COMPLETIONS
        assert "Cradle" in SHAPE_COMPLETIONS

    def test_completion_keys(self):
        for shape, data in SHAPE_COMPLETIONS.items():
            assert "completes_to" in data
            assert "missing_count" in data
            assert "description" in data
