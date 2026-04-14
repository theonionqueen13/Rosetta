"""Tests for the planetary strength / dignity calculation engine.

Refactored from standalone script to proper pytest functions.
Uses a module-scoped fixture with the same birth data as the original script.
"""
import pytest

from src.core.calc_v2 import calculate_chart


# ---------------------------------------------------------------------------
# Module-scoped fixture — same chart the original script used.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def strength_chart():
    """Compute a chart with full planetary states for dignity testing."""
    _df, _asp, _plot, chart = calculate_chart(
        year=1990, month=6, day=15, hour=14, minute=30,
        tz_offset=-5, lat=40.7128, lon=-74.0060,
        tz_name="America/New_York",
        include_aspects=True,
        display_name="Dignity Test",
    )
    return chart


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
CLASSICAL_PLANETS = ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn")

DIGNITY_FLAGS = (
    "domicile", "exaltation", "triplicity", "term", "face",
    "detriment", "fall", "peregrine",
)


def test_planetary_states_populated(strength_chart):
    """Planetary states should be computed for classical + outer planets."""
    assert len(strength_chart.planetary_states) > 0, "No planetary states computed"
    actual_names = set(strength_chart.planetary_states.keys())
    expected = set(CLASSICAL_PLANETS)
    assert expected.issubset(actual_names), f"Missing states for: {expected - actual_names}"


def test_sect_derivable(strength_chart):
    """chart_sect_from_chart should return 'day' or 'night' for this chart."""
    from src.core.calc_v2 import chart_sect_from_chart
    sect = chart_sect_from_chart(strength_chart)
    assert sect.lower() in ("day", "night", "diurnal", "nocturnal"), (
        f"Expected a valid sect string, got '{sect}'"
    )


def test_sun_exempt_from_solar_proximity(strength_chart):
    """Sun should not have combustion or cazimi labels."""
    sun_state = strength_chart.planetary_states.get("Sun")
    assert sun_state is not None, "Sun state should exist"
    assert sun_state.solar_proximity_label == "", (
        f"Sun should be exempt from solar proximity, "
        f"got '{sun_state.solar_proximity_label}'"
    )


def test_essential_dignity_flags_resolved(strength_chart):
    """Every classical planet should have at least one dignity flag set."""
    for name in CLASSICAL_PLANETS:
        state = strength_chart.planetary_states.get(name)
        assert state is not None, f"{name} state missing"
        ed = state.essential_dignity
        active = [f for f in DIGNITY_FLAGS if getattr(ed, f)]
        assert len(active) > 0, f"{name}: no essential dignity flags resolved"


def test_quality_index_in_range(strength_chart):
    """quality_index should be in (-1, 1) (tanh output)."""
    for name, state in strength_chart.planetary_states.items():
        assert -1.0 <= state.quality_index <= 1.0, (
            f"{name} quality_index out of range: {state.quality_index}"
        )


def test_power_index_non_negative(strength_chart):
    """power_index should be >= 0."""
    for name, state in strength_chart.planetary_states.items():
        assert state.power_index >= 0, (
            f"{name} power_index negative: {state.power_index}"
        )


def test_house_score_set(strength_chart):
    """Every state should have a house_score > 0 (angular/succedent/cadent)."""
    for name in CLASSICAL_PLANETS:
        state = strength_chart.planetary_states[name]
        assert state.house_score > 0, (
            f"{name} house_score should be positive, got {state.house_score}"
        )


def test_motion_label_set(strength_chart):
    """Every classical planet should have a motion label."""
    valid = {"direct", "retrograde", "stationary_direct", "stationary_retrograde"}
    for name in CLASSICAL_PLANETS:
        state = strength_chart.planetary_states[name]
        assert state.motion_label in valid, (
            f"{name} unexpected motion_label: '{state.motion_label}'"
        )


def test_mutual_receptions_list(strength_chart):
    """mutual_receptions should be a list (possibly empty) of 3-tuples."""
    assert isinstance(strength_chart.mutual_receptions, list)
    for entry in strength_chart.mutual_receptions:
        assert len(entry) == 3, f"Expected 3-tuple, got {entry}"
