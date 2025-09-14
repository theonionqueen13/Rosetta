# rosetta/lookup.py
# CONSTANTS - All the lookup data in one place

COLOR_EMOJI = {
    "crimson": "🟥",
    "teal": "🟦",
    "darkorange": "🟧",
    "slateblue": "🟪",
    "seagreen": "🟩",
    "hotpink": "🩷",
    "gold": "🟨",
    "deepskyblue": "🟦",
    "orchid": "🟪",
}

ALIASES_MEANINGS = {
    "ASC": "Ascendant",
    "AC": "Ascendant",
    "DSC": "Descendant",
    "MC": "Midheaven",
    "IC": "Imum Coeli",
    "True Node": "North Node",
    "Black Moon Lilith": "Lilith",
}

OBJECT_INTERPRETATIONS = {
    # Axes & Points
    "Ascendant": "The Identity Interface & body-OS bootloader",
    "Descendant": "The Mirror Port for one-to-one contracts & co-regulation",
    "MC": "The Public Interface & executive mission panel",
    "IC": "The Root System & ancestral memory vault",
    "True Node": "The Northbound Vector—evolutionary growth protocol",
    "South Node": "The Ancestral Cache—purge/compost valve for over-learned patterns",
    "Vertex": "The Fate Dock—improbable convergence node",
    "Part of Fortune": "The Ease Circuit—low-friction throughput and natural gains",
    "Black Moon Lilith (Mean)": "The Primal Sovereignty Field—boundary breaker & untamed voltage",

    # Luminaries & Planets
    "Sun": "The Core Reactor & mission kernel",
    "Moon": "The Autonomic Regulator & memory tide",
    "Mercury": "The Signal Router & cognitive codec",
    "Venus": "The Attractor Engine & coherence field",
    "Mars": "The Drive Actuator & ignition vector",
    "Jupiter": "The Meaning Amplifier & growth protocol",
    "Saturn": "The Constraint Architect, time-keeper, & form-governor",
    "Uranus": "The Update Daemon & liberation current",
    "Neptune": "The Dream Renderer & dissolution cloud",
    "Pluto": "The Underworld Compiler & power transmuter",

    # Healing, devotion, sovereignty
    "Ceres": "The Nurture Protocol—cyclical provisioning & metabolic care",
    "Pallas": "The Pattern-Recognition Engine—tactical design & creative strategy",
    "Juno": "The Bond-Contract Manager—commitment format & loyalty spec",
    "Vesta": "The Sacred Focus Kernel—devotional flame & consecrated attention",
    "Lilith": "The Raw Sovereign Impulse—taboo breaker & reclamation surge",
    "Chiron": "The Wound-into-Medicine Bridge—remediation key & apprenticeship path",

    # Muses, arts, memory
    "Iris": "The Spectrum Messenger—bridge-and-translate across bands",
    "Hygiea": "The Sanitation Routine—detox scheduler & systems hygiene",
    "Psyche": "The Deep-Sensing Kernel—bonding depth & intimacy decoder",
    "Thalia": "The Levity Driver—resilience via wit & comedic reframing",
    "Euterpe": "The Melodic Intake—breath-of-inspiration & lyrical flow",
    "Pomona": "The Harvest Module—cultivation, ripeness, and stewardship",
    "Polyhymnia": "The Devotional Channel—sacred rhetoric & potent silence",
    "Harmonia": "The Coherence Balancer—conflict resolver & tonal tuning",
    "Isis": "The Reassembly Protocol—sacred naming & wholeness restoration",
    "Ariadne": "The Labyrinth Navigator—thread management & escape design",
    "Mnemosyne": "The Ancestral Memory Vault—recall indexer & storykeeper",
    "Echo": "The Reflection Loop—call-and-response mapper & resonance check",
    "Niobe": "The Pride-Collapse Lesson—grief calculus & softening cue",
    "Eurydike": "The Underworld Trust Test—retrieval boundary & consent line",
    "Freia": "The Magnetic Allure Field—sovereignty barter & desire economy",
    "Terpsichore": "The Kinetic Rhythm Driver—body-poetry and motion grammar",
    "Minerva": "The Strategic Wisdom Stack—invention schematic & clear seeing",
    "Hekate": "The Threshold Keyring—gate choice, liminal craft, and crossings",
    "Zephyr": "The Gentle Tailwind—signal aeration & effortless drift",
    "Kassandra": "The Unheeded Warning Flag—truth persistence amid noise",
    "Lachesis": "The Timeline Allocator—scope limiter & lifespan apportioner",
    "Nemesis": "The Overreach Corrector—consequences returning to balance",
    "Medusa": "The Gorgon Shield—petrify-to-protect and gaze discipline",
    "Aletheia": "The Disclosure Engine—truth-reveal toggle & clarity lock",
    "Magdalena": "The Redemptive Devotion—eros-as-medicine & lineage healing",
    "Arachne": "The Network Weaver—craft mastery & web-logic (hubris check)",
    "Fama": "The Signal Amplifier—reputation wave & rumor dynamics",
    "Eros": "The Desire Vector—life-force aim & attractive precision",
    "Veritas": "The Integrity Seal—verification checksum & honesty clamp",

    # Makers, rebels, risk
    "Hidalgo": "The Outlaw Ethic—boundary testing & frontier justice",
    "Sirene": "The Siren Call—magnetic lure & navigation of allure tests",
    "Siva": "The Destruction-Creation Pulse—ascetic focus & renewal cycle",
    "Lilith (Asteroid)": "The Embodied Rebel Muse—raw feminine actuator in form",
    "Copernicus": "The Paradigm Pivot Engine—heliocentric reframe & model swap",
    "Icarus": "The Risk-Altitude Gauge—ambition burn limit & heat handling",
    "Toro": "The Raw Torque Channel—stamina, potency, and applied force",
    "Apollo": "The Solar Artistry Beam—precision targeting & performance craft",
    "Koussevitzky": "The Orchestration Lead—ensemble coordination & baton logic",
    "Anteros": "The Reciprocity Circuit—love returned & mutuality check",
    "Tezcatlipoca": "The Obsidian Mirror—shadow tracking & trickster resets",

    # Transpersonal & mythic tech
    "Varuna": "The Cosmic Lawwave—oath-keeping and fluid jurisdiction",
    "West": "The Occidental Vector—dusk-phase transitions & endings craft",
    "Bacchus": "The Ecstatic Release—fermentation, intoxication, and rite",
    "Hephaistos": "The Forge Lab—smithing, prosthetics, and repair invention",
    "Panacea": "The Universal Remedy Hypothesis—integrative fix attempts",
    "Orpheus": "The Music-as-Spell—underworld diplomacy via song",
    "Kafka": "The Metamorphosis Trigger—bureaucracy maze & surreal insight",
    "Pamela": "The Image-Magic Conduit—tarot language & symbolic art channel",
    "Dionysus": "The Ritual Intoxication—boundary dissolution & holy madness",
    "Kaali": "The Serpent Current Monitor—kundalini surge & power handling",
    "Asclepius": "The Clinical Healer Code—crisis medicine & precise repair",
    "Nessus": "The Boundary-Violation Pattern—accountability switch & cycle break",
    "Singer": "The Vocal Node—signature timbre antenna & songcraft focus",
    "Angel": "The Messenger Light Node—protection ping & benevolent signal",
    "Ixion": "The Second-Chance Engine—taboo breaker audit & redemption test",
    "Typhon": "The Primordial Storm Generator—chaos fields & reset weather",
    "Quaoar": "The Creation-Dance Coder—joyful order from primal noise",
    "Sedna": "The Exile Wound Archive—slow-time sovereignty & oceanic depth",
    "Orcus": "The Oath Ledger—underworld contracts & promise enforcement",
    "Haumea": "The Crystalline Birth Matrix—rapid regeneration & lineage splitting",
    "Eris": "The Disruption Catalyst—naming-rights challenger & schism maker",
    "Makemake": "The Ritual Provisioner—island-ecology creativity & feast codes"
}

SHAPE_INSTRUCTIONS = {

    "Wedge": (
        "Three planets in a trine–sextile–opposition triangle. The opposition is the headline polarity; the third planet is the bridge. "
        "It stabilizes one side via the trine (built-in ease) and integrates the other via the sextile (choose-in behaviors). "
        "Lean on the trined planet first, then deliberately engage the sextiled planet to include the opposite pole. "
        "Strengths: fast stabilization, clear routing for major life themes. Failure: comfort bias—overusing the trine and skipping the sextile. "
        "Fix: name and practice the sextile behaviors until they’re native; send the output back across the axis to close the loop."
    ),

    "T-Square": (
        "An opposition with a third planet squaring both ends as the apex. The axis supplies tension; the apex becomes the vector nozzle. "
        "Drive it by balancing both sides of the axis, routing the charge through the apex as a craft (skills, protocols, roles) rather than reactivity. "
        "Use the opposite point (phantom leg) as a pressure release. "
        "Strengths: relentless focus, crisis competence, friction into results. "
        "Failures: ping-ponging between poles, scapegoating/burning the apex. "
        "Fixes: balance axis first, split apex workload into repeatable tasks, and touch the phantom leg often. "
        "Transits: apex hits spike urgency; axis hits tempt polarization; phantom leg hits offer intense, chaotic upgrade portals—stay grounded."
    ),

    "Grand Cross": (
        "Two oppositions locked in four squares—like guy lines pulling in all directions. Feels stabilizing when managed, but spins and launches when mismanaged. "
        "Name both axes; rotate the four jobs in sequence; use center protocols to stop spin. "
        "Strengths: unmatched endurance, load-sharing, sustained momentum. "
        "Failures: burnout, paralysis, whiplash between corners. "
        "Fixes: simple rotation rhythm, floor/ceiling limits, regular center resets. "
        "Transits: any corner pulls the whole grid; axis hits amplify polarization; quadrant hits can open intense, chaotic upgrade portals—stay grounded."
    ),

    "Cradle": (
        "An opposition held by two planets that each trine one outer and sextile the other. Functions like a support sling: tension contained by skillful braces. "
        "Ease first (trines), then deliberate engagement (sextiles). Alternate braces to move charge safely across the axis. "
        "Strengths: elegant mediation, continuous throughput, conflict into growth. "
        "Failures: comfort-looping in the trines, rocking without delivery. "
        "Fixes: name sextile actions, set steady cadence, keep direct axis check-ins. "
        "Transits: outer hits intensify polarity, inner hits open intense, chaotic upgrade portals—stay grounded; trine hits add ease—convert to action."
    ),

    "Mystic Rectangle": (
        "Two oppositions stitched by two parallel trines (rails) and two parallel sextiles (crossovers). Functions like a resonance membrane. "
        "Trines carry tone, sextiles phase-match it, oppositions anchor the tension. Circulate in figure-eights: trine → sextile → opposition → sextile → trine. "
        "Strengths: harmonic entrainment, conflict translation, constant motion without stall. "
        "Failures: over-resonating with noise, dodging opposition work, spinning. "
        "Fixes: install gain controls (time/dose/volume), name a reference tone, ground between passes. "
        "Transits: opposition hits spike amplitude, trines boost flow, sextiles open intense, chaotic upgrade portals—stay grounded."
    ),

    "Grand Trine": (
        "Three trines in a closed loop. Pure ease, low-friction throughput—gift and trap. Needs an external vector or it drifts into pretty motion with no delivery. "
        "Set a clear aim, rotate leadership, and add edges on purpose (deadlines, constraints) to convert flow into results. "
        "Strengths: efficiency, endurance, fast recovery. "
        "Failures: autopilot, insularity, no follow-through. "
        "Fixes: attach to a mission, calendar checkpoints, inject grounded tasks. "
        "Transits: corner hits amplify flow; oppositions give temporary spine; squares can open intense, chaotic upgrade portals—stay grounded."
    ),

    "Kite": (
        "A grand trine with a fourth planet opposing one corner and sextiling the other two. The trine is the airframe; the fourth planet is the spine. "
        "Use the sextile wings to steer the trine’s lift toward the spine’s aim. "
        "Strengths: high efficiency plus direction. "
        "Failures: autopilot drift, chasing spine drama without sextile steering. "
        "Fixes: set a flight plan, schedule sextile reps, alternate the wings. "
        "Transits: spine hits demand aim, sextile hits open intense, chaotic upgrade portals—stay grounded, trine hits boost flow—revector through the spine."
    ),

    "Sextile Wedge": (
        "One trine with a third planet sextiling both ends. Channels a native talent lane through a choice-activated apex. "
        "Strengths: graceful productivity, fast learning, clean delivery. "
        "Failures: coasting on trine with no outcomes, overusing one sextile. "
        "Fixes: name apex tasks, schedule tiny reps, rotate both sextiles. "
        "Transits: apex hits open intense, chaotic upgrade portals—stay grounded; trine hits boost flow—aim it; sextile hits highlight levers to balance."
    ),

    "Unnamed": (
        "One trine, one square, one quincunx. A talent lane, a workbench, and a hazard. Function: convert the trine’s ease through the square into results—never cross the quincunx. "
        "Always detour: trine → square → endpoint or reverse. "
        "Strengths: precision, safe integration. "
        "Failures: hotwiring the quincunx, scapegoating the square, whipsawing endpoints. "
        "Fixes: publish square checklists, lock out the quincunx, pace work in short cycles. "
        "Transits: quincunx hits = red alarm; square hits demand discipline; trine hits boost ease—route through the square."
    ),

    "Lightning Bolt": (
        "Four planets in a square–trine–square–trine zig-zag with the endpoints quincunx. Two Unnamed triangles overlapped. "
        "Use alternating switchback routes to go around the hazard. "
        "Strengths: rapid rerouting, elegant conversion, built-in redundancy. "
        "Failures: hotwiring the quincunx, overworking one adapter, drifting on trines. "
        "Fixes: publish square checklists, alternate the switchbacks, ground between runs. "
        "Transits: quincunx endpoints = red alarm, square hits spike workload, trine hits boost flow—aim it through an adapter. Dual adapter hits can open intense, chaotic upgrade portals—stay grounded."
    ),
}

GLYPHS = {
    "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
    "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
    "Chiron": "⚷", "Ceres": "⚳", "Pallas": "⚴", "Juno": "⚵", "Vesta": "⚶",
    "North Node": "☊", "South Node": "☋", "Part of Fortune": "⊗", "Black Moon Lilith (Mean)": "⚸",
    "Vertex": "☩", "North Node": "☊", "Ascendant": "AC", "Descendant": "DC", "Psyche": "Ψ", "Eros": "♡", 
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
    "North Node", "North Node", "South Node", "Vertex",
]

ZODIAC_SIGNS = ["♈️", "♉️", "♊️", "♋️", "♌️", "♍️", "♎️", "♏️", "♐️", "♑️", "♒️", "♓️"]
ZODIAC_COLORS = ["red", "green", "#DAA520", "blue"] * 3
MODALITIES = ["Cardinal", "Fixed", "Mutable"] * 4
GROUP_COLORS = [
    "crimson", "teal", "darkorange", "slateblue", "seagreen",
    "hotpink", "gold", "deepskyblue", "orchid"
]

# Approximate emoji chips for GROUP_COLORS (works in widget labels)
COLOR_EMOJI = {
    "crimson": "🟥",
    "teal": "🟦",
    "darkorange": "🟧",
    "slateblue": "🟪",
    "seagreen": "🟩",
    "hotpink": "🩷",
    "gold": "🟨",
    "deepskyblue": "🟦",
    "orchid": "🟪",
}

OBJECT_MEANINGS = {
    # Axes & Points
    "Ascendant": "How you show up at first glance—your identity, appearance, vibe, posture, and approach to life.",
    "Descendant": 'What you seek and mirror in close partnerships, and how you relate to others or the archetypal "other"',
    "MC": "Public role and trajectory—how your work, calling, and reputation take visible shape.",
    "IC": "Roots and inner base—home, memory, ancestry, and what truly feels like ‘safe.’",
    "North Node": "Growth direction—the stretch path that opens your future and matures your gifts. The highest and best version of you is in this direction.",
    "South Node": "The natural strengths you bring into this life, your comfort zone, which you must draw from to achieve your North Node goals. It is also where you go to purge, reset, and be re-born.",
    "Vertex": "Fated crossroads—encounters and plot twists that re-route your story.",
    "Part of Fortune": "Your own personal rules for good fortune/luck. During Part of Fortune activations, your personal rules for magic (the Sabian Symbol for your PoF) are in charge of your life.",
    "Black Moon Lilith": 'Sacred no and sovereign yes—your untamed edge, boundaries, and primal honesty. Lilith activations bring out the "AW HELL NAW" response, or deeply powerful feminine magnetism.',

    # Luminaries & Planets
    "Sun": "Core vitality and purpose/primary soul expression—what lights you up and fuels your mission.",
    "Moon": "Emotional climate and instincts—how you self-soothe and stay nourished. The deeper emotional needs and feelings underlying soul expression.",
    "Mercury": "Thinking and communication—how you learn, connect, and make meaning.",
    "Venus": "Value, attraction, sensuality and harmony—what you value, what makes you comfortable and secure (both emotionally and physically), how you bond, value beauty, and build trust. Venus rules matters of money and posessions; all things value-related.",
    "Mars": "Drive and courage—how you pursue, protect, and take decisive action. Mars is the get-up-and-go engine.",
    "Jupiter": "Expansion/growth, philosophy and faith—where you expand, teach, and say a confident yes. Jupiter expands/amplifies everything he touches (via aspect, rulership, transit, etc.)",
    "Saturn": "Time, structure and mastery—your boundaries, responsibilities, and earned authority. Saturn is the timekeeper of your life, and the authority who enforces your discipline.",
    "Uranus": "Liberation, originality, rebellion, innovation and technology—your need for freedom, updates, and breakthroughs. Uranus brings major surprise disruptions to the status quo.",
    "Neptune": "Imagination, dreams, spirituality, fantasies, and illusions—your dreamlife, compassion, and spiritual longing. Neptune rules both true and untrue spiritual visions and dreams, as well as the use of mind-altering substances.",
    "Pluto": "The Underworld Journey: depth and regeneration, power, shadow work, soul retrieval, ancestral memory, and transformational truth. Pluto embodies the energy of intense constriction from all sides, forcing the skeletons out of the closet by turning life inside-out.",

    # Healing, devotion, sovereignty
    "Ceres": "Care cycles—feeding, tending, and the seasonal rhythm of give and receive. Ceres shows our relationship to nurturing ourselves and others; what kind of nurture we need as well as how we nurture the world.",
    "Pallas": "X-Ray vision for seeing the inner workings of whatever it is connected to in the natal chart. Pattern intelligence—strategy, creative problem-solving, and elegant design. Pallas conjunct a natal planet brings high level tactical intelligence to that planet.",
    "Juno": "Commitment style—loyalty, agreements, and what keeps bonds equitable. Juno indicates all things commitment, both in relationships and life pursuits. Keyword: Contracts.",
    "Vesta": "Focused devotion—sacred attention, hearth fire, and purpose as practice. Vesta shows what you tend to day in and day out, as your most sacred flame.",
    "Lilith": "Unfiltered self—refusing shame, reclaiming desire, and standing unowned.",
    "Chiron": "Medicine through experience—your tender spot that becomes a gift to others. Chiron is often called the Wounded Healer. Your Chiron placement indicates your deepest wound, and as you go through that healing journey you become equipped to help others heal similar wounds.",

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
    "Kassandra": "Truth against odds—clear warnings, second sight, and staying with what’s real.",
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
    "Koussevitzky": "Conductor’s touch—coordination, timing, and bringing parts into ensemble.",
    "Anteros": "Reciprocal love—being loved back, mutuality, and earned devotion.",
    "Tezcatlipoca": "Obsidian mirror—seeing shadow clearly and resetting the game board.",

    # Transpersonal & mythic tech
    "Varuna": "Big-water law—oaths, vast accountability, and currents that hold all boats.",
    "West": "Sunset tone—closures, completions, and honoring the day’s last light.",
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
    "Orcus": "Oath keeper—promises, consequences, and the weight of one’s word.",
    "Haumea": "Fertile renewal—rapid regrowth, lineage blessings, and fresh starts.",
    "Eris": "The journey through victimhood and empowerment: being oppressed, learning the truth of that oppression, learning to stand up for yourself, and eventually learning to stand up for others. The key is learning the truth behind the oppression and advocating out loud.",
    "Makemake": "Provision and play—resourceful creativity and community feast codes."
}

ALIASES_MEANINGS = {
    "ASC": "Ascendant",
    "AC": "Ascendant",
    "DSC": "Descendant",
    "MC": "Midheaven",
    "IC": "Imum Coeli",
    "True Node": "North Node",
    "Black Moon Lilith": "Lilith",
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


CATEGORY_MAP = {
    "Character Profiles": {"Sun","Moon","Mercury","Venus","Mars","Jupiter","Saturn","Uranus","Neptune"},
    "Instruments": {
        "Ceres","Pallas","Juno","Vesta","Iris","Hygiea","Psyche","Thalia","Euterpe","Pomona","Polyhymnia",
        "Harmonia","Isis","Ariadne","Mnemosyne","Echo","Niobe","Eurydike","Freia","Terpsichore","Minerva",
        "Hekate","Zephyr","Kassandra","Lachesis","Nemesis","Medusa","Aletheia","Magdalena","Arachne","Fama",
        "Eros","Veritas","Sirene","Siva","Lilith (Asteroid 1181)","Copernicus","Icarus","Toro","Apollo",
        "Koussevitzky","Osiris","Lucifer","Anteros","Tezcatlipoca","West","Bacchus","Hephaistos","Panacea",
        "Orpheus","Kafka","Pamela","Dionysus","Kaali","Asclepius","Singer","Angel"
    },
    "Personal Initiations": {"Chiron","Nessus","Ixion"},
    "Mythic Journeys": {"Pluto","Hidalgo","Varuna","Typhon","Quaoar","Sedna","Orcus","Haumea","Eris","Makemake"},
    "Compass Coordinates": {"Ascendant","Descendant","MC","IC"},
    "Compass Needle": {"True Node","North Node","South Node"},
    "Switches": {"Black Moon Lilith (Mean)","Part of Fortune","Vertex","Anti-Vertex","East Point"},
    "Imprints": {"Fixed Stars"}
} 

CATEGORY_INSTRUCTIONS = {
    "Character Profiles": "Treat these as the primary agents. They have will, drive, and personality. Write their profiles as if they are characters acting within the chart’s system. They initiate, choose, and embody functions.",
    "Instruments": "Treat these as auxiliary tools or implements. They do not act on their own but modify, equip, or flavor the Characters they are attached to. Interpret them as specialized add-ons that enhance or qualify expression.",
    "Personal Initiations": "Treat these as threshold trials and initiatory guides. They mark points of personal wounding, apprenticeship, or rites of passage. Interpret them as initiations the native must undergo, often in embodied or psychological crisis form.",
    "Mythic Journeys": "Treat these as terrains or landscapes. They are collective-scale mythic journeys that reshape the native’s environment. Interpret them as deep fields of transformation that one must endure or traverse, not agents that act.",
    "Compass Coordinates": "Treat these as orienting coordinate markers for the whole chart. They provide direction, aim, and framing. Interpret them as the chart’s compass points, describing location, presentation, public face, and roots.",
    "Compass Needle": "Treat these as the chart’s directional polarity. They mark the karmic vector between where the native has come from and where they are growing toward. Interpret them as the navigational axis of soul trajectory.",
    "Switches": "Treat these as sensitive toggles or thresholds. They activate, invert, or flip circuits. Interpret them as switches that trigger growth arcs, release conditions, or polarity shifts.",
    "Imprints": "Treat these as permanent marks from the heavens. They stamp the chart with mythic inheritance, often conferring unusual talents or fated qualities. Interpret them as imprints that ‘hard-code’ certain powers or vulnerabilities into the native’s system.",
}

HOUSE_SYSTEM_INTERPRETATIONS = {
    "equal": "Interpret Equal House as the Structural Schematic Layer—the body’s architectural blueprint and energetic grid.",
    "placidus": "Interpret Placidus as the Narrative + Trauma Pattern Layer—the psychological time–body interface where memory scripts and emotional timelines run.",
    "whole": "Interpret Whole Sign as the Archetypal + Mythic Layer—the symbolic field that immerses perception in prophecy, dream logic, and mythic meaning.",
    "campanus": "Interpret Campanus as the Spatial Orientation + Visual Field Layer—the horizon-sphere translator that calibrates visual geometry and room-positioning.",
    "koch": "Interpret Koch as the Causal Loop + Psychological Chronology Layer—the personalized clock of formative events and cause-effect echo loops.",
    "regiomontanus": "Interpret Regiomontanus as the Ritual Orientation + Perceptual Direction Layer—the inner compass aligning perception to sacred vectors and cardinal points.",
    "porphyry": "Interpret Porphyry as the Threshold Awareness + Gatekeeping Layer—the initiatory map of inner gates, liminal passages, and decision thresholds.",
    "topocentric": "Interpret Topocentric as the Observer Body + Presence Field Layer—the live-feed interface of being seen/witnessed and arriving in the now-body.",
    "alcabitius": "Interpret Alcabitius as the Status Identity + Role Projection Layer—the social scaffolding where external roles and masks are performed against mirrors."
}

HOUSE_INTERPRETATIONS = {
    1: "Interpret the 1st House as the Identity Interface & body-OS bootloader.",
    2: "Treat the 2nd House as the Resource Engine (value, stability, fuel routing).",
    3: "View the 3rd House as the Local I/O Bus (nervous-system messaging, skill acquisition, neighborhood nodes).",
    4: "Read the 4th House as the Root System & memory vault (home base, attachment roots, inner foundation).",
    5: "Interpret the 5th House as the Creative Kernel & joy engine (self-expression, play, risk, generativity).",
    6: "Treat the 6th House as the Service Lab & maintenance stack (craft, routines, soma-systems).",
    7: "View the 7th House as the Mirror Port (one-to-one bonds, co-regulation, contracts).",
    8: "Read the 8th House as the Deep-Merge Transformer (shared power, taboos, regeneration).",
    9: "Interpret the 9th House as the Meaning-Making Array (exploration, worldview architecture, transmission).",
    10: "Treat the 10th House as the Public Interface & executive panel (role, reputation, mission delivery).",
    11: "View the 11th House as the Network Grid & future lab (alliances, movements, systems innovation).",
    12: "Read the 12th House as the Subconscious Field & sanctuary (dreamwork, dissolution, hidden labs).",
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
        "All major oppositions in a natal chart represent the major over-arching themes of the native’s life. "
        "They are polarities that the native is always working to keep in balance, or their life goes out of balance."
        "List them first when present with other aspects, and explain that the oppositions are the biggest life themes. "
    ),
    "Sesquisquare": (
        "Activation overflow. This is an aspect of momentum, compulsion, and often service. "
        "One planet reaches full activation, and the sesquisquare acts like a surge line — "
        "it pushes energy into the other planet, activating it in a new capacity. "
        "It’s not smooth like a trine, nor tense like a square — it’s quick, sometimes surprising, "
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
        "(trine/sextile/square/sesquisquare/semisextile or a conjunction chain) that converts A’s output into "
        "B’s input via adapters—clear skills, environments, or intermediaries. "
        "The urgency you feel is noise; slow down, build the adapter, then pass the signal. "
        "If the current placements and aspects shown do not provide resolution to re-route the quincunx, "
        "tell the user that other placements not included in this interpretation will be needed to bridge the disconnect."
        "Quincunxes mark injury loops and chronic misfires when hotwired; used correctly, they enforce sound system design."
    )

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