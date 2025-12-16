from house_selector_v2 import render_house_system_selector
from calc_v2 import plot_dispositor_graph

def render_dispositor_section(st, df_cached) -> None:
	"""
	Renders the Dispositor Graph section in the Streamlit app.
	This includes the header, house system selector, scope toggle,
	and the dispositor graph itself with legend.
	"""
	# Add anchor for jump button
	st.markdown('<div id="ruler-hierarchies"></div>', unsafe_allow_html=True)

	header_col, toggle_col, house_col = st.columns([2, 2, 1])

	with header_col:
		st.subheader("Ruler Hierarchies")

	with house_col:
		render_house_system_selector()

	with toggle_col:
		# House system selector (always render, but only relevant for "By House")
		# Dispositor scope toggle
		st.session_state.setdefault("dispositor_scope", "By Sign")
		disp_scope = st.radio(
			"Scope",
			["By Sign", "By House"],
			horizontal=True,
			key="dispositor_scope",
			label_visibility="collapsed"
		)

	plot_data = st.session_state.get("DISPOSITOR_GRAPH_DATA")
	
	if plot_data is not None:
		# The rest of your logic now runs directly on the plot_data variable.
		
		disp_scope = st.session_state.get("dispositor_scope", "By Sign")
		
		# Determine which scope to use
		if disp_scope == "By Sign":
			scope_data = plot_data.get("by_sign")
		else:  # By House
			house_key_map = {
				"placidus": "Placidus",
				"equal": "Equal",
				"whole": "Whole Sign"
			}
			selected_house = st.session_state.get("house_system", "placidus")
			plot_data_key = house_key_map.get(selected_house, "Placidus")
			scope_data = plot_data.get(plot_data_key)

		if scope_data and scope_data.get("raw_links"):
			# Get header info from _current_chart_header_lines
			from drawing_v2 import _current_chart_header_lines
			name, date_line, time_line, city, extra_line = _current_chart_header_lines()
			header_info = {
				'name': name,
				'date_line': date_line,
				'time_line': time_line,
				'city': city,
				'extra_line': extra_line
			}
			disp_fig = plot_dispositor_graph(scope_data, header_info=header_info)
			if disp_fig is not None:
				# Create columns for legend and graph
				legend_col, graph_col = st.columns([1, 5])
				
			with legend_col:
				import os
				import base64
				png_dir = os.path.join(os.path.dirname(__file__), "pngs")
				
				# Get the directory of the current file (e.g., ...\Rosetta_v2\src)
				current_dir = os.path.dirname(__file__) 
				
				# ⬇️ THE FIX: Go up one level (..) to Rosetta_v2, then look for 'pngs' ⬇️
				png_dir = os.path.join(current_dir, "..", "pngs")

				# Load and encode images as base64
				def img_to_b64(filename):
					path = os.path.join(png_dir, filename)
					if os.path.exists(path):
						with open(path, "rb") as f:
							return base64.b64encode(f.read()).decode()
					return ""
				
				# Create legend with dark background
				st.markdown("""
					<div style="background-color: #262730; padding: 15px; border-radius: 8px;">
						<strong style="color: white;">Legend</strong>
					</div>
				""", unsafe_allow_html=True)
				
				legend_items = [
					("green.png", "Sovereign"),
					("orange.png", "Dual rulership"),
					("purple.png", "Loop"),
					("purpleorange.png", "Dual + Loop"),
					("blue.png", "Standard"),
				]
				
				# Wrap all legend items in the dark background
				legend_html = '<div style="background-color: #262730; padding: 15px; border-radius: 8px; margin-top: -15px;">'
				for img_file, label in legend_items:
					b64 = img_to_b64(img_file)
					if b64:
						legend_html += f'<div style="margin-bottom: 8px;"><img src="data:image/png;base64,{b64}" width="20" style="vertical-align:middle;margin-right:5px"/><span style="color: white;">{label}</span></div>'
				legend_html += '<div style="color: white; margin-top: 8px;">↻ Self-Ruling</div>'
				legend_html += '</div>'
				st.markdown(legend_html, unsafe_allow_html=True)
				
			with graph_col:
				import matplotlib.pyplot as plt
				if not isinstance(disp_fig, plt.Figure):
					st.error(f"Debug: disp_fig is of type {type(disp_fig)}")
				st.pyplot(disp_fig, use_container_width=True)
		else:
			st.info("No dispositor graph to display.")
	else:
		st.info("Calculate a chart first.")