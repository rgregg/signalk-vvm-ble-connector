"""Tests for the SignalK Publisher"""

import unittest
from unittest.mock import patch, AsyncMock
from vvm_to_signalk.signalk_publisher import SignalKPublisher, SignalKConfig
from vvm_to_signalk.config_decoder import EngineParameter

class TestSignalKPublisher(unittest.IsolatedAsyncioTestCase):
    """Test the SignalK Publisher"""

    def setUp(self):
        """Set up the test"""
        self.config = SignalKConfig()
        self.config.websocket_url = "ws://localhost:3000/signalk/v1/stream"
        self.health_status = {}
        self.publisher = SignalKPublisher(self.config, self.health_status)

    async def test_generate_delta(self):
        """Test that the delta message is generated correctly"""
        path = "propulsion.port.revolutions"
        value = 1000
        delta = self.publisher.generate_delta(path, value)
        self.assertEqual(delta["context"], "vessels.self")
        self.assertEqual(len(delta["updates"]), 1)
        self.assertEqual(delta["updates"][0]["values"][0]["path"], path)
        self.assertEqual(delta["updates"][0]["values"][0]["value"], value)

    async def test_path_for_parameter(self):
        """Test that the correct SignalK path is generated for a parameter"""
        # Test with engine 0 (port)
        param = EngineParameter(0, 1)
        path = self.publisher.path_for_parameter(param)
        self.assertEqual(path, "propulsion.port.revolutions")

        # Test with engine 1 (starboard)
        param = EngineParameter(256, 1) # 256 is engine 1, 0 is RPM
        path = self.publisher.path_for_parameter(param)
        self.assertEqual(path, "propulsion.starboard.revolutions")

        # Test with another engine id
        param = EngineParameter(512, 1) # 512 is engine 2, 0 is RPM
        path = self.publisher.path_for_parameter(param)
        self.assertEqual(path, "propulsion.2.revolutions")

    @patch('websockets.connect')
    async def test_accept_engine_data(self, mock_connect):
        """Test that engine data is correctly published"""
        # Mock the websocket connection
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        self.publisher.socket_connected = True
        self.publisher._SignalKPublisher__websocket = mock_websocket

        # Test with a known parameter
        param = EngineParameter(0, 1) # Engine 0, RPM
        value = 1500
        await self.publisher.accept_engine_data(param, value)
        mock_websocket.send.assert_called_once()
        
        # Test with an unknown parameter (should not be sent)
        mock_websocket.reset_mock()
        param = EngineParameter(3, 1) # Engine 0, Unknown
        value = 123
        await self.publisher.accept_engine_data(param, value)
        mock_websocket.send.assert_not_called()

        # Test with an unknown parameter (should be sent)
        mock_websocket.reset_mock()
        self.config.send_unknown_parameters = True
        param = EngineParameter(3, 1) # Engine 0, Unknown
        value = 123
        await self.publisher.accept_engine_data(param, value)
        mock_websocket.send.assert_called_once()

if __name__ == '__main__':
    unittest.main()