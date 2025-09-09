# Rosetta: Astrology Chart Pattern Analyzer

## Project Overview
Rosetta is a Streamlit-based astrology chart visualization and pattern analysis tool. It uses Swiss Ephemeris calculations to generate natal charts with sophisticated aspect pattern detection (T-squares, Grand Trines, Kites, etc.) and interactive visualization.

## Architecture & Key Components

### Core Module Structure (`rosetta/`)
- **`calc.py`**: Swiss Ephemeris integration for planetary calculations and chart generation
- **`drawing.py`**: Matplotlib polar chart rendering with zodiac wheel, aspects, and patterns
- **`patterns.py`**: Graph-based aspect pattern detection using NetworkX (T-squares, Grand Trines, Kites)
- **`lookup.py`**: Constants for glyphs, aspects, colors, interpretations, and fixed star data
- **`helpers.py`**: Coordinate conversion, house calculations, and utility functions

### Main Applications
- **`rosetta5.py`**: Primary Streamlit app with full feature set
- **`rosetta.py`**: Main entry point configured in `.devcontainer/devcontainer.json`
- **Numbered variants**: Development iterations (rosetta1.py through rosetta7.py)

## Development Workflow

### Running the Application
```bash
streamlit run rosetta.py  # Main app
streamlit run rosetta5.py  # Feature-complete version
```
The devcontainer auto-starts on port 8501 with CORS disabled.

### Key Dependencies
- **pyswisseph**: Astronomical calculations engine
- **matplotlib**: Polar chart rendering in "polar" projection mode
- **networkx**: Graph analysis for aspect pattern detection
- **streamlit**: Web UI framework

## Project-Specific Patterns

### Chart Coordinate System
- Uses **polar coordinates** with North at top (`ax.set_theta_zero_location("N")`)
- **Counterclockwise rotation** (`ax.set_theta_direction(-1)`)
- Ascendant degree determines chart rotation: `deg_to_rad(degree, asc_deg)`

### Aspect Pattern Detection
Patterns are detected as **connected components** in aspect graphs:
```python
# From patterns.py
def connected_components_from_edges(nodes, edges):
    # Creates NetworkX-style graph analysis
```
- **T-Squares**: 3 planets with 2 squares + 1 opposition
- **Grand Trines**: 3+ planets in trine aspects forming triangles
- **Kites**: Grand Trine + opposition creating diamond shapes

### Data Flow Architecture
1. **Input**: CSV files with planetary positions from astronomical software
2. **Calculation**: `calc.py` processes Swiss Ephemeris data
3. **Pattern Detection**: `patterns.py` analyzes aspect networks
4. **Visualization**: `drawing.py` renders polar charts
5. **UI**: Streamlit manages toggles and interactive controls

### File Organization Conventions
- **Main logic**: Spread across numbered `rosetta*.py` files (development snapshots)
- **Modular code**: Organized in `rosetta/` package
- **Constants**: Centralized in `lookup.py` (not imported across numbered files)
- **Backups**: Historical versions in `backups/` directory

### Swiss Ephemeris Integration
- Ephemeris data files stored in `rosetta/ephe/`
- House systems: Placidus vs Equal houses via `use_placidus` parameter
- Coordinate calculations handle retrograde motion and declination

## Testing & Debugging
- **Pattern validation**: Use the toggle system in Streamlit to isolate specific aspect patterns
- **Chart accuracy**: Compare with professional astrology software using same birth data
- **Visual debugging**: Dark mode toggle helps identify rendering issues

## Common Gotchas
- **Coordinate conversion**: Always use `deg_to_rad(degree, asc_deg)` for chart positioning
- **Aspect orbs**: Defined in `ASPECTS` dict in `lookup.py` - different orbs for major vs minor aspects
- **CSV format**: Expects specific column names like "Computed Absolute Degree"
- **Pattern indexing**: Active patterns tracked by index, not object reference

## Key External Dependencies
- Swiss Ephemeris library requires specific ephemeris data files
- Matplotlib polar plots have unique coordinate behavior
- NetworkX graph operations power the pattern detection algorithms
