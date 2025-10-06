# Astrological Chart Dataclass Refactoring

## Overview

The `calculate_chart()` function has been enhanced with a new dataclass-based API that provides better type safety, clearer structure, and more convenient methods for working with chart data.

## Key Changes

### New Data Models (`chart_models.py`)

Three new dataclasses have been introduced:

1. **`ChartObject`** - Represents celestial objects (planets, points, asteroids)
   - Properties: longitude, sign, DMS, sabian info, dignity, rulership, etc.
   - Method: `to_dict()` for DataFrame conversion

2. **`HouseCusp`** - Represents house cusps
   - Properties: cusp_number, absolute_degree, house_system
   - Method: `to_dict()` for DataFrame conversion

3. **`AstrologicalChart`** - The complete chart container
   - Properties: objects, house_cusps, metadata (datetime, timezone, location)
   - Methods:
     - `to_dataframe()` - Convert to pandas DataFrame
     - `get_object(name)` - Get specific object by name
     - `get_planets()` - Get all traditional planets
     - `get_angles()` - Get chart angles (ASC, MC, DSC, IC)
     - `get_asteroids()` - Get all asteroids
     - `get_retrograde_objects()` - Get objects in retrograde
     - `get_out_of_bounds_objects()` - Get OOB objects

### Updated `calculate_chart()` Function

The function signature now includes a new parameter:

```python
def calculate_chart(
    year, month, day, hour, minute, tz_offset, lat, lon,
    input_is_ut: bool = False,
    tz_name: str | None = None,
    house_system: str = "equal",
    return_dataframe: bool = True,  # NEW PARAMETER
) -> pd.DataFrame | AstrologicalChart:
```

## Usage

### Backward Compatible (DataFrame)

By default, the function returns a DataFrame as before:

```python
from rosetta.calc import calculate_chart

# Returns DataFrame (default behavior)
df = calculate_chart(1990, 7, 29, 1, 39, -6, 38.046, -97.345)
print(df.head())
```

### New Dataclass API

Set `return_dataframe=False` to get the new `AstrologicalChart` object:

```python
# Returns AstrologicalChart object
chart = calculate_chart(
    1990, 7, 29, 1, 39, -6, 38.046, -97.345,
    return_dataframe=False
)

# Access metadata
print(f"Chart time: {chart.chart_datetime}")
print(f"Location: {chart.latitude}, {chart.longitude}")

# Get specific objects
sun = chart.get_object("Sun")
print(f"Sun: {sun.sign} {sun.dms}")

# Get groups of objects
planets = chart.get_planets()
retrograde = chart.get_retrograde_objects()
oob = chart.get_out_of_bounds_objects()

# Convert to DataFrame when needed
df = chart.to_dataframe()
```

## Benefits

1. **Type Safety** - Clear types for all chart components
2. **Convenience Methods** - Easy access to specific object groups
3. **Metadata** - Chart datetime and location info preserved
4. **Backward Compatibility** - Existing code continues to work
5. **Flexibility** - Convert between dataclass and DataFrame as needed

## Migration Guide

### Existing Code
No changes needed! The default behavior remains the same.

### New Code
For new features, consider using the dataclass API:

```python
# Old way
df = calculate_chart(...)
sun_row = df[df['Object'] == 'Sun'].iloc[0]
sun_sign = sun_row['Sign']

# New way
chart = calculate_chart(..., return_dataframe=False)
sun = chart.get_object("Sun")
sun_sign = sun.sign
```

## Testing

The existing test suite continues to work with the DataFrame API. Tests can optionally use the new API for better readability:

```python
def test_with_dataclass():
    chart = calculate_chart(
        1990, 7, 29, 1, 39, -6, 38.046, -97.345,
        return_dataframe=False
    )
    
    # Type-safe assertions
    assert isinstance(chart, AstrologicalChart)
    assert len(chart.objects) > 0
    
    sun = chart.get_object("Sun")
    assert sun is not None
    assert sun.sign in SIGNS
```

## Examples

See `chart_usage_example.py` for comprehensive examples of both APIs.
