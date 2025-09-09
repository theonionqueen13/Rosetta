# Rosetta Test Suite Documentation

## Overview
This test suite validates the Rosetta astrology chart calculation and pattern detection functionality using Joylin's specific birth data as a test case.

## Birth Data Used for Testing
- **Person**: Joylin  
- **Date**: July 29, 1990
- **Time**: 1:39 AM
- **Location**: Newton, KS (38.0469166°N, 97.3447244°W)
- **Timezone**: America/Chicago

## Test Files Created

### 1. `test_joylin_chart.py` - Chart Calculation Tests
Tests the fundamental chart calculation functionality:

#### Basic Chart Validation
- ✅ Chart calculation completes without errors
- ✅ DataFrame has expected columns (Object, Longitude, Sign, DMS, etc.)
- ✅ All major planets are present (Sun through Pluto)
- ✅ Chart angles are calculated (Ascendant, MC, Descendant)
- ✅ House cusps are present (1H through 12H)

#### Specific Planetary Positions (Validated Against Swiss Ephemeris)
- ✅ **Sun**: 125.90° in Leo (5°54')
- ✅ **Moon**: 212.51° in Scorpio (2°30')  
- ✅ **Ascendant**: 57.53° in Taurus (27°31')
- ✅ **Mercury**: 149.73° in Leo (29°43')
- ✅ **Saturn**: 290.96° in Capricorn (20°57')

#### Data Quality Checks
- ✅ All longitude values are within 0-360° range
- ✅ All zodiac signs are valid
- ✅ Retrograde motion detection works properly
- ✅ House cusp degrees are valid
- ✅ Chart calculations are reproducible (same inputs = same outputs)

### 2. `test_joylin_patterns.py` - Pattern Detection Tests
Tests the aspect calculation and pattern detection functionality:

#### Aspect Calculation Validation
- ✅ **Mars-Neptune Trine**: 118.37° (within orb)
- ✅ **Neptune-Venus Opposition**: 178.43° (within orb)
- ✅ **Sun-Uranus Quincunx**: Minor aspect detected
- ✅ **Sun-Moon**: ~86.6° angle (Leo-Scorpio square relationship)

#### Pattern Detection Features
- ✅ Aspect matching function works correctly
- ✅ Minor aspect detection (Quincunx, Sesquisquare)
- ✅ Connected components analysis
- ✅ Position dictionary creation
- ✅ Orb tolerance validation

#### Specific Validations for Joylin's Chart
- ✅ Sun and Jupiter are NOT in conjunction (~10° apart)
- ✅ Mercury and Sun are NOT in conjunction (~24° apart)
- ✅ Saturn aspects enumerated and validated
- ✅ All aspect orbs are within reasonable ranges

## Key Findings from Joylin's Chart

### Major Aspects Detected
1. **Mars-Neptune Trine** (118.37°)
   - Mars at 40.94° (Taurus) 
   - Neptune at 282.57° (Capricorn)

2. **Neptune-Venus Opposition** (178.43°)
   - Neptune at 282.57° (Capricorn)
   - Venus at 101.00° (Cancer)

3. **Sun-Uranus Quincunx** (Minor aspect)
   - Sun at 125.90° (Leo)
   - Uranus at 276.47° (Capricorn)

### Chart Characteristics
- **Sun-Moon Square-ish**: Leo Sun to Scorpio Moon (~86.6°)
- **Leo Stellium**: Sun and Mercury both in Leo
- **No Perfect Squares**: No 90° aspects within orb detected
- **Saturn Isolated**: No major aspects to Saturn found

## Technical Validation

### Swiss Ephemeris Integration
- ✅ Ephemeris path configuration works
- ✅ Julian Day calculation accurate
- ✅ Planetary positions calculated correctly
- ✅ House system calculations (Equal houses default)

### Pattern Detection Engine
- ✅ NetworkX graph analysis functions
- ✅ Aspect orb calculations
- ✅ Connected component detection
- ✅ Minor aspect filtering

## Test Coverage
- **Total Tests**: 33 tests passing
- **Chart Calculation**: 16 tests
- **Pattern Detection**: 11 tests  
- **Structure/Imports**: 6 tests

## Running the Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test files
python -m pytest tests/test_joylin_chart.py -v
python -m pytest tests/test_joylin_patterns.py -v -s

# Run with pattern output visible
python -m pytest tests/test_joylin_patterns.py::TestJoylinPatterns::test_aspect_calculation_trine -v -s
```

## Future Test Enhancements
1. **Additional Birth Charts**: Test with different birth data to validate edge cases
2. **House System Testing**: Validate Placidus vs Equal vs Whole sign houses
3. **Pattern Complex Detection**: Test for Grand Trines, T-Squares, etc.
4. **Fixed Star Integration**: Test fixed star calculations
5. **Transit Calculations**: Test planetary transits
6. **Performance Testing**: Benchmark chart calculation speed

## Notes for Developers
- All tests use the exact birth data from `saved_birth_data.json`
- Tests are designed to be deterministic (same inputs = same outputs)
- Floating point comparisons use reasonable tolerance ranges
- Pattern detection tests reveal actual aspects in the chart
- Swiss Ephemeris data files are required in `rosetta/ephe/` directory
