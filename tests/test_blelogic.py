"""Tests for BLE device logic"""

import logging
import unittest
import asyncio
import sys
from bleak import BleakGATTCharacteristic
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


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stderr)
    logging.getLogger().setLevel(logging.DEBUG)
    unittest.main()
