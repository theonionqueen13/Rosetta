"""
planet_profiles.py — Modular profile data containers for Rosetta v2.

Provides three paired dataclass + reader classes:

  PlanetStats / PlanetStatsReader      — raw positional / astronomical data
  PlanetProfile / PlanetProfileReader  — interpretive data (sign/house combos)
  AspectProfile / AspectProfileReader  — aspect interpretation data

Each dataclass has a classmethod that populates it from a ChartObject.
The readers expose format_html() / format_text() methods that produce
output identical to the legacy profiles_v2 sidebar and interp_base_natal
interpretations respectively, so both systems remain backward-compatible.

Circular-import note
--------------------
This module has no module-level dependency on ``profiles_v2``.  It
duplicates the small formatting helpers that ``profiles_v2`` also defines,
so both modules can freely import from ``models_v2`` without a cycle.
``profiles_v2.format_object_profile_html`` and ``NatalInterpreter``
delegate to these readers after construction.
"""

from __future__ import annotations

import html as _html
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .models_v2 import static_db

if TYPE_CHECKING:
    from .models_v2 import ChartObject


# ═══════════════════════════════════════════════════════════════════════
# Shared formatting utilities  (no dependency on profiles_v2)
# ═══════════════════════════════════════════════════════════════════════

_DEG = "°"
_PRIME = "′"
_DPRIME = "″"


def _dms_abs(v: Any) -> str:
    """Return abs(v) as D°M′S″ (unsigned)."""
    if v is None:
        return ""
    v = abs(float(v))
    d = int(v)
    m_f = (v - d) * 60.0
    m = int(m_f)
    s = int(round((m_f - m) * 60.0))
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d += 1
    return f"{d}{_DEG}{m:02d}{_PRIME}{s:02d}{_DPRIME}"


def _fmt_speed_per_day(v: Any) -> str:
    """Speed as DMS/day (absolute value)."""
    return f"{_dms_abs(v)}/day" if v is not None else ""


def _fmt_lat(v: Any) -> str:
    """Ecliptic latitude with hemisphere indicator."""
    if v is None:
        return ""
    hemi = "N" if float(v) >= 0 else "S"
    return f"{_dms_abs(v)} {hemi}"


def _fmt_decl(v: Any) -> str:
    """Declination with hemisphere indicator."""
    if v is None:
        return ""
    hemi = "N" if float(v) >= 0 else "S"
    return f"{_dms_abs(v)} {hemi}"


def _fmt_distance_au_km(au: Any) -> str:
    """Distance as 'X.XXXXXX AU (≈Y km / ≈Z million km)'."""
    if au is None:
        return ""
    au = float(au)
    km = au * 149_597_870.7
    if km >= 1_000_000:
        km_part = f"≈{km / 1_000_000:.1f} million km"
    else:
        km_part = f"≈{int(round(km)):,} km"
    return f"{au:.6f} AU ({km_part})"


_AXIS_MAPPING: Dict[str, tuple] = {
    "AC": ("AC", "Ascendant"),
    "DC": ("DC", "Descendant"),
    "MC": ("MC", "Midheaven"),
    "IC": ("IC", "Immum Coeli"),
    "Ascendant": ("AC", "Ascendant"),
    "Descendant": ("DC", "Descendant"),
    "Midheaven": ("MC", "Midheaven"),
    "Immum Coeli": ("IC", "Immum Coeli"),
}

_AXIS_OBJECTS = frozenset(
    {"Ascendant", "Descendant", "Midheaven", "Immum Coeli", "MC", "IC", "AC", "DC"}
)

_ACDC_NORM = frozenset({"AC", "DC"})

# Canonical key used for deduplication (mirrors profiles_v2._canon)
_CANON_RE = re.compile(r"[^a-z0-9]+")


def _canon(value: str) -> str:
    if not value:
        return ""
    return _CANON_RE.sub("", str(value).lower())


def _format_axis_for_display(obj_name: str) -> str:
    """Format axis object name as 'Full Name (Abbreviation)'.

    Returns "Ascendant (AC)", "Descendant (DC)", etc.
    For non-axis objects, returns the name unchanged.
    """
    if obj_name in _AXIS_MAPPING:
        abbrev, full_name = _AXIS_MAPPING[obj_name]
        return f"{full_name} ({abbrev})"
    parts = obj_name.split()
    if len(parts) >= 2 and parts[0] in ("AC", "DC", "MC", "IC"):
        return f"{' '.join(parts[1:])} ({parts[0]})"
    return obj_name


def _format_house_label(house_num: Any) -> str:
    """Format a house number as ordinal string e.g. '1st House'."""
    if house_num is None:
        return ""
    try:
        h = int(float(house_num))
    except (ValueError, TypeError):
        return str(house_num)
    ordinals = {
        1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th",
        7: "7th", 8: "8th", 9: "9th", 10: "10th", 11: "11th", 12: "12th",
    }
    return f"{ordinals.get(h, f'{h}th')} House"


_COMBO_NAME_MAP: Dict[str, str] = {
    "Ascendant": "AC",
    "Descendant": "DC",
    "Midheaven": "MC",
    "Immum Coeli": "IC",
    "North Node": "NorthNode",
    "South Node": "SouthNode",
    "Black Moon Lilith (Mean)": "Lilith",
    "Black Moon Lilith (True)": "Lilith",
    "Black Moon Lilith": "Lilith",
    "Part of Fortune": "PartOfFortune",
    "AC": "AC", "DC": "DC", "MC": "MC", "IC": "IC",
    "NorthNode": "NorthNode", "SouthNode": "SouthNode",
    "Lilith": "Lilith", "PartOfFortune": "PartOfFortune",
}


def _normalize_for_combo(obj_name: str) -> str:
    """Return the static-database key prefix for an object name."""
    if obj_name in _COMBO_NAME_MAP:
        return _COMBO_NAME_MAP[obj_name]
    return obj_name.replace(" ", "")


def _format_reception_links(items: List[Any]) -> str:
    """Format a list of ReceptionLink objects into a display string."""
    if not items:
        return ""
    parts = []
    for item in items:
        if not item or not item.other or not item.aspect:
            continue
        mode = " (by orb)" if item.mode == "orb" else " (by sign)"
        verb_map = {
            "Conjunction": "Conjunct",
            "Opposition": "Opposite",
            "Trine": "Trine",
            "Square": "Square",
            "Sextile": "Sextile",
        }
        verb = verb_map.get(item.aspect.name, item.aspect.name)
        parts.append(f"{verb} {item.other.name}{mode}")
    return ", ".join(parts)


def _obj_name(chart_obj: Any) -> str:
    """Extract the plain string name from a ChartObject."""
    if hasattr(chart_obj, "object_name"):
        on = chart_obj.object_name
        return on.name if hasattr(on, "name") else str(on)
    return ""


def _get_house_num(chart_obj: Any, house_system: str = "placidus") -> Optional[int]:
    """Get the appropriate house number from a ChartObject."""
    system = (house_system or "placidus").lower().strip()
    if system == "equal":
        h = getattr(chart_obj, "equal_house", None)
    elif system in ("whole", "whole sign", "wholesign"):
        h = getattr(chart_obj, "whole_sign_house", None)
    else:
        h = getattr(chart_obj, "placidus_house", None)
    if h is None:
        for attr in ("placidus_house", "equal_house", "whole_sign_house"):
            h = getattr(chart_obj, attr, None)
            if h is not None:
                break
    if h is None:
        return None
    return h.number if hasattr(h, "number") else int(h)


def _get_house_rulers(chart_obj: Any, house_system: str = "placidus") -> List[str]:
    """Get house ruler names for the given house system."""
    system = (house_system or "placidus").lower().strip()
    if system == "equal":
        rulers = getattr(chart_obj, "house_ruler_equal", [])
    elif system in ("whole", "whole sign", "wholesign"):
        rulers = getattr(chart_obj, "house_ruler_whole", [])
    else:
        rulers = getattr(chart_obj, "house_ruler_placidus", [])
    return [r.name if hasattr(r, "name") else str(r) for r in (rulers or [])]


def _find_objects_in_sign(
    sign_name: str,
    chart_objects: Optional[List[Any]],
    chart: Optional[Any],
) -> List[str]:
    """Return names of chart objects in the given sign."""
    if chart is not None:
        chart_signs = getattr(chart, "chart_signs", None)
        if chart_signs:
            for cs in chart_signs:
                cs_name = cs.name.name if hasattr(cs.name, "name") else str(cs.name)
                if cs_name == sign_name:
                    return [_obj_name(o) for o in (cs.contains or [])]
    if chart_objects:
        return [
            _obj_name(o) for o in chart_objects
            if (lambda s: s.name if hasattr(s, "name") else str(s))(
                getattr(o, "sign", "")
            ) == sign_name
        ]
    return []


def _find_objects_in_house(
    house_num: int,
    chart_objects: Optional[List[Any]],
    chart: Optional[Any],
    house_system: str,
) -> List[str]:
    """Return names of chart objects in the given house."""
    if chart is not None:
        chart_houses = getattr(chart, "chart_houses", None)
        if chart_houses:
            for ch in chart_houses:
                ch_num = (
                    ch.number.number if hasattr(ch.number, "number") else int(ch.number)
                )
                if ch_num == house_num:
                    return [_obj_name(o) for o in (ch.contains or [])]
    if chart_objects:
        result = []
        for o in chart_objects:
            h = _get_house_num(o, house_system)
            if h == house_num:
                result.append(_obj_name(o))
        return result
    return []


def _compute_rules_str(
    chart_obj: Any,
    chart_objects: Optional[List[Any]],
    chart: Optional[Any],
    house_system: str,
) -> str:
    """Build the 'Rules: ...' line for a chart object."""
    rules_signs_list = getattr(chart_obj, "rules_signs", []) or []
    rules_houses_list = getattr(chart_obj, "rules_houses", []) or []
    if not rules_signs_list and not rules_houses_list:
        return ""

    parts: List[str] = []

    if rules_signs_list:
        sign_parts: List[str] = []
        for sign in rules_signs_list:
            sn = sign.name if hasattr(sign, "name") else str(sign)
            objs = _find_objects_in_sign(sn, chart_objects, chart)
            if objs:
                sign_parts.append(f"{sn} ({', '.join(objs)})")
            else:
                sign_parts.append(sn)
        parts.append("; ".join(sign_parts))

    if rules_houses_list:
        house_parts: List[str] = []
        for house in rules_houses_list:
            hn = house.number if hasattr(house, "number") else int(house)
            hl = _format_house_label(hn)
            objs = _find_objects_in_house(hn, chart_objects, chart, house_system)
            if objs:
                house_parts.append(f"{hl} ({', '.join(objs)})")
            else:
                house_parts.append(hl)
        parts.append("; ".join(house_parts))

    return f"Rules: {'; '.join(parts)}" if parts else ""


# ═══════════════════════════════════════════════════════════════════════
# PlanetStats + PlanetStatsReader
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PlanetStats:
    """Raw positional and astronomical stats for one chart object.

    This is the data layer backing the left-sidebar planet profile cards.
    It holds only pre-computed strings and primitive values — no live chart
    references — so it can be safely cached, serialized, or forwarded to
    any renderer (sidebar HTML, MCP text, chart tooltips).

    Call :class:`PlanetStatsReader` to turn one into displayable output.
    """

    # Identity
    object_name: str
    display_name: str           # "Ascendant (AC)" for axes; same as object_name otherwise
    glyph: str

    # Status flags
    retrograde: bool
    station: str                # "Stationing direct" / "Stationing retrograde" / ""
    dignity_label: str          # "Domicile" / "Exaltation" / "Detriment" / "Fall" / ""

    # Position
    sign_name: str
    dms: str                    # formatted DMS string e.g. "15°24′Ar"

    # Sabian
    sabian_symbol: str
    sabian_short_meaning: str

    # Stars / OOB
    fixed_star_conj: str
    oob_status: str             # "No" / "Yes" / "Extreme"

    # House
    house_num: Optional[int]

    # Relations
    reception_str: str
    house_ruler_names: List[str]
    sign_ruler_names: List[str]

    # Kinematics (pre-formatted strings)
    speed_str: str
    lat_str: str
    decl_str: str
    dist_str: str

    # Interpretive meaning (long meaning text from OBJECT_MEANINGS / Object.long_meaning)
    object_meaning: str

    # Raw numerics for MCP serialization
    speed: Optional[float] = None
    latitude: Optional[float] = None
    declination: Optional[float] = None
    distance: Optional[float] = None

    @classmethod
    def from_chart_object(
        cls,
        chart_obj: Any,
        house_system: str = "Placidus",
    ) -> "PlanetStats":
        """Populate a PlanetStats from a ChartObject instance."""
        # Identity
        name = _obj_name(chart_obj)
        display_name = _format_axis_for_display(name)
        glyph = getattr(chart_obj, "glyph", "") or ""
        if not glyph and getattr(chart_obj, "object_name", None):
            glyph = getattr(chart_obj.object_name, "glyph", "") or ""

        # Status
        retrograde = bool(getattr(chart_obj, "retrograde", False))
        station = getattr(chart_obj, "station", "") or ""
        dignity = getattr(chart_obj, "dignity", None)
        dignity_label = ""
        if dignity:
            dignity_label = (
                dignity if isinstance(dignity, str)
                else getattr(dignity, "name", str(dignity))
            )

        # Position
        sign = getattr(chart_obj, "sign", None)
        sign_name = sign.name if sign and hasattr(sign, "name") else (str(sign) if sign else "")
        dms = getattr(chart_obj, "dms", "") or ""

        # Sabian
        sabian_symbol_text = ""
        sabian_meaning = ""
        ss = getattr(chart_obj, "sabian_symbol", None)
        if ss is not None:
            if hasattr(ss, "symbol"):
                sabian_symbol_text = ss.symbol or ""
            if not sabian_symbol_text and hasattr(ss, "short_meaning"):
                sabian_symbol_text = ss.short_meaning or ""
            if not sabian_symbol_text:
                sabian_symbol_text = str(ss)
            if hasattr(ss, "short_meaning"):
                sabian_meaning = ss.short_meaning or ""

        # Fixed star / OOB
        fixed_star_conj = getattr(chart_obj, "fixed_star_conj", "") or ""
        oob_status = getattr(chart_obj, "oob_status", "No") or "No"

        # House
        house_num = _get_house_num(chart_obj, house_system)

        # Reception
        reception_items = getattr(chart_obj, "reception", []) or []
        reception_str = _format_reception_links(reception_items)

        # Rulers
        house_ruler_names = _get_house_rulers(chart_obj, house_system)
        sign_ruler_items = getattr(chart_obj, "sign_ruler", []) or []
        ruled_by_sign = getattr(chart_obj, "ruled_by_sign", "") or ""
        if ruled_by_sign:
            sign_ruler_names = [n.strip() for n in ruled_by_sign.split(",") if n.strip()]
        else:
            sign_ruler_names = [
                r.name if hasattr(r, "name") else str(r) for r in sign_ruler_items
            ]

        # Kinematics
        speed = getattr(chart_obj, "speed", None)
        latitude = getattr(chart_obj, "latitude", None)
        declination = getattr(chart_obj, "declination", None)
        distance = getattr(chart_obj, "distance", None)

        speed_str = _fmt_speed_per_day(speed)
        lat_str = _fmt_lat(latitude)
        decl_str = _fmt_decl(declination)
        dist_str = _fmt_distance_au_km(distance)

        # Meaning — try Object.long_meaning first, fall back to OBJECT_MEANINGS dict
        obj_def = getattr(chart_obj, "object_name", None)
        object_meaning = ""
        if obj_def:
            object_meaning = getattr(obj_def, "long_meaning", "") or ""
        if not object_meaning:
            meanings = getattr(static_db, "OBJECT_MEANINGS", {})
            object_meaning = meanings.get(name, "") or ""
            if not object_meaning:
                base = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
                if base != name:
                    object_meaning = meanings.get(base, "") or ""

        return cls(
            object_name=name,
            display_name=display_name,
            glyph=glyph,
            retrograde=retrograde,
            station=station,
            dignity_label=dignity_label,
            sign_name=sign_name,
            dms=dms,
            sabian_symbol=sabian_symbol_text,
            sabian_short_meaning=sabian_meaning,
            fixed_star_conj=fixed_star_conj,
            oob_status=oob_status,
            house_num=house_num,
            reception_str=reception_str,
            house_ruler_names=house_ruler_names,
            sign_ruler_names=sign_ruler_names,
            speed_str=speed_str,
            lat_str=lat_str,
            decl_str=decl_str,
            dist_str=dist_str,
            object_meaning=object_meaning,
            speed=float(speed) if speed is not None else None,
            latitude=float(latitude) if latitude is not None else None,
            declination=float(declination) if declination is not None else None,
            distance=float(distance) if distance is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Compact serialization for MCP / JSON transport."""
        d: Dict[str, Any] = {
            "object": self.object_name,
            "sign": self.sign_name,
            "dms": self.dms,
        }
        if self.house_num:
            d["house"] = self.house_num
        if self.retrograde:
            d["retrograde"] = True
        if self.dignity_label:
            d["dignity"] = self.dignity_label
        if self.oob_status and self.oob_status.lower() != "no":
            d["oob"] = self.oob_status
        if self.reception_str:
            d["reception"] = self.reception_str
        if self.sabian_symbol:
            d["sabian"] = self.sabian_symbol
        if self.fixed_star_conj:
            d["fixed_star"] = self.fixed_star_conj
        if self.speed_str:
            d["speed"] = self.speed_str
        if self.house_ruler_names:
            d["house_rulers"] = self.house_ruler_names
        if self.sign_ruler_names:
            d["sign_rulers"] = self.sign_ruler_names
        return d


class PlanetStatsReader:
    """Format a PlanetStats as HTML (sidebar) or plain text (MCP / tooltip)."""

    def __init__(self, stats: PlanetStats) -> None:
        self.s = stats

    def format_html(self, include_house_data: bool = True) -> str:
        """Reproduce the ``<div class='pf-block'>`` HTML output from profiles_v2."""
        s = self.s
        lines: List[str] = []

        # Title — include parenthetical (Rx, Dignity) if applicable
        tags = []
        if s.retrograde:
            tags.append("Rx")
        if s.dignity_label:
            tags.append(s.dignity_label.capitalize())
        paren = f" ({', '.join(tags)})" if tags else ""

        if s.display_name != s.object_name:
            # Axis object: show "Ascendant (AC)" without a separate glyph prefix
            title_content = f"{s.display_name}{paren}"
        else:
            title_content = f"{s.glyph} {s.object_name}{paren}"
        lines.append(f"<div class='pf-title'><strong>{title_content}</strong></div>")

        if s.object_meaning:
            lines.append(f"<div class='pf-meaning'>{_html.escape(s.object_meaning)}</div>")

        if s.sign_name or s.dms:
            lines.append(f"<div><strong>{s.sign_name} {s.dms}</strong></div>")

        if s.sabian_symbol:
            lines.append(f"<div><em>\u201c{s.sabian_symbol}\u201d</em></div>")

        if s.fixed_star_conj:
            lines.append("<div><strong>Fixed Star Conjunctions:</strong></div>")
            lines.append(f"<div>{s.fixed_star_conj}</div>")

        if s.oob_status and s.oob_status.lower() != "no":
            lines.append(f"<div>Out of Bounds: {s.oob_status}</div>")

        if include_house_data and s.house_num is not None:
            lines.append(f"<div><strong>House:</strong> {int(s.house_num)}</div>")

        if s.reception_str:
            lines.append(f"<div><strong>Reception:</strong> {s.reception_str}</div>")

        if s.speed_str:
            lines.append(f"<div><strong>Speed:</strong> {s.speed_str}</div>")
        if s.lat_str:
            lines.append(f"<div><strong>Latitude:</strong> {s.lat_str}</div>")
        if s.decl_str:
            lines.append(f"<div><strong>Declination:</strong> {s.decl_str}</div>")
        if s.dist_str:
            lines.append(f"<div><strong>Distance:</strong> {s.dist_str}</div>")

        # Rulerships
        house_rulers_str = ", ".join(s.house_ruler_names) if include_house_data else ""
        sign_rulers_str = ", ".join(s.sign_ruler_names)

        if include_house_data and house_rulers_str:
            lines.append(
                f"<div><strong>Rulership by House:</strong><br/>"
                f"{house_rulers_str} rules {s.object_name}</div>"
            )
        if sign_rulers_str:
            lines.append(
                f"<div><strong>Rulership by Sign:</strong><br/>"
                f"{sign_rulers_str} rules {s.object_name}</div>"
            )

        inner = "\n".join(lines)
        return f"<div class='pf-block'>\n{inner}\n<hr class='pf-divider'/>\n</div>"

    def format_text(self) -> str:
        """Compact plain-text version for MCP and chart tooltips."""
        s = self.s
        parts: List[str] = []

        tags = []
        if s.retrograde:
            tags.append("Rx")
        if s.dignity_label:
            tags.append(s.dignity_label)
        header = s.display_name
        if tags:
            header += f" ({', '.join(tags)})"
        header += f" in {s.sign_name}"
        if s.dms:
            header += f" — {s.dms}"
        parts.append(header)

        if s.house_num:
            parts.append(f"House: {s.house_num}")
        if s.oob_status and s.oob_status.lower() != "no":
            parts.append(f"Out of Bounds: {s.oob_status}")
        if s.sabian_symbol:
            parts.append(f'Sabian: "{s.sabian_symbol}"')
        if s.fixed_star_conj:
            parts.append(f"Fixed Star: {s.fixed_star_conj}")
        if s.reception_str:
            parts.append(f"Reception: {s.reception_str}")
        if s.speed_str:
            parts.append(f"Speed: {s.speed_str}")
        if s.lat_str:
            parts.append(f"Latitude: {s.lat_str}")
        if s.decl_str:
            parts.append(f"Declination: {s.decl_str}")
        if s.dist_str:
            parts.append(f"Distance: {s.dist_str}")
        if s.house_ruler_names:
            parts.append(f"House Ruler(s): {', '.join(s.house_ruler_names)}")
        if s.sign_ruler_names:
            parts.append(f"Sign Ruler(s): {', '.join(s.sign_ruler_names)}")

        return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
# PlanetProfile + PlanetProfileReader
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class PlanetProfile:
    """Interpretive profile data for one chart object.

    Populated from the ObjectSign and ObjectHouse combo tables in the
    static database, plus pre-computed "other stats" fields (OOB, reception,
    rules, ruled-by).

    Call :class:`PlanetProfileReader` to format the profile as text in
    "default" (concise, one block per object) or "focus" (detailed, multi-block)
    mode.
    """

    # Identity / position (used in display headers)
    object_name: str
    display_name: str
    glyph: str
    retrograde: bool
    sign_name: str
    dms: str
    house_num: Optional[int]
    house_label: str            # "1st House" / "" if N/A

    # Sabian / fixed stars
    sabian_symbol: str
    sabian_short_meaning: str
    fixed_star_conj: str

    # From ObjectSign combo
    sign_short_meaning: str
    dignity: str
    dignity_interp: str
    behavioral_style: str
    strengths: str
    challenges: str
    somatic_signature: str
    shadow_expression: str

    # From ObjectHouse combo
    house_short_meaning: str
    environmental_impact: str
    concrete_manifestation: str
    house_strengths: str
    house_challenges: str
    objective: str

    # Other stats (pre-formatted strings)
    oob_status: str
    reception_str: str
    rules_str: str              # "Rules: Aries (Sun); 1st House (Sun)" or ""
    ruled_by_sign_str: str      # "Ruled by (by sign): Saturn" or ""
    ruled_by_house_str: str     # "Ruled by (by house): Saturn" or ""

    @classmethod
    def from_chart_object(
        cls,
        chart_obj: Any,
        house_system: str = "placidus",
        lookup: Optional[Dict[str, Any]] = None,
        chart_objects: Optional[List[Any]] = None,
        chart: Optional[Any] = None,
    ) -> "PlanetProfile":
        """Build a PlanetProfile from a ChartObject and optional context.

        Parameters
        ----------
        chart_obj : ChartObject
            The chart object to profile.
        house_system : str
            Which house system to use for house number extraction.
        lookup : dict, optional
            Override for the sign/house combo dicts.  Defaults to static_db.
        chart_objects : list, optional
            Full list of chart objects — used to populate the "Rules:" line
            (which objects are in the ruled sign/house).
        chart : AstrologicalChart, optional
            Full chart — used if chart_signs/chart_houses are populated.
        """
        from .models_v2 import ObjectSign, ObjectHouse  # local import avoids cycle

        if lookup is None:
            lookup = {
                "object_sign_combos": getattr(static_db, "object_sign_combos", {}),
                "object_house_combos": getattr(static_db, "object_house_combos", {}),
            }
        sign_combos = lookup.get("object_sign_combos", {})
        house_combos = lookup.get("object_house_combos", {})

        name = _obj_name(chart_obj)
        display_name = _format_axis_for_display(name)
        glyph = getattr(chart_obj, "glyph", "") or ""
        retrograde = bool(getattr(chart_obj, "retrograde", False))

        sign = getattr(chart_obj, "sign", None)
        sign_name = sign.name if sign and hasattr(sign, "name") else (str(sign) if sign else "")
        dms = getattr(chart_obj, "dms", "") or ""

        house_num = _get_house_num(chart_obj, house_system)
        house_label = _format_house_label(house_num) if house_num is not None else ""

        # Sabian
        sabian_symbol_text = ""
        sabian_meaning = ""
        ss = getattr(chart_obj, "sabian_symbol", None)
        if ss is not None and hasattr(ss, "symbol"):
            sabian_symbol_text = ss.symbol or ""
        degree_in_sign = getattr(chart_obj, "degree_in_sign", None)
        sabian_obj = None
        if degree_in_sign is not None:
            try:
                sabian_obj = (
                    static_db.sabian_symbols.get(sign_name, {})
                    .get(int(float(degree_in_sign)) + 1)
                )
            except (TypeError, ValueError, AttributeError):
                pass
        if not sabian_symbol_text and sabian_obj and hasattr(sabian_obj, "symbol"):
            sabian_symbol_text = sabian_obj.symbol or ""
        if sabian_obj and hasattr(sabian_obj, "short_meaning"):
            sabian_meaning = sabian_obj.short_meaning or ""

        fixed_star_conj = getattr(chart_obj, "fixed_star_conj", "") or ""

        # ObjectSign combo
        norm_name = _normalize_for_combo(name)
        sc = sign_combos.get(f"{norm_name}_{sign_name}")
        sign_short_meaning = getattr(sc, "short_meaning", "") or "" if sc else ""
        dignity = getattr(sc, "dignity", "") or "" if sc else ""
        dignity_interp = getattr(sc, "dignity_interp", "") or "" if sc else ""
        behavioral_style = getattr(sc, "behavioral_style", "") or "" if sc else ""
        strengths = getattr(sc, "strengths", "") or "" if sc else ""
        challenges = getattr(sc, "challenges", "") or "" if sc else ""
        somatic_signature = getattr(sc, "somatic_signature", "") or "" if sc else ""
        shadow_expression = getattr(sc, "shadow_expression", "") or "" if sc else ""

        # ObjectHouse combo (skip for AC/DC which are implicitly 1st/7th)
        house_short_meaning = ""
        environmental_impact = ""
        concrete_manifestation = ""
        house_strengths = ""
        house_challenges = ""
        objective = ""
        is_acdc = norm_name in _ACDC_NORM
        if house_num is not None and not is_acdc:
            hc = house_combos.get(f"{norm_name}_House_{house_num}")
            house_short_meaning = getattr(hc, "short_meaning", "") or "" if hc else ""
            environmental_impact = getattr(hc, "environmental_impact", "") or "" if hc else ""
            concrete_manifestation = getattr(hc, "concrete_manifestation", "") or "" if hc else ""
            house_strengths = getattr(hc, "strengths", "") or "" if hc else ""
            house_challenges = getattr(hc, "challenges", "") or "" if hc else ""
            objective = getattr(hc, "objective", "") or "" if hc else ""

        # OOB
        oob_status = getattr(chart_obj, "oob_status", "No") or "No"

        # Reception
        reception_items = getattr(chart_obj, "reception", []) or []
        reception_strs = []
        for rl in reception_items:
            if not rl or not rl.other or not rl.aspect:
                continue
            verb = {
                "Conjunction": "Conjunct", "Opposition": "Opposite",
                "Trine": "Trine", "Square": "Square", "Sextile": "Sextile",
            }.get(rl.aspect.name, rl.aspect.name)
            mode_suffix = " (by orb)" if rl.mode == "orb" else " (by sign)"
            reception_strs.append(f"{verb} {rl.other.name}{mode_suffix}")
        reception_str = ", ".join(reception_strs) if reception_strs else ""

        # Rules
        rules_str = _compute_rules_str(chart_obj, chart_objects, chart, house_system)

        # Ruled by sign
        sign_rulers = getattr(chart_obj, "sign_ruler", []) or []
        ruler_names = [r.name if hasattr(r, "name") else str(r) for r in sign_rulers]
        ruled_by_sign_str = (
            f'Ruled by (by sign): {", ".join(ruler_names)}' if ruler_names else ""
        )

        # Ruled by house
        house_rulers = _get_house_rulers(chart_obj, house_system)
        ruled_by_house_str = (
            f'Ruled by (by house): {", ".join(house_rulers)}' if house_rulers else ""
        )

        return cls(
            object_name=name,
            display_name=display_name,
            glyph=glyph,
            retrograde=retrograde,
            sign_name=sign_name,
            dms=dms,
            house_num=house_num,
            house_label=house_label,
            sabian_symbol=sabian_symbol_text,
            sabian_short_meaning=sabian_meaning,
            fixed_star_conj=fixed_star_conj,
            sign_short_meaning=sign_short_meaning,
            dignity=dignity,
            dignity_interp=dignity_interp,
            behavioral_style=behavioral_style,
            strengths=strengths,
            challenges=challenges,
            somatic_signature=somatic_signature,
            shadow_expression=shadow_expression,
            house_short_meaning=house_short_meaning,
            environmental_impact=environmental_impact,
            concrete_manifestation=concrete_manifestation,
            house_strengths=house_strengths,
            house_challenges=house_challenges,
            objective=objective,
            oob_status=oob_status,
            reception_str=reception_str,
            rules_str=rules_str,
            ruled_by_sign_str=ruled_by_sign_str,
            ruled_by_house_str=ruled_by_house_str,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Compact serialization for MCP use."""
        d: Dict[str, Any] = {
            "object": self.object_name,
            "sign": self.sign_name,
            "dms": self.dms,
        }
        if self.house_label:
            d["house"] = self.house_label
        if self.retrograde:
            d["retrograde"] = True
        if self.sign_short_meaning:
            d["sign_meaning"] = self.sign_short_meaning
        if self.dignity:
            d["dignity"] = self.dignity
            if self.dignity_interp:
                d["dignity_interp"] = self.dignity_interp
        if self.behavioral_style:
            d["style"] = self.behavioral_style
        if self.strengths:
            d["strengths"] = self.strengths
        if self.challenges:
            d["challenges"] = self.challenges
        if self.somatic_signature:
            d["somatic"] = self.somatic_signature
        if self.shadow_expression:
            d["shadow"] = self.shadow_expression
        if self.house_short_meaning:
            d["house_meaning"] = self.house_short_meaning
        if self.environmental_impact:
            d["env_impact"] = self.environmental_impact
        if self.concrete_manifestation:
            d["manifestation"] = self.concrete_manifestation
        if self.house_strengths:
            d["house_strengths"] = self.house_strengths
        if self.house_challenges:
            d["house_challenges"] = self.house_challenges
        if self.objective:
            d["objective"] = self.objective
        if self.oob_status and self.oob_status.lower() != "no":
            d["oob"] = self.oob_status
        if self.reception_str:
            d["reception"] = self.reception_str
        if self.rules_str:
            d["rules"] = self.rules_str
        if self.ruled_by_sign_str:
            d["ruled_by_sign"] = self.ruled_by_sign_str
        if self.ruled_by_house_str:
            d["ruled_by_house"] = self.ruled_by_house_str
        if self.sabian_symbol:
            d["sabian"] = self.sabian_symbol
            if self.sabian_short_meaning:
                d["sabian_meaning"] = self.sabian_short_meaning
        if self.fixed_star_conj:
            d["fixed_star"] = self.fixed_star_conj
        return d


class PlanetProfileReader:
    """Format a PlanetProfile as plain text in default or focus mode."""

    def __init__(self, profile: PlanetProfile) -> None:
        self.p = profile

    def format_text(self, mode: str = "default") -> str:
        """Render the profile as plain text.

        Parameters
        ----------
        mode : str
            "default" — concise block matching ``_format_default_object`` output.
            "focus"   — detailed multi-block matching ``_format_focus_object`` output.
        """
        if mode == "focus":
            return self._format_focus()
        return self._format_default()

    def _format_default(self) -> str:
        """Reproduce interp_base_natal._format_default_object output."""
        p = self.p
        lines: List[str] = []
        is_axis = p.object_name in _AXIS_OBJECTS

        # Line 1: [glyph] [name] (Rx) in [sign]: [short_meaning]
        first = p.display_name if is_axis else f"{p.glyph} {p.display_name}"
        if p.retrograde:
            first += " (Rx)"
        first += f" in {p.sign_name}"
        if p.sign_short_meaning:
            first += f": {p.sign_short_meaning}"
        lines.append(first)

        # Line 2: Dignity (only if present)
        if p.dignity:
            dl = f"{p.dignity}: {p.display_name}"
            if p.dignity_interp:
                dl += f" {p.dignity_interp}"
            lines.append(dl)

        # Line 3: Behavioral style
        if p.behavioral_style:
            lines.append(p.behavioral_style)

        # Sabian / position / fixed star block
        if p.sabian_symbol or p.fixed_star_conj:
            lines.append("𑁋")
            lines.append(f"{p.sign_name} {p.dms}")
            if p.sabian_symbol:
                lines.append(f"Sabian Symbol: {p.sabian_symbol}")
            if p.sabian_short_meaning:
                lines.append(f"Sabian Symbol Meaning: {p.sabian_short_meaning}")
            if p.fixed_star_conj:
                lines.append(f"Fixed star conjunction(s): {p.fixed_star_conj}")

        # House block
        is_acdc = _normalize_for_combo(p.object_name) in _ACDC_NORM
        if p.house_num is not None and not is_acdc:
            lines.append("𑁋")
            if p.house_short_meaning:
                lines.append(
                    f"{p.display_name} in the {p.house_label}: {p.house_short_meaning}"
                )
            if p.environmental_impact:
                lines.append(f"Environmental Impact: {p.environmental_impact}")
            if p.concrete_manifestation:
                lines.append(f"Concrete Manifestations: {p.concrete_manifestation}")

        # Other stats
        other = self._other_stats_lines()
        if other:
            lines.extend(other)

        return "\n".join([ln for ln in lines if ln])

    def _format_focus(self) -> str:
        """Reproduce interp_base_natal._format_focus_object output."""
        p = self.p
        blocks: List[str] = []
        is_axis = p.object_name in _AXIS_OBJECTS

        # Block 1 — Sign placement
        sign_lines: List[str] = []
        first = p.display_name if is_axis else f"{p.glyph} {p.display_name}"
        if p.retrograde:
            first += " (Rx)"
        first += f" in {p.sign_name}"
        if p.sign_short_meaning:
            first += f": {p.sign_short_meaning}"
        sign_lines.append(first)

        if p.dignity:
            dl = f"Dignity: {p.dignity}: {p.display_name}"
            if p.dignity_interp:
                dl += f" {p.dignity_interp}"
            sign_lines.append(dl)
        if p.behavioral_style:
            sign_lines.append(f"Style: {p.behavioral_style}")
        if p.strengths:
            sign_lines.append(f"Strengths: {p.strengths}")
        if p.challenges:
            sign_lines.append(f"Challenges: {p.challenges}")
        if p.somatic_signature:
            sign_lines.append(f"Somatic Signature: {p.somatic_signature}")
        if p.shadow_expression:
            sign_lines.append(f"Shadow Expression: {p.shadow_expression}")
        blocks.append("\n".join([ln for ln in sign_lines if ln]))

        # Block 2 — House placement
        is_acdc = _normalize_for_combo(p.object_name) in _ACDC_NORM
        if p.house_num is not None and not is_acdc:
            house_lines: List[str] = []
            house_lines.append(f"{p.display_name} in {p.house_label}")
            if p.house_short_meaning:
                house_lines.append(p.house_short_meaning)
            if p.environmental_impact:
                house_lines.append(f"Environmental Impact: {p.environmental_impact}")
            if p.concrete_manifestation:
                house_lines.append(f"Concrete Manifestations: {p.concrete_manifestation}")
            if p.house_strengths:
                house_lines.append(f"Strengths: {p.house_strengths}")
            if p.house_challenges:
                house_lines.append(f"Challenges: {p.house_challenges}")
            if p.objective:
                house_lines.append(f"Objective: {p.objective}")
            blocks.append("\n".join([ln for ln in house_lines if ln]))

        # Block 3 — Other stats
        other = self._other_stats_lines()
        if other:
            blocks.append("\n".join(other))

        return "\n\n".join(blocks)

    def _other_stats_lines(self) -> List[str]:
        """Build the 'Other stats:' section lines."""
        p = self.p
        has_oob = p.oob_status and p.oob_status != "No"
        has_reception = bool(p.reception_str)
        has_rules = bool(p.rules_str)
        has_ruled_by_sign = bool(p.ruled_by_sign_str)
        has_ruled_by_house = bool(p.ruled_by_house_str)

        if not any([has_oob, has_reception, has_rules, has_ruled_by_sign, has_ruled_by_house]):
            return []

        lines: List[str] = ["𑁋", "Other stats:"]
        if has_oob:
            lines.append(f"Out of bounds: {p.oob_status}")
        if has_reception:
            lines.append(f"Reception: {p.reception_str}")
        if has_rules:
            lines.append(p.rules_str)
        if has_ruled_by_sign:
            lines.append(p.ruled_by_sign_str)
        if has_ruled_by_house:
            lines.append(p.ruled_by_house_str)
        return lines

    def format_html(self, mode: str = "default") -> str:
        """Format the profile as HTML.
        
        Parameters
        ----------
        mode : str
            "default" — concise block format.
            "focus"   — detailed multi-block format.
        
        Returns
        -------
        str
            HTML string with proper div structure and line breaks.
        """
        # Get the text representation
        text = self.format_text(mode=mode)
        
        # Escape HTML and convert newlines to <br> tags
        escaped = _html.escape(text)
        html_content = escaped.replace("\n", "<br>")
        
        # Wrap in a styled block with divider
        return f"<div class='pf-block'>\n{html_content}\n<hr class='pf-divider'/>\n</div>"


# ═══════════════════════════════════════════════════════════════════════
# AspectProfile + AspectProfileReader
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class AspectProfile:
    """Interpretation data for one drawn aspect edge.

    Built from a (a_name, b_name, meta) tuple plus optional cluster context.
    Call :class:`AspectProfileReader` to render as text.
    """

    obj_a_display: str
    obj_b_display: str
    aspect_name: str
    aspect_verb: str            # sentence verb form e.g. "trines", "is conjunct"
    orb: float
    applying: bool
    short_meaning: str
    sentence_meaning: str       # SENTENCE_ASPECT_MEANINGS entry
    reception: str
    mutual_reception: bool
    is_cluster_edge: bool       # True if either node is a conjunction cluster

    @classmethod
    def from_edge(
        cls,
        a_name: str,
        b_name: str,
        meta: Any,
        cluster_map: Optional[Dict[str, List[str]]] = None,
    ) -> "AspectProfile":
        """Build an AspectProfile from a drawn edge.

        Parameters
        ----------
        a_name, b_name : str
            The two object names from the edge.
        meta : str | dict | object
            Edge metadata: aspect name string, dict with "aspect" key, or
            object with .aspect attribute.
        cluster_map : dict, optional
            {canon_root: [member_name, ...]} from _build_conjunction_cluster_map.
            When provided, cluster members are displayed as "[A + B]".
        """
        SETNENCE_ASPECT_NAMES = static_db.SETNENCE_ASPECT_NAMES
        SENTENCE_ASPECT_MEANINGS = static_db.SENTENCE_ASPECT_MEANINGS

        # Extract aspect name
        if isinstance(meta, str):
            aspect_name = meta
        elif isinstance(meta, dict):
            aspect_name = meta.get("aspect", "")
        else:
            aspect_name = getattr(meta, "aspect", "") or ""

        orb = 0.0
        if isinstance(meta, dict):
            orb = float(meta.get("orb", 0.0))
        else:
            orb = float(getattr(meta, "orb", 0.0) or 0.0)

        applying = False
        if isinstance(meta, dict):
            applying = bool(meta.get("applying", False))
        else:
            applying = bool(getattr(meta, "applying", False))

        # Axis abbreviations for display
        _AXIS_TO_ABBREV = {
            "Ascendant": "AC", "Descendant": "DC",
            "Midheaven": "MC", "Immum Coeli": "IC",
            "AC": "AC", "DC": "DC", "MC": "MC", "IC": "IC",
        }

        def node_label(name: str) -> str:
            if cluster_map:
                name_c = _canon(name)
                for root, members in cluster_map.items():
                    if any(_canon(m) == name_c for m in members):
                        if len(members) >= 2:
                            inner = " + ".join(
                                _AXIS_TO_ABBREV.get(m, m) for m in members
                            )
                            return f"[{inner}]"
                        break
            return _AXIS_TO_ABBREV.get(name, name)

        a_display = node_label(a_name)
        b_display = node_label(b_name)
        is_cluster = a_display.startswith("[") or b_display.startswith("[")

        verb = SETNENCE_ASPECT_NAMES.get(aspect_name, (aspect_name.lower() + "s") if aspect_name else "")
        sentence = SENTENCE_ASPECT_MEANINGS.get(aspect_name, "")

        return cls(
            obj_a_display=a_display,
            obj_b_display=b_display,
            aspect_name=aspect_name,
            aspect_verb=verb,
            orb=orb,
            applying=applying,
            short_meaning="",
            sentence_meaning=sentence,
            reception="",
            mutual_reception=False,
            is_cluster_edge=is_cluster,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "a": self.obj_a_display,
            "b": self.obj_b_display,
            "aspect": self.aspect_name,
        }
        if self.orb:
            d["orb"] = round(self.orb, 1)
        if self.applying:
            d["applying"] = True
        if self.mutual_reception:
            d["mutual_reception"] = True
        if self.sentence_meaning:
            d["meaning"] = self.sentence_meaning
        return d


class AspectProfileReader:
    """Format an AspectProfile as plain text."""

    def __init__(self, profile: AspectProfile) -> None:
        self.p = profile

    def format_text(self) -> str:
        """Render as '[A] [verb] [B]' followed by the meaning sentence."""
        p = self.p
        line = f"{p.obj_a_display} {p.aspect_verb} {p.obj_b_display}"
        parts = [line]
        if p.sentence_meaning:
            parts.append(f"{p.obj_a_display} and {p.obj_b_display} {p.sentence_meaning}")
        return "\n".join(parts)


def format_planet_profile_html(
    chart_obj: Any,
    chart: Any,
    chart_objects: list[Any],
    *,
    house_system: str = "Placidus",
) -> str:
    """Render the interpretive PlanetProfile as HTML.

    This function is intended for UI renderers that want the narrative profile
    output (sign/house combo interpretation) as HTML blocks.
    """
    profile = PlanetProfile.from_chart_object(
        chart_obj,
        house_system=house_system,
        lookup=None,
        chart_objects=chart_objects,
        chart=chart,
    )
    return PlanetProfileReader(profile).format_html(mode="default")


def format_full_planet_profile_html(
    chart_obj: Any,
    chart: Any,
    chart_objects: list[Any],
    *,
    house_system: str = "Placidus",
    include_house_data: bool = True,
) -> str:
    """Render a combined PlanetStats + PlanetProfile HTML block.

    This is intended to be the most comprehensive sidebar profile, merging:
    1) raw positional / status data (from PlanetStats)
    2) interpretive narrative (from PlanetProfile)

    The output is suitable for the sidebar and maintains the same styling as
    the existing `pf-block` HTML.
    """
    stats = PlanetStats.from_chart_object(chart_obj, house_system=house_system)
    stats_html = PlanetStatsReader(stats).format_html(include_house_data=include_house_data)

    profile_html = format_planet_profile_html(
        chart_obj,
        chart,
        chart_objects,
        house_system=house_system,
    )

    retro_addendum = ""
    if stats.retrograde:
        retro_addendum = (
            f"<div>⚶ {_html.escape(stats.object_name)} Retrograde "
            f"(To be added - just wire in a placeholder for now)</div>"
        )

    return "\n".join([stats_html, profile_html, retro_addendum])


# ═══════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════

__all__ = [
    # Data containers
    "PlanetStats",
    "PlanetProfile",
    "AspectProfile",
    # Readers / formatters
    "PlanetStatsReader",
    "PlanetProfileReader",
    "AspectProfileReader",
    # Combined renderers
    "format_planet_profile_html",
    "format_full_planet_profile_html",
    # Shared helpers exposed for use in profiles_v2 / interp_base_natal
    "_format_axis_for_display",
    "_format_house_label",
    "_normalize_for_combo",
    "_canon",
]
