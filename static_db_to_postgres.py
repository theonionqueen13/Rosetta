"""Helper script to push the in-memory static lookup database into Postgres.

Run this after you have created a database and have connection credentials ready.

Usage example (from workspace root):

    set PGHOST=localhost
    set PGPORT=5432
    set PGUSER=myuser
    set PGPASSWORD=mypass
    set PGDATABASE=rosetta
    python -m static_db_to_postgres

The script will create a handful of tables (signs, houses, objects, aspects,
axes, compass_axes, shapes, sabian_symbols) and insert the corresponding
records from ``models_v2.static_db``.  It is intentionally simple; you can
extend or normalise the schema later as needed.
"""

import os
import psycopg2
from psycopg2.extras import execute_values, register_default_jsonb

from models_v2 import static_db

# register jsonb adapter just in case we want to store some fields as json
register_default_jsonb()

CONN_PARAMS = {
    'host': os.environ.get('PGHOST', 'localhost'),
    'port': int(os.environ.get('PGPORT', '5432')),
    'user': os.environ.get('PGUSER', ''),
    'password': os.environ.get('PGPASSWORD', ''),
    'dbname': os.environ.get('PGDATABASE', ''),
}

# helper used by insertion loops to make sure keywords (and similar fields)
# are always plain Python lists. psycopg2 can't adapt dict objects directly.
def _normalize_list(val):
    if val is None:
        return []
    if isinstance(val, dict):
        # if the dict itself has a keywords field, use that; otherwise just
        # turn it into a list of its values
        if 'keywords' in val:
            return _normalize_list(val.get('keywords'))
        return list(val.values())
    if isinstance(val, (list, tuple, set)):
        return list(val)
    # anything else (including str, int) becomes a single-element list
    return [val]

TABLE_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS signs (
        name TEXT PRIMARY KEY,
        glyph TEXT,
        sign_index INTEGER,
        element TEXT,
        modality TEXT,
        polarity TEXT,
        short_meaning TEXT,
        long_meaning TEXT,
        keywords TEXT[],
        instructions TEXT,
        assoc_with_house INTEGER,
        opposite_sign TEXT,
        body_part TEXT,
        gland_organ TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS houses (
        number INTEGER PRIMARY KEY,
        short_meaning TEXT,
        long_meaning TEXT,
        keywords TEXT[],
        life_domain TEXT,
        schematic TEXT,
        instructions TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS objects (
        name TEXT PRIMARY KEY,
        swisseph_id DOUBLE PRECISION,
        glyph TEXT,
        abrev TEXT,
        short_meaning TEXT,
        long_meaning TEXT,
        narrative_role TEXT,
        narrative_interp TEXT,
        object_type TEXT,
        influence TEXT[],
        keywords TEXT[]
    );""",

    """CREATE TABLE IF NOT EXISTS aspects (
        name TEXT PRIMARY KEY,
        glyph TEXT,
        angle DOUBLE PRECISION,
        orb DOUBLE PRECISION,
        line_color TEXT,
        line_style TEXT,
        short_meaning TEXT,
        long_meaning TEXT,
        keywords TEXT[],
        sentence_meaning TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS axes (
        name TEXT PRIMARY KEY,
        sign1 TEXT,
        sign2 TEXT,
        short_meaning TEXT,
        long_meaning TEXT,
        keywords TEXT[],
        schematic TEXT,
        instructions TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS compass_axes (
        name TEXT PRIMARY KEY,
        definition TEXT,
        instructions TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS shapes (
        name TEXT PRIMARY KEY,
        glyph TEXT,
        nodes INTEGER,
        configuration TEXT,
        meaning TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS sabian_symbols (
        sign TEXT,
        degree INTEGER,
        symbol TEXT,
        short_meaning TEXT,
        long_meaning TEXT,
        keywords TEXT[],
        PRIMARY KEY (sign, degree)
    );""",
]


def init_schema(cur):
    for stmt in TABLE_STATEMENTS:
        cur.execute(stmt)
    # in case the table already existed from a previous run, add any new columns
    cur.execute("""
        ALTER TABLE sabian_symbols
        ADD COLUMN IF NOT EXISTS short_meaning TEXT,
        ADD COLUMN IF NOT EXISTS long_meaning TEXT,
        ADD COLUMN IF NOT EXISTS keywords TEXT[];
    """)


def insert_static_data(cur):
    # helper to ensure list-like values are safe for TEXT[] columns
    def _to_list(val):
        if val is None:
            return []
        if isinstance(val, (list, tuple, set)):
            return list(val)
        # if it really is a dict, drop it (shouldn't happen) or take its values
        if isinstance(val, dict):
            return list(val.values())
        # otherwise coerce to string to avoid psycopg2 errors
        return [str(val)]

    # signs
    rows = []
    for s in static_db.signs.values():
        rows.append((
            s.name, s.glyph, s.sign_index, s.element.name, s.modality.name,
            s.polarity.name, s.short_meaning, s.long_meaning, _to_list(s.keywords),
            getattr(s, 'sign_instructions', ''), s.assoc_with_house,
            s.opposite_sign, s.body_part, s.gland_organ
        ))
    execute_values(cur,
                   "INSERT INTO signs VALUES %s ON CONFLICT (name) DO NOTHING",
                   rows)

    # houses
    rows = []
    for h in static_db.houses.values():
        # long_meaning sometimes comes through as a dict (see static_db tests)
        lm = h.long_meaning
        if isinstance(lm, dict):
            lm = lm.get('long_meaning', '') or str(lm)
        rows.append((
            h.number, h.short_meaning, lm, _to_list(h.keywords),
            h.life_domain, h.schematic, h.instructions
        ))
    # upsert houses so that updated keywords/meanings propagate
    execute_values(cur,
                   """
                   INSERT INTO houses VALUES %s
                   ON CONFLICT (number) DO UPDATE SET
                       short_meaning = EXCLUDED.short_meaning,
                       long_meaning = EXCLUDED.long_meaning,
                       keywords = EXCLUDED.keywords,
                       life_domain = EXCLUDED.life_domain,
                       schematic = EXCLUDED.schematic,
                       instructions = EXCLUDED.instructions
                   """,
                   rows)

    # objects
    rows = []
    for o in static_db.objects.values():
        sw_id = o.swisseph_id
        # many 'calculated points' use strings such as 'ASC' or 'MC'; store as
        # NULL instead of trying to coerce to float.
        try:
            sw_id = float(sw_id)
        except Exception:
            sw_id = None
        rows.append((
            o.name, sw_id, o.glyph, o.abrev, o.short_meaning,
            o.long_meaning, o.narrative_role, o.narrative_interp,
            o.object_type, _to_list(o.influence), _to_list(o.keywords)
        ))
    # upsert objects, updating all fields on conflict to ensure corrections propagate
    execute_values(cur,
                   """
                   INSERT INTO objects VALUES %s
                   ON CONFLICT (name) DO UPDATE SET
                       swisseph_id = EXCLUDED.swisseph_id,
                       glyph = EXCLUDED.glyph,
                       abrev = EXCLUDED.abrev,
                       short_meaning = EXCLUDED.short_meaning,
                       long_meaning = EXCLUDED.long_meaning,
                       narrative_role = EXCLUDED.narrative_role,
                       narrative_interp = EXCLUDED.narrative_interp,
                       object_type = EXCLUDED.object_type,
                       influence = EXCLUDED.influence,
                       keywords = EXCLUDED.keywords
                   """,
                   rows)

    # aspects
    rows = []
    for a in static_db.aspects.values():
        rows.append((
            a.name, a.glyph, a.angle, a.orb, a.line_color, a.line_style,
            a.short_meaning, a.long_meaning, _to_list(a.keywords), a.sentence_meaning
        ))
    execute_values(cur,
                   "INSERT INTO aspects VALUES %s ON CONFLICT (name) DO NOTHING",
                   rows)

    # axes
    rows = []
    for k, ax in static_db.axes.items():
        rows.append((
            k, ax.sign1.name if ax.sign1 else None,
            ax.sign2.name if ax.sign2 else None,
            ax.short_meaning, ax.long_meaning, _to_list(ax.keywords),
            ax.schematic, ax.axis_instructions
        ))
    execute_values(cur,
                   "INSERT INTO axes VALUES %s ON CONFLICT (name) DO NOTHING",
                   rows)

    # compass axes
    rows = []
    for k, ca in static_db.compass_axes.items():
        rows.append((k, ca.definition, ca.instructions))
    execute_values(cur,
                   "INSERT INTO compass_axes VALUES %s ON CONFLICT (name) DO NOTHING",
                   rows)

    # shapes
    rows = []
    for k, sh in static_db.shapes.items():
        rows.append((k, sh.glyph, sh.nodes, sh.configuration, sh.meaning))
    execute_values(cur,
                   "INSERT INTO shapes VALUES %s ON CONFLICT (name) DO NOTHING",
                   rows)

    # sabian symbols
    rows = []
    for sign, table in static_db.sabian_symbols.items():
        for deg, sym in table.items():
            symval = sym.symbol
            if isinstance(symval, dict):
                symval = symval.get('sabian symbol', '') or str(symval)
            shortm = getattr(sym, 'short_meaning', '') or ''
            longm = getattr(sym, 'long_meaning', '') or ''
            kw = _to_list(getattr(sym, 'keywords', []))
            rows.append((sign, deg, symval, shortm, longm, kw))
    # upsert so that existing rows get their new meaning/keyword fields updated
    execute_values(cur,
                   "INSERT INTO sabian_symbols (sign, degree, symbol, short_meaning, long_meaning, keywords) VALUES %s "
                   "ON CONFLICT (sign, degree) DO UPDATE SET "
                   "symbol = EXCLUDED.symbol, "
                   "short_meaning = EXCLUDED.short_meaning, "
                   "long_meaning = EXCLUDED.long_meaning, "
                   "keywords = EXCLUDED.keywords",
                   rows)


def main():
    # interactively fill in any missing connection parameters
    if not CONN_PARAMS.get('user'):
        CONN_PARAMS['user'] = input('Postgres user: ')
    if not CONN_PARAMS.get('dbname'):
        CONN_PARAMS['dbname'] = input('Postgres database: ')

    if not CONN_PARAMS.get('password'):
        try:
            import getpass
            CONN_PARAMS['password'] = getpass.getpass('Postgres password: ')
        except Exception:
            pass

    # debug print (mask password)
    print('Connecting with', {k: v for k, v in CONN_PARAMS.items() if k!='password'})
    conn = psycopg2.connect(**CONN_PARAMS)
    try:
        with conn:
            with conn.cursor() as cur:
                init_schema(cur)
                insert_static_data(cur)
            # print basic stats
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM sabian_symbols")
                print('inserted/updated', cur.fetchone()[0], 'sabian symbol rows')
                cur.execute("SELECT COUNT(*) FROM signs")
                print('sign count:', cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM objects")
                print('object count:', cur.fetchone()[0])
                # show a breakdown by object_type so we can spot misclassifications
                cur.execute("SELECT object_type, COUNT(*) FROM objects GROUP BY object_type")
                print('type breakdown:', cur.fetchall())
                # sample house keywords to verify normalization
                cur.execute("SELECT number, keywords FROM houses ORDER BY number LIMIT 3")
                print('house keyword sample:', cur.fetchall())
    finally:
        conn.close()


if __name__ == '__main__':
    main()
