"""
agent_memory.py — Structured private memory for the Rosetta MCP chatbot.

Three dataclasses track the bot's internal state across a session:

  • ToDo          — tasks the bot must complete (auto-created by the
                    reading pipeline or via the /todo slash-command)
  • UserQuestion  — questions the user asked, with cross-tags to the
                    chart objects / shapes / circuits involved; auto-
                    marked answered once a response is produced
  • BotQuestion   — questions the bot asked the user, automatically
                    flagged as "awaiting", with prerequisite links to
                    the ToDos that are blocked until answered

All three implement to_dict() / from_dict() for full round-trip
serialisation — this is the integration seam for future Supabase
persistence (swap session_state reads/writes for upsert/select calls).

AgentMemory is the session-level container. The LLM reads a compact
text summary injected into the system prompt (via to_notes_text()),
but cannot modify these records directly — the pipeline writes them.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    """Generate a random UUID4 string."""
    return str(uuid.uuid4())


# ═══════════════════════════════════════════════════════════════════════
# ToDo
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class ToDo:
    """A task the bot must complete.

    Created automatically by the reading pipeline (e.g. flagged follow-up
    items) or manually via the /todo slash-command.

    blocked_by holds ids of BotQuestion records that must be answered
    before this task can proceed.  open_todos() respects this gate.
    """
    id: str = field(default_factory=_uid)
    description: str = ""
    done: bool = False
    created_at: str = field(default_factory=_now_iso)
    completed_at: Optional[str] = None
    blocked_by: List[str] = field(default_factory=list)  # BotQuestion ids
    source: str = "pipeline"  # "pipeline" | "user"

    def complete(self) -> None:
        """Mark this to-do as done and record the completion timestamp."""
        self.done = True
        self.completed_at = _now_iso()

    # ── serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise this to-do to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "done": self.done,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "blocked_by": list(self.blocked_by),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ToDo":
        """Reconstruct a ToDo from a dictionary."""
        return cls(
            id=d.get("id", _uid()),
            description=d.get("description", ""),
            done=bool(d.get("done", False)),
            created_at=d.get("created_at", _now_iso()),
            completed_at=d.get("completed_at"),
            blocked_by=list(d.get("blocked_by", [])),
            source=d.get("source", "pipeline"),
        )


# ═══════════════════════════════════════════════════════════════════════
# UserQuestion
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class UserQuestion:
    """A question the user asked the bot.

    Cross-tagged to the memory nodes, chart objects, shapes, and circuits
    that are relevant to the answer.  Auto-marked answered once a response
    is produced by the reading pipeline.
    """
    id: str = field(default_factory=_uid)
    text: str = ""
    asked_at: str = field(default_factory=_now_iso)
    answered: bool = False
    answer: Optional[str] = None          # summary of the response produced
    answered_at: Optional[str] = None

    # Cross-tags (populated automatically by the reading engine)
    memory_node_refs: List[str] = field(default_factory=list)  # free-form labels
    chart_object_refs: List[str] = field(default_factory=list) # e.g. ["Sun", "Moon"]
    shape_refs: List[str] = field(default_factory=list)        # e.g. ["Grand Trine"]
    circuit_refs: List[str] = field(default_factory=list)      # circuit/flow names

    def mark_answered(self, answer_summary: str) -> None:
        """Record the answer summary and mark this question as answered."""
        self.answered = True
        self.answer = answer_summary
        self.answered_at = _now_iso()

    # ── serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise this user question to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "asked_at": self.asked_at,
            "answered": self.answered,
            "answer": self.answer,
            "answered_at": self.answered_at,
            "memory_node_refs": list(self.memory_node_refs),
            "chart_object_refs": list(self.chart_object_refs),
            "shape_refs": list(self.shape_refs),
            "circuit_refs": list(self.circuit_refs),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserQuestion":
        """Reconstruct a UserQuestion from a dictionary."""
        return cls(
            id=d.get("id", _uid()),
            text=d.get("text", ""),
            asked_at=d.get("asked_at", _now_iso()),
            answered=bool(d.get("answered", False)),
            answer=d.get("answer"),
            answered_at=d.get("answered_at"),
            memory_node_refs=list(d.get("memory_node_refs", [])),
            chart_object_refs=list(d.get("chart_object_refs", [])),
            shape_refs=list(d.get("shape_refs", [])),
            circuit_refs=list(d.get("circuit_refs", [])),
        )


# ═══════════════════════════════════════════════════════════════════════
# BotQuestion
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class BotQuestion:
    """A question the bot asked the user.

    Automatically flagged awaiting=True when created.  Linked to the ToDo
    ids that are blocked until this question is answered (prerequisite_for).
    Flipped to awaiting=False and answered=True when the user replies.
    """
    id: str = field(default_factory=_uid)
    text: str = ""
    asked_at: str = field(default_factory=_now_iso)
    answered: bool = False
    answer: Optional[str] = None          # user's reply
    answered_at: Optional[str] = None
    awaiting: bool = True
    prerequisite_for: List[str] = field(default_factory=list)  # ToDo ids

    def mark_answered(self, user_reply: str) -> None:
        """Record the user's reply and mark this bot question as answered."""
        self.answered = True
        self.answer = user_reply
        self.answered_at = _now_iso()
        self.awaiting = False

    # ── serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise this bot question to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "text": self.text,
            "asked_at": self.asked_at,
            "answered": self.answered,
            "answer": self.answer,
            "answered_at": self.answered_at,
            "awaiting": self.awaiting,
            "prerequisite_for": list(self.prerequisite_for),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BotQuestion":
        """Reconstruct a BotQuestion from a dictionary."""
        return cls(
            id=d.get("id", _uid()),
            text=d.get("text", ""),
            asked_at=d.get("asked_at", _now_iso()),
            answered=bool(d.get("answered", False)),
            answer=d.get("answer"),
            answered_at=d.get("answered_at"),
            awaiting=bool(d.get("awaiting", True)),
            prerequisite_for=list(d.get("prerequisite_for", [])),
        )


# ═══════════════════════════════════════════════════════════════════════
# AgentMemory — session-level container
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AgentMemory:
    """Session-level container for all private bot memory.

    Holds three chronological lists (todos, user_questions, bot_questions).
    All mutations go through the helper methods so cross-links stay
    consistent.

    Persistence seam
    ----------------
    to_dict() / from_dict() provide full round-trip serialisation.
    The current implementation stores the result in Streamlit session_state;
    a future Supabase integration simply replaces those read/write points
    with upsert / select calls — the dataclass layer stays unchanged.
    """

    todos: List[ToDo] = field(default_factory=list)
    user_questions: List[UserQuestion] = field(default_factory=list)
    bot_questions: List[BotQuestion] = field(default_factory=list)

    # ── ToDo CRUD ──────────────────────────────────────────────────

    def add_todo(
        self,
        description: str,
        *,
        source: str = "pipeline",
        blocked_by: Optional[List[str]] = None,
    ) -> ToDo:
        """Create and store a new ToDo. Returns it for optional chaining."""
        todo = ToDo(
            description=description,
            source=source,
            blocked_by=list(blocked_by or []),
        )
        self.todos.append(todo)
        return todo

    def complete_todo(self, todo_id: str) -> bool:
        """Mark a ToDo as done. Returns True if found."""
        for t in self.todos:
            if t.id == todo_id:
                t.complete()
                return True
        return False

    def open_todos(self) -> List[ToDo]:
        """Todos that are not done AND not blocked by an unanswered BotQuestion."""
        awaiting_ids = {bq.id for bq in self.bot_questions if bq.awaiting}
        return [
            t for t in self.todos
            if not t.done and not (set(t.blocked_by) & awaiting_ids)
        ]

    def blocked_todos(self) -> List[ToDo]:
        """Todos that are waiting on at least one unanswered BotQuestion."""
        awaiting_ids = {bq.id for bq in self.bot_questions if bq.awaiting}
        return [
            t for t in self.todos
            if not t.done and (set(t.blocked_by) & awaiting_ids)
        ]

    # ── UserQuestion CRUD ──────────────────────────────────────────

    def add_user_question(
        self,
        text: str,
        *,
        chart_object_refs: Optional[List[str]] = None,
        shape_refs: Optional[List[str]] = None,
        circuit_refs: Optional[List[str]] = None,
        memory_node_refs: Optional[List[str]] = None,
    ) -> UserQuestion:
        """Log a question the user asked. Returns the new UserQuestion."""
        uq = UserQuestion(
            text=text,
            chart_object_refs=list(chart_object_refs or []),
            shape_refs=list(shape_refs or []),
            circuit_refs=list(circuit_refs or []),
            memory_node_refs=list(memory_node_refs or []),
        )
        self.user_questions.append(uq)
        return uq

    def answer_user_question(self, question_id: str, answer_summary: str) -> bool:
        """Mark a UserQuestion answered. Returns True if found."""
        for uq in self.user_questions:
            if uq.id == question_id:
                uq.mark_answered(answer_summary)
                return True
        return False

    def unanswered_user_questions(self) -> List[UserQuestion]:
        """Return all user questions that have not yet been answered."""
        return [uq for uq in self.user_questions if not uq.answered]

    # ── BotQuestion CRUD ───────────────────────────────────────────

    def add_bot_question(
        self,
        text: str,
        *,
        prerequisite_for: Optional[List[str]] = None,
    ) -> BotQuestion:
        """Log a question the bot asked the user. Returns the new BotQuestion.

        The new BotQuestion is added as a blocker on every ToDo id listed
        in prerequisite_for.
        """
        bq = BotQuestion(
            text=text,
            prerequisite_for=list(prerequisite_for or []),
        )
        self.bot_questions.append(bq)

        # Mark the linked todos as blocked by this question
        for todo in self.todos:
            if todo.id in bq.prerequisite_for:
                if bq.id not in todo.blocked_by:
                    todo.blocked_by.append(bq.id)

        return bq

    def answer_bot_question(self, question_id: str, user_reply: str) -> bool:
        """Mark a BotQuestion answered with the user's reply. Returns True if found."""
        for bq in self.bot_questions:
            if bq.id == question_id:
                bq.mark_answered(user_reply)
                return True
        return False

    def pending_bot_questions(self) -> List[BotQuestion]:
        """BotQuestions still awaiting a reply from the user."""
        return [bq for bq in self.bot_questions if bq.awaiting]

    # ── Last BotQuestion helper ────────────────────────────────────

    def last_pending_bot_question(self) -> Optional[BotQuestion]:
        """The most recently asked BotQuestion that is still awaiting."""
        pending = self.pending_bot_questions()
        return pending[-1] if pending else None

    # ── Bulk updaters ──────────────────────────────────────────────

    def answer_all_pending_bot_questions(self, user_reply: str) -> int:
        """Answer ALL currently-awaiting BotQuestions with the same reply.

        Used when the user returns a single message that resolves whatever
        the bot was waiting for.  Returns the count of records updated.
        """
        count = 0
        for bq in self.bot_questions:
            if bq.awaiting:
                bq.mark_answered(user_reply)
                count += 1
        return count

    # ── Text summary (injected into system prompt) ─────────────────

    def to_notes_text(self) -> str:
        """Compact bullet-point summary for the LLM system prompt and sidebar.

        Sections are emitted only when non-empty so the block stays terse.
        """
        lines: List[str] = ["[AGENT MEMORY — private internal state]"]

        # Open todos
        open_t = self.open_todos()
        if open_t:
            lines.append("\nOpen To-Dos:")
            for t in open_t:
                lines.append(f"  ☐ [{t.id[:8]}] {t.description}")

        # Blocked todos
        blocked = self.blocked_todos()
        if blocked:
            lines.append("\nBlocked To-Dos (waiting on bot questions):")
            for t in blocked:
                lines.append(f"  ⏸ [{t.id[:8]}] {t.description}")

        # Done todos (last 5)
        done_t = [t for t in self.todos if t.done]
        if done_t:
            lines.append("\nCompleted To-Dos (recent):")
            for t in done_t[-5:]:
                lines.append(f"  ✓ [{t.id[:8]}] {t.description}")

        # User questions & their answers
        if self.user_questions:
            lines.append("\nUser Questions:")
            for uq in self.user_questions:
                status = "✓" if uq.answered else "?"
                tags: List[str] = []
                if uq.chart_object_refs:
                    tags.append("objects: " + ", ".join(uq.chart_object_refs))
                if uq.shape_refs:
                    tags.append("shapes: " + ", ".join(uq.shape_refs))
                if uq.circuit_refs:
                    tags.append("circuits: " + ", ".join(uq.circuit_refs))
                tag_str = "  [" + " | ".join(tags) + "]" if tags else ""
                lines.append(f"  {status} [{uq.id[:8]}] Q: {uq.text[:120]}{tag_str}")
                if uq.answered and uq.answer:
                    lines.append(f"         A: {uq.answer[:200]}")

        # Bot questions
        if self.bot_questions:
            lines.append("\nBot Questions asked to user:")
            for bq in self.bot_questions:
                if bq.awaiting:
                    status = "⏳ AWAITING"
                elif bq.answered:
                    status = "✓"
                else:
                    status = "?"
                lines.append(f"  {status} [{bq.id[:8]}] Q: {bq.text[:120]}")
                if bq.answered and bq.answer:
                    lines.append(f"         Reply: {bq.answer[:200]}")
                if bq.prerequisite_for:
                    lines.append(f"         Prerequisite for todos: {bq.prerequisite_for}")

        return "\n".join(lines)

    # ── Serialisation ──────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the full agent memory to a JSON-safe dictionary."""
        return {
            "todos": [t.to_dict() for t in self.todos],
            "user_questions": [uq.to_dict() for uq in self.user_questions],
            "bot_questions": [bq.to_dict() for bq in self.bot_questions],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentMemory":
        """Reconstruct an AgentMemory from a dictionary."""
        return cls(
            todos=[ToDo.from_dict(t) for t in d.get("todos", [])],
            user_questions=[UserQuestion.from_dict(uq) for uq in d.get("user_questions", [])],
            bot_questions=[BotQuestion.from_dict(bq) for bq in d.get("bot_questions", [])],
        )

    # ── Convenience ───────────────────────────────────────────────

    def is_empty(self) -> bool:
        """Return True if no todos, user questions, or bot questions exist."""
        return not (self.todos or self.user_questions or self.bot_questions)

    def stats(self) -> Dict[str, int]:
        """Return summary counts of memory items by category."""
        return {
            "todos_open": len(self.open_todos()),
            "todos_done": len([t for t in self.todos if t.done]),
            "todos_blocked": len(self.blocked_todos()),
            "user_q_total": len(self.user_questions),
            "user_q_unanswered": len(self.unanswered_user_questions()),
            "bot_q_total": len(self.bot_questions),
            "bot_q_awaiting": len(self.pending_bot_questions()),
        }
