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
    # Use the existing value if present; otherwise default to Equal
    current_key = st.session_state.get("house_system", "equal")
    try:
        current_index = options.index(current_key.title().replace(" Sign", ""))
    except ValueError:
        current_index = 0

    ctx = container if container is not None else st
    choice = ctx.selectbox(
        "House System",
        options,
        index=current_index,
        key="house_system_main",
    )

    new_key = choice.lower().replace(" sign", "")  # "Equal"->"equal", "Whole Sign"->"whole", "Placidus"->"placidus"
    prev_key = st.session_state.get("house_system", "equal")

    # Update the chosen system (no run_chart; no planet recompute)
    st.session_state["house_system"] = new_key

    # If it changed, just mark cusps dirty so your next render uses the new system
    if new_key != prev_key:
        st.session_state["last_house_system"] = new_key
        st.session_state["__cusps_dirty__"] = True  # your renderer can read this if needed

    return new_key
