# rosetta/lookup.py
# CONSTANTS - All the lookup data in one place

GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Chiron": "⚷", "Ceres": "⚳", "Pallas": "⚴", "Juno": "⚵", "Vesta": "⚶",
    "North Node": "☊", "South Node": "☋", "Part of Fortune": "⊗", "Black Moon Lilith (Mean)": "⚸",
    "Vertex": "☩", "True Node": "☊", "Ascendant": "AC", "Descendant": "DC", "Psyche": "Ψ", "Eros": "♡", 
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
    "Ceres", "Juno", "Psyche", "Eros", "Part of Fortune", "Black Moon Lilith (Mean)",
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

DIGNITIES = {
  "Aries": {
    "domicile": [
      "Mars"
    ],
    "detriment": [
      "Venus"
    ],
    "exaltation": [
      "Sun"
    ],
    "fall": [
      "Saturn"
    ]
  },
  "Taurus": {
    "domicile": [
      "Venus"
    ],
    "detriment": [
      "Mars"
    ],
    "exaltation": [
      "Moon"
    ],
    "fall": []
  },
  "Gemini": {
    "domicile": [
      "Mercury"
    ],
    "detriment": [
      "Jupiter"
    ],
    "exaltation": [],
    "fall": []
  },
  "Cancer": {
    "domicile": [
      "Moon"
    ],
    "detriment": [
      "Saturn"
    ],
    "exaltation": [
      "Jupiter"
    ],
    "fall": [
      "Mars"
    ]
  },
  "Leo": {
    "domicile": [
      "Sun"
    ],
    "detriment": [
      "Saturn"
    ],
    "exaltation": [],
    "fall": []
  },
  "Virgo": {
    "domicile": [
      "Mercury"
    ],
    "detriment": [
      "Jupiter"
    ],
    "exaltation": [
      "Mercury"
    ],
    "fall": [
      "Venus"
    ]
  },
  "Libra": {
    "domicile": [
      "Venus"
    ],
    "detriment": [
      "Mars"
    ],
    "exaltation": [
      "Saturn"
    ],
    "fall": [
      "Sun"
    ]
  },
  "Scorpio": {
    "domicile": [
      "Mars"
    ],
    "detriment": [
      "Venus"
    ],
    "exaltation": [],
    "fall": [
      "Moon"
    ]
  },
  "Sagittarius": {
    "domicile": [
      "Jupiter"
    ],
    "detriment": [
      "Mercury"
    ],
    "exaltation": [],
    "fall": []
  },
  "Capricorn": {
    "domicile": [
      "Saturn"
    ],
    "detriment": [
      "Moon"
    ],
    "exaltation": [
      "Mars"
    ],
    "fall": [
      "Jupiter"
    ]
  },
  "Aquarius": {
    "domicile": [
      "Saturn"
    ],
    "detriment": [
      "Sun"
    ],
    "exaltation": [],
    "fall": []
  },
  "Pisces": {
    "domicile": [
      "Jupiter"
    ],
    "detriment": [
      "Mercury"
    ],
    "exaltation": [
      "Venus"
    ],
    "fall": [
      "Mercury"
    ]
  }
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

INTERPRETATION_FLAGS = {
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

# Sabian Symbol Lookup Dictionary
SABIAN_SYMBOLS = {
    ('Aries', 1): 'A woman has risen out of the ocean, a seal is embracing her.',
    ('Aries', 2): 'A comedian entertaining the group.',
    ('Aries', 3): 'A cameo profile of a man in the outline of his country.',
    ('Aries', 4): 'Two lovers strolling through a secluded walk.',
    ('Aries', 5): 'A triangle with wings.',
    ('Aries', 6): 'A square brightly lighted on one side.',
    ('Aries', 7): 'A man successfully expressing himself in two realms at once.',
    ('Aries', 8): 'A woman’s hat with streamers blown by the east wind.',
    ('Aries', 9): 'A crystal gazer.',
    ('Aries', 10): 'A teacher gives new symbolic forms to traditional images.',
    ('Aries', 11): 'The ruler of a nation.',
    ('Aries', 12): 'A flock of wild geese.',
    ('Aries', 13): 'A bomb which failed to explode is now safely concealed.',
    ('Aries', 14): 'A serpent coiling near a man and a woman.',
    ('Aries', 15): 'An indian weaving a blanket.',
    ('Aries', 16): 'Brownies dancing in the setting sun.',
    ('Aries', 17): 'Two prim spinsters sitting together in silence.',
    ('Aries', 18): 'An empty hammock.',
    ('Aries', 19): 'The magic carpet of oriental imagery.',
    ('Aries', 20): 'A young girl feeding birds in winter.',
    ('Aries', 21): 'A pugilist (boxer) entering the ring.',
    ('Aries', 22): 'The gate to the garden of all fulfilled desires.',
    ('Aries', 23): 'A woman in pastel colors carrying a heavy and valuable but veiled load.',
    ('Aries', 24): 'An open window and a net curtain blowing into a cornucopia.',
    ('Aries', 25): 'A double promise reveals its inner and outer meanings.',
    ('Aries', 26): 'A man possessed of more gifts than he can hold.',
    ('Aries', 27): 'Through imagination, a lost opportunity is regained.',
    ('Aries', 28): 'A large disappointed audience.',
    ('Aries', 29): 'The music of the spheres.',
    ('Aries', 30): 'A duck pond and its brood.',
    ('Taurus', 1): 'A clear mountain stream.',
    ('Taurus', 2): 'An electrical storm.',
    ('Taurus', 3): 'Steps up to a lawn blooming with clover.',
    ('Taurus', 4): 'The pot of gold at the end of the rainbow.',
    ('Taurus', 5): 'A widow at an open grave.',
    ('Taurus', 6): 'A bridge being built across a gorge.',
    ('Taurus', 7): 'A woman of samaria comes to draw water from the well.',
    ('Taurus', 8): 'A sleigh without snow.',
    ('Taurus', 9): 'A christmas tree decorated.',
    ('Taurus', 10): 'A red cross nurse.',
    ('Taurus', 11): 'A woman sprinkling flowers.',
    ('Taurus', 12): 'A young couple walk down main- street, window-shopping.',
    ('Taurus', 13): 'A porter carrying heavy baggage.',
    ('Taurus', 14): 'On the beach, children play while shellfish grope at the edge of the water.',
    ('Taurus', 15): 'A man with rakish silk hat, muffled against the cold, braves a storm.',
    ('Taurus', 16): 'An old teacher fails to interest his pupils in traditional knowledge.',
    ('Taurus', 17): 'A symbolical battle between ‘swords’ and ‘torches’.',
    ('Taurus', 18): 'A woman airing an old bag through a sunny window.',
    ('Taurus', 19): 'A new continent rising out of the ocean.',
    ('Taurus', 20): 'Wisps of clouds, like wings, are streaming across the sky.',
    ('Taurus', 21): 'Moving finger points to significant passages in a book.',
    ('Taurus', 22): 'White dove flying over troubled waters.',
    ('Taurus', 23): 'A jewellery shop filled with the most magnificent jewels.',
    ('Taurus', 24): 'An indian warrior riding fiercely, human scalps hanging at his belt.',
    ('Taurus', 25): 'A large well-kept public park.',
    ('Taurus', 26): 'A spaniard serenading his senorita.',
    ('Taurus', 27): 'An old indian woman selling beads.',
    ('Taurus', 28): 'A mature woman reawakened to romance.',
    ('Taurus', 29): 'Two cobblers working at a table.',
    ('Taurus', 30): 'A peacock parading on the terrace of an old castle.',
    ('Gemini', 1): 'A glass-bottomed boat reveals under-sea wonders.',
    ('Gemini', 2): 'Santa clause filling stockings furtively.',
    ('Gemini', 3): 'The garden of the tuileries in paris.',
    ('Gemini', 4): 'Holly and mistletoe bring christmas spirit to a home.',
    ('Gemini', 5): 'A radical magazine, asking for action, displays a sensational front page.',
    ('Gemini', 6): 'Workmen drilling for oil.',
    ('Gemini', 7): 'An old-fashioned well.',
    ('Gemini', 8): 'Aroused strikers round a factory.',
    ('Gemini', 9): 'A quiver filled with arrows.',
    ('Gemini', 10): 'Aeroplane performing a nose-dive.',
    ('Gemini', 11): 'Newly opened lands offer the pioneer new opportunities for experience.',
    ('Gemini', 12): 'A black slave-girl demands her rights of her mistress.',
    ('Gemini', 13): 'World famous pianist giving a concert performance.',
    ('Gemini', 14): 'Two people, living far apart, in telepathic communication.',
    ('Gemini', 15): 'Two dutch children talking.',
    ('Gemini', 16): 'A woman activist in an emotional speech, dramatizing her cause.',
    ('Gemini', 17): 'The head of a robust youth changes into that of a mature thinker.',
    ('Gemini', 18): 'Two chinese men talking chinese (in a western crowd).',
    ('Gemini', 19): 'A large archaic volume reveals a traditional wisdom.',
    ('Gemini', 20): 'A cafeteria with an abundance of choices.',
    ('Gemini', 21): 'A tumultuous labor demonstration.',
    ('Gemini', 22): 'Dancing couples crowd the barn in a harvest festival.',
    ('Gemini', 23): 'Three fledglings in a nest high in a tree.',
    ('Gemini', 24): 'Children skating on ice.',
    ('Gemini', 25): 'A gardener trimming large palm trees.',
    ('Gemini', 26): 'Winter frost in the woods.',
    ('Gemini', 27): 'A young gypsy emerging from the woods gazes at far cities.',
    ('Gemini', 28): 'Society granting bankruptcy to him, a man leaves the court.',
    ('Gemini', 29): 'The first mockingbird of spring sings from the tree top.',
    ('Gemini', 30): 'A parade of bathing beauties before large beach crowds.',
    ('Cancer', 1): 'On a ship the sailors lower an old flag and raise a new one.',
    ('Cancer', 2): 'A man on a magic carpet observes vast vistas below him.',
    ('Cancer', 3): 'An arctic explorer leads a reindeer through icy canyons.',
    ('Cancer', 4): 'A cat arguing with a mouse.',
    ('Cancer', 5): 'At a railroad crossing, an automobile is wrecked by a train.',
    ('Cancer', 6): 'Game birds feathering their nests.',
    ('Cancer', 7): 'Two fairies (nature spirits) dancing on a moonlit night.',
    ('Cancer', 8): 'A group rabbits dressed in clothes and on parade.',
    ('Cancer', 9): 'A small, naked girl bends over a pond trying to catch a fish.',
    ('Cancer', 10): 'A large diamond in the first stages of the cutting process.',
    ('Cancer', 11): 'A clown caricaturing well-known personalities.',
    ('Cancer', 12): 'A chinese woman nursing a baby whose aura reveals him to be the reincarnation of a great teacher.',
    ('Cancer', 13): 'One hand slightly flexed with a very prominent thumb.',
    ('Cancer', 14): 'A very old man facing a vast dark space to the northeast.',
    ('Cancer', 15): 'A group of people who have overeaten and enjoyed it.',
    ('Cancer', 16): 'A man studying a mandala in front of him, with the help of a very ancient book.',
    ('Cancer', 17): 'The seed grows into knowledge and life.',
    ('Cancer', 18): 'A hen scratching for her chicks.',
    ('Cancer', 19): 'A priest performing a marriage ceremony.',
    ('Cancer', 20): 'Venetian gondoliers in a serenade.',
    ('Cancer', 21): 'A prima donna singing.',
    ('Cancer', 22): 'A young woman awaiting a sailboat.',
    ('Cancer', 23): 'The meeting of a literary society.',
    ('Cancer', 24): 'A woman and two men castaways on a small island of the south seas.',
    ('Cancer', 25): 'A leader of men wrapped in an invisible mantle of power.',
    ('Cancer', 26): 'Guests are reading in the library of a luxurious home.',
    ('Cancer', 27): 'A violent storm in a canyon filled with expensive homes.',
    ('Cancer', 28): 'Indian girl introduces college boy-friend to her assembled tribe.',
    ('Cancer', 29): 'A greek muse weighing new born twins in golden scales.',
    ('Cancer', 30): 'A daughter of the american revolution.',
    ('Leo', 1): 'Under emotional stress, blood rushes to a man’s head.',
    ('Leo', 2): 'An epidemic of mumps.',
    ('Leo', 3): 'A mature woman, keeping up with the times, having her hair bobbed.',
    ('Leo', 4): 'A man formally dressed stands near trophies he brought back from a hunting expedition.',
    ('Leo', 5): 'Rock formations tower over a deep canyon.',
    ('Leo', 6): 'An old fashioned ‘conservative’ woman is confronted by an up-to-date girl.',
    ('Leo', 7): 'The constellations of stars in the sky.',
    ('Leo', 8): 'Glass blowers shape beautiful vases with their controlled breathing.',
    ('Leo', 9): 'A communist activist spreading his revolutionary ideals.',
    ('Leo', 10): 'Early morning dew.',
    ('Leo', 11): 'Children on a swing in a huge oak tree.',
    ('Leo', 12): 'An evening lawn party of adults.',
    ('Leo', 13): 'An old sea captain rocking on the porch of his cottage.',
    ('Leo', 14): 'Cherub-like, a human soul whispers, seeking to manifest.',
    ('Leo', 15): 'A pageant moving along a street packed with people.',
    ('Leo', 16): 'Brilliant sunshine just after a storm.',
    ('Leo', 17): 'Volunteer church choir makes social event of rehearsal.',
    ('Leo', 18): 'A chemist conducts an experiment for his students.',
    ('Leo', 19): 'A houseboat party.',
    ('Leo', 20): 'American indians perform a ritual to the sun.',
    ('Leo', 21): 'Intoxicated chickens dizzily flap their wings trying to fly.',
    ('Leo', 22): 'A carrier pigeon fulfilling its mission.',
    ('Leo', 23): 'A bareback rider in a circus displays her dangerous skill.',
    ('Leo', 24): 'Totally concentrated upon inner spiritual attainment, a man is sitting in a state of complete neglect of his body.',
    ('Leo', 25): 'A large camel crossing a vast and forbidding desert.',
    ('Leo', 26): 'After a heavy storm, a rainbow.',
    ('Leo', 27): 'Daybreak – the luminescence of dawn in the eastern sky.',
    ('Leo', 28): 'Many little birds on the limb of a large tree.',
    ('Leo', 29): 'A mermaid emerges from the ocean ready for rebirth in human form.',
    ('Leo', 30): 'An unsealed letter.',
    ('Virgo', 1): 'In a portrait the best of a man’s features and traits are idealized.',
    ('Virgo', 2): 'A large white cross-dominating the landscape-stands alone on top of a high hill.',
    ('Virgo', 3): 'Two guardian angels bringing protection.',
    ('Virgo', 4): 'Black and white children playing happily together.',
    ('Virgo', 5): 'A man becoming aware of nature spirits and normally unseen spiritual energies.',
    ('Virgo', 6): 'A merry-go-round.',
    ('Virgo', 7): 'A harem.',
    ('Virgo', 8): 'A girl takes her first dancing instruction.',
    ('Virgo', 9): 'A expressionist painter making a futuristic drawing.',
    ('Virgo', 10): 'Two heads looking out and beyond the shadows.',
    ('Virgo', 11): 'A boy moulded in his mother’s aspirations for him.',
    ('Virgo', 12): 'A bride with her veil snatched away.',
    ('Virgo', 13): 'A powerful statesman overcomes a state of political hysteria.',
    ('Virgo', 14): 'A family tree.',
    ('Virgo', 15): 'A fine lace ornamental handkerchief.',
    ('Virgo', 16): 'Children crowd around the orang-utang cage in a zoo.',
    ('Virgo', 17): 'A volcanic eruption.',
    ('Virgo', 18): 'Two girls playing with a ouija board.',
    ('Virgo', 19): 'A swimming race.',
    ('Virgo', 20): 'A caravan of cars headed for promised lands.',
    ('Virgo', 21): 'A girl’s basketball team.',
    ('Virgo', 22): 'A royal coat of arms enriched with precious stones.',
    ('Virgo', 23): 'A lion-tamer rushes fearlessly into the circus arena.',
    ('Virgo', 24): 'Mary and her white lamb.',
    ('Virgo', 25): 'A flag at half-mast in front of a public building.',
    ('Virgo', 26): 'A boy with a censer serves near the priest at the altar.',
    ('Virgo', 27): 'Aristocratic elderly ladies drinking afternoon tea in a wealthy home.',
    ('Virgo', 28): 'A bald-headed man who has seized power.',
    ('Virgo', 29): 'A man gaining secret knowledge from an ancient scroll he is reading.',
    ('Virgo', 30): 'Having an urgent task to complete, a man doesn’t look to any distractions.',
    ('Libra', 1): 'A butterfly preserved and made perfect with a dart through it.',
    ('Libra', 2): 'The light of the sixth race transmuted to the seventh.',
    ('Libra', 3): 'The dawn of a new day reveals everything changed.',
    ('Libra', 4): 'A group of young people sit in spiritual communion around a campfire.',
    ('Libra', 5): 'A man teaching the true inner knowledge of the new world to his students.',
    ('Libra', 6): 'A man watches his ideals taking a concrete form before his inner vision.',
    ('Libra', 7): 'A woman feeding chickens and protecting them from the hawks.',
    ('Libra', 8): 'A blazing fireplace in a deserted home.',
    ('Libra', 9): 'Three old masters hanging in a special room in an art gallery.',
    ('Libra', 10): 'A canoe approaching safety through dangerous waters.',
    ('Libra', 11): 'A professor peering over his glasses at his students.',
    ('Libra', 12): 'Miners are emerging from a deep coal mine.',
    ('Libra', 13): 'Children blowing soap bubbles.',
    ('Libra', 14): 'In the heat of the noon, a man takes a siesta.',
    ('Libra', 15): 'Circular paths.',
    ('Libra', 16): 'After a storm, a boat landing stands in need of reconstruction.',
    ('Libra', 17): 'A retired sea captain watches ships entering and leaving the harbour.',
    ('Libra', 18): 'Two men placed under arrest.',
    ('Libra', 19): 'A gang of robbers in hiding.',
    ('Libra', 20): 'A jewish rabbi performing his duties.',
    ('Libra', 21): 'A crowd upon a beach.',
    ('Libra', 22): 'A child giving birds a drink at a fountain.',
    ('Libra', 23): 'Chanticleer’s voice heralds the rising sun with exuberant tones.',
    ('Libra', 24): 'A third wing on the left side of a butterfly.',
    ('Libra', 25): 'The sight of an autumn leaf brings to a pilgrim the sudden revelation of the mystery of life and death.',
    ('Libra', 26): 'An eagle and a large white dove turning into each other.',
    ('Libra', 27): 'An airplane sails, high in the clear sky.',
    ('Libra', 28): 'A man in deep gloom. unnoticed, angels come to his help.',
    ('Libra', 29): 'Mankind’s vast enduring effort to reach for knowledge transferable from generation to generation. knowledge.',
    ('Libra', 30): 'Three mounds of knowledge on a philosopher’s head.',
    ('Scorpio', 1): 'A sight-seeing bus filled with tourists.',
    ('Scorpio', 2): 'A broken bottle and spilled perfume.',
    ('Scorpio', 3): 'Neighbours help in a house- raising party in a small village.',
    ('Scorpio', 4): 'A youth holding a lighted candle in a devotional ritual.',
    ('Scorpio', 5): 'A massive, rocky shore resists the pounding of the sea.',
    ('Scorpio', 6): 'A gold rush tears men away from their native soil.',
    ('Scorpio', 7): 'Deep-sea divers.',
    ('Scorpio', 8): 'The moon shining across a lake.',
    ('Scorpio', 9): 'A dentist at work.',
    ('Scorpio', 10): 'A fellowship supper reunites old comrades.',
    ('Scorpio', 11): 'A drowning man is being rescued.',
    ('Scorpio', 12): 'An official embassy ball.',
    ('Scorpio', 13): 'An inventor performs a laboratory experiment.',
    ('Scorpio', 14): 'Telephone linemen at work installing new connections.',
    ('Scorpio', 15): 'Children playing around five mounds of sand.',
    ('Scorpio', 16): 'A girl’s face breaking into a smile.',
    ('Scorpio', 17): 'A woman, filled with her own spirit, is the father of her own child.',
    ('Scorpio', 18): 'A path through woods rich in autumn coloring.',
    ('Scorpio', 19): 'A parrot listening and then talking, repeats a conversation he has overheard.',
    ('Scorpio', 20): 'A woman drawing aside two dark curtains that closed the entrance to a sacred pathway.',
    ('Scorpio', 21): 'Obeying his conscience, a soldier resists orders.',
    ('Scorpio', 22): 'Hunters shooting wild ducks.',
    ('Scorpio', 23): 'A rabbit metamorphosed into a fairy (nature spirit).',
    ('Scorpio', 24): 'Crowds coming down the mountain to listen to one inspired man.',
    ('Scorpio', 25): 'An x ray photograph.',
    ('Scorpio', 26): 'Indians making camp (in new territory)',
    ('Scorpio', 27): 'A military band marches noisily on through the city streets.',
    ('Scorpio', 28): 'The king of the fairies approaching his domain.',
    ('Scorpio', 29): 'An indian woman pleading to the chief for the lives of her children.',
    ('Scorpio', 30): 'Children in halloween costumes indulging in various pranks.',
    ('Sagittarius', 1): 'Retired army veterans gather to reawaken old memories.',
    ('Sagittarius', 2): 'The ocean covered with whitecaps.',
    ('Sagittarius', 3): 'Two men playing chess.',
    ('Sagittarius', 4): 'A little child learning to walk.',
    ('Sagittarius', 5): 'An old owl up in a tree.',
    ('Sagittarius', 6): 'A game of cricket.',
    ('Sagittarius', 7): 'Cupid knocking at the door of a human heart.',
    ('Sagittarius', 8): 'Deep within the depths of the earth, new elements are being formed.',
    ('Sagittarius', 9): 'A mother leads her small child step by step up the stairs.',
    ('Sagittarius', 10): 'A theatrical representation of a golden haired ‘goddess of opportunity’.',
    ('Sagittarius', 11): 'The lamp of physical enlightenment at the left temple.',
    ('Sagittarius', 12): 'A flag that turns into an eagle that crows.',
    ('Sagittarius', 13): 'A widow’s past is brought to light.',
    ('Sagittarius', 14): 'The pyramids and the sphinx.',
    ('Sagittarius', 15): 'The ground hog looking for its shadow on ground hog day.',
    ('Sagittarius', 16): 'Sea gulls fly around a ship looking for food.',
    ('Sagittarius', 17): 'An easter sunrise service.',
    ('Sagittarius', 18): 'Tiny children in sunbonnets.',
    ('Sagittarius', 19): 'Pelicans, disturbed by the garbage of people move their young to a new habitat.',
    ('Sagittarius', 20): 'In winter people cutting ice from a frozen pond, for summer use.',
    ('Sagittarius', 21): 'A child and a dog wearing borrowed eyeglasses.',
    ('Sagittarius', 22): 'A chinese laundry.',
    ('Sagittarius', 23): 'Immigrants entering a new country.',
    ('Sagittarius', 24): 'A bluebird standing at the door of the house.',
    ('Sagittarius', 25): 'A chubby boy on a hobbyhorse.',
    ('Sagittarius', 26): 'A flag-bearer in a battle.',
    ('Sagittarius', 27): 'The sculptor’s vision is taking form.',
    ('Sagittarius', 28): 'An old bridge over a beautiful stream in constant use.',
    ('Sagittarius', 29): 'A fat boy mowing the lawn.',
    ('Sagittarius', 30): 'The pope blessing the faithful.',
    ('Capricorn', 1): 'An indian chief claims power from the assembled tribe.',
    ('Capricorn', 2): 'Three stained-glass windows in a gothic church, one damaged by war.',
    ('Capricorn', 3): 'The human soul, in its eagerness for new experiences, seeks embodiment.',
    ('Capricorn', 4): 'A group of people entering a large canoe for a journey by water.',
    ('Capricorn', 5): 'Indians – some rowing a canoe and others dancing a war dance in it.',
    ('Capricorn', 6): 'Ten logs lie under an archway leading to darker woods.',
    ('Capricorn', 7): 'A veiled prophet speaks, seized by the power of a god.',
    ('Capricorn', 8): 'Birds in the house singing happily.',
    ('Capricorn', 9): 'An angel carrying a harp.',
    ('Capricorn', 10): 'An albatross feeding from the hand of a sailor.',
    ('Capricorn', 11): 'Pheasants display their brilliant colors on a private estate.',
    ('Capricorn', 12): 'A student of nature lecturing revealing little-known aspects of life.',
    ('Capricorn', 13): 'A fire worshipper meditates on the ultimate realities of existence.',
    ('Capricorn', 14): 'An ancient bas-relief carved in granite remains a witness to a long- forgotten culture.',
    ('Capricorn', 15): 'In a hospital, the children’s ward is filled with toys.',
    ('Capricorn', 16): 'School grounds filled with boys and girls in gymnasium suits.',
    ('Capricorn', 17): 'A girl surreptitiously bathing in the nude.',
    ('Capricorn', 18): 'The union jack flies from a new british warship.',
    ('Capricorn', 19): 'A child of about five carrying a huge shopping bag filled with groceries.',
    ('Capricorn', 20): 'A hidden choir singing during a religious service.',
    ('Capricorn', 21): 'A relay race.',
    ('Capricorn', 22): 'A general accepting defeat gracefully.',
    ('Capricorn', 23): 'A soldier receiving two awards for bravery in combat.',
    ('Capricorn', 24): 'A woman entering a convent.',
    ('Capricorn', 25): 'An oriental rug dealer in a store filled with precious ornamental rugs.',
    ('Capricorn', 26): 'A nature spirit dancing in the mist of a waterfall.',
    ('Capricorn', 27): 'A mountain pilgrimage.',
    ('Capricorn', 28): 'A large aviary.',
    ('Capricorn', 29): 'A woman reading tea leaves.',
    ('Capricorn', 30): 'Directors of a large firm meet in secret conference.',
    ('Aquarius', 1): 'An old adobe mission.',
    ('Aquarius', 2): 'An unexpected thunderstorm.',
    ('Aquarius', 3): 'A deserter from the navy.',
    ('Aquarius', 4): 'A hindu healer.',
    ('Aquarius', 5): 'A council of ancestors.',
    ('Aquarius', 6): 'A masked figure performs ritualistic acts in a mystery play.',
    ('Aquarius', 7): 'A child born out of an eggshell.',
    ('Aquarius', 8): 'Beautifully gowned wax figures on display.',
    ('Aquarius', 9): 'A flag is seen turning into an eagle.',
    ('Aquarius', 10): 'A popularity that proves to be fleeting.',
    ('Aquarius', 11): 'During a silent hour, a man receives a new inspiration which may change his life.',
    ('Aquarius', 12): 'People on a vast staircase, graduated upwards.',
    ('Aquarius', 13): 'A barometer.',
    ('Aquarius', 14): 'A train entering a tunnel.',
    ('Aquarius', 15): 'Two lovebirds sitting on a fence and singing happily.',
    ('Aquarius', 16): 'A big-businessman at his desk.',
    ('Aquarius', 17): 'A watchdog standing guard, protecting his master and his possessions.',
    ('Aquarius', 18): 'A man being unmasked at a masquerade.',
    ('Aquarius', 19): 'A forest fire quenched.',
    ('Aquarius', 20): 'A large white dove bearing a message.',
    ('Aquarius', 21): 'A woman disappointed and disillusioned, courageously facing a seemingly empty life.',
    ('Aquarius', 22): 'A rug placed on a floor for children to play on.',
    ('Aquarius', 23): 'A big bear sitting down and waving all its paws.',
    ('Aquarius', 24): 'A man turning his back on his passions teaches deep wisdom from his experience.',
    ('Aquarius', 25): 'A butterfly with the right wing more perfectly formed.',
    ('Aquarius', 26): 'A garage man testing a car’s battery with a hydrometer.',
    ('Aquarius', 27): 'An ancient pottery bowl filled with fresh violets.',
    ('Aquarius', 28): 'A tree felled and sawed to ensure a supply of wood for the winter.',
    ('Aquarius', 29): 'Butterfly emerging from a chrysalis.',
    ('Aquarius', 30): 'Moon-lit fields, once babylon, are blooming white.',
    ('Pisces', 1): 'A crowded public market place.',
    ('Pisces', 2): 'A squirrel hiding from hunters.',
    ('Pisces', 3): 'A petrified forest.',
    ('Pisces', 4): 'Heavy car traffic on a narrow isthmus linking two seaside resorts.',
    ('Pisces', 5): 'A church bazaar.',
    ('Pisces', 6): 'A parade of army officers in full dress.',
    ('Pisces', 7): 'Illuminated by a shaft of light, a large cross lies on rocks surrounded by sea and mist.',
    ('Pisces', 8): 'A girl blowing a bugle.',
    ('Pisces', 9): 'The race begins: intent on outdistancing his rivals, a jockey spurs his horse to great speed.',
    ('Pisces', 10): 'An aviator in the clouds.',
    ('Pisces', 11): 'Men travelling a narrow path, seeking illumination.',
    ('Pisces', 12): 'An examination of initiates in the sanctuary of an occult brotherhood.',
    ('Pisces', 13): 'A sword, used in many battles, in a museum.',
    ('Pisces', 14): 'A lady wrapped in fox fur.',
    ('Pisces', 15): 'An officer drilling his men in a simulated attack.',
    ('Pisces', 16): 'In a quite moment, a creative individual experiences the flow of inspiration.',
    ('Pisces', 17): 'An easter promenade.',
    ('Pisces', 18): 'In a huge tent a famous revivalist conducts his meeting with a spectacular performance.',
    ('Pisces', 19): 'A master instructing his disciple.',
    ('Pisces', 20): 'A table set for an evening meal.',
    ('Pisces', 21): 'A little white lamb, a child and a chinese servant.',
    ('Pisces', 22): 'A prophet bringing down the new law from mount sinai.',
    ('Pisces', 23): 'A ‘materializing medium’ giving a seance.',
    ('Pisces', 24): 'An inhabited island.',
    ('Pisces', 25): 'The purging of the priesthood.',
    ('Pisces', 26): 'A new moon reveals that it’s time for people to go ahead with their different projects.',
    ('Pisces', 27): 'A harvest moon illuminates the sky.',
    ('Pisces', 28): 'A fertile garden under the full moon.',
    ('Pisces', 29): 'Light breaking into many colors as it passes through a prism.',
    ('Pisces', 30): 'A majestic rock formation resembling a face is idealized by a boy who takes it as his ideal of greatness, and as he grows up, begins to look like it.',
}
