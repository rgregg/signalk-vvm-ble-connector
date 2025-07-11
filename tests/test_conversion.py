"""Tests for the unit conversion functions"""

import unittest
from vvm_to_signalk.conversion import Conversion, ConversionConfig
from vvm_to_signalk.config_decoder import EngineParameterType


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


class TestConversionConfig(unittest.TestCase):
    """Test the conversion configuration functionality"""

    def test_default_config(self):
        """Test default configuration with no conversions"""
        config = ConversionConfig()
        self.assertFalse(config.has_conversion(EngineParameterType.ENGINE_RPM))
        self.assertIsNone(config.get_conversion_formula(EngineParameterType.ENGINE_RPM))

    def test_read_config(self):
        """Test reading configuration from dictionary"""
        config_data = {
            "ENGINE_RPM": "value / 60.0",
            "COOLANT_TEMPERATURE": "value + 273.15",
            "BATTERY_VOLTAGE": "value / 1000.0"
        }
        config = ConversionConfig(config_data)
        
        self.assertTrue(config.has_conversion(EngineParameterType.ENGINE_RPM))
        self.assertEqual(config.get_conversion_formula(EngineParameterType.ENGINE_RPM), "value / 60.0")
        
        self.assertTrue(config.has_conversion(EngineParameterType.COOLANT_TEMPERATURE))
        self.assertEqual(config.get_conversion_formula(EngineParameterType.COOLANT_TEMPERATURE), "value + 273.15")
        
        self.assertTrue(config.has_conversion(EngineParameterType.BATTERY_VOLTAGE))
        self.assertEqual(config.get_conversion_formula(EngineParameterType.BATTERY_VOLTAGE), "value / 1000.0")

    def test_unknown_parameter_in_config(self):
        """Test handling of unknown parameter types in config"""
        config_data = {
            "UNKNOWN_PARAMETER": "value * 2",
            "ENGINE_RPM": "value / 60.0"
        }
        config = ConversionConfig(config_data)
        
        # Should ignore unknown parameter but still process valid ones
        self.assertTrue(config.has_conversion(EngineParameterType.ENGINE_RPM))
        self.assertEqual(config.get_conversion_formula(EngineParameterType.ENGINE_RPM), "value / 60.0")

    def test_safe_eval_formula(self):
        """Test safe evaluation of conversion formulas"""
        # Test basic mathematical operations
        self.assertEqual(Conversion.safe_eval_formula("value / 60.0", 120), 2.0)
        self.assertEqual(Conversion.safe_eval_formula("value + 273.15", 25), 298.15)
        self.assertEqual(Conversion.safe_eval_formula("value * 1000", 1.5), 1500)
        self.assertEqual(Conversion.safe_eval_formula("value - 10", 50), 40)
        
        # Test complex formulas
        self.assertEqual(Conversion.safe_eval_formula("(value + 10) * 2", 5), 30)
        self.assertEqual(Conversion.safe_eval_formula("value / 60.0 + 1", 60), 2.0)

    def test_safe_eval_with_unsafe_formula(self):
        """Test that unsafe formulas return original value"""
        # These should return the original value due to safety restrictions
        self.assertEqual(Conversion.safe_eval_formula("import os", 100), 100)
        self.assertEqual(Conversion.safe_eval_formula("open('file')", 100), 100)
        self.assertEqual(Conversion.safe_eval_formula("exec('code')", 100), 100)

    def test_safe_eval_with_invalid_formula(self):
        """Test handling of invalid formulas"""
        # Division by zero should return original value
        self.assertEqual(Conversion.safe_eval_formula("value / 0", 100), 100)
        
        # Invalid syntax should return original value
        self.assertEqual(Conversion.safe_eval_formula("value +", 100), 100)
        self.assertEqual(Conversion.safe_eval_formula("value * (", 100), 100)

    def test_safe_eval_with_none_formula(self):
        """Test handling of None formula"""
        self.assertEqual(Conversion.safe_eval_formula(None, 100), 100)

    def test_convert_with_config(self):
        """Test conversion using configuration"""
        config_data = {
            "ENGINE_RPM": "value / 50.0",  # Custom conversion instead of default /60
            "COOLANT_TEMPERATURE": "value * 1.8 + 32"  # Celsius to Fahrenheit instead of Kelvin
        }
        config = ConversionConfig(config_data)
        
        # Test configured conversion
        result = Conversion.convert_with_config(EngineParameterType.ENGINE_RPM, 100, config)
        self.assertEqual(result, 2.0)  # 100 / 50 = 2
        
        # Test configured conversion for temperature
        result = Conversion.convert_with_config(EngineParameterType.COOLANT_TEMPERATURE, 25, config)
        self.assertEqual(result, 77.0)  # 25 * 1.8 + 32 = 77
        
        # Test parameter without configured conversion (should use default)
        result = Conversion.convert_with_config(EngineParameterType.BATTERY_VOLTAGE, 12000, config)
        self.assertEqual(result, 12.0)  # Default: 12000 / 1000 = 12

    def test_convert_with_no_config(self):
        """Test conversion with no configuration (should use defaults)"""
        # Test without config
        result = Conversion.convert_with_config(EngineParameterType.ENGINE_RPM, 120, None)
        self.assertEqual(result, 2.0)  # Default: 120 / 60 = 2
        
        # Test with empty config
        config = ConversionConfig()
        result = Conversion.convert_with_config(EngineParameterType.ENGINE_RPM, 120, config)
        self.assertEqual(result, 2.0)  # Default: 120 / 60 = 2


if __name__ == '__main__':
    unittest.main()