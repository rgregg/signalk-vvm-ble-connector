# VVM Offline Fault/Alarm Layer — Plan Addendum

> Addendum to `2026-06-19-vvm-full-data-signalk.md`. Implement human-readable engine
> fault/alarm information **fully offline** — no Mercury cloud, no external code tables.
> Uses only data the device streams plus the bundled data dictionary's enum/bitfield labels.

## Why this works without the cloud

The Fault Alert (`0x201`) Legacy/Universal codes can only be turned into prose by Mercury's
cloud API. **But the same alarm conditions are also exposed as ordinary SmartCraft data
items** whose human-readable meaning is baked into the data dictionary (`docs/protocol-map.md §7`):

| ID | Item | Form | Offline text source |
|----|------|------|---------------------|
| 87 | Guardian Cause | enum (uint1) | `{0:GC_NONE, 4:GC_LOW_OIL, 3:GC_TEMPERATURE_HIGH, …}` |
| 97 | Seven Function Gauge Data | bitfield (8bit) | `Oil Fault, Guardian/Check Engine, CAN Fault, Water in Fuel, Voltage Fault, Water Pressure Fault, Coolant Temperature Fault` |
| 106 | Malfunction Indicator Light | enum (uint1) | `{0:MIL Off, 1:MIL Constant On}` |
| 98–105 | individual fault flags | boolean | item name is the label |

These are `AccessType="Engines"`, `AccessPoint={Channel}` — i.e. they can be requested on a
data channel and stream as normal notifications, decoded entirely from the dictionary.

**Approach:** (A) teach the data dictionary to render enum/bitfield values to text;
(B) request the fault-condition items on spare channel slots; (C) publish them to SignalK
`notifications.*` (and as values). This composes with the main plan — do it **after** the
main plan's Task 8.

> **Validation caveat:** the default firmware streams 12 channels; this adds items on spare
> slots (`0x10e`/`0x10f`/`0x110`) by writing the channel-config the app uses. Confirm the
> module accepts the extra channels against a real device; if a write is rejected, skip that
> item and log it (don't fail the connection).

---

## Task A: Enum/bitfield rendering in the data dictionary

**Files:**
- Modify: `vvm_to_signalk/data_dictionary.py`
- Test: `tests/test_data_dictionary.py` (add)

**Interfaces:**
- Consumes: `DataItem` (main plan Task 2); the JSON `enum` (object) and `bits` (raw string
  like `"{0-1:Oil Fault,2-1:Guardian/Check Engine,...}"`) fields.
- Produces on `DataItem`:
  - `is_enum: bool`, `is_bitfield: bool`
  - `render_enum(raw: int) -> str | None`
  - `render_bits(raw: int) -> dict[str, int]` — `{flagName: value}`, skipping names
    containing "Reserved".

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_data_dictionary.py  (append)
from vvm_to_signalk.data_dictionary import DataDictionary

def test_render_enum_guardian_cause():
    item = DataDictionary.load().by_id(87)
    assert item.is_enum
    assert item.render_enum(4) == "GC_LOW_OIL"
    assert item.render_enum(0) == "GC_NONE"

def test_render_bits_seven_function_gauge():
    item = DataDictionary.load().by_id(97)
    assert item.is_bitfield
    # bit2 (Guardian/Check Engine) + bit4 (Water in Fuel) set => 0b10100 = 20
    flags = item.render_bits(0b10100)
    assert flags["Guardian/Check Engine"] == 1
    assert flags["Water in Fuel"] == 1
    assert flags["Oil Fault"] == 0
    assert "Reserved" not in flags  # reserved bits are dropped
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_dictionary.py -k "render" -v`
Expected: FAIL with `AttributeError: 'DataItem' object has no attribute 'is_enum'`

- [ ] **Step 3: Implement enum/bits parsing in `DataItem`**

In `DataItem.__init__`, after the existing assignments, parse the bits string into structured
form and expose helpers:

```python
        self._bit_specs = self._parse_bits(self.bits)  # list[(start, length, name)]

    @staticmethod
    def _parse_bits(bits):
        specs = []
        if not bits:
            return specs
        inner = bits.strip().strip("{}")
        for part in inner.split(","):
            if ":" not in part:
                continue
            rng, name = part.split(":", 1)
            if "-" not in rng:
                continue
            start_s, length_s = rng.split("-", 1)
            try:
                specs.append((int(start_s), int(length_s), name.strip()))
            except ValueError:
                continue
        return specs

    @property
    def is_enum(self) -> bool:
        return bool(self.enum)

    @property
    def is_bitfield(self) -> bool:
        return bool(self._bit_specs)

    def render_enum(self, raw: int):
        if not self.enum:
            return None
        return self.enum.get(str(int(raw)))

    def render_bits(self, raw: int) -> dict:
        raw = int(raw)
        out = {}
        for start, length, name in self._bit_specs:
            if "reserved" in name.lower():
                continue
            mask = (1 << length) - 1
            out[name] = (raw >> start) & mask
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_dictionary.py -k "render" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/data_dictionary.py tests/test_data_dictionary.py
git commit -m "feat: render enum/bitfield data items to human-readable labels"
```

---

## Task B: Build channel-config bytes & request fault-condition channels

**Files:**
- Modify: `vvm_to_signalk/data_dictionary.py` (add `build_channel_config`)
- Modify: `vvm_to_signalk/ble_connection.py`
- Test: `tests/test_data_dictionary.py` (add)

**Interfaces:**
- Produces: `build_channel_config(data_item_id: int, engines: int = 4, rate: int = 20,
  samples: int = 0, vmin: int = 0, vmax: int = 0) -> bytes` — the 6-byte channel config
  (see `docs/protocol-map.md §2.4`).
- BLE: after the runtime channel map is read, write configs for the offline fault items to
  spare channel characteristics and subscribe (covered by the existing notify subscription).

- [ ] **Step 1: Write the failing test (matches protocol-map §2.4)**

```python
# tests/test_data_dictionary.py  (append)
from vvm_to_signalk.data_dictionary import build_channel_config

def test_build_channel_config_rpm_like():
    # id=87 (0x57), 1 engine, rate=20 (0x14), samples=0
    cfg = build_channel_config(87, engines=1, rate=20)
    assert len(cfg) == 6
    assert cfg[0] == 0x57 and cfg[1] == 0x00        # id LE
    assert cfg[2] == (0b0001 | ((20 & 0xF) << 4))   # engine bit 1 + rate low nibble
    assert cfg[3] == ((20 & 0xFFF0) >> 4) | (0 << 6)
    assert cfg[4] == 0 and cfg[5] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_dictionary.py::test_build_channel_config_rpm_like -v`
Expected: FAIL with `ImportError: cannot import name 'build_channel_config'`

- [ ] **Step 3: Implement `build_channel_config`**

```python
# vvm_to_signalk/data_dictionary.py  (append, module level)
def build_channel_config(data_item_id: int, engines: int = 4, rate: int = 20,
                         samples: int = 0, vmin: int = 0, vmax: int = 0) -> bytes:
    """6-byte channel configuration write (see docs/protocol-map.md §2.4)."""
    cfg = bytearray(6)
    cfg[0] = data_item_id & 0xFF
    cfg[1] = (data_item_id >> 8) & 0xFF
    mask = 0
    for engine in range(1, min(engines, 4) + 1):
        mask |= 1 << (engine - 1)
    cfg[2] = (mask & 0x0F) | ((rate & 0x0F) << 4)
    cfg[3] = ((rate & 0xFFF0) >> 4) | ((samples & 0x03) << 6)
    cfg[4] = vmin & 0xFF
    cfg[5] = vmax & 0xFF
    return bytes(cfg)
```

- [ ] **Step 4: Add the channel request to the BLE layer**

In `ble_connection.py`, add the offline-fault item IDs and a method that writes their configs
to spare channel characteristics, then call it from `_device_init_and_loop` after
`_setup_data_notifications` and before enabling streaming. The spare slots are the channel
characteristics not used by the runtime map (the device exposes 15: `0x102`–`0x110`).

```python
# vvm_to_signalk/ble_connection.py
from .data_dictionary import build_channel_config

# offline alarm items to request if not already streamed
OFFLINE_FAULT_ITEM_IDS = [87, 97, 106]   # Guardian Cause, Seven Function Gauge, MIL

_CHANNEL_UUID_TEMPLATE = "000001{:02x}-0000-1000-8000-ec55f9f5b963"  # 0x02..0x10 -> chars
```

```python
    async def _request_offline_fault_channels(self, client, active_ids):
        """Configure spare channel slots to stream offline alarm items."""
        # Channel characteristics are 0x102..0x110 (slots 1..15).
        slot = len(active_ids)  # first unused slot index (0-based -> char 0x102+slot)
        for item_id in OFFLINE_FAULT_ITEM_IDS:
            if item_id in active_ids:
                continue
            if slot >= 15:
                logger.warning("No spare channel slots for offline fault item %s", item_id)
                break
            char_uuid = _CHANNEL_UUID_TEMPLATE.format(0x02 + slot)
            cfg = build_channel_config(item_id, engines=self._max_engines)
            try:
                await client.write_gatt_char(char_uuid, cfg, response=True)
                await client.start_notify(char_uuid, self.notification_handler)
                logger.info("Requested offline fault item %s on %s", item_id, char_uuid)
                slot += 1
            except Exception as e:
                logger.warning("Could not request fault item %s on %s: %s", item_id, char_uuid, e)
```

Call it in `_device_init_and_loop` after notifications are set up:

```python
                await self._setup_data_notifications(client)
                await self._request_offline_fault_channels(client, self._last_active_ids or [])
```

Store the active IDs when the runtime map is parsed: in `update_active_items`, add
`self._last_active_ids = item_ids`.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_data_dictionary.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add vvm_to_signalk/data_dictionary.py vvm_to_signalk/ble_connection.py tests/test_data_dictionary.py
git commit -m "feat: request offline fault-condition channels (guardian/seven-function/MIL)"
```

---

## Task C: Publish offline alarms as SignalK notifications

**Files:**
- Modify: `vvm_to_signalk/signalk_publisher.py`
- Test: `tests/test_signalk_publisher.py` (add)

**Interfaces:**
- Consumes: `DataItem.render_enum` / `render_bits` (Task A); `engine_label` (main plan Task 4).
- Produces: in `accept_engine_data`, items in the offline-fault set route to
  `notifications.propulsion.<label>.<flag>` instead of a data path. Guardian Cause and MIL
  emit one notification (alarm when non-`NONE`/On); Seven Function Gauge emits one per bit.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_signalk_publisher.py  (append)
import asyncio, json
from vvm_to_signalk.signalk_publisher import SignalKPublisher, SignalKConfig
from vvm_to_signalk.data_dictionary import DataDictionary

D = DataDictionary.load()

def _pub():
    p = SignalKPublisher(SignalKConfig({"websocket-url": "ws://x"}), {})
    class WS:
        def __init__(self): self.sent = []
        async def send(self, m): self.sent.append(json.loads(m))
    ws = WS(); p._SignalKPublisher__websocket = ws; p.socket_connected = True
    return p, ws

def test_guardian_cause_active_emits_alarm():
    p, ws = _pub()
    asyncio.get_event_loop().run_until_complete(p.accept_engine_data(D.by_id(87), 1, 4))  # GC_LOW_OIL
    v = ws.sent[0]["updates"][0]["values"][0]
    assert v["path"] == "notifications.propulsion.starboard.guardianCause"
    assert v["value"]["state"] == "alarm"
    assert v["value"]["message"].endswith("GC_LOW_OIL")

def test_guardian_cause_none_is_normal():
    p, ws = _pub()
    asyncio.get_event_loop().run_until_complete(p.accept_engine_data(D.by_id(87), 1, 0))  # GC_NONE
    assert ws.sent[0]["updates"][0]["values"][0]["value"]["state"] == "normal"

def test_seven_function_gauge_emits_per_flag():
    p, ws = _pub()
    asyncio.get_event_loop().run_until_complete(p.accept_engine_data(D.by_id(97), 1, 0b00100))
    paths = {u["updates"][0]["values"][0]["path"]: u["updates"][0]["values"][0]["value"]
             for u in ws.sent}
    assert "notifications.propulsion.starboard.guardianCheckEngine" in paths
    assert paths["notifications.propulsion.starboard.guardianCheckEngine"]["state"] == "alarm"
    assert paths["notifications.propulsion.starboard.oilFault"]["state"] == "normal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_signalk_publisher.py -k "guardian or seven" -v`
Expected: FAIL (no offline-fault routing yet)

- [ ] **Step 3: Implement offline-fault routing in the publisher**

Add a helper and branch at the top of `accept_engine_data` (before the normal path mapping):

```python
# vvm_to_signalk/signalk_publisher.py
import re
from .signalk_mapping import engine_label  # already imported in main plan Task 6

_OFFLINE_FAULT_IDS = {87, 106}     # enum-style single alarm
_BITFIELD_FAULT_IDS = {97}         # one notification per set bit

def _camel(name):
    parts = [p for p in re.split(r"[^0-9A-Za-z]+", name) if p]
    return parts[0].lower() + "".join(p.capitalize() for p in parts[1:]) if parts else "flag"
```

```python
    async def _send_notification(self, path, state, message, extra=None):
        value = {"state": state,
                 "method": ["visual", "sound"] if state == "alarm" else [],
                 "message": message}
        if extra:
            value["vvm"] = extra
        if self.socket_connected:
            try:
                await self.__websocket.send(json.dumps(self.generate_delta(path, value)))
            except Exception as e:
                logger.warning("Error sending notification: %s", e)

    async def accept_engine_data(self, item, engine_id, value):
        label = engine_label(engine_id, self.__config.engine_labels)
        if item.id in _OFFLINE_FAULT_IDS:
            text = item.render_enum(value) or str(int(value))
            inactive = int(value) == 0  # 0 == GC_NONE / MIL Off
            await self._send_notification(
                f"notifications.propulsion.{label}.{_camel(item.name)}",
                "normal" if inactive else "alarm",
                f"Engine {engine_id} {item.name}: {text}")
            return
        if item.id in _BITFIELD_FAULT_IDS:
            for flag_name, flag_val in item.render_bits(value).items():
                await self._send_notification(
                    f"notifications.propulsion.{label}.{_camel(flag_name)}",
                    "alarm" if flag_val else "normal",
                    f"Engine {engine_id} {flag_name}: {'active' if flag_val else 'clear'}")
            return
        # ... existing normal path/SI mapping from main plan Task 6 ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_signalk_publisher.py -k "guardian or seven" -v && pytest -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vvm_to_signalk/signalk_publisher.py tests/test_signalk_publisher.py
git commit -m "feat: publish offline guardian/seven-function alarms as SignalK notifications"
```

---

## Coverage & notes

- **Fully offline:** no network, no credentials, no external code tables — text comes from
  the bundled dictionary enums/bitfields.
- **What it provides:** guardian/alarm cause (overheat, low/critical oil, low battery, sensor
  fault, etc.), the seven-function-gauge flags (oil/CAN/water-in-fuel/voltage/water-pressure/
  coolant-temp faults, check-engine), and MIL state — per engine.
- **What it does NOT provide:** the specific Legacy/Universal fault *code descriptions* from
  `0x201` (those still require the cloud). Keep publishing those raw codes per the main plan
  Tasks 7–8; this addendum is the human-readable companion.
- **Follow-up:** make the requested offline-fault item list configurable; add the individual
  boolean flags (IDs 98–105) if the seven-function-gauge item is unavailable on a given
  firmware.
