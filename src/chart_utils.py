# src/chart_utils.py
"""
Pure-logic chart utilities with no session-state dependencies.

These helpers operate only on data passed to them and are safe to call
from any context (NiceGUI, tests, CLI scripts).
"""
from __future__ import annotations

from typing import Any, Collection, Mapping

import src.core.patterns_v2 as _patterns_mod


def _resolve_visible_from_patterns(toggle_state: Any, chart=None) -> set[str] | None:
    """Try each candidate function name in patterns_v2 to resolve visible objects."""
    if _patterns_mod is None:
        return None
    candidate_funcs = (
        "resolve_visible_objects",
        "visible_objects_from_toggles",
        "visible_object_names",
        "get_visible_objects",
    )
    for func_name in candidate_funcs:
        func = getattr(_patterns_mod, func_name, None)
        if callable(func):
            try:
                result = func(toggle_state, chart=chart)
            except TypeError:
                try:
                    result = func(toggle_state)
                except TypeError:
                    continue
            if result:
                return set(result)
    return None


def resolve_visible_objects(toggle_state: Any = None, chart=None) -> set[str] | None:
    """Return the set of object names that should be rendered.

    Resolution order:
    1. Delegate to ``patterns_v2`` if it exposes a compatible function.
    2. If *toggle_state* is a ``Mapping``, return keys whose value is truthy.
    3. If *toggle_state* is an iterable (not str/bytes), coerce items to str.
    4. Return ``None`` (= show everything) if no state is provided.
    """
    via_patterns = _resolve_visible_from_patterns(toggle_state, chart)
    if via_patterns:
        return via_patterns
    if toggle_state is None:
        return None
    if isinstance(toggle_state, Mapping):
        names = {str(name) for name, enabled in toggle_state.items() if enabled}
        return names or None
    if isinstance(toggle_state, Collection) and not isinstance(toggle_state, (str, bytes)):
        return {str(name) for name in toggle_state}
    return None
