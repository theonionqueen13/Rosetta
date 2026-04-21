"""
Backward-compatibility shim.

models_v2.py was split into two focused modules during Phase 2 refactor:

  src/core/static_models.py  – static lookup dataclasses + static_db singleton
  src/core/chart_models.py   – chart-runtime dataclasses (AstrologicalChart, etc.)

This file re-exports every public symbol from both modules so that all
existing ``from .models_v2 import …`` / ``from src.core.models_v2 import …``
call-sites continue to work without modification.

New code should import directly from the canonical modules.
"""
# ruff: noqa: F401 (unused imports — all intentional re-exports)

from .static_models import (
    # Static dataclasses
    Object,
    Element,
    Modality,
    Polarity,
    Sign,
    House,
    HouseSystem,
    Aspect,
    Axis,
    CompassAxis,
    FixedStar,
    SabianSymbol,
    Dignity,
    Shape,
    StaticLookup,
    ObjectSign,
    ObjectHouse,
    # Functions & singleton
    _init_static_db,
    load_static_lookup,
    static_db,
)

from .chart_models import (
    # Planetary strength
    EssentialDignity,
    PlanetaryState,
    ReceptionLink,
    # Detected shapes
    DetectedShape,
    # Circuit simulation
    CircuitNode,
    CircuitEdge,
    ShapeCircuit,
    CircuitSimulation,
    # Chart objects
    ChartObject,
    HouseCusp,
    # Top-level chart
    AstrologicalChart,
)
