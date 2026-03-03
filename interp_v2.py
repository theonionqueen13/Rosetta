"""
interp_v2.py - New chart interpreter for Rosetta v2

This module provides a clean, modern replacement for the legacy
``interp.py``/``interp_refactor.py`` classes.  The original code was
written prior to the introduction of ``models_v2`` and the
``RenderResult`` dataclass, and over time it has accumulated a large
amount of filtering and normalization logic that now lives elsewhere in
the codebase.

The new ``ChartInterpreter`` accepts a :class:`drawing_v2.RenderResult`
object along with optional mode/lookup overrides.  It delegates object
ordering to :func:`profiles_v2.ordered_object_rows`, uses the
central ``static_db`` lookups defined in ``models_v2`` and keeps its
implementation deliberately small and easy to extend.

Because many existing callers still import the old interpreter, the
legacy module remains intact but deprecated; new code should import
from ``interp_v2`` instead.

Usage::

    from drawing_v2 import RenderResult
    from interp_v2 import ChartInterpreter

    interp = ChartInterpreter(result)
    text = interp.generate(mode="technical")

"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from models_v2 import static_db
from profiles_v2 import (
    STAR_CATALOG,
    find_fixed_star_conjunctions,
    ordered_object_rows,
    _canon,
)
from drawing_v2 import RenderResult

# the interpreter cares only about clustered aspects; if the import fails
# we provide no-op fallbacks to keep the module importable in isolation.
try:
    from calc_v2 import build_conjunction_clusters
except ImportError:  # pragma: no cover - safety fallback
    def build_conjunction_clusters(df, edges):
        return {}, {}, set()


# --- constants ------------------------------------------------------------
AXIS_MAP: Dict[str, str] = {
    "AC": "Ascendant",
    "DC": "Descendant",
    "Mc": "MC",
    "Ic": "IC",
    "Ascendant": "Ascendant",
    "Descendant": "Descendant",
    "MC": "MC",
    "IC": "IC",
    "North Node": "North Node",
    "South Node": "South Node",
}

COMPASS_KEYS: Dict[frozenset, str] = {
    frozenset(["Ascendant", "Descendant"]): "ACDC",
    frozenset(["MC", "IC"]): "MCIC",
    frozenset(["North Node", "South Node"]): "Nodes",
}

ZODIAC_ORDER: List[str] = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]


# ---------------------------------------------------------------------------
class ChartInterpreter:
    """Generate poetic/technical text for a rendered chart.

    ``result`` should normally be the ``RenderResult`` returned by one of
    the rendering helpers in :mod:`drawing_v2`.  The object must contain at
    least ``visible_objects``, ``drawn_major_edges``/``drawn_minor_edges``
    and a ``plot_data`` mapping with an ``'ordered_df'`` key; missing
    attributes are handled gracefully so that older callers continue to
    work.

    ``mode`` defaults to ``"poetic"``; passing ``"technical"`` causes the
    circuit summary to use a terser, data‑oriented sentence.

    ``lookup`` allows ephemeral overrides to the standard static database.
    If omitted, a fully‑populated dictionary is pulled from
    :mod:`models_v2.static_db` and the fixed‑star helpers in
    :mod:`profiles_v2`.
    """

    def __init__(
        self,
        result: RenderResult,
        mode: str = "poetic",
        lookup: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.result = result
        self.mode = mode
        self.lookup = lookup or self._default_lookup()
        self.missing: List[str] = []

        # visible_objects list; may be None or not yet set
        self.visible_objects: List[str] = getattr(result, "visible_objects", []) or []

        # edges drawn during rendering (major/minor)
        self.drawn_major_edges: List[Tuple[str, str, Any]] = getattr(
            result, "drawn_major_edges", []
        ) or []
        self.drawn_minor_edges: List[Tuple[str, str, Any]] = getattr(
            result, "drawn_minor_edges", []
        ) or []

        # compute ordered_df using the same helper used elsewhere in the
        # application.  this keeps filtering logic in one place and makes
        # the interpreter trivial.
        raw_df: Optional[pd.DataFrame] = None
        if result.plot_data:
            raw_df = result.plot_data.get("ordered_df")

        # if plot_data didn't provide anything, try to fall back on
        # Streamlit session state (UI callers only).
        if (raw_df is None or (isinstance(raw_df, pd.DataFrame) and raw_df.empty)):
            try:
                import streamlit as st  # type: ignore

                last = st.session_state.get("last_df")
                if last is not None and isinstance(last, pd.DataFrame):
                    raw_df = last
            except Exception:
                # not running under streamlit or no data available
                pass

        if raw_df is not None and not raw_df.empty:
            # apply object ordering/visibility filter
            self.ordered_df = ordered_object_rows(
                raw_df,
                visible_objects=self.visible_objects,
                edges_major=self.drawn_major_edges,
            )
            # also trim drawn_major_edges to match the filtered objects
            if self.ordered_df is not None:
                active = set(self.ordered_df["Object"].tolist())
                self.drawn_major_edges = [
                    e for e in self.drawn_major_edges if e[0] in active and e[1] in active
                ]
        else:
            self.ordered_df = None

    # internal helpers ------------------------------------------------------

    def _default_lookup(self) -> Dict[str, Any]:
        """Return a copy of the standard lookup dictionary from ``static_db``."""
        return {
            "GLYPHS": static_db.GLYPHS,
            "OBJECT_MEANINGS": static_db.OBJECT_MEANINGS,
            "SIGN_MEANINGS": static_db.SIGN_MEANINGS,
            "HOUSE_MEANINGS": static_db.HOUSE_MEANINGS,
            "INTERP_FLAGS": getattr(static_db, "INTERP_FLAGS", {}),
            "SABIAN_SYMBOLS": static_db.SABIAN_SYMBOLS,
            "ASPECT_INTERP": static_db.ASPECT_INTERP,
            "FIXED_STAR_CATALOG": STAR_CATALOG,
            "find_fixed_star_conjunctions": find_fixed_star_conjunctions,
        }

    def _get_object_row(self, obj_name: str) -> Optional[pd.Series]:
        """Locate the DataFrame row for ``obj_name`` (handles abbreviations)."""
        if self.ordered_df is None:
            return None

        # build a small set of candidates including axis map variants
        variants = {obj_name}
        for key, val in AXIS_MAP.items():
            if val == obj_name:
                variants.add(key)
        # canonical forms (sun -> sun) – use _canon so 'AC' == 'Ascendant'
        canon_variants = {_canon(v) for v in variants}

        for _, row in self.ordered_df.iterrows():
            if _canon(row.get("Object", "")) in canon_variants:
                return row
        return None

    def _get_axis_info(self, obj_name: str) -> Tuple[Any, Any]:
        """Return (house, sign) for an object or (None, None) if unknown."""
        row = self._get_object_row(obj_name)
        if row is not None:
            house = (
                row.get("Placidus House")
                or row.get("House")
                or row.get("Equal House")
                or row.get("Whole Sign House")
            )
            sign = row.get("Sign")
            return house, sign
        return None, None

    def _interpret_object(self, row: pd.Series) -> str:
        obj = row.get("Object", "")
        sign = row.get("Sign", "")
        dms = row.get("DMS", "")
        house = (
            row.get("Placidus House")
            or row.get("House")
            or row.get("Equal House")
            or row.get("Whole Sign House")
        )
        lon_abs: Optional[float] = row.get("Longitude")

        # house meaning
        house_num = None
        if house is not None:
            try:
                house_num = int(float(house))
            except Exception:
                house_num = str(house)
        house_meaning = None
        if house_num is not None:
            hm = self.lookup.get("HOUSE_MEANINGS", {})
            house_meaning = hm.get(house_num)
            if house_meaning:
                # keep only the short description if lookup is structured
                if isinstance(house_meaning, dict):
                    house_meaning = house_meaning.get("meaning", str(house_meaning))
            else:
                self.missing.append(f"house_meaning:{house_num}")
                house_meaning = f"[No meaning for house {house_num}]"

        glyph = self.lookup.get("GLYPHS", {}).get(obj, row.get("Glyph", ""))
        meaning = self.lookup.get("OBJECT_MEANINGS", {}).get(obj)
        if not meaning:
            self.missing.append(f"meaning:{obj}")
            meaning = f"[No meaning for {obj}]"

        sign_meaning = self.lookup.get("SIGN_MEANINGS", {}).get(sign)
        if sign_meaning:
            # structured data now uses a dict with a "meaning" key
            if isinstance(sign_meaning, dict):
                sign_meaning = sign_meaning.get("meaning", str(sign_meaning))
        else:
            self.missing.append(f"sign_meaning:{sign}")
            sign_meaning = f"[No meaning for sign {sign}]"

        retrograde = row.get("Retrograde Bool", False)
        dignity = row.get("Dignity", "")

        interp_flags = self.lookup.get("INTERP_FLAGS", {}).get(obj, "")
        if row.get("INTERP_FLAGS"):
            interp_flags = f"{interp_flags} {row.get('INTERP_FLAGS')}".strip()

        sabian = row.get("Sabian Symbol", "")
        if not sabian and sign and lon_abs is not None:
            sabian = self.lookup.get("SABIAN_SYMBOLS", {}).get(
                (sign, int(lon_abs % 30) + 1),
                "",
            )

        # normalize sabian output: we want phrase and optional short meaning
        sabian_phrase: Optional[str] = None
        sabian_short: Optional[str] = None
        if sabian:
            if isinstance(sabian, dict):
                # the lookup dict may contain sabian_symbol/symbol fields
                sabian_phrase = sabian.get("sabian_symbol") or sabian.get("symbol") or ""
                sabian_short = sabian.get("short_meaning")
            else:
                sabian_phrase = str(sabian)
        # at this point sabian_phrase holds the text we will render

        fixed_stars = ""
        if self.lookup.get("find_fixed_star_conjunctions") and lon_abs is not None:
            try:
                hits = self.lookup["find_fixed_star_conjunctions"](
                    lon_abs, self.lookup.get("FIXED_STAR_CATALOG"), orb=1.0
                )
                if hits:
                    fixed_stars = ", ".join(
                        f"{h['Name']} (orb {h['sep']:.2f}°)" for h in hits
                    )
            except Exception:
                self.missing.append(f"fixedstars:{obj}")

        lines: List[str] = []
        name_line = f"{glyph} {obj}"
        if retrograde:
            name_line += " (Rx)"
        if dignity:
            name_line += f" - {dignity}"
        name_line += f" in {sign} {dms}."
        lines.append(name_line)
        lines.append(meaning)
        lines.append(f"Sign meaning: {sign_meaning}")
        if house_meaning and house_num is not None:
            lines.append(f"House {house_num}: {house_meaning}")
        if interp_flags:
            lines.append(f"Flags: {interp_flags}")
        if sabian_phrase:
            lines.append(f"Sabian Symbol: {sabian_phrase}")
            if sabian_short:
                lines.append(f"Sabian Symbol Meaning: {sabian_short}")
        if fixed_stars:
            lines.append(f"Fixed Stars: {fixed_stars}")
        return "\n".join([l for l in lines if l])

    def _axis_key(self, val1: Any, val2: Any, *, kind: str) -> Optional[str]:
        if val1 is None or val2 is None:
            return None
        if kind == "house":
            try:
                v1, v2 = int(float(val1)), int(float(val2))
                return f"{min(v1, v2)}-{max(v1, v2)}"
            except Exception:
                return None
        elif kind == "sign":
            s1, s2 = str(val1).title(), str(val2).title()
            try:
                i1, i2 = ZODIAC_ORDER.index(s1), ZODIAC_ORDER.index(s2)
                return f"{ZODIAC_ORDER[min(i1, i2)]}-{ZODIAC_ORDER[max(i1, i2)]}"
            except ValueError:
                return f"{min(s1, s2)}-{max(s1, s2)}"
        else:
            return None

    def _interpret_axis_pair(self, axis1: str, axis2: str, interp_key: str) -> str:
        def get_label(name: str, sign: Optional[str]) -> str:
            full, abbr = {
                "Ascendant": ("Ascendant", "AC"),
                "Descendant": ("Descendant", "DC"),
                "MC": ("Midheaven", "MC"),
                "IC": ("Imum Coeli", "IC"),
                "North Node": ("North Node", "\u260A"),
                "South Node": ("South Node", "\u260B"),
            }.get(name, (name, name))
            label = f"{full} ({abbr})"
            if sign:
                label += f" in {sign}"
            return label

        interp_text = COMPASS_KEYS.get(frozenset([axis1, axis2]), "")
        interp_text = static_db.COMPASS_AXIS_INTERP.get(interp_key, interp_text)
        connector = "↔"

        house_a, sign_a = self._get_axis_info(axis1)
        house_b, sign_b = self._get_axis_info(axis2)

        label_a = get_label(axis1, sign_a)
        label_b = get_label(axis2, sign_b)
        output = [f"{label_a} {connector} {label_b}: {interp_text}"]

        hkey = self._axis_key(house_a, house_b, kind="house")
        if hkey:
            h_interp = static_db.HOUSE_AXIS_INTERP.get(hkey)
            if h_interp:
                output.append(str(h_interp))
        skey = self._axis_key(sign_a, sign_b, kind="sign")
        if skey:
            s_interp = static_db.SIGN_AXIS_INTERP.get(skey)
            if s_interp:
                output.append(str(s_interp))
        return "\n".join(output)

    def _interpret_aspect(self, a: str, b: str, meta: Dict[str, Any]) -> str:
        aspect = meta.get("aspect", "")
        key = aspect.strip().title() if aspect else ""
        interp_text = self.lookup.get("ASPECT_INTERP", {}).get(key, f"[{aspect.title()} aspect]")
        connector = "Opposite" if key == "Opposition" else key
        out: List[str] = [f"{a} {connector} {b}: {interp_text}"]

        if key == "Opposition":
            house_a, sign_a = self._get_axis_info(a)
            house_b, sign_b = self._get_axis_info(b)
            hkey = self._axis_key(house_a, house_b, kind="house")
            if hkey:
                h_interp = static_db.HOUSE_AXIS_INTERP.get(hkey)
                if h_interp:
                    out.append(str(h_interp))
            skey = self._axis_key(sign_a, sign_b, kind="sign")
            if skey:
                s_interp = static_db.SIGN_AXIS_INTERP.get(skey)
                if s_interp:
                    out.append(str(s_interp))
        return "\n".join(out)

    def _interpret_circuit(self, objects: List[str], aspects: List[str]) -> str:
        if self.mode == "poetic":
            return "Together, these forces weave a unique circuit of meaning."
        else:
            objs_str = ", ".join(objects[:5]) + ("..." if len(objects) > 5 else "")
            aspects_str = ", ".join(sorted(set(aspects)))
            return f"Circuit summary: Objects {objs_str} with aspects {aspects_str}."

    # public ----------------------------------------------------------------

    def generate(self, mode: Optional[str] = None) -> str:
        if mode:
            self.mode = mode
        if self.ordered_df is None or self.ordered_df.empty:
            return "No active objects selected to interpret."

        sections: List[str] = []
        handled = set()

        # objects
        obj_texts: List[str] = []
        for _, r in self.ordered_df.iterrows():
            text = self._interpret_object(r) or ""
            # trim trailing/leading whitespace and collapse internal multiple blank lines
            text = text.strip()
            # replace any occurrence of 3+ newlines with exactly two (one blank line)
            import re

            text = re.sub(r"\n{3,}", "\n\n", text)
            obj_texts.append(text)

        body = "\n\n".join(obj_texts)
        # ensure the joined body doesn't accidentally contain too many blanks
        import re

        body = re.sub(r"\n{3,}", "\n\n", body)
        sections.append("💫 Object Placements\n" + body)

        # compass/axes
        compass_on = getattr(self.result, "compass_rose_on", False)
        if compass_on:
            axis_pairs = [
                ("Ascendant", "Descendant", "ACDC"),
                ("MC", "IC", "MCIC"),
                ("North Node", "South Node", "Nodes"),
            ]
            axis_texts = []
            for a, b, key in axis_pairs:
                if self._get_object_row(a) is not None and self._get_object_row(b) is not None:
                    axis_texts.append(self._interpret_axis_pair(a, b, key))
                    handled.add(frozenset([a, b]))
            if axis_texts:
                sections.append("## 🧭 Cardinal Axis Interpretations\n" + "\n\n".join(axis_texts))

        # aspects
        clusters, cluster_map, clustered_members = build_conjunction_clusters(
            self.ordered_df, self.drawn_major_edges
        )
        aspect_texts: List[str] = []
        for a, b, meta in self.drawn_major_edges:
            pair = frozenset([a, b])
            if pair not in handled and a not in clustered_members and b not in clustered_members:
                aspect_texts.append(self._interpret_aspect(a, b, meta))
        if aspect_texts:
            sections.append("## ✨ Major Aspects\n" + "\n\n".join(aspect_texts))

        # summary
        circuit = self._interpret_circuit(list(self.ordered_df["Object"]), [])
        sections.append("## 🌐 Whole Chart Summary\n" + circuit)

        return "\n\n".join(sections)


# expose for backwards compatibility
__all__ = ["ChartInterpreter"]
