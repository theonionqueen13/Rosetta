from src.core.models_v2 import static_db

MAJOR_OBJECTS = static_db.MAJOR_OBJECTS


def test_swisseph_ids_from_major_objects():
    # Ensure that major objects have their swisseph_id populated from MAJOR_OBJECTS
    for name in ('Sun', 'Moon', 'Mercury'):
        assert name in static_db.objects
        assert static_db.objects[name].swisseph_id == MAJOR_OBJECTS.get(name)


def test_aspect_harmonic_and_reception_icons():
    from src.core.models_v2 import static_db
    RECEPTION_SYMBOLS = static_db.RECEPTION_SYMBOLS
    assert 'Trine' in static_db.aspects
    tri = static_db.aspects['Trine']
    # harmonic defaults to integer
    assert hasattr(tri, 'harmonic')
    assert isinstance(tri.harmonic, int)
    # reception icons pulled from lookup when available
    recv = RECEPTION_SYMBOLS.get('Trine', {})
    if recv:
        assert tri.reception_icon_orb == recv.get('by orb')
        assert tri.reception_icon_sign == recv.get('by sign')


def test_influence_and_aspect_strengths():
    # Mars is malefic, Venus is benefic
    assert 'Mars' in static_db.objects
    assert 'Venus' in static_db.objects
    assert 'malefic' in static_db.objects['Mars'].influence
    assert 'benefic' in static_db.objects['Venus'].influence

    # Square should have strengths and risks strings from ASPECTS
    assert 'Square' in static_db.aspects
    sq = static_db.aspects['Square']
    assert isinstance(sq.strengths, str)
    assert isinstance(sq.risks, str)
