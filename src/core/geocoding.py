"""
Geocoding — place name → latitude / longitude / timezone resolution.

Wraps the OpenCage geocoding API and *timezonefinder* to convert a
human-readable place string into the ``(lat, lon, tz_str)`` tuple
required by the chart calculation engine.
"""

import logging
from typing import Optional, Tuple
from opencage.geocoder import OpenCageGeocode
from timezonefinder import TimezoneFinder

from config import get_secret

_log = logging.getLogger(__name__)

# --- Configuration ---
_OPENCAGE_KEY = get_secret("opencage", "api_key")
if not _OPENCAGE_KEY:
    _log.warning("OpenCage API key not found. Geocoding will be unavailable.")

# Module-level singletons (constructed once per process — replaces @st.cache_resource)
_geolocator: Optional[OpenCageGeocode] = None
_tzfinder: Optional[TimezoneFinder] = None


def _get_geolocator() -> Optional[OpenCageGeocode]:
    """Return the module-level OpenCageGeocode singleton, creating it on first call."""
    global _geolocator
    if _geolocator is None and _OPENCAGE_KEY:
        _geolocator = OpenCageGeocode(_OPENCAGE_KEY)
    return _geolocator


def _get_tzfinder() -> TimezoneFinder:
    """Return the module-level TimezoneFinder singleton, creating it on first call."""
    global _tzfinder
    if _tzfinder is None:
        _tzfinder = TimezoneFinder(in_memory=True)
    return _tzfinder


# LRU cache replaces @st.cache_data — same city string → same result
from functools import lru_cache


@lru_cache(maxsize=256)
def geocode_city_with_timezone(
    city_query: str,
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    Geocodes a city query, extracts latitude, longitude, timezone name,
    and the formatted address.  Results are cached so repeated reruns for
    the same city string do not open new SSL connections.
    """
    lat = lon = tz_name = formatted_address = None

    if not city_query or not _OPENCAGE_KEY:
        return lat, lon, tz_name, formatted_address

    geolocator = _get_geolocator()
    if geolocator is None:
        return lat, lon, tz_name, formatted_address

    try:
        results = geolocator.geocode(city_query, no_annotations='1', limit=1)
    except Exception as e:
        _log.error(f"Geocoding API failed: {e}")
        return lat, lon, tz_name, formatted_address

    if results:
        first_result = results[0]
        lat = first_result['geometry']['lat']
        lon = first_result['geometry']['lng']
        formatted_address = first_result['formatted']
        tz_name = _get_tzfinder().timezone_at(lng=lon, lat=lat)

    return lat, lon, tz_name, formatted_address