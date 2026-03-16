"""
chat_ui.py — Streamlit chat widget wired to the MCP reading pipeline.

Renders a full chat interface below the chart.  The user types any
astrology question; the engine builds a ReadingPacket and synthesizes
prose via the configured backend (default: OpenRouter).

Usage in test_calc_v2.py (after render_guided_wizard()):
    from src.mcp.chat_ui import render_chat_widget
    render_chat_widget()
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import streamlit as st

from src.mcp.reading_engine import build_reading
from src.mcp.prose_synthesizer import (
    DEFAULT_OPENROUTER_MODEL,
    SynthesisResult,
    synthesize,
)

# ── Model catalogues ─────────────────────────────────────────────────────────

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

# ── Session-state helpers ─────────────────────────────────────────────────────

_HISTORY_KEY = "mcp_chat_history"   # List[Dict]  — {"role", "content", "meta"}
_API_KEY_KEY = "mcp_openrouter_key"
_MODEL_KEY = "mcp_model"
_HS_KEY = "mcp_house_system"


def _init_state() -> None:
    st.session_state.setdefault(_HISTORY_KEY, [])
    if _MODEL_KEY not in st.session_state:
        st.session_state[_MODEL_KEY] = DEFAULT_OPENROUTER_MODEL
    if _HS_KEY not in st.session_state:
        st.session_state[_HS_KEY] = "Placidus"
    if _API_KEY_KEY not in st.session_state:
        # Pre-fill from env var if available
        st.session_state[_API_KEY_KEY] = os.environ.get("OPENROUTER_API_KEY", "")


# ── Main widget ───────────────────────────────────────────────────────────────

def render_chat_widget() -> None:
    """Render the full chat widget.  Call once per Streamlit re-run."""

    _init_state()

    # ── Settings expander ────────────────────────────────────────────────────
    with st.expander("⚙️ Chat settings", expanded=False):
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            api_key_input = st.text_input(
                "OpenRouter API Key",
                value=st.session_state[_API_KEY_KEY],
                type="password",
                key="mcp_api_key_input",
                help="Get a free key at openrouter.ai. Stored only in session memory.",
            )
            st.session_state[_API_KEY_KEY] = api_key_input

        with col2:
            model_index = (
                _OPENROUTER_MODELS.index(st.session_state[_MODEL_KEY])
                if st.session_state[_MODEL_KEY] in _OPENROUTER_MODELS
                else 0
            )
            chosen_model = st.selectbox(
                "Model",
                options=_OPENROUTER_MODELS,
                index=model_index,
                key="mcp_model_select",
            )
            st.session_state[_MODEL_KEY] = chosen_model

        with col3:
            hs_index = (
                _HOUSE_SYSTEMS.index(st.session_state[_HS_KEY])
                if st.session_state[_HS_KEY] in _HOUSE_SYSTEMS
                else 0
            )
            chosen_hs = st.selectbox(
                "House system",
                options=_HOUSE_SYSTEMS,
                index=hs_index,
                key="mcp_hs_select",
            )
            st.session_state[_HS_KEY] = chosen_hs

    # ── Chat header ──────────────────────────────────────────────────────────
    col_title, col_clear = st.columns([6, 1])
    with col_title:
        st.markdown("### 🔮 Ask your chart")
    with col_clear:
        if st.button("🗑 Clear", key="mcp_clear_chat", help="Clear chat history"):
            st.session_state[_HISTORY_KEY] = []
            st.rerun()

    # ── Render existing history ───────────────────────────────────────────────
    history: List[Dict[str, Any]] = st.session_state[_HISTORY_KEY]

    for msg in history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("meta") and not msg["meta"].get("fallback_to_interp"):
                meta = msg["meta"]
                caption_parts = []
                if meta.get("model"):
                    caption_parts.append(f"model: `{meta['model']}`")
                if meta.get("total_tokens"):
                    caption_parts.append(f"tokens: {meta['total_tokens']}")
                if meta.get("domain"):
                    caption_parts.append(f"topic: {meta['domain']}")
                if meta.get("confidence") is not None:
                    caption_parts.append(f"confidence: {meta['confidence']:.0%}")
                if caption_parts:
                    st.caption(" · ".join(caption_parts))

    # ── Input ────────────────────────────────────────────────────────────────
    prompt = st.chat_input("Ask your chart anything…", key="mcp_chat_input")

    if prompt:
        # Add user message to history and display immediately
        history.append({"role": "user", "content": prompt, "meta": {}})
        with st.chat_message("user"):
            st.markdown(prompt)

        # ── Get chart ────────────────────────────────────────────────────────
        chart = st.session_state.get("last_chart")
        if chart is None:
            error_text = (
                "⚠️ No chart loaded yet.  Please calculate a chart first "
                "(fill in the birth data above and press the calculate button)."
            )
            history.append({"role": "assistant", "content": error_text, "meta": {}})
            with st.chat_message("assistant"):
                st.warning(error_text)
            return

        # ── Build reading + synthesize ────────────────────────────────────────
        api_key: str = st.session_state[_API_KEY_KEY]
        model: str = st.session_state[_MODEL_KEY]
        house_system: str = st.session_state[_HS_KEY]

        with st.chat_message("assistant"):
            with st.spinner("Reading the chart…"):
                response_text, meta = _generate_response(
                    question=prompt,
                    chart=chart,
                    house_system=house_system,
                    api_key=api_key,
                    model=model,
                )
            st.markdown(response_text)
            if meta and not meta.get("fallback_to_interp"):
                caption_parts = []
                if meta.get("model"):
                    caption_parts.append(f"model: `{meta['model']}`")
                if meta.get("total_tokens"):
                    caption_parts.append(f"tokens: {meta['total_tokens']}")
                if meta.get("domain"):
                    caption_parts.append(f"topic: {meta['domain']}")
                if meta.get("confidence") is not None:
                    caption_parts.append(f"confidence: {meta['confidence']:.0%}")
                if caption_parts:
                    st.caption(" · ".join(caption_parts))

        history.append({
            "role": "assistant",
            "content": response_text,
            "meta": meta,
        })

        # If fallback redirected to the interpretation expander,
        # rerun so it takes effect (the flag was set during generation,
        # but the expander is already rendered above us on this page).
        if meta.get("fallback_to_interp"):
            st.rerun()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _generate_response(
    *,
    question: str,
    chart: Any,
    house_system: str,
    api_key: str,
    model: str,
) -> tuple[str, Dict[str, Any]]:
    """Run the full MCP pipeline for a single question.

    Returns (response_text, meta_dict).
    meta will include 'fallback_to_interp': True when we redirect to
    the interpretation expander instead of returning prose.
    """
    meta: Dict[str, Any] = {}

    try:
        packet = build_reading(
            question,
            chart,
            house_system=house_system,
            include_sabians=False,
            include_interp_text=True,
            max_aspects=12,
        )
        meta["domain"] = packet.domain
        meta["subtopic"] = packet.subtopic
        meta["confidence"] = packet.confidence

    except Exception as exc:
        return (
            f"⚠️ Failed to build reading packet: `{exc}`\n\n"
            "This may mean the chart data is in an unexpected format.",
            meta,
        )

    # Decide backend
    if not api_key and not os.environ.get("OPENROUTER_API_KEY"):
        # No key at all — redirect to interp expander immediately
        st.session_state["mcp_interp_expander_open"] = True
        msg = (
            "ℹ️ **No OpenRouter API key is configured.**\n\n"
            "Enter your key in the **⚙️ Chat settings** expander above, "
            "then ask again.  \n\n"
            "The **📜 Interpretation** section below has been opened — "
            "it contains the full pre-computed natal reading."
        )
        meta["backend"] = "fallback"
        meta["model"] = "none"
        meta["fallback_to_interp"] = True
        return msg, meta

    effective_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
    backend = "openrouter"

    try:
        result: SynthesisResult = synthesize(
            packet,
            backend=backend,
            model=model,
            mode="natal",
            api_key=effective_key,
        )
        meta["model"] = result.model
        meta["backend"] = result.backend
        meta["prompt_tokens"] = result.prompt_tokens
        meta["completion_tokens"] = result.completion_tokens
        meta["total_tokens"] = result.total_tokens
        return result.text, meta

    except Exception as exc:
        # LLM call failed — open the interp expander and report clearly
        st.session_state["mcp_interp_expander_open"] = True
        error_detail = str(exc)
        msg = (
            f"⚠️ **OpenRouter call failed.**\n\n"
            f"```\n{error_detail}\n```\n\n"
            "Common causes:\n"
            "- Invalid or expired API key\n"
            "- Model name not available on your OpenRouter account\n"
            "- Network error\n\n"
            "The **📜 Interpretation** section below has been opened with "
            "the pre-computed natal reading."
        )
        meta["backend"] = "fallback"
        meta["model"] = "none"
        meta["llm_error"] = error_detail
        meta["fallback_to_interp"] = True
        return msg, meta
