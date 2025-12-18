import math
import tempfile

import pytest

import rosetta.helpers
from rosetta.helpers import build_aspect_graph, format_dms, load_star_df, initialize_swisseph


@pytest.fixture(autouse=True)
def reset_swisseph_state():
    """Reset swisseph state before each test."""
    rosetta.helpers._swe = None
    rosetta.helpers._swe_path = None
    yield


def _normalize_components(components):
    return sorted([tuple(sorted(component)) for component in components])


def test_format_dms_is_deterministic():
    values = [
        (12.3456, {}),
        (-0.5123, {"is_speed": True}),
        (45.5, {"is_latlon": True}),
    ]

    for value, kwargs in values:
        first = format_dms(value, **kwargs)
        for _ in range(3):
            assert format_dms(value, **kwargs) == first


def test_build_aspect_graph_is_deterministic():
    positions = {
        "Sun": 0.0,
        "Moon": 2.5,
        "Mars": 120.0,
        "Venus": 122.0,
        "Jupiter": 250.0,
    }

    first = _normalize_components(build_aspect_graph(positions))
    second = _normalize_components(build_aspect_graph(positions))

    assert first == second
    assert first == [
        ("Mars", "Moon", "Sun", "Venus"),
    ]


def test_load_star_df_is_cached():
    first = load_star_df()
    second = load_star_df()

    assert first is second
    assert not math.isnan(first["Degree"].iloc[0])


def test_load_star_df_cache_clearing():
    """Test that cache can be cleared and rebuilt."""
    first = load_star_df()
    load_star_df.cache_clear()
    second = load_star_df()

    assert first is not second  # Different instances after clear
    assert first.equals(second)  # But same data


def test_initialize_swisseph_is_cached():
    """Test that initialize_swisseph returns the same module instance on subsequent calls."""
    first = initialize_swisseph()
    second = initialize_swisseph()
    assert first is second


def test_initialize_swisseph_default_path():
    """Test that default ephemeris path is used when none is provided."""
    swe = initialize_swisseph()
    # Just verify it returns a module without error
    assert swe is not None
    assert hasattr(swe, 'set_ephe_path')


def test_initialize_swisseph_path_immutable():
    """Test that ephemeris path cannot be changed after initialization."""
    # Initialize with default path (or already initialized)
    initialize_swisseph()
    
    # Try to change the path - should raise ValueError
    with tempfile.TemporaryDirectory() as tmpdir:
        with pytest.raises(ValueError, match="Cannot change ephemeris path"):
            initialize_swisseph(tmpdir)
