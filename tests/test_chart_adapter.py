"""Tests for src/chart_adapter.py — chart computation & rendering adapter."""
from __future__ import annotations

import datetime as dt
from dataclasses import fields
from unittest.mock import MagicMock, patch

import pytest

from src.chart_adapter import (
    ChartInputs,
    ChartResult,
    RenderToggles,
    compute_chart,
    compute_transit_chart,
    compute_combined_circuits,
    compute_inter_chart_aspects,
    render_chart_image,
)


# ═══════════════════════════════════════════════════════════════════════
# Dataclass defaults
# ═══════════════════════════════════════════════════════════════════════

class TestChartInputsDefaults:
    """ChartInputs should have sensible defaults for all fields."""

    def test_defaults(self):
        ci = ChartInputs()
        assert ci.name == ""
        assert ci.year == 2000
        assert ci.tz_name == "UTC"
        assert ci.unknown_time is False
        assert ci.house_system == "placidus"
        assert ci.gender is None

    def test_custom_values(self):
        ci = ChartInputs(name="Alice", year=1990, month=6, day=15,
                         hour_24=14, minute=30, lat=40.7128, lon=-74.006,
                         tz_name="America/New_York")
        assert ci.name == "Alice"
        assert ci.year == 1990
        assert ci.lat == pytest.approx(40.7128)


class TestChartResultDefaults:
    """ChartResult should default to empty collections and None scalars."""

    def test_defaults(self):
        cr = ChartResult()
        assert cr.chart is None
        assert cr.error is None
        assert cr.edges_major == []
        assert cr.patterns == []
        assert cr.positions == {}
        assert cr.singleton_map == {}

    def test_field_count(self):
        """Smoke: result has a reasonable number of fields."""
        assert len(fields(ChartResult)) >= 15


class TestRenderTogglesDefaults:
    """RenderToggles defaults."""

    def test_defaults(self):
        rt = RenderToggles()
        assert rt.compass_inner is True
        assert rt.chart_mode == "Circuits"
        assert rt.dark_mode is False
        assert rt.label_style == "glyph"
        assert rt.pattern_toggles == {}
        assert rt.dpi == 192


# ═══════════════════════════════════════════════════════════════════════
# compute_chart — mocked internals
# ═══════════════════════════════════════════════════════════════════════

class TestComputeChartMocked:
    """Test compute_chart() with mocked calc_v2 + patterns_v2.

    calc_v2 / patterns_v2 / circuit_sim functions are lazy-imported inside
    compute_chart(), so we must patch them at their *source* module paths.
    """

    def _make_mock_chart(self):
        """Create a mock chart object with the attributes compute_chart expects."""
        chart = MagicMock()
        chart.objects = []
        return chart

    @patch("src.core.circuit_sim.simulate_and_attach")
    @patch("src.core.patterns_v2.generate_combo_groups", return_value={})
    @patch("src.core.patterns_v2.detect_minor_links_from_chart", return_value=([], {}))
    @patch("src.core.patterns_v2.detect_shapes", return_value=[])
    @patch("src.core.patterns_v2.prepare_pattern_inputs", return_value=({}, [set()], []))
    @patch("src.core.calc_v2.build_dispositor_tables", return_value=([], []))
    @patch("src.core.calc_v2.build_conjunction_clusters", return_value=([], None, None))
    @patch("src.core.calc_v2.chart_sect_from_chart", return_value="Day")
    @patch("src.core.calc_v2.annotate_chart")
    @patch("src.core.calc_v2.build_aspect_edges", return_value=([], [], []))
    @patch("src.core.calc_v2.calculate_chart")
    def test_happy_path(self, mock_calc, mock_edges, mock_ann,
                        mock_sect, mock_conj, mock_disp, mock_prep,
                        mock_shapes, mock_minor, mock_combos, mock_sim):
        mock_chart = self._make_mock_chart()
        mock_calc.return_value = (MagicMock(), MagicMock(), {}, mock_chart)

        inputs = ChartInputs(
            name="Test", year=1990, month=6, day=15,
            hour_24=14, minute=30, lat=40.71, lon=-74.0,
            tz_name="America/New_York",
        )
        result = compute_chart(inputs)

        assert result.error is None
        assert result.chart is mock_chart
        assert result.utc_datetime is not None
        assert result.local_datetime is not None
        assert result.sect == "Day"
        mock_calc.assert_called_once()

    def test_bad_timezone(self):
        """Invalid timezone should produce an error result (no calc needed)."""
        inputs = ChartInputs(
            name="Bad TZ", year=2000, month=1, day=1,
            hour_24=12, minute=0,
            tz_name="INVALID/TIMEZONE",
        )
        result = compute_chart(inputs)
        assert result.error is not None
        assert "Time parsing failed" in result.error

    @patch("src.core.circuit_sim.simulate_and_attach")
    @patch("src.core.patterns_v2.generate_combo_groups", return_value={})
    @patch("src.core.patterns_v2.detect_minor_links_from_chart", return_value=([], {}))
    @patch("src.core.patterns_v2.detect_shapes", return_value=[])
    @patch("src.core.patterns_v2.prepare_pattern_inputs", return_value=({}, [set()], []))
    @patch("src.core.calc_v2.build_dispositor_tables", return_value=([], []))
    @patch("src.core.calc_v2.build_conjunction_clusters", return_value=([], None, None))
    @patch("src.core.calc_v2.chart_sect_from_chart", return_value="Night")
    @patch("src.core.calc_v2.annotate_chart")
    @patch("src.core.calc_v2.build_aspect_edges", return_value=([], [], []))
    @patch("src.core.calc_v2.calculate_chart")
    def test_unknown_time(self, mock_calc, mock_edges, mock_ann,
                          mock_sect, mock_conj, mock_disp, mock_prep,
                          mock_shapes, mock_minor, mock_combos, mock_sim):
        """unknown_time=True should force hour=12, minute=0 and skip TZ."""
        mock_chart = self._make_mock_chart()
        mock_calc.return_value = (MagicMock(), MagicMock(), {}, mock_chart)

        inputs = ChartInputs(
            name="Unknown", year=2000, month=1, day=1,
            hour_24=8, minute=45,  # should be overridden to 12:00
            tz_name="UTC",
            unknown_time=True,
        )
        result = compute_chart(inputs)

        assert result.error is None
        # UTC datetime should be noon
        assert result.utc_datetime.hour == 12
        assert result.utc_datetime.minute == 0

    @patch("src.core.calc_v2.calculate_chart")
    def test_calc_error_propagates(self, mock_calc):
        """If calculate_chart raises, the error is captured."""
        mock_calc.side_effect = RuntimeError("calc boom")

        inputs = ChartInputs(name="Boom", year=2000, month=1, day=1,
                             tz_name="UTC")
        result = compute_chart(inputs)
        assert result.error is not None
        assert "Chart calculation failed" in result.error


# ═══════════════════════════════════════════════════════════════════════
# compute_chart — integration with real calc_v2 (session-scoped)
# ═══════════════════════════════════════════════════════════════════════

class TestComputeChartIntegration:
    """Integration test using the real calc_v2 pipeline."""

    def test_real_chart(self):
        """compute_chart with real ephemeris → populated ChartResult."""
        inputs = ChartInputs(
            name="Integration", year=1990, month=6, day=15,
            hour_24=14, minute=30, lat=40.7128, lon=-74.006,
            tz_name="America/New_York",
        )
        result = compute_chart(inputs)
        assert result.error is None
        assert result.chart is not None
        assert result.df_positions is not None
        assert len(result.edges_major) > 0
        assert len(result.patterns) > 0
        assert result.utc_datetime is not None


# ═══════════════════════════════════════════════════════════════════════
# compute_transit_chart
# ═══════════════════════════════════════════════════════════════════════

class TestComputeTransitChart:
    """Tests for compute_transit_chart()."""

    def test_default_uses_current_time(self):
        """With no transit_utc, should use now()."""
        result = compute_transit_chart(lat=40.71, lon=-74.0, tz_name="UTC")
        assert result.error is None
        assert result.utc_datetime is not None

    def test_specific_utc(self):
        utc = dt.datetime(2024, 6, 15, 12, 0, 0)
        result = compute_transit_chart(lat=51.5, lon=-0.1, transit_utc=utc)
        assert result.error is None
        assert result.utc_datetime == utc

    def test_aware_datetime_converted(self):
        """Timezone-aware input should be normalised to naive UTC."""
        from zoneinfo import ZoneInfo
        aware = dt.datetime(2024, 6, 15, 8, 0, tzinfo=ZoneInfo("America/New_York"))
        result = compute_transit_chart(lat=40.71, lon=-74.0, transit_utc=aware)
        assert result.error is None
        assert result.utc_datetime.tzinfo is None  # naive UTC


# ═══════════════════════════════════════════════════════════════════════
# compute_combined_circuits — with real sample_chart
# ═══════════════════════════════════════════════════════════════════════

class TestComputeCombinedCircuits:
    """Tests for compute_combined_circuits() using real chart data."""

    def test_basic_structure(self, sample_chart):
        """Merging a chart with itself should produce _2 suffixed keys."""
        data = compute_combined_circuits(sample_chart, sample_chart)

        assert "pos_combined" in data
        assert "patterns_combined" in data
        assert "shapes_combined" in data
        assert "singleton_map_combined" in data
        assert "combined_edges" in data

    def test_chart2_suffix(self, sample_chart):
        """Chart-2 positions should have '_2' suffix."""
        data = compute_combined_circuits(sample_chart, sample_chart)
        pos = data["pos_combined"]

        # Chart 1 plain names + Chart 2 _2 suffixed
        chart1_objs = {o.object_name.name for o in sample_chart.objects
                       if o.object_name}
        for name in chart1_objs:
            assert name in pos, f"Missing Chart 1 key: {name}"
            assert f"{name}_2" in pos, f"Missing Chart 2 key: {name}_2"

    def test_combined_edges_are_tuples(self, sample_chart):
        data = compute_combined_circuits(sample_chart, sample_chart)
        for edge in data["combined_edges"]:
            pair, aspect_name = edge
            assert isinstance(pair, tuple) and len(pair) == 2
            assert isinstance(aspect_name, str)

    def test_singleton_not_in_edges(self, sample_chart):
        """Singletons should not appear in any edge."""
        data = compute_combined_circuits(sample_chart, sample_chart)
        connected = set()
        for (p1, p2), _ in data["combined_edges"]:
            connected.add(p1)
            connected.add(p2)
        for name in data["singleton_map_combined"]:
            assert name not in connected


# ═══════════════════════════════════════════════════════════════════════
# compute_inter_chart_aspects
# ═══════════════════════════════════════════════════════════════════════

class TestComputeInterChartAspects:
    """Tests for compute_inter_chart_aspects()."""

    def test_returns_list_of_triples(self, sample_chart):
        aspects = compute_inter_chart_aspects(sample_chart, sample_chart)
        assert isinstance(aspects, list)
        for item in aspects:
            assert len(item) == 3
            p1, p2, name = item
            assert isinstance(p1, str)
            assert isinstance(p2, str)
            assert isinstance(name, str)

    def test_self_conjunction(self, sample_chart):
        """A chart aspected with itself should find conjunctions (0°)."""
        aspects = compute_inter_chart_aspects(sample_chart, sample_chart)
        conjunctions = [a for a in aspects if a[2] == "Conjunction"]
        # Every planet conjuncts itself → at least as many as object count
        obj_count = len([o for o in sample_chart.objects if o.object_name])
        assert len(conjunctions) >= obj_count

    def test_synthetic_known_aspect(self):
        """Two charts with known positions → predictable aspect."""
        # Sun at 0° and Sun at 120° → Trine
        obj1 = MagicMock()
        obj1.object_name.name = "Sun"
        obj1.longitude = 0.0

        obj2 = MagicMock()
        obj2.object_name.name = "Sun"
        obj2.longitude = 120.0

        chart1 = MagicMock()
        chart1.objects = [obj1]
        chart2 = MagicMock()
        chart2.objects = [obj2]

        aspects = compute_inter_chart_aspects(chart1, chart2)
        aspect_names = [a[2] for a in aspects]
        assert "Trine" in aspect_names

    def test_synthetic_no_aspect(self):
        """Two charts at non-aspect angles should produce no results."""
        obj1 = MagicMock()
        obj1.object_name.name = "Sun"
        obj1.longitude = 0.0

        obj2 = MagicMock()
        obj2.object_name.name = "Moon"
        obj2.longitude = 37.0   # not near any standard aspect

        chart1 = MagicMock()
        chart1.objects = [obj1]
        chart2 = MagicMock()
        chart2.objects = [obj2]

        aspects = compute_inter_chart_aspects(chart1, chart2)
        assert len(aspects) == 0


# ═══════════════════════════════════════════════════════════════════════
# render_chart_image — smoke tests
# ═══════════════════════════════════════════════════════════════════════

class TestRenderChartImage:
    """Smoke tests for render_chart_image() and render_biwheel_image()."""

    @pytest.fixture()
    def chart_result(self, sample_chart):
        """Build a ChartResult from the session-scoped sample_chart."""
        cr = compute_chart(ChartInputs(
            name="Render", year=1990, month=6, day=15,
            hour_24=14, minute=30, lat=40.7128, lon=-74.006,
            tz_name="America/New_York",
        ))
        assert cr.error is None
        return cr

    def test_returns_png_bytes(self, chart_result):
        with patch("src.rendering.drawing_v2.draw_center_earth"):
            png = render_chart_image(chart_result)
            assert isinstance(png, bytes)
            assert len(png) > 100
            # PNG magic bytes
            assert png[:4] == b'\x89PNG'

    def test_standard_mode(self, chart_result):
        toggles = RenderToggles(chart_mode="Standard Chart")
        with patch("src.rendering.drawing_v2.draw_center_earth"):
            png = render_chart_image(chart_result, toggles=toggles)
            assert png[:4] == b'\x89PNG'

    def test_raises_on_empty_result(self):
        cr = ChartResult()  # no chart
        with pytest.raises(ValueError, match="no chart object"):
            render_chart_image(cr)

    def test_dark_mode(self, chart_result):
        toggles = RenderToggles(dark_mode=True)
        with patch("src.rendering.drawing_v2.draw_center_earth"):
            png = render_chart_image(chart_result, toggles=toggles)
            assert isinstance(png, bytes), "dark mode should still produce bytes"
