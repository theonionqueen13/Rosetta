# src/geocoding.py

import os
from typing import Optional, Tuple
import streamlit as st
from opencage.geocoder import OpenCageGeocode
from timezonefinder import TimezoneFinder

# --- Configuration (Moved from top of test_calc_v2.py) ---
try:
    # ⚠️ Check this line and the corresponding entry in your .streamlit/secrets.toml
    _OPENCAGE_KEY = st.secrets["opencage"]["api_key"] 
except KeyError:
    _OPENCAGE_KEY = None
    # ⚠️ This st.error is important for debugging!
    st.error("Error: OpenCage API key not found in st.secrets.") 

# Create a single, reusable geocoder instance
# ⚠️ This line will fail if _OPENCAGE_KEY is None, which is fine, 
# but it could be the source of your "Please enter a valid city" message 
# if the code proceeds with a failed geocoder object.
if _OPENCAGE_KEY:
    _geolocator = OpenCageGeocode(_OPENCAGE_KEY)
else:
    _geolocator = None
    
_tzfinder = TimezoneFinder(in_memory=True)

# Create a single, reusable geocoder instance
_geolocator = OpenCageGeocode(_OPENCAGE_KEY)
_tzfinder = TimezoneFinder()

def geocode_city_with_timezone(
    city_query: str,
) -> Tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
    """
    Geocodes a city query, extracts latitude, longitude, timezone name,
    and the formatted address.
    """
    lat = lon = tz_name = None
    formatted_address = None

    if not city_query or not _OPENCAGE_KEY:
        return lat, lon, tz_name, formatted_address

    try:
        results = _geolocator.geocode(city_query, no_annotations='1', limit=1)
    except Exception as e:
        # Catch potential API key or connection errors
        st.error(f"Geocoding API failed: {e}")
        return lat, lon, tz_name, formatted_address

    if results:
        first_result = results[0]
        lat = first_result['geometry']['lat']
        lon = first_result['geometry']['lng']
        formatted_address = first_result['formatted']
        
        # Use TimezoneFinder on the geocoded coordinates
        tz_name = _tzfinder.timezone_at(lng=lon, lat=lat)

    return lat, lon, tz_name, formatted_address