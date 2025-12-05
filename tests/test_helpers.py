import math

from rosetta.helpers import build_aspect_graph, format_dms, load_star_df


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
