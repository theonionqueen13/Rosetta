#!/usr/bin/env python3
"""
Test pattern detection functionality for Joylin's birth chart.
Tests aspect calculations and specific patterns in the chart.
"""
import pandas as pd
import pytest

from rosetta.calc import calculate_chart
from rosetta.lookup import ASPECTS
from rosetta.patterns import (aspect_match, connected_components_from_edges,
                              detect_minor_links_with_singletons)


class TestJoylinPatterns:
    """Test suite for pattern detection in Joylin's chart."""

    @classmethod
    def setup_class(cls):
        """Set up Joylin's birth data and calculate chart once."""
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

        # Create position dictionary for major planets
        major_objects = cls.chart_df[
            cls.chart_df['Object'].isin([
                'Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto'
            ])
        ]

        cls.positions = {}
        for _, row in major_objects.iterrows():
            cls.positions[row['Object']] = row['Longitude']

    def test_position_setup(self):
        """Test that positions are correctly set up."""
        assert len(
            self.positions) == 10, f"Expected 10 planets, got {len(self.positions)}"

        # Test specific known positions
        assert 125.8 < self.positions['Sun'] < 126.0, "Sun position outside expected range"
        assert 212.4 < self.positions['Moon'] < 212.6, "Moon position outside expected range"

        # Test all positions are valid degrees
        for planet, lon in self.positions.items():
            assert 0 <= lon < 360, f"{planet} longitude {lon} outside valid range"

    def test_aspect_calculation_conjunction(self):
        """Test aspect calculation for close conjunctions."""
        # Sun and Jupiter should be close (both in late Cancer/early Leo)
        sun_pos = self.positions['Sun']    # ~125.9°
        jupiter_pos = self.positions['Jupiter']  # ~115.6°

        angle = abs(sun_pos - jupiter_pos) % 360
        if angle > 180:
            angle = 360 - angle

        # They should be about 10-11 degrees apart (not a conjunction)
        assert 9 < angle < 12, f"Sun-Jupiter angle {angle} outside expected range"

        # Test that they don't form a conjunction (orb is usually 8-10 degrees)
        is_conjunction = aspect_match(
            self.positions, 'Sun', 'Jupiter', 'Conjunction')
        assert not is_conjunction, "Sun and Jupiter should not be in conjunction"

    def test_aspect_calculation_trine(self):
        """Test aspect calculation for trine aspects."""
        # Check for potential trines (120° ± orb)
        trine_orb = ASPECTS['Trine']['orb']

        found_trine = False
        for planet1 in self.positions:
            for planet2 in self.positions:
                if planet1 >= planet2:  # Avoid duplicates
                    continue

                if aspect_match(self.positions, planet1, planet2, 'Trine'):
                    found_trine = True
                    angle = abs(
                        self.positions[planet1] - self.positions[planet2]) % 360
                    if angle > 180:
                        angle = 360 - angle

                    print(f"Found trine: {planet1}-{planet2}, angle: {angle}°")
                    assert 120 - trine_orb <= angle <= 120 + \
                        trine_orb, f"Trine angle {angle} outside valid range"

        # Don't assert that we must find a trine, as charts may not have them
        print(f"Trines found: {found_trine}")

    def test_aspect_calculation_square(self):
        """Test aspect calculation for square aspects."""
        # Check for potential squares (90° ± orb)
        square_orb = ASPECTS['Square']['orb']

        found_square = False
        for planet1 in self.positions:
            for planet2 in self.positions:
                if planet1 >= planet2:  # Avoid duplicates
                    continue

                if aspect_match(self.positions, planet1, planet2, 'Square'):
                    found_square = True
                    angle = abs(
                        self.positions[planet1] - self.positions[planet2]) % 360
                    if angle > 180:
                        angle = 360 - angle

                    print(
                        f"Found square: {planet1}-{planet2}, angle: {angle}°")
                    assert 90 - square_orb <= angle <= 90 + \
                        square_orb, f"Square angle {angle} outside valid range"

        print(f"Squares found: {found_square}")

    def test_aspect_calculation_opposition(self):
        """Test aspect calculation for opposition aspects."""
        # Check for potential oppositions (180° ± orb)
        opposition_orb = ASPECTS['Opposition']['orb']

        found_opposition = False
        for planet1 in self.positions:
            for planet2 in self.positions:
                if planet1 >= planet2:  # Avoid duplicates
                    continue

                if aspect_match(self.positions, planet1, planet2, 'Opposition'):
                    found_opposition = True
                    angle = abs(
                        self.positions[planet1] - self.positions[planet2]) % 360
                    if angle > 180:
                        angle = 360 - angle

                    print(
                        f"Found opposition: {planet1}-{planet2}, angle: {angle}°")
                    assert 180 - opposition_orb <= angle <= 180 + \
                        opposition_orb, f"Opposition angle {angle} outside valid range"

        print(f"Oppositions found: {found_opposition}")

    def test_minor_aspects_detection(self):
        """Test detection of minor aspects like quincunx and sesquisquare."""
        # Test with no patterns initially
        empty_patterns = []

        try:
            connections, singleton_map = detect_minor_links_with_singletons(
                self.positions, empty_patterns
            )

            assert isinstance(
                connections, list), "Connections should be a list"
            assert isinstance(
                singleton_map, dict), "Singleton map should be a dict"

            # Check that all planets are mapped as singletons
            assert len(
                singleton_map) == 10, f"Expected 10 singletons, got {len(singleton_map)}"

            # Check connection format if any exist
            for connection in connections:
                assert len(
                    connection) == 5, f"Connection should have 5 elements, got {len(connection)}"
                p1, p2, aspect, pat1, pat2 = connection
                assert p1 in self.positions, f"Planet {p1} not in positions"
                assert p2 in self.positions, f"Planet {p2} not in positions"
                assert aspect in [
                    "Quincunx", "Sesquisquare"], f"Unexpected aspect {aspect}"

            print(f"Minor aspect connections found: {len(connections)}")
            for conn in connections:
                print(f"  {conn[0]}-{conn[1]}: {conn[2]}")

        except Exception as e:
            pytest.fail(f"Minor aspect detection failed: {e}")

    def test_specific_sun_moon_angle(self):
        """Test the specific Sun-Moon angle in Joylin's chart."""
        sun_pos = self.positions['Sun']      # ~125.9° (Leo)
        moon_pos = self.positions['Moon']    # ~212.5° (Scorpio)

        angle = abs(sun_pos - moon_pos) % 360
        if angle > 180:
            angle = 360 - angle

        # Sun in Leo and Moon in Scorpio should form roughly a square aspect
        # Expected angle: ~86-87 degrees
        assert 85 < angle < 89, f"Sun-Moon angle {angle} outside expected range for Leo-Scorpio square"

        # Test if it's detected as a square
        is_square = aspect_match(self.positions, 'Sun', 'Moon', 'Square')
        square_orb = ASPECTS['Square']['orb']

        if abs(angle - 90) <= square_orb:
            assert is_square, f"Sun-Moon should form a square (angle: {angle}°, orb: {square_orb}°)"
        else:
            assert not is_square, f"Sun-Moon should not form a square (angle: {angle}°, orb: {square_orb}°)"

    def test_mercury_sun_conjunction(self):
        """Test for potential Mercury-Sun conjunction."""
        mercury_pos = self.positions['Mercury']  # ~149.7° (late Leo)
        sun_pos = self.positions['Sun']          # ~125.9° (early Leo)

        angle = abs(mercury_pos - sun_pos) % 360
        if angle > 180:
            angle = 360 - angle

        # Mercury and Sun are both in Leo but about 23-24 degrees apart
        assert 23 < angle < 25, f"Mercury-Sun angle {angle} outside expected range"

        # They should not form a conjunction (orb typically 8-10 degrees)
        is_conjunction = aspect_match(
            self.positions, 'Mercury', 'Sun', 'Conjunction')
        assert not is_conjunction, "Mercury and Sun should not be in conjunction"

    def test_saturn_positions_aspects(self):
        """Test Saturn's aspects with other planets."""
        saturn_pos = self.positions['Saturn']  # ~290.9° (Capricorn)

        # Test Saturn's potential aspects
        aspects_found = []
        for planet in self.positions:
            if planet == 'Saturn':
                continue

            for aspect_name in ['Conjunction', 'Opposition', 'Trine', 'Square', 'Sextile']:
                if aspect_match(self.positions, 'Saturn', planet, aspect_name):
                    angle = abs(saturn_pos - self.positions[planet]) % 360
                    if angle > 180:
                        angle = 360 - angle
                    aspects_found.append((planet, aspect_name, angle))

        print(f"Saturn aspects found: {aspects_found}")

        # Verify that any found aspects have correct angles
        for planet, aspect_name, angle in aspects_found:
            expected_angle = ASPECTS[aspect_name]['angle']
            orb = ASPECTS[aspect_name]['orb']
            assert abs(
                angle - expected_angle) <= orb, f"Saturn-{planet} {aspect_name} angle {angle} outside orb {orb}"

    def test_connected_components_basic(self):
        """Test basic connected components functionality."""
        # Create some test edges
        test_nodes = ['Sun', 'Moon', 'Mercury']
        test_edges = [
            (('Sun', 'Mercury'), 'Conjunction'),
            # Venus not in nodes, should be ignored
            (('Moon', 'Venus'), 'Trine')
        ]

        components = connected_components_from_edges(test_nodes, test_edges)

        # Should have components based on actual connections
        assert isinstance(components, list), "Components should be a list"

        # Each component should be a set of connected nodes
        for comp in components:
            assert isinstance(comp, set), "Each component should be a set"
            for node in comp:
                assert node in test_nodes, f"Node {node} not in original nodes"

    def test_aspect_orbs_valid(self):
        """Test that all aspects have valid orb values."""
        for aspect_name, data in ASPECTS.items():
            assert 'angle' in data, f"Aspect {aspect_name} missing angle"
            assert 'orb' in data, f"Aspect {aspect_name} missing orb"
            assert isinstance(data['angle'], (int, float)
                              ), f"Aspect {aspect_name} angle not numeric"
            assert isinstance(data['orb'], (int, float)
                              ), f"Aspect {aspect_name} orb not numeric"
            assert 0 <= data['angle'] <= 180, f"Aspect {aspect_name} angle {data['angle']} outside valid range"
            assert 0 < data['orb'] <= 20, f"Aspect {aspect_name} orb {data['orb']} outside reasonable range"


if __name__ == "__main__":
    pytest.main([__file__])
