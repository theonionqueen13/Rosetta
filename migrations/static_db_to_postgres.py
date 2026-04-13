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

    """CREATE TABLE IF NOT EXISTS object_sign_combos (
        combo_key TEXT PRIMARY KEY,
        object_name TEXT,
        sign_name TEXT,
        short_meaning TEXT,
        behavioral_style TEXT,
        dignity TEXT,
        dignity_interp TEXT,
        somatic_signature TEXT,
        shadow_expression TEXT,
        strengths TEXT,
        challenges TEXT,
        keywords TEXT[],
        remediation_tips TEXT[]
    );""",

    """CREATE TABLE IF NOT EXISTS object_house_combos (
        combo_key TEXT PRIMARY KEY,
        object_name TEXT,
        house_number INTEGER,
        short_meaning TEXT,
        environmental_impact TEXT,
        concrete_manifestation TEXT,
        strengths TEXT,
        challenges TEXT,
        objective TEXT,
        keywords TEXT[]
    );""",

    """CREATE TABLE IF NOT EXISTS ordered_objects (
        position INTEGER PRIMARY KEY,
        object_name TEXT NOT NULL
    );""",

    """CREATE TABLE IF NOT EXISTS house_system_interp (
        name TEXT PRIMARY KEY,
        description TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS astrological_terms (
        id SERIAL PRIMARY KEY,
        canonical TEXT NOT NULL UNIQUE,
        aliases TEXT[],
        factors TEXT[],
        intent TEXT,
        domain TEXT,
        description TEXT
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
    cur.execute("""
        ALTER TABLE object_sign_combos
        ADD COLUMN IF NOT EXISTS dignity_interp TEXT;
    """)
    cur.execute("""
        ALTER TABLE aspects
        ADD COLUMN IF NOT EXISTS sign_interval INTEGER;
    """)
    cur.execute("""
        ALTER TABLE aspects
        ADD COLUMN IF NOT EXISTS sentence_name TEXT;
    """)


def seed_astrological_terms(cur):
    """Upsert the built-in astrological terms vocabulary.

    Each row encodes one canonical concept with its alias patterns,
    optional astrological factors, routing intent, domain grouping, and
    a short description.  Rows are keyed on ``canonical`` so repeated
    runs are idempotent.
    """
    # Source of truth lives in src/mcp/term_registry._BUILTIN_TERMS;
    # we duplicate minimally here to keep the migration self-contained.
    rows = [
        # (canonical, aliases, factors, intent, domain, description)
        (
            "influential planet",
            ["most influential planet", "most influential",
             "which planet.*most influence", "what.*most influential",
             "planet.*most influence", "influential planet",
             "what is.*influential", "most significant planet"],
            [],
            "potency_ranking",
            "Identity & Self",
            "Asks which planet(s) have the greatest overall potency per the power index.",
        ),
        (
            "strongest planet",
            ["strongest planet", "most powerful planet", "most potent planet",
             "dominant planet", "dominant energy", "most dominant",
             "which planet is strongest", "what.*strongest planet",
             "planet.*greatest power", "most forceful planet"],
            [],
            "potency_ranking",
            "Identity & Self",
            "Asks for the planet with the highest combined power index.",
        ),
        (
            "weakest planet",
            ["weakest planet", "least powerful planet", "least active planet",
             "least prominent planet", "least influential",
             "which planet.*weakest", "most inactive planet",
             "planet.*lowest power"],
            [],
            "potency_ranking",
            "Identity & Self",
            "Asks for the planet with the lowest power index.",
        ),
        (
            "most dignified planet",
            ["most dignified", "best dignified", "highest dignity",
             "greatest dignity", "planet.*most dignified",
             "which planet.*dignified", "best placed.*dignity"],
            [],
            "potency_ranking",
            "Identity & Self",
            "Asks which planet has the best essential dignity score.",
        ),
        (
            "afflicted planet",
            ["afflicted planet", "most afflicted", "debilitated planet",
             "fallen planet", "planet.*in detriment", "planet.*in fall",
             "which planet.*afflicted", "most debilitated"],
            [],
            "potency_ranking",
            "Identity & Self",
            "Asks about planets with negative dignity or poor accidental state.",
        ),
        (
            "prominent planet",
            ["prominent planet", "most prominent", "which planet stands out",
             "planet.*stands out", "well.placed planet", "best placed planet",
             "planet.*prominent", "angular planet", "which planet.*angular"],
            [],
            "potency_ranking",
            "Identity & Self",
            "Asks for planets that are especially active or visible in the chart.",
        ),
        (
            "planet power",
            ["planet.*power", "power.*planet", "potency of.*planet",
             "planetary potency", "planetary power", "planetary strength",
             "strength.*planet", "which planet.*strong",
             "overall.*planet.*strength", "chart.*power"],
            [],
            "potency_ranking",
            "Identity & Self",
            "General inquiry about the relative power or strength of planets in the chart.",
        ),
    ]
    execute_values(
        cur,
        """
        INSERT INTO astrological_terms
            (canonical, aliases, factors, intent, domain, description)
        VALUES %s
        ON CONFLICT (canonical) DO UPDATE SET
            aliases     = EXCLUDED.aliases,
            factors     = EXCLUDED.factors,
            intent      = EXCLUDED.intent,
            domain      = EXCLUDED.domain,
            description = EXCLUDED.description
        """,
        rows,
    )
    print(f"astrological_terms seeded: {len(rows)} rows")


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
            a.short_meaning, a.long_meaning, _to_list(a.keywords), a.sentence_meaning,
            getattr(a, 'sign_interval', None), getattr(a, 'sentence_name', None)
        ))
    execute_values(cur,
                   """
                   INSERT INTO aspects
                   (name, glyph, angle, orb, line_color, line_style,
                    short_meaning, long_meaning, keywords, sentence_meaning,
                    sign_interval, sentence_name)
                   VALUES %s
                   ON CONFLICT (name) DO UPDATE SET
                       glyph = EXCLUDED.glyph,
                       angle = EXCLUDED.angle,
                       orb = EXCLUDED.orb,
                       line_color = EXCLUDED.line_color,
                       line_style = EXCLUDED.line_style,
                       short_meaning = EXCLUDED.short_meaning,
                       long_meaning = EXCLUDED.long_meaning,
                       keywords = EXCLUDED.keywords,
                       sentence_meaning = EXCLUDED.sentence_meaning,
                       sign_interval = EXCLUDED.sign_interval,
                       sentence_name = EXCLUDED.sentence_name
                   """,
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
    # *new* lookup data has been completed for the second half of the zodiac
    # (Leo through Pisces).  Older migrations may have inserted placeholder
    # or partial data for those signs; we want to completely overwrite
    # whatever is in the database with the fresh information from
    # ``static_db.sabian_symbols``.  To avoid stale rows lingering we delete
    # the existing entries for that range before writing.
    half_zodiac = ['Leo','Virgo','Libra','Scorpio','Sagittarius',
                   'Capricorn','Aquarius','Pisces']
    cur.execute("DELETE FROM sabian_symbols WHERE sign = ANY(%s)",
                (half_zodiac,))

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

    # object_sign_combos
    rows = []
    for combo_key, combo in static_db.object_sign_combos.items():
        rows.append((
            combo_key,
            combo.object.name if combo.object else None,
            combo.sign.name if combo.sign else None,
            combo.short_meaning,
            combo.behavioral_style,
            combo.dignity if isinstance(combo.dignity, str) else None,
            combo.dignity_interp if isinstance(combo.dignity_interp, str) else None,
            combo.somatic_signature,
            combo.shadow_expression,
            combo.strengths,
            combo.challenges,
            _to_list(combo.keywords),
            _to_list(combo.remediation_tips)
        ))
    execute_values(cur,
                   "INSERT INTO object_sign_combos "
                   "(combo_key, object_name, sign_name, short_meaning, behavioral_style, "
                   "dignity, dignity_interp, somatic_signature, shadow_expression, "
                   "strengths, challenges, keywords, remediation_tips) "
                   "VALUES %s ON CONFLICT (combo_key) DO UPDATE SET "
                   "object_name = EXCLUDED.object_name, "
                   "sign_name = EXCLUDED.sign_name, "
                   "short_meaning = EXCLUDED.short_meaning, "
                   "behavioral_style = EXCLUDED.behavioral_style, "
                   "dignity = EXCLUDED.dignity, "
                   "dignity_interp = EXCLUDED.dignity_interp, "
                   "somatic_signature = EXCLUDED.somatic_signature, "
                   "shadow_expression = EXCLUDED.shadow_expression, "
                   "strengths = EXCLUDED.strengths, "
                   "challenges = EXCLUDED.challenges, "
                   "keywords = EXCLUDED.keywords, "
                   "remediation_tips = EXCLUDED.remediation_tips",
                   rows)
    # post-insert sanity: ensure all combos from lookup exist in the table
    cur.execute("SELECT combo_key FROM object_sign_combos")
    db_sign_keys = {r[0] for r in cur.fetchall()}
    expected_sign_keys = set(static_db.object_sign_combos.keys())
    missing_sign = expected_sign_keys - db_sign_keys
    if missing_sign:
        raise RuntimeError(f"Missing object_sign_combos after migration: {sorted(missing_sign)}")
    else:
        print(f"object_sign_combos in DB after upsert: {len(db_sign_keys)}")

    # object_house_combos
    # make sure any prior North/South Node placements are removed before
    # we start; historically a previous migration run didn't include these
    # keys at all so some databases may have zero rows for them. deleting
    # first guarantees they'll be recreated by the bulk operation below.
    cur.execute("DELETE FROM object_house_combos WHERE object_name = ANY(%s)",
                (['North Node', 'South Node'],))

    # previously we used DO NOTHING on conflict; that meant updates to
    # existing combos were ignored.  New keys would still be inserted, but
    # since we now occasionally tweak meanings or add keywords to existing
    # placements it's safer to upsert all fields just like object_sign_combos.
    rows = []
    for combo_key, combo in static_db.object_house_combos.items():
        rows.append((
            combo_key,
            combo.object.name if combo.object else None,
            combo.house.number if combo.house else None,
            combo.short_meaning,
            combo.environmental_impact,
            combo.concrete_manifestation,
            combo.strengths,
            combo.challenges,
            combo.objective,
            _to_list(combo.keywords)
        ))
    execute_values(cur,
                   "INSERT INTO object_house_combos "
                   "(combo_key, object_name, house_number, short_meaning, "
                   "environmental_impact, concrete_manifestation, strengths, "
                   "challenges, objective, keywords) VALUES %s "
                   "ON CONFLICT (combo_key) DO UPDATE SET "
                   "object_name = EXCLUDED.object_name, "
                   "house_number = EXCLUDED.house_number, "
                   "short_meaning = EXCLUDED.short_meaning, "
                   "environmental_impact = EXCLUDED.environmental_impact, "
                   "concrete_manifestation = EXCLUDED.concrete_manifestation, "
                   "strengths = EXCLUDED.strengths, "
                   "challenges = EXCLUDED.challenges, "
                   "objective = EXCLUDED.objective, "
                   "keywords = EXCLUDED.keywords",
                   rows)

    # ordered_objects — full replace each run so position changes are picked up
    cur.execute("DELETE FROM ordered_objects")
    rows = [(pos, name) for pos, name in enumerate(static_db.ordered_objects)]
    if rows:
        execute_values(cur, "INSERT INTO ordered_objects (position, object_name) VALUES %s", rows)
    print(f"ordered_objects rows: {len(rows)}")

    # house_system_interp
    rows = [(name, desc) for name, desc in static_db.house_system_interp.items()]
    if rows:
        execute_values(cur,
                       "INSERT INTO house_system_interp (name, description) VALUES %s "
                       "ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description",
                       rows)
    print(f"house_system_interp rows: {len(rows)}")

    # astrological terms vocabulary
    seed_astrological_terms(cur)

    # post-insert sanity: make sure all north/south node combos landed
    cur.execute("SELECT combo_key FROM object_house_combos "
                "WHERE object_name IN ('North Node','South Node')")
    db_keys = {r[0] for r in cur.fetchall()}
    expected_keys = {k for k in static_db.object_house_combos
                     if k.startswith('NorthNode') or k.startswith('SouthNode')}
    missing = expected_keys - db_keys
    if missing:
        # this is unexpected; abort so the issue is visible
        raise RuntimeError(f"Migration inserted {len(db_keys)} node combos, "
                           f"missing: {sorted(missing)}")
    else:
        print(f"node combos in DB after upsert: {len(db_keys)}")


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
                # New stats for object_sign_combos and object_house_combos
                cur.execute("SELECT COUNT(*) FROM object_sign_combos")
                sign_cnt = cur.fetchone()[0]
                print('object_sign_combos count:', sign_cnt)
                cur.execute("SELECT COUNT(*) FROM object_house_combos")
                cnt = cur.fetchone()[0]
                print('object_house_combos count:', cnt)
                cur.execute("SELECT COUNT(*) FROM object_house_combos WHERE object_name IN ('North Node','South Node')")
                print('node combos present:', cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM ordered_objects")
                print('ordered_objects count:', cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM house_system_interp")
                print('house_system_interp count:', cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM aspects WHERE sign_interval IS NOT NULL")
                print('aspects with sign_interval:', cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM astrological_terms")
                print('astrological_terms count:', cur.fetchone()[0])
    finally:
        conn.close()


if __name__ == '__main__':
    main()
