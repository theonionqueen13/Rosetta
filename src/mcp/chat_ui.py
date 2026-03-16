"""
chat_ui.py — Streamlit chat widget wired to the MCP reading pipeline.

Layout:
    [  wide chat column (dark bg)  ] [ narrow right column ]
                                       - Agent notes (read-only)
                                       - Model picker
                                       - Ask / Plan / Agent mode picker
                                       - House system picker

API key is read from .streamlit/secrets.toml [openrouter] api_key
then falls back to OPENROUTER_API_KEY env var.  No key entry in UI.
"""

from __future__ import annotations

import html as _html
import os
from typing import Any, Dict, List, Optional

import streamlit as st

from src.mcp.reading_engine import build_reading
from src.mcp.prose_synthesizer import (
    DEFAULT_OPENROUTER_MODEL,
    SynthesisResult,
    synthesize,
)

# ── Catalogue constants ───────────────────────────────────────────────────────

_OPENROUTER_MODELS: List[str] = [
    "google/gemini-2.0-flash-001",
    "google/gemini-2.5-pro-preview",
    "anthropic/claude-sonnet-4-5",
    "anthropic/claude-3-5-haiku",
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "meta-llama/llama-4-scout",
    "mistralai/mistral-large",
]

_HOUSE_SYSTEMS: List[str] = ["Placidus", "Whole Sign", "Koch", "Equal", "Campanus"]

_CHAT_MODES: List[str] = ["Ask", "Plan", "Agent"]
_VOICE_MODES: List[str] = ["Plain", "Circuit"]

# ── Session-state keys ────────────────────────────────────────────────────────

_HISTORY_KEY = "mcp_chat_history"   # List[Dict] — {role, content, meta}
_MODEL_KEY   = "mcp_model"
_HS_KEY      = "mcp_house_system"
_NOTES_KEY   = "mcp_agent_notes"    # str — accumulated across conversation
_MODE_KEY    = "mcp_chat_mode"      # "Ask" | "Plan" | "Agent"
_VOICE_KEY   = "mcp_voice_mode"    # "Plain" | "Circuit"

# ── CSS injection ─────────────────────────────────────────────────────────────

_CHAT_CSS = """
<style>
/* Dark tinted background on the chat (left) column.
   The :has() selector targets the block that contains the chat input,
   the first child of which is our chat pane. */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatInput"])
    > div:first-child {
    background: #0e1117;
    border-radius: 10px;
    padding: 0.75rem 1rem 0.25rem 1rem;
    border: 1px solid #1f2937;
}

/* Notes box in right column */
.mcp-notes-box {
    background: #0d1117;
    color: #58a6ff;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 0.75em;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 8px 10px;
    min-height: 180px;
    max-height: 360px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.5;
}

.mcp-notes-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 3px;
}
</style>
"""

# ── Key resolution ────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    """Read OpenRouter key: secrets.toml [openrouter].api_key -> env var."""
    try:
        key = st.secrets.get("openrouter", {}).get("api_key", "")
        if key and key != "PASTE_YOUR_KEY_HERE":
            return key
    except Exception:
        pass
    return os.environ.get("OPENROUTER_API_KEY", "")


# ── Session init ──────────────────────────────────────────────────────────────

def _init_state() -> None:
    st.session_state.setdefault(_HISTORY_KEY, [])
    st.session_state.setdefault(_MODEL_KEY, DEFAULT_OPENROUTER_MODEL)
    st.session_state.setdefault(_HS_KEY, "Placidus")
    st.session_state.setdefault(_NOTES_KEY, "")
    st.session_state.setdefault(_MODE_KEY, "Ask")
    st.session_state.setdefault(_VOICE_KEY, "Plain")


# ── Public entry point ────────────────────────────────────────────────────────

def render_chat_widget() -> None:
    """Render the two-column chat widget.  Call once per Streamlit re-run."""

    _init_state()
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    col_chat, col_right = st.columns([4, 1.5], gap="medium")

    # ════════════════════════════════════════════════════════════════════════
    # RIGHT COLUMN — agent notes + controls
    # ════════════════════════════════════════════════════════════════════════
    with col_right:
        st.markdown('<div class="mcp-notes-label">Agent notes</div>',
                    unsafe_allow_html=True)
        notes_raw = st.session_state.get(_NOTES_KEY, "") or "(no notes yet)"
        st.markdown(
            f'<div class="mcp-notes-box">{_html.escape(notes_raw)}</div>',
            unsafe_allow_html=True,
        )

        # Memory controls (stubbed for future wiring)
        b1, b2 = st.columns([1, 1])
        if b1.button("Save to Memory", key="mcp_memory_save"):
            st.session_state[_NOTES_KEY] = (
                st.session_state.get(_NOTES_KEY, "")
                + "\n[Saved current conversation to memory]"
            )
        if b2.button("Manage Memory", key="mcp_memory_manage"):
            st.session_state[_NOTES_KEY] = (
                st.session_state.get(_NOTES_KEY, "")
                + "\n[Open memory manager (not yet implemented)]"
            )

        st.markdown("---")

        # Model picker
        model_idx = (
            _OPENROUTER_MODELS.index(st.session_state[_MODEL_KEY])
            if st.session_state[_MODEL_KEY] in _OPENROUTER_MODELS
            else 0
        )
        st.session_state[_MODEL_KEY] = st.selectbox(
            "Model",
            options=_OPENROUTER_MODELS,
            index=model_idx,
            key="mcp_model_select",
        )

        # Mode picker
        mode_idx = (
            _CHAT_MODES.index(st.session_state[_MODE_KEY])
            if st.session_state[_MODE_KEY] in _CHAT_MODES
            else 0
        )
        st.session_state[_MODE_KEY] = st.radio(
            "Mode",
            options=_CHAT_MODES,
            index=mode_idx,
            key="mcp_mode_radio",
            help=(
                "**Ask** — single-turn Q&A\n\n"
                "**Plan** — multi-step analysis outline *(coming soon)*\n\n"
                "**Agent** — autonomous chart research loop *(coming soon)*"
            ),
        )

        # Voice toggle
        voice_idx = (
            _VOICE_MODES.index(st.session_state[_VOICE_KEY])
            if st.session_state[_VOICE_KEY] in _VOICE_MODES
            else 0
        )
        st.session_state[_VOICE_KEY] = st.radio(
            "Voice",
            options=_VOICE_MODES,
            index=voice_idx,
            key="mcp_voice_radio",
            help=(
                "**Plain** — warm, psychological language\n\n"
                "**Circuit** — energy/flow/friction metaphor"
            ),
        )

    # ════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN — chat
    # ════════════════════════════════════════════════════════════════════════
    with col_chat:

        # Header row
        col_title, col_clear = st.columns([7, 1])
        with col_title:
            st.markdown("### 🔮 Ask your chart")
        with col_clear:
            if st.button("🗑", key="mcp_clear_chat", help="Clear chat history"):
                st.session_state[_HISTORY_KEY] = []
                st.session_state[_NOTES_KEY] = ""
                st.session_state[_VOICE_KEY] = "Plain"
                st.rerun()

        # History replay
        history: List[Dict[str, Any]] = st.session_state[_HISTORY_KEY]
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if (msg["role"] == "assistant"
                        and msg.get("meta")
                        and not msg["meta"].get("fallback_to_interp")):
                    _render_caption(msg["meta"])

        # Chat input (must be inside the column to make :has() CSS work)
        prompt = st.chat_input("Ask your chart anything…", key="mcp_chat_input")

    # ── Handle new prompt ─────────────────────────────────────────────────
    # Done outside the column context so st.rerun() works without nesting
    if prompt:
        history.append({"role": "user", "content": prompt, "meta": {}})

        chart = st.session_state.get("last_chart")
        if chart is None:
            history.append({
                "role": "assistant",
                "content": (
                    "⚠️ No chart loaded yet. Please calculate a chart first "
                    "(fill in the birth data above and press the calculate button)."
                ),
                "meta": {},
            })
            st.rerun()
            return

        with st.spinner("Reading the chart…"):
            response_text, meta = _generate_response(
                question=prompt,
                chart=chart,
                house_system=st.session_state[_HS_KEY],
                api_key=_get_api_key(),
                model=st.session_state[_MODEL_KEY],
                mode=st.session_state[_MODE_KEY],
                voice=st.session_state.get(_VOICE_KEY, "Plain"),
                agent_notes=st.session_state.get(_NOTES_KEY, ""),
                render_result=st.session_state.get("render_result"),
            )

        # Accumulate agent notes from this turn
        turn_note = meta.get("comprehension_note", "")
        if turn_note:
            existing = st.session_state.get(_NOTES_KEY, "")
            st.session_state[_NOTES_KEY] = (
                (existing + "\n" if existing else "") + turn_note
            )

        history.append({"role": "assistant", "content": response_text, "meta": meta})
        st.rerun()


# ── Caption helper ────────────────────────────────────────────────────────────

def _render_caption(meta: Dict[str, Any]) -> None:
    parts: List[str] = []
    if meta.get("model"):
        parts.append(f"model: `{meta['model']}`")
    if meta.get("total_tokens"):
        parts.append(f"tokens: {meta['total_tokens']}")
    if meta.get("domain"):
        parts.append(f"topic: {meta['domain']}")
    if meta.get("question_type"):
        parts.append(f"type: {meta['question_type']}")
    if meta.get("confidence") is not None:
        parts.append(f"confidence: {meta['confidence']:.0%}")
    if meta.get("voice"):
        parts.append(f"voice: {meta['voice']}")
    if meta.get("mode"):
        parts.append(f"mode: {meta['mode']}")
    if parts:
        st.caption(" · ".join(parts))


# ── Generation ────────────────────────────────────────────────────────────────

def _generate_response(
    *,
    question: str,
    chart: Any,
    house_system: str,
    api_key: str,
    model: str,
    mode: str = "Ask",
    voice: str = "Plain",
    agent_notes: str = "",
    render_result: Any = None,
) -> tuple[str, Dict[str, Any]]:
    """Run the full MCP pipeline. Returns (response_text, meta)."""

    meta: Dict[str, Any] = {"mode": mode, "voice": voice}
    voice_lower = voice.lower()

    try:
        packet = build_reading(
            question,
            chart,
            house_system=house_system,
            include_sabians=False,
            include_interp_text=True,
            max_aspects=12,
            api_key=api_key,
            agent_notes=agent_notes,
            render_result=render_result,
        )
        meta["domain"]     = packet.domain
        meta["subtopic"]   = packet.subtopic
        meta["confidence"] = packet.confidence
        meta["question_type"] = packet.question_type
        meta["comprehension_note"] = packet.comprehension_note

    except Exception as exc:
        return (
            f"⚠️ Failed to build reading packet: `{exc}`\n\n"
            "This may mean the chart data is in an unexpected format.",
            meta,
        )

    # No key — redirect to interpretation expander
    if not api_key:
        st.session_state["mcp_interp_expander_open"] = True
        meta.update({"backend": "fallback", "model": "none", "fallback_to_interp": True})
        return (
            "ℹ️ **No OpenRouter API key configured.**\n\n"
            "Paste your key into `.streamlit/secrets.toml` under `[openrouter]`, "
            "then restart Streamlit.\n\n"
            "The **📜 Interpretation** section below has been opened with "
            "the pre-computed natal reading.",
            meta,
        )

    try:
        result: SynthesisResult = synthesize(
            packet,
            backend="openrouter",
            model=model,
            mode="natal",
            voice=voice_lower,
            api_key=api_key,
        )
        meta.update({
            "model":             result.model,
            "backend":           result.backend,
            "prompt_tokens":     result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens":      result.total_tokens,
        })
        return result.text, meta

    except Exception as exc:
        st.session_state["mcp_interp_expander_open"] = True
        err = str(exc)
        meta.update({
            "backend":           "fallback",
            "model":             "none",
            "llm_error":         err,
            "fallback_to_interp": True,
        })
        return (
            f"⚠️ **OpenRouter call failed.**\n\n"
            f"```\n{err}\n```\n\n"
            "Common causes: invalid/expired key, model unavailable, network error.\n\n"
            "The **📜 Interpretation** section below has been opened.",
            meta,
        )
