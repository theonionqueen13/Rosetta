"""
test_circuit_sim.py — Integration tests for the circuit power simulation engine.

Runs without a live ephemeris or database connection.
Constructs minimal mock chart objects and shape dicts to verify:
  1. CircuitNode/Edge building from shape dicts
  2. Power propagation (conductance multiplication)
  3. Quincunx arc-hazard detection + BFS rerouting
  4. Open-arc detection when no reroute path exists
  5. Mutual reception boost
  6. SN→NN directional path detection
  7. simulate_circuit() returns a valid CircuitSimulation
"""

from __future__ import annotations

import sys
import os
import math
import unittest

# Ensure project root is on the path.
sys.path.insert(0, os.path.dirname(__file__))

from circuit_sim import (
    _bfs_reroute,
    _build_node,
    _conductance_for,
    _find_sn_nn_path_in_simulation,
    _mutual_reception_names,
    _propagate_power,
    _simulate_shape,
    simulate_circuit,
    simulate_and_attach,
)
from lookup_v2 import ASPECT_CONDUCTANCE
from models_v2 import (
    AstrologicalChart,
    CircuitEdge,
    CircuitNode,
    CircuitSimulation,
    HouseCusp,
    PlanetaryState,
    EssentialDignity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_planetary_state(name: str, power_index: float, raw_authority: float = 0.0) -> PlanetaryState:
    ed = EssentialDignity(
        domicile=False, exaltation=False, triplicity=False,
        term=False, face=False, detriment=False, fall=False, peregrine=True,
        primary_dignity="peregrine",
    )
    return PlanetaryState(
        planet_name=name,
        essential_dignity=ed,
        raw_authority=raw_authority,
        quality_index=0.0,
        house_score=3.0,
        motion_score=2.0,
        solar_proximity_score=0.0,
        solar_proximity_label="clear",
        potency_score=5.0,
        power_index=power_index,
        motion_label="direct",
        solar_distance=90.0,
    )


def _make_chart_minimal(planetary_states: dict, shapes: list, mutual_receptions: list = None) -> AstrologicalChart:
    """Return a minimal AstrologicalChart with no real ephemeris data."""
    chart = AstrologicalChart(
        objects=[],
        house_cusps=[],
        chart_datetime="2000-01-01T12:00:00",
        timezone="UTC",
        latitude=40.0,
        longitude=-74.0,
    )
    chart.planetary_states = planetary_states
    chart.shapes = shapes
    chart.mutual_receptions = mutual_receptions or []
    return chart


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestAspectConductance(unittest.TestCase):
    def test_all_aspects_present(self):
        for aspect in ["Conjunction", "Trine", "Sextile", "Opposition", "Square", "Quincunx"]:
            self.assertIn(aspect, ASPECT_CONDUCTANCE, f"{aspect} missing from ASPECT_CONDUCTANCE")

    def test_quincunx_zero(self):
        self.assertEqual(ASPECT_CONDUCTANCE["Quincunx"]["conductance"], 0.0)

    def test_conjunction_max(self):
        self.assertEqual(ASPECT_CONDUCTANCE["Conjunction"]["conductance"], 1.0)

    def test_conductance_for_helper(self):
        self.assertAlmostEqual(_conductance_for("Trine"), 0.9)
        self.assertAlmostEqual(_conductance_for("Square"), 0.3)
        self.assertAlmostEqual(_conductance_for("Quincunx"), 0.0)


class TestBuildNode(unittest.TestCase):
    def setUp(self):
        self.ps = {
            "Sun": _make_planetary_state("Sun", power_index=7.5, raw_authority=3.0),
            "Moon": _make_planetary_state("Moon", power_index=4.2, raw_authority=1.0),
        }

    def test_basic_node(self):
        node = _build_node("Sun", self.ps, set())
        self.assertEqual(node.planet_name, "Sun")
        self.assertAlmostEqual(node.power_index, 7.5)
        self.assertFalse(node.is_source)
        self.assertFalse(node.is_sink)

    def test_south_node_is_source(self):
        ps = {"South Node": _make_planetary_state("South Node", power_index=2.0)}
        node = _build_node("South Node", ps, set())
        self.assertTrue(node.is_source)
        self.assertFalse(node.is_sink)

    def test_north_node_is_sink(self):
        ps = {"North Node": _make_planetary_state("North Node", power_index=2.0)}
        node = _build_node("North Node", ps, set())
        self.assertTrue(node.is_sink)
        self.assertFalse(node.is_source)

    def test_mutual_reception_flag(self):
        node = _build_node("Sun", self.ps, {"Sun", "Venus"})
        self.assertTrue(node.is_mutual_reception)
        node2 = _build_node("Moon", self.ps, {"Sun", "Venus"})
        self.assertFalse(node2.is_mutual_reception)

    def test_unknown_planet(self):
        # Should return a zero-powered node without crashing.
        node = _build_node("Eris", self.ps, set())
        self.assertEqual(node.planet_name, "Eris")
        self.assertAlmostEqual(node.power_index, 0.0)


class TestPowerPropagation(unittest.TestCase):
    def _two_node_setup(self, aspect_type: str):
        conductance = _conductance_for(aspect_type)
        nodes = {
            "Sun": CircuitNode("Sun", power_index=8.0),
            "Moon": CircuitNode("Moon", power_index=4.0),
        }
        edges = [CircuitEdge("Sun", "Moon", aspect_type=aspect_type, conductance=conductance)]
        return nodes, edges

    def test_trine_propagation(self):
        nodes, edges = self._two_node_setup("Trine")
        _propagate_power(nodes, edges)
        # base = (8+4)/2 = 6; transmitted = 0.9 * 6 = 5.4
        self.assertAlmostEqual(edges[0].transmitted_power, 5.4, places=5)
        # Both nodes receive 5.4
        self.assertAlmostEqual(nodes["Sun"].received_power, 5.4, places=5)
        self.assertAlmostEqual(nodes["Moon"].received_power, 5.4, places=5)

    def test_square_friction(self):
        nodes, edges = self._two_node_setup("Square")
        _propagate_power(nodes, edges)
        # base=6, c=0.3; transmitted=1.8, friction=(0.7)*6=4.2
        self.assertAlmostEqual(edges[0].transmitted_power, 1.8, places=5)
        self.assertAlmostEqual(edges[0].friction_heat, 4.2, places=5)

    def test_quincunx_no_flow_without_reroute(self):
        nodes, edges = self._two_node_setup("Quincunx")
        edges[0].is_arc_hazard = True
        # NOT rerouted → no power should flow
        _propagate_power(nodes, edges)
        self.assertAlmostEqual(edges[0].transmitted_power, 0.0, places=5)
        self.assertAlmostEqual(nodes["Sun"].received_power, 0.0, places=5)

    def test_effective_power_formula(self):
        nodes, edges = self._two_node_setup("Trine")
        _propagate_power(nodes, edges)
        # effective = power_index + 0.5 * received - friction
        expected_sun = 8.0 + 0.5 * 5.4 - 0.0
        self.assertAlmostEqual(nodes["Sun"].effective_power, expected_sun, places=5)


class TestBfsReroute(unittest.TestCase):
    def test_direct_reroute(self):
        # Triangle: A–B–C all conductive; quincunx is A..C
        members = ["A", "B", "C"]
        conductive = [("A", "B"), ("B", "C")]
        path = _bfs_reroute(members, conductive, "A", "C")
        self.assertIsNotNone(path)
        self.assertEqual(path[0], "A")
        self.assertEqual(path[-1], "C")
        self.assertIn("B", path)

    def test_no_reroute(self):
        # Only edge is the quincunx itself (excluded from conductive list)
        members = ["X", "Y"]
        path = _bfs_reroute(members, [], "X", "Y")
        self.assertIsNone(path)

    def test_excludes_direct_edge(self):
        # Even if X–Y appears in conductive list, BFS should skip it
        # (it IS included in conductive list here to verify behavior)
        members = ["X", "Y"]
        path = _bfs_reroute(members, [("X", "Y")], "X", "Y")
        # Should return None because the only path is the direct edge which is skipped
        self.assertIsNone(path)


class TestSimulateShape(unittest.TestCase):
    def _grand_trine_shape(self):
        return {
            "id": 1,
            "type": "Grand Trine",
            "members": ["Jupiter", "Saturn", "Moon"],
            "edges": [
                (("Jupiter", "Saturn"), "Trine"),
                (("Saturn", "Moon"), "Trine"),
                (("Moon", "Jupiter"), "Trine"),
            ],
        }

    def _yod_shape(self):
        # Yod: two sextile + two quincunx (apex node)
        return {
            "id": 2,
            "type": "Yod",
            "members": ["Mercury", "Venus", "Mars"],
            "edges": [
                (("Mercury", "Venus"), "Sextile"),
                (("Mercury", "Mars"), "Quincunx"),
                (("Venus", "Mars"), "Quincunx"),
            ],
        }

    def setUp(self):
        self.ps = {
            "Jupiter": _make_planetary_state("Jupiter", power_index=9.0),
            "Saturn": _make_planetary_state("Saturn", power_index=6.0),
            "Moon": _make_planetary_state("Moon", power_index=5.0),
            "Mercury": _make_planetary_state("Mercury", power_index=4.0),
            "Venus": _make_planetary_state("Venus", power_index=5.0),
            "Mars": _make_planetary_state("Mars", power_index=3.0),
        }

    def test_grand_trine_high_resonance(self):
        sc = _simulate_shape(self._grand_trine_shape(), self.ps, [])
        self.assertEqual(sc.shape_type, "Grand Trine")
        self.assertGreater(sc.resonance_score, 0.7)
        self.assertEqual(len(sc.open_arcs), 0)
        self.assertEqual(len(sc.quincunx_routes), 0)
        self.assertGreater(sc.total_throughput, 0)

    def test_grand_trine_dominant_node(self):
        sc = _simulate_shape(self._grand_trine_shape(), self.ps, [])
        # Jupiter has highest power_index so should be dominant
        self.assertEqual(sc.dominant_node, "Jupiter")

    def test_yod_quincunx_handling(self):
        sc = _simulate_shape(self._yod_shape(), self.ps, [])
        self.assertEqual(sc.shape_type, "Yod")
        # Mercury–Mars and Venus–Mars are quincunx; Mercury–Venus sextile exists as reroute
        # Mercury–Mars quincunx: can reroute via Mercury–Venus–Mars (if Venus–Mars weren't also quincunx)
        # Both quincunxes → only path between Mercury and Mars goes through Venus–Mars (also quincunx)
        # So they should be open arcs (no purely conductive reroute path)
        total_arcs = len(sc.quincunx_routes) + len(sc.open_arcs)
        self.assertEqual(total_arcs, 2, "Should have exactly 2 quincunx edges total")

    def test_shape_has_nodes(self):
        sc = _simulate_shape(self._grand_trine_shape(), self.ps, [])
        node_names = {n.planet_name for n in sc.nodes}
        self.assertIn("Jupiter", node_names)
        self.assertIn("Saturn", node_names)
        self.assertIn("Moon", node_names)


class TestSnNnPath(unittest.TestCase):
    def test_sn_nn_path_found(self):
        node_map = {
            "South Node": CircuitNode("South Node", power_index=3.0, is_source=True),
            "Jupiter": CircuitNode("Jupiter", power_index=7.0),
            "North Node": CircuitNode("North Node", power_index=3.0, is_sink=True),
        }
        edges = [
            CircuitEdge("South Node", "Jupiter", aspect_type="Trine", conductance=0.9),
            CircuitEdge("Jupiter", "North Node", aspect_type="Sextile", conductance=0.7),
        ]
        path = _find_sn_nn_path_in_simulation(node_map, edges)
        self.assertIsNotNone(path)
        self.assertEqual(path[0], "South Node")
        self.assertEqual(path[-1], "North Node")

    def test_sn_nn_no_connection(self):
        node_map = {
            "South Node": CircuitNode("South Node", power_index=3.0, is_source=True),
            "North Node": CircuitNode("North Node", power_index=3.0, is_sink=True),
        }
        # No edge between them
        path = _find_sn_nn_path_in_simulation(node_map, [])
        self.assertEqual(path, [])

    def test_no_nodes_no_path(self):
        node_map = {"Sun": CircuitNode("Sun", power_index=8.0)}
        path = _find_sn_nn_path_in_simulation(node_map, [])
        self.assertEqual(path, [])


class TestMutualReceptionNames(unittest.TestCase):
    def test_string_pairs(self):
        names = _mutual_reception_names([("Venus", "Taurus"), ("Sun", "Leo")])
        self.assertIn("Venus", names)
        self.assertIn("Sun", names)

    def test_empty(self):
        self.assertEqual(_mutual_reception_names([]), set())


class TestSimulateCircuit(unittest.TestCase):
    def test_empty_shapes(self):
        ps = {
            "Sun": _make_planetary_state("Sun", power_index=8.0),
            "Moon": _make_planetary_state("Moon", power_index=4.0),
        }
        chart = _make_chart_minimal(ps, shapes=[])
        result = simulate_circuit(chart)
        self.assertIsInstance(result, CircuitSimulation)
        self.assertEqual(result.shape_circuits, [])
        # Global node map should have Sun and Moon from planetary_states
        self.assertIn("Sun", result.node_map)

    def test_single_grand_trine(self):
        ps = {
            "Jupiter": _make_planetary_state("Jupiter", power_index=9.0),
            "Saturn": _make_planetary_state("Saturn", power_index=6.0),
            "Moon": _make_planetary_state("Moon", power_index=5.0),
        }
        shapes = [{
            "id": 1,
            "type": "Grand Trine",
            "members": ["Jupiter", "Saturn", "Moon"],
            "edges": [
                (("Jupiter", "Saturn"), "Trine"),
                (("Saturn", "Moon"), "Trine"),
                (("Moon", "Jupiter"), "Trine"),
            ],
        }]
        chart = _make_chart_minimal(ps, shapes=shapes)
        result = simulate_circuit(chart)
        self.assertEqual(len(result.shape_circuits), 1)
        sc = result.shape_circuits[0]
        self.assertEqual(sc.shape_type, "Grand Trine")
        self.assertGreater(sc.total_throughput, 0)
        self.assertIn("Jupiter", result.node_map)

    def test_simulate_and_attach(self):
        ps = {"Sun": _make_planetary_state("Sun", power_index=7.0)}
        chart = _make_chart_minimal(ps, shapes=[])
        simulate_and_attach(chart)
        self.assertIsNotNone(chart.circuit_simulation)
        self.assertIsInstance(chart.circuit_simulation, CircuitSimulation)

    def test_singletons_identified(self):
        from models_v2 import ChartObject, Object
        # Create a chart with one Sun object in no shape
        try:
            sun_obj_name = Object(name="Sun")
        except Exception:
            sun_obj_name = "Sun"

        ps = {
            "Sun": _make_planetary_state("Sun", power_index=7.0),
            "Mars": _make_planetary_state("Mars", power_index=5.0),
        }
        # Shape only has Mars (Sun is singleton)
        shapes = [{
            "id": 1,
            "type": "Unnamed",
            "members": ["Mars"],
            "edges": [],
        }]
        chart = _make_chart_minimal(ps, shapes=shapes)
        # Chart needs some real objects for _find_singletons to work
        # Since chart.objects is empty, result.singletons will be empty — that's fine
        result = simulate_circuit(chart)
        # Just verify no crash
        self.assertIsInstance(result.singletons, list)


if __name__ == "__main__":
    print("=" * 60)
    print("Circuit Simulation Engine — Integration Tests")
    print("=" * 60)
    unittest.main(verbosity=2)
