# house_selector_v2.py
import streamlit as st

def _selected_house_system() -> str:
    """
    Returns the current house system key ('equal', 'whole', 'placidus'),
    defaulting to 'equal' if unset.
    """
    return st.session_state.get("house_system", "equal")

def render_house_system_selector(container=None) -> str:
    """
    Renders the selectbox and updates session state WITHOUT recalculating planets.
    Only marks cusps as needing redraw. Returns the normalized key.
    """
    options = ["Equal", "Whole Sign", "Placidus"]
    # Map lowercase keys to display names
    key_to_display = {
        "equal": "Equal",
        "whole": "Whole Sign",
        "placidus": "Placidus"
    }
    display_to_key = {
        "Equal": "equal",
        "Whole Sign": "whole",
        "Placidus": "placidus"
    }
    
    # Callback to update session state when selectbox changes
    def on_change():
        choice = st.session_state.get("house_system_main")
        new_key = display_to_key.get(choice, "equal")
        prev_key = st.session_state.get("house_system", "equal")
        st.session_state["house_system"] = new_key
        if new_key != prev_key:
            st.session_state["last_house_system"] = new_key
            st.session_state["__cusps_dirty__"] = True
    
    # Use the existing value if present; otherwise default to Equal
    current_key = st.session_state.get("house_system", "equal")
    current_display = key_to_display.get(current_key, "Equal")

    ctx = container if container is not None else st
    ctx.selectbox(
        "House System",
        options,
        index=options.index(current_display),
        key="house_system_main",
        on_change=on_change
    )

    return current_key
