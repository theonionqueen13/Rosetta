# Contributing to Rosetta

## Development Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_joylin_chart.py -v
pytest tests/test_joylin_patterns.py -v
```

## Code Quality

### Linting
We use flake8 for basic syntax checking:
```bash
flake8 . --count --select=E9,F63,F7,F82 --ignore=F824 --show-source --statistics --exclude=.venv,__pycache__,backups
```

### Formatting
We recommend using black for code formatting:
```bash
black .
```

### Testing Imports
Make sure core modules can be imported:
```bash
python -c "from rosetta.calc import calculate_chart"
python -c "from rosetta.patterns import detect_shapes"
python -c "from rosetta.drawing import draw_aspect_lines"
```

## Pull Requests

All pull requests automatically run CI that:
- ✅ Checks for Python syntax errors
- ✅ Runs the complete test suite (37 tests)
- ✅ Validates core module imports
- ✅ Tests basic chart calculation functionality
- ℹ️ Shows code formatting suggestions (non-blocking)

The CI must pass for PRs to be merged.

## Test Coverage

Current test coverage includes:
- Chart calculation with Swiss Ephemeris
- Pattern detection and aspect analysis
- Data validation and error handling
- House system consistency
- Integration testing with real birth data

## Project Structure

- `rosetta/` - Core astrology calculation modules
- `tests/` - Test suite with comprehensive birth chart validation
- `backups/` - Legacy code (excluded from CI)
- `.github/workflows/` - CI configuration
