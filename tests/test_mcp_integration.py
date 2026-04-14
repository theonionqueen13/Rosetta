"""
Quick integration smoke test for the circuit-driven MCP chatbot pipeline.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))


def test_reading_packet_circuit_fields():
    """ReadingPacket serializes circuit-aware fields."""
    from src.mcp.reading_packet import (
        ReadingPacket, CircuitFlowFact, PowerNodeFact,
        CircuitPathFact,
    )
    pkt = ReadingPacket(
        question="Tell me about my career",
        domain="Career",
        circuit_flows=[CircuitFlowFact(
            "Grand Trine", "gt1", ["Sun", "Jupiter", "Saturn"],
            0.85, 0.10, 12.5, "Effortless loop",
        )],
        power_nodes=[PowerNodeFact("Sun", 5.5, 6.2, 0.3, 1.2)],
        circuit_paths=[CircuitPathFact(
            "career", "money", ["Sun", "Jupiter"], ["Trine"], 0.9, "direct_shape",
        )],
        narrative_seeds=["Sun powers this trine"],
        power_summary={"dominant_node": "Sun"},
        sn_nn_relevance="Path runs through Jupiter",
        question_type="single_focus",
    )
    d = pkt.to_dict()
    assert "circuit_flows" in d
    assert "power_nodes" in d
    assert "circuit_paths" in d
    assert "narrative_seeds" in d
    assert "power_summary" in d
    assert "sn_nn" in d
    assert d["question_type"] == "single_focus"
    assert "circuits" in pkt.summary_line()


def test_prompt_templates_voice_toggle():
    """Voice toggle produces different system prompts."""
    from src.mcp.reading_packet import ReadingPacket
    from src.mcp.prompt_templates import build_prompt

    pkt = ReadingPacket(question="career", domain="Career")
    msgs_plain = build_prompt(pkt, mode="natal", voice="plain")
    msgs_circuit = build_prompt(pkt, mode="natal", voice="circuit")

    # Plain voice should mention psychological/life language
    plain_sys = msgs_plain[0]["content"].lower()
    assert "life language" in plain_sys or "psychological" in plain_sys

    # Circuit voice should mention electrical system
    circuit_sys = msgs_circuit[0]["content"].lower()
    assert "electrical" in circuit_sys or "circuit" in circuit_sys


def _make_fake_chart():
    class Obj:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class FakeChart:
        objects = [
            Obj(object_name=Obj(name="Sun"), sign=Obj(name="Aries"),
                placidus_house=Obj(number=10)),
            Obj(object_name=Obj(name="Moon"), sign=Obj(name="Cancer"),
                placidus_house=Obj(number=4)),
            Obj(object_name=Obj(name="Venus"), sign=Obj(name="Taurus"),
                placidus_house=Obj(number=7)),
        ]
        circuit_simulation = None
        shapes = []

    return FakeChart()


def test_comprehension_keyword_fallback():
    """Keyword fallback produces a valid ComprehensionResult wrapping a QuestionGraph."""
    from src.mcp.comprehension import comprehend, QuestionGraph
    from src.mcp.comprehension_models import ComprehensionResult

    chart = _make_fake_chart()
    result = comprehend("Tell me about my career", chart)
    assert isinstance(result, ComprehensionResult)
    assert result.is_complete
    assert not result.needs_clarification
    qg = result.graph
    assert isinstance(qg, QuestionGraph)
    assert qg.source == "keyword"
    assert len(qg.all_factors) > 0


def test_circuit_query_no_sim():
    """Circuit query returns graceful empty reading when no sim data."""
    from src.mcp.comprehension import comprehend
    from src.mcp.circuit_query import query_circuit, CircuitReading

    chart = _make_fake_chart()
    result = comprehend("Tell me about my career", chart)
    qg = result.graph
    cr = query_circuit(qg, chart)
    assert isinstance(cr, CircuitReading)
    assert len(cr.narrative_seeds) > 0
    assert "not available" in cr.narrative_seeds[0].lower()


def test_tool_registry():
    """All registered tools have matching handlers (count may grow as tools are added)."""
    from src.mcp.tools import TOOL_SCHEMAS, _HANDLERS

    assert len(TOOL_SCHEMAS) == len(_HANDLERS), (
        f"TOOL_SCHEMAS has {len(TOOL_SCHEMAS)} entries but _HANDLERS has {len(_HANDLERS)}"
    )
    assert "get_circuit_reading" in _HANDLERS
    assert "trace_circuit_path" in _HANDLERS

    schema_names = {s["name"] for s in TOOL_SCHEMAS}
    assert schema_names == set(_HANDLERS.keys())


def test_comprehension_relationship_detection():
    """Multi-concept questions produce relationship type."""
    from src.mcp.comprehension import comprehend

    chart = _make_fake_chart()
    result = comprehend("How does my career relate to my relationships?", chart)
    qg = result.graph
    assert qg.question_type == "relationship"
    assert len(qg.nodes) >= 2


def test_prompt_with_agent_notes():
    """Agent notes are included in the system prompt."""
    from src.mcp.reading_packet import ReadingPacket
    from src.mcp.prompt_templates import build_prompt

    pkt = ReadingPacket(
        question="career",
        agent_notes="Prior turn: user interested in 10th house themes.",
    )
    msgs = build_prompt(pkt, mode="natal", voice="plain")
    assert "Prior turn" in msgs[0]["content"]


# ── 5W+H dataclass & ComprehensionResult tests ──────────────────────────────

def test_comprehension_result_wrapper():
    """ComprehensionResult correctly reports needs_clarification and is_complete."""
    from src.mcp.comprehension import QuestionGraph
    from src.mcp.comprehension_models import (
        ComprehensionResult, ClarificationRequest, ClarificationCategory,
    )
    # Complete result
    g = QuestionGraph(nodes=[], question_type="single_focus", domain="Career")
    cr = ComprehensionResult(graph=g, clarification=None)
    assert cr.is_complete
    assert not cr.needs_clarification

    # Clarification result
    clar = ClarificationRequest(
        reason="Ambiguous",
        category=ClarificationCategory.AMBIGUOUS_INTENT,
        follow_up_question="Can you be more specific?",
    )
    cr2 = ComprehensionResult(graph=None, clarification=clar)
    assert cr2.needs_clarification
    assert not cr2.is_complete


def test_clarification_request_serialization():
    """ClarificationRequest.to_dict() roundtrips."""
    from src.mcp.comprehension_models import (
        ClarificationRequest, ClarificationCategory,
    )
    clar = ClarificationRequest(
        reason="Missing info",
        category=ClarificationCategory.MISSING_CONTEXT,
        follow_up_question="Who are you asking about?",
        best_guesses=["partner", "child"],
    )
    d = clar.to_dict()
    assert d["category"] == "missing_context"
    assert d["best_guesses"] == ["partner", "child"]
    assert "follow_up_question" in d


def test_person_profile_creation():
    """PersonProfile builds and serializes correctly."""
    from src.mcp.comprehension_models import PersonProfile, LocationLink
    pp = PersonProfile(
        name="Maria",
        relationship_to_querent="mother",
        locations=[LocationLink(location_name="Madrid", connection="birthplace")],
    )
    d = pp.to_dict()
    assert d["name"] == "Maria"
    assert d["relationship_to_querent"] == "mother"
    assert len(d["locations"]) == 1
    assert d["locations"][0]["location"] == "Madrid"


def test_answer_aim_defaults():
    """AnswerAim defaults to reasonable enum values."""
    from src.mcp.comprehension_models import (
        AnswerAim, AimType, Depth, Urgency, Specificity,
    )
    aim = AnswerAim()
    assert aim.aim_type == AimType.EXPLORATORY
    assert aim.depth == Depth.MODERATE
    assert aim.urgency == Urgency.MODERATE
    assert aim.specificity == Specificity.FOCUSED
    d = aim.to_dict()
    assert d["aim_type"] == "exploratory"


def test_querent_state_serialization():
    """QuerentState serializes enums as strings."""
    from src.mcp.comprehension_models import (
        QuerentState, EmotionalTone, CertaintyLevel, GuidanceOpenness,
    )
    qs = QuerentState(
        emotional_tone=EmotionalTone.ANXIOUS,
        certainty_level=CertaintyLevel.UNSURE,
        guidance_openness=GuidanceOpenness.EXTENSIVE,
        expressed_feelings=["worried", "hopeful"],
    )
    d = qs.to_dict()
    assert d["emotional_tone"] == "anxious"
    assert d["certainty_level"] == "unsure"
    assert "worried" in d["expressed_feelings"]


def test_question_graph_rich_fields():
    """QuestionGraph carries 5W+H fields in to_dict()."""
    from src.mcp.comprehension import QuestionGraph
    from src.mcp.comprehension_models import (
        PersonProfile, AnswerAim, AimType, QuerentState, EmotionalTone,
    )
    g = QuestionGraph(
        nodes=[], question_type="single_focus", domain="Love",
        persons=[PersonProfile(name="Alex", relationship_to_querent="partner")],
        answer_aim=AnswerAim(aim_type=AimType.PREDICTIVE),
        querent_state=QuerentState(emotional_tone=EmotionalTone.HOPEFUL),
    )
    d = g.to_dict()
    assert d["persons"][0]["name"] == "Alex"
    assert d["answer_aim"]["aim_type"] == "predictive"
    assert d["querent_state"]["emotional_tone"] == "hopeful"


def test_location_serialization():
    """Location serializes connected_persons tuples."""
    from src.mcp.comprehension_models import Location
    loc = Location(
        name="New York", location_type="city",
        connected_persons=[("partner", "lives there")],
    )
    d = loc.to_dict()
    assert d["name"] == "New York"
    assert d["connected_persons"][0] == {"person": "partner", "connection": "lives there"}


def test_reading_packet_5wh_fields():
    """ReadingPacket includes 5W+H fields in to_dict when populated."""
    from src.mcp.reading_packet import ReadingPacket
    pkt = ReadingPacket(
        question="career",
        domain="Career",
        persons=[{"name": "Boss", "relationship_to_querent": "employer"}],
        dilemma={"description": "Should I quit?", "options": ["stay", "leave"]},
        answer_aim={"aim_type": "decision", "depth": "moderate"},
        querent_state={"emotional_tone": "anxious"},
        intent_context="career crossroads",
    )
    d = pkt.to_dict()
    assert d["persons"][0]["name"] == "Boss"
    assert d["dilemma"]["description"] == "Should I quit?"
    assert d["answer_aim"]["aim_type"] == "decision"
    assert d["querent_state"]["emotional_tone"] == "anxious"
    assert d["intent_context"] == "career crossroads"


def test_sufficiency_no_explicit_question():
    """Statements without a question trigger clarification via no_explicit_question."""
    from src.mcp.comprehension import QuestionGraph, _check_sufficiency
    from src.mcp.comprehension_models import ClarificationRequest

    g = QuestionGraph(
        nodes=[], question_type="single_focus", domain="General",
        comprehension_confidence=0.2,
        ambiguities=["no_explicit_question"],
    )
    clar = _check_sufficiency(g)
    assert clar is not None
    assert isinstance(clar, ClarificationRequest)
    assert "no_explicit_question" in g.ambiguities
    assert "specific" in clar.follow_up_question.lower() or "context" in clar.follow_up_question.lower()


def test_sufficiency_passes_normal_question():
    """A normal question with decent confidence should NOT trigger clarification."""
    from src.mcp.comprehension import QuestionGraph, _check_sufficiency

    g = QuestionGraph(
        nodes=[], question_type="single_focus", domain="Career",
        comprehension_confidence=0.85,
        ambiguities=[],
    )
    clar = _check_sufficiency(g)
    assert clar is None


# ═══════════════════════════════════════════════════════════════════════
# AgentMemory unit tests
# ═══════════════════════════════════════════════════════════════════════

def test_agent_memory_todo_crud():
    """Add, complete, and query todos."""
    from src.mcp.agent_memory import AgentMemory

    mem = AgentMemory()
    assert mem.is_empty()

    t1 = mem.add_todo("Think about career", source="user")
    t2 = mem.add_todo("Pull full chart placements", source="pipeline")
    assert len(mem.todos) == 2
    assert len(mem.open_todos()) == 2

    mem.complete_todo(t1.id)
    assert t1.done
    assert t1.completed_at is not None
    assert len(mem.open_todos()) == 1
    assert mem.open_todos()[0].id == t2.id


def test_agent_memory_user_question_crud():
    """Log a UserQuestion, cross-tag it, then mark it answered."""
    from src.mcp.agent_memory import AgentMemory

    mem = AgentMemory()
    uq = mem.add_user_question(
        "What is my strongest planet?",
        chart_object_refs=["Sun", "Jupiter"],
        shape_refs=["Grand Trine"],
        circuit_refs=["career→identity"],
    )
    assert not uq.answered
    assert len(mem.unanswered_user_questions()) == 1

    mem.answer_user_question(uq.id, "Sun is the dominant power node.")
    assert uq.answered
    assert uq.answer == "Sun is the dominant power node."
    assert len(mem.unanswered_user_questions()) == 0


def test_agent_memory_bot_question_blocks_todo():
    """BotQuestion blocks linked todo until answered."""
    from src.mcp.agent_memory import AgentMemory

    mem = AgentMemory()
    todo = mem.add_todo("Build reading for user question")

    # Bot asks a clarification; links to the todo as prerequisite
    bq = mem.add_bot_question(
        "Do you mean your career or your vocation?",
        prerequisite_for=[todo.id],
    )

    assert bq.awaiting
    assert bq.id in todo.blocked_by   # auto-linked
    assert len(mem.open_todos()) == 0  # blocked, not open
    assert len(mem.blocked_todos()) == 1

    # User replies
    mem.answer_bot_question(bq.id, "Career, specifically finances.")
    assert bq.answered
    assert not bq.awaiting

    # Now the todo should be open again
    assert len(mem.open_todos()) == 1
    assert len(mem.blocked_todos()) == 0


def test_agent_memory_round_trip_serialisation():
    """to_dict / from_dict round-trips for all three dataclasses."""
    from src.mcp.agent_memory import AgentMemory, ToDo, UserQuestion, BotQuestion

    # --- ToDo ---
    t = ToDo(description="check Mars", source="pipeline")
    t.complete()
    t2 = ToDo.from_dict(t.to_dict())
    assert t2.description == t.description
    assert t2.done == t.done
    assert t2.completed_at == t.completed_at

    # --- UserQuestion ---
    uq = UserQuestion(
        text="Is Saturn strong?",
        chart_object_refs=["Saturn"],
        shape_refs=["T-Square"],
    )
    uq2 = UserQuestion.from_dict(uq.to_dict())
    assert uq2.text == uq.text
    assert uq2.chart_object_refs == ["Saturn"]
    assert uq2.shape_refs == ["T-Square"]

    # --- BotQuestion ---
    bq = BotQuestion(text="Which house system do you prefer?", prerequisite_for=["abc-123"])
    bq2 = BotQuestion.from_dict(bq.to_dict())
    assert bq2.text == bq.text
    assert bq2.awaiting
    assert bq2.prerequisite_for == ["abc-123"]

    # --- Full AgentMemory ---
    mem = AgentMemory(todos=[t], user_questions=[uq], bot_questions=[bq])
    mem2 = AgentMemory.from_dict(mem.to_dict())
    assert len(mem2.todos) == 1
    assert len(mem2.user_questions) == 1
    assert len(mem2.bot_questions) == 1
    assert mem2.todos[0].description == "check Mars"


def test_agent_memory_to_notes_text():
    """to_notes_text() produces a non-empty string with key labels."""
    from src.mcp.agent_memory import AgentMemory

    mem = AgentMemory()
    todo = mem.add_todo("Answer user question about career")
    uq = mem.add_user_question("Tell me about career", chart_object_refs=["Sun"])
    bq = mem.add_bot_question("Are you asking about professional or financial?",
                               prerequisite_for=[todo.id])

    notes = mem.to_notes_text()
    assert "[AGENT MEMORY" in notes
    assert "Answer user question about career" in notes
    assert "Tell me about career" in notes
    assert "Are you asking about professional or financial?" in notes
    assert "AWAITING" in notes   # BotQuestion is awaiting


def test_tool_context_has_agent_memory():
    """ToolContext initialises with a fresh AgentMemory by default."""
    from src.mcp.tools import ToolContext
    from src.mcp.agent_memory import AgentMemory

    ctx = ToolContext()
    assert isinstance(ctx.agent_memory, AgentMemory)
    assert ctx.agent_memory.is_empty()

    # Can also supply a pre-populated one
    mem = AgentMemory()
    mem.add_todo("pre-existing")
    ctx2 = ToolContext(agent_memory=mem)
    assert not ctx2.agent_memory.is_empty()


def test_answer_all_pending_bot_questions():
    """answer_all_pending_bot_questions() resolves every awaiting question."""
    from src.mcp.agent_memory import AgentMemory

    mem = AgentMemory()
    bq1 = mem.add_bot_question("What time were you born?")
    bq2 = mem.add_bot_question("Which city?")
    assert len(mem.pending_bot_questions()) == 2

    count = mem.answer_all_pending_bot_questions("7am, New York")
    assert count == 2
    assert all(not bq.awaiting for bq in [bq1, bq2])
    assert len(mem.pending_bot_questions()) == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
