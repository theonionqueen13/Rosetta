# src/state_manager.py

# A constant list of session state keys that need to be swapped
# when swapping Chart 1 and Chart 2 (i.e., when Chart 2 moves to Chart 1's position).

import streamlit as st
from typing import List

CHART_KEYS_TO_SWAP = [
    # Input Data
    "year", "month_name", "day", "hour_12", "minute_str", "ampm", "city",
    
    # Calculated Data (DataFrame/Chart Objects)
    "last_df",
    "plot_data",
    "chart_dt_utc",
    "chart_unknown_time",
    "chart_positions",

    # Calculated Astrological Summaries
    "dispositor_summary_rows",
    "dispositor_chains_rows",
    
    # Calculated Patterns/Aspects
    "edges_major",
    "edges_minor",
    "patterns",
    "shapes",
    "filaments",
    "combos",
    "singleton_map",
    "major_edges_all",
]

def swap_primary_and_secondary_charts() -> None:
    """
    Performs the chart swap operation by iterating over a predefined
    list of keys and swapping the values between key and key_2 in session state.
    """
    # 1. Preserve widget states that shouldn't be affected by swap
    # These are saved, then restored after the mass swap.
    preserved_synastry_mode = st.session_state.get("synastry_mode", False)
    preserved_chart_mode = st.session_state.get("chart_mode", "Circuits")
    preserved_house_system = st.session_state.get("house_system", "placidus")

    # 2. Swap the test chart radio button selections
    test_chart_1 = st.session_state.get("test_chart_radio", "Custom")
    test_chart_2 = st.session_state.get("test_chart_2", "Custom")
    st.session_state["test_chart_radio"] = test_chart_2
    st.session_state["test_chart_2"] = test_chart_1

    # 3. Swap the last_test_chart trackers
    last_1 = st.session_state.get("last_test_chart")
    last_2 = st.session_state.get("last_test_chart_2")
    st.session_state["last_test_chart"] = last_2
    st.session_state["last_test_chart_2"] = last_1

    # 4. Perform the mass swap of all calculated and input data
    for key1 in CHART_KEYS_TO_SWAP:
        key2 = key1 + "_2"
        val1 = st.session_state.get(key1)
        val2 = st.session_state.get(key2)
        
        # NOTE: We use .get() here to prevent KeyErrors if one of the 
        # keys hasn't been initialized yet, which can happen on first run.
        if key1 in st.session_state:
            st.session_state[key1] = val2
        if key2 in st.session_state:
            st.session_state[key2] = val1
            
    # 5. Restore preserved widget states
    st.session_state["synastry_mode"] = preserved_synastry_mode
    st.session_state["chart_mode"] = preserved_chart_mode
    st.session_state["house_system"] = preserved_house_system

    # 6. Clear cached outputs to force a re-render
    st.session_state["render_fig"] = None
    st.session_state["render_result"] = None
    
    # 7. Clean caches and force rerun
    try:
        st.cache_data.clear()
        import matplotlib.pyplot as plt
        plt.close('all')
    except Exception:
        # Ignore errors if Streamlit's internal cache mechanism changes
        pass
    
    # 8. Clear the flag and force a full refresh
    if "__pending_swap_charts__" in st.session_state:
        del st.session_state["__pending_swap_charts__"]
        
    st.rerun()