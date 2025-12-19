# profile_manager_v2.py
from __future__ import annotations
import streamlit as st
import pytz
from typing import Callable, Dict, Any, Optional, List

def ensure_profile_session_defaults(month_names: List[str]) -> None:
    """Create the session keys this panel expects before any widgets render."""
    st.session_state.setdefault("current_profile", None)
    st.session_state.setdefault("active_profile_tab", "Load Profile")
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

    # ---- data load (safe to call repeatedly) ----
    saved_profiles: Dict[str, Any] = load_user_profiles_db(current_user_id)

    # =====================
    # 👤 Profile Manager UI
    # =====================
    tab_labels = ["Add Profile", "Load Profile", "Delete Profile"]
    default_tab = st.session_state.get("active_profile_tab", "Load Profile")
    if default_tab not in tab_labels:
        default_tab = tab_labels[0]

    active_tab = st.radio(
        "👤 Chart Profile Manager",
        tab_labels,
        index=tab_labels.index(default_tab),
        horizontal=True,
        key="profile_tab_selector",
    )
    st.session_state["active_profile_tab"] = active_tab

    # --- Add ---
    if active_tab == "Add Profile":
        profile_name = st.text_input("Profile Name (unique)", value="", key="profile_name_input")

        if st.button("💾 Save / Update Profile"):
            if profile_name.strip() == "":
                st.error("Please enter a name for the profile.")
            else:
                # keep or initialize circuit names
                if profile_name in saved_profiles and "patterns" in st.session_state:
                    circuit_names = {
                        f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                        for i in range(len(st.session_state.patterns))
                    }
                elif "patterns" in st.session_state:
                    circuit_names = {
                        f"circuit_name_{i}": f"Circuit {i+1}"
                        for i in range(len(st.session_state.patterns))
                    }
                else:
                    circuit_names = {}

                # require valid geocode before saving
                if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and tz_name):
                    st.error("Please enter a valid city (lat/lon/timezone lookup must succeed) before saving the profile.")
                    st.stop()

                if tz_name not in pytz.all_timezones:
                    st.error(f"Unrecognized timezone '{tz_name}'. Please refine the city and try again.")
                    st.stop()

                profile_data = {
                    "year":   int(st.session_state.get("profile_year", 1990)),
                    "month":  int(MONTH_NAMES.index(st.session_state.get("profile_month_name", "July")) + 1),
                    "day":    int(st.session_state.get("profile_day", 1)),
                    "hour":   int(st.session_state.get("profile_hour", 0)),
                    "minute": int(st.session_state.get("profile_minute", 0)),
                    "city":   st.session_state.get("profile_city", ""),
                    "lat":    lat,
                    "lon":    lon,
                    "tz_name": tz_name,
                    "circuit_names": circuit_names,
                }

                try:
                    save_user_profile_db(current_user_id, profile_name, profile_data)
                except Exception as e:
                    st.error(f"Could not save profile: {e}")
                    st.stop()
                else:
                    st.success(f"Profile '{profile_name}' saved!")
                    saved_profiles = load_user_profiles_db(current_user_id)

    # --- Load ---
    elif active_tab == "Load Profile":
        if saved_profiles:
            with st.expander("Saved Profiles", expanded=False):
                cols = st.columns(2)
                for i, (name, data) in enumerate(saved_profiles.items()):
                    col = cols[i % 2]
                    with col:
                        if st.button(name, key=f"load_{name}"):
                            st.session_state["_loaded_profile"] = data
                            st.session_state["current_profile"] = name
                            st.session_state["profile_loaded"] = True

                            # restore canonical keys
                            st.session_state["profile_year"] = data["year"]
                            st.session_state["profile_month_name"] = MONTH_NAMES[data["month"] - 1]
                            st.session_state["profile_day"] = data["day"]
                            st.session_state["profile_hour"] = data["hour"]
                            st.session_state["profile_minute"] = data["minute"]
                            st.session_state["profile_city"] = data["city"]

                            st.session_state["hour_val"] = data["hour"]
                            st.session_state["minute_val"] = data["minute"]
                            st.session_state["city_input"] = data["city"]

                            st.session_state["last_location"] = data["city"]
                            st.session_state["last_timezone"] = data.get("tz_name")

                            # restore circuit names
                            if "circuit_names" in data:
                                for key, val in data["circuit_names"].items():
                                    st.session_state[key] = val
                                st.session_state["saved_circuit_names"] = data["circuit_names"].copy()
                            else:
                                st.session_state["saved_circuit_names"] = {}

                            # run chart if location is valid
                            if any(v is None for v in (data.get("lat"), data.get("lon"), data.get("tz_name"))):
                                st.error(f"Profile '{name}' is missing location/timezone info. Re-save it after a successful city lookup.")
                            else:
                                run_chart(data["lat"], data["lon"], data["tz_name"],)
                                st.session_state["chart_ready"] = True
                                st.success(f"Profile '{name}' loaded and chart calculated!")
                                st.rerun()

            # quick-save circuit names into current profile
            if st.session_state.get("current_profile") and "patterns" in st.session_state:
                if st.button("💾 Save Circuit Names to Current Profile", key="save_names_only"):
                    circuit_names = {
                        f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                        for i in range(len(st.session_state.patterns))
                    }
                    profiles = load_user_profiles_db(current_user_id)
                    prof_name = st.session_state["current_profile"]
                    profile_data = profiles.get(prof_name, {}).copy()

                    if not profile_data:
                        st.error("No profile data found. Load a profile first.")
                    else:
                        profile_data["circuit_names"] = circuit_names
                        save_user_profile_db(current_user_id, prof_name, profile_data)
                        st.session_state["saved_circuit_names"] = circuit_names.copy()
                        st.success("Circuit names updated.")
        else:
            st.info("No saved profiles yet.")

    # --- Delete (private, per-user) ---
    elif active_tab == "Delete Profile":
        saved_profiles = load_user_profiles_db(current_user_id)
        if saved_profiles:
            delete_choice = st.selectbox(
                "Select a profile to delete",
                options=sorted(saved_profiles.keys()),
                key="profile_delete"
            )

            if st.button("🗑️ Delete Selected Profile", key="priv_delete_ask"):
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

    return saved_profiles
