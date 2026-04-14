# src/mcp/chat_pipeline.py
"""
Chat pipeline — the blocking LLM call extracted from app.py.

This module contains zero UI dependencies.  All NiceGUI state values are
passed as arguments so the function never touches ``app.storage.user``.
"""
from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-session chat data (non-JSON-serializable objects keyed by user_id)
# ---------------------------------------------------------------------------
CHAT_MEMORY: dict = {}      # uid -> AgentMemory
CHAT_DEV_TRACE: dict = {}   # uid -> dict  (last dev trace)
CHAT_PERSONS: dict = {}     # uid -> list[dict]  (known persons)
CHAT_LOCATIONS: dict = {}   # uid -> list[dict]  (known locations)


def merge_chat_persons(uid: str, new_persons) -> None:
    """Merge new person dicts into per-session known persons."""
    existing = CHAT_PERSONS.setdefault(uid, [])
    names = {p.get("name", "").lower() for p in existing}
    self_names = {
        p.get("name", "").lower()
        for p in existing
        if p.get("relationship_to_querent") == "self"
    }
    for p in new_persons:
        d = p if isinstance(p, dict) else (p.to_dict() if hasattr(p, "to_dict") else {})
        key = (d.get("name") or "").lower()
        if not key or key in names or key in self_names:
            continue
        existing.append(d)
        names.add(key)


def merge_chat_locations(uid: str, new_locations) -> None:
    """Merge new location dicts into per-session known locations."""
    existing = CHAT_LOCATIONS.setdefault(uid, [])
    names = {loc.get("name", "").lower() for loc in existing}
    for loc in new_locations:
        d = loc if isinstance(loc, dict) else (loc.to_dict() if hasattr(loc, "to_dict") else {})
        key = (d.get("name") or "").lower()
        if key and key not in names:
            existing.append(d)
            names.add(key)


def run_pipeline(
    question: str,
    chart: Any,
    chart_b: Any,
    house_system: str,
    *,
    uid: str,
    api_key: str,
    model: str,
    mode: str,
    voice: str,
    agent_notes: str,
    pending_q: str,
) -> tuple[str, dict, dict]:
    """Blocking call — run from ``run.io_bound`` thread.

    All NiceGUI state values are passed as arguments so that this function
    never touches ``app.storage.user``.

    Returns ``(response_text, meta, state_updates)`` where *state_updates*
    is a dict of keys to write back into the per-user state.
    """
    from src.mcp.reading_engine import build_reading
    from src.mcp.prose_synthesizer import synthesize, SynthesisResult
    from src.mcp.agent_memory import AgentMemory
    from src.mcp.comprehension_models import PersonProfile, Location, LocationLink

    state_updates: dict = {}

    # Resolve per-session memory objects
    mem = CHAT_MEMORY.get(uid)
    if mem is None:
        mem = AgentMemory()
        CHAT_MEMORY[uid] = mem
    known_persons = CHAT_PERSONS.get(uid, [])
    known_locations = CHAT_LOCATIONS.get(uid, [])

    # Convert dicts → dataclass instances
    _persons = None
    if known_persons:
        _persons = []
        for pd in known_persons:
            locs = [LocationLink(
                location_name=ld.get("location", ""),
                connection=ld.get("connection", ""))
                for ld in pd.get("locations", [])]
            _persons.append(PersonProfile(
                name=pd.get("name"),
                relationship_to_querent=pd.get("relationship_to_querent"),
                relationships_to_others=pd.get("relationships_to_others", []),
                memories=pd.get("memories", []),
                significant_places=pd.get("significant_places", []),
                chart_id=pd.get("chart_id"),
                locations=locs,
            ))
    _locations = None
    if known_locations:
        _locations = []
        for ld in known_locations:
            conn = [(cp.get("person", ""), cp.get("connection", ""))
                    for cp in ld.get("connected_persons", [])]
            _locations.append(Location(
                name=ld.get("name", ""),
                location_type=ld.get("location_type"),
                connected_persons=conn,
                relevance=ld.get("relevance"),
            ))

    pending_clar = None
    actual_question = question
    if pending_q:
        pending_clar = question
        actual_question = pending_q
        state_updates["mcp_pending_question"] = ""
        mem.answer_all_pending_bot_questions(question)

    meta: dict = {"mode": mode, "voice": voice}

    try:
        packet = build_reading(
            actual_question, chart,
            house_system=house_system,
            include_sabians=False,
            include_interp_text=True,
            max_aspects=12,
            api_key=api_key,
            agent_notes=agent_notes,
            chart_b=chart_b,
            known_persons=_persons,
            known_locations=_locations,
            pending_clarification=pending_clar,
            agent_memory=mem,
        )

        # Clarification request
        if packet._clarification:
            clar = packet._clarification
            state_updates["mcp_pending_question"] = actual_question
            follow_up = clar.get(
                "follow_up_question",
                "Could you tell me more about what you'd like to know?",
            )
            meta["_is_clarification"] = True
            return follow_up, meta, state_updates

        meta["domain"] = packet.domain
        meta["subtopic"] = packet.subtopic
        meta["confidence"] = packet.confidence
        meta["question_type"] = packet.question_type
        meta["comprehension_note"] = packet.comprehension_note

        # Accumulate persons & locations
        if packet.persons:
            merge_chat_persons(uid, packet.persons)
        if packet.locations:
            merge_chat_locations(uid, packet.locations)

        # Accumulate agent notes
        turn_note = meta.get("comprehension_note", "")
        if turn_note:
            existing = agent_notes or ""
            state_updates["mcp_agent_notes"] = (
                (existing + "\n" if existing else "") + turn_note
            )

        # Dev trace
        _dev = {
            "question": actual_question,
            "step1_comprehension": {
                "domain": packet.domain,
                "subtopic": packet.subtopic,
                "confidence": packet.confidence,
                "question_type": packet.question_type,
                "paraphrase": packet.paraphrase or "",
            },
            "step2_factor_resolution": {
                "merged_factors": getattr(packet, "debug_relevant_factors", []),
                "relevant_objects": getattr(packet, "debug_relevant_objects", []),
            },
            "step3_circuit": getattr(packet, "debug_circuit_summary", {}),
            "step5_synthesis": {},
        }

    except Exception as exc:
        return (
            f"Failed to build reading: {exc}",
            meta,
            state_updates,
        )

    # Synthesis mode detection
    _td = packet.temporal_dimension or "natal"
    if _td == "synastry" or (
        packet.subject_config == "dyadic"
        and packet.chart_b_full_placements
    ):
        _synth_mode = "synastry"
    elif _td in ("transit", "cycle", "timing_predict", "solar_return"):
        _synth_mode = "transit"
    else:
        _synth_mode = "natal"

    if not api_key:
        meta.update(backend="fallback", model="none")
        return (
            "No OpenRouter API key configured. "
            "Set OPENROUTER_API_KEY in .env to enable chat.",
            meta,
            state_updates,
        )

    try:
        result: SynthesisResult = synthesize(
            packet,
            backend="openrouter",
            model=model,
            mode=_synth_mode,
            voice=voice.lower(),
            api_key=api_key,
            agent_memory=mem,
        )
        meta.update(
            model=result.model,
            backend=result.backend,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        )
        _dev["step5_synthesis"] = {
            "model": result.model,
            "backend": result.backend,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        }
        CHAT_DEV_TRACE[uid] = _dev
        return result.text, meta, state_updates

    except Exception as exc:
        meta.update(backend="fallback", model="none", llm_error=str(exc))
        CHAT_DEV_TRACE[uid] = _dev
        return (
            f"OpenRouter call failed: {exc}\n\n"
            "Check API key and model availability.",
            meta,
            state_updates,
        )
