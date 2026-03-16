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
from typing import Optional, Dict, List, Tuple

from lookup_v2 import (
	DIGNITIES,
	DIGNITY_SCORES,
	TRIPLICITY_RULERS,
	TERMS,
	FACES,
	SIGN_ELEMENT,
	ELEMENT,
	PLANETARY_RULERS,
)
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
		potency = calculate_potency(h_score, m_score, solar_score)

		# --- Combined: Power Index ---
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

	return states


def score_and_attach(
	chart: AstrologicalChart,
	sect: str = "Diurnal",
	house_system: str = "placidus",
) -> None:
	"""
	Score all planets and attach results to the chart object.

	This is the convenience wrapper that calculate_chart() should call.
	It populates:
	  - chart.planetary_states (dict of PlanetaryState)
	  - chart.mutual_receptions (list of reception tuples)
	  - Each ChartObject.planetary_state
	  - Each ChartObject.station (if stationary)
	"""
	states = score_chart(chart, sect=sect, house_system=house_system)
	chart.planetary_states = states
	chart.mutual_receptions = detect_mutual_receptions(chart.objects)
