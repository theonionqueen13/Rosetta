# profile_manager_v2.py
from __future__ import annotations
import streamlit as st
import pytz
from typing import Callable, Dict, Any, Optional, List

def ensure_profile_session_defaults(month_names: List[str]) -> None:
    """Create the session keys this panel expects before any widgets render."""
    st.session_state.setdefault("current_profile", None)
    st.session_state.setdefault("active_profile_tab", "Load Chart")
    st.session_state.setdefault("profile_loaded", False)
    st.session_state.setdefault("saved_circuit_names", {})
    # basic birth defaults (don’t assume user has set them yet)
    st.session_state.setdefault("profile_year", 1990)
    st.session_state.setdefault("profile_month_name", "July")
    st.session_state.setdefault("profile_day", 1)
    st.session_state.setdefault("profile_hour", 0)
    st.session_state.setdefault("profile_minute", 0)
    st.session_state.setdefault("profile_city", "")
    # helpers for quick access
    st.session_state.setdefault("hour_val", st.session_state["profile_hour"])
    st.session_state.setdefault("minute_val", st.session_state["profile_minute"])
    st.session_state.setdefault("city_input", st.session_state["profile_city"])
    # geocode cache
    st.session_state.setdefault("current_lat", None)
    st.session_state.setdefault("current_lon", None)
    st.session_state.setdefault("current_tz_name", None)
    st.session_state.setdefault("last_location", None)
    st.session_state.setdefault("last_timezone", None)
    # circuit pattern list may or may not exist yet
    st.session_state.setdefault("patterns", [])
    st.session_state.setdefault("chart_ready", False) 
    st.session_state.setdefault("show_now_city_field", False)
    st.session_state.setdefault("now_city_temp", "")
    st.session_state.setdefault("__clear_now_city_temp__", False)
    # synastry controls inside profile manager
    st.session_state.setdefault("synastry_mode", False)
    st.session_state.setdefault("pm_synastry_slot", "Outer Chart")

def render_profile_manager(
    *,
    MONTH_NAMES: List[str],
    current_user_id: str,
    run_chart: Callable[[float, float, str], None],
    _selected_house_system: Callable[[], str],
    save_user_profile_db: Callable[[str, str, Dict[str, Any]], None],
    load_user_profiles_db: Callable[[str], Dict[str, Any]],
    delete_user_profile_db: Callable[[str, str], None],
    community_save: Callable[[str, Dict[str, Any]], Any],
    community_list: Callable[..., List[Dict[str, Any]]],
    community_get: Callable[[Any], Optional[Dict[str, Any]]],
    community_delete: Callable[[Any], None],
    is_admin: Callable[[str], bool],
    geocode_city: Optional[Callable[[str], tuple[float, float, str]]] = None,
    # Optional live geocode inputs (fallback to session_state if None)
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    tz_name: Optional[str] = None,
    hour_val: Optional[int] = None,
    minute_val: Optional[int] = None,
    city_name: Optional[str] = None,
    # <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    chart_ready: bool = False,  # <- ADD THIS PARAM
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    # New group functions
    save_user_profile_group_db: Optional[Callable[[str, str], Dict[str, Any]]] = None,
    load_user_profile_groups_db: Optional[Callable[[str], Dict[str, Any]]] = None,
    load_user_profiles_by_group_db: Optional[Callable[[str], Dict[str, Any]]] = None,
    delete_user_profile_group_db: Optional[Callable[[str, str], None]] = None,
) -> Dict[str, Any]:
    """
    Renders the full Profile Manager UI. Returns the (possibly refreshed) saved_profiles dict.
    All external dependencies are injected to avoid circular imports and 'name not defined' errors.
    """

    # ✅ Clear the quick-city temp safely BEFORE any widgets are instantiated
    if st.session_state.get("__clear_now_city_temp__", False):
        st.session_state.pop("now_city_temp", None)
        st.session_state["__clear_now_city_temp__"] = False

    # --- pull fallbacks from session_state if caller didn’t pass them ---
    lat = st.session_state.get("current_lat") if lat is None else lat
    lon = st.session_state.get("current_lon") if lon is None else lon
    tz_name = st.session_state.get("current_tz_name") if tz_name is None else tz_name
    hour_val = st.session_state.get("hour_val") if hour_val is None else hour_val
    minute_val = st.session_state.get("minute_val") if minute_val is None else minute_val
    city_name = st.session_state.get("profile_city") if city_name is None else city_name

    # ---- data load (lazy – only fetched when the active tab needs it) ----
    # With @st.cache_data on the Supabase functions this is near-instant on
    # repeat calls, but we still avoid the import-time call for tabs that
    # don't need it.
    _profiles_cache: Dict[str, Any] | None = None

    def _get_saved_profiles() -> Dict[str, Any]:
        nonlocal _profiles_cache
        if _profiles_cache is None:
            _profiles_cache = load_user_profiles_db(current_user_id)
        return _profiles_cache

    # =====================
    # 👤 Profile Manager UI
    # =====================
    tab_labels = ["Add Chart", "Load Chart", "Delete Chart"]
    default_tab = st.session_state.get("active_profile_tab", "Load Chart")
    if default_tab not in tab_labels:
        default_tab = tab_labels[0]

    active_tab = st.radio(
        "👤 Chart Manager",
        tab_labels,
        index=tab_labels.index(default_tab),
        horizontal=True,
        key="profile_tab_selector",
    )
    st.session_state["active_profile_tab"] = active_tab

    # Check for deferred errors from profile load
    if st.session_state.get("__profile_load_error__"):
        st.error(st.session_state.pop("__profile_load_error__"))
    
    # Show success message if a profile was just loaded
    if st.session_state.get("profile_loaded") and st.session_state.get("current_profile"):
        _profile_name = st.session_state["current_profile"]
        if st.session_state.get("last_chart"):
            st.success(f"✅ Chart '{_profile_name}' loaded! Chart is ready.")
        else:
            st.info(f"📋 Chart '{_profile_name}' loaded. (Recalculation may be needed if birth data changed.)")
        st.session_state["profile_loaded"] = False  # Show message only once

    # --- Add ---
    if active_tab == "Add Chart":
        # Show the current chart's birth data (read-only) so the user knows what they're saving
        _current_chart = st.session_state.get("last_chart")
        if _current_chart is None:
            st.warning("No chart calculated yet. Calculate a chart before saving a profile.")
        else:
            _, _date_line, _time_line, _chart_city, _ = _current_chart.header_lines()
            st.markdown(
                f"**📅** {_date_line}  \n**🕐** {_time_line}  \n**📍** {_chart_city or '—'}"
            )
            st.divider()
            profile_name = st.text_input("Chart Name (unique)", value="", key="profile_name_input")

            if st.button("💾 Save / Update Chart"):
                if profile_name.strip() == "":
                    st.error("Please enter a name for the chart.")
                else:
                    # keep or initialize circuit names
                    _patterns = _current_chart.aspect_groups or []
                    saved_profiles = _get_saved_profiles()
                    if profile_name in saved_profiles and _patterns:
                        circuit_names = {
                            f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                            for i in range(len(_patterns))
                        }
                    elif _patterns:
                        circuit_names = {
                            f"circuit_name_{i}": f"Circuit {i+1}"
                            for i in range(len(_patterns))
                        }
                    else:
                        circuit_names = {}

                    # Prefer session-state geocode; fall back to the chart's own coords
                    # (chart always has valid lat/lon/timezone from calculation)
                    _save_lat    = lat if isinstance(lat, (int, float)) else _current_chart.latitude
                    _save_lon    = lon if isinstance(lon, (int, float)) else _current_chart.longitude
                    _save_tz     = tz_name or _current_chart.timezone

                    if not (_save_lat is not None and _save_lon is not None and _save_tz):
                        st.error("Chart is missing location/timezone data. Re-calculate it first.")
                        st.stop()

                    if _save_tz not in pytz.all_timezones:
                        # timezone stored on the chart comes from the calculation engine;
                        # if it's still unrecognised, just store it as-is (non-fatal)
                        pass

                    # Read birth data from the main birth form keys (with profile_ fallbacks)
                    _save_yr   = int(st.session_state.get("year")         or st.session_state.get("profile_year", 1990))
                    _save_mname = st.session_state.get("month_name")       or st.session_state.get("profile_month_name", "July")
                    _save_day  = int(st.session_state.get("day")           or st.session_state.get("profile_day", 1))
                    _save_city = st.session_state.get("city")              or st.session_state.get("profile_city", "")
                    # Convert 12-hour form time to 24-hour for storage
                    _h12_raw  = st.session_state.get("hour_12")
                    _min_raw  = st.session_state.get("minute_str")
                    _ampm_raw = st.session_state.get("ampm")
                    if _h12_raw and str(_h12_raw) != "--" and _min_raw and str(_min_raw) != "--" and _ampm_raw and str(_ampm_raw) != "--":
                        _h12 = int(_h12_raw)
                        _save_min = int(_min_raw)
                        if _ampm_raw == "PM" and _h12 != 12:
                            _save_hour = _h12 + 12
                        elif _ampm_raw == "AM" and _h12 == 12:
                            _save_hour = 0
                        else:
                            _save_hour = _h12
                    else:
                        _save_hour = int(st.session_state.get("profile_hour", 0))
                        _save_min  = int(st.session_state.get("profile_minute", 0))

                    try:
                        # Preserve existing group_id if updating a profile
                        existing_group_id = None
                        _existing_profiles = _get_saved_profiles()
                        if profile_name in _existing_profiles:
                            existing_group_id = _existing_profiles[profile_name].get("group_id")
                        
                        profile_data = {
                            "year":   _save_yr,
                            "month":  int(MONTH_NAMES.index(_save_mname) + 1),
                            "day":    _save_day,
                            "hour":   _save_hour,
                            "minute": _save_min,
                            "city":   _save_city,
                            "lat":    _save_lat,
                            "lon":    _save_lon,
                            "tz_name": _save_tz,
                            "circuit_names": circuit_names,
                            # Serialise the fully-computed chart for instant reload
                            "chart": _current_chart.to_json(),
                        }
                        # Preserve group_id if it exists
                        if existing_group_id:
                            profile_data["group_id"] = existing_group_id
                        
                        print(f"[ProfileManager] Saving profile '{profile_name}' for user {current_user_id}")
                        save_user_profile_db(current_user_id, profile_name, profile_data)
                        print(f"[ProfileManager] Save succeeded.")
                    except Exception as e:
                        import traceback
                        print(f"[ProfileManager] Save FAILED: {e}")
                        traceback.print_exc()
                        st.error(f"Could not save chart: {e}")
                    else:
                        st.success(f"Chart '{profile_name}' saved!")
                        st.rerun()

    # --- Load ---
    elif active_tab == "Load Chart":
        # Initialize group management functions with defaults if not provided
        if save_user_profile_group_db is None:
            from supabase_profiles import (
                save_user_profile_group_db as _save_group,
                load_user_profile_groups_db as _load_groups,
                load_user_profiles_by_group_db as _load_by_group,
                delete_user_profile_group_db as _delete_group,
            )
            save_user_profile_group_db = _save_group
            load_user_profile_groups_db = _load_groups
            load_user_profiles_by_group_db = _load_by_group
            delete_user_profile_group_db = _delete_group
        
        # --- New Group Button + Synastry Mode (visible once a chart is loaded) ---
        _has_loaded_chart = st.session_state.get("last_chart") is not None
        _btn_col, _syn_col = st.columns([1, 4])
        with _btn_col:
            if st.button("➕ New Group", key="new_group_btn"):
                st.session_state["_show_new_group_dialog"] = True
        with _syn_col:
            if _has_loaded_chart:
                def _on_synastry_toggle_pm():
                    # When turning synastry OFF, clear Chart 2 so it doesn't linger
                    if not st.session_state.get("synastry_mode", False):
                        st.session_state.pop("last_chart_2", None)
                        st.session_state.pop("chart_2_source", None)

                st.checkbox("👭 Synastry", key="synastry_mode", on_change=_on_synastry_toggle_pm)
                if st.session_state.get("synastry_mode"):
                    st.radio(
                        "Assign next profile to:",
                        ["Inner Chart", "Outer Chart"],
                        index=1,
                        key="pm_synastry_slot",
                        horizontal=True,
                    )

        # New group dialog (shown below the button row)
        if st.session_state.get("_show_new_group_dialog"):
            group_name = st.text_input("Group Name", key="new_group_input", placeholder="e.g., Family, Friends, etc.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Create", key="create_group_btn"):
                    if group_name and group_name.strip():
                        try:
                            save_user_profile_group_db(current_user_id, group_name.strip())
                            st.success(f"Group '{group_name}' created!")
                            st.session_state["_show_new_group_dialog"] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"Could not create group: {e}")
                    else:
                        st.error("Group name cannot be empty.")
            with c2:
                if st.button("Cancel", key="cancel_group_btn"):
                    st.session_state["_show_new_group_dialog"] = False
                    st.rerun()
        
        st.divider()
        
        # Load profiles organized by group
        try:
            profiles_by_group = load_user_profiles_by_group_db(current_user_id)
        except Exception as e:
            # If the groups table doesn't exist yet (first time), show setup instruction
            if "groups" in str(e).lower() or "relation" in str(e).lower():
                st.info(
                    "📋 Chart groups not yet set up. Run this SQL in your Supabase dashboard to enable groups:\n\n"
                    "```sql\n"
                    "create table if not exists public.user_profile_groups (\n"
                    "    id       uuid primary key default gen_random_uuid(),\n"
                    "    user_id  uuid not null references auth.users(id),\n"
                    "    group_name text not null,\n"
                    "    created_at timestamptz default now(),\n"
                    "    updated_at timestamptz default now(),\n"
                    "    unique (user_id, group_name)\n"
                    ");\n"
                    "alter table public.user_profile_groups enable row level security;\n"
                    "create policy \"users_own_profile_groups\" on public.user_profile_groups\n"
                    "    for all using (auth.uid() = user_id) with check (auth.uid() = user_id);\n"
                    "```\n\n"
                    "For now, your profiles are displayed without groups. After running the SQL, refresh the page."
                )
                # Fallback: show profiles flat without groups
                profiles_by_group = {"__ungrouped__": {"group_name": "All Charts", "profiles": _get_saved_profiles()}}
            else:
                raise
        
        if profiles_by_group:
            # Helper to format profile display
            def _format_profile_label(name: str, data: Dict[str, Any]) -> str:
                """Format profile info for display: [Name] - [MM/DD/YYYY] [HH:MM AM/PM] [City, St]"""
                try:
                    year = data.get("year", 1990)
                    month = data.get("month", 1)
                    day = data.get("day", 1)
                    hour = data.get("hour", 0)
                    minute = data.get("minute", 0)
                    city = data.get("city", "Unknown")
                    
                    # Format date as MM/DD/YYYY
                    date_str = f"{month:02d}/{day:02d}/{year}"
                    
                    # Convert to 12-hour format
                    h12 = hour % 12 or 12
                    ampm = "AM" if hour < 12 else "PM"
                    time_str = f"{h12:02d}:{minute:02d} {ampm}"
                    
                    return f"{name} - {date_str} {time_str} {city}"
                except Exception:
                    return name
            
            # Display each group as a collapsible section (even if empty, so user can see newly created groups)
            for group_id, group_data in sorted(
                profiles_by_group.items(),
                key=lambda x: (x[1]["group_name"] == "Ungrouped", x[1]["group_name"])
            ):
                group_name = group_data["group_name"]
                profiles_in_group = group_data["profiles"]
                profile_count = len(profiles_in_group)
                
                # Show all groups, even if empty (so user sees newly created ones)
                with st.expander(f"📁 {group_name} ({profile_count})", expanded=False):
                    if profiles_in_group:
                        for name, data in profiles_in_group.items():
                            col1, col2 = st.columns([4, 1])
                            
                            # Load button with formatted label
                            with col1:
                                label = _format_profile_label(name, data)
                                if st.button(label, key=f"load_{group_id}_{name}", use_container_width=True):
                                    _syn_on = st.session_state.get("synastry_mode", False)
                                    _syn_slot = st.session_state.get("pm_synastry_slot", "Outer Chart")
                                    if _syn_on and _syn_slot == "Outer Chart":
                                        # Load this profile as Chart 2 (outer / synastry chart)
                                        st.session_state["__pending_profile_load_2__"] = {
                                            "profile_name": name,
                                            "profile_data": data,
                                        }
                                    else:
                                        # Load as primary (inner) chart
                                        st.session_state["__pending_profile_load__"] = {
                                            "profile_name": name,
                                            "profile_data": data,
                                            "group_id": group_id,
                                        }
                                    st.rerun()
                            
                            # Group management popover
                            with col2:
                                with st.popover("⋯"):
                                    st.caption("Move to group")
                                    
                                    try:
                                        # Reuse profiles_by_group keys as group list
                                        # (avoids extra DB call per popover)
                                        group_options = {gid: gdata["group_name"] for gid, gdata in profiles_by_group.items()}
                                        
                                        # Current group indicator
                                        current_group_name = group_options.get(group_id, "__ungrouped__")
                                        st.caption(f"Currently in: **{current_group_name}**")
                                        
                                        # Option to ungroup (only if currently in a named group)
                                        if group_id != "__ungrouped__":
                                            if st.button("📭 Ungroup", key=f"ungroup_{group_id}_{name}"):
                                                # Move to ungrouped by updating payload
                                                updated_data = data.copy()
                                                updated_data["group_id"] = None
                                                save_user_profile_db(current_user_id, name, updated_data)
                                                st.success(f"Moved '{name}' to Ungrouped")
                                                st.rerun()
                                        
                                        # Select a group to move to
                                        group_choices = {gid: gname for gid, gname in group_options.items() if gid != group_id}
                                        if group_choices:
                                            selected_group_id = st.selectbox(
                                                "Move to:",
                                                options=list(group_choices.keys()),
                                                format_func=lambda x: group_choices[x],
                                                key=f"move_group_{group_id}_{name}"
                                            )
                                            if st.button("✓ Move", key=f"move_confirm_{group_id}_{name}"):
                                                # Update profile with new group_id
                                                updated_data = data.copy()
                                                if selected_group_id != "__ungrouped__":
                                                    updated_data["group_id"] = selected_group_id
                                                else:
                                                    updated_data["group_id"] = None
                                                save_user_profile_db(current_user_id, name, updated_data)
                                                st.success(f"Moved '{name}' to {group_options[selected_group_id]}")
                                                st.rerun()
                                    except Exception as e:
                                        st.error(f"Could not load groups: {e}")
                    else:
                        st.caption("📭 This group is empty. Add charts by saving them in the 'Add Chart' tab.")

            # quick-save circuit names into current profile
            _last_chart = st.session_state.get("last_chart")
            _patterns = _last_chart.aspect_groups if _last_chart else []
            if st.session_state.get("current_profile") and _patterns:
                if st.button("💾 Save Circuit Names to Current Chart", key="save_names_only"):
                    circuit_names = {
                        f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                        for i in range(len(_patterns))
                    }
                    prof_name = st.session_state["current_profile"]
                    profile_data = _get_saved_profiles().get(prof_name, {}).copy()

                    if not profile_data:
                        st.error("No chart data found. Load a chart first.")
                    else:
                        profile_data["circuit_names"] = circuit_names
                        # Refresh the stored chart object so it stays in sync
                        _curr_chart = st.session_state.get("last_chart")
                        if _curr_chart is not None:
                            profile_data["chart"] = _curr_chart.to_json()
                        save_user_profile_db(current_user_id, prof_name, profile_data)
                        st.session_state["saved_circuit_names"] = circuit_names.copy()
                        st.success("Circuit names updated.")
        else:
            st.info("No saved profiles yet.")

    # --- Delete (private, per-user) ---
    elif active_tab == "Delete Chart":
        saved_profiles = _get_saved_profiles()
        if saved_profiles:
            delete_choice = st.selectbox(
                "Select a chart to delete",
                options=sorted(saved_profiles.keys()),
                key="profile_delete"
            )

            if st.button("🗑️ Delete Selected Chart", key="priv_delete_ask"):
                st.session_state["priv_delete_target"] = delete_choice
                st.rerun()

            target = st.session_state.get("priv_delete_target")
            if target:
                st.warning(f"Are you sure you want to delete this chart: **{target}**?")
                d1, d2 = st.columns([1, 1], gap="small")
                with d1:
                    if st.button("Delete", key="priv_delete_yes", use_container_width=True):
                        delete_user_profile_db(current_user_id, target)
                        st.session_state.pop("priv_delete_target", None)
                        st.success(f"Deleted profile '{target}'.")
                        st.rerun()
                with d2:
                    if st.button("No!", key="priv_delete_no", use_container_width=True):
                        st.session_state.pop("priv_delete_target", None)
                        st.info("Delete canceled.")
                        st.rerun()
        else:
            st.info("No saved profiles yet.")

    return _get_saved_profiles()
