#!/usr/bin/env python3
"""
Pytest tests to ensure the modernized Rosetta structure works correctly.
"""
import ast
import os


def test_imports():
    """Test that all rosetta package imports work."""
    # These imports should not raise ImportError
    from rosetta.calc import calculate_chart
    from rosetta.drawing import draw_aspect_lines, draw_zodiac_signs
    from rosetta.helpers import deg_to_rad, get_ascendant_degree
    from rosetta.lookup import ASPECTS, GLYPHS
    from rosetta.patterns import detect_minor_links_with_singletons


def test_constants():
    """Test that constants are properly accessible."""
    from rosetta.lookup import ASPECTS, MAJOR_OBJECTS

    assert "Conjunction" in ASPECTS, "Conjunction aspect should be in ASPECTS"
    assert "Sun" in MAJOR_OBJECTS, "Sun should be in MAJOR_OBJECTS"
    assert isinstance(ASPECTS["Conjunction"],
                      dict), "Aspect data should be a dictionary"
    assert "angle" in ASPECTS["Conjunction"], "Aspect should have angle property"


def test_main_app_exists():
    """Test that main application file exists and is syntactically valid."""
    app_path = "rosetta.py"

    # Check if file exists (relative to project root, not tests dir)
    root_dir = os.path.dirname(os.path.dirname(__file__))
    full_path = os.path.join(root_dir, app_path)

    assert os.path.exists(
        full_path), f"Main application {app_path} should exist"

    # Check syntax is valid
    with open(full_path, 'r') as f:
        content = f.read()

    # This will raise SyntaxError if invalid, causing test to fail
    ast.parse(content)


def test_package_structure():
    """Test that the rosetta package has expected modules."""
    import rosetta.calc
    import rosetta.drawing
    import rosetta.helpers
    import rosetta.lookup
    import rosetta.patterns

    # Check that key functions exist
    assert hasattr(rosetta.calc, 'calculate_chart')
    assert hasattr(rosetta.patterns, 'detect_minor_links_with_singletons')
    assert hasattr(rosetta.helpers, 'deg_to_rad')
