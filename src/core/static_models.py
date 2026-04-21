"""
Static astrological data models and the *static_db* lookup singleton.

Defines all data-tier dataclasses: :class:`Object`, :class:`Sign`, :class:`Element`,
:class:`Modality`, :class:`Polarity`, :class:`House`, :class:`HouseSystem`,
:class:`Aspect`, :class:`Axis`, :class:`CompassAxis`, :class:`FixedStar`,
:class:`SabianSymbol`, :class:`Dignity`, :class:`Shape`, :class:`StaticLookup`,
:class:`ObjectSign`, :class:`ObjectHouse`.

Also exposes ``static_db`` — a lazily-loaded namespace that holds every shared
constant table (signs, aspects, dignities, glyphs, colour palettes, etc.).

Split from models_v2.py during Phase 2 refactor.
"""
import logging
import re
import json
import os
from dataclasses import dataclass, field
from typing import Union, List, Optional, Any, Dict, Literal

_log = logging.getLogger(__name__)

from .constants import (
    GLYPHS, MAJOR_OBJECTS, EPHE_MAJOR_OBJECTS, ALL_MAJOR_PLACEMENTS, ASPECTS,
    RECEPTION_SYMBOLS, SIGNS, SIGN_ANATOMY, LUMINARIES_AND_PLANETS, PLANETS_PLUS,
    ABREVIATED_PLANET_NAMES, PLANETARY_RULERS, DIGNITY_MEANINGS, _RECEPTION_ASPECTS,
    ALIASES_MEANINGS, MALEFICS, BENEFICS, OBJECT_TYPE, SYNASTRY_COLORS_1, SYNASTRY_COLORS_2,
    ZODIAC_SIGNS, ZODIAC_COLORS, GROUP_COLORS, GROUP_COLORS_LIGHT, SUBSHAPE_COLORS,
    SUBSHAPE_COLORS_LIGHT, TOGGLE_ASPECTS, ORDERED_OBJECTS_FOCUS, ASPECT_CONDUCTANCE,
    DIGNITY_SCORES, TRIPLICITY_RULERS, TERMS, FACES, SIGN_ELEMENT, SIGN_GLYPH,
    ZODIAC_NUMBERS, ASPECTS_BY_SIGN, CATEGORY_MAP, CATEGORY_INSTRUCTIONS, INTERP_FLAGS,
    MONTH_NAMES, STANDARD_BASE_BODIES, SHAPE_NODE_COUNTS,
    DIGNITIES, ELEMENT, SIGN_MEANINGS, HOUSE_MEANINGS,
    OBJECT_MEANINGS, OBJECT_MEANINGS_SHORT,
    ASPECT_INTERP, SHORT_ASPECT_MEANINGS,
    SETNENCE_ASPECT_NAMES, SENTENCE_ASPECT_MEANINGS,
)

from .static_data import (
    SABIAN_SYMBOLS as _SABIAN_SYMBOLS_DATA,
    SABIAN_SYMBOLS,
    POLARITY, MODE, SHAPES, LONG_OBJECT_MEANINGS,
    LONG_HOUSE_MEANINGS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Static Data Dataclasses
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Object:
    name: str
    swisseph_id: Union[int, str]
    glyph: str
    abrev: Optional[str] = None
    alias: List[str] = field(default_factory=list)

    # Classification
    influence: List[str] = field(default_factory=list)
    object_type: Literal["Planet", "Luminary", "Asteroid", "Centaur", "Dwarf Planet", "Fixed Star", "Calculated Point"] = "Planet"
    narrative_role: Literal["Compass Coordinate", "Compass Needle", "Character", "Instrument", "Personal Initiation", "Mythic Journey", "Switch", "Imprint"] = "Character"
    narrative_interp: str = ""

    goes_oob: bool = False

    # Astrology Data
    rules_signs: List[str] = field(default_factory=list)  # Domicile Rulership
    assoc_with_house: List[int] = field(default_factory=list)
    short_meaning: str = ""
    long_meaning: str = ""
    category: str = ""

    # Archetypal Data
    life_domain: Optional[str] = None
    personification: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None

    # Astronomical Data
    orbit_period: Optional[str] = None
    avg_speed: Optional[str] = None
    retrograde_period: Optional[str] = None

    # Future-proofing
    object_instructions: str = ""

@dataclass
class Element:
    name: str
    glyph: str
    short_meaning: str = ""
    long_meaning: str = ""
    remedy: str = ""
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None
    element_instructions: str = ""

@dataclass
class Modality:
    name: str
    glyph: str
    short_meaning: str = ""
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None
    modality_instructions: str = ""

@dataclass
class Polarity:
    name: str
    glyph: str
    short_meaning: str = ""
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None
    polarity_instructions: str = ""

@dataclass
class Sign:
    name: str
    glyph: str
    sign_index: int      # 1 for Aries, 12 for Pisces

    # Fundamental Qualities
    element: Element         # Fire, Earth, Air, Water
    modality: Modality        # Cardinal, Fixed, Mutable
    polarity: Polarity        # Masculine/Feminine or Positive/Negative

    # Rulerships & Dignities (matching lookup_v2.py DIGNITIES)
    rulers: List[str] = field(default_factory=list)      # e.g., ["Mars"] or ["Mars", "Pluto"]
    exaltation: Optional[str] = None
    detriment: List[str] = field(default_factory=list)
    fall: Optional[str] = None
    # Meaning & Keywords
    short_meaning: str = ""
    long_meaning: str = ""
    keywords: List[str] = field(default_factory=list)

    # Associations
    assoc_with_house: int = 1   # Primary house (e.g., Aries = 1)
    opposite_sign: str = ""     # e.g., "Libra"
    body_part: str = ""          # e.g., "Head"
    gland_organ: str = ""      # e.g., "Adrenal Glands"

    # Technical/Visual
    schematic: Optional[str] = None
    sign_instructions: str = ""      # Your deliberate override field

@dataclass
class House:
    number: int
    short_meaning: str = ""
    long_meaning: str = ""
    keywords: List[str] = field(default_factory=list)
    life_domain: str = ""  # e.g., "Resources", "Communication"
    schematic: Optional[str] = None
    instructions: str = ""

@dataclass
class HouseSystem:
    name: str              # e.g., "Placidus", "Whole Sign", "Porphyry"
    short_meaning: str = ""  # e.g., "Time-proportional quadrant system."
    long_meaning: str = ""  # The deep philosophy of how this system views life.
    keywords: List[str] = field(default_factory=list)

    # Visuals & Meta
    schematic: Optional[str] = None
    instructions: str = ""  # Your override for how to interpret this system

    # Classification (Optional but helpful for UI)
    is_quadrant_system: bool = True  # Placidus/Koch/Regiomontanus are quadrant

@dataclass
class Aspect:
    name: str
    glyph: str
    angle: int
    orb: int

    # Visuals (matching your lookup_v2.py ASPECTS dict)
    line_color: str
    line_style: str  # e.g., "solid" or "dotted"

    # Interpretation (matching your ASPECT_INTERP dict)
    short_meaning: str = ""
    long_meaning: str = ""
    sentence_meaning: str = ""
    keywords: List[str] = field(default_factory=list)
    aspect_instructions: str = ""  # Your deliberate future-proofing field
    risks: str = ""  # Potential challenges associated with this aspect
    strengths: str = ""  # Potential strengths associated with this aspect

    # Classification & Technicals
    aspect_type: str = "Major"  # "Major", "Minor", or "Harmonic"
    harmonic: int = 1
    polarity: Optional[str] = None  # e.g., "Harmonious" vs "Tense"

    # Metadata
    alias: Optional[str] = None
    schematic: Optional[str] = None

    # New: Reception (to match RECEPTION_SYMBOLS in lookup_v2.py)
    reception_icon_orb: Optional[str] = None   # e.g., "blue_trine.png"
    reception_icon_sign: Optional[str] = None  # e.g., "green_trine.png"

    # Sign-interval number (from ASPECTS_BY_SIGN; e.g. Trine=4, Square=3)
    sign_interval: Optional[int] = None

    # Verb form used in sentences (from SETNENCE_ASPECT_NAMES; e.g. "trines", "is conjunct")
    sentence_name: Optional[str] = None

@dataclass
class Axis:
    name: str             # e.g., "Taurus-Scorpio Axis"
    sign1: Sign            # e.g., "Taurus"
    sign2: Sign            # e.g., "Scorpio"

    # Interpretation
    short_meaning: str = ""
    long_meaning: str = ""
    keywords: List[str] = field(default_factory=list)

    # Visuals & Meta
    schematic: Optional[str] = None
    axis_instructions: str = ""  # Your custom instructions field

    # Potential addition: Modality (optional)
    # Since signs on an axis always share a modality (Fixed, Cardinal, or Mutable)
    modality: Optional[Modality] = None

@dataclass
class CompassAxis:
    name: str             # e.g., "The Horizon"
    point1: Optional[Object] = None           # e.g., "Ascendant"
    point2: Optional[Object] = None           # e.g., "Descendant"
    definition: str = ""  # e.g., "The line representing the horizon at birth time."
    short_meaning: str = ""
    long_meaning: str = ""
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None
    instructions: str = ""

@dataclass
class FixedStar:
    short_name: str
    full_name: str
    glyph: str
    magnitude: float
    short_meaning: str
    long_meaning: str
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None
    body_part: str = ""

@dataclass
class SabianSymbol:
    sign: str              # e.g., "Aries"
    degree: int            # 1-30 (Standard Sabian notation usually starts at 1)
    symbol: str            # The descriptive text (e.g., "A woman just risen from the sea...")
    short_meaning: str = ""
    long_meaning: str = ""
    keywords: List[str] = field(default_factory=list)

@dataclass
class Dignity:
    name: str              # e.g., "Domicile", "Exaltation"
    short_meaning: str
    long_meaning: str
    keywords: List[str] = field(default_factory=list)
    schematic: Optional[str] = None
    dignity_instructions: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Shape (static template) — distinct from chart-runtime shape instances
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Shape:
    name: str
    glyph: str
    nodes: int
    configuration: str
    meaning: str

@dataclass
class StaticLookup:
    elements: Dict[str, Element] = field(default_factory=dict)
    modalities: Dict[str, Modality] = field(default_factory=dict)
    polarities: Dict[str, Polarity] = field(default_factory=dict)
    signs: Dict[str, Sign] = field(default_factory=dict)
    objects: Dict[str, Object] = field(default_factory=dict)
    aspects: Dict[str, Aspect] = field(default_factory=dict)
    houses: Dict[int, House] = field(default_factory=dict)
    axes: Dict[str, Axis] = field(default_factory=dict)
    compass_axes: Dict[str, CompassAxis] = field(default_factory=dict)
    shapes: Dict[str, Shape] = field(default_factory=dict)
    sabian_symbols: Dict[str, Dict[int, SabianSymbol]] = field(default_factory=dict)
    object_sign_combos: Dict[str, "ObjectSign"] = field(default_factory=dict)
    object_house_combos: Dict[str, "ObjectHouse"] = field(default_factory=dict)
    # Flat lookup tables not absorbed into other models
    ordered_objects: List[str] = field(default_factory=list)
    house_system_interp: Dict[str, str] = field(default_factory=dict)

@dataclass
class ObjectSign:
    object: Object
    sign: Sign
    short_meaning: str
    behavioral_style: str = ""
    dignity: Optional[Union[Dignity, str]] = None
    dignity_interp: Optional[str] = None
    somatic_signature: Optional[str] = None
    shadow_expression: Optional[str] = None
    strengths: Optional[str] = None
    challenges: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    remediation_tips: List[str] = field(default_factory=list)

@dataclass
class ObjectHouse:
    object: Object
    house: House
    short_meaning: str
    environmental_impact: str = ""
    concrete_manifestation: str = ""
    strengths: Optional[str] = None
    challenges: Optional[str] = None
    objective: str = ""
    keywords: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Static DB initialisation
# ─────────────────────────────────────────────────────────────────────────────


def _init_static_db() -> StaticLookup:
    """Initialize static_db from PostgreSQL (required).

    Raises ``RuntimeError`` with a helpful message if the PG environment
    variables are missing. Raises any psycopg2 exception on connection
    failure so the problem is visible immediately at startup, rather than
    silently falling back to stale Python file data.
    """
    import os
    if not (os.environ.get('PGUSER') and os.environ.get('PGDATABASE')):
        raise RuntimeError(
            "PostgreSQL not configured. Set PGUSER and PGDATABASE environment "
            "variables (plus PGHOST, PGPORT, PGPASSWORD as needed). "
            "See README.md for local setup instructions."
        )

    from src.db.db_access import load_static_from_db
    _log.info("[static_db] Loading from PostgreSQL...")
    db = load_static_from_db()

    # Copy utility constants (imported from .constants) onto the instance so
    # rendering-layer code can access them via static_db.GLYPHS etc.
    for _name, _val in list(globals().items()):
        if _name.isupper():
            try:
                setattr(db, _name, _val)
            except (AttributeError, TypeError):
                pass

    _log.info(
        "[static_db] Loaded %d signs, %d objects, %d aspects from PostgreSQL",
        len(db.signs), len(db.objects), len(db.aspects),
    )
    return db


static_db: StaticLookup = _init_static_db()


def load_static_lookup() -> StaticLookup:
    """Force-reload static_db from PostgreSQL and update the existing singleton.

    Mutates the global ``static_db`` in-place so that callers that already
    hold a reference pick up new data without re-importing.
    """
    from src.db.db_access import load_static_from_db
    new_db = load_static_from_db()

    # Copy utility constants onto the freshly loaded instance
    for _name, _val in list(globals().items()):
        if _name.isupper():
            try:
                setattr(new_db, _name, _val)
            except (AttributeError, TypeError):
                pass

    # Update in-place so existing references remain valid
    static_db.__dict__.update(new_db.__dict__)
    return static_db

