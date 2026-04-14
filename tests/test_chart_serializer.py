"""
tests/test_chart_serializer.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verify that chart_serializer produces valid, JSON-safe output with all
expected fields present.
"""
import json
import math
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

# ── Minimal stubs so the serializer can be imported without a full
#    Swiss Ephemeris / Streamlit environment ──────────────────────────
import sys, types

# The serializer imports from models_v2 → lookup_v2 → swisseph, and from
# models_v2 → static_db.  We rely on the real modules being importable
# from the project root.  If they are not (CI, etc.), skip gracefully.
_skip_reason = ""
try:
    from src.rendering.chart_serializer import (
        serialize_chart_for_rendering,
        _serialize_object,
        _serialize_aspect_edge,
        _serialize_houses,
        _serialize_signs,
        _serialize_shapes,
        _safe_float,
        _safe_str,
    )
    from src.core.models_v2 import (
        AstrologicalChart,
        Object as AstroObject,
        Sign,
        House,
        Element,
        Modality,
        Polarity,
        Aspect,
        SabianSymbol,
        ChartObject,
        PlanetaryState,
        EssentialDignity,
        CircuitNode,
        CircuitEdge,
        ShapeCircuit,
        CircuitSimulation,
        DetectedShape,
        HouseCusp,
    )
    HAS_DEPS = True
except ImportError as exc:
    HAS_DEPS = False
    _skip_reason = str(exc)

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason=f"Dependencies not available: {_skip_reason}")


# ---------------------------------------------------------------------------
# Fixtures: build a minimal but realistic chart
# ---------------------------------------------------------------------------

def _make_element(name):
    return Element(name=name, glyph="", short_meaning="", long_meaning="")

def _make_modality(name):
    return Modality(name=name, glyph="")

def _make_polarity(name):
    return Polarity(name=name, glyph="")

def _make_sign(name, index, element="Fire"):
    return Sign(
        name=name, glyph="♈️", sign_index=index,
        element=_make_element(element),
        modality=_make_modality("Cardinal"),
        polarity=_make_polarity("Yang"),
    )

def _make_house(num):
    return House(number=num, short_meaning=f"House {num}", life_domain=f"Domain {num}")

def _make_object(name, glyph="☉"):
    return AstroObject(
        name=name, swisseph_id=0, glyph=glyph,
        object_type="Planet", narrative_role="Character",
        short_meaning=f"{name} meaning", long_meaning=f"Long {name} meaning",
        keywords=["keyword1", "keyword2"],
    )

def _make_chart_object(name, longitude, sign_name="Aries", house_num=1, retrograde=False):
    obj = _make_object(name)
    sign = _make_sign(sign_name, 1)
    house = _make_house(house_num)
    sabian = SabianSymbol(sign=sign_name, degree=int(longitude % 30) + 1, symbol=f"Sabian for {name}")
    ps = PlanetaryState(
        planet_name=name,
        essential_dignity=EssentialDignity(domicile=(name == "Sun")),
        raw_authority=3.5,
        quality_index=0.46,
        house_score=5.0 if house_num in (1, 10, 7, 4) else 3.0,
        motion_score=2.0,
        motion_label="direct",
        solar_proximity_score=0.0,
        solar_proximity_label="",
        potency_score=7.0,
        power_index=4.2,
    )
    return ChartObject(
        object_name=obj,
        glyph=obj.glyph,
        longitude=longitude,
        abs_deg=longitude,
        sign=sign,
        dms=f"{int(longitude % 30)}° {sign_name[:2]}",
        latitude=0.0,
        declination=0.0,
        placidus_house=house,
        equal_house=house,
        whole_sign_house=house,
        sabian_symbol=sabian,
        speed=1.0,
        retrograde=retrograde,
        planetary_state=ps,
    )

def _make_house_cusp(num, degree, system="Placidus"):
    return HouseCusp(cusp_number=num, absolute_degree=degree, house_system=system)


def _make_minimal_chart():
    """Build a minimal AstrologicalChart with Sun, Moon, Saturn for testing."""
    sun = _make_chart_object("Sun", 15.0, "Aries", 1)
    moon = _make_chart_object("Moon", 120.0, "Leo", 5)
    saturn = _make_chart_object("Saturn", 280.0, "Capricorn", 10, retrograde=True)
    ac = _make_chart_object("Ascendant", 0.0, "Aries", 1)

    cusps = [_make_house_cusp(i + 1, (i * 30.0) % 360.0) for i in range(12)]

    chart = AstrologicalChart(
        objects=[sun, moon, saturn, ac],
        house_cusps=cusps,
        chart_datetime="2024-01-01 12:00:00",
        timezone="UTC",
        latitude=40.7128,
        longitude=-74.006,
    )
    chart.edges_major = [("Sun", "Moon", {"aspect": "Trine"})]
    chart.edges_minor = [("Sun", "Saturn", {"aspect": "Quincunx"})]
    chart.aspect_groups = [["Sun", "Moon"]]
    chart.shapes = [
        DetectedShape(
            shape_id=1,
            shape_type="Grand Trine",
            parent=0,
            members=["Sun", "Moon"],
            edges=[(("Sun", "Moon"), "Trine")],
        )
    ]
    chart.singleton_map = {"Saturn": True}
    chart.positions = {"Sun": 15.0, "Moon": 120.0, "Saturn": 280.0}
    chart.major_edges_all = [(("Sun", "Moon"), "Trine")]
    chart.filaments = []
    chart.combos = {}
    chart.unknown_time = False

    # Attach circuit simulation
    node_sun = CircuitNode(planet_name="Sun", power_index=4.2, effective_power=5.0,
                           received_power=1.0, emitted_power=0.8, friction_load=0.2)
    node_moon = CircuitNode(planet_name="Moon", power_index=3.5, effective_power=4.0,
                            received_power=0.8, emitted_power=0.7, friction_load=0.1)
    edge = CircuitEdge(node_a="Sun", node_b="Moon", aspect_type="Trine",
                       conductance=0.9, transmitted_power=3.0, friction_heat=0.0)
    sc = ShapeCircuit(
        shape_type="Grand Trine", shape_id=1,
        nodes=[node_sun, node_moon], edges=[edge],
        total_throughput=3.0, resonance_score=0.85,
        dominant_node="Sun", flow_characterization="Harmonious flow",
    )
    chart.circuit_simulation = CircuitSimulation(
        shape_circuits=[sc],
        node_map={"Sun": node_sun, "Moon": node_moon},
        sn_nn_path=[],
    )

    return chart


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSafeHelpers:
    def test_safe_float_normal(self):
        assert _safe_float(3.14159) == 3.14159

    def test_safe_float_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) == 0.0

    def test_safe_float_inf(self):
        assert _safe_float(float("inf")) == 0.0

    def test_safe_float_string(self):
        assert _safe_float("not a number") == 0.0

    def test_safe_str_none(self):
        assert _safe_str(None) == ""

    def test_safe_str_value(self):
        assert _safe_str(42) == "42"


class TestSerializeChart:
    def test_returns_dict(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert isinstance(result, dict)

    def test_top_level_keys(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        expected_keys = {
            "objects", "aspects", "houses", "signs", "shapes",
            "singletons", "circuit_summary", "patterns", "config", "colors", "highlights",
            "header", "moon_phase",
        }
        assert expected_keys == set(result.keys())

    def test_json_serializable(self):
        """The entire output must be JSON-serializable (no numpy, datetime, etc.)."""
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        serialized = json.dumps(result)
        assert isinstance(serialized, str)
        # Roundtrip
        parsed = json.loads(serialized)
        assert parsed["config"]["asc_degree"] == 0.0

    def test_objects_present(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        names = [o["name"] for o in result["objects"]]
        assert "Sun" in names
        assert "Moon" in names
        assert "Saturn" in names

    def test_object_fields(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        sun = next(o for o in result["objects"] if o["name"] == "Sun")
        assert sun["longitude"] == 15.0
        assert sun["sign"] == "Aries"
        assert sun["house"] == 1
        assert sun["retrograde"] is False
        assert sun["meaning_short"] == "Sun meaning"
        assert "keyword1" in sun["keywords"]
        # Planetary state
        assert sun["planetary_state"]["power_index"] == 4.2
        assert sun["planetary_state"]["essential_dignity"]["domicile"] is True
        # Circuit node
        assert sun["circuit_node"]["effective_power"] == 5.0

    def test_retrograde_object(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        saturn = next(o for o in result["objects"] if o["name"] == "Saturn")
        assert saturn["retrograde"] is True

    def test_aspects_present(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert len(result["aspects"]) >= 1
        trine = next((a for a in result["aspects"] if a["aspect"] == "Trine"), None)
        assert trine is not None
        assert trine["obj_a"] == "Sun"
        assert trine["obj_b"] == "Moon"
        assert trine["is_major"] is True

    def test_aspect_circuit_data(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        trine = next(a for a in result["aspects"] if a["aspect"] == "Trine")
        assert trine["conductance"] == 0.9
        assert trine["transmitted_power"] == 3.0

    def test_houses_count(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert len(result["houses"]) == 12

    def test_signs_count(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert len(result["signs"]) == 12

    def test_signs_have_colors(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        for sign in result["signs"]:
            assert "band_color" in sign
            assert "glyph_color" in sign

    def test_shapes_present(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert len(result["shapes"]) == 1
        assert result["shapes"][0]["type"] == "Grand Trine"

    def test_shape_circuit_data(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        shape = result["shapes"][0]
        assert "circuit" in shape
        assert shape["circuit"]["resonance_score"] == 0.85
        assert shape["circuit"]["dominant_node"] == "Sun"

    def test_singletons(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert "Saturn" in result["singletons"]

    def test_config(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart, dark_mode=True, label_style="text")
        assert result["config"]["dark_mode"] is True
        assert result["config"]["label_style"] == "text"

    def test_colors_palette(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert "group_colors" in result["colors"]
        assert "subshape_colors" in result["colors"]
        assert len(result["colors"]["group_colors"]) > 0

    def test_patterns(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        assert len(result["patterns"]) == 1
        assert "Sun" in result["patterns"][0]

    def test_circuit_summary(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart)
        cs = result["circuit_summary"]
        assert cs["shape_circuit_count"] == 1

    def test_highlights_passthrough(self):
        chart = _make_minimal_chart()
        hl = {"objects": ["Saturn"], "clear": False}
        result = serialize_chart_for_rendering(chart, highlights=hl)
        assert result["highlights"]["objects"] == ["Saturn"]

    def test_visible_objects_filter(self):
        chart = _make_minimal_chart()
        result = serialize_chart_for_rendering(chart, visible_objects=["Sun"])
        names = [o["name"] for o in result["objects"]]
        assert names == ["Sun"]

    def test_dark_mode_sign_colors(self):
        chart = _make_minimal_chart()
        light = serialize_chart_for_rendering(chart, dark_mode=False)
        dark = serialize_chart_for_rendering(chart, dark_mode=True)
        # Band colors should differ between modes
        assert light["signs"][0]["band_color"] != dark["signs"][0]["band_color"]


class TestSerializeSigns:
    def test_twelve_signs(self):
        signs = _serialize_signs(False)
        assert len(signs) == 12

    def test_sign_names(self):
        signs = _serialize_signs(False)
        assert signs[0]["name"] == "Aries"
        assert signs[11]["name"] == "Pisces"

    def test_sign_start_degrees(self):
        signs = _serialize_signs(False)
        for i, s in enumerate(signs):
            assert s["start_degree"] == i * 30
