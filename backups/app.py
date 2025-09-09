import streamlit as st
from dictionary import OBJECT_MEANINGS
from profiles import format_planet_profile

st.title("🌌 Astro Profile Generator")

planet = st.selectbox("Choose a planet", list(OBJECT_MEANINGS.keys()))
if planet:
    st.write(format_planet_profile(planet))
