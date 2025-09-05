# rosetta/lookup.py
# # CONSTANTS - All the lookup data in one place
GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Chiron": "⚷", "Ceres": "⚳", "Pallas": "⚴", "Juno": "⚵", "Vesta": "⚶",
    "North Node": "☊", "South Node": "☋", "Part of Fortune": "⊗", "Lilith": "⚸",
    "Vertex": "🜊", "True Node": "☊",
}

ASPECTS = {
    "Conjunction": {"angle": 0, "orb": 3, "color": "#888888", "style": "solid"},
    "Sextile": {"angle": 60, "orb": 3, "color": "purple", "style": "solid"},
    "Square": {"angle": 90, "orb": 3, "color": "red", "style": "solid"},
    "Trine": {"angle": 120, "orb": 3, "color": "blue", "style": "solid"},
    "Sesquisquare": {"angle": 135, "orb": 2, "color": "orange", "style": "dotted"},
    "Quincunx": {"angle": 150, "orb": 3, "color": "green", "style": "dotted"},
    "Opposition": {"angle": 180, "orb": 3, "color": "red", "style": "solid"},
}

MAJOR_OBJECTS = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn",
    "Uranus", "Neptune", "Pluto", "Eris", "Chiron", "Vesta", "Pallas",
    "Ceres", "Juno", "Psyche", "Eros", "Part of Fortune", "Black Moon Lilith",
    "Lilith", "Ascendant", "AC", "Descendant", "DC", "Midheaven", "MC", "IC",
    "North Node", "True Node", "South Node", "Vertex",
]

ZODIAC_SIGNS = ["♈️", "♉️", "♊️", "♋️", "♌️", "♍️", "♎️", "♏️", "♐️", "♑️", "♒️", "♓️"]
ZODIAC_COLORS = ["red", "green", "#DAA520", "blue"] * 3
MODALITIES = ["Cardinal", "Fixed", "Mutable"] * 4
GROUP_COLORS = [
    "crimson", "teal", "darkorange", "slateblue", "seagreen",
    "hotpink", "gold", "deepskyblue", "orchid"
]

OBJECT_MEANINGS = {
    "AC": "The mask you wear and how others first see you.",
    "Desc": "What you seek in relationships and partners.",
    "True Node": "Your soul's growth direction in this life.",
    "Sun": "Your core identity, purpose, and life force.",
    "Moon": "Your emotions, inner world, and instinctive needs.",
    "Mercury": "Your mind, communication style, and how you think.",
    "Venus": "How you love, attract, and experience beauty.",
    "Mars": "How you act, assert yourself, and pursue desires.",
    "Jupiter": "Your growth path, optimism, and what expands you.",
    "Saturn": "Your responsibilities, discipline, and long-term lessons.",
    "Uranus": "Your uniqueness, rebellion, and breakthroughs.",
    "Neptune": "Your dreams, illusions, and spiritual longing.",
    "Pluto": "Your power, transformations, and shadow work.",
    "Ceres": "The nurturing instinct and cycles of giving and receiving.",
    "Pallas": "Pattern recognition, creative intelligence, and tactics.",
    "Juno": "What you need in committed partnerships.",
    "Vesta": "Sacred focus, devotion, and spiritual flame.",
    "Lilith": "Your raw feminine power, rebellion, and untamed self.",
    "Chiron": "The deep wound you heal in others by healing yourself.",
    "Vertex": "A fated meeting point — unexpected turning points.",
    "Part of Fortune": "Where you find natural ease and success.",
    # Add more meanings as needed...
}

ASPECT_INTERPRETATIONS = {
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
        "Two or more planets that share the same perspective and location. "
        "They work together as a singular node. If they are planets that naturally have a tense "
        "relationship, such as Saturn and Uranus, then they can sometimes be tough roommates "
        "together until the two archetypes are resolved into a working friendship."
    ),
    "Opposition": (
        "The balance of opposites, like Yin and Yang. Each set of polarities is complementary, "
        "but the tendency is for them to compete when ungrounded. "
        "The dichotomy in a classic heterosexual marriage diagram explains the opposite polarities well: "
        "either the man and woman recognize that they have different but complementary poles "
        "and honor their differences, creating symbiotic balance, "
        "or they compete, trying to dominate or control one another out of competition, superiority, or insecurity. "
        "All major oppositions in a natal chart represent the major over-arching themes of the native’s life. "
        "They are polarities that the native is always working to keep in balance, or their life goes out of balance."
    ),
    "Sesquisquare": (
        "Activation overflow. This is an aspect of momentum, compulsion, and often service. "
        "One planet reaches full activation, and the sesquisquare acts like a surge line — "
        "it pushes energy into the other planet, activating it in a new capacity. "
        "It’s not smooth like a trine, nor tense like a square — it’s quick, sometimes surprising, "
        "and highly energetic. These are often 'helper circuits' or 'gift-wired compulsions,' "
        "where someone finds themselves acting or serving without even planning to, simply because "
        "the conditions are right for them to be 'in their element.' "
        "They can be hijacked without good boundaries, but when integrated, "
        "sesquisquares unlock multidimensional creativity and functional genius."
    ),
    "Quincunx": (
        "A misaligned connection that demands adjustment. These planets feel like they should connect — "
        "there’s tension and urgency — but the angles don’t support clean communication or mutual understanding. "
        "This creates frustration, indecision, awkward compensations, or even complete disaster when pushed "
        "against hard enough – until a new integration pathway is consciously invented. "
        "It’s like trying to plug a round wire into a triangular socket. "
        "You’re likely to fry or break something if you try too hard. "
        "Quincunxes often signal health issues, compulsions that always seem to go badly, "
        "patterns of bad luck, repeated disaster/trauma signatures, or parts of self that never seem to belong… "
        "until the chart holder invents a whole new framework to hold them."
    ),
}
