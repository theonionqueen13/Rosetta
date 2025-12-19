# src/test_data.py

from typing import Dict, Any
import streamlit as st

# --- Centralized Test Chart Data (Defined once) ---
# MONTH_NAMES is included here for context, as it's directly used by the chart logic
MONTH_NAMES = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

TEST_CHARTS: Dict[str, Dict[str, Any]] = {
    "Wildhorse": {
        "year": 1983,
        "month_name": "January",
        "day": 15,
        "hour_12": "11",
        "minute_str": "27",
        "ampm": "AM",
        "city": "Red Bank, NJ",
    },
    "Joylin": {
        "year": 1990,
        "month_name": "July",
        "day": 29,
        "hour_12": "1",
        "minute_str": "39",
        "ampm": "AM",
        "city": "Newton, KS",
    },
    "Terra": {
        "year": 1992,
        "month_name": "January",
        "day": 28,
        "hour_12": "2",
        "minute_str": "54",
        "ampm": "PM",
        "city": "Newton, KS",
    },
    "Jessica": {
        "year": 1990,
        "month_name": "November",
        "day": 20,
        "hour_12": "4",
        "minute_str": "29",
        "ampm": "PM",
        "city": "Wichita, KS",
    }
}

def apply_test_chart_to_session(chart_name: str, suffix: str = "") -> bool:
    """
    Applies the birth data for the given chart_name to st.session_state,
    using the provided suffix for synastry (e.g., '_2').
    Returns True if data was successfully applied.
    """
    if chart_name not in TEST_CHARTS:
        return False
        
    data = TEST_CHARTS[chart_name]
    
    for key, value in data.items():
        st.session_state[key + suffix] = value
        
    # Set a flag indicating defaults were loaded for Chart 1
    if not suffix:
        st.session_state["defaults_loaded"] = True
        
    return True