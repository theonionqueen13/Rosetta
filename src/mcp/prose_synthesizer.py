"""
prose_synthesizer.py — Thin LLM wrapper for turning ReadingPackets into prose.

Supports multiple backends (OpenAI, Anthropic, OpenRouter) with a clean
fallback to a structured-text-only mode (no LLM).

This is intentionally the *thinnest possible* layer.  All intelligence
lives in the reading engine and topic maps — the LLM only synthesizes.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.mcp.prompt_templates import build_prompt, estimate_prompt_tokens
from src.mcp.reading_packet import ReadingPacket

# TYPE_CHECKING import to avoid circular dependency at runtime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.mcp.agent_memory import AgentMemory


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "google/gemini-2.0-flash-001"


@dataclass
class SynthesisResult:
    """The output of prose synthesis."""
    text: str
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    backend: str = ""          # "openai", "anthropic", "openrouter", "fallback"

    def to_dict(self) -> Dict[str, Any]:
        """Serialise this synthesis result to a dictionary."""
        return {
            "text": self.text,
            "model": self.model,
            "tokens": self.total_tokens,
            "backend": self.backend,
        }


# ═══════════════════════════════════════════════════════════════════════
# Backend: structured-text fallback (no LLM)
# ═══════════════════════════════════════════════════════════════════════

def _fallback_synthesize(packet: ReadingPacket) -> SynthesisResult:
    """Produce a structured text reading without any LLM.

    This is the zero-cost, zero-hallucination baseline.  It simply
    formats the ReadingPacket's pre-baked interpretation text.
    """
    parts: List[str] = []

    if packet.chart_name:
        parts.append(f"# Reading for {packet.chart_name}")
    if packet.domain:
        parts.append(f"**Topic:** {packet.domain}")
        if packet.subtopic:
            parts.append(f"**Subtopic:** {packet.subtopic}")

    if packet.placements:
        parts.append("\n## Key Placements")
        for p in packet.placements:
            line = f"- **{p.object_name}** in {p.sign} ({p.sign_element}, {p.sign_modality}), House {p.house}"
            if p.retrograde:
                line += " [Rx]"
            if p.dignity:
                line += f" [{p.dignity}]"
            parts.append(line)
            if p.sign_combo_text:
                parts.append(f"  *Sign:* {p.sign_combo_text}")
            if p.house_combo_text:
                parts.append(f"  *House:* {p.house_combo_text}")

    if packet.aspects:
        parts.append("\n## Aspects")
        for a in packet.aspects:
            line = f"- {a.object1} {a.aspect_name} {a.object2} (orb {a.orb:.1f}°)"
            if a.applying:
                line += " [applying]"
            if a.mutual_reception:
                line += " [mutual reception]"
            parts.append(line)
            if a.aspect_meaning:
                parts.append(f"  *{a.aspect_meaning}*")

    if packet.patterns:
        parts.append("\n## Patterns")
        for pat in packet.patterns:
            parts.append(f"- **{pat.pattern_type}**: {', '.join(pat.members)}")
            if pat.meaning:
                parts.append(f"  *{pat.meaning}*")

    if packet.sect:
        parts.append(f"\n## Sect: {packet.sect.sect}")
        parts.append(f"Sect light: {packet.sect.sect_light} | "
                      f"Benefic of sect: {packet.sect.benefic_of_sect} | "
                      f"Malefic of sect: {packet.sect.malefic_of_sect}")

    # Circuit data
    if packet.circuit_flows:
        parts.append("\n## Circuit Flows")
        for cf in packet.circuit_flows:
            # Use to_dict() which now returns qualitative tier labels
            cfd = cf.to_dict()
            parts.append(
                f"- **{cfd['shape']}** ({', '.join(cfd['members'])}): "
                f"resonance: {cfd['resonance']}, friction: {cfd['friction']}, "
                f"throughput: {cfd['throughput']}"
            )
            if cf.flow_characterization:
                parts.append(f"  *{cf.flow_characterization}*")

    if packet.power_nodes:
        parts.append("\n## Power Nodes")
        for pn in packet.power_nodes:
            pnd = pn.to_dict()
            if pn.tier_label:
                line = f"- **{pn.planet_name}**: {pn.tier_label}"
            else:
                line = f"- **{pn.planet_name}**"
            parts.append(line)

    if packet.circuit_paths:
        parts.append("\n## Circuit Paths")
        for cp in packet.circuit_paths:
            parts.append(
                f"- {cp.from_concept} → {cp.to_concept}: "
                f"{cp.connection_quality}"
            )
            if cp.path_planets:
                parts.append(f"  Path: {' → '.join(cp.path_planets)}")

    if packet.narrative_seeds:
        parts.append("\n## Circuit Analysis")
        for seed in packet.narrative_seeds:
            parts.append(f"- {seed}")

    if packet.interp_text:
        parts.append("\n## Interpretation")
        parts.append(packet.interp_text)

    text = "\n".join(parts) if parts else "No data available for this question."

    return SynthesisResult(
        text=text,
        model="structured-fallback",
        backend="fallback",
    )


# ═══════════════════════════════════════════════════════════════════════
# Backend: OpenAI
# ═══════════════════════════════════════════════════════════════════════

def _openai_synthesize(
    packet: ReadingPacket,
    *,
    model: str = "gpt-4o-mini",
    mode: str = "natal",
    voice: str = "plain",
    extra_instructions: str = "",
    api_key: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None,
    agent_memory: Optional["AgentMemory"] = None,
) -> SynthesisResult:
    """Call OpenAI's chat completion API."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = openai.OpenAI(api_key=key)
    messages = build_prompt(
        packet, mode=mode, voice=voice,
        extra_instructions=extra_instructions,
        conversation_history=conversation_history,
        agent_memory=agent_memory,
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=1024,
    )

    choice = response.choices[0]
    usage = response.usage

    return SynthesisResult(
        text=choice.message.content or "",
        model=model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        backend="openai",
    )


# ═══════════════════════════════════════════════════════════════════════
# Backend: OpenRouter (OpenAI-compatible, any model)
# ═══════════════════════════════════════════════════════════════════════

def _openrouter_synthesize(
    packet: ReadingPacket,
    *,
    model: str = DEFAULT_OPENROUTER_MODEL,
    mode: str = "natal",
    voice: str = "plain",
    extra_instructions: str = "",
    api_key: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None,
    agent_memory: Optional["AgentMemory"] = None,
) -> SynthesisResult:
    """Call OpenRouter via the OpenAI SDK with a base_url override."""
    try:
        import openai
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set")

    client = openai.OpenAI(
        api_key=key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/theonionqueen13/Rosetta",
            "X-Title": "Rosetta Astrology",
        },
    )
    messages = build_prompt(
        packet, mode=mode, voice=voice,
        extra_instructions=extra_instructions,
        conversation_history=conversation_history,
        agent_memory=agent_memory,
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=1024,
    )

    choice = response.choices[0]
    usage = response.usage

    return SynthesisResult(
        text=choice.message.content or "",
        model=model,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        total_tokens=usage.total_tokens if usage else 0,
        backend="openrouter",
    )


# ═══════════════════════════════════════════════════════════════════════
# Backend: Anthropic
# ═══════════════════════════════════════════════════════════════════════

def _anthropic_synthesize(
    packet: ReadingPacket,
    *,
    model: str = "claude-sonnet-4-20250514",
    mode: str = "natal",
    voice: str = "plain",
    extra_instructions: str = "",
    api_key: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None,
    agent_memory: Optional["AgentMemory"] = None,
) -> SynthesisResult:
    """Call Anthropic's messages API."""
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. Run: pip install anthropic")

    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=key)
    messages = build_prompt(
        packet, mode=mode, voice=voice,
        extra_instructions=extra_instructions,
        conversation_history=conversation_history,
        agent_memory=agent_memory,
    )

    # Anthropic API separates system from messages
    system_content = messages[0]["content"]
    user_messages = [{"role": m["role"], "content": m["content"]} for m in messages[1:]]

    response = client.messages.create(
        model=model,
        system=system_content,
        messages=user_messages,
        temperature=0.7,
        max_tokens=1024,
    )

    text = response.content[0].text if response.content else ""

    return SynthesisResult(
        text=text,
        model=model,
        prompt_tokens=response.usage.input_tokens if response.usage else 0,
        completion_tokens=response.usage.output_tokens if response.usage else 0,
        total_tokens=(
            (response.usage.input_tokens + response.usage.output_tokens)
            if response.usage else 0
        ),
        backend="anthropic",
    )


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def synthesize(
    packet: ReadingPacket,
    *,
    backend: str = "auto",
    model: Optional[str] = None,
    mode: str = "natal",
    voice: str = "plain",
    extra_instructions: str = "",
    api_key: Optional[str] = None,
    conversation_history: Optional[List[Dict]] = None,
    agent_memory: Optional["AgentMemory"] = None,
) -> SynthesisResult:
    """Synthesize prose from a ReadingPacket.

    Parameters
    ----------
    packet : ReadingPacket
        The structured chart data to narrate.
    backend : str
        "openrouter", "openai", "anthropic", "fallback", or "auto".
        "auto" tries OpenRouter → Anthropic → OpenAI → fallback.
    model : str, optional
        Override the default model for the chosen backend.
    mode : str
        "natal", "transit", or "synastry" — selects the system prompt.
    voice : str
        "circuit" or "plain" — selects language/metaphor style.
    extra_instructions : str
        Extra text appended to the system prompt.
    api_key : str, optional
        API key override (otherwise reads from env vars).
    conversation_history : list of {"role", "content"} dicts, optional
        Prior conversation turns to inject as real messages before the
        current user message.  This is the primary multi-turn memory
        mechanism — the LLM sees the prior exchange and knows it offered
        a keystone deep dive, so a follow-up "yes" is handled correctly.
    """
    def _kwargs(**extra):
        """Build the common keyword arguments for the LLM call."""
        kw: Dict[str, Any] = {
            "packet": packet, "mode": mode,
            "voice": voice,
            "extra_instructions": extra_instructions,
            "api_key": api_key,
            "conversation_history": conversation_history,
            "agent_memory": agent_memory,
        }
        if model:
            kw["model"] = model
        kw.update(extra)
        return kw

    if backend == "fallback":
        return _fallback_synthesize(packet)

    if backend == "openrouter":
        return _openrouter_synthesize(**_kwargs())

    if backend == "anthropic":
        return _anthropic_synthesize(**_kwargs())

    if backend == "openai":
        return _openai_synthesize(**_kwargs())

    # Auto mode: try backends in order of preference
    if backend == "auto":
        if os.environ.get("OPENROUTER_API_KEY") or (api_key and backend == "openrouter"):
            try:
                return _openrouter_synthesize(**_kwargs())
            except Exception:
                pass

        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                return _anthropic_synthesize(**_kwargs())
            except Exception:
                pass

        if os.environ.get("OPENAI_API_KEY"):
            try:
                return _openai_synthesize(**_kwargs())
            except Exception:
                pass

        return _fallback_synthesize(packet)

    # Unknown backend — use fallback
    return _fallback_synthesize(packet)
