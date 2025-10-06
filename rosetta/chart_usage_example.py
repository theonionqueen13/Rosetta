"""
Examples of using the AstrologicalChart dataclass.

This module demonstrates how to use the new dataclass-based chart API
while maintaining backward compatibility with the DataFrame-based API.
"""

from rosetta.calc import calculate_chart


def example_dataframe_usage():
    """Traditional usage - returns a DataFrame (default)."""
    df = calculate_chart(1990, 7, 29, 1, 39, -6, 38.046, -97.345)
    print("DataFrame shape:", df.shape)
    print("\nFirst 5 objects:")
    print(df.head())
    return df


def example_dataclass_usage():
    """New usage - returns an AstrologicalChart object."""
    chart = calculate_chart(
        1990, 7, 29, 1, 39, -6, 38.046, -97.345, return_dataframe=False
    )

    # Access chart metadata
    print(f"Chart datetime: {chart.chart_datetime}")
    print(f"Timezone: {chart.timezone}")
    print(f"Location: {chart.latitude}, {chart.longitude}")

    # Get specific objects
    sun = chart.get_object("Sun")
    if sun:
        print(f"\nSun at {sun.longitude}° in {sun.sign}")
        print(f"Sabian Symbol: {sun.sabian_symbol}")

    # Get all planets
    planets = chart.get_planets()
    print(f"\nFound {len(planets)} planets")

    # Get chart angles
    angles = chart.get_angles()
    for angle in angles:
        print(f"{angle.object_name}: {angle.sign} {angle.dms}")

    # Get retrograde planets
    retrogrades = chart.get_retrograde_objects()
    print(f"\nRetrograde objects:")
    for obj in retrogrades:
        print(f"  {obj.object_name} in {obj.sign}")

    # Get out of bounds objects
    oob_objects = chart.get_out_of_bounds_objects()
    if oob_objects:
        print(f"\nOut of bounds objects:")
        for obj in oob_objects:
            print(
                f"  {obj.object_name}: {obj.declination}° declination"
            )

    # Convert to DataFrame when needed
    df = chart.to_dataframe()
    print(f"\nConverted to DataFrame: {df.shape}")

    return chart


def example_house_systems():
    """Examples with different house systems."""
    for system in ["equal", "placidus", "whole"]:
        chart = calculate_chart(
            1990,
            7,
            29,
            1,
            39,
            -6,
            38.046,
            -97.345,
            house_system=system,
            return_dataframe=False,
        )
        print(f"\n{system.title()} Houses:")
        for cusp in chart.house_cusps[:3]:  # First 3 cusps
            print(
                f"  House {cusp.cusp_number}: "
                f"{cusp.absolute_degree}°"
            )


if __name__ == "__main__":
    print("=" * 60)
    print("Example 1: DataFrame Usage (Backward Compatible)")
    print("=" * 60)
    example_dataframe_usage()

    print("\n" + "=" * 60)
    print("Example 2: Dataclass Usage (New API)")
    print("=" * 60)
    example_dataclass_usage()

    print("\n" + "=" * 60)
    print("Example 3: Different House Systems")
    print("=" * 60)
    example_house_systems()
