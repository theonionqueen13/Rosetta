"""Tests for src/core/event_lookup_v2.py — date parsing, delta formatting, event search."""
from datetime import datetime, timezone, timedelta

import pytest

from src.core.event_lookup_v2 import (
    _parse_ts,
    _is_exact_time,
    _format_delta,
    find_nearby_events,
    WINDOWS,
    EXCLUDED,
)


# ═══════════════════════════════════════════════════════════════════════
# _parse_ts
# ═══════════════════════════════════════════════════════════════════════

class TestParseTs:
    def test_iso_with_z(self):
        dt = _parse_ts("2024-03-20T10:06:00Z")
        assert dt.year == 2024
        assert dt.month == 3
        assert dt.day == 20
        assert dt.hour == 10
        assert dt.minute == 6

    def test_iso_with_offset(self):
        dt = _parse_ts("2024-06-20T14:51:00+00:00")
        assert dt.tzinfo is not None
        assert dt.hour == 14

    def test_date_only_with_z(self):
        dt = _parse_ts("2024-01-01T00:00:00Z")
        assert dt.year == 2024
        assert dt.hour == 0


# ═══════════════════════════════════════════════════════════════════════
# _is_exact_time
# ═══════════════════════════════════════════════════════════════════════

class TestIsExactTime:
    def test_meta_time_listed_true(self):
        ev = {"meta": {"time_listed": True}}
        assert _is_exact_time(ev) is True

    def test_meta_time_listed_false(self):
        ev = {"meta": {"time_listed": False}}
        assert _is_exact_time(ev) is False

    def test_midnight_utc_is_inexact(self):
        ev = {"timestamp_ut": "2024-01-01T00:00:00Z"}
        assert _is_exact_time(ev) is False

    def test_nonmidnight_is_exact(self):
        ev = {"timestamp_ut": "2024-03-20T10:06:00Z"}
        assert _is_exact_time(ev) is True

    def test_no_meta_no_timestamp(self):
        ev = {}
        assert _is_exact_time(ev) is True  # doesn't end with T00:00:00Z


# ═══════════════════════════════════════════════════════════════════════
# _format_delta
# ═══════════════════════════════════════════════════════════════════════

class TestFormatDelta:
    def test_exact_zero(self):
        result = _format_delta(0, exact=True)
        assert result == "at chart time"

    def test_exact_positive(self):
        result = _format_delta(3600, exact=True)
        assert "after" in result
        assert "1 hr" in result

    def test_exact_negative(self):
        result = _format_delta(-7200, exact=True)
        assert "before" in result

    def test_exact_days(self):
        result = _format_delta(172800, exact=True)  # 2 days
        assert "2 days" in result

    def test_inexact_same_day(self):
        result = _format_delta(3600, exact=False)  # < 86400
        assert result == "same day"

    def test_inexact_days_after(self):
        result = _format_delta(172800, exact=False)  # 2 days
        assert "2 days" in result
        assert "after" in result

    def test_inexact_days_before(self):
        result = _format_delta(-259200, exact=False)  # 3 days
        assert "3 days" in result
        assert "before" in result

    def test_exact_minutes_only(self):
        result = _format_delta(300, exact=True)  # 5 min
        assert "5 min" in result


# ═══════════════════════════════════════════════════════════════════════
# find_nearby_events
# ═══════════════════════════════════════════════════════════════════════

class TestFindNearbyEvents:
    @pytest.fixture
    def target_dt(self):
        return datetime(2024, 3, 20, 12, 0, 0, tzinfo=timezone.utc)

    @pytest.fixture
    def sample_events(self):
        return [
            {
                "type": "eclipse",
                "timestamp_ut": "2024-03-20T10:06:00Z",
                "meta": {"time_listed": True, "subtype": "Total Solar Eclipse"},
            },
            {
                "type": "ingress",
                "timestamp_ut": "2024-03-20T03:06:00Z",
                "meta": {"time_listed": True, "subtype": "Sun enters Aries"},
            },
            {
                "type": "lunation",
                "timestamp_ut": "2024-04-08T18:21:00Z",
                "meta": {"time_listed": True, "subtype": "New Moon"},
            },
            {
                # Excluded type
                "type": "opposition",
                "timestamp_ut": "2024-03-20T12:00:00Z",
                "meta": {},
            },
            {
                # Too far away for its window
                "type": "station",
                "timestamp_ut": "2024-04-15T00:00:00Z",
                "meta": {"time_listed": False},
            },
        ]

    def test_finds_eclipse(self, target_dt, sample_events):
        results = find_nearby_events(target_dt, sample_events)
        types = [r[1] for r in results]
        assert "eclipse" in types

    def test_finds_ingress(self, target_dt, sample_events):
        results = find_nearby_events(target_dt, sample_events)
        types = [r[1] for r in results]
        assert "ingress" in types

    def test_excludes_opposition(self, target_dt, sample_events):
        results = find_nearby_events(target_dt, sample_events)
        types = [r[1] for r in results]
        assert "opposition" not in types

    def test_sorted_by_proximity(self, target_dt, sample_events):
        results = find_nearby_events(target_dt, sample_events)
        if len(results) >= 2:
            assert abs(results[0][3]) <= abs(results[1][3])

    def test_empty_target(self, sample_events):
        results = find_nearby_events(None, sample_events)
        assert results == []

    def test_empty_events(self, target_dt):
        results = find_nearby_events(target_dt, [])
        assert results == []

    def test_station_outside_window(self, target_dt, sample_events):
        """Station 26 days away — the window is only 2 days."""
        results = find_nearby_events(target_dt, sample_events)
        types = [r[1] for r in results]
        assert "station" not in types

    def test_result_tuple_structure(self, target_dt, sample_events):
        results = find_nearby_events(target_dt, sample_events)
        for item in results:
            assert len(item) == 5
            ev_dt, etype, ev, delta_seconds, exact = item
            assert isinstance(ev_dt, datetime)
            assert isinstance(etype, str)
            assert isinstance(ev, dict)
            assert isinstance(delta_seconds, (int, float))
            assert isinstance(exact, bool)
