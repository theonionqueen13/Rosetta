#!/usr/bin/env python3
"""
Rosetta DAG — Auto-generate graph_data.json from the codebase AST.

Walks all .py files in the workspace root and src/ directory, parses each
file's AST to extract modules, classes, top-level functions, and import
edges.  Outputs a Cytoscape.js-compatible JSON file.

Usage:
    python rosetta_dag/generate_graph.py
"""

import ast
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parent.parent  # one level up from rosetta_dag/
OUTPUT = Path(__file__).resolve().parent / "data" / "graph_data.json"

# Directories to scan (relative to WORKSPACE)
SCAN_DIRS = [
    ".",       # top-level .py files
    "src",     # src/ sub-package
    "tests",   # test files
    "scripts", # utility scripts
]

# Files/dirs to skip
SKIP_FILES = {"__init__.py", "setup.py", "conftest.py"}
SKIP_DIRS  = {"__pycache__", ".venv", "venv", "ephe",
              "rosetta_dag", "New folder", "pngs", "sabian_data", "node_modules"}

# Layer classification heuristics — checked in order, first match wins
LAYER_RULES = [
    # (condition_fn,  layer_name)
    (lambda m, imps: m.startswith("tests/") or m.startswith("test_"),  "test"),
    (lambda m, imps: m.startswith("scripts/"),                          "script"),
    (lambda m, imps: any(x in imps for x in ["db_access", "psycopg2", "supabase"]) or
                     "postgres" in m or "migration" in m or "export_static" in m or
                     "db_access" in m or "static_db_to" in m,          "db"),
    (lambda m, imps: any(x in imps for x in ["swisseph", "pyswisseph"]) or
                     "calc_v2" == m.replace(".py",""),                   "calc"),
    (lambda m, imps: "patterns_v2" == m.replace(".py","") or
                     "profiles_v2" == m.replace(".py",""),              "calc"),
    (lambda m, imps: "drawing" in m or "drawing_primitives" in m,       "rendering"),
    (lambda m, imps: "dispositor_graph" in m,                           "rendering"),
    (lambda m, imps: "lookup_v2" in m or "models_v2" in m or
                     "chart_models" in m or "data_helpers" in m or
                     "data_stubs" in m,                                 "data"),
    (lambda m, imps: "nicegui_state" in m,                              "data"),
    (lambda m, imps: m == "app",                                        "orchestration"),
    (lambda m, imps: "mcp" in m,                                         "mcp"),
    (lambda m, imps: m.startswith("src/ui/"),                            "ui"),
    (lambda m, imps: "geocoding" in m,                                  "orchestration"),
    (lambda m, imps: "interp" in m,                                     "calc"),
    (lambda m, imps: "event_lookup" in m,                               "calc"),
    # Generic nicegui-import fallback — must be last so name-based rules win
    (lambda m, imps: any(x in imps for x in ["nicegui"]),               "ui"),
]

LAYER_COLORS = {
    "data":          "#4A90D9",
    "calc":          "#E8873A",
    "rendering":     "#5CB85C",
    "ui":            "#9B59B6",
    "orchestration": "#F1C40F",
    "db":            "#95A5A6",
    "test":          "#1ABC9C",
    "script":        "#7F8C8D",
    "mcp":           "#E74C3C",
    "unknown":       "#BDC3C7",
}

LAYER_DESCRIPTIONS = {
    "data":          "Core data layer — models, lookup tables, helpers",
    "calc":          "Calculation engine — chart computation, patterns, profiles",
    "rendering":     "Rendering — Matplotlib chart drawing",
    "ui":            "UI components — NiceGUI pages and components",
    "orchestration": "Orchestration — wires calc → render → display",
    "db":            "Database & migration scripts",
    "test":          "Test files",
    "script":        "Utility / one-off scripts",
    "mcp":           "MCP pipeline — topic maps, reading engine, LLM synthesis",
    "unknown":       "Unclassified",
}


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------
def _resolve_module_id(filepath: Path) -> str:
    """Return a clean module ID like 'calc_v2' or 'src/ui/layout'."""
    rel = filepath.relative_to(WORKSPACE)
    parts = rel.with_suffix("").parts
    # top-level → just filename;  src/x → 'src/x'
    if len(parts) == 1:
        return parts[0]
    return "/".join(parts)


def _get_docstring(node) -> str:
    """Extract the docstring from a module/class/function node."""
    try:
        return ast.get_docstring(node) or ""
    except Exception:
        return ""


def _collect_imports(tree: ast.Module) -> set:
    """Collect all imported module names (stdlib + local)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split(".")[0])
    return names


def _resolve_local_edges(tree: ast.Module, module_id: str, known_modules: set) -> list:
    """
    Return list of (source_module_id, target_module_id, relationship) tuples
    for all imports that resolve to a local module in the workspace.
    """
    edges = []
    for node in ast.walk(tree):
        target = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                # handle 'from src.mcp.chat_ui import ...'  →  'src/mcp/chat_ui'
                # Try longest match first, then shorten until found
                parts = node.module.split(".")
                target = None
                for depth in range(len(parts), 0, -1):
                    candidate = "/".join(parts[:depth])
                    if candidate in known_modules:
                        target = candidate
                        break
                if target is None:
                    target = parts[0]

        if target and target in known_modules and target != module_id:
            edges.append((module_id, target, "imports"))
    # deduplicate
    return list(set(edges))


def _classify_layer(module_id: str, imports: set) -> str:
    """Classify a module into a layer using heuristics."""
    for cond, layer in LAYER_RULES:
        try:
            if cond(module_id, imports):
                return layer
        except Exception:
            continue
    return "unknown"


def _extract_children(tree: ast.Module, module_id: str) -> list:
    """Extract classes and top-level functions as child nodes."""
    children = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(item.name)
            children.append({
                "id":        f"{module_id}::{node.name}",
                "label":     node.name,
                "type":      "class",
                "parent":    module_id,
                "docstring": _get_docstring(node),
                "methods":   methods,
                "line_start": node.lineno,
                "line_end":   node.end_lineno or node.lineno,
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # skip private helpers that start with __ except __init__
            decorators = []
            for dec in node.decorator_list:
                if isinstance(dec, ast.Name):
                    decorators.append(dec.id)
                elif isinstance(dec, ast.Attribute):
                    decorators.append(f"{getattr(dec.value, 'id', '?')}.{dec.attr}")

            children.append({
                "id":         f"{module_id}::{node.name}",
                "label":      node.name,
                "type":       "function",
                "parent":     module_id,
                "docstring":  _get_docstring(node),
                "decorators": decorators,
                "line_start": node.lineno,
                "line_end":   node.end_lineno or node.lineno,
            })
    return children


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def scan_workspace():
    """Walk the workspace recursively and collect all parsable .py files."""
    py_files = []
    seen = set()
    for scan_dir in SCAN_DIRS:
        target = WORKSPACE / scan_dir if scan_dir != "." else WORKSPACE
        if not target.exists():
            continue
        for item in sorted(target.rglob("*.py")):
            # Skip any path component that is in SKIP_DIRS
            if any(part in SKIP_DIRS for part in item.parts):
                continue
            if item.name in SKIP_FILES:
                continue
            if item in seen:
                continue
            seen.add(item)
            py_files.append(item)
    return py_files


def build_graph():
    py_files = scan_workspace()
    print(f"Found {len(py_files)} Python files to parse.")

    # First pass: collect module IDs so we can resolve local imports
    module_map = {}  # module_id → filepath
    for fp in py_files:
        mid = _resolve_module_id(fp)
        module_map[mid] = fp
    known_modules = set(module_map.keys())

    nodes = []
    edges = []

    # Second pass: parse each file
    for mid, fp in sorted(module_map.items()):
        try:
            source = fp.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(fp))
        except SyntaxError as e:
            print(f"  SKIP {mid}: SyntaxError - {e}")
            continue

        line_count = len(source.splitlines())
        imports = _collect_imports(tree)
        layer = _classify_layer(mid, imports)
        docstring = _get_docstring(tree)
        children = _extract_children(tree, mid)

        # Module (compound/parent) node
        nodes.append({
            "data": {
                "id":          mid,
                "label":       mid.split("/")[-1],
                "full_path":   str(fp.relative_to(WORKSPACE)),
                "abs_path":    str(fp),
                "type":        "module",
                "layer":       layer,
                "layer_color": LAYER_COLORS.get(layer, LAYER_COLORS["unknown"]),
                "docstring":   (docstring[:300] + "…") if len(docstring) > 300 else docstring,
                "line_count":  line_count,
                "class_count": sum(1 for c in children if c["type"] == "class"),
                "func_count":  sum(1 for c in children if c["type"] == "function"),
                "child_ids":   [c["id"] for c in children],
            }
        })

        # Child nodes (hidden by default — the JS side handles expand/collapse)
        for child in children:
            nodes.append({
                "data": {
                    "id":          child["id"],
                    "label":       child["label"],
                    "type":        child["type"],
                    "parent_module": mid,
                    "layer":       layer,
                    "layer_color": LAYER_COLORS.get(layer, LAYER_COLORS["unknown"]),
                    "docstring":   (child["docstring"][:200] + "…") if len(child.get("docstring","")) > 200 else child.get("docstring",""),
                    "line_start":  child.get("line_start"),
                    "line_end":    child.get("line_end"),
                    "methods":     child.get("methods", []),
                    "decorators":  child.get("decorators", []),
                }
            })

        # Import edges
        local_edges = _resolve_local_edges(tree, mid, known_modules)
        for src, tgt, rel in local_edges:
            edges.append({
                "data": {
                    "id":           f"{src}→{tgt}",
                    "source":       src,
                    "target":       tgt,
                    "relationship": rel,
                }
            })

    # Deduplicate edges by id
    seen_edge_ids = set()
    unique_edges = []
    for e in edges:
        eid = e["data"]["id"]
        if eid not in seen_edge_ids:
            seen_edge_ids.add(eid)
            unique_edges.append(e)

    graph = {
        "metadata": {
            "generated_by": "rosetta_dag/generate_graph.py",
            "workspace":    str(WORKSPACE),
            "module_count": sum(1 for n in nodes if n["data"]["type"] == "module"),
            "child_count":  sum(1 for n in nodes if n["data"]["type"] in ("class", "function")),
            "edge_count":   len(unique_edges),
            "layers":       {k: {"color": v, "description": LAYER_DESCRIPTIONS.get(k,"")}
                             for k, v in LAYER_COLORS.items()},
        },
        "elements": {
            "nodes": nodes,
            "edges": unique_edges,
        }
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Wrote {OUTPUT}")
    print(f"  Modules: {graph['metadata']['module_count']}")
    print(f"  Classes + Functions: {graph['metadata']['child_count']}")
    print(f"  Import edges: {graph['metadata']['edge_count']}")
    # Layer summary
    from collections import Counter
    layer_counts = Counter(n["data"]["layer"] for n in nodes if n["data"]["type"] == "module")
    for layer, cnt in sorted(layer_counts.items()):
        print(f"    {layer}: {cnt} modules")


if __name__ == "__main__":
    build_graph()
