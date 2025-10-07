# profiles_v2.py

from __future__ import annotations
from pathlib import Path
from typing import List, Dict
import pandas as pd
import re
from lookup_v2 import SABIAN_SYMBOLS, GLYPHS, OBJECT_MEANINGS
import html 

def glyph_for(obj: str) -> str:
    """
    Return a display glyph for an object name.
    - Tries exact match first (e.g. 'Black Moon Lilith (Mean)').
    - Falls back to stripping trailing parenthetical (e.g. '(Mean)').
    - Handles common aliases used in your DF (AC/DC/MC/IC/POF).
    Returns "" if no glyph found.
    """
    if not obj:
        return ""

    # exact
    g = GLYPHS.get(obj)
    if g:
        return g

    # strip trailing ( ... )
    base = re.sub(r"\s*\(.*?\)\s*$", "", str(obj)).strip()

    # common aliases in your DF
    alias = {
        "AC": "Ascendant",
        "Asc": "Ascendant",
        "DC": "Descendant",
        "POF": "Part of Fortune",
        "North Node (True)": "North Node",
        "South Node (True)": "South Node",
    }
    key = alias.get(base, base)

    return GLYPHS.get(key, "")

# ---------- Sabian symbols ----------

def sabian_for(sign: str, lon_abs: float) -> str:
    """
    Return Sabian symbol text for an object at absolute longitude `lon_abs`
    that is in zodiac `sign`.

    `SABIAN_SYMBOLS` is keyed as (sign_name, index_1_30).
    """
    deg_in_sign = int(lon_abs % 30)          # 0..29
    idx = deg_in_sign + 1                    # 1..30
    return SABIAN_SYMBOLS.get((sign, idx), "")


# ---------- Fixed stars ----------

def _norm360(x: float) -> float:
    return x % 360.0

def _sep_deg(a: float, b: float) -> float:
    """Unsigned separation 0..180 (smallest arc)."""
    d = abs(_norm360(a) - _norm360(b)) % 360.0
    return d if d <= 180.0 else 360.0 - d

# --- formatting helpers (angles & distance) ---
_DEG = "°"; _PRIME = "′"; _DPRIME = "″"

def _dms_abs(v: float | int | None) -> str:
    """Return abs(v) as D°M′S″ (no sign)."""
    if v is None:
        return ""
    v = abs(float(v))
    d = int(v)
    m_f = (v - d) * 60.0
    m = int(m_f)
    s = int(round((m_f - m) * 60.0))
    if s == 60:
        s = 0; m += 1
    if m == 60:
        m = 0; d += 1
    return f"{d}{_DEG}{m:02d}{_PRIME}{s:02d}{_DPRIME}"

def _fmt_speed_per_day(v: float | int | None) -> str:
    """Speed as DMS/day (absolute; Rx is shown in header already)."""
    return f"{_dms_abs(v)}/day" if v is not None else ""

def _fmt_lat(v: float | int | None) -> str:
    """Ecliptic latitude with hemisphere."""
    if v is None: 
        return ""
    hemi = "N" if float(v) >= 0 else "S"
    return f"{_dms_abs(v)} {hemi}"

def _fmt_decl(v: float | int | None) -> str:
    """Declination with hemisphere."""
    if v is None: 
        return ""
    hemi = "N" if float(v) >= 0 else "S"
    return f"{_dms_abs(v)} {hemi}"

def _fmt_distance_au_km(au: float | int | None) -> str:
    """Distance as 'X.XXXXXX AU (≈Y km / ≈Z million km)'. Uses AU from DF."""
    if au is None:
        return ""
    au = float(au)
    km = au * 149_597_870.7
    if km >= 1_000_000:
        km_part = f"≈{km/1_000_000:.1f} million km"
    else:
        km_part = f"≈{int(round(km)):,} km"
    return f"{au:.6f} AU ({km_part})"

# -------- Fixed star catalog loading from local Excel --------
HERE = Path(__file__).resolve().parent
DEFAULT_STAR_CATALOG = HERE / "fixed_stars.xlsx"   # <— use the local Excel file

def load_fixed_star_catalog(path: str | Path = DEFAULT_STAR_CATALOG) -> pd.DataFrame:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Fixed star catalog not found at: {p}")
    # requires openpyxl installed for .xlsx
    df = pd.read_excel(p)
    required = {"Name", "Longitude"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Star catalog missing columns: {sorted(missing)}")
    df = df.copy()
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df = df.dropna(subset=["Name", "Longitude"])
    return df

# Load once at import
STAR_CATALOG = load_fixed_star_catalog()

def find_fixed_star_conjunctions(lon_abs: float, catalog: pd.DataFrame, orb: float = 1.0) -> List[Dict]:
    """
    Return stars conjunct with `lon_abs` within `orb` degrees.
    Output rows: [{"Name": "...", "sep": <deg>, "orb": <orb>}, ...], sorted by smallest separation.
    """
    hits: List[Dict] = []
    for _, r in catalog.iterrows():
        sep = _sep_deg(lon_abs, float(r["Longitude"]))
        if sep <= orb:
            hits.append({"Name": str(r["Name"]), "sep": float(sep), "orb": float(orb)})
    hits.sort(key=lambda x: x["sep"])
    return hits


# Optional: load your default catalog at import-time (matches your snippet)
# Adjust the path if needed.
STAR_CATALOG = load_fixed_star_catalog("Rosetta_v2/fixed_stars.xlsx")

__all__ = [
    "sabian_for",
    "load_fixed_star_catalog",
    "find_fixed_star_conjunctions",
    "STAR_CATALOG",
]

import re
import pandas as pd

# Optional meanings (safe if the dict isn't present)
try:
    from Rosetta_v2.lookup_v2 import OBJECT_MEANINGS  # {"Sun": "...", ...}
except Exception:
    OBJECT_MEANINGS = {}

# Map “Conjunct/Opposite/…” → noun form for your Reception line
_ASPECT_VERB_TO_NOUN = {
    "conjunct": "Conjunction",
    "opposite": "Opposition",
    "trine": "Trine",
    "square": "Square",
    "sextile": "Sextile",
}

def _transform_reception_cell(cell: str | None) -> str:
    """
    "Conjunct Pluto (by sign), Opposite Mars (by sign)"
      -> "Reception: Has reception via Pluto Conjunction (by sign), Mars Opposition (by sign)"
    Pass-through if empty.
    """
    if not cell or not isinstance(cell, str):
        return ""
    items = [x.strip() for x in cell.split(",") if x.strip()]
    out = []
    for it in items:
        # Verb → Noun
        m = re.match(r"^(Conjunct|Opposite|Trine|Square|Sextile)\s+(.+?)(\s*\(by sign\))?$", it, flags=re.I)
        if m:
            verb, target, bysign = m.group(1), m.group(2), (m.group(3) or "")
            noun = _ASPECT_VERB_TO_NOUN.get(verb.lower(), verb.title())
            out.append(f"{target} {noun}{bysign}")
            continue
        # Already a noun form
        m2 = re.match(r"^(Conjunction|Opposition|Trine|Square|Sextile)\s+(.+?)(\s*\(by sign\))?$", it, flags=re.I)
        if m2:
            noun, target, bysign = m2.group(1), m2.group(2), (m2.group(3) or "")
            out.append(f"{target} {noun}{bysign}")
            continue
        out.append(it)
    return "Reception: Has reception via " + ", ".join(out) if out else ""

def _paren_rx_dignity(is_rx: bool, dignity: str | None) -> str:
    parts = []
    if is_rx:
        parts.append("Rx")
    if dignity:
        d = str(dignity).strip()
        if d:
            parts.append(d.capitalize())
    return f" ({', '.join(parts)})" if parts else ""

def format_object_profile_html(row, house_label: str = "Placidus") -> str:
    """
    Build a single object's profile block using ONLY values already in the DF row.
    No recalculation here—pure formatting.
    """
    glyph = (row.get("Glyph") or "").strip()
    obj   = (row.get("Object") or "").strip()

    # Header tag: (Rx first, then dignity) — omit if neither present
    tags = []
    if row.get("Retrograde Bool"):
        tags.append("Rx")
    if row.get("Dignity"):
        tags.append(str(row.get("Dignity")).strip())
    paren = f" ({', '.join(tags)})" if tags else ""

    # Short meaning (from lookup_v2.OBJECT_MEANINGS)
    # Try exact key first, then a version with any trailing "(...)" removed.
    base_obj = re.sub(r"\s*\(.*?\)\s*$", "", obj).strip()
    meaning_short = (
        OBJECT_MEANINGS.get(obj)
        or OBJECT_MEANINGS.get(base_obj)
        or ""
    )

    # Core text bits already in DF
    sign   = row.get("Sign") or ""
    dms    = row.get("DMS") or ""                       # precomputed positional DMS
    sabian = (row.get("Sabian Symbol") or "").strip()
    stars  = (row.get("Fixed Star Conj") or "").strip()
    oob    = (row.get("OOB Status") or "").strip()

    # House (prefer specified label; fall back if missing)
    house = row.get(f"{house_label} House")
    if house is None:
        for alt in ("Placidus House", "Equal House", "Whole Sign House"):
            if row.get(alt) is not None:
                house = row.get(alt); break

    # Rulership summaries (simple strings the DF already carries)
    by_house = (row.get(f"{house_label} House Rulers") or "").strip()
    by_sign  = (row.get("Ruled by (sign)") or "").strip()

    # Reception text (already written into DF by annotate_reception)
    reception = (row.get("Reception") or "").strip()

    # Format kinematics/coords using helpers
    speed_txt = _fmt_speed_per_day(row.get("Speed"))
    lat_txt   = _fmt_lat(row.get("Latitude"))
    dec_txt   = _fmt_decl(row.get("Declination"))
    dist_txt  = _fmt_distance_au_km(row.get("Distance"))

    # Build HTML (single-spaced via your sidebar CSS)
    lines: list[str] = []

    # Title line (slightly larger/bold—your CSS controls exact look)
    lines.append(f"<div class='pf-title'><strong>{glyph} {obj}{paren}</strong></div>")

    # Meaning line directly under the title
    if meaning_short:
        lines.append(f"<div class='pf-meaning'>{html.escape(meaning_short)}</div>")

    # Sign & degree, Sabian
    if sign or dms:
        lines.append(f"<div><strong>{sign} {dms}</strong></div>")
    if sabian:
        # in quotes and italicized
        lines.append(f"<div><em>“{sabian}”</em></div>")

    # Fixed stars & OOB
    if stars:
        lines.append(f"<div>{stars}</div>")
    if oob and oob.lower() != "no":
        # show 'Yes' or 'Extreme'
        lines.append(f"<div>Out of Bounds: {oob}</div>")

    # House & Reception (Reception directly after House)
    if house is not None:
        lines.append(f"<div><strong>House:</strong> {int(house)}</div>")
    if reception:
        lines.append(f"<div><strong>Reception:</strong> {reception}</div>")

    # Kinematics/coords
    if speed_txt:
        lines.append(f"<div><strong>Speed:</strong> {speed_txt}</div>")
    if lat_txt:
        lines.append(f"<div><strong>Latitude:</strong> {lat_txt}</div>")
    if dec_txt:
        lines.append(f"<div><strong>Declination:</strong> {dec_txt}</div>")
    if dist_txt:
        lines.append(f"<div><strong>Distance:</strong> {dist_txt}</div>")

    # Rulership summaries
    if by_house:
        lines.append(f"<div><strong>Rulership by House:</strong><br/>{by_house} rules {obj}</div>")
    if by_sign:
        lines.append(f"<div><strong>Rulership by Sign:</strong><br/>{by_sign} rules {obj}</div>")

    # Join lines; add a divider for spacing between profiles
    inner = "\n".join(lines)
    return f"<div class='pf-block'>\n{inner}\n<hr class='pf-divider'/>\n</div>"
