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
                png_dir = os.path.join(os.path.dirname(__file__), "pngs")
                
                # Get the directory of the current file (e.g., ...\Rosetta_v2\src)
                current_dir = os.path.dirname(__file__) 
                
                # ⬇️ THE FIX: Go up one level (..) to Rosetta_v2, then look for 'pngs' ⬇️
                png_dir = os.path.join(current_dir, "..", "pngs")

                # Load and encode images as base64
                def img_to_b64(filename):
                    path = os.path.join(png_dir, filename)
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            return base64.b64encode(f.read()).decode()
                    return ""
                
                # Create legend with dark background
                st.markdown("""
                    <div style="background-color: #262730; padding: 15px; border-radius: 8px;">
                        <strong style="color: white;">Legend</strong>
                    </div>
                """, unsafe_allow_html=True)
                
                legend_items = [
                    ("green.png", "Sovereign"),
                    ("orange.png", "Dual rulership"),
                    ("purple.png", "Loop"),
                    ("purpleorange.png", "Dual + Loop"),
                    ("blue.png", "Standard"),
                ]
                
                # Wrap all legend items in the dark background
                legend_html = '<div style="background-color: #262730; padding: 15px; border-radius: 8px; margin-top: -15px;">'
                for img_file, label in legend_items:
                    b64 = img_to_b64(img_file)
                    if b64:
                        legend_html += f'<div style="margin-bottom: 8px;"><img src="data:image/png;base64,{b64}" width="20" style="vertical-align:middle;margin-right:5px"/><span style="color: white;">{label}</span></div>'
                legend_html += '<div style="color: white; margin-top: 8px;">↻ Self-Ruling</div>'
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

        # Calculate dynamic spacing based on tree size relative to largest tree
        num_nodes = len(tree_nodes)  # Use tree_nodes (actual count) not nodes (includes duplicates)
        # Gentler scaling: interpolate between 0.85 and 1.0
        raw_scale = num_nodes / max_nodes
        scale_factor = 0.85 + (0.15 * raw_scale)  # Scale ranges from 0.85 to 1.0
        
        # Scale spacing
        min_spacing = 5.0 * scale_factor
        vertical_gap = 2.0 * scale_factor
        
        # Simple node-count-based sizing (like original code)
        if num_nodes <= 5:
            label_fontsize = 9
            symbol_fontsize = 12
            circle_size = 2000
            icon_zoom = 0.90  # Largest icons for small trees
        elif num_nodes <= 15:
            label_fontsize = 11
            symbol_fontsize = 13
            circle_size = 2000
            icon_zoom = 0.75
        elif num_nodes <= 20:
            label_fontsize = 12
            symbol_fontsize = 14
            circle_size = 3000
            icon_zoom = 0.66
        elif num_nodes <= 25:
            label_fontsize = 11
            symbol_fontsize = 13
            circle_size = 3000
            icon_zoom = 0.60
        else:
            label_fontsize = 8
            symbol_fontsize = 10
            circle_size = 900
            icon_zoom = 0.54  # Smallest icons for crowded trees

        subtree_gap = -min_spacing * 1  # Negative gap to bring siblings closer
        
        # Build parent->children map for this tree
        tree_edges = {}
        for parent_id, child_id in edges:
            tree_edges.setdefault(parent_id, []).append(child_id)
        
        # Position nodes level by level, centering children under parents
        pos = {}
        next_x_by_level = {}  # track next available x position per level
        
        def position_subtree(node_id, parent_x=None):
            """Position node and its descendants, returning the node's final x position."""
            level = next(lev for lev, ids in level_nodes.items() if node_id in ids)
            children = tree_edges.get(node_id, [])
            
            if not children:
                # Leaf node: place at next available position
                x = next_x_by_level.get(level, 0.0)
                pos[node_id] = (x, -level * vertical_gap)
                next_x_by_level[level] = x + min_spacing
                return x
            else:
                # Internal node: position children one by one
                child_positions = []
                for child in children:
                    # Position this child subtree
                    child_x = position_subtree(child, parent_x=None)
                    child_positions.append(child_x)
                    
                    # After positioning child, find rightmost node in its subtree and update tracker
                    def update_tracker_for_subtree(nid):
                        if nid in pos:
                            node_level = next(lev for lev, ids in level_nodes.items() if nid in ids)
                            node_x = pos[nid][0]
                            next_x_by_level[node_level] = max(
                                next_x_by_level.get(node_level, -float('inf')),
                                node_x + min_spacing
                            )
                        for c in tree_edges.get(nid, []):
                            update_tracker_for_subtree(c)
                    
                    # Update tracker based on final positions in this child's subtree
                    update_tracker_for_subtree(child)
                
                # Parent centers over its children's actual final positions
                leftmost_child = min(child_positions)
                rightmost_child = max(child_positions)
                x = (leftmost_child + rightmost_child) / 2.0
                
                # Ensure parent doesn't collide with other nodes at its level
                min_x = next_x_by_level.get(level, -float('inf'))
                if x < min_x:
                    # Need to shift: calculate how much and shift the whole subtree
                    shift = min_x - x
                    x = min_x
                    
                    # Shift all descendants that were already positioned
                    def shift_subtree(nid, dx):
                        if nid in pos:
                            old_x, old_y = pos[nid]
                            pos[nid] = (old_x + dx, old_y)
                        for c in tree_edges.get(nid, []):
                            shift_subtree(c, dx)
                    
                    for child in children:
                        shift_subtree(child, shift)
                    
                    # After shifting, update tracker again for all children
                    for child in children:
                        update_tracker_for_subtree(child)
                
                pos[node_id] = (x, -level * vertical_gap)
                
                # Add extra spacing after parent nodes to separate subtree groups
                next_x_by_level[level] = x + min_spacing + subtree_gap
                return x
        
        # Start positioning from root
        root_id = f"{root}_0"
        position_subtree(root_id)

        root_id = f"{root}_0"
        if root_id not in pos:
            pos[root_id] = (0.0, 0.0)
        
        # COMPACTION PHASE: Pack childless siblings into gaps between parent siblings
        # For each parent node, compact its direct children
        def compact_children(parent_id):
            """Reposition childless children to fill gaps between parent children."""
            children = tree_edges.get(parent_id, [])
            if len(children) <= 1:
                return  # nothing to compact
            
            # Separate children into parents (have their own children) and leaves (no children)
            parent_children = [cid for cid in children if tree_edges.get(cid)]
            leaf_children = [cid for cid in children if not tree_edges.get(cid)]
            
            if not parent_children or not leaf_children:
                return  # need both types to compact
            
            # Sort parent children by x position
            parent_children.sort(key=lambda cid: pos[cid][0])
            
            # Sort leaf children by current x position to maintain relative order
            leaf_children.sort(key=lambda cid: pos[cid][0])
            
            # Get the level of these children (all siblings are at same level)
            child_level = next(lev for lev, ids in level_nodes.items() if children[0] in ids)
            
            # Collect ALL nodes at this level to check for collisions
            all_nodes_at_level = [(nid, pos[nid][0]) for nid in level_nodes.get(child_level, []) if nid in pos]
            all_nodes_at_level.sort(key=lambda x: x[1])  # sort by x position
            
            # Calculate total gap space between all parent children
            gaps = []
            total_gap_space = 0
            for i in range(len(parent_children) - 1):
                left_child = parent_children[i]
                right_child = parent_children[i + 1]
                left_x = pos[left_child][0]
                right_x = pos[right_child][0]
                gap_size = right_x - left_x - min_spacing
                # Only use gaps that can fit at least one leaf with proper spacing
                if gap_size >= min_spacing * 1.5:  # Relaxed threshold
                    gaps.append({
                        'left_x': left_x,
                        'right_x': right_x,
                        'size': gap_size
                    })
                    total_gap_space += gap_size
            
            if not gaps:
                return  # no gaps to fill
            
            # Distribute leaves evenly across all gaps
            num_leaves = len(leaf_children)
            leaf_idx = 0
            
            for gap in gaps:
                # Calculate how many leaves should go in this gap (proportional to gap size)
                gap_proportion = gap['size'] / total_gap_space
                leaves_for_gap = max(1, round(num_leaves * gap_proportion))
                
                # Don't exceed remaining leaves
                leaves_for_gap = min(leaves_for_gap, num_leaves - leaf_idx)
                
                if leaves_for_gap == 0:
                    continue
                
                # Evenly space the leaves in this gap
                gap_start = gap['left_x'] + min_spacing
                gap_end = gap['right_x']
                available_space = gap_end - gap_start
                
                # Ensure we have enough space for the leaves with minimum spacing
                required_space = leaves_for_gap * min_spacing
                if available_space < required_space:
                    # Adjust number of leaves to fit
                    leaves_for_gap = max(1, int(available_space / min_spacing))
                
                spacing = available_space / (leaves_for_gap + 1)
                # Don't let spacing go below min_spacing
                spacing = max(spacing, min_spacing * 0.8)
                
                for i in range(leaves_for_gap):
                    if leaf_idx >= num_leaves:
                        break
                    leaf_id = leaf_children[leaf_idx]
                    new_x = gap_start + spacing * (i + 1)
                    
                    # CRITICAL: Check if this position would overlap with any existing node
                    collision = False
                    for other_id, other_x in all_nodes_at_level:
                        if other_id != leaf_id and abs(new_x - other_x) < min_spacing * 0.9:
                            collision = True
                            break
                    
                    if not collision:
                        old_x, y = pos[leaf_id]
                        pos[leaf_id] = (new_x, y)
                    # If collision, keep original position
                    
                    leaf_idx += 1
                
                if leaf_idx >= num_leaves:
                    break
        
        # COMPACTION PHASE: Pack childless siblings into gaps between parent siblings
        # Always apply compaction, but respect min_spacing
        for node_id in pos.keys():
            if tree_edges.get(node_id):  # is a parent
                compact_children(node_id)

        # Calculate tree extent
        x_coords = [p[0] for p in pos.values()]
        y_coords = [p[1] for p in pos.values()]
        tree_width = max(x_coords) - min(x_coords) if x_coords else 0
        tree_height = max(y_coords) - min(y_coords) if y_coords else 0
        
        # Store all data for this tree
        all_tree_data.append({
            'root': root,
            'nodes': nodes,
            'edges': edges,
            'pos': pos,
            'label_fontsize': label_fontsize,
            'symbol_fontsize': symbol_fontsize,
            'circle_size': circle_size,
            'width': tree_width,
            'height': tree_height
        })
    
    # Count planet occurrences across all trees to detect duplicates (dual rulership)
    for tree_data in all_tree_data:
        for name, node_id in tree_data['nodes']:
            planet_occurrences[name] = planet_occurrences.get(name, 0) + 1
    
    # Identify planets that appear more than once
    duplicated_planets = {name for name, count in planet_occurrences.items() if count > 1}
    
    # PHASE 2: Create figure with proper size based on actual tree extents
    tree_widths = [td['width'] for td in all_tree_data]
    tree_heights = [td['height'] for td in all_tree_data]
    
    # Use a fixed, reasonable figure size that's not based on data width
    # Data widths can be large due to spacing, but we don't want huge figures
    fig_width = 8 * n  # 8 inches per tree - reasonable and consistent
    fig_height = 10     # 10 inches tall
    
    # Use GridSpec to control subplot widths proportionally
    
    # Calculate width ratios based on tree widths
    max_width = max(tree_widths) if tree_widths else 1
    width_ratios = [w / max_width for w in tree_widths]
    
    fig = plt.figure(figsize=(fig_width, fig_height))
    gs = gridspec.GridSpec(1, n, figure=fig, width_ratios=width_ratios, wspace=0.15)
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
        # Set axis limits FIRST so the coordinate system is stable
        if pos:
            x_coords = [p[0] for p in pos.values()]
            y_coords = [p[1] for p in pos.values()]
            x_min, x_max = min(x_coords), max(x_coords)
            y_min, y_max = min(y_coords), max(y_coords)
            
            x_pad = (x_max - x_min) * 0.1 if x_max > x_min else 1.0
            ax.set_xlim(x_min - x_pad, x_max + x_pad)
            
            y_range = max_height
            ax.set_ylim(y_max - y_range - 1, y_max + 1)

        # Turn off axis before drawing artists
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
                                bboxprops=dict(facecolor='white', edgecolor='none', alpha=0.9),
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