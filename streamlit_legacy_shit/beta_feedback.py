# beta_feedback.py
"""
Beta Testers Bug/Feedback Report Feature

Provides:
- render_feedback_expander(): Main feedback form (top of app & auth page)
- render_admin_alert(): Red alert banner for admins when reports exist
- render_admin_report_viewer(): Expander at bottom for admin to view reports
- buffered_error(): Wrapper for st.error that also buffers for attachment
"""
import io
import json
import base64
import datetime as dt
from typing import Optional, Any
import streamlit as st


# ---------------------------------------------------------------------------
# Error Buffering (for "include error message" attachment)
# ---------------------------------------------------------------------------

_ERROR_BUFFER_KEY = "_app_error_buffer"


def buffered_error(msg: str) -> None:
    """Display an error via st.error AND buffer it for feedback attachment."""
    st.error(msg)
    buf = st.session_state.setdefault(_ERROR_BUFFER_KEY, [])
    buf.append({
        "message": msg,
        "timestamp": dt.datetime.utcnow().isoformat(),
    })


def get_buffered_errors() -> list[dict]:
    """Return all buffered errors."""
    return st.session_state.get(_ERROR_BUFFER_KEY, [])


def clear_buffered_errors() -> None:
    """Clear the error buffer."""
    st.session_state[_ERROR_BUFFER_KEY] = []


# ---------------------------------------------------------------------------
# Attachment Helpers
# ---------------------------------------------------------------------------

def _collect_chat_history() -> Optional[str]:
    """Serialize chat history to JSON string."""
    history = st.session_state.get("mcp_chat_history", [])
    if not history:
        return None
    # Convert to serializable format (remove any non-serializable objects)
    serializable = []
    for msg in history:
        entry = {
            "role": msg.get("role", "unknown"),
            "content": msg.get("content", ""),
        }
        if "meta" in msg:
            entry["meta"] = str(msg["meta"])
        serializable.append(entry)
    return json.dumps(serializable, indent=2, ensure_ascii=False)


def _capture_chart_image() -> Optional[str]:
    """Capture the current matplotlib chart as base64 PNG."""
    fig = st.session_state.get("render_fig")
    if fig is None:
        return None
    try:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
        buf.seek(0)
        return base64.b64encode(buf.read()).decode("utf-8")
    except Exception as e:
        return f"Error capturing chart: {e}"


def _get_app_state_snapshot() -> dict:
    """Capture current app state for debugging context."""
    return {
        "chart_mode": st.session_state.get("chart_mode"),
        "circuit_submode": st.session_state.get("circuit_submode"),
        "synastry_mode": st.session_state.get("synastry_mode"),
        "transit_mode": st.session_state.get("transit_mode"),
        "interactive_chart": st.session_state.get("interactive_chart"),
        "dark_mode": st.session_state.get("dark_mode"),
        "label_style": st.session_state.get("label_style"),
        "current_profile": st.session_state.get("current_profile"),
        "has_chart": st.session_state.get("last_chart") is not None,
        "has_chart_2": st.session_state.get("last_chart_2") is not None,
        "timestamp_utc": dt.datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Database Operations
# ---------------------------------------------------------------------------

def _submit_feedback_to_db(payload: dict) -> tuple[bool, str]:
    """Insert feedback into Supabase user_feedback table.
    
    Returns (success: bool, message: str)
    """
    try:
        from supabase_client import get_supabase
        client = get_supabase()
        
        # Insert the feedback
        result = client.table("user_feedback").insert(payload).execute()
        
        if result.data:
            return True, "Feedback submitted successfully! Thank you for helping improve Rosetta."
        else:
            return False, "Submission failed - no data returned."
    except Exception as e:
        error_msg = str(e)
        if "relation" in error_msg.lower() and "does not exist" in error_msg.lower():
            return False, "Feedback table not set up yet. Please contact the admin."
        return False, f"Submission failed: {error_msg}"


def _send_admin_email_notification(payload: dict, admin_email: str) -> bool:
    """Send email notification to admin about new feedback.
    
    Uses Supabase Edge Functions or similar. Returns True if sent.
    Note: This is a placeholder - actual implementation depends on your email setup.
    """
    # For now, we'll store the notification intent; actual email sending
    # would require Supabase Edge Functions, SendGrid, or similar
    try:
        from supabase_client import get_supabase
        client = get_supabase()
        
        # Store notification in a queue table (admin can configure email delivery)
        notification = {
            "admin_email": admin_email,
            "feedback_id": payload.get("id"),
            "user_email": payload.get("user_email", "unknown"),
            "problem_types": payload.get("problem_types", []),
            "description_preview": (payload.get("description", "")[:200] + "...") if payload.get("description") else "",
            "created_at": dt.datetime.utcnow().isoformat(),
            "sent": False,
        }
        
        # Attempt to insert notification (table may not exist yet)
        try:
            client.table("admin_notifications").insert(notification).execute()
        except Exception:
            pass  # Notification queue is optional
        
        return True
    except Exception:
        return False


def _fetch_pending_reports(user_id: str) -> list[dict]:
    """Fetch unread feedback reports for admin viewing."""
    try:
        from supabase_client import get_supabase
        client = get_supabase()
        
        result = client.table("user_feedback") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
        
        return result.data or []
    except Exception as e:
        st.error(f"Failed to fetch reports: {e}")
        return []


def _get_unread_report_count() -> int:
    """Get count of unread/new feedback reports (last 7 days)."""
    try:
        from supabase_client import get_supabase
        client = get_supabase()
        
        week_ago = (dt.datetime.utcnow() - dt.timedelta(days=7)).isoformat()
        result = client.table("user_feedback") \
            .select("id", count="exact") \
            .gte("created_at", week_ago) \
            .eq("admin_viewed", False) \
            .execute()
        
        return result.count or 0
    except Exception:
        # Table might not exist or column missing - gracefully return 0
        return 0


def _mark_report_viewed(report_id: str) -> None:
    """Mark a report as viewed by admin."""
    try:
        from supabase_client import get_supabase
        client = get_supabase()
        
        client.table("user_feedback") \
            .update({"admin_viewed": True}) \
            .eq("id", report_id) \
            .execute()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Problem Types & Affected Features
# ---------------------------------------------------------------------------

PROBLEM_TYPES = [
    "The chat said something ridiculous",
    "Unable to use a feature",
    "Got an error message",
    "Login problem",
    "Problem with saving chart data",
    "Other",
]

AFFECTED_FEATURES = {
    "Chart Types": [
        "Single chart",
        "Synastry chart",
        "Transit chart",
    ],
    "Chart Display": [
        "Interactive Chart",
        "Regular Read-Only Chart",
        "Standard Chart Mode",
        "Circuits Mode",
    ],
    "Features": [
        "Circuit/Shape Toggles",
        "Planet Profile Sidebar",
        "Chart Manager",
        "Birth Data Entry",
        "Login/Account/Password",
        '"Now" Button',
        "Chatbot",
    ],
}


# ---------------------------------------------------------------------------
# Main Feedback Form
# ---------------------------------------------------------------------------

def render_feedback_expander(auth_page: bool = False) -> None:
    """Render the beta feedback expander.
    
    Args:
        auth_page: If True, disables attachments that require chart/app data
    """
    expander_label = "🐛 Beta Feedback / Bug Report"
    
    with st.expander(expander_label, expanded=False):
        st.markdown("**Help us improve Rosetta!** Report bugs, share feedback, or suggest features.")
        st.markdown("---")
        
        # --- User Info (auto-populated) ---
        col_email, col_uid = st.columns(2)
        with col_email:
            user_email = st.session_state.get("supabase_user_email", "")
            email_input = st.text_input(
                "Your email",
                value=user_email,
                key="feedback_email",
                placeholder="Enter your email",
            )
        with col_uid:
            user_id = st.session_state.get("supabase_user_id")
            if user_id:
                st.text_input("User ID", value=user_id[:8] + "...", disabled=True, key="feedback_uid_display")
            else:
                st.text_input("User ID", value="Not logged in", disabled=True, key="feedback_uid_display")
        
        st.markdown("---")
        
        # --- Attachments Section ---
        st.markdown("**📎 Attachments** (auto-captured from app)")
        
        att_col1, att_col2 = st.columns(2)
        
        with att_col1:
            # These work even on auth page (but return empty)
            include_chat = st.checkbox(
                "Include chat history",
                key="feedback_include_chat",
                disabled=auth_page,
                help="Attaches your conversation with the chatbot" if not auth_page else "Not available on login page",
            )
            include_chart = st.checkbox(
                "Include read-only chart image",
                key="feedback_include_chart",
                disabled=auth_page,
                help="Captures the current chart as an image" if not auth_page else "Not available on login page",
            )
            include_interactive = st.checkbox(
                "Include interactive chart snapshot",
                key="feedback_include_interactive",
                disabled=True,  # Always disabled - coming soon
                help="Coming soon – use screenshot upload for now",
            )
        
        with att_col2:
            include_errors = st.checkbox(
                "Include error messages",
                key="feedback_include_errors",
                disabled=auth_page,
                help="Attaches any error messages shown by the app" if not auth_page else "Not available on login page",
            )
            upload_screenshot = st.checkbox(
                "Upload screenshot",
                key="feedback_upload_screenshot",
            )
            include_copypaste = st.checkbox(
                "Copy/paste text from app",
                key="feedback_include_copypaste",
            )
        
        # Screenshot uploader (appears when checked)
        screenshot_data = None
        if upload_screenshot:
            uploaded_file = st.file_uploader(
                "Upload a screenshot",
                type=["png", "jpg", "jpeg", "gif"],
                key="feedback_screenshot_file",
            )
            if uploaded_file:
                screenshot_data = base64.b64encode(uploaded_file.read()).decode("utf-8")
                st.success(f"Screenshot attached: {uploaded_file.name}")
        
        # Copy/paste text area (appears when checked)
        copypaste_text = ""
        if include_copypaste:
            copypaste_text = st.text_area(
                "Paste text from the app here",
                key="feedback_copypaste_text",
                height=100,
                placeholder="Copy and paste any relevant text from the app...",
            )
        
        st.markdown("---")
        
        # --- Problem Type ---
        st.markdown("**What type of problem is this?**")
        problem_cols = st.columns(3)
        selected_problems = []
        for i, problem in enumerate(PROBLEM_TYPES):
            with problem_cols[i % 3]:
                if st.checkbox(problem, key=f"feedback_problem_{i}"):
                    selected_problems.append(problem)
        
        st.markdown("---")
        
        # --- Describe the Problem ---
        description = st.text_area(
            "**Describe the problem**",
            key="feedback_description",
            height=120,
            placeholder="Please describe what happened, what you expected, and any steps to reproduce...",
        )
        
        st.markdown("---")
        
        # --- Affected Features ---
        st.markdown("**What feature(s) were affected?**")
        selected_features = []
        
        for category, features in AFFECTED_FEATURES.items():
            st.caption(category)
            cols = st.columns(min(4, len(features)))
            for i, feature in enumerate(features):
                with cols[i % len(cols)]:
                    if st.checkbox(feature, key=f"feedback_feature_{feature.replace(' ', '_')}"):
                        selected_features.append(feature)
        
        st.markdown("---")
        
        # --- Quick Questions ---
        q_col1, q_col2 = st.columns(2)
        with q_col1:
            still_having = st.radio(
                "Are you still having the problem?",
                ["Yes", "No", "Not sure"],
                key="feedback_still_having",
                horizontal=True,
            )
        with q_col2:
            blocking = st.radio(
                "Is this preventing you from using the app?",
                ["Yes", "No", "Somewhat"],
                key="feedback_blocking",
                horizontal=True,
            )
        
        st.markdown("---")
        
        # --- Optional Feedback ---
        st.markdown("**Optional feedback**")
        
        suggestions = st.text_area(
            "Suggestions for future features",
            key="feedback_suggestions",
            height=80,
            placeholder="Any features you wish the app had?",
        )
        
        love_feedback = st.text_area(
            "Anything you love about the app?",
            key="feedback_love",
            height=80,
            placeholder="Let us know what's working well!",
        )
        
        other_feedback = st.text_area(
            "Other feedback",
            key="feedback_other",
            height=80,
            placeholder="Anything else you'd like to share...",
        )
        
        st.markdown("---")
        
        # --- Submit Button ---
        if st.button("📤 Submit Feedback", key="feedback_submit", type="primary", use_container_width=True):
            # Validate required fields
            if not email_input:
                st.error("Please enter your email address.")
                return
            if not selected_problems:
                st.error("Please select at least one problem type.")
                return
            if not description.strip():
                st.error("Please describe the problem.")
                return
            
            # Collect attachments
            attachments = {}
            
            if include_chat and not auth_page:
                chat_data = _collect_chat_history()
                if chat_data:
                    attachments["chat_history"] = chat_data
            
            if include_chart and not auth_page:
                chart_data = _capture_chart_image()
                if chart_data and not chart_data.startswith("Error"):
                    attachments["chart_image"] = chart_data
            
            if include_errors and not auth_page:
                errors = get_buffered_errors()
                if errors:
                    attachments["error_messages"] = json.dumps(errors)
            
            if screenshot_data:
                attachments["screenshot"] = screenshot_data
            
            if copypaste_text.strip():
                attachments["copypaste_text"] = copypaste_text.strip()
            
            # Build payload
            payload = {
                "user_email": email_input,
                "user_id": st.session_state.get("supabase_user_id"),
                "problem_types": selected_problems,
                "description": description.strip(),
                "affected_features": selected_features,
                "attachments": attachments,
                "still_having_problem": still_having,
                "blocking_issue": blocking,
                "suggestions": suggestions.strip() if suggestions else None,
                "love_feedback": love_feedback.strip() if love_feedback else None,
                "other_feedback": other_feedback.strip() if other_feedback else None,
                "app_state_snapshot": _get_app_state_snapshot() if not auth_page else {"page": "auth"},
                "admin_viewed": False,
                "created_at": dt.datetime.utcnow().isoformat(),
            }
            
            # Submit to database
            success, message = _submit_feedback_to_db(payload)
            
            if success:
                st.success(message)
                st.balloons()
                
                # Try to send admin notification
                try:
                    from supabase_admin import get_admin_email
                    admin_email = get_admin_email()
                    if admin_email:
                        _send_admin_email_notification(payload, admin_email)
                except Exception:
                    pass  # Admin notification is optional
                
                # Clear form state
                for key in list(st.session_state.keys()):
                    if key.startswith("feedback_"):
                        del st.session_state[key]
            else:
                st.error(message)


# ---------------------------------------------------------------------------
# Admin Alert Banner
# ---------------------------------------------------------------------------

def render_admin_alert() -> None:
    """Render red alert banner at top of app if there are unread reports.
    
    Only shows for admin users.
    """
    try:
        from supabase_admin import is_admin
        if not is_admin():
            return
    except Exception:
        return
    
    count = _get_unread_report_count()
    if count == 0:
        return
    
    # Store the count for the report viewer
    st.session_state["_admin_report_count"] = count
    
    # Red alert banner
    st.markdown(
        f"""
        <div style="
            background-color: #ff4b4b;
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        ">
            <span style="font-weight: bold; font-size: 1.1rem;">
                🚨 ALERT: {count} new feedback report{'s' if count != 1 else ''} to review! 🚨
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    # Jump to report viewer button
    if st.button("📋 Jump to Report Viewer", key="admin_jump_to_reports", type="primary"):
        st.session_state["_scroll_to_reports"] = True
        st.session_state["_expand_report_viewer"] = True


# ---------------------------------------------------------------------------
# Admin Report Viewer
# ---------------------------------------------------------------------------

def render_admin_report_viewer() -> None:
    """Render the admin report viewer expander at bottom of page.
    
    Only shows for admin users.
    """
    try:
        from supabase_admin import is_admin
        if not is_admin():
            return
    except Exception:
        return
    
    # Scroll target anchor
    st.markdown('<div id="admin-report-viewer"></div>', unsafe_allow_html=True)
    
    # Handle scroll request
    if st.session_state.get("_scroll_to_reports"):
        st.session_state["_scroll_to_reports"] = False
        # Inject JavaScript to scroll to this element using components
        import streamlit.components.v1 as components
        components.html(
            """
            <script>
                setTimeout(function() {
                    var el = window.parent.document.getElementById('admin-report-viewer');
                    if (el) el.scrollIntoView({behavior: 'smooth'});
                }, 100);
            </script>
            """,
            height=0,
        )
    
    # Determine if expander should be open
    expand = st.session_state.pop("_expand_report_viewer", False)
    
    report_count = st.session_state.get("_admin_report_count", 0)
    label = f"🔍 Admin: Feedback Reports ({report_count} new)" if report_count else "🔍 Admin: Feedback Reports"
    
    with st.expander(label, expanded=expand):
        st.markdown("### Beta Tester Feedback Reports")
        
        # Refresh button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Refresh", key="admin_refresh_reports"):
                st.rerun()
        
        # Fetch reports
        user_id = st.session_state.get("supabase_user_id", "")
        reports = _fetch_pending_reports(user_id)
        
        if not reports:
            st.info("No feedback reports found.")
            return
        
        st.markdown(f"**{len(reports)} reports** (most recent first)")
        st.markdown("---")
        
        for i, report in enumerate(reports):
            _render_single_report(report, i)
            st.markdown("---")


def _render_single_report(report: dict, index: int) -> None:
    """Render a single feedback report."""
    report_id = report.get("id", "unknown")
    created_at = report.get("created_at", "")
    user_email = report.get("user_email", "Unknown")
    problem_types = report.get("problem_types", [])
    description = report.get("description", "No description")
    affected_features = report.get("affected_features", [])
    still_having = report.get("still_having_problem", "Unknown")
    blocking = report.get("blocking_issue", "Unknown")
    admin_viewed = report.get("admin_viewed", False)
    
    # Header with status indicator
    status_emoji = "✅" if admin_viewed else "🆕"
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        st.markdown(f"**{status_emoji} Report #{index + 1}**")
    with col2:
        st.caption(f"From: {user_email}")
    with col3:
        st.caption(f"📅 {created_at[:16] if created_at else 'Unknown date'}")
    
    # Problem types as tags
    if problem_types:
        st.markdown("**Problems:** " + ", ".join(f"`{p}`" for p in problem_types))
    
    # Description
    st.markdown("**Description:**")
    st.text(description)
    
    # Affected features
    if affected_features:
        st.markdown("**Affected:** " + ", ".join(affected_features))
    
    # Impact indicators
    impact_col1, impact_col2 = st.columns(2)
    with impact_col1:
        st.markdown(f"Still having problem: **{still_having}**")
    with impact_col2:
        st.markdown(f"Blocking issue: **{blocking}**")
    
    # Optional feedback sections
    suggestions = report.get("suggestions")
    love_feedback = report.get("love_feedback")
    other_feedback = report.get("other_feedback")
    
    if suggestions:
        st.markdown(f"**Suggestions:** {suggestions}")
    if love_feedback:
        st.markdown(f"**What they love:** {love_feedback}")
    if other_feedback:
        st.markdown(f"**Other:** {other_feedback}")
    
    # Attachments
    attachments = report.get("attachments", {})
    if attachments:
        with st.expander("📎 View Attachments", expanded=False):
            if "chat_history" in attachments:
                st.markdown("**Chat History:**")
                try:
                    chat = json.loads(attachments["chat_history"])
                    for msg in chat:
                        role = msg.get("role", "?")
                        content = msg.get("content", "")
                        st.markdown(f"**{role}:** {content[:500]}{'...' if len(content) > 500 else ''}")
                except Exception:
                    st.text(attachments["chat_history"][:2000])
            
            if "chart_image" in attachments:
                st.markdown("**Chart Image:**")
                try:
                    img_data = base64.b64decode(attachments["chart_image"])
                    st.image(img_data, caption="Attached Chart Image")
                except Exception as e:
                    st.error(f"Could not decode chart image: {e}")
            
            if "screenshot" in attachments:
                st.markdown("**Screenshot:**")
                try:
                    img_data = base64.b64decode(attachments["screenshot"])
                    st.image(img_data, caption="User Screenshot")
                except Exception as e:
                    st.error(f"Could not decode screenshot: {e}")
            
            if "error_messages" in attachments:
                st.markdown("**Error Messages:**")
                st.code(attachments["error_messages"])
            
            if "copypaste_text" in attachments:
                st.markdown("**Copy/Pasted Text:**")
                st.text(attachments["copypaste_text"])
    
    # App state snapshot
    app_state = report.get("app_state_snapshot", {})
    if app_state:
        with st.expander("🔧 App State Snapshot", expanded=False):
            st.json(app_state)
    
    # Mark as viewed button
    if not admin_viewed:
        if st.button(f"✓ Mark as Viewed", key=f"mark_viewed_{report_id}"):
            _mark_report_viewed(report_id)
            st.success("Marked as viewed!")
            st.rerun()
