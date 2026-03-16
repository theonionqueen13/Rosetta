"""Utilities for reading lookup data back from PostgreSQL into Python objects.

The purpose of this module is to demonstrate how the application can be changed
from relying exclusively on the in-memory ``static_db`` to pulling lookup
information from the database.  You can call ``load_static_from_db()`` at
startup and then use the returned ``StaticLookup`` just as you do with
``models_v2.static_db``.

It uses psycopg2 for simplicity; you could replace the implementation with
SQLAlchemy if you prefer.
"""

import os
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from models_v2 import (StaticLookup, Sign, House, Object, Aspect, Axis,
                        CompassAxis, Shape, SabianSymbol)

CONN_PARAMS = {
    'host': os.environ.get('PGHOST', 'localhost'),
    'port': int(os.environ.get('PGPORT', '5432')),
    'user': os.environ.get('PGUSER', ''),
    'password': os.environ.get('PGPASSWORD', ''),
    'dbname': os.environ.get('PGDATABASE', ''),
}


def _connect():
    return psycopg2.connect(**CONN_PARAMS)


def load_static_from_db() -> StaticLookup:
    """Fetches all lookup tables from the database and returns a StaticLookup.

    The returned object has the same structure as ``models_v2.static_db``.
    """
    static = StaticLookup()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # signs
            cur.execute("SELECT * FROM signs")
            for row in cur:
                static.signs[row['name']] = Sign(
                    name=row['name'],
                    glyph=row['glyph'],
                    sign_index=row['sign_index'],
                    element=None,  # leave for caller to reconcile or ignore
                    modality=None,
                    polarity=None,
                    short_meaning=row['short_meaning'],
                    long_meaning=row['long_meaning'],
                    keywords=row.get('keywords') or [],
                    assoc_with_house=row.get('assoc_with_house'),
                    opposite_sign=row.get('opposite_sign'),
                    body_part=row.get('body_part'),
                    gland_organ=row.get('gland_organ'),
                )
            # houses
            cur.execute("SELECT * FROM houses")
            for row in cur:
                static.houses[row['number']] = House(
                    number=row['number'],
                    short_meaning=row['short_meaning'],
                    long_meaning=row['long_meaning'],
                    keywords=row.get('keywords') or [],
                    life_domain=row.get('life_domain'),
                    schematic=row.get('schematic'),
                    instructions=row.get('instructions') or '',
                )
            # other tables could be filled similarly if needed
    finally:
        conn.close()
    return static


_terms_cache: Optional[list] = None


def get_terms(intent: Optional[str] = None) -> list:
    """Fetch rows from the astrological_terms table.

    Results are cached in memory for the lifetime of the process so the DB
    is queried at most once per intake.

    Parameters
    ----------
    intent : str, optional
        If provided, only rows with a matching ``intent`` value are returned.

    Returns
    -------
    list of dict
        Each dict has keys: canonical, aliases, factors, intent, domain,
        description.
    """
    global _terms_cache
    if _terms_cache is None:
        try:
            conn = _connect()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT canonical, aliases, factors, intent, domain, "
                        "description FROM astrological_terms ORDER BY id"
                    )
                    _terms_cache = [dict(r) for r in cur.fetchall()]
            finally:
                conn.close()
        except Exception:
            _terms_cache = []  # Don't retry — fall back to built-ins

    if intent is not None:
        return [r for r in _terms_cache if r.get("intent") == intent]
    return list(_terms_cache)
