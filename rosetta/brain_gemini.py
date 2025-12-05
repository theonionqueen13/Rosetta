"""Gemini wrapper utilities for the Rosetta brain."""

from __future__ import annotations

import json
from typing import Any, Dict


def ask_gemini_brain(
    genai_module: Any,
    prompt_text: str,
    context: Dict[str, Any],
    model: str = "gemini-1.5-flash",
    temperature: float = 0.2,
) -> str:
    """Send a structured prompt to Gemini and return the model response text."""

    generative_model = genai_module.GenerativeModel(
        model_name=model,
        system_instruction=(
            "You are an astrology interpreter.\n"
            "ONLY generate profile sections for placements listed in OBJECTS.\n"
            "Use ONLY ASPECTS for relationships; do not recalculate or infer aspects.\n"
            "GLOBAL context (compass, dispositors, graph) is for orientation only.\n"
            "Write clearly, address the user as 'you'.\n"
            "Do not use the word 'Astroneurology'."
        ),
        generation_config={"temperature": temperature},
    )

    payload = (
        f"TASK:\n{prompt_text.strip()}\n\n"
        f"OBJECTS (visible only):\n{json.dumps(context.get('objects', []), indent=2)}\n\n"
        f"ASPECTS (single source of truth):\n{json.dumps(context.get('aspects', []), indent=2)}\n\n"
        f"SHAPES:\n{json.dumps(context.get('shapes', []), indent=2)}\n\n"
        f"GLOBAL (silent orientation):\n{json.dumps(context.get('global', {}), indent=2)}\n\n"
        f"FIXED STARS:\n{json.dumps(context.get('fixed_stars', {}), indent=2)}\n"
    )

    resp = generative_model.generate_content(payload)
    if not getattr(resp, "candidates", None):
        return "⚠️ Gemini returned no content (possibly safety-blocked)."
    return (resp.text or "").strip()


def choose_task_instruction(chart_mode: str, visible_objects: list, active_shapes: list, context: dict) -> str:
    """Return the instruction text given the current chart mode."""

    if chart_mode == "natal":
        return (
            "You are an astrology interpreter.\n"
            "ONLY generate profile sections for the placements in context.objects.\n"
            "Use EXACTLY context.aspects for inter-object relationships; these are pre-clustered.\n"
            "Do NOT recalculate or invent aspects. Do NOT infer relationships from the dispositor graph.\n"
            "Use global context (compass summary; dispositor_graph summary) only for orientation notes—"
            "do not expand them into full profiles unless the points are in context.objects.\n"
            "Write clearly, address the user as 'you', and avoid cookbook clichés."
        )
    return "Describe the chart elements clearly and factually using only the provided context."


__all__ = ["ask_gemini_brain", "choose_task_instruction"]
