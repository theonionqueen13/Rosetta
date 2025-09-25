# rosetta/brain.py
# A lightweight “brain” that builds structured context from your own lookups & chart data.
from __future__ import annotations
from typing import Dict, List, Tuple, Any
import importlib
import math
import networkx as nx  # if you don’t have it, install with: pip install networkx
from rosetta.patterns import _cluster_conjunctions_for_detection
# ---- Load your lookups once (same pattern as rosetta5) ----
_L = importlib.import_module("rosetta.lookup")

GLYPHS                 = getattr(_L, "GLYPHS", {})
ALIASES_MEANINGS       = getattr(_L, "ALIASES_MEANINGS", {})
OBJECT_MEANINGS        = getattr(_L, "OBJECT_MEANINGS", {})
OBJECT_INTERPRETATIONS = getattr(_L, "OBJECT_INTERPRETATIONS", {})
OBJECT_MEANINGS_SHORT  = getattr(_L, "OBJECT_MEANINGS_SHORT", {})
SIGN_MEANINGS          = getattr(_L, "SIGN_MEANINGS", {})
HOUSE_MEANINGS         = getattr(_L, "HOUSE_MEANINGS", {})
ASPECTS                = getattr(_L, "ASPECTS", {})
ASPECT_INTERPRETATIONS = getattr(_L, "ASPECT_INTERPRETATIONS", {})
PLANETARY_RULERS       = getattr(_L, "PLANETARY_RULERS", {})
DIGNITIES              = getattr(_L, "DIGNITIES", {})
CATEGORY_MAP           = getattr(_L, "CATEGORY_MAP", {})
SABIAN_SYMBOLS         = getattr(_L, "SABIAN_SYMBOLS", {})
SIGN_NAMES             = getattr(_L, "SIGN_NAMES", [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
])

# ------------ Small internal helpers (no UI, no plotting) ------------
def _norm_name(name: str) -> str:
    """Normalize aliases to canonical names (e.g., AC -> Ascendant)."""
    if not name:
        return name
    return ALIASES_MEANINGS.get(name, name)

def _sign_index(longitude_deg: float) -> int:
    """0..11 sign index from absolute ecliptic longitude."""
    return int((longitude_deg % 360.0) // 30)

def _deg_in_sign(longitude_deg: float) -> int:
    """0..29 integer degrees within sign."""
    return int(round(longitude_deg % 30.0))

def _degree_for(name: str, pos: Dict[str, float]) -> float | None:
    """
    Find an object's degree from pos using the given name, its canonical display name,
    and any alias keys that map to that canonical display.
    Example: 'MC' -> tries 'MC', then 'Midheaven', then any alias that points to 'Midheaven'.
    """
    if not name:
        return None
    canonical = _norm_name(name)

    # Try the exact name and the canonical display name
    for nm in (name, canonical):
        if nm in pos and pos[nm] is not None:
            return pos[nm]

    # Try any alias that maps to this canonical display name
    for alias, display in ALIASES_MEANINGS.items():
        if display == canonical and alias in pos and pos[alias] is not None:
            return pos[alias]

    return None

def _get_row_from_df(name: str, df):
    """
    Pull the data row for this object from df['Object'] with alias awareness.
    Returns a dict (row) or None.
    """
    if df is None or "Object" not in df.columns:
        return None

    canonical = _norm_name(name)
    # names to try: exact, canonical, any alias→display matches, and any display→alias match
    names_to_try = {name, canonical}

    # alias -> display
    for alias, display in ALIASES_MEANINGS.items():
        if alias == name:
            names_to_try.add(display)
        if display == canonical:
            names_to_try.add(alias)

    obj_series = df["Object"].astype("string").str.strip()
    hit = df[obj_series.isin([str(n) for n in names_to_try])]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()

def _resolve_dignity(obj: str, sign: str) -> str:
    """
    Try both shapes of DIGNITIES:
    - DIGNITIES[obj][sign] -> 'Domicile', etc.
    - DIGNITIES[sign][obj] -> 'Domicile', etc.
    Returns '' if not found.
    """
    if not obj or not sign:
        return ""
    try:
        d = DIGNITIES.get(obj)
        if isinstance(d, dict):
            s = d.get(sign)
            if s:
                return s
        d2 = DIGNITIES.get(sign)
        if isinstance(d2, dict):
            s = d2.get(obj)
            if s:
                return s
    except Exception:
        pass
    return ""

def _extract_cusps_from_df(df) -> List[float]:
    """
    Try to extract the 12 house cusp longitudes from the DataFrame your app already produces.
    If not present, return [] and the caller can decide to skip 'house' in context.
    """
    if df is None or "Object" not in df.columns or "Longitude" not in df.columns:
        return []
    # Common labels you already use (variants are handled)
    labels = [
        "1 H Cusp","2 H Cusp","3 H Cusp","4 H Cusp","5 H Cusp","6 H Cusp",
        "7 H Cusp","8 H Cusp","9 H Cusp","10 H Cusp","11 H Cusp","12 H Cusp"
    ]
    cusps = []
    for lab in labels:
        row = df[df["Object"].astype(str).str.fullmatch(lab, case=False, na=False)]
        if row.empty:
            return []
        try:
            cusps.append(float(row["Longitude"].iloc[0]))
        except Exception:
            return []
    return cusps  # 12 floats

def _in_forward_arc(start_deg: float, end_deg: float, x_deg: float) -> bool:
    """True if x lies on the forward arc from start->end (mod 360)."""
    span = (end_deg - start_deg) % 360.0
    off  = (x_deg   - start_deg) % 360.0
    return (off < span) if span != 0 else (off == 0)

def _house_of_degree(deg: float, cusps: List[float]) -> int | None:
    """Given a degree and 12 cusp list, return 1..12 or None."""
    if not cusps or len(cusps) != 12:
        return None
    for i in range(12):
        a = cusps[i]
        b = cusps[(i + 1) % 12]
        if _in_forward_arc(a, b, deg):
            return i + 1
    return 12

def _angle_sep(a: float, b: float) -> float:
    """Smallest angular separation (0..180)."""
    d = abs((a - b) % 360.0)
    return 360.0 - d if d > 180.0 else d

def build_object_context(name: str, pos: dict, df, profile_rows: dict | None = None) -> dict:
    canonical = _norm_name(name)
    abs_deg = _degree_for(name, pos)
    if abs_deg is None:
        return {"object": canonical, "available": False, "reason": f"No position for {name!r} in pos"}

    # Prefer prebuilt sidebar/enriched row
    row = {}
    if profile_rows and name in profile_rows:
        row = profile_rows[name]
    elif profile_rows and canonical in profile_rows:
        row = profile_rows[canonical]
    else:
        # DF fallback only (no computations here)
        row = _get_row_from_df(name, df) or {}

    # Sign: prefer row; minimal fallback to degree-derived sign is OK
    sign_name = (row.get("Sign") or "").strip()
    if not sign_name:
        sign_name = SIGN_NAMES[_sign_index(abs_deg)]
    deg_in = _deg_in_sign(abs_deg)

    # House: ONLY if present in row (no computation)
    house = None
    if "House" in row and str(row["House"]).strip():
        try:
            house = int(row["House"])
        except Exception:
            house = None

    # Motion/flags: read as-is from row
    motion_raw = " ".join(str(row.get(k, "")) for k in ["Retrograde","Rx","Motion","Station"]).lower()
    rx_flag      = ("rx" in motion_raw) or ("retro" in motion_raw)
    station_flag = ("station" in motion_raw)
    oob_raw  = str(row.get("OOB Status", "") or row.get("OOB", "") or row.get("Out of Bounds", "")).strip().lower()
    oob_flag = oob_raw in ("yes","true","y","1")

    # Dignity: ONLY if present in row (no lookup fallback) — be robust to non-strings
    _d = row.get("Dignity")
    dignity = _d.strip() if isinstance(_d, str) else ""


    # Rulers: ONLY if present in row (no lookup fallback)
    def _as_list(x):
        if isinstance(x, (list, tuple)):
            return list(x)
        return [x] if x else []

    sign_ruler  = _as_list(row.get("Sign Ruler"))
    house_ruler = _as_list(row.get("House Ruler"))

    display_name = (row.get("Display Name") or canonical).strip()
    sabian = (row.get("Sabian Symbol") or row.get("Sabian") or "").strip()

    ctx = {
        "object": canonical,
        "display_name": display_name,
        "glyph": GLYPHS.get(canonical, ""),
        "absolute_degree": round(abs_deg % 360.0, 2),
        "sign": sign_name,
        "degree_in_sign": int(deg_in),
        "house": int(house) if house else None,
        "house_meaning": HOUSE_MEANINGS.get(int(house), "") if house else "",
        "sign_meaning": SIGN_MEANINGS.get(sign_name, ""),
        "object_meaning": OBJECT_MEANINGS.get(canonical) or OBJECT_INTERPRETATIONS.get(canonical, ""),
        "object_meaning_short": OBJECT_MEANINGS_SHORT.get(canonical, ""),
        "sabian_symbol": sabian,
        "retrograde": bool(rx_flag),
        "station": bool(station_flag),
        "oob": bool(oob_flag),
        "declination": row.get("Declination", ""),
        "latitude": row.get("Latitude", ""),
        "speed": row.get("Speed", ""),
        "dignity": dignity,
        "sign_ruler": sign_ruler,
        "house_ruler": house_ruler,
    }
    return ctx

def build_context_for_objects(
    targets: List[str],
    pos: Dict[str, float],
    df,
    active_shapes: List[Any] | None = None,
    aspects: List[Dict[str, str]] | None = None,
    star_catalog=None,
    profile_rows: dict | None = None,
) -> Dict[str, Any]:
    """
    Build the context for interpretation:
    - objects: ONLY selected/toggled placements (targets)
    - aspects: ALREADY clustered by conjunctions (single source of truth)
    - global:  compact orientation (compass) + dispositor_graph summary
    - shapes:  active shapes (human-readable)
    - fixed_stars: optional hits
    """
    # Per-object profiles (visible only)
    out_objects = [build_object_context(t, pos, df, profile_rows=profile_rows) for t in targets]

    context = {
        "version": "brain.v1",
        "objects": out_objects,
        "shapes": [],
        "aspects": [],
        "notes": {
            "protocol": (
                "Profiles cover only the selected objects. "
                "Use global context (compass, dispositors summary) for orientation, "
                "but do not output those as full profiles unless relevant."
            )
        },
        "global": {}
    }

    # Clustered aspects (ONLY what the renderer hands in)
    if aspects:
        context["aspects"] = _collapse_aspects_by_clusters(aspects, targets, pos)

    # Silent global layers
    context["global"].update(build_compass_context(pos, df))              # keep
    context.update(build_shapes_context(active_shapes))                    # keep
    context["global"]["dispositor_graph"] = analyze_dispositors(pos, df)  # summary only

    # Fixed stars (optional)
    if star_catalog is not None:
        context.update(build_fixed_star_context(pos, star_catalog))

    return context

def _collapse_aspects_by_clusters(
    aspects: List[Dict[str, str]],
    visible: List[str],
    pos: Dict[str, float],
) -> List[Dict[str, Any]]:
    """
    Convert pairwise aspects into cluster-to-cluster aspects using your
    _cluster_conjunctions_for_detection (single source of truth).
    Input 'aspects' are dicts like {"from": A, "to": B, "aspect": "Opposition"}.
    Output entries look like:
      {"left": ["Sun","South Node","IC"], "aspect": "Opposition", "right": ["MC","North Node"]}
    Dedupe by (frozenset(left), aspect, frozenset(right)).
    """
    if not aspects:
        return []

    # 1) Build cluster maps only over visible objects
    vis = [o for o in visible if o in pos]
    rep_pos, rep_map, rep_anchor = _cluster_conjunctions_for_detection(pos, vis)

    # Helper: return the full, ordered membership list for an object’s cluster
    def members_for(obj: str) -> List[str]:
        if obj not in rep_anchor:
            return [obj]  # singleton
        rep = rep_anchor[obj]
        cluster = rep_map.get(rep, [obj])
        # order members by their absolute degree for stability
        return sorted(cluster, key=lambda m: pos.get(m, 9999.0))

    # 2) Collapse endpoints to their clusters
    seen = set()
    out  = []
    for e in aspects:
        a = e.get("from"); b = e.get("to"); asp = e.get("aspect")
        if not a or not b or not asp:
            continue
        L = members_for(a)
        R = members_for(b)
        # skip internal edges (aspect within the same cluster)
        if set(L) == set(R):
            continue

        key = (frozenset(L), asp, frozenset(R))
        # also treat reversed cluster pair the same for symmetry
        rkey = (frozenset(R), asp, frozenset(L))
        if key in seen or rkey in seen:
            continue
        seen.add(key)

        out.append({"left": L, "aspect": asp, "right": R})

    return out

# ------------ Minimal Gemini wrapper (output-only safe) ------------
import json

def ask_gemini_brain(genai_module, prompt_text: str, context: Dict[str, Any],
                     model: str = "gemini-1.5-flash", temperature: float = 0.2) -> str:
    generative_model = genai_module.GenerativeModel(
        model_name=model,
        system_instruction=(
            "You are an astrology interpreter.\n"
            "ONLY generate profile sections for placements listed in OBJECTS.\n"
            "Use ONLY ASPECTS for relationships; do not recalculate or infer aspects.\n"
            "GLOBAL context (compass, dispositors, graph) is for orientation only.\n"
            "Write clearly, address the user as 'you'.\n"
            "Do not use the word 'Astroneurology'."
        ),
        generation_config={"temperature": temperature},
    )

    payload = (
        f"TASK:\n{prompt_text.strip()}\n\n"
        f"OBJECTS (visible only):\n{json.dumps(context.get('objects', []), indent=2)}\n\n"
        f"ASPECTS (single source of truth):\n{json.dumps(context.get('aspects', []), indent=2)}\n\n"
        f"SHAPES:\n{json.dumps(context.get('shapes', []), indent=2)}\n\n"
        f"GLOBAL (silent orientation):\n{json.dumps(context.get('global', {}), indent=2)}\n\n"
        f"FIXED STARS:\n{json.dumps(context.get('fixed_stars', {}), indent=2)}\n"
    )

    resp = generative_model.generate_content(payload)
    if not getattr(resp, "candidates", None):
        return "⚠️ Gemini returned no content (possibly safety-blocked)."
    return (resp.text or "").strip()


# -----------------------------
# Global Context Collectors
# -----------------------------
def build_dispositor_context(pos: dict, df) -> dict:
    """
    Phase 1: raw dispositor mapping for ALL major objects.
    - sign_ruler: ruler of the object's sign
    - house_ruler: ruler of the sign on the house cusp the object sits in
    """
    cusps = _extract_cusps_from_df(df)  # list of 12 absolute degrees or []
    out = {}

    for obj, deg in pos.items():
        # object's sign + sign ruler
        sign_idx    = _sign_index(deg)
        sign        = SIGN_NAMES[sign_idx]
        sign_ruler  = PLANETARY_RULERS.get(sign, "")

        # object's house + ruler of that house cusp sign
        house       = _house_of_degree(deg, cusps) if cusps else None
        house_ruler = ""
        if house and cusps and 1 <= house <= 12:
            cusp_deg   = cusps[house - 1]
            cusp_sign  = SIGN_NAMES[_sign_index(cusp_deg)]
            house_ruler = PLANETARY_RULERS.get(cusp_sign, "")

        out[_norm_name(obj)] = {
            "sign": sign,
            "sign_ruler": sign_ruler,
            "house": int(house) if house else None,
            "house_ruler": house_ruler,
        }

    return {"dispositors": out}

def build_compass_context(pos: dict, df) -> dict:
    """
    Always analyze Compass Rose points (AC/DC, MC/IC, Nodes) even if not toggled.
    For now, just attach their core profile data.
    """
    compass_points = ["Ascendant", "Descendant", "MC", "IC", "North Node", "South Node"]
    out = {}
    for pt in compass_points:
        deg = pos.get(pt)
        if deg is None:
            continue
        sign_idx = _sign_index(deg)
        sign = SIGN_NAMES[sign_idx]
        house = None
        cusps = _extract_cusps_from_df(df)
        if cusps:
            house = _house_of_degree(deg, cusps)

        out[pt] = {
            "absolute_degree": round(deg % 360.0, 2),
            "sign": sign,
            "degree_in_sign": _deg_in_sign(deg),
            "house": house,
            "sign_meaning": SIGN_MEANINGS.get(sign, ""),
            "object_meaning": OBJECT_MEANINGS.get(pt, ""),
        }
    return {"compass": out}

import pandas as pd

# -----------------------------
# Shapes Context
# -----------------------------

def build_shapes_context(active_shapes: list) -> dict:
    """
    Take the list of active shapes detected in the chart
    and map them to human-readable instructions.
    """
    out = []
    for shape in active_shapes or []:
        instruction = SHAPE_INSTRUCTIONS.get(shape, "")
        out.append({
            "name": shape,
            "instruction": instruction
        })
    return {"shapes": out}


# -----------------------------
# Fixed Stars Context
# -----------------------------

def load_fixed_star_catalog(path: str) -> pd.DataFrame:
    """
    Load the fixed star Excel catalog.
    Expect columns: Name, Sign, Degree, Orb, Meaning (where available).
    """
    df = pd.read_excel(path)
    df.columns = [c.strip().lower() for c in df.columns]  # normalize headers
    return df


def build_fixed_star_context(pos: dict, catalog: pd.DataFrame) -> dict:
    """
    For each planet/point in pos, check if it conjoins any star within orb.
    Return a mapping of hits.
    """
    out = {}
    for obj, deg in pos.items():
        matches = []
        for _, row in catalog.iterrows():
            star_name = row.get("name")
            sign = row.get("sign")
            star_deg = row.get("degree")
            orb = row.get("orb", 1.0)
            meaning = row.get("meaning", "")

            if pd.isna(star_name) or pd.isna(sign) or pd.isna(star_deg):
                continue

            # Convert star degree into absolute zodiac degree
            sign_idx = SIGN_NAMES.index(sign) if sign in SIGN_NAMES else None
            if sign_idx is None:
                continue
            abs_deg = sign_idx * 30 + float(star_deg)

            sep = abs((deg - abs_deg + 180) % 360 - 180)  # min separation
            if sep <= orb:
                matches.append({
                    "star": star_name,
                    "orb": round(sep, 2),
                    "meaning": meaning
                })

        if matches:
            out[_norm_name(obj)] = matches
    return {"fixed_stars": out}

# -----------------------------
# Dispositor Graph Analysis
# -----------------------------
def analyze_dispositors(pos: dict, df) -> dict:
    """
    Build a rulership (dispositor) graph across ALL objects in pos.
    Returned JSON is compact:
      - dominant_rulers: out-degree >= 3
      - final_dispositors: in-degree >=1 and out-degree == 0
      - sovereign: single-node self-rulers (Sun in Leo, Saturn in Capricorn, etc.)
      - loops: cycles of length >= 2 (e.g., Venus -> Moon -> Mars -> Venus)
    We do NOT emit the raw edges list in JSON to save tokens.
    Internally we label parallel edges (sign, house, or both) but that’s not returned.
    """
    cusps = _extract_cusps_from_df(df)
    G = nx.DiGraph()

    # Track parallel reasons internally, in case you want to log
    from collections import defaultdict
    reasons = defaultdict(set)  # (src, dst) -> {'sign','house'}

    def _add_reasons(src, dsts, why: str):
        if not dsts:
            return
        if isinstance(dsts, (list, tuple)):
            for d in dsts:
                if d:
                    G.add_edge(src, d)
                    reasons[(src, d)].add(why)
        else:
            G.add_edge(src, dsts)
            reasons[(src, dsts)].add(why)

    for obj, deg in pos.items():
        sign = SIGN_NAMES[_sign_index(deg)]
        sign_rulers = PLANETARY_RULERS.get(sign, [])
        _add_reasons(obj, sign_rulers, "sign")

        if cusps:
            h = _house_of_degree(deg, cusps)
            if h:
                cusp_sign = SIGN_NAMES[_sign_index(cusps[h - 1])]
                house_rulers = PLANETARY_RULERS.get(cusp_sign, [])
                _add_reasons(obj, house_rulers, "house")

    # Classify
    cycles = list(nx.simple_cycles(G))
    sovereign = sorted([c[0] for c in cycles if len(c) == 1])   # single-node self-loop
    loops     = [c for c in cycles if len(c) >= 2]              # multi-node only

    dominant = sorted([n for n, outdeg in G.out_degree() if outdeg >= 3])
    final    = sorted([n for n in G.nodes if G.out_degree(n) == 0 and G.in_degree(n) >= 1])

    # We do NOT include raw edges in JSON. If you ever need a compact edge summary,
    # you could compute counts here without listing each link.

    return {
        "dominant_rulers": dominant,
        "final_dispositors": final,
        "sovereign": sovereign,
        "loops": loops,
    }

# -----------------------------
# Task Dispatcher
# -----------------------------
def choose_task_instruction(chart_mode: str,
                            visible_objects: list,
                            active_shapes: list,
                            context: dict) -> str:
    if chart_mode == "natal":
        return (
            "You are an astrology interpreter.\n"
            "ONLY generate profile sections for the placements in context.objects.\n"
            "Use EXACTLY context.aspects for inter-object relationships; these are pre-clustered.\n"
            "Do NOT recalculate or invent aspects. Do NOT infer relationships from the dispositor graph.\n"
            "Use global context (compass summary; dispositor_graph summary) only for orientation notes—"
            "do not expand them into full profiles unless the points are in context.objects.\n"
            "Write clearly, address the user as 'you', and avoid cookbook clichés."
        )
    return "Describe the chart elements clearly and factually using only the provided context."
