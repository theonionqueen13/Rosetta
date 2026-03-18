"""
tools.py — MCP tool definitions for the Rosetta astrology server.

Each tool is a pure function: (arguments) → result dict.
No server framework dependency — these are callable directly for testing,
and wired into the MCP server in server.py.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.mcp.agent_memory import AgentMemory
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
from src.mcp.comprehension import comprehend
from src.mcp.circuit_query import query_circuit


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
            "in the chart (sign, house, dignity, aspects to it). "
            "Use chart='chart_2' to query the second chart in a biwheel."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Object name (e.g. 'Sun', 'Venus', 'MC', 'North Node')",
                },
                "chart": {
                    "type": "string",
                    "enum": ["chart_1", "chart_2"],
                    "description": "Which chart to query. 'chart_2' is the outer chart in a biwheel (synastry partner or transiting planets). Defaults to 'chart_1'.",
                    "default": "chart_1",
                },
            },
            "required": ["object_name"],
        },
    },
    {
        "name": "get_house",
        "description": (
            "Get information about a specific house: sign on the cusp, "
            "ruler, and objects occupying it. "
            "Use chart='chart_2' to query the second chart in a biwheel."
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
                "chart": {
                    "type": "string",
                    "enum": ["chart_1", "chart_2"],
                    "description": "Which chart to query. Defaults to 'chart_1'.",
                    "default": "chart_1",
                },
            },
            "required": ["house_number"],
        },
    },
    {
        "name": "get_aspects",
        "description": (
            "Get all aspects involving a specific object in the chart. "
            "Use chart='chart_2' to query the second chart in a biwheel. "
            "For aspects between the two charts use get_inter_chart_aspects."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "object_name": {
                    "type": "string",
                    "description": "Object name to find aspects for",
                },
                "chart": {
                    "type": "string",
                    "enum": ["chart_1", "chart_2"],
                    "description": "Which chart to query. Defaults to 'chart_1'.",
                    "default": "chart_1",
                },
            },
            "required": ["object_name"],
        },
    },
    {
        "name": "get_patterns",
        "description": (
            "Get all detected geometric patterns (Grand Trine, T-Square, "
            "Yod, Kite, etc.) in the chart. "
            "Use chart='chart_2' to get the second chart's patterns in a biwheel."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart": {
                    "type": "string",
                    "enum": ["chart_1", "chart_2"],
                    "description": "Which chart to query. Defaults to 'chart_1'.",
                    "default": "chart_1",
                },
            },
        },
    },
    {
        "name": "get_chart_summary",
        "description": (
            "Get a high-level summary of the chart: key placements, "
            "sect, dominant element/modality, and pattern count. "
            "Use chart='chart_2' to summarise the second chart in a biwheel."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart": {
                    "type": "string",
                    "enum": ["chart_1", "chart_2"],
                    "description": "Which chart to summarise. Defaults to 'chart_1'.",
                    "default": "chart_1",
                },
            },
        },
    },
    {
        "name": "get_inter_chart_aspects",
        "description": (
            "Get all cross-chart aspects between chart_1 and chart_2 when a "
            "biwheel is loaded (synastry or transit mode). Returns the aspect "
            "list pre-computed by the drawing layer. Returns an empty list if "
            "no second chart is loaded."
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
    {
        "name": "get_circuit_reading",
        "description": (
            "Get the circuit simulation reading for a question. Returns "
            "the power-flow subgraph relevant to the question, including "
            "shape circuits, power nodes, connecting paths, "
            "and narrative seeds. This is the primary circuit-aware tool."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Free-text question about the chart",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "trace_circuit_path",
        "description": (
            "Trace the conductive path between two planets or concepts "
            "in the circuit simulation. Returns the connecting path, "
            "conductance values, and whether they share a circuit shape "
            "or are bridged through intermediate shapes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "concept_a": {
                    "type": "string",
                    "description": "First planet/concept (e.g. 'Venus', 'career')",
                },
                "concept_b": {
                    "type": "string",
                    "description": "Second planet/concept (e.g. 'Saturn', 'relationships')",
                },
            },
            "required": ["concept_a", "concept_b"],
        },
    },
    {
        "name": "get_switch_points",
        "description": (
            "Detect switch points in the chart \u2014 missing vertices of "
            "incomplete resonant shapes (T-Square \u2192 Grand Cross, "
            "Wedge \u2192 Mystic Rectangle, etc.). Returns the zodiacal "
            "position, activation range, Sabian symbol, and Saturn-informed "
            "keystone guidance for each switch point. Keystones are "
            "deliberate practices, habits, objects, or structures that "
            "complete the harmonic circuit."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "chart": {
                    "type": "string",
                    "enum": ["chart_1", "chart_2"],
                    "description": "Which chart to analyse. Defaults to 'chart_1'.",
                    "default": "chart_1",
                },
            },
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

    conversation_history stores prior turns so the internal synthesizer
    LLM has multi-turn context (e.g. remembers it offered a keystone
    deep dive and can follow through when the user replies "yes").
    Each entry: {"role": "user"|"assistant", "content": str}
    User entries store just the plain question text.
    Assistant entries store the full response text.
    History is capped at MAX_HISTORY_TURNS most-recent exchanges.
    """

    MAX_HISTORY_TURNS = 4  # keep last 4 exchanges (8 messages) in context

    def __init__(
        self,
        chart: Any = None,
        house_system: str = "placidus",
        llm_backend: str = "auto",
        llm_model: Optional[str] = None,
        api_key: Optional[str] = None,
        chart_b: Any = None,
        edges_inter_chart: Optional[List] = None,
        agent_memory: Optional[AgentMemory] = None,
    ):
        self.chart = chart
        self.house_system = house_system
        self.llm_backend = llm_backend
        self.llm_model = llm_model
        self.api_key = api_key
        self.chart_b = chart_b
        self.edges_inter_chart = edges_inter_chart or []
        self.conversation_history: List[Dict[str, str]] = []
        self.agent_memory: AgentMemory = agent_memory if agent_memory is not None else AgentMemory()

    def add_turn(self, question: str, response: str) -> None:
        """Append a user/assistant exchange to the conversation history.

        Keeps only the most recent MAX_HISTORY_TURNS exchanges to avoid
        token bloat on long conversations.
        """
        self.conversation_history.append({"role": "user", "content": question})
        self.conversation_history.append({"role": "assistant", "content": response})
        # Trim to MAX_HISTORY_TURNS exchanges (2 messages each)
        max_messages = self.MAX_HISTORY_TURNS * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]

    def prior_turns(self) -> List[Dict[str, str]]:
        """Return the stored conversation history for injection into prompts."""
        return list(self.conversation_history)


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

def _resolve_chart(ctx: ToolContext, args: Dict[str, Any]) -> Any:
    """Return ctx.chart or ctx.chart_b based on the 'chart' arg."""
    which = args.get("chart", "chart_1")
    if which == "chart_2" and ctx.chart_b is not None:
        return ctx.chart_b
    return ctx.chart


def _ask_chart(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded. Load a chart first."}

    question = args.get("question", "")
    backend = args.get("backend", ctx.llm_backend)
    include_raw = args.get("include_raw_data", False)

    packet = build_reading(
        question, ctx.chart,
        house_system=ctx.house_system,
        api_key=ctx.api_key,
        chart_b=ctx.chart_b or None,
        edges_inter_chart=ctx.edges_inter_chart or None,
    )

    # Inject prior conversation turns into agent_notes so the synthesizer
    # LLM knows what was said in previous turns (e.g. it offered a keystone
    # deep dive and the user just replied "yes").
    prior = ctx.prior_turns()
    if prior:
        # Build a compact summary of the last turn to anchor context
        last_user = next(
            (m["content"] for m in reversed(prior) if m["role"] == "user"), ""
        )
        last_asst = next(
            (m["content"] for m in reversed(prior) if m["role"] == "assistant"), ""
        )
        # Truncate prior assistant response to avoid token overload
        asst_preview = last_asst[:600] + ("…" if len(last_asst) > 600 else "")
        notes_lines = [
            f"Prior user message: {last_user}",
            f"Prior assistant response (excerpt): {asst_preview}",
        ]
        if len(prior) > 2:
            notes_lines.insert(0, f"[{len(prior)//2} prior exchange(s) in this session]")
        packet.agent_notes = "\n".join(notes_lines)

    # Auto-detect synthesis mode from detected temporal dimension
    _td = packet.temporal_dimension or "natal"
    if _td == "synastry":
        _mode = "synastry"
    elif _td in ("transit", "cycle", "timing_predict", "solar_return"):
        _mode = "transit"
    else:
        _mode = "natal"

    result = synthesize(
        packet,
        backend=backend,
        model=ctx.llm_model,
        api_key=ctx.api_key,
        mode=_mode,
        conversation_history=prior,
    )

    # Record this exchange so future turns have context
    ctx.add_turn(question, result.text)

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
        chart_b=ctx.chart_b or None,
        edges_inter_chart=ctx.edges_inter_chart or None,
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
    target_chart = _resolve_chart(ctx, args)
    if target_chart is None:
        return {"error": "Requested chart is not loaded."}
    # Use the reading engine to get placement data for this object
    packet = build_reading(
        f"Tell me about {obj_name}",
        target_chart,
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
    target_chart = _resolve_chart(ctx, args)
    if target_chart is None:
        return {"error": "Requested chart is not loaded."}
    packet = build_reading(
        f"Tell me about the {house_num}th house",
        target_chart,
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
    target_chart = _resolve_chart(ctx, args)
    if target_chart is None:
        return {"error": "Requested chart is not loaded."}
    packet = build_reading(
        f"aspects of {obj_name}",
        target_chart,
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

    target_chart = _resolve_chart(ctx, args)
    if target_chart is None:
        return {"error": "Requested chart is not loaded."}
    # Build a broad reading to capture all patterns
    packet = build_reading(
        "Show me all chart patterns",
        target_chart,
        house_system=ctx.house_system,
        include_interp_text=False,
    )
    # Grab patterns directly from shapes
    all_patterns: List[Dict[str, Any]] = []
    for shape in (target_chart.shapes or []):
        if hasattr(shape, "shape_type"):  # DetectedShape
            shape_name = shape.shape_type
            members = list(shape.members)
        elif isinstance(shape, dict):  # legacy
            shape_name = shape.get("type", "Unknown")
            members = list(shape.get("members", []))
        else:
            continue
        all_patterns.append({
            "type": shape_name,
            "members": members,
            "meaning": "",
        })
    return {"patterns": all_patterns, "count": len(all_patterns)}


def _get_chart_summary(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    if not ctx.chart:
        return {"error": "No chart loaded."}

    chart = _resolve_chart(ctx, args)
    if chart is None:
        return {"error": "Requested chart is not loaded."}
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


def _get_inter_chart_aspects(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Return pre-computed inter-chart aspects from biwheel mode."""
    if not ctx.chart:
        return {"error": "No chart loaded."}
    if not ctx.edges_inter_chart:
        note = (
            "No second chart loaded — load a synastry partner or transit chart first."
            if ctx.chart_b is None
            else "No inter-chart aspects computed yet. Display the biwheel chart first."
        )
        return {"inter_chart_aspects": [], "count": 0, "note": note}
    result: List[Dict[str, str]] = []
    for record in ctx.edges_inter_chart:
        if isinstance(record, (list, tuple)) and len(record) >= 3:
            result.append({
                "planet_1": str(record[0]),
                "planet_2": str(record[1]),
                "aspect": str(record[2]),
            })
    return {"inter_chart_aspects": result, "count": len(result)}


def _get_domain_factors(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    domain = args.get("domain", "")
    factors = all_factors_for_domain(domain)
    if not factors:
        return {"error": f"Domain not found: {domain}"}
    return {"domain": domain, "factors": factors}


def _get_circuit_reading(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Get circuit simulation reading for a question."""
    if not ctx.chart:
        return {"error": "No chart loaded."}

    question = args.get("question", "")
    q_graph = comprehend(question, ctx.chart, api_key=ctx.api_key)
    cr = query_circuit(q_graph, ctx.chart)

    return {
        "question_type": q_graph.question_type,
        "domain": q_graph.domain,
        "factors": q_graph.all_factors,
        "circuit_reading": cr.to_dict(),
    }


def _trace_circuit_path(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Trace conductive path between two concepts."""
    if not ctx.chart:
        return {"error": "No chart loaded."}

    concept_a = args.get("concept_a", "")
    concept_b = args.get("concept_b", "")
    question = f"How does {concept_a} relate to {concept_b}?"

    q_graph = comprehend(question, ctx.chart, api_key=ctx.api_key)
    cr = query_circuit(q_graph, ctx.chart)

    result: Dict[str, Any] = {
        "concept_a": concept_a,
        "concept_b": concept_b,
        "factors_a": q_graph.nodes[0].factors if q_graph.nodes else [],
        "factors_b": q_graph.nodes[1].factors if len(q_graph.nodes) > 1 else [],
    }

    if cr.connecting_paths:
        result["paths"] = [p.to_dict() for p in cr.connecting_paths]
    if cr.relevant_shapes:
        result["shared_shapes"] = [
            {"type": s.shape_type, "members": [n.planet_name for n in s.nodes]}
            for s in cr.relevant_shapes
        ]

    return result


def _get_switch_points(args: Dict[str, Any], ctx: ToolContext) -> Dict[str, Any]:
    """Detect switch points (incomplete drum heads / membranes)."""
    if not ctx.chart:
        return {"error": "No chart loaded."}

    target_chart = _resolve_chart(ctx, args)
    if target_chart is None:
        return {"error": "Requested chart is not loaded."}

    try:
        from switch_points import find_switch_points
    except ImportError:
        return {"error": "switch_points module not found"}

    sps = find_switch_points(target_chart, house_system=ctx.house_system)
    result = [sp.to_dict() for sp in sps]
    return {
        "switch_points": result,
        "count": len(result),
        "note": (
            "Each switch point is a missing vertex that would complete an "
            "incomplete shape into a full resonant membrane. It can be "
            "activated by transit, synastry, or a deliberately chosen "
            "keystone (practice / habit / object / structure)."
        ) if result else "No incomplete resonant shapes detected.",
    }


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
    "get_inter_chart_aspects": _get_inter_chart_aspects,
    "get_domain_factors": _get_domain_factors,
    "get_circuit_reading": _get_circuit_reading,
    "trace_circuit_path": _trace_circuit_path,
    "get_switch_points": _get_switch_points,
}
