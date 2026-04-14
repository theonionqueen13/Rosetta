"""Tests for src/core/patterns_v2.py — aspect matching, components, shape detection."""
import pytest

from src.core.patterns_v2 import (
    aspect_match,
    connected_components_from_edges,
    detect_shapes,
    generate_combo_groups,
    positions_from_dataframe,
    edges_from_major_list,
    ASPECTS,
)


# ═══════════════════════════════════════════════════════════════════════
# aspect_match
# ═══════════════════════════════════════════════════════════════════════

class TestAspectMatch:
    @pytest.fixture
    def trine_pos(self):
        """Two planets exactly 120° apart (Trine)."""
        return {"A": 0.0, "B": 120.0}

    @pytest.fixture
    def square_pos(self):
        """Two planets exactly 90° apart (Square)."""
        return {"A": 0.0, "B": 90.0}

    def test_exact_trine(self, trine_pos):
        assert aspect_match(trine_pos, "A", "B", "Trine") is True

    def test_exact_square(self, square_pos):
        assert aspect_match(square_pos, "A", "B", "Square") is True

    def test_not_matching(self, trine_pos):
        assert aspect_match(trine_pos, "A", "B", "Square") is False

    def test_within_orb(self):
        # ASPECTS["Trine"] should have an orb (typically ~8°)
        orb = ASPECTS["Trine"]["orb"]
        pos = {"A": 0.0, "B": 120.0 + orb - 0.5}
        assert aspect_match(pos, "A", "B", "Trine") is True

    def test_outside_orb(self):
        orb = ASPECTS["Trine"]["orb"]
        pos = {"A": 0.0, "B": 120.0 + orb + 1.0}
        assert aspect_match(pos, "A", "B", "Trine") is False

    def test_opposition(self):
        pos = {"A": 10.0, "B": 190.0}
        assert aspect_match(pos, "A", "B", "Opposition") is True

    def test_conjunction(self):
        pos = {"A": 100.0, "B": 101.0}
        assert aspect_match(pos, "A", "B", "Conjunction") is True

    def test_sextile(self):
        pos = {"A": 0.0, "B": 60.0}
        assert aspect_match(pos, "A", "B", "Sextile") is True


# ═══════════════════════════════════════════════════════════════════════
# connected_components_from_edges
# ═══════════════════════════════════════════════════════════════════════

class TestConnectedComponents:
    def test_single_component(self):
        nodes = ["A", "B", "C"]
        edges = [(("A", "B"), "Trine"), (("B", "C"), "Sextile")]
        comps = connected_components_from_edges(nodes, edges)
        assert len(comps) == 1
        assert comps[0] == {"A", "B", "C"}

    def test_two_components(self):
        nodes = ["A", "B", "C", "D"]
        edges = [(("A", "B"), "Trine"), (("C", "D"), "Square")]
        comps = connected_components_from_edges(nodes, edges)
        assert len(comps) == 2

    def test_isolated_nodes_excluded(self):
        nodes = ["A", "B", "C"]
        edges = [(("A", "B"), "Trine")]
        comps = connected_components_from_edges(nodes, edges)
        # C has no edges, so it should NOT form its own component
        members = set()
        for c in comps:
            members.update(c)
        assert "C" not in members

    def test_empty(self):
        comps = connected_components_from_edges([], [])
        assert comps == []


# ═══════════════════════════════════════════════════════════════════════
# detect_shapes — Grand Trine
# ═══════════════════════════════════════════════════════════════════════

class TestDetectShapesGrandTrine:
    @pytest.fixture
    def grand_trine_data(self):
        """Three planets 120° apart → Grand Trine."""
        pos = {"A": 0.0, "B": 120.0, "C": 240.0}
        edges = [
            (("A", "B"), "Trine"),
            (("B", "C"), "Trine"),
            (("A", "C"), "Trine"),
        ]
        patterns = [{"A", "B", "C"}]
        return pos, patterns, edges

    def test_grand_trine_detected(self, grand_trine_data):
        pos, patterns, edges = grand_trine_data
        shapes = detect_shapes(pos, patterns, edges)
        shape_types = [s.shape_type for s in shapes]
        assert "Grand Trine" in shape_types

    def test_grand_trine_members(self, grand_trine_data):
        pos, patterns, edges = grand_trine_data
        shapes = detect_shapes(pos, patterns, edges)
        gt = next(s for s in shapes if s.shape_type == "Grand Trine")
        assert set(gt.members) == {"A", "B", "C"}


# ═══════════════════════════════════════════════════════════════════════
# detect_shapes — T-Square
# ═══════════════════════════════════════════════════════════════════════

class TestDetectShapesTSquare:
    @pytest.fixture
    def t_square_data(self):
        """Opposition (A-B) + two Squares from C → T-Square."""
        pos = {"A": 0.0, "B": 180.0, "C": 90.0}
        edges = [
            (("A", "B"), "Opposition"),
            (("A", "C"), "Square"),
            (("B", "C"), "Square"),
        ]
        patterns = [{"A", "B", "C"}]
        return pos, patterns, edges

    def test_t_square_detected(self, t_square_data):
        pos, patterns, edges = t_square_data
        shapes = detect_shapes(pos, patterns, edges)
        shape_types = [s.shape_type for s in shapes]
        assert "T-Square" in shape_types


# ═══════════════════════════════════════════════════════════════════════
# detect_shapes — no shape
# ═══════════════════════════════════════════════════════════════════════

class TestDetectShapesNone:
    def test_single_aspect_only_remainder(self):
        """A single trine with two planets should only produce a Remainder shape."""
        pos = {"A": 0.0, "B": 120.0}
        edges = [(("A", "B"), "Trine")]
        patterns = [{"A", "B"}]
        shapes = detect_shapes(pos, patterns, edges)
        named_shapes = [s for s in shapes if s.shape_type != "Remainder"]
        assert named_shapes == []


# ═══════════════════════════════════════════════════════════════════════
# edges_from_major_list
# ═══════════════════════════════════════════════════════════════════════

class TestEdgesFromMajorList:
    def test_converts_3_tuples(self):
        major = [
            ("Sun", "Moon", {"aspect": "Trine", "orb": 2.0}),
            ("Mars", "Jupiter", {"aspect": "Square", "orb": 1.5}),
        ]
        result = edges_from_major_list(major)
        assert len(result) == 2
        assert result[0] == (("Sun", "Moon"), "Trine")
        assert result[1] == (("Mars", "Jupiter"), "Square")

    def test_empty(self):
        assert edges_from_major_list([]) == []
        assert edges_from_major_list(None) == []


# ═══════════════════════════════════════════════════════════════════════
# generate_combo_groups
# ═══════════════════════════════════════════════════════════════════════

class TestGenerateComboGroups:
    def test_linked_patterns(self):
        filaments = [
            ("A", "B", "Trine", 0, 1),
            ("C", "D", "Square", 1, 2),
        ]
        groups = generate_combo_groups(filaments)
        # Patterns 0-1 linked, 1-2 linked → all three connected
        assert len(groups) == 1
        assert set(groups[0]) == {0, 1, 2}

    def test_no_cross_links(self):
        filaments = [
            ("A", "B", "Trine", 0, 0),  # same pattern, no cross-link
        ]
        groups = generate_combo_groups(filaments)
        assert groups == []

    def test_empty(self):
        groups = generate_combo_groups([])
        assert groups == []


# ═══════════════════════════════════════════════════════════════════════
# Integration: detect_shapes with sample_chart fixture
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestDetectShapesIntegration:
    def test_with_real_chart(self, sample_chart):
        """Smoke test: detect_shapes should not crash on a real chart."""
        from src.core.patterns_v2 import prepare_pattern_inputs
        from src.core.calc_v2 import build_aspect_edges

        edges_major, _, _ = build_aspect_edges(sample_chart)
        pos = {}
        for obj in sample_chart.objects:
            if obj.object_name:
                pos[obj.object_name.name] = obj.longitude
        formatted_edges = edges_from_major_list(edges_major)
        patterns = connected_components_from_edges(list(pos.keys()), formatted_edges)
        shapes = detect_shapes(pos, patterns, formatted_edges)
        assert isinstance(shapes, list)
        # Each shape should have shape_type, members, edges attributes
        for s in shapes:
            assert hasattr(s, "shape_type") or "type" in s
            assert hasattr(s, "members") or "members" in s
