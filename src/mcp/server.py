"""
server.py — MCP (Model Context Protocol) server for Rosetta.

Speaks JSON-RPC 2.0 over stdio, implementing the MCP specification:
  • tools/list   → returns TOOL_SCHEMAS
  • tools/call   → dispatches to tools.execute_tool()
  • initialize   → handshake
  • notifications/initialized → ack

Usage:
  python -m src.mcp.server                    # stdio mode (for MCP clients)
  python -m src.mcp.server --test             # quick self-test
  python -m src.mcp.server --demo "career"    # demo question with fallback LLM

The server holds ONE active chart in memory (loaded via the 'load_chart'
mechanism or pre-loaded via --profile).
"""

from __future__ import annotations

import json
import sys
import os
from typing import Any, Dict, List, Optional

# Ensure project root is importable
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.mcp.tools import TOOL_SCHEMAS, ToolContext, execute_tool


# ═══════════════════════════════════════════════════════════════════════
# MCP Protocol implementation (JSON-RPC 2.0 over stdio)
# ═══════════════════════════════════════════════════════════════════════

SERVER_INFO = {
    "name": "rosetta-astrology",
    "version": "0.1.0",
}

CAPABILITIES = {
    "tools": {},
}


def _handle_request(method: str, params: Dict[str, Any], ctx: ToolContext) -> Any:
    """Handle a single JSON-RPC method call."""

    if method == "initialize":
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": CAPABILITIES,
        }

    if method == "notifications/initialized":
        return None  # No response needed for notifications

    if method == "tools/list":
        return {"tools": TOOL_SCHEMAS}

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = execute_tool(tool_name, arguments, ctx)
        # MCP expects { content: [{type: "text", text: "..."}] }
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, ensure_ascii=False),
                }
            ],
        }

    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


def _make_response(req_id: Any, result: Any) -> Dict[str, Any]:
    """Build a JSON-RPC response envelope."""
    resp: Dict[str, Any] = {"jsonrpc": "2.0", "id": req_id}
    if isinstance(result, dict) and "error" in result and "code" in result.get("error", {}):
        resp["error"] = result["error"]
    else:
        resp["result"] = result
    return resp


def run_stdio(ctx: ToolContext):
    """Run the MCP server on stdin/stdout."""
    sys.stderr.write("[rosetta-mcp] Server started on stdio\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError as e:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
            continue

        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        result = _handle_request(method, params, ctx)

        # Notifications (no id) don't get a response
        if req_id is not None and result is not None:
            response = _make_response(req_id, result)
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════
# Chart loading helper
# ═══════════════════════════════════════════════════════════════════════

def load_chart_from_profile(
    profile_data: Dict[str, Any],
    house_system: str = "placidus",
) -> Any:
    """Compute an AstrologicalChart from saved profile data.

    This is the bridge from stored profile JSON → live chart object,
    reusing the existing calc_v2.calculate_chart() pipeline.
    """
    from src.core.calc_v2 import calculate_chart

    year = int(profile_data.get("year", 2000))
    month_name = profile_data.get("month_name", "January")
    day = int(profile_data.get("day", 1))
    hour = int(profile_data.get("hour", 12))
    minute = int(profile_data.get("minute", 0))
    lat = float(profile_data.get("lat", 0.0))
    lon = float(profile_data.get("lon", 0.0))
    tz_name = profile_data.get("tz_name", "UTC")
    city = profile_data.get("city", "")
    name = profile_data.get("name", "")
    unknown_time = bool(profile_data.get("unknown_time", False))

    import datetime
    month_num = datetime.datetime.strptime(month_name, "%B").month

    df, aspect_df, plot_data, chart = calculate_chart(
        year=year, month=month_num, day=day,
        hour=hour, minute=minute,
        tz_offset=0, lat=lat, lon=lon,
        input_is_ut=False,
        tz_name=tz_name,
        include_aspects=True,
        unknown_time=unknown_time,
        display_name=name,
        city=city,
    )

    chart.plot_data = plot_data
    chart.df_positions = df
    chart.aspect_df = aspect_df

    return chart


# ═══════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════

def main():
    """CLI entry point for the Rosetta MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Rosetta MCP Astrology Server")
    parser.add_argument("--test", action="store_true", help="Run self-test")
    parser.add_argument("--demo", type=str, default="", help="Demo question (uses fallback)")
    parser.add_argument("--profile", type=str, default="", help="JSON file with profile data (chart_1 / natal)")
    parser.add_argument("--profile-b", type=str, default="", help="JSON file for second chart (synastry / transits)")
    parser.add_argument("--house-system", type=str, default="placidus")
    parser.add_argument("--backend", type=str, default="auto",
                        choices=["auto", "openai", "anthropic", "fallback"])
    args = parser.parse_args()

    ctx = ToolContext(
        house_system=args.house_system,
        llm_backend=args.backend,
    )

    # Load chart from profile if provided
    if args.profile:
        with open(args.profile) as f:
            profile = json.load(f)
        sys.stderr.write(f"[rosetta-mcp] Loading chart from {args.profile}...\n")
        ctx.chart = load_chart_from_profile(profile, args.house_system)
        sys.stderr.write(f"[rosetta-mcp] Chart loaded: {len(ctx.chart.objects)} objects\n")

    # Load second chart for biwheel mode (synastry / transits)
    if args.profile_b:
        with open(args.profile_b) as f:
            profile_b = json.load(f)
        sys.stderr.write(f"[rosetta-mcp] Loading chart_b from {args.profile_b}...\n")
        ctx.chart_b = load_chart_from_profile(profile_b, args.house_system)
        sys.stderr.write(f"[rosetta-mcp] Chart_b loaded: {len(ctx.chart_b.objects)} objects\n")

    if args.test:
        _run_self_test(ctx)
        return

    if args.demo:
        _run_demo(args.demo, ctx)
        return

    # Default: stdio MCP server
    run_stdio(ctx)


def _run_self_test(ctx: ToolContext):
    """Quick self-test: exercise topic routing and tool dispatch."""
    print("=== Rosetta MCP Self-Test ===\n")

    # Test 1: Topic routing
    from src.mcp.topic_maps import resolve_factors
    match = resolve_factors("Tell me about my career and public image")
    print(f"Topic routing: 'career and public image'")
    print(f"  Domain:     {match.domain}")
    print(f"  Subtopic:   {match.subtopic}")
    print(f"  Factors:    {match.factors[:8]}...")
    print(f"  Confidence: {match.confidence:.2f}")
    print(f"  Keywords:   {match.matched_keywords}")
    print()

    # Test 2: List tools
    result = execute_tool("list_topics", {}, ctx)
    domains = result.get("domains", [])
    print(f"Available domains: {len(domains)}")
    for d in domains:
        print(f"  - {d['name']}: {d['description']}")
    print()

    # Test 3: Resolve question
    result = execute_tool("resolve_question", {"question": "shadow work and healing"}, ctx)
    print(f"Resolve 'shadow work and healing':")
    print(f"  {json.dumps(result, indent=2)}")
    print()

    # Test 4: Domain factors
    result = execute_tool("get_domain_factors", {"domain": "Relationships & Love"}, ctx)
    print(f"Factors for 'Relationships & Love': {result.get('factors', [])[:10]}...")
    print()

    if ctx.chart:
        # Test 5: Chart summary
        result = execute_tool("get_chart_summary", {}, ctx)
        print(f"Chart summary: {json.dumps(result, indent=2)}")
        print()

        # Test 6: Ask chart (fallback)
        result = execute_tool("ask_chart", {
            "question": "What does my chart say about relationships?",
            "backend": "fallback",
        }, ctx)
        print(f"Reading (fallback):")
        print(result.get("reading", "")[:500])
        print()

    print("=== Self-Test Complete ===")


def _run_demo(question: str, ctx: ToolContext):
    """Run a demo question and print the result."""
    if not ctx.chart:
        print("No chart loaded. Use --profile to load one, or just see routing:")
        result = execute_tool("resolve_question", {"question": question}, ctx)
        print(json.dumps(result, indent=2))
        return

    result = execute_tool("ask_chart", {
        "question": question,
        "backend": ctx.llm_backend,
        "include_raw_data": True,
    }, ctx)
    print(f"Domain: {result.get('domain')}")
    print(f"Subtopic: {result.get('subtopic')}")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Backend: {result.get('backend')}")
    print(f"Tokens: {result.get('tokens')}")
    print()
    print(result.get("reading", ""))


if __name__ == "__main__":
    main()
