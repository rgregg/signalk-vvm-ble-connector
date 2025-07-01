"""Tests for the unit conversion functions"""

import unittest
import math
from vvm_to_signalk.conversion import Conversion


class TestConversion(unittest.TestCase):
    """Test the unit conversion functions"""

    def test_rpm_to_hertz(self):
        """Test conversion of RPM to Hertz"""
        self.assertEqual(Conversion.rpm_to_hertz(60), 1)
        self.assertEqual(Conversion.rpm_to_hertz(120), 2)
        self.assertEqual(Conversion.rpm_to_hertz(0), 0)

    def test_celsius_to_kelvin(self):
        """Test conversion of Celsius to Kelvin"""
        self.assertAlmostEqual(Conversion.celsius_to_kelvin(0), 273.15)
        self.assertAlmostEqual(Conversion.celsius_to_kelvin(100), 373.15)
        self.assertAlmostEqual(Conversion.celsius_to_kelvin(-273.15), 0)

    def test_cl_per_hour_to_m3_per_sec(self):
        """Test conversion of centiliters per hour to cubic meters per second"""
        self.assertAlmostEqual(Conversion.cl_per_hour_to_m3_per_sec(1000), 2.77778e-6)
        self.assertAlmostEqual(Conversion.cl_per_hour_to_m3_per_sec(0), 0)

    def test_decapascals_to_pascals(self):
        """Test conversion of decaPascals to Pascals"""
        self.assertEqual(Conversion.decapascals_to_pascals(10), 100)
        self.assertEqual(Conversion.decapascals_to_pascals(0), 0)

    def test_millivolts_to_volts(self):
        """Test conversion of millivolts to volts"""
        self.assertAlmostEqual(Conversion.millivolts_to_volts(1000), 1.0)
        self.assertAlmostEqual(Conversion.millivolts_to_volts(12500), 12.5)
        self.assertAlmostEqual(Conversion.millivolts_to_volts(0), 0)

    def test_minutes_to_seconds(self):
        """Test conversion of minutes to seconds"""
        self.assertEqual(Conversion.minutes_to_seconds(60), 3600)
        self.assertEqual(Conversion.minutes_to_seconds(30), 1800)
        self.assertEqual(Conversion.minutes_to_seconds(0), 0)

if __name__ == '__main__':
    unittest.main()