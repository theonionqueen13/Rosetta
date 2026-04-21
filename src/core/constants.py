"""
src/core/constants.py — Runtime utility constants.

Small, import-time constants used by UI modules and the rendering layer.
These are NOT domain data loaded from PostgreSQL — they are structural
constants, lookup glyphs, colour palettes, and body/aspect catalogues
that are defined once and read-only at runtime.

For domain data (sign meanings, house interps, object combos, Sabian
symbols, etc.), use ``static_db`` loaded from Supabase at startup.

Migration-only source data lives in ``src/core/static_data.py``.

Import guide
------------
Runtime code  → ``from src.core.constants import MONTH_NAMES, GLYPHS, ...``
Rendering     → ``static_db.ATTRIBUTE_NAME``   (set by static_models.py setattr loop)
Migration     → ``from src.core.static_data import SABIAN_SYMBOLS, ...``
"""
import swisseph as swe

# ── Glyph map ─────────────────────────────────────────────────────────────
GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Chiron": "⚷", "Ceres": "⚳", "Pallas": "⚴", "Juno": "⚵", "Vesta": "⚶",
    "North Node": "☊", "South Node": "☋", "Part of Fortune": "⊗",
    "Black Moon Lilith (Mean)": "⚸",
    "Vertex": "☩", "Ascendant": "AC", "Descendant": "DC",
    "Psyche": "Ψ", "Eros": "♡",
    "Midheaven": "MC", "Imum Coeli": "IC",
}

# ── Ephemeris-backed objects ───────────────────────────────────────────────
EPHE_MAJOR_OBJECTS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "North Node": swe.TRUE_NODE,
    "South Node": -1,
    "Black Moon Lilith (Mean)": swe.MEAN_APOG,
    "Chiron": swe.CHIRON,
    "Ceres": swe.AST_OFFSET + 1,
    "Pallas": swe.AST_OFFSET + 2,
    "Juno": swe.AST_OFFSET + 3,
    "Vesta": swe.AST_OFFSET + 4,
    "Eris": swe.AST_OFFSET + 136199,
    "Eros": swe.AST_OFFSET + 433,
    "Psyche": swe.AST_OFFSET + 16,
}

ALL_MAJOR_PLACEMENTS = {
    **EPHE_MAJOR_OBJECTS,
    "AC": "ASC",
    "DC": "DC",
    "MC": "MC",
    "IC": "IC",
    "Vertex": "VERTEX",
    "Part of Fortune": "POF",
}

# Backward-compat alias
MAJOR_OBJECTS = ALL_MAJOR_PLACEMENTS

LUMINARIES_AND_PLANETS = {
    "sun", "moon", "mercury", "venus", "mars",
    "jupiter", "saturn", "uranus", "neptune", "pluto",
}

MALEFICS = {
    "malefics": {"Mars", "Saturn", "Pluto"},
    "semi-malefics": {
        "Neptune", "Uranus", "Chiron", "Eris", "Sedna",
        "Nessus", "Nemesis", "Black Moon Lilith (Mean)",
    },
}

BENEFICS = {
    "benefics": {"Venus", "Jupiter"},
    "semi-benefics": {
        "Mercury", "Moon", "Sun", "Ceres", "Pallas",
        "Juno", "Vesta", "Eros", "Psyche",
    },
}

PLANETS_PLUS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Uranus": swe.URANUS,
    "Neptune": swe.NEPTUNE,
    "Pluto": swe.PLUTO,
    "Black Moon Lilith (Mean)": swe.MEAN_APOG,
    "Chiron": swe.CHIRON,
}

TOGGLE_ASPECTS = {
    "North Node": swe.TRUE_NODE,
    "South Node": -1,
    "AC": "ASC",
    "MC": "MC",
    "Vertex": "VERTEX",
    "Part of Fortune": "POF",
    "Ceres": swe.AST_OFFSET + 1,
    "Pallas": swe.AST_OFFSET + 2,
    "Juno": swe.AST_OFFSET + 3,
    "Vesta": swe.AST_OFFSET + 4,
    "Eris": swe.AST_OFFSET + 136199,
    "Eros": swe.AST_OFFSET + 433,
    "Psyche": swe.AST_OFFSET + 16,
}

PLANETARY_RULERS = {
    "Aries": ["Mars"],
    "Taurus": ["Venus"],
    "Gemini": ["Mercury"],
    "Cancer": ["Moon"],
    "Leo": ["Sun"],
    "Virgo": ["Mercury", "Ceres"],
    "Libra": ["Venus"],
    "Scorpio": ["Pluto", "Mars"],
    "Sagittarius": ["Jupiter"],
    "Capricorn": ["Saturn"],
    "Aquarius": ["Uranus", "Saturn"],
    "Pisces": ["Neptune", "Jupiter"],
}

# ── Dignity tables ─────────────────────────────────────────────────────────
DIGNITY_MEANINGS = {
    "domicile": ["The planet is in its home sign — operating with full authority, comfort, and natural expression."],
    "detriment": ["The planet is in the sign opposite its home — it must work harder, adapt, and find unconventional pathways to express itself."],
    "exaltation": ["The planet is honored and elevated — its gifts are amplified and celebrated, though this can tip toward excess."],
    "fall": ["The planet is in the sign opposite its exaltation — its strengths are muted and must be rebuilt through effort and humility."],
    "triplicity": ["The planet has elemental kinship with this sign — a quiet, background support that operates through shared nature."],
    "term": ["The planet governs this specific degree range — a localized authority, like a neighborhood steward."],
    "face": ["The planet has minor dignity by decan — the weakest essential dignity, providing a thin but real thread of belonging."],
    "peregrine": ["The planet has no essential dignity whatsoever — it is a stranger in a foreign land, forced to rely entirely on accidental dignity and aspects."],
}

DIGNITY_SCORES = {
    "domicile": 5,
    "exaltation": 4,
    "triplicity": 3,
    "term": 2,
    "face": 1,
    "detriment": -5,
    "fall": -4,
    "peregrine": 0,
}

TRIPLICITY_RULERS = {
    "Fire":  {"day": "Sun",    "night": "Jupiter", "participating": "Saturn"},
    "Earth": {"day": "Venus",  "night": "Moon",    "participating": "Mars"},
    "Air":   {"day": "Saturn", "night": "Mercury", "participating": "Jupiter"},
    "Water": {"day": "Venus",  "night": "Mars",    "participating": "Moon"},
}

TERMS = {
    "Aries":       [(6, "Jupiter"), (12, "Venus"),   (20, "Mercury"), (25, "Mars"),    (30, "Saturn")],
    "Taurus":      [(8, "Venus"),   (14, "Mercury"), (22, "Jupiter"), (27, "Saturn"),  (30, "Mars")],
    "Gemini":      [(6, "Mercury"), (12, "Jupiter"), (17, "Venus"),   (24, "Mars"),    (30, "Saturn")],
    "Cancer":      [(7, "Mars"),    (13, "Venus"),   (19, "Mercury"), (26, "Jupiter"), (30, "Saturn")],
    "Leo":         [(6, "Jupiter"), (11, "Venus"),   (18, "Saturn"),  (24, "Mercury"), (30, "Mars")],
    "Virgo":       [(7, "Mercury"), (17, "Venus"),   (21, "Jupiter"), (28, "Mars"),    (30, "Saturn")],
    "Libra":       [(6, "Saturn"),  (14, "Mercury"), (21, "Jupiter"), (28, "Venus"),   (30, "Mars")],
    "Scorpio":     [(7, "Mars"),    (11, "Venus"),   (19, "Mercury"), (24, "Jupiter"), (30, "Saturn")],
    "Sagittarius": [(12, "Jupiter"),(17, "Venus"),   (21, "Mercury"), (26, "Saturn"),  (30, "Mars")],
    "Capricorn":   [(7, "Mercury"), (14, "Jupiter"), (22, "Venus"),   (26, "Saturn"),  (30, "Mars")],
    "Aquarius":    [(7, "Mercury"), (13, "Venus"),   (20, "Jupiter"), (25, "Mars"),    (30, "Saturn")],
    "Pisces":      [(12, "Venus"),  (16, "Jupiter"), (19, "Mercury"), (28, "Mars"),    (30, "Saturn")],
}

FACES = {
    "Aries":       ["Mars", "Sun",     "Venus"],
    "Taurus":      ["Mercury", "Moon", "Saturn"],
    "Gemini":      ["Jupiter", "Mars", "Sun"],
    "Cancer":      ["Venus", "Mercury","Moon"],
    "Leo":         ["Saturn", "Jupiter","Mars"],
    "Virgo":       ["Sun", "Venus",    "Mercury"],
    "Libra":       ["Moon", "Saturn",  "Jupiter"],
    "Scorpio":     ["Mars", "Sun",     "Venus"],
    "Sagittarius": ["Mercury", "Moon", "Saturn"],
    "Capricorn":   ["Jupiter", "Mars", "Sun"],
    "Aquarius":    ["Venus", "Mercury","Moon"],
    "Pisces":      ["Saturn", "Jupiter","Mars"],
}

# ── Sign-element reverse lookup ────────────────────────────────────────────
SIGN_ELEMENT = {
    "Aries": "Fire", "Leo": "Fire", "Sagittarius": "Fire",
    "Taurus": "Earth", "Virgo": "Earth", "Capricorn": "Earth",
    "Gemini": "Air", "Libra": "Air", "Aquarius": "Air",
    "Cancer": "Water", "Scorpio": "Water", "Pisces": "Water",
}

# ── Circuit conductance ────────────────────────────────────────────────────
ASPECT_CONDUCTANCE = {
    "Conjunction":  {"conductance": 1.0, "flow_type": "merge_amplify",      "harmonic": 1},
    "Trine":        {"conductance": 0.9, "flow_type": "effortless_flow",     "harmonic": 3},
    "Sextile":      {"conductance": 0.7, "flow_type": "engaged_flow",        "harmonic": 6},
    "Opposition":   {"conductance": 0.5, "flow_type": "polarized_split",     "harmonic": 2},
    "Sesquisquare": {"conductance": 0.4, "flow_type": "overflow_valve",      "harmonic": 8},
    "Semisextile":  {"conductance": 0.35,"flow_type": "pressure_release",    "harmonic": 12},
    "Square":       {"conductance": 0.3, "flow_type": "friction_work",       "harmonic": 4},
    "Quincunx":     {"conductance": 0.0, "flow_type": "arc_hazard_reroute",  "harmonic": None},
}

# ── Colour palettes ────────────────────────────────────────────────────────
GROUP_COLORS = [
    "#B80303", "#FF5100", "#FFAE00", "#53B800",
    "#0071BD", "#1D1FC5", "#6321CE", "#440101",
]
GROUP_COLORS_LIGHT = [
    "#B8030375", "#FF510075", "#FFAE0075", "#53B80075",
    "#0071BD75", "#1D20C575", "#6321CE75", "#44010175",
]
SUBSHAPE_COLORS = [
    "#FF5214FF", "#FFA600FF", "#FBFF00FF", "#87DB00FF",
    "#00B828FF", "#049167FF", "#006EFFFF", "#1100FFFF",
    "#6320FFFF", "#9E0099FF", "#FF00EAFF", "#720022FF",
    "#4B2C06FF", "#534546FF", "#C4A5A5FF", "#5F7066FF",
]
SUBSHAPE_COLORS_LIGHT = [
    "#FF521475", "#FFA60075", "#FBFF0075", "#87DB0075",
    "#00B82875", "#04916775", "#006EFF75", "#1100FF75",
    "#6320FF75", "#9E009975", "#FF00EA75", "#72002275",
    "#4B2C0675", "#53454675", "#C4A5A575", "#5F706675",
]
# Note: alpha-channel (75 suffix) version is the canonical one
SYNASTRY_COLORS_1 = [
    "#FF000075", "#FF5E0075", "#FF990075", "#FFD00075",
    "#AA7D0075", "#96550075", "#5E2D0075", "#44010175",
]
SYNASTRY_COLORS_2 = [
    "#2D9E0075", "#01F50D75", "#00D49575", "#00E1FF75",
    "#00A2FF75", "#0044FF75", "#46278F75", "#72529775",
]

# ── Sign catalogue ─────────────────────────────────────────────────────────
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

SIGN_ANATOMY = {
    "Aries":       {"Body Part": "Head, face",                               "Glands and Organs": "The suprarenals (adrenal gland), the eyes"},
    "Taurus":      {"Body Part": "Neck, throat, vocal cords",                "Glands and Organs": "Thyroid, sensory organs, tonsils"},
    "Gemini":      {"Body Part": "Arms, lungs, hands",                       "Glands and Organs": "Thymus, respiratory and nervous systems"},
    "Cancer":      {"Body Part": "Breasts, stomach, gallbladder",            "Glands and Organs": 'Mammary glands, body "containers" that retain water'},
    "Leo":         {"Body Part": "Heart, back, spine",                       "Glands and Organs": "Cardiac muscle, aorta, circulatory system"},
    "Virgo":       {"Body Part": "Intestines, abdomen",                      "Glands and Organs": "Digestive system, pancreas, spleen, lymphatic system"},
    "Libra":       {"Body Part": "Kidneys, bladder, lower back",             "Glands and Organs": "Endocrine system and glands, urinary system"},
    "Scorpio":     {"Body Part": "Reproductive organs, sexual organs, bowels","Glands and Organs": "Reproductive and elimination systems"},
    "Sagittarius": {"Body Part": "Hips, thighs",                             "Glands and Organs": "Liver, sciatic nerve, sacral plexus, hepatic system, pituitary gland"},
    "Capricorn":   {"Body Part": "\tKnees, bones, skin, teeth",              "Glands and Organs": "Skeletal system"},
    "Aquarius":    {"Body Part": "Ankles, calves, circulatory system",       "Glands and Organs": "\tPineal gland, blood, circulation system"},
    "Pisces":      {"Body Part": "Feet, toes",                               "Glands and Organs": "Lymphatic system, immune system, pituitary gland"},
}

ZODIAC_SIGNS = ["♈️", "♉️", "♊️", "♋️", "♌️", "♍️", "♎️", "♏️", "♐️", "♑️", "♒️", "♓️"]
SIGN_GLYPH = ZODIAC_SIGNS   # alias — identical list
ZODIAC_COLORS = ["red", "green", "#DAA520", "blue"] * 3
ZODIAC_NUMBERS = {
    "Aries": "1", "Taurus": "2", "Gemini": "3", "Cancer": "4",
    "Leo": "5", "Virgo": "6", "Libra": "7", "Scorpio": "8",
    "Sagittarius": "9", "Capricorn": "10", "Aquarius": "11", "Pisces": "12",
}

# ── Aspects table ──────────────────────────────────────────────────────────
_SEPTILE = 51 + 26 / 60
_BISEPT  = 102 + 52 / 60
_TRISEPT = 154 + 17 / 60

ASPECTS = {
    # ── Major ───────────────────────────────────────────────────────────────
    "Conjunction": {
        "angle": 0, "orb": 3, "aspect_type": "Major", "harmonic": 1,
        "color": "#888888", "style": "solid", "glyph": "☌",
        "strengths": "Conjunctions bring planets together, blending their energies into a unified force, often intensifying their effects.",
        "risks": "planets that don't get along well may be poor roommates; they need to learn to appreciate each other's differences.",
    },
    "Sextile": {
        "angle": 60, "orb": 3, "aspect_type": "Major", "harmonic": 6,
        "color": "purple", "style": "solid", "glyph": "⚹",
        "strengths": "Sextiles are harmonious like trines, but you have to engage them with your free will to make them connect; they don't automatically integrate like trines. This means that sextiles are opportunities to make your life better through active initiative.",
        "risks": "planets may become complacent and not push each other to grow.",
    },
    "Square": {
        "angle": 90, "orb": 3, "aspect_type": "Major", "harmonic": 4,
        "color": "red", "style": "solid", "glyph": "□",
        "strengths": "Squares are like the gears that run the machine; you will not get anywhere without them. Squares = work, and work is how we gain traction and momentum.",
        "risks": "planets may clash, leading to frustration and conflict, especially when involving malefics.",
    },
    "Trine": {
        "angle": 120, "orb": 3, "aspect_type": "Major", "harmonic": 3,
        "color": "blue", "style": "solid", "glyph": "△",
        "strengths": "Planets do not get more harmonious than this with each other. Trining planets understand each other perfectly, with no need for translation. The gifts of planets in trine work together as a combined force, which can be a source of strength and rapid or \"automatic\" intelligence in a given area.",
        "risks": "planets may become too comfortable, leading to laziness, or may lack understanding and patience for others who do not resonate.",
    },
    "Opposition": {
        "angle": 180, "orb": 3, "aspect_type": "Major", "harmonic": 2,
        "color": "red", "style": "solid", "glyph": "☍",
        "strengths": "A well-integrated opposition understands the full expanse of its dual polarities, allowing the native to transcend the limitations of its dualities. The opposition is the only aspect that touches the Earth on the chart. Without bridging opposites, there is no grounding.",
        "risks": "planets may create polarization and conflict, leading to a 'us vs them' mentality. Requires balance and compromise.",
    },
    # ── Minor (filaments) ────────────────────────────────────────────────────
    "Sesquisquare": {
        "angle": 135, "orb": 2, "aspect_type": "Minor", "harmonic": 8,
        "color": "orange", "style": "dotted", "glyph": "⚼",
        "strengths": "A sesquisquare is often the site of an innate talent, which functions like an overflow channel whenever certain conditions are met. These are those special personal talents which spring up to be used as soon as the need for them arises.",
        "risks": "planets may create tension and irritability, leading to impulsive actions without considering consequences. May be exploited by others.",
    },
    "Quincunx": {
        "angle": 150, "orb": 3, "aspect_type": "Minor", "harmonic": 12,
        "color": "green", "style": "dotted", "glyph": "⚻",
        "strengths": "Quincunxes are inherently frustrating, but their frustrating outcomes have the potential to protect us from much more terrible and catastrophic versions of the same, encouraging us to give up on what will never work and try a more creative, resourceful, and effective approach.",
        "risks": "planets may struggle to attempt direct integration, leading to stress, failures, and health issues if not managed properly. Must re-route through other aspects. Go around.",
    },
    "Semisextile": {
        "angle": 30, "orb": 2, "aspect_type": "Minor", "harmonic": 12,
        "color": "#C51DA1", "style": "dotted", "glyph": "⚺",
        "strengths": "Spiritual anesthesia for tough integrations. Painless, lighthearted, humorous processing of normally painful topics. A pressure release valve.",
        "risks": "planets may struggle to find common ground, leading to misunderstandings and missed opportunities for growth. Can disrupt the flow of material reality, inspiring spontenaeity that may not be grounded.",
    },
    # ── Harmonic ─────────────────────────────────────────────────────────────
    "Quintile":       {"angle": 72,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 5,  "color": "#9B59B6", "style": "dotted", "glyph": "Q",  "strengths": "", "risks": ""},
    "Biquintile":     {"angle": 144,       "orb": 2, "aspect_type": "Harmonic", "harmonic": 5,  "color": "#9B59B6", "style": "dotted", "glyph": "bQ", "strengths": "", "risks": ""},
    "Septile":        {"angle": _SEPTILE,  "orb": 2, "aspect_type": "Harmonic", "harmonic": 7,  "color": "#1ABC9C", "style": "dotted", "glyph": "S",  "strengths": "", "risks": ""},
    "Biseptile":      {"angle": _BISEPT,   "orb": 2, "aspect_type": "Harmonic", "harmonic": 7,  "color": "#1ABC9C", "style": "dotted", "glyph": "bS", "strengths": "", "risks": ""},
    "Triseptile":     {"angle": _TRISEPT,  "orb": 2, "aspect_type": "Harmonic", "harmonic": 7,  "color": "#1ABC9C", "style": "dotted", "glyph": "tS", "strengths": "", "risks": ""},
    "Semi-square":    {"angle": 45,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 8,  "color": "#E67E22", "style": "dotted", "glyph": "∠", "strengths": "", "risks": ""},
    "Novile":         {"angle": 40,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 9,  "color": "#3498DB", "style": "dotted", "glyph": "N",  "strengths": "", "risks": ""},
    "Binovile":       {"angle": 80,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 9,  "color": "#3498DB", "style": "dotted", "glyph": "bN", "strengths": "", "risks": ""},
    "Decile":         {"angle": 36,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 10, "color": "#F39C12", "style": "dotted", "glyph": "D",  "strengths": "", "risks": ""},
    "Vigintile":      {"angle": 18,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 10, "color": "#F39C12", "style": "dotted", "glyph": "Vg", "strengths": "", "risks": ""},
    "Undecile":       {"angle": 32.7272727,"orb": 2, "aspect_type": "Harmonic", "harmonic": 11, "color": "#8E44AD", "style": "dotted", "glyph": "U",  "strengths": "", "risks": ""},
    "Bi-undecile":    {"angle": 65.4545454,"orb": 2, "aspect_type": "Harmonic", "harmonic": 11, "color": "#8E44AD", "style": "dotted", "glyph": "bU", "strengths": "", "risks": ""},
    "Tri-undecile":   {"angle": 98.1818181,"orb": 2, "aspect_type": "Harmonic", "harmonic": 11, "color": "#8E44AD", "style": "dotted", "glyph": "tU", "strengths": "", "risks": ""},
    "Quad-undecile":  {"angle": 130.9090909,"orb":2, "aspect_type": "Harmonic", "harmonic": 11, "color": "#8E44AD", "style": "dotted", "glyph": "qU", "strengths": "", "risks": ""},
    "Vigintiseptile": {"angle": 15,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 24, "color": "#95A5A6", "style": "dotted", "glyph": "Vs", "strengths": "", "risks": ""},
    "Quindecile":     {"angle": 24,        "orb": 2, "aspect_type": "Harmonic", "harmonic": 24, "color": "#95A5A6", "style": "dotted", "glyph": "Qd", "strengths": "", "risks": ""},
}

RECEPTION_SYMBOLS = {
    "Conjunction": {"by orb": "blue_conjunction.png", "by sign": "green_conjunction.png"},
    "Sextile":     {"by orb": "blue_sextile.png",     "by sign": "green_sextile.png"},
    "Square":      {"by orb": "blue_square.png",      "by sign": "green_square.png"},
    "Trine":       {"by orb": "blue_trine.png",       "by sign": "green_trine.png"},
    "Opposition":  {"by orb": "blue_opposition.png",  "by sign": "green_opposition.png"},
}

_RECEPTION_ASPECTS = {
    "Conjunction": 0,
    "Sextile":     60,
    "Square":      90,
    "Trine":       120,
    "Opposition":  180,
}

ALIASES_MEANINGS = {
    "ASC":        "Ascendant",
    "AC":         "Ascendant",
    "DSC":        "Descendant",
    "MC":         "Midheaven",
    "IC":         "Imum Coeli",
    "True Node":  "North Node",
    "Black Moon Lilith": "Lilith",
}

ABREVIATED_PLANET_NAMES = {
    "Ascendant":               "AC",
    "Descendant":              "DC",
    "Midheaven":               "MC",
    "Imum Coeli":              "IC",
    "North Node":              "NN",
    "South Node":              "SN",
    "Part of Fortune":         "PoF",
    "Black Moon Lilith":       "Lilith",
    "Black Moon Lilith (Mean)":"Lilith",
}

OBJECT_TYPE = {
    "Luminaries": ["Sun", "Moon"],
    "Planets": ["Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"],
    "Asteroids": [
        "Ceres", "Pallas", "Juno", "Vesta", "Lilith",
        "Iris", "Hygiea", "Psyche", "Thalia", "Euterpe", "Pomona", "Polyhymnia",
        "Harmonia", "Isis", "Ariadne", "Mnemosyne", "Echo", "Niobe", "Eurydike",
        "Freia", "Terpsichore", "Minerva", "Hekate", "Zephyr", "Kassandra",
        "Lachesis", "Nemesis", "Medusa", "Aletheia", "Magdalena", "Arachne", "Fama",
        "Eros", "Veritas", "Sirene", "Siva", "Lilith (Asteroid)", "Copernicus",
        "Icarus", "Toro", "Apollo", "Koussevitzky", "Anteros", "Tezcatlipoca",
        "Bacchus", "Hephaistos", "Panacea", "Orpheus", "Kafka", "Pamela",
        "Dionysus", "Kaali", "Asclepius", "Singer", "Angel", "Typhon",
    ],
    "Centaurs": ["Chiron", "Hidalgo", "Nessus"],
    "Dwarf Planets": ["Varuna", "Ixion", "Quaoar", "Sedna", "Orcus", "Haumea", "Eris", "Makemake"],
    "Compass points": ["Ascendant", "Descendant", "MC", "IC", "North Node", "South Node"],
    "Calculated Points": ["Vertex", "Part of Fortune", "Black Moon Lilith"],
}

INTERP_FLAGS = {
    "Out of Bounds": (
        "Out of Bounds: This planet/object's energy is operating beyond typical solar influence, "
        "leading to an expression that is unconventional, extreme, potentially limitless, and can "
        "manifest as either extraordinary genius or volatile, out-of-character behavior."
    ),
    "Retrograde": (
        "Retrograde: Periods when a planet appears to move backward, revisiting recently learned "
        "lessons. Retrograde planets prompt introspection, reflection, and integration, preparing "
        "for a refined 'do-over' once the planet goes direct."
    ),
    "Station Point": (
        "Station Point: A planet at its station is intensified, frozen in place. Its energy becomes "
        "amplified and highly emphasized, often marking pivotal transition points."
    ),
    "Fixed Star": (
        "Fixed Star Conjunctions: Any fixed stars conjunct a planet lend their meaning and qualities "
        "to the placement. If a ruled body part is listed in the fixed star meaning, include it in "
        "the Character Profile output for that placement."
    ),
}

ORDERED_OBJECTS_FOCUS = [
    # Compass coordinates
    "Ascendant", "Descendant", "MC", "IC",
    # Compass needle
    "North Node", "South Node",
    # Characters (+ Pluto, Eris)
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "Eris",
    # Moved up
    "Ceres", "Pallas", "Juno", "Vesta",
    # Chiron before BML
    "Chiron", "Black Moon Lilith (Mean)",
    # Switches
    "Part of Fortune", "Vertex", "Anti-Vertex", "East Point",
    # Personal Initiations
    "Nessus", "Ixion",
    # Mythic Journeys
    "Hidalgo", "Varuna", "Typhon", "Quaoar", "Sedna", "Orcus", "Haumea", "Makemake",
    # Instruments
    "Iris", "Hygiea", "Psyche", "Thalia", "Euterpe", "Pomona", "Polyhymnia",
    "Harmonia", "Isis", "Ariadne", "Mnemosyne", "Echo", "Niobe", "Eurydike",
    "Freia", "Terpsichore", "Minerva", "Hekate", "Zephyr", "Kassandra", "Lachesis",
    "Nemesis", "Medusa", "Aletheia", "Magdalena", "Arachne", "Fama",
    "Eros", "Veritas", "Sirene", "Siva", "Lilith (Asteroid)", "Copernicus",
    "Icarus", "Toro", "Apollo", "Koussevitzky", "Osiris", "Lucifer", "Anteros",
    "Tezcatlipoca", "West", "Bacchus", "Hephaistos", "Panacea", "Orpheus",
    "Kafka", "Pamela", "Dionysus", "Kaali", "Asclepius", "Singer", "Angel",
]

CATEGORY_MAP = {
    "Character Profiles": {
        "Sun", "Moon", "Mercury", "Venus", "Mars",
        "Jupiter", "Saturn", "Uranus", "Neptune",
    },
    "Instruments": {
        "Ceres", "Pallas", "Juno", "Vesta",
        "Iris", "Hygiea", "Psyche", "Thalia", "Euterpe", "Pomona", "Polyhymnia",
        "Harmonia", "Isis", "Ariadne", "Mnemosyne", "Echo", "Niobe", "Eurydike",
        "Freia", "Terpsichore", "Minerva", "Hekate", "Zephyr", "Kassandra",
        "Lachesis", "Nemesis", "Medusa", "Aletheia", "Magdalena", "Arachne", "Fama",
        "Eros", "Veritas", "Sirene", "Siva", "Lilith (Asteroid 1181)", "Copernicus",
        "Icarus", "Toro", "Apollo", "Koussevitzky", "Osiris", "Lucifer", "Anteros",
        "Tezcatlipoca", "West", "Bacchus", "Hephaistos", "Panacea", "Orpheus",
        "Kafka", "Pamela", "Dionysus", "Kaali", "Asclepius", "Singer", "Angel",
    },
    "Personal Initiations": {"Chiron", "Nessus", "Ixion"},
    "Mythic Journeys": {
        "Pluto", "Hidalgo", "Varuna", "Typhon", "Quaoar",
        "Sedna", "Orcus", "Haumea", "Eris", "Makemake",
    },
    "Compass Coordinates": {"Ascendant", "Descendant", "MC", "IC"},
    "Compass Needle": {"True Node", "North Node", "South Node"},
    "Switches": {
        "Black Moon Lilith (Mean)", "Part of Fortune",
        "Vertex", "Anti-Vertex", "East Point",
    },
    "Imprints": {"Fixed Stars"},
}

CATEGORY_INSTRUCTIONS = {
    "Character Profiles":   "The primary agents. They have will, drive, and personality. Write their profiles as if they are characters acting within the chart's system. They initiate, choose, and embody functions.",
    "Instruments":          "Auxiliary tools or implements. They do not act on their own but modify, equip, or flavor the Characters they are attached to. Interpret them as specialized add-ons that enhance or qualify expression.",
    "Personal Initiations": "Threshold trials and initiatory guides. They mark points of personal wounding, apprenticeship, or rites of passage. Interpret them as initiations the native must undergo, often in embodied or psychological crisis form.",
    "Mythic Journeys":      "Terrains or landscapes. They are collective-scale mythic journeys that reshape the native's environment. Interpret them as deep fields of transformation that one must endure or traverse, not agents that act.",
    "Compass Coordinates":  "Orienting coordinate markers for the whole chart. They provide direction, aim, and framing. Interpret them as the chart's compass points, describing location, presentation, public face, and roots.",
    "Compass Needle":       "The chart's directional polarity. They mark the karmic vector between where the native has come from and where they are growing toward. Interpret them as the navigational axis of soul trajectory.",
    "Switches":             "Sensitive toggles or thresholds. They activate, invert, or flip circuits. Interpret them as switches that trigger growth arcs, release conditions, or polarity shifts.",
    "Imprints":             "Permanent marks from the heavens. They stamp the chart with mythic inheritance, often conferring unusual talents or fated qualities. Interpret them as imprints that 'hard-code' certain powers or vulnerabilities into the native's system.",
}

ASPECTS_BY_SIGN = {
    "Conjunction": "0",
    "Sextile":     "2",
    "Square":      "3",
    "Trine":       "4",
    "Opposition":  "6",
}

# ── UI utility constants ───────────────────────────────────────────────────
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

STANDARD_BASE_BODIES = frozenset({
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "Black Moon Lilith (Mean)", "Chiron",
})

SHAPE_NODE_COUNTS = {
    "Envelope": 5, "Grand Cross": 4, "Mystic Rectangle": 4,
    "Cradle": 4, "Kite": 4, "Lightning Bolt": 4,
    "Grand Trine": 3, "T-Square": 3, "Wedge": 3,
    "Sextile Wedge": 3, "Yod": 3, "Wide Yod": 3,
    "Unnamed": 3, "Remainder": 2,
}

# ── Interpretation constants (accessed via static_db.X in runtime code) ───

DIGNITIES = {
    "Aries":       {"domicile": ["Mars"],    "detriment": ["Venus"],   "exaltation": ["Sun"],     "fall": ["Saturn"]},
    "Taurus":      {"domicile": ["Venus"],   "detriment": ["Mars"],    "exaltation": ["Moon"],    "fall": []},
    "Gemini":      {"domicile": ["Mercury"], "detriment": ["Jupiter"], "exaltation": [],          "fall": []},
    "Cancer":      {"domicile": ["Moon"],    "detriment": ["Saturn"],  "exaltation": ["Jupiter"], "fall": ["Mars"]},
    "Leo":         {"domicile": ["Sun"],     "detriment": ["Saturn"],  "exaltation": [],          "fall": []},
    "Virgo":       {"domicile": ["Mercury"], "detriment": ["Jupiter"], "exaltation": ["Mercury"], "fall": ["Venus"]},
    "Libra":       {"domicile": ["Venus"],   "detriment": ["Mars"],    "exaltation": ["Saturn"],  "fall": ["Sun"]},
    "Scorpio":     {"domicile": ["Mars"],    "detriment": ["Venus"],   "exaltation": [],          "fall": ["Moon"]},
    "Sagittarius": {"domicile": ["Jupiter"], "detriment": ["Mercury"], "exaltation": [],          "fall": []},
    "Capricorn":   {"domicile": ["Saturn"],  "detriment": ["Moon"],    "exaltation": ["Mars"],    "fall": ["Jupiter"]},
    "Aquarius":    {"domicile": ["Saturn"],  "detriment": ["Sun"],     "exaltation": [],          "fall": []},
    "Pisces":      {"domicile": ["Jupiter"], "detriment": ["Mercury"], "exaltation": ["Venus"],   "fall": ["Mercury"]},
}

ELEMENT = {
    "Fire":  {"signs": ["Aries", "Leo", "Sagittarius"],   "glyph": "🔥", "short_meaning": "The Spark of Life & Vitality",    "long_meaning": "Fire is what runs the engine; it is drive, passion, inspiration, initative, excitement. Fire makes you want to get up and go, to do, to create.", "keywords": "Enthusiasm, ignite, spontaneous, radiant, courage, willpower, inspiration, dynamic, heat, direct, perform, passion, spirit, catalyst, bold, burning, authentic, identity", "remedy": "If you're feeling low on energy, engage in physical activity or spend time in the sun.", "instructions": "placeholder", "zodiac_color": "#6D9EC4FF", "dark_mode_zodiac_color": "#1567A5FF"},
    "Earth": {"signs": ["Taurus", "Virgo", "Capricorn"],  "glyph": "🌍", "short_meaning": "The Foundation & Physicality",     "long_meaning": "Earth is grounding; the ability to bring energy and ideas into tangible presence and material creations. Earth makes you want to take root.", "keywords": "Manifest, tangible, concrete, reliability, sensuality, steady, practical, substance, grounded, results, craftsmanship, anchor, endurance, simplify, harvest, structure, useful, realism", "remedy": "If you're un-grounded, eat a good meal and touch the Earth.", "instructions": "placeholder", "zodiac_color": "#CE7878FF", "dark_mode_zodiac_color": "#6D2424FF"},
    "Air":   {"signs": ["Gemini", "Libra", "Aquarius"],   "glyph": "💨", "short_meaning": "The Intellect & Social Connection", "long_meaning": "Air is thought; it is the mind, questions, introspection, academics, inquiry, pattern recognition, learning, intellect. Air makes you think. ", "keywords": "Circulate, objective, concept, communication, abstract, perspective, logic, movement, social, ideas, detached, bridge, analyze, breadth, exchange, theory, curious, breeze", "remedy": "If your mind is stagnant, sing, make vocal noises, or stand in the wind or in front of a fan.", "instructions": "placeholder", "zodiac_color": "#7CAF6AFF", "dark_mode_zodiac_color": "#366E21FF"},
    "Water": {"signs": ["Cancer", "Scorpio", "Pisces"],   "glyph": "💧", "short_meaning": "The Soul & Emotional Depth",       "long_meaning": "Water is emotion; it is feelings, intuition, empathy, sensitivity, and the subconscious. Water carries emotions through the body's tissues.", "keywords": "Intuition, absorb, sentiment, flow, depth, empathy, reflection, unconscious, soul, immersive, feel, healing, mystery, porous, subjective, memory, sanctuary, ripple", "remedy": "If your feelings are stuck, drink water, take a bath or shower, or go swimming.", "instructions": "placeholder", "zodiac_color": "#D8B873FF", "dark_mode_zodiac_color": "#946D19FF"},
}

SIGN_MEANINGS = {
    "Aries":       {"meaning": "Sign of Action & Initiation",        "keywords": "Courage, initiate, bold, spark, assertion, compete, independence, direct, fire, willpower, lead, kinetic, honesty, impulse, challenge, vitality",                                            "instructions": "placeholder"},
    "Taurus":      {"meaning": "Sign of Stability & Sensation",      "keywords": "Stability, nurture, sensual, patient, endurance, luxury, grounded, persist, comfort, loyalty, tactile, values, beauty, steady, build, nature",                                               "instructions": "placeholder"},
    "Gemini":      {"meaning": "Sign of Communication & Curiosity",  "keywords": "Curiosity, adapt, versatile, chatter, intellect, dual, connect, witty, swift, information, playful, analyze, variety, perceive, networking, restless",                                       "instructions": "placeholder"},
    "Cancer":      {"meaning": "Sign of Nurturing & Home",           "keywords": "Intuition, feel, sanctuary, maternal, memory, soft, defensive, tide, empathy, protect, roots, sensitive, tenacity, mood, belonging, care",                                                   "instructions": "placeholder"},
    "Leo":         {"meaning": "Sign of Creativity & Expression",    "keywords": "Radiance, create, warmth, charisma, express, dramatic, pride, heart, generous, center-stage, loyalty, shine, noble, play, applause, leadership",                                             "instructions": "placeholder"},
    "Virgo":       {"meaning": "Sign of Service & Refinement",       "keywords": "Precision, refine, service, practical, discern, health, logic, craft, meticulous, order, useful, improve, modest, analytical, detail, devotion",                                             "instructions": "placeholder"},
    "Libra":       {"meaning": "Sign of Balance & Relationships",    "keywords": "Harmony, balance, relate, aesthetic, justice, charm, collaborate, poise, fairness, social, mediate, elegant, partnership, choice, peace, symmetry",                                           "instructions": "placeholder"},
    "Scorpio":     {"meaning": "Sign of Transformation & Depth",     "keywords": "Intensity, transform, depth, power, mystery, investigate, passion, rebirth, private, focus, magnetic, soul, penetrate, resilient, truth, subtext",                                           "instructions": "placeholder"},
    "Sagittarius": {"meaning": "Sign of Exploration & Belief",       "keywords": "Expansion, seek, freedom, truth, wander, optimistic, philosophical, direct, growth, adventure, belief, wild, honest, perspective, quest, laughter",                                          "instructions": "placeholder"},
    "Capricorn":   {"meaning": "Sign of Ambition & Structure",       "keywords": "Ambition, structure, mastery, climb, discipline, legacy, status, endurance, achieve, pragmatic, time, integrity, climb, stoic, tradition, authority",                                        "instructions": "placeholder"},
    "Aquarius":    {"meaning": "Sign of Innovation & Community",     "keywords": "Innovation, rebel, community, unique, detach, future, ideal, radical, humanitarian, inventive, logic, electricity, progress, friendship, network, objective",                                 "instructions": "placeholder"},
    "Pisces":      {"meaning": "Sign of Imagination & Compassion",   "keywords": "Dream, dissolve, compassion, nebulous, artistic, surrender, transcendent, porous, gentle, imagination, psychic, flow, sacrifice, spiritual, mystery, empathy",                               "instructions": "placeholder"},
}

HOUSE_MEANINGS = {
    1:  {"meaning": "House of Self & Identity",                                "keywords": 'Identity, appearance, "I am," vitality, beginnings, mask, physical body, temperament, first impressions, emergence, outlook, presence, persona, leadership, self-image'},
    2:  {"meaning": "House of Money, Values & Work Routines",                  "keywords": "Money, possessions, self-worth, assets, senses, income, security, values, material world, habits, stability, earning-power, comfort, luxury, talents, sustenance"},
    3:  {"meaning": "House of Communication, Local Neighborhood & Peers",      "keywords": "Mindset, siblings, local travel, chatter, neighbors, learning, school, writing, speaking, gadgets, curiosity, perception, logistics, immediate environment, data, networking"},
    4:  {"meaning": "House of Home, Family & Ancestry",                        "keywords": "Roots, family, sanctuary, the mother, privacy, foundations, heritage, domesticity, emotions, ancestors, property, security, subconscious, endings, the nest, nurture"},
    5:  {"meaning": "House of Creativity, Pleasure & Children",                "keywords": "Joy, romance, play, children, self-expression, hobbies, risk, pleasure, drama, leisure, speculation, authenticity, flirting, heart, performance, artistic-spark"},
    6:  {"meaning": "House of Health & Daily Routines",                        "keywords": "Routine, service, health, habits, work, pets, efficiency, organization, skills, discipline, detail, hygiene, chores, improvement, coworkers, maintenance"},
    7:  {"meaning": "House of Partnerships & Relationships with Others",       "keywords": 'Marriage, contracts, "The Other," diplomacy, open enemies, balance, collaboration, harmony, shadow-self, agreements, mirrors, commitment, legalities, social-grace, equality'},
    8:  {"meaning": "House of Transformation & Shared Resources",              "keywords": "Intimacy, shared-resources, death, rebirth, taxes, secrets, taboos, inheritance, psychology, intensity, vulnerability, power, occult, crisis, evolution, sex"},
    9:  {"meaning": "House of Philosophy, Travel & Higher Learning",           "keywords": "Philosophy, travel, higher-education, truth, belief, adventure, ethics, publishing, foreign-lands, law, wisdom, quest, optimism, religion, teaching, broad-view"},
    10: {"meaning": "House of Career, Legacy & Public Life",                   "keywords": "Reputation, public-image, status, authority, legacy, father-figure, ambition, achievement, calling, responsibility, discipline, vocation, social-standing, mastery, structure"},
    11: {"meaning": "House of Community & Friends",                            "keywords": "Friendship, networks, goals, hopes, humanitarianism, groups, the future, collective, idealism, teamwork, circles, vision, technology, eccentricity, rebellion, alignment"},
    12: {"meaning": "House of Spirituality, Institutions, & the Subconscious", "keywords": "Solitude, secrets, spiritual, transcendence, institutions, dreams, hidden-enemies, retreats, karma, jail, hospital, surrender, isolation, mysticism, healing, subconscious, release, closure, the-void"},
}

OBJECT_MEANINGS = {
    # Axes & Points
    "Ascendant":              "How you show up at first glance—your identity, appearance, vibe, posture, and approach to life.",
    "Descendant":             'What you seek and mirror in close partnerships, and how you relate to others or the archetypal "other"',
    "MC":                     "Public role and trajectory—how your work, calling, and reputation take visible shape.",
    "IC":                     "Roots and inner base—home, memory, ancestry, and what truly feels like 'safe.'",
    "North Node":             "Growth direction—the stretch path that opens your future and matures your gifts. The highest and best version of you is in this direction.",
    "South Node":             "The natural strengths you bring into this life, your comfort zone, which you must draw from to achieve your North Node goals. It is also where you go to purge, reset, and be re-born.",
    "Vertex":                 "Fated crossroads—encounters and plot twists that re-route your story.",
    "Part of Fortune":        "Your own personal rules for good fortune/luck. During Part of Fortune activations, your personal rules for magic (the Sabian Symbol for your PoF) are in charge of your life.",
    "Black Moon Lilith (Mean)": 'Sacred no and sovereign yes—your untamed edge, boundaries, and primal honesty. Lilith activations bring out the "AW HELL NAW" response, or deeply powerful feminine magnetism.',
    "Black Moon Lilith":      'Sacred no and sovereign yes—your untamed edge, boundaries, and primal honesty. Lilith activations bring out the "AW HELL NAW" response, or deeply powerful feminine magnetism.',
    # Luminaries & Planets
    "Sun":     "Core vitality and purpose/primary soul expression—what lights you up and fuels your mission.",
    "Moon":    "Emotional climate and instincts—how you self-soothe and stay nourished. The deeper emotional needs and feelings underlying soul expression.",
    "Mercury": "Thinking and communication—how you learn, connect, and make meaning.",
    "Venus":   "Value, attraction, sensuality and harmony—what you value, what makes you comfortable and secure (both emotionally and physically), how you bond, value beauty, and build trust. Venus rules matters of money and possessions; all things value-related.",
    "Mars":    "Drive and courage—how you pursue, protect, and take decisive action. Mars is the get-up-and-go engine.",
    "Jupiter": "Expansion/growth, philosophy and faith—where you expand, teach, and say a confident yes. Jupiter expands/amplifies everything he touches (via aspect, rulership, transit, etc.)",
    "Saturn":  "Time, structure and mastery—your boundaries, responsibilities, and earned authority. Saturn is the timekeeper of your life, and the authority who enforces your discipline.",
    "Uranus":  "Liberation, originality, rebellion, innovation and technology—your need for freedom, updates, and breakthroughs. Uranus brings major surprise disruptions to the status quo.",
    "Neptune": "Imagination, dreams, spirituality, fantasies, and illusions—your dreamlife, compassion, and spiritual longing. Neptune rules both true and untrue spiritual visions and dreams, as well as the use of mind-altering substances.",
    "Pluto":   "The Underworld Journey: depth and regeneration, power, shadow work, soul retrieval, ancestral memory, and transformational truth. Pluto embodies the energy of intense constriction from all sides, forcing the skeletons out of the closet by turning life inside-out.",
    # Healing, devotion, sovereignty
    "Ceres":   "Care cycles—feeding, tending, and the seasonal rhythm of give and receive. Ceres shows our relationship to nurturing ourselves and others; what kind of nurture we need as well as how we nurture the world.",
    "Pallas":  "X-Ray vision for seeing the inner workings of whatever it is connected to in the natal chart. Pattern intelligence—strategy, creative problem-solving, and elegant design. Pallas conjunct a natal planet brings high level tactical intelligence to that planet.",
    "Juno":    "Commitment style—loyalty, agreements, and what keeps bonds equitable. Juno indicates all things commitment, both in relationships and life pursuits. Keyword: Contracts.",
    "Vesta":   "Focused devotion—sacred attention, hearth fire, and purpose as practice. Vesta shows what you tend to day in and day out, as your most sacred flame.",
    "Lilith":  "Unfiltered self—refusing shame, reclaiming desire, and standing unowned.",
    "Chiron":  "Medicine through experience—your tender spot that becomes a gift to others. Chiron is often called the Wounded Healer. Your Chiron placement indicates your deepest wound, and as you go through that healing journey you become equipped to help others heal similar wounds.",
    # Muses, arts, memory
    "Iris": "Bridge-builder—translating between worlds, people, and color bands of meaning.",
    "Hygiea": "Clean routines—hygiene, detox, and keeping systems simple and unclogged.",
    "Psyche": "Soul sensitivity—bonding depth, intuition, and the courage to be seen within.",
    "Thalia": "Lightness and humor—resilience through wit, play, and comic relief.",
    "Euterpe": "Breath of music—lyric flow, melody, and mood-shaping through sound.",
    "Pomona": "Harvest and stewardship—cultivation, ripeness, and tending what feeds life.",
    "Polyhymnia": "Sacred voice—prayerful focus, silence as power, and devotional speech.",
    "Harmonia": "Peacemaking—tuning relationships, smoothing conflict, and restoring balance.",
    "Isis": "Re-membering wholeness—naming, mending, and honoring what was broken.",
    "Ariadne": "Wayfinding—threads, maps, and staying oriented in complex mazes.",
    "Mnemosyne": "Living archive—ancestral memory, storytelling, and recall that matters.",
    "Echo": "Reflective resonance—mirroring, call-and-response, and listening that shapes speech.",
    "Niobe": "Humbling pride—learning through loss, softening, and rehumanizing success.",
    "Eurydike": "Trust at the threshold—tender retrievals, promises kept, and consent.",
    "Freia": "Magnetism and worth—sovereign charm, valuables, and the art of receiving.",
    "Terpsichore": "Movement as meaning—dance, rhythm, and expression through the body.",
    "Minerva": "Calm clarity—craftsmanship, wise strategy, and elegant solutions.",
    "Hekate": "Crossroads keeper—choice points, thresholds, and traveling with good keys.",
    "Zephyr": "Gentle tailwinds—subtle support, easeful motion, and kinder pacing.",
    "Kassandra": "Truth against odds—clear warnings, second sight, and staying with what's real.",
    "Lachesis": "Right-sizing—scope, pacing, and measuring what a season can hold.",
    "Nemesis": "Rebalancing—natural consequences that restore proportion and fairness.",
    "Medusa": "Protective gaze—defense of dignity, warding off harm, and righteous rage.",
    "Aletheia": "Disclosure—honesty, clarity, and letting truth clean the air.",
    "Magdalena": "Heartful devotion—erotic innocence, forgiveness, and love as remedy.",
    "Arachne": "Master craft—skill, reputation, and webs that connect without trapping.",
    "Fama": "Signal and story—news, reputation waves, and what carries your name.",
    "Eros": "Life-aimed desire—magnetism, creative union, and sacred yes.",
    "Veritas": "Integrity seal—accuracy, alignment, and promises you can stand on.",
    # Makers, rebels, risk
    "Hidalgo": "Frontier ethics—standing up to power and staking your own claim.",
    "Sirene": "Calling and testing—irresistible songs, choice points, and steering by values.",
    "Siva": "Destroy-to-renew—paring back to essence so new life can begin.",
    "Lilith (Asteroid)": "Embodied rebel—living your no and yes without apology.",
    "Copernicus": "Paradigm shift—seeing from a truer center and updating the model.",
    "Icarus": "Heat management—ambition, altitude, and learning your safe burn range.",
    "Toro": "Applied strength—endurance, potency, and steady, grounded force.",
    "Apollo": "Spotlight craft—aimed excellence, artistry, and clean performance energy.",
    "Koussevitzky": "Conductor's touch—coordination, timing, and bringing parts into ensemble.",
    "Anteros": "Reciprocal love—being loved back, mutuality, and earned devotion.",
    "Tezcatlipoca": "Obsidian mirror—seeing shadow clearly and resetting the game board.",
    # Transpersonal & mythic tech
    "Varuna": "Big-water law—oaths, vast accountability, and currents that hold all boats.",
    "West": "Sunset tone—closures, completions, and honoring the day's last light.",
    "Bacchus": "Fermented joy—celebration, loosening, and ritual release.",
    "Hephaistos": "The forge—repair, invention, and tools that fit real hands.",
    "Panacea": "Universal remedy impulse—integrating fixes and seeking the root cause.",
    "Orpheus": "Song as spell—softening the hard places with music and mercy.",
    "Kafka": "Strange wisdom—seeing through red tape and finding truth in the surreal.",
    "Pamela": "Symbol craft—tarot-grade imagery, archetypes, and picture-language.",
    "Dionysus": "Holy wild—ecstasy, boundary-melting, and sacred mischief.",
    "Kaali": "Life-force surge—kundalini awareness and respectful power handling.",
    "Asclepius": "Skilled healing—diagnosis, practice, and repair through craft.",
    "Nessus": "Cycle break—naming harm, keeping lines clean, and ending abuse patterns.",
    "Singer": "Voice node—signature tone, message delivery, and being heard.",
    "Angel": "Protective messenger—kind interventions, guidance, and unseen help.",
    "Ixion": "Second chances—taboo lessons, accountability, and redemption arcs.",
    "Typhon": "Primordial weather—chaos cleanouts and storm-born clarity.",
    "Quaoar": "Creation dance—playful order, culture-making, and new songs for life.",
    "Sedna": "Oceanic depth—betrayal to sovereignty and slow, tidal healing.",
    "Orcus": "Oath keeper—promises, consequences, and the weight of one's word.",
    "Haumea": "Fertile renewal—rapid regrowth, lineage blessings, and fresh starts.",
    "Eris": "The journey through victimhood and empowerment: being oppressed, learning the truth of that oppression, learning to stand up for yourself, and eventually learning to stand up for others. The key is learning the truth behind the oppression and advocating out loud.",
    "Makemake": "Provision and play—resourceful creativity and community feast codes.",
}

OBJECT_MEANINGS_SHORT = {
    # Axes & Points
    "Ascendant":       "House of Self — how you appear and begin things.",
    "Descendant":      "House of Others — partnerships and mirroring.",
    "MC":              "Public role, career, and reputation.",
    "IC":              "Home, roots, and inner foundation.",
    "North Node":      "Growth path and future direction.",
    "South Node":      "Comfort zone and past strengths.",
    "Vertex":          "Fated encounters and turning points.",
    "Part of Fortune": "Your personal key to luck and flow.",
    "Black Moon Lilith": "Raw boundaries and untamed power.",
    # Luminaries & Planets
    "Sun":     "Core self and vitality.",
    "Moon":    "Emotions, instincts, and needs.",
    "Mercury": "Mind, communication, and learning.",
    "Venus":   "Love, beauty, and values.",
    "Mars":    "Drive, action, and courage.",
    "Jupiter": "Growth, luck, and expansion.",
    "Saturn":  "Discipline, limits, and mastery.",
    "Uranus":  "Change, freedom, and innovation.",
    "Neptune": "Dreams, spirit, and illusions.",
    "Pluto":   "Power, shadow, and transformation.",
    # Healing, devotion, sovereignty
    "Ceres":   "Nurturing and care cycles.",
    "Pallas":  "Wisdom, patterns, and strategy.",
    "Juno":    "Commitments and contracts.",
    "Vesta":   "Sacred focus and devotion.",
    "Lilith":  "Authenticity and defiance.",
    "Chiron":  "Wounding and healing gift.",
    "Eros":    "Desire and creative spark.",
    "Psyche":  "Soul, bonds, and intuition.",
    "Eris":    "Disruption, truth, and empowerment.",
}

ASPECT_INTERP = {
    "Trine": (
        "Complete, automatic connection and collaboration. "
        "What happens to one happens to the other – these two planets are attached at the hip, "
        "total besties, zero resistance, zero interference. Full mutual signal transfer."
    ),
    "Sextile": (
        "Potential for strong harmonious connection, much like the trine, but not automatic. "
        "Sextiles are opportunities for two planets to work together and develop a latent talent. "
        "They require choice and active participation under normal circumstances – "
        "but can be automatically activated by transits."
    ),
    "Square": (
        "Work. Square does not necessarily mean conflict, but it always means work; "
        "two planets that must work to reconcile their differences because they both feel "
        "like the other is shoving them from the side and totally interfering with their trajectory. "
        "They can be reconciled, and need to be – the keys are in the other two points "
        "that complete the grand cross."
    ),
    "Conjunction": (
        "Planets/placements that share the same perspective and location, approaching life from the same place. "
        "They combine their powers to form one node in the circuit together. If they are planets that"
        "naturally have a tense relationship, such as Saturn and Uranus, then they can sometimes be tough"
        "roommates until the two archetypes are resolved into a working friendship."
        "When creating profile paragraphs, list the profiles for all placements within one conjunction cluster consecutively, even if that means repeating headers."
    ),
    "Opposition": (
        "The balance of opposites, like Yin and Yang. Each set of polarities is complementary, "
        "but the tendency is for them to compete when ungrounded. "
        "The dichotomy in a classic heterosexual marriage diagram explains the opposite polarities well: "
        "either the man and woman recognize that they have different but complementary poles "
        "and honor their differences, creating symbiotic balance, "
        "or they compete, trying to dominate or control one another out of competition, superiority, or insecurity. "
        "All major oppositions in a natal chart represent the major over-arching themes of the native's life. "
        "They are polarities that the native is always working to keep in balance, or their life goes out of balance."
        "List them first when present with other aspects, and explain that the oppositions are the biggest life themes. "
    ),
    "Sesquisquare": (
        "Activation overflow. This is an aspect of momentum, compulsion, and often service. "
        "One planet reaches full activation, and the sesquisquare acts like a surge line — "
        "it pushes energy into the other planet, activating it in a new capacity. "
        "It's not smooth like a trine, nor tense like a square — it's quick, sometimes surprising, "
        "and highly energetic. These are often 'helper circuits' or 'gift-wired compulsions,' "
        "where someone finds themselves acting or serving without even planning to, simply because "
        "the conditions are right for them to be 'in their element.' "
        "They can be hijacked or manipulated without good boundaries, but when integrated, "
        "sesquisquares unlock multidimensional creativity and functional genius. "
        "Example: a teacher who cannot help but passionately teach when her area of expertise is mentioned. "
    ),
    "Quincunx": (
        "Hard misalignment—treat as a red-wire/black-wire hazard. Do NOT connect directly. "
        "These are two points that feel extremely tempted to connect directly, like an itch that can't be directly scratched."
        "Forcing contact causes arc, blowouts, symptom cascades, heartbreak, betrayal, failure, and general regrets. "
        "Protocol: GO AROUND. Design an indirect route through non-quincunx links "
        "(trine/sextile/square/sesquisquare/semisextile or a conjunction chain) that converts A's output into "
        "B's input via adapters—clear skills, environments, or intermediaries. "
        "The urgency you feel is noise; slow down, build the adapter, then pass the signal. "
        "If the current placements and aspects shown do not provide resolution to re-route the quincunx, "
        "tell the user that other placements not included in this interpretation will be needed to bridge the disconnect."
        "quincunx mark injury loops and chronic misfires when hotwired; used correctly, they enforce sound system design."
    ),
}

SHORT_ASPECT_MEANINGS = {
    "Trine":        "complete, automatic, instantaneous connectivity",
    "Sextile":      "opportunity for harmonious integration",
    "Square":       "integration through struggle or effort between seemingly contradictory viewpoints",
    "Conjunction":  "unified perspective, unified action",
    "Opposition":   "two balancing polarities on an axis",
    "Sesquisquare": "the itch that must be scratched",
    "Quincunx":     "the itch that can never be scratched",
    "Semisextile":  "the sneaky, frictionless backway",
}

SETNENCE_ASPECT_NAMES = {
    "Trine":        "trines",
    "Sextile":      "sextiles",
    "Square":       "squares",
    "Conjunction":  "conjunct",
    "Opposition":   "opposite",
    "Sesquisquare": "sesquisquares",
    "Quincunx":     "quincunxes",
    "Semisextile":  "semisextiles",
}

SENTENCE_ASPECT_MEANINGS = {
    "Trine":        "share complete, automatic, instantaneous connectivity, for better or for worse. On the positive side, they work together perfectly as a team, which is a major strength. However, these parts of yourself are so connected, that you may not be able to relate to others who have a hard time integrating the same placements due to a hard aspect in their own chart.",
    "Sextile":      "have the opportunity for harmonious integration if actively connected, and represents a potential talent that you can develop if you choose.",
    "Square":       "may feel at odds with each other; they require ongoing integration through work. This may express as conflict at times; however, the work of squares is the engine that powers the whole chart. You would get nowhere without them.",
    "Conjunction":  "share the same perspective, and take action from the same place, like roommates. As long as they are getting along and well integrated, they will function as one unit, combining the traits of both.",
    "Opposition":   "are two opposite polarities, striving to balance each other, and represent an over-arching theme in your life. They have a tendency to want to compete, but they can be complementary if they recognize their differences and honor them, reaching across the spanse and building a bridge of collaboration. The opposition is the only aspect in the astrology that touches the Earth; it is the only aspect that can truly ground you. Embrace the balancing of opposites.",
    "Sesquisquare": 'cannot help but connect, like the itch that must be scratched. This is like an overflow path; whenever one planet is charged up to "overflowing", it will spill over and connect across this aspect automatically, activating this talent. Watch out for exploitation here, as others may be able to use this to manipulate you.',
    "Quincunx":     "want to connect, but it will always result in failure, like the itch that can never be scratched. Go around; these energies will have to balance through indirect connections. Trying harder to connect them dirctly will only make the failure more epic and painful.",
    "Semisextile":  'like to rendezvous via the sneaky, frictionless backway of the semi-sextile. While other connections to these two points may be more intense or triggering when dealing with hard subjects, the semi-sextile provides a sort of "spiritual anesthesia" that makes it light-hearted and safe.',
}
