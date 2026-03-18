import os, sys, json
os.environ['SE_EPHE_PATH'] = os.path.abspath('ephe').replace('\\','/')
import swisseph as swe
swe.set_ephe_path(os.environ['SE_EPHE_PATH'])
sys.path.insert(0, '.')

from calc_v2 import calculate_chart, build_aspect_edges
from patterns_v2 import prepare_pattern_inputs, detect_shapes, detect_minor_links_from_chart, generate_combo_groups

df, asp_df, plot_data, chart = calculate_chart(
    year=1990, month=7, day=1, hour=12, minute=0,
    tz_offset=0, lat=40.71, lon=-74.01, tz_name='America/New_York',
    house_system='placidus', include_aspects=True,
    display_name='Test', city='New York'
)
chart.df_positions = df
chart.aspect_df = asp_df
edges_major, edges_minor = build_aspect_edges(chart)
chart.edges_major = edges_major
chart.edges_minor = edges_minor
pos, patterns, major_edges_all = prepare_pattern_inputs(df, edges_major)
chart.aspect_groups = [sorted(list(s)) for s in patterns]
chart.positions = pos
chart.major_edges_all = major_edges_all
filaments, singleton_map = detect_minor_links_from_chart(chart, edges_major)
chart.filaments = filaments
chart.singleton_map = singleton_map
chart.combos = generate_combo_groups(filaments)

try:
    d = chart.to_json()
    s = json.dumps(d)
    print(f'SUCCESS: to_json() produced {len(s)} bytes = {len(s)//1024} KB')
    print(f'Keys: {list(d.keys())}')
    print(f'objects count: {len(d["objects"])}')
    print(f'edges_major count: {len(d["edges_major"])}')
    print(f'aspect_groups: {d["aspect_groups"]}')
    print(f'singleton_map sample: {list(d["singleton_map"].items())[:3]}')
except Exception as e:
    import traceback
    print('FAILED:')
    traceback.print_exc()
