import pandas as pd

from src.core.models_v2 import AstrologicalChart, ChartObject, static_db


def test_chart_object_from_dict_roundtrip():
    row = {
        "Object": "Sun",
        "Glyph": "☉",
        "Longitude": 15.5,
        "Absolute Degree": 15.5,
        "Sign": "Aries",
        "Sign Index": 1,
        "Degree In Sign": 15,
        "Minute In Sign": 30,
        "Second In Sign": 0,
        "DMS": "15°30'00\"",
        "Sabian Index": 16,
        "Sabian Symbol": "A test symbol",
        "Fixed Star Conj": "",
        "Retrograde Bool": False,
        "Retrograde": "",
        "OOB Status": "No",
        "Dignity": "",
        "Ruled by (sign)": "Mars",
        "Latitude": 0.0,
        "Declination": 0.0,
        "Distance": 1.0,
        "Speed": 1.0,
        "Placidus House": 1,
        "Placidus House Rulers": "Mars",
        "Equal House": 1,
        "Equal House Rulers": "Mars",
        "Whole Sign House": 1,
        "Whole Sign House Rulers": "Mars",
    }

    obj = ChartObject.from_dict(row, static=static_db)
    out = obj.to_dict()

    assert out["Object"] == "Sun"
    assert out["Sign"] == "Aries"
    assert out["Longitude"] == 15.5
    assert out["Placidus House"] == 1
    assert out["Ruled by (sign)"] == "Mars"


def test_astrological_chart_from_dataframe():
    rows = [
        {
            "Object": "Sun",
            "Glyph": "☉",
            "Longitude": 15.5,
            "Absolute Degree": 15.5,
            "Sign": "Aries",
            "Sign Index": 1,
            "Degree In Sign": 15,
            "Minute In Sign": 30,
            "Second In Sign": 0,
            "DMS": "15°30'00\"",
            "Sabian Index": 16,
            "Sabian Symbol": "A test symbol",
            "Retrograde Bool": False,
            "Retrograde": "",
            "OOB Status": "No",
            "Dignity": "",
            "Ruled by (sign)": "Mars",
            "Latitude": 0.0,
            "Declination": 0.0,
            "Distance": 1.0,
            "Speed": 1.0,
            "Placidus House": 1,
            "Placidus House Rulers": "Mars",
            "Equal House": 1,
            "Equal House Rulers": "Mars",
            "Whole Sign House": 1,
            "Whole Sign House Rulers": "Mars",
        },
        {
            "Object": "Placidus 1H cusp",
            "Longitude": 15.0,
        },
    ]
    df = pd.DataFrame(rows)

    chart = AstrologicalChart.from_dataframe(
        df,
        chart_datetime="2024-01-01 00:00:00",
        timezone="UTC",
        latitude=40.0,
        longitude=-74.0,
        static=static_db,
    )

    assert chart.objects
    assert chart.house_cusps
