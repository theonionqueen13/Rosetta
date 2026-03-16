"""
tools.py — MCP tool definitions for the Rosetta astrology server.

Each tool is a pure function: (arguments) → result dict.
No server framework dependency — these are callable directly for testing,
and wired into the MCP server in server.py.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.mcp.topic_maps import (
    all_factors_for_domain,
    list_domains,
    list_subtopics,
    resolve_factors,
)
from src.mcp.reading_engine import build_reading
from src.mcp.reading_packet import ReadingPacket
from src.mcp.prose_synthesizer import synthesize, SynthesisResult
from src.mcp.prompt_templates import estimate_prompt_tokens


# ═══════════════════════════════════════════════════════════════════════
# Tool registry — each entry maps a tool name to its handler + schema
# ═══════════════════════════════════════════════════════════════════════

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "name": "ask_chart",
        "description": (
            "Ask a free-text question about a loaded natal chart. "
            "The engine routes the question to relevant astrological factors, "
            "gathers hard-coded interpretive data, and returns a prose reading. "
            "This is the primary tool for chart consultation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The user's question (e.g. 'Tell me about my career')",
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "openai", "anthropic", "fallback"],
                    "description": "LLM backend for prose synthesis. 'fallback' uses no LLM.",
                    "default": "auto",
                },
                "include_raw_data": {
                    "type": "boolean",
                    "description": "If true, also return the raw ReadingPacket JSON.",
                    "default": False,
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_reading_data",
        "description": (
            "Get the raw structured astrological data for a question, "
            "without any LLM prose synthesis. Returns a ReadingPacket JSON. "
            "Useful for inspecting what the engine computed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The user's question",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "list_topics",
        "description": (
            "List all available topic domains and their descriptions. "
            "Returns the 12 life-area domains from the topic map."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "list_subtopics",
        "description": (
            "List subtopics for a given domain. "
            "Returns the subtopic labels that can be explored."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain name (e.g. 'Career & Public Life')",
                },
            },
            "required": ["domain"],
        },
    },
    {
        "name": "resolve_question",
        "description": (
            "Show what astrological factors a question maps to, "
            "without fetching any chart data. Useful for understanding "
            "the intent routing."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Free-text question to route",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_placement",
        "description": (
            "Get detailed information about a specific object's placement "
            "in the chart (sign, house, dignity, aspects to it)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Object name (e.g. 'Sun', 'Venus', 'MC', 'North Node')",
                },
            },
            "required": ["object_name"],
        },
    },
    {
        "name": "get_house",
        "description": (
            "Get information about a specific house: sign on the cusp, "
            "ruler, and objects occupying it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "house_number": {
                    "type": "integer",
                    "description": "House number (1-12)",
                    "minimum": 1,
                    "maximum": 12,
                },
            },
            "required": ["house_number"],
        },
    },
    {
        "name": "get_aspects",
        "description": (
            "Get all aspects involving a specific object in the chart."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Object name to find aspects for",
                },
            },
            "required": ["object_name"],
        },
    },
    {
        "name": "get_patterns",
        "description": (
            "Get all detected geometric patterns (Grand Trine, T-Square, "
            "Yod, Kite, etc.) in the chart."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_chart_summary",
        "description": (
            "Get a high-level summary of the chart: key placements, "
            "sect, dominant element/modality, and pattern count."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_domain_factors",
        "description": (
            "Get all astrological factors associated with a life domain. "
            "Useful for understanding what the topic map covers."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain name (e.g. 'Relationships & Love')",
                },
            },
            "required": ["domain"],
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════
# Tool implementations
# ═══════════════════════════════════════════════════════════════════════

class ToolContext:
    """Holds the active chart and configuration for tool execution.

    The MCP server creates one of these when a chart is loaded,
    and passes it to every tool call.
    """

    def __init__(
        self,
        chart: Any = None,
        house_system: str = "placidus",
        llm_backend: str = "auto",
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.chart = chart
        self.house_system = house_system
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.api_key = api_key


def execute_tool(
    tool_name: str,
    arguments: Dict[str, Any],
    ctx: ToolContext,
) -> Dict[str, Any]:
    """Dispatch a tool call.  Returns a JSON-serializable result dict."""
    handler = _HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return handler(arguments, ctx)
    except Exception as e:
        return {"error": str(e)}


# ── Individual handlers ──────────────────────────────────────────────

def _ask_chart(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded. Load a chart first."}

    question = args.get("question", "")
    backend = args.get("backend", ctx.llm_backend)
    include_raw = args.get("include_raw_data", False)

    packet = build_reading(
        question, ctx.chart,
        house_system=ctx.house_system,
    )
    result = synthesize(
        packet,
        backend=backend,
        model=ctx.llm_model,
        api_key=ctx.api_key,
    )

    out: Dict[str, Any] = {
        "reading": result.text,
        "model": result.model,
        "tokens": result.total_tokens,
        "backend": result.backend,
        "domain": packet.domain,
        "subtopic": packet.subtopic,
        "confidence": packet.confidence,
    }
    if include_raw:
        out["raw_data"] = packet.to_dict()
    return out


def _get_reading_data(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    question = args.get("question", "")
    packet = build_reading(
        question, ctx.chart,
        house_system=ctx.house_system,
    )
    return {
        "packet": packet.to_dict(),
        "summary": packet.summary_line(),
        "token_estimate": packet.token_estimate(),
    }


def _list_topics(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    return {"domains": list_domains()}


def _list_subtopics_handler(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    domain = args.get("domain", "")
    subs = list_subtopics(domain)
    if not subs:
        return {"error": f"Domain not found: {domain}"}
    return {"domain": domain, "subtopics": subs}


def _resolve_question(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    question = args.get("question", "")
    match = resolve_factors(question)
    return {
        "domain": match.domain,
        "subtopic": match.subtopic,
        "factors": match.factors,
        "confidence": match.confidence,
        "matched_keywords": match.matched_keywords,
    }


def _get_placement(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    obj_name = args.get("object_name", "")
    # Use the reading engine to get placement data for this object
    packet = build_reading(
        f"Tell me about {obj_name}",
        ctx.chart,
        house_system=ctx.house_system,
        include_interp_text=False,
    )
    # Find the specific placement
    for p in packet.placements:
        if p.object_name.lower() == obj_name.lower():
            return {"placement": p.to_dict(), "aspects": [a.to_dict() for a in packet.aspects]}
    return {"error": f"Object not found: {obj_name}", "available": [p.object_name for p in packet.placements]}


def _get_house(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    house_num = args.get("house_number", 0)
    packet = build_reading(
        f"Tell me about the {house_num}th house",
        ctx.chart,
        house_system=ctx.house_system,
        include_interp_text=False,
    )
    for h in packet.houses:
        if h.house_number == house_num:
            return {"house": h.to_dict()}
    return {"error": f"House {house_num} not found"}


def _get_aspects(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    obj_name = args.get("object_name", "")
    packet = build_reading(
        f"aspects of {obj_name}",
        ctx.chart,
        house_system=ctx.house_system,
        include_interp_text=False,
        max_aspects=50,
    )
    matching = [a.to_dict() for a in packet.aspects
                if a.object1.lower() == obj_name.lower()
                or a.object2.lower() == obj_name.lower()]
    return {"object": obj_name, "aspects": matching, "count": len(matching)}


def _get_patterns(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    # Build a broad reading to capture all patterns
    packet = build_reading(
        "Show me all chart patterns",
        ctx.chart,
        house_system=ctx.house_system,
        include_interp_text=False,
    )
    # Also grab patterns from shapes directly
    all_patterns: List[Dict[str, Any]] = []
    for shape in (ctx.chart.shapes or []):
        name = getattr(shape, "name", type(shape).__name__)
        members: List[str] = []
        for attr in dir(shape):
            if attr.startswith("node_") or attr in ("apex", "base_1", "base_2"):
                node = getattr(shape, attr, None)
                if node and hasattr(node, "name"):
                    members.append(node.name)
                elif node and hasattr(node, "object_name"):
                    n = node.object_name
                    members.append(n.name if hasattr(n, "name") else str(n))
        meaning = getattr(shape, "meaning", "")
        all_patterns.append({
            "type": name,
            "members": members,
            "meaning": meaning or "",
        })
    return {"patterns": all_patterns, "count": len(all_patterns)}


def _get_chart_summary(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    chart = ctx.chart
    hdr = chart.header_lines() if hasattr(chart, "header_lines") else ("",) * 5

    # Element/modality counts
    elements: Dict[str, int] = {}
    modalities: Dict[str, int] = {}
    for cobj in chart.objects:
        if cobj.sign:
            el = cobj.sign.element if cobj.sign.element else ""
            mod = cobj.sign.modality if cobj.sign.modality else ""
            if el:
                elements[str(el)] = elements.get(str(el), 0) + 1
            if mod:
                modalities[str(mod)] = modalities.get(str(mod), 0) + 1

    return {
        "name": hdr[0],
        "date": hdr[1],
        "time": hdr[2],
        "city": hdr[3],
        "unknown_time": bool(chart.unknown_time),
        "object_count": len(chart.objects),
        "pattern_count": len(chart.shapes or []),
        "sect": chart.sect or "unknown",
        "elements": elements,
        "modalities": modalities,
    }


def _get_domain_factors(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    domain = args.get("domain", "")
    factors = all_factors_for_domain(domain)
    if not factors:
        return {"error": f"Domain not found: {domain}"}
    return {"domain": domain, "factors": factors}


# Handler dispatch table
_HANDLERS: Dict[str, Any] = {
    "ask_chart": _ask_chart,
    "get_reading_data": _get_reading_data,
    "list_topics": _list_topics,
    "list_subtopics": _list_subtopics_handler,
    "resolve_question": _resolve_question,
    "get_placement": _get_placement,
    "get_house": _get_house,
    "get_aspects": _get_aspects,
    "get_patterns": _get_patterns,
    "get_chart_summary": _get_chart_summary,
    "get_domain_factors": _get_domain_factors,
}
