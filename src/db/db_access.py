"""Utilities for reading lookup data back from PostgreSQL into Python objects.

This module provides the primary runtime data access layer. The app should call
``load_static_from_db()`` at startup to populate ``static_db`` from PostgreSQL
instead of reading from Python files.

The one-time seeding of the database is done by ``static_db_to_postgres.py``.
"""

import os
from typing import Optional, Dict

import psycopg2
from psycopg2.extras import RealDictCursor

from src.core.models_v2 import (
    StaticLookup, Sign, House, Object, Aspect, Axis,
    CompassAxis, Shape, SabianSymbol, Element, Modality, Polarity,
    ObjectSign, ObjectHouse
)

CONN_PARAMS = {
    'host': os.environ.get('PGHOST', 'localhost'),
    'port': int(os.environ.get('PGPORT', '5432')),
    'user': os.environ.get('PGUSER', ''),
    'password': os.environ.get('PGPASSWORD', ''),
    'dbname': os.environ.get('PGDATABASE', ''),
}


def _connect():
    return psycopg2.connect(**CONN_PARAMS)


def is_db_configured() -> bool:
    """Return True if PostgreSQL credentials are configured."""
    return bool(CONN_PARAMS.get('user') and CONN_PARAMS.get('dbname'))


def load_static_from_db() -> StaticLookup:
    """Fetches ALL lookup tables from the database and returns a StaticLookup.

    The returned object has the same structure as ``models_v2.static_db``.
    This is the PRIMARY data source for the app at runtime.
    """
    static = StaticLookup()
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # ─────────────────────────────────────────────────────────────
            # 1. HOUSES (load first - needed by ObjectHouse refs)
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM houses ORDER BY number")
            for row in cur:
                static.houses[row['number']] = House(
                    number=row['number'],
                    short_meaning=row['short_meaning'] or '',
                    long_meaning=row['long_meaning'] or '',
                    keywords=row.get('keywords') or [],
                    life_domain=row.get('life_domain') or '',
                    schematic=row.get('schematic'),
                    instructions=row.get('instructions') or '',
                )

            # ─────────────────────────────────────────────────────────────
            # 2. SIGNS (load before objects - needed by ObjectSign refs)
            #    We build lightweight Element/Modality/Polarity stubs from
            #    the stored string values in the signs table.
            # ─────────────────────────────────────────────────────────────
            # Build element/modality/polarity lookup stubs
            element_stubs: Dict[str, Element] = {}
            modality_stubs: Dict[str, Modality] = {}
            polarity_stubs: Dict[str, Polarity] = {}

            cur.execute("SELECT * FROM signs ORDER BY sign_index")
            for row in cur:
                # Create element stub if needed
                elem_name = row.get('element') or 'Unknown'
                if elem_name not in element_stubs:
                    element_stubs[elem_name] = Element(name=elem_name, glyph='')
                # Create modality stub if needed
                mod_name = row.get('modality') or 'Unknown'
                if mod_name not in modality_stubs:
                    modality_stubs[mod_name] = Modality(name=mod_name, glyph='')
                # Create polarity stub if needed
                pol_name = row.get('polarity') or 'Unknown'
                if pol_name not in polarity_stubs:
                    polarity_stubs[pol_name] = Polarity(name=pol_name, glyph='')

                static.signs[row['name']] = Sign(
                    name=row['name'],
                    glyph=row['glyph'] or '',
                    sign_index=row['sign_index'],
                    element=element_stubs[elem_name],
                    modality=modality_stubs[mod_name],
                    polarity=polarity_stubs[pol_name],
                    short_meaning=row['short_meaning'] or '',
                    long_meaning=row['long_meaning'] or '',
                    keywords=row.get('keywords') or [],
                    assoc_with_house=row.get('assoc_with_house') or 1,
                    opposite_sign=row.get('opposite_sign') or '',
                    body_part=row.get('body_part') or '',
                    gland_organ=row.get('gland_organ') or '',
                )

            # Store element/modality/polarity lookups on static
            static.elements = element_stubs
            static.modalities = modality_stubs
            static.polarities = polarity_stubs

            # ─────────────────────────────────────────────────────────────
            # 3. OBJECTS
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM objects")
            for row in cur:
                static.objects[row['name']] = Object(
                    name=row['name'],
                    swisseph_id=row.get('swisseph_id') or 0,
                    glyph=row.get('glyph') or '',
                    abrev=row.get('abrev'),
                    short_meaning=row.get('short_meaning') or '',
                    long_meaning=row.get('long_meaning') or '',
                    narrative_role=row.get('narrative_role') or 'Character',
                    narrative_interp=row.get('narrative_interp') or '',
                    object_type=row.get('object_type') or 'Planet',
                    influence=row.get('influence') or [],
                    keywords=row.get('keywords') or [],
                )

            # ─────────────────────────────────────────────────────────────
            # 4. ASPECTS
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM aspects")
            for row in cur:
                static.aspects[row['name']] = Aspect(
                    name=row['name'],
                    glyph=row.get('glyph') or '',
                    angle=int(row.get('angle') or 0),
                    orb=int(row.get('orb') or 0),
                    line_color=row.get('line_color') or '',
                    line_style=row.get('line_style') or 'solid',
                    short_meaning=row.get('short_meaning') or '',
                    long_meaning=row.get('long_meaning') or '',
                    sentence_meaning=row.get('sentence_meaning') or '',
                    keywords=row.get('keywords') or [],
                    sign_interval=row.get('sign_interval'),
                    sentence_name=row.get('sentence_name'),
                )

            # ─────────────────────────────────────────────────────────────
            # 5. AXES
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM axes")
            for row in cur:
                sign1 = static.signs.get(row.get('sign1'))
                sign2 = static.signs.get(row.get('sign2'))
                static.axes[row['name']] = Axis(
                    name=row['name'],
                    sign1=sign1,
                    sign2=sign2,
                    short_meaning=row.get('short_meaning') or '',
                    long_meaning=row.get('long_meaning') or '',
                    keywords=row.get('keywords') or [],
                    schematic=row.get('schematic'),
                    axis_instructions=row.get('instructions') or '',
                )

            # ─────────────────────────────────────────────────────────────
            # 6. COMPASS_AXES
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM compass_axes")
            for row in cur:
                static.compass_axes[row['name']] = CompassAxis(
                    name=row['name'],
                    definition=row.get('definition') or '',
                    instructions=row.get('instructions') or '',
                )

            # ─────────────────────────────────────────────────────────────
            # 7. SHAPES
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM shapes")
            for row in cur:
                static.shapes[row['name']] = Shape(
                    name=row['name'],
                    glyph=row.get('glyph') or '',
                    nodes=row.get('nodes') or 0,
                    configuration=row.get('configuration') or '',
                    meaning=row.get('meaning') or '',
                )

            # ─────────────────────────────────────────────────────────────
            # 8. SABIAN_SYMBOLS
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM sabian_symbols ORDER BY sign, degree")
            for row in cur:
                sign = row['sign']
                degree = row['degree']
                if sign not in static.sabian_symbols:
                    static.sabian_symbols[sign] = {}
                static.sabian_symbols[sign][degree] = SabianSymbol(
                    sign=sign,
                    degree=degree,
                    symbol=row.get('symbol') or '',
                    short_meaning=row.get('short_meaning') or '',
                    long_meaning=row.get('long_meaning') or '',
                    keywords=row.get('keywords') or [],
                )

            # ─────────────────────────────────────────────────────────────
            # 9. OBJECT_SIGN_COMBOS
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM object_sign_combos")
            for row in cur:
                obj = static.objects.get(row.get('object_name'))
                sign = static.signs.get(row.get('sign_name'))
                if obj and sign:
                    static.object_sign_combos[row['combo_key']] = ObjectSign(
                        object=obj,
                        sign=sign,
                        short_meaning=row.get('short_meaning') or '',
                        behavioral_style=row.get('behavioral_style') or '',
                        dignity=row.get('dignity'),
                        dignity_interp=row.get('dignity_interp'),
                        somatic_signature=row.get('somatic_signature'),
                        shadow_expression=row.get('shadow_expression'),
                        strengths=row.get('strengths'),
                        challenges=row.get('challenges'),
                        keywords=row.get('keywords') or [],
                        remediation_tips=row.get('remediation_tips') or [],
                    )

            # ─────────────────────────────────────────────────────────────
            # 10. OBJECT_HOUSE_COMBOS
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT * FROM object_house_combos")
            for row in cur:
                obj = static.objects.get(row.get('object_name'))
                house = static.houses.get(row.get('house_number'))
                if obj and house:
                    static.object_house_combos[row['combo_key']] = ObjectHouse(
                        object=obj,
                        house=house,
                        short_meaning=row.get('short_meaning') or '',
                        environmental_impact=row.get('environmental_impact') or '',
                        concrete_manifestation=row.get('concrete_manifestation') or '',
                        strengths=row.get('strengths'),
                        challenges=row.get('challenges'),
                        objective=row.get('objective') or '',
                        keywords=row.get('keywords') or [],
                    )

            # ─────────────────────────────────────────────────────────────
            # 11. ORDERED_OBJECTS
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT object_name FROM ordered_objects ORDER BY position")
            static.ordered_objects = [row['object_name'] for row in cur]

            # ─────────────────────────────────────────────────────────────
            # 12. HOUSE_SYSTEM_INTERP
            # ─────────────────────────────────────────────────────────────
            cur.execute("SELECT name, description FROM house_system_interp")
            for row in cur:
                static.house_system_interp[row['name']] = row['description'] or ''

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
