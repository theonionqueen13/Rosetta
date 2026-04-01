#!/usr/bin/env python3
"""
One-time migration: convert old-format user_profiles payloads to PersonProfile format.

Old format (flat keys):
    {
        "year": 1990, "month": 3, "day": 15,
        "hour": 14, "minute": 30, "city": "...",
        "lat": ..., "lon": ...,
        "chart": { <AstrologicalChart.to_json()> },
        "circuit_names": { ... },
        "group_id": "..."
    }

New format (PersonProfile.to_dict()):
    {
        "name": "<profile_name>",
        "relationship_to_querent": "",
        "chart_id": "<profile_name>",
        "significant_places": ["<city>"],
        "locations": [{"location_name": "<city>", "connection": "born there"}],
        "chart": {
            <AstrologicalChart.to_json()>        -- includes circuit_names, group_id
        }
    }

Usage:
    python migrate_profiles_to_person_profile.py [--dry-run]

Requires SUPABASE_URL and SUPABASE_KEY (service-role key) env vars,
or the same .env / Streamlit secrets used by supabase_client.py.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# ── Bootstrap paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# ── Supabase client ──────────────────────────────────────────────────────────
from supabase_client import get_authed_supabase

TABLE = "user_profiles"


def _is_old_format(payload: dict) -> bool:
    """Return True if the payload is the old flat-key format."""
    # Old format has top-level birth-data keys; new format has "name" + nested "chart".
    return "year" in payload and "month" in payload and "name" not in payload


def _migrate_payload(profile_name: str, old: dict) -> dict:
    """Convert an old-format payload to a PersonProfile-shaped dict."""
    chart_dict = old.get("chart")
    if isinstance(chart_dict, dict):
        chart_dict = dict(chart_dict)  # shallow copy to mutate safely
        # Move circuit_names and group_id INTO the chart dict (if present at top level)
        if "circuit_names" in old and "circuit_names" not in chart_dict:
            chart_dict["circuit_names"] = old["circuit_names"]
        if "group_id" in old and "group_id" not in chart_dict:
            chart_dict["group_id"] = old["group_id"]
    else:
        chart_dict = None

    city = old.get("city", "")
    locations = []
    significant_places = []
    if city:
        significant_places = [city]
        locations = [{"location_name": city, "connection": "born there"}]

    new_payload = {
        "name": profile_name,
        "relationship_to_querent": "",
        "chart_id": profile_name,
        "significant_places": significant_places,
        "locations": locations,
    }
    if chart_dict is not None:
        new_payload["chart"] = chart_dict

    return new_payload


def run_migration(dry_run: bool = False) -> None:
    client = get_authed_supabase()

    # Fetch all rows (paginate if needed)
    print("[migration] Fetching all user_profiles rows …")
    response = (
        client.table(TABLE)
        .select("id, user_id, profile_name, payload")
        .execute()
    )
    rows = response.data or []
    print(f"[migration] Found {len(rows)} total rows.")

    migrated = 0
    skipped = 0
    errors = 0

    for row in rows:
        row_id = row["id"]
        profile_name = row["profile_name"]
        payload = row.get("payload") or {}

        if not _is_old_format(payload):
            skipped += 1
            continue

        try:
            new_payload = _migrate_payload(profile_name, payload)
        except Exception as exc:
            print(f"  [ERROR] row {row_id} ({profile_name}): {exc}")
            errors += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would migrate row {row_id} ({profile_name})")
            print(f"    old keys: {sorted(payload.keys())}")
            print(f"    new keys: {sorted(new_payload.keys())}")
            migrated += 1
            continue

        # Write back
        try:
            client.table(TABLE).update({"payload": new_payload}).eq("id", row_id).execute()
            print(f"  [OK] Migrated row {row_id} ({profile_name})")
            migrated += 1
        except Exception as exc:
            print(f"  [ERROR] row {row_id} ({profile_name}): {exc}")
            errors += 1

    print()
    print(f"[migration] Done.  migrated={migrated}  skipped={skipped}  errors={errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate user_profiles to PersonProfile format")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()
    run_migration(dry_run=args.dry_run)
