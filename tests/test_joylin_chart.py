#!/usr/bin/env python3
"""
Test Joylin's birth chart calculation and pattern detection.
Uses specific birth data to ensure consistent chart outputs.
"""
import pandas as pd
import pytest

from rosetta.calc import calculate_chart


class TestJoylinChart:
    """Test suite for Joylin's specific birth chart."""

    @classmethod
    def setup_class(cls):
        """Set up Joylin's birth data once for all tests."""
        cls.birth_data = {
            "year": 1990,
            "month": 7,
            "day": 29,
            "hour": 1,
            "minute": 39,
            "lat": 38.0469166,
            "lon": -97.3447244,
            "tz_name": "America/Chicago"
        }

        # Calculate chart once
        cls.chart_df = calculate_chart(
            cls.birth_data["year"],
            cls.birth_data["month"],
            cls.birth_data["day"],
            cls.birth_data["hour"],
            cls.birth_data["minute"],
            None,  # tz_offset
            cls.birth_data["lat"],
            cls.birth_data["lon"],
            tz_name=cls.birth_data["tz_name"]
        )

    def test_chart_calculation_success(self):
        """Test that chart calculation completes without errors."""
        assert self.chart_df is not None
        assert isinstance(self.chart_df, pd.DataFrame)
        assert len(self.chart_df) > 0

    def test_chart_has_expected_columns(self):
        """Test that chart has all expected columns."""
        expected_columns = [
            'Object', 'Longitude', 'Sign', 'DMS', 'Sabian Index',
            'Sabian Symbol', 'Retrograde', 'OOB Status', 'Dignity',
            'Ruled by (sign)', 'Latitude', 'Declination', 'Distance', 'Speed'
        ]

        for col in expected_columns:
            assert col in self.chart_df.columns, f"Missing column: {col}"

    def test_major_planets_present(self):
        """Test that all major planets are present in the chart."""
        major_planets = [
            'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
            'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'
        ]

        chart_objects = set(self.chart_df['Object'].tolist())
        for planet in major_planets:
            assert planet in chart_objects, f"Missing planet: {planet}"

    def test_angles_present(self):
        """Test that chart angles are calculated."""
        angles = ['Ascendant', 'MC', 'Descendant']
        chart_objects = set(self.chart_df['Object'].tolist())

        for angle in angles:
            assert angle in chart_objects, f"Missing angle: {angle}"

    def test_sun_position(self):
        """Test Sun's specific position for Joylin's chart."""
        sun_row = self.chart_df[self.chart_df['Object'] == 'Sun'].iloc[0]

        # Test longitude (should be around 125.9 degrees)
        assert 125.8 < sun_row[
            'Longitude'] < 126.0, f"Sun longitude {sun_row['Longitude']} outside expected range"

        # Test sign (should be Leo)
        assert sun_row['Sign'] == 'Leo', f"Sun sign is {sun_row['Sign']}, expected Leo"

        # Test degree within sign (should be around 5-6 degrees)
        degree_in_sign = sun_row['Longitude'] % 30
        assert 5.0 < degree_in_sign < 6.5, f"Sun degree in sign {degree_in_sign} outside expected range"

    def test_moon_position(self):
        """Test Moon's specific position for Joylin's chart."""
        moon_row = self.chart_df[self.chart_df['Object'] == 'Moon'].iloc[0]

        # Test longitude (should be around 212.5 degrees)
        assert 212.4 < moon_row[
            'Longitude'] < 212.6, f"Moon longitude {moon_row['Longitude']} outside expected range"

        # Test sign (should be Scorpio)
        assert moon_row['Sign'] == 'Scorpio', f"Moon sign is {moon_row['Sign']}, expected Scorpio"

        # Test degree within sign (should be around 2-3 degrees)
        degree_in_sign = moon_row['Longitude'] % 30
        assert 2.0 < degree_in_sign < 3.0, f"Moon degree in sign {degree_in_sign} outside expected range"

    def test_ascendant_position(self):
        """Test Ascendant's specific position for Joylin's chart."""
        asc_row = self.chart_df[self.chart_df['Object'] == 'Ascendant'].iloc[0]

        # Test longitude (should be around 57.5 degrees)
        assert 57.4 < asc_row[
            'Longitude'] < 57.7, f"Ascendant longitude {asc_row['Longitude']} outside expected range"

        # Test sign (should be Taurus)
        assert asc_row['Sign'] == 'Taurus', f"Ascendant sign is {asc_row['Sign']}, expected Taurus"

        # Test degree within sign (should be around 27-28 degrees)
        degree_in_sign = asc_row['Longitude'] % 30
        assert 27.0 < degree_in_sign < 28.0, f"Ascendant degree in sign {degree_in_sign} outside expected range"

    def test_mercury_position(self):
        """Test Mercury's specific position for Joylin's chart."""
        mercury_row = self.chart_df[self.chart_df['Object']
                                    == 'Mercury'].iloc[0]

        # Test longitude (should be around 149.7 degrees)
        assert 149.6 < mercury_row[
            'Longitude'] < 149.8, f"Mercury longitude {mercury_row['Longitude']} outside expected range"

        # Test sign (should be Leo)
        assert mercury_row['Sign'] == 'Leo', f"Mercury sign is {mercury_row['Sign']}, expected Leo"

        # Test it's late in Leo (around 29 degrees)
        degree_in_sign = mercury_row['Longitude'] % 30
        assert 29.0 < degree_in_sign < 30.0, f"Mercury degree in sign {degree_in_sign} outside expected range"

    def test_saturn_position(self):
        """Test Saturn's specific position for Joylin's chart."""
        saturn_row = self.chart_df[self.chart_df['Object'] == 'Saturn'].iloc[0]

        # Test longitude (should be around 290.9 degrees)
        assert 290.8 < saturn_row[
            'Longitude'] < 291.1, f"Saturn longitude {saturn_row['Longitude']} outside expected range"

        # Test sign (should be Capricorn)
        assert saturn_row['Sign'] == 'Capricorn', f"Saturn sign is {saturn_row['Sign']}, expected Capricorn"

        # Test degree within sign (should be around 20-21 degrees)
        degree_in_sign = saturn_row['Longitude'] % 30
        assert 20.0 < degree_in_sign < 22.0, f"Saturn degree in sign {degree_in_sign} outside expected range"

    def test_house_cusps_present(self):
        """Test that house cusps are calculated."""
        house_cusps = [f"{i}H Cusp" for i in range(1, 13)]
        chart_objects = set(self.chart_df['Object'].tolist())

        for cusp in house_cusps:
            assert cusp in chart_objects, f"Missing house cusp: {cusp}"

    def test_house_cusp_degrees(self):
        """Test that house cusps have valid degree values."""
        for i in range(1, 13):
            cusp_name = f"{i}H Cusp"
            cusp_row = self.chart_df[self.chart_df['Object'] == cusp_name]
            assert not cusp_row.empty, f"Missing {cusp_name}"

            degree = cusp_row['Computed Absolute Degree'].iloc[0]
            assert 0 <= degree < 360, f"{cusp_name} degree {degree} outside valid range"

    def test_no_missing_longitudes(self):
        """Test that all objects have valid longitude values."""
        for _, row in self.chart_df.iterrows():
            if pd.notna(row['Longitude']):
                assert 0 <= row['Longitude'] < 360, f"{row['Object']} longitude {row['Longitude']} outside valid range"

    def test_retrograde_detection(self):
        """Test that retrograde motion is properly detected."""
        # Check that retrograde column exists and has valid values
        retrograde_values = self.chart_df['Retrograde'].dropna().unique()
        valid_values = {'', 'Rx'}
        assert set(retrograde_values).issubset(
            valid_values), f"Invalid retrograde values: {retrograde_values}"

    def test_signs_valid(self):
        """Test that all signs are valid zodiac signs."""
        valid_signs = [
            'Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
            'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'
        ]

        chart_signs = self.chart_df['Sign'].dropna().unique()
        for sign in chart_signs:
            assert sign in valid_signs, f"Invalid sign: {sign}"

    def test_pattern_detection_basic(self):
        """Test basic pattern detection functionality."""
        # Get major planets for pattern detection
        major_objects = self.chart_df[
            self.chart_df['Object'].isin([
                'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'
            ])
        ].copy()

        assert len(
            major_objects) == 10, f"Expected 10 major objects, got {len(major_objects)}"

        # Create position dictionary
        pos = {}
        for _, row in major_objects.iterrows():
            pos[row['Object']] = row['Longitude']

        # Test that positions are valid
        assert len(
            pos) == 10, f"Position dict should have 10 entries, got {len(pos)}"
        for planet, longitude in pos.items():
            assert 0 <= longitude < 360, f"{planet} longitude {longitude} outside valid range"

    def test_chart_reproducibility(self):
        """Test that calculating the same chart twice gives identical results."""
        chart_df2 = calculate_chart(
            self.birth_data["year"],
            self.birth_data["month"],
            self.birth_data["day"],
            self.birth_data["hour"],
            self.birth_data["minute"],
            None,  # tz_offset
            self.birth_data["lat"],
            self.birth_data["lon"],
            tz_name=self.birth_data["tz_name"]
        )

        # Compare longitude values for planets
        planets = ['Sun', 'Moon', 'Mercury',
                   'Venus', 'Mars', 'Jupiter', 'Saturn']
        for planet in planets:
            lon1 = self.chart_df[self.chart_df['Object']
                                 == planet]['Longitude'].iloc[0]
            lon2 = chart_df2[chart_df2['Object']
                             == planet]['Longitude'].iloc[0]

            # Allow tiny floating point differences
            assert abs(
                lon1 - lon2) < 0.000001, f"{planet} longitude differs between calculations: {lon1} vs {lon2}"


if __name__ == "__main__":
    pytest.main([__file__])
