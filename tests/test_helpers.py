import json

import pytest

from rosetta.helpers import (
    build_aspect_graph,
    calculate_oob_status,
    format_dms,
    format_longitude,
    parse_declination,
)


def test_parse_declination_handles_compass_style():
    decimal, direction = parse_declination("23°26' N")
    assert round(decimal, 3) == pytest.approx(23.433, abs=1e-3)
    assert direction == "N"


def test_parse_declination_allows_negative_numeric():
    decimal, direction = parse_declination(-10.5)
    assert decimal == -10.5
    assert direction == "S"


def test_format_dms_with_speed_rounds_seconds():
    assert format_dms(-12.9994, is_speed=True) == "-12°59′58″"


def test_format_longitude_rolls_over_signs():
    assert format_longitude(33.5) == "Taurus 3°30′"
    assert format_longitude(359.9) == "Pisces 29°54′"


def test_build_aspect_graph_groups_major_links():
    positions = {"Sun": 0.0, "Moon": 180.0, "Mars": 60.0, "Venus": 240.0}
    components = build_aspect_graph(positions)
    normalized = sorted([sorted(component) for component in components])
    assert normalized == [["Mars", "Moon", "Sun", "Venus"]]


def test_calculate_oob_status_labels_boundaries():
    assert calculate_oob_status("23°10' N") == "No"
    assert calculate_oob_status("24°00' S").startswith("OOB by")
    assert calculate_oob_status("26°00' N").startswith("Extreme OOB")


def test_app_cli_aspect_components(tmp_path, capsys):
    from rosetta.app import main

    rc = main(["aspect-components", "Sun=0", "Moon=180", "Mars=60"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    parsed = json.loads(out)
    assert parsed == [["Mars", "Moon", "Sun"]]
