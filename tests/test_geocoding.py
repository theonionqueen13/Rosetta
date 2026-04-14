"""Tests for src/core/geocoding.py — geocode_city_with_timezone (mocked HTTP)."""
from unittest.mock import patch, MagicMock

import pytest


# ═══════════════════════════════════════════════════════════════════════
# We need to mock _OPENCAGE_KEY at import time, so we patch config first.
# ═══════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _reset_geocoding_singletons():
    """Reset module-level singletons between tests."""
    import src.core.geocoding as geo
    geo._geolocator = None
    geo._tzfinder = None
    # Also clear the lru_cache
    geo.geocode_city_with_timezone.cache_clear()
    yield
    geo._geolocator = None
    geo._tzfinder = None
    geo.geocode_city_with_timezone.cache_clear()


class TestGeocodeCityWithTimezone:
    def test_empty_query_returns_nones(self):
        from src.core.geocoding import geocode_city_with_timezone
        lat, lon, tz, addr = geocode_city_with_timezone("")
        assert lat is None
        assert lon is None
        assert tz is None
        assert addr is None

    @patch("src.core.geocoding._OPENCAGE_KEY", "fake-key")
    @patch("src.core.geocoding._get_geolocator")
    @patch("src.core.geocoding._get_tzfinder")
    def test_successful_geocode(self, mock_tzfinder_fn, mock_geo_fn):
        from src.core.geocoding import geocode_city_with_timezone
        geocode_city_with_timezone.cache_clear()

        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = [
            {
                "geometry": {"lat": 40.7128, "lng": -74.006},
                "formatted": "New York, NY, USA",
            }
        ]
        mock_geo_fn.return_value = mock_geocoder

        mock_tzf = MagicMock()
        mock_tzf.timezone_at.return_value = "America/New_York"
        mock_tzfinder_fn.return_value = mock_tzf

        lat, lon, tz, addr = geocode_city_with_timezone("New York")
        assert lat == pytest.approx(40.7128)
        assert lon == pytest.approx(-74.006)
        assert tz == "America/New_York"
        assert addr == "New York, NY, USA"

    @patch("src.core.geocoding._OPENCAGE_KEY", "fake-key")
    @patch("src.core.geocoding._get_geolocator")
    def test_no_results(self, mock_geo_fn):
        from src.core.geocoding import geocode_city_with_timezone
        geocode_city_with_timezone.cache_clear()

        mock_geocoder = MagicMock()
        mock_geocoder.geocode.return_value = []
        mock_geo_fn.return_value = mock_geocoder

        lat, lon, tz, addr = geocode_city_with_timezone("ZZZZZZXXX")
        assert lat is None
        assert lon is None

    @patch("src.core.geocoding._OPENCAGE_KEY", "fake-key")
    @patch("src.core.geocoding._get_geolocator")
    def test_api_exception(self, mock_geo_fn):
        from src.core.geocoding import geocode_city_with_timezone
        geocode_city_with_timezone.cache_clear()

        mock_geocoder = MagicMock()
        mock_geocoder.geocode.side_effect = RuntimeError("API down")
        mock_geo_fn.return_value = mock_geocoder

        lat, lon, tz, addr = geocode_city_with_timezone("London")
        assert lat is None
        assert lon is None

    @patch("src.core.geocoding._OPENCAGE_KEY", None)
    def test_no_api_key(self):
        from src.core.geocoding import geocode_city_with_timezone
        geocode_city_with_timezone.cache_clear()

        lat, lon, tz, addr = geocode_city_with_timezone("Paris")
        assert lat is None


class TestGetGeolocator:
    @patch("src.core.geocoding._OPENCAGE_KEY", "fake-key")
    def test_creates_instance(self):
        import src.core.geocoding as geo
        geo._geolocator = None
        with patch("src.core.geocoding.OpenCageGeocode") as MockOCG:
            result = geo._get_geolocator()
            MockOCG.assert_called_once_with("fake-key")

    @patch("src.core.geocoding._OPENCAGE_KEY", None)
    def test_returns_none_without_key(self):
        import src.core.geocoding as geo
        geo._geolocator = None
        result = geo._get_geolocator()
        assert result is None


class TestGetTzfinder:
    def test_creates_singleton(self):
        import src.core.geocoding as geo
        geo._tzfinder = None
        with patch("src.core.geocoding.TimezoneFinder") as MockTZF:
            result = geo._get_tzfinder()
            MockTZF.assert_called_once_with(in_memory=True)
