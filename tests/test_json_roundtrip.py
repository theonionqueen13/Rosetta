"""Verify chart JSON serialization roundtrip (calculate → to_json → dumps)."""
import json

import pytest

from src.core.calc_v2 import build_aspect_edges, calculate_chart
from src.core.patterns_v2 import (
    detect_minor_links_from_chart,
    generate_combo_groups,
    prepare_pattern_inputs,
)


@pytest.fixture(scope="module")
def full_chart():
    """Build a fully-populated test chart with patterns and combos (module-scoped)."""
    df, asp_df, plot_data, chart = calculate_chart(
        year=1990, month=7, day=1, hour=12, minute=0,
        tz_offset=0, lat=40.71, lon=-74.01, tz_name="America/New_York",
        house_system="placidus", include_aspects=True,
        display_name="Test", city="New York",
    )
    chart.df_positions = df
    chart.aspect_df = asp_df
    edges_major, edges_minor, _edges_harmonic = build_aspect_edges(chart)
    chart.edges_major = edges_major
    chart.edges_minor = edges_minor
    pos, patterns, major_edges_all = prepare_pattern_inputs(df, edges_major)
    chart.aspect_groups = [sorted(list(s)) for s in patterns]
    chart.positions = pos
    chart.major_edges_all = major_edges_all
    filaments, singleton_map = detect_minor_links_from_chart(chart, edges_major)
    chart.filaments = filaments
    chart.singleton_map = singleton_map
    chart.combos = generate_combo_groups(filaments)
    return chart


def test_to_json_produces_valid_json(full_chart):
    d = full_chart.to_json()
    s = json.dumps(d)
    assert len(s) > 0, "Serialized JSON should be non-empty"


def test_to_json_has_expected_keys(full_chart):
    d = full_chart.to_json()
    for key in ("objects", "edges_major", "aspect_groups", "singleton_map"):
        assert key in d, f"Missing key: {key}"


def test_to_json_objects_count(full_chart):
    d = full_chart.to_json()
    assert len(d["objects"]) > 0, "Should have at least one object"


def test_to_json_edges_major_count(full_chart):
    d = full_chart.to_json()
    assert len(d["edges_major"]) > 0, "Should have at least one major edge"
