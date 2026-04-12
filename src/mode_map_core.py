# src/mode_map_core.py
"""
Mode Map — pure-data / framework-agnostic core
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Contains the MODE_TREE constant, active-path computation, Cytoscape element
builder, and HTML template.  No Streamlit or NiceGUI imports.

This module is consumed by app.py (NiceGUI) to render the Mode Map inside
the Settings tab via ``ui.html()``.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# MODE_TREE: declarative graph topology
# ---------------------------------------------------------------------------
# Each entry: (node_id, label, category, list_of_parent_node_ids)
#
# Categories control visual styling:
#   "input"       – blue   – chart input methods
#   "core"        – white  – the Single Chart hub
#   "chart_mode"  – green  – Standard Chart Mode / Circuits Mode
#   "biwheel"     – orange – Bi-Wheel Chart hub
#   "circuit_sub" – purple – Combined / Connected Circuits sub-modes
#   "toggle_group"– gray   – groups of toggles
#   "toggle_leaf" – dim    – individual toggle leaf items

MODE_TREE: List[Tuple[str, str, str, List[str]]] = [
    # --- Input modes ---
    ("input_now",        "\"Now\" Button\n(Current Planets)", "input", []),
    ("input_birth",      "Enter Birth Data",         "input", []),
    ("input_manager",    "Chart Manager\n(Save/Load)","input",
     ["input_birth"]),

    # --- Core hub ---
    ("single_chart",     "Single Chart",             "core",
     ["input_birth", "input_manager", "input_now"]),

    # --- Biwheel feeder modes ---
    ("input_transit",    "Transit Mode",             "input",  ["single_chart"]),
    ("input_synastry",   "Synastry Mode",            "input",
     ["single_chart", "input_manager"]),
    ("biwheel_chart",    "Bi-Wheel Chart",           "biwheel",
     ["input_transit", "input_synastry"]),

    # === SINGLE-CHART PATH ===
    ("sc_standard",      "Standard Chart\nMode",     "chart_mode", ["single_chart"]),
    ("sc_circuits",      "Circuits Mode",            "chart_mode", ["single_chart"]),

    ("sc_addl_aspects",  "Additional\nAspects",      "toggle_group", ["sc_standard"]),
    ("sc_circuit_tg",    "Circuit Toggles",          "toggle_group", ["sc_circuits"]),
    ("sc_planet_tg",     "Single Planet\nToggles",   "toggle_group", ["sc_circuits"]),
    ("sc_shape_tg",      "Shape Toggles",            "toggle_group", ["sc_circuits"]),

    # === BI-WHEEL PATH ===
    ("bw_standard",      "Standard Chart\nMode",     "chart_mode", ["biwheel_chart"]),
    ("bw_circuits",      "Circuits Mode",            "chart_mode", ["biwheel_chart"]),

    ("bw_addl_aspects",  "Additional\nAspects",      "toggle_group", ["bw_standard"]),
    ("bw_chart1_asp",    "Chart 1\nAspects",         "toggle_group", ["bw_standard"]),
    ("bw_inter_asp",     "Chart 1 ↔ Chart 2\nAspects", "toggle_group", ["bw_standard"]),
    ("bw_chart2_asp",    "Chart 2\nAspects",         "toggle_group", ["bw_standard"]),

    ("bw_combined",      "Combined\nCircuits Mode",  "circuit_sub", ["bw_circuits"]),
    ("bw_connected",     "Connected\nCircuits Mode", "circuit_sub", ["bw_circuits"]),

    ("bw_comb_shapes",   "Chart 1 + Chart 2\nCombined Shapes", "toggle_group", ["bw_combined"]),

    ("bw_cc_circ_tg",    "Chart 1\nCircuit Toggles", "circuit_sub", ["bw_connected"]),
    ("bw_cc_shape_tg",   "Chart 1\nShape Toggles",   "circuit_sub", ["bw_connected"]),
    ("bw_cc_planet_tg",  "Chart 1 Single\nPlanet Toggles", "circuit_sub", ["bw_connected"]),

    ("bw_cc2_per_circ",  "Connected Chart 2\nShape Toggles per\nSelected Circuit",
     "toggle_leaf", ["bw_cc_circ_tg"]),
    ("bw_cc2_per_shape", "Connected Chart 2\nShape Toggles per\nSelected Shape",
     "toggle_leaf", ["bw_cc_shape_tg"]),
]


# ---------------------------------------------------------------------------
# Active-path computation  (framework-agnostic)
# ---------------------------------------------------------------------------

def compute_active_ids(
    *,
    chart_mode: str = "Circuits",
    circuit_submode: str = "Combined",
    has_chart: bool = False,
    synastry_mode: bool = False,
    transit_mode: bool = False,
    now_mode_active: bool = False,
    profile_loaded: bool = False,
    # Toggle snapshots (plain dicts)
    aspect_toggles: Optional[Dict[str, bool]] = None,
    pattern_toggles: Optional[Dict[int, bool]] = None,
    singleton_toggles: Optional[Dict[str, bool]] = None,
    shape_toggles: Optional[Dict[str, bool]] = None,
    synastry_aspects_chart1: bool = False,
    synastry_aspects_inter: bool = True,
    synastry_aspects_chart2: bool = False,
    num_patterns: int = 0,
    num_shapes: int = 0,
    num_singletons: int = 0,
) -> Set[str]:
    """Determine which node IDs should be highlighted as 'active'.

    All parameters are plain Python values — no framework state is read.
    """
    aspect_toggles = aspect_toggles or {}
    pattern_toggles = pattern_toggles or {}
    singleton_toggles = singleton_toggles or {}
    shape_toggles = shape_toggles or {}

    active: Set[str] = set()
    biwheel = synastry_mode or transit_mode

    # --- Input modes ---
    if now_mode_active:
        active.add("input_now")
    if profile_loaded:
        active.add("input_manager")
    if has_chart and not now_mode_active and not profile_loaded:
        active.add("input_birth")
    if transit_mode:
        active.add("input_transit")
    if synastry_mode:
        active.add("input_synastry")

    # --- Core hubs ---
    if has_chart:
        active.add("single_chart")
    if has_chart and biwheel:
        active.add("biwheel_chart")

    # --- Determine which path is active ---
    is_standard = chart_mode == "Standard Chart"

    if has_chart and biwheel:
        # Bi-Wheel path
        if is_standard:
            active.add("bw_standard")
            active.add("bw_addl_aspects")
            if synastry_aspects_chart1:
                active.add("bw_chart1_asp")
            if synastry_aspects_inter:
                active.add("bw_inter_asp")
            if synastry_aspects_chart2:
                active.add("bw_chart2_asp")
        else:
            active.add("bw_circuits")
            if circuit_submode in ("Combined Circuits", "Combined"):
                active.add("bw_combined")
                active.add("bw_comb_shapes")
            elif circuit_submode in ("Connected Circuits", "Connected"):
                active.add("bw_connected")
                active.add("bw_cc_circ_tg")
                active.add("bw_cc_shape_tg")
                active.add("bw_cc_planet_tg")
                active.add("bw_cc2_per_circ")
                active.add("bw_cc2_per_shape")

    elif has_chart:
        # Single-chart path
        if is_standard:
            active.add("sc_standard")
            if any(v for v in aspect_toggles.values()):
                active.add("sc_addl_aspects")
        else:
            active.add("sc_circuits")
            if any(pattern_toggles.get(i, False) for i in range(num_patterns)):
                active.add("sc_circuit_tg")
            if any(v for v in singleton_toggles.values()):
                active.add("sc_planet_tg")
            if any(v for v in shape_toggles.values()):
                active.add("sc_shape_tg")

    return active


# ---------------------------------------------------------------------------
# Build Cytoscape elements JSON
# ---------------------------------------------------------------------------

def build_elements(
    active_ids: Set[str],
    num_patterns: int = 0,
    num_shapes: int = 0,
    num_singletons: int = 0,
) -> List[Dict[str, Any]]:
    """Build the Cytoscape elements list (nodes + edges)."""
    elements: List[Dict[str, Any]] = []

    for node_id, label, category, parents in MODE_TREE:
        display_label = label
        if node_id == "sc_circuit_tg" and num_patterns > 0:
            display_label = f"{label} ({num_patterns})"
        elif node_id == "sc_shape_tg" and num_shapes > 0:
            display_label = f"{label} ({num_shapes})"
        elif node_id == "sc_planet_tg" and num_singletons > 0:
            display_label = f"{label} ({num_singletons})"

        elements.append({
            "data": {
                "id": node_id,
                "label": display_label,
                "category": category,
                "active": node_id in active_ids,
            }
        })
        for parent_id in parents:
            elements.append({
                "data": {
                    "source": parent_id,
                    "target": node_id,
                }
            })

    return elements


# ---------------------------------------------------------------------------
# HTML template (Cytoscape.js + dagre)
# ---------------------------------------------------------------------------

CYTOSCAPE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/dagre/0.8.5/dagre.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js"></script>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: transparent; font-family: 'Segoe UI', sans-serif; }
  #cy {
    width: 100%;
    height: %%HEIGHT%%px;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px;
    background: rgba(20, 20, 35, 0.85);
  }
  #legend {
    display: flex; gap: 14px; padding: 6px 10px; flex-wrap: wrap;
    font-size: 11px; color: #ccc;
  }
  .legend-item { display: flex; align-items: center; gap: 4px; }
  .legend-dot {
    width: 10px; height: 10px; border-radius: 50%; display: inline-block;
  }
  #tooltip {
    position: absolute; display: none; padding: 5px 10px;
    background: rgba(0,0,0,0.85); color: #fff; border-radius: 4px;
    font-size: 12px; pointer-events: none; z-index: 999;
    white-space: nowrap;
  }
</style>
</head>
<body>
<div id="legend">
  <span class="legend-item"><span class="legend-dot" style="background:#5B9BD5;"></span> Input</span>
  <span class="legend-item"><span class="legend-dot" style="background:#E8E8E8;"></span> Core</span>
  <span class="legend-item"><span class="legend-dot" style="background:#70AD47;"></span> Chart Mode</span>
  <span class="legend-item"><span class="legend-dot" style="background:#ED7D31;"></span> Bi-Wheel Hub</span>
  <span class="legend-item"><span class="legend-dot" style="background:#B07DD8;"></span> Circuit Sub-mode</span>
  <span class="legend-item"><span class="legend-dot" style="background:#A0A0A0;"></span> Toggle Group</span>
  <span class="legend-item"><span class="legend-dot" style="background:#666;"></span> Toggle Item</span>
  <span class="legend-item"><span class="legend-dot" style="background:#FFD700; border:2px solid #FFD700;"></span> Active</span>
</div>
<div id="cy"></div>
<div id="tooltip"></div>
<script>
(function() {
  var elements = %%ELEMENTS%%;

  var cy = cytoscape({
    container: document.getElementById('cy'),
    elements: elements,
    layout: {
      name: 'dagre',
      rankDir: 'LR',
      rankSep: 45,
      nodeSep: 18,
      edgeSep: 10,
      animate: false,
      fit: true,
      padding: 20,
    },
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '10px',
          'color': '#222',
          'text-wrap': 'wrap',
          'text-max-width': '90px',
          'width': 'label',
          'height': 'label',
          'padding': '8px',
          'shape': 'roundrectangle',
          'border-width': 1,
          'border-color': '#666',
        }
      },
      { selector: 'node[category="input"]', style: {
          'background-color': '#5B9BD5', 'color': '#fff', 'border-color': '#3A7ABD',
          'font-weight': 'bold',
      }},
      { selector: 'node[category="core"]', style: {
          'background-color': '#E8E8E8', 'color': '#222', 'border-color': '#999',
          'font-weight': 'bold', 'font-size': '12px',
      }},
      { selector: 'node[category="chart_mode"]', style: {
          'background-color': '#70AD47', 'color': '#fff', 'border-color': '#4E8A2E',
          'font-weight': 'bold',
      }},
      { selector: 'node[category="biwheel"]', style: {
          'background-color': '#ED7D31', 'color': '#fff', 'border-color': '#C66520',
          'font-weight': 'bold',
      }},
      { selector: 'node[category="circuit_sub"]', style: {
          'background-color': '#B07DD8', 'color': '#fff', 'border-color': '#8B5FB5',
      }},
      { selector: 'node[category="toggle_group"]', style: {
          'background-color': '#A0A0A0', 'color': '#fff', 'border-color': '#777',
          'font-size': '9px',
      }},
      { selector: 'node[category="toggle_leaf"]', style: {
          'background-color': '#555', 'color': '#ddd', 'border-color': '#444',
          'font-size': '8px', 'padding': '5px',
      }},
      { selector: 'node[?active]', style: {
          'border-width': 3,
          'border-color': '#FFD700',
          'shadow-blur': 12,
          'shadow-color': '#FFD700',
          'shadow-opacity': 0.7,
          'shadow-offset-x': 0,
          'shadow-offset-y': 0,
      }},
      {
        selector: 'edge',
        style: {
          'width': 1.5,
          'line-color': '#888',
          'target-arrow-color': '#888',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'arrow-scale': 0.8,
        }
      },
      {
        selector: 'edge[source = "single_chart"]',
        style: { 'line-color': '#aaa', 'target-arrow-color': '#aaa' }
      },
    ],
    userZoomingEnabled: true,
    userPanningEnabled: true,
    boxSelectionEnabled: false,
    autoungrabify: true,
    minZoom: 0.3,
    maxZoom: 3,
  });

  var nowNode = cy.getElementById('input_now');
  if (nowNode.length) {
    var pos = nowNode.position();
    nowNode.position({ x: pos.x, y: pos.y + 80 });
  }

  var tooltip = document.getElementById('tooltip');
  cy.on('mouseover', 'node', function(e) {
    var node = e.target;
    var label = node.data('label');
    var cat = node.data('category');
    var isActive = node.data('active');
    var text = label + ' [' + cat.replace('_', ' ') + ']';
    if (isActive) text += ' \\u2726 ACTIVE';
    tooltip.textContent = text;
    tooltip.style.display = 'block';
  });
  cy.on('mousemove', 'node', function(e) {
    tooltip.style.left = (e.originalEvent.offsetX + 12) + 'px';
    tooltip.style.top  = (e.originalEvent.offsetY + 12) + 'px';
  });
  cy.on('mouseout', 'node', function() {
    tooltip.style.display = 'none';
  });

  cy.on('tap', 'node', function(e) {
    cy.elements().removeClass('highlighted');
    var clicked = e.target;
    var neighborhood = clicked.neighborhood().add(clicked);
    neighborhood.addClass('highlighted');
  });
  cy.on('tap', function(e) {
    if (e.target === cy) {
      cy.elements().removeClass('highlighted');
    }
  });
})();
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Public helper: build complete HTML string
# ---------------------------------------------------------------------------

def render_mode_map_html(
    *,
    chart_mode: str = "Circuits",
    circuit_submode: str = "Combined",
    has_chart: bool = False,
    synastry_mode: bool = False,
    transit_mode: bool = False,
    now_mode_active: bool = False,
    profile_loaded: bool = False,
    aspect_toggles: Optional[Dict[str, bool]] = None,
    pattern_toggles: Optional[Dict[int, bool]] = None,
    singleton_toggles: Optional[Dict[str, bool]] = None,
    shape_toggles: Optional[Dict[str, bool]] = None,
    synastry_aspects_chart1: bool = False,
    synastry_aspects_inter: bool = True,
    synastry_aspects_chart2: bool = False,
    num_patterns: int = 0,
    num_shapes: int = 0,
    num_singletons: int = 0,
) -> str:
    """Build the complete Mode Map HTML string ready to embed via ui.html().

    Returns a self-contained HTML document that renders a Cytoscape DAG.
    """
    active_ids = compute_active_ids(
        chart_mode=chart_mode,
        circuit_submode=circuit_submode,
        has_chart=has_chart,
        synastry_mode=synastry_mode,
        transit_mode=transit_mode,
        now_mode_active=now_mode_active,
        profile_loaded=profile_loaded,
        aspect_toggles=aspect_toggles,
        pattern_toggles=pattern_toggles,
        singleton_toggles=singleton_toggles,
        shape_toggles=shape_toggles,
        synastry_aspects_chart1=synastry_aspects_chart1,
        synastry_aspects_inter=synastry_aspects_inter,
        synastry_aspects_chart2=synastry_aspects_chart2,
        num_patterns=num_patterns,
        num_shapes=num_shapes,
        num_singletons=num_singletons,
    )
    elements = build_elements(
        active_ids,
        num_patterns=num_patterns,
        num_shapes=num_shapes,
        num_singletons=num_singletons,
    )

    num_nodes = sum(1 for e in elements if "source" not in e.get("data", {}))
    height = max(480, min(700, 400 + num_nodes * 5))

    html = CYTOSCAPE_HTML.replace("%%ELEMENTS%%", json.dumps(elements))
    html = html.replace("%%HEIGHT%%", str(height))
    return html
