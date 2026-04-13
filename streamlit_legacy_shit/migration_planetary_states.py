"""
migration_planetary_states.py — Future Persistence for Planetary Strength Data
================================================================================

SQL schema + Python helpers for persisting per-chart planetary state scores
to a Supabase (PostgreSQL) database.

STATUS: DORMANT — This script is ready to run once Supabase is re-connected
and user logins are wired back in. Until then, planetary states are computed
in real time by dignity_calc.score_and_attach() and live only in session memory.

Tables created:
  - user_planetary_states: Per-chart, per-planet strength scores
  - user_mutual_receptions: Per-chart mutual reception pairs

Both are keyed to (user_id, profile_id) so they are private to the user.
"""

import json
from typing import Dict, List, Optional

# ═══════════════════════════════════════════════════════════════════════
# SQL Schema
# ═══════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- Planetary strength states (per-chart, per-planet)
-- Keyed to user + profile so scores are private to the user's saved chart.
CREATE TABLE IF NOT EXISTS user_planetary_states (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL,
    profile_id      UUID NOT NULL,
    planet_name     TEXT NOT NULL,

    -- Vector A: Essential Dignity (Authority)
    raw_authority       REAL DEFAULT 0,
    quality_index       REAL DEFAULT 0,
    primary_dignity     TEXT,           -- 'domicile', 'exaltation', ..., 'peregrine', or NULL
    dignity_domicile    BOOLEAN DEFAULT FALSE,
    dignity_exaltation  BOOLEAN DEFAULT FALSE,
    dignity_triplicity  BOOLEAN DEFAULT FALSE,
    dignity_term        BOOLEAN DEFAULT FALSE,
    dignity_face        BOOLEAN DEFAULT FALSE,
    dignity_detriment   BOOLEAN DEFAULT FALSE,
    dignity_fall        BOOLEAN DEFAULT FALSE,
    dignity_peregrine   BOOLEAN DEFAULT FALSE,

    -- Vector B: Accidental Dignity (Potency)
    house_score             REAL DEFAULT 0,
    motion_score            REAL DEFAULT 0,
    motion_label            TEXT DEFAULT '',
    solar_proximity_score   REAL DEFAULT 0,
    solar_proximity_label   TEXT DEFAULT '',
    solar_distance          REAL,
    potency_score           REAL DEFAULT 0,

    -- Combined
    power_index     REAL DEFAULT 0,

    -- Metadata
    house_system    TEXT DEFAULT 'placidus',
    sect            TEXT DEFAULT 'Diurnal',
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, profile_id, planet_name)
);

-- Mutual reception pairs (per-chart)
CREATE TABLE IF NOT EXISTS user_mutual_receptions (
    id              BIGSERIAL PRIMARY KEY,
    user_id         UUID NOT NULL,
    profile_id      UUID NOT NULL,
    planet_a        TEXT NOT NULL,
    planet_b        TEXT NOT NULL,
    reception_type  TEXT NOT NULL DEFAULT 'domicile',
    created_at      TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (user_id, profile_id, planet_a, planet_b)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_ups_user_profile
    ON user_planetary_states (user_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_ups_planet
    ON user_planetary_states (planet_name);
CREATE INDEX IF NOT EXISTS idx_umr_user_profile
    ON user_mutual_receptions (user_id, profile_id);
"""

DROP_SQL = """
DROP TABLE IF EXISTS user_mutual_receptions;
DROP TABLE IF EXISTS user_planetary_states;
"""


# ═══════════════════════════════════════════════════════════════════════
# Python Serialization Helpers
# ═══════════════════════════════════════════════════════════════════════

def planetary_state_to_row(
    user_id: str,
    profile_id: str,
    state,  # PlanetaryState
    house_system: str = "placidus",
    sect: str = "Diurnal",
) -> tuple:
    """
    Convert a PlanetaryState dataclass to a tuple for INSERT.

    Returns a tuple matching the user_planetary_states column order
    (excluding id and created_at which are auto-generated).
    """
    ed = state.essential_dignity
    return (
        user_id,
        profile_id,
        state.planet_name,
        state.raw_authority,
        state.quality_index,
        ed.primary_dignity,
        ed.domicile,
        ed.exaltation,
        ed.triplicity,
        ed.term,
        ed.face,
        ed.detriment,
        ed.fall,
        ed.peregrine,
        state.house_score,
        state.motion_score,
        state.motion_label,
        state.solar_proximity_score,
        state.solar_proximity_label,
        state.solar_distance,
        state.potency_score,
        state.power_index,
        house_system,
        sect,
    )


INSERT_STATE_SQL = """
INSERT INTO user_planetary_states (
    user_id, profile_id, planet_name,
    raw_authority, quality_index, primary_dignity,
    dignity_domicile, dignity_exaltation, dignity_triplicity,
    dignity_term, dignity_face, dignity_detriment, dignity_fall, dignity_peregrine,
    house_score, motion_score, motion_label,
    solar_proximity_score, solar_proximity_label, solar_distance,
    potency_score, power_index, house_system, sect
) VALUES (
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s,
    %s, %s, %s, %s
) ON CONFLICT (user_id, profile_id, planet_name) DO UPDATE SET
    raw_authority = EXCLUDED.raw_authority,
    quality_index = EXCLUDED.quality_index,
    primary_dignity = EXCLUDED.primary_dignity,
    dignity_domicile = EXCLUDED.dignity_domicile,
    dignity_exaltation = EXCLUDED.dignity_exaltation,
    dignity_triplicity = EXCLUDED.dignity_triplicity,
    dignity_term = EXCLUDED.dignity_term,
    dignity_face = EXCLUDED.dignity_face,
    dignity_detriment = EXCLUDED.dignity_detriment,
    dignity_fall = EXCLUDED.dignity_fall,
    dignity_peregrine = EXCLUDED.dignity_peregrine,
    house_score = EXCLUDED.house_score,
    motion_score = EXCLUDED.motion_score,
    motion_label = EXCLUDED.motion_label,
    solar_proximity_score = EXCLUDED.solar_proximity_score,
    solar_proximity_label = EXCLUDED.solar_proximity_label,
    solar_distance = EXCLUDED.solar_distance,
    potency_score = EXCLUDED.potency_score,
    power_index = EXCLUDED.power_index,
    house_system = EXCLUDED.house_system,
    sect = EXCLUDED.sect,
    created_at = NOW();
"""

INSERT_RECEPTION_SQL = """
INSERT INTO user_mutual_receptions (
    user_id, profile_id, planet_a, planet_b, reception_type
) VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (user_id, profile_id, planet_a, planet_b) DO NOTHING;
"""


def save_chart_states(
    cur,
    user_id: str,
    profile_id: str,
    chart,  # AstrologicalChart
    house_system: str = "placidus",
    sect: str = "Diurnal",
) -> int:
    """
    Persist all planetary states + mutual receptions for a chart.

    Parameters
    ----------
    cur : psycopg2 cursor
    user_id : str (UUID)
    profile_id : str (UUID)
    chart : AstrologicalChart (must have planetary_states populated)
    house_system : str
    sect : str

    Returns
    -------
    int : Number of planetary state rows upserted.
    """
    count = 0

    for name, state in (chart.planetary_states or {}).items():
        row = planetary_state_to_row(user_id, profile_id, state, house_system, sect)
        cur.execute(INSERT_STATE_SQL, row)
        count += 1

    for planet_a, planet_b, rtype in (chart.mutual_receptions or []):
        cur.execute(INSERT_RECEPTION_SQL, (user_id, profile_id, planet_a, planet_b, rtype))

    return count


def load_chart_states(cur, user_id: str, profile_id: str) -> Dict:
    """
    Load planetary states from DB for a saved chart.

    Returns a dict of {planet_name: row_dict} that can be used to
    reconstruct PlanetaryState objects.
    """
    cur.execute(
        "SELECT * FROM user_planetary_states WHERE user_id = %s AND profile_id = %s",
        (user_id, profile_id),
    )
    columns = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    return {
        row[columns.index("planet_name")]: dict(zip(columns, row))
        for row in rows
    }


def delete_chart_states(cur, user_id: str, profile_id: str) -> None:
    """Remove all planetary states and mutual receptions for a chart."""
    cur.execute(
        "DELETE FROM user_planetary_states WHERE user_id = %s AND profile_id = %s",
        (user_id, profile_id),
    )
    cur.execute(
        "DELETE FROM user_mutual_receptions WHERE user_id = %s AND profile_id = %s",
        (user_id, profile_id),
    )


# ═══════════════════════════════════════════════════════════════════════
# Standalone runner — creates tables when Supabase is available
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    try:
        import psycopg2
    except ImportError:
        print("psycopg2 not installed — run: pip install psycopg2-binary")
        raise SystemExit(1)

    CONN_PARAMS = {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": int(os.environ.get("PGPORT", 5432)),
        "user": os.environ.get("PGUSER", "postgres"),
        "password": os.environ.get("PGPASSWORD", ""),
        "dbname": os.environ.get("PGDATABASE", "rosetta"),
    }

    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(**CONN_PARAMS)
    conn.autocommit = True
    cur = conn.cursor()

    print("Creating tables...")
    cur.execute(SCHEMA_SQL)
    print("  ✓ user_planetary_states")
    print("  ✓ user_mutual_receptions")

    # Verify
    cur.execute("SELECT COUNT(*) FROM user_planetary_states")
    print(f"  user_planetary_states rows: {cur.fetchone()[0]}")
    cur.execute("SELECT COUNT(*) FROM user_mutual_receptions")
    print(f"  user_mutual_receptions rows: {cur.fetchone()[0]}")

    cur.close()
    conn.close()
    print("Done. Tables ready for use when user logins are wired in.")
