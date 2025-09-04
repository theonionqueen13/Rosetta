import streamlit as st

# MUST be first Streamlit command
st.set_page_config(layout="wide")

st.title("🧭️ Rosetta Flight Deck")

# Upload CSV
uploaded_file = st.file_uploader("Upload natal chart CSV", type=["csv"])
label_style = st.radio("Label Style", ["Text", "Glyph"], index=1, horizontal=True)

if uploaded_file:
    # ----------------------------
    # Main layout: two columns
    # ----------------------------
    left_col, right_col = st.columns([2, 1])  # wider for patterns, narrower for expansions

    # ----------------------------------
    # Left column: Patterns & Shapes
    # ----------------------------------
    with left_col:
        st.subheader("Patterns")

        # Placeholder for parent patterns (later we’ll loop actual patterns here)
        with st.expander("Pattern 1: T-Square (AC–DC–Mercury)"):
            st.checkbox("T-Square", value=True)
            st.checkbox("Kite", value=False)
            st.checkbox("Wedge", value=False)

        with st.expander("Pattern 2: Grand Trine (Moon–Venus–Neptune)"):
            st.checkbox("Grand Trine", value=True)
            st.checkbox("Cradle", value=False)

    # ----------------------------------
    # Right column: Expansion Options
    # ----------------------------------
    with right_col:
        st.subheader("Expansion Options")

        # Minor asteroids toggle
        st.checkbox("Show Minor Asteroids", value=False)

        # Harmonics toggles
        st.markdown("#### Harmonics")
        cols = st.columns(6)
        harmonic_labels = ["5", "7", "9", "10", "11", "12"]
        for i, label in enumerate(harmonic_labels):
            cols[i].checkbox(label, value=False, key=f"harmonic_{label}")

    # ----------------------------------
    # Sidebar: Planet Profiles
    # ----------------------------------
    st.sidebar.subheader("🪐 Planet Profiles")
    st.sidebar.markdown("**Sun** — Core identity, purpose, and vitality.")
    st.sidebar.markdown("**Moon** — Emotions, inner world, instinctive needs.")
    st.sidebar.markdown("---")
