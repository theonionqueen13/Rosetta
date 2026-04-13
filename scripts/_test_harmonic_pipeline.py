"""Quick diagnostic: verify the harmonic-edge pipeline end-to-end."""
import swisseph as swe
swe.set_ephe_path("ephe")

from src.core.calc_v2 import build_aspect_edges, calculate_chart
from src.core.models_v2 import AstrologicalChart

# 1. Calculate a chart
df, asp_df, plot_data, chart = calculate_chart(
    year=2000, month=1, day=1, hour=12, minute=0,
    tz_offset=0, lat=40.7128, lon=-74.0060,
    input_is_ut=True, house_system="placidus",
    include_aspects=True, unknown_time=False,
    display_name="Test", city="NYC",
)

# 2. Build edges
edges_major, edges_minor, edges_harmonic = build_aspect_edges(chart)
print(f"Detection: Major={len(edges_major)}, Minor={len(edges_minor)}, Harmonic={len(edges_harmonic)}")

# 3. Attach to chart (as compute_chart now does)
chart.edges_major = [tuple(e) for e in edges_major]
chart.edges_minor = [tuple(e) for e in edges_minor]
chart.edges_harmonic = [tuple(e) for e in edges_harmonic]

# 4. Serialize
j = chart.to_json()
print(f"to_json: edges_harmonic has {len(j.get('edges_harmonic', []))} entries")

# 5. Deserialize
chart2 = AstrologicalChart.from_json(j)
print(f"from_json: edges_harmonic has {len(chart2.edges_harmonic)} entries")

# 6. Check edge format after roundtrip
if chart2.edges_harmonic:
    e = chart2.edges_harmonic[0]
    print(f"  Sample: {e[0]} - {e[1]}, meta type={type(e[2])}")
    if isinstance(e[2], dict):
        print(f"  Meta keys: {list(e[2].keys())}")
        print(f"  aspect={e[2].get('aspect')}")
    else:
        print(f"  *** NOT A DICT! Value: {e[2]}")
        print("  *** THIS IS THE BUG: filtering checks isinstance(e[2], dict)")

# 7. Check filter logic
enabled = {"Quintile", "Biquintile"}
_STANDARD_BASE = {
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "Black Moon Lilith (Mean)", "Chiron",
}
filtered = [
    e for e in chart2.edges_harmonic
    if e[0] in _STANDARD_BASE and e[1] in _STANDARD_BASE
    and (isinstance(e[2], dict) and e[2].get("aspect") in enabled)
]
print(f"\nWith toggles {enabled}: {len(filtered)} edges pass filter")
for e in filtered[:3]:
    print(f"  {e[0]} - {e[1]}: {e[2].get('aspect')} (orb={e[2].get('orb')})")

# 8. Check with empty toggles (should be 0)
enabled_empty = set()
filtered_empty = [
    e for e in chart2.edges_harmonic
    if e[0] in _STANDARD_BASE and e[1] in _STANDARD_BASE
    and (isinstance(e[2], dict) and e[2].get("aspect") in enabled_empty)
]
print(f"With empty toggles: {len(filtered_empty)} edges (should be 0)")
