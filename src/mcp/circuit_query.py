"""
circuit_query.py — Circuit Subgraph Extraction
===============================================
Given a ``QuestionGraph`` and a ``CircuitSimulation``, extract the
relevant power-flow subgraph that answers the user's question.

Extraction rules by question_type
----------------------------------
  single_focus
      All shapes containing any focus factor.  Return full shape data,
      not just the filtered nodes.

  relationship
      For each concept cluster pair, find every shape that contains
      factors from *either* cluster.  If both clusters share a shape,
      that is a *direct connection*.  If not, scan the global node_map
      for any bridging aspects between clusters.  Always include
      **entire shapes** — never trim to just the shortest path.

  multi_node
      Union of all shapes containing any factor from any node.

  open_exploration
      Top shapes by throughput + SN→NN path + dominant/bottleneck.

Public API
----------
  query_circuit(question_graph, chart) → CircuitReading
"""

from __future__ import annotations

import os
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.mcp.comprehension import QuestionGraph

if TYPE_CHECKING:
    from models_v2 import AstrologicalChart, CircuitSimulation, CircuitNode, ShapeCircuit, CircuitEdge


# ═══════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class CircuitPath:
    """A traced path between two concept clusters inside the circuit."""
    from_concept: str           # label of source concept node
    to_concept: str             # label of target concept node
    path_planets: List[str] = field(default_factory=list)    # planet names along the path
    path_aspects: List[str] = field(default_factory=list)    # aspect types along the path
    total_conductance: float = 0.0
    connection_quality: str = ""   # "direct_shape", "bridged", "isolated"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "from": self.from_concept,
            "to": self.to_concept,
            "quality": self.connection_quality,
        }
        if self.path_planets:
            d["path"] = " → ".join(self.path_planets)
        if self.path_aspects:
            d["aspects"] = self.path_aspects
        if self.total_conductance:
            d["conductance"] = round(self.total_conductance, 3)
        return d


@dataclass
class CircuitReading:
    """The query result: a circuit subgraph focused on the question."""

    # Full shapes containing relevant factors (entire shapes, not trimmed)
    relevant_shapes: list = field(default_factory=list)           # List[ShapeCircuit]
    # The specific circuit nodes the question targets
    focus_nodes: list = field(default_factory=list)               # List[CircuitNode]
    # Traced paths between concept clusters (for relationship queries)
    connecting_paths: List[CircuitPath] = field(default_factory=list)
    # Power summary
    power_summary: Dict[str, Any] = field(default_factory=dict)
    # SN→NN relevance — note if path crosses queried factors
    sn_nn_relevance: str = ""
    # Isolation notes — when queried factors aren't circuited together
    isolation_notes: List[str] = field(default_factory=list)
    # Deterministic narrative seeds from circuit data
    narrative_seeds: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.relevant_shapes:
            d["shapes"] = [_shape_to_dict(s) for s in self.relevant_shapes]
        if self.focus_nodes:
            d["focus_nodes"] = [_node_to_dict(n) for n in self.focus_nodes]
        if self.connecting_paths:
            d["paths"] = [p.to_dict() for p in self.connecting_paths]
        if self.power_summary:
            d["power_summary"] = self.power_summary
        if self.sn_nn_relevance:
            d["sn_nn"] = self.sn_nn_relevance
        if self.isolation_notes:
            d["isolation"] = self.isolation_notes
        if self.narrative_seeds:
            d["narrative_seeds"] = self.narrative_seeds
        return d


# ═══════════════════════════════════════════════════════════════════════
# Serialization helpers
# ═══════════════════════════════════════════════════════════════════════

def _shape_to_dict(sc) -> Dict[str, Any]:
    """Serialize a ShapeCircuit to a compact dict for the reading packet."""
    return {
        "type": sc.shape_type,
        "id": sc.shape_id,
        "members": [n.planet_name for n in sc.nodes],
        "resonance": round(sc.resonance_score, 2),
        "friction": round(sc.friction_score, 2),
        "throughput": round(sc.total_throughput, 2),
        "flow": sc.flow_characterization,
        "dominant": sc.dominant_node,
        "bottleneck": sc.bottleneck_node,
        "open_arcs": len(sc.open_arcs),
        "rerouted_arcs": len(sc.quincunx_routes),
    }


def _node_to_dict(node) -> Dict[str, Any]:
    """Serialize a CircuitNode to a compact dict."""
    d: Dict[str, Any] = {
        "planet": node.planet_name,
        "power_index": round(node.power_index, 2),
        "effective_power": round(node.effective_power, 2),
    }
    if node.friction_load > 0.01:
        d["friction_load"] = round(node.friction_load, 2)
    if node.received_power > 0.01:
        d["received_power"] = round(node.received_power, 2)
    if node.is_source:
        d["role"] = "source (South Node)"
    elif node.is_sink:
        d["role"] = "sink (North Node)"
    if node.is_mutual_reception:
        d["mutual_reception"] = True
    return d


# ═══════════════════════════════════════════════════════════════════════
# Internal extraction logic
# ═══════════════════════════════════════════════════════════════════════

def _get_simulation(chart: "AstrologicalChart"):
    """Safely retrieve the CircuitSimulation from a chart."""
    sim = getattr(chart, "circuit_simulation", None)
    if sim is None:
        return None
    return sim


def _factors_to_planet_names(
    factors: List[str],
    chart: "AstrologicalChart",
) -> Set[str]:
    """
    Expand factor list (which may include houses/signs) into a set
    of chart-object names that are relevant.

    "6th House" → all planets in the 6th house.
    "Scorpio"   → all planets in Scorpio.
    "Sun"       → "Sun".
    """
    import re
    _HOUSE_RE = re.compile(r"^(\d+)\w*\s+[Hh]ouse$")
    _SIGN_NAMES = {
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    }

    names: Set[str] = set()
    target_houses: Set[int] = set()
    target_signs: Set[str] = set()

    for f in factors:
        m = _HOUSE_RE.match(f)
        if m:
            target_houses.add(int(m.group(1)))
        elif f in _SIGN_NAMES:
            target_signs.add(f)
        else:
            names.add(f)

    # Expand houses and signs from chart objects
    for cobj in chart.objects:
        obj_name = cobj.object_name.name if cobj.object_name else ""
        if not obj_name:
            continue
        # House match
        h = getattr(cobj, "placidus_house", None)
        if h and (getattr(h, "number", 0) in target_houses):
            names.add(obj_name)
        # Sign match
        sign = cobj.sign.name if cobj.sign else ""
        if sign in target_signs:
            names.add(obj_name)

    return names


def _shapes_containing(
    planet_names: Set[str],
    sim,
) -> list:
    """Return all ShapeCircuits that contain any of the named planets."""
    results = []
    for sc in (sim.shape_circuits or []):
        shape_members = {n.planet_name for n in sc.nodes}
        if shape_members & planet_names:
            results.append(sc)
    return results


def _nodes_for(planet_names: Set[str], sim) -> list:
    """Return CircuitNodes for the named planets."""
    return [
        sim.node_map[name]
        for name in planet_names
        if name in sim.node_map
    ]


def _bfs_between_clusters(
    cluster_a: Set[str],
    cluster_b: Set[str],
    sim,
) -> Optional[Tuple[List[str], List[str], float]]:
    """
    BFS across all conductive edges in the simulation to find the shortest
    path from any node in cluster_a to any node in cluster_b.

    Returns (path_planets, path_aspects, total_conductance) or None.
    """
    # Build adjacency from all edges in all shapes
    adj: Dict[str, List[Tuple[str, str, float]]] = {}
    for sc in (sim.shape_circuits or []):
        for edge in sc.edges:
            if edge.conductance > 0 or edge.is_rerouted:
                adj.setdefault(edge.node_a, []).append((edge.node_b, edge.aspect_type, edge.conductance))
                adj.setdefault(edge.node_b, []).append((edge.node_a, edge.aspect_type, edge.conductance))

    # BFS from all cluster_a nodes simultaneously
    visited: Dict[str, Tuple[List[str], List[str], float]] = {}
    queue: deque = deque()
    for start in cluster_a:
        if start in adj or start in sim.node_map:
            visited[start] = ([start], [], 1.0)
            queue.append(start)

    while queue:
        current = queue.popleft()
        cur_path, cur_aspects, cur_cond = visited[current]

        if current in cluster_b:
            return cur_path, cur_aspects, cur_cond

        for (neighbor, asp_type, cond) in adj.get(current, []):
            if neighbor not in visited:
                new_cond = min(cur_cond, cond)  # bottleneck conductance
                visited[neighbor] = (
                    cur_path + [neighbor],
                    cur_aspects + [asp_type],
                    new_cond,
                )
                queue.append(neighbor)

    return None


def _generate_narrative_seeds(
    focus_nodes: list,
    relevant_shapes: list,
    connecting_paths: List[CircuitPath],
    sn_nn_path: List[str],
    focus_names: Set[str],
) -> List[str]:
    """
    Generate deterministic prose fragments from circuit data.

    These are NOT LLM output — they are template-rendered from numbers.
    """
    from lookup_v2 import ASPECT_CONDUCTANCE

    seeds: List[str] = []

    # Shape flow descriptions
    for sc in relevant_shapes:
        seeds.append(
            f"The {sc.shape_type} ({', '.join(n.planet_name for n in sc.nodes)}) "
            f"has a resonance score of {sc.resonance_score:.0%} and friction score of "
            f"{sc.friction_score:.0%}. {sc.flow_characterization}"
        )

    # Focus node power descriptions
    for node in focus_nodes:
        desc = f"{node.planet_name}: power index {node.power_index:.1f}"
        if node.effective_power != node.power_index:
            desc += f", effective power {node.effective_power:.1f}"
        if node.friction_load > 0.01:
            desc += f", carrying {node.friction_load:.1f} friction load"
        if node.received_power > 0.01:
            desc += f", receiving {node.received_power:.1f} from connected nodes"
        seeds.append(desc)

    # Edge-level descriptions for focus nodes
    for sc in relevant_shapes:
        for edge in sc.edges:
            if edge.node_a in focus_names or edge.node_b in focus_names:
                cond_entry = ASPECT_CONDUCTANCE.get(edge.aspect_type, {})
                flow_type = cond_entry.get("flow_type", "connection")
                desc = (
                    f"{edge.node_a} {edge.aspect_type} {edge.node_b}: "
                    f"conductance {edge.conductance:.0%}, flow type '{flow_type}', "
                    f"transmitting {edge.transmitted_power:.1f} power"
                )
                if edge.friction_heat > 0.01:
                    desc += f" with {edge.friction_heat:.1f} friction heat"
                if edge.is_rerouted:
                    desc += f" (rerouted via {' → '.join(edge.reroute_path)})"
                elif edge.is_open_arc:
                    desc += " (OPEN ARC — no alternative conductive path)"
                seeds.append(desc)

    # Connection path descriptions
    for path in connecting_paths:
        if path.connection_quality == "direct_shape":
            seeds.append(
                f"'{path.from_concept}' and '{path.to_concept}' share a direct circuit: "
                f"{' → '.join(path.path_planets)} "
                f"(conductance {path.total_conductance:.0%})"
            )
        elif path.connection_quality == "bridged":
            seeds.append(
                f"'{path.from_concept}' connects to '{path.to_concept}' via a bridge: "
                f"{' → '.join(path.path_planets)} through {', '.join(path.path_aspects)} "
                f"(bottleneck conductance {path.total_conductance:.0%})"
            )
        elif path.connection_quality == "isolated":
            seeds.append(
                f"'{path.from_concept}' and '{path.to_concept}' have no conductive path "
                f"between them — they operate as independent systems."
            )

    # SN→NN path relevance
    if sn_nn_path and focus_names:
        overlap = set(sn_nn_path) & focus_names
        if overlap:
            seeds.append(
                f"The South Node → North Node growth path passes through "
                f"{', '.join(sorted(overlap))}, linking the queried topics "
                f"to the chart's core developmental arc."
            )

    return seeds


# ═══════════════════════════════════════════════════════════════════════
# Main extraction entry points
# ═══════════════════════════════════════════════════════════════════════

def _query_single_focus(
    graph: QuestionGraph,
    sim,
    chart: "AstrologicalChart",
) -> CircuitReading:
    """Extract circuit data for a single-focus question."""
    all_factors = set(graph.all_factors)
    planet_names = _factors_to_planet_names(list(all_factors), chart)

    relevant_shapes = _shapes_containing(planet_names, sim)
    focus_nodes = _nodes_for(planet_names, sim)

    sn_nn_path = sim.sn_nn_path or []
    narrative_seeds = _generate_narrative_seeds(
        focus_nodes, relevant_shapes, [], sn_nn_path, planet_names,
    )

    # Power summary
    power_summary = _build_power_summary(focus_nodes, relevant_shapes)

    # SN/NN relevance
    sn_nn_rel = ""
    overlap = set(sn_nn_path) & planet_names
    if overlap:
        sn_nn_rel = (
            f"The SN → NN developmental path includes "
            f"{', '.join(sorted(overlap))}."
        )

    return CircuitReading(
        relevant_shapes=relevant_shapes,
        focus_nodes=focus_nodes,
        power_summary=power_summary,
        sn_nn_relevance=sn_nn_rel,
        narrative_seeds=narrative_seeds,
    )


def _query_relationship(
    graph: QuestionGraph,
    sim,
    chart: "AstrologicalChart",
) -> CircuitReading:
    """
    Extract circuit data for a relationship question (how does X relate to Y).

    Always includes ENTIRE shapes containing any factor from either cluster.
    """
    # Build planet-name sets for each concept node
    cluster_names: List[Tuple[str, Set[str]]] = []
    for node in graph.nodes:
        names = _factors_to_planet_names(node.factors, chart)
        cluster_names.append((node.label, names))

    # Collect ALL shapes containing ANY factor from ANY cluster
    all_planet_names: Set[str] = set()
    for _, names in cluster_names:
        all_planet_names |= names

    relevant_shapes = _shapes_containing(all_planet_names, sim)
    focus_nodes = _nodes_for(all_planet_names, sim)

    # Trace paths between each pair of clusters
    connecting_paths: List[CircuitPath] = []
    isolation_notes: List[str] = []

    for i in range(len(cluster_names)):
        for j in range(i + 1, len(cluster_names)):
            label_a, names_a = cluster_names[i]
            label_b, names_b = cluster_names[j]

            # Check if they share any shapes (direct connection)
            shared_shapes = []
            for sc in relevant_shapes:
                members_set = {n.planet_name for n in sc.nodes}
                if (members_set & names_a) and (members_set & names_b):
                    shared_shapes.append(sc)

            if shared_shapes:
                # Direct shape connection — use the shape with highest throughput
                best = max(shared_shapes, key=lambda s: s.total_throughput)
                path_members = [n.planet_name for n in best.nodes]
                connecting_paths.append(CircuitPath(
                    from_concept=label_a,
                    to_concept=label_b,
                    path_planets=path_members,
                    path_aspects=[e.aspect_type for e in best.edges],
                    total_conductance=best.resonance_score,
                    connection_quality="direct_shape",
                ))
            else:
                # Try BFS bridge across all shapes
                bridge = _bfs_between_clusters(names_a, names_b, sim)
                if bridge:
                    path_planets, path_aspects, cond = bridge
                    connecting_paths.append(CircuitPath(
                        from_concept=label_a,
                        to_concept=label_b,
                        path_planets=path_planets,
                        path_aspects=path_aspects,
                        total_conductance=cond,
                        connection_quality="bridged",
                    ))
                else:
                    connecting_paths.append(CircuitPath(
                        from_concept=label_a,
                        to_concept=label_b,
                        connection_quality="isolated",
                    ))
                    # Only report isolation if every planet in BOTH clusters is a
                    # genuine singleton (not in any shape), per singleton_map — the
                    # authoritative record of unconnected planets.
                    singleton_map = getattr(chart, "singleton_map", None) or {}
                    all_isolated = (
                        all(n in singleton_map for n in names_a)
                        and all(n in singleton_map for n in names_b)
                    )
                    if all_isolated:
                        isolation_notes.append(
                            f"'{label_a}' and '{label_b}' are not conductively "
                            f"connected — they operate as separate electrical systems "
                            f"in this chart. This means these areas of life develop "
                            f"independently."
                        )

    sn_nn_path = sim.sn_nn_path or []
    narrative_seeds = _generate_narrative_seeds(
        focus_nodes, relevant_shapes, connecting_paths, sn_nn_path, all_planet_names,
    )

    power_summary = _build_power_summary(focus_nodes, relevant_shapes)

    sn_nn_rel = ""
    overlap = set(sn_nn_path) & all_planet_names
    if overlap:
        sn_nn_rel = (
            f"The SN → NN developmental path includes "
            f"{', '.join(sorted(overlap))}."
        )

    return CircuitReading(
        relevant_shapes=relevant_shapes,
        focus_nodes=focus_nodes,
        connecting_paths=connecting_paths,
        power_summary=power_summary,
        sn_nn_relevance=sn_nn_rel,
        isolation_notes=isolation_notes,
        narrative_seeds=narrative_seeds,
    )


def _query_multi_node(
    graph: QuestionGraph,
    sim,
    chart: "AstrologicalChart",
) -> CircuitReading:
    """Multi-node: union of all shapes + paths between all pairs."""
    # Reuse relationship logic — it already handles N clusters
    return _query_relationship(graph, sim, chart)


def _query_open_exploration(
    sim,
    chart: "AstrologicalChart",
) -> CircuitReading:
    """Open exploration: top shapes by throughput + SN→NN + summary."""
    all_shapes = list(sim.shape_circuits or [])
    sorted_shapes = sorted(all_shapes, key=lambda s: s.total_throughput, reverse=True)
    top_shapes = sorted_shapes[:5]  # Top 5 by throughput

    all_nodes = list(sim.node_map.values())
    # Focus on the most powerful and most friction-loaded
    sorted_by_power = sorted(all_nodes, key=lambda n: n.effective_power, reverse=True)
    focus_nodes = sorted_by_power[:8]  # Top 8 nodes

    sn_nn_path = sim.sn_nn_path or []
    focus_names = {n.planet_name for n in focus_nodes}
    narrative_seeds = _generate_narrative_seeds(
        focus_nodes, top_shapes, [], sn_nn_path, focus_names,
    )

    power_summary = _build_power_summary(all_nodes, all_shapes)

    sn_nn_rel = ""
    if sn_nn_path:
        sn_nn_rel = f"Developmental arc: {' → '.join(sn_nn_path)}"

    return CircuitReading(
        relevant_shapes=top_shapes,
        focus_nodes=focus_nodes,
        power_summary=power_summary,
        sn_nn_relevance=sn_nn_rel,
        narrative_seeds=narrative_seeds,
    )


def _build_power_summary(focus_nodes: list, shapes: list) -> Dict[str, Any]:
    """Compute aggregate power summary from nodes and shapes."""
    summary: Dict[str, Any] = {}

    if focus_nodes:
        dominant = max(focus_nodes, key=lambda n: n.effective_power)
        summary["dominant_node"] = dominant.planet_name
        summary["dominant_power"] = round(dominant.effective_power, 2)

        highest_friction = max(focus_nodes, key=lambda n: n.friction_load)
        if highest_friction.friction_load > 0.01:
            summary["highest_friction_node"] = highest_friction.planet_name
            summary["highest_friction"] = round(highest_friction.friction_load, 2)

    if shapes:
        most_resonant = max(shapes, key=lambda s: s.resonance_score)
        summary["most_resonant_shape"] = {
            "type": most_resonant.shape_type,
            "resonance": round(most_resonant.resonance_score, 2),
        }
        most_tense = max(shapes, key=lambda s: s.friction_score)
        if most_tense.friction_score > 0.3:
            summary["most_tense_shape"] = {
                "type": most_tense.shape_type,
                "friction": round(most_tense.friction_score, 2),
            }

    return summary


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def query_circuit(
    question_graph: QuestionGraph,
    chart: "AstrologicalChart",
) -> CircuitReading:
    """
    Query the chart's circuit simulation through the lens of a QuestionGraph.

    Parameters
    ----------
    question_graph : QuestionGraph
        Decomposed question (from ``comprehension.comprehend()``).
    chart : AstrologicalChart
        Chart with ``circuit_simulation`` populated.

    Returns
    -------
    CircuitReading
        Extracted circuit subgraph, paths, narrative seeds, etc.
    """
    sim = _get_simulation(chart)
    if sim is None:
        # No simulation data — return empty reading
        return CircuitReading(
            narrative_seeds=["Circuit simulation data is not available for this chart."],
        )

    q_type = question_graph.question_type

    if q_type == "open_exploration":
        return _query_open_exploration(sim, chart)
    elif q_type == "relationship":
        return _query_relationship(question_graph, sim, chart)
    elif q_type == "multi_node":
        return _query_multi_node(question_graph, sim, chart)
    else:
        # single_focus or fallback
        return _query_single_focus(question_graph, sim, chart)
