"""
generate_flow_nodes.py — Extract node stubs from source code for thought_flow.json.

Reads TermIntent constants, WIZARD_TARGETS domains, and SHAPE_COMPLETIONS
from the actual codebase and prints JSON fragments to stdout that can be
COPY-PASTED into the relevant tab section of thought_flow.json.

This script NEVER writes to thought_flow.json directly — authoring stays manual.

Usage:
    python generate_flow_nodes.py
"""

import json
import sys
import os

# ── Resolve project root so imports work ────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # Rosetta_v2/
sys.path.insert(0, ROOT)


def extract_term_intents():
    """Pull TermIntent constants from src/mcp/term_registry.py."""
    try:
        from src.mcp.term_registry import TermIntent
        intents = {k: v for k, v in vars(TermIntent).items() if not k.startswith("_")}
        nodes = []
        for name, value in intents.items():
            nodes.append({
                "id": f"intent_{name.lower()}",
                "label": name.replace("_", " ").title(),
                "type": "gate",
                "stage": "intent_check",
                "tabs": ["intent_routing"],
                "chart_modes": [],
                "status": "not-built",
                "description": f"TermIntent.{name} = \"{value}\"",
                "source_file": "src/mcp/term_registry.py",
                "source_line": None,
            })
        return nodes
    except Exception as e:
        print(f"[WARN] Could not extract TermIntent: {e}", file=sys.stderr)
        return []


def extract_wizard_targets():
    """Pull WIZARD_TARGETS domain keys from src/mcp/topic_maps.py."""
    try:
        from src.mcp.topic_maps import WIZARD_TARGETS
        nodes = []
        for i, (domain, config) in enumerate(WIZARD_TARGETS.items()):
            label = domain if isinstance(domain, str) else str(domain)
            nodes.append({
                "id": f"domain_{label.lower().replace(' ', '_').replace('&', 'and')}",
                "label": label,
                "type": "process",
                "stage": "domain",
                "tabs": ["topic_maps"],
                "chart_modes": [],
                "status": "not-built",
                "description": f"WIZARD_TARGETS domain #{i+1}",
                "source_file": "src/mcp/topic_maps.py",
                "source_line": None,
            })
        return nodes
    except Exception as e:
        print(f"[WARN] Could not extract WIZARD_TARGETS: {e}", file=sys.stderr)
        return []


def extract_shape_completions():
    """Pull SHAPE_COMPLETIONS keys from switch_points.py."""
    try:
        from switch_points import SHAPE_COMPLETIONS
        nodes = []
        for shape_name, info in SHAPE_COMPLETIONS.items():
            completes_to = info.get("completes_to", "?") if isinstance(info, dict) else str(info)
            nodes.append({
                "id": f"shape_{shape_name.lower().replace(' ', '_').replace('-', '_')}",
                "label": shape_name,
                "type": "process",
                "stage": "shape_detect",
                "tabs": ["switch_points"],
                "chart_modes": [],
                "status": "done",
                "description": f"Completes to: {completes_to}",
                "source_file": "switch_points.py",
                "source_line": None,
            })
        return nodes
    except Exception as e:
        print(f"[WARN] Could not extract SHAPE_COMPLETIONS: {e}", file=sys.stderr)
        return []


def main():
    sections = {
        "intent_routing_nodes": extract_term_intents(),
        "topic_map_nodes": extract_wizard_targets(),
        "switch_point_nodes": extract_shape_completions(),
    }

    print("=" * 60)
    print("  Thought-Flow Node Stubs — paste into thought_flow.json")
    print("=" * 60)

    for section_name, nodes in sections.items():
        print(f"\n// ── {section_name} ({len(nodes)} nodes) ──\n")
        for node in nodes:
            print(json.dumps(node, indent=2) + ",")

    total = sum(len(n) for n in sections.values())
    print(f"\n// Total: {total} node stubs generated.")


if __name__ == "__main__":
    main()
