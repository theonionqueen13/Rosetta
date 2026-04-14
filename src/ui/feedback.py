"""Feedback FAB and bug-report dialog."""
from __future__ import annotations

import datetime as _dtm
import logging
from typing import Any

from nicegui import ui

_log = logging.getLogger(__name__)

_PROBLEM_TYPES = [
    "The chat said something ridiculous",
    "Unable to use a feature",
    "Got an error message",
    "Login problem",
    "Problem with saving chart data",
    "Other",
]

_AFFECTED_FEATURES = [
    "Single chart", "Synastry chart", "Transit chart",
    "Interactive Chart", "Regular Read-Only Chart",
    "Standard Chart Mode", "Circuits Mode",
    "Circuit/Shape Toggles", "Ruler Chains",
    "Profiles (save/load/delete)", "Birth Data Entry",
    "Login/Account/Password", "Now Button", "Chatbot",
]


def build(state: dict, *, get_user_id, get_supabase) -> None:
    """Create the feedback dialog and the fixed-position FAB button.

    Parameters
    ----------
    state : dict
        Per-user app state (reads ``supabase_user_email``).
    get_user_id : callable
        Returns the current user's ID string.
    get_supabase : callable
        Returns a Supabase client instance.
    """
    with ui.dialog().classes("w-full") as feedback_dlg, \
            ui.card().classes("w-full").style("max-width: 700px"):
        ui.label("Bug Report / Feedback").classes("text-h5 q-mb-sm")
        ui.label(
            "Help us improve Rosetta! Report bugs, share feedback, "
            "or suggest features."
        ).classes("text-body2 text-grey q-mb-md")

        fb_email = ui.input(
            "Your email",
            value=state.get("supabase_user_email", "") or "",
        ).classes("w-full")

        ui.label("What type of problem is this?").classes(
            "text-subtitle2 q-mt-md"
        )
        fb_problems: dict[str, ui.checkbox] = {}
        with ui.row().classes("w-full flex-wrap gap-x-4"):
            for pt in _PROBLEM_TYPES:
                fb_problems[pt] = ui.checkbox(pt)

        fb_description = ui.textarea(
            "Describe the problem",
            placeholder=(
                "Please describe what happened, what you expected, "
                "and any steps to reproduce…"
            ),
        ).classes("w-full q-mt-sm")

        ui.label("Affected features").classes("text-subtitle2 q-mt-md")
        fb_features: dict[str, ui.checkbox] = {}
        with ui.row().classes("w-full flex-wrap gap-x-4"):
            for feat in _AFFECTED_FEATURES:
                fb_features[feat] = ui.checkbox(feat)

        with ui.row().classes("w-full gap-4 q-mt-sm"):
            fb_still = ui.radio(
                ["Yes", "No", "Not sure"],
                value="Not sure",
            ).props("inline")
            ui.label("Still having the problem?").classes(
                "text-caption text-grey self-center"
            )

        with ui.row().classes("w-full gap-4"):
            fb_blocking = ui.radio(
                ["Yes", "No", "Somewhat"],
                value="No",
            ).props("inline")
            ui.label("Blocking you from using the app?").classes(
                "text-caption text-grey self-center"
            )

        fb_suggestions = ui.textarea(
            "Suggestions for future features",
            placeholder="Any features you wish the app had?",
        ).classes("w-full q-mt-sm")

        fb_love = ui.textarea(
            "Anything you love about the app?",
            placeholder="Let us know what's working well!",
        ).classes("w-full q-mt-sm")

        fb_other = ui.textarea(
            "Other feedback",
            placeholder="Anything else you'd like to share…",
        ).classes("w-full q-mt-sm")

        fb_status_label = ui.label("").classes("text-body2")
        fb_status_label.set_visibility(False)

        with ui.row().classes("w-full justify-end gap-2 q-mt-md"):
            ui.button("Cancel", on_click=feedback_dlg.close).props("flat")

            async def _submit_feedback():
                """Validate and submit the user feedback form."""
                email = fb_email.value or ""
                if not email.strip():
                    fb_status_label.text = "Please enter your email."
                    fb_status_label.classes(replace="text-body2 text-negative")
                    fb_status_label.set_visibility(True)
                    return
                sel_problems = [p for p, cb in fb_problems.items() if cb.value]
                if not sel_problems:
                    fb_status_label.text = "Select at least one problem type."
                    fb_status_label.classes(replace="text-body2 text-negative")
                    fb_status_label.set_visibility(True)
                    return
                desc = (fb_description.value or "").strip()
                if not desc:
                    fb_status_label.text = "Please describe the problem."
                    fb_status_label.classes(replace="text-body2 text-negative")
                    fb_status_label.set_visibility(True)
                    return

                sel_features = [f for f, cb in fb_features.items() if cb.value]
                payload = {
                    "user_email": email.strip(),
                    "user_id": get_user_id(),
                    "problem_types": sel_problems,
                    "description": desc,
                    "affected_features": sel_features,
                    "attachments": {},
                    "still_having_problem": fb_still.value,
                    "blocking_issue": fb_blocking.value,
                    "suggestions": (fb_suggestions.value or "").strip() or None,
                    "love_feedback": (fb_love.value or "").strip() or None,
                    "other_feedback": (fb_other.value or "").strip() or None,
                    "app_state_snapshot": {},
                    "admin_viewed": False,
                    "created_at": _dtm.datetime.utcnow().isoformat(),
                }
                try:
                    client = get_supabase()
                    result = client.table("user_feedback").insert(payload).execute()
                    if result.data:
                        fb_status_label.text = (
                            "Feedback submitted! Thank you for helping "
                            "improve Rosetta."
                        )
                        fb_status_label.classes(
                            replace="text-body2 text-positive"
                        )
                        fb_status_label.set_visibility(True)
                        await ui.run_javascript("", timeout=1.5)
                        feedback_dlg.close()
                    else:
                        fb_status_label.text = "Submission failed."
                        fb_status_label.classes(
                            replace="text-body2 text-negative"
                        )
                        fb_status_label.set_visibility(True)
                except Exception as exc:
                    fb_status_label.text = f"Submission failed: {exc}"
                    fb_status_label.classes(
                        replace="text-body2 text-negative"
                    )
                    fb_status_label.set_visibility(True)

            ui.button(
                "Submit Feedback", icon="send",
                on_click=_submit_feedback,
            ).props("color=primary")

    # Floating action button — always visible
    ui.button(
        icon="bug_report",
        on_click=feedback_dlg.open,
    ).props(
        "fab color=orange"
    ).classes("fixed-bottom-right").style(
        "position: fixed; bottom: 24px; right: 24px; z-index: 9999"
    )
