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

FIXED_STAR_LOOKUP = {
    2.9: '⭐ Diphda (Beta Ceti)',
    9.47: '⭐ Algenib (γ\u202fPegasi)\n\nConstellation & Degree: Tip of Pegasus’ wing, ~09°09′\u202fAries\n\nPlanetary Nature: Mars + Mercury (primary), with Jupiter undertones from spectral class\n\nBody part: rules the bottom portion of the skull between the nose and upper lip\n\n\nAlgenib fuels intensity, oratory, and relentless drive. It grants a sharp, determined mind but can create volatility, notoriety, and tension under strain.\n\nPositive:\nPenetrating intellect, decisive speech, inventive ideas, fighting spirit, charisma in writing and rhetoric, pioneering ambition.\n\nShadow:\nViolence, notoriety, dishonor, obsessive drive, hypocrisy, accident-proneness, neurological stress around the face and jaw.',
    14.62: '⭐ Alpheratz (Alpha Andromedae)',
    20.22: '⭐ Revati (Zeta Piscium)',
    22.27: '⭐ Baten Kaitos (Zeta Ceti)',
    27.13: '⭐ Al Pherg (Eta Piscium)',
    28.17: '⭐ Vertex / Andromeda Galaxy (M31)\nConstellation & Degree: Near the head of Andromeda, ~27–28° Aries (approximate)\n\nPlanetary Nature: Mars + Moon\n\nBody part: rules slightly to the back of the crown of the head\n\nThis galactic force amplifies unconscious drives, deep passions, and psychic instability. It can bring visionary healing potential—or erupt as obsession, illness, or psychic fragmentation.\n\nPositive:\nIntense drive to succeed, gift for healing psychological illness, fearless confrontation of neurosis or shadow, mystic insight, transmutation through inner fire.\n\nShadow:\nBlindness (literal or psychic), obsession, violence, mental illness, martyrdom, self-sabotage, inherited trauma, psychic instability, risk of violent death.',
    29.7: '⭐ Al Rescha (α\u202fPiscium)\nConstellation & Degree: Knot of the Fishes (Pisces), ~29° Aries\n\nPlanetary Nature: Mars + Mercury (traditional); Spectral Class A2 suggests Venusian influence\n\nBody part: not specified in current sources\n\nAl Rescha marks the binding point of Pisces—linking paths, people, and ideas. A stabilizing node in a sea of chaos, it grants orientation and unity, or confusion if untethered.\n\nPositive:\nUnifier of people and systems, spiritual lifeline, creative intelligence, navigational wisdom, artist’s grace, connector of disparate threads, clarity in uncertainty.\n\nShadow:\nIndecision, over-attachment, entanglement in others’ karma, anxiety, illusion of direction, misjudged loyalty, scandals when misaligned.',
    30.72: '⭐ Mirach (Beta Andromedae)',
    33.52: '⭐ Mesarthim (Gamma Arietis)',
    34.28: '⭐ Sheratan (Beta Arietis)',
    37.98: '⭐ Hamal (Alpha Arietis)',
    38.13: '⭐ Schedar (Alpha Cassiopeiae)',
    44.55: '⭐ Almach (γ\u202fAndromedae)\n\nConstellation & Degree: Foot of Andromeda, ~14°14′\u202fTaurus\n\nPlanetary Nature: Venus (Ptolemy, Robson), with alternating Mars/Jupiter influences per Ebertin and spectral data\n\nBody part: rules the left side of the neck\n\n\nAlmach brings charm, beauty, and public favor through expressive grace and romantic magnetism.\n\nPositive:\nArtistic brilliance, cheerful sociability, creative elegance, public recognition.\n\nShadow:\nVanity, insecurity, emotional dependence, overindulgence, blocked creative fulfillment.',
    44.63: '⭐ Menkar (α Ceti)\nConstellation & Degree: Cetus, around 14°–15° Taurus\n\nPlanetary Nature: Saturn (primary), with influence from Mars, Venus, and the Moon depending on source\n\nBody part: Rules the thyroid gland\n\nMenkar sits in the mouth or nose of the great sea monster, Cetus. As a powerful Saturn-type star, it often correlates with collective fear, karmic consequence, and ancestral burdens. It can mark the individual as a carrier of deep social or familial grief, especially through illness, misfortune, or sacrifice. Its influence can be sobering, even harsh, but when integrated, it fosters great humility, wisdom, and resilience through hardship. This star often speaks to the tension between isolation and service.\n\nPositive:\nGravitas, endurance, social consciousness, karmic processing of ancestral or collective patterns, capacity to mature through trials, ability to withstand disgrace and rebuild.\n\nShadow:\nIllness, loss of status, vulnerability to attack or ruin, scapegoating, chronic health issues (especially thyroid), deceptive associations, inherited burdens, existential fatigue.',
    48.53: '⭐ Bharani (41 Arietis)',
    51.18: '⭐ Botein (δ Arietis)\nConstellation & Degree: Tail of the Ram, ~27° Aries\n\nPlanetary Nature: [Unspecified; inferred Mars–Mercury by Aries placement]\n\nBotein, once known as Al Butain, meaning “the Little Belly,” was part of the 28th Arabic Moon Mansion along with ε and ρ Arietis. Though modern sky maps place it in the tail of Aries, its origin suggests a connection to the hidden or interior—“belly” as a metaphysical seat of knowing. Lunar rituals aligned to this star emphasized treasure-seeking and restraint of captives, hinting at its ability to both illuminate and contain.\n\nPositive:\nReveals hidden wealth, strategic insight, shrewd in negotiations, perceptive in matters of security and possession.\n\nShadow:\nControl issues, fear of exposure, greed, or confinement—energetically linked to hoarding or power imbalance.',
    54.5: '⭐ Capulus (M34 Perseus)',
    56.48: '⭐ Algol (Beta Persei)',
    60.32: '⭐ Alcyone (Eta Tauri)',
    62.4: '⭐ Mirfak (Alpha Persei)',
    66.13: '⭐ Prima Hyadum (Gamma Tauri)',
    70.12: '⭐ Aldebaran (Alpha Tauri)',
    77.15: '⭐ Rigel (Beta Orionis)',
    81.27: '⭐ Bellatrix (Gamma Orionis)',
    82.18: '⭐ Capella (Alpha Aurigae)',
    82.5: '⭐ Phact (Alpha Columbae)',
    82.68: '⭐ Mintaka (δ Orionis)\nConstellation & Degree: Orion, ~22° Gemini\n\nPlanetary Nature: Saturn + Mercury\n\nBody Part: Left side of the 8th vertebra (First Dorsal)\n\nA lucky and dignified star, Mintaka grants honor, order, and strength, with a cerebral edge and martial sharpness. It conveys both divine protection and a tendency toward verbal combat. Success comes through disciplined action, organizational skill, and clear moral conviction. Misfortune arises when risk becomes recklessness or argument turns to provocation.\n\nPositive:\nProtection, dignity, mental clarity, organization, energy, moral conviction, strength in battle.\n\nShadow:\nOverzealous arguments, combative pride, reckless crusading, moral rigidity.',
    82.9: '⭐ El Nath (β Tauri)\nConstellation & Degree: Taurus / Auriga crossover, ~22° Gemini\n\nPlanetary Nature: Mars + Mercury (spectrally Jupiter)\n\nBody Part: Right side of the 8th vertebra (First Dorsal)\n\nEl Nath, "The Butting One," sits at the tip of the Bull’s northern horn. It marks a forceful and ambitious nature—headstrong, combative, and skilled with tools or words. Though it offers honor and fortune, the Mars-Mercury mix creates sharp edges: bold pursuit, tactical brilliance, or conflict-prone arrogance. Often a “frontline officer,” this star empowers those willing to charge ahead but warns against stubborn pride and reckless crusading.\n\nPositive:\nFortune, technical skill, ambition, martial clarity, tactical strength, commanding presence.\n\nShadow:\nCombativeness, verbal aggression, obstinance, misfortune through overreach or stubbornness.',
    83.78: '⭐ Alnilam (ε Orionis)\nConstellation & Degree: Orion’s Belt, ~23° Gemini\n\nPlanetary Nature: Jupiter + Saturn (spectrally Jupiter)\n\nBody Part: Diaphragm\n\nAlnilam, the radiant center of Orion’s Belt (from Al Nitham, “String of Pearls”), signals bold achievement and the potential for public acclaim—but often of a fleeting kind. Its Jupiter-Saturn nature lends grandeur, gravitas, and aspiration, yet its brilliance can attract both admiration and danger. Combative, theatrical, and sometimes shameless, Alnilam gives an intense drive for recognition that can elevate or destroy depending on alignment.\n\nPositive:\nHigh honors, dazzling charisma, ambition, leadership, mental sharpness, reward for great effort.\n\nShadow:\nFleeting fame, arrogance, recklessness, dishonor through deceit, romantic scandal, showy aggression.',
    84.03: '⭐ Meissa (Lambda Orionis)',
    85.03: '⭐ Alnitak (Zeta Orionis)',
    85.1: '⭐ Al Hecka (Zeta Tauri)',
    86.72: '⭐ Saiph (Kappa Orionis)',
    88.9: '⭐ Polaris (Alpha Ursae Minoris)',
    89.08: '⭐ Betelgeuse (Alpha Orionis)',
    90.23: '⭐ Menkalinan (Beta Aurigae)',
    93.77: '⭐ Propus (ι\u202fGeminorum)\n\nConstellation & Degree: Between the shoulders of the Twins, ~19°01′\u202fCancer\n\nPlanetary Nature: Mercury + Venus (Robson); with some Sun and Mars influence from spectral class\n\nBody part: rules the top of the stomach\n\n\nPropus enhances associative thinking and psychic receptivity, but can overstimulate the nervous system and gut when imbalanced.\n\nPositive:\nEloquence, intellectual finesse, strength, psychic insight, success in arts or speech.\n\nShadow:\nOverindulgence, neurosis, paranoia, digestive distress, escapism through comfort.',
    95.63: '⭐ Tejat (Mu Geminorum)',
    99.43: '⭐ Alhena (Gamma Geminorum)',
    104.4: '⭐ Sirius (Alpha Canis Majoris)',
    105.3: '⭐ Canopus (α\u202fCarinae)\nConstellation & Degree: Hull of Argo Navis (Carina), ~15° Cancer\n\nPlanetary Nature: Jupiter + Saturn (traditional); Spectral Class A9 adds Venus + Mercury overtones\n\nBody part: Left side below the breast\n\nCanopus is a star of ancient reverence and far-reaching voyages—physical, spiritual, and emotional. Its light can bestow greatness through perseverance, guiding the seeker toward mastery, but often through trials that test the heart and soul.\n\nPositive:\nExpansive vision, love of travel, sacred duty, spiritual authority, transformation through hardship, artistic elevation, profound knowledge, enduring reputation.\n\nShadow:\nEmotional turmoil, exile or isolation, lawsuits, death by water, martyrdom, unrequited love, chronic longing, tendency toward escapism or self-destruction if misaligned.',
    108.85: '⭐ Wasat (Delta Geminorum)',
    110.57: '⭐ Castor (Alpha Geminorum)',
    113.53: '⭐ Pollux (Beta Geminorum)',
    116.1: '⭐ Procyon (α Canis Minoris)\nConstellation & Degree: Canis Minor, ~25° Cancer\n\nPlanetary Nature: Mercury + Mars\n\nBody Part: Below the left eye\n\nBlazing, restless, and fiercely intelligent, Procyon grants rapid rise, sharp instincts, and bold initiative—but warns of burnout, backlash, or fall from grace if not tempered with patience. It’s a star of sudden elevation and equally sudden collapse. Courage, speed, and visionary action are highlighted, but so are temper, pride, and overreach.\n\nPositive:\nSharp mind, psychic protection, swift success, courage under fire, eloquence, fierce loyalty.\n\nShadow:\nImpatience, ego-driven collapse, rage, volatility, fame followed by downfall.',
    127.53: '⭐ Praesepe (M44/The Beehive Cluster)',
    127.87: '⭐ North Asellus/Asellus Borealis (Gamma Cancri)',
    129.05: '⭐ South Asellus/Asellus Australis (Delta Cancri)',
    133.97: "⭐ Acubens (α Cancri)\nConstellation & Degree: Cancer, approx. 13° Leo\n\nPlanetary Nature: Saturn + Mercury (with alternate spectral influence of Venus)\n\nBody Part: Outer tissues of the left kidney\n\nAcubens, located in the southern claw of the Crab, is the slicing point of the Cancer constellation—its name deriving from Al Zubanah, “The Claw.” This is not the gentle, maternal side of Cancer. Acubens bears the knife's edge of intellect under pressure, often manifesting as a quick, reactive mind with a tendency toward cunning, coercion, or forced mental adaptation. Like a nerve exposed, this star can produce brilliance or bitterness—depending on how well the native navigates inner conflict and external pressure.\n\nWhile the Saturn-Mercury combination often connotes cold calculation or systemic thought, Acubens pushes this toward extremes. It can bestow organized brilliance, speculative ability, and enduring tenacity—but also carries the darker archetype of the strategist turned saboteur, or the poisoner whose words cut deeper than any blade.\n\nPositive:\nStrategic mind, resilience under mental pressure, clever underdog, verbal precision, organizational leadership, speculative success, activist thinker.\n\nShadow:\nMalevolence, lying, criminality, internalized rage, poisoning (literal or emotional), repression turned reactive, weaponized intelligence.",
    138.22: '⭐ Alterf (Lambda Leonis)',
    141.03: '⭐ Ras Elhased/Algenubi (Epsilon Leonis)',
    147.6: '⭐ Alphard (Alpha Hydrae)',
    147.9: '⭐ Adhafera (Zeta Leonis)',
    148.23: '⭐ Al Jabbah (Eta Leonis)',
    150.15: '⭐ Regulus (Alpha Leonis)',
    156.05: '⭐ Zhang (Upsilon Hydrae)',
    157.78: '⭐ Thuban (Alpha Draconis)',
    161.65: '⭐ Zosma (δ Leonis)\nConstellation & Degree: Back of the Lion, ~11° Virgo\n\nPlanetary Nature: Saturn + Venus (spectrally Venus)\n\nBody Part: Left side of the body to the back of the lungs\n\nZosma sits on the Lion’s back, a sensitive Saturn–Venus point carrying themes of melancholy, prophetic sensitivity, and moral testing. Often linked with suffering for a higher purpose or finding meaning through disgrace or loss, Zosma marks those who carry both pain and potential for compassionate insight. In ancient Babylon it was part of the Oracle god Kua, lending it visionary and prophetic undertones.\n\nPositive:\nSharp mind, prophetic insight, ability to inspire through vulnerability, strength through adversity, social influence through emotional intelligence.\n\nShadow:\nMelancholy, selfishness, shameless egotism, fear of poison, intestinal issues, disgraceful fame, internalized shame.',
    163.77: '⭐ Coxa (Theta Leonis)',
    171.95: '⭐ Denebola (Beta Leonis)',
    174.03: '⭐ Alkes (Alpha Crateris)',
    177.02: '⭐ Labrum (Delta Crateris)',
    177.27: '⭐ Alkaid (Eta Ursae Majoris)',
    177.52: '⭐ Zavijava (Beta Virginis)',
    182.42: '⭐ Virgo Cluster',
    185.17: '⭐ Zaniah (Eta Virginis)',
    190.27: '⭐ Vindemiatrix (Epsilon Virginis)',
    190.47: '⭐ Porrima/Caphir (Gamma Virginis)',
    193.78: '⭐ Algorab (Delta Corvi)',
    198.0: '⭐ Seginus (Gamma Boötis)',
    202.48: '⭐ Foramen (Eta Carinae)',
    204.18: '⭐ Spica (Alpha Virginis)',
    204.55: '⭐ Arcturus (Alpha Boötis)',
    213.48: '⭐ Princeps (δ\u202fBoötis)\n\nConstellation & Degree: Spear of Boötes (the Herdsman), ~03°10′\u202fScorpio\n\nPlanetary Nature: Mercury + Saturn (Robson, Ptolemy); Sun influence from spectral type\n\nBody part: rules four inches below the navel\n\n\nPrinceps grants mental depth, discipline, and protective authority.\n\nPositive:\nResearch skill, leadership, spiritual resilience, loyalty to duty.\n\nShadow:\nFear-driven restraint, self-doubt, obsessive overthinking, karmic burdens.',
    214.13: '⭐ Syrma (Iota Virginis)',
    217.28: '⭐ Khambalia (Lambda Virginis)',
    222.18: '⭐ Acrux (Alpha Crucis)',
    222.62: '⭐ Alphecca (Alpha Coronae Borealis)',
    225.4: '⭐ Zubenelgenubi (α Librae)\nConstellation & Degree: Libra, around 15° Scorpio\n\nPlanetary Nature: Saturn + Mars\n\nBody part: Rules the lower half of the colon\n\nZubenelgenubi, the Southern Scale, represents the price of imbalance and unresolved judgment. Its Saturn-Mars nature lends it a heavy, often harsh influence—linked with disgrace, violence, and karmic retribution. It can indicate entanglement in injustice, obsession with punishment, or being cast into roles of villain or victim. Still, it can also forge fierce protectors and uncompromising truth-tellers—if the energy is tempered with wisdom.\n\nPositive:\nCourage to confront wrongs, karmic awareness, power to rectify imbalance, unflinching pursuit of truth, ability to hold space for social or relational shadow.\n\nShadow:\nDisgrace, malevolence, unforgiveness, violent tendencies, abuse of authority, miscarriages of justice, inflammatory illness (especially in the colon), karmic backlash.',
    229.7: '⭐ Zubenelgenubi (α Librae)\nConstellation & Degree: Libra, around 15° Scorpio\n\nPlanetary Nature: Saturn + Mars\n\nBody part: Rules the lower half of the colon\n\nZubenelgenubi, the Southern Scale, represents the price of imbalance and unresolved judgment. Its Saturn-Mars nature lends it a heavy, often harsh influence—linked with disgrace, violence, and karmic retribution. It can indicate entanglement in injustice, obsession with punishment, or being cast into roles of villain or victim. Still, it can also forge fierce protectors and uncompromising truth-tellers—if the energy is tempered with wisdom.\n\nPositive:\nCourage to confront wrongs, karmic awareness, power to rectify imbalance, unflinching pursuit of truth, ability to hold space for social or relational shadow.\n\nShadow:\nDisgrace, malevolence, unforgiveness, violent tendencies, abuse of authority, miscarriages of justice, inflammatory illness (especially in the colon), karmic backlash.',
    232.4: '⭐ Unukalhai (Alpha Serpentis)',
    234.12: '⭐ Agena (Beta Centauri)',
    239.77: '⭐ Bungula (Alpha Centauri)',
    242.62: '⭐ Yed Prior (δ Ophiuchi)\nConstellation & Degree: Ophiuchus, approx. 3° Sagittarius\n\nPlanetary Nature: Saturn + Venus\n\nBody Part: Rules the left side of the second lumbar vertebra\n\nYed Prior, "The Fore Star of the Hand," resides in the left hand of the Serpent Holder, just as it grasps the serpent near its head. With a Saturn-Venus charge, this star governs a paradoxical blend of discipline and indulgence, restraint and temptation. It can signify practical healing hands and courageous boundary-keepers—or those who transgress societal or moral codes. In negative charts, it can trigger shamelessness, immorality, or scandal, especially when power is abused. In constructive alignments, it suggests grounded compassion, hands-on healing, and fierce personal integrity.\n\nPositive:\nPractical healer, committed servant, courageous in the face of moral hypocrisy, uses power to protect or reform, determined, touch of the mystic or medical hand.\n\nShadow:\nShamelessness, abuse of position, sexual immorality, chronic spinal or lower back issues, seduction through power, revolutionary without cause, scandal.',
    242.9: '⭐ Dschubba (δ Scorpii)\nConstellation & Degree: Scorpio, approx. 2–3° Sagittarius\n\nPlanetary Nature: Mars + Saturn (with alternate associations to Jupiter or Mercury)\n\nBody Part: Rules the left side of the buttocks\n\nDschubba—also known as Isidis or Acrab—is located in the forehead of the Scorpion, a region known historically as Al Akil Al Jabbah, the “Crown of the Forehead.” Despite its ominous Mars–Saturn charge, Dschubba was one of the few stars in Scorpio once considered auspicious, symbolizing concentrated intelligence, psychic defense, and precision. It marks a zone of extreme intensity and focused will—whether manifesting in surgeons, investigators, occultists, or warriors.\n\nThe darker face of Dschubba includes assault, shamelessness, treachery, or violent backlash. Positively, it grants sharp insight, patient strategy, and unrivaled control under pressure. This is the Scorpio war helm—where every thought is a blade.\n\nPositive:\nStrategic genius, surgical precision, psychic shielding, occult mastery, investigator’s mind, triumph over adversity through secrecy and skill.\n\nShadow:\nAssault, revenge, psychosexual manipulation, secrecy turned corrosive, betrayal of trust, karmic entanglements with violence or dishonor.',
    243.52: '⭐ Graffias / Acrab (β\u202fScorpii)\nConstellation & Degree: Head of the Scorpion (Scorpius), ~3–4° Sagittarius\n\nPlanetary Nature: Mars + Saturn (traditional); some sources add Jupiter or Moon via aspect\n\nBody part: rules the left side of the buttocks, close to the spine\n\nAcrab bestows intense precision, strategic aggression, and hidden depth, but carries potential for venomous projection and deep karmic entanglements if misused.\n\nPositive:\nSurgical skill, investigative genius, mastery in secrecy, persistence under pressure, high intellect, elite success in warfare, medicine, or espionage.\n\nShadow:\nMalevolence, cruelty, contagious illness, treachery, criminality, violent power plays, dangerous research, hidden rot at the core.',
    249.55: '⭐ Han (Zeta Ophiuchi)',
    250.08: '⭐ Antares (Alpha Scorpii)',
    252.28: '⭐ Alwaid (β Draconis, Rastaban)\nConstellation & Degree: Head of the Dragon, ~13° Sagittarius\n\nPlanetary Nature: Saturn + Mars (spectrally Solar)\n\nBody Part: Left side of the spine, 6th Lumbar vertebra\n\nAlwaid, also known as Rastaban or the Dragon’s Eye, sits in the head of Draco and holds ancient significance as a former pole star, once revered in Egyptian temple alignments. Its Saturn-Mars tone sharpens the intellect and intensifies ambition, but also carries a reputation for downfall through violence, dishonor, or criminal behavior. When consciously channeled, it can yield powerful insight and access to ancient wisdom—especially related to healing and hidden knowledge.\n\nPositive:\nProminence, mental intensity, intuitive healing intelligence, visionary leadership, reverence for ancient knowledge.\n\nShadow:\nDishonor, violent downfall, criminal behavior, misuse of power, spinal instability (energetically or literally).',
    256.5: '⭐ Rasalgethi (Alpha Herculis)',
    258.28: '⭐ Sabik (Eta Ophiuchi)',
    262.77: '⭐ Rasalhague (Alpha Ophiuchi)',
    264.33: '⭐ Lesath (υ\u202fScorpii)\n\nConstellation & Degree: Stinger of the Scorpion, ~24°01′\u202fSagittarius\n\nPlanetary Nature: Mercury + Mars (primary); Jupiter influence via spectral type\n\nBody part: rules the middle of the groin\n\n\nLesath transmits piercing intelligence, intense psychic force, and a drive toward revelation or destruction. It is a blade-point star—surgical, exacting, volatile.\n\nPositive:\nKeen insight, fearless intellect, psychic precision, success in science, writing, high-pressure careers, sudden fortune, transformative clarity.\n\nShadow:\nViolence, malice, moral corrosion, obsession, surgical crises, self-destruction, sexual rage, groin-related health issues or energetic trauma.',
    264.92: '⭐ Shaula (Lambda Scorpii)',
    266.12: '⭐ Aculeus (M6 Scorpius)',
    269.03: '⭐ Acumen (M7 Scorpius)',
    270.07: '⭐ Sinistra (Nu Ophiuchi)',
    271.35: '⭐ Spiculum (M8, 18, 20, 21/NGC6523)',
    271.6: '⭐ Alnasl (Gamma2 Sagittarii)',
    273.53: '⭐ Polis (μ\u202fSagittarii)\nConstellation & Degree: Bow of the Archer, ~3° Capricorn\n\nPlanetary Nature: Jupiter + Mars — spiritual rulership, assertive wisdom\n\nBody part: Rules the right leg above the knee\n\nPolis channels the fervor of sacred leadership. It carries the commanding dignity of spiritual authority—philosopher-kings, high priests, moral reformers, or warrior-poets. With a well-placed Sun or MC, the bearer is often chosen by legacy or karma to lead from the frontlines of principle.\n\nPositive:\nNoble ambition, principled leadership, spiritual discipline, compelling vision, philosophical conviction, piercing truthfulness, destiny-bound legacy.\n\nShadow:\nDogmatism, spiritual arrogance, misuse of authority, authoritarian preaching, unmet potential, self-righteous crusading, pretender to thrones they can’t carry.',
    278.63: '⭐ Facies (M22)',
    282.7: '⭐ Nunki (σ Sagittarii)\nConstellation & Degree: Sagittarius, approx. 12° Capricorn\n\nPlanetary Nature: Jupiter + Mercury (with alternate attribution: Saturn + Mercury)\n\nBody Part: Below the left knee\n\nNunki, also known as Pelagus, is one of the few stars in Sagittarius with a strongly dignified Jupiter-Mercury tone that carries a divine authority of voice. The Chaldean name translates to “The Edict of the Sea,” symbolizing law, decree, and sacred order spoken across vast domains—whether oceans, institutions, or ideologies. This is a star of commanding communication—those with Nunki strong in their charts often serve as emissaries, statespeople, broadcasters, or spiritual teachers, with their power rooted in a compelling blend of faith and intellect.\n\nNunki’s influence blends devotion, optimism, and blunt candor. It speaks what others dare not say—often as a disruptive truth that demands restructuring of old systems, values, or assumptions. At its best, Nunki calls the native to embody right speech and use their platform to elevate collective vision. At its worst, it may foster moral hypocrisy or betrayal disguised as righteousness.\n\nPositive:\nSpiritual leadership, visionary communication, unshakable integrity, psychological insight, diplomatic skill, intuitive travel through collective consciousness (empathic direction, psychometry).\n\nShadow:\nReligious superiority, betrayal masked as honesty, opportunistic diplomacy, chronic ideological illness, arrogance of spiritual or moral authority.',
    283.95: '⭐ Ascella (ζ\u202fSagittarii)\n\nConstellation & Degree: Armpit of the Archer (Sagittarius), ~13°38′\u202fCapricorn\n\nPlanetary Nature: Jupiter + Mercury (traditional); spectral influence suggests Venus\n\nBody part: rules below the right knee\n\n\nAscella brings cheerful brilliance, strategic insight, and public honor. It carries spiritual strength and leadership potential, with a gift for placing things in their most effective position.\n\nPositive:\nGood fortune, moral resilience, friendship with powerful allies, success in governance, military, or publishing; visionary planning and grace under pressure.\n\nShadow:\nTroublesome temperament, spiritual frustration, insecurity in relationships, delayed recognition (especially for women), potential for knee discomfort.',
    285.32: '⭐ Manubrium (ο\u202fSagittarii)\nConstellation & Degree: Face of the Archer, ~12° Capricorn\n\nPlanetary Nature: Sun + Mars — vital fire, impact, ignition\n\nBody part: Back of the left knee at the center\n\nFiery and forceful, Manubrium is a volatile fixed star associated with the power of ignition—explosive insight, courageous confrontation, or even literal combustion. It is a trigger point for bold action, inner fire, and physical or political heat.\n\nPositive:\nHeroism, precision under pressure, warrior courage, defiant brilliance, battle instinct, high-performance drive, visionary intensity.\n\nShadow:\nExplosive temper, eye injuries, chronic inflammation, burnout, excessive pride, blind aggression, fire-related trauma, or obsession with control.',
    285.63: '⭐ Vega (α\u202fLyrae)\nConstellation & Degree: The Harp (Lyra), ~15° Capricorn\n\nPlanetary Nature: Venus + Mercury — grace, harmony, charisma\n\nBody part: Back of the right knee\n\nVega is the song of the soul—radiant, poetic, and magnetic. It confers musical or artistic brilliance, public appeal, and refined ideals, but can also inflate ego or obscure truth in pursuit of fame.\n\nPositive:\nArtistic mastery, popularity, poetic genius, refinement, charisma, harmony in public life, psychic and musical gifts, protector of visionaries.\n\nShadow:\nVanity, entitlement, fleeting fame, seduction by praise, egotism, laziness masked as inspiration, emotional detachment, exploitative charm.',
    286.58: '⭐ Albaldah (π\u202fSagittarii)\nConstellation & Degree: Head of the Archer, ~11° Capricorn\n\nPlanetary Nature: Mercury + Saturn — mind control, solemn focus\n\nBody part: Rules the upper inside of the left thigh\n\nAlbaldah carries the weight of wisdom, structure, and inner resolve. It lends gravitas and foresight, yet can produce suppression of emotional expression and inner tension if not consciously transmuted.\n\nPositive:\nStrategic mind, organizational power, maturity beyond years, solitude as strength, sacred architecture, steady judgment, long-term vision.\n\nShadow:\nEmotional repression, chronic over-seriousness, depressive cycles, rigid thinking, burnout from excessive duty, or fear of vulnerability.',
    286.97: '⭐ Rukbat (Alpha Sagittarii)',
    290.12: '⭐ Deneb el Okab Australis (Zeta Aquilae)',
    296.17: '⭐ Terebellum (ω\u202fSagittarii)\nConstellation & Degree: Tail of the Archer (Sagittarius), ~27–28° Capricorn\n\nPlanetary Nature: Venus + Saturn (traditional); Sun influence from spectral type\n\nBody part: rules three inches below the right knee\n\nTerebellum confers ambition, leadership, and calculated success, but often at a cost—emotional regret, moral compromise, or ruthless self-interest.\n\nPositive:\nPerseverance, strategic ambition, leadership in complex systems, success through endurance, high status potential.\n\nShadow:\nCunning, moral ambiguity, emotional detachment, regret after gain, self-destruction, repulsiveness when misaligned.',
    301.58: '⭐ Albireo (β Cygni)\nConstellation & Degree: Cygnus, approx. 24° Aquarius\n\nPlanetary Nature: Venus + Mercury (with some sources noting Martian undertones)\n\nBody Part: 7 inches below the bend of the left knee\n\nAlbireo, the radiant beak of the celestial Swan, offers a poetic and magnetic social aura—marked by charisma, artistry, and a refined aesthetic sensibility. With its twin tones of Venus and Mercury, Albireo shines through gentle charm, eloquence, and grace under pressure, especially in moments of hardship or despair. Those marked by this star are often beloved by others, even when their own emotional landscape is stormy.\n\nThere’s a bittersweet undertone to Albireo’s influence—fame, fortune, and adoration may come with or because of misfortune. The Swan flies highest when dignity is preserved through trials; downfall tends to follow when success is not tempered by humility. This star encourages expression through beauty, particularly in moments where words or appearances fail.\n\nPositive:\nElegant voice, diplomatic beauty, magnetic warmth, artistry in adversity, lovable disposition, thoughtful communication, graceful movement, visual or poetic expression.\n\nShadow:\nDespair masked with charm, social downfall after pride, indiscretion, emotional escapism, loss through over-identification with aesthetic success or idealized persona.',
    302.1: '⭐ Altair (α Aquilae)\nConstellation & Degree: Aquila, approx. 2° Aquarius\n\nPlanetary Nature: Mars + Jupiter (with noted spectral influence of Venus, and secondary associations with Mercury)\n\nBody Part: 7 inches below the bend of the left knee\n\nAltair, the piercing eye of the celestial Eagle, imbues the native with boldness, ambition, and fierce independence. Often linked with military prowess and elevated command, this star lifts individuals into positions of visibility or honor, often through acts of courage or sheer force of will. Its Mars–Jupiter signature is explosive yet regal—like the eagle diving from the heights, swift and sovereign.\n\nAquila, the constellation housing Altair, is associated with powerful empires, divine ascent, and celestial surveillance. It portends clairvoyance, sudden changes in environment or politics, and rulership over matters such as space travel, aerial warfare, imperial power structures, and religious institutions. Its link to the Roman Catholic Church, the United States, and the European Union highlights its impact on collective destiny and ideological authority.\n\nWhen well-aspected, Altair grants fame, leadership, and valor. But without grounding, it may produce those who rise too fast, act rashly, or fall into disgrace after overreaching. Power with principle leads to lasting flight; power without it invites a crash.\n\nPositive:\nCourageous, visionary, commanding presence, penetrating mind, ambition with conviction, military or legal advancement, clairvoyance, success in politics or statecraft, technological influence, respected by peers.\n\nShadow:\nOverbearing pride, foolhardy risks, fall from grace, ruthlessness, mischief-making, fleeting success, destructive ambition, misuse of power, danger through high-tech weaponry or political overreach.',
    304.1: '⭐ Algedi/Giedi (Alpha Capricorni)',
    304.37: '⭐ Dabith (Beta Capricorni)',
    305.03: '⭐ Oculus (π\u202fCapricorni)\n\nConstellation & Degree: Right eye of Capricornus, ~04°43′\u202fAquarius\n\nPlanetary Nature: Saturn + Venus\n\nBody part: rules two inches below the center of the calf of the left leg\n\n\nOculus imparts cool observation, composure in authority, and a grounded sense of tradition, but may struggle with moral clarity or emotional coldness when afflicted.\n\nPositive:\nCalm leadership, steady intellect, resilience, practical intuition, gains through marriage or institutional support.\n\nShadow:\nCold detachment, moral ambiguity, loss in love, leg ailments, lack of foresight, emotional suppression, decay through neglect.',
    305.48: '⭐ Bos (Rho Capricorni)',
    312.05: '⭐ Albali (ε\u202fAquarii)\nConstellation & Degree: Shoulder of the Water Bearer (Aquarius), ~11°43′\u202fAquarius\n\nPlanetary Nature: Saturn + Mercury (traditional); potential Neptune resonance from heliocentric node\n\nBody part: not specified in current sources\n\nAlbali represents hidden threat or blessing — the "Lucky Swallower" swallows light and influence. It brings quiet potency that can tilt toward either fortune or persecution.\n\nPositive:\nHidden strength, stealthy support, sharp perception, helpfulness in crisis, spiritual purification through trials.\n\nShadow:\nSudden danger, persecution, potential for disgrace or fatal entanglement, psychic vulnerability.',
    313.05: '⭐ Armus (η\u202fCapricorni)\nConstellation & Degree: Heart of the Goat (Capricornus), ~12°44′\u202fAquarius\n\nPlanetary Nature: Mars + Mercury (traditional); spectral influence suggests Venus + Mercury\n\nBody part: rules the front of the left leg, 7 inches below the knee\n\nArmus energizes social impact and burden-bearing leadership but brings friction when not directed constructively. It marks those who provoke, lead, or endure under pressure.\n\nPositive:\nWillingness to shoulder responsibility, activist spirit, sharp rhetoric, capacity for social influence through writing, leadership in times of crisis.\n\nShadow:\nNagging, instability, shamelessness, argumentative nature, troublemaking tendencies, contempt for others.',
    314.17: '⭐ Dorsum (Theta Capricorni)',
    316.23: '⭐ Alnair (Alpha Gruis)',
    317.73: '⭐ Sualocin (Alpha Delphini)',
    320.52: '⭐ Castra (Epsilon Capricorni)',
    322.1: '⭐ Nashira (Gamma Capricorni)',
    323.72: '⭐ Sadalsuud (Beta Aquarii)',
    323.87: '⭐ Deneb Algedi (Delta Capricorni)',
    328.08: '⭐ Aljanah (ε\u202fCygni)\nConstellation & Degree: Right wing of the Swan (Cygnus), approx. ~13–14° Aquarius (exact tropical degree may vary slightly depending on source)\n\nPlanetary Nature: Mars (dominant, per Noonan) with additional influence from Mercury and Venus depending on sources and spectral interpretation\n\nBody part: not specified in current sources\n\nAljanah imparts poetic perception, forceful charisma, and a swanlike grace, but with an edge — it flies between elegance and the threat of piercing impact.\n\nPositive:\nBold expression, refined talent, visionary art, powerful voice or presence, connection to birds or aerial symbolism, mystical or poetic insight.\n\nShadow:\nVolatility in affections, aggression masked by charm, arrogance, late-blooming talents, ego-driven expression, sharp-tongued cruelty.',
    333.68: '⭐ Sadalmelek (Alpha Aquarii)',
    334.18: '⭐ Fomalhaut (Alpha Piscis Australis)',
    335.63: '⭐ Deneb Adige (Alpha Cygni)',
    337.05: '⭐ Sadalachbia (Gamma Aquarii)',
    339.18: '⭐ Skat (Delta Aquarii)',
    341.92: '⭐ Hydor (Lambda Aquarii)',
    345.63: '⭐ Achernar (Alpha Eridani)',
    345.82: '⭐ Ankaa (Alpha Phoenicis)',
    353.8: '⭐ Markab (Alpha Pegasi)',
    359.68: '⭐ Scheat (Beta Pegasi)',
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
