"""Chat tab — message rendering, send/clear, model/voice controls."""
from __future__ import annotations

import logging
from typing import Any, Callable

from nicegui import run, ui

from config import get_secret
from src.mcp.chat_pipeline import (
    CHAT_MEMORY, CHAT_DEV_TRACE, CHAT_PERSONS, CHAT_LOCATIONS,
    run_pipeline,
)
from src.nicegui_state import get_chart_object, get_chart_2_object
from src.ui.auth import get_user_id

_log = logging.getLogger(__name__)


def build(
    state: dict,
    _form: dict,
) -> dict[str, Any]:
    """Build the Chat tab panel contents.

    Returns ``{"chat_no_chart_notice": ui.label}``.
    """
    # ── Constants ──────────────────────────────────────────────────
    _OPENROUTER_MODELS = [
        "google/gemini-2.0-flash-001",
        "google/gemini-2.5-pro-preview",
        "anthropic/claude-sonnet-4-5",
        "anthropic/claude-3-5-haiku",
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "meta-llama/llama-4-scout",
        "mistralai/mistral-large",
    ]
    _CHAT_MODES = ["Query", "Map", "Execute"]
    _VOICE_MODES = ["Plain", "Circuit"]
    _EXAMPLE_PROMPTS = {
        "natal": [
            "What are the main power planets of my chart, and how do they drive my motivations?",
            "Where do I have the most internal 'friction' in my personality?",
            "How can I best structure my career to be sustainable and fulfilling?",
        ],
        "synastry": [
            "Which parts of my personality get amplified most when we are together?",
            "Where do our communication styles naturally sync up or short-circuit?",
            "What is our biggest relationship challenge?",
        ],
        "transit": [
            "Which areas of my life are under the most 'cosmic pressure' right now?",
            "I feel a shift in my energy lately — is a current planet poking a sensitive spot?",
            "Is this a better time to push forward or to sit back and recalibrate?",
        ],
    }

    # ── Two-column layout ──────────────────────────────────────────
    with ui.row().classes("w-full gap-4 items-start"):

        # ── LEFT: Chat column ──────────────────────────────────────
        with ui.column().classes("col-grow"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Ask your chart").classes("text-h6")
                chat_clear_btn = ui.button(
                    icon="delete", color="grey",
                ).props("flat dense size=sm").tooltip("Clear chat history")

            chat_no_chart_notice = ui.label(
                "No chart loaded.  Calculate or load a chart using the"
                " birth data panel to get meaningful responses."
            ).classes(
                "text-body2 q-pa-xs q-mt-xs rounded-borders"
            ).style(
                "background: rgba(255,193,7,0.12);"
                " border: 1px solid rgba(255,193,7,0.35);"
                " color: #b8860b;"
            )
            chat_no_chart_notice.set_visibility(
                get_chart_object(state) is None
            )

            chat_scroll = ui.scroll_area().classes(
                "w-full border rounded q-pa-sm"
            ).style("height: 55vh; background: #0e1117;")
            with chat_scroll:
                chat_messages_col = ui.column().classes("w-full gap-2")

            chat_examples_container = ui.column().classes("w-full gap-1 q-mt-xs")

            # forward-declared so _populate_example_prompts can reference it
            _send_ref: list[Callable] = []

            def _populate_example_prompts():
                """Fill the example-prompt chips based on chat state."""
                chat_examples_container.clear()
                history = state.get("mcp_chat_history", [])
                if history:
                    chat_examples_container.set_visibility(False)
                    return
                chat_examples_container.set_visibility(True)
                syn = state.get("synastry_mode", False)
                tran = state.get("transit_mode", False)
                mode_key = "synastry" if syn else ("transit" if tran else "natal")
                prompts = _EXAMPLE_PROMPTS.get(mode_key, _EXAMPLE_PROMPTS["natal"])
                with chat_examples_container:
                    ui.label("Try asking…").classes("text-caption text-grey-6")
                    for q in prompts:
                        _q = q
                        ui.button(
                            _q,
                            on_click=lambda _q=_q: _send_ref[0](_q),
                        ).props("flat dense no-caps align=left").classes(
                            "text-body2 text-left w-full"
                        )

            with ui.row().classes("w-full items-center gap-2 q-mt-xs"):
                chat_input = ui.input(
                    placeholder="Ask your chart anything…",
                ).classes("col-grow").props('outlined dense')
                chat_send_btn = ui.button(
                    icon="send", color="primary",
                ).props("flat dense")
                chat_spinner = ui.spinner("dots", size="sm")
                chat_spinner.set_visibility(False)

        # ── RIGHT: Controls column ─────────────────────────────────
        with ui.column().classes("w-64 gap-3"):
            chat_model_sel = ui.select(
                _OPENROUTER_MODELS,
                label="Model",
                value=state.get("mcp_model", _OPENROUTER_MODELS[0]),
            ).props("dense outlined").classes("w-full")
            chat_model_sel.on_value_change(
                lambda e: state.update(mcp_model=e.value)
            )

            chat_mode_radio = ui.radio(
                _CHAT_MODES,
                value=state.get("mcp_chat_mode", "Query"),
            ).props("dense inline")
            chat_mode_radio.on_value_change(
                lambda e: state.update(mcp_chat_mode=e.value)
            )

            chat_voice_radio = ui.radio(
                _VOICE_MODES,
                value=state.get("mcp_voice_mode", "Plain"),
            ).props("dense inline")
            chat_voice_radio.on_value_change(
                lambda e: state.update(mcp_voice_mode=e.value)
            )

            ui.separator()
            ui.label("Voice EQ").classes("text-caption text-grey-6")
            with ui.column().classes("w-full gap-1"):
                ui.label("Bass").classes("text-caption")
                chat_eq_bass = ui.slider(
                    min=-20, max=20, step=2,
                    value=state.get("mcp_eq_bass", 0.0),
                ).props("dense label-always")
                chat_eq_bass.on_value_change(
                    lambda e: state.update(mcp_eq_bass=e.value)
                )

                ui.label("Mids").classes("text-caption")
                chat_eq_mids = ui.slider(
                    min=-20, max=20, step=2,
                    value=state.get("mcp_eq_mids", 0.0),
                ).props("dense label-always")
                chat_eq_mids.on_value_change(
                    lambda e: state.update(mcp_eq_mids=e.value)
                )

                ui.label("Treble").classes("text-caption")
                chat_eq_treble = ui.slider(
                    min=-20, max=20, step=2,
                    value=state.get("mcp_eq_treble", 0.0),
                ).props("dense label-always")
                chat_eq_treble.on_value_change(
                    lambda e: state.update(mcp_eq_treble=e.value)
                )

            ui.separator()
            chat_dev_exp = ui.expansion(
                "Dev Trace", icon="science",
            ).classes("w-full").props("dense")
            with chat_dev_exp:
                chat_dev_content = ui.html("").classes(
                    "text-caption"
                ).style("max-height: 30vh; overflow-y: auto;")

    # ── Chat helpers & handlers ────────────────────────────────────

    def _render_chat_history():
        """Re-render the full chat history into the message column."""
        chat_messages_col.clear()
        history = state.get("mcp_chat_history", [])
        with chat_messages_col:
            for msg in history:
                role = msg.get("role", "user")
                sent = role == "user"
                ui.chat_message(
                    text=msg.get("content", ""),
                    name="You" if sent else "Rosetta",
                    sent=sent,
                    stamp=msg.get("caption", ""),
                ).classes("w-full")

    def _append_chat_bubble(role: str, text: str, caption: str = ""):
        """Append a single chat bubble to the message column."""
        with chat_messages_col:
            sent = role == "user"
            ui.chat_message(
                text=text,
                name="You" if sent else "Rosetta",
                sent=sent,
                stamp=caption,
            ).classes("w-full")

    def _build_caption(meta: dict) -> str:
        """Build a metadata caption string from response metadata."""
        parts = []
        if meta.get("model"):
            parts.append(meta["model"].split("/")[-1])
        if meta.get("total_tokens"):
            parts.append(f"{meta['total_tokens']} tok")
        if meta.get("domain"):
            parts.append(meta["domain"])
        if meta.get("confidence") is not None:
            parts.append(f"{meta['confidence']:.0%}")
        if meta.get("voice"):
            parts.append(meta["voice"])
        return " · ".join(parts)

    def _render_dev_trace(trace: dict):
        """Render the developer trace/debug panel content."""
        if not trace:
            chat_dev_content.content = "<em>No trace yet.</em>"
            return
        import html as _html_mod
        esc = _html_mod.escape
        parts = []
        q = trace.get("question", "")
        if q:
            parts.append(f"<b>Question:</b> {esc(q)}")
        s1 = trace.get("step1_comprehension", {})
        if s1:
            parts.append(f"<b>Domain:</b> {esc(str(s1.get('domain', '')))} "
                         f"/ {esc(str(s1.get('subtopic', '')))}")
            parts.append(f"<b>Type:</b> {esc(str(s1.get('question_type', '')))}")
            parts.append(f"<b>Confidence:</b> {s1.get('confidence', 0):.0%}")
            para = s1.get("paraphrase", "")
            if para:
                parts.append(f"<b>Understood as:</b> <em>{esc(para)}</em>")
        s2 = trace.get("step2_factor_resolution", {})
        if s2:
            mf = s2.get("merged_factors", [])
            ro = s2.get("relevant_objects", [])
            if mf:
                parts.append(f"<b>Factors:</b> {esc(', '.join(str(f) for f in mf))}")
            if ro:
                parts.append(f"<b>Objects:</b> {esc(', '.join(str(o) for o in ro))}")
        s3 = trace.get("step3_circuit", {})
        if s3:
            parts.append(f"<b>Shapes:</b> {s3.get('shapes_count', 0)}")
            seeds = s3.get("narrative_seeds", [])
            if seeds:
                parts.append("<b>Seeds:</b><ul>" + "".join(
                    f"<li>{esc(str(s))}</li>" for s in seeds[:5]
                ) + "</ul>")
        s5 = trace.get("step5_synthesis", {})
        if s5:
            parts.append(f"<b>Synthesis:</b> {esc(str(s5.get('model', '')))} "
                         f"({s5.get('prompt_tokens', 0)}+{s5.get('completion_tokens', 0)} tok)")
        chat_dev_content.content = "<br>".join(parts) if parts else "<em>Empty trace.</em>"

    def _get_api_key() -> str:
        """Retrieve the OpenRouter API key from secrets."""
        key = get_secret("openrouter", "api_key", default="")
        if key and key != "PASTE_YOUR_KEY_HERE":
            return key
        return ""

    async def _send_chat_message(text: str | None = None):
        """Send a user message through the MCP chat pipeline."""
        prompt = text or chat_input.value
        if not prompt or not prompt.strip():
            return
        prompt = prompt.strip()

        chat_input.value = ""
        chat_examples_container.set_visibility(False)

        chart_obj = get_chart_object(state)
        if chart_obj is None:
            _append_chat_bubble("user", prompt)
            err_msg = ("No chart loaded yet. Please calculate a "
                       "chart first using the birth data form above.")
            _append_chat_bubble("assistant", err_msg)
            history = state.get("mcp_chat_history", [])
            history.append({"role": "user", "content": prompt, "caption": ""})
            history.append({"role": "assistant", "content": err_msg, "caption": ""})
            state["mcp_chat_history"] = history
            return

        _append_chat_bubble("user", prompt)
        history = state.get("mcp_chat_history", [])
        history.append({"role": "user", "content": prompt, "caption": ""})

        chat_spinner.set_visibility(True)
        chat_send_btn.disable()

        chart_b = get_chart_2_object(state) if (
            state.get("synastry_mode") or state.get("transit_mode")
        ) else None
        hs = state.get("house_system", "placidus")

        uid = get_user_id() or "anon"
        _api_key = _get_api_key()
        _model = state.get("mcp_model", "google/gemini-2.0-flash-001")
        _mode = state.get("mcp_chat_mode", "Query")
        _voice = state.get("mcp_voice_mode", "Plain")
        _agent_notes = state.get("mcp_agent_notes", "")
        _pending_q = state.get("mcp_pending_question", "")

        try:
            response_text, meta, state_updates = await run.io_bound(
                run_pipeline, prompt, chart_obj, chart_b, hs,
                uid=uid,
                api_key=_api_key,
                model=_model,
                mode=_mode,
                voice=_voice,
                agent_notes=_agent_notes,
                pending_q=_pending_q,
            )
        except Exception as exc:
            response_text = f"Error: {exc}"
            meta = {}
            state_updates = {}

        for k, v in state_updates.items():
            state[k] = v

        caption = _build_caption(meta)
        _append_chat_bubble("assistant", response_text, caption)
        history.append({
            "role": "assistant",
            "content": response_text,
            "caption": caption,
        })
        state["mcp_chat_history"] = history

        _render_dev_trace(CHAT_DEV_TRACE.get(uid, {}))

        chat_spinner.set_visibility(False)
        chat_send_btn.enable()
        chat_scroll.scroll_to(percent=100)

    # Store reference so example-prompt buttons can call it
    _send_ref.append(_send_chat_message)

    chat_send_btn.on_click(lambda: _send_chat_message())
    chat_input.on("keydown.enter", lambda: _send_chat_message())

    def _clear_chat():
        """Reset chat history, agent notes, and trace state."""
        state["mcp_chat_history"] = []
        state["mcp_agent_notes"] = ""
        state["mcp_pending_question"] = ""
        uid = get_user_id() or "anon"
        CHAT_MEMORY.pop(uid, None)
        CHAT_DEV_TRACE.pop(uid, None)
        CHAT_PERSONS.pop(uid, None)
        CHAT_LOCATIONS.pop(uid, None)
        chat_messages_col.clear()
        chat_dev_content.content = ""
        _populate_example_prompts()

    chat_clear_btn.on_click(_clear_chat)

    _render_chat_history()
    _populate_example_prompts()

    uid_init = get_user_id() or "anon"
    _render_dev_trace(CHAT_DEV_TRACE.get(uid_init, {}))

    return {"chat_no_chart_notice": chat_no_chart_notice}
