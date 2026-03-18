# src/toggle_state.py
"""
Unified Toggle State Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Consolidates all chart toggle states into a single session_state key to prevent
resets when switching between Interactive and non-Interactive chart modes.

All toggle values are stored in st.session_state["_toggle_state"] as a dict.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
import streamlit as st


# The single session key that holds all toggle state
_TOGGLE_STATE_KEY = "_toggle_state"


@dataclass
class ToggleStateSnapshot:
    """Immutable snapshot of current toggle states for rendering."""
    patterns: Dict[int, bool] = field(default_factory=dict)        # circuit toggles
    shapes: Dict[str, bool] = field(default_factory=dict)          # shape toggles (key: f"{parent}_{shape_id}")
    singletons: Dict[str, bool] = field(default_factory=dict)      # singleton toggles
    compass_inner: bool = True                                      # main compass rose
    compass_outer: bool = True                                      # biwheel outer compass
    chart_mode: str = "Circuits"                                    # "Standard Chart" or "Circuits"
    circuit_submode: str = "Combined Circuits"                      # "Combined Circuits", "Connected Circuits", or "single"
    aspect_toggles: Dict[str, bool] = field(default_factory=dict)  # Additional aspect body toggles
    synastry_aspects_inter: bool = True                             # Inter-chart aspects toggle
    synastry_aspects_chart1: bool = False                           # Chart 1 internal aspects
    synastry_aspects_chart2: bool = False                           # Chart 2 internal aspects
    cc_shapes: Dict[str, bool] = field(default_factory=dict)       # Connected Circuits Chart 2 shapes
    label_style: str = "glyph"                                      # "glyph" or "text"
    dark_mode: bool = False
    interactive_chart: bool = False


def _get_state() -> Dict[str, Any]:
    """Get or initialize the toggle state dict."""
    if _TOGGLE_STATE_KEY not in st.session_state:
        st.session_state[_TOGGLE_STATE_KEY] = {
            "patterns": {},
            "shapes": {},
            "singletons": {},
            "compass_inner": True,
            "compass_outer": True,
            "chart_mode": "Circuits",
            "circuit_submode": "Combined Circuits",
            "aspect_toggles": {},
            "synastry_aspects_inter": True,
            "synastry_aspects_chart1": False,
            "synastry_aspects_chart2": False,
            "cc_shapes": {},
            "label_style": "glyph",
            "dark_mode": False,
            "interactive_chart": False,
            "circuit_names": {},
        }
    return st.session_state[_TOGGLE_STATE_KEY]


def get_snapshot() -> ToggleStateSnapshot:
    """Get an immutable snapshot of the current toggle state."""
    s = _get_state()
    return ToggleStateSnapshot(
        patterns=dict(s.get("patterns", {})),
        shapes=dict(s.get("shapes", {})),
        singletons=dict(s.get("singletons", {})),
        compass_inner=s.get("compass_inner", True),
        compass_outer=s.get("compass_outer", True),
        chart_mode=s.get("chart_mode", "Circuits"),
        circuit_submode=s.get("circuit_submode", "Combined Circuits"),
        aspect_toggles=dict(s.get("aspect_toggles", {})),
        synastry_aspects_inter=s.get("synastry_aspects_inter", True),
        synastry_aspects_chart1=s.get("synastry_aspects_chart1", False),
        synastry_aspects_chart2=s.get("synastry_aspects_chart2", False),
        cc_shapes=dict(s.get("cc_shapes", {})),
        label_style=s.get("label_style", "glyph"),
        dark_mode=s.get("dark_mode", False),
        interactive_chart=s.get("interactive_chart", False),
    )


# ---------------------------------------------------------------------------
# Individual toggle accessors (fast path with no allocation)
# ---------------------------------------------------------------------------

def get_pattern_toggle(idx: int) -> bool:
    """Get circuit toggle state for pattern index."""
    return _get_state().get("patterns", {}).get(idx, False)


def set_pattern_toggle(idx: int, value: bool):
    """Set circuit toggle state for pattern index."""
    _get_state().setdefault("patterns", {})[idx] = value


def get_shape_toggle(parent: int, shape_id: str) -> bool:
    """Get shape toggle state."""
    key = f"{parent}_{shape_id}"
    return _get_state().get("shapes", {}).get(key, False)


def set_shape_toggle(parent: int, shape_id: str, value: bool):
    """Set shape toggle state."""
    key = f"{parent}_{shape_id}"
    _get_state().setdefault("shapes", {})[key] = value


def get_singleton_toggle(planet: str) -> bool:
    """Get singleton toggle state."""
    return _get_state().get("singletons", {}).get(planet, False)


def set_singleton_toggle(planet: str, value: bool):
    """Set singleton toggle state."""
    _get_state().setdefault("singletons", {})[planet] = value


def get_compass_inner() -> bool:
    """Get inner chart compass rose toggle."""
    return _get_state().get("compass_inner", True)


def set_compass_inner(value: bool):
    """Set inner chart compass rose toggle."""
    _get_state()["compass_inner"] = value


def get_compass_outer() -> bool:
    """Get outer chart compass rose toggle (biwheel)."""
    return _get_state().get("compass_outer", True)


def set_compass_outer(value: bool):
    """Set outer chart compass rose toggle (biwheel)."""
    _get_state()["compass_outer"] = value


def get_chart_mode() -> str:
    """Get chart mode ("Standard Chart" or "Circuits")."""
    return _get_state().get("chart_mode", "Circuits")


def set_chart_mode(value: str):
    """Set chart mode."""
    _get_state()["chart_mode"] = value


def get_circuit_submode() -> str:
    """Get circuit submode ("Combined Circuits", "Connected Circuits", or "single")."""
    return _get_state().get("circuit_submode", "Combined Circuits")


def set_circuit_submode(value: str):
    """Set circuit submode."""
    _get_state()["circuit_submode"] = value


def get_aspect_toggle(body_name: str) -> bool:
    """Get additional aspect body toggle."""
    return _get_state().get("aspect_toggles", {}).get(body_name, False)


def set_aspect_toggle(body_name: str, value: bool):
    """Set additional aspect body toggle."""
    _get_state().setdefault("aspect_toggles", {})[body_name] = value


def get_synastry_aspects_inter() -> bool:
    """Get inter-chart aspects toggle."""
    return _get_state().get("synastry_aspects_inter", True)


def set_synastry_aspects_inter(value: bool):
    """Set inter-chart aspects toggle."""
    _get_state()["synastry_aspects_inter"] = value


def get_synastry_aspects_chart1() -> bool:
    """Get Chart 1 internal aspects toggle."""
    return _get_state().get("synastry_aspects_chart1", False)


def set_synastry_aspects_chart1(value: bool):
    """Set Chart 1 internal aspects toggle."""
    _get_state()["synastry_aspects_chart1"] = value


def get_synastry_aspects_chart2() -> bool:
    """Get Chart 2 internal aspects toggle."""
    return _get_state().get("synastry_aspects_chart2", False)


def set_synastry_aspects_chart2(value: bool):
    """Set Chart 2 internal aspects toggle."""
    _get_state()["synastry_aspects_chart2"] = value


def get_cc_shape_toggle(circuit_idx: int, shape_id: str) -> bool:
    """Get Connected Circuits Chart 2 shape toggle."""
    key = f"{circuit_idx}_{shape_id}"
    return _get_state().get("cc_shapes", {}).get(key, False)


def set_cc_shape_toggle(circuit_idx: int, shape_id: str, value: bool):
    """Set Connected Circuits Chart 2 shape toggle."""
    key = f"{circuit_idx}_{shape_id}"
    _get_state().setdefault("cc_shapes", {})[key] = value


def get_label_style() -> str:
    """Get label style ("glyph" or "text")."""
    return _get_state().get("label_style", "glyph")


def set_label_style(value: str):
    """Set label style."""
    _get_state()["label_style"] = value.lower()


def get_dark_mode() -> bool:
    """Get dark mode state."""
    return _get_state().get("dark_mode", False)


def set_dark_mode(value: bool):
    """Set dark mode state."""
    _get_state()["dark_mode"] = value


def get_interactive_chart() -> bool:
    """Get interactive chart mode state."""
    return _get_state().get("interactive_chart", False)


def set_interactive_chart(value: bool):
    """Set interactive chart mode state."""
    _get_state()["interactive_chart"] = value


def get_circuit_name(idx: int) -> str:
    """Get circuit name for pattern index."""
    return _get_state().get("circuit_names", {}).get(idx, f"Circuit {idx + 1}")


def set_circuit_name(idx: int, name: str):
    """Set circuit name for pattern index."""
    _get_state().setdefault("circuit_names", {})[idx] = name


# ---------------------------------------------------------------------------
# Bulk operations for show all / hide all
# ---------------------------------------------------------------------------

def show_all(num_patterns: int, singleton_planets: List[str]):
    """Show all circuits, singletons, and compass roses."""
    state = _get_state()
    # Show all patterns
    patterns = state.setdefault("patterns", {})
    for i in range(num_patterns):
        patterns[i] = True
    # Show all singletons
    singletons = state.setdefault("singletons", {})
    for planet in singleton_planets:
        singletons[planet] = True
    # Show compass roses
    state["compass_inner"] = True
    state["compass_outer"] = True


def hide_all(num_patterns: int, shapes: List[Any], singleton_planets: List[str]):
    """Hide all circuits, shapes, singletons, and compass roses."""
    state = _get_state()
    # Hide all patterns
    patterns = state.setdefault("patterns", {})
    for i in range(num_patterns):
        patterns[i] = False
    # Hide all shapes
    shapes_state = state.setdefault("shapes", {})
    for sh in shapes:
        parent = getattr(sh, 'parent', sh.get('parent', 0)) if hasattr(sh, 'get') else sh.parent
        shape_id = getattr(sh, 'shape_id', sh.get('shape_id', sh.get('id', ''))) if hasattr(sh, 'get') else sh.shape_id
        key = f"{parent}_{shape_id}"
        shapes_state[key] = False
    # Hide all singletons
    singletons = state.setdefault("singletons", {})
    for planet in singleton_planets:
        singletons[planet] = False
    # Hide compass roses
    state["compass_inner"] = False
    state["compass_outer"] = False


# ---------------------------------------------------------------------------
# Sync functions for backward compatibility with legacy session keys
# ---------------------------------------------------------------------------

def sync_from_legacy_keys():
    """
    Migrate legacy individual session_state keys to the unified toggle state.
    Call this once at the start of render_circuit_toggles.
    """
    state = _get_state()
    
    # Migrate COMPASS_KEY
    if "ui_compass_overlay" in st.session_state:
        state["compass_inner"] = st.session_state["ui_compass_overlay"]
    if "ui_compass_overlay_2" in st.session_state:
        state["compass_outer"] = st.session_state["ui_compass_overlay_2"]
    
    # Migrate chart_mode and circuit_submode
    if "chart_mode" in st.session_state:
        state["chart_mode"] = st.session_state["chart_mode"]
    if "circuit_submode" in st.session_state:
        state["circuit_submode"] = st.session_state["circuit_submode"]
    
    # Migrate label_style, dark_mode, interactive_chart
    if "label_style" in st.session_state:
        state["label_style"] = st.session_state["label_style"]
    if "dark_mode" in st.session_state:
        state["dark_mode"] = st.session_state["dark_mode"]
    if "interactive_chart" in st.session_state:
        state["interactive_chart"] = st.session_state["interactive_chart"]
    
    # Migrate synastry aspect toggles
    if "synastry_aspects_inter" in st.session_state:
        state["synastry_aspects_inter"] = st.session_state["synastry_aspects_inter"]
    if "synastry_aspects_chart1" in st.session_state:
        state["synastry_aspects_chart1"] = st.session_state["synastry_aspects_chart1"]
    if "synastry_aspects_chart2" in st.session_state:
        state["synastry_aspects_chart2"] = st.session_state["synastry_aspects_chart2"]
    
    # Migrate pattern toggles
    patterns = state.setdefault("patterns", {})
    for key in list(st.session_state.keys()):
        if key.startswith("toggle_pattern_"):
            try:
                idx = int(key.split("_")[-1])
                patterns[idx] = st.session_state[key]
            except ValueError:
                pass
    
    # Migrate singleton toggles
    singletons = state.setdefault("singletons", {})
    for key in list(st.session_state.keys()):
        if key.startswith("singleton_") and not key.startswith("singleton_map"):
            planet = key[10:]  # len("singleton_") = 10
            singletons[planet] = st.session_state[key]
    
    # Migrate shape toggles
    shapes = state.setdefault("shapes", {})
    for key in list(st.session_state.keys()):
        if key.startswith("shape_") and "_" in key[6:]:
            # key format: "shape_{parent}_{shape_id}"
            parts = key[6:].split("_", 1)  # Split only on first underscore after "shape_"
            if len(parts) == 2:
                shapes[key[6:]] = st.session_state[key]
    
    # Migrate aspect toggles
    aspect_toggles = state.setdefault("aspect_toggles", {})
    for key in list(st.session_state.keys()):
        if key.startswith("aspect_toggle_"):
            body_name = key[14:]  # len("aspect_toggle_") = 14
            aspect_toggles[body_name] = st.session_state[key]
    
    # Migrate circuit names
    circuit_names = state.setdefault("circuit_names", {})
    for key in list(st.session_state.keys()):
        if key.startswith("circuit_name_"):
            try:
                idx = int(key.split("_")[-1])
                circuit_names[idx] = st.session_state[key]
            except ValueError:
                pass


# ---------------------------------------------------------------------------
# Compute visible_objects from toggle state
# ---------------------------------------------------------------------------

def compute_visible_objects(
    patterns: List[List[str]],
    shapes: List[Any],
    singleton_map: Dict[str, Any],
    compass_on: bool = True,
    chart_mode: str = "Circuits",
) -> List[str]:
    """
    Compute the list of visible objects based on current toggle state.
    
    In Standard Chart mode, returns all objects (or None to show everything).
    In Circuits mode, returns only objects from active toggles.
    """
    state = _get_state()
    
    if chart_mode == "Standard Chart":
        # Standard Chart mode: all objects visible by default
        all_objects = set()
        for pattern in patterns:
            all_objects.update(pattern)
        all_objects.update(singleton_map.keys())
        if compass_on:
            all_objects.update(["Ascendant", "Descendant", "Midheaven", "IC",
                                "AC", "DC", "MC", "North Node", "South Node"])
        return sorted(all_objects)
    
    # Circuits mode: only show objects from active toggles
    visible = set()
    patterns_state = state.get("patterns", {})
    shapes_state = state.get("shapes", {})
    singletons_state = state.get("singletons", {})
    
    # Add objects from active circuits
    for i, pattern in enumerate(patterns):
        if patterns_state.get(i, False):
            visible.update(pattern)
    
    # Add objects from active shapes
    for sh in shapes:
        parent = getattr(sh, 'parent', sh.get('parent', 0)) if hasattr(sh, 'get') else sh.parent
        shape_id = getattr(sh, 'shape_id', sh.get('shape_id', sh.get('id', ''))) if hasattr(sh, 'get') else sh.shape_id
        key = f"{parent}_{shape_id}"
        if shapes_state.get(key, False):
            members = getattr(sh, 'members', sh.get('members', [])) if hasattr(sh, 'get') else sh.members
            visible.update(members)
    
    # Add active singletons
    for planet, val in singletons_state.items():
        if val and planet in singleton_map:
            visible.add(planet)
    
    # Always include compass axes when compass is on
    if compass_on:
        visible.update(["Ascendant", "Descendant", "Midheaven", "IC",
                        "AC", "DC", "MC", "North Node", "South Node"])
    
    return sorted(visible) if visible else []
