"""
Test the rosetta package structure and functionality.
"""
import ast
import os


def test_basic_imports():
    """Test that basic rosetta imports work."""
    from rosetta.lookup import ASPECTS
    assert "Conjunction" in ASPECTS


def test_main_file_exists():
    """Test that rosetta.py exists in the root."""
    # Get the project root directory (parent of tests directory)
    project_root = os.path.dirname(os.path.dirname(__file__))
    rosetta_path = os.path.join(project_root, "rosetta.py")
    assert os.path.exists(rosetta_path), "Main rosetta.py should exist"
