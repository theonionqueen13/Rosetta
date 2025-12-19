# donate_v2.py
from __future__ import annotations
from typing import Callable, Dict, Any, Optional, List
import streamlit as st
import datetime as dt
import pytz

def donate_chart(
    *,
    MONTH_NAMES: List[str],
    current_user_id: str,
    is_admin: Callable[[str], bool],
    community_save: Callable[[str, Dict[str, Any], Optional[str]], Any],
    community_list: Callable[..., List[Dict[str, Any]]],
    community_get: Callable[[Any], Optional[Dict[str, Any]]],
    community_delete: Callable[[Any], None],
    run_chart: Callable[[float, float, str], None],
    chart_ready: Optional[bool] = None,
    expander_title: str = "🧪 Donate Your Chart to Science 🧬",
) -> None:
    """
    Render the 'Donate Your Chart to Science' UI and handle publish/load/delete.

    Parameters
    ----------
    MONTH_NAMES : list[str]
        Month labels used for converting profile_month_name -> month index.
    current_user_id : str
        The signed-in user's id, used as submitted_by on donations.
    is_admin, community_* : callables
        Your data-layer functions for admin gating and CRUD on donated charts.
    run_chart : (lat, lon, tz_name) -> None
        Your existing chart compute function (3-arg version).
    chart_ready : bool | None
        If None, inferred from st.session_state['last_df'] is not None.
        If False, UI won’t render (no chart to donate).
    expander_title : str
        Title for the enclosing expander.
    """
    if chart_ready is None:
        chart_ready = st.session_state.get("last_df") is not None

    if not chart_ready:
        return  # nothing to show yet

    # NOTE: This function itself uses an expander.
    # Call it OUTSIDE any other expander to avoid nested-expander errors.
    with st.expander(expander_title):
        st.caption(
            "Optional participation: Donate a chart profile to the research dataset. "
            "Joylin may study donated charts for app development and pattern research."
        )

        # Info-only button
        if st.button("Whaaaat?", key="comm_info_btn"):
            st.session_state["comm_confirm_open"] = True
            st.session_state["comm_confirm_mode"] = "info"
            st.session_state.pop("comm_confirm_payload", None)
            st.session_state.pop("comm_confirm_name", None)

        comm_name = st.text_input("Name or Event", key="comm_profile_name")
        pub_c1, pub_c2 = st.columns([1, 1], gap="small")

        # ----- Donate current chart -----
        with pub_c1:
            if st.button("Donate current chart", key="comm_publish_btn"):
                valid = True
                lat = st.session_state.get("current_lat")
                lon = st.session_state.get("current_lon")
                tz_name = st.session_state.get("current_tz_name")

                if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and tz_name):
                    st.error("Enter a valid city (lat/lon/timezone lookup must succeed) before donating.")
                    valid = False
                else:
                    if tz_name not in pytz.all_timezones:
                        st.error(f"Unrecognized timezone '{tz_name}'. Refine the city and try again.")
                        valid = False

                if not (comm_name or "").strip():
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

        # ----- Final confirmation (publish/info) -----
        if st.session_state.get("comm_confirm_open"):
            mode = st.session_state.get("comm_confirm_mode", "info")
            confirm_text_publish = "✨Do you want to donate your chart to Science?💫"
            confirm_text_info = (
                "This is entirely voluntary. If you choose to donate your chart, it will only be available to the app admin (Joylin) for research and development. "
                "Joylin will NOT share your chart with others.\n\n"
                "Potential uses:\n\n"
                "• Testing this app's features across many charts\n\n"
                "• Studying patterns for the app's 'thinking brain'\n\n"
                "• Informing future data-science studies\n\n"
            )
            st.warning(confirm_text_publish if mode == "publish" else confirm_text_info)

            c_yes, c_no = st.columns([1, 1], gap="small")
            with c_yes:
                if st.button("Donate", key="comm_confirm_yes", use_container_width=True):
                    payload = st.session_state.get("comm_confirm_payload")
                    name_to_publish = st.session_state.get("comm_confirm_name", "")
                    if payload:
                        community_save(name_to_publish, payload, submitted_by=current_user_id)
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

        # ----- Admin-only browser -----
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

                    # handle clicks
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
                            run_chart(data["lat"], data["lon"], data["tz_name"])
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
