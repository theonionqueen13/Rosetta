"""
Data models for astrological chart calculations.
"""
from dataclasses import dataclass, asdict
from typing import Optional
import pandas as pd


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

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility."""
        return {
            "Object": self.object_name,
            "Longitude": self.longitude,
            "Sign": self.sign,
            "DMS": self.dms,
            "Sabian Index": self.sabian_index,
            "Sabian Symbol": self.sabian_symbol,
            "Retrograde": self.retrograde,
            "OOB Status": self.oob_status,
            "Dignity": self.dignity,
            "Ruled by (sign)": self.ruled_by_sign,
            "Latitude": self.latitude,
            "Declination": self.declination,
            "Distance": self.distance,
            "Speed": self.speed,
        }


@dataclass
class HouseCusp:
    """Represents a house cusp in an astrological chart."""

    cusp_number: int
    absolute_degree: float
    house_system: str

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame compatibility."""
        return {
            "Object": f"{self.cusp_number}H Cusp",
            "Computed Absolute Degree": self.absolute_degree,
            "House System": self.house_system,
        }


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
        This maintains backward compatibility with the original function.
        """
        # Convert objects to dicts
        object_rows = [obj.to_dict() for obj in self.objects]
        cusp_rows = [cusp.to_dict() for cusp in self.house_cusps]

        # Create DataFrames
        base_df = pd.DataFrame(object_rows)
        cusp_df = pd.DataFrame(cusp_rows)

        # Concatenate
        return pd.concat([base_df, cusp_df], ignore_index=True)

    def get_object(self, name: str) -> Optional[ChartObject]:
        """Get a specific celestial object by name."""
        for obj in self.objects:
            if obj.object_name == name:
                return obj
        return None

    def get_planets(self) -> list[ChartObject]:
        """Get all traditional planets (Sun through Pluto)."""
        planet_names = [
            "Sun",
            "Moon",
            "Mercury",
            "Venus",
            "Mars",
            "Jupiter",
            "Saturn",
            "Uranus",
            "Neptune",
            "Pluto",
        ]
        return [obj for obj in self.objects if obj.object_name in planet_names]

    def get_angles(self) -> list[ChartObject]:
        """Get the chart angles (Ascendant, MC, Descendant, IC)."""
        angle_names = ["Ascendant", "MC", "Descendant", "IC"]
        return [obj for obj in self.objects if obj.object_name in angle_names]

    def get_asteroids(self) -> list[ChartObject]:
        """Get all asteroids in the chart."""
        asteroid_names = ["Chiron", "Ceres", "Pallas", "Juno", "Vesta", "Pholus", "Eris", "Eros", "Psyche"]
        return [obj for obj in self.objects if obj.object_name in asteroid_names]

    def get_retrograde_objects(self) -> list[ChartObject]:
        """Get all objects currently in retrograde motion."""
        return [obj for obj in self.objects if obj.retrograde == "Rx"]

    def get_out_of_bounds_objects(self) -> list[ChartObject]:
        """Get all objects currently out of bounds."""
        return [obj for obj in self.objects if obj.oob_status == "Yes"]
