#!/usr/bin/env python3
"""
Rosetta DAG — Generate git_status.json from the current git diff.

Runs `git diff --name-only` and `git diff --stat` against the default branch
(or HEAD if on main) and writes data/git_status.json that the JS app consumes.

Usage:
    python rosetta_dag/update_git_status.py
"""

import json
import subprocess
import re
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parent.parent
OUTPUT = Path(__file__).resolve().parent / "data" / "git_status.json"


def run_git(*args):
    """Run a git command and return stdout."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, cwd=str(WORKSPACE),
            timeout=10,
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"  git error: {e}")
        return ""


def get_changed_files():
    """Get list of files changed relative to HEAD (unstaged + staged + untracked)."""
    changed = set()

    # Unstaged changes
    diff_unstaged = run_git("diff", "--name-only")
    if diff_unstaged:
        changed.update(diff_unstaged.splitlines())

    # Staged changes
    diff_staged = run_git("diff", "--cached", "--name-only")
    if diff_staged:
        changed.update(diff_staged.splitlines())

    # Untracked files
    untracked = run_git("ls-files", "--others", "--exclude-standard")
    if untracked:
        changed.update(untracked.splitlines())

    return sorted(changed)


def get_diff_stats():
    """Get per-file addition/deletion counts."""
    stats = {}

    # Combined staged + unstaged
    raw = run_git("diff", "HEAD", "--numstat")
    if raw:
        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                additions = int(parts[0]) if parts[0] != "-" else 0
                deletions = int(parts[1]) if parts[1] != "-" else 0
                filepath = parts[2]
                stats[filepath] = {"additions": additions, "deletions": deletions}

    return stats


def get_current_branch():
    return run_git("branch", "--show-current") or "unknown"


def get_last_commit():
    return run_git("log", "-1", "--format=%H %s")


def build_status():
    changed_files = get_changed_files()
    diff_stats = get_diff_stats()
    branch = get_current_branch()
    last_commit = get_last_commit()

    # Filter to only .py files that the DAG cares about
    py_changed = [f for f in changed_files if f.endswith(".py")]

    status = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "last_commit": last_commit,
        "changed_files": py_changed,
        "all_changed_files": changed_files,
        "stats": {f: diff_stats.get(f, {"additions": 0, "deletions": 0})
                  for f in py_changed},
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)

    print(f"✓ Wrote {OUTPUT}")
    print(f"  Branch: {branch}")
    print(f"  Changed .py files: {len(py_changed)}")
    for fp in py_changed:
        s = diff_stats.get(fp, {})
        adds = s.get("additions", "?")
        dels = s.get("deletions", "?")
        print(f"    {fp}  (+{adds} / -{dels})")


if __name__ == "__main__":
    build_status()
