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

def render_profile_manager(
    *,
    MONTH_NAMES: List[str],
    current_user_id: str,
    run_chart: Callable[[float, float, str, str], None],
    _selected_house_system: Callable[[], str],
    save_user_profile_db: Callable[[str, str, Dict[str, Any]], None],
    load_user_profiles_db: Callable[[str], Dict[str, Any]],
    delete_user_profile_db: Callable[[str, str], None],
    community_save: Callable[[str, Dict[str, Any]], Any],
    community_list: Callable[..., List[Dict[str, Any]]],
    community_get: Callable[[Any], Optional[Dict[str, Any]]],
    community_delete: Callable[[Any], None],
    is_admin: Callable[[str], bool],
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
                                run_chart(data["lat"], data["lon"], data["tz_name"], _selected_house_system())
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
    
    if chart_ready:
        # ===============================
        # 🧪 Donate Your Chart to Science
        # ===============================
        with st.expander("🧪 Donate Your Chart to Science 🧬"):
            st.caption(
                "Optional participation: Donate a chart profile to the research dataset. "
                "Joylin may study donated charts for app development and pattern research."
            )

            if st.button("Whaaaat?", key="comm_info_btn"):
                st.session_state["comm_confirm_open"] = True
                st.session_state["comm_confirm_mode"] = "info"
                st.session_state.pop("comm_confirm_payload", None)
                st.session_state.pop("comm_confirm_name", None)

            comm_name = st.text_input("Name or Event", key="comm_profile_name")
            pub_c1, pub_c2 = st.columns([1, 1], gap="small")

            with pub_c1:
                if st.button("Donate current chart", key="comm_publish_btn"):
                    valid = True
                    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and tz_name):
                        st.error("Enter a valid city (lat/lon/timezone lookup must succeed) before donating.")
                        valid = False
                    else:
                        if tz_name not in pytz.all_timezones:
                            st.error(f"Unrecognized timezone '{tz_name}'. Refine the city and try again.")
                            valid = False
                    if not comm_name.strip():
                        st.error("Please provide a label for the donated chart.")
                        valid = False

                    if valid:
                        circuit_names = {
                            f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
                            for i in range(len(st.session_state.get("patterns", [])))
                        }
                        payload = {
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
                        st.session_state["comm_confirm_open"] = True
                        st.session_state["comm_confirm_mode"] = "publish"
                        st.session_state["comm_confirm_name"] = comm_name.strip()
                        st.session_state["comm_confirm_payload"] = payload

            with pub_c2:
                st.info("100% optional!")

            if st.session_state.get("comm_confirm_open"):
                mode = st.session_state.get("comm_confirm_mode", "info")
                confirm_text_publish = "✨Do you want to donate your chart to Science?💫"
                confirm_text_info = (
                    "This is entirely voluntary. If you choose to donate your chart, it will only be available to the app admin (Joylin) for research and development. "
                    "Joylin will NOT share your chart with others.\n\n"
                    "Potential uses:\n\n"
                    "• Testing this app's features throughout development to make sure that they work on many charts\n\n"
                    "• Studying patterns in astrology for further development of the 'thinking brain' of the app\n\n"
                    "• Long-term, this will inform studies with a data scientist.\n\n"
                )

                st.warning(confirm_text_publish if mode == "publish" else confirm_text_info)

                c_yes, c_no = st.columns([1, 1], gap="small")
                with c_yes:
                    if st.button("Donate", key="comm_confirm_yes", use_container_width=True):
                        payload = st.session_state.get("comm_confirm_payload")
                        name_to_publish = st.session_state.get("comm_confirm_name", "")
                        if payload:
                            community_save(name_to_publish, payload)  # assumes admin context inside
                            st.success(f"Thank you! Donated as “{name_to_publish}”.")
                        else:
                            st.info("This was an info-only view. Click “Donate current chart” first.")
                        for k in ("comm_confirm_open", "comm_confirm_mode", "comm_confirm_name", "comm_confirm_payload"):
                            st.session_state.pop(k, None)
                        st.rerun()

                with c_no:
                    if st.button("Cancel", key="comm_confirm_no", use_container_width=True):
                        for k in ("comm_confirm_open", "comm_confirm_mode", "comm_confirm_name", "comm_confirm_payload"):
                            st.session_state.pop(k, None)
                        st.info("No problem—nothing was donated.")
                        st.rerun()

            # Admin-only browser
            if is_admin(current_user_id):
                st.markdown("**Browse Donated Charts (admin-only)**")
                rows = community_list(limit=300)

                if not rows:
                    st.caption("No donated charts yet.")
                else:
                    for r in rows:
                        by = r.get("submitted_by", "unknown")
                        confirm_id = st.session_state.get("comm_delete_confirm_id")

                        with st.container(border=True):
                            st.markdown(f"**{r['profile_name']}** · submitted by **{by}**")

                            b1, b2 = st.columns([1, 1], gap="small")
                            with b1:
                                load_clicked = st.button("Load", key=f"comm_load_{r['id']}", use_container_width=True)

                            with b2:
                                if confirm_id == r["id"]:
                                    st.warning("Delete this donated chart?")
                                    ask = False
                                else:
                                    ask = st.button("Delete", key=f"comm_delete_{r['id']}", use_container_width=True)

                            if confirm_id == r["id"]:
                                cdel1, cdel2 = st.columns([1, 1], gap="small")
                                with cdel1:
                                    really = st.button("Delete", key=f"comm_delete_yes_{r['id']}", use_container_width=True)
                                with cdel2:
                                    cancel = st.button("No!", key=f"comm_delete_no_{r['id']}", use_container_width=True)
                            else:
                                really = cancel = False

                        # --- handle clicks ---
                        if load_clicked:
                            data = r["payload"]
                            st.session_state["_loaded_profile"] = data
                            st.session_state["current_profile"] = f"community:{r['id']}"
                            st.session_state["profile_loaded"] = True

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

                            if "circuit_names" in data:
                                for key, val in data["circuit_names"].items():
                                    st.session_state[key] = val
                                st.session_state["saved_circuit_names"] = data["circuit_names"].copy()
                            else:
                                st.session_state["saved_circuit_names"] = {}

                            if any(v is None for v in (data.get("lat"), data.get("lon"), data.get("tz_name"))):
                                st.error("This donated profile is missing location/timezone info.")
                            else:
                                run_chart(data["lat"], data["lon"], data["tz_name"], _selected_house_system())
                                st.session_state["chart_ready"] = True
                                st.success(f"Loaded donated profile: {r['profile_name']}")
                                st.rerun()

                        if ask:
                            st.session_state["comm_delete_confirm_id"] = r["id"]
                            st.rerun()

                        if cancel:
                            st.session_state.pop("comm_delete_confirm_id", None)
                            st.info("Delete canceled.")
                            st.rerun()

                        if really:
                            rec = community_get(r["id"])
                            if rec:
                                community_delete(r["id"])
                                st.session_state.pop("comm_delete_confirm_id", None)
                                st.success(f"Deleted donated profile: {r['profile_name']}")
                                st.rerun()
                            else:
                                st.error("Record not found.")

    # final return so caller can reuse refreshed dict if needed
    return saved_profiles
