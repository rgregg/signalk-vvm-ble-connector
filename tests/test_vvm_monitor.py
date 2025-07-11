"""Tests for the VVM Monitor application"""

import unittest
import os
import logging
from unittest.mock import patch
from vvm_to_signalk.vvm_monitor import VVMConfig, VesselViewMobileDataRecorder
from vvm_to_signalk.config_decoder import EngineParameterType

class TestVVMConfig(unittest.TestCase):
    """Test the VVMConfig class"""

    def test_default_config(self):
        """Test that the default configuration is loaded correctly"""
        config = VVMConfig()
        self.assertEqual(config.logging_level, logging.INFO)
        self.assertEqual(config.logging_file, "./logs/vvm_monitor.log")
        self.assertEqual(config.logging_keep, 5)
        self.assertFalse(config.healthcheck_enable)
        self.assertIsNotNone(config.conversions)

    def test_read_dict(self):
        """Test that the configuration is loaded correctly from a dictionary"""
        data = {
            'signalk': {
                'websocket-url': 'ws://localhost:3000/signalk/v1/stream',
                'username': 'testuser',
                'password': 'testpassword'
            },
            'ble-device': {
                'name': 'TestDevice',
                'address': '00:11:22:33:44:55'
            },
            'csv': {
                'enabled': True,
                'filename': '/tmp/test.csv'
            },
            'conversions': {
                'ENGINE_RPM': 'value / 50.0',
                'COOLANT_TEMPERATURE': 'value + 273.15'
            },
            'logging': {
                'level': 'DEBUG',
                'file': '/tmp/test.log',
                'keep': 10
            }
        }
        config = VVMConfig(data)
        self.assertEqual(config.signalk.websocket_url, 'ws://localhost:3000/signalk/v1/stream')
        self.assertEqual(config.signalk.username, 'testuser')
        self.assertEqual(config.signalk.password, 'testpassword')
        self.assertEqual(config.bluetooth.device_name, 'TestDevice')
        self.assertEqual(config.bluetooth.device_address, '00:11:22:33:44:55')
        self.assertTrue(config.csv.enabled)
        self.assertEqual(config.csv.filename, '/tmp/test.csv')
        self.assertTrue(config.conversions.has_conversion(EngineParameterType.ENGINE_RPM))
        self.assertEqual(config.conversions.get_conversion_formula(EngineParameterType.ENGINE_RPM), 'value / 50.0')
        self.assertEqual(config.logging_level, logging.DEBUG)
        self.assertEqual(config.logging_file, '/tmp/test.log')
        self.assertEqual(config.logging_keep, 10)

class TestVesselViewMobileDataRecorder(unittest.TestCase):
    """Test the VesselViewMobileDataRecorder class"""

    @patch('argparse.ArgumentParser.parse_args', return_value=unittest.mock.Mock(signalk_websocket_url='ws://test.com', device_address=None, device_name=None, debug=False, username=None, password=None))
    def test_parse_arguments_signalk_url(self, mock_parse_args):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_arguments(config)
        self.assertEqual(config.signalk.websocket_url, 'ws://test.com')

    @patch('argparse.ArgumentParser.parse_args', return_value=unittest.mock.Mock(signalk_websocket_url=None, device_address='AA:BB:CC:DD:EE:FF', device_name=None, debug=False, username=None, password=None))
    def test_parse_arguments_device_address(self, mock_parse_args):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_arguments(config)
        self.assertEqual(config.bluetooth.device_address, 'AA:BB:CC:DD:EE:FF')

    @patch('argparse.ArgumentParser.parse_args', return_value=unittest.mock.Mock(signalk_websocket_url=None, device_address=None, device_name='MyDevice', debug=False, username=None, password=None))
    def test_parse_arguments_device_name(self, mock_parse_args):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_arguments(config)
        self.assertEqual(config.bluetooth.device_name, 'MyDevice')

    @patch('argparse.ArgumentParser.parse_args', return_value=unittest.mock.Mock(signalk_websocket_url=None, device_address=None, device_name=None, debug=True, username=None, password=None))
    def test_parse_arguments_debug(self, mock_parse_args):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_arguments(config)
        self.assertEqual(config.logging_level, logging.DEBUG)

    @patch.dict(os.environ, {'VVM_SIGNALK_URL': 'ws://env.test.com'})
    def test_parse_env_variables_signalk_url(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertEqual(config.signalk.websocket_url, 'ws://env.test.com')

    @patch.dict(os.environ, {'VVM_DEVICE_ADDRESS': '11:22:33:44:55:66'})
    def test_parse_env_variables_device_address(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertEqual(config.bluetooth.device_address, '11:22:33:44:55:66')

    @patch.dict(os.environ, {'VVM_DEVICE_NAME': 'EnvDevice'})
    def test_parse_env_variables_device_name(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertEqual(config.bluetooth.device_name, 'EnvDevice')

    @patch.dict(os.environ, {'VVM_DEBUG': 'true'})
    def test_parse_env_variables_debug_true(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertEqual(config.logging_level, logging.DEBUG)

    @patch.dict(os.environ, {'VVM_DEBUG': '1'})
    def test_parse_env_variables_debug_1(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertEqual(config.logging_level, logging.DEBUG)

    @patch.dict(os.environ, {'APP_HEALTHCHECK_ENABLE': 'true'})
    def test_parse_env_variables_healthcheck_true(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertTrue(config.healthcheck_enable)

    @patch.dict(os.environ, {'APP_HEALTHCHECK_ENABLE': '0'})
    def test_parse_env_variables_healthcheck_false(self):
        config = VVMConfig()
        VesselViewMobileDataRecorder.parse_env_variables(config)
        self.assertFalse(config.healthcheck_enable)

if __name__ == '__main__':
    unittest.main()