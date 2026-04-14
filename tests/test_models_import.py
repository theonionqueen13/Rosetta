from src.core.models_v2 import static_db
from src.core.static_data import ZODIAC_NUMBERS, SIGN_ANATOMY, SIGN_MEANINGS


def test_signs_present():
    assert len(static_db.signs) == 12
    assert 'Aries' in static_db.signs


def test_sign_fields():
    aries = static_db.signs['Aries']
    assert getattr(aries, 'glyph', None) is not None
    assert isinstance(aries.sign_index, int)
    # sign_index now mirrors ZODIAC_NUMBERS (1..12)
    assert 1 <= aries.sign_index <= 12
    assert aries.sign_index == int(ZODIAC_NUMBERS['Aries'])

    # Anatomy fields should be populated from SIGN_ANATOMY
    anatomy = SIGN_ANATOMY.get('Aries', {})
    assert aries.body_part == anatomy.get('Body Part', '').strip()
    assert aries.gland_organ == anatomy.get('Glands and Organs', '').strip()

    # Sign short meaning, keywords, and instructions should come from SIGN_MEANINGS
    s_info = SIGN_MEANINGS.get('Aries', {})
    expected_short = s_info.get('meaning', s_info if isinstance(s_info, str) else '')
    assert aries.short_meaning == expected_short
    assert isinstance(aries.keywords, list)
    assert aries.sign_instructions == (s_info.get('instructions', '') if isinstance(s_info, dict) else '')


def test_house_schematic():
    from src.core.static_data import HOUSE_INTERP
    # Ensure house 1 exists and its schematic mirrors HOUSE_INTERP[1]
    assert 1 in static_db.houses
    expected = HOUSE_INTERP.get(1)
    if isinstance(expected, dict):
        assert static_db.houses[1].schematic == expected.get('schematic', None)
    else:
        # expected is a string description; we want that as schematic
        assert static_db.houses[1].schematic == expected

    # Short and long meanings should come from HOUSE_MEANINGS and LONG_HOUSE_MEANINGS
    from src.core.static_data import HOUSE_MEANINGS, LONG_HOUSE_MEANINGS
    hm = HOUSE_MEANINGS.get(1)
    if isinstance(hm, dict):
        assert static_db.houses[1].short_meaning == hm.get('meaning', '')
        # keywords should always be a list regardless of original format
        assert isinstance(static_db.houses[1].keywords, list)
        if isinstance(hm.get('keywords', None), (list, tuple, set)):
            assert static_db.houses[1].keywords == list(hm.get('keywords', []))
        elif isinstance(hm.get('keywords', None), str):
            # string splitted by commas should match
            split = [k.strip() for k in hm['keywords'].split(',') if k.strip()]
            assert static_db.houses[1].keywords == split
    else:
        assert static_db.houses[1].short_meaning == hm
    assert static_db.houses[1].long_meaning == LONG_HOUSE_MEANINGS.get(1, '')


def test_objects_have_meanings_and_keywords():
    assert 'Sun' in static_db.objects
    sun = static_db.objects['Sun']
    assert sun.short_meaning is not None
    assert isinstance(sun.short_meaning, str)
    # keywords is optional; if present it should be a list
    assert hasattr(sun, 'keywords')
    assert isinstance(sun.keywords, list)


def test_house_schematic():
    from src.core.static_data import HOUSE_INTERP
    # Ensure house 1 exists and its schematic mirrors HOUSE_INTERP[1]
    assert 1 in static_db.houses
    expected = HOUSE_INTERP.get(1)
    if isinstance(expected, dict):
        assert static_db.houses[1].schematic == expected.get('schematic', None)
    else:
        # expected is a string description; we want that as schematic
        assert static_db.houses[1].schematic == expected


def test_element_long_meaning_and_remedy():
    # Elements should expose long_meaning and remedy fields populated from lookup_v2.ELEMENT
    assert 'Fire' in static_db.elements
    fire = static_db.elements['Fire']
    assert hasattr(fire, 'long_meaning')
    assert isinstance(fire.long_meaning, str)
    assert hasattr(fire, 'remedy')
    assert isinstance(fire.remedy, str)
    # element_instructions should reflect the 'instructions' key and not be a color fallback
    from src.core.static_data import ELEMENT
    assert fire.element_instructions == ELEMENT['Fire'].get('instructions', '')


def test_aspect_short_and_sentence_meanings():
    from src.core.static_data import SHORT_ASPECT_MEANINGS, SENTENCE_ASPECT_MEANINGS
    # Pick a known aspect like 'Trine'
    assert 'Trine' in static_db.aspects
    tri = static_db.aspects['Trine']
    assert hasattr(tri, 'short_meaning')
    assert hasattr(tri, 'sentence_meaning')
    # If SHORT_ASPECT_MEANINGS has an entry for 'Trine', they should match
    if 'Trine' in SHORT_ASPECT_MEANINGS:
        assert tri.short_meaning == SHORT_ASPECT_MEANINGS['Trine']
    if 'Trine' in SENTENCE_ASPECT_MEANINGS:
        assert tri.sentence_meaning == SENTENCE_ASPECT_MEANINGS['Trine']


def test_object_narrative_role_and_interp():
    from src.core.static_data import CATEGORY_MAP, CATEGORY_INSTRUCTIONS
    # Sun belongs to 'Character Profiles' in CATEGORY_MAP
    assert 'Sun' in static_db.objects
    sun = static_db.objects['Sun']
    assert sun.narrative_role in ("Character","Instrument","Personal Initiation","Mythic Journey","Compass Coordinate","Compass Needle","Switch","Imprint")
    # If category present, narrative_interp should equal CATEGORY_INSTRUCTIONS[cat]
    # Find expected category
    expected_cat = next((c for c, members in CATEGORY_MAP.items() if 'Sun' in members), None)
    if expected_cat:
        assert sun.narrative_interp == CATEGORY_INSTRUCTIONS.get(expected_cat, '')


def test_static_db_exposes_legacy_constants():
    """Several lists and maps that used to live in lookup_v2 should now be
    accessible directly on the ``static_db`` object and reflect the same
    values as static_data (raw dicts) and static_db (dataclass instances)."""
    import src.core.static_data as static_data
    # pick a sample of uppercase attributes that other modules may rely on
    attrs = [
        'SYNASTRY_COLORS_1', 'ZODIAC_SIGNS', 'ZODIAC_COLORS',
        'GROUP_COLORS', 'SUBSHAPE_COLORS', 'GLYPHS', 'ASPECTS',
        'MAJOR_OBJECTS', 'PLANETS_PLUS', 'TOGGLE_ASPECTS',
    ]
    for attr in attrs:
        assert hasattr(static_db, attr), f"static_db is missing {attr}"
        assert getattr(static_db, attr) == getattr(static_data, attr)


def test_compass_axes_populated():
    # COMPASS_AXIS_INTERP should populate static_db.compass_axes
    from src.core.static_data import COMPASS_AXIS_INTERP
    for k in COMPASS_AXIS_INTERP.keys():
        assert k in static_db.compass_axes
        ca = static_db.compass_axes[k]
        assert hasattr(ca, 'definition')
        assert isinstance(ca.definition, str)


def test_sign_and_house_axes_populated():
    # Both SIGN_AXIS_INTERP and HOUSE_AXIS_INTERP should fill static_db.axes
    from src.core.static_data import SIGN_AXIS_INTERP, HOUSE_AXIS_INTERP
    for k in SIGN_AXIS_INTERP.keys():
        assert k in static_db.axes
        ax = static_db.axes[k]
        assert ax.sign1 is not None and ax.sign2 is not None
        assert isinstance(ax.short_meaning, str)
    for k in HOUSE_AXIS_INTERP.keys():
        assert k in static_db.axes
        ax = static_db.axes[k]
        assert ax.sign1 is not None and ax.sign2 is not None
        assert isinstance(ax.short_meaning, str)


def test_object_types_from_lookup():
    # every object listed in static_data.OBJECT_TYPE should be classified correctly
    from src.core.static_data import OBJECT_TYPE
    # build expected map using same logic as migrate_lookup_data
    mapping = {}
    cat_map = {
        "Luminaries": "Luminary",
        "Planets": "Planet",
        "Asteroids": "Asteroid",
        "Centaurs": "Centaur",
        "Dwarf Planets": "Dwarf Planet",
        "Compass points": "Calculated Point",
        "Calculated Points": "Calculated Point",
    }
    for cat, names in OBJECT_TYPE.items():
        expected_type = cat_map.get(cat, cat.rstrip('s'))
        for n in names:
            mapping[n] = expected_type

    for name, expected in mapping.items():
        assert name in static_db.objects, f"{name} missing from static objects"
        actual = static_db.objects[name].object_type
        assert actual == expected, f"{name} -> {actual} not {expected}"


def test_at_least_one_object_has_keywords():
    # ensure keyword migration is not empty for all objects
    has_kw = any(obj.keywords for obj in static_db.objects.values())
    assert has_kw, "Expected at least one catalog object to carry keywords"


def test_profile_formatter_chartobject():
    # Build a minimal ChartObject and ensure formatter does not attempt to
    # treat it like a mapping (no AttributeError and returns a non-empty string)
    from src.core.models_v2 import ChartObject
    from src.rendering.profiles_v2 import format_object_profile_html
    sun_obj = static_db.objects.get('Sun')
    sign_obj = static_db.signs.get('Aries')
    sample = ChartObject(
        object_name=sun_obj,
        glyph=sun_obj.glyph,
        longitude=0.0,
        abs_deg=0.0,
        sign=sign_obj,
        dms="0°",
        latitude=0.0,
        declination=0.0,
        placidus_house=static_db.houses.get(1),
        equal_house=static_db.houses.get(1),
        whole_sign_house=static_db.houses.get(1),
        sabian_symbol=static_db.sabian_symbols.get('Aries', {}).get(1),
    )
    out = format_object_profile_html(sample)
    assert isinstance(out, str) and out
    # verify sabian symbol text (not repr) is included
    # set up a fake sabian symbol to test this
    class FakeSabian:
        def __init__(self, symbol):
            self.symbol = symbol
    sample.sabian_symbol = FakeSabian("HelloSabian")
    out2 = format_object_profile_html(sample)
    assert "HelloSabian" in out2, "Sabian symbol text should appear"
    # also verify fallback when symbol empty but short_meaning present
    class FakeWithShort(FakeSabian):
        def __init__(self, symbol, short):
            super().__init__(symbol)
            self.short_meaning = short
    sample.sabian_symbol = FakeWithShort("", "ShortMeaningHere")
    out3 = format_object_profile_html(sample)
    assert "ShortMeaningHere" in out3, "Should use short_meaning when symbol blank"

def test_optional_db_migration():
    """If a PostgreSQL database is configured, run the migration script and do a simple sanity check.

    This test is skipped silently when the necessary environment variables are not defined.
    """
    import os
    import pytest
    if not os.environ.get('PGDATABASE'):
        pytest.skip("no PGDATABASE env var; skipping DB migration test")
    # we import here to reuse the same connection logic
    from static_db_to_postgres import main as migrate
    # run an initial migration so tables exist
    migrate()
    import psycopg2
    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=os.environ.get('PGPORT', '5432'),
        user=os.environ.get('PGUSER', ''),
        password=os.environ.get('PGPASSWORD', ''),
        dbname=os.environ.get('PGDATABASE', ''),
    )
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM signs")
    cnt = cur.fetchone()[0]
    # verify sabian_symbols table includes meaning columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='sabian_symbols'")
    cols = {r[0] for r in cur.fetchall()}
    assert 'short_meaning' in cols and 'long_meaning' in cols

    # now simulate stale data for the half-zodiac (e.g. Leo degree 1) and
    # ensure migrating again overwrites it.  The first migration should have
    # populated a proper value; we clobber it and then rerun migrate().
    cur.execute("UPDATE sabian_symbols SET symbol = 'OLD' WHERE sign='Leo' AND degree=1")
    conn.commit()
    # re-run migration which should delete and re-insert Leo-Pisces rows
    migrate()
    # verify our artificial 'OLD' value has been replaced with the current
    # lookup entry
    from src.core.models_v2 import static_db
    expected = static_db.sabian_symbols['Leo'][1].symbol
    cur.execute("SELECT symbol FROM sabian_symbols WHERE sign='Leo' AND degree=1")
    got = cur.fetchone()[0]
    assert got == expected, "Leo symbol should be refreshed by migration"

    # exercise house-combo upsert: pick an existing key and clobber the
    # short_meaning, then rerun migration and confirm it updates.
    house_key = next(iter(static_db.object_house_combos))
    cur.execute("UPDATE object_house_combos SET short_meaning='OLD' WHERE combo_key=%s",(house_key,))
    conn.commit()
    migrate()
    cur.execute("SELECT short_meaning FROM object_house_combos WHERE combo_key=%s",(house_key,))
    updated = cur.fetchone()[0]
    assert updated == static_db.object_house_combos[house_key].short_meaning, \
        "object_house_combos row should be refreshed by migration"

    # exercise sign-combo upsert similarly
    sign_key = next(iter(static_db.object_sign_combos))
    cur.execute("UPDATE object_sign_combos SET short_meaning='OLD' WHERE combo_key=%s",(sign_key,))
    conn.commit()
    migrate()
    cur.execute("SELECT short_meaning FROM object_sign_combos WHERE combo_key=%s",(sign_key,))
    updated2 = cur.fetchone()[0]
    assert updated2 == static_db.object_sign_combos[sign_key].short_meaning, \
        "object_sign_combos row should be refreshed by migration"

    conn.close()
    assert cnt == 12, f"expected 12 signs in DB, got {cnt}"

def test_db_completeness():
    """Verify the database rows mirror the in-memory lookup data.

    Runs only when PGDATABASE is set.
    """
    import os
    import pytest
    if not os.environ.get('PGDATABASE'):
        pytest.skip("no PGDATABASE env var; skipping DB completeness check")
    import psycopg2
    from src.core.models_v2 import static_db

    conn = psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=os.environ.get('PGPORT', '5432'),
        user=os.environ.get('PGUSER', ''),
        password=os.environ.get('PGPASSWORD', ''),
        dbname=os.environ.get('PGDATABASE', ''),
    )
    cur = conn.cursor()
    def check(table, expected):
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        got = cur.fetchone()[0]
        assert got == expected, f"{table} count {got} != {expected}"
    check('signs', len(static_db.signs))

    # extra sanity: ensure object types in the database match in-memory values
    cur.execute("SELECT name, object_type FROM objects")
    db_types = {name: typ for name, typ in cur.fetchall()}
    for name, obj in static_db.objects.items():
        if name in db_types:
            assert db_types[name] == obj.object_type, \
                f"db {name} type {db_types[name]} != {obj.object_type}"

    # make sure house keywords in DB mirror in-memory values
    cur.execute("SELECT number, keywords FROM houses")
    db_house_kw = {num: kws for num, kws in cur.fetchall()}
    for num, h in static_db.houses.items():
        if num in db_house_kw:
            assert db_house_kw[num] == h.keywords, \
                f"house {num} keywords {db_house_kw[num]} != {h.keywords}"
    check('houses', len(static_db.houses))
    check('objects', len(static_db.objects))
    check('aspects', len(static_db.aspects))
    check('axes', len(static_db.axes))
    check('compass_axes', len(static_db.compass_axes))
    check('shapes', len(static_db.shapes))
    check('object_house_combos', len(static_db.object_house_combos))
    # ensure north/south node combos are present in DB
    cur.execute("SELECT COUNT(*) FROM object_house_combos WHERE object_name IN ('North Node','South Node')")
    node_count = cur.fetchone()[0]
    assert node_count >= 24, f"expected at least 24 node combos, got {node_count}"
    # ensure sign combos mirror in-memory lookup exactly
    cur.execute("SELECT COUNT(*) FROM object_sign_combos")
    sign_count = cur.fetchone()[0]
    assert sign_count == len(static_db.object_sign_combos), \
        f"sign combos count {sign_count} != {len(static_db.object_sign_combos)}"
    cur.execute("SELECT combo_key FROM object_sign_combos LIMIT 1")
    assert cur.fetchone()[0] is not None
    cur.execute("SELECT COUNT(*) FROM sabian_symbols")
    sb_cnt = cur.fetchone()[0]
    assert sb_cnt >= 360
    # spot checks
    cur.execute("SELECT symbol FROM sabian_symbols LIMIT 3")
    for (s,) in cur.fetchall():
        assert s is not None and s != ''
    cur.execute("SELECT glyph FROM signs LIMIT 3")
    for (g,) in cur.fetchall():
        assert g is not None and g != ''
    conn.close()

