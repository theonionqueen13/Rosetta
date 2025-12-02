import streamlit as st
from event_lookup_v2 import update_events_html_state
from lookup_v2 import GLYPHS, TOGGLE_ASPECTS

COMPASS_KEY = "ui_compass_overlay"

def render_circuit_toggles(
	patterns,
	shapes,
	singleton_map,
	saved_profiles,
	current_user_id,
	save_user_profile_db,
	load_user_profiles_db,
):
	# --- PRE-INIT (so keys exist before any widgets render) ---
	for i in range(len(patterns)):
		st.session_state.setdefault(f"toggle_pattern_{i}", False)
		for sh in [sh for sh in shapes if sh["parent"] == i]:
			st.session_state.setdefault(f"shape_{i}_{sh['id']}", False)
	if singleton_map:
		for planet in singleton_map.keys():
			st.session_state.setdefault(f"singleton_{planet}", False)

	st.session_state.setdefault(COMPASS_KEY, True)
	"""
	Renders the Circuits UI (checkboxes, expanders, bulk buttons, compass rose, sub-shapes)
	and handles saving circuit names.

	Returns:
		toggles (list[bool]), pattern_labels (list[str]), saved_profiles (dict)
	"""
	st.session_state.pop("events_block", None)
	# guards
	patterns = patterns or []
	shapes = shapes or []
	singleton_map = singleton_map or {}
	toggles: list[bool] = []
	pattern_labels: list[str] = []

	# --- Chart Mode Selector ---
	st.session_state.setdefault("chart_mode", "Circuits")
	mode_col1, mode_col2 = st.columns([1, 5])
	with mode_col1:
		chart_mode = st.radio(
			"Chart Mode",
			["Standard Chart", "Circuits"],
			index=0 if st.session_state.get("chart_mode") == "Standard Chart" else 1,
			key="__chart_mode_radio",
			horizontal=False,
		)
		if chart_mode != st.session_state.get("chart_mode"):
			st.session_state["chart_mode"] = chart_mode
			st.rerun()

	# --- Handle pending "Hide All" (from previous run) safely ---
	if st.session_state.get("__pending_hide_all__"):
		updates = {}
		for i in range(len(patterns)):
			updates[f"toggle_pattern_{i}"] = False
			for sh in [sh for sh in shapes if sh["parent"] == i]:
				updates[f"shape_{i}_{sh['id']}"] = False
		if singleton_map:
			for planet in singleton_map.keys():
				updates[f"singleton_{planet}"] = False
		updates[COMPASS_KEY] = False  # safe now; checkbox not yet instantiated
		st.session_state.update(updates)
		st.session_state["__pending_hide_all__"] = False
		st.rerun()
	
	# --- Handle pending "Show All" (from previous run) safely ---
	if st.session_state.get("__pending_show_all__"):
		updates = {}
		for i in range(len(patterns)):
			updates[f"toggle_pattern_{i}"] = True
		if singleton_map:
			for planet in singleton_map.keys():
				updates[f"singleton_{planet}"] = True
		updates[COMPASS_KEY] = True  # safe here, checkbox not yet instantiated
		st.session_state.update(updates)
		st.session_state["__pending_show_all__"] = False
		st.rerun()

	# ---------- Header + events panel ----------
	
	# Adjust header based on chart mode
	current_mode = st.session_state.get("chart_mode", "Circuits")
	header_text = "🗺️Circuits" if current_mode == "Circuits" else "Standard Chart"

	header_col, events_col, jump_col = st.columns([1, 6, 2])
	with header_col:
		st.subheader(header_text)
	with jump_col:
		st.markdown(
			'<a href="#ruler-hierarchies" style="display:inline-block;padding:0.25rem 0.75rem;background-color:#ff4b4b;color:white;text-decoration:none;border-radius:0.25rem;text-align:center;width:100%;">Jump to Houses & Rulers</a>',
			unsafe_allow_html=True
		)
	with events_col:
		# Reserve a dedicated spot for the events block so we can reliably
		# clear any prior render when a new chart is calculated.
		events_placeholder = st.empty()

		# Always compute and blank/overwrite first on every rerun
		update_events_html_state(
				st.session_state.get("chart_dt_utc"),
				events_path="events.jsonl",
				show_no_events=False,   # flip True if you want a soft message on no results
		)

		# Single, fixed render point. When there is no HTML, explicitly
		# empty the placeholder so stale content never lingers.
		html = st.session_state.get("events_lookup_html", "")
		if html:
				events_placeholder.markdown(html, unsafe_allow_html=True)
		else:
				events_placeholder.empty()
						
	st.divider()
	
	# ---------- Circuits Mode-Specific UI ----------
	if current_mode == "Circuits":
		c1, c2, c3, c4 = st.columns([2, 1, 1, 2])

		with c1:
			unknown_time = bool(
				st.session_state.get("chart_unknown_time")
				or st.session_state.get("profile_unknown_time")
			)
			label = "Compass Needle" if unknown_time else "Compass Rose"
			new_value = st.checkbox(label, key=COMPASS_KEY)

		# Track compass value change but do not rerun immediately
		prev_value = st.session_state.get("_last_compass_value")
		if new_value != prev_value:
			st.session_state["_last_compass_value"] = new_value
			st.session_state["_pending_compass_rerun"] = True

		with c2:
			if st.button("Show All", key="btn_show_all_main"):
				st.session_state["__pending_show_all__"] = True
				st.rerun()

		with c3:
			if st.button("Hide All", key="btn_hide_all_main"):
				# store desired state for next run instead of mutating live widget state
				st.session_state["__pending_hide_all__"] = True
				st.rerun()

		st.session_state.setdefault("label_style", "glyph")
		with c4:
			st.subheader("Single Placements")

			# --- ensure label style is fully synced before rendering ---
			old_style = st.session_state.get("label_style", "glyph")
			# The radio button writes to this key; read its current choice
			new_style = st.session_state.get("__label_style_choice", old_style)
			if new_style.lower() != old_style:
				st.session_state["label_style"] = new_style.lower()
				st.rerun()  # force full refresh so both chart + singles update instantly
			else:
				st.session_state["label_style"] = new_style.lower()

			# now use the up-to-date label style
			label_style = st.session_state["label_style"]
			want_glyphs = label_style == "glyph"

			if singleton_map:
				cols_per_row = min(8, max(1, len(singleton_map)))
				cols = st.columns(cols_per_row)
				for j, (planet, _) in enumerate(singleton_map.items()):
					with cols[j % cols_per_row]:
						key = f"singleton_{planet}"
						label_text = GLYPHS.get(planet, planet) if want_glyphs else planet
						if key not in st.session_state:
							st.checkbox(label_text, value=False, key=key)
						else:
							st.checkbox(label_text, key=key)
			else:
				st.markdown("_(none)_")
	else:
		# ---------- Standard Chart Mode UI ----------
		synastry_mode = st.session_state.get("synastry_mode", False)
		
		# Create columns for compass checkbox and swap button
		compass_col, swap_col = st.columns([1, 1])
		
		with compass_col:
			unknown_time = bool(
				st.session_state.get("chart_unknown_time")
				or st.session_state.get("profile_unknown_time")
			)
			label = "Compass Needle" if unknown_time else "Compass Rose"
			new_value = st.checkbox(label, key=COMPASS_KEY)

			# Track compass value change but do not rerun immediately
			prev_value = st.session_state.get("_last_compass_value")
			if new_value != prev_value:
				st.session_state["_last_compass_value"] = new_value
				st.session_state["_pending_compass_rerun"] = True
		
		with swap_col:
			if synastry_mode:
				# Define swap function that runs in the on_click callback
				def swap_charts_callback():
					"""Swap all chart data between Chart 1 and Chart 2"""
					# Swap radio button selections
					test_chart_1 = st.session_state.get("test_chart_radio", "Custom")
					test_chart_2 = st.session_state.get("test_chart_2", "Custom")
					st.session_state["test_chart_radio"] = test_chart_2
					st.session_state["test_chart_2"] = test_chart_1
					
					# Swap last_test_chart trackers
					last_1 = st.session_state.get("last_test_chart")
					last_2 = st.session_state.get("last_test_chart_2")
					st.session_state["last_test_chart"] = last_2
					st.session_state["last_test_chart_2"] = last_1
					
					# Define data keys to swap
					swap_pairs = [
						("year", "year_2"),
						("month_name", "month_name_2"),
						("day", "day_2"),
						("hour_12", "hour_12_2"),
						("minute_str", "minute_str_2"),
						("ampm", "ampm_2"),
						("city", "city_2"),
						("last_df", "last_df_2"),
						("plot_data", "plot_data_2"),
						("chart_dt_utc", "chart_dt_utc_2"),
						("chart_unknown_time", "chart_unknown_time_2"),
					]
					
					# Perform the swap
					for key1, key2 in swap_pairs:
						val1 = st.session_state.get(key1)
						val2 = st.session_state.get(key2)
						st.session_state[key1] = val2
						st.session_state[key2] = val1
					
					# Clear cached figures
					st.session_state["render_fig"] = None
					st.session_state["render_result"] = None
				
				# Button with on_click callback
				st.button("Swap Chart Wheels", key="swap_chart_wheels", on_click=swap_charts_callback)
		
		st.markdown("---")

	circuits_col, spacer_col, options_col = st.columns([3, 1, 2])
	
	# Add Standard Chart aspect toggles in left column
	if current_mode == "Standard Chart":
		with circuits_col:
			# Check if we're in synastry mode
			synastry_mode = st.session_state.get("synastry_mode", False)
			
			if synastry_mode:
				# Synastry mode: show aspect group toggles
				st.subheader("Aspect Groups")
				
				# Get chart names
				chart1_name = st.session_state.get("test_chart_radio", "Chart 1")
				if chart1_name == "Custom":
					chart1_name = "Chart 1"
				chart2_name = st.session_state.get("test_chart_2", "Chart 2")
				if chart2_name == "Custom":
					chart2_name = "Chart 2"
				
				# Initialize synastry aspect group toggles
				st.session_state.setdefault("synastry_aspects_inter", True)  # Default on
				st.session_state.setdefault("synastry_aspects_chart1", False)  # Default off
				st.session_state.setdefault("synastry_aspects_chart2", False)  # Default off
				
				# Aspect group toggles
				st.checkbox(f"{chart1_name} ↔ {chart2_name}", key="synastry_aspects_inter")
				st.checkbox(f"{chart1_name} Aspects", key="synastry_aspects_chart1")
				st.checkbox(f"{chart2_name} Aspects", key="synastry_aspects_chart2")
				
				st.markdown("---")
			with st.expander("Additional Aspects"):
				
				# Get current label style
				label_style = st.session_state.get("label_style", "glyph")
				want_glyphs = label_style == "glyph"
				
				# Select All checkbox
				select_all_key = "aspect_toggle_select_all"
				st.session_state.setdefault(select_all_key, False)
				select_all = st.checkbox("Select All", key=select_all_key)
				
				# If select all state changed, update all toggles
				if select_all != st.session_state.get("_last_select_all_state", False):
					for body_name in TOGGLE_ASPECTS.keys():
						st.session_state[f"aspect_toggle_{body_name}"] = select_all
					st.session_state["_last_select_all_state"] = select_all
					st.rerun()
				
				# Create checkboxes for TOGGLE_ASPECTS in a grid
				toggle_bodies = list(TOGGLE_ASPECTS.keys())
				cols_per_row = 4
				cols = st.columns(cols_per_row)
				
				for j, body_name in enumerate(toggle_bodies):
					with cols[j % cols_per_row]:
						key = f"aspect_toggle_{body_name}"
						label_text = GLYPHS.get(body_name, body_name) if want_glyphs else body_name
						st.session_state.setdefault(key, False)
						st.checkbox(label_text, key=key)

	with spacer_col:
		st.write("")  # just a spacer

	with circuits_col:
		# Only show circuit patterns in Circuits mode
		if current_mode == "Circuits":
			# Pattern checkboxes + expanders
			half = (len(patterns) + 1) // 2
			left_patterns, right_patterns = st.columns(2)

			# Get current label style
			label_style = st.session_state.get("label_style", "glyph")
			want_glyphs = label_style == "glyph"

			for i, component in enumerate(patterns):
				target_col = left_patterns if i < half else right_patterns
				checkbox_key = f"toggle_pattern_{i}"

				# circuit name session key
				circuit_name_key = f"circuit_name_{i}"
				default_label = f"Circuit {i+1}"
				st.session_state.setdefault(circuit_name_key, default_label)

				circuit_title = st.session_state[circuit_name_key]  # shown on checkbox row
				# Apply glyph/text style to planet names in expander header
				if want_glyphs:
					members_label = ", ".join(GLYPHS.get(planet, planet) for planet in component)
				else:
					members_label = ", ".join(component)

				with target_col:
					cbox = st.checkbox(f"{circuit_title}", key=checkbox_key)
					toggles.append(cbox)
					pattern_labels.append(circuit_title)

					with st.expander(members_label, expanded=False):
						st.text_input("Circuit name", key=circuit_name_key)

						# Auto-save when circuit name changes
						if st.session_state.get("current_profile"):
							saved = st.session_state.get("saved_circuit_names", {})
							current_name = st.session_state[circuit_name_key]
							last_saved = saved.get(circuit_name_key, default_label)
							if current_name != last_saved:
								current = {
									f"circuit_name_{j}": st.session_state.get(
										f"circuit_name_{j}", f"Circuit {j+1}"
									)
									for j in range(len(patterns))
								}
								profile_name = st.session_state["current_profile"]
								payload = saved_profiles.get(profile_name, {}).copy()
								payload["circuit_names"] = current
								save_user_profile_db(current_user_id, profile_name, payload)
								saved_profiles = load_user_profiles_db(current_user_id)
								st.session_state["saved_circuit_names"] = current.copy()

						# Sub-shapes
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

						shape_toggle_map = st.session_state.setdefault(
							"shape_toggles_by_parent", {}
						)
						shape_toggle_map[i] = shape_entries

			# Save Circuit Names (only if edits exist)
			if st.session_state.get("current_profile"):
				saved = st.session_state.get("saved_circuit_names", {})
				current = {
					f"circuit_name_{i}": st.session_state.get(
						f"circuit_name_{i}", f"Circuit {i+1}"
					)
					for i in range(len(patterns))
				}
				if current != saved:
					st.markdown("---")
					if st.button("💾 Save Circuit Names"):
						profile_name = st.session_state["current_profile"]
						payload = saved_profiles.get(profile_name, {}).copy()
						payload["circuit_names"] = current
						save_user_profile_db(current_user_id, profile_name, payload)
						saved_profiles = load_user_profiles_db(current_user_id)
						st.session_state["saved_circuit_names"] = current.copy()

	# ---------- RIGHT: house system / label style / dark mode ----------
	with options_col:
		# Only show these after a chart exists
		if st.session_state.get("last_df") is not None:
			# House selector moved to dispositor graph section
			# from house_selector_v2 import render_house_system_selector
			# render_house_system_selector()

			# --- Label Style (keep visual location, fix instant sync) ---
			st.session_state.setdefault("label_style", "glyph")
			old_style = st.session_state["label_style"]
			label_default_is_glyph = old_style == "glyph"

			label_choice = st.radio(
				"Label Style",
				["Text", "Glyph"],
				index=(1 if label_default_is_glyph else 0),
				horizontal=True,
				key="__label_style_choice_main",  # unique key
			)
			new_style = label_choice.lower()

			# Update session + rerun instantly if changed
			if new_style != old_style:
				st.session_state["label_style"] = new_style
				st.rerun()
			else:
				st.session_state["label_style"] = new_style

			# Dark mode → persist to session
			st.session_state.setdefault("dark_mode", False)
			st.checkbox("🌙 Dark Mode", key="dark_mode")

	# If compass value changed, trigger a single safe rerun *after* all widgets exist
	if st.session_state.get("_pending_compass_rerun"):
		st.session_state["_pending_compass_rerun"] = False
		st.rerun()

	# return AFTER both columns render
	chart_mode = st.session_state.get("chart_mode", "Circuits")
	
	# Collect aspect toggles for Standard Chart mode
	aspect_toggles = {}
	if chart_mode == "Standard Chart":
		for body_name in TOGGLE_ASPECTS.keys():
			key = f"aspect_toggle_{body_name}"
			aspect_toggles[body_name] = st.session_state.get(key, False)
	
	return toggles, pattern_labels, saved_profiles, chart_mode, aspect_toggles

