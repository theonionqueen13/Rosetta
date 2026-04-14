"""Specs tab — chart data tables.

Displays Objects, Conjunctions, Aspects Graph and Aspects List expansions.
"""
from __future__ import annotations

import logging
from typing import Any

from nicegui import ui

from src.nicegui_state import get_chart_object

_log = logging.getLogger(__name__)


def build(state: dict, _form: dict) -> dict[str, Any]:
    """Build the Specs tab contents inside the current ``ui.tab_panel`` context.

    Returns a dict with ``refresh_specs_tab`` callback.
    """
    ui.label("Chart Specs").classes("text-h5 q-mb-md")

    with ui.expansion("Objects", icon="table_chart").classes("w-full"):
        specs_objects_container = ui.column().classes("w-full")

    with ui.expansion("Conjunctions", icon="group_work").classes("w-full"):
        specs_conj_container = ui.column().classes("w-full")

    with ui.expansion("Aspects Graph", icon="grid_on").classes("w-full"):
        specs_aspects_graph_container = ui.column().classes("w-full")

    with ui.expansion("Aspects List", icon="list").classes("w-full"):
        specs_aspects_list_container = ui.column().classes("w-full")

    def _refresh_specs_tab():
        """Rebuild the specifications table from the current chart."""
        import pandas as pd
        chart_obj = get_chart_object(state)

        # ---- Objects table ----
        specs_objects_container.clear()
        with specs_objects_container:
            if chart_obj is None:
                ui.label("No chart loaded.").classes("text-body2 text-grey")
            else:
                try:
                    df = chart_obj.to_dataframe()
                    cols = [
                        {"name": c, "label": c, "field": c, "sortable": True, "align": "left"}
                        for c in df.columns
                    ]
                    rows = df.fillna("").astype(str).to_dict("records")
                    ui.table(
                        columns=cols, rows=rows, row_key="Object",
                        pagination={"rowsPerPage": 50},
                    ).classes("w-full").props("dense flat")
                except Exception as exc:
                    ui.label(f"Error: {exc}").classes("text-negative")

        # ---- Conjunctions table ----
        specs_conj_container.clear()
        with specs_conj_container:
            if chart_obj is None:
                ui.label("No chart loaded.").classes("text-body2 text-grey")
            else:
                conj_rows = getattr(chart_obj, "conj_clusters_rows", None) or []
                if not conj_rows:
                    ui.label("No conjunction clusters found.").classes("text-body2 text-grey")
                else:
                    if isinstance(conj_rows[0], dict):
                        col_names = list(conj_rows[0].keys())
                    else:
                        col_names = [f"Col{i}" for i in range(len(conj_rows[0]))]
                    cols = [
                        {"name": c, "label": c, "field": c, "sortable": True, "align": "left"}
                        for c in col_names
                    ]
                    rows = [
                        (r if isinstance(r, dict) else dict(zip(col_names, r)))
                        for r in conj_rows
                    ]
                    rows = [{k: str(v) for k, v in r.items()} for r in rows]
                    ui.table(
                        columns=cols, rows=rows,
                        pagination={"rowsPerPage": 50},
                    ).classes("w-full").props("dense flat")

        # ---- Aspects Graph table ----
        specs_aspects_graph_container.clear()
        with specs_aspects_graph_container:
            if chart_obj is None:
                ui.label("No chart loaded.").classes("text-body2 text-grey")
            else:
                a_df = getattr(chart_obj, "aspect_df", None)
                if a_df is None or (isinstance(a_df, pd.DataFrame) and a_df.empty):
                    ui.label("No aspect graph available.").classes("text-body2 text-grey")
                else:
                    if isinstance(a_df, pd.DataFrame):
                        if a_df.index.name or not all(isinstance(i, int) for i in a_df.index):
                            a_df = a_df.reset_index()
                        cols = [
                            {"name": c, "label": c, "field": c, "sortable": True, "align": "left"}
                            for c in a_df.columns
                        ]
                        rows = a_df.fillna("").astype(str).to_dict("records")
                    else:
                        col_names = list(a_df[0].keys()) if a_df else []
                        cols = [
                            {"name": c, "label": c, "field": c, "sortable": True, "align": "left"}
                            for c in col_names
                        ]
                        rows = [{k: str(v) for k, v in r.items()} for r in a_df]
                    ui.table(
                        columns=cols, rows=rows,
                        pagination={"rowsPerPage": 50},
                    ).classes("w-full").props("dense flat")

        # ---- Aspects List (clustered) ----
        specs_aspects_list_container.clear()
        with specs_aspects_list_container:
            if chart_obj is None:
                ui.label("No chart loaded.").classes("text-body2 text-grey")
            else:
                edges_major = getattr(chart_obj, "drawn_major_edges", None) or []
                edges_minor = getattr(chart_obj, "drawn_minor_edges", None) or []
                if not edges_major and not edges_minor:
                    ui.label("No aspect data available.").classes("text-body2 text-grey")
                else:
                    try:
                        from src.core.calc_v2 import build_clustered_aspect_edges
                        clustered = build_clustered_aspect_edges(chart_obj, edges_major)
                        rows = []
                        for a, b, meta in clustered:
                            row = {"Kind": "Major", "Cluster A": str(a), "Cluster B": str(b)}
                            for k, v in meta.items():
                                row[k] = str(v)
                            rows.append(row)
                        for a, b, meta in edges_minor:
                            row = {"Kind": "Minor", "A": str(a), "B": str(b)}
                            for k, v in meta.items():
                                row[k] = str(v)
                            rows.append(row)
                        if rows:
                            all_keys: list[str] = []
                            for r in rows:
                                for k in r:
                                    if k not in all_keys:
                                        all_keys.append(k)
                            cols = [
                                {"name": k, "label": k, "field": k, "sortable": True, "align": "left"}
                                for k in all_keys
                            ]
                            ui.table(
                                columns=cols, rows=rows,
                                pagination={"rowsPerPage": 50},
                            ).classes("w-full").props("dense flat")
                        else:
                            ui.label("No clustered aspects.").classes("text-body2 text-grey")
                    except Exception as exc:
                        ui.label(f"Error building aspects list: {exc}").classes("text-negative")

    return {"refresh_specs_tab": _refresh_specs_tab}
