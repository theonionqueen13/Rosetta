import streamlit as st
from event_lookup_v2 import update_events_html_state
from models_v2 import static_db

GLYPHS = static_db.GLYPHS
TOGGLE_ASPECTS = static_db.TOGGLE_ASPECTS
ASPECTS = static_db.ASPECTS

COMPASS_KEY = "ui_compass_overlay"
COMPASS_KEY_2 = "ui_compass_overlay_2"  # separate overlay toggle for second chart (biwheel)

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

	# Pre-init Connected Circuits Chart 2 shape toggle keys.
	# These must exist before any widget render so Streamlit doesn't complain
	# about missing keys when the circuit expanders open.
	if st.session_state.get("synastry_mode") and st.session_state.get("circuit_submode") == "Connected Circuits":
		_cc_shapes2_init = st.session_state.get("circuit_connected_shapes2", {})
		for _ci in range(len(patterns)):
			for _sh2 in _cc_shapes2_init.get(_ci, []):
				st.session_state.setdefault(f"cc_shape_{_ci}_{_sh2['id']}", False)

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

	# ensure compass keys exist before any widgets render
	st.session_state.setdefault(COMPASS_KEY, True)
	st.session_state.setdefault(COMPASS_KEY_2, True)
	# track previous checkbox values for delayed rerun
	st.session_state.setdefault("_last_compass_value", st.session_state.get(COMPASS_KEY, False))
	st.session_state.setdefault("_last_compass_value_2", st.session_state.get(COMPASS_KEY_2, False))

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
		updates[COMPASS_KEY_2] = False
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
		updates[COMPASS_KEY_2] = True
		st.session_state.update(updates)
		st.session_state["__pending_show_all__"] = False
		st.rerun()

	# ---------- Header + events panel ----------
	
	# Adjust header based on chart mode
	chart_mode = st.session_state.get("chart_mode", "Circuits")
	header_text = "🗺️Circuits" if chart_mode == "Circuits" else "Standard Chart"

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
	if chart_mode == "Circuits":
		# Allow two circuit view modes when in Circuit chart mode
		st.session_state.setdefault("circuit_submode", "Combined Circuits")
		submode = st.radio(
			"Circuit View Mode",
			["Combined Circuits", "Connected Circuits"],
			index=0 if st.session_state.get("circuit_submode") == "Combined Circuits" else 1,
			key="__circuit_submode_radio",
			horizontal=False,
		)
		if submode != st.session_state.get("circuit_submode"):
			st.session_state["circuit_submode"] = submode
			st.rerun()

		c1, c2, c3, c4 = st.columns([2, 1, 1, 2])

		with c1:
			synastry_mode = st.session_state.get("synastry_mode", False)
			# chart names for labeling
			chart1_name = st.session_state.get("test_chart_radio", "Chart 1")
			if chart1_name == "Custom":
				chart1_name = "Chart 1"
			unknown_time1 = bool(
				st.session_state.get("chart_unknown_time")
				or st.session_state.get("profile_unknown_time")
			)
			label1 = f"{chart1_name} {'Compass Needle' if unknown_time1 else 'Compass Rose'}"
			new_value = st.checkbox(label1, key=COMPASS_KEY)
			
			# second chart toggle if synastry
			if synastry_mode:
				chart2_name = st.session_state.get("test_chart_2", "Chart 2")
				if chart2_name == "Custom":
					chart2_name = "Chart 2"
				unknown_time2 = bool(
					st.session_state.get("chart_unknown_time_2")
					or st.session_state.get("profile_unknown_time")
				)
				label2 = f"{chart2_name} {'Compass Needle' if unknown_time2 else 'Compass Rose'}"
				new_value2 = st.checkbox(label2, key=COMPASS_KEY_2)

		# Track compass value change but do not rerun immediately
		prev_value = st.session_state.get("_last_compass_value")
		if new_value != prev_value:
			st.session_state["_last_compass_value"] = new_value
			st.session_state["_pending_compass_rerun"] = True
		# track second
		if synastry_mode:
			prev2 = st.session_state.get("_last_compass_value_2")
			if new_value2 != prev2:
				st.session_state["_last_compass_value_2"] = new_value2
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
			# use chart names for labels
			chart1_name = st.session_state.get("test_chart_radio", "Chart 1")
			if chart1_name == "Custom":
				chart1_name = "Chart 1"
			unknown_time1 = bool(
				st.session_state.get("chart_unknown_time")
				or st.session_state.get("profile_unknown_time")
			)
			label1 = f"{chart1_name} {'Compass Needle' if unknown_time1 else 'Compass Rose'}"
			new_value = st.checkbox(label1, key=COMPASS_KEY)
			
			# optionally show second chart toggle
			synastry_mode = st.session_state.get("synastry_mode", False)
			if synastry_mode:
				chart2_name = st.session_state.get("test_chart_2", "Chart 2")
				if chart2_name == "Custom":
					chart2_name = "Chart 2"
				unknown_time2 = bool(
					st.session_state.get("chart_unknown_time_2")
					or st.session_state.get("profile_unknown_time")
				)
				label2 = f"{chart2_name} {'Compass Needle' if unknown_time2 else 'Compass Rose'}"
				new_value2 = st.checkbox(label2, key=COMPASS_KEY_2)
		
			# Track compass value change but do not rerun immediately
			prev_value = st.session_state.get("_last_compass_value")
			if new_value != prev_value:
				st.session_state["_last_compass_value"] = new_value
				st.session_state["_pending_compass_rerun"] = True
			# second
			if synastry_mode:
				prev2 = st.session_state.get("_last_compass_value_2")
				if new_value2 != prev2:
					st.session_state["_last_compass_value_2"] = new_value2
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
	if chart_mode == "Standard Chart":
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
		# Get synastry and circuit mode state
		synastry_mode = st.session_state.get("synastry_mode", False)
		circuit_submode = st.session_state.get("circuit_submode", "Combined Circuits")
		
		# Combined Circuits mode in synastry: show only shapes, grouped by type
		if chart_mode == "Circuits" and synastry_mode and circuit_submode == "Combined Circuits":
			# Get current label style
			label_style = st.session_state.get("label_style", "glyph")
			want_glyphs = label_style == "glyph"
			
			if shapes:
				st.subheader("Combined Shapes")
				
				# Group shapes by type
				shapes_by_type: dict[str, list] = {}
				for sh in shapes:
					shape_type = sh.get("type", "Unknown")
					if shape_type not in shapes_by_type:
						shapes_by_type[shape_type] = []
					shapes_by_type[shape_type].append(sh)
				
				# Node counts from patterns_v2.py shape detection:
				# - Envelope: combinations(R, 5) → 5 nodes
				# - Grand Cross, Mystic Rectangle, Cradle, Kite: combinations(R, 4) → 4 nodes
				# - Lightning Bolt: [q1, q2, r1, r2] → 4 nodes
				# - Grand Trine, T-Square, Wedge, Sextile Wedge: combinations(R, 3) → 3 nodes
				# - Yod, Wide Yod, Unnamed: [a, b, c] → 3 nodes
				SHAPE_NODE_COUNTS = {
					"Envelope": 5,
					"Grand Cross": 4,
					"Mystic Rectangle": 4,
					"Cradle": 4,
					"Kite": 4,
					"Lightning Bolt": 4,
					"Grand Trine": 3,
					"T-Square": 3,
					"Wedge": 3,
					"Sextile Wedge": 3,
					"Yod": 3,
					"Wide Yod": 3,
					"Unnamed": 3,
					"Remainder": 2,  # variable, but listed last
				}
				
				# Sort shape types by node count (descending), then alphabetically
				sorted_types = sorted(
					shapes_by_type.keys(),
					key=lambda t: (-SHAPE_NODE_COUNTS.get(t, 1), t)
				)
				
				# Render shapes grouped by type in two columns of expanders
				half = (len(sorted_types) + 1) // 2
				col_left, col_right = st.columns(2)
				for idx, shape_type in enumerate(sorted_types):
					type_shapes = shapes_by_type[shape_type]
					node_count = SHAPE_NODE_COUNTS.get(shape_type, len(type_shapes[0].get("members", [])) if type_shapes else 2)
					# choose column
					target_col = col_left if idx < half else col_right
					with target_col:
						with st.expander(f"**{shape_type}** – {len(type_shapes)} found", expanded=False):
							for sh in type_shapes:
								# Format members by chart origin
								members = sh.get("members", [])
								# determine chart names
								chart1_name = st.session_state.get("test_chart_radio", "Chart 1")
								if chart1_name == "Custom":
									chart1_name = "Chart 1"
								chart2_name = st.session_state.get("test_chart_2", "Chart 2")
								if chart2_name == "Custom":
									chart2_name = "Chart 2"
								
								members1 = [m for m in members if not m.endswith("_2")]
								members2 = [m[:-2] for m in members if m.endswith("_2")]
								
								def fmt_list(lst):
									if want_glyphs:
										return ", ".join(GLYPHS.get(m, m) for m in lst)
									else:
										return ", ".join(lst)
								
								members_label = f"{chart1_name}: {fmt_list(members1)}"
								if members2:
									members_label += f"; {chart2_name}: {fmt_list(members2)}"
								# Create unique key for this shape
								parent = sh.get("parent", 0)
								shape_id = sh["id"]
								unique_key = f"shape_{parent}_{shape_id}"
								
								st.session_state.setdefault(unique_key, False)
								st.checkbox(
									members_label,
									key=unique_key,
									value=st.session_state.get(unique_key, False),
								)
				
				# Store shape toggle map for compatibility
				shape_toggle_map = st.session_state.setdefault("shape_toggles_by_parent", {})
				for sh in shapes:
					parent = sh.get("parent", 0)
					if parent not in shape_toggle_map:
						shape_toggle_map[parent] = []
					unique_key = f"shape_{parent}_{sh['id']}"
					shape_toggle_map[parent].append({
						"id": sh["id"],
						"on": st.session_state.get(unique_key, False)
					})
			else:
				st.info("No shapes detected in combined charts.")
			
			# Empty toggles/pattern_labels for Combined Circuits mode
			toggles = []
			pattern_labels = []
		
		# Regular Circuits mode (single chart or Connected Circuits in synastry)
		elif chart_mode == "Circuits":
			# Compute circuit_connected_shapes2 fresh here so it is always ready
			# when the expander loop runs below.  Reading it from session state
			# would be stale because _refresh_chart_figure runs AFTER this function.
			circuit_connected_shapes2: dict[int, list] = {}
			if synastry_mode and circuit_submode == "Connected Circuits":
				_pos_inner = st.session_state.get("chart_positions") or {}
				_pos_outer = st.session_state.get("chart_positions_2") or {}
				_shapes_2  = st.session_state.get("shapes_2") or []
				# Build all inter-chart aspects (Chart 1 × Chart 2 bodies)
				_edges_inter: list[tuple[str, str, str]] = []
				for _ep1, _d1 in _pos_inner.items():
					for _ep2, _d2 in _pos_outer.items():
						_angle = abs(_d1 - _d2) % 360
						if _angle > 180:
							_angle = 360 - _angle
						for _asp_name, _asp_data in ASPECTS.items():
							if abs(_angle - _asp_data["angle"]) <= _asp_data["orb"]:
								_edges_inter.append((_ep1, _ep2, _asp_name))
								break
				for _ci, _component in enumerate(patterns):
					_comp_set = set(_component)
					_connected = {_ep2 for (_ep1, _ep2, _) in _edges_inter if _ep1 in _comp_set}
					_linked = [sh for sh in _shapes_2 if set(sh.get("members", [])) & _connected]
					if _linked:
						circuit_connected_shapes2[_ci] = _linked
				# Persist for the drawing function in _refresh_chart_figure
				st.session_state["circuit_connected_shapes2"] = circuit_connected_shapes2
				st.session_state["edges_inter_chart_cc"] = _edges_inter

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

						# ---------- Chart 2 Connections (Connected Circuits + synastry only) ----------
						# Show connections when the circuit itself OR any of its sub-shapes is active.
						any_shape_on = any(e["on"] for e in shape_entries)
						if synastry_mode and circuit_submode == "Connected Circuits" and (cbox or any_shape_on):
							cc_shapes_for_circuit = circuit_connected_shapes2.get(i, [])
							st.markdown("---")
							if cc_shapes_for_circuit:
								st.markdown("**Chart 2 Connections:**")
								if not cbox:
									st.caption("_Enable the circuit above to draw connections._")
								for sh2 in cc_shapes_for_circuit:
									sh2_members = sh2.get("members", [])
									if want_glyphs:
										members_str = ", ".join(GLYPHS.get(m, m) for m in sh2_members)
									else:
										members_str = ", ".join(sh2_members)
									sh2_label = f"{sh2['type']}: {members_str}"
									cc_key = f"cc_shape_{i}_{sh2['id']}"
									st.session_state.setdefault(cc_key, False)
									st.checkbox(sh2_label, key=cc_key)
							else:
								st.markdown("_No Chart 2 connections found._")
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
	circuit_submode = st.session_state.get("circuit_submode", "Combined Circuits")
	
	# Collect aspect toggles for Standard Chart mode
	aspect_toggles = {}
	if chart_mode == "Standard Chart":
		for body_name in TOGGLE_ASPECTS.keys():
			key = f"aspect_toggle_{body_name}"
			aspect_toggles[body_name] = st.session_state.get(key, False)
	
	return toggles, pattern_labels, saved_profiles, chart_mode, aspect_toggles, circuit_submode

