from src.core.models_v2 import static_db

# we no longer need to import the raw lookup; use static_db instead
SHAPES = static_db.SHAPES


def test_shapes_present_for_all_defined_shapes():
    # Every shape defined in LOOKUP should be present in the static lookup
    for name in SHAPES.keys():
        assert name in static_db.shapes, f"Missing shape {name} in static_db.shapes"


def test_shape_template_fields_and_types():
    # Pick a couple of shapes and validate fields
    for name, tpl in static_db.shapes.items():
        assert hasattr(tpl, 'glyph')
        assert hasattr(tpl, 'meaning')
        assert hasattr(tpl, 'configuration')
        assert hasattr(tpl, 'nodes')
        assert isinstance(tpl.glyph, str)
        assert isinstance(tpl.meaning, str)
        assert isinstance(tpl.configuration, str)
        assert isinstance(tpl.nodes, int)


def test_nodes_count_inferred_reasonably():
    # If a configuration contains node_1, node_2 etc, nodes should be >= the max index
    import re
    for name, data in SHAPES.items():
        cfg = data.get('configuration', '') if isinstance(data, dict) else ''
        nums = [int(n) for n in re.findall(r'node_(\d+)', cfg)]
        if nums:
            assert static_db.shapes[name].nodes >= max(nums)
