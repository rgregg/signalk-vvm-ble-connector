"""Tests for the SignalK Publisher"""

import unittest
from unittest.mock import AsyncMock
from vvm_to_signalk.signalk_publisher import SignalKPublisher, SignalKConfig


class FakeItem:
    """Minimal stand-in for DataItem used in publisher tests."""
    def __init__(self, item_id=1, name="RPM", units="revs/minute", is_vessel=False):
        self.id = item_id
        self.name = name
        self.units = units
        self.is_vessel = is_vessel


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

    async def test_accept_engine_data_known_path(self):
        """Engine data for a known item is sent with SI-converted value."""
        mock_websocket = AsyncMock()
        self.publisher.socket_connected = True
        self.publisher._SignalKPublisher__websocket = mock_websocket

        item = FakeItem(item_id=1, name="RPM", units="revs/minute")
        await self.publisher.accept_engine_data(item, 1, 600.0)

        mock_websocket.send.assert_called_once()
        import json
        sent = json.loads(mock_websocket.send.call_args[0][0])
        values = sent["updates"][0]["values"]
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["path"], "propulsion.starboard.revolutions")
        self.assertAlmostEqual(values[0]["value"], 600.0 / 60.0)  # Hz

    async def test_accept_engine_data_unknown_skipped(self):
        """Engine data for an unmapped item is skipped by default."""
        mock_websocket = AsyncMock()
        self.publisher.socket_connected = True
        self.publisher._SignalKPublisher__websocket = mock_websocket

        item = FakeItem(item_id=9999, name="UnknownValue", units="")
        await self.publisher.accept_engine_data(item, 1, 42.0)
        mock_websocket.send.assert_not_called()

    async def test_accept_engine_data_unknown_included_when_configured(self):
        """Engine data for an unmapped item is sent when send_unknown_parameters=True."""
        mock_websocket = AsyncMock()
        self.publisher.socket_connected = True
        self.publisher._SignalKPublisher__websocket = mock_websocket
        self.config.send_unknown_parameters = True

        item = FakeItem(item_id=9999, name="UnknownValue", units="")
        await self.publisher.accept_engine_data(item, 1, 42.0)
        mock_websocket.send.assert_called_once()

    def test_update_active_items_is_noop(self):
        """update_active_items should not raise."""
        self.publisher.update_active_items([1, 2, 3])


if __name__ == '__main__':
    unittest.main()
