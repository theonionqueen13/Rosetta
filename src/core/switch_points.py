"""
switch_points.py — Switch Point Detection & Keystone Guidance
==============================================================

A **switch point** is the zodiacal position that, if occupied by a transit
planet, synastry partner's natal planet, or a deliberately chosen
"keystone," would complete an incomplete shape into a resonant membrane
(drum head or receptive antenna).

Completion map
--------------
    T-Square     → Grand Cross         (drum_head)
    Wedge        → Mystic Rectangle    (resonant_membrane)
    Envelope     → Merkabah            (drum_head)
    Cradle       → Envelope            (extends toward Merkabah)

Activation modes
----------------
    1. Transit      — transiting planet enters the switch-point range
    2. Synastry     — another person's natal planet occupies the range
    3. Keystone     — human-designed structure/habit/practice/object that
                      embodies the switch-point archetype
    4. Location     — (noted but not computed by this app)

The term **keystone** (from architecture — the final stone that locks an
arch in place) is the Rosetta name for any deliberately installed
anchor — object, habit, practice, system, room, tool — that completes
the harmonic circuit represented by the switch point.

Public API
----------
    find_switch_points(chart) → List[SwitchPoint]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from .models_v2 import AstrologicalChart, ChartObject, DetectedShape


# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# Which incomplete shapes complete into which resonant structures
SHAPE_COMPLETIONS: Dict[str, Dict[str, Any]] = {
    "T-Square": {
        "completes_to": "Grand Cross",
        "membrane_class": "drum_head",
        "missing_count": 1,
        "description": (
            "The T-Square is a Grand Cross with one corner missing — a drum "
            "head pulled tight on only three of its four pegs. The missing "
            "fourth point is the switch point."
        ),
    },
    "Wedge": {
        "completes_to": "Mystic Rectangle",
        "membrane_class": "resonant_membrane",
        "missing_count": 1,
        "description": (
            "The Wedge is a Mystic Rectangle with one corner missing — a "
            "receptive antenna missing one of its four support struts. "
            "The missing point is the switch point."
        ),
    },
    "Envelope": {
        "completes_to": "Merkabah",
        "membrane_class": "drum_head",
        "missing_count": 1,
        "description": (
            "The Envelope is a Merkabah with one vertex missing — a super "
            "drum head with five of its six pegs in place. The missing sixth "
            "point is the switch point."
        ),
    },
    "Cradle": {
        "completes_to": "Envelope",
        "membrane_class": None,   # Envelope is a stepping stone toward Merkabah
        "missing_count": 1,
        "description": (
            "The Cradle can extend into an Envelope by adding one more "
            "sextile-chain link and opposition, a step toward the Merkabah "
            "super drum head."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════
# Degree / zodiac helpers
# ═══════════════════════════════════════════════════════════════════════

def _normalize_deg(deg: float) -> float:
    """Normalize a degree value to 0–360."""
    return deg % 360


def _sign_from_longitude(lon: float) -> str:
    """Return the sign name for a 0–360 longitude."""
    idx = int(_normalize_deg(lon) // 30)
    return _SIGNS[idx]


def _degree_in_sign(lon: float) -> int:
    """Return the degree within the sign (1–30, Sabian convention)."""
    raw = _normalize_deg(lon) % 30
    return int(math.ceil(raw)) if raw > 0 else 1


def _opposite_longitude(lon: float) -> float:
    """Return the point 180° away."""
    return _normalize_deg(lon + 180)


def _format_dms(lon: float) -> str:
    """Format a longitude as 'DD°MM' SS\"' within its sign."""
    n = _normalize_deg(lon)
    deg_in_sign = n % 30
    d = int(deg_in_sign)
    remainder = (deg_in_sign - d) * 60
    m = int(remainder)
    s = int((remainder - m) * 60)
    sign_abbr = _sign_from_longitude(n)[:3]
    return f"{d}°{m:02d}'{s:02d}\"{sign_abbr}"


# ═══════════════════════════════════════════════════════════════════════
# Sabian symbol lookup (reuses models_v2 loader)
# ═══════════════════════════════════════════════════════════════════════

_sabian_cache: Optional[dict] = None


def _get_sabians() -> dict:
    """Lazy-load Sabian symbol data."""
    global _sabian_cache
    if _sabian_cache is not None:
        return _sabian_cache
    try:
        from .models_v2 import _load_sabian_symbols_json
        _sabian_cache = _load_sabian_symbols_json()
    except Exception:
        _sabian_cache = {}
    return _sabian_cache


def _sabian_for(sign: str, degree: int) -> Dict[str, str]:
    """Return sabian symbol dict for a sign + degree (1–30)."""
    data = _get_sabians()
    entry = data.get((sign, degree))
    if not entry:
        return {}
    if isinstance(entry, dict):
        return {
            "symbol": entry.get("sabian_symbol", ""),
            "short_meaning": entry.get("short_meaning", ""),
        }
    # If entry is a dataclass or something else, try attribute access
    return {
        "symbol": getattr(entry, "symbol", "") or getattr(entry, "sabian_symbol", ""),
        "short_meaning": getattr(entry, "short_meaning", ""),
    }


# ═══════════════════════════════════════════════════════════════════════
# SwitchPoint dataclass
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class SwitchPoint:
    """A detected switch point — the missing vertex of an incomplete shape."""

    # Source shape info
    source_shape_type: str          # e.g. "T-Square"
    source_members: List[str]       # planet names in the incomplete shape
    completes_to: str               # e.g. "Grand Cross"
    membrane_class: str             # "drum_head", "resonant_membrane", or ""

    # Switch point location
    longitude: float                # 0–360 absolute degree
    sign: str                       # e.g. "Scorpio"
    degree_in_sign: int             # 1–30 (Sabian convention)
    dms: str                        # formatted display string

    # Activation range (accounts for orb spread of source members)
    range_low: float                # lower bound longitude
    range_high: float               # upper bound longitude
    range_description: str          # e.g. "14°–16° Scorpio"

    # Sabian symbol at the switch point degree
    sabian_symbol: str = ""
    sabian_meaning: str = ""

    # Saturn context for keystone guidance
    saturn_sign: str = ""
    saturn_house: int = 0
    saturn_summary: str = ""        # pre-built sentence about Saturn

    # Switch-point house (which natal house does this degree fall in?)
    switch_point_house: int = 0

    # Narrative description
    description: str = ""           # shape completion narrative

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the switch point to a nested dict suitable for JSON output."""
        d: Dict[str, Any] = {
            "source_shape": self.source_shape_type,
            "source_members": self.source_members,
            "completes_to": self.completes_to,
            "membrane_class": self.membrane_class,
            "switch_point": {
                "sign": self.sign,
                "degree": self.degree_in_sign,
                "dms": self.dms,
                "range": self.range_description,
            },
        }
        if self.switch_point_house:
            d["switch_point"]["house"] = self.switch_point_house
        if self.sabian_symbol:
            d["sabian"] = {
                "symbol": self.sabian_symbol,
                "meaning": self.sabian_meaning,
            }
        if self.saturn_sign:
            d["saturn_context"] = {
                "sign": self.saturn_sign,
                "house": self.saturn_house,
                "guidance": self.saturn_summary,
            }
        if self.description:
            d["description"] = self.description
        return d


# ═══════════════════════════════════════════════════════════════════════
# Shape analysis — identify roles and compute switch points
# ═══════════════════════════════════════════════════════════════════════

def _get_positions(chart: "AstrologicalChart") -> Dict[str, float]:
    """Get {planet_name: longitude} from the chart."""
    if chart.positions:
        return dict(chart.positions)
    pos: Dict[str, float] = {}
    for cobj in chart.objects:
        name = cobj.object_name.name if cobj.object_name else ""
        if name:
            pos[name] = cobj.longitude
    return pos


def _get_shape_edges(shape: Any) -> List[Tuple[Tuple[str, str], str]]:
    """Extract edge list from a DetectedShape (dataclass or dict)."""
    if hasattr(shape, "edges"):
        return list(shape.edges)
    if isinstance(shape, dict):
        return list(shape.get("edges", []))
    return []


def _get_shape_members(shape: Any) -> List[str]:
    """Extract member list from a DetectedShape (dataclass or dict)."""
    if hasattr(shape, "members"):
        return list(shape.members)
    if isinstance(shape, dict):
        return list(shape.get("members", []))
    return []


def _get_shape_type(shape: Any) -> str:
    """Extract shape type from a DetectedShape (dataclass or dict)."""
    if hasattr(shape, "shape_type"):
        return shape.shape_type
    if isinstance(shape, dict):
        return shape.get("type", "")
    return ""


def _find_t_square_apex(
    members: List[str],
    edges: List[Tuple[Tuple[str, str], str]],
) -> Optional[str]:
    """Identify the apex of a T-Square from its edges.

    The apex is the planet that appears in two Square edges but NOT in the
    Opposition edge.
    """
    opp_planets: set = set()
    square_planets: List[str] = []

    for (a, b), asp_type in edges:
        clean = asp_type.replace("_approx", "")
        if clean == "Opposition":
            opp_planets.update([a, b])
        elif clean == "Square":
            square_planets.extend([a, b])

    if not opp_planets:
        return None

    # The apex squares both bases but is NOT part of the opposition
    for m in members:
        if m not in opp_planets and square_planets.count(m) >= 2:
            return m

    return None


def _find_wedge_non_opposition_planet(
    members: List[str],
    edges: List[Tuple[Tuple[str, str], str]],
) -> Optional[str]:
    """Identify the planet in a Wedge that is NOT part of the opposition.

    This is the planet whose two connections are trine + sextile.
    The switch point = 180° from this planet to complete the Mystic Rectangle.
    """
    opp_planets: set = set()
    for (a, b), asp_type in edges:
        clean = asp_type.replace("_approx", "")
        if clean == "Opposition":
            opp_planets.update([a, b])

    for m in members:
        if m not in opp_planets:
            return m
    return None


def _find_envelope_missing_sextile_point(
    members: List[str],
    edges: List[Tuple[Tuple[str, str], str]],
    positions: Dict[str, float],
) -> Optional[float]:
    """Compute the missing 6th point for an Envelope → Merkabah completion.

    The Envelope has 5 sextile-chain nodes. The 6th would extend the chain
    and form a third opposition. We find the two chain endpoints (nodes with
    only one sextile connection each) and compute the midpoint of their
    opposition-complement.
    """
    sextile_count: Dict[str, int] = {m: 0 for m in members}
    opp_partners: Dict[str, str] = {}

    for (a, b), asp_type in edges:
        clean = asp_type.replace("_approx", "")
        if clean == "Sextile":
            if a in sextile_count:
                sextile_count[a] += 1
            if b in sextile_count:
                sextile_count[b] += 1
        elif clean == "Opposition":
            opp_partners[a] = b
            opp_partners[b] = a

    # Chain endpoints have exactly 1 sextile connection
    endpoints = [m for m in members if sextile_count.get(m, 0) == 1]
    if len(endpoints) != 2:
        return None

    # The missing 6th point is 180° from whichever endpoint lacks an opposition
    for ep in endpoints:
        if ep not in opp_partners and ep in positions:
            return _opposite_longitude(positions[ep])

    return None


def _find_cradle_extension_point(
    members: List[str],
    edges: List[Tuple[Tuple[str, str], str]],
    positions: Dict[str, float],
) -> Optional[float]:
    """Compute the missing 5th point for a Cradle → Envelope extension.

    The Cradle has 3 sextiles in a chain (A-B-C-D) with A opposite D.
    The 5th point would extend the sextile chain and add a second opposition.
    The chain endpoints that only have 1 sextile: one has the opposition (A or D),
    the other doesn't (C or B). The missing point is ~60° from the endpoint that
    has no opposition, continuing the sextile chain, AND 180° from the member
    that currently only has trine + sextile connections.
    """
    sextile_count: Dict[str, int] = {m: 0 for m in members}
    opp_planets: set = set()

    for (a, b), asp_type in edges:
        clean = asp_type.replace("_approx", "")
        if clean == "Sextile":
            if a in sextile_count:
                sextile_count[a] += 1
            if b in sextile_count:
                sextile_count[b] += 1
        elif clean == "Opposition":
            opp_planets.update([a, b])

    # Chain endpoints: nodes with exactly 1 sextile
    endpoints = [m for m in members if sextile_count.get(m, 0) == 1]
    if len(endpoints) != 2:
        return None

    # The endpoint that has an opposition already (A or D in A-B-C-D)
    # The extension should be opposite the *other* endpoint's opposition partner
    # Actually, simpler: extend from the endpoint that has no opposition
    for ep in endpoints:
        if ep not in opp_planets and ep in positions:
            # Need to figure out which direction the sextile chain goes
            # The missing point should be +60° or -60° from ep
            # and should create a new opposition with someone
            ep_lon = positions[ep]
            # Check ±60° from this endpoint
            for direction in [60, -60]:
                candidate = _normalize_deg(ep_lon + direction)
                # Check if this candidate is ~180° from any member
                for m in members:
                    if m == ep:
                        continue
                    diff = abs(_normalize_deg(candidate - positions[m]))
                    if diff > 180:
                        diff = 360 - diff
                    if 177 <= diff <= 183:  # within ~3° of opposition
                        return candidate
    return None


def _compute_activation_range(
    center_lon: float,
    source_members: List[str],
    positions: Dict[str, float],
) -> Tuple[float, float, str]:
    """Compute the activation degree range for a switch point.

    The range is based on the spread of relevant member degrees around
    the expected angle relationships, clamped to a reasonable orb.
    """
    # Collect the degrees-in-sign of all source members
    member_degrees = []
    for m in source_members:
        if m in positions:
            deg = positions[m] % 30
            member_degrees.append(deg)

    if not member_degrees:
        # Fallback: ±3° orb
        center_in_sign = center_lon % 30
        sign = _sign_from_longitude(center_lon)
        low_d = max(0, center_in_sign - 3)
        high_d = min(30, center_in_sign + 3)
        desc = f"{int(low_d)}°–{int(math.ceil(high_d))}° {sign}"
        sign_base = (int(center_lon) // 30) * 30
        return sign_base + low_d, sign_base + high_d, desc

    min_deg = min(member_degrees)
    max_deg = max(member_degrees)

    # The activation range in the switch point's sign mirrors the member spread
    center_in_sign = center_lon % 30
    sign = _sign_from_longitude(center_lon)
    sign_base = (int(center_lon) // 30) * 30

    # Use the member spread, but also ensure at least ±1° around center
    spread_low = center_in_sign - (center_in_sign - min_deg) if min_deg < center_in_sign else center_in_sign - 1
    spread_high = center_in_sign + (max_deg - center_in_sign) if max_deg > center_in_sign else center_in_sign + 1

    # Clamp to sign boundaries
    spread_low = max(0, min(spread_low, center_in_sign - 1))
    spread_high = min(30, max(spread_high, center_in_sign + 1))

    # Use floor/ceil for clean integer display
    low_i = int(math.floor(spread_low))
    high_i = int(math.ceil(spread_high))
    desc = f"{low_i}°–{high_i}° {sign}"

    return sign_base + spread_low, sign_base + spread_high, desc


# ═══════════════════════════════════════════════════════════════════════
# Saturn context for keystone guidance
# ═══════════════════════════════════════════════════════════════════════

def _saturn_context(chart: "AstrologicalChart") -> Dict[str, Any]:
    """Extract Saturn's sign, house, and a brief guidance sentence."""
    saturn = chart.get_object("Saturn") if hasattr(chart, "get_object") else None
    if not saturn:
        return {}

    sign = saturn.sign.name if saturn.sign else ""
    house = 0
    # Try placidus first, then whole sign
    if saturn.placidus_house and hasattr(saturn.placidus_house, "number"):
        house = saturn.placidus_house.number
    elif saturn.whole_sign_house and hasattr(saturn.whole_sign_house, "number"):
        house = saturn.whole_sign_house.number

    summary = _build_saturn_summary(sign, house)
    return {"sign": sign, "house": house, "summary": summary}


def _build_saturn_summary(sign: str, house: int) -> str:
    """Build a concise sentence about how Saturn shapes keystone selection."""
    if not sign:
        return ""

    parts = [f"Saturn in {sign}"]
    if house:
        parts[0] += f" (house {house})"

    # Element-based structural style
    _FIRE = {"Aries", "Leo", "Sagittarius"}
    _EARTH = {"Taurus", "Virgo", "Capricorn"}
    _AIR = {"Gemini", "Libra", "Aquarius"}
    _WATER = {"Cancer", "Scorpio", "Pisces"}

    if sign in _FIRE:
        parts.append(
            "builds through bold action and visible initiative — "
            "keystones work best when they are active, performative, "
            "and identity-affirming"
        )
    elif sign in _EARTH:
        parts.append(
            "builds through tangible routine and physical structure — "
            "keystones work best when they are material, sensory, "
            "and embedded in daily practice"
        )
    elif sign in _AIR:
        parts.append(
            "builds through intellectual systems and social frameworks — "
            "keystones work best when they involve learning, community, "
            "dialogue, or systematic thinking"
        )
    elif sign in _WATER:
        parts.append(
            "builds through emotional depth and intuitive ritual — "
            "keystones work best when they involve reflection, creativity, "
            "sacred space, or emotional processing"
        )

    return "; ".join(parts) + "."


# ═══════════════════════════════════════════════════════════════════════
# House lookup for switch point degree
# ═══════════════════════════════════════════════════════════════════════

def _house_for_degree(chart: "AstrologicalChart", longitude: float, house_system: str = "placidus") -> int:
    """Determine which house a degree falls in, using chart cusps."""
    cusps: List[float] = []
    for cusp in (chart.house_cusps or []):
        hs = getattr(cusp, "house_system", "")
        if str(hs).lower().strip() == house_system.lower().strip():
            deg = float(getattr(cusp, "absolute_degree", 0))
            cusps.append(deg)

    if len(cusps) < 12:
        # Fallback: whole sign houses
        return int((_normalize_deg(longitude) // 30) + 1)

    # Sort cusps by house number (they should be in order)
    # House N contains degrees from cusp[N-1] to cusp[N]
    lon = _normalize_deg(longitude)
    for i in range(12):
        start = cusps[i]
        end = cusps[(i + 1) % 12]
        if start <= end:
            if start <= lon < end:
                return i + 1
        else:  # wraps around 360°
            if lon >= start or lon < end:
                return i + 1
    return 1  # fallback


# ═══════════════════════════════════════════════════════════════════════
# Main detection — public API
# ═══════════════════════════════════════════════════════════════════════

def find_switch_points(
    chart: "AstrologicalChart",
    house_system: str = "placidus",
) -> List[SwitchPoint]:
    """Detect all switch points in a chart.

    Examines every detected shape, checks whether it matches an incomplete
    resonant structure (T-Square, Wedge, Envelope, Cradle), and computes
    the missing vertex position, activation range, Sabian symbol, and
    Saturn-informed keystone guidance.
    """
    shapes = chart.shapes or []
    positions = _get_positions(chart)
    saturn_ctx = _saturn_context(chart)
    results: List[SwitchPoint] = []

    for shape in shapes:
        shape_type = _get_shape_type(shape)
        completion = SHAPE_COMPLETIONS.get(shape_type)
        if not completion:
            continue

        members = _get_shape_members(shape)
        edges = _get_shape_edges(shape)

        # ── Compute the switch point longitude ─────────────────────
        switch_lon: Optional[float] = None

        if shape_type == "T-Square":
            apex = _find_t_square_apex(members, edges)
            if apex and apex in positions:
                switch_lon = _opposite_longitude(positions[apex])

        elif shape_type == "Wedge":
            non_opp = _find_wedge_non_opposition_planet(members, edges)
            if non_opp and non_opp in positions:
                switch_lon = _opposite_longitude(positions[non_opp])

        elif shape_type == "Envelope":
            switch_lon = _find_envelope_missing_sextile_point(
                members, edges, positions,
            )

        elif shape_type == "Cradle":
            switch_lon = _find_cradle_extension_point(
                members, edges, positions,
            )

        if switch_lon is None:
            continue

        switch_lon = _normalize_deg(switch_lon)

        # ── Compute activation range ──────────────────────────────
        range_low, range_high, range_desc = _compute_activation_range(
            switch_lon, members, positions,
        )

        # ── Zodiac position ───────────────────────────────────────
        sign = _sign_from_longitude(switch_lon)
        deg = _degree_in_sign(switch_lon)
        dms = _format_dms(switch_lon)

        # ── Sabian symbol ─────────────────────────────────────────
        sab = _sabian_for(sign, deg)
        sabian_symbol = sab.get("symbol", "")
        sabian_meaning = sab.get("short_meaning", "")

        # ── House placement ───────────────────────────────────────
        sp_house = _house_for_degree(chart, switch_lon, house_system)

        # ── Build the SwitchPoint ─────────────────────────────────
        sp = SwitchPoint(
            source_shape_type=shape_type,
            source_members=members,
            completes_to=completion["completes_to"],
            membrane_class=completion.get("membrane_class") or "",
            longitude=switch_lon,
            sign=sign,
            degree_in_sign=deg,
            dms=dms,
            range_low=range_low,
            range_high=range_high,
            range_description=range_desc,
            sabian_symbol=sabian_symbol,
            sabian_meaning=sabian_meaning,
            saturn_sign=saturn_ctx.get("sign", ""),
            saturn_house=saturn_ctx.get("house", 0),
            saturn_summary=saturn_ctx.get("summary", ""),
            switch_point_house=sp_house,
            description=completion.get("description", ""),
        )
        results.append(sp)

    return results
