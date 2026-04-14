"""Tests for src.rendering.drawing_primitives — geometry & color helpers."""
from __future__ import annotations

import math

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# _phase_label_from_delta
# ---------------------------------------------------------------------------
class TestPhaseLabelFromDelta:
    """Tests for the moon-phase bin mapper."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.drawing_primitives import _phase_label_from_delta
        self.fn = _phase_label_from_delta

    @pytest.mark.parametrize(
        "delta, expected",
        [
            (0.0,   "New Moon"),
            (10.0,  "New Moon"),
            (45.0,  "Waxing Crescent"),
            (90.0,  "First Quarter"),
            (135.0, "Waxing Gibbous"),
            (180.0, "Full Moon"),
            (225.0, "Waning Gibbous"),
            (270.0, "Last Quarter"),
            (315.0, "Waning Crescent"),
        ],
    )
    def test_phase_bins(self, delta, expected):
        assert self.fn(delta) == expected

    @pytest.mark.parametrize(
        "delta, expected",
        [
            (22.5,  "Waxing Crescent"),   # boundary → next bin
            (67.5,  "First Quarter"),
            (337.5, "New Moon"),           # wraps back
            (359.9, "New Moon"),
        ],
    )
    def test_boundary_values(self, delta, expected):
        assert self.fn(delta) == expected

    def test_negative_wraps(self):
        # -45° → 315° mod 360 → Waning Crescent
        assert self.fn(-45.0) == "Waning Crescent"

    def test_large_values_wrap(self):
        assert self.fn(720.0) == "New Moon"  # 720 % 360 == 0


# ---------------------------------------------------------------------------
# _moon_phase_label_emoji
# ---------------------------------------------------------------------------
class TestMoonPhaseLabelEmoji:
    """Tests for moon phase emoji/path helper."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.drawing_primitives import _moon_phase_label_emoji
        self.fn = _moon_phase_label_emoji

    def test_returns_tuple(self):
        label, path = self.fn(0.0, 180.0)
        assert isinstance(label, str)
        assert isinstance(path, str)
        assert label == "Full Moon"

    def test_path_mode_returns_file_path(self):
        label, path = self.fn(0.0, 0.0)
        assert path.endswith(".png")

    def test_html_mode_returns_img_tag(self):
        label, html = self.fn(0.0, 0.0, emoji_size_px=32)
        assert "<img" in html


# ---------------------------------------------------------------------------
# deg_to_rad
# ---------------------------------------------------------------------------
class TestDegToRad:
    """Tests for the degree-to-polar-radian converter."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.drawing_primitives import deg_to_rad
        self.fn = deg_to_rad

    def test_returns_float(self):
        assert isinstance(self.fn(0.0), float)

    def test_zero_with_no_shift(self):
        # Deterministic mapping — just verify finite float
        result = self.fn(0.0)
        assert math.isfinite(result)

    def test_with_asc_shift(self):
        r1 = self.fn(90.0, asc_shift=0.0)
        r2 = self.fn(90.0, asc_shift=45.0)
        assert r1 != r2  # shift should change the result

    def test_full_circle(self):
        # 360 degrees should wrap back to same value as 0
        assert abs(self.fn(0.0) - self.fn(360.0)) < 1e-10


# ---------------------------------------------------------------------------
# _segment_points
# ---------------------------------------------------------------------------
class TestSegmentPoints:
    """Tests for polar chord interpolation."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.drawing_primitives import _segment_points
        self.fn = _segment_points

    def test_returns_two_arrays(self):
        thetas, radii = self.fn(0.0, math.pi / 2)
        assert isinstance(thetas, np.ndarray)
        assert isinstance(radii, np.ndarray)

    def test_default_length(self):
        thetas, radii = self.fn(0.0, math.pi / 2)
        assert len(thetas) == 48
        assert len(radii) == 48

    def test_custom_steps(self):
        thetas, radii = self.fn(0.0, math.pi, steps=10)
        assert len(thetas) == 10

    def test_custom_radius(self):
        _, radii = self.fn(0.0, 0.0, radius=2.5, steps=5)
        # At start and end the radius should be ~2.5
        assert abs(radii[0] - 2.5) < 1e-10


# ---------------------------------------------------------------------------
# _lighten_color / _light_variant_for
# ---------------------------------------------------------------------------
class TestColorHelpers:
    """Tests for color manipulation utilities."""

    def test_lighten_color_returns_hex(self):
        from src.rendering.drawing_primitives import _lighten_color

        result = _lighten_color("#ff0000", 0.5)
        assert isinstance(result, str)
        assert result.startswith("#")

    def test_lighten_color_blend_1_approaches_white(self):
        from src.rendering.drawing_primitives import _lighten_color
        from matplotlib.colors import to_rgba

        result = _lighten_color("#ff0000", 1.0)
        r, g, b, _ = to_rgba(result)
        # blend=1.0 → should be close to white
        assert r > 0.9 and g > 0.9 and b > 0.9

    def test_lighten_color_blend_0_same_color(self):
        from src.rendering.drawing_primitives import _lighten_color
        from matplotlib.colors import to_rgba

        result = _lighten_color("#ff0000", 0.0)
        r, g, b, _ = to_rgba(result)
        # blend=0 → should stay red
        assert r > 0.9 and g < 0.2 and b < 0.2

    def test_light_variant_for_returns_string(self):
        from src.rendering.drawing_primitives import _light_variant_for

        result = _light_variant_for("#336699")
        assert isinstance(result, str)
        assert result.startswith("#")


# ---------------------------------------------------------------------------
# _earth_emoji_for_region
# ---------------------------------------------------------------------------
class TestEarthEmojiForRegion:
    """Tests for geographic emoji mapping."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.rendering.drawing_primitives import _earth_emoji_for_region
        self.fn = _earth_emoji_for_region

    @pytest.mark.parametrize(
        "lat, lon, expected",
        [
            (40.7, -74.0, "🌎"),    # New York → Americas
            (51.5, -0.1, "🌍"),     # London → Europe/Africa
            (35.7, 139.7, "🌏"),    # Tokyo → Asia
            (-33.9, 18.4, "🌍"),    # Cape Town → Africa
            (-33.9, 151.2, "🌏"),   # Sydney → Asia/Australia
        ],
    )
    def test_known_locations(self, lat, lon, expected):
        assert self.fn(lat, lon) == expected

    def test_none_returns_globe(self):
        assert self.fn(None, None) == "🌐"

    def test_none_lat_returns_globe(self):
        assert self.fn(None, -74.0) == "🌐"
