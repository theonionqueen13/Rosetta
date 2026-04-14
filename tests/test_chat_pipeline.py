"""Tests for src.mcp.chat_pipeline — chat pipeline with mocked LLM."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

MODULE = "src.mcp.chat_pipeline"

# Lazy imports inside run_pipeline — patch at source modules
_BUILD = "src.mcp.reading_engine.build_reading"
_SYNTH = "src.mcp.prose_synthesizer.synthesize"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_chat_state():
    """Reset all module-level per-session dicts before & after each test."""
    from src.mcp.chat_pipeline import (
        CHAT_MEMORY, CHAT_DEV_TRACE, CHAT_PERSONS, CHAT_LOCATIONS,
    )
    CHAT_MEMORY.clear()
    CHAT_DEV_TRACE.clear()
    CHAT_PERSONS.clear()
    CHAT_LOCATIONS.clear()
    yield
    CHAT_MEMORY.clear()
    CHAT_DEV_TRACE.clear()
    CHAT_PERSONS.clear()
    CHAT_LOCATIONS.clear()


@pytest.fixture()
def mock_packet():
    """Return a MagicMock mimicking a ReadingPacket from build_reading."""
    p = MagicMock(name="ReadingPacket")
    p._clarification = None
    p.domain = "natal"
    p.subtopic = "planets"
    p.confidence = 0.9
    p.question_type = "factual"
    p.comprehension_note = ""
    p.persons = []
    p.locations = []
    p.temporal_dimension = "natal"
    p.subject_config = "singular"
    p.chart_b_full_placements = None
    p.paraphrase = "test paraphrase"
    p.debug_relevant_factors = []
    p.debug_relevant_objects = []
    p.debug_circuit_summary = {}
    return p


@pytest.fixture()
def mock_synth_result():
    """Return a MagicMock mimicking a SynthesisResult from synthesize."""
    r = MagicMock(name="SynthesisResult")
    r.text = "The Moon in Aries is fiery."
    r.model = "test-model"
    r.backend = "openrouter"
    r.prompt_tokens = 100
    r.completion_tokens = 50
    r.total_tokens = 150
    return r


def _run_defaults(**overrides):
    """Return a kwargs dict for run_pipeline with sensible defaults."""
    kw = dict(
        question="What does my Moon mean?",
        chart=MagicMock(name="chart"),
        chart_b=None,
        house_system="placidus",
        uid="test-user",
        api_key="sk-test",
        model="test-model",
        mode="natal",
        voice="Modern",
        agent_notes="",
        pending_q="",
    )
    kw.update(overrides)
    return kw


# ---------------------------------------------------------------------------
# merge_chat_persons
# ---------------------------------------------------------------------------

class TestMergeChatPersons:
    def test_add_new_person(self):
        from src.mcp.chat_pipeline import merge_chat_persons, CHAT_PERSONS
        merge_chat_persons("u1", [{"name": "Alice", "relationship_to_querent": "friend"}])
        assert len(CHAT_PERSONS["u1"]) == 1
        assert CHAT_PERSONS["u1"][0]["name"] == "Alice"

    def test_dedup_by_name(self):
        from src.mcp.chat_pipeline import merge_chat_persons, CHAT_PERSONS
        merge_chat_persons("u1", [{"name": "Alice"}])
        merge_chat_persons("u1", [{"name": "alice"}])  # case-insensitive dup
        assert len(CHAT_PERSONS["u1"]) == 1

    def test_empty_input_noop(self):
        from src.mcp.chat_pipeline import merge_chat_persons, CHAT_PERSONS
        merge_chat_persons("u1", [])
        assert CHAT_PERSONS.get("u1", []) == []

    def test_skip_blank_name(self):
        from src.mcp.chat_pipeline import merge_chat_persons, CHAT_PERSONS
        merge_chat_persons("u1", [{"name": ""}])
        assert len(CHAT_PERSONS.get("u1", [])) == 0

    def test_handles_dataclass_with_to_dict(self):
        from src.mcp.chat_pipeline import merge_chat_persons, CHAT_PERSONS
        obj = MagicMock()
        obj.to_dict.return_value = {"name": "Bob", "relationship_to_querent": "partner"}
        merge_chat_persons("u1", [obj])
        assert len(CHAT_PERSONS["u1"]) == 1
        assert CHAT_PERSONS["u1"][0]["name"] == "Bob"


# ---------------------------------------------------------------------------
# merge_chat_locations
# ---------------------------------------------------------------------------

class TestMergeChatLocations:
    def test_add_new_location(self):
        from src.mcp.chat_pipeline import merge_chat_locations, CHAT_LOCATIONS
        merge_chat_locations("u1", [{"name": "London", "location_type": "city"}])
        assert len(CHAT_LOCATIONS["u1"]) == 1

    def test_dedup_by_name(self):
        from src.mcp.chat_pipeline import merge_chat_locations, CHAT_LOCATIONS
        merge_chat_locations("u1", [{"name": "London"}])
        merge_chat_locations("u1", [{"name": "london"}])
        assert len(CHAT_LOCATIONS["u1"]) == 1

    def test_empty_input_noop(self):
        from src.mcp.chat_pipeline import merge_chat_locations, CHAT_LOCATIONS
        merge_chat_locations("u1", [])
        assert CHAT_LOCATIONS.get("u1", []) == []

    def test_skip_blank_name(self):
        from src.mcp.chat_pipeline import merge_chat_locations, CHAT_LOCATIONS
        merge_chat_locations("u1", [{"name": ""}])
        assert len(CHAT_LOCATIONS.get("u1", [])) == 0


# ---------------------------------------------------------------------------
# run_pipeline
# ---------------------------------------------------------------------------

class TestRunPipeline:
    """Tests for run_pipeline — all LLM/reading dependencies mocked."""

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_happy_path(self, mock_build, mock_synth, mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        text, meta, updates = run_pipeline(**_run_defaults())

        assert text == "The Moon in Aries is fiery."
        assert meta["model"] == "test-model"
        assert meta["domain"] == "natal"
        assert meta["confidence"] == 0.9
        assert "prompt_tokens" in meta
        mock_build.assert_called_once()
        mock_synth.assert_called_once()

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_missing_api_key(self, mock_build, mock_synth, mock_packet):
        from src.mcp.chat_pipeline import run_pipeline
        mock_build.return_value = mock_packet

        text, meta, updates = run_pipeline(**_run_defaults(api_key=""))

        assert "API key" in text
        mock_synth.assert_not_called()
        assert meta["backend"] == "fallback"

    @patch(_BUILD)
    def test_build_reading_raises(self, mock_build):
        from src.mcp.chat_pipeline import run_pipeline
        mock_build.side_effect = RuntimeError("bad data")

        text, meta, _ = run_pipeline(**_run_defaults())

        assert "Failed to build reading" in text
        assert "bad data" in text

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_synthesize_raises(self, mock_build, mock_synth, mock_packet):
        from src.mcp.chat_pipeline import run_pipeline
        mock_build.return_value = mock_packet
        mock_synth.side_effect = ConnectionError("timeout")

        text, meta, _ = run_pipeline(**_run_defaults())

        assert "OpenRouter call failed" in text
        assert "timeout" in text
        assert meta.get("llm_error") == "timeout"

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_clarification_flow(self, mock_build, mock_synth, mock_packet):
        from src.mcp.chat_pipeline import run_pipeline
        mock_packet._clarification = {
            "follow_up_question": "Which person are you asking about?"
        }
        mock_build.return_value = mock_packet

        text, meta, updates = run_pipeline(**_run_defaults())

        assert text == "Which person are you asking about?"
        assert meta.get("_is_clarification") is True
        assert updates.get("mcp_pending_question") == "What does my Moon mean?"
        mock_synth.assert_not_called()

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_clarification_default_follow_up(self, mock_build, mock_synth, mock_packet):
        from src.mcp.chat_pipeline import run_pipeline
        mock_packet._clarification = {"type": "general"}  # truthy but no follow_up_question key
        mock_build.return_value = mock_packet

        text, meta, _ = run_pipeline(**_run_defaults())

        assert "tell me more" in text.lower()
        mock_synth.assert_not_called()

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_persons_merged_after_build(self, mock_build, mock_synth,
                                        mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_PERSONS
        mock_packet.persons = [MagicMock(name="PersonObj")]
        mock_packet.persons[0].to_dict = MagicMock(
            return_value={"name": "Alice", "relationship_to_querent": "friend"}
        )
        # Override isinstance check — treat as non-dict
        mock_packet.persons[0].__class__ = type("PersonProfile", (), {})
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())

        assert len(CHAT_PERSONS.get("test-user", [])) == 1
        assert CHAT_PERSONS["test-user"][0]["name"] == "Alice"

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_locations_merged_after_build(self, mock_build, mock_synth,
                                          mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_LOCATIONS
        mock_packet.locations = [MagicMock(name="LocObj")]
        mock_packet.locations[0].to_dict = MagicMock(
            return_value={"name": "Paris", "location_type": "city"}
        )
        mock_packet.locations[0].__class__ = type("Location", (), {})
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())

        assert len(CHAT_LOCATIONS.get("test-user", [])) == 1

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_memory_created_first_call(self, mock_build, mock_synth,
                                       mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_MEMORY
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())

        assert "test-user" in CHAT_MEMORY

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_memory_reused_second_call(self, mock_build, mock_synth,
                                       mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_MEMORY
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())
        mem1 = CHAT_MEMORY["test-user"]
        run_pipeline(**_run_defaults())
        mem2 = CHAT_MEMORY["test-user"]

        assert mem1 is mem2

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_pending_q_answers_bot_questions(self, mock_build, mock_synth,
                                             mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_MEMORY
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        # First call creates memory
        run_pipeline(**_run_defaults())
        mem = CHAT_MEMORY["test-user"]
        mem.answer_all_pending_bot_questions = MagicMock()

        # Second call with pending_q set
        run_pipeline(**_run_defaults(pending_q="original question"))
        mem.answer_all_pending_bot_questions.assert_called_once_with(
            "What does my Moon mean?"
        )

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_dev_trace_stored(self, mock_build, mock_synth,
                               mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_DEV_TRACE
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())

        trace = CHAT_DEV_TRACE.get("test-user")
        assert trace is not None
        assert "question" in trace
        assert "step1_comprehension" in trace
        assert trace["step1_comprehension"]["domain"] == "natal"

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_comprehension_note_appended_to_agent_notes(
        self, mock_build, mock_synth, mock_packet, mock_synth_result,
    ):
        from src.mcp.chat_pipeline import run_pipeline
        mock_packet.comprehension_note = "User seems anxious about career."
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        _, _, updates = run_pipeline(**_run_defaults(agent_notes="prior note"))

        assert "User seems anxious about career." in updates.get("mcp_agent_notes", "")
        assert "prior note" in updates["mcp_agent_notes"]

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_synastry_mode_detection(self, mock_build, mock_synth,
                                      mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline
        mock_packet.temporal_dimension = "synastry"
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())

        # synthesize should be called with mode="synastry"
        _, kwargs = mock_synth.call_args
        assert kwargs["mode"] == "synastry"

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_transit_mode_detection(self, mock_build, mock_synth,
                                     mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline
        mock_packet.temporal_dimension = "transit"
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        run_pipeline(**_run_defaults())

        _, kwargs = mock_synth.call_args
        assert kwargs["mode"] == "transit"

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_dev_trace_stored_on_synth_error(self, mock_build, mock_synth,
                                              mock_packet):
        from src.mcp.chat_pipeline import run_pipeline, CHAT_DEV_TRACE
        mock_build.return_value = mock_packet
        mock_synth.side_effect = ValueError("API broke")

        run_pipeline(**_run_defaults())

        assert "test-user" in CHAT_DEV_TRACE

    @patch(_SYNTH)
    @patch(_BUILD)
    def test_return_tuple_shape(self, mock_build, mock_synth,
                                 mock_packet, mock_synth_result):
        from src.mcp.chat_pipeline import run_pipeline
        mock_build.return_value = mock_packet
        mock_synth.return_value = mock_synth_result

        result = run_pipeline(**_run_defaults())

        assert isinstance(result, tuple)
        assert len(result) == 3
        text, meta, updates = result
        assert isinstance(text, str)
        assert isinstance(meta, dict)
        assert isinstance(updates, dict)
