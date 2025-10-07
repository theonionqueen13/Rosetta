# toggles_v2.py
import streamlit as st

def render_circuit_toggles(
    patterns,
    shapes,
    singleton_map,
    saved_profiles,
    current_user_id,
    save_user_profile_db,
    load_user_profiles_db,
):
    """
    Renders the Circuits UI (checkboxes, expanders, bulk buttons, compass rose, sub-shapes)
    and handles saving circuit names.

    Returns:
        toggles (list[bool]), pattern_labels (list[str]), saved_profiles (dict)
    """
    # guard against None
    patterns = patterns or []
    shapes = shapes or []
    singleton_map = singleton_map or {}

    # ---------- Toggles ----------
    st.subheader("Circuits")

    # ---------- PRE-INIT (so keys exist before any widgets render) ----------
    # patterns & sub-shapes
    for i in range(len(patterns)):
        st.session_state.setdefault(f"toggle_pattern_{i}", False)
        for sh in [sh for sh in shapes if sh["parent"] == i]:
            st.session_state.setdefault(f"shape_{i}_{sh['id']}", False)

    # singleton planets (guard if not present)
    if singleton_map:
        for planet in singleton_map.keys():
            st.session_state.setdefault(f"singleton_{planet}", False)

    # we'll collect these as we render
    toggles = []
    pattern_labels = []

    # ---------- BULK ACTION HANDLERS (must run BEFORE widgets) ----------
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("Show All", key="btn_show_all_main"):
            # flip ON only the circuits (not sub-shapes, not singletons)
            for i in range(len(patterns)):
                st.session_state[f"toggle_pattern_{i}"] = True
            st.rerun()

    with b2:
        if st.button("Hide All", key="btn_hide_all_main"):
            # flip everything OFF
            for i in range(len(patterns)):
                st.session_state[f"toggle_pattern_{i}"] = False
                for sh in [sh for sh in shapes if sh["parent"] == i]:
                    st.session_state[f"shape_{i}_{sh['id']}"] = False
            st.session_state["toggle_compass_rose"] = False
            if singleton_map:
                for planet in singleton_map.keys():
                    st.session_state[f"singleton_{planet}"] = False
            st.rerun()

    # --- Compass Rose (independent overlay, ON by default) ---
    if "toggle_compass_rose" not in st.session_state:
        st.session_state["toggle_compass_rose"] = True
    st.checkbox("Compass Rose", key="toggle_compass_rose")

    # Pattern checkboxes + expanders
    half = (len(patterns) + 1) // 2
    left_patterns, right_patterns = st.columns(2)

    for i, component in enumerate(patterns):
        target_col = left_patterns if i < half else right_patterns
        checkbox_key = f"toggle_pattern_{i}"

        # circuit name session key
        circuit_name_key = f"circuit_name_{i}"
        default_label = f"Circuit {i+1}"
        if circuit_name_key not in st.session_state:
            st.session_state[circuit_name_key] = default_label

        # what shows where
        circuit_title  = st.session_state[circuit_name_key]   # shown on checkbox row
        members_label  = ", ".join(component)                 # shown in expander header

        with target_col:
            # checkbox row: [chip] Circuit N
            cbox = st.checkbox(f"{circuit_title}", key=checkbox_key)
            toggles.append(cbox)
            pattern_labels.append(circuit_title)

            # expander shows only the member list on its header
            with st.expander(members_label, expanded=False):
                # rename field
                st.text_input("Circuit name", key=circuit_name_key)

                # --- Auto-save when circuit name changes (your same logic) ---
                if st.session_state.get("current_profile"):
                    saved = st.session_state.get("saved_circuit_names", {})
                    current_name = st.session_state[circuit_name_key]
                    last_saved = saved.get(circuit_name_key, default_label)

                    if current_name != last_saved:
                        current = {
                            f"circuit_name_{j}": st.session_state.get(f"circuit_name_{j}", f"Circuit {j+1}")
                            for j in range(len(patterns))
                        }
                        profile_name = st.session_state["current_profile"]
                        payload = saved_profiles.get(profile_name, {}).copy()
                        payload["circuit_names"] = current
                        save_user_profile_db(current_user_id, profile_name, payload)
                        saved_profiles = load_user_profiles_db(current_user_id)
                        st.session_state["saved_circuit_names"] = current.copy()

                # --- Sub-shapes (uses callback to safely toggle parent circuit) ---
                parent_shapes = [sh for sh in shapes if sh["parent"] == i]
                shape_entries = []
                if parent_shapes:
                    st.markdown("**Sub-shapes detected:**")
                    for sh in parent_shapes:
                        label_text = f"{sh['type']}: {', '.join(str(m) for m in sh['members'])}"
                        unique_key = f"shape_{i}_{sh['id']}"
                        on = st.checkbox(
                            label_text,
                            key=unique_key,
                            value=st.session_state.get(unique_key, False),
                        )
                        shape_entries.append({"id": sh["id"], "on": on})
                else:
                    st.markdown("_(no sub-shapes found)_")

                shape_toggle_map = st.session_state.setdefault("shape_toggles_by_parent", {})
                shape_toggle_map[i] = shape_entries

    # --- Save Circuit Names button (only if edits exist) ---
    unsaved_changes = False
    if st.session_state.get("current_profile"):
        saved = st.session_state.get("saved_circuit_names", {})
        current = {
            f"circuit_name_{i}": st.session_state.get(f"circuit_name_{i}", f"Circuit {i+1}")
            for i in range(len(patterns))
        }
        if current != saved:
            unsaved_changes = True

        if unsaved_changes:
            st.markdown("---")
            if st.button("💾 Save Circuit Names"):
                profile_name = st.session_state["current_profile"]
                payload = saved_profiles.get(profile_name, {}).copy()
                payload["circuit_names"] = current
                save_user_profile_db(current_user_id, profile_name, payload)
                saved_profiles = load_user_profiles_db(current_user_id)
                st.session_state["saved_circuit_names"] = current.copy()

    return toggles, pattern_labels, saved_profiles
