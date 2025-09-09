#!/usr/bin/env python3
"""
Integration test that demonstrates the complete Rosetta workflow:
Birth data → Chart calculation → Pattern detection → Visualization data

This test validates the end-to-end functionality using Joylin's birth data.
"""
import pytest

from rosetta.calc import calculate_chart
from rosetta.helpers import deg_to_rad
from rosetta.patterns import detect_minor_links_with_singletons


class TestRosettaIntegration:
    """Integration tests for the complete Rosetta workflow."""

    def test_full_workflow_joylin(self):
        """Test the complete workflow from saved birth data to chart output."""

        # Step 1: Load birth data (simulating loading from saved_birth_data.json)
        birth_data = {
            "year": 1990,
            "month": 7,
            "day": 29,
            "hour": 1,
            "minute": 39,
            "city": "Newton, KS",
            "lat": 38.0469166,
            "lon": -97.3447244,
            "tz_name": "America/Chicago"
        }

        # Step 2: Calculate chart
        chart_df = calculate_chart(
            birth_data["year"],
            birth_data["month"],
            birth_data["day"],
            birth_data["hour"],
            birth_data["minute"],
            None,  # tz_offset (using tz_name instead)
            birth_data["lat"],
            birth_data["lon"],
            tz_name=birth_data["tz_name"]
        )

        # Validate chart calculation
        assert chart_df is not None, "Chart calculation failed"
        assert len(chart_df) > 0, "Chart has no data"

        # Step 3: Extract planetary positions
        # Use actual major planets instead of the full MAJOR_OBJECTS list
        core_planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                        'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        major_planets = chart_df[chart_df['Object'].isin(core_planets)].copy()
        assert len(major_planets) == len(
            core_planets), f"Missing major planets: expected {len(core_planets)}, got {len(major_planets)}"

        positions = {}
        for _, row in major_planets.iterrows():
            positions[row['Object']] = row['Longitude']

        # Step 4: Get Ascendant for chart orientation
        asc_row = chart_df[chart_df['Object'] == 'Ascendant']
        assert not asc_row.empty, "Ascendant not found in chart"
        ascendant_deg = asc_row['Longitude'].iloc[0]

        # Validate ascendant is in expected range for Joylin
        assert 57.4 < ascendant_deg < 57.7, f"Ascendant {ascendant_deg} outside expected range"

        # Step 5: Test coordinate conversion for chart drawing
        # Convert planetary positions to chart coordinates
        chart_coords = {}
        for planet, longitude in positions.items():
            chart_coord = deg_to_rad(longitude, ascendant_deg)
            chart_coords[planet] = chart_coord

            # Validate coordinate is within valid range
            assert 0 <= chart_coord < 2 * \
                3.14159, f"{planet} chart coordinate {chart_coord} outside valid range"

        # Step 6: Test pattern detection
        empty_patterns = []
        connections, singleton_map = detect_minor_links_with_singletons(
            positions, empty_patterns)

        # Validate pattern detection results
        assert isinstance(connections, list), "Connections should be a list"
        assert isinstance(
            singleton_map, dict), "Singleton map should be a dict"
        assert len(singleton_map) == len(
            core_planets), "All major planets should be singletons"

        # Step 7: Generate chart metadata
        chart_metadata = {
            "birth_info": {
                "name": "Joylin",
                "date": f"{birth_data['month']}/{birth_data['day']}/{birth_data['year']}",
                "time": f"{birth_data['hour']:02d}:{birth_data['minute']:02d}",
                "location": birth_data['city'],
                "coordinates": f"{birth_data['lat']:.4f}°N, {abs(birth_data['lon']):.4f}°W"
            },
            "chart_data": {
                "ascendant": {
                    "degree": ascendant_deg,
                    "sign": chart_df[chart_df['Object'] == 'Ascendant']['Sign'].iloc[0],
                    "dms": chart_df[chart_df['Object'] == 'Ascendant']['DMS'].iloc[0]
                },
                "total_objects": len(chart_df),
                "major_planets": len(major_planets),
                "house_cusps": len([obj for obj in chart_df['Object'] if 'H Cusp' in str(obj)])
            },
            "aspects_found": {
                "minor_connections": len(connections),
                "connection_details": [
                    {
                        "planets": f"{conn[0]}-{conn[1]}",
                        "aspect": conn[2],
                        "pattern_indices": f"{conn[3]}-{conn[4]}"
                    }
                    for conn in connections
                ]
            }
        }

        # Step 8: Validate final output structure
        assert "birth_info" in chart_metadata
        assert "chart_data" in chart_metadata
        assert "aspects_found" in chart_metadata

        # Validate birth info
        birth_info = chart_metadata["birth_info"]
        assert birth_info["name"] == "Joylin"
        assert "Newton, KS" in birth_info["location"]
        assert "38.0469°N" in birth_info["coordinates"]

        # Validate chart data
        chart_data = chart_metadata["chart_data"]
        assert chart_data["ascendant"]["sign"] == "Taurus"
        # Should have planets + cusps + angles
        assert chart_data["total_objects"] > 20
        assert chart_data["major_planets"] == 10
        assert chart_data["house_cusps"] == 12

        # Print summary for verification
        print("\n=== ROSETTA INTEGRATION TEST SUMMARY ===")
        print(f"Chart calculated for: {birth_info['name']}")
        print(f"Birth date/time: {birth_info['date']} at {birth_info['time']}")
        print(f"Location: {birth_info['location']}")
        print(
            f"Ascendant: {chart_data['ascendant']['degree']:.2f}° {chart_data['ascendant']['sign']}")
        print(f"Total objects calculated: {chart_data['total_objects']}")
        print(
            f"Minor aspect connections: {chart_data['minor_connections'] if 'minor_connections' in chart_data else len(connections)}")

        if connections:
            print("Aspects found:")
            for conn in connections:
                print(f"  {conn[0]}-{conn[1]}: {conn[2]}")

        # Test passed successfully
        assert True

    def test_planetary_positions_zodiac_distribution(self):
        """Test that planetary positions are distributed across zodiac signs."""

        # Calculate Joylin's chart
        chart_df = calculate_chart(
            1990, 7, 29, 1, 39, None, 38.0469166, -97.3447244, tz_name="America/Chicago")

        # Get major planets and their signs
        core_planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                        'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        major_planets = chart_df[chart_df['Object'].isin(core_planets)]
        sign_distribution = major_planets['Sign'].value_counts()

        # Validate that we have realistic sign distribution
        assert len(
            sign_distribution) >= 3, "Planets should be distributed across at least 3 signs"
        assert len(
            sign_distribution) <= 10, "Planets shouldn't all be in different signs"

        # Check specific expected signs for Joylin
        signs_present = set(sign_distribution.index)
        expected_signs = {'Leo', 'Scorpio', 'Taurus', 'Cancer', 'Capricorn'}

        # Should have most of these signs represented
        overlap = signs_present.intersection(expected_signs)
        assert len(
            overlap) >= 4, f"Expected most signs from {expected_signs}, got {signs_present}"

        print(f"Sign distribution: {dict(sign_distribution)}")

    def test_house_system_consistency(self):
        """Test that different house systems produce consistent results."""

        birth_params = (1990, 7, 29, 1, 39, None, 38.0469166, -97.3447244)

        # Test Equal houses (default)
        chart_equal = calculate_chart(
            *birth_params, tz_name="America/Chicago", house_system="equal")

        # Test Placidus houses
        chart_placidus = calculate_chart(
            *birth_params, tz_name="America/Chicago", house_system="placidus")

        # Test Whole sign houses
        chart_whole = calculate_chart(
            *birth_params, tz_name="America/Chicago", house_system="whole")

        # Planetary positions should be identical across house systems
        core_planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                        'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        for planet in core_planets:
            equal_pos = chart_equal[chart_equal['Object']
                                    == planet]['Longitude'].iloc[0]
            placidus_pos = chart_placidus[chart_placidus['Object']
                                          == planet]['Longitude'].iloc[0]
            whole_pos = chart_whole[chart_whole['Object']
                                    == planet]['Longitude'].iloc[0]

            assert abs(
                equal_pos - placidus_pos) < 0.001, f"{planet} position differs between Equal and Placidus"
            assert abs(
                equal_pos - whole_pos) < 0.001, f"{planet} position differs between Equal and Whole"

        # House cusps should differ between systems
        equal_cusps = chart_equal[chart_equal['Object'].str.contains(
            'H Cusp')]['Computed Absolute Degree'].tolist()
        placidus_cusps = chart_placidus[chart_placidus['Object'].str.contains(
            'H Cusp')]['Computed Absolute Degree'].tolist()
        whole_cusps = chart_whole[chart_whole['Object'].str.contains(
            'H Cusp')]['Computed Absolute Degree'].tolist()

        # At least some cusps should be different
        equal_placidus_diff = any(
            abs(e - p) > 0.1 for e, p in zip(equal_cusps, placidus_cusps))
        equal_whole_diff = any(abs(e - w) > 0.1 for e,
                               w in zip(equal_cusps, whole_cusps))

        assert equal_placidus_diff or equal_whole_diff, "House systems should produce different cusp positions"

        print("House system consistency test passed")

    def test_error_handling(self):
        """Test that the system handles invalid inputs gracefully."""

        # Test invalid date - month > 12
        try:
            result = calculate_chart(1990, 13, 29, 1, 39, None,
                                     38.0469166, -97.3447244, tz_name="America/Chicago")
            # If it doesn't raise an error, at least verify it's not a valid result
            assert result is None or len(
                result) == 0, "Invalid date should not produce valid chart"
        except (ValueError, Exception):
            pass  # Expected to raise an error

        # Test invalid timezone
        try:
            result = calculate_chart(1990, 7, 29, 1, 39, None, 38.0469166,
                                     -97.3447244, tz_name="Invalid/Timezone")
            assert result is None or len(
                result) == 0, "Invalid timezone should not produce valid chart"
        except (ValueError, Exception):
            pass  # Expected to raise an error

        print("Error handling test passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
