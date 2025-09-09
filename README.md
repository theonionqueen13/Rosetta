# Rosetta: Astrology Chart Pattern Analyzer

A modern Streamlit-based astrology chart visualization and pattern analysis tool using Swiss Ephemeris calculations.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the main application
streamlit run rosetta.py
```

## Project Structure

```
/workspaces/Rosetta/                    # Project root
├── rosetta.py                          # Main Streamlit application
├── rosetta/                            # Core package modules
│   ├── calc.py                         # Swiss Ephemeris calculations
│   ├── drawing.py                      # Chart rendering with matplotlib
│   ├── patterns.py                     # Aspect pattern detection (NetworkX)
│   ├── lookup.py                       # Constants and lookup tables
│   ├── helpers.py                      # Utility functions
│   └── ephe/                           # Swiss Ephemeris data files
├── backups/                            # Legacy development files
└── requirements.txt                    # Python dependencies
```

**Note**: Experimental features with advanced shape detection are available in the `experimental-shapes` branch.

## Features

- **Interactive natal chart visualization** with polar coordinates
- **Aspect pattern detection**: T-squares, Grand Trines, Kites, and more
- **Swiss Ephemeris integration** for accurate astronomical calculations
- **Multiple house systems**: Placidus, Equal, and Whole Sign
- **Dark mode support** for chart visualization
- **CSV import/export** for chart data
- **Fixed star conjunctions** and interpretations

## Architecture

Built with a modular design using the `rosetta/` package:
- **Streamlit** for the web interface
- **matplotlib** for polar chart rendering
- **NetworkX** for graph-based pattern analysis
- **pyswisseph** for astronomical calculations
- **pandas** for data handling

## Development

The project uses a modern modular architecture. All legacy monolithic files have been moved to `backups/`. New development should use the `rosetta/` package structure with proper imports:

```python
from rosetta.calc import calculate_chart
from rosetta.patterns import detect_minor_links_with_singletons
from rosetta.drawing import draw_aspect_lines
```

See `.github/copilot-instructions.md` for detailed AI coding agent guidance.
