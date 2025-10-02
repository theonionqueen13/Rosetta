#!/usr/bin/env python3
import argparse, json, os, inspect
import pandas as pd
from rosetta.brain import (
    build_context_for_objects,
    load_fixed_star_catalog,
    ensure_profile_detail_strings,
    choose_task_instruction
)

# Import your modules
from rosetta.calc import calculate_chart
from rosetta.brain import build_context_for_objects, load_fixed_star_catalog
import importlib
_L = importlib.import_module("rosetta.lookup")

MAJOR_OBJECTS = getattr(_L, "MAJOR_OBJECTS", [])
SIGN_NAMES    = getattr(_L, "SIGN_NAMES", [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
])
PLANETARY_RULERS = getattr(_L, "PLANETARY_RULERS", {})
ASPECTS = getattr(_L, "ASPECTS", {})
COMPASS = ["Ascendant","Descendant","MC","IC","North Node","South Node"]

def _sign_index(deg: float) -> int:
    return int((float(deg) % 360.0) // 30)

def _sign_from_degree(deg: float) -> str:
    return SIGN_NAMES[_sign_index(deg)]

def _in_forward_arc(a: float, b: float, x: float) -> bool:
    span = (b - a) % 360.0
    off  = (x - a) % 360.0
    return (off < span) if span != 0 else (off == 0)

def _house_of_degree(deg: float, cusps: list[float]) -> int | None:
    if not cusps or len(cusps) != 12:
        return None
    for i in range(12):
        if _in_forward_arc(cusps[i], cusps[(i+1) % 12], deg):
            return i + 1
    return 12

def _extract_cusps(df: pd.DataFrame):
    """
    Return 12 absolute degrees for house cusps, in 1..12 order.
    Your calc writes 'Computed Absolute Degree' for cusp rows; fall back to 'Longitude' if needed.
    """
    if "Object" not in df.columns:
        return []
    cusp_rows = df[df["Object"].astype(str).str.contains(r"^\s*\d+\s*H\s*Cusp\s*$", case=False, regex=True)].copy()
    if cusp_rows.empty:
        return []
    # sort by the numeric house number in "Object"
    cusp_rows["_house"] = cusp_rows["Object"].str.extract(r"(\d+)", expand=False).astype(int)
    cusp_rows = cusp_rows.sort_values("_house")
    # prefer 'Computed Absolute Degree' (your calc.py), fallback to 'Longitude'
    deg_col = "Computed Absolute Degree" if "Computed Absolute Degree" in cusp_rows.columns else "Longitude"
    vals = cusp_rows[deg_col].astype(float).tolist()
    return vals if len(vals) == 12 else []

def _build_pos(df: pd.DataFrame):
    """Create pos dict for major objects (and compass points if present)."""
    pos = {}
    if "abs_deg" not in df.columns:
        # normalize
        if "Longitude" in df.columns:
            df["abs_deg"] = pd.to_numeric(df["Longitude"], errors="coerce")
        else:
            df["abs_deg"] = pd.NA
    for obj in set(MAJOR_OBJECTS + COMPASS):
        row = df[df["Object"].astype(str) == obj]
        if not row.empty:
            val = row["abs_deg"].iloc[0]
            if pd.notna(val):
                pos[obj] = float(val) % 360.0
    return pos

def _visible(mode: str, custom_list: str, pos: dict):
    if mode == "compass":
        return [o for o in COMPASS if o in pos]
    if mode == "all":
        # everything we have a position for (major objects + compass)
        return [o for o in (set(MAJOR_OBJECTS) | set(COMPASS)) if o in pos]
    if mode == "custom":
        items = [s.strip() for s in custom_list.split(",") if s.strip()]
        return [o for o in items if o in pos]
    return []

def _compass_aspects(visible):
    """Only add the three axes as oppositions to keep 'single source of truth' for this CLI."""
    A = []
    def add(a,b):
        if a in visible and b in visible:
            A.append({"from": a, "to": b, "aspect": "Opposition"})
    add("South Node","North Node")
    add("Ascendant","Descendant")
    add("MC","IC")
    return A

def main():
    ap = argparse.ArgumentParser(description="Print Rosetta brain JSON context (no Gemini).")
    ap.add_argument("--year",   type=int, required=True)
    ap.add_argument("--month",  type=int, required=True, help="1-12")
    ap.add_argument("--day",    type=int, required=True)
    ap.add_argument("--hour",   type=int, required=True)
    ap.add_argument("--minute", type=int, required=True)
    ap.add_argument("--lat",    type=float, required=True)
    ap.add_argument("--lon",    type=float, required=True)
    ap.add_argument("--tz",     dest="tz_name", required=True, help="IANA tz, e.g. America/Chicago")
    ap.add_argument("--house",  default="equal", choices=["equal","whole","placidus"])
    ap.add_argument("--mode",   default="compass", choices=["compass","all","custom"])
    ap.add_argument("--objects", default="", help="Comma list for --mode custom")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    ap.add_argument("--out",    default="", help="Write JSON to file")
    args = ap.parse_args()

    # 1) Calculate chart DataFrame using your engine
    df = calculate_chart(
        args.year, args.month, args.day, args.hour, args.minute,
        tz_offset=0.0, lat=args.lat, lon=args.lon,
        input_is_ut=False, tz_name=args.tz_name, house_system=args.house
    )

    # 2) Build pos + cusps
    cusps = _extract_cusps(df)
    df["abs_deg"] = pd.to_numeric(df.get("Longitude", pd.NA), errors="coerce")
    pos = _build_pos(df)

    # 3) Which placements are “visible”
    visible = _visible(args.mode, args.objects, pos)

    # 4) Aspects: for CLI we include only Compass axes (no recalculation)
    aspects = _compass_aspects(visible)

    # 4.5) Build profile_rows mirroring the sidebar formatting (no recomputation)
    profile_rows = {}
    if "Object" in df.columns:
        obj_series = df["Object"].astype("string").str.strip()
        for obj in visible:
            hit = df[obj_series == obj]
            if not hit.empty:
                row = hit.iloc[0].to_dict()

                # degree for this object (prefer DF abs_deg, else from pos)
                deg = None
                if isinstance(row.get("abs_deg"), (int, float)):
                    deg = float(row["abs_deg"])
                elif obj in pos:
                    deg = float(pos[obj])

                if deg is not None:
                    # Sign (only if missing)
                    if not row.get("Sign"):
                        row["Sign"] = _sign_from_degree(deg)

                    # House (compute here so the brain doesn't)
                    if cusps and len(cusps) == 12:
                        hs = _house_of_degree(deg, cusps)
                        if hs:
                            row["House"] = int(hs)
                            # House Ruler (from cusp sign)
                            cusp_sign = SIGN_NAMES[_sign_index(cusps[hs - 1])]
                            hr = PLANETARY_RULERS.get(cusp_sign, [])
                            if isinstance(hr, str):
                                hr = [hr]
                            elif isinstance(hr, tuple):
                                hr = list(hr)
                            row["House Ruler"] = hr if hr else []
                sign = (row.get("Sign") or "").strip()
                rulers = PLANETARY_RULERS.get(sign, [])
                if isinstance(rulers, str):
                    rulers = [rulers] if rulers else []
                elif isinstance(rulers, tuple):
                    rulers = list(rulers)
                row["Sign Ruler"] = rulers if rulers else []

                ensure_profile_detail_strings(row)

                profile_rows[obj] = row

    # 5) Optional star catalog
    star_path = os.path.join("rosetta", "2b) Fixed Star Lookup.xlsx")
    star_df = None
    if os.path.exists(star_path):
        try:
            star_df = load_fixed_star_catalog(star_path)
        except Exception:
            star_df = None

    # 6) Build context with signature-aware kwargs (your brain may or may not have new params)
    ctx_kwargs = {
        "targets": visible,
        "pos": pos,
        "df": df,
        "active_shapes": [],
    }
    sig = inspect.signature(build_context_for_objects).parameters
    if "aspects" in sig:
        ctx_kwargs["aspects"] = aspects
    if "star_catalog" in sig:
        ctx_kwargs["star_catalog"] = star_df
    if "profile_rows" in sig:
        ctx_kwargs["profile_rows"] = profile_rows

    # 6.1) Build the context FIRST
    context = build_context_for_objects(**ctx_kwargs)

    # 6.2) Build the instruction string using the dispatcher (needs 'context')
    task = choose_task_instruction(
        chart_mode="natal",
        visible_objects=visible,
        active_shapes=[],
        context=context,
    )

    # 6.3) Put instruction FIRST in the output
    output = {"instruction": task}
    output.update(context)

    # 7) Print or write JSON
    text = json.dumps(output, indent=2 if args.pretty else None, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Wrote {args.out}")
    else:
        print(text)

if __name__ == "__main__":
    main()
