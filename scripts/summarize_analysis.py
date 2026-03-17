#!/usr/bin/env python3
"""
scripts/summarize_analysis.py
──────────────────────────────
Reads question_analysis_log.jsonl (produced by analyze_question.py) and
distils it into a structured action report covering:

  1. New intents identified  — what routing paths need to be built
  2. Term gaps               — vocabulary missing from the registry
  3. Domain routing accuracy — where keyword matching agrees / diverges from LLM
  4. Dimension distributions — temporal, subject config, question form
  5. Answer architecture patterns — grouped by intent
  6. Priority action list    — ordered by frequency / impact

Usage
-----
  python scripts/summarize_analysis.py [question_analysis_log.jsonl]
  python scripts/summarize_analysis.py --out findings.txt   # also write to file
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

W = 72


# ── formatting ────────────────────────────────────────────────────────────────

def _h1(title: str) -> str:
    return f"\n{'=' * W}\n  {title}\n{'=' * W}"

def _h2(title: str) -> str:
    return f"\n  -- {title} {'--' * max(0, (W - len(title) - 7) // 2)}"

def _row(label: str, value: str, w: int = 28) -> str:
    return f"  {label:<{w}} {value}"

def _bar(n: int, total: int, width: int = 20) -> str:
    filled = round(width * n / total) if total else 0
    return f"[{'#' * filled}{' ' * (width - filled)}] {n:>2} ({100*n/total:.0f}%)" if total else f"[{' '*width}] 0"


# ── load & deduplicate ────────────────────────────────────────────────────────

def _load(path: Path) -> list[dict[str, Any]]:
    """
    Load JSONL records.  When the same question_idx appears more than once
    (script was run multiple times), keep the LAST record that has LLM data.
    If no LLM record exists for an index, keep the deterministic one.
    """
    raw: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    # deduplicate: latest llm-enriched record wins per question_idx
    by_idx: dict[int, dict[str, Any]] = {}
    for r in raw:
        idx = r.get("question_idx", -1)
        existing = by_idx.get(idx)
        if existing is None:
            by_idx[idx] = r
        elif r.get("llm") and not existing.get("llm"):
            by_idx[idx] = r
        elif r.get("llm") and existing.get("llm"):
            # both have llm — keep latest timestamp
            if r.get("timestamp", "") >= existing.get("timestamp", ""):
                by_idx[idx] = r

    return [by_idx[k] for k in sorted(by_idx)]


# ── extraction helpers ────────────────────────────────────────────────────────

def _llm(r: dict) -> Optional[dict]:
    return r.get("llm") or None

def _det(r: dict) -> dict:
    return r.get("deterministic") or {}


# ── section builders ──────────────────────────────────────────────────────────

def _section_intents(records: list[dict], out: list[str]) -> dict[str, list[dict]]:
    """Deduplicate new intents; return intent -> list of records."""
    intent_records: dict[str, list[dict]] = defaultdict(list)
    intent_desc:    dict[str, str]        = {}

    for r in records:
        l = _llm(r)
        if not l:
            continue
        intent = l.get("intent_suggested", "").strip()
        if not intent:
            continue
        intent_records[intent].append(r)
        if intent not in intent_desc:
            intent_desc[intent] = l.get("intent_description", "")

    # sort by frequency descending
    sorted_intents = sorted(intent_records.items(), key=lambda x: -len(x[1]))
    new_intents    = [(i, rs) for i, rs in sorted_intents if any(_llm(r) and _llm(r).get("intent_is_new") for r in rs)]
    exist_intents  = [(i, rs) for i, rs in sorted_intents if not any(_llm(r) and _llm(r).get("intent_is_new") for r in rs)]

    out.append(_h1("1. INTENTS IDENTIFIED"))
    out.append(f"\n  {len(new_intents)} NEW  +  {len(exist_intents)} EXISTING\n")

    if new_intents:
        out.append("  NEW INTENTS (need engine branches):")
        for intent, rs in new_intents:
            desc = intent_desc.get(intent, "")
            q_nums = ", ".join(str(r["question_idx"]) for r in rs)
            out.append(f"\n    [{len(rs):>2}x]  {intent}")
            out.append(f"           Q#: {q_nums}")
            if desc:
                # word-wrap desc
                import textwrap
                for ln in textwrap.wrap(desc, width=W - 12):
                    out.append(f"           {ln}")
    if exist_intents:
        out.append("\n  EXISTING INTENTS (already implemented):")
        for intent, rs in exist_intents:
            q_nums = ", ".join(str(r["question_idx"]) for r in rs)
            out.append(f"    [{len(rs):>2}x]  {intent}  (Q#{q_nums})")

    return dict(intent_records)


def _section_term_gaps(records: list[dict], out: list[str]) -> None:
    seen: dict[str, dict] = {}
    sources: dict[str, list[int]] = defaultdict(list)

    for r in records:
        l = _llm(r)
        if not l:
            continue
        for gap in l.get("term_gaps", []):
            canon = gap.get("canonical", "").strip().lower()
            if not canon:
                continue
            if canon not in seen:
                seen[canon] = gap
            sources[canon].append(r["question_idx"])

    out.append(_h1("2. TERM GAPS  (vocabulary missing from registry)"))
    if not seen:
        out.append("\n  (none — all questions matched existing terms or need structural intents)\n")
        return

    out.append(f"\n  {len(seen)} unique terms missing:\n")
    for canon, gap in sorted(seen.items(), key=lambda x: -len(sources[x[0]])):
        q_nums = ", ".join(str(i) for i in sources[canon])
        out.append(f"  [{len(sources[canon]):>2}x]  canonical : {gap.get('canonical')}")
        out.append(f"        Q#        : {q_nums}")
        als = gap.get("aliases", [])
        if als:
            out.append(f"        aliases   : {', '.join(als[:5])}")
        fct = gap.get("factors", [])
        if fct:
            out.append(f"        factors   : {', '.join(fct)}")
        out.append(f"        intent    : {gap.get('intent', '?')}")
        out.append(f"        domain    : {gap.get('domain', '?')}")
        d = gap.get("description", "")
        if d:
            out.append(f"        desc      : {d[:90]}")
        out.append("")


def _section_domain_accuracy(records: list[dict], out: list[str]) -> None:
    agree = 0
    disagree_list: list[tuple[int, str, str, str]] = []  # (idx, q, det_dom, llm_dom)

    for r in records:
        l = _llm(r)
        d = _det(r)
        if not l:
            continue
        det_dom = d.get("domain_baseline", {}).get("domain", "")
        llm_dom = l.get("domain_primary", "")
        if not det_dom or not llm_dom:
            continue
        if det_dom.lower() == llm_dom.lower():
            agree += 1
        else:
            disagree_list.append((r["question_idx"], r["question"][:55], det_dom, llm_dom))

    total = agree + len(disagree_list)
    out.append(_h1("3. DOMAIN ROUTING ACCURACY  (keyword vs. LLM)"))
    out.append(f"\n  Agreement: {agree}/{total} ({100*agree//total if total else 0}%)\n")

    if disagree_list:
        out.append("  MISMATCHES  (where keyword matching got the wrong domain):")
        for idx, q, det_dom, llm_dom in disagree_list:
            out.append(f"\n  Q{idx:>2}  \"{q}...\"")
            out.append(f"       keyword -> {det_dom}")
            out.append(f"       LLM     -> {llm_dom}  <<< correct")
    else:
        out.append("  All domain routing matched LLM assessment.\n")


def _section_distributions(records: list[dict], out: list[str]) -> None:
    llm_records = [r for r in records if _llm(r)]
    N = len(llm_records)
    if not N:
        return

    form_c:     Counter = Counter()
    temporal_c: Counter = Counter()
    subject_c:  Counter = Counter()
    domain_c:   Counter = Counter()

    for r in llm_records:
        l = _llm(r)
        form_c[l.get("question_form", "?")] += 1
        for t in (l.get("temporal_dimension") or []):
            temporal_c[t] += 1
        subject_c[l.get("subject_config", "?")] += 1
        domain_c[l.get("domain_primary", "?")] += 1

    out.append(_h1("4. DIMENSION DISTRIBUTIONS"))

    out.append(_h2("Question Form"))
    for form, n in form_c.most_common():
        out.append(f"  {_bar(n, N)}  {form}")

    out.append(_h2("Temporal Dimension"))
    for t, n in temporal_c.most_common():
        out.append(f"  {_bar(n, N)}  {t}")

    out.append(_h2("Subject Config"))
    for s, n in subject_c.most_common():
        out.append(f"  {_bar(n, N)}  {s}")

    out.append(_h2("Primary Domain"))
    for dom, n in domain_c.most_common():
        out.append(f"  {_bar(n, N)}  {dom}")


def _section_architecture(records: list[dict], intent_map: dict[str, list[dict]], out: list[str]) -> None:
    out.append(_h1("5. ANSWER ARCHITECTURE  (grouped by intent)"))

    for intent, rs in sorted(intent_map.items(), key=lambda x: -len(x[1])):
        out.append(f"\n  {intent}  ({len(rs)} question{'s' if len(rs)>1 else ''})")
        out.append(f"  {'- '*34}")
        for r in rs:
            l = _llm(r)
            if not l:
                continue
            arch = l.get("answer_architecture", "")
            if arch:
                import textwrap
                q_short = r["question"][:60]
                out.append(f"    Q{r['question_idx']:>2}: \"{q_short}\"")
                for ln in textwrap.wrap(arch, width=W - 10):
                    out.append(f"          {ln}")
                notes = l.get("comprehension_notes", "")
                if notes:
                    out.append(f"      [!] Current system:")
                    for ln in textwrap.wrap(notes, width=W - 14):
                        out.append(f"          {ln}")
                out.append("")


def _section_priority(records: list[dict], intent_map: dict[str, list[dict]], out: list[str]) -> None:
    out.append(_h1("6. PRIORITY ACTION LIST"))
    out.append("")

    # Intents sorted by frequency
    new_intents = [
        (i, rs) for i, rs in sorted(intent_map.items(), key=lambda x: -len(x[1]))
        if any(_llm(r) and _llm(r).get("intent_is_new") for r in rs)
    ]

    # Domain mismatches
    bad_domains: list[tuple[str, str]] = []
    for r in records:
        l = _llm(r)
        d = _det(r)
        if not l:
            continue
        det_dom = d.get("domain_baseline", {}).get("domain", "")
        llm_dom = l.get("domain_primary", "")
        if det_dom and llm_dom and det_dom.lower() != llm_dom.lower():
            bad_domains.append((det_dom, llm_dom))

    # term gaps
    gap_count: Counter = Counter()
    for r in records:
        l = _llm(r)
        if not l:
            continue
        for gap in l.get("term_gaps", []):
            canon = gap.get("canonical", "").strip().lower()
            if canon:
                gap_count[canon] += 1

    out.append("  ENGINE BRANCHES  (implement these intents in reading_engine.py)")
    for rank, (intent, rs) in enumerate(new_intents, 1):
        needs_biwheel = any(
            "biwheel" in ((_llm(r) or {}).get("answer_architecture", "")).lower() or
            "chart_b"  in ((_llm(r) or {}).get("answer_architecture", "")).lower() or
            "synastry" in ((_llm(r) or {}).get("temporal_dimension") or [])
            for r in rs
        )
        flag = " [needs chart_b]" if needs_biwheel else ""
        out.append(f"  {rank:>2}. {intent}{flag}  ({len(rs)}x)")

    out.append("")
    out.append("  TERM REGISTRY  (add to term_registry.py + astrological_terms table)")
    if gap_count:
        for rank, (canon, n) in enumerate(gap_count.most_common(), 1):
            out.append(f"  {rank:>2}. \"{canon}\"  ({n}x)")
    else:
        out.append("      (none — re-run analyze_question.py with --api-key to populate)")

    if bad_domains:
        out.append("")
        out.append("  KEYWORD ROUTING FIXES  (subtopic/keyword additions in topic_maps.py)")
        seen_pairs: set[tuple[str,str]] = set()
        rank = 1
        for det_dom, llm_dom in bad_domains:
            pair = (det_dom, llm_dom)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                out.append(f"  {rank:>2}. keyword matched \"{det_dom}\"  but should be \"{llm_dom}\"")
                rank += 1

    # synastry / biwheel note
    synastry_qs = [r for r in records if _llm(r) and "synastry" in (_llm(r).get("temporal_dimension") or [])]
    if synastry_qs:
        out.append("")
        out.append(f"  BIWHEEL SUPPORT  ({len(synastry_qs)} questions require chart_b / synastry loading)")
        out.append("      reading_engine.py needs a subject_config=dyadic branch that")
        out.append("      requests chart_b before building the reading packet.")

    out.append("")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize question_analysis_log.jsonl into an action report."
    )
    parser.add_argument("log", nargs="?", default="question_analysis_log.jsonl",
                        help="Path to the JSONL log file.")
    parser.add_argument("--out", default="",
                        help="Also write the report to this file.")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        sys.exit(f"Error: log file not found: {log_path}")

    records  = _load(log_path)
    llm_n    = sum(1 for r in records if _llm(r))
    det_only = len(records) - llm_n

    lines: list[str] = []
    lines.append(f"\nRosetta Question Analysis Summary")
    lines.append(f"  Log      : {log_path}  ({len(records)} unique questions)")
    lines.append(f"  LLM data : {llm_n} questions  |  deterministic-only: {det_only}")
    if det_only and not llm_n:
        lines.append("\n  [!] No LLM data found.  Re-run analyze_question.py with --api-key.")
        print("\n".join(lines))
        return

    intent_map = _section_intents(records, lines)
    _section_term_gaps(records, lines)
    _section_domain_accuracy(records, lines)
    _section_distributions(records, lines)
    _section_architecture(records, intent_map, lines)
    _section_priority(records, intent_map, lines)

    report = "\n".join(lines)
    print(report)

    if args.out:
        out_path = Path(args.out)
        out_path.write_text(report, encoding="utf-8")
        print(f"\n  Report written to {out_path}")


if __name__ == "__main__":
    main()
