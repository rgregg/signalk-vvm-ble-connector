# VVM Full-Data & SignalK Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decode every Vessel View Mobile data item for all engines using the SmartCraft
data dictionary, map each to its correct SignalK path in SI units, and publish engine faults
as SignalK notifications.

**Architecture:** Replace the current slot-index → fixed-enum model with a
**data-dictionary-driven** decoder. A bundled data dictionary (`smartcraft_data_items.json`,
generated from `docs/protocol-map.md §7`) is the single source of truth for each item's
type, gain, units, and access scope. The BLE layer reads the channel→data-item map at
runtime, decodes each notification into per-engine values, and a mapping layer converts to
SI and SignalK paths. A separate fault decoder handles Fault Alert (`0x201`) indications.

**Tech Stack:** Python 3.12, `bleak` (BLE), `websockets` (SignalK), `pytest`. See
`docs/protocol-map.md` for the full protocol reference this plan implements.

## Global Constraints

- **Python 3.12**; no new third-party dependencies (stdlib + existing `bleak`/`websockets`/`pyyaml` only).
- **SignalK values are SI base units** (Hz, K, Pa, V, m³/s, m³, s, ratio, m, m/s).
- **Single source of truth:** all item metadata (type/gain/units/access) comes from the data
  dictionary; never hard-code per-parameter scaling factors in decode logic.
- **All integers from the device are little-endian**, signed per the item's `Type`.
- **Decode by data-item ID** (`uint16 LE` = first 2 notification bytes), not by characteristic.
- Follow existing module style (class-per-file-ish, `logging.getLogger(__name__)`, property-based config objects).
- TDD: write the failing test first; commit after each green task.

---

## File Structure

**Create:**
- `tools/generate_data_items.py` — one-off generator: parses `docs/protocol-map.md §7` → JSON.
- `vvm_to_signalk/data/smartcraft_data_items.json` — bundled data dictionary (generated).
- `vvm_to_signalk/data_dictionary.py` — `DataItemType`, `DataItem`, `DataDictionary`, notification decode.
- `vvm_to_signalk/signalk_mapping.py` — SI unit conversion + data-item → SignalK path.
- `vvm_to_signalk/fault_decoder.py` — `Fault`, `parse_fault`.
- Tests: `tests/test_data_dictionary.py`, `tests/test_signalk_mapping.py`, `tests/test_fault_decoder.py`, `tests/test_channel_map.py`.

**Modify:**
- `vvm_to_signalk/config_decoder.py` — repurpose `ConfigDecoder` to emit active data-item IDs + engine count; retire the slot-index `EngineParameterType`.
- `vvm_to_signalk/ble_connection.py` — dictionary-driven multi-engine decode; subscribe to fault indications.
- `vvm_to_signalk/signalk_publisher.py` — new `accept_engine_data`/`accept_fault`; path+SI via `signalk_mapping`; engine-label config.
- `vvm_to_signalk/conversion.py` — delete (logic moves to `signalk_mapping.py`).
- `vvm_monitor.example.yaml`, `README.md` — document engine labels + new parameters/faults.

---

## Task 1: Bundled data dictionary + generator

**Files:**
- Create: `tools/generate_data_items.py`
- Create: `vvm_to_signalk/data/smartcraft_data_items.json`
- Test: `tests/test_data_dictionary.py` (first test only)

**Interfaces:**
- Produces: `vvm_to_signalk/data/smartcraft_data_items.json` — a JSON array of objects with
  keys `id` (int), `name` (str), `type` (str), `gain` (float), `units` (str),
  `enum` (object `{int_str: str}` or null), `bits` (string or null), `access` (str, e.g.
  `"Channel/Engines"`, `"UserVar/Vessel"`).

- [ ] **Step 1: Write the generator**

```python
# tools/generate_data_items.py
"""Generate vvm_to_signalk/data/smartcraft_data_items.json from docs/protocol-map.md §7."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "protocol-map.md"
OUT = ROOT / "vvm_to_signalk" / "data" / "smartcraft_data_items.json"

def parse_enum(cell: str):
    cell = cell.strip()
    if not (cell.startswith("{") and ":" in cell):
        return None, None
    inner = cell.strip("{}")
    # bits look like "0-1:Name" (start-length); enums look like "0:Name"
    is_bits = bool(re.match(r"\s*\d+\s*-\s*\d+\s*:", inner))
    if is_bits:
        return None, cell
    enum = {}
    for pair in inner.split(","):
        if ":" in pair:
            k, v = pair.split(":", 1)
            enum[k.strip()] = v.strip()
    return (enum or None), None

def main():
    rows = []
    in_table = False
    for line in DOC.read_text().splitlines():
        if line.startswith("| Id | Name |"):
            in_table = True
            continue
        if in_table:
            if not line.startswith("|"):
                break
            if set(line.replace("|", "").strip()) <= {"-"}:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 7 or cells[0] == "Id":
                continue
            enum, bits = parse_enum(cells[5])
            rows.append({
                "id": int(cells[0]),
                "name": cells[1],
                "type": cells[2],
                "gain": float(cells[3]) if cells[3] not in ("-", "") else 1.0,
                "units": cells[4],
                "enum": enum,
                "bits": bits,
                "access": cells[6],
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"wrote {len(rows)} items to {OUT}")

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the generator**

Run: `python tools/generate_data_items.py`
Expected: `wrote 153 items to .../smartcraft_data_items.json`

- [ ] **Step 3: Write a sanity test on the generated data**

```python
# tests/test_data_dictionary.py
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
```

- [ ] **Step 4: Run the test**

Run: `pytest tests/test_data_dictionary.py::test_data_file_has_known_items -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/generate_data_items.py vvm_to_signalk/data/smartcraft_data_items.json tests/test_data_dictionary.py
git commit -m "feat: bundle SmartCraft data dictionary generated from protocol map"
```

---

## Task 2: Data dictionary model & notification decode

**Files:**
- Create: `vvm_to_signalk/data_dictionary.py`
- Test: `tests/test_data_dictionary.py` (add)

**Interfaces:**
- Consumes: `smartcraft_data_items.json` (Task 1).
- Produces:
  - `DataItemType` enum-like with `size(type_str) -> int` and `signed(type_str) -> bool`.
  - `class DataItem` with attrs `id:int, name:str, type:str, gain:float, units:str, access:str, enum:dict|None, bits:str|None`, properties `value_size:int`, `signed:bool`, `is_vessel:bool`, and method `decode_values(payload: bytes, max_engines: int=4) -> list[float]`.
  - `class DataDictionary` with classmethod `load() -> DataDictionary` and `by_id(item_id:int) -> DataItem|None`.
  - `decode_notification(data: bytes, dictionary: DataDictionary, max_engines: int=4) -> tuple[DataItem|None, list[float]]` — reads `id = int.from_bytes(data[:2],"little")`, looks it up, returns `(item, per_engine_values)`. Returns `(None, [])` for unknown ID.

- [ ] **Step 1: Write the failing tests (real capture bytes)**

```python
# tests/test_data_dictionary.py  (append)
from vvm_to_signalk.data_dictionary import DataDictionary, decode_notification

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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_dictionary.py -v`
Expected: FAIL with `ModuleNotFoundError: vvm_to_signalk.data_dictionary`

- [ ] **Step 3: Implement the module**

```python
# vvm_to_signalk/data_dictionary.py
"""SmartCraft data dictionary: decode VVM notifications into engineering values."""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_FILE = Path(__file__).resolve().parent / "data" / "smartcraft_data_items.json"

# type name -> (byte width, signed)
_TYPE_SIZES = {
    "uint1": (1, False), "uint2": (2, False), "uint3": (3, False),
    "uint4": (4, False), "uint8": (8, False),
    "sint1": (1, True), "sint2": (2, True), "sint3": (3, True),
    "sint4": (4, True), "sint8": (8, True),
    "boolean": (1, False), "Flag": (1, False), "8bit": (1, False),
    "16bit": (2, False), "string": (0, False), "null": (0, False),
}


class DataItemType:
    """Helpers for the SmartCraft type strings."""

    @staticmethod
    def size(type_str: str) -> int:
        return _TYPE_SIZES.get(type_str, (0, False))[0]

    @staticmethod
    def signed(type_str: str) -> bool:
        return _TYPE_SIZES.get(type_str, (0, False))[1]


class DataItem:
    """A single SmartCraft data item and how to decode its value(s)."""

    def __init__(self, record: dict):
        self.id = record["id"]
        self.name = record["name"]
        self.type = record["type"]
        self.gain = record.get("gain", 1.0)
        self.units = record.get("units", "")
        self.access = record.get("access", "")
        self.enum = record.get("enum")
        self.bits = record.get("bits")

    def __str__(self):
        return f"DataItem(id={self.id}, name={self.name!r}, type={self.type}, units={self.units})"

    @property
    def value_size(self) -> int:
        return DataItemType.size(self.type)

    @property
    def signed(self) -> bool:
        return DataItemType.signed(self.type)

    @property
    def is_vessel(self) -> bool:
        return self.access.endswith("Vessel")

    def decode_values(self, payload: bytes, max_engines: int = 4) -> list[float]:
        """Decode the per-engine values that follow the 2-byte ID.

        Vessel items carry a single value; engine items carry one value per engine
        (the device sends a slot for every engine up to max_engines). Each value is
        little-endian, signed per type, then multiplied by gain.
        """
        size = self.value_size
        if size == 0:
            return []
        count = 1 if self.is_vessel else min(max_engines, len(payload) // size)
        values = []
        for i in range(count):
            chunk = payload[i * size:(i + 1) * size]
            if len(chunk) < size:
                break
            raw = int.from_bytes(chunk, byteorder="little", signed=self.signed)
            values.append(raw * self.gain)
        return values


class DataDictionary:
    """Lookup table of DataItem by ID, loaded from the bundled JSON."""

    def __init__(self, items: dict[int, DataItem]):
        self._items = items

    @classmethod
    def load(cls, path: Path = _DATA_FILE) -> "DataDictionary":
        records = json.loads(Path(path).read_text())
        return cls({r["id"]: DataItem(r) for r in records})

    def by_id(self, item_id: int) -> DataItem | None:
        return self._items.get(item_id)


def decode_notification(data: bytes, dictionary: DataDictionary,
                        max_engines: int = 4) -> tuple[DataItem | None, list[float]]:
    """Decode a channel notification into (DataItem, per-engine values)."""
    if data is None or len(data) < 2:
        return None, []
    item_id = int.from_bytes(data[:2], byteorder="little")
    item = dictionary.by_id(item_id)
    if item is None:
        logger.debug("Unknown data-item ID %s in notification %s", item_id, data.hex())
        return None, []
    return item, item.decode_values(data[2:], max_engines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_dictionary.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/data_dictionary.py tests/test_data_dictionary.py
git commit -m "feat: data-dictionary-driven multi-engine notification decode"
```

---

## Task 3: SI unit conversion

**Files:**
- Create: `vvm_to_signalk/signalk_mapping.py` (first half)
- Test: `tests/test_signalk_mapping.py`

**Interfaces:**
- Produces: `to_si(value: float, units: str) -> float` — converts a value in the data
  dictionary's `units` to SignalK SI units. Unknown/unitless units pass through unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signalk_mapping.py
import math
from vvm_to_signalk.signalk_mapping import to_si

def test_rpm_to_hz():
    assert to_si(600.0, "revs/minute") == 10.0

def test_celsius_to_kelvin():
    assert to_si(0.0, "degrees C") == 273.15

def test_kpa_to_pascals():
    assert to_si(295.42, "kPa") == 295420.0

def test_liters_per_hour_to_m3_per_s():
    assert math.isclose(to_si(3600.0, "liters/hour"), 0.001, rel_tol=1e-9)

def test_liters_to_m3():
    assert to_si(1000.0, "liters") == 1.0

def test_minutes_to_seconds():
    assert to_si(5806.0, "minutes") == 348360.0

def test_percent_to_ratio():
    assert to_si(50.0, "percent") == 0.5

def test_kmh_to_ms():
    assert math.isclose(to_si(3.6, "km/hour"), 1.0, rel_tol=1e-9)

def test_volts_passthrough():
    assert to_si(14.523, "volts") == 14.523

def test_unknown_unit_passthrough():
    assert to_si(42.0, "A/D Counts") == 42.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_signalk_mapping.py -v`
Expected: FAIL with `ModuleNotFoundError: vvm_to_signalk.signalk_mapping`

- [ ] **Step 3: Implement `to_si`**

```python
# vvm_to_signalk/signalk_mapping.py
"""Map SmartCraft data items to SignalK paths and SI units."""
import logging

logger = logging.getLogger(__name__)

# Convert a value in the dictionary's units to SignalK SI base units.
_SI_CONVERTERS = {
    "revs/minute": lambda v: v / 60.0,        # Hz
    "degrees C": lambda v: v + 273.15,        # K
    "kPa": lambda v: v * 1000.0,              # Pa
    "liters/hour": lambda v: v / 3_600_000.0, # m3/s
    "liters": lambda v: v / 1000.0,           # m3
    "minutes": lambda v: v * 60.0,            # s
    "percent": lambda v: v / 100.0,           # ratio
    "km/hour": lambda v: v / 3.6,             # m/s
    "volts": lambda v: v,                     # V
    "meters": lambda v: v,                    # m
    "Hz": lambda v: v,
}


def to_si(value: float, units: str) -> float:
    """Convert a value from dictionary units to SignalK SI units (passthrough if unknown)."""
    converter = _SI_CONVERTERS.get(units)
    if converter is None:
        return value
    return converter(value)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_signalk_mapping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/signalk_mapping.py tests/test_signalk_mapping.py
git commit -m "feat: SI unit conversion for SignalK"
```

---

## Task 4: SignalK path mapping + engine labels

**Files:**
- Modify: `vvm_to_signalk/signalk_mapping.py` (add path mapping)
- Test: `tests/test_signalk_mapping.py` (add)

**Interfaces:**
- Consumes: `DataItem` (Task 2).
- Produces:
  - `engine_label(engine_id: int, labels: dict[int, str] | None = None) -> str` — default
    `{1:"starboard", 2:"port", 3:"3", 4:"4"}` (preserves current single-engine behavior).
  - `signalk_path(item, engine_id: int, labels: dict[int,str]|None=None, include_unmapped: bool=False) -> str | None`
    — returns the full SignalK path, or `None` when the item is unmapped and
    `include_unmapped` is False. Vessel-scope items ignore `engine_id`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signalk_mapping.py  (append)
from vvm_to_signalk.data_dictionary import DataDictionary
from vvm_to_signalk.signalk_mapping import engine_label, signalk_path

D = DataDictionary.load()

def test_engine_label_defaults():
    assert engine_label(1) == "starboard"
    assert engine_label(2) == "port"
    assert engine_label(3) == "3"

def test_engine_label_override():
    assert engine_label(1, {1: "main"}) == "main"

def test_path_rpm():
    assert signalk_path(D.by_id(1), 1) == "propulsion.starboard.revolutions"

def test_path_oil_pressure():
    assert signalk_path(D.by_id(181), 2) == "propulsion.port.oilPressure"

def test_path_block_pressure_is_coolant_pressure():
    assert signalk_path(D.by_id(212), 1) == "propulsion.starboard.coolantPressure"

def test_path_seawater_is_vessel_environment():
    assert signalk_path(D.by_id(251), 1) == "environment.water.temperature"

def test_path_fuel_remaining_tank():
    assert signalk_path(D.by_id(8000), 1) == "tanks.fuel.0.currentVolume"

def test_unmapped_returns_none_by_default():
    assert signalk_path(D.by_id(87), 1) is None  # Guardian Cause, unmapped

def test_unmapped_with_include_flag():
    assert signalk_path(D.by_id(87), 1, include_unmapped=True) == "propulsion.starboard.vvm.guardianCause"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_signalk_mapping.py -v`
Expected: FAIL with `ImportError: cannot import name 'signalk_path'`

- [ ] **Step 3: Implement path mapping**

```python
# vvm_to_signalk/signalk_mapping.py  (append)
import re

_DEFAULT_LABELS = {1: "starboard", 2: "port", 3: "3", 4: "4"}

# data-item id -> SignalK path template. "{engine}" is filled for engine-scope items.
# Vessel-scope items use a fixed path (no {engine}).
_PATH_MAP = {
    1:    "propulsion.{engine}.revolutions",
    3:    "propulsion.{engine}.boostPressure",
    10:   "propulsion.{engine}.fuel.rate",
    52:   "propulsion.{engine}.engineLoad",
    143:  "propulsion.{engine}.intakeManifoldTemperature",
    150:  "propulsion.{engine}.runTime",
    181:  "propulsion.{engine}.oilPressure",
    182:  "propulsion.{engine}.oilTemperature",
    210:  "propulsion.{engine}.coolantTemperature",
    211:  "propulsion.{engine}.coolantTemperature",
    212:  "propulsion.{engine}.coolantPressure",   # Block Pressure
    230:  "environment.outside.pressure",
    231:  "environment.water.temperature",
    232:  "propulsion.{engine}.alternatorVoltage",
    250:  "environment.depth.belowTransducer",
    251:  "environment.water.temperature",
    252:  "navigation.speedThroughWater",
    300:  "propulsion.{engine}.runTime",
    6000: "propulsion.{engine}.fuel.used",
    6004: "propulsion.{engine}.fuel.rate",
    8000: "tanks.fuel.0.currentVolume",
}


def engine_label(engine_id: int, labels: dict[int, str] | None = None) -> str:
    """Resolve an engine id to a SignalK instance label."""
    table = labels or _DEFAULT_LABELS
    return table.get(engine_id, str(engine_id))


def _camel(name: str) -> str:
    parts = re.split(r"[^0-9A-Za-z]+", name.strip())
    parts = [p for p in parts if p]
    if not parts:
        return "value"
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])


def signalk_path(item, engine_id: int, labels: dict[int, str] | None = None,
                 include_unmapped: bool = False) -> str | None:
    """Return the SignalK path for an item, or None if unmapped and not included."""
    template = _PATH_MAP.get(item.id)
    if template is not None:
        return template.format(engine=engine_label(engine_id, labels))
    if not include_unmapped:
        return None
    prop = _camel(item.name)
    if item.is_vessel:
        return f"vvm.{prop}"
    return f"propulsion.{engine_label(engine_id, labels)}.vvm.{prop}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_signalk_mapping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/signalk_mapping.py tests/test_signalk_mapping.py
git commit -m "feat: map SmartCraft data items to SignalK paths"
```

---

## Task 5: Runtime channel map (refactor ConfigDecoder)

**Files:**
- Modify: `vvm_to_signalk/config_decoder.py`
- Test: `tests/test_channel_map.py`

**Interfaces:**
- Consumes: raw config-response bytes (the multi-part indication after `28 00 03 01`).
- Produces (replacing `EngineParameter`/`EngineParameterType`):
  - `ConfigDecoder.add(item)` (unchanged signature).
  - `ConfigDecoder.active_data_item_ids() -> list[int]` — the data-item IDs the device will
    stream (slot pairs whose header/id is non-zero), in slot order, parsed little-endian.
  - `ConfigDecoder.has_all_data` (unchanged behavior).
- Keep `EngineDataReceiver` Protocol but update method signatures (see Task 6).

> The config response is `28 <len:2> <magic:2>` then 4-byte pairs `slot(uint16) id(uint16)`.
> Per `docs/protocol-map.md §2.3`, the **id is little-endian** and equals a data-dictionary
> ID; a zero id means the slot is unused.

- [ ] **Step 1: Write the failing test (captured config response)**

```python
# tests/test_channel_map.py
from vvm_to_signalk.config_decoder import ConfigDecoder

# Reassembled config response. Layout matches ConfigDecoder.parse_params:
#   byte0 = 0x28; byte1 = payload length (1 byte); byte2 = 0x00;
#   bytes3.. = payload = magic(2) + 4-byte (slot, id) pairs; id is little-endian.
# 6 pairs (24B) + magic (2B) = 26B payload -> length byte = 0x1a.
# Pairs (LE id): slot0->1(RPM) slot1->210 slot2->232 slot3->6000 slot4->150 slot5->10
RAW = bytes.fromhex(
    "28" "1a" "00"   # header: marker, length=26, spacer
    "0100"           # magic (discarded)
    "0000" "0100"    # slot 0 -> id 0x0001 = 1
    "0100" "d200"    # slot 1 -> id 0x00d2 = 210
    "0200" "e800"    # slot 2 -> id 0x00e8 = 232
    "0300" "7017"    # slot 3 -> id 0x1770 = 6000
    "0400" "9600"    # slot 4 -> id 0x0096 = 150
    "0500" "0a00"    # slot 5 -> id 0x000a = 10
)

def _packetize(raw: bytes) -> list[bytes]:
    # Re-create the indication chunks: each prefixed with a sequence byte,
    # as ConfigDecoder.combine_and_parse_data expects (sorts by, then strips, byte 0).
    chunks = [raw[i:i + 19] for i in range(0, len(raw), 19)]
    return [bytes([i]) + c for i, c in enumerate(chunks)]

def test_active_ids_parsed_little_endian():
    dec = ConfigDecoder()
    dec.add(_packetize(RAW))
    assert dec.has_all_data
    assert dec.active_data_item_ids() == [1, 210, 232, 6000, 150, 10]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_channel_map.py -v`
Expected: FAIL with `AttributeError: 'ConfigDecoder' object has no attribute 'active_data_item_ids'`

- [ ] **Step 3: Refactor ConfigDecoder**

Replace the body of `parse_params` (currently building `EngineParameter` objects) with
data-item ID extraction, and add the accessor. Keep `add`, `has_all_data`,
`combine_and_parse_data`, and `pop_bytes` as they are. Replace the parameter-storage parts:

```python
# vvm_to_signalk/config_decoder.py  (within parse_params, replace the parse loop)
        magic_number, parsing_data = ConfigDecoder.pop_bytes(combined_data[3:], 2)
        logger.debug("Magic number was %s", magic_number.hex())
        found_ids = []
        while len(parsing_data) != 0:
            next_pair, parsing_data = ConfigDecoder.pop_bytes(parsing_data, 4)
            # bytes 0-1 = slot index, bytes 2-3 = data-item id (little-endian)
            data_item_id = int.from_bytes(next_pair[2:4], byteorder="little")
            if data_item_id != 0:
                found_ids.append(data_item_id)
            remaining_bytes = len(parsing_data)
            if 0 < remaining_bytes < 4:
                logger.debug("Remaining bytes (%s) indicate incomplete data.", remaining_bytes)
                self.has_all_data = False
                raise ValueError("Incorrect data length.")

        self.__active_ids = found_ids
        self.has_all_data = True
        return found_ids
```

Add the storage init in `__init__` (`self.__active_ids = []`) and the accessor:

```python
    def active_data_item_ids(self) -> list[int]:
        """Data-item IDs the device will stream, in slot order (zero slots dropped)."""
        if self.__has_all_data is None:
            self.has_all_data  # trigger parse
        return self.__active_ids
```

Delete the `EngineParameterType` enum and `EngineParameter` class (replaced by the data
dictionary). Update `EngineDataReceiver` to the new signatures:

```python
class EngineDataReceiver(Protocol):
    """Protocol for classes that can receive decoded engine data."""
    async def accept_engine_data(self, item, engine_id: int, value: float) -> None:
        ...

    def update_active_items(self, item_ids: list[int]) -> None:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_channel_map.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/config_decoder.py tests/test_channel_map.py
git commit -m "refactor: parse runtime channel map into active data-item IDs"
```

---

## Task 6: Wire dictionary decode into the BLE layer

**Files:**
- Modify: `vvm_to_signalk/ble_connection.py`
- Modify: `vvm_to_signalk/signalk_publisher.py`
- Delete: `vvm_to_signalk/conversion.py`
- Test: `tests/test_blelogic.py` (update existing), `tests/test_signalk_publisher.py` (update)

**Interfaces:**
- Consumes: `DataDictionary`, `decode_notification` (Task 2); `signalk_path`, `to_si` (Tasks 3–4); `ConfigDecoder.active_data_item_ids` (Task 5).
- Produces: BLE layer calls `receiver.accept_engine_data(item, engine_id, value_in_units)`
  for each engine value of each channel notification, and tracks the active-engine set from
  data-item 10000.

- [ ] **Step 1: Write the failing test (fake receiver captures decoded values)**

```python
# tests/test_blelogic.py  (add; keep existing tests that still apply)
import asyncio
from vvm_to_signalk.ble_connection import BleDeviceConnection, BleConnectionConfig
from vvm_to_signalk.data_dictionary import DataDictionary

class FakeReceiver:
    def __init__(self):
        self.calls = []
    async def accept_engine_data(self, item, engine_id, value):
        self.calls.append((item.id, engine_id, value))
    def update_active_items(self, item_ids):
        self.active = item_ids

class FakeChar:
    def __init__(self, uuid):
        self.uuid = uuid

def test_notification_decodes_all_engines():
    health = {}
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), health)
    rx = FakeReceiver()
    conn.accept_data_receiver(rx)
    conn._dictionary = DataDictionary.load()
    conn._max_engines = 2
    # id 1 (RPM), engine1=600, engine2=1000 (0x03E8)
    data = bytearray.fromhex("0100" + "5802" + "e803")
    conn.notification_handler(FakeChar("00000102-0000-1000-8000-ec55f9f5b963"), data)
    # allow the scheduled publish tasks to run
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert (1, 1, 600.0) in rx.calls
    assert (1, 2, 1000.0) in rx.calls
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_blelogic.py::test_notification_decodes_all_engines -v`
Expected: FAIL (current handler matches by header and produces one int value)

- [ ] **Step 3: Update the BLE notification path**

In `ble_connection.py`: import the new modules, hold a `DataDictionary`, replace
`notification_handler`'s engine-data branch and delete the slot-index matching.

```python
# vvm_to_signalk/ble_connection.py  (imports)
from .config_decoder import ConfigDecoder, EngineDataReceiver
from .data_dictionary import DataDictionary, decode_notification
```

```python
# in __init__:
        self._dictionary = DataDictionary.load()
        self._max_engines = 4
        self._active_engine_ids = None   # set from data-item 10000
```

```python
# replace notification_handler body (engine-data portion):
    def notification_handler(self, characteristic: BleakGATTCharacteristic, data: bytearray):
        """Handles BLE notifications and indications."""
        self.__last_message_time = asyncio.get_event_loop().time()
        uuid = characteristic.uuid
        logger.debug("Notification UUID %s data %s", uuid, data.hex())

        # Fault Alert characteristic is handled separately (Task 8).
        if uuid == UUIDs.DEVICE_201_UUID:
            self._handle_fault_notification(bytes(data))
            return

        # Config / UserVar exchanges are resolved via registered futures, not decoded
        # as channel data (avoids "unmatched data" noise on every engine notification).
        if uuid in (UUIDs.DEVICE_CONFIG_UUID, UUIDs.DEVICE_NEXT_UUID):
            self._trigger_event_listener(uuid, data, True)
            return

        item, values = decode_notification(bytes(data), self._dictionary, self._max_engines)
        if item is None:
            return
        if item.id == 10000:
            self._update_active_engines(bytes(data))
            return
        for index, value in enumerate(values):
            engine_id = index + 1
            if self._active_engine_ids is not None and engine_id not in self._active_engine_ids:
                continue
            self._publish_engine_value(item, engine_id, value)
```

```python
# new helpers:
    def _publish_engine_value(self, item, engine_id, value):
        for receiver in self.__data_receivers:
            loop = asyncio.get_event_loop()
            loop.create_task(receiver.accept_engine_data(item, engine_id, value))

    def _update_active_engines(self, data: bytes):
        # data-item 10000 is a 1-byte bitfield after the 2-byte id
        if len(data) >= 3:
            bits = data[2]
            self._active_engine_ids = {e for e in (1, 2, 3, 4) if bits & (1 << (e - 1))}
            logger.info("Active engines: %s", sorted(self._active_engine_ids))
```

Update `update_engine_params` → `update_active_items` and call it from
`_request_device_parameter_config` using `decoder.active_data_item_ids()`:

```python
    def update_active_items(self, item_ids: list[int]) -> None:
        for receiver in self.__data_receivers:
            receiver.update_active_items(item_ids)
```

In `_request_device_parameter_config`, replace
`engine_parameters = decoder.combine_and_parse_data(); return engine_parameters` with:

```python
                decoder.combine_and_parse_data()
                return decoder.active_data_item_ids()
```

and in `_initalize_vvm` replace `self.update_engine_params(engine_params)` with
`self.update_active_items(engine_params)` (variable now a list of ints).

Delete `_strip_header_and_convert_to_int`, `_publish_data`, `update_engine_params`, and the
`self.__engine_parameters` dict.

- [ ] **Step 4: Update the publisher to the new signature**

```python
# vvm_to_signalk/signalk_publisher.py
from .signalk_mapping import signalk_path, to_si, engine_label  # replaces conversion import
```

Replace `convert_value`, `PATH_MAP`, `path_for_parameter`, `update_engine_parameters`, and
`accept_engine_data` with:

```python
    def update_active_items(self, item_ids):
        """No-op: the publisher maps each value as it arrives."""

    async def accept_engine_data(self, item, engine_id, value):
        """Publish a decoded engine value as a SignalK delta."""
        path = signalk_path(item, engine_id, self.__config.engine_labels,
                            include_unmapped=self.__config.send_unknown_parameters)
        if path is None:
            logger.debug("No SignalK path for %s; skipping", item.name)
            return
        si_value = to_si(value, item.units)
        if self.socket_connected:
            delta = self.generate_delta(path, si_value)
            try:
                await self.__websocket.send(json.dumps(delta))
                self.__should_log_connection_down = True
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Websocket closed; delta not published.")
            except Exception as e:
                logger.warning("Error sending on websocket: %s", e)
```

Add `engine_labels` to `SignalKConfig` (Task 9 wires YAML; default here):

```python
        self.__engine_labels = None   # in __init__
    @property
    def engine_labels(self):
        return self.__engine_labels
```

- [ ] **Step 5: Update affected existing tests and delete conversion.py**

Update `tests/test_conversion.py` → remove (or convert to `test_signalk_mapping` cases) and
`tests/test_signalk_publisher.py` to use `accept_engine_data(item, engine_id, value)`.
Delete `vvm_to_signalk/conversion.py` and `tests/test_conversion.py`.

```bash
git rm vvm_to_signalk/conversion.py tests/test_conversion.py
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: PASS (update any remaining references to removed symbols until green)

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: dictionary-driven multi-engine decode in BLE + publisher"
```

---

## Task 7: Fault decoder

**Files:**
- Create: `vvm_to_signalk/fault_decoder.py`
- Test: `tests/test_fault_decoder.py`

**Interfaces:**
- Produces:
  - `class Fault` with attrs `fault_type:str` (`"Legacy"|"Universal"|"Unknown"`),
    `engine_position:int`, `is_active:bool`, `fault_id:int`, `failure_type_id:int|None`,
    `severity:int|None`, `action_id:int|None`, and property `fault_key:str`.
  - `parse_fault(data: bytes) -> Fault | None` — 4 bytes → Legacy, 9 bytes → Universal, else None.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fault_decoder.py
from vvm_to_signalk.fault_decoder import parse_fault

def test_legacy_fault():
    # byte0: type=2 (Legacy) low nibble, engine=1 high nibble -> 0x12
    # byte1: active bit -> 0x01 ; bytes2-3: fault id 0x0457 = 1111 (LE 57 04)
    f = parse_fault(bytes.fromhex("12" "01" "5704"))
    assert f.fault_type == "Legacy"
    assert f.engine_position == 1
    assert f.is_active is True
    assert f.fault_id == 1111
    assert f.fault_key == "1111-Legacy"

def test_legacy_fault_cleared():
    f = parse_fault(bytes.fromhex("12" "00" "5704"))
    assert f.is_active is False

def test_universal_fault_bitfields():
    # Construct a uint64 with known fields, take 7 LE bytes after the 2-byte header.
    severity, action, longid, shortid, failure, fault_id = 5, 300, 1000, 1500, 12, 2222
    packed = (severity & 0x7) | ((action & 0x1FF) << 3) | ((longid & 0x7FF) << 12) \
        | ((shortid & 0x7FF) << 23) | ((failure & 0x7F) << 35) | ((fault_id & 0xFFFF) << 42)
    body = packed.to_bytes(8, "little")[:7]
    data = bytes([0x21, 0x01]) + body  # type=1 Universal, engine=2, active
    f = parse_fault(data)
    assert f.fault_type == "Universal"
    assert f.engine_position == 2
    assert f.severity == 5
    assert f.failure_type_id == 12
    assert f.fault_id == 2222
    assert f.fault_key == "2222-12"

def test_bad_length_returns_none():
    assert parse_fault(bytes.fromhex("0000")) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fault_decoder.py -v`
Expected: FAIL with `ModuleNotFoundError: vvm_to_signalk.fault_decoder`

- [ ] **Step 3: Implement the fault decoder**

```python
# vvm_to_signalk/fault_decoder.py
"""Decode VVM Fault Alert (0x201) indications. See docs/protocol-map.md §3."""
import logging

logger = logging.getLogger(__name__)

_FAULT_TYPES = {0: "Unknown", 1: "Universal", 2: "Legacy"}


class Fault:
    """A decoded engine fault event."""

    def __init__(self, fault_type, engine_position, is_active, fault_id,
                 failure_type_id=None, severity=None, action_id=None):
        self.fault_type = fault_type
        self.engine_position = engine_position
        self.is_active = is_active
        self.fault_id = fault_id
        self.failure_type_id = failure_type_id
        self.severity = severity
        self.action_id = action_id

    def __str__(self):
        return (f"Fault(type={self.fault_type}, engine={self.engine_position}, "
                f"active={self.is_active}, key={self.fault_key})")

    @property
    def fault_key(self) -> str:
        if self.fault_type == "Universal":
            return f"{self.fault_id}-{self.failure_type_id}"
        return f"{self.fault_id}-Legacy"


def _common_header(data: bytes):
    fault_type = _FAULT_TYPES.get(data[0] & 0x0F, "Unknown")
    engine_position = data[0] >> 4
    is_active = bool(data[1] & 0x01)
    return fault_type, engine_position, is_active


def parse_fault(data: bytes) -> Fault | None:
    """Parse a Fault Alert payload (4 bytes = Legacy, 9 bytes = Universal)."""
    if data is None:
        return None
    if len(data) == 4:
        fault_type, engine, active = _common_header(data)
        fault_id = int.from_bytes(data[2:4], byteorder="little")
        return Fault(fault_type, engine, active, fault_id)
    if len(data) == 9:
        fault_type, engine, active = _common_header(data)
        body = data[2:9].ljust(8, b"\x00")
        num = int.from_bytes(body, byteorder="little")
        severity = num & 0x7
        action_id = (num & 0xFF8) >> 3
        # long_id = (num & 0x7FF000) >> 12  # not currently published
        # short_id = (num & 0x7FF800000) >> 23
        failure_type_id = (num & 0x3F800000000) >> 35
        fault_id = (num & 0xFFFC0000000000) >> 42
        return Fault(fault_type, engine, active, fault_id,
                     failure_type_id=failure_type_id, severity=severity, action_id=action_id)
    logger.warning("Unexpected fault payload length %s: %s", len(data), data.hex())
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fault_decoder.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/fault_decoder.py tests/test_fault_decoder.py
git commit -m "feat: decode VVM Legacy/Universal fault payloads"
```

---

## Task 8: Subscribe to faults & publish notifications

**Files:**
- Modify: `vvm_to_signalk/ble_connection.py`
- Modify: `vvm_to_signalk/signalk_publisher.py`
- Test: `tests/test_signalk_publisher.py` (add)

**Interfaces:**
- Consumes: `parse_fault`, `Fault` (Task 7); `engine_label` (Task 4).
- Produces:
  - BLE: `_handle_fault_notification(data: bytes)` (referenced in Task 6) parses the fault
    and calls `receiver.accept_fault(fault)` on each receiver.
  - `EngineDataReceiver.accept_fault(fault) -> None` (add to Protocol).
  - Publisher: `accept_fault` emits a SignalK delta on
    `notifications.propulsion.<label>.vvmFault.<fault_key>` with value
    `{"state": "alarm"|"normal", "method": [...], "message": str, "vvm": {...}}`.

- [ ] **Step 1: Write the failing test (publisher fault delta)**

```python
# tests/test_signalk_publisher.py  (add)
import asyncio, json
from vvm_to_signalk.signalk_publisher import SignalKPublisher, SignalKConfig
from vvm_to_signalk.fault_decoder import Fault

class FakeWS:
    def __init__(self): self.sent = []
    async def send(self, msg): self.sent.append(json.loads(msg))

def test_accept_fault_emits_notification():
    pub = SignalKPublisher(SignalKConfig({"websocket-url": "ws://x"}), {})
    ws = FakeWS()
    pub._SignalKPublisher__websocket = ws
    pub.socket_connected = True
    fault = Fault("Legacy", 1, True, 1111)
    asyncio.get_event_loop().run_until_complete(pub.accept_fault(fault))
    delta = ws.sent[0]["updates"][0]["values"][0]
    assert delta["path"] == "notifications.propulsion.starboard.vvmFault.1111-Legacy"
    assert delta["value"]["state"] == "alarm"
    assert delta["value"]["vvm"]["faultId"] == 1111

def test_accept_fault_cleared_is_normal():
    pub = SignalKPublisher(SignalKConfig({"websocket-url": "ws://x"}), {})
    ws = FakeWS(); pub._SignalKPublisher__websocket = ws; pub.socket_connected = True
    asyncio.get_event_loop().run_until_complete(pub.accept_fault(Fault("Legacy", 1, False, 1111)))
    assert ws.sent[0]["updates"][0]["values"][0]["value"]["state"] == "normal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_signalk_publisher.py -v`
Expected: FAIL with `AttributeError: 'SignalKPublisher' object has no attribute 'accept_fault'`

- [ ] **Step 3: Implement publisher.accept_fault**

```python
# vvm_to_signalk/signalk_publisher.py  (add to SignalKPublisher)
    async def accept_fault(self, fault):
        """Publish a fault as a SignalK notification delta."""
        label = engine_label(fault.engine_position, self.__config.engine_labels)
        path = f"notifications.propulsion.{label}.vvmFault.{fault.fault_key}"
        value = {
            "state": "alarm" if fault.is_active else "normal",
            "method": ["visual", "sound"] if fault.is_active else [],
            "message": f"Engine {fault.engine_position} fault {fault.fault_key}"
                       + ("" if fault.is_active else " cleared"),
            "vvm": {
                "faultId": fault.fault_id,
                "failureTypeId": fault.failure_type_id,
                "severity": fault.severity,
                "type": fault.fault_type,
            },
        }
        if self.socket_connected:
            try:
                await self.__websocket.send(json.dumps(self.generate_delta(path, value)))
            except Exception as e:
                logger.warning("Error sending fault on websocket: %s", e)
```

- [ ] **Step 4: Implement BLE fault handling + subscription**

Add to `EngineDataReceiver` Protocol in `config_decoder.py`:

```python
    async def accept_fault(self, fault) -> None:
        ...
```

In `ble_connection.py` add the import and handler, and subscribe to indicate-only chars:

```python
from .fault_decoder import parse_fault
```

```python
    def _handle_fault_notification(self, data: bytes):
        fault = parse_fault(data)
        if fault is None:
            return
        logger.info("Fault received: %s", fault)
        for receiver in self.__data_receivers:
            asyncio.get_event_loop().create_task(receiver.accept_fault(fault))
```

In `_setup_data_notifications`, subscribe to both notify and indicate characteristics:

```python
                props = characteristic.properties
                if "notify" in props or "indicate" in props:
                    try:
                        await client.start_notify(characteristic.uuid, self.notification_handler)
                        logger.debug("Subscribed to %s", characteristic.uuid)
                    except Exception as e:
                        logger.warning("Unable to subscribe to %s: %s", characteristic.uuid, e)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_signalk_publisher.py -v && pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: publish engine faults as SignalK notifications"
```

---

## Task 9: Engine-label configuration & docs

**Files:**
- Modify: `vvm_to_signalk/signalk_publisher.py` (`SignalKConfig.read`)
- Modify: `vvm_monitor.example.yaml`, `README.md`
- Test: `tests/test_signalk_publisher.py` (add)

**Interfaces:**
- Consumes: YAML `signalk.engine-labels` (mapping of engine number → label).
- Produces: `SignalKConfig.engine_labels: dict[int,str] | None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_signalk_publisher.py  (add)
from vvm_to_signalk.signalk_publisher import SignalKConfig

def test_engine_labels_parsed_from_config():
    cfg = SignalKConfig({"websocket-url": "ws://x",
                         "engine-labels": {1: "port", 2: "starboard"}})
    assert cfg.engine_labels == {1: "port", 2: "starboard"}

def test_engine_labels_default_none():
    assert SignalKConfig({"websocket-url": "ws://x"}).engine_labels is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_signalk_publisher.py::test_engine_labels_parsed_from_config -v`
Expected: FAIL

- [ ] **Step 3: Implement config parsing**

```python
# vvm_to_signalk/signalk_publisher.py  (in SignalKConfig.read)
        labels = data.get('engine-labels')
        if labels is not None:
            self.__engine_labels = {int(k): str(v) for k, v in labels.items()}
```

(with `self.__engine_labels = None` already in `__init__` from Task 6, and the property added.)

- [ ] **Step 4: Update example config and README**

Add to `vvm_monitor.example.yaml` under `signalk:`:

```yaml
  # Optional: map engine numbers (1-4) to SignalK propulsion instance labels.
  # Default: 1=starboard, 2=port, 3=3, 4=4
  engine-labels:
    1: starboard
    2: port
```

In `README.md`, replace the "Currently supported" parameter list with a pointer to
`docs/protocol-map.md` and note new capabilities: all SmartCraft channels (multi-engine),
engine faults via SignalK `notifications.*`, runtime channel discovery, and configurable
engine labels.

- [ ] **Step 5: Run tests**

Run: `pytest -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: configurable engine labels; document new capabilities"
```

---

## Task 10: End-to-end integration test & cleanup

**Files:**
- Test: `tests/test_vvm_monitor.py` (add an integration-style test)
- Modify: any remaining references to deleted symbols (`EngineParameter*`, `Conversion`).

**Interfaces:**
- Consumes: all prior tasks.

- [ ] **Step 1: Write an integration test (capture → deltas)**

```python
# tests/test_vvm_monitor.py  (add)
import asyncio
from vvm_to_signalk.ble_connection import BleDeviceConnection, BleConnectionConfig, UUIDs
from vvm_to_signalk.data_dictionary import DataDictionary

class RecordingReceiver:
    def __init__(self): self.values = {}; self.faults = []
    async def accept_engine_data(self, item, engine_id, value):
        self.values[(item.id, engine_id)] = value
    def update_active_items(self, ids): pass
    async def accept_fault(self, fault): self.faults.append(fault)

class FakeChar:
    def __init__(self, uuid): self.uuid = uuid

def test_capture_bytes_produce_expected_values():
    conn = BleDeviceConnection(BleConnectionConfig({"name": "x"}), {})
    rx = RecordingReceiver(); conn.accept_data_receiver(rx)
    conn._dictionary = DataDictionary.load(); conn._max_engines = 4
    conn._active_engine_ids = {1}
    # RPM 600, Voltage 14.523, Oil pressure 295.42 kPa
    conn.notification_handler(FakeChar("00000102-0000-1000-8000-ec55f9f5b963"),
                              bytearray.fromhex("01005802000000000000"))
    conn.notification_handler(FakeChar("00000104-0000-1000-8000-ec55f9f5b963"),
                              bytearray.fromhex("e800bb38000000000000"))
    # Fault on 0x201
    conn.notification_handler(FakeChar(UUIDs.DEVICE_201_UUID), bytearray.fromhex("12015704"))
    asyncio.get_event_loop().run_until_complete(asyncio.sleep(0))
    assert rx.values[(1, 1)] == 600.0
    assert round(rx.values[(232, 1)], 3) == 14.523
    assert rx.faults and rx.faults[0].fault_key == "1111-Legacy"
```

- [ ] **Step 2: Run the full suite**

Run: `pytest -q`
Expected: PASS. Fix any lingering imports of removed `EngineParameter`/`conversion` symbols
(search: `grep -rn "EngineParameter\|conversion import\|Conversion" vvm_to_signalk tests`).

- [ ] **Step 3: Run the linter**

Run: `pylint vvm_to_signalk` (match existing CI expectations; fix new warnings).
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "test: end-to-end decode + fault integration; remove dead code"
```

---

## Self-Review Notes (coverage map)

- **All data items decoded** → Tasks 1–2 (dictionary + multi-engine decode).
- **Correct SI mapping to SignalK namespaces** → Tasks 3–4.
- **Runtime channel map** → Task 5.
- **Multi-engine + active-engine gating** → Task 6.
- **Engine faults** → Tasks 7–8.
- **Configurable engine labels** → Task 9.
- **Backwards-compatible default labels** (engine 1 = starboard) → Task 4.
- **Unmapped-parameter passthrough** honored via existing `send-unknown-parameters` → Task 6.

**Open follow-ups (out of scope, note for later):** richer fault severity → SignalK state
mapping; offline fault-text table; publishing enum/bitfield items (gear, guardian flags) as
strings; tank instance numbering for multiple fuel tanks.
