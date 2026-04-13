#!/usr/bin/env python3
"""
scripts/analyze_question.py
────────────────────────────
Design-time research tool.  Reads a file of sample questions (one per line,
# comment lines and blank lines ignored) and for each question produces:

  • A box-formatted terminal report
  • A JSON record appended to a JSONL log file

After all questions, it presents a deduplicated list of suggested new Term
entries derived from LLM gap analysis and asks which (if any) to write back
into term_registry.py and the astrological_terms Postgres table.

Usage
-----
  python scripts/analyze_question.py scripts/sample_questions.txt \\
      --api-key <OPENROUTER_KEY> \\
      [--model  google/gemini-2.0-flash-001] \\
      [--out    question_analysis_log.jsonl]

The script is purely a research / architecture-planning tool.  It never
modifies any runtime file unless the user explicitly confirms term additions
at the end.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── path so we can import from workspace root ─────────────────────────────────
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from src.mcp.topic_maps import resolve_factors, list_domains  # type: ignore
    from src.mcp.term_registry import load_terms, match_terms, Term  # type: ignore
    _INFRA_AVAILABLE = True
except ImportError as _e:
    print(f"[warn] Could not import local infrastructure ({_e}). "
          "Domain matching & term lookup will be skipped.\n")
    _INFRA_AVAILABLE = False

# ── constants ─────────────────────────────────────────────────────────────────

EXISTING_DOMAINS = [
    "Identity & Self",
    "Emotions & Inner World",
    "Relationships & Love",
    "Career & Public Life",
    "Finances & Resources",
    "Creativity & Expression",
    "Spirituality & Imagination",
    "Change & Transformation",
    "Learning & Mind",
    "Devotion & Purposeful Service",
    "Community & Future",
    "Conflict & Enemies",
]

EXISTING_INTENTS = [
    "potency_ranking",
]

TEMPORAL_KEYWORDS: dict[str, list[str]] = {
    "transit":        ["transit", "transiting", "right now", "currently", "lately",
                       "these days", "at this time", "this week", "this month",
                       "this year", "passing through", "retrograde"],
    "synastry":       ["synastry", "compatibility", "partner", "spouse", "our chart",
                       "we have", "between us", "her chart", "his chart", "their chart"],
    "solar_return":   ["solar return", "birthday chart", "this year"],
    "relocation":     ["relocation", "moving to", "astrocartography", "new city",
                       "relocate", "astromap"],
    "cycle":          ["saturn return", "planetary cycle", "progressed", "progression",
                       "life cycle", "nodal return", "chiron return"],
    "timing_predict": ["when will", "when does", "how soon", "what year",
                       "waiting room", "energy shift", "coming up"],
}

_FORM_PATTERNS: list[tuple[str, str]] = [
    # (pattern, label)
    (r"^\s*(is|are|does|do|did|was|were|will|would|could|should|has|have|can)\b",
     "polar"),
    (r"\bor\b.{5,}\?",                    "comparative"),
    (r"^\s*why\b",                         "why-diagnostic"),
    (r"\bwhen\b|\bhow soon\b|\bwhat year\b|\bwhat month\b",
     "temporal-when"),
    (r"^\s*(what|which).{0,40}\b(most|least|best|worst|strongest|weakest|highest|lowest|primary|main)\b",
     "ranking"),
    (r"^\s*how (can|do|should|might|would) (i|we|one)\b",
     "advisory-how"),
    (r"^\s*(what|which)\b",               "wh-what"),
    (r"^\s*(who|where|why|how)\b",        "wh-other"),
]

W = 68  # terminal report width
_HEAVY = "=" * W
_LIGHT = "-" * W


# ── helpers ───────────────────────────────────────────────────────────────────

def _wrap(text: str, indent: int = 16) -> str:
    """Wrap text to W chars with a hanging indent."""
    prefix = " " * indent
    lines = textwrap.wrap(text, width=W - indent)
    if not lines:
        return ""
    return lines[0] + ("\n" + prefix + ("\n" + prefix).join(lines[1:])
                       if len(lines) > 1 else "")


def _box_line(label: str, value: str, label_width: int = 14) -> str:
    label_str = f"{label:<{label_width}}"
    return f"{label_str}  {_wrap(value, label_width + 2)}"


# ── deterministic analysis ────────────────────────────────────────────────────

def _classify_form(q: str) -> str:
    ql = q.lower().strip()
    for pattern, label in _FORM_PATTERNS:
        if re.search(pattern, ql, re.IGNORECASE):
            return label
    return "wh-open"


def _detect_temporal(q: str) -> list[str]:
    ql = q.lower()
    hits: list[str] = []
    for dim, kws in TEMPORAL_KEYWORDS.items():
        if any(kw in ql for kw in kws):
            hits.append(dim)
    return hits if hits else ["natal"]


def _detect_subject(q: str) -> str:
    ql = q.lower()
    dyadic_kws = ["my partner", "my spouse", "our synastry", "our chart",
                  "between us", " we ", " our ", " us ", "her chart", "his chart",
                  "their chart", "with my"]
    familial_kws = ["my parent", "my mother", "my father", "my child",
                    "my sibling", "my family", "my ex"]
    if any(k in ql for k in dyadic_kws):
        return "dyadic"
    if any(k in ql for k in familial_kws):
        return "familial"
    return "single"


def _match_domain_baseline(q: str) -> dict[str, Any]:
    """Call resolve_factors() from topic_maps and return a concise summary."""
    if not _INFRA_AVAILABLE:
        return {"domain": "(unavailable)", "subtopic": "", "confidence": 0.0,
                "matched_keywords": []}
    try:
        tm = resolve_factors(q)
        return {
            "domain":            tm.domain,
            "subtopic":          tm.subtopic,
            "confidence":        round(tm.confidence, 3),
            "matched_keywords":  tm.matched_keywords,
        }
    except Exception as exc:
        return {"domain": f"(error: {exc})", "subtopic": "", "confidence": 0.0,
                "matched_keywords": []}


def _match_term_baseline(q: str) -> Optional[dict[str, Any]]:
    """Run match_terms() and return Term info or None."""
    if not _INFRA_AVAILABLE:
        return None
    try:
        terms = load_terms()
        match = match_terms(q, terms)
        if match:
            return {
                "canonical":   match.canonical,
                "intent":      match.intent,
                "domain":      match.domain,
                "description": match.description,
            }
    except Exception:
        pass
    return None


def _deterministic(q: str) -> dict[str, Any]:
    """Run all deterministic checks and return a combined baseline dict."""
    domain_info = _match_domain_baseline(q)
    term_info   = _match_term_baseline(q)
    return {
        "question_form":    _classify_form(q),
        "temporal":         _detect_temporal(q),
        "subject_config":   _detect_subject(q),
        "domain_baseline":  domain_info,
        "term_match":       term_info,
    }


# ── LLM meta-analysis ─────────────────────────────────────────────────────────

_ANALYSIS_SYSTEM = """\
You are a COMPREHENSION ARCHITECTURE ANALYST for an astrology chatbot.

Your job is to analyze the STRUCTURE of user questions — not to answer them
astrologically. You are helping a developer design the comprehension layer.

You will be given:
 • A user question
 • A deterministic baseline analysis (form, domain guess, temporal context,
   subject config, term registry match or none)
 • EXISTING_DOMAINS — the 12 life-area domains the system knows about
 • EXISTING_INTENTS — routing intents already implemented

Analyze the question across ALL of the following dimensions and return ONLY
a single valid JSON object.  No preamble, no markdown, no explanation outside
the JSON.

JSON schema (all fields required):
{
  "paraphrase":          <string: restate the question in one plain sentence, no astrology jargon>,
  "question_form":       <string: one of polar | comparative | why-diagnostic | temporal-when |
                          ranking | advisory-how | wh-what | wh-other | wh-open | compound>,
  "temporal_dimension":  <array of strings from:
                          natal | transit | synastry | solar_return | relocation | cycle |
                          timing_prediction>,
  "subject_config":      <string: single | dyadic | familial>,
  "domain_primary":      <string: one domain from EXISTING_DOMAINS>,
  "domain_secondary":    <array of strings from EXISTING_DOMAINS, may be empty>,
  "subtopic":            <string: best-fit subtopic label, free text>,
  "intent_suggested":    <string: snake_case label for the routing intent this question requires
                          — use an existing one from EXISTING_INTENTS if it truly fits, else propose a new one>,
  "intent_is_new":       <boolean>,
  "intent_description":  <string: one sentence — what should the engine DO differently
                          when this intent is detected?>,
  "term_gaps":           <array of objects — vocabulary this question uses that the registry LACKS.
                          Only include genuinely missing terms, not already present ones.
                          Each gap object has exactly:
                            canonical    : string
                            aliases      : array of strings (regex-safe patterns)
                            factors      : array of valid planet/house/sign names, may be empty
                            intent       : string (intent_suggested value or existing intent)
                            domain       : string (from EXISTING_DOMAINS)
                            description  : string (one sentence)
                          >,
  "answer_architecture": <string: what facts from the reading packet are needed, what shape the
                          response should take, what chart data is required (natal only? needs chart_b?)>,
  "comprehension_notes": <string: what the CURRENT system (keyword domain routing + term registry)
                          would get right vs. wrong for this question. Be specific.>
}

Strict rules:
 1. question_form should reflect the actual grammatical form, overriding the deterministic
    baseline if it is more accurate.
 2. intent_suggested must be snake_case.  If the deterministic baseline already matched a term
    with a valid intent, use that intent (set intent_is_new to false).
 3. term_gaps should be EMPTY if the term registry already has a perfect match.
 4. factors in term_gaps must be valid astrological objects
    (planet names, "Nth house" e.g. "7th house", sign names, or node names).
    Use empty array if the concept is structural (e.g. "most active planet").
 5. Do not invent domain names.  Only use strings from EXISTING_DOMAINS.
 6. answer_architecture should mention: natal vs. transit data, single vs. biwheel,
    and what ReadingPacket fact types are most relevant
    (placements, aspects, dignities, power_nodes, houses, circuit_flows, etc.).
"""


def _llm_analyze(
    question: str,
    baseline: dict[str, Any],
    api_key: str,
    model: str = "google/gemini-2.0-flash-001",
) -> Optional[dict[str, Any]]:
    """Call OpenRouter to get structured meta-analysis of a question."""
    try:
        import httpx  # type: ignore
    except ImportError:
        print("[warn] httpx not installed -- LLM analysis unavailable.")
        return None

    # Build the user message
    existing_terms_canonical: list[str] = []
    if _INFRA_AVAILABLE:
        try:
            existing_terms_canonical = [t.canonical for t in load_terms()]
        except Exception:
            pass

    user_msg = f"""\
QUESTION: {question}

DETERMINISTIC BASELINE:
{json.dumps(baseline, indent=2)}

EXISTING_DOMAINS:
{json.dumps(EXISTING_DOMAINS, indent=2)}

EXISTING_INTENTS:
{json.dumps(EXISTING_INTENTS, indent=2)}

EXISTING_TERMS (canonical values already in registry):
{json.dumps(existing_terms_canonical, indent=2)}

Now produce your JSON analysis.
"""

    payload = {
        "model": model,
        "temperature": 0.0,
        "max_tokens": 700,
        "messages": [
            {"role": "system",  "content": _ANALYSIS_SYSTEM},
            {"role": "user",    "content": user_msg},
        ],
    }

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization":  f"Bearer {api_key}",
                "Content-Type":   "application/json",
                "HTTP-Referer":   "https://github.com/theonionqueen13/Rosetta",
                "X-Title":        "Rosetta Question Analyzer",
            },
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip()

        # strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$",       "", raw)

        return json.loads(raw)

    except Exception as exc:
        print(f"  [LLM error] {exc}")
        return None


# ── terminal report ───────────────────────────────────────────────────────────

def _render_report(
    idx: int,
    total: int,
    question: str,
    det: dict[str, Any],
    llm: Optional[dict[str, Any]],
) -> None:
    dom  = det["domain_baseline"]
    term = det["term_match"]

    print()
    print(_HEAVY)
    q_label = f"Q{idx} of {total}"
    print(f"  {q_label}")
    print(_LIGHT)
    # wrap question text
    qlines = textwrap.wrap('"' + question + '"', width=W - 4)
    for ql in qlines:
        print(f"  {ql}")
    print(_LIGHT)

    if llm:
        _p = llm.get("paraphrase", "")
        if _p:
            plines = textwrap.wrap(_p, width=W - 18)
            print(f"{'UNDERSTOOD AS':<14}  {plines[0]}")
            for pl in plines[1:]:
                print(f"{'':<16}{pl}")
        print()
        form          = llm.get("question_form", det["question_form"])
        temporal      = llm.get("temporal_dimension", det["temporal"])
        subj          = llm.get("subject_config", det["subject_config"])
        dom_primary   = llm.get("domain_primary", dom["domain"])
        dom_secondary = llm.get("domain_secondary", [])
        subtopic      = llm.get("subtopic", dom.get("subtopic", ""))
        intent        = llm.get("intent_suggested", "")
        intent_new    = llm.get("intent_is_new", True)
        intent_desc   = llm.get("intent_description", "")
        gaps          = llm.get("term_gaps", [])
        arch          = llm.get("answer_architecture", "")
        notes         = llm.get("comprehension_notes", "")
    else:
        print("  [LLM unavailable -- deterministic only]\n")
        form          = det["question_form"]
        temporal      = det["temporal"]
        subj          = det["subject_config"]
        dom_primary   = dom["domain"]
        dom_secondary = []
        subtopic      = dom.get("subtopic", "")
        intent        = (term["intent"] if term else "")
        intent_new    = not bool(term)
        intent_desc   = ""
        gaps          = []
        arch          = ""
        notes         = ""

    print(_box_line("FORM",     form))
    print(_box_line("TEMPORAL", ", ".join(temporal) if isinstance(temporal, list) else temporal))
    print(_box_line("SUBJECT",  subj))

    dom_str = f"{dom_primary}"
    if subtopic:
        dom_str += f"  ->  {subtopic}"
    conf = dom.get("confidence", 0)
    dom_str += f"  [{conf:.0%}]"
    print(_box_line("DOMAIN", dom_str))
    for sd in dom_secondary:
        print(_box_line("",     f"{sd}  [secondary]"))

    if term:
        print(_box_line("TERM MATCH", f'"{term["canonical"]}"  ->  {term["intent"]}'))
    else:
        print(_box_line("TERM MATCH", "(none in registry)"))

    kws = dom.get("matched_keywords", [])
    if kws:
        print(_box_line("KW HITS", ", ".join(kws[:8])))

    print()
    new_flag = "  [NEW]" if intent_new else "  [existing]"
    print(_box_line("INTENT", f"{intent or '(none)'}{new_flag}"))
    if intent_desc:
        idlines = textwrap.wrap(intent_desc, width=W - 18)
        print(f"{'':14}  {idlines[0]}")
        for il in idlines[1:]:
            print(f"{'':16}{il}")

    if gaps:
        print()
        print("  TERM GAPS:")
        for g in gaps:
            print(f"    * canonical : {g.get('canonical', '?')}")
            als = g.get("aliases", [])
            if als:
                print(f"      aliases   : {', '.join(als[:4])}")
            fct = g.get("factors", [])
            if fct:
                print(f"      factors   : {', '.join(fct[:6])}")
            print(f"      intent    : {g.get('intent', '?')}")
            gdom = g.get("domain", "")
            if gdom:
                print(f"      domain    : {gdom}")
            print(f"      desc      : {g.get('description', '')[:80]}")
    else:
        print()
        print("  TERM GAPS: (none)")

    if arch:
        print()
        print("  ANSWER ARCHITECTURE:")
        for line in textwrap.wrap(arch, width=W - 4):
            print(f"    {line}")

    if notes:
        print()
        print("  COMPREHENSION NOTES:")
        for line in textwrap.wrap(notes, width=W - 4):
            print(f"    {line}")

    print(_HEAVY)


# ── JSONL logging ─────────────────────────────────────────────────────────────

def _append_log(record: dict[str, Any], path: Path) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ── post-batch term confirmation ──────────────────────────────────────────────

def _confirm_terms(all_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate, present to user, return the confirmed subset."""
    seen: dict[str, dict[str, Any]] = {}
    for g in all_gaps:
        canon = g.get("canonical", "").strip().lower()
        if canon and canon not in seen:
            seen[canon] = g

    deduped = list(seen.values())
    if not deduped:
        print("\n[No new term gaps collected across all questions.]\n")
        return []

    print()
    print(_HEAVY)
    print("  PROPOSED NEW TERMS  (collected across all questions)")
    print(_HEAVY)
    for i, g in enumerate(deduped, 1):
        print(f"\n  [{i}]  canonical : {g.get('canonical')}")
        als = g.get("aliases", [])
        if als:
            print(f"       aliases   : {', '.join(als[:5])}")
        fct = g.get("factors", [])
        if fct:
            print(f"       factors   : {', '.join(fct)}")
        print(f"       intent    : {g.get('intent')}")
        print(f"       domain    : {g.get('domain')}")
        print(f"       desc      : {g.get('description', '')[:100]}")

    print()
    raw = input(
        "  Add to registry? Enter numbers (comma-separated), 'all', or 'none' [none]: "
    ).strip().lower()

    if not raw or raw == "none":
        return []
    if raw == "all":
        confirmed = deduped
    else:
        indices: list[int] = []
        for token in raw.split(","):
            try:
                indices.append(int(token.strip()) - 1)
            except ValueError:
                pass
        confirmed = [deduped[i] for i in indices if 0 <= i < len(deduped)]

    return confirmed


# ── write confirmed terms back to registry + DB ───────────────────────────────

def _write_terms_to_registry(confirmed: list[dict[str, Any]]) -> None:
    """
    Append confirmed Term entries to _BUILTIN_TERMS in term_registry.py and
    insert corresponding rows into the astrological_terms Postgres table.
    """
    if not confirmed:
        return

    registry_path = _ROOT / "src" / "mcp" / "term_registry.py"

    # ── 1. Write to term_registry.py ──────────────────────────────────────
    src = registry_path.read_text(encoding="utf-8")
    anchor = "# ── END BUILTIN TERMS"
    if anchor not in src:
        print(f"  [warn] Could not find anchor '{anchor}' in term_registry.py --"
              "skipping file write.  Add terms manually.")
    else:
        new_entries = ""
        for g in confirmed:
            canon   = g.get("canonical", "")
            aliases = g.get("aliases", [])
            factors = g.get("factors", [])
            intent  = g.get("intent", "potency_ranking")
            domain  = g.get("domain", "")
            desc    = g.get("description", "")
            alias_py  = repr(aliases)
            factors_py = repr(factors)
            new_entries += (
                f'    Term(\n'
                f'        canonical="{canon}",\n'
                f'        aliases={alias_py},\n'
                f'        factors={factors_py},\n'
                f'        intent="{intent}",\n'
                f'        domain="{domain}",\n'
                f'        description="{desc}",\n'
                f'    ),\n'
            )
        src = src.replace(anchor, new_entries + anchor)
        registry_path.write_text(src, encoding="utf-8")
        print(f"  OK: {len(confirmed)} term(s) appended to term_registry.py")

    # ── 2. Write to Postgres ───────────────────────────────────────────────
    if not _INFRA_AVAILABLE:
        print("  [skip] DB write -- infrastructure not available.")
        return

    try:
        from src.db.db_access import get_connection  # type: ignore
        conn = get_connection()
        cur  = conn.cursor()
        sql  = """
            INSERT INTO astrological_terms
                (canonical, aliases, factors, intent, domain, description)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (canonical) DO NOTHING
        """
        rows: list[tuple] = []
        for g in confirmed:
            rows.append((
                g.get("canonical", ""),
                g.get("aliases", []),
                g.get("factors", []),
                g.get("intent", ""),
                g.get("domain", ""),
                g.get("description", ""),
            ))
        cur.executemany(sql, rows)
        conn.commit()
        cur.close()
        conn.close()
        print(f"  OK: {len(confirmed)} term(s) inserted into astrological_terms table.")
    except Exception as exc:
        print(f"  [warn] DB write failed: {exc}")


# ── question loader ───────────────────────────────────────────────────────────

def _load_questions(path: Path) -> list[str]:
    questions: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        questions.append(line)
    return questions


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze sample astrology questions to guide comprehension layer design.",
    )
    parser.add_argument("questions_file",
                        help="Path to a text file with one question per line.")
    parser.add_argument("--api-key", default=os.environ.get("OPENROUTER_API_KEY", ""),
                        help="OpenRouter API key (or set OPENROUTER_API_KEY env var).")
    parser.add_argument("--model",   default="google/gemini-2.0-flash-001",
                        help="OpenRouter model name.")
    parser.add_argument("--out",     default="question_analysis_log.jsonl",
                        help="Output JSONL log path (appended to if existing).")
    parser.add_argument("--start",   type=int, default=1,
                        help="Start at question N (1-indexed, for resuming).")
    args = parser.parse_args()

    questions_path = Path(args.questions_file)
    if not questions_path.exists():
        sys.exit(f"Error: questions file not found: {questions_path}")

    questions = _load_questions(questions_path)
    if not questions:
        sys.exit("Error: no questions found in file (check for blank lines / # comments).")

    log_path = Path(args.out)
    api_key  = args.api_key
    model    = args.model
    start    = max(1, args.start)

    total    = len(questions)
    print(f"\nRosetta Question Analyzer  --  {total} questions loaded from {questions_path.name}")
    if api_key:
        print(f"LLM: {model}")
    else:
        print("LLM: disabled (no --api-key; deterministic analysis only)")
    print(f"Log: {log_path}")
    print()

    all_gaps:        list[dict[str, Any]] = []
    all_new_intents: list[str]            = []
    llm_failures     = 0

    for idx, question in enumerate(questions, 1):
        if idx < start:
            continue

        print(f"  Analyzing {idx}/{total}...", end=" ", flush=True)

        det = _deterministic(question)

        llm: Optional[dict[str, Any]] = None
        if api_key:
            llm = _llm_analyze(question, det, api_key, model)
            if llm is None:
                llm_failures += 1
        print("done")

        _render_report(idx, total, question, det, llm)

        # collect gaps & new intents
        if llm:
            for gap in llm.get("term_gaps", []):
                all_gaps.append(gap)
            intent     = llm.get("intent_suggested", "")
            intent_new = llm.get("intent_is_new", False)
            if intent and intent_new and intent not in all_new_intents:
                all_new_intents.append(intent)

        # JSONL record
        record: dict[str, Any] = {
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "question_idx": idx,
            "question":     question,
            "deterministic": det,
            "llm":          llm,
        }
        _append_log(record, log_path)

    # ── post-batch summary ────────────────────────────────────────────────
    print()
    print(_HEAVY)
    print("  BATCH SUMMARY")
    print(_HEAVY)
    print(f"  Questions analyzed : {total - (start - 1)}")
    print(f"  LLM calls failed   : {llm_failures}")
    print(f"  New intents found  : {len(all_new_intents)}")
    if all_new_intents:
        for ni in all_new_intents:
            print(f"    *  {ni}")
    print(f"  Term gaps found    : {len(all_gaps)}")
    print(f"  Log appended to    : {log_path}")
    print()

    # ── term confirmation ─────────────────────────────────────────────────
    if api_key and all_gaps:
        confirmed = _confirm_terms(all_gaps)
        if confirmed:
            print(f"\n  Writing {len(confirmed)} confirmed term(s)...")
            _write_terms_to_registry(confirmed)
        else:
            print("  No terms written.")
    elif not api_key:
        print("  (Run with --api-key to enable term gap collection and registry updates.)")

    print()


if __name__ == "__main__":
    main()
