"""
circuit_sim.py — Circuit Power Simulation Engine
=================================================
Models an astrological chart as an electrical circuit:
  • Planets/points  →  power sources (voltage = power_index from dignity_calc)
  • Aspect edges    →  conductive wires (ASPECT_CONDUCTANCE values)
  • Shapes          →  distinct circuit topologies (Grand Trine, T-Square, …)

Key design rules
----------------
  Quincunx  = arc hazard (conductance 0.0).  BFS searches for an alternative
              path through the same shape's other edges.  If found, the arc is
              "rerouted"; if not, it is marked "open arc".

  South Node = source emitter (comfort-zone energy radiates outward).
  North Node = sink/attractor (growth energy draws inward).
              Edges on the shortest SN→NN path receive a small conductance
              boost (+0.1, capped at 1.0) to represent directional pull.

  Mutual reception pairs  →  secret bidirectional boost (+0.15 each direction)
              applied before the main propagation pass.

Power propagation (simplified metaphorical model, not strict Kirchhoff)
------------------------------------------------------------------------
  For each edge:
      base_power  = (power_a + power_b) / 2
      transmitted = conductance × base_power
      friction    = (1 − conductance) × base_power   [only for lossy aspects]

  Node effective_power = power_index + 0.5 × received_power − friction_load

Public API
----------
  simulate_and_attach(chart)  →  None
      Runs the simulation and stores the result in chart.circuit_simulation.

  simulate_circuit(chart)  →  CircuitSimulation
      Pure function; does not mutate the chart.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .models_v2 import (
    static_db,
    AstrologicalChart,
    CircuitEdge,
    CircuitNode,
    CircuitSimulation,
    ShapeCircuit,
)
ASPECT_CONDUCTANCE = static_db.ASPECT_CONDUCTANCE

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Aspects that generate friction/heat loss beyond the transmitted power.
FRICTION_ASPECTS = {"Square", "Opposition", "Sesquisquare"}

#: Conductance bonus on SN→NN pathway edges.
SN_NN_BONUS = 0.10
#: Conductance bonus per endpoint for mutual reception pairs.
MUTUAL_RECEPTION_BONUS = 0.15

#: Minimum conductance considered "conductive" (above arc-hazard level).
MIN_CONDUCTIVE = 0.01

#: Shape topology profile table.  Maps shape type → (resonance_base, friction_base,
#: flow_characterization template).
#: resonance_base and friction_base are 0–1 floats used as starting points before
#: empirical values are blended in.
SHAPE_TOPOLOGY = {
    "Grand Trine": {
        "resonance_base": 0.95,
        "friction_base": 0.05,
        "membrane_class": None,
        "flow": "Resonant recycling loop — energy circulates freely between all three nodes.",
    },
    "Kite": {
        "resonance_base": 0.85,
        "friction_base": 0.15,
        "membrane_class": None,
        "flow": "Directed Grand Trine — the apex node focuses and projects the loop's energy outward.",
    },
    "T-Square": {
        "resonance_base": 0.30,
        "friction_base": 0.70,
        "membrane_class": None,
        "flow": "Pressure funnel — friction tension from the base funnels into the apex, charging it with driven output.",
    },
    "Grand Cross": {
        "resonance_base": 0.15,
        "friction_base": 0.85,
        "membrane_class": "drum_head",
        "flow": (
            "Drum head — even tension in all four directions pulls the energy "
            "taut and LIVE with resonance, creating a spinning vortex effect "
            "like a pinwheel. The squares provide propulsive friction that makes "
            "the structure spin; the intersecting oppositions ground and balance "
            "polarities across the entire structure. Energy can be intensely "
            "fast-paced — everything clicking into place so rapidly it can be "
            "hard to stay grounded."
        ),
    },
    "Yod": {
        "resonance_base": 0.55,
        "friction_base": 0.45,
        "membrane_class": None,
        "flow": "Indirect pressure concentrator — quincunx arcs focus unresolved tension on the apex, forcing redirection.",
    },
    "Mystic Rectangle": {
        "resonance_base": 0.70,
        "friction_base": 0.30,
        "membrane_class": "resonant_membrane",
        "flow": (
            "Resonant membrane — the trines and sextiles stretch a harmonious "
            "surface between the grounding oppositions, picking up and "
            "amplifying resonant frequencies like an antenna with foil stretched "
            "across it. The structure is symmetrical about the origin, creating "
            "a sixth-sense receiver that heightens intuitive and sensory "
            "perception."
        ),
    },
    "Merkabah": {
        "resonance_base": 0.80,
        "friction_base": 0.20,
        "membrane_class": "drum_head",
        "flow": (
            "Super drum head — three intersecting oppositions create a triple-taut "
            "membrane across six harmonic points, with two interlocking Grand "
            "Trines providing massive resonant surface area. The most structurally "
            "complete drum head possible; every opposition is connected to every "
            "other through the harmonic sextile chain, generating extraordinary "
            "propulsive spin from the sheer scope of intersecting tension."
        ),
    },
    "Opposition": {
        "resonance_base": 0.35,
        "friction_base": 0.65,
        "membrane_class": None,
        "flow": "Polarized channel — power splits between two poles and oscillates in tension.",
    },
    "Conjunction": {
        "resonance_base": 0.90,
        "friction_base": 0.10,
        "membrane_class": None,
        "flow": "Merged power source — energies fuse into a single amplified expression.",
    },
    "Cradle": {
        "resonance_base": 0.65,
        "friction_base": 0.35,
        "membrane_class": None,
        "flow": "Contained arc — sextile/trine cradle cushions oppositions and channels friction productively.",
    },
    "LightningBolt": {
        "resonance_base": 0.50,
        "friction_base": 0.50,
        "membrane_class": None,
        "flow": "Tension discharge — built-up friction releases in a single directed flash of output.",
    },
    "Envelope": {
        "resonance_base": 0.60,
        "friction_base": 0.40,
        "membrane_class": None,
        "flow": "Contained tension — outer trines or sextiles wrap an inner friction dynamic.",
    },
    "Unnamed": {
        "resonance_base": 0.50,
        "friction_base": 0.50,
        "membrane_class": None,
        "flow": "Custom topology — mixed aspect blend with emergent flow characteristics.",
    },
}

_DEFAULT_TOPOLOGY = {
    "resonance_base": 0.50,
    "friction_base": 0.50,
    "membrane_class": None,
    "flow": "Unclassified circuit topology.",
}

# South/North Node canonical names as used throughout the codebase.
_SN_NAMES = {"South Node", "True South Node", "Mean South Node", "South Node (Mean)", "South Node (True)"}
_NN_NAMES = {"North Node", "True North Node", "Mean North Node", "North Node (Mean)", "North Node (True)"}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _conductance_for(aspect_type: str) -> float:
    """Return the conductance value for an aspect type, defaulting to 0.5."""
    entry = ASPECT_CONDUCTANCE.get(aspect_type)
    if entry is None:
        # fallback: try partial match
        for key, val in ASPECT_CONDUCTANCE.items():
            if key.lower() in aspect_type.lower() or aspect_type.lower() in key.lower():
                return val["conductance"]
        return 0.5
    return entry["conductance"]


def _is_quincunx(aspect_type: str) -> bool:
    """Return True if the aspect type is a quincunx (inconjunct)."""
    return "quincunx" in aspect_type.lower() or "inconjunct" in aspect_type.lower()


def _build_node(name: str, planetary_states: dict, mutual_reception_names: set) -> CircuitNode:
    """Construct a CircuitNode, seeding power values from PlanetaryState."""
    state = planetary_states.get(name)
    node = CircuitNode(planet_name=name)
    if state is not None:
        node.raw_authority = state.raw_authority or 0.0
        node.raw_potency = state.potency_score or 0.0
        node.power_index = state.power_index or 0.0
    node.is_source = name in _SN_NAMES
    node.is_sink = name in _NN_NAMES
    node.is_mutual_reception = name in mutual_reception_names
    return node


def _mutual_reception_names(mutual_receptions: list) -> set:
    """Flatten mutual reception pairs into a set of planet names."""
    names: set = set()
    for pair in mutual_receptions:
        # pair may be a tuple/list of planet names or objects with .planet_name
        for item in pair:
            if isinstance(item, str):
                names.add(item)
            elif hasattr(item, "planet_name"):
                names.add(item.planet_name)
            elif hasattr(item, "object_name"):
                # ChartObject — get string name
                obj_name = item.object_name
                if hasattr(obj_name, "name"):
                    obj_name = obj_name.name
                names.add(str(obj_name))
    return names


def _bfs_reroute(
    member_names: List[str],
    conductive_edges: List[Tuple[str, str]],
    source: str,
    target: str,
) -> Optional[List[str]]:
    """
    BFS through conductive_edges (excluding the source-target quincunx itself)
    to find the shortest alternative path from source to target.

    Returns a list of node names forming the path (inclusive of endpoints),
    or None if no path exists.
    """
    if source == target:
        return None

    # Build adjacency map from conductive edges only.
    adj: Dict[str, List[str]] = {n: [] for n in member_names}
    for (a, b) in conductive_edges:
        # Skip the direct quincunx we're trying to reroute.
        if {a, b} == {source, target}:
            continue
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    # BFS
    visited = {source}
    queue: deque = deque([[source]])
    while queue:
        path = queue.popleft()
        node = path[-1]
        for neighbour in adj.get(node, []):
            if neighbour == target:
                return path + [target]
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])
    return None


def _apply_mutual_reception_boost(
    nodes: Dict[str, CircuitNode],
    edges: List[CircuitEdge],
    mutual_reception_names: set,
) -> None:
    """
    Boost effective_power on mutual reception nodes and clamp edge conductance
    upward for edges connecting them.  Mutates in place.
    """
    for node in nodes.values():
        if node.is_mutual_reception:
            node.power_index = min(node.power_index + MUTUAL_RECEPTION_BONUS * 5, 10.0)

    for edge in edges:
        if edge.node_a in mutual_reception_names and edge.node_b in mutual_reception_names:
            edge.conductance = min(edge.conductance + MUTUAL_RECEPTION_BONUS * 2, 1.0)


def _apply_sn_nn_boost(edges: List[CircuitEdge], sn_nn_path: List[str]) -> None:
    """
    Boost conductance on edges that lie along the SN→NN path.
    Mutates edges in place.
    """
    if len(sn_nn_path) < 2:
        return
    path_pairs = set()
    for i in range(len(sn_nn_path) - 1):
        path_pairs.add(frozenset([sn_nn_path[i], sn_nn_path[i + 1]]))

    for edge in edges:
        if frozenset([edge.node_a, edge.node_b]) in path_pairs:
            edge.conductance = min(edge.conductance + SN_NN_BONUS, 1.0)


def _propagate_power(
    nodes: Dict[str, CircuitNode],
    edges: List[CircuitEdge],
) -> None:
    """
    Run one pass of power propagation across all edges.
    Mutates CircuitNode and CircuitEdge objects in place.
    """
    for edge in edges:
        a = nodes.get(edge.node_a)
        b = nodes.get(edge.node_b)
        if a is None or b is None:
            continue

        if edge.conductance < MIN_CONDUCTIVE and not edge.is_rerouted:
            # Arc hazard and not rerouted — no direct power flow.
            continue

        c = edge.conductance
        base = (a.power_index + b.power_index) / 2.0
        edge.transmitted_power = c * base

        # Determine flow direction hint
        if a.is_source or b.is_sink:
            edge.flow_direction = "a→b"
        elif b.is_source or a.is_sink:
            edge.flow_direction = "b→a"
        else:
            edge.flow_direction = "bidirectional"

        # Both nodes receive power from the other.
        a.received_power += edge.transmitted_power
        b.received_power += edge.transmitted_power

        # Friction heat on lossy aspects.
        if edge.aspect_type in FRICTION_ASPECTS:
            edge.friction_heat = (1.0 - c) * base
            # The node with lower power_index bears more friction (weak node overloads).
            if a.power_index <= b.power_index:
                a.friction_load += edge.friction_heat
            else:
                b.friction_load += edge.friction_heat

    # Compute effective_power after all edges are processed.
    for node in nodes.values():
        node.effective_power = (
            node.power_index
            + 0.5 * node.received_power
            - node.friction_load
        )


def _find_sn_nn_path_in_simulation(
    node_map: Dict[str, CircuitNode],
    all_edges: List[CircuitEdge],
) -> List[str]:
    """
    BFS on all nodes (across all shapes) to find the shortest conductive path
    from any South Node variant to any North Node variant.

    Returns the path as a list of planet names, or [] if no path exists.
    """
    sn_present = [n for n in node_map if n in _SN_NAMES]
    nn_present = [n for n in node_map if n in _NN_NAMES]
    if not sn_present or not nn_present:
        return []

    # Build adjacency from all conductive edges.
    adj: Dict[str, List[str]] = {n: [] for n in node_map}
    for edge in all_edges:
        if edge.conductance >= MIN_CONDUCTIVE or edge.is_rerouted:
            adj.setdefault(edge.node_a, []).append(edge.node_b)
            adj.setdefault(edge.node_b, []).append(edge.node_a)

    source = sn_present[0]
    targets = set(nn_present)

    visited = {source}
    queue: deque = deque([[source]])
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node in targets:
            return path
        for neighbour in adj.get(node, []):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(path + [neighbour])
    return []


# ---------------------------------------------------------------------------
# Shape-level simulation
# ---------------------------------------------------------------------------

def _simulate_shape(
    shape: dict,
    planetary_states: dict,
    mutual_receptions: list,
) -> ShapeCircuit:
    """
    Build and run the circuit simulation for a single shape dict as produced
    by patterns_v2.detect_shapes().

    shape dict keys used:
        id       (int)
        type     (str)
        members  (List[str])
        edges    (List[((p1, p2), aspect_name)])
    """
    shape_type = shape.get("type", "Unnamed")
    shape_id = shape.get("id", -1)
    members: List[str] = shape.get("members", [])
    raw_edges = shape.get("edges", [])

    topology = SHAPE_TOPOLOGY.get(shape_type, _DEFAULT_TOPOLOGY)
    mr_names = _mutual_reception_names(mutual_receptions)

    # --- Build nodes ---
    nodes: Dict[str, CircuitNode] = {}
    for name in members:
        nodes[name] = _build_node(name, planetary_states, mr_names)

    # --- Build edges ---
    edges: List[CircuitEdge] = []
    quincunx_edges: List[CircuitEdge] = []
    conductive_pairs: List[Tuple[str, str]] = []  # non-quincunx

    for raw_edge in raw_edges:
        # raw_edge is ((p1, p2), aspect_name)
        try:
            (p1, p2), aspect_name = raw_edge
        except (ValueError, TypeError):
            continue

        if p1 not in nodes:
            nodes[p1] = _build_node(p1, planetary_states, mr_names)
        if p2 not in nodes:
            nodes[p2] = _build_node(p2, planetary_states, mr_names)

        conductance = _conductance_for(aspect_name)
        is_arc = _is_quincunx(aspect_name)

        edge = CircuitEdge(
            node_a=p1,
            node_b=p2,
            aspect_type=aspect_name,
            conductance=conductance,
            is_arc_hazard=is_arc,
        )
        edges.append(edge)
        if is_arc:
            quincunx_edges.append(edge)
        else:
            conductive_pairs.append((p1, p2))

    # --- Quincunx rerouting ---
    for qe in quincunx_edges:
        reroute = _bfs_reroute(list(nodes.keys()), conductive_pairs, qe.node_a, qe.node_b)
        if reroute is not None:
            qe.is_rerouted = True
            qe.reroute_path = reroute
            # Use average conductance of the reroute path's edges as its effective conductance.
            path_conductances = []
            for i in range(len(reroute) - 1):
                edge_c = next(
                    (
                        e.conductance
                        for e in edges
                        if {e.node_a, e.node_b} == {reroute[i], reroute[i + 1]}
                    ),
                    0.5,
                )
                path_conductances.append(edge_c)
            qe.conductance = min(path_conductances) * 0.8 if path_conductances else 0.2
        else:
            qe.is_open_arc = True

    # --- Boosts ---
    _apply_mutual_reception_boost(nodes, edges, mr_names)

    # --- Propagate power ---
    _propagate_power(nodes, edges)

    # --- Aggregate metrics ---
    total_throughput = sum(e.transmitted_power for e in edges)
    total_friction = sum(e.friction_heat for e in edges)

    sorted_by_power = sorted(nodes.values(), key=lambda n: n.effective_power, reverse=True)
    dominant = sorted_by_power[0].planet_name if sorted_by_power else ""
    sorted_by_friction = sorted(nodes.values(), key=lambda n: n.friction_load, reverse=True)
    bottleneck = sorted_by_friction[0].planet_name if sorted_by_friction else ""

    # Scale empirical resonance/friction from throughput / (throughput + friction).
    if total_throughput + total_friction > 0:
        empirical_resonance = total_throughput / (total_throughput + total_friction)
    else:
        empirical_resonance = topology["resonance_base"]

    # Blend base and empirical values (60/40 toward empirical).
    resonance_score = round(
        0.40 * topology["resonance_base"] + 0.60 * empirical_resonance, 3
    )
    friction_score = round(1.0 - resonance_score, 3)

    # Flow characterization — append dominant node info.
    flow_char = topology["flow"]
    if dominant:
        flow_char += f" Dominant node: {dominant}."

    quincunx_routes = [e for e in edges if e.is_rerouted]
    open_arcs = [e for e in edges if e.is_open_arc]

    return ShapeCircuit(
        shape_type=shape_type,
        shape_id=shape_id,
        nodes=list(nodes.values()),
        edges=edges,
        total_throughput=round(total_throughput, 4),
        total_friction=round(total_friction, 4),
        dominant_node=dominant,
        bottleneck_node=bottleneck,
        resonance_score=resonance_score,
        friction_score=friction_score,
        flow_characterization=flow_char,
        membrane_class=topology.get("membrane_class") or "",
        quincunx_routes=quincunx_routes,
        open_arcs=open_arcs,
    )


# ---------------------------------------------------------------------------
# Chart singletons (planets not in any shape)
# ---------------------------------------------------------------------------

def _find_singletons(chart: AstrologicalChart, shape_member_names: set) -> List[str]:
    """Return planet names that appear in no shape."""
    all_names: List[str] = []
    for obj in chart.objects:
        name = obj.object_name
        if hasattr(name, "name"):
            name = name.name
        all_names.append(str(name))
    return [n for n in all_names if n not in shape_member_names]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate_circuit(chart: AstrologicalChart) -> CircuitSimulation:
    """
    Run the full circuit power simulation on a chart.

    Requires:
        chart.planetary_states — populated by dignity_calc.score_and_attach()
        chart.shapes           — populated by drawing_v2.get_shapes() or similar
        chart.mutual_receptions — populated by dignity_calc.score_and_attach()

    Returns a CircuitSimulation object (does not mutate the chart).
    """
    shapes: list = chart.shapes or []
    planetary_states: dict = chart.planetary_states or {}
    mutual_receptions: list = chart.mutual_receptions or []

    shape_circuits: List[ShapeCircuit] = []
    all_edges_flat: List[CircuitEdge] = []
    global_node_map: Dict[str, CircuitNode] = {}
    shape_member_names: set = set()

    mr_names = _mutual_reception_names(mutual_receptions)

    # --- Simulate each shape ---
    for shape in shapes:
        sc = _simulate_shape(shape, planetary_states, mutual_receptions)
        shape_circuits.append(sc)

        members = shape.get("members", [])
        shape_member_names.update(members)

        all_edges_flat.extend(sc.edges)

        # Merge nodes into global map; keep highest effective_power on collision.
        for node in sc.nodes:
            existing = global_node_map.get(node.planet_name)
            if existing is None or node.effective_power > existing.effective_power:
                global_node_map[node.planet_name] = node

    # --- Ensure every planet in planetary_states has a node entry ---
    for name in planetary_states:
        if name not in global_node_map:
            n = _build_node(name, planetary_states, mr_names)
            n.effective_power = n.power_index  # no circuit contribution
            global_node_map[name] = n

    # --- SN→NN directional path ---
    sn_nn_path = _find_sn_nn_path_in_simulation(global_node_map, all_edges_flat)

    # --- Apply SN→NN boost and re-propagate affected shape circuits ---
    if sn_nn_path:
        path_pairs = set()
        for i in range(len(sn_nn_path) - 1):
            path_pairs.add(frozenset([sn_nn_path[i], sn_nn_path[i + 1]]))

        for sc in shape_circuits:
            affected = any(
                frozenset([e.node_a, e.node_b]) in path_pairs for e in sc.edges
            )
            if affected:
                _apply_sn_nn_boost(sc.edges, sn_nn_path)
                # Reset and re-propagate.
                node_dict = {n.planet_name: n for n in sc.nodes}
                for n in node_dict.values():
                    n.received_power = 0.0
                    n.friction_load = 0.0
                    n.effective_power = 0.0
                _propagate_power(node_dict, sc.edges)
                # Refresh aggregate metrics.
                sc.total_throughput = round(sum(e.transmitted_power for e in sc.edges), 4)
                sc.total_friction = round(sum(e.friction_heat for e in sc.edges), 4)
                # Update dominant/bottleneck.
                sorted_p = sorted(node_dict.values(), key=lambda n: n.effective_power, reverse=True)
                if sorted_p:
                    sc.dominant_node = sorted_p[0].planet_name
                sorted_f = sorted(node_dict.values(), key=lambda n: n.friction_load, reverse=True)
                if sorted_f:
                    sc.bottleneck_node = sorted_f[0].planet_name
                # Refresh global node map.
                for node in node_dict.values():
                    existing = global_node_map.get(node.planet_name)
                    if existing is None or node.effective_power > existing.effective_power:
                        global_node_map[node.planet_name] = node

    singletons = _find_singletons(chart, shape_member_names)

    return CircuitSimulation(
        shape_circuits=shape_circuits,
        node_map=global_node_map,
        sn_nn_path=sn_nn_path,
        singletons=singletons,
        mutual_receptions=mutual_receptions,
    )


def simulate_and_attach(chart: AstrologicalChart) -> None:
    """
    Convenience wrapper: run simulate_circuit() and store the result on chart.
    Safe to call even if chart.shapes is empty — returns an empty simulation.
    """
    try:
        result = simulate_circuit(chart)
    except Exception as exc:  # noqa: BLE001
        # Never crash the main pipeline — store None silently.
        import traceback
        traceback.print_exc()
        result = None
    chart.circuit_simulation = result
