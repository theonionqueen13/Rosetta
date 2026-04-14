from src.core.models_v2 import static_db

# use static_db for lookups instead of importing lookup_v2 directly
SABIAN_SYMBOLS = static_db.SABIAN_SYMBOLS
MAJOR_OBJECTS = static_db.MAJOR_OBJECTS


def test_sabian_symbol_present():
    # Ensure a known sabian symbol exists (Cancer 11)
    assert 'Cancer' in static_db.sabian_symbols
    assert 11 in static_db.sabian_symbols['Cancer']
    expected = SABIAN_SYMBOLS.get(('Cancer', 11))
    # the lookup may be a string or a dict containing various fields
    if isinstance(expected, dict):
        # migrate_lookup_data uses 'sabian_symbol' or 'symbol' or 'short_meaning' as the printed name
        expected_text = expected.get('sabian_symbol') or expected.get('symbol') or expected.get('short_meaning', '')
    else:
        expected_text = expected
    assert static_db.sabian_symbols['Cancer'][11].symbol == expected_text


def test_black_moon_lilith_swisseph():
    # Ensure Black Moon Lilith mapping uses MAJOR_OBJECTS value
    name = 'Black Moon Lilith (Mean)'
    assert name in static_db.objects
    assert static_db.objects[name].swisseph_id == MAJOR_OBJECTS.get(name)
