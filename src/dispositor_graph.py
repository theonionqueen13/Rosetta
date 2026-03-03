import os
import re
import base64
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import gridspec
from house_selector_v2 import render_house_system_selector
from drawing_v2 import _current_chart_header_lines
import matplotlib.patheffects as pe
from models_v2 import static_db

ABREVIATED_PLANET_NAMES = static_db.ABREVIATED_PLANET_NAMES
_RECEPTION_ASPECTS = static_db._RECEPTION_ASPECTS
ASPECTS = static_db.ASPECTS
ZODIAC_NUMBERS = static_db.ZODIAC_NUMBERS
ASPECTS_BY_SIGN = static_db.ASPECTS_BY_SIGN
RECEPTION_SYMBOLS = static_db.RECEPTION_SYMBOLS
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.patches import Rectangle, FancyBboxPatch  # use FancyBboxPatch for rounded corners


# Helper function to get abbreviated name if available
def get_display_name(name):
    return ABREVIATED_PLANET_NAMES.get(name, name)


def compute_house_map(chart, house_system: str) -> dict:
    """Return mapping object name -> house number for the given chart/system.

    ``house_system`` should be one of "placidus", "equal", or "whole"
    (case insensitive).  If no house information is available for an object,
    its value will be ``None``.  The chart is assumed to be an
    ``AstrologicalChart`` instance; this helper simply inspects the
    per-object house attributes created during calculation.
    """
    out = {}
    if chart is None:
        return out
    sys_lc = (house_system or "placidus").strip().lower()
    for obj in chart.objects:
        if not obj.object_name:
            continue
        name = obj.object_name.name
        if sys_lc == "placidus":
            hobj = getattr(obj, "placidus_house", None)
        elif sys_lc == "equal":
            hobj = getattr(obj, "equal_house", None)
        elif sys_lc == "whole":
            hobj = getattr(obj, "whole_sign_house", None)
        else:
            hobj = getattr(obj, "placidus_house", None)
        # store numeric house if possible
        out[name] = hobj.number if hasattr(hobj, "number") else None
    return out


def order_siblings(names, global_weights, house_map=None):
    """Return an ordering of ``names``.

    The behaviour mirrors the previous ``get_sandwich_order`` logic.  When
    ``house_map`` is provided (a dict of object->house number), siblings are
    grouped first by house (ascending, ``None`` last) and then each group is
    internally ordered according to weight buckets as before.  This allows the
    plotting code to place same-house siblings next to each other at the
    appropriate horizontal position.
    """
    if not names:
        return []

    # if no house_map or only one household, fall back to existing behaviour
    if house_map is None:
        # use original algorithm inline
        def _bucketed_order(ns):
            if len(ns) <= 2:
                return sorted(ns, key=lambda x: global_weights.get(x, 0), reverse=True)
            # compute buckets as before
            def get_bucket_score(name):
                w = global_weights.get(name, 0)
                if w >= 10: return 5
                if w >= 6:  return 4
                if w >= 4:  return 3
                if w >= 2:  return 2
                if w >= 1:  return 1
                return 0
            buckets = {i: [] for i in range(6)}
            for name in ns:
                buckets[get_bucket_score(name)].append(name)
            current_order = []
            for b_idx in range(5, -1, -1):
                if buckets[b_idx]:
                    current_order = sorted(buckets[b_idx], key=lambda x: global_weights.get(x, 0), reverse=True)
                    buckets[b_idx] = []
                    break
            for b_idx in range(5, -1, -1):
                to_place = buckets[b_idx]
                if not to_place: continue
                to_place = sorted(to_place, key=lambda x: global_weights.get(x, 0), reverse=True)
                num_gaps = len(current_order) - 1
                new_order = []
                if num_gaps <= 0:
                    mid = len(to_place) // 2
                    new_order = to_place[:mid] + current_order + to_place[mid:]
                else:
                    items_per_gap, extra = divmod(len(to_place), num_gaps)
                    l_idx = 0
                    for i in range(num_gaps):
                        new_order.append(current_order[i])
                        count = items_per_gap + (1 if i < extra else 0)
                        new_order.extend(to_place[l_idx : l_idx + count])
                        l_idx += count
                    new_order.append(current_order[-1])
                current_order = new_order
            return current_order
        return _bucketed_order(names)

    # group by house
    groups = {}
    none_group = []
    for name in names:
        h = house_map.get(name)
        if h is None:
            none_group.append(name)
        else:
            groups.setdefault(h, []).append(name)
    ordered = []
    for h in sorted(groups.keys()):
        ordered.extend(order_siblings(groups[h], global_weights, house_map=None))
    if none_group:
        ordered.extend(order_siblings(none_group, global_weights, house_map=None))
    return ordered


def _draw_dispositor_header(fig, header_info):
    """
    Draw a single-line header across the top of the dispositor graph.
    Format: Name | Date | Time | City
    """
    
    # Get header components
    name = header_info.get('name', 'Untitled Chart')
    date_line = header_info.get('date_line', '')
    time_line = header_info.get('time_line', '')
    city = header_info.get('city', '')
    extra_line = header_info.get('extra_line', '')
    
    # Build single line: Name | Date | Time | City
    # Handle unknown time format where date_line might be "AC = Aries 0° (default)"
    parts = [name]
    
    if date_line:
        parts.append(date_line)
    if time_line:
        parts.append(time_line)
    if city:
        parts.append(city)
    if extra_line:
        parts.append(extra_line)
    
    # Join with separator
    header_text = "  |  ".join(parts)
    
    # Draw centered at top
    color = "white"  # White text for dark background
    stroke = "black"
    effects = [pe.withStroke(linewidth=3, foreground=stroke, alpha=0.6)]
    
    fig.text(
        0.5, 0.98,  # Centered horizontally, near top
        header_text,
        ha="center", va="top",
        fontsize=11,
        color=color,
        path_effects=effects
    )

def render_dispositor_section(st, chart) -> None:
    """
    Renders the Dispositor Graph section in the Streamlit app.
    This includes the header, house system selector, scope toggle,
    and the dispositor graph itself with legend.
    """
    # Add anchor for jump button
    st.markdown('<div id="ruler-hierarchies"></div>', unsafe_allow_html=True)

    header_col, toggle_col, house_col = st.columns([2, 2, 1])

    with header_col:
        st.subheader("Ruler Hierarchies")

    with house_col:
        render_house_system_selector()

    with toggle_col:
        # House system selector (always render, but only relevant for "By House")
        # Dispositor scope toggle
        st.session_state.setdefault("dispositor_scope", "By Sign")
        disp_scope = st.radio(
            "Scope",
            ["By Sign", "By House"],
            horizontal=True,
            key="dispositor_scope",
            label_visibility="collapsed"
        )

    plot_data = st.session_state.get("DISPOSITOR_GRAPH_DATA")
    
    if plot_data is not None:
        # The rest of your logic now runs directly on the plot_data variable.
        
        disp_scope = st.session_state.get("dispositor_scope", "By Sign")
        
        # Determine which scope to use
        if disp_scope == "By Sign":
            scope_data = plot_data.get("by_sign")
        else:  # By House
            house_key_map = {
                "placidus": "Placidus",
                "equal": "Equal",
                "whole": "Whole Sign"
            }
            selected_house = st.session_state.get("house_system", "placidus")
            plot_data_key = house_key_map.get(selected_house, "Placidus")
            scope_data = plot_data.get(plot_data_key)

        if scope_data and scope_data.get("raw_links"):
            name, date_line, time_line, city, extra_line = _current_chart_header_lines()
            header_info = {
                'name': name,
                'date_line': date_line,
                'time_line': time_line,
                'city': city,
                'extra_line': extra_line
            }

            legend_col, graph_col = st.columns([1, 5])
                
            with legend_col:
                # Get the directory of the current file and point to pngs
                current_dir = os.path.dirname(__file__) 
                png_dir = os.path.abspath(os.path.join(current_dir, "..", "pngs"))

                # Load and encode images as base64
                def img_to_b64(filename):
                    path = os.path.join(png_dir, filename)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            return base64.b64encode(f.read()).decode()
                    return ""
                
                # Create legend header
                st.markdown("""
                    <div style="background-color: #262730; padding: 15px; border-radius: 8px;">
                        <strong style="color: white;">Legend</strong>
                    </div>
                """, unsafe_allow_html=True)
                
                # Updated list including the two new reception icons
                legend_items = [
                    ("green.png", "Sovereign"),
                    ("orange.png", "Dual rulership"),
                    ("purple.png", "Loop"),
                    ("purpleorange.png", "Dual + Loop"),
                    ("blue.png", "Standard"),
                    ("blue_reception.png", "Has reception (in orb)"),
                    ("green_reception.png", "Has reception by sign"),
                    ("conjunction.png", "Conjunction"),
                    ("sextile.png", "Sextile"),
                    ("square.png", "Square"),
                    ("trine.png", "Trine"),
                    ("opposition.png", "Opposition"),
                ]
                
                # Build the HTML
                legend_html = '<div style="background-color: #262730; padding: 15px; border-radius: 8px; margin-top: -15px;">'
                
                # 1. Move Self-Ruling to the very top
                legend_html += '<div style="color: white; margin-bottom: 12px; font-size: 0.9em; border-bottom: 1px solid #444; padding-bottom: 12px;">↻ Self-Ruling</div>'
                
                # 2. Iterate through the rest of the items
                for i, (img_file, label) in enumerate(legend_items):
                    # We adjusted the divider logic: 
                    # Since Self-Ruling is at the top, we now only need a divider before the aspect icons.
                    # In your list, the aspects/reception start at index 5 ("blue_reception.png")
                    margin_top = "margin-top: 12px; border-top: 1px solid #444; padding-top: 12px;" if i == 5 else ""
                    
                    b64 = img_to_b64(img_file)
                    if b64:
                        legend_html += f'''
                        <div style="margin-bottom: 8px; {margin_top}">
                            <img src="data:image/png;base64,{b64}" width="20" style="vertical-align:middle;margin-right:8px"/>
                            <span style="color: white; font-size: 0.9em;">{label}</span>
                        </div>'''
                
                legend_html += '</div>'
                
                st.markdown(legend_html, unsafe_allow_html=True)
                
            with graph_col:
                selected_house = st.session_state.get("house_system", "placidus")
                disp_fig = plot_dispositor_graph(
                    scope_data,
                    chart=chart,
                    header_info=header_info,
                    house_system=selected_house,
                )
                st.pyplot(disp_fig, use_container_width=True)
        else:
            st.info("No dispositor graph to display.")
    else:
        st.info("Calculate a chart first.")


# Define the base path for your icons
ICON_BASE_PATH = r"C:\Users\theon\OneDrive\Desktop\Rosetta\Rosetta_v2\pngs"

def get_base_name(node_id):
    """Cleans IDs like 'Saturn_1_0' or 'South_Node_0' into 'Saturn' or 'South_Node'."""
    return re.sub(r'(_\d+)+$', '', node_id)

def get_sign_aspect_name(p1_name, p2_name, chart):
    """Calculates if two planets are in signs that aspect each other using chart objects."""
    try:
        search_p1 = p1_name.replace('_', ' ')
        search_p2 = p2_name.replace('_', ' ')
        if chart is None:
            return None

        s1 = None
        s2 = None
        for obj in chart.objects:
            if not obj.object_name:
                continue
            if obj.object_name.name == search_p1:
                s1 = obj.sign.name if obj.sign else None
            if obj.object_name.name == search_p2:
                s2 = obj.sign.name if obj.sign else None

        if not s1 or not s2:
            return None
        
        # FIX: Convert the string values from ZODIAC_NUMBERS to integers
        n1 = int(ZODIAC_NUMBERS.get(s1, 0))
        n2 = int(ZODIAC_NUMBERS.get(s2, 0))
        
        if n1 == 0 or n2 == 0: 
            return None

        diff = abs(n1 - n2)
        if diff > 6: 
            diff = 12 - diff
        
        # Simple sign-distance to aspect name
        aspect_map = {0: "Conjunction", 2: "Sextile", 3: "Square", 4: "Trine", 6: "Opposition"}
        return aspect_map.get(diff)
    except Exception as e:
        # Debugging: if it still fails, this will show why in the terminal
        print(f"Error in sign aspect calc: {e}")
        return None

def plot_dispositor_graph(plot_data, chart, header_info=None, house_system=None):
    """Return a matplotlib figure containing the dispositor graph.

    ``house_system`` is one of "placidus","equal","whole" and is used both
    for ordering siblings by house and for the house‑number labels.  If
    omitted we fall back to the value stored in ``st.session_state``.
    """
    # --- 0. DATA EXTRACTION ---
    raw_links = plot_data.get("raw_links", [])
    sovereigns = plot_data.get("sovereigns", [])
    self_ruling = plot_data.get("self_ruling", [])

    # determine the house system from argument / session
    if house_system is None:
        house_system = st.session_state.get("house_system", "placidus")
    house_map = compute_house_map(chart, house_system)
    # debug info
    print(f"[DEBUG] plot_dispositor_graph called; house_system={house_system}, house_map_count={len(house_map)}")
    
    def find_rulership_loops(links):
        graph = {}
        for parent, child in links:
            if parent != child:
                graph.setdefault(parent, []).append(child)
        loop_members = set()
        def dfs_find_cycles(node, path, visited_in_path):
            if node in visited_in_path:
                idx = path.index(node)
                cycle = path[idx:]
                if len(cycle) >= 2: loop_members.update(cycle)
                return
            if node not in graph: return
            visited_in_path.add(node); path.append(node)
            for neighbor in graph[node]:
                dfs_find_cycles(neighbor, list(path), set(visited_in_path))
        for node in list(graph.keys()): dfs_find_cycles(node, [], set())
        return loop_members

    rulership_loops = find_rulership_loops(raw_links)
    
    children_by_parent = {}
    for parent, child in raw_links:
        children_by_parent.setdefault(parent, []).append(child)

    parents_by_child = {}
    for parent, child in raw_links:
        parents_by_child.setdefault(child, []).append(parent)

    all_nodes = set(children_by_parent.keys())
    for v in children_by_parent.values(): all_nodes.update(v)

    # --- 1. ROOT DETECTION (PHASED) ---
    roots, accounted_for, all_trees = [], set(), []

    def find_root_by_following_parents(start_node):
        visited, path, current = set(), [], start_node
        while True:
            if current in visited:
                idx = path.index(current)
                cycle = path[idx:]; return max(cycle, key=lambda n: len(children_by_parent.get(n, [])))
            visited.add(current); path.append(current)
            parents = [p for p in parents_by_child.get(current, []) if p != current]
            if not parents: return current
            current = parents[0]

    def collect_tree_downward(start_node):
        comp, q = set(), [start_node]
        while q:
            n = q.pop(0)
            if n not in comp:
                comp.add(n); q.extend(children_by_parent.get(n, []))
        return comp

    def collect_connected_component(start_node):
        neighbors = {}
        for p, c in raw_links:
            neighbors.setdefault(p, []).append(c); neighbors.setdefault(c, []).append(p)
        comp, q = set(), [start_node]
        while q:
            n = q.pop(0)
            if n not in comp:
                comp.add(n); q.extend(neighbors.get(n, []))
        return comp

    potential_roots = set(find_root_by_following_parents(n) for n in all_nodes)
    def root_priority_score(n):
        return (- (1 if n in sovereigns else 0), len(children_by_parent.get(n, [])), n)

    # Phase 1 & 2
    for r in sorted(potential_roots, key=root_priority_score):
        if r not in accounted_for:
            tree_nodes = collect_tree_downward(r)
            all_trees.append(tree_nodes); accounted_for.update(tree_nodes); roots.append(r)
    
    # Phase 3: Fallback
    remaining = list(all_nodes - accounted_for)
    while remaining:
        start = remaining[0]; full_comp = collect_connected_component(start)
        unaccounted = full_comp - accounted_for
        if not unaccounted: remaining.pop(0); continue
        best_r = sorted(unaccounted, key=root_priority_score)[0]
        all_trees.append(unaccounted); accounted_for.update(unaccounted); roots.append(best_r)
        remaining = [n for n in remaining if n not in unaccounted]

    # --- 2. POSITIONING & WEIGHTS ---
    # H_GAP defines the minimum horizontal separation (in data units) between
    # sibling nodes.  Later code will scale the entire layout if any pair of
    # nodes ends up closer than H_GAP, and the figure width computation is
    # designed to respect this spacing.  This makes H_GAP a hard limit that
    # cannot be violated by downstream scaling or rendering.
    H_GAP, V_GAP = 1.2, 5.0
    global_weights = {}
    def calc_weight(name, seen=None):
        if seen is None: seen = set()
        if name in seen: return 0
        seen.add(name); kids = children_by_parent.get(name, [])
        return len(kids) + sum(calc_weight(k, seen.copy()) for k in kids)
    for n in all_nodes: global_weights[n] = calc_weight(n)

    def get_sandwich_order(names):
        if len(names) <= 2: 
            return sorted(names, key=lambda x: global_weights.get(x, 0), reverse=True)

        # 1. Absolute Buckets
        def get_bucket_score(name):
            w = global_weights.get(name, 0)
            if w >= 10: return 5  # XXL
            if w >= 6:  return 4  # XL
            if w >= 4:  return 3  # L
            if w >= 2:  return 2  # M
            if w >= 1:  return 1  # S
            return 0              # Leaf

        buckets = {i: [] for i in range(6)}
        for name in names:
            buckets[get_bucket_score(name)].append(name)

        # 2. Start with the highest non-empty bucket
        current_order = []
        for b_idx in range(5, -1, -1):
            if buckets[b_idx]:
                current_order = sorted(buckets[b_idx], key=lambda x: global_weights.get(x, 0), reverse=True)
                buckets[b_idx] = []
                break
        
        # 3. Fill gaps with lower buckets
        for b_idx in range(5, -1, -1):
            to_place = buckets[b_idx]
            if not to_place: continue
            to_place = sorted(to_place, key=lambda x: global_weights.get(x, 0), reverse=True)
            
            num_gaps = len(current_order) - 1
            new_order = []
            if num_gaps <= 0:
                mid = len(to_place) // 2
                new_order = to_place[:mid] + current_order + to_place[mid:]
            else:
                items_per_gap, extra = divmod(len(to_place), num_gaps)
                l_idx = 0
                for i in range(num_gaps):
                    new_order.append(current_order[i])
                    count = items_per_gap + (1 if i < extra else 0)
                    new_order.extend(to_place[l_idx : l_idx + count])
                    l_idx += count
                new_order.append(current_order[-1])
            current_order = new_order
        return current_order

    all_tree_data, global_max_h = [], 0
    for tree_idx, root in enumerate(roots):
        nodes, edges, tree_edges_map = [], [], {}
        queue = [(root, f"{root}_0", 0)]
        processed_links = set()

        while queue:
            p_name, p_id, level = queue.pop(0)
            nodes.append((p_name, p_id))
            # THIS NOW CALLS THE CORRECT SANDWICH
            sandwiched_kids = order_siblings(children_by_parent.get(p_name, []), global_weights, house_map=house_map)

            for i, child in enumerate(sandwiched_kids):
                if (p_name, child) in processed_links or level > 12: continue
                processed_links.add((p_name, child))
                c_id = f"{child}_{level+1}_{i}_{p_name}"
                edges.append((p_id, c_id))
                tree_edges_map.setdefault(p_id, []).append(c_id)
                queue.append((child, c_id, level+1))

        pos, lvl_next_x = {}, {}
        def assign_pos(nid, lvl):
            kids = tree_edges_map.get(nid, [])
            if not kids:
                x = lvl_next_x.get(lvl, 0.0)
                pos[nid] = [x, -lvl * V_GAP]
                lvl_next_x[lvl] = x + H_GAP
                return x, x
            
            bounds = [assign_pos(k, lvl + 1) for k in kids]
            min_x, max_x = bounds[0][0], bounds[-1][1]
            ideal_x = (min_x + max_x) / 2.0
            
            curr_occ = lvl_next_x.get(lvl, 0.0)
            if ideal_x < curr_occ:
                shift = curr_occ - ideal_x
                ideal_x += shift
                def shift_recursive(target_id, amt):
                    pos[target_id][0] += amt
                    l = round(abs(pos[target_id][1]) / V_GAP)
                    lvl_next_x[l] = max(lvl_next_x.get(l, 0.0), pos[target_id][0] + H_GAP)
                    for c in tree_edges_map.get(target_id, []): shift_recursive(c, amt)
                for k in kids: shift_recursive(k, shift)
                min_x += shift; max_x += shift
            
            pos[nid] = [ideal_x, -lvl * V_GAP]
            lvl_next_x[lvl] = max(lvl_next_x.get(lvl, 0.0), ideal_x + H_GAP)
            return min_x, max_x

        assign_pos(f"{root}_0", 0)
		# 2. RE-CENTER THE ROOT (Parent Fix)
        # Find all direct children of the root
        root_id = f"{root}_0"
        root_kids = tree_edges_map.get(root_id, [])
        if root_kids:
            # Get the actual final X positions of the first and last child
            first_kid_x = pos[root_kids[0]][0]
            last_kid_x = pos[root_kids[-1]][0]
            
            # Snap parent to the exact midpoint of its children
            new_root_x = (first_kid_x + last_kid_x) / 2.0
            pos[root_id][0] = new_root_x
            
            # Update the level tracker to ensure the next tree doesn't overlap parent
            lvl_next_x[0] = max(lvl_next_x.get(0, 0.0), new_root_x + H_GAP)

        # 2b. REDISTRIBUTE CHILDLESS SIBLINGS IN GAPS
        # For each parent, find gaps between children that have their own children,
        # and evenly space the childless siblings within those gaps
        for parent_id, child_ids in tree_edges_map.items():
            if len(child_ids) < 2:
                continue
            
            # Identify which children have their own children (fixed-position)
            with_kids_indices = [i for i, cid in enumerate(child_ids) if tree_edges_map.get(cid)]
            
            # Process each gap between fixed-position siblings
            for gap_num in range(len(with_kids_indices) - 1):
                left_idx = with_kids_indices[gap_num]
                right_idx = with_kids_indices[gap_num + 1]
                
                # Find childless siblings in this gap
                gap_childless = [i for i in range(left_idx + 1, right_idx) 
                                if not tree_edges_map.get(child_ids[i])]
                
                if gap_childless:
                    left_x = pos[child_ids[left_idx]][0]
                    right_x = pos[child_ids[right_idx]][0]
                    
                    # Evenly space childless siblings across the gap
                    num_childless = len(gap_childless)
                    spacing = (right_x - left_x) / (num_childless + 1)
                    
                    for place_idx, sibling_idx in enumerate(gap_childless):
                        pos[child_ids[sibling_idx]][0] = left_x + spacing * (place_idx + 1)

        # 3. Normalize to 0 (Keep your existing normalization logic)
        min_x_val = min(p[0] for p in pos.values())
        for nid in pos: pos[nid][0] -= min_x_val
        
        h = max(abs(p[1]) for p in pos.values())
        global_max_h = max(global_max_h, h)
        # include H_GAP margin so house rectangles aren't clipped
        tree_width = max(p[0] for p in pos.values()) + H_GAP
        all_tree_data.append({
            'nodes': nodes, 'edges': edges, 'pos': pos, 
            'width': tree_width, 'height': h
        })
        
    # --- 3. RENDERING ---
    n = len(all_tree_data)
    if n == 0: return None

    # --- ENFORCE MINIMUM HORIZONTAL SPACING (per tree) ---
    # Earlier we attempted a global scale based on the smallest gap
    # across **all** trees.  That blew up when multiple independent trees
    # were present: a tight cluster in one tree forced the entire figure to
    # expand, leaving enormous white margins between otherwise normal trees.
    #
    # To fix this we perform the gap check on each tree individually and
    # only scale that tree if needed.  This keeps sibling spacing inside a
    # tree at least H_GAP without affecting neighbouring trees.

    for td in all_tree_data:
        local_min_dx = float("inf")
        # group x coordinates by level within this tree
        levels = {}
        for name, nid in td['nodes']:
            lvl = int(nid.split("_")[1])
            levels.setdefault(lvl, []).append(td['pos'][nid][0])
        for xs in levels.values():
            xs.sort()
            for a, b in zip(xs, xs[1:]):
                local_min_dx = min(local_min_dx, b - a)
        if local_min_dx < H_GAP and local_min_dx > 0:
            factor = H_GAP / local_min_dx
            for nid, xy in td['pos'].items():
                xy[0] *= factor
            td['width'] *= factor
    # note: global_max_h unaffected by horizontal scaling

    planet_counts = {}
    for td in all_tree_data:
        for name, _ in td['nodes']: planet_counts[name] = planet_counts.get(name, 0) + 1
    duplicated_planets = {name for name, count in planet_counts.items() if count > 1}

    # merge all trees into a single axis, offsetting each tree sequentially
    total_width = 0.0
    merged_nodes = []
    merged_edges = []
    merged_pos = {}
    for td in all_tree_data:
        # copy current tree positions with offset
        for nid, xy in td['pos'].items():
            merged_pos[nid] = [xy[0] + total_width, xy[1]]
        for name, nid in td['nodes']:
            merged_nodes.append((name, nid))
        for edge in td['edges']:
            merged_edges.append(edge)
        total_width += td['width'] + H_GAP  # insert a gap between trees
    # subtract last gap since we added one too many
    total_width = max(0.0, total_width - H_GAP)

    fig_w = max(15, total_width)
    fig = plt.figure(figsize=(fig_w, 12))
    ax = fig.add_subplot(1, 1, 1)

    # determine marker size so that the rendered circles never shrink to an
    # unreadable size when the figure is later squashed by streamlit.
    # ``s`` passed to scatter is in points^2; a figure that is much wider than
    # the minimum baseline (15 inches) will typically be downscaled by the
    # container, causing markers to appear smaller.  By enlarging the area
    # proportionally to ``fig_w`` we keep a roughly constant pixel footprint.
    # This also gives us a universal *minimum* display size, because when
    # ``fig_w`` is at the baseline the scale factor is 1.0.
    base_marker = 3500
    scale_factor = fig_w / 18.0
    marker_s = base_marker * scale_factor
    # also compute font sizes based on the same scale factor so labels grow
    base_font = 11
    base_symbol_font = 14
    font_size = base_font * scale_factor
    symbol_font_size = base_symbol_font * scale_factor
    # house label text likewise should scale
    house_font_size = base_symbol_font * scale_factor * 1.1

    edges_major = st.session_state.get('edges_major', [])
    png_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pngs")

    # collect x extents for each (house, level, parent) combination using merged data
    # the extra parent component ensures rectangles never span across distinct
    # family units even when multiple objects share the same house/level.
    house_groups = {}
    for name, nid in merged_nodes:
        house = house_map.get(name)
        lvl = int(nid.split('_')[1])
        # last segment of nid is parent identifier for non-root nodes
        parent = nid.split('_')[-1] if '_' in nid else None
        x = merged_pos[nid][0]
        house_groups.setdefault((house, lvl, parent), []).append(x)
    if not house_groups:
        for name, nid in merged_nodes:
            lvl = int(nid.split('_')[1])
            parent = nid.split('_')[-1] if '_' in nid else None
            x = merged_pos[nid][0]
            house_groups.setdefault((None, lvl, parent), []).append(x)

    # draw edges first
    for p_id, c_id in merged_edges:
        start, end = merged_pos[p_id], merged_pos[c_id]
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", color="black", lw=1.8), zorder=1)
        p_name, c_name = p_id.split('_')[0], c_id.split('_')[0]
        mid_x, mid_y = (start[0]+end[0])/2, (start[1]+end[1])/2
        asp_meta = next((m for p,c,m in edges_major if (p==p_name and c==c_name) or (p==c_name and c==p_name)), None)
        icon_file = RECEPTION_SYMBOLS.get(asp_meta.get("aspect"), {}).get("by orb") if asp_meta else RECEPTION_SYMBOLS.get(get_sign_aspect_name(p_name, c_name, chart), {}).get("by sign")
        if icon_file and os.path.exists(os.path.join(png_dir, icon_file)):
            img = plt.imread(os.path.join(png_dir, icon_file))
            ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=0.6), (mid_x, mid_y), frameon=False, zorder=10))

    # draw the house rectangles; keys now include parent to keep units separate
    for (house, lvl, parent), xs in house_groups.items():
        xmin, xmax = min(xs), max(xs)
        pad = H_GAP / 2.0
        width = (xmax - xmin) + pad
        cx = (xmin + xmax) / 2.0
        cy = -lvl * V_GAP
        rect_height = V_GAP * 0.75
        rect_y = cy - rect_height / 2.0 + V_GAP * 0.1
        ax.add_patch(FancyBboxPatch(
            (xmin - pad/2.0, rect_y),
            width,
            rect_height,
            boxstyle="round,pad=0,rounding_size=0.1",
            facecolor="#fd8e8e",
            edgecolor="#ff5656",
            linewidth=1.5,
            alpha=0.6,
            zorder=0,
        ))
        if house is not None:
            label_y = cy + rect_height/2.0 - rect_height*0.15
            ax.text(cx, label_y, f"{house}H",
                    ha='center', va='bottom', fontsize=house_font_size, fontweight="bold",
                    path_effects=[pe.withStroke(linewidth=2, foreground="white")],
                    zorder=100)

    # draw planets & labels
    for name, nid in merged_nodes:
        xy = merged_pos[nid]
        is_sov, is_dup, is_loop = name in sovereigns, name in duplicated_planets, name in rulership_loops
        if is_sov:
            ax.scatter(xy[0], xy[1], s=marker_s, c="#59A54A", zorder=2)
        elif is_dup and is_loop:
            ax.scatter(xy[0], xy[1], s=marker_s, c="#FF8656", zorder=2)
            ax.scatter(xy[0], xy[1], s=marker_s * 0.6, c="#B386D8", zorder=3)
        elif is_dup:
            ax.scatter(xy[0], xy[1], s=marker_s, c="#FF8656", zorder=2)
        elif is_loop:
            ax.scatter(xy[0], xy[1], s=marker_s, c="#B386D8", zorder=2)
        else:
            ax.scatter(xy[0], xy[1], s=marker_s, c="#5F6FFF", zorder=2)

        ax.text(xy[0], xy[1], ABREVIATED_PLANET_NAMES.get(name, name), ha='center', va='center', fontsize=font_size, fontweight="bold", zorder=4)
        if name in self_ruling or name in sovereigns:
            ax.text(xy[0], xy[1]-0.08, "↻", ha='center', va='top', fontsize=symbol_font_size, zorder=3)

    # redraw edges over planets for icon placement (same as before)
    for p_id, c_id in merged_edges:
        start, end = merged_pos[p_id], merged_pos[c_id]
        ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", color="black", lw=1.8), zorder=1)
        p_name, c_name = p_id.split('_')[0], c_id.split('_')[0]
        mid_x, mid_y = (start[0]+end[0])/2, (start[1]+end[1])/2
        asp_meta = next((m for p,c,m in edges_major if (p==p_name and c==c_name) or (p==c_name and c==p_name)), None)
        icon_file = RECEPTION_SYMBOLS.get(asp_meta.get("aspect"), {}).get("by orb") if asp_meta else RECEPTION_SYMBOLS.get(get_sign_aspect_name(p_name, c_name, chart), {}).get("by sign")
        if icon_file and os.path.exists(os.path.join(png_dir, icon_file)):
            img = plt.imread(os.path.join(png_dir, icon_file))
            ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=0.6), (mid_x, mid_y), frameon=False, zorder=10))

    ax.set_xlim(-1.0, total_width + 1.0 + H_GAP)
    ax.set_ylim(-global_max_h - 2.5, 2.5)
    ax.axis("off")

    plt.subplots_adjust(left=0.02, right=0.98, top=0.92 if header_info else 0.98, bottom=0.05)
    if header_info: _draw_dispositor_header(fig, header_info)
    return fig