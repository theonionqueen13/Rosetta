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
import json
import os
import uuid
from typing import Any, Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components

from src.mcp.reading_engine import build_reading
from src.mcp.prose_synthesizer import (
    DEFAULT_OPENROUTER_MODEL,
    SynthesisResult,
    synthesize,
)
from src.mcp.agent_memory import AgentMemory

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

_CHAT_MODES: List[str] = ["Query", "Map", "Execute"]
_VOICE_MODES: List[str] = ["Plain", "Circuit"]

# ── Session-state keys ────────────────────────────────────────────────────────

_HISTORY_KEY    = "mcp_chat_history"   # List[Dict] — {role, content, meta}
_MODEL_KEY      = "mcp_model"
_HS_KEY         = "mcp_house_system"
_NOTES_KEY      = "mcp_agent_notes"    # str — accumulated across conversation
_MODE_KEY       = "mcp_chat_mode"      # "Query" | "Map" | "Execute"
_VOICE_KEY      = "mcp_voice_mode"     # "Plain" | "Circuit"
_DEV_TRACE_KEY  = "mcp_dev_trace"      # dict  — last-turn inner-monologue (dev only)
_PERSONS_KEY    = "mcp_known_persons"  # List[dict] — accumulated PersonProfile dicts
_LOCATIONS_KEY  = "mcp_known_locations" # List[dict] — accumulated Location dicts
_PENDING_Q_KEY       = "mcp_pending_question"   # str — original question when clarification is pending
_STARTER_PROMPT_KEY = "mcp_starter_prompt"     # str — example prompt clicked by user before any history
_AGENT_MEMORY_KEY   = "mcp_agent_memory"        # AgentMemory — structured private memory for the session
_EQ_BASS_KEY    = "mcp_eq_bass"        # float -20 to +20 dB
_EQ_MIDS_KEY    = "mcp_eq_mids"        # float -20 to +20 dB
_EQ_TREBLE_KEY  = "mcp_eq_treble"      # float -20 to +20 dB

# ── Example starter prompts ─────────────────────────────────────────────────

_EXAMPLE_PROMPTS: Dict[str, List[str]] = {
    "natal": [
        "What are the main power planets of my chart, and how do they drive my motivations?",
        "Where do I have the most internal 'friction' in my personality, and how can I balance it?",
        "How can I best structure my career to be sustainable and fulfilling in the long term?",
    ],
    "synastry": [
        "When we are together, which parts of my personality get amplified the most?",
        "Where do our communication styles naturally sync up, and where do we tend to short-circuit?",
        "What is our biggest relationship challenge, and what lesson can it teach me?",
    ],
    "transit": [
        "Which areas of my life are under the most 'cosmic pressure' right now, and what is it trying to change?",
        "I feel a shift in my energy lately—is there a current planet 'poking' a sensitive spot in my chart?",
        "Is this a better time for me to push forward on a project or to sit back and recalibrate my system?",
    ],
}


def _render_example_prompts() -> None:
    """Render clickable starter-question buttons when chat history is empty."""
    synastry_on = st.session_state.get("synastry_mode", False)
    transit_on  = st.session_state.get("transit_mode",  False)

    if synastry_on:
        mode_key = "synastry"
    elif transit_on:
        mode_key = "transit"
    else:
        mode_key = "natal"

    prompts = _EXAMPLE_PROMPTS[mode_key]

    st.markdown(
        "<div style='color:#6b7280; font-size:0.8rem; margin-bottom:0.4rem;'>"
        "Try asking…</div>",
        unsafe_allow_html=True,
    )
    for i, q in enumerate(prompts):
        if st.button(q, key=f"starter_prompt_{mode_key}_{i}", use_container_width=True):
            st.session_state[_STARTER_PROMPT_KEY] = q
            st.rerun()


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
    color: #fff; /* ensure all chat panel text stays white */
    max-height: 68vh;
    overflow-y: auto;
    overflow-x: hidden;
}

/* Also ensure any chat message bubbles, labels, and inputs inside the
   chat pane remain white for readability on the dark background. */
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatInput"])
    div[data-testid="stChatMessage"],
div[data-testid="stHorizontalBlock"]:has(div[data-testid="stChatInput"])
    div[data-testid="stChatInput"] {
    color: #fff !important;
}

</style>
"""

# ── Agent-notes tree helpers ─────────────────────────────────────────────────

# Keys in comprehension_note that hold comma-separated lists (bracket-wrapped)
_LIST_NOTE_KEYS = {"nodes", "shapes", "persons", "focus"}


def _parse_note_line(line: str) -> "dict | str":
    """Parse a pipe-delimited comprehension_note line into a dict.

    Format: "Q: <text> -> <type> | key: value | ..."
    List-valued keys (nodes/shapes/persons/focus) are returned as lists.
    Returns the raw string on any parse failure.
    """
    line = line.strip()
    if not line.startswith("Q:"):
        return line
    try:
        segments = [s.strip() for s in line.split(" | ")]
        result: dict = {}
        # First segment: "Q: <text> -> <type>"
        first = segments[0]  # e.g. "Q: will I get the job? -> predictive"
        if " -> " in first:
            q_part, type_part = first.split(" -> ", 1)
            result["q"] = q_part[2:].strip()   # strip leading "Q: "
            result["type"] = type_part.strip()
        else:
            result["q"] = first[2:].strip()
        # Remaining segments: "key: value"
        for seg in segments[1:]:
            if ":" not in seg:
                continue
            k, v = seg.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k in _LIST_NOTE_KEYS:
                # Strip surrounding brackets and split
                v_clean = v.strip("[]")
                items = [i.strip().strip("'\"") for i in v_clean.split(",") if i.strip()]
                result[k] = items
            else:
                result[k] = v
        return result
    except Exception:
        return line


def _render_agent_notes_tree(notes_raw: str) -> None:
    """Render agent notes as a collapsible <details>/<summary> tree."""
    lines = [ln for ln in (notes_raw or "").splitlines() if ln.strip()]
    entries = [_parse_note_line(ln) for ln in lines]

    # ── HTML + inline CSS ────────────────────────────────────────────────
    style = """
    <style>
      .an-root {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 6px 8px;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 0.73em;
        color: #c9d1d9;
        line-height: 1.55;
      }
      .an-title {
        font-size: 0.68rem;
        font-weight: 700;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin: 0 0 5px 0;
      }
      details.turn > summary {
        cursor: pointer;
        color: #58a6ff;
        font-weight: 600;
        padding: 2px 0;
        list-style: disclosure-closed;
        outline: none;
        user-select: none;
      }
      details.turn[open] > summary {
        list-style: disclosure-open;
        border-bottom: 1px solid #21262d;
        margin-bottom: 3px;
        padding-bottom: 3px;
      }
      details.turn {
        border-left: 2px solid #30363d;
        padding-left: 6px;
        margin-bottom: 4px;
      }
      .turn-body {
        padding: 2px 0 2px 8px;
      }
      .kv {
        display: flex;
        gap: 6px;
        padding: 1px 0;
      }
      .kv .k {
        color: #7ee787;   /* green — key */
        min-width: 62px;
        flex-shrink: 0;
      }
      .kv .v {
        color: #e6edf3;
        word-break: break-word;
      }
      details.sub > summary {
        cursor: pointer;
        color: #d2a8ff;   /* purple — list keys */
        list-style: disclosure-closed;
        outline: none;
        user-select: none;
        padding: 1px 0;
      }
      details.sub[open] > summary { list-style: disclosure-open; }
      details.sub {
        margin-left: 0;
        padding-left: 4px;
        border-left: 1px dotted #30363d;
      }
      .list-item {
        color: #ffa657;   /* orange — list values */
        padding: 0px 0 0 10px;
      }
      .list-item::before { content: "• "; color: #30363d; }
      .freeform {
        color: #8b949e;
        padding: 2px 0;
        font-style: italic;
      }
      .empty { color: #4b5563; font-style: italic; }
    </style>
    """

    def _esc(s: str) -> str:
        return _html.escape(str(s))

    # Scalar fields to show (in order), with display labels
    SCALAR_FIELDS = [
        ("type",      "type"),
        ("intent",    "intent"),
        ("source",    "source"),
        ("conf",      "conf"),
        ("temporal",  "temporal"),
        ("subject",   "subject"),
        ("aim",       "aim"),
        ("tone",      "tone"),
        ("understood", "understood"),
    ]
    LIST_FIELDS = [
        ("nodes",   "nodes"),
        ("shapes",  "shapes"),
        ("focus",   "focus"),
        ("persons", "persons"),
    ]

    body_parts: list[str] = []

    if not entries:
        body_parts.append('<div class="empty">(no notes yet)</div>')
    else:
        turn_n = 0
        for entry in entries:
            if isinstance(entry, str):
                # Free-form / memory-stub line
                body_parts.append(f'<div class="freeform">{_esc(entry)}</div>')
                continue

            turn_n += 1
            q_text = entry.get("q", "")
            q_type = entry.get("type", "")
            # Truncate Q to ~50 chars for summary
            q_excerpt = (q_text[:48] + "…") if len(q_text) > 50 else q_text
            summary_badge = f" <span style='color:#6b7280;font-weight:400'>({_esc(q_type)})</span>" if q_type else ""

            rows: list[str] = []

            # Full question as first row
            if q_text:
                rows.append(
                    f'<div class="kv">'
                    f'<span class="k">Q</span>'
                    f'<span class="v">{_esc(q_text)}</span>'
                    f'</div>'
                )

            # Scalar fields
            for field_key, label in SCALAR_FIELDS:
                val = entry.get(field_key)
                if val and str(val) not in ("-", "none", "None", ""):
                    rows.append(
                        f'<div class="kv">'
                        f'<span class="k">{_esc(label)}</span>'
                        f'<span class="v">{_esc(val)}</span>'
                        f'</div>'
                    )

            # List fields — nested <details>
            for field_key, label in LIST_FIELDS:
                items = entry.get(field_key)
                if items and isinstance(items, list) and items:
                    items_html = "".join(
                        f'<div class="list-item">{_esc(it)}</div>' for it in items
                    )
                    rows.append(
                        f'<details class="sub">'
                        f'<summary>{_esc(label)} ({len(items)})</summary>'
                        f'{items_html}'
                        f'</details>'
                    )

            inner = "".join(rows)
            body_parts.append(
                f'<details class="turn">'
                f'<summary>Turn {turn_n} &nbsp;·&nbsp; {_esc(q_excerpt)}{summary_badge}</summary>'
                f'<div class="turn-body">{inner}</div>'
                f'</details>'
            )

    html_content = (
        style
        + '<div class="an-root">'
        + '<p class="an-title">Agent Notes</p>'
        + "".join(body_parts)
        + "</div>"
    )
    components.html(html_content, height=360, scrolling=True)


def _render_agent_memory_panel() -> None:
    """Render a compact structured-memory panel in the right sidebar.

    Shows open todos, pending bot questions, and unanswered user questions
    from the session's AgentMemory.  Empty state is hidden silently.
    """
    import streamlit as st  # local reference — already imported globally but kept explicit
    mem: AgentMemory = st.session_state.get(_AGENT_MEMORY_KEY) or AgentMemory()
    if mem.is_empty():
        return

    stats = mem.stats()

    with st.expander(
        f"🧠 Memory  "
        f"({stats['todos_open']} todo{'s' if stats['todos_open'] != 1 else ''} · "
        f"{stats['bot_q_awaiting']} awaiting)",
        expanded=False,
    ):
        # Open todos
        open_t = mem.open_todos()
        if open_t:
            st.markdown("**☐ Open To-Dos**")
            for t in open_t:
                src = " *(user)*" if t.source == "user" else ""
                st.markdown(f"- {t.description}{src}")

        # Blocked todos
        blocked = mem.blocked_todos()
        if blocked:
            st.markdown("**⏸ Blocked (waiting on reply)**")
            for t in blocked:
                st.markdown(f"- {t.description}")

        # Pending bot questions
        pending_bq = mem.pending_bot_questions()
        if pending_bq:
            st.markdown("**⏳ Awaiting user reply**")
            for bq in pending_bq:
                st.markdown(f"- *{bq.text[:140]}*")

        # Unanswered user questions
        unanswered_uq = mem.unanswered_user_questions()
        if unanswered_uq:
            st.markdown("**? Unanswered user questions**")
            for uq in unanswered_uq:
                st.markdown(f"- {uq.text[:120]}")

        # Completed todos (last 5, collapsed)
        done_t = [t for t in mem.todos if t.done]
        if done_t:
            with st.expander(f"✓ Completed ({len(done_t)})", expanded=False):
                for t in done_t[-5:]:
                    st.markdown(f"- ~~{t.description}~~")


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
    st.session_state.setdefault(_MODE_KEY, "Query")
    st.session_state.setdefault(_VOICE_KEY, "Plain")
    st.session_state.setdefault(_DEV_TRACE_KEY, {})
    st.session_state.setdefault(_PERSONS_KEY, [])
    st.session_state.setdefault(_LOCATIONS_KEY, [])
    st.session_state.setdefault(_PENDING_Q_KEY, "")
    st.session_state.setdefault(_EQ_BASS_KEY, 0.0)
    st.session_state.setdefault(_EQ_MIDS_KEY, 0.0)
    st.session_state.setdefault(_EQ_TREBLE_KEY, 0.0)
    if _AGENT_MEMORY_KEY not in st.session_state:
        st.session_state[_AGENT_MEMORY_KEY] = AgentMemory()


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
        _render_agent_notes_tree(st.session_state.get(_NOTES_KEY, "") or "")
        _render_agent_memory_panel()

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
                "**Query** — single-turn Q&A\n\n"
                "**Map** — establish comprehension of complex questions; multi-step analysis outline *(coming soon)*\n\n"
                "**Execute** — autonomous chart research loop; executes what was planned in Map mode (if switching from planning in Map mode) *(coming soon)*"
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

        # EQ Controls
        st.markdown("### 🎛️ Audio EQ")
        st.session_state[_EQ_BASS_KEY] = st.slider(
            "Bass",
            min_value=-20.0,
            max_value=20.0,
            value=st.session_state.get(_EQ_BASS_KEY, 0.0),
            step=2.0,
            key="mcp_eq_bass_slider",
            help="Boost low frequencies to reduce tininess",
        )
        st.session_state[_EQ_MIDS_KEY] = st.slider(
            "Mids",
            min_value=-20.0,
            max_value=20.0,
            value=st.session_state.get(_EQ_MIDS_KEY, 0.0),
            step=2.0,
            key="mcp_eq_mids_slider",
            help="Adjust mid frequencies for clarity",
        )
        st.session_state[_EQ_TREBLE_KEY] = st.slider(
            "Treble",
            min_value=-20.0,
            max_value=20.0,
            value=st.session_state.get(_EQ_TREBLE_KEY, 0.0),
            step=2.0,
            key="mcp_eq_treble_slider",
            help="Reduce high frequencies to decrease treble/tinny sound",
        )

    # ════════════════════════════════════════════════════════════════════════
    # LEFT COLUMN — chat
    # ════════════════════════════════════════════════════════════════════════
    with col_chat:

        # Header row
        col_title, col_clear = st.columns([7, 1])
        with col_title:
            st.markdown("<h3 style='color: #fff; margin: 0;'>🔮 Ask your chart</h3>", unsafe_allow_html=True)
        with col_clear:
            if st.button("🗑", key="mcp_clear_chat", help="Clear chat history"):
                st.session_state[_HISTORY_KEY] = []
                st.session_state[_NOTES_KEY] = ""
                st.session_state[_VOICE_KEY] = "Plain"
                st.session_state[_DEV_TRACE_KEY] = {}
                st.session_state[_PERSONS_KEY] = []
                st.session_state[_LOCATIONS_KEY] = []
                st.session_state[_PENDING_Q_KEY] = ""
                st.session_state[_AGENT_MEMORY_KEY] = AgentMemory()
                st.rerun()

        # History replay
        history: List[Dict[str, Any]] = st.session_state[_HISTORY_KEY]
        for msg_idx, msg in enumerate(history):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if (msg["role"] == "assistant"
                        and msg.get("meta")
                        and not msg["meta"].get("fallback_to_interp")):
                    _render_caption(msg["meta"])
                    _render_read_aloud_button(
                        msg["content"],
                        key=f"msg_{msg_idx}",
                        bass=st.session_state.get(_EQ_BASS_KEY, 0.0),
                        mids=st.session_state.get(_EQ_MIDS_KEY, 0.0),
                        treble=st.session_state.get(_EQ_TREBLE_KEY, 0.0),
                    )

        # Show example starter prompts when there is no history yet
        if not history:
            _render_example_prompts()

        # Chat input (must be inside the column to make :has() CSS work)
        prompt = st.chat_input("Ask your chart anything…", key="mcp_chat_input")

    # ── Dev inner-monologue expander (always rendered after columns) ───────
    _render_dev_expander()

    # ── Handle new prompt ─────────────────────────────────────────────────
    # Done outside the column context so st.rerun() works without nesting
    # Pick up either a directly typed prompt or one chosen from starters.
    _starter = st.session_state.pop(_STARTER_PROMPT_KEY, None)
    if not prompt and _starter:
        prompt = _starter
    if prompt:
        # ── /todo slash-command ───────────────────────────────────────
        if prompt.strip().lower().startswith("/todo "):
            description = prompt.strip()[len("/todo "):].strip()
            if description:
                _mem: AgentMemory = st.session_state[_AGENT_MEMORY_KEY]
                new_todo = _mem.add_todo(description=description, source="user")
                history.append({"role": "user", "content": prompt, "meta": {}})
                history.append({
                    "role": "assistant",
                    "content": f"\u2713 To-do added: **{description}**",
                    "meta": {"_is_todo_ack": True},
                })
            st.rerun()
            return

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

        # ── Resolve pending clarification context ─────────────────────
        actual_question = prompt
        pending_clar: Optional[str] = None
        stored_q = st.session_state.get(_PENDING_Q_KEY)
        if stored_q:
            # User is replying to a clarification follow-up
            pending_clar = prompt            # their new reply is the clarification
            actual_question = stored_q       # re-ask the original question
            st.session_state[_PENDING_Q_KEY] = ""
            # Mark any awaiting BotQuestions as answered with the user's reply
            _mem_clar: AgentMemory = st.session_state[_AGENT_MEMORY_KEY]
            _mem_clar.answer_all_pending_bot_questions(prompt)

        with st.spinner("Reading the chart…"):
            # Resolve pre-computed inter-chart aspects from whichever biwheel mode is active
            _edges_inter = (
                st.session_state.get("edges_inter_chart_cc")
                or st.session_state.get("_biwheel_standard_cache", {}).get("inter_aspects")
                or []
            )
            response_text, meta = _generate_response(
                question=actual_question,
                chart=chart,
                house_system=st.session_state[_HS_KEY],
                api_key=_get_api_key(),
                model=st.session_state[_MODEL_KEY],
                mode=st.session_state[_MODE_KEY],
                voice=st.session_state.get(_VOICE_KEY, "Plain"),
                agent_notes=st.session_state.get(_NOTES_KEY, ""),
                render_result=st.session_state.get("render_result"),
                chart_b=st.session_state.get("last_chart_2"),
                edges_inter_chart=_edges_inter,
                known_persons=st.session_state.get(_PERSONS_KEY) or None,
                known_locations=st.session_state.get(_LOCATIONS_KEY) or None,
                pending_clarification=pending_clar,
                agent_memory=st.session_state.get(_AGENT_MEMORY_KEY),
            )

        # ── Handle clarification request from pipeline ────────────────
        if meta.get("_is_clarification"):
            st.session_state[_PENDING_Q_KEY] = actual_question
            history.append({"role": "assistant", "content": response_text, "meta": meta})
            st.rerun()
            return

        # Accumulate agent notes from this turn
        turn_note = meta.get("comprehension_note", "")
        if turn_note:
            existing = st.session_state.get(_NOTES_KEY, "")
            st.session_state[_NOTES_KEY] = (
                (existing + "\n" if existing else "") + turn_note
            )

        # ── Accumulate persons & locations across turns ───────────────
        _merge_persons(meta.get("_new_persons", []))
        _merge_locations(meta.get("_new_locations", []))

        # Persist dev trace to session state for the expander
        if meta.get("_dev"):
            st.session_state[_DEV_TRACE_KEY] = meta["_dev"]

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


# ── Dev inner-monologue expander ──────────────────────────────────────────────

def _render_dev_expander() -> None:
    """Dev-only expander that shows every step of the MCP pipeline for the last turn."""
    trace: Dict[str, Any] = st.session_state.get(_DEV_TRACE_KEY) or {}
    if not trace:
        return

    with st.expander("🔬 Dev: Inner Monologue (last turn)", expanded=False):
        question = trace.get("question", "")
        if question:
            st.markdown(f"**Question:** {question}")
        st.markdown("---")

        # ── Step 0: Grammar Parse ─────────────────────────────────────────
        with st.container():
            st.markdown("#### Step 0 — Grammar Parse")
            s0 = trace.get("step0_grammar")
            if s0 and isinstance(s0, dict) and s0.get("confidence", 0) > 0:
                # Sentence type badge
                _stype = s0.get("sentence_type", "unknown")
                st.markdown(f"**Sentence type:** `{_stype}`")

                # Subject → Verb → Object chain
                _subj = s0.get("subject", "")
                _verb = s0.get("verb", "")
                _vtense = s0.get("verb_tense", "")
                _dobj = s0.get("direct_object", "")
                _iobj = s0.get("indirect_object", "")
                svo_parts = []
                if _subj:
                    svo_parts.append(f"**Subject:** {_subj}")
                if _verb:
                    tense_tag = f" *({_vtense})*" if _vtense else ""
                    svo_parts.append(f"**Verb:** {_verb}{tense_tag}")
                if _dobj:
                    svo_parts.append(f"**Direct Object:** {_dobj}")
                if _iobj:
                    svo_parts.append(f"**Indirect Object:** {_iobj}")
                if svo_parts:
                    st.markdown(" → ".join(svo_parts))

                # Prepositional phrases
                _pps = s0.get("prepositional_phrases", [])
                if _pps:
                    st.markdown("**Prepositional phrases:**")
                    for pp in _pps:
                        st.markdown(f"  • *{pp.get('preposition', '')}* → {pp.get('object', '')}")

                # Modifiers table
                _mods = s0.get("modifiers", [])
                if _mods:
                    st.markdown("**Modifiers:**")
                    for m in _mods:
                        st.markdown(
                            f'  • "{m.get("word", "")}" modifies '
                            f'"{m.get("modifies", "")}" ({m.get("type", "")})'
                        )

                # Clauses
                _cls = s0.get("clauses", [])
                if _cls:
                    st.markdown("**Clauses:**")
                    for cl in _cls:
                        st.markdown(
                            f'  • [{cl.get("clause_type", "")}] "{cl.get("text", "")}" → {cl.get("role", "")}'
                        )

                # Parse tree
                _tree = s0.get("raw_parse_tree", "")
                if _tree:
                    st.markdown("**Parse tree:**")
                    st.code(_tree, language=None)

                # Confidence
                st.metric("Grammar confidence", f"{s0.get('confidence', 0):.0%}")
            else:
                st.caption("Grammar parse skipped (no API key or failed)")

        st.markdown("---")

        # ── Step 1: Comprehension ─────────────────────────────────────────
        with st.container():
            st.markdown("#### Step 1 — Question Comprehension")
            s1 = trace.get("step1_comprehension", {})

            if s1.get("needs_chart_b"):
                st.warning(
                    "This question involves another person. For a full synastry "
                    "reading, load a second chart using the biwheel panel."
                )

            # ── 5W+H Extraction (always shown first) ─────────────────
            with st.expander("🧠 5W+H Extraction", expanded=False):
                # ── WHO ────────────────────────────────────────────
                _persons = s1.get("persons") or []
                st.markdown("##### 👤 WHO — Persons")
                if _persons:
                    for p in _persons:
                        name = p.get("name") or "*(unnamed)*"
                        rel = p.get("relationship_to_querent") or ""
                        locs = p.get("locations") or []
                        loc_str = ", ".join(
                            f"{loc.get('location', '?')} ({loc.get('connection', '')})"
                            for loc in locs
                        ) if locs else ""
                        parts = [f"**{name}**"]
                        if rel:
                            parts.append(f"({rel})")
                        if loc_str:
                            parts.append(f"— 📍 {loc_str}")
                        st.markdown("- " + " ".join(parts))
                else:
                    st.caption("*(not detected)*")

                # ── WHAT ───────────────────────────────────────────
                _story = s1.get("story_objects") or []
                _dilemma = s1.get("dilemma")
                _aim = s1.get("answer_aim")
                st.markdown("##### 🎯 WHAT — Story & Aim")
                if _story:
                    for so in _story:
                        sig = so.get("significance") or ""
                        st.markdown(
                            f"- **{so.get('name', '?')}**"
                            + (f" — *{sig}*" if sig else "")
                        )
                if _dilemma:
                    desc = _dilemma.get("description") or ""
                    opts = _dilemma.get("options") or []
                    stakes = _dilemma.get("stakes") or ""
                    st.warning(
                        f"**Dilemma:** {desc}"
                        + (f"  \nOptions: {', '.join(opts)}" if opts else "")
                        + (f"  \nStakes: *{stakes}*" if stakes else "")
                    )
                if _aim:
                    aim_parts = []
                    for k in ("aim_type", "depth", "urgency", "specificity"):
                        v = _aim.get(k)
                        if v:
                            aim_parts.append(f"{k}: `{v}`")
                    st.markdown(f"**Answer aim:** {' · '.join(aim_parts)}")
                if not _story and not _dilemma and not _aim:
                    st.caption("*(not detected)*")

                # ── WHEN ───────────────────────────────────────────
                _setting = s1.get("setting_time")
                _transits = s1.get("transits") or []
                st.markdown("##### ⏱️ WHEN — Temporal")
                if _setting:
                    st.markdown(f"**Setting time:** {_setting}")
                if _transits:
                    for t in _transits:
                        bodies = " ".join(filter(None, [
                            t.get("transiting_body"), "→", t.get("natal_body"),
                        ]))
                        asp = t.get("aspect_type") or ""
                        tf = t.get("timeframe") or ""
                        st.markdown(
                            f"- {bodies}"
                            + (f" ({asp})" if asp else "")
                            + (f" — *{tf}*" if tf else "")
                        )
                if not _setting and not _transits:
                    st.caption("*(not detected)*")

                # ── WHERE ──────────────────────────────────────────
                _locations = s1.get("locations") or []
                st.markdown("##### 📍 WHERE — Locations")
                if _locations:
                    for loc in _locations:
                        lname = loc.get("name") or "?"
                        ltype = loc.get("location_type") or ""
                        conn = loc.get("connected_persons") or []
                        conn_str = ", ".join(
                            f"{c.get('person', '?')} ({c.get('connection', '')})"
                            for c in conn
                        ) if conn else ""
                        st.markdown(
                            f"- **{lname}**"
                            + (f" *({ltype})*" if ltype else "")
                            + (f" — {conn_str}" if conn_str else "")
                        )
                else:
                    st.caption("*(not detected)*")

                # ── WHY ────────────────────────────────────────────
                _intent_ctx = s1.get("intent_context")
                _desired = s1.get("desired_input")
                st.markdown("##### 💡 WHY — Intent & Desired Input")
                if _intent_ctx:
                    st.markdown(f"**Context:** {_intent_ctx}")
                if _desired:
                    st.markdown(f"**Desired input:** {_desired}")
                if not _intent_ctx and not _desired:
                    st.caption("*(not detected)*")

                # ── HOW ────────────────────────────────────────────
                _qs = s1.get("querent_state")
                st.markdown("##### 🫀 HOW — Querent State")
                if _qs:
                    qs_parts = []
                    for k in ("emotional_tone", "certainty_level", "guidance_openness"):
                        v = _qs.get(k)
                        if v:
                            label = k.replace("_", " ").title()
                            qs_parts.append(f"{label}: `{v}`")
                    if qs_parts:
                        st.markdown(" · ".join(qs_parts))
                    feelings = _qs.get("expressed_feelings") or []
                    if feelings:
                        st.markdown(f"**Expressed feelings:** {', '.join(feelings)}")
                    demeanor = _qs.get("demeanor_notes")
                    if demeanor:
                        st.caption(f"Demeanor: {demeanor}")
                else:
                    st.caption("*(not detected)*")

            # ── QuestionGraph detail (placeholder) ────────────────────
            with st.expander("QuestionGraph detail", expanded=False):
                st.caption(
                    "Concept node mapping will be rebuilt in a future step. "
                    "This section is intentionally empty."
                )
                q_graph = s1.get("q_graph") or {}
                _qi = q_graph.get("question_intent") or ""
                if _qi:
                    st.success(f"**Routing intent:** `{_qi}`")
                focus = q_graph.get("focus_circuits", [])
                if focus:
                    st.markdown(f"**Focus circuit IDs:** {focus}")
                all_f = q_graph.get("all_factors", [])
                if all_f:
                    st.markdown(f"**All factors:** {', '.join(all_f)}")

            # ── Metadata ──────────────────────────────────────────────
            c1, c2, c3 = st.columns(3)
            c1.metric("Domain", s1.get("domain") or "—")
            c2.metric("Subtopic", s1.get("subtopic") or "—")
            c3.metric("Confidence", f"{s1.get('confidence', 0):.0%}")

            col_a, col_b = st.columns(2)
            _intent = s1.get("question_intent") or ""
            col_a.markdown(
                f"**Source:** `{s1.get('source', '—')}`  \n"
                f"**Question type:** `{s1.get('question_type', '—')}`  \n"
                + (f"**Intent:** `{_intent}`" if _intent else "**Intent:** *(none — general)*")
            )
            kws = s1.get("matched_keywords") or []
            col_b.markdown(f"**Matched keywords:** {', '.join(kws) if kws else '*(none)*'}")

            note = s1.get("comprehension_note", "")
            if note:
                st.info(f"📝 {note}")

            # ── Paraphrase (last) ─────────────────────────────────────
            _paraphrase = s1.get("paraphrase", "")
            if _paraphrase and not _paraphrase.startswith("("):
                st.info(f'**Understood as:** "{_paraphrase}"')

        st.markdown("---")

        # ── Step 2: Factor resolution ─────────────────────────────────────
        with st.container():
            st.markdown("#### Step 2 — Factor Resolution & Object Selection")
            s2 = trace.get("step2_factor_resolution", {})
            col_l, col_r = st.columns(2)
            merged = s2.get("merged_factors", [])
            col_l.markdown(
                f"**Merged factors ({len(merged)}):**  \n"
                + (", ".join(merged) if merged else "*(none)*")
            )
            relevant = s2.get("relevant_objects", [])
            col_r.markdown(
                f"**Relevant chart objects ({len(relevant)}):**  \n"
                + (", ".join(relevant) if relevant else "*(none selected)*")
            )

        st.markdown("---")

        # ── Step 3: Circuit query ─────────────────────────────────────────
        with st.container():
            st.markdown("#### Step 3 — Circuit Simulation Query")
            s3 = trace.get("step3_circuit", {})
            col_a, col_b, col_c = st.columns(3)
            col_a.metric("Shapes found", s3.get("shapes_count", 0))
            focus_n = s3.get("focus_nodes", [])
            col_b.markdown(f"**Focus nodes:** {', '.join(focus_n) if focus_n else '*(none)*'}")
            sn_nn = s3.get("sn_nn_relevance", "")
            col_c.markdown(f"**SN→NN arc:** {sn_nn or '*(not relevant)*'}")

            seeds = s3.get("narrative_seeds", [])
            if seeds:
                st.markdown("**Narrative seeds:**")
                for seed in seeds:
                    st.markdown(f"- {seed}")

            ps = s3.get("power_summary", {})
            if ps:
                with st.expander("Power summary", expanded=False):
                    st.json(ps)

        st.markdown("---")

        # ── Step 4: Classical facts ───────────────────────────────────────
        with st.container():
            st.markdown("#### Step 4 — Classical Facts Assembled")
            s4 = trace.get("step4_facts", {})
            summary_line = s4.get("summary", "")
            if summary_line:
                st.caption(f"Packet: {summary_line}  ·  ~{s4.get('token_estimate', 0)} tokens")

            tabs = st.tabs(["Placements", "Aspects", "Patterns", "Dignities", "Dispositors", "Houses / Sect"])

            with tabs[0]:
                rows = s4.get("placements", [])
                if rows:
                    for obj, sign, house, dig in rows:
                        st.markdown(f"- **{obj}** in {sign} {house}" + (f" *{dig}*" if dig and dig != "—" else ""))
                else:
                    st.caption("*(none)*")

            with tabs[1]:
                rows = s4.get("aspects", [])
                if rows:
                    for a, asp, b, orb in rows:
                        st.markdown(f"- {a} **{asp}** {b} `{orb}`")
                else:
                    st.caption("*(none)*")

            with tabs[2]:
                rows = s4.get("patterns", [])
                if rows:
                    for ptype, members in rows:
                        st.markdown(f"- **{ptype}**: {', '.join(members)}")
                else:
                    st.caption("*(none)*")

            with tabs[3]:
                rows = s4.get("dignities", [])
                if rows:
                    for obj, dtype, sign in rows:
                        st.markdown(f"- **{obj}** — {dtype} in {sign}")
                else:
                    st.caption("*(none)*")

            with tabs[4]:
                rows = s4.get("dispositors", [])
                if rows:
                    for obj, ruler in rows:
                        st.markdown(f"- **{obj}** ruled by {ruler}")
                else:
                    st.caption("*(none)*")

            with tabs[5]:
                houses = s4.get("houses", [])
                sect = s4.get("sect")
                if sect:
                    st.markdown(
                        f"**Sect:** {sect.get('sect', '—')}  ·  "
                        f"Sect light: {sect.get('sect_light', '—')}  ·  "
                        f"Benefic: {sect.get('benefic_of_sect', '—')}"
                    )
                if houses:
                    for h in houses:
                        occupants = h.get("occupants", [])
                        occ_str = f" — {', '.join(occupants)}" if occupants else ""
                        meaning = h.get("meaning", "")
                        st.markdown(
                            f"- **H{h.get('house', '?')}** {h.get('cusp_sign', '?')} "
                            f"(ruler: {h.get('ruler', '?')}){occ_str}"
                            + (f"  *{meaning}*" if meaning else "")
                        )
                if not houses and not sect:
                    st.caption("*(none)*")

        st.markdown("---")

        # ── Step 5: Synthesis ─────────────────────────────────────────────
        with st.container():
            st.markdown("#### Step 5 — LLM Synthesis")
            s5 = trace.get("step5_synthesis", {})
            if s5:
                cols = st.columns(4)
                cols[0].metric("Model", (s5.get("model") or "—").split("/")[-1])
                cols[1].metric("Backend", s5.get("backend") or "—")
                cols[2].metric("Prompt tokens", s5.get("prompt_tokens", 0))
                cols[3].metric("Completion tokens", s5.get("completion_tokens", 0))
            else:
                st.caption("*(synthesis has not run yet — no API key or error)*")

        st.markdown("---")

        # ── Agent Memory state ────────────────────────────────────────────
        with st.container():
            st.markdown("#### 🧠 Agent Memory (session state)")
            mem: AgentMemory = st.session_state.get(_AGENT_MEMORY_KEY) or AgentMemory()
            if mem.is_empty():
                st.caption("*(no memory recorded yet)*")
            else:
                _stats = mem.stats()
                _mcols = st.columns(3)
                _mcols[0].metric(
                    "To-Dos",
                    f"{_stats['todos_open']} open · {_stats['todos_done']} done"
                    + (f" · {_stats['todos_blocked']} blocked" if _stats['todos_blocked'] else ""),
                )
                _mcols[1].metric(
                    "User Questions",
                    f"{_stats['user_q_total']} total · {_stats['user_q_unanswered']} pending",
                )
                _mcols[2].metric(
                    "Bot Questions",
                    f"{_stats['bot_q_total']} asked · {_stats['bot_q_awaiting']} awaiting",
                )

                _mem_tabs = st.tabs(["To-Dos", "User Questions", "Bot Questions", "Raw text", "JSON"])

                with _mem_tabs[0]:
                    if not mem.todos:
                        st.caption("*(none)*")
                    for t in mem.todos:
                        icon = "✓" if t.done else ("⏸" if t.id in {bq.id for bq in mem.blocked_todos()} else "☐")
                        src = f" *({t.source})*"
                        blocked_note = ""
                        if t.blocked_by:
                            blocked_note = f"  \n⛔ blocked by: `{'`, `'.join(b[:8] for b in t.blocked_by)}`"
                        done_note = f"  \n✓ completed: `{t.completed_at}`" if t.completed_at else ""
                        st.markdown(
                            f"**{icon} [{t.id[:8]}]** {t.description}{src}"
                            f"  \ncreated: `{t.created_at}`{done_note}{blocked_note}"
                        )
                        st.markdown("---")

                with _mem_tabs[1]:
                    if not mem.user_questions:
                        st.caption("*(none)*")
                    for uq in mem.user_questions:
                        status = "✓" if uq.answered else "?"
                        tags: List[str] = []
                        if uq.chart_object_refs:
                            tags.append(f"objects: `{'`, `'.join(uq.chart_object_refs)}`")
                        if uq.shape_refs:
                            tags.append(f"shapes: `{'`, `'.join(uq.shape_refs)}`")
                        if uq.circuit_refs:
                            tags.append(f"circuits: `{'`, `'.join(uq.circuit_refs)}`")
                        if uq.memory_node_refs:
                            tags.append(f"factors: `{'`, `'.join(uq.memory_node_refs[:4])}`…")
                        tag_block = "  \n" + "  \n".join(tags) if tags else ""
                        answer_block = (
                            f"  \n**Answer summary:** {uq.answer}"
                            if uq.answered and uq.answer else ""
                        )
                        st.markdown(
                            f"**{status} [{uq.id[:8]}]** {uq.text}"
                            f"  \nasked: `{uq.asked_at}`"
                            f"{tag_block}{answer_block}"
                        )
                        st.markdown("---")

                with _mem_tabs[2]:
                    if not mem.bot_questions:
                        st.caption("*(none)*")
                    for bq in mem.bot_questions:
                        if bq.awaiting:
                            status_icon = "⏳ AWAITING"
                        elif bq.answered:
                            status_icon = "✓"
                        else:
                            status_icon = "?"
                        prereq_note = ""
                        if bq.prerequisite_for:
                            prereq_note = f"  \n🔗 prereq for todos: `{'`, `'.join(b[:8] for b in bq.prerequisite_for)}`"
                        reply_note = f"  \n**Reply:** {bq.answer}" if bq.answered and bq.answer else ""
                        st.markdown(
                            f"**{status_icon} [{bq.id[:8]}]** {bq.text}"
                            f"  \nasked: `{bq.asked_at}`"
                            f"{prereq_note}{reply_note}"
                        )
                        st.markdown("---")

                with _mem_tabs[3]:
                    st.code(mem.to_notes_text(), language="text")

                with _mem_tabs[4]:
                    st.json(mem.to_dict())

def _render_read_aloud_button(text: str, key: str, bass: float = 0.0, mids: float = 0.0, treble: float = 0.0) -> None:
    """Render a set of playback controls using the browser SpeechSynthesis API.

    Controls include play/pause, paragraph navigation, speed adjustment, and EQ controls.
    
    Args:
        text: The content to speak
        key: Unique identifier for this button set
        bass: Bass adjustment in dB (-20 to +20)
        mids: Mids adjustment in dB (-20 to +20)
        treble: Treble adjustment in dB (-20 to +20)
    """

    # Use JSON to safely embed the text in JS (properly escapes quotes/newlines)
    js_text = json.dumps(text)
    
    # Calculate pitch and rate modifiers from EQ values
    # Treble reduction = lower pitch; Bass boost = slower rate perception
    pitch_mod = 1.0 - (treble * 0.01)  # Reduce pitch for treble cut
    if pitch_mod < 0.5:
        pitch_mod = 0.5  # Clamp to reasonable range
    elif pitch_mod > 2.0:
        pitch_mod = 2.0
    
    html = r"""
    <div style="margin-top: 0.35rem; font-size: 0.85rem;">
      <div style="display: flex; gap: 0.35rem; align-items: center; flex-wrap: wrap;">
        <button id="tts_play_{key}" style="padding: 0.25rem 0.5rem;">▶️</button>
        <button id="tts_pause_{key}" style="padding: 0.25rem 0.5rem;">⏸️</button>
        <button id="tts_prev_{key}" style="padding: 0.25rem 0.5rem;">⏮️</button>
        <button id="tts_next_{key}" style="padding: 0.25rem 0.5rem;">⏭️</button>
        <label for="tts_speed_{key}" style="margin-left: 0.5rem; font-size: 0.75rem;">speed</label>
        <select id="tts_speed_{key}" style="padding: 0.2rem 0.3rem; font-size: 0.75rem;">
          <option value="0.75">0.75×</option>
          <option value="1.0" selected>1.0×</option>
          <option value="1.25">1.25×</option>
          <option value="1.5">1.5×</option>
          <option value="2.0">2.0×</option>
        </select>
        <label for="tts_volume_{key}" style="margin-left: 0.5rem; font-size: 0.75rem;">vol</label>
        <input id="tts_volume_{key}" type="range" min="0" max="1" step="0.1" value="1" style="width: 70px;" />
        <label for="tts_pitch_{key}" style="margin-left: 0.5rem; font-size: 0.75rem;">pitch</label>
        <input id="tts_pitch_{key}" type="range" min="0.5" max="2.0" step="0.1" value="{pitch_mod}" style="width: 70px;" />
        <span id="tts_status_{key}" style="margin-left: 0.5rem; color: #8b949e; font-size: 0.75rem;">(ready)</span>
      </div>
    </div>"
    <script>
      (function() {{
        if (typeof window === 'undefined' || !window.speechSynthesis) {{
          const statusEl = document.getElementById('tts_status_{key}');
          if (statusEl) {{
            statusEl.textContent = '(TTS not supported)';
          }}
          return;
        }}

        const paragraphs = String({js_text})
          .split(/\n\s*\n/)
          .map(p => p.trim())
          .filter(Boolean);
        if (!paragraphs.length) return;

        let currentIndex = 0;
        let utter = null;
        let isPaused = false;

        const statusEl = document.getElementById('tts_status_{key}');
        const updateStatus = () => {{
          if (!utter) {{
            statusEl.textContent = '(ready)';
          }} else if (isPaused) {{
            statusEl.textContent = `(paused) paragraph ${{currentIndex + 1}}/${{paragraphs.length}}`;
          }} else {{
            statusEl.textContent = `(playing) paragraph ${{currentIndex + 1}}/${{paragraphs.length}}`;
          }}
        }};

        const makeUtterance = (text) => {{
          const u = new SpeechSynthesisUtterance(text);
          const speed = parseFloat(document.getElementById('tts_speed_{key}').value) || 1.0;
          u.rate = speed;
          const volume = parseFloat(document.getElementById('tts_volume_{key}').value) || 1.0;
          u.volume = volume;
          const pitch = parseFloat(document.getElementById('tts_pitch_{key}').value) || 1.0;
          u.pitch = pitch;
          u.onend = () => {{
            if (currentIndex < paragraphs.length - 1) {{
              currentIndex += 1;
              playCurrent();
            }} else {{
              utter = null;
              isPaused = false;
              updateStatus();
            }}
          }};
          return u;
        }};

        const playCurrent = () => {{
          try {{
            if (utter && isPaused) {{
              speechSynthesis.resume();
              isPaused = false;
              updateStatus();
              return;
            }}

            if (speechSynthesis.speaking) {{
              speechSynthesis.cancel();
            }}
            utter = makeUtterance(paragraphs[currentIndex]);
            isPaused = false;
            speechSynthesis.speak(utter);
            updateStatus();
          }} catch (err) {{
            console.warn('TTS play failed', err);
            const statusEl = document.getElementById('tts_status_{key}');
            if (statusEl) statusEl.textContent = '(TTS error)';
          }}
        }};

        const pause = () => {{
          if (speechSynthesis.speaking) {{
            speechSynthesis.pause();
            isPaused = true;
            updateStatus();
          }}
        }};

        const prev = () => {{
          if (currentIndex > 0) {{
            currentIndex -= 1;
            playCurrent();
          }}
        }};

        const next = () => {{
          if (currentIndex < paragraphs.length - 1) {{
            currentIndex += 1;
            playCurrent();
          }}
        }};

        document.getElementById('tts_play_{key}')?.addEventListener('click', playCurrent);
        document.getElementById('tts_pause_{key}')?.addEventListener('click', pause);
        document.getElementById('tts_prev_{key}')?.addEventListener('click', prev);
        document.getElementById('tts_next_{key}')?.addEventListener('click', next);
        document.getElementById('tts_speed_{key}')?.addEventListener('change', () => {{
          if (utter && speechSynthesis.speaking && !isPaused) {{
            // restart current paragraph at new speed
            playCurrent();
          }}
        }});
        document.getElementById('tts_volume_{key}')?.addEventListener('change', () => {{
          if (utter && speechSynthesis.speaking && !isPaused) {{
            // restart current paragraph at new volume
            playCurrent();
          }}
        }});
        document.getElementById('tts_pitch_{key}')?.addEventListener('change', () => {{
          if (utter && speechSynthesis.speaking && !isPaused) {{
            // restart current paragraph at new pitch
            playCurrent();
          }}
        }});

        updateStatus();
      }})();
    </script>
    """.format(js_text=js_text, key=key, pitch_mod=pitch_mod)

    components.html(html, height=110)

# ── Session accumulator helpers ───────────────────────────────────────────────

def _merge_persons(new_persons: List[Dict[str, Any]]) -> None:
    """Merge newly-discovered person dicts into session-state list (by name).

    The ``"self"`` entry (relationship_to_querent == "self") is protected:
    if a new person dict shares the same name as the existing self-entry,
    the self-entry is kept unchanged.
    """
    if not new_persons:
        return
    existing: List[Dict[str, Any]] = st.session_state.get(_PERSONS_KEY, [])
    names = {p.get("name", "").lower() for p in existing}
    # Collect names that belong to the protected self-entry
    _self_names = {
        p.get("name", "").lower()
        for p in existing
        if p.get("relationship_to_querent") == "self"
    }
    for p in new_persons:
        key = (p.get("name") or "").lower()
        if not key or key in names:
            continue
        # Never let a new entry overwrite / collide with the self-entry
        if key in _self_names:
            continue
        existing.append(p)
        names.add(key)
    st.session_state[_PERSONS_KEY] = existing


def _merge_locations(new_locations: List[Dict[str, Any]]) -> None:
    """Merge newly-discovered location dicts into session-state list (by name)."""
    if not new_locations:
        return
    existing: List[Dict[str, Any]] = st.session_state.get(_LOCATIONS_KEY, [])
    names = {loc.get("name", "").lower() for loc in existing}
    for loc in new_locations:
        key = (loc.get("name") or "").lower()
        if key and key not in names:
            existing.append(loc)
            names.add(key)
    st.session_state[_LOCATIONS_KEY] = existing


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
    chart_b: Any = None,
    edges_inter_chart: Optional[List[Any]] = None,
    known_persons: Optional[List[Dict[str, Any]]] = None,
    known_locations: Optional[List[Dict[str, Any]]] = None,
    pending_clarification: Optional[str] = None,
    agent_memory: Optional[AgentMemory] = None,
) -> tuple[str, Dict[str, Any]]:
    """Run the full MCP pipeline. Returns (response_text, meta)."""

    meta: Dict[str, Any] = {"mode": mode, "voice": voice}
    voice_lower = voice.lower()

    # Convert session-stored dicts back to dataclass instances for comprehension
    from src.mcp.comprehension_models import PersonProfile, Location, LocationLink
    _persons: Optional[List[PersonProfile]] = None
    _locations: Optional[List[Location]] = None
    if known_persons:
        _persons = []
        for pd in known_persons:
            locs = [LocationLink(location_name=ld.get("location", ""), connection=ld.get("connection", ""))
                    for ld in pd.get("locations", [])]
            _persons.append(PersonProfile(
                name=pd.get("name"), relationship_to_querent=pd.get("relationship_to_querent"),
                relationships_to_others=pd.get("relationships_to_others", []),
                memories=pd.get("memories", []), significant_places=pd.get("significant_places", []),
                chart_id=pd.get("chart_id"), locations=locs,
            ))
    if known_locations:
        _locations = []
        for ld in known_locations:
            conn = [(cp.get("person", ""), cp.get("connection", "")) for cp in ld.get("connected_persons", [])]
            _locations.append(Location(
                name=ld.get("name", ""), location_type=ld.get("location_type"),
                connected_persons=conn, relevance=ld.get("relevance"),
            ))

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
            chart_b=chart_b,
            edges_inter_chart=edges_inter_chart or None,
            known_persons=_persons,
            known_locations=_locations,
            pending_clarification=pending_clarification,
            agent_memory=agent_memory,
        )

        # ── Handle clarification request ─────────────────────────────
        if packet._clarification:
            clar = packet._clarification
            meta["_is_clarification"] = True
            meta["comprehension_note"] = packet.comprehension_note
            follow_up = clar.get("follow_up_question", "Could you tell me more about what you'd like to know?")
            return follow_up, meta

        meta["domain"]     = packet.domain
        meta["subtopic"]   = packet.subtopic
        meta["confidence"] = packet.confidence
        meta["question_type"] = packet.question_type
        meta["comprehension_note"] = packet.comprehension_note

        # ── Accumulate persons & locations from this turn ────────────
        if packet.persons:
            meta["_new_persons"] = packet.persons
        if packet.locations:
            meta["_new_locations"] = packet.locations

        # ── Dev trace — full inner-monologue snapshot ──────────────
        meta["_dev"] = {
            "question": question,
            # Step 0 — grammar diagram
            "step0_grammar": packet.debug_q_graph.get("grammar") if packet.debug_q_graph else None,
            # Step 1 — comprehension
            "step1_comprehension": {
                "source": packet.debug_comprehension_source or "keyword",
                "domain": packet.domain,
                "subtopic": packet.subtopic,
                "confidence": packet.confidence,
                "question_type": packet.question_type,
                "question_intent": packet.question_intent or "",
                "paraphrase": packet.paraphrase or "",
                "comprehension_note": packet.comprehension_note,
                "matched_keywords": packet.matched_keywords,
                "temporal_dimension": packet.temporal_dimension,
                "subject_config": packet.subject_config,
                "needs_chart_b": packet.needs_chart_b,
                "q_graph": packet.debug_q_graph,
                # 5W+H enrichments
                "persons": packet.persons or [],
                "story_objects": packet.story_objects or [],
                "locations": packet.locations or [],
                "dilemma": packet.dilemma,
                "answer_aim": packet.answer_aim,
                "querent_state": packet.querent_state,
                "setting_time": packet.setting_time,
                "intent_context": packet.intent_context,
                "desired_input": packet.desired_input,
                "transits": packet.transits or [],
            },
            # Step 2 — factor resolution & relevant objects
            "step2_factor_resolution": {
                "merged_factors": packet.debug_relevant_factors,
                "relevant_objects": packet.debug_relevant_objects,
            },
            # Step 3 — circuit query
            "step3_circuit": packet.debug_circuit_summary,
            # Step 4 — classical facts assembled
            "step4_facts": {
                "placements":  [(p.object_name, p.sign, f"H{p.house}", p.dignity or "—") for p in packet.placements],
                "aspects":     [(a.object1, a.aspect_name, a.object2, f"{a.orb:.1f}°") for a in packet.aspects],
                "patterns":    [(pat.pattern_type, pat.members) for pat in packet.patterns],
                "dignities":   [(d.object_name, d.dignity_type, d.sign) for d in packet.dignities],
                "dispositors": [(ds.object_name, ds.ruled_by) for ds in packet.dispositors],
                "houses":      [h.to_dict() for h in (packet.houses or [])],
                "sect":        packet.sect.to_dict() if packet.sect else None,
                "summary":     packet.summary_line(),
                "token_estimate": packet.token_estimate(),
            },
            # Step 5 will be filled after synthesis
            "step5_synthesis": {},
        }

    except Exception as exc:
        return (
            f"⚠️ Failed to build reading packet: `{exc}`\n\n"
            "This may mean the chart data is in an unexpected format.",
            meta,
        )

    # Auto-detect synthesis mode from comprehension result
    _td = packet.temporal_dimension or "natal"
    if _td == "synastry" or (
        packet.subject_config == "dyadic" and packet.chart_b_full_placements
    ):
        _synthesize_mode = "synastry"
    elif _td in ("transit", "cycle", "timing_predict", "solar_return"):
        _synthesize_mode = "transit"
    else:
        _synthesize_mode = "natal"

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
            mode=_synthesize_mode,
            voice=voice_lower,
            api_key=api_key,
            agent_memory=agent_memory,
        )
        meta.update({
            "model":             result.model,
            "backend":           result.backend,
            "prompt_tokens":     result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens":      result.total_tokens,
            "synthesis_mode":    _synthesize_mode,
        })
        if "_dev" in meta:
            meta["_dev"]["step5_synthesis"] = {
                "model":             result.model,
                "backend":          result.backend,
                "prompt_tokens":    result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "total_tokens":     result.total_tokens,
            }
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
