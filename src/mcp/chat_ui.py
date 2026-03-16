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

_HISTORY_KEY    = "mcp_chat_history"   # List[Dict] — {role, content, meta}
_MODEL_KEY      = "mcp_model"
_HS_KEY         = "mcp_house_system"
_NOTES_KEY      = "mcp_agent_notes"    # str — accumulated across conversation
_MODE_KEY       = "mcp_chat_mode"      # "Ask" | "Plan" | "Agent"
_VOICE_KEY      = "mcp_voice_mode"     # "Plain" | "Circuit"
_DEV_TRACE_KEY  = "mcp_dev_trace"      # dict  — last-turn inner-monologue (dev only)

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
    st.session_state.setdefault(_DEV_TRACE_KEY, {})


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
                st.session_state[_DEV_TRACE_KEY] = {}
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
                    _render_read_aloud_button(msg["content"], key=f"msg_{msg_idx}")

        # Chat input (must be inside the column to make :has() CSS work)
        prompt = st.chat_input("Ask your chart anything…", key="mcp_chat_input")

    # ── Dev inner-monologue expander (always rendered after columns) ───────
    _render_dev_expander()

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
                chart_b=st.session_state.get("last_chart_2"),
            )

        # Accumulate agent notes from this turn
        turn_note = meta.get("comprehension_note", "")
        if turn_note:
            existing = st.session_state.get(_NOTES_KEY, "")
            st.session_state[_NOTES_KEY] = (
                (existing + "\n" if existing else "") + turn_note
            )

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

        # ── Step 1: Comprehension ─────────────────────────────────────────
        with st.container():
            st.markdown("#### Step 1 — Question Comprehension")
            s1 = trace.get("step1_comprehension", {})
            _paraphrase = s1.get("paraphrase", "")
            if _paraphrase and not _paraphrase.startswith("("):
                st.info(f'**Understood as:** "{_paraphrase}"')
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

            q_graph = s1.get("q_graph") or {}
            if q_graph:
                with st.expander("QuestionGraph detail", expanded=False):
                    _qi = q_graph.get("question_intent") or ""
                    if _qi:
                        st.success(f"**Routing intent:** `{_qi}`")
                    nodes = q_graph.get("nodes", [])
                    if nodes:
                        st.markdown("**Concept nodes:**")
                        for n in nodes:
                            st.markdown(
                                f"- `{n.get('label', '?')}` "
                                f"(source: *{n.get('source', '?')}*) — "
                                f"factors: {', '.join(n.get('factors', [])) or '*(none — intent-driven)*'}"
                            )
                    edges = q_graph.get("edges", [])
                    if edges:
                        st.markdown("**Concept edges:**")
                        for e in edges:
                            st.markdown(
                                f"- `{e.get('a', '?')}` ↔ `{e.get('b', '?')}` "
                                f"(*{e.get('rel', '?')}*)"
                            )
                    focus = q_graph.get("focus_circuits", [])
                    if focus:
                        st.markdown(f"**Focus circuit IDs:** {focus}")
                    all_f = q_graph.get("all_factors", [])
                    if all_f:
                        st.markdown(f"**All factors:** {', '.join(all_f)}")

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

            isolations = s3.get("isolation_notes", [])
            if isolations:
                st.warning("**Isolation notes:** " + " | ".join(isolations))

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

def _render_read_aloud_button(text: str, key: str) -> None:
    """Render a set of playback controls using the browser SpeechSynthesis API.

    Controls include play/pause, paragraph navigation, and speed adjustment.
    """

    # Use JSON to safely embed the text in JS (properly escapes quotes/newlines)
    js_text = json.dumps(text)
    html = r"""
    <div style="margin-top: 0.35rem; font-size: 0.85rem;">
      <div style="display: flex; gap: 0.35rem; align-items: center;">
        <button id="tts_play_{key}" style="padding: 0.25rem 0.5rem;">▶️</button>
        <button id="tts_pause_{key}" style="padding: 0.25rem 0.5rem;">⏸️</button>
        <button id="tts_prev_{key}" style="padding: 0.25rem 0.5rem;">⏮️</button>
        <button id="tts_next_{key}" style="padding: 0.25rem 0.5rem;">⏭️</button>
        <label for="tts_speed_{key}" style="margin-left: 0.5rem;">speed</label>
        <select id="tts_speed_{key}" style="padding: 0.2rem 0.3rem;">
          <option value="0.75">0.75×</option>
          <option value="1.0" selected>1.0×</option>
          <option value="1.25">1.25×</option>
          <option value="1.5">1.5×</option>
          <option value="2.0">2.0×</option>
        </select>
        <label for="tts_volume_{key}" style="margin-left: 0.5rem;">vol</label>
        <input id="tts_volume_{key}" type="range" min="0" max="1" step="0.1" value="1" style="width: 90px;" />
        <span id="tts_status_{key}" style="margin-left: 0.5rem; color: #8b949e;">(ready)</span>
      </div>
    </div>
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

        updateStatus();
      }})();
    </script>
    """.format(js_text=js_text, key=key)

    components.html(html, height=110)

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
            chart_b=chart_b,
        )
        meta["domain"]     = packet.domain
        meta["subtopic"]   = packet.subtopic
        meta["confidence"] = packet.confidence
        meta["question_type"] = packet.question_type
        meta["comprehension_note"] = packet.comprehension_note

        # ── Dev trace — full inner-monologue snapshot ──────────────
        meta["_dev"] = {
            "question": question,
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
                "q_graph": packet.debug_q_graph,
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
