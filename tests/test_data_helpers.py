"""Tests for src/core/data_helpers.py — pure DataFrame / dict utilities."""
import pandas as pd
import pytest

from src.core.data_helpers import (
    _canonical_name,
    _in_forward_arc,
    _house_of_degree,
    _degree_for_label,
    _normalise_aspect,
    _resolve_aspect,
    _edge_record_to_components,
    _expand_visible_canon,
    _object_rows,
    _canonical_series,
    _find_row,
    get_ascendant_degree,
    extract_positions,
    extract_compass_positions,
)


# ═══════════════════════════════════════════════════════════════════════
# _canonical_name
# ═══════════════════════════════════════════════════════════════════════

class TestCanonicalName:
    def test_basic(self):
        assert _canonical_name("Sun") == "sun"

    def test_strips_special_chars(self):
        assert _canonical_name("North Node") == "northnode"
        assert _canonical_name("Black Moon Lilith (Mean)") == "blackmoonlilithmean"

    def test_none(self):
        assert _canonical_name(None) == ""

    def test_numeric_preserved(self):
        assert _canonical_name("1H Cusp") == "1hcusp"


# ═══════════════════════════════════════════════════════════════════════
# _in_forward_arc
# ═══════════════════════════════════════════════════════════════════════

class TestInForwardArc:
    def test_simple_arc(self):
        assert _in_forward_arc(10, 50, 30) is True

    def test_outside_arc(self):
        assert _in_forward_arc(10, 50, 5) is False

    def test_wrap_around(self):
        assert _in_forward_arc(350, 10, 355) is True
        assert _in_forward_arc(350, 10, 5) is True
        assert _in_forward_arc(350, 10, 180) is False

    def test_zero_span(self):
        assert _in_forward_arc(100, 100, 100) is True
        assert _in_forward_arc(100, 100, 101) is False


# ═══════════════════════════════════════════════════════════════════════
# _house_of_degree
# ═══════════════════════════════════════════════════════════════════════

class TestHouseOfDegree:
    @pytest.fixture
    def equal_cusps(self):
        return [i * 30.0 for i in range(12)]

    def test_first_house(self, equal_cusps):
        assert _house_of_degree(15.0, equal_cusps) == 1

    def test_last_house(self, equal_cusps):
        assert _house_of_degree(335.0, equal_cusps) == 12

    def test_none_for_bad_cusps(self):
        assert _house_of_degree(10.0, []) is None
        assert _house_of_degree(10.0, None) is None

    def test_none_for_short_cusps(self):
        assert _house_of_degree(10.0, [0, 30, 60]) is None


# ═══════════════════════════════════════════════════════════════════════
# _degree_for_label
# ═══════════════════════════════════════════════════════════════════════

class TestDegreeForLabel:
    def test_direct_match(self):
        pos = {"Sun": 120.5}
        assert _degree_for_label(pos, "Sun") == pytest.approx(120.5)

    def test_alias_match(self):
        pos = {"AC": 45.0}
        # "Ascendant" should resolve via alias to the AC key
        result = _degree_for_label(pos, "Ascendant")
        assert result == pytest.approx(45.0)

    def test_none_positions(self):
        assert _degree_for_label(None, "Sun") is None

    def test_missing_label(self):
        pos = {"Sun": 120.0}
        assert _degree_for_label(pos, "Pluto") is None

    def test_wraps_to_360(self):
        pos = {"Sun": 400.0}
        result = _degree_for_label(pos, "Sun")
        assert result == pytest.approx(40.0)  # 400 % 360


# ═══════════════════════════════════════════════════════════════════════
# _normalise_aspect / _resolve_aspect
# ═══════════════════════════════════════════════════════════════════════

class TestNormaliseAspect:
    def test_clean_name(self):
        name, approx = _normalise_aspect("Trine")
        assert name == "Trine"
        assert approx is False

    def test_approx_suffix(self):
        name, approx = _normalise_aspect("Sextile_approx")
        assert name == "Sextile"
        assert approx is True

    def test_none(self):
        name, approx = _normalise_aspect(None)
        assert name == ""
        assert approx is False

    def test_whitespace(self):
        name, approx = _normalise_aspect("  Opposition  ")
        assert name == "Opposition"


class TestResolveAspect:
    def test_known_aspect(self):
        name, approx, spec = _resolve_aspect("Trine")
        assert name == "Trine"
        assert approx is False
        assert "angle" in spec

    def test_case_insensitive(self):
        name, approx, spec = _resolve_aspect("trine")
        assert name == "Trine"
        assert "angle" in spec

    def test_unknown_aspect(self):
        name, approx, spec = _resolve_aspect("Quintile")
        # Quintile may or may not be in ASPECTS; check it doesn't crash
        assert isinstance(spec, dict)

    def test_approx_flag(self):
        name, approx, spec = _resolve_aspect("Square_approx")
        assert name == "Square"
        assert approx is True


# ═══════════════════════════════════════════════════════════════════════
# _edge_record_to_components
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeRecordToComponents:
    def test_three_tuple(self):
        record = ("Sun", "Moon", {"aspect": "Trine"})
        a, b, asp = _edge_record_to_components(record)
        assert a == "Sun"
        assert b == "Moon"
        assert asp == "Trine"

    def test_two_tuple(self):
        record = (("Sun", "Moon"), {"aspect": "Square"})
        a, b, asp = _edge_record_to_components(record)
        assert a == "Sun"
        assert b == "Moon"
        assert asp == "Square"

    def test_invalid_record(self):
        a, b, asp = _edge_record_to_components("not a tuple")
        assert a is None
        assert b is None
        assert asp is None


# ═══════════════════════════════════════════════════════════════════════
# _expand_visible_canon
# ═══════════════════════════════════════════════════════════════════════

class TestExpandVisibleCanon:
    def test_expands_aliases(self):
        result = _expand_visible_canon(["AC"])
        assert "ascendant" in result
        assert "ac" in result

    def test_none_returns_none(self):
        assert _expand_visible_canon(None) is None

    def test_empty_returns_none(self):
        assert _expand_visible_canon([]) is None

    def test_non_aliased_name(self):
        result = _expand_visible_canon(["Sun"])
        assert "sun" in result


# ═══════════════════════════════════════════════════════════════════════
# DataFrame-based helpers
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_df():
    """Minimal chart DataFrame with objects + cusps."""
    return pd.DataFrame([
        {"Object": "Sun", "Longitude": 120.5},
        {"Object": "Moon", "Longitude": 200.3},
        {"Object": "AC", "Longitude": 45.0},
        {"Object": "MC", "Longitude": 315.0},
        {"Object": "Placidus 1H cusp", "Longitude": 45.0},
        {"Object": "Placidus 7H cusp", "Longitude": 225.0},
    ])


class TestObjectRows:
    def test_excludes_cusps(self, sample_df):
        result = _object_rows(sample_df)
        assert all("cusp" not in str(o).lower() for o in result["Object"])

    def test_keeps_planets(self, sample_df):
        result = _object_rows(sample_df)
        objects = list(result["Object"])
        assert "Sun" in objects
        assert "Moon" in objects


class TestCanonicalSeries:
    def test_produces_lowercase(self, sample_df):
        series = _canonical_series(sample_df)
        assert all(s == s.lower() for s in series)


class TestFindRow:
    def test_finds_sun(self, sample_df):
        row = _find_row(sample_df, ["Sun"])
        assert row is not None
        assert row["Object"] == "Sun"

    def test_finds_by_alias(self, sample_df):
        row = _find_row(sample_df, ["Ascendant"])
        assert row is not None
        assert float(row["Longitude"]) == pytest.approx(45.0)

    def test_not_found(self, sample_df):
        row = _find_row(sample_df, ["Pluto"])
        assert row is None


class TestGetAscendantDegree:
    def test_returns_float(self, sample_df):
        deg = get_ascendant_degree(sample_df)
        assert deg == pytest.approx(45.0)

    def test_default_zero(self):
        empty_df = pd.DataFrame([{"Object": "Sun", "Longitude": 100}])
        deg = get_ascendant_degree(empty_df)
        assert deg == 0.0


class TestExtractPositions:
    def test_extracts_all_objects(self, sample_df):
        pos = extract_positions(sample_df)
        assert "Sun" in pos
        assert "Moon" in pos
        # cusps should NOT appear
        assert not any("cusp" in k.lower() for k in pos)

    def test_with_visible_filter(self, sample_df):
        pos = extract_positions(sample_df, visible_names=["Sun"])
        assert "Sun" in pos
        assert "Moon" not in pos


class TestExtractCompassPositions:
    def test_extracts_angles(self, sample_df):
        pos = extract_compass_positions(sample_df)
        # AC and MC should be present
        assert "Ascendant" in pos or "AC" in pos or len(pos) >= 1

    def test_with_visible_filter(self, sample_df):
        # Filter to only include AC
        pos = extract_compass_positions(sample_df, visible_names=["AC"])
        assert len(pos) >= 1
