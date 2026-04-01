"""
dignity_calc.py — Planetary Strength Engine
============================================

Computes per-chart planetary strength via two vectors:

  Vector A (Authority) — Essential dignity score, normalized via sigmoid.
  Vector B (Potency)   — Accidental dignity: house angularity, motion, solar proximity.
  Power Index          — Combined magnitude of both vectors.

All data comes from lookup_v2.py (DIGNITIES, TRIPLICITY_RULERS, TERMS, FACES,
DIGNITY_SCORES, SIGN_ELEMENT) and the chart's computed positions.

This module is called from calculate_chart() in calc_v2.py after all positions
and houses are resolved but before final return.
"""

import math
import re
from typing import Optional, Dict, List, Tuple

from models_v2 import static_db
DIGNITIES = static_db.DIGNITIES
DIGNITY_SCORES = static_db.DIGNITY_SCORES
TRIPLICITY_RULERS = static_db.TRIPLICITY_RULERS
TERMS = static_db.TERMS
FACES = static_db.FACES
SIGN_ELEMENT = static_db.SIGN_ELEMENT
ELEMENT = static_db.ELEMENT
PLANETARY_RULERS = static_db.PLANETARY_RULERS
from models_v2 import (
	EssentialDignity,
	PlanetaryState,
	ChartObject,
	AstrologicalChart,
)


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

# Station detection: if |speed| < threshold (deg/day), planet is stationary
# These thresholds are generous — real station windows are narrow
STATION_SPEED_THRESHOLDS = {
	"Mercury": 0.10,
	"Venus": 0.05,
	"Mars": 0.03,
	"Jupiter": 0.02,
	"Saturn": 0.015,
	"Uranus": 0.01,
	"Neptune": 0.005,
	"Pluto": 0.004,
	"Chiron": 0.01,
}
DEFAULT_STATION_THRESHOLD = 0.02

# House angularity scores by house number
# Angular (1, 4, 7, 10) = 5; Succedent (2, 5, 8, 11) = 3; Cadent (3, 6, 9, 12) = 1
HOUSE_ANGULARITY = {
	1: 5, 4: 5, 7: 5, 10: 5,       # Angular
	2: 3, 5: 3, 8: 3, 11: 3,       # Succedent
	3: 1, 6: 1, 9: 1, 12: 1,       # Cadent
}

# Solar proximity thresholds (degrees)
CAZIMI_ORB = 0.28          # Within ~17 arcminutes = heart of the Sun
COMBUST_ORB = 8.5          # Traditional combustion boundary
UNDER_BEAMS_ORB = 17.0     # Under the Sun's beams boundary

# Objects exempt from combustion rules (the Sun itself, lunar nodes, angles, etc.)
COMBUST_EXEMPT = {
	"Sun", "North Node", "South Node", "AC", "DC", "MC", "IC",
	"Vertex", "Part of Fortune", "Black Moon Lilith (Mean)",
}

# Only classical planets + Chiron get essential dignity scoring
DIGNITY_ELIGIBLE = {
	"Sun", "Moon", "Mercury", "Venus", "Mars",
	"Jupiter", "Saturn",
}

# All objects that receive accidental dignity scoring (potency)
POTENCY_ELIGIBLE = {
	"Sun", "Moon", "Mercury", "Venus", "Mars",
	"Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
	"Chiron", "Ceres", "Pallas", "Juno", "Vesta",
	"North Node", "South Node", "Eris", "Eros", "Psyche",
	"Black Moon Lilith (Mean)",
}

# ─────────────────────────────────────────────────────────────────────
# Asteroid / minor-body conjunction potency scores
# When one of these objects is conjunct a scoring-eligible planet it
# adds this value to that planet's asteroid_bonus.
#
# Tier 1 (≈ small planet): score 3.0
#   Major goddess asteroids + Black Moon Lilith
# Tier 2 (significant body): score 2.0
#   Eros, Psyche, outer dwarfs / centaurs
# Tier 3 (notable minor body): score 1.0
#   Named minor asteroids present in the chart
# ─────────────────────────────────────────────────────────────────────
ASTEROID_POTENCY_SCORES: Dict[str, float] = {
	# Tier 1 — major archetypes, treated as small planets
	"Ceres": 3.0,
	"Pallas": 3.0,
	"Juno": 3.0,
	"Vesta": 3.0,
	"Black Moon Lilith (Mean)": 3.0,
	# Tier 2 — significant but secondary bodies
	"Eros": 2.0,
	"Psyche": 2.0,
	"Eris": 2.0,
	"Chiron": 2.0,   # Counts only as a *bonus to others*, not double-scored for itself
	"Sedna": 2.0,
	"Haumea": 2.0,
	"Makemake": 2.0,
	"Orcus": 2.0,
	"Quaoar": 2.0,
	"Nessus": 2.0,
	"Ixion": 2.0,
	"Varuna": 2.0,
	# Tier 3 — named minor asteroids
	"Hygiea": 1.0,
	"Iris": 1.0,
	"Thalia": 1.0,
	"Euterpe": 1.0,
	"Pomona": 1.0,
	"Polyhymnia": 1.0,
	"Harmonia": 1.0,
	"Isis": 1.0,
	"Ariadne": 1.0,
	"Mnemosyne": 1.0,
	"Echo": 1.0,
	"Niobe": 1.0,
	"Eurydike": 1.0,
	"Freia": 1.0,
	"Terpsichore": 1.0,
	"Minerva": 1.0,
	"Hekate": 1.0,
	"Kassandra": 1.0,
	"Lachesis": 1.0,
	"Nemesis": 1.0,
	"Medusa": 1.0,
	"Aletheia": 1.0,
	"Magdalena": 1.0,
	"Arachne": 1.0,
	"Fama": 1.0,
	"Veritas": 1.0,
	"Sirene": 1.0,
	"Siva": 1.0,
	"Lilith (Asteroid)": 1.0,
	"Copernicus": 1.0,
	"Icarus": 1.0,
	"Toro": 1.0,
	"Apollo": 1.0,
	"Osiris": 1.0,
	"Lucifer": 1.0,
	"Anteros": 1.0,
	"Tezcatlipoca": 1.0,
	"Bacchus": 1.0,
	"Hephaistos": 1.0,
	"Panacea": 1.0,
	"Orpheus": 1.0,
	"Dionysus": 1.0,
	"Kaali": 1.0,
	"Asclepius": 1.0,
	"Typhon": 1.0,
	"Hidalgo": 1.0,
}

# ─────────────────────────────────────────────────────────────────────
# Fixed-star nature catalogue
# Keys are the "short_name" values stored in FixedStar / fixed_stars.xlsx.
# "nature" one of: "benefic", "malefic", "neutral"
# Magnitude tier is derived from the FixedStar.magnitude field at runtime;
# this dict only carries the nature so we avoid hard-coding magnitudes
# (the Excel catalog is the authoritative source for those).
# ─────────────────────────────────────────────────────────────────────
FIXED_STAR_NATURES: Dict[str, str] = {
	# 1st-magnitude benefics
	"Regulus": "benefic",       # Royal star; honors and glory (with caution: fall from pride)
	"Spica": "benefic",         # Most reliably fortunate star in the sky
	"Arcturus": "benefic",      # Pioneer, success through own efforts
	"Vega": "benefic",          # Artistic genius, magic, charisma
	"Canopus": "benefic",       # Navigation, wisdom, piety
	"Fomalhaut": "benefic",     # Royal star; spiritual idealism
	"Capella": "benefic",       # Curiosity, broad interests, civic honor
	"Rigel": "benefic",         # Education, achievement, civilization-building
	# 1st-magnitude malefics
	"Algol": "malefic",         # "Demon star"; beheading, chaos, violence, extreme crisis
	"Antares": "malefic",       # Royal star; fierce martial energy, potential ruin through excess
	# 1st-magnitude neutral
	"Aldebaran": "neutral",     # Royal star; great success but must maintain integrity
	"Pollux": "neutral",        # Adventurer; bold but with a shadow side
	"Sirius": "neutral",        # Fame, brilliance, glory, but can burn intensely
	"Deneb Algedi": "neutral",  # Law, justice, stern virtue
	# 2nd-magnitude benefics
	"Zuben Eschamali": "benefic",   # Generosity, success in social reform
	"Ras Alhague": "benefic",       # Healing, integration of opposites
	"Deneb": "benefic",             # Artistic, pious, otherworldly gifts
	"Achernar": "benefic",          # Success in public office, noble aspirations
	"Alphecca": "benefic",          # Poetic and artistic ability, graceful talent
	"Altair": "benefic",            # Boldness, ambition, sudden rise
	"Castor": "benefic",            # Intellectual brilliance, versatility
	# 2nd-magnitude malefics
	"Scheat": "malefic",        # Drowning, misfortune, creative suffering
	"Algedi": "malefic",        # Self-preservation at any cost
	"Facies": "malefic",        # Ruthlessness, blindness (literal and metaphorical)
	"Alcyone": "malefic",       # Sorrow, weeping; Pleiades grief-star
	"Unukalhai": "malefic",     # Immorality, trouble through own vices
	"Zaurak": "malefic",        # Despondency, fear, tendency toward gloom
	"Alnilam": "malefic",       # Fleeting fame, oratorical gifts with instability
	# 2nd-magnitude neutral
	"Vindemiatrix": "neutral",  # The "star of widowhood"; loss but also resilience
	"Procyon": "neutral",       # Quick rise followed by equally quick fall
	"Acrab": "neutral",         # Intensity, strategic intelligence
	"Zuben Elgenubi": "neutral",# Legal matters, social-justice themes, reform
	"Zosma": "neutral",         # Strength forged through victimization; service through suffering
	"Murzim": "neutral",        # Preparation; heralding something significant
	# 3rd-magnitude benefics
	"Acrux": "benefic",         # Sacred, ceremonial, shamanic
	"Gacrux": "benefic",        # Navigation, direction, clarity of purpose
	"Sualocin": "benefic",      # Joy, playfulness, dolphin energy
	"Bos": "benefic",           # Patience, endurance, agricultural stability
	# 3rd-magnitude malefics / difficult
	"Bungula": "malefic",       # Idealism pushed to dangerous extremes
	"Aculus": "malefic",        # Blindness, sharp trauma
	"Terebellum": "malefic",    # Cunning resourcefulness with moral cost
}


def _fixed_star_potency(magnitude: float, nature: str) -> float:
	"""
	Convert a fixed star's magnitude and nature into a potency bonus.

	Tier	Magnitude range		benefic		neutral		malefic
	  1		< 1.5				+5.0		+3.0		+2.0
	  2		1.5 – 2.49			+3.0		+2.0		+1.0
	  3		2.5 – 3.49			+2.0		+1.0		+0.5
	  4		≥ 3.5				0.0			0.0			0.0    (too faint to score)

	Even malefic stars add *some* potency — a hard star still amplifies.
	The nature is used by the profile layer for narrative tone, not to zero-out.
	"""
	if magnitude < 1.5:
		return {"benefic": 5.0, "neutral": 3.0, "malefic": 2.0}.get(nature, 3.0)
	elif magnitude < 2.5:
		return {"benefic": 3.0, "neutral": 2.0, "malefic": 1.0}.get(nature, 2.0)
	elif magnitude < 3.5:
		return {"benefic": 2.0, "neutral": 1.0, "malefic": 0.5}.get(nature, 1.0)
	return 0.0


# ─────────────────────────────────────────────────────────────────────
# Minor-orb conjunction detection (used internally to avoid circular
# imports — calc_v2 already has build_aspect_edges but cannot be
# imported from here without a circular dependency).
# ─────────────────────────────────────────────────────────────────────
_MINOR_CONJ_ORB = 2.0   # tighter orb for minor-body conjunctions


def _local_sep_deg(a: float, b: float) -> float:
	"""Unsigned arc 0..180 between two ecliptic longitudes."""
	d = abs(a - b) % 360.0
	return d if d <= 180.0 else 360.0 - d


def _build_conjunction_edges(chart: "AstrologicalChart", orb: float = 4.0) -> list:
	"""
	Detect conjunction edges among all chart objects (major + minor).
	Returns list of (name_a, name_b, {"aspect": "Conjunction", "orb": float}).
	This is a lightweight clone of build_aspect_edges limited to conjunctions,
	used internally so dignity_calc.py stays independent of calc_v2.py.
	"""
	lons: Dict[str, float] = {
		obj.object_name.name: obj.longitude
		for obj in chart.objects
		if obj.object_name and obj.longitude is not None
	}
	names = list(lons.keys())
	edges = []
	for i in range(len(names)):
		for j in range(i + 1, len(names)):
			a, b = names[i], names[j]
			sep = _local_sep_deg(lons[a], lons[b])
			if sep <= orb:
				edges.append((a, b, {"aspect": "Conjunction", "orb": round(sep, 3)}))
	return edges


def _build_cluster_map(conjunction_edges: list) -> Tuple[Dict[str, int], List[List[str]]]:
	"""
	BFS over conjunction edges → connected components.
	Returns (cluster_map, cluster_member_lists):
	  cluster_map  : {object_name → cluster_id}
	  clusters     : list of sorted member-name lists, one per cluster (size ≥ 2)
	"""
	from collections import defaultdict, deque

	adj: Dict[str, set] = defaultdict(set)
	all_nodes: set = set()
	for a, b, _meta in conjunction_edges:
		adj[a].add(b)
		adj[b].add(a)
		all_nodes.update((a, b))

	visited: set = set()
	cluster_map: Dict[str, int] = {}
	clusters: List[List[str]] = []

	for start in list(all_nodes):
		if start in visited:
			continue
		comp: List[str] = []
		q: deque = deque([start])
		visited.add(start)
		while q:
			u = q.popleft()
			comp.append(u)
			for v in adj[u]:
				if v not in visited:
					visited.add(v)
					q.append(v)
		if len(comp) >= 2:
			cid = len(clusters)
			clusters.append(sorted(comp))
			for obj in comp:
				cluster_map[obj] = cid

	return cluster_map, clusters


# ═══════════════════════════════════════════════════════════════════════
# Vector A: Essential Dignity (Authority)
# ═══════════════════════════════════════════════════════════════════════

def _get_sign_element(sign_name: str) -> str:
	"""Return element name for a sign, e.g., 'Aries' → 'Fire'."""
	return SIGN_ELEMENT.get(sign_name, "")


def resolve_essential_dignity(
	planet_name: str,
	sign_name: str,
	degree_in_sign: float,
	sect: str = "Diurnal",
) -> EssentialDignity:
	"""
	Determine ALL essential dignities a planet holds at a specific sign/degree.

	Unlike the old _resolve_dignity() which returns only the single highest,
	this returns a full breakdown so we can sum weighted scores.

	Parameters
	----------
	planet_name : str
		Base planet name (e.g., "Mars", not "Mars (retrograde)").
	sign_name : str
		Sign the planet occupies (e.g., "Aries").
	degree_in_sign : float
		Degree within the sign, 0.0–29.999...
	sect : str
		"Diurnal" or "Nocturnal" — needed for triplicity determination.

	Returns
	-------
	EssentialDignity
		Full breakdown of all dignities this planet holds here.
	"""
	import re
	base_name = re.sub(r"\s*\(.*?\)\s*$", "", planet_name).strip()

	ed = EssentialDignity()

	# --- Domicile / Detriment / Exaltation / Fall (from DIGNITIES) ---
	sign_data = DIGNITIES.get(sign_name, {})
	if base_name in (sign_data.get("domicile") or []):
		ed.domicile = True
	if base_name in (sign_data.get("detriment") or []):
		ed.detriment = True
	if base_name in (sign_data.get("exaltation") or []):
		ed.exaltation = True
	if base_name in (sign_data.get("fall") or []):
		ed.fall = True

	# --- Triplicity (Dorothean, by sect) ---
	element = _get_sign_element(sign_name)
	if element:
		trip_data = TRIPLICITY_RULERS.get(element, {})
		sect_key = "day" if sect == "Diurnal" else "night"
		if trip_data.get(sect_key) == base_name:
			ed.triplicity = True
		elif trip_data.get("participating") == base_name:
			ed.triplicity = True

	# --- Term / Bound (Egyptian terms, degree-specific) ---
	term_list = TERMS.get(sign_name, [])
	int_degree = int(degree_in_sign)
	for end_deg, ruler in term_list:
		if int_degree < end_deg:
			if ruler == base_name:
				ed.term = True
			break

	# --- Face / Decan (Chaldean, 10-degree segments) ---
	face_list = FACES.get(sign_name, [])
	if face_list:
		decan_index = min(int(degree_in_sign // 10), 2)
		if face_list[decan_index] == base_name:
			ed.face = True

	# --- Peregrine check ---
	has_positive = any([ed.domicile, ed.exaltation, ed.triplicity, ed.term, ed.face])
	if not has_positive and not ed.detriment and not ed.fall:
		ed.peregrine = True

	# --- Primary dignity (highest rank that is True) ---
	for label in ("domicile", "exaltation", "triplicity", "term", "face", "detriment", "fall", "peregrine"):
		if getattr(ed, label, False):
			ed.primary_dignity = label
			break

	return ed


def calculate_raw_authority(ed: EssentialDignity) -> float:
	"""
	Sum of weighted essential dignity scores.

	A planet can hold multiple dignities simultaneously (e.g., domicile + face).
	Positive and negative dignities can coexist (e.g., exaltation in one system
	but that's not how it works here — domicile and detriment are mutually
	exclusive per sign). But triplicity/term/face can stack with domicile.
	"""
	score = 0.0
	if ed.domicile:
		score += DIGNITY_SCORES["domicile"]
	if ed.exaltation:
		score += DIGNITY_SCORES["exaltation"]
	if ed.triplicity:
		score += DIGNITY_SCORES["triplicity"]
	if ed.term:
		score += DIGNITY_SCORES["term"]
	if ed.face:
		score += DIGNITY_SCORES["face"]
	if ed.detriment:
		score += DIGNITY_SCORES["detriment"]
	if ed.fall:
		score += DIGNITY_SCORES["fall"]
	return score


def calculate_quality_index(raw_authority: float) -> float:
	"""
	Sigmoid normalization of raw authority.

	QI = tanh(raw_authority / 7)

	This maps the raw score into (-1, 1):
	  - Strong positive dignity → approaches +1
	  - No dignity (peregrine) → 0
	  - Strong debility → approaches -1
	"""
	return math.tanh(raw_authority / 7.0)


# ═══════════════════════════════════════════════════════════════════════
# Vector B: Accidental Dignity (Potency)
# ═══════════════════════════════════════════════════════════════════════

def calculate_house_score(house_number: int) -> float:
	"""
	Angular = 5, Succedent = 3, Cadent = 1.
	Returns 0 if house_number is unknown/invalid.
	"""
	return HOUSE_ANGULARITY.get(house_number, 0.0)


# Objects with no meaningful speed — their Swiss Ephemeris speed is 0 or synthetic
MOTION_EXEMPT = {
	"AC", "DC", "MC", "IC", "Vertex", "Part of Fortune",
	"North Node", "South Node",
}


def classify_motion(
	planet_name: str,
	speed: float,
) -> Tuple[str, float]:
	"""
	Classify a planet's motion state and return (label, score).

	Labels:
	  - "stationary_direct"    → 5.0  (essentially stopped, about to go direct)
	  - "stationary_retrograde"→ 3.5  (essentially stopped, about to go retrograde)
	  - "direct"               → 2.0
	  - "retrograde"           → 1.0

	Sun and Moon never go retrograde, so they always return "direct".
	Calculated points (AC, MC, nodes, etc.) are exempt — returns ("", 0).
	"""
	import re
	base_name = re.sub(r"\s*\(.*?\)\s*$", "", planet_name).strip()

	# Calculated points / angles have no meaningful speed
	if base_name in MOTION_EXEMPT:
		return "", 0.0

	# Sun and Moon never station or retrograde
	if base_name in ("Sun", "Moon"):
		return "direct", 2.0

	threshold = STATION_SPEED_THRESHOLDS.get(base_name, DEFAULT_STATION_THRESHOLD)

	if abs(speed) < threshold:
		# Stationary — which direction is it about to go?
		if speed >= 0:
			return "stationary_direct", 5.0
		else:
			return "stationary_retrograde", 3.5
	elif speed < 0:
		return "retrograde", 1.0
	else:
		return "direct", 2.0


def calculate_solar_proximity(
	planet_name: str,
	planet_longitude: float,
	sun_longitude: float,
) -> Tuple[str, float, float]:
	"""
	Determine a planet's relationship to the Sun by angular distance.

	Returns (label, score, distance):
	  - "cazimi"      → +5.0  (within 0.28° — in the heart of the Sun)
	  - "combust"     → negative gradient  (-5 at 0.28° fading to 0 at 8.5°)
	  - "under_beams" → -1.0  (8.5° to 17°)
	  - ""            → 0.0   (beyond 17° — no solar proximity effect)

	The Sun itself and non-planetary points are exempt.
	"""
	import re
	base_name = re.sub(r"\s*\(.*?\)\s*$", "", planet_name).strip()

	if base_name in COMBUST_EXEMPT:
		return "", 0.0, 0.0

	# Angular distance (shortest arc)
	diff = abs(planet_longitude - sun_longitude)
	if diff > 180.0:
		diff = 360.0 - diff

	if diff <= CAZIMI_ORB:
		return "cazimi", 5.0, diff
	elif diff <= COMBUST_ORB:
		# Linear gradient: -5 at the boundary of cazimi, fading to 0 at 8.5°
		score = -5.0 * (1.0 - diff / COMBUST_ORB)
		return "combust", score, diff
	elif diff <= UNDER_BEAMS_ORB:
		return "under_beams", -1.0, diff
	else:
		return "", 0.0, diff


def calculate_potency(
	house_score: float,
	motion_score: float,
	solar_proximity_score: float,
) -> float:
	"""Sum of all accidental dignity components."""
	return house_score + motion_score + solar_proximity_score


# ═══════════════════════════════════════════════════════════════════════
# Power Index: Combined Strength
# ═══════════════════════════════════════════════════════════════════════

def calculate_power_index(quality_index: float, potency_score: float) -> float:
	"""
	Combined planetary strength magnitude.

	PI = sqrt((|QI| * 0.4)^2 + (P * 0.6)^2) * mu

	Where:
	  QI = quality index (essential dignity, normalized)
	  P  = potency score (accidental dignity, raw sum)
	  mu = 0.85 if QI < 0 (debilitated planets are slightly dampened), else 1.0

	The 0.4/0.6 weighting gives accidental dignity (actual chart conditions)
	slightly more weight than essential dignity (zodiacal placement alone).
	"""
	a_component = abs(quality_index) * 0.4
	p_component = potency_score * 0.6
	magnitude = math.sqrt(a_component ** 2 + p_component ** 2)
	mu = 0.85 if quality_index < 0 else 1.0
	return round(magnitude * mu, 4)


# ═══════════════════════════════════════════════════════════════════════
# Conjunction bonuses: fixed stars & asteroids
# ═══════════════════════════════════════════════════════════════════════

def calculate_conjunction_bonuses(
	obj_name: str,
	chart_obj: "ChartObject",
	all_conjunction_edges: list,
) -> Tuple[float, float, List[str]]:
	"""
	For *one* chart object, compute the potency bonuses it earns from:
	  1. Conjunctions to fixed stars   (via ChartObject.fixed_stars)
	  2. Conjunctions to asteroids/BML (via the unified conjunction-edge list)

	Parameters
	----------
	obj_name : str
		The object's name (e.g. "Venus").
	chart_obj : ChartObject
		The fully populated ChartObject for this planet.
	all_conjunction_edges : list of (a, b, meta) tuples
		Every conjunction edge across the chart (major + minor bodies).

	Returns
	-------
	(asteroid_bonus, fixed_star_bonus, contributors)
	  asteroid_bonus   : float  — sum of ASTEROID_POTENCY_SCORES for all conjunct bodies
	  fixed_star_bonus : float  — sum of _fixed_star_potency() for all conjunct stars
	  contributors     : list[str] — display names for narrative layer
	"""
	asteroid_bonus: float = 0.0
	fixed_star_bonus: float = 0.0
	contributors: List[str] = []

	# 1. Fixed star bonuses — from the pre-populated fixed_stars list on ChartObject
	#    (populated during chart construction from the fixed_stars.xlsx catalog)
	for star in (chart_obj.fixed_stars or []):
		mag = star.magnitude if (star.magnitude is not None and star.magnitude != "") else 4.0
		try:
			mag = float(mag)
		except (TypeError, ValueError):
			mag = 4.0
		nature = FIXED_STAR_NATURES.get(star.short_name, "neutral")
		bonus = _fixed_star_potency(mag, nature)
		if bonus > 0:
			fixed_star_bonus += bonus
			contributors.append(star.short_name)

	# Fallback: parse fixed_star_conj string if fixed_stars list is empty
	# (older chart builds may not have populated the list)
	if not chart_obj.fixed_stars and chart_obj.fixed_star_conj:
		for star_name in re.split(r"[,;]", chart_obj.fixed_star_conj):
			star_name = star_name.strip()
			if not star_name:
				continue
			nature = FIXED_STAR_NATURES.get(star_name, "neutral")
			# Without a magnitude we default to 2nd-magnitude (conservative)
			bonus = _fixed_star_potency(2.0, nature)
			if bonus > 0:
				fixed_star_bonus += bonus
				contributors.append(star_name)

	# 2. Asteroid / minor-body bonuses — scan conjunction edges
	#    A body gets a bonus only when it is conjunct a *different* asteroid;
	#    Chiron is only counted as a bonus-giver, never double-scored for itself.
	for a, b, _meta in all_conjunction_edges:
		other = None
		if a == obj_name:
			other = b
		elif b == obj_name:
			other = a
		if other is None:
			continue
		score = ASTEROID_POTENCY_SCORES.get(other, 0.0)
		if score > 0:
			asteroid_bonus += score
			contributors.append(other)

	return asteroid_bonus, fixed_star_bonus, contributors


def aggregate_cluster_potency(
	states: Dict[str, "PlanetaryState"],
	cluster_map: Dict[str, int],
	clusters: List[List[str]],
) -> None:
	"""
	For each conjunction cluster, sum the potency_score of all members and
	write that aggregate back onto every member's PlanetaryState.

	After this call:
	  state.cluster_id      → index into `clusters` (or None if singleton)
	  state.cluster_potency → aggregate potency of the whole cluster
	  state.cluster_members → sorted list of all member names
	  state.power_index     → recomputed using cluster_potency

	Singletons (not in any cluster) get cluster_potency == potency_score.
	"""
	# Write cluster metadata and aggregated potency onto each member
	for cid, members in enumerate(clusters):
		# Only members that have a PlanetaryState contribute to the sum
		scored_members = [m for m in members if m in states]
		total_potency = sum(states[m].potency_score for m in scored_members)
		for member in scored_members:
			s = states[member]
			s.cluster_id = cid
			s.cluster_potency = round(total_potency, 4)
			s.cluster_members = list(members)
			# Recompute power_index using cluster_potency
			s.power_index = calculate_power_index(s.quality_index, s.cluster_potency)

	# Singletons: cluster_potency mirrors their own potency_score
	for name, s in states.items():
		if s.cluster_id is None:
			s.cluster_potency = s.potency_score
			s.cluster_members = []


# ═══════════════════════════════════════════════════════════════════════
# Mutual Reception Detection
# ═══════════════════════════════════════════════════════════════════════

def detect_mutual_receptions(
	chart_objects: List[ChartObject],
) -> List[Tuple[str, str, str]]:
	"""
	Find mutual reception pairs: Planet A rules B's sign AND Planet B rules A's sign.

	Returns a list of (planet_a, planet_b, reception_type) tuples.
	reception_type is "domicile" (classical mutual reception by rulership).

	Example: Mars in Pisces + Jupiter in Aries → mutual reception
	(Mars rules Aries where Jupiter sits; Jupiter rules Pisces where Mars sits).
	"""
	receptions = []
	seen = set()

	# Build {planet_name: sign_name} mapping
	placements = {}
	for obj in chart_objects:
		if obj.object_name and obj.sign:
			placements[obj.object_name.name] = obj.sign.name

	# Check all pairs
	planet_names = list(placements.keys())
	for i, name_a in enumerate(planet_names):
		sign_a = placements[name_a]
		rulers_of_a = PLANETARY_RULERS.get(sign_a, [])

		for name_b in planet_names[i + 1:]:
			sign_b = placements[name_b]
			rulers_of_b = PLANETARY_RULERS.get(sign_b, [])

			# Classical mutual reception: A rules B's sign AND B rules A's sign
			if name_a in rulers_of_b and name_b in rulers_of_a:
				pair_key = tuple(sorted([name_a, name_b]))
				if pair_key not in seen:
					seen.add(pair_key)
					receptions.append((name_a, name_b, "domicile"))

	return receptions


# ═══════════════════════════════════════════════════════════════════════
# Main Entry Point: Score All Planets in a Chart
# ═══════════════════════════════════════════════════════════════════════

def score_chart(
	chart: AstrologicalChart,
	sect: str = "Diurnal",
	house_system: str = "placidus",
	edges_major: Optional[list] = None,
) -> Dict[str, PlanetaryState]:
	"""
	Compute PlanetaryState for every eligible object in the chart.

	This is the main entry point called from calculate_chart() in calc_v2.py.

	Parameters
	----------
	chart : AstrologicalChart
		Fully constructed chart with objects, houses, and positions.
	sect : str
		"Diurnal" or "Nocturnal" — affects triplicity calculation.
	house_system : str
		Which house system to use for angularity scoring.
		One of "placidus", "equal", "whole_sign".
	edges_major : list, optional
		Pre-computed major aspect edges from build_aspect_edges(). When supplied
		the conjunction-detection step is skipped for major-body pairs (they are
		already in this list). Minor-body conjunctions are always detected locally.

	Returns
	-------
	Dict[str, PlanetaryState]
		Keyed by planet name.
	"""
	states: Dict[str, PlanetaryState] = {}

	# Get Sun longitude for solar proximity calculations
	sun_obj = chart.get_object("Sun")
	sun_lon = sun_obj.longitude if sun_obj else 0.0

	for obj in chart.objects:
		if not obj.object_name:
			continue

		name = obj.object_name.name

		# Skip calculated/derived points — they aren't celestial bodies with
		# meaningful strength.  They still participate in aspects and reception,
		# but authority/potency scoring doesn't apply to them.
		if name in MOTION_EXEMPT:
			continue

		sign_name = obj.sign.name if obj.sign else ""
		degree_in_sign = (obj.longitude % 30) if obj.longitude is not None else 0.0

		# Pick house number based on requested system
		if house_system == "equal":
			house_num = obj.equal_house.number if obj.equal_house else 0
		elif house_system == "whole_sign":
			house_num = obj.whole_sign_house.number if obj.whole_sign_house else 0
		else:
			house_num = obj.placidus_house.number if obj.placidus_house else 0

		# --- Vector A: Essential Dignity (Authority) ---
		if name in DIGNITY_ELIGIBLE:
			ed = resolve_essential_dignity(name, sign_name, degree_in_sign, sect)
			raw_auth = calculate_raw_authority(ed)
			qi = calculate_quality_index(raw_auth)
		else:
			# Non-classical planets don't get essential dignity scoring
			ed = EssentialDignity()
			raw_auth = 0.0
			qi = 0.0

		# --- Vector B: Accidental Dignity (Potency) ---
		h_score = calculate_house_score(house_num)
		motion_label, m_score = classify_motion(name, obj.speed)
		solar_label, solar_score, solar_dist = calculate_solar_proximity(
			name, obj.longitude, sun_lon,
		)
		# Conjunction bonuses are added after all states are built (see below)
		potency = calculate_potency(h_score, m_score, solar_score)

		# --- Combined: Power Index (preliminary — recalculated after cluster aggregation) ---
		pi = calculate_power_index(qi, potency)

		state = PlanetaryState(
			planet_name=name,
			essential_dignity=ed,
			raw_authority=round(raw_auth, 2),
			quality_index=round(qi, 4),
			house_score=h_score,
			motion_score=m_score,
			solar_proximity_score=round(solar_score, 4),
			solar_proximity_label=solar_label,
			potency_score=round(potency, 4),
			power_index=pi,
			motion_label=motion_label,
			solar_distance=round(solar_dist, 4) if solar_dist else None,
		)

		states[name] = state

		# Also attach to the ChartObject for convenience
		obj.planetary_state = state

		# Update station field on ChartObject (was always None before)
		if motion_label == "stationary_direct":
			obj.station = "Stationing direct"
		elif motion_label == "stationary_retrograde":
			obj.station = "Stationing retrograde"

	# ─────────────────────────────────────────────────────────────────
	# Phase 2: Conjunction bonuses (fixed stars + asteroids)
	# ─────────────────────────────────────────────────────────────────
	#
	# Build a unified edge list.  We use a 4° orb for all objects so that
	# asteroid-to-planet conjunctions align with the main aspect engine.
	# If edges_major was passed in from the call site we re-use those edges
	# (they already cover all objects); otherwise we detect locally.
	all_conj_edges: list = []
	if edges_major is not None:
		# Extract only conjunction edges from the pre-built list
		all_conj_edges = [
			(a, b, m) for a, b, m in edges_major
			if isinstance(m, dict) and m.get("aspect") == "Conjunction"
		]
		# Supplement with any minor-body conjunctions not in edges_major
		extra = _build_conjunction_edges(chart, orb=_MINOR_CONJ_ORB)
		existing_pairs = {(a, b) for a, b, _ in all_conj_edges} | {(b, a) for a, b, _ in all_conj_edges}
		for a, b, m in extra:
			if (a, b) not in existing_pairs and (b, a) not in existing_pairs:
				all_conj_edges.append((a, b, m))
	else:
		all_conj_edges = _build_conjunction_edges(chart, orb=4.0)

	# Quick object-name → ChartObject lookup
	obj_lookup = {
		o.object_name.name: o
		for o in chart.objects
		if o.object_name
	}

	for name, state in states.items():
		chart_obj = obj_lookup.get(name)
		if chart_obj is None:
			continue
		ast_bonus, star_bonus, contributors = calculate_conjunction_bonuses(
			name, chart_obj, all_conj_edges,
		)
		if ast_bonus > 0 or star_bonus > 0:
			state.asteroid_bonus = round(ast_bonus, 4)
			state.fixed_star_bonus = round(star_bonus, 4)
			state.conjunction_contributors = contributors
			# Incorporate bonuses into potency_score
			state.potency_score = round(
				state.potency_score + ast_bonus + star_bonus, 4
			)
			# Preliminary power_index update (cluster aggregation may revise again)
			state.power_index = calculate_power_index(
				state.quality_index, state.potency_score
			)

	# ─────────────────────────────────────────────────────────────────
	# Phase 3: Conjunction cluster aggregation
	# Every member of a stellium shares the sum potency of the group.
	# ─────────────────────────────────────────────────────────────────
	cluster_map, clusters = _build_cluster_map(all_conj_edges)
	aggregate_cluster_potency(states, cluster_map, clusters)

	return states


def score_and_attach(
	chart: AstrologicalChart,
	sect: str = "Diurnal",
	house_system: str = "placidus",
	edges_major: Optional[list] = None,
) -> None:
	"""
	Score all planets and attach results to the chart object.

	This is the convenience wrapper that calculate_chart() should call.
	It populates:
	  - chart.planetary_states (dict of PlanetaryState)
	  - chart.mutual_receptions (list of reception tuples)
	  - Each ChartObject.planetary_state
	  - Each ChartObject.station (if stationary)

	Parameters
	----------
	edges_major : list, optional
		Pre-computed major aspect edges from build_aspect_edges().
		When supplied, avoids redundant conjunction detection.
	"""
	states = score_chart(
		chart, sect=sect, house_system=house_system, edges_major=edges_major
	)
	chart.planetary_states = states
	chart.mutual_receptions = detect_mutual_receptions(chart.objects)
