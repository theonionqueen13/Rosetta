"""Admin tab — feedback reports viewer (admin-only)."""
from __future__ import annotations

import json
import logging
from typing import Any

from nicegui import ui

from src.db.supabase_client import get_supabase

_log = logging.getLogger(__name__)


def build(state: dict, _form: dict) -> dict[str, Any]:
    """Build the Admin tab inside the current ``ui.tab_panel`` context.

    Returns an empty dict (no shared callbacks).
    """
    ui.label("Admin — Feedback Reports").classes("text-h5 q-mb-md")

    admin_status_label = ui.label("").classes("text-body2 text-grey q-mb-sm")
    admin_reports_container = ui.column().classes("w-full gap-4")

    def _fetch_admin_reports() -> list:
        """Fetch all admin feedback reports from Supabase."""
        try:
            client = get_supabase()
            result = (
                client.table("user_feedback")
                .select("*")
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
            return result.data or []
        except Exception as exc:
            _log.warning("Failed to fetch admin reports: %s", exc)
            return []

    def _mark_viewed(report_id: str):
        """Mark a feedback report as viewed in the database."""
        try:
            client = get_supabase()
            client.table("user_feedback").update(
                {"admin_viewed": True}
            ).eq("id", report_id).execute()
        except Exception:
            pass
        _load_admin_reports()

    def _render_admin_report(report: dict, index: int):
        """Render a single admin feedback report card."""
        rid = report.get("id", "unknown")
        created = report.get("created_at", "")
        email = report.get("user_email", "Unknown")
        problem_types = report.get("problem_types", [])
        description = report.get("description", "No description")
        affected = report.get("affected_features", [])
        still_having = report.get("still_having_problem", "Unknown")
        blocking = report.get("blocking_issue", "Unknown")
        viewed = report.get("admin_viewed", False)

        status = "\u2705" if viewed else "\U0001F195"
        with ui.card().classes("w-full q-pa-sm"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label(f"{status} Report #{index + 1}").classes("text-subtitle2 text-weight-bold")
                ui.label(f"From: {email}").classes("text-caption text-grey")
                ui.label(f"{created[:16] if created else 'Unknown date'}").classes("text-caption text-grey")

            if problem_types:
                with ui.row().classes("gap-1 q-mt-xs"):
                    for pt in problem_types:
                        ui.badge(pt, color="orange").props("outline")

            ui.label("Description:").classes("text-caption text-weight-medium q-mt-xs")
            ui.label(description).classes("text-body2")

            if affected:
                ui.label("Affected: " + ", ".join(affected)).classes("text-caption text-grey q-mt-xs")

            with ui.row().classes("gap-4 q-mt-xs"):
                ui.label(f"Still having problem: {still_having}").classes("text-caption")
                ui.label(f"Blocking: {blocking}").classes("text-caption")

            suggestions = report.get("suggestions")
            love = report.get("love_feedback")
            other = report.get("other_feedback")
            if suggestions:
                ui.label(f"Suggestions: {suggestions}").classes("text-body2 q-mt-xs")
            if love:
                ui.label(f"What they love: {love}").classes("text-body2 q-mt-xs")
            if other:
                ui.label(f"Other: {other}").classes("text-body2 q-mt-xs")

            # Attachments
            attachments = report.get("attachments", {})
            if attachments:
                with ui.expansion("Attachments", icon="attach_file").classes("w-full q-mt-xs"):
                    if "chat_history" in attachments:
                        ui.label("Chat History:").classes("text-caption text-weight-medium")
                        try:
                            chat = json.loads(attachments["chat_history"])
                            for msg in chat:
                                role = msg.get("role", "?")
                                content = msg.get("content", "")
                                ui.label(f"{role}: {content[:500]}").classes("text-body2")
                        except Exception:
                            ui.label(attachments["chat_history"][:2000]).classes("text-body2")

                    if "chart_image" in attachments:
                        ui.label("Chart Image:").classes("text-caption text-weight-medium q-mt-xs")
                        try:
                            ui.image(f"data:image/png;base64,{attachments['chart_image']}").classes("w-64")
                        except Exception as exc:
                            ui.label(f"Could not decode: {exc}").classes("text-negative")

                    if "screenshot" in attachments:
                        ui.label("Screenshot:").classes("text-caption text-weight-medium q-mt-xs")
                        try:
                            ui.image(f"data:image/png;base64,{attachments['screenshot']}").classes("w-64")
                        except Exception as exc:
                            ui.label(f"Could not decode: {exc}").classes("text-negative")

                    if "error_messages" in attachments:
                        ui.label("Error Messages:").classes("text-caption text-weight-medium q-mt-xs")
                        ui.code(attachments["error_messages"]).classes("w-full")

                    if "copypaste_text" in attachments:
                        ui.label("Copy/Pasted Text:").classes("text-caption text-weight-medium q-mt-xs")
                        ui.label(attachments["copypaste_text"]).classes("text-body2")

            # App state snapshot
            app_state = report.get("app_state_snapshot", {})
            if app_state:
                with ui.expansion("App State Snapshot", icon="data_object").classes("w-full q-mt-xs"):
                    ui.code(json.dumps(app_state, indent=2, default=str)).classes("w-full")

            if not viewed:
                ui.button(
                    "Mark as Viewed", icon="check",
                    on_click=lambda _rid=rid: _mark_viewed(_rid),
                ).props("flat dense color=primary").classes("q-mt-xs")

    def _load_admin_reports():
        """Load and display all feedback reports in the admin panel."""
        reports = _fetch_admin_reports()
        new_count = sum(1 for r in reports if not r.get("admin_viewed", False))
        admin_status_label.text = (
            f"{len(reports)} reports ({new_count} new)" if reports else "No reports found."
        )
        admin_reports_container.clear()
        if not reports:
            with admin_reports_container:
                ui.label("No feedback reports found.").classes("text-body2 text-grey")
            return
        with admin_reports_container:
            for idx, report in enumerate(reports):
                _render_admin_report(report, idx)

    with ui.row().classes("gap-2 q-mb-sm"):
        ui.button(
            "Refresh Reports", icon="refresh",
            on_click=lambda: _load_admin_reports(),
        ).props("flat")

    _load_admin_reports()

    return {}
