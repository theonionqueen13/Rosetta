"""Unit tests for chart_models (ChartObject, HouseCusp, AstrologicalChart).

Updated for the rich-model API introduced in Phase 2 refactor:
  - ChartObject.object_name is now an Object dataclass (use .object_name.name for the name string)
  - ChartObject.retrograde is now a bool (True == retrograde)
  - ChartObject is constructed via ChartObject.from_dict(row) which resolves
    Object/Sign/House instances from static_db automatically
"""
import pandas as pd
from src.core.chart_models import ChartObject, HouseCusp, AstrologicalChart


# ---------------------------------------------------------------------------
# Helper: minimal row dict for a chart object
# ---------------------------------------------------------------------------

def _sun_row():
    return {
        "Object": "Sun",
        "Longitude": 45.5,
        "Sign": "Taurus",
        "DMS": "15°30'00\"",
        "Sabian Index": 16,
        "Sabian Symbol": "A woman sprinkling water",
        "OOB Status": "No",
        "Dignity": "domicile",
        "Ruled by (sign)": "Venus",
        "Latitude": 0.1,
        "Declination": 15.0,
        "Distance": 1.0,
        "Speed": 1.0,
        "Glyph": "☉",
        "Retrograde Bool": False,
        "Retrograde": "",
        "Placidus House": 2,
        "Equal House": 2,
        "Whole Sign House": 2,
        "Placidus House Rulers": "Venus",
        "Equal House Rulers": "Venus",
        "Whole Sign House Rulers": "Venus",
        "Degree In Sign": 15,
        "Minute In Sign": 30,
    }


def _moon_row():
    return {
        "Object": "Moon",
        "Longitude": 90.0,
        "Sign": "Cancer",
        "DMS": "0°00'00\"",
        "Sabian Index": 1,
        "Sabian Symbol": "",
        "OOB Status": "No",
        "Dignity": None,
        "Ruled by (sign)": "Moon",
        "Latitude": 0.0,
        "Declination": 0.0,
        "Distance": 0.0,
        "Speed": 0.0,
        "Glyph": "☽",
        "Retrograde Bool": False,
        "Retrograde": "",
        "Placidus House": 4,
        "Equal House": 4,
        "Whole Sign House": 4,
        "Degree In Sign": 0,
    }


# ---------------------------------------------------------------------------
# ChartObject
# ---------------------------------------------------------------------------

def test_chart_object_to_dict_schema():
    """ChartObject.to_dict emits all columns consumers expect."""
    obj = ChartObject.from_dict(_sun_row())
    d = obj.to_dict()
    # Rich API: object name is stored as Object instance; .to_dict() emits the string
    assert d["Object"] == "Sun"
    assert d["Longitude"] == 45.5
    assert d["Glyph"] == "☉"
    assert d["Retrograde Bool"] is False
    assert d["Placidus House"] == 2


def test_chart_object_from_dict_roundtrip():
    row = {
        "Object": "Mars",
        "Longitude": 200.5,
        "Sign": "Scorpio",
        "DMS": "20°30'00\"",
        "Sabian Index": 21,
        "Sabian Symbol": "",
        "Retrograde": "Rx",
        "OOB Status": "No",
        "Dignity": "domicile",
        "Ruled by (sign)": "Pluto, Mars",
        "Latitude": 0.0,
        "Declination": -10.0,
        "Distance": 1.5,
        "Speed": -0.5,
        "Glyph": "♂",
        "Reception": "",
        "Retrograde Bool": True,
        "Placidus House": 8,
        "Equal House": 8,
        "Whole Sign House": 8,
        "Placidus House Rulers": "Pluto, Mars",
        "Degree In Sign": 20,
    }
    obj = ChartObject.from_dict(row)
    # New API: object_name is an Object instance
    assert obj.object_name.name == "Mars"
    # New API: retrograde is bool
    assert obj.retrograde is True
    d2 = obj.to_dict()
    assert d2["Object"] == "Mars"
    assert d2["Retrograde Bool"] is True
    assert d2["Placidus House"] == 8


# ---------------------------------------------------------------------------
# HouseCusp
# ---------------------------------------------------------------------------

def test_house_cusp_to_dict_schema():
    """HouseCusp.to_dict outputs Object and Longitude (drawing_v2/dispositor format)."""
    cusp = HouseCusp(cusp_number=1, absolute_degree=12.5, house_system="placidus")
    d = cusp.to_dict()
    assert d["Object"] == "Placidus 1H cusp"
    assert "Longitude" in d
    assert d["Longitude"] == 12.5
    assert "Computed Absolute Degree" not in d

    cusp_eq = HouseCusp(cusp_number=5, absolute_degree=120.0, house_system="equal")
    d_eq = cusp_eq.to_dict()
    assert d_eq["Object"] == "Equal 5H cusp"


def test_house_cusp_whole_sign():
    cusp = HouseCusp(cusp_number=7, absolute_degree=180.0, house_system="whole")
    d = cusp.to_dict()
    assert d["Object"] == "Whole Sign 7H cusp"


def test_house_cusp_from_dict():
    row = {"Object": "Placidus 3H cusp", "Longitude": 60.5}
    cusp = HouseCusp.from_dict(row)
    assert cusp.cusp_number == 3
    assert cusp.absolute_degree == 60.5
    assert cusp.house_system == "placidus"


def test_house_cusp_to_json_roundtrip():
    cusp = HouseCusp(cusp_number=10, absolute_degree=275.0, house_system="equal")
    restored = HouseCusp.from_json(cusp.to_json())
    assert restored.cusp_number == 10
    assert restored.absolute_degree == 275.0
    assert restored.house_system == "equal"


# ---------------------------------------------------------------------------
# AstrologicalChart
# ---------------------------------------------------------------------------

def test_astrological_chart_to_dataframe():
    """AstrologicalChart.to_dataframe produces object rows + cusp rows."""
    obj = ChartObject.from_dict(_moon_row())
    cusp = HouseCusp(cusp_number=1, absolute_degree=10.0, house_system="placidus")
    chart = AstrologicalChart(
        objects=[obj],
        house_cusps=[cusp],
        chart_datetime="2024-01-01 12:00:00",
        timezone="UTC",
        latitude=40.0,
        longitude=-74.0,
    )
    df = chart.to_dataframe()
    assert len(df) == 2
    obj_row = df.iloc[0]
    assert obj_row["Object"] == "Moon"
    assert obj_row["Longitude"] == 90.0
    cusp_row = df.iloc[1]
    assert "Placidus 1H cusp" in str(cusp_row["Object"])
    assert cusp_row["Longitude"] == 10.0


def test_astrological_chart_from_dataframe():
    df = pd.DataFrame([
        {
            "Object": "Sun", "Longitude": 0.0, "Sign": "Aries", "DMS": "0°",
            "Sabian Index": 1, "Sabian Symbol": "", "Retrograde": "", "OOB Status": "No",
            "Dignity": None, "Ruled by (sign)": "Mars", "Latitude": 0.0,
            "Declination": 0.0, "Distance": 1.0, "Speed": 1.0,
            "Retrograde Bool": False, "Placidus House": 1, "Degree In Sign": 0,
        },
        {"Object": "Placidus 1H cusp", "Longitude": 350.0},
    ])
    chart = AstrologicalChart.from_dataframe(
        df, chart_datetime="2024-01-01", timezone="UTC", latitude=40.0, longitude=-74.0
    )
    assert len(chart.objects) == 1
    # New API: object_name is an Object instance
    assert chart.objects[0].object_name.name == "Sun"
    assert len(chart.house_cusps) == 1
    assert chart.house_cusps[0].cusp_number == 1


def test_get_object():
    """AstrologicalChart.get_object finds by Object.name."""
    obj = ChartObject.from_dict(_sun_row())
    chart = AstrologicalChart(
        objects=[obj],
        house_cusps=[],
        chart_datetime="",
        timezone="",
        latitude=0.0,
        longitude=0.0,
    )
    found = chart.get_object("Sun")
    assert found is not None
    assert found.object_name.name == "Sun"
    assert chart.get_object("Moon") is None

