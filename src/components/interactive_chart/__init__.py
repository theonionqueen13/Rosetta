"""
Interactive Chart — Streamlit custom component
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bidirectional D3.js/SVG chart renderer with hover tooltips, click events,
and a highlight API for the MCP chat widget.

Usage
-----
    from src.components.interactive_chart import st_interactive_chart

    event = st_interactive_chart(
        chart_data=serialized_payload,   # from chart_serializer.serialize_chart_for_rendering()
        highlights={"objects": ["Saturn"]},
        width=600,
        height=600,
        key="main_chart",
    )
    if event and event.get("type") == "click":
        st.write(f"Clicked: {event['element']}")
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# Component registration
# ---------------------------------------------------------------------------
_FRONTEND_DIR = str(Path(__file__).parent / "frontend")

_component_func = components.declare_component(
    "interactive_chart",
    path=_FRONTEND_DIR,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def st_interactive_chart(
    chart_data: Dict[str, Any],
    *,
    highlights: Optional[Dict[str, Any]] = None,
    width: int = 600,
    height: int = 600,
    key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Render an interactive astrological chart.

    Parameters
    ----------
    chart_data : dict
        The serialized chart payload from chart_serializer.serialize_chart_for_rendering().
    highlights : dict | None
        Elements to visually highlight: {"objects": [...], "aspects": [...],
        "houses": [...], "shapes": [...], "clear": True/False}
    width / height : int
        Component dimensions in pixels.
    key : str | None
        Streamlit component key for state management.

    Returns
    -------
    dict | None
        Event dict from the component (e.g., {"type": "click", "element": "Saturn",
        "element_type": "object", ...}), or None if no event occurred.
    """
    # Merge highlights into chart_data
    payload = dict(chart_data)
    if highlights:
        payload["highlights"] = highlights

    # `height` is consumed by Streamlit to set the iframe height.
    # `chart_width` / `chart_height` are sent as args for the JS renderer.
    return _component_func(
        chart_data=payload,
        chart_width=width,
        chart_height=height,
        height=height,
        key=key,
        default=None,
    )
