# src/chart_core.py

import streamlit as st
import datetime as dt
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, Tuple
import pandas as pd
from toggles_v2 import COMPASS_KEY
# Import the new geocoding module
from src.geocoding import geocode_city_with_timezone
# Import the core calculation functions from the original calc_v2.py
from calc_v2 import calculate_chart, chart_sect_from_df, build_aspect_edges, \
                    annotate_reception, build_dispositor_tables, \
                    build_conjunction_clusters, plot_dispositor_graph 
                    
# You'll also need the global constants from the lookup file:
from lookup_v2 import MAJOR_OBJECTS, TOGGLE_ASPECTS, ASPECTS
# And the house system selector:
from house_selector_v2 import _selected_house_system


def get_chart_inputs_from_session(suffix: str = "") -> Dict[str, Any]:
    """Extracts all necessary birth data inputs from session state."""
    # This structure mirrors the inputs used in your original file.
    data = {}
    data["year"] = st.session_state.get(f"year{suffix}")
    data["month_name"] = st.session_state.get(f"month_name{suffix}")
    data["day"] = st.session_state.get(f"day{suffix}")
    data["hour_12"] = st.session_state.get(f"hour_12{suffix}")
    data["minute_str"] = st.session_state.get(f"minute_str{suffix}")
    data["ampm"] = st.session_state.get(f"ampm{suffix}")
    data["city"] = st.session_state.get(f"city{suffix}")
    
    # Non-suffixed inputs required for calculation
    data["house_system"] = st.session_state.get("house_system", "placidus")
    
    # Crucial: Get the unknown time flag
    data["unknown_time_flag"] = st.session_state.get(f"profile_unknown_time{suffix}", False)
    
    return data

def calculate_chart_from_session(suffix: str = "") -> bool:
    """
    Core function to read input data, geocode, calculate the chart using 
    calc_v2, and store all results back into session state (with suffix).
    
    Returns True on success, False otherwise.
    """
    inputs = get_chart_inputs_from_session(suffix)
    city = inputs.get("city")
    chart_unknown_time = inputs.get("unknown_time_flag") # DERIVED HERE
    
    # 1. Input Validation and Time Parsing
    try:
        year = int(inputs.get("year"))
        month = dt.datetime.strptime(inputs.get("month_name"), "%B").month
        day = int(inputs.get("day"))
        hour_12 = int(inputs.get("hour_12"))
        minute = int(inputs.get("minute_str"))
        ampm = inputs.get("ampm", "AM")
        
        # Convert 12-hour time to 24-hour time
        hour_24 = hour_12
        if ampm == "PM" and hour_12 != 12:
            hour_24 += 12
        elif ampm == "AM" and hour_12 == 12: # Midnight
            hour_24 = 0
            
        local_dt = dt.datetime(year, month, day, hour_24, minute)
        
    except Exception as e:
        # st.error(f"Input parsing failed: {e}")
        return False # Fail gracefully if inputs are bad
        
    # 2. Geocoding and Timezone
    lat, lon, tz_name, _ = geocode_city_with_timezone(city)
    
    if lat is None or lon is None or tz_name is None:
        # st.error(f"Geocoding failed for {city}.")
        return False
        
    # 3. Timezone Conversion (local -> UTC)
    try:
        tz = ZoneInfo(tz_name)
        # local_dt is naive, make it aware using the found tz
        local_dt_aware = local_dt.replace(tzinfo=tz)
        utc_dt = local_dt_aware.astimezone(dt.timezone.utc).replace(tzinfo=None)
    except Exception as e:
        # st.error(f"Timezone conversion failed: {e}")
        return False
        
    # 4. Core Calculation
    try:
        # Fix 1: Extract components and define offset
        utc_tz_offset = 0 # Time is already UTC
        
        # Fix 2: Unpack 3 values, not 4
        (
            df_positions,     # combined_df
            aspect_df_result, # aspect_df / None
            plot_data,        # plot_data
        ) = calculate_chart(
            # Pass the required components separately
            year=utc_dt.year,
            month=utc_dt.month,
            day=utc_dt.day,
            hour=utc_dt.hour,
            minute=utc_dt.minute,
            tz_offset=utc_tz_offset,
            lat=lat,
            lon=lon,
            # Other arguments
            input_is_ut=True, 
            tz_name=tz_name, 
            house_system=inputs["house_system"],
            include_aspects=False,
            # Fix 3: Pass the DERIVED flag
            unknown_time=chart_unknown_time,
        )
        
        # Derive placeholders for keys expected elsewhere in the app
        house_angles_df = df_positions[df_positions["Object"].str.contains("cusp")].copy()
        chart_data_summary = df_positions 

    except Exception as e:
        st.error(f"Core astrological calculation failed: {e}")
        return False

    # 5. Post-Processing (Aspects, Dispositors, Patterns)
    # ... (using the returned df_positions)
    
    # Aspects and Edge Calculation
    aspects_toggle = st.session_state.get("toggle_aspects", TOGGLE_ASPECTS) 
    
# Aspects and Edge Calculation
    aspects_toggle = st.session_state.get("toggle_aspects", TOGGLE_ASPECTS) 
    
    # ⬇️ PULL THE DYNAMIC FLAG FROM SESSION STATE ⬇️
    include_compass_rose = st.session_state.get(COMPASS_KEY, False)

    # CORRECT CALLS: Pass the DataFrame and the dynamic boolean flag.
    edges_major, edges_minor = build_aspect_edges(
        df_positions, 
        compass_rose=include_compass_rose
    )
    
    # Chart Sections and Summary
    dispositor_summary_rows = build_dispositor_tables(df_positions)
    
    # 6. Store ALL Results in Session State
    
    st.session_state[f"last_df{suffix}"] = df_positions
    st.session_state[f"chart_dt_utc{suffix}"] = utc_dt
    # Use the DERIVED flag
    st.session_state[f"chart_unknown_time{suffix}"] = chart_unknown_time 
    st.session_state[f"chart_positions{suffix}"] = chart_data_summary
    st.session_state[f"house_angles_df{suffix}"] = house_angles_df # Keep angles for rendering
    st.session_state[f"dispositor_summary_rows{suffix}"] = dispositor_summary_rows
    st.session_state[f"dispositor_chains_rows{suffix}"] = [] # Placeholder for chains
    st.session_state[f"edges_major{suffix}"] = edges_major
    st.session_state[f"edges_minor{suffix}"] = edges_minor
    # st.session_state[f"patterns{suffix}"] = ... (calculated later in UI)
    # st.session_state[f"shapes{suffix}"] = ... (calculated later in UI)

    return True