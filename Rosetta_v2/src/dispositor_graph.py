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

def determine_node_color(node, duplicated_planets, rulership_loops, sovereigns):
    """
    Determine the color of a node based on its properties.

    Args:
        node: The node to determine the color for.
        duplicated_planets: Set of planets that appear multiple times.
        rulership_loops: Set of planets in rulership loops.
        sovereigns: List of sovereign planets.

    Returns:
        The color of the node.
    """
    if node in sovereigns:
        return "#59A54A"
    elif node in duplicated_planets and node in rulership_loops:
        return "#FF8656"  # Dual rulership + Loop
    elif node in duplicated_planets:
        return "#FF8656"  # Dual rulership
    elif node in rulership_loops:
        return "#B386D8"  # Loop
    else:
        return "#5F6FFF"  # Standard

def calculate_dynamic_scaling(tree_node_counts):
    """
    Calculate dynamic scaling factors for tree spacing and node sizes based on node counts.

    Args:
        tree_node_counts: List of node counts for each tree.

    Returns:
        A list of dictionaries containing scaling factors for spacing, font sizes, and circle sizes.
    """
    max_nodes = max(tree_node_counts) if tree_node_counts else 1
    scaling_factors = []

    for num_nodes in tree_node_counts:
        raw_scale = num_nodes / max_nodes
        scale_factor = 0.85 + (0.15 * raw_scale)  # Scale ranges from 0.85 to 1.0

        if num_nodes <= 5:
            label_fontsize = 9
            symbol_fontsize = 12
            circle_size = 2000
        elif num_nodes <= 15:
            label_fontsize = 11
            symbol_fontsize = 13
            circle_size = 2000
        elif num_nodes <= 20:
            label_fontsize = 12
            symbol_fontsize = 14
            circle_size = 3000
        elif num_nodes <= 25:
            label_fontsize = 11
            symbol_fontsize = 13
            circle_size = 3000
        else:
            label_fontsize = 8
            symbol_fontsize = 10
            circle_size = 900

        scaling_factors.append({
            "label_fontsize": label_fontsize,
            "symbol_fontsize": symbol_fontsize,
            "circle_size": circle_size,
        })

    return scaling_factors

# Helper function to collect all nodes connected to a given node
def collect_connected_component(start_node, raw_links):
    """Collect all nodes connected to start_node (both upward and downward in the graph)."""
    neighbors = {}
    for parent, child in raw_links:
        neighbors.setdefault(parent, []).append(child)
        neighbors.setdefault(child, []).append(parent)

    component = set()
    queue = [start_node]
    while queue:
        n = queue.pop(0)
        if n in component:
            continue
        component.add(n)
        queue.extend(neighbors.get(n, []))
    return component

# Helper function to collect all nodes reachable downward from a start node
def collect_tree_downward(start_node, children_by_parent):
    """Collect all nodes reachable downward from start_node."""
    component = set()
    queue = [start_node]
    while queue:
        n = queue.pop(0)
        if n in component:
            continue
        component.add(n)
        queue.extend(children_by_parent.get(n, []))
    return component

# Helper function to find the root of a tree by following parents upward
def find_root_by_following_parents(start_node, parents_by_child, children_by_parent):
    """Follow parents upward until hitting a self-ruling node or cycle. Returns the root node."""
    visited = set()
    current = start_node
    path = []

    while True:
        if current in visited:
            cycle_start_idx = path.index(current)
            cycle_nodes = path[cycle_start_idx:]
            best = max(cycle_nodes, key=lambda n: len(children_by_parent.get(n, [])))
            return best

        visited.add(current)
        path.append(current)

        parents = parents_by_child.get(current, [])
        parents = [p for p in parents if p != current]

        if not parents:
            return current

        current = parents[0]

# Helper function to build parent and child mappings
def build_parent_child_mappings(raw_links):
    """Build mappings for children by parent and parents by child."""
    # Convert raw_links to a lookup for children by parent (preserve order)
    children_by_parent = {}
    for parent, child in raw_links:
        children_by_parent.setdefault(parent, []).append(child)

    # Build parent lookup (child -> parents)
    parents_by_child = {}
    for parent, child in raw_links:
        parents_by_child.setdefault(child, []).append(parent)

    return children_by_parent, parents_by_child

# Helper function to detect duplicated planets
def detect_duplicated_planets(all_tree_data):
    """Count planet occurrences across all trees to detect duplicates."""
    planet_occurrences = {}
    for tree_data in all_tree_data:
        for name, node_id in tree_data['nodes']:
            planet_occurrences[name] = planet_occurrences.get(name, 0) + 1

    duplicated_planets = {name for name, count in planet_occurrences.items() if count > 1}
    return duplicated_planets

# Function to build self-ruling trees
def build_self_ruling_trees(self_ruling, children_by_parent, accounted_for, all_trees, roots):
    """
    Build trees for self-ruling planets that are not yet accounted for.

    Args:
        self_ruling: List of self-ruling planets.
        children_by_parent: Mapping of parent nodes to their children.
        accounted_for: Set of nodes already included in trees.
        all_trees: List to store all trees.
        roots: List to store root nodes of trees.
    """
    self_ruling_parents = [s for s in self_ruling 
                           if s in children_by_parent 
                           and len(children_by_parent.get(s, [])) > 0
                           and s not in accounted_for]

    # Sort self-ruling by most children (most dominant), then alphabetically
    self_ruling_parents.sort(key=lambda s: (-len(children_by_parent.get(s, [])), s))

    for sr in self_ruling_parents:
        # Check if this self-ruling planet is already in any existing tree
        if any(sr in tree for tree in all_trees):
            continue

        tree_nodes = collect_tree_downward(sr, children_by_parent)
        all_trees.append(tree_nodes)
        accounted_for.update(tree_nodes)
        roots.append(sr)

def handle_unaccounted_nodes(all_nodes, accounted_for, children_by_parent, all_trees, roots):
    """
    Handle any remaining unaccounted nodes by grouping them into connected components.

    Args:
        all_nodes: Set of all nodes in the graph.
        accounted_for: Set of nodes already included in trees.
        children_by_parent: Mapping of parent nodes to their children.
        all_trees: List to store all trees.
        roots: List to store root nodes of trees.
    """
    remaining_nodes = list(all_nodes - accounted_for)

    while remaining_nodes:
        # Pick the first unprocessed node as a starting point
        start_node = remaining_nodes[0]

        # Find all nodes connected to this one (bidirectionally)
        full_component = collect_connected_component(start_node, children_by_parent)

        # Filter to only unaccounted nodes
        component_unaccounted = full_component - accounted_for

        if not component_unaccounted:
            remaining_nodes.pop(0)
            continue

        # Choose the best root for this component
        candidates = sorted(
            component_unaccounted,
            key=lambda n: (
                0 if n in children_by_parent and len(children_by_parent.get(n, [])) > 0 else 1,
                -len(children_by_parent.get(n, [])),
                n
            )
        )

        best_root = candidates[0]
        all_trees.append(component_unaccounted)
        accounted_for.update(component_unaccounted)
        roots.append(best_root)

        # Remove all nodes in this component from remaining_nodes
        remaining_nodes = [n for n in remaining_nodes if n not in component_unaccounted]

def validate_all_nodes_accounted(all_nodes, accounted_for, all_trees, roots):
    """
    Ensure all nodes are accounted for and add any missing nodes as individual trees.

    Args:
        all_nodes: Set of all nodes in the graph.
        accounted_for: Set of nodes already included in trees.
        all_trees: List to store all trees.
        roots: List to store root nodes of trees.
    """
    missing_nodes = all_nodes - accounted_for
    if missing_nodes:
        for node in sorted(missing_nodes):
            roots.append(node)
            all_trees.append({node})
            accounted_for.add(node)

def position_tree_nodes(tree_edges, level_nodes, min_spacing, vertical_gap):
    """
    Position nodes within a tree, ensuring proper layout and avoiding overlaps.

    Args:
        tree_edges: Mapping of parent nodes to their children.
        level_nodes: Mapping of levels to lists of node IDs.
        min_spacing: Minimum horizontal spacing between nodes.
        vertical_gap: Vertical gap between levels.

    Returns:
        A dictionary mapping node IDs to their (x, y) positions.
    """
    pos = {}
    next_x_by_level = {}  # Track next available x position per level
    visited = set()  # Track visited nodes to prevent cycles

    def position_subtree(node_id):
        """Position a node and its descendants."""
        visited.add(node_id)

        level = next((lev for lev, ids in level_nodes.items() if node_id in ids), None)

        children = tree_edges.get(node_id, [])

        # Deduplicate children to avoid redundant processing
        children = list(set(children))

        if not children:
            # Leaf node: place at next available position
            x = next_x_by_level.get(level, 0.0)
            pos[node_id] = (x, -level * vertical_gap)
            next_x_by_level[level] = x + min_spacing
            return x
        else:
            # Internal node: position children one by one
            child_positions = [position_subtree(child) for child in children]
            x = sum(child_positions) / len(child_positions)  # Center over children
            pos[node_id] = (x, -level * vertical_gap)
            next_x_by_level[level] = max(next_x_by_level.get(level, 0.0), x + min_spacing)
            return x

    # Start positioning from the root node
    root_id = next(iter(level_nodes.get(0, [])), None)
    position_subtree(root_id)

    # Fallback for any nodes not positioned
    all_nodes = set(node for nodes in level_nodes.values() for node in nodes)
    unpositioned_nodes = all_nodes - set(pos.keys())
    if unpositioned_nodes:
        for node in unpositioned_nodes:
            # Assign default positions for unpositioned nodes
            level = next((lev for lev, ids in level_nodes.items() if node in ids), 0)
            x = next_x_by_level.get(level, 0.0)
            pos[node] = (x, -level * vertical_gap)
            next_x_by_level[level] = x + min_spacing

    return pos

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
    """
    Plot dispositor trees in a vertical family-tree style.

    Rules:
    - Sovereign planets are roots of their own trees.
    - Each generation (distance from root) is a horizontal layer.
    - A planet may appear multiple times under different rulers if dual-ruled.
    - Never repeat the same parent->child edge.
    
    Args:
        plot_data: Dispositor data structure with raw_links, sovereigns, self_ruling
        edges_major: reception aspects for edges
        header_info: Optional dict with keys: name, date_line, time_line, city, extra_line
    """

    raw_links = plot_data.get("raw_links", [])
    sovereigns = plot_data.get("sovereigns", [])
    self_ruling = plot_data.get("self_ruling", [])
    
    # Detect rulership loops (2+ planets in a rulership cycle)
    def find_rulership_loops(links):
        """Find all planets involved in rulership loops of 2 or more."""
        # Build adjacency list
        graph = {}
        for parent, child in links:
            if parent != child:  # Exclude self-ruling
                graph.setdefault(parent, []).append(child)
        
        # Find all cycles using DFS
        loop_members = set()
        
        def dfs_find_cycles(node, path, visited_in_path):
            if node in visited_in_path:
                # Found a cycle - add all nodes from cycle start to current
                cycle_start_idx = path.index(node)
                cycle = path[cycle_start_idx:]
                if len(cycle) >= 2:  # Only loops of 2+
                    loop_members.update(cycle)
                return
            
            if node not in graph:
                return
            
            visited_in_path.add(node)
            path.append(node)
            
            for neighbor in graph[node]:
                dfs_find_cycles(neighbor, path[:], visited_in_path.copy())
        
        # Start DFS from each node
        for node in graph:
            dfs_find_cycles(node, [], set())
        
        return loop_members
    
    rulership_loops = find_rulership_loops(raw_links)
    
    # Detect planets that appear multiple times (dual rulership)
    # We'll count occurrences as we build the trees, then identify duplicates
    planet_occurrences = {}  # planet_name -> count
    
    # Helper function to get abbreviated name if available
    def get_display_name(name):
        return ABREVIATED_PLANET_NAMES.get(name, name)

    # Convert raw_links to a lookup for children by parent (preserve order)
    children_by_parent = {}
    for parent, child in raw_links:
        children_by_parent.setdefault(parent, []).append(child)

    # Build parent lookup (child -> parents)
    parents_by_child = {}
    for parent, child in raw_links:
        parents_by_child.setdefault(child, []).append(parent)

    # Track edges drawn globally so each parent->child is drawn once
    drawn_edges = set()

    # Create figure (one column per sovereign)
    # --- Determine roots dynamically using a phased approach ---
    all_nodes = set(children_by_parent.keys())
    for v in children_by_parent.values():
        all_nodes.update(v)

    roots = []
    accounted_for = set()  # Track all nodes already included in a tree
    all_trees = []  # Track the actual node sets for each tree

    def find_root_by_following_parents(start_node):
        """Follow parents upward until hitting a self-ruling node or cycle. Returns the root node."""
        visited = set()
        current = start_node
        path = []
        
        while True:
            if current in visited:
                # Hit a cycle - return the node with most children in the cycle
                cycle_start_idx = path.index(current)
                cycle_nodes = path[cycle_start_idx:]
                # Pick the node in the cycle with the most children
                best = max(cycle_nodes, key=lambda n: len(children_by_parent.get(n, [])))
                return best
            
            visited.add(current)
            path.append(current)
            
            # Get parents (rulers) of current node
            parents = parents_by_child.get(current, [])
            
            # Filter out self-loops
            parents = [p for p in parents if p != current]
            
            if not parents:
                # No parents - this is a self-ruling node or true root
                return current
            
            # Continue following the first parent
            current = parents[0]

    def collect_tree_downward(start_node):
        """Collect all nodes reachable downward from start_node."""
        component = set()
        queue = [start_node]
        while queue:
            n = queue.pop(0)
            if n in component:
                continue
            component.add(n)
            queue.extend(children_by_parent.get(n, []))
        return component
    
    def collect_connected_component(start_node):
        """Collect all nodes connected to start_node (both upward and downward in the graph)."""
        # Build a bidirectional graph from parent->child relationships
        neighbors = {}
        for parent, child in raw_links:
            neighbors.setdefault(parent, []).append(child)
            neighbors.setdefault(child, []).append(parent)
        
        # BFS to find all connected nodes
        component = set()
        queue = [start_node]
        while queue:
            n = queue.pop(0)
            if n in component:
                continue
            component.add(n)
            queue.extend(neighbors.get(n, []))
        return component

    # === PHASE 1: Find roots by following parents upward from all nodes ===
    potential_roots = set()
    for node in all_nodes:
        root = find_root_by_following_parents(node)
        potential_roots.add(root)
    
    # For each root, collect its full tree using DOWNWARD traversal only (not bidirectional)
    for root in sorted(potential_roots):
        if root in accounted_for:
            continue
        
        tree_nodes = collect_tree_downward(root)
        all_trees.append(tree_nodes)
        accounted_for.update(tree_nodes)
        roots.append(root)

    # === OLD PHASE 1: Sovereign trees ===
    sovereign_parents = [s for s in sovereigns if s in children_by_parent and len(children_by_parent.get(s, [])) > 0]
    
    # Sort sovereigns by most children (most dominant first)
    sovereign_parents.sort(key=lambda s: (-len(children_by_parent.get(s, [])), s))
    
    for sov in sovereign_parents:        
        tree_nodes = collect_tree_downward(sov)
        all_trees.append(tree_nodes)
        accounted_for.update(tree_nodes)
        roots.append(sov)

    # === PHASE 2: Self-ruling trees (not yet accounted for) ===
    self_ruling_parents = [s for s in self_ruling 
                           if s in children_by_parent 
                           and len(children_by_parent.get(s, [])) > 0
                           and s not in accounted_for]
    
    # Sort self-ruling by most children (most dominant), then alphabetical
    self_ruling_parents.sort(key=lambda s: (-len(children_by_parent.get(s, [])), s))
    
    for sr in self_ruling_parents:
        tree_nodes = collect_tree_downward(sr)
        all_trees.append(tree_nodes)
        accounted_for.update(tree_nodes)
        roots.append(sr)

    # === PHASE 3: Fallback for any remaining unaccounted nodes ===
    remaining_nodes = list(all_nodes - accounted_for)
    
    
    # Group remaining nodes into connected components
    processed_in_phase3 = set()
    
    while remaining_nodes:
        # Pick the first unprocessed node as a starting point
        start_node = remaining_nodes[0]
        
        if start_node in processed_in_phase3:
            remaining_nodes.pop(0)
            continue
        
        # Find ALL nodes connected to this one (bidirectionally), not just unaccounted ones
        full_component = collect_connected_component(start_node)
        
        # Filter to only unaccounted nodes
        component_unaccounted = full_component - accounted_for
        
        if not component_unaccounted:
            remaining_nodes.pop(0)
            continue
        
        
        # Choose the best root for this component from the unaccounted nodes:
        # 1. Prefer nodes with children (parents) over childless nodes
        # 2. Among parents, prefer those with most children
        # 3. Tie-break alphabetically
        candidates = sorted(
            component_unaccounted,
            key=lambda n: (
                0 if n in children_by_parent and len(children_by_parent.get(n, [])) > 0 else 1,
                -len(children_by_parent.get(n, [])),
                n
            )
        )
        
        best_root = candidates[0]
        
        # Store this tree with ALL unaccounted nodes in the component
        all_trees.append(component_unaccounted)
        accounted_for.update(component_unaccounted)
        roots.append(best_root)
        
        # Remove all nodes in this component from remaining_nodes
        remaining_nodes = [n for n in remaining_nodes if n not in component_unaccounted]


    # === VALIDATION: Ensure all nodes are accounted for ===
    missing_nodes = all_nodes - accounted_for
    if missing_nodes:
        for node in sorted(missing_nodes):
            roots.append(node)
            all_trees.append({node})
            accounted_for.add(node)
    else:
        print(f"\n✅ All {len(all_nodes)} nodes accounted for in {len(roots)} tree(s)")

    n = len(roots)
    
    # PHASE 0: Count nodes in each tree to calculate scaling factors
    tree_node_counts = []
    for tree_idx, root in enumerate(roots):
        tree_nodes = all_trees[tree_idx]
        tree_node_counts.append(len(tree_nodes))
    
    max_nodes = max(tree_node_counts) if tree_node_counts else 1
    
    # PHASE 1: Position all trees and calculate their extents
    all_tree_data = []
    
    for tree_idx, root in enumerate(roots):
        # Get the set of nodes that should be in this tree
        tree_nodes = all_trees[tree_idx]
        
        # Build a parent->children map ONLY for nodes in this tree
        tree_children_map = {}
        for parent, child in raw_links:
            if parent in tree_nodes and child in tree_nodes:
                tree_children_map.setdefault(parent, []).append(child)
        
        # Also build a reverse map (child->parents) to handle rulership
        tree_parents_map = {}
        for parent, child in raw_links:
            if parent in tree_nodes and child in tree_nodes:
                tree_parents_map.setdefault(child, []).append(parent)
        
        nodes = []          # list of tuples (name, node_id)
        edges = []          # list of tuples (parent_id, child_id)
        level_nodes = {}    # level -> ordered list of node_ids (no duplicates)
        queue = [(root, f"{root}_0", 0)]  # (name, unique_id, level)

        visited_names = set([root])  # track which planet NAMES we've added
        visited_ids = set([f"{root}_0"])  # track unique node IDs to prevent infinite loops
        processed_pairs = set()  # track (parent_name, child_name) pairs to prevent reprocessing

        while queue:
            parent_name, parent_id, level = queue.pop(0)

            nodes.append((parent_name, parent_id))
            level_nodes.setdefault(level, [])
            if parent_id not in level_nodes[level]:
                level_nodes[level].append(parent_id)

            # Process children (downward edges)
            children = tree_children_map.get(parent_name, [])
            for i, child in enumerate(children):
                # Skip if we've already processed this parent->child relationship
                if (parent_name, child) in processed_pairs:
                    continue
                processed_pairs.add((parent_name, child))
                
                child_id = f"{child}_{level+1}_{i}"

                # Prevent infinite recursion while still allowing repeats at different levels
                if child_id in visited_ids:
                    continue
                visited_ids.add(child_id)
                visited_names.add(child)

                edges.append((parent_id, child_id))
                queue.append((child, child_id, level+1))
                level_nodes.setdefault(level+1, [])
                if child_id not in level_nodes[level+1]:
                    level_nodes[level+1].append(child_id)

        if not nodes:
            continue

        # Circle label, icon and font sizes
        label_fontsize = 11
        symbol_fontsize = 16
        circle_size = 2300
        icon_zoom = 0.60        
        
        # Build parent->children map for this tree
        tree_edges = {}
        for parent_id, child_id in edges:
            tree_edges.setdefault(parent_id, []).append(child_id)
            
        # --- COLUMN-BASED POSITIONING (NO OVERLAP + BOOKEND RULE) ---

        # 1. Build parent->children map
        tree_edges = {}
        for parent_id, child_id in edges:
            tree_edges.setdefault(parent_id, []).append(child_id)
            
        # 2. CONFIGURATION
        H_GAP = 1.0  # Since we are level-aware, we can go back to a normal number
        V_GAP = 5.0 

        def get_branch_weight(node_id):
            """Helper to count how many descendants a planet has."""
            kids = tree_edges.get(node_id, [])
            count = len(kids)
            for k in kids:
                count += get_branch_weight(k)
            return count

        def get_ordered_children(parent_id):
            children = tree_edges.get(parent_id, [])
            if not children: return []
            
            # 1. Categorize children by family size
            # We'll store them as tuples: (node_id, weight)
            weighted_kids = [(c, get_branch_weight(c)) for c in children]
            
            # Sort by weight descending (biggest families first)
            weighted_kids.sort(key=lambda x: x[1], reverse=True)
            
            # 2. Separate them into "Heavy Families" and "Light/Leaf"
            # We'll consider any branch with more than 1 descendant a "Heavy Family"
            heavy = [k[0] for k in weighted_kids if k[1] > 1]
            light = [k[0] for k in weighted_kids if k[1] <= 1]

            # 3. THE "SANDWICH" RULE
            # Place the heaviest families on the ends, and tuck the lighter ones in the gaps.
            if len(heavy) < 2:
                # If there's only one big family, put it in the middle of the leaves
                mid = len(light) // 2
                return light[:mid] + heavy + light[mid:]

            # If we have multiple big families, distribute leaves/small families between them
            num_gaps = len(heavy) - 1
            distributed_list = []
            light_per_gap = len(light) // num_gaps
            extra_light = len(light) % num_gaps
            light_idx = 0
            
            for i in range(num_gaps):
                distributed_list.append(heavy[i])
                count = light_per_gap + (1 if i < extra_light else 0)
                distributed_list.extend(light[light_idx : light_idx + count])
                light_idx += count
                
            distributed_list.append(heavy[-1])
            return distributed_list

        # 4. LEVEL-AWARE POSITIONING
        pos = {}
        level_next_x = {} # Tracks the next 'free' edge for each level

        def assign_pos_final(node_id, level):
            kids = get_ordered_children(node_id)
            
            if not kids:
                # 1. It's a leaf. Place it at the next available slot on this level.
                x = level_next_x.get(level, 0.0)
                pos[node_id] = (x, -level * V_GAP)
                level_next_x[level] = x + H_GAP
                return x, x # Return (min_x, max_x) of this branch

            # 2. It's a parent. Position all children first to find the family's width.
            child_bounds = [assign_pos_final(k, level + 1) for k in kids]
            
            # The 'Kingdom Width' is defined by the first and last child
            min_child_x = child_bounds[0][0]
            max_child_x = child_bounds[-1][1]
            
            # 3. Calculate the ideal center point for the parent
            ideal_x = (min_child_x + max_child_x) / 2.0
            
            # 4. SAFETY CHECK: Is the parent's level already crowded?
            current_level_min = level_next_x.get(level, 0.0)
            
            if ideal_x < current_level_min:
                # If the family is too far left, we must shift the WHOLE family right
                shift = current_level_min - ideal_x
                
                # Update this parent's position
                ideal_x += shift
                
                # Recursive Shift: We have to move the children we already placed
                def shift_branch(n_id, s_amount):
                    curr_p = pos[n_id]
                    pos[n_id] = (curr_p[0] + s_amount, curr_p[1])
                    # Update the level tracker for the children's levels too
                    node_level = int(abs(curr_p[1]) / V_GAP)
                    level_next_x[node_level] = max(level_next_x.get(node_level, 0.0), pos[n_id][0] + H_GAP)
                    
                    for child in tree_edges.get(n_id, []):
                        shift_branch(child, s_amount)

                # Move all descendants to keep them vertical/centered
                for k in kids:
                    shift_branch(k, shift)
            
            # 5. Finalize the parent and update the level tracker
            pos[node_id] = (ideal_x, -level * V_GAP)
            level_next_x[level] = ideal_x + H_GAP
            
            # Return the new bounds of this entire shifted family
            return min_child_x + (shift if 'shift' in locals() else 0), max_child_x + (shift if 'shift' in locals() else 0)

        # --- EXECUTION ---
        root_id = f"{root}_0"
        assign_pos_final(root_id, 0)
    
        # 6. Calculate ACTUAL width for scaling later
        x_coords = [p[0] for p in pos.values()]
        tree_width = max(x_coords) - min(x_coords) if x_coords else 0
        
        all_tree_data.append({
            'root': root, 'nodes': nodes, 'edges': edges, 'pos': pos,
            'label_fontsize': label_fontsize, 'symbol_fontsize': symbol_fontsize,
            'circle_size': circle_size, 'width': tree_width,
            'height': max([abs(p[1]) for p in pos.values()]) if pos else 0
        })
    
    # Count planet occurrences across all trees to detect duplicates (dual rulership)
    for tree_data in all_tree_data:
        for name, node_id in tree_data['nodes']:
            planet_occurrences[name] = planet_occurrences.get(name, 0) + 1
    
    # Identify planets that appear more than once
    duplicated_planets = {name for name, count in planet_occurrences.items() if count > 1}
    
    # PHASE 2: Create figure with dynamic scaling
    tree_widths = [td['width'] for td in all_tree_data]
    tree_heights = [td['height'] for td in all_tree_data]

    # Calculate the total physical inches needed
    # We use 0.15 as a "multiplier" to turn coordinate units into inches
    # If the chart is too wide for your screen, make 0.15 a smaller number like 0.1
    total_inches_needed = sum(tree_widths) * 0.15 
    
    # Ensure the figure isn't too small or absurdly large
    fig_width = max(15, total_inches_needed)
    fig_height = 12 
    
    # width_ratios ensures a 10-planet tree gets more room than a 2-planet tree
    width_ratios = [max(0.1, w) for w in tree_widths]
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = gridspec.GridSpec(1, n, figure=fig, width_ratios=width_ratios, wspace=0.3)
    axes = [fig.add_subplot(gs[0, i]) for i in range(n)]
    # PHASE 3: Render all trees
    # First, calculate the maximum y-range needed across all trees
    max_height = max(tree_heights) if tree_heights else 10
    
    for ax, tree_data in zip(axes, all_tree_data):
        nodes = tree_data['nodes']
        edges = tree_data['edges']
        pos = tree_data['pos']
        label_fontsize = tree_data['label_fontsize']
        symbol_fontsize = tree_data['symbol_fontsize']
        circle_size = tree_data['circle_size']

        # Define pair_to_aspect based on edges and reception logic
        pair_to_aspect = {}
        for parent_id, child_id in edges:
            edge_key = tuple(sorted((parent_id, child_id)))
            # Assuming reception data is available in `meta` for each edge
            meta = tree_data.get('meta', {}).get(edge_key, {})
            aspect = meta.get('aspect')
            if aspect in _RECEPTION_ASPECTS:
                pair_to_aspect[edge_key] = aspect
        
        for name, node_id in nodes:
            xy = pos.get(node_id)
            if xy is None:
                xy = (0.0, 0.0)
                pos[node_id] = xy
            
            # Color logic with support for dual colors (orange + purple)
            is_sovereign = name in sovereigns
            is_duplicated = name in duplicated_planets
            is_in_loop = name in rulership_loops
            
            # Determine color(s)
            if is_sovereign:
                color = "#59A54A"
                ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
            elif is_duplicated and is_in_loop:
                # Both orange and purple - draw concentric circles
                # Outer circle (orange) at full size
                ax.scatter(xy[0], xy[1], s=circle_size, c="#FF8656", zorder=2)
                # Inner circle (purple) at 60% size
                ax.scatter(xy[0], xy[1], s=circle_size * 0.6, c="#B386D8", zorder=3)
            elif is_duplicated:
                color = "#FF8656"
                ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
            elif is_in_loop:
                color = "#B386D8"
                ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
            else:
                color = "#5F6FFF"
                ax.scatter(xy[0], xy[1], s=circle_size, c=color, zorder=2)
            
            display_name = get_display_name(name)
            ax.text(xy[0], xy[1], display_name, ha='center', va='center', fontsize=label_fontsize, fontweight="bold", zorder=4)
            
            # Add circular arrow symbol below the planet name for self-ruling planets
            if name in self_ruling or name in sovereigns:
                # Position arrow directly below the text, tucked close
                ax.text(xy[0], xy[1] - 0.08, "↻", ha='center', va='top', 
                        fontsize=symbol_fontsize, color='black', zorder=3)

        # --- PHASE 1: PRE-CALCULATION & AXIS SETUP ---
        # SET AXIS LIMITS - This locks the camera to the family's width
        if pos:
            x_coords = [p[0] for p in pos.values()]
            y_coords = [p[1] for p in pos.values()]
            
            # Give it a small 10% buffer so the circles aren't cut off
            x_margin = H_GAP * 0.5
            ax.set_xlim(min(x_coords) - x_margin, max(x_coords) + x_margin)
            
            # Use a fixed bottom limit so all trees start at the top
            ax.set_ylim(min(y_coords) - 20, 10) 
            
        ax.axis("off")

# --- PHASE 4: Render Arrows and Aspect Icons ---
        edges_major = st.session_state.get('edges_major', [])
        png_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pngs")

        for parent_id, child_id in edges:
            start = pos.get(parent_id)
            end = pos.get(child_id)
            
            if start and end:
                # 1. Draw Arrow
                ax.annotate("", xy=end, xytext=start,
                            arrowprops=dict(arrowstyle="-|>", color="black", lw=1.8),
                            zorder=1)

                # 2. Extract base names
                p_name = parent_id.rsplit('_', 2)[0]
                c_name = child_id.rsplit('_', 2)[0]

                aspect_for_text = None 
                icon_filename = None
                icon_drawn = False
                mid_x, mid_y = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2

                # 3. Check Orb Aspect (Blue)
                aspect_meta = next(
                    (m for p, c, m in edges_major 
                     if (p == p_name and c == c_name) or (p == c_name and c == p_name)), 
                    None
                )

                if aspect_meta:
                    aspect_for_text = aspect_meta.get("aspect")
                    if aspect_for_text in RECEPTION_SYMBOLS:
                        icon_filename = RECEPTION_SYMBOLS[aspect_for_text].get("by orb")

                # 4. Check Sign Aspect (Green) - If no orb aspect found
                if not icon_filename:
                    sign_asp = get_sign_aspect_name(p_name, c_name, planets_df)
                    if sign_asp:
                        aspect_for_text = sign_asp # Synchronize names!
                        if aspect_for_text in RECEPTION_SYMBOLS:
                            icon_filename = RECEPTION_SYMBOLS[aspect_for_text].get("by sign")

                # 5. Render Icon logic
                if icon_filename:
                    icon_path = os.path.abspath(os.path.join(png_dir, icon_filename))
                    if os.path.exists(icon_path):
                        try:
                            img = plt.imread(icon_path)
                            imagebox = OffsetImage(img, zoom=icon_zoom)
                            ab = AnnotationBbox(
                                imagebox, (mid_x, mid_y),
                                xycoords='data', frameon=True, pad=0.1,
                                bboxprops=dict(facecolor='none', edgecolor='none', alpha=0.9),
                                zorder=10
                            )
                            ax.add_artist(ab)
                            icon_drawn = True
                        except Exception as e:
                            st.sidebar.error(f"Error reading PNG {icon_filename}: {e}")

                # 6. FALLBACK 1: Text Glyph (if icon failed or missing)
                if not icon_drawn and aspect_for_text in _RECEPTION_ASPECTS:
                    glyph = ASPECTS.get(aspect_for_text, {}).get("glyph", "?")
                    ax.text(
                        mid_x, mid_y, glyph, 
                        ha='center', va='center',
                        fontsize=13, zorder=11, fontweight='bold',
                        bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=0.5)
                    )
                    icon_drawn = True
                    
        # --- SET AXIS LIMITS (After the loop, exactly like your working snippet) ---
        if pos:
            x_coords = [p[0] for p in pos.values()]
            y_coords = [p[1] for p in pos.values()]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
            ax.set_xlim(x_min - x_pad, x_max + x_pad)
            y_range = max_height
            ax.set_ylim(y_max - y_range - 1, y_max + 1)

        ax.axis("off")

    # --- PHASE 3: FINAL FIGURE ADJUSTMENTS ---
    if header_info:
        plt.subplots_adjust(left=0.02, right=0.98, top=0.94, bottom=0.02, wspace=0.1)
        _draw_dispositor_header(fig, header_info)
    else:
        plt.subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02, wspace=0.1)
        
    return fig