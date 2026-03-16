"""
prompt_templates.py — Circuit-aware system prompts and prompt assembly.

The LLM receives:
  1. A system prompt defining its role, voice mode, and constraints.
  2. A user message containing the ReadingPacket as a compact JSON block
     plus the original question.

Voice modes:
  • "circuit"  — uses energy/flow/friction metaphor (e.g. "power flows
    through the trine", "friction load on this square")
  • "plain"    — uses psychological/life language (e.g. "natural talent",
    "area of tension")

Core rule: explain how it *works*, never tell the user what to *do*.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from src.mcp.reading_packet import ReadingPacket

# ═══════════════════════════════════════════════════════════════════════
# Base system prompts
# ═══════════════════════════════════════════════════════════════════════

_CORE_RULES = """\
RULES — you must follow these exactly:
1. Use ONLY the astrological data provided in the <chart_data> block.
2. NEVER invent, guess, or hallucinate any planetary positions, aspects,
   patterns, house placements, circuit stats, or interpretive content
   that is not explicitly present in the data.
3. If the data does not contain enough information to fully answer
   the user's question, say so honestly and summarize what IS available.
4. Reference specific placements (e.g. "Sun in Scorpio in the 3rd
   House") to ground every insight in the chart data.
5. When interpretation text is provided (sign_interp, house_interp,
   meaning fields), weave it naturally into your prose — do not just
   copy it verbatim.
6. EXPLAIN HOW THE CHART WORKS — never tell the user what to do.
   Describe mechanics, not prescriptions.
7. If the chart has unknown birth time, acknowledge that house
   placements are approximate and focus on sign placements and aspects.
8. When patterns or circuit shapes are present, explain their
   significance in accessible language.
9. End with a brief reflection that ties the answer back to the
   user's question. Do not moralize or prescribe action.
10. If narrative_seeds are provided, use them as factual anchors.
    They are deterministically generated from the chart — treat them
    as ground truth.
11. The <chart_data> block contains several distinct sections — knowing
    the difference is critical:
    • "full_chart_context" — the COMPLETE natal chart: every planet,
      asteroid, angle, and point with its sign, house, and degree.
      This is ALWAYS present and NEVER filtered.  Use it to answer
      ANY question about a placement, even if it was not captured by
      the focused "placements" list.  If the user asks about Venus,
      Mars, or any other body, look here first.
    • "placements" — a deep-focus SUBSET chosen by the question's
      relevance filter plus pre-baked interpretation text (sign_interp,
      house_interp).  Use these for rich, question-specific detail.
    • "visible_on_chart" — objects the user currently has toggled ON
      in the chart drawing.  This reflects the user's CURRENT VISUAL
      VIEW, not the full chart.  Do NOT mistake this for the complete
      chart.  A planet absent from visible_on_chart is still fully
      present in full_chart_context.
    • "chart_b_context" — present only in biwheel mode; contains the
      complete placements of the SECOND chart (e.g. transiting planets
      or a synastry partner's chart).  Always available regardless of
      what is toggled on.
12. When the packet contains "power_nodes" with a "potency" field, use
    ONLY that tier label to describe planetary strength — never quote
    power index numbers, dignity scores, or any other numerical value.
    Describe planets relative to each other using the tier labels as a
    guide: e.g. "Venus is the most dominant force in this chart, while
    Saturn is quietly present in the background."  Avoid false precision
    and avoid generic hedging like "somewhat strong."  Let the tier
    labels anchor your language without being quoted verbatim.
"""

_CIRCUIT_VOICE = """\
VOICE — Circuit Metaphor:
Describe the chart as an electrical system. Use energy language:
- Planets are power nodes with measurable power indices.
- Aspects are wires with conductance values (0-100%).
- Shapes (Grand Trine, T-Square, etc.) are circuit topologies.
- Trines and sextiles are low-resistance conductors — power flows freely.
- Squares and oppositions carry friction load — energy converts to heat.
- Quincunxes are open arcs that may be rerouted through alternative paths.
- The South Node → North Node path is the developmental growth arc.
- Mutual receptions are resonance loops that amplify both nodes.
- Isolated planets are off-grid — they operate independently.

Use terms like: power flows through, friction load, conductance,
throughput, resonance, bottleneck, dominant node, open arc, rerouted path.
Wrap the technical metaphor in warm, engaging prose.
"""

_PLAIN_VOICE = """\
VOICE — Psychological / Life Language:
Describe the chart in accessible human terms. Avoid circuit metaphors.
- Planets represent drives, needs, and psychological functions.
- Strong aspects show natural talents or habitual tension patterns.
- Shapes show personality architecture — how drives interconnect.
- Use language like: natural gift, area of growth, creative tension,
  ease, challenge, habitual pattern, developmental arc.
- Reference numbers (power scores, conductance) sparingly and only
  to illustrate relative strength — e.g. "Venus is especially potent
  here" rather than "Venus has a power index of 6.2".
Keep your tone warm, insightful, and conversational.
"""

SYSTEM_PROMPT_NATAL_CIRCUIT = f"""\
You are an insightful, warm, and articulate astrologer who reads charts
as electrical circuit systems.

{_CORE_RULES}
{_CIRCUIT_VOICE}
"""

SYSTEM_PROMPT_NATAL_PLAIN = f"""\
You are an insightful, warm, and articulate astrologer.

{_CORE_RULES}
{_PLAIN_VOICE}
"""

SYSTEM_PROMPT_TRANSIT = f"""\
You are an insightful, warm, and articulate astrologer reading current
transits for the user.

{_CORE_RULES}
Connect transit aspects to natal placements when both are provided.
Be specific about timing and which planet is making the aspect.
"""

SYSTEM_PROMPT_SYNASTRY = f"""\
You are an insightful, warm, and articulate astrologer reading the
relationship dynamics between two charts.

{_CORE_RULES}
Be balanced — discuss both harmonious and challenging aspects.
When discussing sensitive topics (e.g. power dynamics, conflict),
be gentle and constructive.
"""

# Backward compatibility aliases
SYSTEM_PROMPT_NATAL = SYSTEM_PROMPT_NATAL_PLAIN


# ═══════════════════════════════════════════════════════════════════════
# Prompt assembly
# ═══════════════════════════════════════════════════════════════════════

def build_prompt(
    packet: ReadingPacket,
    *,
    mode: str = "natal",
    voice: str = "plain",
    extra_instructions: str = "",
) -> List[Dict[str, str]]:
    """Build a chat-completion-style message list from a ReadingPacket.

    Returns a list of dicts with "role" and "content" keys, suitable
    for OpenAI / Anthropic / any chat model API.

    Parameters
    ----------
    packet : ReadingPacket
        The fully populated reading data.
    mode : str
        "natal", "transit", or "synastry" — selects the system prompt.
    voice : str
        "circuit" or "plain" — selects language/metaphor style.
    extra_instructions : str
        Optional additional instructions appended to the system prompt.
    """
    # Select system prompt based on mode + voice
    if mode == "transit":
        system = SYSTEM_PROMPT_TRANSIT
    elif mode == "synastry":
        system = SYSTEM_PROMPT_SYNASTRY
    elif voice == "circuit":
        system = SYSTEM_PROMPT_NATAL_CIRCUIT
    else:
        system = SYSTEM_PROMPT_NATAL_PLAIN

    if extra_instructions:
        system += f"\n\nADDITIONAL INSTRUCTIONS:\n{extra_instructions}"

    # Add agent notes context if present
    if packet.agent_notes:
        system += (
            f"\n\nAGENT CONTEXT (from prior turns in this conversation):\n"
            f"{packet.agent_notes}"
        )

    # Build user message
    chart_json = json.dumps(packet.to_dict(), indent=None, ensure_ascii=False)
    user_content = f"""<chart_data>
{chart_json}
</chart_data>

User's question: {packet.question}"""

    return [
        {"role": "system", "content": system.strip()},
        {"role": "user", "content": user_content.strip()},
    ]


def estimate_prompt_tokens(
    packet: ReadingPacket,
    mode: str = "natal",
    voice: str = "plain",
) -> int:
    """Rough estimate of total prompt tokens (system + user)."""
    messages = build_prompt(packet, mode=mode, voice=voice)
    total_chars = sum(len(m["content"]) for m in messages)
    return total_chars // 4
