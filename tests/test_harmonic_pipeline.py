"""Verify the harmonic-edge pipeline end-to-end (calculate → serialize → roundtrip)."""
import pytest

from src.core.calc_v2 import build_aspect_edges, calculate_chart
from src.core.models_v2 import AstrologicalChart
from src.core.static_data import STANDARD_BASE_BODIES


@pytest.fixture(scope="module")
def harmonic_chart():
    """Build a test chart with edges attached (module-scoped, computed once)."""
    df, asp_df, plot_data, chart = calculate_chart(
        year=2000, month=1, day=1, hour=12, minute=0,
        tz_offset=0, lat=40.7128, lon=-74.0060,
        input_is_ut=True, house_system="placidus",
        include_aspects=True, unknown_time=False,
        display_name="Test", city="NYC",
    )
    edges_major, edges_minor, edges_harmonic = build_aspect_edges(chart)
    chart.edges_major = [tuple(e) for e in edges_major]
    chart.edges_minor = [tuple(e) for e in edges_minor]
    chart.edges_harmonic = [tuple(e) for e in edges_harmonic]
    return chart


def test_edge_detection_counts(harmonic_chart):
    assert len(harmonic_chart.edges_major) > 0, "Should detect at least one major edge"
    assert isinstance(harmonic_chart.edges_harmonic, list)


def test_json_roundtrip_preserves_harmonics(harmonic_chart):
    j = harmonic_chart.to_json()
    assert "edges_harmonic" in j
    chart2 = AstrologicalChart.from_json(j)
    assert len(chart2.edges_harmonic) == len(harmonic_chart.edges_harmonic)


def test_harmonic_edge_meta_is_dict(harmonic_chart):
    j = harmonic_chart.to_json()
    chart2 = AstrologicalChart.from_json(j)
    if chart2.edges_harmonic:
        e = chart2.edges_harmonic[0]
        assert isinstance(e[2], dict), f"Edge meta should be dict, got {type(e[2])}"
        assert "aspect" in e[2]


def test_filter_with_enabled_toggles(harmonic_chart):
    j = harmonic_chart.to_json()
    chart2 = AstrologicalChart.from_json(j)
    enabled = {"Quintile", "Biquintile"}
    filtered = [
        e for e in chart2.edges_harmonic
        if e[0] in STANDARD_BASE_BODIES and e[1] in STANDARD_BASE_BODIES
        and isinstance(e[2], dict) and e[2].get("aspect") in enabled
    ]
    # Just verify it doesn't crash; count depends on the chart
    assert isinstance(filtered, list)


def test_filter_with_empty_toggles(harmonic_chart):
    j = harmonic_chart.to_json()
    chart2 = AstrologicalChart.from_json(j)
    enabled_empty = set()
    filtered = [
        e for e in chart2.edges_harmonic
        if e[0] in STANDARD_BASE_BODIES and e[1] in STANDARD_BASE_BODIES
        and isinstance(e[2], dict) and e[2].get("aspect") in enabled_empty
    ]
    assert len(filtered) == 0, "Empty toggles should yield zero edges"
