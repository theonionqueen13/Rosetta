# src/state_manager.py

# A constant list of session state keys that need to be swapped
# when swapping Chart 1 and Chart 2 (i.e., when Chart 2 moves to Chart 1's position).

import streamlit as st
from typing import List

# Month name list for backfilling form keys from chart objects
_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

CHART_KEYS_TO_SWAP = [
    # Form input data (widget state)
    "year", "month_name", "day", "hour_12", "minute_str", "ampm", "city",
    "profile_unknown_time",
    
    # Chart objects — all computed data travels inside them
    # (plot_data is an attribute on AstrologicalChart, not a separate session state key)
    "last_chart",
]


def _backfill_form_keys_from_chart(suffix: str = "") -> None:
    """After a swap, if form keys ended up None (because the _2 keys
    were never populated), fill them from the chart object that now
    occupies that slot."""
    chart = st.session_state.get(f"last_chart{suffix}")
    if chart is None:
        return

    dt_local = getattr(chart, "display_datetime", None)
    if dt_local is None:
        return

    key = lambda k: f"{k}{suffix}"

    if st.session_state.get(key("year")) is None:
        st.session_state[key("year")] = dt_local.year
    if st.session_state.get(key("month_name")) is None:
        st.session_state[key("month_name")] = _MONTH_NAMES[dt_local.month - 1]
    if st.session_state.get(key("day")) is None:
        st.session_state[key("day")] = dt_local.day

    # Time fields
    if st.session_state.get(key("hour_12")) is None:
        if getattr(chart, "unknown_time", False):
            st.session_state[key("hour_12")] = "--"
            st.session_state[key("minute_str")] = "--"
            st.session_state[key("ampm")] = "--"
        else:
            h24 = dt_local.hour
            h12 = h24 % 12 or 12
            st.session_state[key("hour_12")] = f"{h12:02d}"
            st.session_state[key("minute_str")] = f"{dt_local.minute:02d}"
            st.session_state[key("ampm")] = "AM" if h24 < 12 else "PM"

    if st.session_state.get(key("city")) is None:
        st.session_state[key("city")] = getattr(chart, "city", "") or ""

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

    # 2. Swap profile name trackers
    name_1 = st.session_state.get("current_profile")
    name_2 = st.session_state.get("last_test_chart_2")
    st.session_state["current_profile"] = name_2
    st.session_state["last_test_chart_2"] = name_1

    # 3. (last_chart / last_chart_2 are swapped via CHART_KEYS_TO_SWAP below)

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
            
    # 5. Normalize bool keys that may have been swapped to None
    #    (e.g. profile_unknown_time_2 may never have been set)
    for _bool_key in ("profile_unknown_time",):
        st.session_state[_bool_key] = bool(st.session_state.get(_bool_key) or False)
        st.session_state[_bool_key + "_2"] = bool(st.session_state.get(_bool_key + "_2") or False)

    # 6. Backfill any form keys that are None from the chart objects
    #    (happens when Chart 2 was loaded as an AstrologicalChart, not via form)
    _backfill_form_keys_from_chart("")
    _backfill_form_keys_from_chart("_2")

    # 7. Restore preserved widget states
    st.session_state["synastry_mode"] = preserved_synastry_mode
    st.session_state["chart_mode"] = preserved_chart_mode
    st.session_state["house_system"] = preserved_house_system

    # 8. Clear cached outputs to force a re-render
    st.session_state["render_fig"] = None
    st.session_state["render_result"] = None
    st.session_state.pop("_sidebar_cache", None)
    st.session_state.pop("_sidebar_cache_key", None)
    
    # 9. Clean caches
    try:
        st.cache_data.clear()
        import matplotlib.pyplot as plt
        plt.close('all')
    except Exception:
        # Ignore errors if Streamlit's internal cache mechanism changes
        pass
    
    # 10. Clear the pending flag (if triggered via deferred mechanism)
    st.session_state.pop("__pending_swap_charts__", None)
    
    # NOTE: Do NOT call st.rerun() here. This function is used as an
    # on_click callback, and Streamlit already reruns after on_click.
    # Calling st.rerun() would abort the current render mid-page,
    # causing form submit buttons to go missing.