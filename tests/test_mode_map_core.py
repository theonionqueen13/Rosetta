"""Tests for src/mode_map_core.py — Mode Map DAG logic."""
from __future__ import annotations

import json

import pytest

from src.mode_map_core import (
    MODE_TREE,
    compute_active_ids,
    build_elements,
    render_mode_map_html,
)


# ═══════════════════════════════════════════════════════════════════════
# MODE_TREE structural validation
# ═══════════════════════════════════════════════════════════════════════

class TestModeTree:
    """Validate the MODE_TREE constant structure."""

    def test_entries_are_4_tuples(self):
        for entry in MODE_TREE:
            assert len(entry) == 4, f"Entry should be 4-tuple: {entry}"

    def test_ids_unique(self):
        ids = [e[0] for e in MODE_TREE]
        assert len(ids) == len(set(ids)), "Duplicate node IDs in MODE_TREE"

    def test_parent_ids_exist(self):
        """Every parent_id reference must point to a valid node."""
        node_ids = {e[0] for e in MODE_TREE}
        for node_id, _label, _cat, parents in MODE_TREE:
            for pid in parents:
                assert pid in node_ids, (
                    f"Node '{node_id}' references unknown parent '{pid}'"
                )

    def test_categories_are_known(self):
        known = {"input", "core", "chart_mode", "biwheel",
                 "circuit_sub", "toggle_group", "toggle_leaf"}
        for node_id, _label, category, _parents in MODE_TREE:
            assert category in known, (
                f"Node '{node_id}' has unknown category '{category}'"
            )

    def test_minimum_node_count(self):
        """Sanity: tree should have a reasonable number of nodes."""
        assert len(MODE_TREE) >= 20


# ═══════════════════════════════════════════════════════════════════════
# compute_active_ids — no chart
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActiveNoChart:
    """When has_chart=False, very few (if any) nodes are active."""

    def test_no_chart_minimal(self):
        active = compute_active_ids(has_chart=False)
        # No chart hubs should be active
        assert "single_chart" not in active
        assert "biwheel_chart" not in active

    def test_now_mode_without_chart(self):
        active = compute_active_ids(has_chart=False, now_mode_active=True)
        assert "input_now" in active
        assert "single_chart" not in active


# ═══════════════════════════════════════════════════════════════════════
# compute_active_ids — single chart, Standard mode
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActiveSingleStandard:
    """Single chart in Standard Chart mode."""

    def test_standard_mode_basics(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Standard Chart",
        )
        assert "single_chart" in active
        assert "sc_standard" in active
        assert "sc_circuits" not in active

    def test_standard_with_aspect_toggles(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Standard Chart",
            aspect_toggles={"Chiron": True},
        )
        assert "sc_addl_aspects" in active

    def test_standard_no_aspect_toggles(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Standard Chart",
            aspect_toggles={"Chiron": False},
        )
        assert "sc_addl_aspects" not in active


# ═══════════════════════════════════════════════════════════════════════
# compute_active_ids — single chart, Circuits mode
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActiveSingleCircuits:
    """Single chart in Circuits mode."""

    def test_circuits_mode_basics(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Circuits",
        )
        assert "sc_circuits" in active
        assert "sc_standard" not in active

    def test_circuit_toggles_active(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Circuits",
            pattern_toggles={0: True},
            num_patterns=3,
        )
        assert "sc_circuit_tg" in active

    def test_shape_toggles_active(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Circuits",
            shape_toggles={"T-Square": True},
        )
        assert "sc_shape_tg" in active

    def test_singleton_toggles_active(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Circuits",
            singleton_toggles={"Pluto": True},
        )
        assert "sc_planet_tg" in active

    def test_all_toggles_off(self):
        active = compute_active_ids(
            has_chart=True,
            chart_mode="Circuits",
            pattern_toggles={0: False},
            shape_toggles={},
            singleton_toggles={},
        )
        assert "sc_circuit_tg" not in active
        assert "sc_shape_tg" not in active
        assert "sc_planet_tg" not in active


# ═══════════════════════════════════════════════════════════════════════
# compute_active_ids — input mode flags
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActiveInputFlags:
    """Input mode flags: now_mode, profile_loaded, transit, synastry."""

    def test_now_mode(self):
        active = compute_active_ids(has_chart=True, now_mode_active=True)
        assert "input_now" in active

    def test_profile_loaded(self):
        active = compute_active_ids(has_chart=True, profile_loaded=True)
        assert "input_manager" in active

    def test_birth_input_default(self):
        active = compute_active_ids(
            has_chart=True, now_mode_active=False, profile_loaded=False,
        )
        assert "input_birth" in active

    def test_transit_mode(self):
        active = compute_active_ids(has_chart=True, transit_mode=True)
        assert "input_transit" in active
        assert "biwheel_chart" in active

    def test_synastry_mode(self):
        active = compute_active_ids(has_chart=True, synastry_mode=True)
        assert "input_synastry" in active
        assert "biwheel_chart" in active


# ═══════════════════════════════════════════════════════════════════════
# compute_active_ids — biwheel Standard
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActiveBiwheelStandard:
    """Biwheel in Standard Chart mode."""

    def test_biwheel_standard(self):
        active = compute_active_ids(
            has_chart=True,
            synastry_mode=True,
            chart_mode="Standard Chart",
        )
        assert "bw_standard" in active
        assert "bw_addl_aspects" in active

    def test_synastry_aspect_groups(self):
        active = compute_active_ids(
            has_chart=True,
            synastry_mode=True,
            chart_mode="Standard Chart",
            synastry_aspects_chart1=True,
            synastry_aspects_inter=True,
            synastry_aspects_chart2=True,
        )
        assert "bw_chart1_asp" in active
        assert "bw_inter_asp" in active
        assert "bw_chart2_asp" in active

    def test_synastry_inter_only_default(self):
        active = compute_active_ids(
            has_chart=True,
            synastry_mode=True,
            chart_mode="Standard Chart",
            synastry_aspects_inter=True,
        )
        assert "bw_inter_asp" in active
        assert "bw_chart1_asp" not in active
        assert "bw_chart2_asp" not in active


# ═══════════════════════════════════════════════════════════════════════
# compute_active_ids — biwheel Circuits (Combined / Connected)
# ═══════════════════════════════════════════════════════════════════════

class TestComputeActiveBiwheelCircuits:
    """Biwheel in Circuits mode — Combined vs Connected sub-modes."""

    def test_combined_circuits(self):
        active = compute_active_ids(
            has_chart=True,
            transit_mode=True,
            chart_mode="Circuits",
            circuit_submode="Combined",
        )
        assert "bw_circuits" in active
        assert "bw_combined" in active
        assert "bw_comb_shapes" in active
        assert "bw_connected" not in active

    def test_connected_circuits(self):
        active = compute_active_ids(
            has_chart=True,
            synastry_mode=True,
            chart_mode="Circuits",
            circuit_submode="Connected",
        )
        assert "bw_circuits" in active
        assert "bw_connected" in active
        assert "bw_cc_circ_tg" in active
        assert "bw_cc_shape_tg" in active
        assert "bw_cc_planet_tg" in active
        assert "bw_cc2_per_circ" in active
        assert "bw_cc2_per_shape" in active
        assert "bw_combined" not in active

    def test_combined_circuits_full_name(self):
        """'Combined Circuits' (full name) should work too."""
        active = compute_active_ids(
            has_chart=True,
            transit_mode=True,
            chart_mode="Circuits",
            circuit_submode="Combined Circuits",
        )
        assert "bw_combined" in active

    def test_connected_circuits_full_name(self):
        active = compute_active_ids(
            has_chart=True,
            synastry_mode=True,
            chart_mode="Circuits",
            circuit_submode="Connected Circuits",
        )
        assert "bw_connected" in active


# ═══════════════════════════════════════════════════════════════════════
# build_elements
# ═══════════════════════════════════════════════════════════════════════

class TestBuildElements:
    """Tests for the Cytoscape element builder."""

    def test_returns_list(self):
        elements = build_elements(set())
        assert isinstance(elements, list)
        assert len(elements) > 0

    def test_node_and_edge_structure(self):
        elements = build_elements(set())
        nodes = [e for e in elements if "source" not in e.get("data", {})]
        edges = [e for e in elements if "source" in e.get("data", {})]
        # Every MODE_TREE entry → 1 node
        assert len(nodes) == len(MODE_TREE)
        # Edges come from parents
        total_parents = sum(len(parents) for _, _, _, parents in MODE_TREE)
        assert len(edges) == total_parents

    def test_active_flag(self):
        active = {"single_chart", "sc_circuits"}
        elements = build_elements(active)
        for elem in elements:
            data = elem["data"]
            if data.get("id") in active:
                assert data["active"] is True
            elif "id" in data:
                assert data["active"] is False

    def test_count_labels(self):
        """When counts > 0, labels should include parenthetical counts."""
        elements = build_elements(set(), num_patterns=3, num_shapes=2, num_singletons=1)
        label_map = {e["data"]["id"]: e["data"]["label"]
                     for e in elements if "id" in e["data"]}
        assert "(3)" in label_map.get("sc_circuit_tg", "")
        assert "(2)" in label_map.get("sc_shape_tg", "")
        assert "(1)" in label_map.get("sc_planet_tg", "")

    def test_zero_counts_no_parens(self):
        elements = build_elements(set(), num_patterns=0, num_shapes=0, num_singletons=0)
        label_map = {e["data"]["id"]: e["data"]["label"]
                     for e in elements if "id" in e["data"]}
        assert "(" not in label_map.get("sc_circuit_tg", "")
        assert "(" not in label_map.get("sc_shape_tg", "")
        assert "(" not in label_map.get("sc_planet_tg", "")


# ═══════════════════════════════════════════════════════════════════════
# render_mode_map_html
# ═══════════════════════════════════════════════════════════════════════

class TestRenderModeMapHtml:
    """Smoke tests for the complete HTML builder."""

    def test_returns_string(self):
        html = render_mode_map_html()
        assert isinstance(html, str)

    def test_placeholders_replaced(self):
        html = render_mode_map_html()
        assert "%%ELEMENTS%%" not in html
        assert "%%HEIGHT%%" not in html

    def test_contains_cytoscape_script(self):
        html = render_mode_map_html()
        assert "cytoscape" in html.lower()

    def test_contains_elements_json(self):
        html = render_mode_map_html(has_chart=True, chart_mode="Circuits")
        # The JSON elements should be embedded — parseable substring
        assert '"id":' in html
        assert '"category":' in html

    def test_height_within_bounds(self):
        html = render_mode_map_html()
        # Height should be between 480 and 700
        # Extract from the HTML: height: NNNpx
        import re
        m = re.search(r'height:\s*(\d+)px', html)
        if m:
            h = int(m.group(1))
            assert 480 <= h <= 700

    def test_active_nodes_reflected(self):
        html = render_mode_map_html(
            has_chart=True,
            chart_mode="Standard Chart",
        )
        # The JSON should contain "active": true for sc_standard
        assert '"active": true' in html or '"active":true' in html
