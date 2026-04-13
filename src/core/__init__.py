"""
src/core — core astrological data models, calculations, and static data.

Re-exports the most-used symbols so callers can write:
    from src.core import static_db, AstrologicalChart
"""

from src.core.models_v2 import AstrologicalChart, ChartObject, static_db
from src.core.calc_v2 import calculate_chart
from src.core.patterns_v2 import detect_shapes
from src.core.static_data import GLYPHS, SIGNS

__all__ = [
    "AstrologicalChart",
    "ChartObject",
    "static_db",
    "calculate_chart",
    "detect_shapes",
    "GLYPHS",
    "SIGNS",
]
