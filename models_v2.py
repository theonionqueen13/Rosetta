import re
import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Union, List, Optional, Any, Dict, Literal, ClassVar  # Added Literal here
import pandas as pd
from lookup_v2 import GLYPHS, SHAPES, MAJOR_OBJECTS, EPHE_MAJOR_OBJECTS, ALL_MAJOR_PLACEMENTS, ASPECTS, ASPECT_INTERP, DIGNITIES, RECEPTION_SYMBOLS, ELEMENT, MODE, SIGNS, SIGN_ANATOMY, LUMINARIES_AND_PLANETS, PLANETS_PLUS, ABREVIATED_PLANET_NAMES, PLANETARY_RULERS, DIGNITY_MEANINGS, DIGNITIES, _RECEPTION_ASPECTS, ALIASES_MEANINGS, ABREVIATED_PLANET_NAMES, OBJECT_MEANINGS, OBJECT_MEANINGS_SHORT, LONG_OBJECT_MEANINGS, ASPECTS_BY_SIGN, SIGN_MEANINGS, HOUSE_MEANINGS, ASPECT_INTERP, SIGN_AXIS_INTERP, HOUSE_AXIS_INTERP, COMPASS_AXIS_INTERP, HOUSE_SYSTEM_INTERP, HOUSE_INTERP, SIGN_GLYPH, ZODIAC_NUMBERS, POLARITY, SHORT_ASPECT_MEANINGS, SENTENCE_ASPECT_MEANINGS, CATEGORY_MAP, CATEGORY_INSTRUCTIONS, LONG_HOUSE_MEANINGS, MALEFICS, BENEFICS, OBJECT_TYPE, SYNASTRY_COLORS_1, SYNASTRY_COLORS_2, ZODIAC_SIGNS, ZODIAC_COLORS, GROUP_COLORS, GROUP_COLORS_LIGHT, SUBSHAPE_COLORS, SUBSHAPE_COLORS_LIGHT, TOGGLE_ASPECTS, ORDERED_OBJECTS_FOCUS, SETNENCE_ASPECT_NAMES

# --- Lazy-loaded JSON data (much faster than parsing Python dicts) ---
_JSON_DIR = os.path.dirname(__file__)
_CACHED_SABIAN_SYMBOLS = None
_CACHED_OBJECT_SIGN_COMBO = None
_CACHED_OBJECT_HOUSE_COMBO = None

def _load_sabian_symbols_json() -> dict:
    """Load Sabian symbols from JSON file. Returns dict keyed by (sign, degree) tuples."""
    global _CACHED_SABIAN_SYMBOLS
    if _CACHED_SABIAN_SYMBOLS is not None:
        return _CACHED_SABIAN_SYMBOLS
    
    json_path = os.path.join(_JSON_DIR, "sabian_symbols.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Convert "Aries_1" keys back to ("Aries", 1) tuples
        _CACHED_SABIAN_SYMBOLS = {}
        for key, value in raw.items():
            parts = key.rsplit("_", 1)
            if len(parts) == 2:
                sign, deg = parts[0], int(parts[1])
                _CACHED_SABIAN_SYMBOLS[(sign, deg)] = value
        return _CACHED_SABIAN_SYMBOLS
    
    # Fallback to lookup_v2 if JSON doesn't exist
    from lookup_v2 import SABIAN_SYMBOLS
    _CACHED_SABIAN_SYMBOLS = SABIAN_SYMBOLS
    return _CACHED_SABIAN_SYMBOLS

def _load_object_sign_combo_json() -> dict:
    """Load object-sign combos from JSON file."""
    global _CACHED_OBJECT_SIGN_COMBO
    if _CACHED_OBJECT_SIGN_COMBO is not None:
        return _CACHED_OBJECT_SIGN_COMBO
    
    json_path = os.path.join(_JSON_DIR, "object_sign_combo.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            _CACHED_OBJECT_SIGN_COMBO = json.load(f)
        return _CACHED_OBJECT_SIGN_COMBO
    
    # Fallback to lookup_v2 if JSON doesn't exist
    from lookup_v2 import OBJECT_SIGN_COMBO
    _CACHED_OBJECT_SIGN_COMBO = OBJECT_SIGN_COMBO
    return _CACHED_OBJECT_SIGN_COMBO

def _load_object_house_combo_json() -> dict:
    """Load object-house combos from JSON file."""
    global _CACHED_OBJECT_HOUSE_COMBO
    if _CACHED_OBJECT_HOUSE_COMBO is not None:
        return _CACHED_OBJECT_HOUSE_COMBO
    
    json_path = os.path.join(_JSON_DIR, "object_house_combo.json")
    if os.path.exists(json_path):
        with open(json_path, "r", encoding="utf-8") as f:
            _CACHED_OBJECT_HOUSE_COMBO = json.load(f)
        return _CACHED_OBJECT_HOUSE_COMBO
    
    # Fallback to lookup_v2 if JSON doesn't exist
    from lookup_v2 import OBJECT_HOUSE_COMBO
    _CACHED_OBJECT_HOUSE_COMBO = OBJECT_HOUSE_COMBO
    return _CACHED_OBJECT_HOUSE_COMBO

PatternNode = Union['ChartObject', 'Cluster']

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
    rules_signs: List[str] = field(default_factory=list) # Domicile Rulership
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
    life_domain: str = "" # e.g., "Resources", "Communication"
    schematic: Optional[str] = None
    instructions: str = ""

@dataclass
class HouseSystem:
    name: str              # e.g., "Placidus", "Whole Sign", "Porphyry"
    short_meaning: str = "" # e.g., "Time-proportional quadrant system."
    long_meaning: str = ""  # The deep philosophy of how this system views life.
    keywords: List[str] = field(default_factory=list)
    
    # Visuals & Meta
    schematic: Optional[str] = None
    instructions: str = ""  # Your override for how to interpret this system
    
    # Classification (Optional but helpful for UI)
    is_quadrant_system: bool = True # Placidus/Koch/Regiomontanus are quadrant

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
    aspect_instructions: str = "" # Your deliberate future-proofing field
    risks: str = ""  # Potential challenges associated with this aspect
    strengths: str = ""  # Potential strengths associated with this aspect
    
    # Classification & Technicals
    aspect_type: str = "Major" # "Major", "Minor", or "Harmonic"
    harmonic: int = 1
    polarity: Optional[str] = None # e.g., "Harmonious" vs "Tense"
    
    # Metadata
    alias: Optional[str] = None
    schematic: Optional[str] = None
    
    # New: Reception (to match RECEPTION_SYMBOLS in lookup_v2.py)
    reception_icon_orb: Optional[str] = None # e.g., "blue_trine.png"
    reception_icon_sign: Optional[str] = None # e.g., "green_trine.png"

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
    axis_instructions: str = "" # Your custom instructions field
    
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

@dataclass
class EssentialDignity:
    """Full essential dignity breakdown for a planet in a specific sign/degree."""
    domicile: bool = False
    exaltation: bool = False
    triplicity: bool = False          # Dorothean triplicity ruler for chart sect
    term: bool = False                # Egyptian term/bound ruler at this degree
    face: bool = False                # Chaldean decan ruler at this degree
    detriment: bool = False
    fall: bool = False
    peregrine: bool = False           # True if no positive essential dignity at all
    primary_dignity: Optional[str] = None  # Highest-ranking dignity name, or None

@dataclass
class PlanetaryState:
    """
    Per-chart planetary strength assessment.

    Vector A (Authority) = essential dignity score → normalized via tanh.
    Vector B (Potency)   = accidental dignity: house angularity + motion + solar proximity.
    Power Index          = combined magnitude of both vectors.
    """
    planet_name: str

    # --- Essential Dignity (Vector A: Authority) ---
    essential_dignity: EssentialDignity = field(default_factory=EssentialDignity)
    raw_authority: float = 0.0        # Sum of weighted dignity scores
    quality_index: float = 0.0        # tanh(raw_authority / 7), range (-1, 1)

    # --- Accidental Dignity (Vector B: Potency) ---
    house_score: float = 0.0          # Angular=5, Succedent=3, Cadent=1
    motion_score: float = 0.0         # Station-Direct=5, Station-Rx=3.5, Direct=2, Rx=1
    solar_proximity_score: float = 0.0  # Cazimi=+5, Combust=negative gradient, Under Beams=-1
    solar_proximity_label: str = ""   # "cazimi", "combust", "under_beams", or ""
    potency_score: float = 0.0       # Sum of house + motion + solar proximity

    # --- Combined ---
    power_index: float = 0.0         # sqrt((|A|*0.4)^2 + (P*0.6)^2) * mu

    # --- Motion metadata ---
    motion_label: str = ""            # "stationary_direct", "stationary_retrograde", "direct", "retrograde"
    solar_distance: Optional[float] = None  # Angular distance from Sun (degrees)

    # --- Conjunction bonuses (populated by dignity_calc.py) ---
    fixed_star_bonus: float = 0.0        # Potency bonus from conjunct fixed stars
    asteroid_bonus: float = 0.0          # Potency bonus from conjunct asteroids / BML
    conjunction_contributors: List[str] = field(default_factory=list)
    # ^ names of every star / asteroid that contributed a bonus to this object
    # (used by the profile layer: "your Venus is amplified by Pallas Athena, conjunct Spica")

    # --- Cluster aggregation (populated by dignity_calc.py) ---
    cluster_id: Optional[int] = None      # Index of the conjunction cluster this object belongs to
    cluster_potency: float = 0.0          # Aggregated potency sum across all cluster members
    cluster_members: List[str] = field(default_factory=list)
    # ^ all object names in this cluster (empty if singleton)

@dataclass
class ReceptionLink:
    other: Object
    aspect: Aspect
    mode: Literal["orb", "sign"] = "orb"

@dataclass
class ChartObject:
    object_name: Object
    glyph: str
    
    # Position Data
    longitude: float
    abs_deg: float        # Total 0-360 value
    sign: Sign             # e.g., "Aries"
    dms: str              # e.g., "15° Ar 24'" (formatted string)
    latitude: float
    declination: float
 
    # House Data (required)
    placidus_house: House   
    equal_house: House
    whole_sign_house: House

    # Interpretive Data
    sabian_symbol: SabianSymbol
    sabian_index: int = 0
    dignity: Optional[Union[Dignity, str]] = None
    ruled_by_sign: Optional[str] = None

    # Movement Data (defaults)
    speed: float = 0.0
    distance: float = 0.0
    retrograde: bool = False
    station: Optional[str] = None # "Stationing direct", "Stationing retrograde"
    oob_status: Literal["No", "Yes", "Extreme"] = "No"

    # Planetary strength (populated by dignity_calc.py)
    planetary_state: Optional[PlanetaryState] = None

    # Relationships & Rulerships
    rules_signs: List[Sign] = field(default_factory=list)
    rules_houses: List[House] = field(default_factory=list)
    sign_ruler: List[Object] = field(default_factory=list)
    house_ruler_placidus: List[Object] = field(default_factory=list)
    house_ruler_equal: List[Object] = field(default_factory=list)
    house_ruler_whole: List[Object] = field(default_factory=list)
    
    # Dynamic Connections
    reception: List[ReceptionLink] = field(default_factory=list)
    afflictions: List[Union[Object, Aspect]] = field(default_factory=list) 
    assists: List[Union[Object, Aspect]] = field(default_factory=list)
    conjunctions: List[Object] = field(default_factory=list)
    aspects: List[Aspect] = field(default_factory=list)     # All aspects
    fixed_stars: List[FixedStar] = field(default_factory=list)

    sign_index: Optional[int] = None
    degree_in_sign: Optional[int] = None
    minute_in_sign: Optional[int] = None
    second_in_sign: Optional[int] = None
    fixed_star_conj: Optional[str] = None
    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility."""
        def _names(items: List[Object]) -> str:
            return ", ".join([obj.name for obj in items if obj is not None])

        def _house_num(house: Optional[House]) -> Optional[int]:
            return house.number if isinstance(house, House) else None

        def _aspect_verb(aspect_name: str) -> str:
            mapping = {
                "Conjunction": "Conjunct",
                "Opposition": "Opposite",
                "Trine": "Trine",
                "Square": "Square",
                "Sextile": "Sextile",
            }
            return mapping.get(aspect_name, aspect_name)

        def _format_reception(items: List[ReceptionLink]) -> str:
            if not items:
                return ""
            parts = []
            for item in items:
                if not item or not item.other or not item.aspect:
                    continue
                mode_suffix = " (by orb)" if item.mode == "orb" else " (by sign)"
                verb = _aspect_verb(item.aspect.name)
                parts.append(f"{verb} {item.other.name}{mode_suffix}")
            return ", ".join(parts)

        return {
            "Object": self.object_name.name if self.object_name else "",
            "Glyph": self.glyph,
            "Dignity": self.dignity,
            "Reception": _format_reception(self.reception),
            "Ruled by (sign)": self.ruled_by_sign or _names(self.sign_ruler),
            "Longitude": self.longitude,
            "Absolute Degree": self.abs_deg or self.longitude,
            "Sign": self.sign.name if self.sign else "",
            "Sign Index": self.sign_index if self.sign_index is not None else (self.sign.sign_index if self.sign else None),
            "Degree In Sign": self.degree_in_sign if self.degree_in_sign is not None else int(self.longitude % 30) if self.longitude is not None else None,
            "Minute In Sign": self.minute_in_sign,
            "Second In Sign": self.second_in_sign,
            "DMS": self.dms,
            "Sabian Index": self.sabian_index,
            "Sabian Symbol": self.sabian_symbol.symbol if isinstance(self.sabian_symbol, SabianSymbol) else self.sabian_symbol,
            "Fixed Star Conj": self.fixed_star_conj,
            "Retrograde Bool": self.retrograde,
            "Retrograde": "Rx" if self.retrograde else "",
            "Station": self.station,
            "OOB Status": self.oob_status,
            "Placidus House": _house_num(self.placidus_house),
            "Placidus House Rulers": _names(self.house_ruler_placidus or self.placidus_ruler),
            "Equal House": _house_num(self.equal_house),
            "Equal House Rulers": _names(self.house_ruler_equal or self.equal_ruler),
            "Whole Sign House": _house_num(self.whole_sign_house),
            "Whole Sign House Rulers": _names(self.house_ruler_whole),
            "Latitude": self.latitude,
            "Declination": self.declination,
            "Distance": self.distance,
            "Speed": self.speed,
        }

    @classmethod
    def from_dict(cls, row: Dict[str, Any], static: Optional["StaticLookup"] = None) -> "ChartObject":
        static = static or static_db

        def _float(val: Any, default: float = 0.0) -> float:
            if val is None or (hasattr(val, "__float__") and str(val) == "nan"):
                return default
            try:
                return float(val)
            except (TypeError, ValueError):
                return default

        def _int_or_none(val: Any) -> Optional[int]:
            if val is None or (hasattr(val, "__float__") and str(val) == "nan"):
                return None
            try:
                return int(float(val))
            except (TypeError, ValueError):
                return None

        def _str(val: Any) -> str:
            if val is None or (hasattr(val, "__float__") and str(val) == "nan"):
                return ""
            return str(val).strip()

        def _obj_list(text: Any) -> List[Object]:
            raw = _str(text)
            if not raw:
                return []
            names = [s.strip() for s in raw.split(",") if s.strip()]
            return [static.objects.get(n) for n in names if static.objects.get(n) is not None]

        name = _str(row.get("Object"))
        obj = static.objects.get(name, Object(name=name, swisseph_id="", glyph=""))

        sign_name = _str(row.get("Sign"))
        sign = static.signs.get(sign_name)
        lon = _float(row.get("Longitude"))
        abs_deg = _float(row.get("Absolute Degree", lon))
        dms = _str(row.get("DMS"))
        sabian_idx = _int_or_none(row.get("Sabian Index")) or 0
        sabian_text = row.get("Sabian Symbol")
        sabian_symbol = None
        if sign_name and isinstance(static, StaticLookup):
            degree_in_sign = _int_or_none(row.get("Degree In Sign"))
            if degree_in_sign is not None:
                sabian_symbol = static.sabian_symbols.get(sign_name, {}).get(degree_in_sign + 1)
        if sabian_symbol is None:
            sabian_symbol = SabianSymbol(
                sign=sign_name or "",
                degree=(sabian_idx % 30) or 1,
                symbol=_str(sabian_text),
            )

        placidus_house_num = _int_or_none(row.get("Placidus House"))
        equal_house_num = _int_or_none(row.get("Equal House"))
        whole_house_num = _int_or_none(row.get("Whole Sign House"))

        # Populate rules_signs and rules_houses from static object data
        # The Object contains the planetary rulerships (e.g., Mars rules Aries and Scorpio)
        rules_sign_objs = []
        rules_house_objs = []
        if obj and obj.rules_signs:
            for sign_name in obj.rules_signs:
                sign_obj = static.signs.get(sign_name)
                if sign_obj:
                    rules_sign_objs.append(sign_obj)

        return cls(
            object_name=obj,
            glyph=_str(row.get("Glyph")) or obj.glyph,
            longitude=lon,
            abs_deg=abs_deg,
            sign=sign,
            dms=dms,
            latitude=_float(row.get("Latitude")),
            declination=_float(row.get("Declination")),
            placidus_house=static.houses.get(placidus_house_num),
            equal_house=static.houses.get(equal_house_num),
            whole_sign_house=static.houses.get(whole_house_num),
            sabian_symbol=sabian_symbol,
            sabian_index=sabian_idx,
            dignity=row.get("Dignity"),
            ruled_by_sign=_str(row.get("Ruled by (sign)")),
            speed=_float(row.get("Speed")),
            distance=_float(row.get("Distance")),
            retrograde=bool(row.get("Retrograde Bool", False)),
            station=_str(row.get("Station")) or None,
            oob_status=_str(row.get("OOB Status")) or "No",
            rules_signs=rules_sign_objs,
            rules_houses=rules_house_objs,
            sign_ruler=_obj_list(row.get("Ruled by (sign)")),
            house_ruler_placidus=_obj_list(row.get("Placidus House Rulers")),
            house_ruler_equal=_obj_list(row.get("Equal House Rulers")),
            house_ruler_whole=_obj_list(row.get("Whole Sign House Rulers")),
            sign_index=_int_or_none(row.get("Sign Index")),
            degree_in_sign=_int_or_none(row.get("Degree In Sign")),
            minute_in_sign=_int_or_none(row.get("Minute In Sign")),
            second_in_sign=_int_or_none(row.get("Second In Sign")),
            fixed_star_conj=_str(row.get("Fixed Star Conj")) or None,
        )

@dataclass
class ChartSign:
    name: Sign
    glyph: str
    ruled_by: List[ChartObject]
    reception: List[ChartObject] = field(default_factory=list)
    
    # House placement (Placidus)
    ruling_placidus_house: str = ""        # The house cusp this sign sits on
    occupying_placidus_house: str = ""     # The house(s) this sign's 30° span falls into
    
    # House placement (Equal)
    ruling_equal_house: str = ""
    occupying_equal_house: str = ""
    
    # Interception Logic (Original)
    intercepted_by: Optional[str] = None               # The house that is intercepting this sign
    intercepts_house: Optional[str] = None             # The house that this sign is intercepting
    
    contains: list = field(default_factory=list) # Objects currently in this sign

@dataclass
class ChartAspect:
    aspect_type: Aspect
    object1: ChartObject
    object2: ChartObject
    angle: int
    orb: float
    applying: bool
    decl_diff: float
    overtaking: str
    reception: List[Union[Object, Aspect]] = field(default_factory=list)
    mutual_reception: bool = False 

@dataclass
class HouseCusp:
    """Represents a house cusp in an astrological chart."""

    cusp_number: int
    absolute_degree: float
    house_system: str

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility."""
        sys_key = (self.house_system or "placidus").strip().lower()
        system_map = {
            "placidus": "Placidus",
            "equal": "Equal",
            "whole": "Whole Sign",
            "whole sign": "Whole Sign",
            "wholesign": "Whole Sign",
        }
        label = system_map.get(sys_key, "Placidus")
        return {
            "Object": f"{label} {self.cusp_number}H cusp",
            "Longitude": self.absolute_degree,
        }

@dataclass
class ChartHouse:
    number: House
    house_system: HouseSystem     # e.g., "Placidus", "Equal", "Whole Sign"
    
    # Cusp & Boundaries
    cusp: HouseCusp
    cusp_deg: float       # Degree within the sign (0-29.99)
    cusp_sign: Sign        # e.g., "Gemini"
    end_deg: float        # Where the next house begins
    
    # Sign Relationships
    occupying_sign: Sign   # Primary sign in the house
    intercepts_sign: Sign  # If the house swallows a whole sign
    intercepted_by: Sign   # If a sign swallows the whole house
    
    # Contents & Interaction
    contains: List[ChartObject] = field(default_factory=list) # List of ChartObjects
    reception: List[ChartObject] = field(default_factory=list)
    
    instructions: str = ""

@dataclass
class ClusterAspect:
    name: List[ChartObject]
    object1: List[ChartObject]  # e.g., ["Sun", "Mercury"]
    object2: List[ChartObject]  # e.g., ["Jupiter"] if aspecting a cluster, or another list
    angle: int
    orb: float
    overtaking: str
    cluster_aspect_instructions: str

@dataclass
class ChartAxis:
    name: Axis                   # e.g., "Taurus-Scorpio Axis"
    
    # Sign Polarity
    sign1: ChartSign                  # e.g., "Taurus"
    sign1_contains: List[ChartObject]   # e.g., ["Sun", "Mercury"]
    
    sign2: ChartSign                  # e.g., "Scorpio"
    sign2_contains: List[ChartObject]   # e.g., ["Jupiter"]
    
    # House Polarity (Dynamic based on House System)
    house1: House                 # e.g., "2" or "2nd House"
    house2: House                 # e.g., "8" or "8th House"
    
    # Direct Interactions
    # List of ChartAspect names or objects for specific 180° hits
    exact_oppositions: List[Union[ChartObject, ChartAspect]] = field(default_factory=list) 

    # Special Points (matching GLYPHS in lookup_v2.py)
    # e.g., ["Ascendant", "Descendant"]
    compass_axis: bool = False
    
    instructions: str = ""

@dataclass
class ChartCompassAxis:
    compass_data: CompassAxis
    point_1: ChartObject
    point_2: ChartObject
    # These would store names of ChartObjects (e.g., ["Mars", "Sun"])
    point_1_conjunctions: List[ChartObject] = field(default_factory=list)
    point_2_conjunctions: List[ChartObject] = field(default_factory=list)

@dataclass
class Cluster:
    name: str
    glyph: str
    sign: ChartSign
    members: List[ChartObject] = field(default_factory=list)
    degree: float = 0.0

@dataclass
class Kite: 
    name: str # e.g., "Kite" (if there is only one in the chart), "Kite 1", "Kite 2"
    glyph: str

    node_1: PatternNode
    trine_1_2: List[ChartAspect]
    sextile_apex_1: List[ChartAspect]

    node_2: PatternNode
    trine_2_3: List[ChartAspect]
    opposite_apex_2: List[ChartAspect]

    node_3: PatternNode
    trine_1_3: List[ChartAspect]
    sextile_apex_3: List[ChartAspect]

    apex: PatternNode

    meaning: str = ""
#where node_1, node_2, and node_3 form a Grand Trine, and apex opposes node_2 and sextiles node_1 and node_3 

@dataclass
class MysticRectangle:
    name: str # e.g., "Mystic Rectangle" (if there is only one in the chart), "Mystic Rectangle 1", "Mystic Rectangle 2"
    glyph: str

    node_1: PatternNode
    trine_1_2: List[ChartAspect]
    sextile_1_4: List[ChartAspect]
    opposite_1_3: List[ChartAspect]

    node_2: PatternNode
    sextile_2_3: List[ChartAspect]
    opposite_2_4: List[ChartAspect]

    node_3: PatternNode
    trine_3_4: List[ChartAspect]

    node_4: PatternNode

    meaning: str = ""
#where node_1 opposing node_3, node_2 opposing node_4, node_1 trining node_2 and sextiling node_4, and node_3 trines node_4 and sextiles node_2

@dataclass
class Envelope:
    name: str # e.g., "Envelope" (if there is only one in the chart), "Envelope 1", "Envelope 2"
    glyph: str
    node_1: PatternNode
    sextile_1_2: List[ChartAspect]
    trine_1_3: List[ChartAspect]
    opposite_1_4: List[ChartAspect]

    node_2: PatternNode
    sextile_2_3: List[ChartAspect]
    trine_2_4: List[ChartAspect]
    opposite_2_5: List[ChartAspect]
    
    node_3: PatternNode
    sextile_3_4: List[ChartAspect]
    trine_3_5: List[ChartAspect]
    
    node_4: PatternNode
    sextile_4_5: List[ChartAspect]

    node_5: PatternNode
    sextile_5_1: List[ChartAspect]
    meaning: str = ""
#where all five nodes are in a continuous string of sextiles, with node_1 opposing node_4, and node_2 opposing node_5

@dataclass
class Merkabah:
    name: str # e.g., "Merkabah" (if there is only one in the chart), "Merkabah 1", "Merkabah 2"
    glyph: str

    node_1: PatternNode
    sextile_1_2: List[ChartAspect]
    trine_1_3: List[ChartAspect]
    opposite_1_4: List[ChartAspect]

    node_2: PatternNode
    sextile_2_3: List[ChartAspect]
    trine_2_4: List[ChartAspect]
    opposite_2_5: List[ChartAspect]

    node_3: PatternNode
    sextile_3_4: List[ChartAspect]
    trine_3_5: List[ChartAspect]
    opposite_3_6: List[ChartAspect]

    node_4: PatternNode
    sextile_4_5: List[ChartAspect]
    trine_4_6: List[ChartAspect]

    node_5: PatternNode 
    sextile_5_6: List[ChartAspect]
    trine_5_1: List[ChartAspect]

    node_6: PatternNode
    sextile_6_1: List[ChartAspect]
    trine_6_2: List[ChartAspect]
    meaning: str = ""
#where node_1, node_2, and node_3 form a Grand Trine, node_4, node_5, and node_6 form a second Grand Trine, and node_1, node_2, node_3, node_4, node_5, and node_6 form a continuous loop of sextiles, with node_4 opposing node_2, node_5 opposing node_3, and node_6 opposing node_1

@dataclass 
class Yod:
    name: str # e.g., "Yod" (if there is only one in the chart), "Yod 1", "Yod 2"
    glyph: str

    base_1: PatternNode
    sextile_1_2: List[ChartAspect]

    base_2: PatternNode

    apex: PatternNode
    quincunx_apex_1: List[ChartAspect]
    quincunx_apex_2: List[ChartAspect]

    meaning: str = ""
#where apex quincunxes both base_1 and base_2, and base_1 sextiles base_2

@dataclass
class WideYod:
    name: str # e.g., "Wide Yod" (if there is only one in the chart), "Wide Yod 1", "Wide Yod 2"
    glyph: str

    base_1: PatternNode
    square_1_2: List[ChartAspect]
    base_2: PatternNode
    
    apex: PatternNode
    sesqui_apex_1: List[ChartAspect]
    sesqui_apex_2: List[ChartAspect]

    meaning: str = ""
#where apex sesquisquares both base_1 and base_2, and base_1 squares base_2

@dataclass
class Cradle:
    name: str # e.g., "Cradle" (if there is only one in the chart), "Cradle 1", "Cradle 2"
    glyph: str
    
    node_1: PatternNode
    sextile_1_2: List[ChartAspect]
    trine_1_3: List[ChartAspect]
    opposite_1_4: List[ChartAspect]

    node_2: PatternNode
    sextile_2_3: List[ChartAspect]
    trine_2_4: List[ChartAspect]
    
    node_3: PatternNode
    sextile_3_4: List[ChartAspect]

    node_4: PatternNode
    meaning: str = ""
#where node_1, node_2, node_3, and node_4 form a string of sextiles, with node_1 opposing node_4, node_2 trining node_4, and node_1 trining node_3

@dataclass
class GrandTrine:
    name: str # e.g., "Grand Trine" (if there is only one in the chart), "Grand Trine 1", "Grand Trine 2"
    glyph: str

    node_1: PatternNode
    trine_1_2: List[ChartAspect]

    node_2: PatternNode
    trine_2_3: List[ChartAspect]

    node_3: PatternNode
    trine_1_3: List[ChartAspect]

    meaning: str = ""
#where each node trines both of the other nodes

@dataclass
class LightningBolt:
    name: str # e.g., "Lightning Bolt" (if there is only one in the chart), "Lightning Bolt 1", "Lightning Bolt 2"
    glyph: str
    node_1: PatternNode
    trine_1_2: List[ChartAspect]
    quincunx_1_3: List[ChartAspect]

    node_2: PatternNode
    square_2_3: List[ChartAspect]

    node_3: PatternNode
    trine_3_4: List[ChartAspect]

    node_4: PatternNode
    square_1_4: List[ChartAspect]

    meaning: str = ""
#where node_1 trines node_2, node_2 squares node_3, node_3 trines node_4, node_4 squares node_1, and node_1 quincunxes node_3

@dataclass
class Unnamed:
    name: str
    node_1: PatternNode
    trine_1_2: List[ChartAspect]

    node_2: PatternNode
    square_2_3: List[ChartAspect]

    node_3: PatternNode
    quincunx_1_3: List[ChartAspect]

    meaning: str = ""
#where node_1 trines node_2, node_2 squares node_3, and node_3 quincunxes node_1

@dataclass
class TSquare:
    name: str # e.g., "T-Square" (if there is only one in the chart), "T-Square 1", "T-Square 2"
    glyph: str

    base_1: PatternNode
    opposite_1_2: List[ChartAspect]
    square_apex_1: List[ChartAspect]

    base_2: PatternNode
    square_apex_2: List[ChartAspect]

    apex: PatternNode

    meaning: str = ""
#where apex squares both base_1 and base_2, and base_1 opposes base_2

@dataclass
class GrandCross:
    name: str # e.g., "Grand Cross" (if there is only one in the chart), "Grand Cross 1", "Grand Cross 2"
    glyph: str

    node_1: PatternNode
    square_1_2: List[ChartAspect]
    square_1_4: List[ChartAspect]
    opposite_1_3: List[ChartAspect]

    node_2: PatternNode
    square_2_3: List[ChartAspect]
    opposite_2_4: List[ChartAspect]

    node_3: PatternNode
    square_3_4: List[ChartAspect]

    node_4: PatternNode

    meaning: str = ""
#where node_1 squares node_2 and node_4 and opposes node_3, node_2 opposes node_4, and node_3 squares node_2 and node_4

ChartShape = Union[Kite, Yod, Merkabah, GrandTrine, TSquare, GrandCross, MysticRectangle, Envelope, Cradle, LightningBolt, Unnamed]

@dataclass
class ShapeConnect:
    # originally intended to describe two shapes that share some symmetries;
    # use direct ChartShape references rather than attempting to subscript str.
    shape_1: ChartShape
    shape_2: ChartShape
    shared_aspects: List[Union[ChartAspect, ClusterAspect]]
    shared_nodes: List[PatternNode]
    close_aspects: List[Union[ChartAspect, ClusterAspect]]
    close_nodes: List[PatternNode]
    connecting_aspects: List[Union[ChartAspect, ClusterAspect]]
    remainder_aspects: List[Union[ChartAspect, ClusterAspect]]


@dataclass
class Circuit:
    name: str
    members: List[ChartObject] = field(default_factory=list)
    shapes: List[ChartShape] = field(default_factory=list)
    remainders: List[ChartObject] = field(default_factory=list)

@dataclass
class ChartPatterns:
    # We use Union here so the shapes list can hold Kites, Yods, etc.
    circuits: List['Circuit'] = field(default_factory=list)
    shapes: List[ChartShape] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)
    single_planets: List['ChartObject'] = field(default_factory=list)

@dataclass
class CircuitConnect:
    circuit_a: Circuit
    circuit_b: Circuit
    connecting_aspects: List[Union[ChartAspect, ClusterAspect]]


# ─────────────────────────────────────────────────────────────────────────────
# Circuit Power Simulation — produced by circuit_sim.py
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CircuitNode:
    """One planet/point inside the circuit simulation."""
    planet_name: str
    # Raw scores from dignity_calc (may be None for un-scored points)
    raw_authority: float = 0.0          # Vector A
    raw_potency: float = 0.0            # Vector B
    power_index: float = 0.0            # combined PI from PlanetaryState
    # Post-simulation flow values
    received_power: float = 0.0         # total power flowing INTO this node
    emitted_power: float = 0.0          # total power flowing OUT of this node
    friction_load: float = 0.0          # heat dissipated by friction edges
    # Role flags
    is_source: bool = False             # True for South Node
    is_sink: bool = False               # True for North Node
    is_mutual_reception: bool = False   # True if part of a mutual reception pair
    # Net effective power = power_index + received_power − friction_load
    effective_power: float = 0.0


@dataclass
class CircuitEdge:
    """One aspect wire connecting two CircuitNodes."""
    node_a: str                          # planet name
    node_b: str                          # planet name
    aspect_type: str                     # e.g. "Trine"
    conductance: float = 1.0             # from ASPECT_CONDUCTANCE
    flow_direction: str = "bidirectional"  # "a→b", "b→a", or "bidirectional"
    transmitted_power: float = 0.0       # actual power flowing through this edge
    friction_heat: float = 0.0           # loss on Square / Opposition edges
    # Quincunx rerouting fields
    is_arc_hazard: bool = False          # True if this is a Quincunx edge
    is_rerouted: bool = False            # True if alternative path was found
    reroute_path: List[str] = field(default_factory=list)  # [nodeA, mid1, …, nodeB]
    is_open_arc: bool = False            # True if no reroute path exists


@dataclass
class ShapeCircuit:
    """Simulation result for one detected astrological shape."""
    shape_type: str                      # "Grand Trine", "T-Square", etc.
    shape_id: int                        # matches shape dict id from patterns_v2
    # Participating nodes and edges
    nodes: List[CircuitNode] = field(default_factory=list)
    edges: List[CircuitEdge] = field(default_factory=list)
    # Aggregate flow metrics
    total_throughput: float = 0.0        # sum of all transmitted_power values
    total_friction: float = 0.0          # sum of all friction_heat values
    # Notable nodes
    dominant_node: str = ""              # planet with highest effective_power
    bottleneck_node: str = ""            # planet with highest friction_load
    # Shape-level characterization
    resonance_score: float = 0.0         # 0–1, how harmonically resonant the shape is
    friction_score: float = 0.0          # 0–1, how much tension the shape carries
    flow_characterization: str = ""      # human-readable topology description
    # Membrane classification — "drum_head", "resonant_membrane", or "" (none)
    membrane_class: str = ""
    # Quincunx findings
    quincunx_routes: List[CircuitEdge] = field(default_factory=list)   # rerouted arcs
    open_arcs: List[CircuitEdge] = field(default_factory=list)         # unresolvable arcs


@dataclass
class CircuitSimulation:
    """Top-level result of the circuit power simulation for a chart."""
    # Per-shape circuit results
    shape_circuits: List[ShapeCircuit] = field(default_factory=list)
    # All nodes across all shapes (union; planets may appear in multiple shapes)
    node_map: Dict[str, CircuitNode] = field(default_factory=dict)
    # Directional SN→NN flow path (list of planet names from SN to NN)
    sn_nn_path: List[str] = field(default_factory=list)
    # Planets not in any shape (floating singletons)
    singletons: List[str] = field(default_factory=list)
    # Mutual reception pairs boosted during simulation
    mutual_receptions: List[tuple] = field(default_factory=list)


@dataclass
class DetectedShape:
    """A geometric pattern detected in a chart's aspect graph.

    Produced by ``patterns_v2.detect_shapes()``.  Each instance encodes one
    multi-planet configuration (Grand Trine, Mystic Rectangle, Yod, etc.)
    identified within a connected component of the major-aspect graph.

    Replaces the ad-hoc dict format ``{"id": …, "type": …, "members": …,
    "edges": …}`` previously returned by detect_shapes.
    """
    shape_id: int                               # unique id within this chart
    shape_type: str                             # e.g. "Grand Trine", "Mystic Rectangle"
    parent: int                                 # index into chart.aspect_groups
    members: List[str]                          # planet/point names involved
    edges: List[Any]                            # list of ((node_a, node_b), aspect_type)
    suppresses: Optional[Any] = None            # internal suppression metadata

    @property
    def name(self) -> str:
        """Human-readable alias for shape_type."""
        return self.shape_type

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DetectedShape":
        """Create a DetectedShape from a patterns_v2 shape dict."""
        return cls(
            shape_id=int(d["id"]),
            shape_type=str(d["type"]),
            parent=int(d.get("parent", 0)),
            members=list(d.get("members", [])),
            edges=list(d.get("edges", [])),
            suppresses=d.get("suppresses"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise back to dict form (for JSON export or legacy callers)."""
        d: Dict[str, Any] = {
            "id": self.shape_id,
            "type": self.shape_type,
            "parent": self.parent,
            "members": list(self.members),
            "edges": self.edges,
        }
        if self.suppresses is not None:
            d["suppresses"] = self.suppresses
        return d

    # ── Mapping interface ─────────────────────────────────────────────
    # Allows legacy callers (drawing_v2, circuit_sim, etc.) that use
    # shape["id"], shape.get("members", []) etc. to continue working
    # without modification.  The canonical attrs (shape_type, shape_id)
    # remain the primary interface.
    _KEY_MAP: ClassVar[Dict[str, str]] = {
        "id":         "shape_id",
        "type":       "shape_type",
        "members":    "members",
        "edges":      "edges",
        "parent":     "parent",
        "suppresses": "suppresses",
    }

    def __getitem__(self, key: str) -> Any:
        attr = self._KEY_MAP.get(key, key)
        try:
            return getattr(self, attr)
        except AttributeError:
            raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


@dataclass
class AstrologicalChart:
    """Complete astrological chart with all celestial objects and house cusps."""

    objects: list[ChartObject]
    house_cusps: list[HouseCusp]
    chart_datetime: str
    timezone: str
    latitude: float
    longitude: float
    # Header/display metadata — populated at chart creation time so renderers
    # never need to reach back into session state for label data.
    display_name: str = field(default="")
    city: str = field(default="")
    unknown_time: bool = field(default=False)
    display_datetime: Optional[datetime.datetime] = field(default=None)
    patterns: ChartPatterns = field(default_factory=ChartPatterns)
    chart_signs: List["ChartSign"] = field(default_factory=list)
    chart_houses: List["ChartHouse"] = field(default_factory=list)

    # -----------------------------------------------------------------
    # Computed chart data — all post-processing results live here so that
    # session state only ever stores the AstrologicalChart object itself,
    # not a parallel bag of individual data fragments.
    # -----------------------------------------------------------------
    df_positions: Optional[pd.DataFrame] = field(default=None)        # was session "last_df"
    aspect_df: Optional[pd.DataFrame] = field(default=None)           # was "last_aspect_df"
    edges_major: list = field(default_factory=list)                    # was "edges_major"
    edges_minor: list = field(default_factory=list)                    # was "edges_minor"
    aspect_groups: list = field(default_factory=list)                  # was session "patterns" (connected components)
    shapes: List["DetectedShape"] = field(default_factory=list)        # was "shapes"
    filaments: list = field(default_factory=list)                      # was "filaments"
    singleton_map: dict = field(default_factory=dict)                  # was "singleton_map"
    combos: list = field(default_factory=list)                         # was "combos"
    positions: dict = field(default_factory=dict)                      # was "chart_positions" {name: degree}
    major_edges_all: list = field(default_factory=list)                # was "major_edges_all"
    dispositor_summary_rows: list = field(default_factory=list)        # was "dispositor_summary_rows"
    dispositor_chains_rows: list = field(default_factory=list)         # was "dispositor_chains_rows"
    conj_clusters_rows: list = field(default_factory=list)             # was "conj_clusters_rows"
    sect: Optional[str] = field(default=None)                          # was "last_sect"
    sect_error: Optional[str] = field(default=None)                    # was "last_sect_error"
    plot_data: Any = field(default=None)                               # was "DISPOSITOR_GRAPH_DATA"
    utc_datetime: Optional[datetime.datetime] = field(default=None)    # was "chart_dt_utc"

    # Planetary strength states — keyed by planet name
    planetary_states: Dict[str, "PlanetaryState"] = field(default_factory=dict)
    # Mutual reception loops detected during strength analysis
    mutual_receptions: list = field(default_factory=list)
    # Circuit power simulation result (populated by circuit_sim.simulate_and_attach)
    circuit_simulation: Optional["CircuitSimulation"] = field(default=None)

    def __getattr__(self, name: str):
        # Gracefully return None for fields that don't exist on cached instances
        # (e.g. after schema additions between hot-reloads / session resumes).
        return None

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert the chart to a pandas DataFrame.
        This maintains backward compatibility with the original function.
        """
        # Convert objects to dicts
        object_rows = [obj.to_dict() for obj in self.objects]
        cusp_rows = [cusp.to_dict() for cusp in self.house_cusps]

        # Create DataFrames
        base_df = pd.DataFrame(object_rows)
        cusp_df = pd.DataFrame(cusp_rows)

        # Concatenate
        return pd.concat([base_df, cusp_df], ignore_index=True)

    def get_object(self, name: str) -> Optional[ChartObject]:
        for obj in self.objects:
            if obj.object_name.name == name: # Access the .name of the Object
                return obj
        return None

    def get_planets(self) -> List[ChartObject]:
        return [
            obj for obj in self.objects
            if obj.object_name and obj.object_name.object_type in ("Planet", "Luminary")
        ]

    def get_angles(self) -> list[ChartObject]:
        angle_names = ["Ascendant", "MC", "Descendant", "IC"]
        # MUST check .name or it will fail
        return [obj for obj in self.objects if obj.object_name.name in angle_names]

    def get_asteroids(self) -> list[ChartObject]:
        asteroid_names = ["Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Pholus", "Eris", "Eros", "Psyche"]
        return [obj for obj in self.objects if obj.object_name.name in asteroid_names]

    def get_retrograde_objects(self) -> List[ChartObject]:
        # Simplified since retrograde is now a boolean
        return [obj for obj in self.objects if obj.retrograde]

    def get_out_of_bounds_objects(self, include_extreme: bool = True) -> List[ChartObject]:
        """Returns objects that are either 'Yes' or 'Extreme'."""
        targets = ["Yes", "Extreme"] if include_extreme else ["Yes"]
        return [obj for obj in self.objects if obj.oob_status in targets]

    def get_extreme_oob_objects(self) -> List[ChartObject]:
        """Returns only the highly anomalous 'Extreme' OOB objects."""
        return [obj for obj in self.objects if obj.oob_status == "Extreme"]

    def header_lines(self) -> tuple[str, str, str, str, str]:
        """Return (name, date_line, time_line, city, extra_line) for chart header rendering.

        Replaces the session-state reads previously scattered across drawing
        functions.  The returned tuple matches the _draw_header_on_figure*()
        call signature exactly.
        """
        name = self.display_name or "Untitled Chart"
        city_val = self.city or ""

        dt_obj = self.display_datetime
        if dt_obj:
            month_name = dt_obj.strftime("%B")
            day_str    = str(dt_obj.day)
            year_str   = str(dt_obj.year)
            date_str   = f"{month_name} {day_str}, {year_str}"
            h          = dt_obj.hour
            m          = dt_obj.minute
            ampm       = "AM" if h < 12 else "PM"
            h12        = 12 if (h % 12 == 0) else (h % 12)
            time_str   = f"{h12}:{m:02d} {ampm}"
        else:
            date_str = ""
            time_str = ""

        if self.unknown_time:
            # Special layout for charts with unknown birth time:
            # line1 = name, line2 = "AC = Aries 0° (default)",
            # line3 = date, line4 = "12:00 PM"
            return name, "AC = Aries 0° (default)", date_str, "12:00 PM", ""

        return name, date_str, time_str, city_val, ""

    def _build_chart_signs(self, static: Optional["StaticLookup"] = None) -> List["ChartSign"]:
        """Build ChartSign objects from chart's objects and static data."""
        if not static:
            return []
        
        chart_signs = []
        for sign_name, sign_obj in static.signs.items():
            # Find all objects in this sign
            objs_in_sign = [
                obj for obj in self.objects
                if obj.sign and obj.sign.name == sign_name
            ]
            
            # Find rulers of this sign
            rulers = []
            if sign_obj.rulers:
                for ruler_name in sign_obj.rulers:
                    ruler = static.objects.get(ruler_name)
                    if ruler:
                        # Find if this ruler is in the chart
                        chart_ruler = self.get_object(ruler_name)
                        if chart_ruler:
                            rulers.append(chart_ruler)
            
            # Create ChartSign
            chart_sign = ChartSign(
                name=sign_obj,
                glyph=sign_obj.glyph,
                ruled_by=rulers,
                contains=objs_in_sign,
            )
            chart_signs.append(chart_sign)
        
        return chart_signs

    def _build_chart_houses(self, static: Optional["StaticLookup"] = None, house_system: str = "placidus") -> List["ChartHouse"]:
        """Build ChartHouse objects from chart's objects, house cusps, and static data.
        
        Args:
            static: StaticLookup database (optional)
            house_system: Which house system to use ("placidus", "equal", "whole")
        
        Returns:
            List of ChartHouse objects for all 12 houses
        """
        if not static:
            return []
        
        chart_houses = []
        house_system_key = house_system.lower().strip()
        
        for house_num in range(1, 13):
            house_obj = static.houses.get(house_num)
            if not house_obj:
                continue
            
            # Find the house cusp matching this system and number
            house_cusp = None
            for cusp in self.house_cusps:
                if cusp.cusp_number == house_num and cusp.house_system.lower().startswith(house_system_key[0]):
                    house_cusp = cusp
                    break
            
            if not house_cusp:
                continue
            
            # Determine which attribute to use based on house_system
            if house_system_key.startswith("p"):  # Placidus
                house_attr = "placidus_house"
            elif house_system_key.startswith("e"):  # Equal
                house_attr = "equal_house"
            else:  # Whole Sign
                house_attr = "whole_sign_house"
            
            # Find all objects in this house
            objs_in_house = [
                obj for obj in self.objects
                if getattr(obj, house_attr, None) and 
                   getattr(getattr(obj, house_attr), "number", None) == house_num
            ]
            
            # Find the sign on the cusp
            cusp_degree = house_cusp.absolute_degree % 360
            cusp_sign = None
            for sign in static.signs.values():
                sign_start = (sign.sign_index - 1) * 30
                sign_end = sign_start + 30
                if sign_start <= cusp_degree < sign_end:
                    cusp_sign = sign
                    break
            
            if not cusp_sign:
                # Default to first sign if not found
                cusp_sign = static.signs.get("Aries", Sign(name="Aries", glyph="♈", sign_index=1, element=Element(name="Fire", glyph="🔥"), modality=Modality(name="Cardinal", glyph="→"), polarity=Polarity(name="Masculine", glyph="+")))
            
            # Create HouseSystem object if needed
            house_system_obj = HouseSystem(name=house_system.capitalize())
            
            # Create ChartHouse
            chart_house = ChartHouse(
                number=house_obj,
                house_system=house_system_obj,
                cusp=house_cusp,
                cusp_deg=cusp_degree % 30,
                cusp_sign=cusp_sign,
                end_deg=((cusp_degree + 30) % 360),
                occupying_sign=cusp_sign,
                intercepts_sign=Sign(name="", glyph="", sign_index=0, element=Element(name="", glyph=""), modality=Modality(name="", glyph=""), polarity=Polarity(name="", glyph="")),
                intercepted_by=Sign(name="", glyph="", sign_index=0, element=Element(name="", glyph=""), modality=Modality(name="", glyph=""), polarity=Polarity(name="", glyph="")),
                contains=objs_in_house,
            )
            chart_houses.append(chart_house)
        
        return chart_houses

    def _populate_rules_houses(self, static: Optional["StaticLookup"] = None, house_system: str = "placidus") -> None:
        """Populate rules_houses for each object based on which houses have their ruled signs on cusps.
        
        For example, if Mars rules Aries and Scorpio, and Aries is on your 5th house cusp
        and Scorpio is on your 11th, then Mars rules houses 5 and 11 (not 1 and 8).
        
        Args:
            static: StaticLookup database for sign/object lookups
            house_system: Which system to use ("placidus", "equal", "whole")
        """
        if not static:
            return
        
        # Determine which attribute to use based on house_system
        house_system_key = house_system.lower().strip()
        if house_system_key.startswith("p"):  # Placidus
            house_attr = "placidus_house"
        elif house_system_key.startswith("e"):  # Equal
            house_attr = "equal_house"
        else:  # Whole Sign
            house_attr = "whole_sign_house"
        
        # Build a map of sign name -> house number for this system
        sign_to_house: dict[str, int] = {}
        for cusp in self.house_cusps:
            if cusp.house_system.lower().startswith(house_system_key[0]):
                # Determine which sign is on this cusp
                cusp_degree = cusp.absolute_degree % 360
                for sign in static.signs.values():
                    sign_start = (sign.sign_index - 1) * 30
                    sign_end = sign_start + 30
                    if sign_start <= cusp_degree < sign_end:
                        sign_to_house[sign.name] = cusp.cusp_number
                        break
        
        # For each object, find which houses it rules based on its ruled signs
        for obj in self.objects:
            if not obj.object_name:
                continue
            
            obj_static = static.objects.get(obj.object_name.name)
            if not obj_static or not obj_static.rules_signs:
                continue
            
            ruled_houses = []
            for ruled_sign_name in obj_static.rules_signs:
                if ruled_sign_name in sign_to_house:
                    house_num = sign_to_house[ruled_sign_name]
                    house_obj = static.houses.get(house_num)
                    if house_obj and house_obj not in ruled_houses:
                        ruled_houses.append(house_obj)
            
            obj.rules_houses = ruled_houses

    def populate_chart_structure(self, static: Optional["StaticLookup"] = None, house_system: str = "placidus") -> None:
        """Populate chart_signs and chart_houses from chart objects and static data.
        
        Call this after creating the chart to enable access to organized sign/house data.
        
        Args:
            static: StaticLookup database (if None, structures will be empty)
            house_system: Which house system to use ("placidus", "equal", "whole")
        """
        self.chart_signs = self._build_chart_signs(static)
        self.chart_houses = self._build_chart_houses(static, house_system)
        self._populate_rules_houses(static, house_system)
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        chart_datetime: str = "",
        timezone: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        static: Optional["StaticLookup"] = None,
    ) -> "AstrologicalChart":
        if df is None or df.empty:
            return cls(
                objects=[],
                house_cusps=[],
                chart_datetime=chart_datetime,
                timezone=timezone,
                latitude=latitude,
                longitude=longitude,
            )

        obj_mask = ~df["Object"].astype(str).str.contains("cusp", case=False, na=False)
        obj_df = df.loc[obj_mask]
        cusp_df = df.loc[~obj_mask]

        objects = [ChartObject.from_dict(row, static=static) for _, row in obj_df.iterrows()]
        house_cusps = []
        for _, row in cusp_df.iterrows():
            obj = str(row.get("Object", "")).strip()
            lon = row.get("Longitude") or row.get("Computed Absolute Degree", 0.0)
            lon = float(lon)
            m = re.match(r"^\s*(?:Placidus|Equal|Whole\s*Sign)\s*(\d+)\s*H\s*cusp", obj, re.I)
            num = int(m.group(1)) if m else 1
            if "Placidus" in obj:
                sys_key = "placidus"
            elif "Equal" in obj:
                sys_key = "equal"
            elif "Whole" in obj:
                sys_key = "whole"
            else:
                sys_key = row.get("House System", "placidus")
            house_cusps.append(HouseCusp(cusp_number=num, absolute_degree=lon, house_system=sys_key))

        return cls(
            objects=objects,
            house_cusps=house_cusps,
            chart_datetime=chart_datetime,
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
        )

    @classmethod
    def from_dataframe_with_signs_houses(
        cls,
        df: pd.DataFrame,
        chart_datetime: str = "",
        timezone: str = "",
        latitude: float = 0.0,
        longitude: float = 0.0,
        static: Optional["StaticLookup"] = None,
        house_system: str = "placidus",
    ) -> "AstrologicalChart":
        """Create chart and populate chart_signs and chart_houses.
        
        This is the recommended method when you need access to organized sign/house data.
        """
        chart = cls.from_dataframe(
            df,
            chart_datetime=chart_datetime,
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
            static=static,
        )
        chart.populate_chart_structure(static=static, house_system=house_system)
        return chart

@dataclass
class RenderResult:
	# Existing Chart Drawing Fields
	fig: Any
	ax: Any
	positions: dict[str, float]
	cusps: list[float]
	visible_objects: list[str]

	selected_objects: list[str]

	drawn_major_edges: list[tuple[str, str, str]]
	drawn_minor_edges: list[tuple[str, str, str]]

	selected_edges: list[tuple[str, str, str]]

	active_objects: list[str]
	active_edges: list[tuple[str, str, str]]

	selection_glow_on: bool
	
	# ⬇️ Optional fields with defaults ⬇️
	patterns: Optional[List[List[str]]] = None
	shapes: Optional[List["DetectedShape"]] = None
	singleton_map: Optional[Dict[str, Any]] = None
	plot_data: Optional[Dict[str, Any]] = None

	# ⬇️ ADDED FIELDS FOR FLEXIBILITY (Bi-Wheel and Text Output) ⬇️
	# Text output from the rendering process (e.g., from shape summary)
	out_text: Optional[str] = None

	# Bi-Wheel specific data (for the outer chart)
	outer_positions: Optional[Dict[str, float]] = None
	outer_cusps: Optional[List[float]] = None

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
    house: House  # Changed from 'sign' to 'house'
    short_meaning: str
    environmental_impact: str = ""
    concrete_manifestation: str = ""
    strengths: Optional[str] = None
    challenges: Optional[str] = None
    objective: str = ""
    keywords: List[str] = field(default_factory=list)

def migrate_lookup_data():
    static = StaticLookup()

    # --- 1. THE TRIADS (Using ELEMENT, MODE, POLARITY imports) ---
    for name, data in ELEMENT.items():
        # Support both 'meaning' and 'short meaning' keys used in lookup
        short_meaning_val = data.get('meaning', data.get('short meaning', ''))
        long_meaning_val = data.get('long', data.get('long meaning', ''))
        static.elements[name] = Element(
            name=name,
            glyph=data.get('glyph', ''),
            short_meaning=short_meaning_val,
            long_meaning=long_meaning_val,
            remedy=data.get('remedy', ''),
            keywords=data.get('keywords', []),
            schematic=data.get('schematic', None),
            element_instructions=data.get('instructions', '')
        )
    
    for name, data in MODE.items():
        static.modalities[name] = Modality(
            name=name,
            glyph=data.get('glyph', ''),
            short_meaning=data.get('meaning', ''),
            keywords=data.get('keywords', []),
            schematic=data.get('schematic', None),
            modality_instructions=data.get('instructions', '')
        )

    for name, data in POLARITY.items():
        static.polarities[name] = Polarity(
            name=name,
            glyph=data.get('glyph', ''),
            short_meaning=data.get('meaning', ''),
            keywords=data.get('keywords', []),
            schematic=data.get('schematic', None),
            polarity_instructions=data.get('instructions', '')
        )

    # --- 2. SIGNS (Using SIGNS and SIGN_MEANINGS) ---
    # `SIGNS` in `lookup_v2.py` is a list of names; derive sign metadata from
    # other lookup tables (ELEMENT, MODE, POLARITY, PLANETARY_RULERS, DIGNITIES).
    for idx, name in enumerate(SIGNS):
        # SIGN_MEANINGS now provides structured data: {'meaning':..., 'keywords':..., 'instructions':...}
        sign_info = SIGN_MEANINGS.get(name, {})
        if isinstance(sign_info, dict):
            short_meaning = sign_info.get('meaning', '')
            raw_keywords = sign_info.get('keywords', [])
            sign_instructions = sign_info.get('instructions', '')
        else:
            short_meaning = sign_info if isinstance(sign_info, str) else ""
            raw_keywords = []
            sign_instructions = ''

        # Normalize keywords to a list (accept comma-separated strings, lists, or sets)
        if isinstance(raw_keywords, str):
            sign_keywords = [k.strip() for k in raw_keywords.split(',') if k.strip()]
        elif isinstance(raw_keywords, (list, tuple, set)):
            sign_keywords = [str(k).strip() for k in raw_keywords if str(k).strip()]
        else:
            sign_keywords = []

        # Determine element/modality/polarity by checking which group lists the sign
        element_name = next((e for e, v in ELEMENT.items() if name in v.get('signs', [])), None)
        modality_name = next((m for m, v in MODE.items() if name in v.get('signs', [])), None)
        polarity_name = next((p for p, v in POLARITY.items() if name in v.get('signs', [])), None)

        # Safely resolve objects from the previously created static maps (fallback to any available one)
        def resolve_or_first(mapping, key, fallback_name=None):
            if key and key in mapping:
                return mapping[key]
            if fallback_name and fallback_name in mapping:
                return mapping[fallback_name]
            # pick the first value if available
            return next(iter(mapping.values())) if mapping else None

        element_obj = resolve_or_first(static.elements, element_name, fallback_name='Fire')
        modality_obj = resolve_or_first(static.modalities, modality_name, fallback_name='Cardinal')
        polarity_obj = resolve_or_first(static.polarities, polarity_name, fallback_name='Yang')

        # Gather dignity info from the per-sign DIGNITIES structure
        sign_digs = DIGNITIES.get(name, {})
        exaltation_val = sign_digs.get('exaltation')
        detriment_val = sign_digs.get('detriment', []) or []
        fall_val = sign_digs.get('fall')

        # Compute glyph (prefer SIGN_GLYPH by index) and sign_index (from ZODIAC_NUMBERS when available)
        glyph_val = (SIGN_GLYPH[idx] if 'SIGN_GLYPH' in globals() and idx < len(SIGN_GLYPH) else GLYPHS.get(name, ""))
        try:
            # Use the explicit mapping provided by ZODIAC_NUMBERS (1..12)
            sign_index_val = int(ZODIAC_NUMBERS.get(name, str(idx+1)))
        except Exception:
            # fallback to positional index + 1 to be consistent with ZODIAC_NUMBERS
            sign_index_val = idx + 1

        # Populate anatomy fields from SIGN_ANATOMY when available
        anatomy = SIGN_ANATOMY.get(name, {}) if 'SIGN_ANATOMY' in globals() else {}
        body_part_val = anatomy.get('Body Part', '').strip() if isinstance(anatomy, dict) else ''
        gland_organ_val = anatomy.get('Glands and Organs', '').strip() if isinstance(anatomy, dict) else ''

        static.signs[name] = Sign(
            name=name,
            glyph=glyph_val,
            sign_index=sign_index_val,
            element=element_obj,
            modality=modality_obj,
            polarity=polarity_obj,
            rulers=PLANETARY_RULERS.get(name, []),
            exaltation=exaltation_val,
            detriment=detriment_val,
            fall=fall_val,
            short_meaning=short_meaning,
            long_meaning=sign_info.get('long', '') if isinstance(sign_info, dict) else "",
            keywords=sign_keywords,
            sign_instructions=sign_instructions,
            assoc_with_house=idx + 1,
            opposite_sign=SIGNS[(idx + 6) % len(SIGNS)],
            body_part=body_part_val,
            gland_organ=gland_organ_val
        )

    # --- 3. OBJECTS (Using LUMINARIES_AND_PLANETS, PLANETS_PLUS, etc.) ---
    # Build a complete object set by pulling names from multiple lookup sources
    all_names = set()

    # Primary maps
    if isinstance(PLANETS_PLUS, dict):
        all_names.update(PLANETS_PLUS.keys())
    if isinstance(MAJOR_OBJECTS, dict):
        all_names.update(MAJOR_OBJECTS.keys())

    # Include named objects from OBJECT_MEANINGS (instruments, mythics, etc.)
    if isinstance(OBJECT_MEANINGS, dict):
        all_names.update(OBJECT_MEANINGS.keys())

    # Additional lists/ordering that include objects
    try:
        seq = globals().get('ORDERED_OBJECTS_FOCUS')
        if seq:
            all_names.update(seq)
    except Exception:
        pass

    # Add LUMINARIES_AND_PLANETS (may be lowercase set/list)
    if isinstance(LUMINARIES_AND_PLANETS, (set, list, tuple)):
        for raw in LUMINARIES_AND_PLANETS:
            all_names.add(str(raw).title())

    # Now create Object entries for each unique name
    CATEGORY_ROLE_MAP = {
        "Character Profiles": "Character",
        "Instruments": "Instrument",
        "Personal Initiations": "Personal Initiation",
        "Mythic Journeys": "Mythic Journey",
        "Compass Coordinates": "Compass Coordinate",
        "Compass Needle": "Compass Needle",
        "Switches": "Switch",
        "Imprints": "Imprint"
    }

    for name in sorted(all_names):
        # Resolve an id preferring MAJOR_OBJECTS (this is the canonical swisseph id)
        sw_id = None
        if isinstance(MAJOR_OBJECTS, dict) and name in MAJOR_OBJECTS:
            sw_id = MAJOR_OBJECTS[name]
        elif isinstance(PLANETS_PLUS, dict) and name in PLANETS_PLUS:
            sw_id = PLANETS_PLUS[name]

        # Pull short and long meanings; LONG_OBJECT_MEANINGS may contain a
        # dict with additional metadata such as keywords.
        short_m = OBJECT_MEANINGS_SHORT.get(name, "")
        long_entry = OBJECT_MEANINGS.get(name, "")
        # If OBJECT_MEANINGS stores a dict, extract the 'meaning' field
        if isinstance(long_entry, dict):
            long_m = long_entry.get('meaning', '')
        else:
            long_m = long_entry

        # Determine keywords for the object from either lookup dict.
        kw_list: List[str] = []
        def _extract_keywords(val):
            if isinstance(val, dict):
                kw = val.get('keywords', [])
                return kw
            return []
        kw_val = _extract_keywords(long_entry) or _extract_keywords(LONG_OBJECT_MEANINGS.get(name, {}))
        if isinstance(kw_val, str):
            # comma-separated string -> list
            kw_list = [k.strip() for k in kw_val.split(',') if k.strip()]
        elif isinstance(kw_val, (list, tuple, set)):
            kw_list = list(kw_val)
        else:
            kw_list = []

        # Determine narrative role/category
        found_category = None
        for cat, members in CATEGORY_MAP.items():
            try:
                if name in members:
                    found_category = cat
                    break
            except Exception:
                # members might be a dict or other structure
                try:
                    if isinstance(members, (list, set, tuple)) and name in members:
                        found_category = cat
                        break
                except Exception:
                    continue
        narrative_role_val = CATEGORY_ROLE_MAP.get(found_category, 'Character')
        narrative_interp_val = CATEGORY_INSTRUCTIONS.get(found_category, '') if found_category else ''

        # Determine object type using explicit OBJECT_TYPE lookup mapping when available.
        # If lookup doesn't provide an answer, fall back to previous heuristics.
        obj_type = None
        if 'OBJECT_TYPE' in globals():
            # build reverse map once on first use
            if not hasattr(migrate_lookup_data, '_obj_type_map'):
                mapping = {}
                # translate plural categories into the literal choices allowed by Object
                category_map = {
                    "Luminaries": "Luminary",
                    "Planets": "Planet",
                    "Asteroids": "Asteroid",
                    "Centaurs": "Centaur",
                    "Dwarf Planets": "Dwarf Planet",
                    # compass points and calculated points are treated as calculated
                    "Compass points": "Calculated Point",
                    "Calculated Points": "Calculated Point",
                }
                for cat, members in OBJECT_TYPE.items():
                    target = category_map.get(cat, cat.rstrip('s'))
                    for n in members:
                        mapping[n] = target
                migrate_lookup_data._obj_type_map = mapping
            obj_type = migrate_lookup_data._obj_type_map.get(name)

        if obj_type is None:
            # fallback heuristics used previously
            if isinstance(sw_id, (int, float)):
                obj_type = 'Planet'
            elif isinstance(sw_id, str):
                obj_type = 'Calculated Point'
            else:
                obj_type = 'Planet' if (isinstance(LUMINARIES_AND_PLANETS, (set, list, tuple)) and name.lower() in LUMINARIES_AND_PLANETS) else 'Calculated Point'

        # Determine influence categories from MALEFICS and BENEFICS lookups
        influence_list = []
        try:
            if name in MALEFICS.get('malefics', set()):
                influence_list.append('malefic')
            if name in MALEFICS.get('semi-malefics', set()):
                influence_list.append('semi-malefic')
            if name in BENEFICS.get('benefics', set()):
                influence_list.append('benefic')
            if name in BENEFICS.get('semi-benefics', set()):
                influence_list.append('semi-benefic')
        except Exception:
            pass

        # Determine which signs this object rules by reverse-lookup in PLANETARY_RULERS
        ruled_signs = []
        if isinstance(PLANETARY_RULERS, dict):
            for sign_name, rulers_list in PLANETARY_RULERS.items():
                if isinstance(rulers_list, (list, tuple, set)):
                    if name in rulers_list:
                        ruled_signs.append(sign_name)
                elif isinstance(rulers_list, str) and name == rulers_list:
                    # Handle single string rulers (though PLANETARY_RULERS typically uses lists)
                    ruled_signs.append(sign_name)

        static.objects[name] = Object(
            name=name,
            swisseph_id=sw_id,
            glyph=GLYPHS.get(name, ""),
            abrev=ABREVIATED_PLANET_NAMES.get(name),
            short_meaning=short_m,
            long_meaning=long_m,
            narrative_role=narrative_role_val,
            narrative_interp=narrative_interp_val,
            object_type=obj_type,
            influence=influence_list,
            keywords=kw_list,
            rules_signs=ruled_signs
        )

    # --- 4. ASPECTS (Using ASPECTS and ASPECT_INTERP) ---
    for name, data in ASPECTS.items():
        interp = ASPECT_INTERP.get(name, "")

        # Prefer explicit short/sentence maps if present
        short_pref = SHORT_ASPECT_MEANINGS.get(name)
        sentence_pref = SENTENCE_ASPECT_MEANINGS.get(name, "")

        if isinstance(interp, dict):
            short_meaning = short_pref or interp.get('short', interp.get('long', ""))
            long_meaning = interp.get('long', "")
            keywords = interp.get('keywords', [])
        else:
            short_meaning = short_pref or (interp if isinstance(interp, str) else "")
            long_meaning = interp if isinstance(interp, str) else ""
            keywords = []

        # ASPECTS_BY_SIGN maps aspect name -> sign-interval string ("0","2","3","4","6")
        raw_interval = ASPECTS_BY_SIGN.get(name)
        sign_interval_val = int(raw_interval) if raw_interval is not None else None

        # SETNENCE_ASPECT_NAMES maps aspect name -> verb form (e.g. "trines", "is conjunct")
        sentence_name_val = SETNENCE_ASPECT_NAMES.get(name)

        recv = RECEPTION_SYMBOLS.get(name, {}) if 'RECEPTION_SYMBOLS' in globals() else {}
        static.aspects[name] = Aspect(
            name=name,
            glyph=data.get('glyph', ''),
            angle=data.get('angle', 0),
            orb=data.get('orb', 0),
            line_color=data.get('color', 'grey'),
            line_style=data.get('style', 'solid'),
            short_meaning=short_meaning,
            long_meaning=long_meaning,
            sentence_meaning=sentence_pref,
            keywords=keywords,
            aspect_instructions=data.get('instructions', ''),
            strengths=data.get('strengths', ''),
            risks=data.get('risks', ''),
            harmonic=data.get('harmonic', 1),
            reception_icon_orb=recv.get('by orb'),
            reception_icon_sign=recv.get('by sign'),
            sign_interval=sign_interval_val,
            sentence_name=sentence_name_val
        )

    # --- 5. MIGRATING HOUSES (Using HOUSE_INTERP and HOUSE_MEANINGS) ---
    for i in range(1, 13):
        interp = HOUSE_INTERP.get(i, "")
        meanings = HOUSE_MEANINGS.get(i, "")

        # Normalize 'interp' to dict/string and get house short meaning & keywords from HOUSE_MEANINGS
        if isinstance(interp, dict):
            schematic_val = interp.get('schematic', None)
            instructions_val = interp.get('instructions', '')
        else:
            schematic_val = interp if isinstance(interp, str) else None
            instructions_val = ''

        if isinstance(meanings, dict):
            short_meaning = meanings.get('meaning', meanings.get('short', ""))
            raw_kw = meanings.get('keywords', [])
            life_domain = meanings.get('domain', "")
        else:
            short_meaning = meanings if isinstance(meanings, str) else ""
            raw_kw = []
            life_domain = ""

        # normalize keywords to list like we did for signs; accepts comma-separated
        if isinstance(raw_kw, str):
            keywords = [k.strip() for k in raw_kw.split(',') if k.strip()]
        elif isinstance(raw_kw, (list, tuple, set)):
            keywords = [str(k).strip() for k in raw_kw if str(k).strip()]
        else:
            keywords = []

        # Long meaning comes from LONG_HOUSE_MEANINGS explicitly
        long_meaning_val = LONG_HOUSE_MEANINGS.get(i, "") if 'LONG_HOUSE_MEANINGS' in globals() else ""

        static.houses[i] = House(
            number=i,
            short_meaning=short_meaning,
            long_meaning=long_meaning_val,
            keywords=keywords,
            life_domain=life_domain,
            schematic=schematic_val,
            instructions=instructions_val
        )

    # --- 6. MIGRATING SABIAN SYMBOLS (Using JSON/SABIAN_SYMBOLS) ---
    # We store these in a nested dict or a flat list for quick lookup
    # Structure: static.sabian_symbols[sign_name][degree]
    static.sabian_symbols = {} # Adding a dynamic attribute for the lookup
    
    # Load from JSON file (fast) or fallback to lookup_v2 (slow)
    # Normalize both forms into static.sabian_symbols[sign][degree]
    static.sabian_symbols = {}
    _sabian_data = _load_sabian_symbols_json()
    for key, value in _sabian_data.items():
        def _extract_fields(symbol_entry):
            # symbol_entry may be a simple string or a dict with extra metadata
            if isinstance(symbol_entry, dict):
                # allow either spaced or underscored key names
                text = symbol_entry.get('sabian symbol', '') or symbol_entry.get('sabian_symbol', '') or symbol_entry.get('symbol', '')
                short = symbol_entry.get('short meaning', '') or symbol_entry.get('short_meaning', '')
                long = symbol_entry.get('long meaning', '') or symbol_entry.get('long_meaning', '')
                kw = symbol_entry.get('keywords', [])
                return text, short, long, kw
            else:
                # treat anything else as the raw text
                return str(symbol_entry), '', '', []

        if isinstance(key, tuple) and len(key) == 2:
            sign_name, deg = key
            static.sabian_symbols.setdefault(sign_name, {})
            text, short, longm, kw = _extract_fields(value)
            static.sabian_symbols[sign_name][int(deg)] = SabianSymbol(
                sign=sign_name,
                degree=int(deg),
                symbol=text,
                short_meaning=short,
                long_meaning=longm,
                keywords=kw if isinstance(kw, (list, tuple)) else [kw] if kw else []
            )
        else:
            sign_name = key
            static.sabian_symbols.setdefault(sign_name, {})
            degrees = value
            # `degrees` may be a dict mapping degree->text or a single string; handle both
            if isinstance(degrees, dict):
                for deg, symbol_text in degrees.items():
                    text, short, longm, kw = _extract_fields(symbol_text)
                    static.sabian_symbols[sign_name][int(deg)] = SabianSymbol(
                        sign=sign_name,
                        degree=int(deg),
                        symbol=text,
                        short_meaning=short,
                        long_meaning=longm,
                        keywords=kw if isinstance(kw, (list, tuple)) else [kw] if kw else []
                    )
            elif isinstance(degrees, str):
                # If a single string provided, store it at degree 1 as fallback
                static.sabian_symbols[sign_name][1] = SabianSymbol(
                    sign=sign_name,
                    degree=1,
                    symbol=degrees
                )
            else:
                # If it's an iterable list, assume index+1 mapping
                try:
                    for i, symbol_text in enumerate(degrees):
                        text, short, longm, kw = _extract_fields(symbol_text)
                        static.sabian_symbols[sign_name][i+1] = SabianSymbol(
                            sign=sign_name,
                            degree=i+1,
                            symbol=text,
                            short_meaning=short,
                            long_meaning=longm,
                            keywords=kw if isinstance(kw, (list, tuple)) else [kw] if kw else []
                        )
                except Exception:
                    # fallback: leave empty for this sign
                    continue
    
    # Backward compatibility: populate static.SABIAN_SYMBOLS with tuple keys
    # for code that uses SABIAN_SYMBOLS.get((sign, degree), "")
    static.SABIAN_SYMBOLS = {}
    for sign_name, degrees_dict in static.sabian_symbols.items():
        for degree, sabian_obj in degrees_dict.items():
            static.SABIAN_SYMBOLS[(sign_name, degree)] = sabian_obj.symbol if hasattr(sabian_obj, 'symbol') else str(sabian_obj)

    # --- 6.1 MIGRATING SIGN & HOUSE AXES ---
    # `static.axes` should include both the zodiacal axis interpretations defined
    # by SIGN_AXIS_INTERP and the house-number axis data from HOUSE_AXIS_INTERP.
    for axis_name, interp in SIGN_AXIS_INTERP.items():
        # axis_name looks like 'Aries-Libra'
        parts = [p.strip() for p in axis_name.split('-')]
        sign1 = static.signs.get(parts[0]) if parts else None
        sign2 = static.signs.get(parts[1]) if len(parts) > 1 else None
        short = interp if isinstance(interp, str) else interp.get('short', interp)
        long = interp if isinstance(interp, str) else interp.get('long', interp)
        static.axes[axis_name] = Axis(
            name=axis_name,
            sign1=sign1,
            sign2=sign2,
            short_meaning=short,
            long_meaning=long,
            keywords=[],
            schematic=None,
            axis_instructions=(interp.get('instructions', '') if isinstance(interp, dict) else ''),
            modality=None
        )

    for axis_name, interp in HOUSE_AXIS_INTERP.items():
        # axis_name looks like '1-7', we convert to sign names via SIGNS list
        parts = axis_name.split('-')
        try:
            h1 = int(parts[0])
            h2 = int(parts[1])
        except Exception:
            h1 = h2 = None
        sign1 = static.signs.get(SIGNS[h1-1]) if h1 and 1 <= h1 <= len(SIGNS) else None
        sign2 = static.signs.get(SIGNS[h2-1]) if h2 and 1 <= h2 <= len(SIGNS) else None
        short = interp if isinstance(interp, str) else interp.get('short', interp)
        long = interp if isinstance(interp, str) else interp.get('long', interp)
        static.axes[axis_name] = Axis(
            name=axis_name,
            sign1=sign1,
            sign2=sign2,
            short_meaning=short,
            long_meaning=long,
            keywords=[],
            schematic=None,
            axis_instructions=(interp.get('instructions', '') if isinstance(interp, dict) else ''),
            modality=None
        )

    # --- 7. MIGRATING COMPASS AXES (Using COMPASS_AXIS_INTERP) ---
    # Populate a simple compass_axes lookup from COMPASS_AXIS_INTERP
    for axis_name, interp in COMPASS_AXIS_INTERP.items():
        if isinstance(interp, dict):
            definition = interp.get('definition', interp.get('short', ""))
            instructions = interp.get('instructions', '')
        else:
            definition = interp if isinstance(interp, str) else ''
            instructions = ''
        static.compass_axes[axis_name] = CompassAxis(
            name=axis_name,
            definition=definition,
            instructions=instructions
        )

    # --- 7.5 ORDERED OBJECTS & HOUSE SYSTEM INTERP ---
    static.ordered_objects = list(ORDERED_OBJECTS_FOCUS)
    static.house_system_interp = {k: v for k, v in HOUSE_SYSTEM_INTERP.items()}

    # --- 8. MIGRATING SHAPE TEMPLATES (Using SHAPES) ---
    # SHAPES is a mapping from shape name -> {glyph, meaning, configuration}
    # We derive a node count heuristically from the configuration string and store a Shape.
    import re
    for shape_name, data in SHAPES.items():
        glyph = data.get('glyph', '') if isinstance(data, dict) else ''
        meaning = data.get('meaning', '') if isinstance(data, dict) else ''
        configuration = data.get('configuration', '') if isinstance(data, dict) else ''
        # find node numbers like node_1, node_2 ... and apex/base nodes
        node_nums = {int(n) for n in re.findall(r'node_(\d+)', configuration)}
        node_count = max(node_nums) if node_nums else 0
        # include apex/base as nodes if present
        if 'apex' in configuration:
            node_count += 1
        if 'base_1' in configuration or 'base 1' in configuration:
            node_count += 1
        if 'base_2' in configuration or 'base 2' in configuration:
            node_count += 1
        static.shapes[shape_name] = Shape(
            name=shape_name,
            glyph=glyph,
            nodes=node_count,
            configuration=configuration,
            meaning=meaning
        )

    # --- 9. MIGRATING OBJECT-SIGN COMBOS (Using JSON/OBJECT_SIGN_COMBO) ---
    # Load from JSON file (fast) or fallback to lookup_v2 (slow)
    _object_sign_data = _load_object_sign_combo_json()
    for combo_key, data in _object_sign_data.items():
        if not isinstance(data, dict):
            continue
        
        obj_name = data.get('object')
        sign_name = data.get('sign')
        
        # Resolve object and sign from static lookups
        obj = static.objects.get(obj_name) if obj_name else None
        sign = static.signs.get(sign_name) if sign_name else None
        
        # Extract dignity and dignity_interp - both plain strings or None
        dignity_val = data.get('dignity')  # e.g. "Domicile", "Exalted", "Fall", "Detriment"
        if dignity_val is not None and not isinstance(dignity_val, str):
            dignity_val = None
        dignity_interp_val = data.get('dignity_interp') if dignity_val else None
        if dignity_interp_val is not None and not isinstance(dignity_interp_val, str):
            dignity_interp_val = None

        # Extract and normalize keywords
        raw_keywords = data.get('keywords', [])
        if isinstance(raw_keywords, str):
            keywords = [k.strip() for k in raw_keywords.split(',') if k.strip()]
        elif isinstance(raw_keywords, (list, tuple, set)):
            keywords = [str(k).strip() for k in raw_keywords if str(k).strip()]
        else:
            keywords = []
        
        # Extract and normalize remediation_tips
        raw_tips = data.get('remediation_tips', [])
        if isinstance(raw_tips, str):
            remediation_tips = [t.strip() for t in raw_tips.split('\n') if t.strip()]
        elif isinstance(raw_tips, (list, tuple, set)):
            remediation_tips = [str(t).strip() for t in raw_tips if str(t).strip()]
        else:
            remediation_tips = []
        
        static.object_sign_combos[combo_key] = ObjectSign(
            object=obj,
            sign=sign,
            short_meaning=data.get('short_meaning', ''),
            dignity=dignity_val,
            dignity_interp=dignity_interp_val,
            behavioral_style=data.get('behavioral_style', ''),
            somatic_signature=data.get('somatic_signature'),
            shadow_expression=data.get('shadow_expression'),
            strengths=data.get('strengths'),
            challenges=data.get('challenges'),
            keywords=keywords,
            remediation_tips=remediation_tips
        )

    # --- 10. MIGRATING OBJECT-HOUSE COMBOS (Using JSON/OBJECT_HOUSE_COMBO) ---
    # Load from JSON file (fast) or fallback to lookup_v2 (slow)
    _object_house_data = _load_object_house_combo_json()
    for combo_key, data in _object_house_data.items():
        if not isinstance(data, dict):
            continue
        
        obj_name = data.get('object')
        house_name = data.get('house')
        
        # Resolve object and house from static lookups
        obj = static.objects.get(obj_name) if obj_name else None
        
        # Parse house number from "Nth House" string
        house_num = None
        if isinstance(house_name, str):
            # Extract number from "1st House", "2nd House", "3rd House", etc.
            import re as re_module
            match = re_module.match(r'(\d+)(?:st|nd|rd|th)?\s+House', house_name)
            house_num = int(match.group(1)) if match else None
        elif isinstance(house_name, int):
            house_num = house_name
        
        house = static.houses.get(house_num) if house_num else None
        
        # Extract and normalize keywords
        raw_keywords = data.get('keywords', [])
        if isinstance(raw_keywords, str):
            keywords = [k.strip() for k in raw_keywords.split(',') if k.strip()]
        elif isinstance(raw_keywords, (list, tuple, set)):
            keywords = [str(k).strip() for k in raw_keywords if str(k).strip()]
        else:
            keywords = []
        
        static.object_house_combos[combo_key] = ObjectHouse(
            object=obj,
            house=house,
            short_meaning=data.get('short_meaning', ''),
            environmental_impact=data.get('environmental_impact', ''),
            concrete_manifestation=data.get('concrete_manifestation', ''),
            strengths=data.get('strengths'),
            challenges=data.get('challenges'),
            objective=data.get('objective', ''),
            keywords=keywords
        )

    # ------------------------------------------------------------------
    # copy uppercase constants from models_v2 globals onto the lookup so
    # callers can continue to reference legacy tables (colors, glyph maps,
    # aliases, etc.) directly off ``static_db``.  this mirrors the data that
    # originally lived in lookup_v2 and will be helpful while migrating code.
    for _name, _val in list(globals().items()):
        if _name.isupper():
            try:
                setattr(static, _name, _val)
            except Exception:
                # ignore read-only / built-in names
                pass

    return static

static_db = migrate_lookup_data()


def load_static_lookup():
    """If a PostgreSQL instance is configured, populate ``static_db``
    from the database.  This mirrors ``db_access.load_static_from_db`` and
    mutates the existing global so callers need only import ``static_db``.
    """
    try:
        from db_access import load_static_from_db
    except ImportError:
        raise
    # perform the load and update the global object in-place
    new_db = load_static_from_db()
    # copy attributes over to keep any existing references alive
    static_db.__dict__.update(new_db.__dict__)
    return static_db

if __name__ == "__main__":
    sample_sign = static_db.signs.get('Aries')
    print('Sample sign (Aries):', sample_sign)
    print('Sample house:', static_db.houses.get(1))
    print('Sample object (Black Moon Lilith (Mean)):', static_db.objects.get('Black Moon Lilith (Mean)'))
    print('Sample aspect (Trine):', static_db.aspects.get('Trine'))
    print('Sample shape (Grand Trine):', static_db.shapes.get('Grand Trine'))
    print('Sample sabian symbol (Cancer 11°):', static_db.sabian_symbols.get('Cancer', {}).get(11))



