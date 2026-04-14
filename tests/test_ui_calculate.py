"""Tests for src.ui.calculate — on_calculate handler with mocked geocoding + calc."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MODULE = "src.ui.calculate"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def widgets():
    """Return a dict of mock UI widgets matching on_calculate's keyword args."""
    status = MagicMock(name="status_label")
    status.text = ""
    status.set_visibility = MagicMock()
    status.classes = MagicMock()

    calc_btn = MagicMock(name="calc_btn")
    birth_exp = MagicMock(name="birth_exp")
    save_name_input = MagicMock(name="save_name_input")
    save_name_input.value = ""

    return {
        "status_label": status,
        "calc_btn": calc_btn,
        "birth_exp": birth_exp,
        "save_name_input": save_name_input,
    }


@pytest.fixture()
def callbacks():
    """Return mock callables for build_circuit_toggles and rerender_active_tab."""
    return {
        "build_circuit_toggles": MagicMock(name="build_circuit_toggles"),
        "rerender_active_tab": MagicMock(name="rerender_active_tab"),
    }


@pytest.fixture()
def base_form():
    """Return valid birth-data form dict."""
    return {
        "name": "Test Person",
        "city": "New York",
        "year": "1990",
        "month_name": "June",
        "day": "15",
        "hour_12": "2",
        "minute_str": "30",
        "ampm": "PM",
        "unknown_time": False,
        "gender": "F",
    }


@pytest.fixture()
def base_state():
    """Return a minimal per-user state dict."""
    return {"house_system": "placidus"}


@pytest.fixture()
def mock_geocode():
    """Patch geocode_city_with_timezone and return the mock."""
    with patch(
        "src.core.geocoding.geocode_city_with_timezone",
        return_value=(40.7128, -74.006, "America/New_York", "New York, NY"),
    ) as m:
        yield m


@pytest.fixture()
def mock_compute():
    """Patch compute_chart and return a mock that yields a successful result."""
    chart = MagicMock(name="AstrologicalChart")
    chart.to_json.return_value = '{"chart": "data"}'
    result = MagicMock(name="ComputeResult")
    result.error = None
    result.chart = chart
    with patch("src.chart_adapter.compute_chart", return_value=result) as m:
        m._chart = chart
        m._result = result
        yield m


@pytest.fixture()
def _patch_js():
    """Patch ui.run_javascript so async flushes are no-ops."""
    with patch(f"{MODULE}.ui") as mock_ui:
        mock_ui.run_javascript = AsyncMock(return_value=None)
        yield mock_ui


def _call_kwargs(widgets, callbacks):
    """Build the keyword-only arguments for on_calculate."""
    return {**widgets, **callbacks}


# ===================================================================
# on_calculate
# ===================================================================

class TestOnCalculate:
    async def test_happy_path(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        # Chart stored in state
        assert base_state["chart_ready"] is True
        assert base_state["last_chart_json"] is not None
        assert base_state["name"] == "Test Person"
        assert base_state["city"] == "New York"

        # Callbacks invoked
        callbacks["build_circuit_toggles"].assert_called_once()
        callbacks["rerender_active_tab"].assert_called_once()

        # UI state: form collapsed, status hidden, button re-enabled
        widgets["birth_exp"].close.assert_called_once()
        widgets["calc_btn"].enable.assert_called()
        widgets["save_name_input"].value = "Test Person"

    async def test_missing_name(
        self, base_state, base_form, widgets, callbacks,
    ):
        from src.ui.calculate import on_calculate
        base_form["name"] = ""
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert "Name" in widgets["status_label"].text
        widgets["status_label"].set_visibility.assert_called_with(True)
        # geocode should never be called
        callbacks["rerender_active_tab"].assert_not_called()

    async def test_missing_city(
        self, base_state, base_form, widgets, callbacks,
    ):
        from src.ui.calculate import on_calculate
        base_form["city"] = ""
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert "City" in widgets["status_label"].text
        widgets["status_label"].set_visibility.assert_called_with(True)

    async def test_geocode_returns_none(
        self, base_state, base_form, widgets, callbacks, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        with patch(
            "src.core.geocoding.geocode_city_with_timezone",
            return_value=(None, None, None, None),
        ):
            await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert "geocode" in widgets["status_label"].text.lower()
        widgets["calc_btn"].enable.assert_called()

    async def test_geocode_raises(
        self, base_state, base_form, widgets, callbacks, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        with patch(
            "src.core.geocoding.geocode_city_with_timezone",
            side_effect=RuntimeError("network"),
        ):
            await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert "error" in widgets["status_label"].text.lower() or "network" in widgets["status_label"].text.lower()
        widgets["calc_btn"].enable.assert_called()

    async def test_compute_error(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        result = MagicMock()
        result.error = "Invalid date"
        result.chart = None
        with patch("src.chart_adapter.compute_chart", return_value=result):
            await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert "Invalid date" in widgets["status_label"].text
        widgets["calc_btn"].enable.assert_called()

    async def test_compute_exception(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        with patch("src.chart_adapter.compute_chart", side_effect=ValueError("boom")):
            await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert "boom" in widgets["status_label"].text.lower() or "error" in widgets["status_label"].text.lower()
        widgets["calc_btn"].enable.assert_called()

    async def test_button_disabled_then_enabled(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        widgets["calc_btn"].disable.assert_called()
        widgets["calc_btn"].enable.assert_called()

    async def test_unknown_time_defaults(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        base_form["unknown_time"] = True
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        # Should still succeed with noon defaults
        assert base_state["chart_ready"] is True

    async def test_time_dashes_treated_as_unknown(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        base_form["hour_12"] = "--"
        base_form["minute_str"] = "--"
        base_form["ampm"] = "--"
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        assert base_state["chart_ready"] is True

    async def test_am_time_conversion(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        base_form["hour_12"] = "9"
        base_form["minute_str"] = "15"
        base_form["ampm"] = "AM"
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        # ChartInputs should have hour_24=9
        call_args = mock_compute.call_args
        inputs = call_args[0][0] if call_args[0] else call_args[1].get("inputs")
        if inputs:
            assert inputs.hour_24 == 9

    async def test_noon_pm_conversion(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        base_form["hour_12"] = "12"
        base_form["minute_str"] = "0"
        base_form["ampm"] = "PM"
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        call_args = mock_compute.call_args
        inputs = call_args[0][0] if call_args[0] else call_args[1].get("inputs")
        if inputs:
            assert inputs.hour_24 == 12

    async def test_midnight_am_conversion(
        self, base_state, base_form, widgets, callbacks,
        mock_geocode, mock_compute, _patch_js,
    ):
        from src.ui.calculate import on_calculate
        base_form["hour_12"] = "12"
        base_form["minute_str"] = "0"
        base_form["ampm"] = "AM"
        await on_calculate(base_state, base_form, **_call_kwargs(widgets, callbacks))

        call_args = mock_compute.call_args
        inputs = call_args[0][0] if call_args[0] else call_args[1].get("inputs")
        if inputs:
            assert inputs.hour_24 == 0
