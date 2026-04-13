"""
Data models for astrological chart calculations.
"""
import re
from dataclasses import dataclass
from typing import Optional
import pandas as pd

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
    def from_dict(cls, row: dict) -> "ChartObject":
        """Create ChartObject from a row dict (e.g. from calc_v2 or DataFrame)."""
        def _float(x, default=0.0):
            if x is None or (hasattr(x, "__float__") and str(x) == "nan"):
                return default
            try:
                return float(x)
            except (TypeError, ValueError):
                return default

        def _int_or_none(x):
            if x is None or (hasattr(x, "__float__") and str(x) == "nan"):
                return None
            try:
                return int(float(x))
            except (TypeError, ValueError):
                return None

        def _str(x, default=""):
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

    def to_dataframe(self) -> pd.DataFrame:
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
