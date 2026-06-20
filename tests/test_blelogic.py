"""Tests for BLE device logic"""

import logging
import unittest
import asyncio
import sys
from unittest.mock import patch
from bleak import BleakGATTCharacteristic
from bleak.exc import BleakCharacteristicNotFoundError
from vvm_to_signalk.ble_connection import BleDeviceConnection, BleConnectionConfig
from vvm_to_signalk.config_decoder import ConfigDecoder
from vvm_to_signalk.data_dictionary import DataDictionary

logger = logging.getLogger(__name__)

class FakeReceiver:
    """Fake receiver that captures decoded engine data calls."""
    def __init__(self):
        self.calls = []

    async def accept_engine_data(self, item, engine_id, value):
        """Capture a decoded engine data call."""
        self.calls.append((item.id, engine_id, value))

    def update_active_items(self, item_ids):
        """Capture active item IDs."""
        self.active = item_ids


class FakeChar:
    """Minimal stand-in for BleakGATTCharacteristic."""
    def __init__(self, uuid):
        self.uuid = uuid


def test_notification_decodes_all_engines():
    """BLE notification handler decodes multi-engine payloads via the dictionary."""
    health = {}
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), health)
    rx = FakeReceiver()
    conn.accept_data_receiver(rx)
    conn._dictionary = DataDictionary.load()
    conn._max_engines = 2
    # id 1 (RPM), engine1=600 (0x0258), engine2=1000 (0x03E8)
    data = bytearray.fromhex("0100" + "5802" + "e803")
    conn.notification_handler(FakeChar("00000102-0000-1000-8000-ec55f9f5b963"), data)
    # allow the scheduled publish tasks to run
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert (1, 1, 600.0) in rx.calls
    assert (1, 2, 1000.0) in rx.calls


def test_update_active_engines_parses_bitfield():
    """Data-item 10000 (Active Engines) bitfield populates the active-engine set."""
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), {})
    conn._dictionary = DataDictionary.load()
    # id 10000 (0x2710 -> LE "1027"), bitfield 0x03 = engines 1 and 2 active
    conn.notification_handler(FakeChar("00000109-0000-1000-8000-ec55f9f5b963"),
                              bytearray.fromhex("1027" + "03"))
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert conn._active_engine_ids == {1, 2}


def test_inactive_engine_excluded():
    """Values for engines not in the active set are not published."""
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), {})
    rx = FakeReceiver()
    conn.accept_data_receiver(rx)
    conn._dictionary = DataDictionary.load()
    conn._max_engines = 2
    conn._active_engine_ids = {1}  # only engine 1 active
    # id 1 (RPM), engine1=600 (0x0258), engine2=1000 (0x03E8)
    conn.notification_handler(FakeChar("00000102-0000-1000-8000-ec55f9f5b963"),
                              bytearray.fromhex("0100" + "5802" + "e803"))
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert (1, 1, 600.0) in rx.calls
    assert all(engine_id != 2 for _id, engine_id, _value in rx.calls)


def test_failing_receiver_exception_is_logged(caplog):
    """A receiver that raises must have its exception observed and logged,
    not silently swallowed by a fire-and-forget task."""
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), {})

    class FailingReceiver:
        """Receiver that always raises when handed data"""
        async def accept_engine_data(self, item, engine_id, value):
            raise RuntimeError("boom")

        def update_active_items(self, item_ids):
            pass

    conn.accept_data_receiver(FailingReceiver())
    conn._dictionary = DataDictionary.load()
    conn._max_engines = 1

    with caplog.at_level(logging.WARNING, logger="vvm_to_signalk.ble_connection"):
        conn.notification_handler(FakeChar("00000102-0000-1000-8000-ec55f9f5b963"),
                                  bytearray.fromhex("0100" + "5802"))
        # allow the scheduled task and its done-callback to run
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.01))

    assert any("boom" in r.getMessage() for r in caplog.records)


def test_retrieve_device_info_handles_missing_characteristics():
    """A device missing standard characteristics must not crash init."""
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), {})

    class MissingCharsClient:
        """Fake client whose characteristic reads all report 'not found'"""
        is_connected = True

        async def read_gatt_char(self, uuid):
            """Every standard characteristic is absent on this device"""
            raise BleakCharacteristicNotFoundError(uuid)

    # Must not raise even though every characteristic read returns None
    asyncio.get_event_loop().run_until_complete(
        conn._retrieve_device_info(MissingCharsClient()))


class Test_ConnectionLifecycle(unittest.IsolatedAsyncioTestCase):
    """Tests for the connect / reconnect lifecycle"""

    async def test_connection_timeout_passed_to_bleak_client(self):
        """The configured connection timeout must be handed to BleakClient."""
        config = BleConnectionConfig()
        config.device_name = "UnitTestRunner"
        config.connection_timeout = 17.0
        decoder = BleDeviceConnection(config, {})

        captured = {}

        class FakeClient:
            """Records constructor args then bails out of the context manager"""
            def __init__(self, device, disconnected_callback=None, timeout=None, **kwargs):
                captured["timeout"] = timeout

            async def __aenter__(self):
                raise RuntimeError("stop after construction")

            async def __aexit__(self, *args):
                return False

        with patch("vvm_to_signalk.ble_connection.BleakClient", FakeClient):
            await decoder._device_init_and_loop("fake-device")

        assert captured["timeout"] == 17.0

    async def test_run_backs_off_after_failed_connection(self):
        """After a failed connection cycle the loop should wait retry_interval
        before scanning again, instead of busy-looping."""
        config = BleConnectionConfig()
        config.device_name = "UnitTestRunner"
        config.retry_interval = 7
        decoder = BleDeviceConnection(config, {})

        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        cycles = {"n": 0}

        async def fake_scan():
            return "fake-device"

        async def fake_init(_device):
            cycles["n"] += 1
            if cycles["n"] >= 2:
                await decoder.close()
            return False

        decoder._scan_for_device = fake_scan
        decoder._device_init_and_loop = fake_init

        with patch("vvm_to_signalk.ble_connection.asyncio.sleep", fake_sleep):
            await decoder.run(task_group=None)

        assert 7 in sleeps


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
