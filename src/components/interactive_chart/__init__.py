"""
Interactive Chart — NiceGUI component
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
D3.js/SVG chart renderer with hover tooltips and click events.

The frontend assets (d3.v7.min.js, chart_renderer.js, tooltip.js, styles.css)
are served as static files at the /d3chart route — registered in app.py via:
    app.add_static_files('/d3chart', 'src/components/interactive_chart/frontend')

Usage
-----
    from src.components.interactive_chart import render_interactive_chart

    render_interactive_chart(
        container=my_nicegui_container,
        chart_data=serialized_payload,   # from chart_serializer.serialize_chart_for_rendering()
        width=680,
        height=620,
    )
"""
from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from nicegui import ui

# ---------------------------------------------------------------------------
# Static asset route (must match app.add_static_files registration in app.py)
# ---------------------------------------------------------------------------
_FRONTEND_DIR = Path(__file__).parent / "frontend"
_D3_ROUTE = "/d3chart"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_interactive_chart(
    container,
    chart_data: Dict[str, Any],
    *,
    width: int = 680,
    height: int = 620,
    on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> None:
    """
    Render an interactive D3 astrological chart inside a NiceGUI container.

    The container is cleared before rendering.

    Parameters
    ----------
    container : nicegui container element
        The NiceGUI element to render into (will be cleared first).
    chart_data : dict
        The serialized chart payload from chart_serializer.serialize_chart_for_rendering().
    width / height : int
        Chart dimensions in pixels.
    on_event : callable | None
        Optional callback for click events emitted by the chart.
        Receives a dict like {"type": "click", "element": "Saturn",
        "element_type": "object"}.
    """
    container.clear()

    with container:
        # Encode chart data as base64 JSON to pass safely into inline JS.
        json_b64 = base64.b64encode(json.dumps(chart_data).encode()).decode()
        chart_div_id = f"rosetta-d3-{id(container)}"
        is_biwheel = bool(chart_data.get("config", {}).get("is_biwheel"))
        render_fn = "biwheel" if is_biwheel else "single"

        # Load D3 scripts + stylesheet once per page (idempotent guard).
        cache_bust = int(time.time())
        ui.run_javascript(f'''
            if (!window._rosettaD3ScriptsLoaded) {{
                window._rosettaD3ScriptsLoaded = "loading";
                var scripts = [
                    "{_D3_ROUTE}/d3.v7.min.js",
                    "{_D3_ROUTE}/chart_renderer.js?v={cache_bust}",
                    "{_D3_ROUTE}/tooltip.js?v={cache_bust}"
                ];
                var loaded = 0;
                scripts.forEach(function(src) {{
                    var s = document.createElement("script");
                    s.src = src;
                    s.onload = function() {{
                        loaded++;
                        console.log("[Rosetta D3] loaded " + src + " (" + loaded + "/" + scripts.length + ")");
                        if (loaded === scripts.length) {{
                            window._rosettaD3ScriptsLoaded = "ready";
                            console.log("[Rosetta D3] all scripts ready");
                            if (window._rosettaD3RenderPending) {{
                                window._rosettaD3RenderPending();
                                window._rosettaD3RenderPending = null;
                            }}
                        }}
                    }};
                    s.onerror = function() {{
                        console.error("[Rosetta D3] FAILED to load " + src);
                    }};
                    document.head.appendChild(s);
                }});
            }}
        ''')

        ui.run_javascript(f'''
            if (!document.getElementById("rosetta-d3-css")) {{
                var link = document.createElement("link");
                link.id = "rosetta-d3-css";
                link.rel = "stylesheet";
                link.href = "{_D3_ROUTE}/styles.css?v={cache_bust}";
                document.head.appendChild(link);
            }}
        ''')

        # Chart host div
        ui.html(
            f'<div id="{chart_div_id}" '
            f'style="width:100%; max-width:{width}px; height:{height}px; '
            f'display:block; margin:0 auto; overflow:hidden;"></div>'
        )

        # Render the chart — defer until scripts finish loading if needed.
        ui.run_javascript(f'''
            (function() {{
                var b64 = "{json_b64}";
                var data = JSON.parse(atob(b64));
                function doRender() {{
                    var el = document.getElementById("{chart_div_id}");
                    if (!el) {{
                        console.error("[Rosetta D3] container div not found, retrying...");
                        setTimeout(doRender, 200);
                        return;
                    }}
                    try {{
                        if ("{render_fn}" === "biwheel") {{
                            RosettaChart.renderBiwheel(el, data, {width}, {height});
                        }} else {{
                            RosettaChart.render(el, data, {width}, {height});
                        }}
                        console.log("[Rosetta D3] chart rendered successfully");
                        try {{
                            if (typeof RosettaTooltip !== "undefined") {{
                                var svg = el.querySelector("svg");
                                if (svg) RosettaTooltip.wire(d3.select(svg), data);
                            }}
                        }} catch(te) {{
                            console.warn("[Rosetta D3] tooltip wiring:", te);
                        }}
                    }} catch(e) {{
                        console.error("[Rosetta D3] render error:", e);
                        el.innerHTML = "<p style=\\"color:red;padding:1em;\\">Chart render error: " + e.message + "</p>";
                    }}
                }}
                if (window._rosettaD3ScriptsLoaded === "ready") {{
                    doRender();
                }} else {{
                    window._rosettaD3RenderPending = doRender;
                }}
            }})();
        ''')
