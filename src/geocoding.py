# src/geocoding.py

import os
from typing import Optional, Tuple
import streamlit as st
from opencage.geocoder import OpenCageGeocode
from timezonefinder import TimezoneFinder

# --- Configuration ---
try:
    _OPENCAGE_KEY = st.secrets["opencage"]["api_key"]
except KeyError:
    _OPENCAGE_KEY = None
    st.error("Error: OpenCage API key not found in st.secrets.")

# Use cache_resource so these are constructed ONCE per server process and
# survive Streamlit hot-reloads without re-opening all their file handles.
@st.cache_resource(show_spinner=False)
def _get_geolocator() -> Optional[OpenCageGeocode]:
    return OpenCageGeocode(_OPENCAGE_KEY) if _OPENCAGE_KEY else None

@st.cache_resource(show_spinner=False)
def _get_tzfinder() -> TimezoneFinder:
    return TimezoneFinder(in_memory=True)


@st.cache_data(show_spinner=False)
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
        st.error(f"Geocoding API failed: {e}")
        return lat, lon, tz_name, formatted_address

    if results:
        first_result = results[0]
        lat = first_result['geometry']['lat']
        lon = first_result['geometry']['lng']
        formatted_address = first_result['formatted']
        tz_name = _get_tzfinder().timezone_at(lng=lon, lat=lat)

    return lat, lon, tz_name, formatted_address