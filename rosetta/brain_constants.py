"""Shared lookup constants for the Rosetta brain helpers.

This module centralizes the import of astrology lookup tables so they can be
reused across the smaller brain submodules without repeatedly importing the
heavy ``rosetta.lookup`` module.
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, List, Mapping

_L = importlib.import_module("rosetta.lookup")

GLYPHS: Dict[str, str] = getattr(_L, "GLYPHS", {})
ALIASES_MEANINGS: Dict[str, str] = getattr(_L, "ALIASES_MEANINGS", {})
OBJECT_MEANINGS: Dict[str, str] = getattr(_L, "OBJECT_MEANINGS", {})
OBJECT_INTERPRETATIONS: Dict[str, str] = getattr(_L, "OBJECT_INTERPRETATIONS", {})
OBJECT_MEANINGS_SHORT: Dict[str, str] = getattr(_L, "OBJECT_MEANINGS_SHORT", {})
SIGN_MEANINGS: Dict[str, str] = getattr(_L, "SIGN_MEANINGS", {})
HOUSE_MEANINGS: Dict[str, str] = getattr(_L, "HOUSE_MEANINGS", {})
ASPECTS: Mapping[str, Any] = getattr(_L, "ASPECTS", {})
ASPECT_INTERPRETATIONS: Dict[str, str] = getattr(_L, "ASPECT_INTERPRETATIONS", {})
PLANETARY_RULERS: Mapping[str, Any] = getattr(_L, "PLANETARY_RULERS", {})
DIGNITIES: Mapping[str, Any] = getattr(_L, "DIGNITIES", {})
CATEGORY_MAP: Dict[str, str] = getattr(_L, "CATEGORY_MAP", {})
SABIAN_SYMBOLS: Mapping[str, Any] = getattr(_L, "SABIAN_SYMBOLS", {})
SHAPE_INSTRUCTIONS: Mapping[str, str] = getattr(_L, "SHAPE_INSTRUCTIONS", {})

SIGN_NAMES: List[str] = getattr(
    _L,
    "SIGN_NAMES",
    [
        "Aries",
        "Taurus",
        "Gemini",
        "Cancer",
        "Leo",
        "Virgo",
        "Libra",
        "Scorpio",
        "Sagittarius",
        "Capricorn",
        "Aquarius",
        "Pisces",
    ],
)

__all__ = [
    "ALIASES_MEANINGS",
    "ASPECTS",
    "ASPECT_INTERPRETATIONS",
    "CATEGORY_MAP",
    "DIGNITIES",
    "GLYPHS",
    "HOUSE_MEANINGS",
    "OBJECT_INTERPRETATIONS",
    "OBJECT_MEANINGS",
    "OBJECT_MEANINGS_SHORT",
    "PLANETARY_RULERS",
    "SABIAN_SYMBOLS",
    "SHAPE_INSTRUCTIONS",
    "SIGN_MEANINGS",
    "SIGN_NAMES",
]
