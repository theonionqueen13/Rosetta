"""
Data models for astrological chart calculations.
"""
import re
import json
import math
import datetime
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd

# ---------------------------------------------------------------------------
# Planetary strength / dignity dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EssentialDignity:
    """Essential dignity breakdown for a planet at a specific sign/degree."""
    domicile: bool = False
    detriment: bool = False
    exaltation: bool = False
    fall: bool = False
    triplicity: bool = False
    term: bool = False
    face: bool = False
    peregrine: bool = False
    primary_dignity: str = ""


@dataclass
class PlanetaryState:
    """Combined essential + accidental dignity score for a chart object."""
    planet_name: str = ""
    essential_dignity: Optional[EssentialDignity] = None
    raw_authority: float = 0.0
    quality_index: float = 0.0
    house_score: float = 0.0
    motion_score: float = 0.0
    solar_proximity_score: float = 0.0
    solar_proximity_label: str = ""
    potency_score: float = 0.0
    power_index: float = 0.0
    motion_label: str = ""
    solar_distance: Optional[float] = None
    cluster_potency: float = 0.0


@dataclass
class ReceptionLink:
    """A single mutual-reception relationship between two chart objects."""
    other: Any = None   # ChartObject or compatible; has .name attribute
    aspect: Any = None  # Aspect object; has .name attribute
    mode: str = ""      # "orb" or "sign"


# ---------------------------------------------------------------------------
# Detected pattern shapes
# ---------------------------------------------------------------------------

@dataclass
class DetectedShape:
    """A single detected astrological pattern shape."""
    shape_type: str = ""
    shape_id: str = ""
    members: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    remainder: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "DetectedShape":
        """Create a DetectedShape from a raw pattern dict."""
        return cls(
            shape_type=d.get("type", ""),
            shape_id=str(d.get("id", "")),
            members=list(d.get("members", [])),
            edges=list(d.get("edges", [])),
            remainder=bool(d.get("remainder", False)),
        )


# ---------------------------------------------------------------------------
# Circuit simulation dataclasses
# ---------------------------------------------------------------------------

@dataclass
class CircuitNode:
    """A single planet/point node in the circuit power simulation."""
    planet_name: str = ""
    raw_authority: float = 0.0
    raw_potency: float = 0.0
    power_index: float = 0.0
    is_source: bool = False
    is_sink: bool = False
    is_mutual_reception: bool = False
    received_power: float = 0.0
    friction_load: float = 0.0
    effective_power: float = 0.0


@dataclass
class CircuitEdge:
    """An aspect edge in the circuit power simulation."""
    node_a: str = ""
    node_b: str = ""
    aspect_type: str = ""
    conductance: float = 0.0
    is_arc_hazard: bool = False
    is_rerouted: bool = False
    reroute_path: list = field(default_factory=list)
    is_open_arc: bool = False
    transmitted_power: float = 0.0
    friction_heat: float = 0.0


@dataclass
class ShapeCircuit:
    """Circuit simulation result for a single detected shape."""
    shape_type: str = ""
    shape_id: str = ""
    nodes: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    total_throughput: float = 0.0
    total_friction: float = 0.0
    dominant_node: str = ""
    bottleneck_node: str = ""
    resonance_score: float = 0.0
    friction_score: float = 0.0
    flow_characterization: str = ""
    membrane_class: str = ""
    quincunx_routes: list = field(default_factory=list)
    open_arcs: list = field(default_factory=list)


@dataclass
class CircuitSimulation:
    """Full circuit simulation result for a chart."""
    shape_circuits: list = field(default_factory=list)
    node_map: dict = field(default_factory=dict)
    sn_nn_path: list = field(default_factory=list)
    singletons: list = field(default_factory=list)
    mutual_receptions: list = field(default_factory=list)


# System labels must match drawing_v2/system_map and dispositor lookup
_SYSTEM_LABEL_MAP = {
    "placidus": "Placidus",
    "equal": "Equal",
    "whole": "Whole Sign",
}

# Object name alias groups for get_object (any name in group matches any other)
_OBJECT_ALIAS_GROUPS = [
    {"Ascendant", "AC", "Asc"},
    {"Descendant", "DC", "Dsc"},
]


@dataclass
class ChartObject:
    """Represents a celestial object or chart point in an astrological chart."""

    object_name: str
    longitude: float
    sign: str
    dms: str
    sabian_index: int
    sabian_symbol: str
    retrograde: str
    oob_status: str
    dignity: dict | str
    ruled_by_sign: str
    latitude: float
    declination: float
    distance: float
    speed: float
    # Optional fields for consumer compatibility
    glyph: str = ""
    reception: str = ""
    retrograde_bool: bool = False
    fixed_star_conj: str = ""
    sign_index: Optional[int] = None
    degree_in_sign: Optional[int] = None
    minute_in_sign: Optional[int] = None
    second_in_sign: Optional[int] = None
    # Per-system house placements (None if not computed)
    placidus_house: Optional[int] = None
    placidus_house_rulers: Optional[str] = None
    equal_house: Optional[int] = None
    equal_house_rulers: Optional[str] = None
    whole_sign_house: Optional[int] = None
    whole_sign_house_rulers: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility.
        Emits all columns consumers expect (profiles_v2, drawing_v2, dispositor_graph).
        """
        return {
            "Glyph": self.glyph,
            "Object": self.object_name,
            "Dignity": self.dignity,
            "Reception": self.reception,
            "Ruled by (sign)": self.ruled_by_sign,
            "Longitude": round(self.longitude, 6),
            "Sign": self.sign,
            "Sign Index": self.sign_index,
            "Degree In Sign": self.degree_in_sign,
            "Minute In Sign": self.minute_in_sign,
            "Second In Sign": self.second_in_sign,
            "DMS": self.dms,
            "Sabian Index": self.sabian_index,
            "Sabian Symbol": self.sabian_symbol,
            "Fixed Star Conj": self.fixed_star_conj,
            "Retrograde Bool": self.retrograde_bool,
            "Retrograde": self.retrograde,
            "OOB Status": self.oob_status,
            "Latitude": round(self.latitude, 6),
            "Declination": round(self.declination, 6),
            "Distance": round(self.distance, 6),
            "Speed": round(self.speed, 6),
            "Placidus House": self.placidus_house,
            "Placidus House Rulers": self.placidus_house_rulers,
            "Equal House": self.equal_house,
            "Equal House Rulers": self.equal_house_rulers,
            "Whole Sign House": self.whole_sign_house,
            "Whole Sign House Rulers": self.whole_sign_house_rulers,
        }

    @classmethod
    def from_dict(cls, row: dict, static=None) -> "ChartObject":
        """Create ChartObject from a row dict (e.g. from calc_v2 or DataFrame).
        The *static* argument is accepted for backward compatibility but ignored.
        """
        def _float(x, default=0.0):
            """Safely convert *x* to float, returning *default* for None or NaN."""
            if x is None or (hasattr(x, "__float__") and str(x) == "nan"):
                return default
            try:
                return float(x)
            except (TypeError, ValueError):
                return default

        def _int_or_none(x):
            """Safely convert *x* to int, returning None for None or NaN."""
            if x is None or (hasattr(x, "__float__") and str(x) == "nan"):
                return None
            try:
                return int(float(x))
            except (TypeError, ValueError):
                return None

        def _str(x, default=""):
            """Safely convert *x* to a stripped string, returning *default* for None or NaN."""
            if x is None or (hasattr(x, "__float__") and str(x) == "nan"):
                return default
            return str(x).strip()

        name = _str(row.get("Object"))
        lon = _float(row.get("Longitude"))
        sign = _str(row.get("Sign"))
        dms = _str(row.get("DMS"))
        sabian_idx = _int_or_none(row.get("Sabian Index")) or 0
        sabian_sym = _str(row.get("Sabian Symbol"))
        retro = _str(row.get("Retrograde"))
        oob = _str(row.get("OOB Status"))
        dignity = row.get("Dignity")
        if dignity is not None and hasattr(dignity, "__float__") and str(dignity) == "nan":
            dignity = None
        ruled = _str(row.get("Ruled by (sign)"))
        lat = _float(row.get("Latitude"))
        decl = _float(row.get("Declination"))
        dist = _float(row.get("Distance"))
        spd = _float(row.get("Speed"))

        glyph = _str(row.get("Glyph"))
        reception = _str(row.get("Reception"))
        retro_bool = bool(row.get("Retrograde Bool", False))
        if isinstance(retro_bool, str):
            retro_bool = retro_bool.lower() in ("true", "1", "yes", "rx")
        fixed_star = _str(row.get("Fixed Star Conj"))
        sign_idx = _int_or_none(row.get("Sign Index"))
        deg_in_sign = _int_or_none(row.get("Degree In Sign"))
        min_in_sign = _int_or_none(row.get("Minute In Sign"))
        sec_in_sign = _int_or_none(row.get("Second In Sign"))

        p_house = _int_or_none(row.get("Placidus House"))
        p_rulers = row.get("Placidus House Rulers")
        e_house = _int_or_none(row.get("Equal House"))
        e_rulers = row.get("Equal House Rulers")
        w_house = _int_or_none(row.get("Whole Sign House"))
        w_rulers = row.get("Whole Sign House Rulers")
        if p_rulers is not None and not (hasattr(p_rulers, "__float__") and str(p_rulers) == "nan"):
            p_rulers = str(p_rulers).strip()
        else:
            p_rulers = None
        if e_rulers is not None and not (hasattr(e_rulers, "__float__") and str(e_rulers) == "nan"):
            e_rulers = str(e_rulers).strip()
        else:
            e_rulers = None
        if w_rulers is not None and not (hasattr(w_rulers, "__float__") and str(w_rulers) == "nan"):
            w_rulers = str(w_rulers).strip()
        else:
            w_rulers = None

        return cls(
            object_name=name,
            longitude=lon,
            sign=sign,
            dms=dms,
            sabian_index=sabian_idx,
            sabian_symbol=sabian_sym,
            retrograde=retro,
            oob_status=oob,
            dignity=dignity,
            ruled_by_sign=ruled,
            latitude=lat,
            declination=decl,
            distance=dist,
            speed=spd,
            glyph=glyph,
            reception=reception,
            retrograde_bool=retro_bool,
            fixed_star_conj=fixed_star,
            sign_index=sign_idx,
            degree_in_sign=deg_in_sign,
            minute_in_sign=min_in_sign,
            second_in_sign=sec_in_sign,
            placidus_house=p_house,
            placidus_house_rulers=p_rulers,
            equal_house=e_house,
            equal_house_rulers=e_rulers,
            whole_sign_house=w_house,
            whole_sign_house_rulers=w_rulers,
        )


@dataclass
class HouseCusp:
    """Represents a house cusp in an astrological chart."""

    cusp_number: int
    absolute_degree: float
    house_system: str

    def to_json(self) -> dict:
        """Serialise to a plain JSON-safe dict."""
        return {
            "cusp_number": self.cusp_number,
            "absolute_degree": self.absolute_degree,
            "house_system": self.house_system,
        }

    @classmethod
    def from_json(cls, d: dict) -> "HouseCusp":
        """Reconstruct from a dict produced by to_json()."""
        return cls(
            cusp_number=int(d["cusp_number"]),
            absolute_degree=float(d["absolute_degree"]),
            house_system=str(d["house_system"]),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility.
        Output schema matches drawing_v2 and dispositor lookup:
        - Object: '<System Label> <n>H cusp' (e.g. 'Placidus 1H cusp')
        - Longitude: absolute degree (not 'Computed Absolute Degree')
        """
        sys_lower = str(self.house_system).strip().lower()
        label = _SYSTEM_LABEL_MAP.get(sys_lower, "Placidus")
        return {
            "Object": f"{label} {self.cusp_number}H cusp",
            "Longitude": round(self.absolute_degree % 360.0, 6),
        }

    @classmethod
    def from_dict(cls, row: dict) -> "HouseCusp":
        """Create HouseCusp from a row dict."""
        obj = str(row.get("Object", "")).strip()
        lon = row.get("Longitude") or row.get("Computed Absolute Degree", 0.0)
        lon = float(lon)
        m = re.match(r"^\s*(?:Placidus|Equal|Whole\s*Sign)\s*(\d+)\s*H\s*cusp", obj, re.I)
        num = int(m.group(1)) if m else 1
        if "Placidus" in obj:
            sys_key = "placidus"
        elif "Equal" in obj:
            sys_key = "equal"
        elif "Whole" in obj:
            sys_key = "whole"
        else:
            sys_key = row.get("House System", "placidus")
        return cls(cusp_number=num, absolute_degree=lon, house_system=sys_key)


def _object_names_from_lookup() -> tuple[list[str], list[str], list[str]]:
    """Derive planet/angle/asteroid names from lookup_v2.ALL_MAJOR_PLACEMENTS.
    
    Note: all_names below is currently unused; placements are hardcoded to maintain
    explicit categorization (planets, angles, asteroids).
    """
    try:
        from .models_v2 import static_db
        all_names = list(static_db.ALL_MAJOR_PLACEMENTS.keys())
    except ImportError:
        all_names = []
    planets = [
        "Sun", "Moon", "Mercury", "Venus", "Mars",
        "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto",
    ]
    angles = ["Ascendant", "MC", "Descendant", "IC", "AC", "DC"]
    asteroids = ["Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Pholus", "Eris", "Eros", "Psyche"]
    return planets, angles, asteroids


@dataclass
class AstrologicalChart:
    """Complete astrological chart with all celestial objects and house cusps."""

    objects: list[ChartObject]
    house_cusps: list[HouseCusp]
    chart_datetime: str
    timezone: str
    latitude: float
    longitude: float
    # Header/display metadata
    display_name: str = field(default="")
    city: str = field(default="")
    unknown_time: bool = field(default=False)
    display_datetime: Optional[datetime.datetime] = field(default=None)
    # Computed chart data attached by chart_adapter / calc_v2
    df_positions: Optional[Any] = field(default=None)
    aspect_df: Optional[Any] = field(default=None)
    edges_major: list = field(default_factory=list)
    edges_minor: list = field(default_factory=list)
    edges_harmonic: list = field(default_factory=list)
    aspect_groups: list = field(default_factory=list)
    shapes: list = field(default_factory=list)
    filaments: list = field(default_factory=list)
    singleton_map: dict = field(default_factory=dict)
    combos: list = field(default_factory=list)
    positions: dict = field(default_factory=dict)
    major_edges_all: list = field(default_factory=list)
    dispositor_summary_rows: list = field(default_factory=list)
    dispositor_chains_rows: list = field(default_factory=list)
    conj_clusters_rows: list = field(default_factory=list)
    sect: Optional[str] = field(default=None)
    sect_error: Optional[str] = field(default=None)
    plot_data: Any = field(default=None)
    utc_datetime: Optional[datetime.datetime] = field(default=None)
    planetary_states: dict = field(default_factory=dict)
    mutual_receptions: list = field(default_factory=list)
    circuit_simulation: Optional[Any] = field(default=None)
    circuit_names: dict = field(default_factory=dict)
    group_id: Optional[str] = field(default=None)
    chart_signs: list = field(default_factory=list)
    chart_houses: list = field(default_factory=list)

    def __getattr__(self, name: str):
        """Gracefully return None for fields added after this instance was created."""
        return None

    def header_lines(self) -> tuple[str, str, str, str, str]:
        """Return 5 display strings: (name, date_line, time_line, city, extra_line).

        Used by drawing_v2, chart_serializer, tab_rulers, etc.
        """
        name = self.display_name or ""
        # Try to format date/time from chart_datetime
        date_line = ""
        time_line = ""
        raw_dt = self.chart_datetime or ""
        try:
            import datetime as _dt
            dt = _dt.datetime.fromisoformat(raw_dt)
            date_line = dt.strftime("%B %d, %Y").replace(" 0", " ")
            if not self.unknown_time:
                time_line = dt.strftime("%I:%M %p").lstrip("0")
            else:
                time_line = "Time Unknown"
        except Exception:
            date_line = raw_dt[:10] if raw_dt else ""
            time_line = raw_dt[11:16] if len(raw_dt) > 10 else ""
        city = self.city or ""
        extra_line = "Unknown Time" if self.unknown_time else ""
        return (name, date_line, time_line, city, extra_line)


        """
        Convert the chart to a pandas DataFrame.
        Schema matches calc_v2 output for backward compatibility.
        Object rows and cusp rows have different column sets; concat produces NaN for missing cols.
        """
        object_rows = [obj.to_dict() for obj in self.objects]
        cusp_rows = [cusp.to_dict() for cusp in self.house_cusps]

        base_df = pd.DataFrame(object_rows)
        cusp_df = pd.DataFrame(cusp_rows)
        return pd.concat([base_df, cusp_df], ignore_index=True)

    def to_json(self) -> Dict[str, Any]:
        """Serialise the chart to a JSON-safe dict for state storage.

        Heavy computed fields (planetary_states, circuit_simulation,
        mutual_receptions) are omitted — they are recomputed on demand.
        """
        def _native(obj):
            """Recursively convert numpy/pandas scalars to plain Python types."""
            try:
                import numpy as np
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.floating):
                    v = float(obj)
                    return None if math.isnan(v) or math.isinf(v) else v
                if isinstance(obj, np.ndarray):
                    return [_native(x) for x in obj.tolist()]
                if isinstance(obj, np.bool_):
                    return bool(obj)
            except ImportError:
                pass
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
            if isinstance(obj, dict):
                return {k: _native(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple, set, frozenset)):
                return [_native(x) for x in obj]
            return obj

        def _safe_list(lst):
            try:
                native = _native(list(lst or []))
                json.dumps(native)
                return native
            except (TypeError, ValueError):
                return []

        def _edge_list(edges):
            out = []
            for edge in (edges or []):
                try:
                    a, b, meta = edge
                    safe_meta = _native(meta) if isinstance(meta, dict) else {}
                    out.append([str(a), str(b), safe_meta])
                except Exception:
                    pass
            return out

        def _major_edges_all(edges):
            out = []
            for edge in (edges or []):
                try:
                    (a, b), asp = edge
                    out.append([[str(a), str(b)], str(asp)])
                except Exception:
                    pass
            return out

        def _df_to_records(df):
            if df is None:
                return None
            try:
                return json.loads(df.to_json(orient="records", default_handler=str))
            except Exception:
                return None

        # Serialize shapes — accept both DetectedShape objects and raw dicts
        def _shape_list(shapes):
            out = []
            for s in (shapes or []):
                if isinstance(s, dict):
                    out.append(_native(s))
                elif hasattr(s, "to_dict"):
                    out.append(s.to_dict())
            return out

        result = {
            "display_name": self.display_name or "",
            "city": self.city or "",
            "chart_datetime": self.chart_datetime,
            "timezone": self.timezone,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "unknown_time": bool(self.unknown_time),
            "sect": self.sect,
            "sect_error": self.sect_error,
            "display_datetime": self.display_datetime.isoformat() if self.display_datetime else None,
            "utc_datetime": self.utc_datetime.isoformat() if self.utc_datetime else None,
            "objects": [obj.to_dict() for obj in (self.objects or [])],
            "house_cusps": [c.to_json() for c in (self.house_cusps or [])],
            "df_positions": _df_to_records(self.df_positions),
            "aspect_df": _df_to_records(self.aspect_df),
            "edges_major": _edge_list(self.edges_major),
            "edges_minor": _edge_list(self.edges_minor),
            "edges_harmonic": _edge_list(self.edges_harmonic),
            "major_edges_all": _major_edges_all(self.major_edges_all),
            "aspect_groups": [list(g) for g in (self.aspect_groups or [])],
            "shapes": _shape_list(self.shapes),
            "singleton_map": _native(self.singleton_map or {}),
            "positions": _native(self.positions or {}),
            "filaments": _safe_list(self.filaments or []),
            "combos": _safe_list(self.combos or []),
            "dispositor_summary_rows": _safe_list(self.dispositor_summary_rows or []),
            "dispositor_chains_rows": _safe_list(self.dispositor_chains_rows or []),
            "conj_clusters_rows": _safe_list(self.conj_clusters_rows or []),
            "circuit_names": _native(self.circuit_names or {}),
            "group_id": self.group_id,
        }
        return _native(result)

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "AstrologicalChart":
        """Reconstruct an AstrologicalChart from a dict produced by to_json().

        planetary_states and circuit_simulation are not restored;
        they are recomputed by the caller when needed.
        """
        def _parse_dt(s):
            if not s:
                return None
            try:
                return datetime.datetime.fromisoformat(s)
            except (ValueError, TypeError):
                return None

        def _df(records):
            if not records:
                return None
            try:
                return pd.DataFrame(records)
            except Exception:
                return None

        def _edge_list(raw):
            out = []
            for row in (raw or []):
                try:
                    out.append((row[0], row[1], row[2]))
                except Exception:
                    pass
            return out

        def _major_edges_all(raw):
            out = []
            for row in (raw or []):
                try:
                    (a, b), asp = row[0], row[1]
                    out.append(((a, b), asp))
                except Exception:
                    pass
            return out

        objects = [ChartObject.from_dict(row) for row in (d.get("objects") or [])]
        house_cusps = [
            HouseCusp.from_json(c) for c in (d.get("house_cusps") or [])
        ]

        # shapes may be DetectedShape-friendly dicts
        shapes = d.get("shapes") or []

        return cls(
            objects=objects,
            house_cusps=house_cusps,
            chart_datetime=d.get("chart_datetime", ""),
            timezone=d.get("timezone", ""),
            latitude=float(d.get("latitude") or 0.0),
            longitude=float(d.get("longitude") or 0.0),
            display_name=d.get("display_name", ""),
            city=d.get("city", ""),
            unknown_time=bool(d.get("unknown_time", False)),
            display_datetime=_parse_dt(d.get("display_datetime")),
            sect=d.get("sect"),
            sect_error=d.get("sect_error"),
            df_positions=_df(d.get("df_positions")),
            aspect_df=_df(d.get("aspect_df")),
            edges_major=_edge_list(d.get("edges_major")),
            edges_minor=_edge_list(d.get("edges_minor")),
            edges_harmonic=_edge_list(d.get("edges_harmonic")),
            major_edges_all=_major_edges_all(d.get("major_edges_all")),
            aspect_groups=[list(g) for g in (d.get("aspect_groups") or [])],
            shapes=shapes,
            singleton_map=d.get("singleton_map") or {},
            positions=d.get("positions") or {},
            filaments=d.get("filaments") or [],
            combos=d.get("combos") or [],
            dispositor_summary_rows=d.get("dispositor_summary_rows") or [],
            dispositor_chains_rows=d.get("dispositor_chains_rows") or [],
            conj_clusters_rows=d.get("conj_clusters_rows") or [],
            utc_datetime=_parse_dt(d.get("utc_datetime")),
            circuit_names=d.get("circuit_names") or {},
            group_id=d.get("group_id"),
        )

    def populate_chart_structure(self, static=None, house_system: str = "placidus") -> None:
        """Populate chart_signs and chart_houses from chart objects.

        This is a stub — the heavy work requires full static_models lookup.
        Currently sets empty lists to avoid AttributeError in callers.
        """
        # chart_signs and chart_houses are already initialised as empty lists
        # by the dataclass field defaults. Full population would require
        # building ChartSign/ChartHouse objects from static_db, which is
        # handled by calc_v2 directly on the live AstrologicalChart.
        pass

    def get_object(self, name: str) -> Optional[ChartObject]:
        """Get a specific celestial object by name. Handles aliases (AC/Ascendant, DC/Descendant)."""
        name = (name or "").strip()
        for obj in self.objects:
            if obj.object_name == name:
                return obj
        for group in _OBJECT_ALIAS_GROUPS:
            if name in group:
                for obj in self.objects:
                    if obj.object_name in group:
                        return obj
                break
        return None

    def get_planets(self) -> list[ChartObject]:
        """Get all traditional planets (Sun through Pluto)."""
        planets, _, _ = _object_names_from_lookup()
        return [obj for obj in self.objects if obj.object_name in planets]

    def get_angles(self) -> list[ChartObject]:
        """Get the chart angles (Ascendant, MC, Descendant, IC)."""
        _, angles, _ = _object_names_from_lookup()
        return [obj for obj in self.objects if obj.object_name in angles]

    def get_asteroids(self) -> list[ChartObject]:
        """Get all asteroids in the chart."""
        _, _, asteroids = _object_names_from_lookup()
        return [obj for obj in self.objects if obj.object_name in asteroids]

    def get_retrograde_objects(self) -> list[ChartObject]:
        """Get all objects currently in retrograde motion."""
        return [obj for obj in self.objects if obj.retrograde == "Rx"]

    def get_out_of_bounds_objects(self) -> list[ChartObject]:
        """Get all objects currently out of bounds."""
        return [obj for obj in self.objects if obj.oob_status == "Yes"]

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame, chart_datetime: str = "", timezone: str = "",
                       latitude: float = 0.0, longitude: float = 0.0) -> "AstrologicalChart":
        """
        Create AstrologicalChart from a DataFrame (e.g. from calc_v2 output).
        Splits object rows (no 'cusp' in Object) from cusp rows.
        """
        if df is None or df.empty:
            return cls(
                objects=[],
                house_cusps=[],
                chart_datetime=chart_datetime,
                timezone=timezone,
                latitude=latitude,
                longitude=longitude,
            )
        obj_mask = ~df["Object"].astype(str).str.contains("cusp", case=False, na=False)
        obj_df = df.loc[obj_mask]
        cusp_df = df.loc[~obj_mask]

        objects = [ChartObject.from_dict(row) for _, row in obj_df.iterrows()]
        house_cusps = [HouseCusp.from_dict(row) for _, row in cusp_df.iterrows()]

        return cls(
            objects=objects,
            house_cusps=house_cusps,
            chart_datetime=chart_datetime,
            timezone=timezone,
            latitude=latitude,
            longitude=longitude,
        )
