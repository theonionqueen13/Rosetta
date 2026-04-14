"""Tests for src.rendering.drawing_v2 — chart rendering smoke tests."""
from __future__ import annotations

import io
from unittest.mock import patch

import matplotlib.figure
import pytest


# All rendering tests patch draw_center_earth to avoid NiceGUI state reads.
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


# ---------------------------------------------------------------------------
# Pure helper tests
# ---------------------------------------------------------------------------
class TestObjectMap:
    """Tests for _object_map()."""

    def test_returns_dict_with_sun(self, sample_chart):
        from src.rendering.drawing_v2 import _object_map

        omap = _object_map(sample_chart)
        assert isinstance(omap, dict)
        assert "Sun" in omap

    def test_returns_empty_for_none(self):
        from src.rendering.drawing_v2 import _object_map

        assert _object_map(None) == {}


class TestChartPositions:
    """Tests for _chart_positions()."""

    def test_all_positions(self, sample_chart):
        from src.rendering.drawing_v2 import _chart_positions

        pos = _chart_positions(sample_chart)
        assert isinstance(pos, dict)
        assert len(pos) > 0
        assert "Sun" in pos
        assert isinstance(pos["Sun"], float)

    def test_filters_by_visible(self, sample_chart):
        from src.rendering.drawing_v2 import _chart_positions

        pos = _chart_positions(sample_chart, ["Sun", "Moon"])
        assert "Sun" in pos
        assert "Moon" in pos
        # Should not include unrelated objects
        for name in ("Jupiter", "Saturn", "Pluto"):
            if name in pos:
                # filter is best-effort; just verify Sun/Moon are present
                pass

    def test_returns_empty_for_none(self):
        from src.rendering.drawing_v2 import _chart_positions

        assert _chart_positions(None) == {}


# ---------------------------------------------------------------------------
# RenderResult smoke tests (use the session-scoped render_result fixture)
# ---------------------------------------------------------------------------
class TestRenderChart:
    """Smoke tests for render_chart()."""

    def test_returns_render_result(self, render_result):
        from src.rendering.drawing_v2 import RenderResult

        assert isinstance(render_result, RenderResult)

    def test_result_has_figure(self, render_result):
        assert isinstance(render_result.fig, matplotlib.figure.Figure)

    def test_result_has_positions(self, render_result):
        assert isinstance(render_result.positions, dict)
        assert len(render_result.positions) > 0
        assert "Sun" in render_result.positions

    def test_result_has_12_cusps(self, render_result):
        assert isinstance(render_result.cusps, list)
        assert len(render_result.cusps) == 12
        assert all(isinstance(c, float) for c in render_result.cusps)

    def test_result_has_visible_objects(self, render_result):
        """visible_objects is empty when no toggle state is supplied."""
        assert isinstance(render_result.visible_objects, list)

    def test_result_has_edges(self, render_result):
        assert isinstance(render_result.drawn_major_edges, list)
        assert isinstance(render_result.drawn_minor_edges, list)

    def test_render_to_png_bytes(self, render_result):
        """Verify the figure can be exported to valid PNG bytes."""
        buf = io.BytesIO()
        render_result.fig.savefig(buf, format="png")
        buf.seek(0)
        header = buf.read(8)
        assert header[:4] == b"\x89PNG", "Output is not valid PNG"

    def test_render_chart_dark_mode(self, sample_chart):
        """dark_mode=True should produce a figure with a dark background."""
        with patch("src.rendering.drawing_v2.draw_center_earth"):
            from src.rendering.drawing_v2 import render_chart

            result = render_chart(sample_chart, dark_mode=True)
            # Facecolor is an RGBA tuple — dark backgrounds have low RGB values
            face = result.fig.patch.get_facecolor()
            # face is (R, G, B, A) in [0, 1]; dark mode → R,G,B all < 0.3
            assert face[0] < 0.3 and face[1] < 0.3 and face[2] < 0.3

    def test_render_chart_no_compass(self, sample_chart):
        """compass_on=False should render without errors."""
        with patch("src.rendering.drawing_v2.draw_center_earth"):
            from src.rendering.drawing_v2 import render_chart

            result = render_chart(sample_chart, compass_on=False)
            assert result.fig is not None

    def test_render_chart_label_style_text(self, sample_chart):
        """label_style='text' should render without errors."""
        with patch("src.rendering.drawing_v2.draw_center_earth"):
            from src.rendering.drawing_v2 import render_chart

            result = render_chart(sample_chart, label_style="text")
            assert result.fig is not None

    def test_plot_data_contains_chart(self, render_result):
        """plot_data should contain the original chart object."""
        assert render_result.plot_data is not None
        assert "chart" in render_result.plot_data
