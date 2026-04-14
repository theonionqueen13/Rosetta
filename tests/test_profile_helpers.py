"""Tests for src.db.profile_helpers — profile apply/convert (pure logic)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import datetime as _dt

import pytest


# ---------------------------------------------------------------------------
# birth_data_from_chart
# ---------------------------------------------------------------------------
class TestBirthDataFromChart:
    """Tests for birth_data_from_chart()."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.db.profile_helpers import birth_data_from_chart
        self.fn = birth_data_from_chart

    def test_with_display_datetime(self):
        chart = SimpleNamespace(
            display_datetime=_dt.datetime(1990, 6, 15, 14, 30),
            city="New York",
        )
        yr, mo, dy, hr, mn, city = self.fn(chart)
        assert (yr, mo, dy, hr, mn) == (1990, 6, 15, 14, 30)
        assert city == "New York"

    def test_with_chart_datetime_isoformat(self):
        chart = SimpleNamespace(
            display_datetime=None,
            chart_datetime="1985-03-22T09:15:00",
            city="London",
        )
        yr, mo, dy, hr, mn, city = self.fn(chart)
        assert (yr, mo, dy, hr, mn) == (1985, 3, 22, 9, 15)
        assert city == "London"

    def test_no_datetime_returns_nones(self):
        chart = SimpleNamespace(
            display_datetime=None,
            chart_datetime=None,
            city="Paris",
        )
        yr, mo, dy, hr, mn, city = self.fn(chart)
        assert yr is None and mo is None and dy is None
        assert hr is None and mn is None
        assert city == "Paris"

    def test_missing_city_returns_empty(self):
        chart = SimpleNamespace(
            display_datetime=_dt.datetime(2000, 1, 1, 0, 0),
        )
        _, _, _, _, _, city = self.fn(chart)
        assert city == ""

    def test_with_sample_chart(self, sample_chart):
        yr, mo, dy, hr, mn, city = self.fn(sample_chart)
        # sample_chart is 1990-06-15 14:30
        assert yr == 1990
        assert mo == 6
        assert dy == 15


# ---------------------------------------------------------------------------
# apply_profile — new format
# ---------------------------------------------------------------------------
class TestApplyProfileNewFormat:
    """Tests for apply_profile() with PersonProfile format."""

    def _make_chart_stub(self, *, unknown_time=False):
        """Create a minimal chart-like object."""
        return SimpleNamespace(
            display_datetime=_dt.datetime(1990, 6, 15, 14, 30),
            display_name="Test",
            city="NYC",
            latitude=40.7,
            longitude=-74.0,
            timezone="America/New_York",
            unknown_time=unknown_time,
            circuit_names={},
        )

    def _make_pp_stub(self, chart, *, name="Test", gender=None, rel="self"):
        """Create a PersonProfile-like object."""
        return SimpleNamespace(
            name=name,
            gender=gender,
            relationship_to_querent=rel,
            astro_chart=chart,
        )

    def test_new_format_returns_true(self):
        from src.db.profile_helpers import apply_profile

        chart = self._make_chart_stub()
        pp = self._make_pp_stub(chart)

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp):
            state = {}
            result = apply_profile("Test", {}, state)
            assert result is True

    def test_populates_state_keys(self):
        from src.db.profile_helpers import apply_profile

        chart = self._make_chart_stub()
        pp = self._make_pp_stub(chart)

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp):
            state = {}
            apply_profile("Test", {}, state)

            assert state["year"] == 1990
            assert state["day"] == 15
            assert state["current_lat"] == 40.7
            assert state["current_lon"] == -74.0
            assert state["birth_name"] == "Test"
            assert state["is_my_chart"] is True

    def test_am_pm_conversion_pm(self):
        from src.db.profile_helpers import apply_profile

        chart = self._make_chart_stub()  # hour=14 → PM
        pp = self._make_pp_stub(chart)

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp):
            state = {}
            apply_profile("Test", {}, state)

            assert state["ampm"] == "PM"
            assert state["hour_12"] == "02"

    def test_am_pm_conversion_am(self):
        from src.db.profile_helpers import apply_profile

        chart = SimpleNamespace(
            display_datetime=_dt.datetime(1990, 6, 15, 9, 15),
            display_name="AM Test",
            city="NYC",
            latitude=40.7,
            longitude=-74.0,
            timezone="America/New_York",
            unknown_time=False,
            circuit_names={},
        )
        pp = self._make_pp_stub(chart)

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp):
            state = {}
            apply_profile("Test", {}, state)

            assert state["ampm"] == "AM"
            assert state["hour_12"] == "09"

    def test_midnight_conversion(self):
        from src.db.profile_helpers import apply_profile

        chart = SimpleNamespace(
            display_datetime=_dt.datetime(1990, 6, 15, 0, 0),
            display_name="Midnight",
            city="NYC",
            latitude=40.7,
            longitude=-74.0,
            timezone="America/New_York",
            unknown_time=False,
            circuit_names={},
        )
        pp = self._make_pp_stub(chart)

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp):
            state = {}
            apply_profile("Test", {}, state)

            assert state["hour_12"] == "12"
            assert state["ampm"] == "AM"

    def test_unknown_time_flag(self):
        from src.db.profile_helpers import apply_profile

        chart = self._make_chart_stub(unknown_time=True)
        pp = self._make_pp_stub(chart)

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp):
            state = {}
            apply_profile("Test", {}, state)

            assert state["profile_unknown_time"] is True
            assert state["hour_12"] == "--"
            assert state["minute_str"] == "--"
            assert state["ampm"] == "--"


# ---------------------------------------------------------------------------
# apply_profile — old format
# ---------------------------------------------------------------------------
class TestApplyProfileOldFormat:
    """Tests for apply_profile() with legacy dict format."""

    def test_old_format_returns_false(self):
        from src.db.profile_helpers import apply_profile

        pp_no_chart = SimpleNamespace(
            name=None,
            gender=None,
            relationship_to_querent=None,
            astro_chart=None,
        )

        with patch("src.mcp.comprehension_models.PersonProfile.from_dict", return_value=pp_no_chart):
            old_data = {
                "year": 1985,
                "month": 3,
                "day": 22,
                "hour": 9,
                "minute": 15,
                "city": "London",
                "lat": 51.5,
                "lon": -0.1,
                "tz_name": "Europe/London",
            }
            state = {}
            result = apply_profile("Test", old_data, state)
            assert result is False
            assert state["year"] == 1985
            assert state["city"] == "London"
            assert state["ampm"] == "AM"
            assert state["hour_12"] == "09"


# ---------------------------------------------------------------------------
# community_save
# ---------------------------------------------------------------------------
class TestCommunitySave:
    """Tests for community_save() in-memory store."""

    def test_returns_id(self):
        from src.db.profile_helpers import community_save, _COMMUNITY_CHARTS

        # Clear the store to avoid cross-test bleed
        _COMMUNITY_CHARTS.clear()

        cid = community_save("Alice", {"year": 1990})
        assert cid == "comm_1"

    def test_increments_id(self):
        from src.db.profile_helpers import community_save, _COMMUNITY_CHARTS

        _COMMUNITY_CHARTS.clear()

        community_save("Alice", {"year": 1990})
        cid2 = community_save("Bob", {"year": 1985})
        assert cid2 == "comm_2"

    def test_stores_payload(self):
        from src.db.profile_helpers import community_save, _COMMUNITY_CHARTS

        _COMMUNITY_CHARTS.clear()

        cid = community_save("Alice", {"year": 1990}, submitted_by="user1")
        assert _COMMUNITY_CHARTS[cid]["profile_name"] == "Alice"
        assert _COMMUNITY_CHARTS[cid]["submitted_by"] == "user1"
