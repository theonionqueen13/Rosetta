"""
grammar_parse.py — Step 0: Grammatical Sentence Diagram
========================================================
Extracts the grammatical skeleton of a user's question BEFORE the
5W+H comprehension layer runs.  This gives the downstream pipeline
a pre-parsed structural foundation: subjects, verbs, objects,
modifiers, prepositional phrases, and clause structure.

Uses the existing OpenRouter LLM infrastructure — no new libraries
required.  On any failure the pipeline continues with a minimal
stub so grammar never blocks comprehension.

Public API
----------
  parse_grammar(question, api_key, model) → GrammarDiagram
  format_grammar_for_display(diagram)     → str   (dev expander)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PrepPhrase:
    """A prepositional phrase extracted from the sentence."""
    preposition: str = ""
    object: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Serialise this prepositional phrase to a dictionary."""
        return {"preposition": self.preposition, "object": self.object}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PrepPhrase":
        """Reconstruct a PrepPhrase from a dictionary."""
        return cls(
            preposition=str(d.get("preposition", "")),
            object=str(d.get("object", "")),
        )


@dataclass
class Modifier:
    """A modifier (adjective, adverb, determiner) attached to a word."""
    word: str = ""
    modifies: str = ""
    type: str = ""          # "adjective" | "adverb" | "determiner" | "possessive" | "quantifier"

    def to_dict(self) -> Dict[str, str]:
        """Serialise this modifier to a dictionary."""
        return {"word": self.word, "modifies": self.modifies, "type": self.type}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Modifier":
        """Reconstruct a Modifier from a dictionary."""
        return cls(
            word=str(d.get("word", "")),
            modifies=str(d.get("modifies", "")),
            type=str(d.get("type", "")),
        )


@dataclass
class Clause:
    """A subordinate or coordinate clause identified in the sentence."""
    clause_type: str = ""   # "subordinate" | "relative" | "conditional" | "temporal" | "causal" | "coordinate"
    text: str = ""
    role: str = ""          # "subject_modifier" | "object_modifier" | "adverbial" | "complement" | "condition"

    def to_dict(self) -> Dict[str, str]:
        """Serialise this clause to a dictionary."""
        return {"clause_type": self.clause_type, "text": self.text, "role": self.role}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Clause":
        """Reconstruct a Clause from a dictionary."""
        return cls(
            clause_type=str(d.get("clause_type", "")),
            text=str(d.get("text", "")),
            role=str(d.get("role", "")),
        )


@dataclass
class GrammarDiagram:
    """
    Structured grammatical parse of a user's sentence.

    Fields cover the core sentence skeleton (S-V-O), modifiers,
    prepositional phrases, clause structure, sentence type, and a
    compact bracketed parse tree for dev display.
    """
    subject: str = ""
    verb: str = ""
    verb_tense: str = ""                # "present" | "past" | "future" | "conditional" | "imperative"
    direct_object: str = ""
    indirect_object: str = ""
    prepositional_phrases: List[PrepPhrase] = field(default_factory=list)
    modifiers: List[Modifier] = field(default_factory=list)
    clauses: List[Clause] = field(default_factory=list)
    sentence_type: str = "interrogative"  # "declarative" | "interrogative" | "imperative" | "conditional"
    raw_parse_tree: str = ""            # compact bracketed notation for dev display
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the full grammar diagram to a dictionary."""
        return {
            "subject": self.subject,
            "verb": self.verb,
            "verb_tense": self.verb_tense,
            "direct_object": self.direct_object,
            "indirect_object": self.indirect_object,
            "prepositional_phrases": [pp.to_dict() for pp in self.prepositional_phrases],
            "modifiers": [m.to_dict() for m in self.modifiers],
            "clauses": [c.to_dict() for c in self.clauses],
            "sentence_type": self.sentence_type,
            "raw_parse_tree": self.raw_parse_tree,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GrammarDiagram":
        """Reconstruct a GrammarDiagram from a dictionary."""
        return cls(
            subject=str(d.get("subject", "")),
            verb=str(d.get("verb", "")),
            verb_tense=str(d.get("verb_tense", "")),
            direct_object=str(d.get("direct_object", "")),
            indirect_object=str(d.get("indirect_object", "")),
            prepositional_phrases=[
                PrepPhrase.from_dict(pp) for pp in d.get("prepositional_phrases", [])
            ],
            modifiers=[Modifier.from_dict(m) for m in d.get("modifiers", [])],
            clauses=[Clause.from_dict(c) for c in d.get("clauses", [])],
            sentence_type=str(d.get("sentence_type", "interrogative")),
            raw_parse_tree=str(d.get("raw_parse_tree", "")),
            confidence=float(d.get("confidence", 0.0)),
        )


# ═══════════════════════════════════════════════════════════════════════
# LLM system prompt — grammar extraction
# ═══════════════════════════════════════════════════════════════════════

_GRAMMAR_SYSTEM = """\
You are a grammatical parser. Given a sentence (which may be a question,\
 statement, or command), extract its full grammatical structure.

Return ONLY valid JSON matching this schema:
{
  "subject": "the grammatical subject noun/pronoun (+ its determiners)",
  "verb": "the main verb or verb phrase",
  "verb_tense": "present | past | future | conditional | imperative",
  "direct_object": "what the verb acts on (empty string if none)",
  "indirect_object": "to/for whom (empty string if none)",
  "prepositional_phrases": [
    {"preposition": "about", "object": "my career"}
  ],
  "modifiers": [
    {"word": "new", "modifies": "job", "type": "adjective"}
  ],
  "clauses": [
    {"clause_type": "relative", "text": "that I was offered", "role": "object_modifier"}
  ],
  "sentence_type": "interrogative | declarative | imperative | conditional",
  "raw_parse_tree": "[S [NP ...] [VP ...]]",
  "confidence": 0.95
}

Rules:
1. "subject" is the grammatical subject — for questions like "How does X \
affect Y?", the subject is "X", not "how".
2. "verb" includes auxiliaries: "does affect", "will impact", "has been affecting".
3. "verb_tense": use "present" for simple present / present progressive, etc.
4. For WH-questions, the WH-word is NOT the subject unless it truly is \
(e.g. "Who called?" → subject is "who").
5. "direct_object": the thing being acted upon. In "How does my career \
affect my relationships?", direct_object is "my relationships".
6. "modifiers": include adjectives, adverbs, determiners, possessives \
("my", "the", "very", "new"). Type must be one of: adjective, adverb, \
determiner, possessive, quantifier.
7. "clauses": subordinate, relative, conditional, temporal, causal, or \
coordinate clauses. Role must be one of: subject_modifier, object_modifier, \
adverbial, complement, condition.
8. "raw_parse_tree": a compact bracketed constituency parse. Use standard \
labels: S, NP, VP, PP, SBAR, ADJP, ADVP, DT, NN, VB, IN, PRP, etc.
9. "confidence": 0.0–1.0 how certain you are of the parse.
10. Do NOT include markdown fences, commentary, or anything outside the JSON.
11. For fragments or single-word inputs, do your best — set confidence low.
"""


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

def parse_grammar(
    question: str,
    api_key: str,
    model: str = "google/gemini-2.0-flash-001",
) -> GrammarDiagram:
    """
    Parse the grammatical structure of *question* via LLM.

    Returns a populated ``GrammarDiagram`` on success, or a minimal
    stub with ``confidence=0.0`` on any failure.  Never raises.
    """
    # Minimal stub returned on any failure
    _fallback = GrammarDiagram(subject=question, confidence=0.0)

    if not question or not question.strip():
        return _fallback

    try:
        import openai
    except ImportError:
        return _fallback

    try:
        client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/theonionqueen13/Rosetta",
                "X-Title": "Rosetta Astrology",
            },
        )
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _GRAMMAR_SYSTEM.strip()},
                {"role": "user", "content": question},
            ],
            temperature=0.0,
            max_tokens=400,
        )
        raw = response.choices[0].message.content or ""
    except Exception:
        return _fallback

    # Strip markdown fences if the model wraps them
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    try:
        data: Dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return _fallback

    # ── Build GrammarDiagram from parsed JSON ────────────────────────
    try:
        prep_phrases = [
            PrepPhrase(
                preposition=str(pp.get("preposition", "")),
                object=str(pp.get("object", "")),
            )
            for pp in data.get("prepositional_phrases", [])
            if isinstance(pp, dict)
        ]

        modifiers = [
            Modifier(
                word=str(m.get("word", "")),
                modifies=str(m.get("modifies", "")),
                type=str(m.get("type", "")),
            )
            for m in data.get("modifiers", [])
            if isinstance(m, dict)
        ]

        clauses = [
            Clause(
                clause_type=str(c.get("clause_type", "")),
                text=str(c.get("text", "")),
                role=str(c.get("role", "")),
            )
            for c in data.get("clauses", [])
            if isinstance(c, dict)
        ]

        # Validate sentence_type
        s_type = str(data.get("sentence_type", "interrogative"))
        if s_type not in {"declarative", "interrogative", "imperative", "conditional"}:
            s_type = "interrogative"

        # Validate verb_tense
        v_tense = str(data.get("verb_tense", "present"))
        if v_tense not in {"present", "past", "future", "conditional", "imperative"}:
            v_tense = "present"

        return GrammarDiagram(
            subject=str(data.get("subject", "")).strip(),
            verb=str(data.get("verb", "")).strip(),
            verb_tense=v_tense,
            direct_object=str(data.get("direct_object", "")).strip(),
            indirect_object=str(data.get("indirect_object", "")).strip(),
            prepositional_phrases=prep_phrases,
            modifiers=modifiers,
            clauses=clauses,
            sentence_type=s_type,
            raw_parse_tree=str(data.get("raw_parse_tree", "")).strip(),
            confidence=float(data.get("confidence", 0.9)),
        )
    except Exception:
        return _fallback


# ═══════════════════════════════════════════════════════════════════════
# Display helper — for the dev inner-monologue expander
# ═══════════════════════════════════════════════════════════════════════

def format_grammar_for_display(diagram: GrammarDiagram) -> str:
    """
    Render a ``GrammarDiagram`` as a readable multi-line string
    suitable for the dev inner-monologue expander.

    Example output::

        Sentence type: interrogative
        ─────────────────────────────
        Subject  → my career
        Verb     → does affect  (present)
        D.Object → my relationships
        ─────────────────────────────
        Prep phrases:
          • about → my health
          • in    → the coming year
        Modifiers:
          • "new" modifies "job" (adjective)
        Clauses:
          • [relative] "that I was offered" → object_modifier
        ─────────────────────────────
        Parse tree:
          [S [NP my career] [VP does affect [NP my relationships]]]
        Confidence: 95%
    """
    lines: List[str] = []
    divider = "─" * 35

    lines.append(f"Sentence type: {diagram.sentence_type}")
    lines.append(divider)

    lines.append(f"Subject  → {diagram.subject or '(none)'}")
    tense_tag = f"  ({diagram.verb_tense})" if diagram.verb_tense else ""
    lines.append(f"Verb     → {diagram.verb or '(none)'}{tense_tag}")
    if diagram.direct_object:
        lines.append(f"D.Object → {diagram.direct_object}")
    if diagram.indirect_object:
        lines.append(f"I.Object → {diagram.indirect_object}")

    if diagram.prepositional_phrases or diagram.modifiers or diagram.clauses:
        lines.append(divider)

    if diagram.prepositional_phrases:
        lines.append("Prep phrases:")
        for pp in diagram.prepositional_phrases:
            lines.append(f"  • {pp.preposition} → {pp.object}")

    if diagram.modifiers:
        lines.append("Modifiers:")
        for m in diagram.modifiers:
            lines.append(f'  • "{m.word}" modifies "{m.modifies}" ({m.type})')

    if diagram.clauses:
        lines.append("Clauses:")
        for c in diagram.clauses:
            lines.append(f'  • [{c.clause_type}] "{c.text}" → {c.role}')

    if diagram.raw_parse_tree:
        lines.append(divider)
        lines.append("Parse tree:")
        lines.append(f"  {diagram.raw_parse_tree}")

    lines.append(f"Confidence: {diagram.confidence:.0%}")

    return "\n".join(lines)


def grammar_summary_line(diagram: GrammarDiagram) -> str:
    """One-line summary for the comprehension note: ``S=... V=... O=...``."""
    parts = []
    if diagram.subject:
        parts.append(f"S={diagram.subject}")
    if diagram.verb:
        parts.append(f"V={diagram.verb}")
    if diagram.direct_object:
        parts.append(f"O={diagram.direct_object}")
    if not parts:
        return ""
    return " ".join(parts)
