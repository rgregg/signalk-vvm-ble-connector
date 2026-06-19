import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "vvm_to_signalk" / "data" / "smartcraft_data_items.json"

def test_data_file_has_known_items():
    items = {d["id"]: d for d in json.loads(DATA.read_text())}
    assert len(items) >= 150
    assert items[1]["name"] == "RPM" and items[1]["type"] == "uint2" and items[1]["gain"] == 1.0
    assert items[232]["name"] == "Voltage" and items[232]["gain"] == 0.001
    assert items[181]["name"] == "Oil Pressure" and items[181]["units"] == "kPa"
    assert items[10000]["name"] == "Active Engines"
