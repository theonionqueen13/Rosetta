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
from lookup_v2 import ABREVIATED_PLANET_NAMES, _RECEPTION_ASPECTS, ASPECTS, ZODIAC_NUMBERS, ASPECTS_BY_SIGN, RECEPTION_SYMBOLS
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

# Helper function to get abbreviated name if available
def get_display_name(name):
    return ABREVIATED_PLANET_NAMES.get(name, name)

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

def render_dispositor_section(st, df_cached) -> None:
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
                disp_fig = plot_dispositor_graph(scope_data, planets_df=df_cached, header_info=header_info)
                st.pyplot(disp_fig, use_container_width=True)
        else:
            st.info("No dispositor graph to display.")
    else:
        st.info("Calculate a chart first.")



def setup_figure_layout(tree_widths, tree_heights, n, header_info):
    """
    Set up the figure layout dynamically based on tree dimensions and header information.

    Args:
        tree_widths: List of widths for each tree.
        tree_heights: List of heights for each tree.
        n: Number of trees.
        header_info: Optional header information for the figure.

    Returns:
        A Matplotlib figure and axes.
    """
    max_width = max(tree_widths) if tree_widths else 1
    width_ratios = [w / max_width for w in tree_widths]
    fig_width = 8 * n  # 8 inches per tree
    fig_height = 10    # Fixed height

    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = gridspec.GridSpec(1, n, figure=fig, width_ratios=width_ratios, wspace=0.15)
    axes = [fig.add_subplot(gs[0, i]) for i in range(n)]

    if header_info:
        plt.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.02, wspace=0.1)
        _draw_dispositor_header(fig, header_info)
    else:
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02, wspace=0.1)

    return fig, axes

# Define the base path for your icons
ICON_BASE_PATH = r"C:\Users\theon\OneDrive\Desktop\Rosetta\Rosetta_v2\pngs"

def get_base_name(node_id):
    """Cleans IDs like 'Saturn_1_0' or 'South_Node_0' into 'Saturn' or 'South_Node'."""
    return re.sub(r'(_\d+)+$', '', node_id)

def get_sign_aspect_name(p1_name, p2_name, planets_df):
    """Calculates if two planets are in signs that aspect each other using 'Object' column."""
    try:
        col = "Object" if "Object" in planets_df.columns else "object"
        search_p1 = p1_name.replace('_', ' ')
        search_p2 = p2_name.replace('_', ' ')

        row1 = planets_df.loc[planets_df[col] == search_p1]
        row2 = planets_df.loc[planets_df[col] == search_p2]

        if row1.empty or row2.empty:
            return None
            
        s1 = str(row1['Sign'].iloc[0]).strip().title()
        s2 = str(row2['Sign'].iloc[0]).strip().title()
        
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


def plot_dispositor_graph(plot_data, planets_df, header_info=None):
    # --- 0. DATA EXTRACTION ---
    raw_links = plot_data.get("raw_links", [])
    sovereigns = plot_data.get("sovereigns", [])
    self_ruling = plot_data.get("self_ruling", [])
    
    # 1. FIXED: Added path tracking to DFS to prevent infinite loops in rulership cycles
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
                if len(cycle) >= 2:
                    loop_members.update(cycle)
                return
            if node not in graph: return
            
            visited_in_path.add(node)
            path.append(node)
            for neighbor in graph[node]:
                # Using a copy of path/visited to branch correctly
                dfs_find_cycles(neighbor, list(path), set(visited_in_path))
        
        for node in list(graph.keys()):
            dfs_find_cycles(node, [], set())
        return loop_members

    rulership_loops = find_rulership_loops(raw_links)
    
    # --- 1. MAPPING & UTILS ---
    def get_display_name(name):
        return ABREVIATED_PLANET_NAMES.get(name, name)

    children_by_parent = {}
    for parent, child in raw_links:
        children_by_parent.setdefault(parent, []).append(child)

    parents_by_child = {}
    for parent, child in raw_links:
        parents_by_child.setdefault(child, []).append(parent)

    all_nodes = set(children_by_parent.keys())
    for v in children_by_parent.values():
        all_nodes.update(v)

    # --- 2. THE THREE PHASES (RETAINED EXACTLY AS YOURS) ---
    roots = []
    accounted_for = set()
    all_trees = []

    def find_root_by_following_parents(start_node):
        visited, path, current = set(), [], start_node
        while True:
            if current in visited:
                cycle_start_idx = path.index(current)
                cycle_nodes = path[cycle_start_idx:]
                return max(cycle_nodes, key=lambda n: len(children_by_parent.get(n, [])))
            visited.add(current)
            path.append(current)
            parents = [p for p in parents_by_child.get(current, []) if p != current]
            if not parents: return current
            current = parents[0]

    def collect_tree_downward(start_node):
        comp, q = set(), [start_node]
        while q:
            n = q.pop(0)
            if n not in comp:
                comp.add(n)
                q.extend(children_by_parent.get(n, []))
        return comp

    def collect_connected_component(start_node):
        neighbors = {}
        for p, c in raw_links:
            neighbors.setdefault(p, []).append(c)
            neighbors.setdefault(c, []).append(p)
        comp, q = set(), [start_node]
        while q:
            n = q.pop(0)
            if n not in comp:
                comp.add(n)
                q.extend(neighbors.get(n, []))
        return comp

    # Phase 1: Following Parents
    potential_roots = set()
    for node in all_nodes:
        potential_roots.add(find_root_by_following_parents(node))
    
    for root in sorted(potential_roots):
        if root not in accounted_for:
            tree_nodes = collect_tree_downward(root)
            all_trees.append(tree_nodes); accounted_for.update(tree_nodes); roots.append(root)

    # Phase 2: Self-Ruling (if not accounted for)
    sr_parents = sorted([s for s in self_ruling if s in children_by_parent and s not in accounted_for],
                        key=lambda s: (-len(children_by_parent.get(s, [])), s))
    for sr in sr_parents:
        tree_nodes = collect_tree_downward(sr)
        all_trees.append(tree_nodes); accounted_for.update(tree_nodes); roots.append(sr)

    # Phase 3: Fallback Components
    remaining = list(all_nodes - accounted_for)
    while remaining:
        start = remaining[0]
        full_comp = collect_connected_component(start)
        unaccounted = full_comp - accounted_for
        if not unaccounted:
            remaining.pop(0); continue
        best_root = sorted(unaccounted, key=lambda n: (0 if n in children_by_parent else 1, -len(children_by_parent.get(n, [])), n))[0]
        all_trees.append(unaccounted); accounted_for.update(unaccounted); roots.append(best_root)
        remaining = [n for n in remaining if n not in unaccounted]

    # --- 3. TREE DATA & POSITIONING ---
    all_tree_data = []
    processed_nodes = set()
    
    for tree_idx, root in enumerate(roots):
        if root in processed_nodes: continue
        tree_nodes = all_trees[tree_idx]
        for p_name in tree_nodes: processed_nodes.add(p_name)

        nodes, edges, level_nodes = [], [], {}
        queue = [(root, f"{root}_0", 0)]
        visited_ids, processed_pairs = {f"{root}_0"}, set()

        while queue:
            p_name, p_id, level = queue.pop(0)
            nodes.append((p_name, p_id))
            level_nodes.setdefault(level, []).append(p_id)
            
            # FIXED: Avoid circular references in tree building by checking 'level'
            for i, child in enumerate(children_by_parent.get(p_name, [])):
                if (p_name, child) in processed_pairs or level > 10: continue
                processed_pairs.add((p_name, child))
                c_id = f"{child}_{level+1}_{i}"
                edges.append((p_id, c_id))
                queue.append((child, c_id, level+1))

        if not nodes: continue

        # --- PYRAMID SANDWICH LOGIC (RETAINED) ---
        tree_edges_map = {}
        for p_id, c_id in edges: tree_edges_map.setdefault(p_id, []).append(c_id)

        def get_branch_weight(node_id):
            kids = tree_edges_map.get(node_id, [])
            return len(kids) + sum(get_branch_weight(k) for k in kids)

        def get_ordered_children(parent_id):
            children = tree_edges_map.get(parent_id, [])
            if not children: return []
            w_kids = sorted([(c, get_branch_weight(c)) for c in children], key=lambda x: x[1], reverse=True)
            heavy, light = [k[0] for k in w_kids if k[1] > 0], [k[0] for k in w_kids if k[1] == 0]
            if not heavy: return light
            ord_heavy = [None] * len(heavy)
            l, r = 0, len(heavy)-1
            for i, h in enumerate(heavy):
                if i % 2 == 0: ord_heavy[l] = h; l += 1
                else: ord_heavy[r] = h; r -= 1
            mid = len(ord_heavy) // 2
            return ord_heavy[:mid] + light + ord_heavy[mid:]

        pos, level_next_x = {}, {}
        def assign_pos_final(node_id, level):
            kids = get_ordered_children(node_id)
            
            if not kids:
                # Leaf placement
                x = level_next_x.get(level, 0.0)
                pos[node_id] = [x, -level * 5.0]
                level_next_x[level] = x + 1.2 
                return x, x 

            # 1. Position all children subtrees first
            # We still need the bounds to handle collisions correctly
            child_bounds = [assign_pos_final(k, level + 1) for k in kids]
            
            # 2. THE "GOOD CHANGE": Centering based on child circles, not bounds
            # This is what keeps Jupiter from leaning
            child_x_positions = [pos[k][0] for k in kids]
            ideal_x = (min(child_x_positions) + max(child_x_positions)) / 2.0
            
            # 3. COLLISION CHECK: Shift the parent AND the family if the spot is taken
            current_level_x = level_next_x.get(level, 0.0)
            if ideal_x < current_level_x:
                diff = current_level_x - ideal_x
                ideal_x += diff
                
                def shift_subtree(n_id, amount):
                    pos[n_id][0] += amount
                    for child in tree_edges_map.get(n_id, []):
                        shift_subtree(child, amount)
                
                for k in kids:
                    shift_subtree(k, diff)

            # 4. COMMIT POSITION
            pos[node_id] = [ideal_x, -level * 5.0]
            
            # 5. BOOKKEEPING
            level_next_x[level] = ideal_x + 1.2
            for l in range(level + 1, max(level_next_x.keys()) + 1):
                level_nodes = [p[0] for nid, p in pos.items() if int(abs(p[1])/5.0) == l]
                if level_nodes:
                    level_next_x[l] = max(level_next_x.get(l, 0.0), max(level_nodes) + 1.2)

            # Return the actual horizontal span of this subtree for the parent to use
            all_subtree_x = [p[0] for nid, p in pos.items() if nid == node_id or any(nid.startswith(k) for k in kids)]
            return min(all_subtree_x), max(all_subtree_x)

        assign_pos_final(f"{root}_0", 0)
        
        # Squeeze & Store
        min_x_val = min(p[0] for p in pos.values())
        for nid in pos: pos[nid][0] -= min_x_val
        all_tree_data.append({'root': root, 'nodes': nodes, 'edges': edges, 'pos': pos, 
                              'width': max(p[0] for p in pos.values()), 
                              'height': max(abs(p[1]) for p in pos.values())})

    # --- 4. RENDERING ---
    n = len(all_tree_data)
    if n == 0: return None

    # Count for Duplicates
    planet_occurrences = {}
    for td in all_tree_data:
        for name, _ in td['nodes']: planet_occurrences[name] = planet_occurrences.get(name, 0) + 1
    duplicated_planets = {name for name, count in planet_occurrences.items() if count > 1}

    fig_w = max(15, sum(td['width'] for td in all_tree_data) * 0.15)
    fig = plt.figure(figsize=(fig_w, 12))
    gs = gridspec.GridSpec(1, n, figure=fig, width_ratios=[max(0.1, td['width']) for td in all_tree_data], wspace=0.3)
    
    max_h = max(td['height'] for td in all_tree_data)
    edges_major = st.session_state.get('edges_major', [])
    png_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pngs")

    for i, td in enumerate(all_tree_data):
        ax = fig.add_subplot(gs[i])
        pos = td['pos']
        
        for name, nid in td['nodes']:
            xy = pos[nid]
            is_sov, is_dup, is_loop = name in sovereigns, name in duplicated_planets, name in rulership_loops
            
            if is_sov: ax.scatter(xy[0], xy[1], s=2300, c="#59A54A", zorder=2)
            elif is_dup and is_loop:
                ax.scatter(xy[0], xy[1], s=2300, c="#FF8656", zorder=2)
                ax.scatter(xy[0], xy[1], s=2300*0.6, c="#B386D8", zorder=3)
            elif is_dup: ax.scatter(xy[0], xy[1], s=2300, c="#FF8656", zorder=2)
            elif is_loop: ax.scatter(xy[0], xy[1], s=2300, c="#B386D8", zorder=2)
            else: ax.scatter(xy[0], xy[1], s=2300, c="#5F6FFF", zorder=2)
            
            ax.text(xy[0], xy[1], get_display_name(name), ha='center', va='center', fontsize=11, fontweight="bold", zorder=4)
            if name in self_ruling or name in sovereigns:
                ax.text(xy[0], xy[1]-0.08, "↻", ha='center', va='top', fontsize=16, zorder=3)

        # Edges & Aspect Icons
        for p_id, c_id in td['edges']:
            start, end = pos[p_id], pos[c_id]
            ax.annotate("", xy=end, xytext=start, arrowprops=dict(arrowstyle="-|>", color="black", lw=1.8), zorder=1)
            
            p_name, c_name = p_id.rsplit('_', 2)[0], c_id.rsplit('_', 2)[0]
            mid_x, mid_y = (start[0]+end[0])/2, (start[1]+end[1])/2
            
            # Logic for Orb/Sign Aspects (Simplified for brevity but kept your intent)
            aspect_meta = next((m for p, c, m in edges_major if (p==p_name and c==c_name) or (p==c_name and c==p_name)), None)
            icon_file = None
            if aspect_meta:
                icon_file = RECEPTION_SYMBOLS.get(aspect_meta.get("aspect"), {}).get("by orb")
            if not icon_file:
                sign_asp = get_sign_aspect_name(p_name, c_name, planets_df)
                icon_file = RECEPTION_SYMBOLS.get(sign_asp, {}).get("by sign")
            
            if icon_file:
                icon_path = os.path.join(png_dir, icon_file)
                if os.path.exists(icon_path):
                    img = plt.imread(icon_path)
                    ab = AnnotationBbox(OffsetImage(img, zoom=0.6), (mid_x, mid_y), frameon=False, zorder=10)
                    ax.add_artist(ab)

        ax.set_xlim(min(p[0] for p in pos.values())-0.5, max(p[0] for p in pos.values())+0.5)
        ax.set_ylim(-max_h - 1, 1)
        ax.axis("off")

    plt.subplots_adjust(left=0.02, right=0.98, top=0.94 if header_info else 0.98, bottom=0.02, wspace=0.1)
    if header_info: _draw_dispositor_header(fig, header_info)
    return fig