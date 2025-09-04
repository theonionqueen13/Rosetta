import streamlit as st
from profiles import format_planet_profile
from dictionary import OBJECT_MEANINGS

st.title("🌌 Astro Profile Generator")

planet = st.selectbox("Choose a planet", list(OBJECT_MEANINGS.keys()))
if planet:
    st.write(format_planet_profile(planet))