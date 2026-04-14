"""Unit tests for chart_models (ChartObject, HouseCusp, AstrologicalChart)."""
import pandas as pd
from src.core.chart_models import ChartObject, HouseCusp, AstrologicalChart


def test_chart_object_to_dict_schema():
    """ChartObject.to_dict emits all columns consumers expect."""
    obj = ChartObject(
        object_name="Sun",
        longitude=45.5,
        sign="Taurus",
        dms="15°30'00\"",
        sabian_index=46,
        sabian_symbol="A woman sprinkling water",
        retrograde="",
        oob_status="No",
        dignity="domicile",
        ruled_by_sign="Venus",
        latitude=0.1,
        declination=15.0,
        distance=1.0,
        speed=1.0,
        glyph="☉",
        reception="",
        retrograde_bool=False,
        fixed_star_conj="",
        placidus_house=2,
        placidus_house_rulers="Venus",
    )
    d = obj.to_dict()
    assert d["Object"] == "Sun"
    assert d["Longitude"] == 45.5
    assert d["Glyph"] == "☉"
    assert d["Retrograde Bool"] is False
    assert d["Reception"] == ""
    assert d["Fixed Star Conj"] == ""
    assert d["Placidus House"] == 2
    assert d["Placidus House Rulers"] == "Venus"


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


def test_astrological_chart_to_dataframe():
    """AstrologicalChart.to_dataframe produces object rows + cusp rows."""
    obj = ChartObject(
        object_name="Moon",
        longitude=90.0,
        sign="Cancer",
        dms="0°00'00\"",
        sabian_index=91,
        sabian_symbol="",
        retrograde="",
        oob_status="No",
        dignity=None,
        ruled_by_sign="Moon",
        latitude=0.0,
        declination=0.0,
        distance=0.0,
        speed=0.0,
    )
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


def test_chart_object_from_dict_roundtrip():
    row = {
        "Object": "Mars",
        "Longitude": 200.5,
        "Sign": "Scorpio",
        "DMS": "20°30'00\"",
        "Sabian Index": 221,
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
        "Fixed Star Conj": "",
        "Placidus House": 8,
        "Placidus House Rulers": "Pluto, Mars",
    }
    obj = ChartObject.from_dict(row)
    assert obj.object_name == "Mars"
    assert obj.retrograde_bool is True
    assert obj.placidus_house == 8
    d2 = obj.to_dict()
    assert d2["Object"] == "Mars"
    assert d2["Retrograde Bool"] is True


def test_house_cusp_from_dict():
    row = {"Object": "Placidus 3H cusp", "Longitude": 60.5}
    cusp = HouseCusp.from_dict(row)
    assert cusp.cusp_number == 3
    assert cusp.absolute_degree == 60.5
    assert cusp.house_system == "placidus"


def test_astrological_chart_from_dataframe():
    df = pd.DataFrame([
        {"Object": "Sun", "Longitude": 0.0, "Sign": "Aries", "DMS": "0°", "Sabian Index": 1,
         "Sabian Symbol": "", "Retrograde": "", "OOB Status": "No", "Dignity": None,
         "Ruled by (sign)": "Mars", "Latitude": 0.0, "Declination": 0.0, "Distance": 1.0, "Speed": 1.0},
        {"Object": "Placidus 1H cusp", "Longitude": 350.0},
    ])
    chart = AstrologicalChart.from_dataframe(df, chart_datetime="2024-01-01", timezone="UTC", latitude=40.0, longitude=-74.0)
    assert len(chart.objects) == 1
    assert chart.objects[0].object_name == "Sun"
    assert len(chart.house_cusps) == 1
    assert chart.house_cusps[0].cusp_number == 1


def test_get_object_with_alias():
    obj_ac = ChartObject(
        object_name="AC",
        longitude=0.0,
        sign="Aries",
        dms="0°",
        sabian_index=1,
        sabian_symbol="",
        retrograde="",
        oob_status="No",
        dignity=None,
        ruled_by_sign="",
        latitude=0.0,
        declination=0.0,
        distance=0.0,
        speed=0.0,
    )
    chart = AstrologicalChart(
        objects=[obj_ac],
        house_cusps=[],
        chart_datetime="",
        timezone="",
        latitude=0.0,
        longitude=0.0,
    )
    assert chart.get_object("AC") is not None
    assert chart.get_object("Ascendant") is not None  # alias
    assert chart.get_object("DC") is None
