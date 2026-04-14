"""Tests for src/nicegui_state.py — per-user NiceGUI state helpers."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════════
# get_profile_lat_lon  (pure dict logic — no NiceGUI import needed)
# ═══════════════════════════════════════════════════════════════════════

class TestGetProfileLatLon:
    """Tests for get_profile_lat_lon() — pure function, no framework deps."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.nicegui_state import get_profile_lat_lon
        self.fn = get_profile_lat_lon

    def test_valid_floats(self):
        state = {"current_lat": 40.7128, "current_lon": -74.006}
        assert self.fn(state) == (40.7128, -74.006)

    def test_string_floats(self):
        state = {"current_lat": "51.5074", "current_lon": "-0.1278"}
        assert self.fn(state) == pytest.approx((51.5074, -0.1278))

    def test_none_lat(self):
        state = {"current_lat": None, "current_lon": -74.006}
        assert self.fn(state) == (None, None)

    def test_none_lon(self):
        state = {"current_lat": 40.7128, "current_lon": None}
        assert self.fn(state) == (None, None)

    def test_both_none(self):
        state = {"current_lat": None, "current_lon": None}
        assert self.fn(state) == (None, None)

    def test_missing_keys(self):
        assert self.fn({}) == (None, None)

    def test_non_numeric_string(self):
        state = {"current_lat": "not-a-number", "current_lon": "10.0"}
        assert self.fn(state) == (None, None)

    def test_zero_values(self):
        """Zero is a valid coordinate (equator / prime meridian)."""
        state = {"current_lat": 0.0, "current_lon": 0.0}
        assert self.fn(state) == (0.0, 0.0)

    def test_integer_values(self):
        state = {"current_lat": 45, "current_lon": -90}
        assert self.fn(state) == (45.0, -90.0)


# ═══════════════════════════════════════════════════════════════════════
# reset_chart_toggles  (pure dict mutation — no NiceGUI import needed)
# ═══════════════════════════════════════════════════════════════════════

class TestResetChartToggles:
    """Tests for reset_chart_toggles() — clears transient toggle state."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.nicegui_state import reset_chart_toggles
        self.fn = reset_chart_toggles

    def test_clears_toggle_dicts(self):
        state = {
            "pattern_toggles": {0: True, 1: False},
            "shape_toggles": {"T-Square": True},
            "singleton_toggles": {"Pluto": True},
        }
        self.fn(state)
        assert state["pattern_toggles"] == {}
        assert state["shape_toggles"] == {}
        assert state["singleton_toggles"] == {}

    def test_pops_shape_toggles_by_parent(self):
        state = {
            "pattern_toggles": {},
            "shape_toggles": {},
            "singleton_toggles": {},
            "shape_toggles_by_parent": {0: {"T-Square": True}},
        }
        self.fn(state)
        assert "shape_toggles_by_parent" not in state

    def test_no_error_when_by_parent_missing(self):
        state = {
            "pattern_toggles": {0: True},
            "shape_toggles": {},
            "singleton_toggles": {},
        }
        self.fn(state)  # should not raise

    def test_preserves_other_keys(self):
        state = {
            "pattern_toggles": {0: True},
            "shape_toggles": {},
            "singleton_toggles": {},
            "chart_mode": "Circuits",
            "dark_mode": True,
        }
        self.fn(state)
        assert state["chart_mode"] == "Circuits"
        assert state["dark_mode"] is True


# ═══════════════════════════════════════════════════════════════════════
# ensure_state  (requires mocking nicegui.app.storage.user)
# ═══════════════════════════════════════════════════════════════════════

class TestEnsureState:
    """Tests for ensure_state() — lazily initialises per-user state."""

    def _make_mock_storage(self):
        """Create a mock app.storage.user that behaves like a dict."""
        return {}

    def test_creates_rosetta_state(self):
        storage = self._make_mock_storage()
        with patch("src.nicegui_state.app") as mock_app:
            mock_app.storage.user = storage
            from src.nicegui_state import ensure_state
            state = ensure_state()
            assert "rosetta_state" in storage
            assert isinstance(state, dict)

    def test_populates_defaults(self):
        storage = self._make_mock_storage()
        with patch("src.nicegui_state.app") as mock_app:
            mock_app.storage.user = storage
            from src.nicegui_state import ensure_state, _DEFAULTS
            state = ensure_state()
            for key in _DEFAULTS:
                assert key in state, f"Missing default key: {key}"

    def test_preserves_existing_values(self):
        storage = {"rosetta_state": {"name": "Alice", "year": 1985}}
        with patch("src.nicegui_state.app") as mock_app:
            mock_app.storage.user = storage
            from src.nicegui_state import ensure_state
            state = ensure_state()
            assert state["name"] == "Alice"
            assert state["year"] == 1985

    def test_merges_new_defaults_into_existing(self):
        # Simulate an older session that's missing newer keys
        storage = {"rosetta_state": {"name": "Bob"}}
        with patch("src.nicegui_state.app") as mock_app:
            mock_app.storage.user = storage
            from src.nicegui_state import ensure_state, _DEFAULTS
            state = ensure_state()
            # Bob's name is preserved
            assert state["name"] == "Bob"
            # But all other defaults are filled
            assert state["chart_mode"] == _DEFAULTS["chart_mode"]

    def test_returns_same_dict_on_repeated_calls(self):
        storage = self._make_mock_storage()
        with patch("src.nicegui_state.app") as mock_app:
            mock_app.storage.user = storage
            from src.nicegui_state import ensure_state
            s1 = ensure_state()
            s2 = ensure_state()
            assert s1 is s2


# ═══════════════════════════════════════════════════════════════════════
# get_chart_object / get_chart_2_object  (mock AstrologicalChart.from_json)
# ═══════════════════════════════════════════════════════════════════════

class TestGetChartObject:
    """Tests for get_chart_object() — JSON → AstrologicalChart."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.nicegui_state import get_chart_object
        self.fn = get_chart_object

    def test_none_json_returns_none(self):
        assert self.fn({"last_chart_json": None}) is None

    def test_missing_key_returns_none(self):
        assert self.fn({}) is None

    def test_non_dict_returns_none(self):
        assert self.fn({"last_chart_json": "not-a-dict"}) is None
        assert self.fn({"last_chart_json": 42}) is None
        assert self.fn({"last_chart_json": [1, 2, 3]}) is None

    def test_valid_dict_calls_from_json(self):
        sentinel = object()
        chart_dict = {"objects": [], "house_cusps": []}
        with patch("src.nicegui_state.AstrologicalChart", create=True) as mock_cls:
            # We need to patch the lazy import inside get_chart_object
            with patch.dict("sys.modules", {}):
                pass
        # Simpler approach: mock the from_json call at the models level
        with patch("src.core.models_v2.AstrologicalChart") as MockChart:
            MockChart.from_json.return_value = sentinel
            result = self.fn({"last_chart_json": chart_dict})
            MockChart.from_json.assert_called_once_with(chart_dict)
            assert result is sentinel


class TestGetChart2Object:
    """Tests for get_chart_2_object() — JSON → AstrologicalChart (Chart 2)."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.nicegui_state import get_chart_2_object
        self.fn = get_chart_2_object

    def test_none_json_returns_none(self):
        assert self.fn({"last_chart_2_json": None}) is None

    def test_missing_key_returns_none(self):
        assert self.fn({}) is None

    def test_non_dict_returns_none(self):
        assert self.fn({"last_chart_2_json": "string"}) is None

    def test_valid_dict_calls_from_json(self):
        sentinel = object()
        chart_dict = {"objects": [], "house_cusps": []}
        with patch("src.core.models_v2.AstrologicalChart") as MockChart:
            MockChart.from_json.return_value = sentinel
            result = self.fn({"last_chart_2_json": chart_dict})
            MockChart.from_json.assert_called_once_with(chart_dict)
            assert result is sentinel


# ═══════════════════════════════════════════════════════════════════════
# _DEFAULTS sanity checks
# ═══════════════════════════════════════════════════════════════════════

class TestDefaults:
    """Sanity checks on the _DEFAULTS template."""

    def test_defaults_is_dict(self):
        from src.nicegui_state import _DEFAULTS
        assert isinstance(_DEFAULTS, dict)

    def test_critical_keys_present(self):
        from src.nicegui_state import _DEFAULTS
        for key in ("name", "year", "chart_mode", "dark_mode",
                     "pattern_toggles", "shape_toggles", "singleton_toggles",
                     "mcp_chat_history", "auto_load_on_startup"):
            assert key in _DEFAULTS, f"Missing critical default: {key}"

    def test_toggle_defaults_are_empty_dicts(self):
        from src.nicegui_state import _DEFAULTS
        for key in ("pattern_toggles", "shape_toggles", "singleton_toggles", "aspect_toggles"):
            assert _DEFAULTS[key] == {}, f"{key} should default to empty dict"

    def test_chat_history_default_is_list(self):
        from src.nicegui_state import _DEFAULTS
        assert _DEFAULTS["mcp_chat_history"] == []
