"""
prompt_templates.py — System prompts and prompt assembly for the LLM.

The LLM receives:
  1. A system prompt defining its role and constraints.
  2. A user message containing the ReadingPacket as a compact JSON block
     plus the original question.

The system prompt is deliberately rigid: it tells the LLM it must
synthesize prose *only* from the supplied facts, and must never
invent positions, aspects, or patterns that aren't in the data.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

from src.mcp.reading_packet import ReadingPacket

# ═══════════════════════════════════════════════════════════════════════
# System prompts
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT_NATAL = """\
You are an insightful, warm, and articulate astrologer.

RULES — you must follow these exactly:
1. Use ONLY the astrological data provided in the <chart_data> block.
2. NEVER invent, guess, or hallucinate any planetary positions, aspects,
   patterns, house placements, or interpretive content that is not
   explicitly present in the data.
3. If the data does not contain enough information to fully answer
   the user's question, say so honestly and summarize what IS available.
4. Reference specific placements (e.g. "your Sun in Scorpio in the 3rd
   House") to ground every insight in the chart data.
5. When interpretation text is provided (sign_interp, house_interp,
   meaning fields), weave it naturally into your prose — do not just
   copy it verbatim.
6. Keep your response focused, warm, and conversational. Aim for
   2-4 paragraphs unless the user asks for more detail.
7. If the chart has unknown birth time, acknowledge that house
   placements are approximate and focus on sign placements and aspects.
8. When patterns (Grand Trine, T-Square, Yod, etc.) are present,
   explain their significance in accessible language.
9. End with a brief, encouraging reflection that ties the answer
   back to the user's question.
"""

SYSTEM_PROMPT_TRANSIT = """\
You are an insightful, warm, and articulate astrologer reading current
transits for the user.

RULES — you must follow these exactly:
1. Use ONLY the transit data provided in the <chart_data> block.
2. NEVER invent any planetary positions, aspects, or events that are
   not explicitly present in the data.
3. Connect transit aspects to natal placements when both are provided.
4. Be specific about timing and which planet is making the aspect.
5. Keep your tone encouraging and practical.
"""

SYSTEM_PROMPT_SYNASTRY = """\
You are an insightful, warm, and articulate astrologer reading the
relationship dynamics between two charts.

RULES — you must follow these exactly:
1. Use ONLY the synastry data provided in the <chart_data> block.
2. NEVER invent any planetary positions, aspects, or compatibility
   claims that are not explicitly present in the data.
3. Be balanced — discuss both harmonious and challenging aspects.
4. When discussing sensitive topics (e.g. power dynamics, conflict),
   be gentle and constructive.
"""

# ═══════════════════════════════════════════════════════════════════════
# Prompt assembly
# ═══════════════════════════════════════════════════════════════════════

def build_prompt(
    packet: ReadingPacket,
    *,
    mode: str = "natal",
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
    extra_instructions : str
        Optional additional instructions appended to the system prompt
        (e.g. "Respond in Spanish", "Be very concise").
    """
    # Select system prompt
    sys_prompts = {
        "natal": SYSTEM_PROMPT_NATAL,
        "transit": SYSTEM_PROMPT_TRANSIT,
        "synastry": SYSTEM_PROMPT_SYNASTRY,
    }
    system = sys_prompts.get(mode, SYSTEM_PROMPT_NATAL)
    if extra_instructions:
        system += f"\n\nADDITIONAL INSTRUCTIONS:\n{extra_instructions}"

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
) -> int:
    """Rough estimate of total prompt tokens (system + user)."""
    messages = build_prompt(packet, mode=mode)
    total_chars = sum(len(m["content"]) for m in messages)
    return total_chars // 4
