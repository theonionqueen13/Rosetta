import re
import pandas as pd
from typing import Any, Collection, Iterable, Mapping, Sequence, List, Dict
from lookup_v2 import ASPECTS, LUMINARIES_AND_PLANETS


_CANON_RE = re.compile(r"[^a-z0-9]+")

def _canonical_name(name: Any) -> str:
	if name is None:
		return ""
	return _CANON_RE.sub("", str(name).lower())

_ALIAS_GROUPS = [
	{"ac", "ascendant"},
	{"dc", "descendant"},
	{"mc", "midheaven"},
	{"ic", "imumcoeli"},
	{"northnode", "truenode"},
	{"southnode"},
	{"partoffortune", "pof"},
	{"blackmoonlilithmean", "blackmoonlilith", "lilith"},
]

_ALIAS_LOOKUP: dict[str, set[str]] = {}
for group in _ALIAS_GROUPS:
	canon_group = {_canonical_name(name) for name in group}
	for entry in canon_group:
		_ALIAS_LOOKUP[entry] = canon_group

_COMPASS_ALIAS_MAP: dict[str, list[str]] = {
	"Ascendant": ["AC", "Ascendant"],
	"Descendant": ["DC", "Descendant"],
	"MC": ["MC", "Midheaven"],
	"IC": ["IC", "Imum Coeli"],
	"North Node": ["North Node", "True Node"],
	"South Node": ["South Node"],
}
def _is_luminary_or_planet(name: str) -> bool:
	return _canonical_name(name) in LUMINARIES_AND_PLANETS

def _in_forward_arc(start_deg, end_deg, x_deg):
	"""True if x lies on the forward arc from start->end (mod 360)."""
	span = (end_deg - start_deg) % 360.0
	off  = (x_deg   - start_deg) % 360.0
	return off < span if span != 0 else off == 0

def _house_of_degree(deg, cusps):
	"""Given a degree and a 12-length cusp list (House 1..12), return 1..12."""
	if not cusps or len(cusps) != 12:
		return None
	for i in range(12):
		a = cusps[i]
		b = cusps[(i + 1) % 12]
		if _in_forward_arc(a, b, deg):
			return i + 1
	return 12

def _degree_for_label(pos: Mapping[str, float] | None, name: str) -> float | None:
	if not pos:
		return None
	value = pos.get(name)
	if value is not None:
		try:
			return float(value) % 360.0
		except Exception:
			return None
	canon = _canonical_name(name)
	aliases = _ALIAS_LOOKUP.get(canon, {canon})
	for key, val in pos.items():
		if val is None:
			continue
		try:
			deg = float(val) % 360.0
		except Exception:
			continue
		if _canonical_name(key) in aliases:
			return deg
	return None

def _expand_visible_canon(names: Collection[str] | None) -> set[str] | None:
	if not names:
		return None
	expanded: set[str] = set()
	for name in names:
		canon = _canonical_name(name)
		expanded.update(_ALIAS_LOOKUP.get(canon, {canon}))
	return expanded

def _object_rows(df: pd.DataFrame) -> pd.DataFrame:
	if df is None or "Object" not in df:
		return pd.DataFrame(columns=["Object", "Longitude"])
	obj_series = df["Object"].astype("string")
	mask = ~obj_series.str.contains("cusp", case=False, na=False)
	return df.loc[mask].copy()

def _canonical_series(df: pd.DataFrame) -> pd.Series:
	obj_series = df["Object"].astype("string")
	return obj_series.map(_canonical_name)

def _find_row(df: pd.DataFrame, names: Iterable[str]) -> pd.Series | None:
	if df is None or "Object" not in df:
		return None
	canon_series = _canonical_series(df)
	for candidate in names:
		canon = _canonical_name(candidate)
		target = _ALIAS_LOOKUP.get(canon, {canon})
		mask = canon_series.isin(target)
		if mask.any():
			return df.loc[mask].iloc[0]
	return None

def get_ascendant_degree(df: pd.DataFrame) -> float:
	row = _find_row(df, ["AC", "Ascendant", "Asc"])
	if row is None:
		return 0.0
	try:
		return float(row.get("Longitude", 0.0))
	except Exception:
		return 0.0
	
def extract_positions(df: pd.DataFrame, visible_names: Collection[str] | None = None) -> dict[str, float]:
	objs = _object_rows(df)
	if objs.empty:
		return {}
	visible_canon = _expand_visible_canon(visible_names)
	canon_series = _canonical_series(objs)
	positions: dict[str, float] = {}
	for (_, row), canon in zip(objs.iterrows(), canon_series):
		if visible_canon is not None and canon not in visible_canon:
			continue
		lon = row.get("Longitude")
		if lon is None or (pd.isna(lon) if pd is not None else False):
			continue
		positions[str(row.get("Object"))] = float(lon)
	return positions

def extract_compass_positions(
	df: pd.DataFrame,
	visible_names: Collection[str] | None = None,
) -> dict[str, float]:
	visible_canon = _expand_visible_canon(visible_names)
	out: dict[str, float] = {}
	for label, names in _COMPASS_ALIAS_MAP.items():
		row = _find_row(df, names)
		if row is None:
			continue
		target_group: set[str] = set()
		for n in names:
			target_group.update(_ALIAS_LOOKUP.get(_canonical_name(n), {_canonical_name(n)}))
		if visible_canon is not None and target_group.isdisjoint(visible_canon):
			continue
		lon = row.get("Longitude")
		if lon is None or (pd.isna(lon) if pd is not None else False):
			continue
		out[label] = float(lon)
	return out

def _normalise_aspect(aspect: Any) -> tuple[str, bool]:
	"""Return (clean_name, is_approx) for an aspect label."""

	if aspect is None:
		return "", False
	name = str(aspect).strip()
	if not name:
		return "", False
	approx = False
	if name.endswith("_approx"):
		approx = True
		name = name[:-7]
	return name, approx

def _resolve_aspect(aspect: Any) -> tuple[str, bool, Mapping[str, Any]]:
	"""Return (canon_name, is_approx, spec) with case-insensitive lookup."""
	name, approx = _normalise_aspect(aspect)
	if not name:
		return "", approx, {}
	# case-insensitive match against ASPECTS keys
	for k in ASPECTS.keys():
		if k.lower() == name.lower():
			return k, approx, ASPECTS[k]
	return name, approx, {}  # unknown aspect -> empty spec

def _edge_record_to_components(record: Any):
	if isinstance(record, (list, tuple)):
		if len(record) == 3:
			a, b, meta = record
			aspect = meta.get("aspect") if isinstance(meta, Mapping) else meta
			return str(a), str(b), aspect
		if len(record) == 2:
			(a, b), meta = record
			aspect = meta.get("aspect") if isinstance(meta, Mapping) else meta
			return str(a), str(b), aspect
	return None, None, None