import json
from pathlib import Path

from vvm_to_signalk.data_dictionary import DataDictionary, decode_notification

DATA = Path(__file__).resolve().parent.parent / "vvm_to_signalk" / "data" / "smartcraft_data_items.json"

def test_data_file_has_known_items():
    items = {d["id"]: d for d in json.loads(DATA.read_text())}
    assert len(items) >= 150
    assert items[1]["name"] == "RPM" and items[1]["type"] == "uint2" and items[1]["gain"] == 1.0
    assert items[232]["name"] == "Voltage" and items[232]["gain"] == 0.001
    assert items[181]["name"] == "Oil Pressure" and items[181]["units"] == "kPa"
    assert items[10000]["name"] == "Active Engines"

def test_decode_rpm_four_engine_layout():
    d = DataDictionary.load()
    # capture: id=1 (00 01 LE), engine1=0x0258=600, engines 2-4 = 0
    data = bytes.fromhex("0100" + "5802" + "0000" + "0000" + "0000")
    item, values = decode_notification(data, d)
    assert item.id == 1 and item.name == "RPM"
    assert values == [600.0, 0.0, 0.0, 0.0]

def test_decode_voltage_applies_gain():
    d = DataDictionary.load()
    data = bytes.fromhex("e800" + "bb38" + "0000" + "0000" + "0000")  # id 232, raw 0x38bb
    item, values = decode_notification(data, d)
    assert item.name == "Voltage"
    assert round(values[0], 3) == 14.523  # 14523 * 0.001

def test_decode_runtime_uint4():
    d = DataDictionary.load()
    data = bytes.fromhex("9600" + "ae160000" + "00000000" + "00000000" + "00000000")  # id 150
    item, values = decode_notification(data, d)
    assert item.name == "Engine Run Time"
    assert values[0] == 5806.0  # minutes

def test_decode_vessel_item_single_value():
    d = DataDictionary.load()
    data = bytes.fromhex("401f" + "00000000")  # id 8000 Fuel Remaining, AccessType Vessel
    item, values = decode_notification(data, d)
    assert item.id == 8000 and item.is_vessel
    assert values == [0.0]

def test_decode_signed_negative():
    d = DataDictionary.load()
    # id 12 Manifold Vacuum, sint2, gain 0.01, raw = -100 (0xFF9C LE)
    data = bytes.fromhex("0c00" + "9cff" + "9cff" + "9cff" + "9cff")
    item, values = decode_notification(data, d)
    assert round(values[0], 2) == -1.0

def test_unknown_id_returns_none():
    d = DataDictionary.load()
    item, values = decode_notification(bytes.fromhex("ffff0000"), d)
    assert item is None and values == []
