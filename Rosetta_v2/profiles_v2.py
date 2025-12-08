# profiles_v2.py

from __future__ import annotations
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
import pandas as pd
import re
import html
# --- shared lookups -------------------------------------------------------
#
# The module is imported from multiple entry-points (as a package via
# ``Rosetta_v2.profiles_v2`` and also sometimes as a loose script from inside
# the ``Rosetta_v2`` directory).  The original code unconditionally tried to
# import ``lookup_v2`` using the bare module name and then, further down in the
# file, overwrote ``OBJECT_MEANINGS`` with ``{}`` if a package-style import
# failed.  When the file was executed from inside the directory that bare
# import succeeded, but the later fallback path still failed and replaced the
# populated dictionary with an empty one—leaving the profiles without any
# meaning text.
#
# To keep the meanings populated regardless of how the module is loaded we
# attempt the imports in order of preference (package-relative first, then the
# older flat layout) and only fall back to the legacy ``rosetta.lookup`` module
# if both of those fail.  We also avoid clobbering already-imported globals.
try:  # Preferred: package relative
    from .lookup_v2 import SABIAN_SYMBOLS, GLYPHS, OBJECT_MEANINGS  # type: ignore
    from .lookup_v2 import (  # type: ignore
        SABIAN_SYMBOLS,
        GLYPHS,
        OBJECT_MEANINGS,
        ALIASES_MEANINGS,
    )
except ImportError:
    try:  # Fallback: same directory on sys.path
        from lookup_v2 import (  # type: ignore
            SABIAN_SYMBOLS,
            GLYPHS,
            OBJECT_MEANINGS,
            ALIASES_MEANINGS,
        )
    except ImportError:
        # Last resort: legacy lookup module.  Only assign when available so we
        # never end up with an empty dictionary due to import order.
        from rosetta.lookup import (  # type: ignore
            SABIAN_SYMBOLS,  # noqa: F401 (re-exported)
            GLYPHS,          # noqa: F401 (re-exported)
            OBJECT_MEANINGS,
        )
        ALIASES_MEANINGS: Dict[str, str] = {}

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

def meaning_for(obj: str) -> str:
    """Return the long-form meaning string for an object name."""
    if not obj:
        return ""

    # exact match first
    meaning = OBJECT_MEANINGS.get(obj)
    if meaning:
        return meaning

    # strip trailing parentheses (e.g. "Black Moon Lilith (Mean)")
    base = re.sub(r"\s*\(.*?\)\s*$", "", str(obj)).strip()

    alias = {
        "AC": "Ascendant",
        "Asc": "Ascendant",
        "DC": "Descendant",
        "POF": "Part of Fortune",
        "MC": "MC",
        "IC": "IC",
        "North Node (True)": "North Node",
        "South Node (True)": "South Node",
        "Black Moon Lilith": "Black Moon Lilith",
    }

    key = alias.get(obj, alias.get(base, base))
    return OBJECT_MEANINGS.get(key, "")

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


# ----- Profile ordering helpers -------------------------------------------------

_CLUSTER_MEMBER_ORDER = [
    "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus",
    "Neptune", "Pluto", "Eris", "Ceres", "Pallas", "Juno", "Vesta", "Eros",
    "Psyche", "Chiron", "Nessus", "Ixion", "Hidalgo", "Varuna", "Typhon",
    "Quaoar", "Sedna", "Orcus", "Haumea", "Makemake", "Iris", "Hygiea",
    "Thalia", "Euterpe", "Pomona", "Polyhymnia", "Harmonia", "Isis", "Ariadne",
    "Mnemosyne", "Echo", "Niobe", "Eurydike", "Freia", "Terpsichore",
    "Minerva", "Hekate", "Zephyr", "Kassandra", "Lachesis", "Nemesis",
    "Medusa", "Aletheia", "Magdalena", "Arachne", "Fama", "Veritas", "Sirene",
    "Siva", "Lilith (Asteroid)", "Copernicus", "Icarus", "Toro", "Apollo",
    "Koussevitzky", "Osiris", "Lucifer", "Anteros", "Tezcatlipoca", "West",
    "Bacchus", "Hephaistos", "Panacea", "Orpheus", "Kafka", "Pamela",
    "Dionysus", "Kaali", "Asclepius", "Singer", "Angel", "Black Moon Lilith (Mean)",
    "Part of Fortune", "Vertex", "Anti-Vertex", "East Point", "Ascendant",
    "Descendant", "MC", "IC", "North Node", "South Node",
]

_FALLBACK_OBJECT_ORDER = [
    "Ascendant", "Descendant", "MC", "IC", "North Node", "South Node", "Sun",
    "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus",
    "Neptune", "Pluto", "Eris", "Ceres", "Pallas", "Juno", "Vesta", "Eros",
    "Psyche", "Chiron", "Nessus", "Ixion", "Hidalgo", "Varuna", "Typhon",
    "Quaoar", "Sedna", "Orcus", "Haumea", "Makemake", "Iris", "Hygiea",
    "Thalia", "Euterpe", "Pomona", "Polyhymnia", "Harmonia", "Isis", "Ariadne",
    "Mnemosyne", "Echo", "Niobe", "Eurydike", "Freia", "Terpsichore",
    "Minerva", "Hekate", "Zephyr", "Kassandra", "Lachesis", "Nemesis",
    "Medusa", "Aletheia", "Magdalena", "Arachne", "Fama", "Veritas", "Sirene",
    "Siva", "Lilith (Asteroid)", "Copernicus", "Icarus", "Toro", "Apollo",
    "Koussevitzky", "Osiris", "Lucifer", "Anteros", "Tezcatlipoca", "West",
    "Bacchus", "Hephaistos", "Panacea", "Orpheus", "Kafka", "Pamela",
    "Dionysus", "Kaali", "Asclepius", "Singer", "Angel", "Black Moon Lilith (Mean)",
    "Part of Fortune", "Vertex", "Anti-Vertex", "East Point",
]

_ASPECT_PRIORITY = {
    "opposition": 0,
    "trine": 1,
    "square": 2,
    "sextile": 3,
}

_CANON_RE = re.compile(r"[^a-z0-9]+")


def _strip_parenthetical(name: str | None) -> str:
    if not name:
        return ""
    return re.sub(r"\s*\(.*?\)\s*$", "", str(name)).strip()


def _canon(value: str | None) -> str:
    if not value:
        return ""
    return _CANON_RE.sub("", str(value).lower())


_ALIAS_CANON_MAP = {
    _canon(src): _canon(dst)
    for src, dst in (ALIASES_MEANINGS or {}).items()
    if _canon(src) and _canon(dst)
}

_REVERSE_ALIAS_MAP: dict[str, set[str]] = defaultdict(set)
for src, dst in (ALIASES_MEANINGS or {}).items():
    src_c = _canon(src)
    dst_c = _canon(dst)
    if src_c and dst_c:
        _REVERSE_ALIAS_MAP[dst_c].add(src_c)


def _canon_variants(name: str | None) -> set[str]:
    text = "" if name is None else str(name)
    variants: set[str] = set()
    stack: list[str] = []

    def _push(candidate: str | None) -> None:
        if not candidate:
            return
        canon_val = _canon(candidate)
        if canon_val and canon_val not in variants:
            variants.add(canon_val)
            stack.append(canon_val)

    _push(text)
    base = _strip_parenthetical(text)
    if base and base != text:
        _push(base)

    alias = ALIASES_MEANINGS.get(text)
    if alias:
        _push(alias)
    if base:
        alias_base = ALIASES_MEANINGS.get(base)
        if alias_base:
            _push(alias_base)

    for rev in _REVERSE_ALIAS_MAP.get(_canon(text), set()):
        _push(rev)
    if base:
        for rev in _REVERSE_ALIAS_MAP.get(_canon(base), set()):
            _push(rev)

    while stack:
        canon_key = stack.pop()
        alias_target = _ALIAS_CANON_MAP.get(canon_key)
        if alias_target and alias_target not in variants:
            variants.add(alias_target)
            stack.append(alias_target)
        for rev in _REVERSE_ALIAS_MAP.get(canon_key, set()):
            if rev not in variants:
                variants.add(rev)
                stack.append(rev)

    if not variants:
        canon_text = _canon(text)
        if canon_text:
            variants.add(canon_text)
    return variants


def _build_rank_map(order_list: List[str]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for idx, name in enumerate(order_list):
        for variant in _canon_variants(name) | {_canon(name)}:
            if variant and variant not in ranks:
                ranks[variant] = idx
    return ranks


_CLUSTER_RANKS = _build_rank_map(_CLUSTER_MEMBER_ORDER)
_FALLBACK_RANKS = _build_rank_map(_FALLBACK_OBJECT_ORDER)


def _get_rank(name: str, ranks: dict[str, int]) -> int | None:
    for variant in _canon_variants(name):
        if variant in ranks:
            return ranks[variant]
    return None


def _sort_key(name: str, ranks: dict[str, int]) -> tuple[float, str, str]:
    rank = _get_rank(name, ranks)
    canon = _canon(name)
    return (
        float(rank) if rank is not None else float("inf"),
        canon,
        str(name).lower(),
    )


def _sort_members(members: List[str], ranks: dict[str, int]) -> List[str]:
    return sorted(members, key=lambda member: _sort_key(member, ranks))


def _min_rank(names: List[str], ranks: dict[str, int]) -> float:
    values = [_get_rank(name, ranks) for name in names]
    filtered = [v for v in values if v is not None]
    return float(min(filtered)) if filtered else float("inf")


def _build_clusters(edges_major: List[tuple], visible_canons: set[str]) -> List[set[str]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges_major or []:
        try:
            a, b, meta = edge
        except ValueError:
            continue
        aspect = None
        if isinstance(meta, dict):
            aspect = meta.get("aspect")
        else:
            aspect = getattr(meta, "aspect", None)
        if not isinstance(aspect, str) or aspect.lower() != "conjunction":
            continue
        ca = _canon(a)
        cb = _canon(b)
        if ca in visible_canons and cb in visible_canons:
            adjacency[ca].add(cb)
            adjacency[cb].add(ca)

    clusters: List[set[str]] = []
    visited: set[str] = set()
    for node in adjacency:
        if node in visited:
            continue
        stack = [node]
        component: set[str] = set()
        visited.add(node)
        while stack:
            cur = stack.pop()
            component.add(cur)
            for nxt in adjacency[cur]:
                if nxt not in visited:
                    visited.add(nxt)
                    stack.append(nxt)
        if len(component) >= 2:
            clusters.append(component)
    return clusters


def _build_units(
    canon_to_name: dict[str, str],
    canon_to_pos: dict[str, int],
    clusters: List[set[str]],
) -> tuple[dict[str, dict], dict[str, str], List[str]]:
    units: dict[str, dict] = {}
    canon_to_unit: dict[str, str] = {}

    for idx, cluster in enumerate(clusters):
        members = [canon_to_name[c] for c in cluster if c in canon_to_name]
        if not members:
            continue
        first_index = min(canon_to_pos.get(c, 10**9) for c in cluster)
        unit_id = f"cluster_{idx}"
        units[unit_id] = {
            "members": members,
            "canons": set(cluster),
            "size": len(members),
            "first_index": first_index,
        }
        for canon in cluster:
            canon_to_unit[canon] = unit_id

    for canon, name in canon_to_name.items():
        if canon in canon_to_unit:
            continue
        unit_id = f"single_{canon}"
        units[unit_id] = {
            "members": [name],
            "canons": {canon},
            "size": 1,
            "first_index": canon_to_pos.get(canon, 10**9),
        }
        canon_to_unit[canon] = unit_id

    unit_order = sorted(units.keys(), key=lambda uid: units[uid]["first_index"])
    return units, canon_to_unit, unit_order


def _units_with_aspects(
    primary_id: str,
    units: dict[str, dict],
    canon_to_unit: dict[str, str],
    edges_major: List[tuple],
) -> List[str]:
    priorities: dict[str, int] = {}
    for edge in edges_major or []:
        try:
            a, b, meta = edge
        except ValueError:
            continue
        aspect = None
        if isinstance(meta, dict):
            aspect = meta.get("aspect")
        else:
            aspect = getattr(meta, "aspect", None)
        if not isinstance(aspect, str):
            continue
        aspect_key = aspect.strip().lower()
        priority = _ASPECT_PRIORITY.get(aspect_key)
        if priority is None:
            continue
        ca = _canon(a)
        cb = _canon(b)
        unit_a = canon_to_unit.get(ca)
        unit_b = canon_to_unit.get(cb)
        if unit_a == primary_id and unit_b and unit_b != primary_id:
            prev = priorities.get(unit_b)
            if prev is None or priority < prev:
                priorities[unit_b] = priority
        elif unit_b == primary_id and unit_a and unit_a != primary_id:
            prev = priorities.get(unit_a)
            if prev is None or priority < prev:
                priorities[unit_a] = priority

    sorted_units = sorted(
        priorities.items(),
        key=lambda item: (
            item[1],
            _min_rank(units[item[0]]["members"], _CLUSTER_RANKS),
            units[item[0]]["first_index"],
        ),
    )
    return [uid for uid, _ in sorted_units]


def _determine_visible_order(
    objs_df: pd.DataFrame,
    edges_major: List[tuple],
) -> List[str]:
    canon_to_name: dict[str, str] = {}
    canon_to_pos: dict[str, int] = {}
    names_in_order: List[tuple[str, int]] = []

    for pos, (_, row) in enumerate(objs_df.iterrows()):
        name = str(row.get("Object") or "").strip()
        canon = str(row.get("__canon") or "")
        if not name:
            continue
        names_in_order.append((name, pos))
        if not canon:
            continue
        canon_to_name.setdefault(canon, name)
        canon_to_pos.setdefault(canon, pos)

    if not canon_to_name:
        names_in_order.sort(key=lambda item: _sort_key(item[0], _FALLBACK_RANKS) + (item[1],))
        return [name for name, _ in names_in_order]

    visible_canons = set(canon_to_name.keys())
    clusters = _build_clusters(edges_major, visible_canons)
    units, canon_to_unit, unit_order = _build_units(canon_to_name, canon_to_pos, clusters)
    if not units:
        names_in_order.sort(key=lambda item: _sort_key(item[0], _FALLBACK_RANKS) + (item[1],))
        return [name for name, _ in names_in_order]

    cluster_unit_ids = [uid for uid in unit_order if units[uid]["size"] >= 2]
    if not cluster_unit_ids:
        names_in_order.sort(key=lambda item: _sort_key(item[0], _FALLBACK_RANKS) + (item[1],))
        return [name for name, _ in names_in_order]

    primary_unit_id = sorted(
        cluster_unit_ids,
        key=lambda uid: (
            -units[uid]["size"],
            _min_rank(units[uid]["members"], _CLUSTER_RANKS),
            units[uid]["first_index"],
        ),
    )[0]

    ordered_names: List[str] = []
    processed_units = {primary_unit_id}
    ordered_names.extend(_sort_members(units[primary_unit_id]["members"], _CLUSTER_RANKS))

    for uid in _units_with_aspects(primary_unit_id, units, canon_to_unit, edges_major):
        if uid in processed_units:
            continue
        ordered_names.extend(_sort_members(units[uid]["members"], _CLUSTER_RANKS))
        processed_units.add(uid)

    remaining_units = [uid for uid in unit_order if uid not in processed_units]
    remaining_units.sort(
        key=lambda uid: (
            _min_rank(units[uid]["members"], _FALLBACK_RANKS),
            -units[uid]["size"],
            units[uid]["first_index"],
        ),
    )

    for uid in remaining_units:
        ordered_names.extend(_sort_members(units[uid]["members"], _CLUSTER_RANKS))

    return ordered_names


def ordered_object_rows(
    df: pd.DataFrame,
    *,
    visible_objects: List[str] | None = None,
    edges_major: List[tuple] | None = None,
) -> pd.DataFrame:
    """Return object rows ordered according to visibility and pattern rules."""


    if df is None or "Object" not in df:
        return pd.DataFrame()
    # Ensure all AC/DC are renamed to Ascendant/Descendant for canonical filtering
    df["Object"] = df["Object"].replace({"AC": "Ascendant", "DC": "Descendant"})


    # Fallback: If Compass Rose is toggled and AC/DC missing, inject from Equal House cusps BEFORE any filtering
    compass_rose_on = False
    if visible_objects:
        compass_rose_on = any(
            _canon(name) in {"compassrose", "compass rose"}
            for name in visible_objects
        )
        ac_aliases = {"ac", "ascendant", "asc"}
        dc_aliases = {"dc", "descendant", "dsc"}
        obj_series_pre = df["Object"].astype("string")
        missing_ac = not any(_canon(name) in ac_aliases for name in obj_series_pre)
        missing_dc = not any(_canon(name) in dc_aliases for name in obj_series_pre)
        rows_to_add = []
        if compass_rose_on and (missing_ac or missing_dc):
            eq1 = df[df["Object"].astype(str).str.fullmatch(r"Equal 1H cusp", case=False)]
            eq7 = df[df["Object"].astype(str).str.fullmatch(r"Equal 7H cusp", case=False)]
            if missing_ac and not eq1.empty:
                ac_row = eq1.iloc[0].copy()
                ac_row["Object"] = "Ascendant"
                rows_to_add.append(ac_row)
            if missing_dc and not eq7.empty:
                dc_row = eq7.iloc[0].copy()
                dc_row["Object"] = "Descendant"
                rows_to_add.append(dc_row)
        if rows_to_add:
            print("[ordered_object_rows] Injecting AC/DC rows:", [r["Object"] for r in rows_to_add])
            add_df = pd.DataFrame(rows_to_add)
            df = pd.concat([df, add_df], ignore_index=True)

    # If Compass Rose is on, ensure all AC/DC canonical variants are in visible_objects
    if compass_rose_on:
        ac_variants = ["Ascendant", "AC", "Asc"]
        dc_variants = ["Descendant", "DC"]
        # Add to visible_objects if not present
        if visible_objects is not None:
            for v in ac_variants + dc_variants:
                if v not in visible_objects:
                    visible_objects.append(v)

    obj_series = df["Object"].astype("string")
    mask = ~obj_series.str.contains("cusp", case=False, na=False)
    objs_only = df.loc[mask].copy()
    if objs_only.empty:
        return objs_only

    objs_only["Object"] = objs_only["Object"].astype("string")
    objs_only["__canon"] = objs_only["Object"].map(_canon)

    print("[ordered_object_rows] Canonical names after filtering:", objs_only["Object"].tolist(), objs_only["__canon"].tolist())

    if visible_objects:
        visible_canon = {_canon(name) for name in visible_objects if name}
        print("[ordered_object_rows] Filtering for visible_canon:", visible_canon)
        if visible_canon:
            objs_only = objs_only[objs_only["__canon"].isin(visible_canon)]
            print("[ordered_object_rows] After visible_canon filter:", objs_only["Object"].tolist(), objs_only["__canon"].tolist())

    if objs_only.empty:
        print("[ordered_object_rows] Final sidebar DataFrame is EMPTY after filtering.")
        return objs_only.drop(columns=["__canon"], errors="ignore")

    order_names = _determine_visible_order(objs_only, edges_major or [])

    ordered_indices: List[int] = []
    seen_indices: set[int] = set()

    if order_names:
        for name in order_names:
            idxs = objs_only.index[objs_only["Object"] == name].tolist()
            for idx in idxs:
                if idx not in seen_indices:
                    ordered_indices.append(idx)
                    seen_indices.add(idx)

    for idx in objs_only.index:
        if idx not in seen_indices:
            ordered_indices.append(idx)
            seen_indices.add(idx)

    ordered_df = objs_only.loc[ordered_indices]
    print(f"[ordered_object_rows] Final sidebar DataFrame length: {len(ordered_df)}; objects: {ordered_df['Object'].tolist() if not ordered_df.empty else 'EMPTY'}")
    return ordered_df.drop(columns=["__canon"], errors="ignore")

__all__ = [
    "sabian_for",
    "load_fixed_star_catalog",
    "find_fixed_star_conjunctions",
    "STAR_CATALOG",
    "ordered_object_rows",
]

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

def format_object_profile_html(
    row,
    *,
    house_label: str = "Placidus",
    include_house_data: bool = True,
) -> str:
    """
    Build a single object's profile block using ONLY values already in the DF row.
    No recalculation here—pure formatting.
    """
    glyph = (row.get("Glyph") or "").strip()
    obj   = (row.get("Object") or "").strip()
    meaning = meaning_for(obj)

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
                house = row.get(alt)
                break

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
    if meaning:
        lines.append(f"<div class='pf-meaning'>{html.escape(meaning)}</div>")

    # Sign & degree, Sabian
    if sign or dms:
        lines.append(f"<div><strong>{sign} {dms}</strong></div>")
    if sabian:
        # in quotes and italicized
        lines.append(f"<div><em>“{sabian}”</em></div>")

    # Fixed stars & OOB
    if stars:
        lines.append("<div><strong>Fixed Star Conjunctions:</strong></div>")
        lines.append(f"<div>{stars}</div>")
    if oob and oob.lower() != "no":
        # show 'Yes' or 'Extreme'
        lines.append(f"<div>Out of Bounds: {oob}</div>")

    # House & Reception (Reception directly after House)
    if include_house_data and house is not None:
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
    if not include_house_data:
        by_house = ""

    if include_house_data and by_house:
        lines.append(f"<div><strong>Rulership by House:</strong><br/>{by_house} rules {obj}</div>")
    if by_sign:
        lines.append(f"<div><strong>Rulership by Sign:</strong><br/>{by_sign} rules {obj}</div>")

    # Join lines; add a divider for spacing between profiles
    inner = "\n".join(lines)
    return f"<div class='pf-block'>\n{inner}\n<hr class='pf-divider'/>\n</div>"
