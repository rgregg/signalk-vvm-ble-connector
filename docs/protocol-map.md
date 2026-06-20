# Vessel View Mobile — BLE Protocol Map

**Status:** Complete reference for the Vessel View Mobile BLE protocol, validated against
captured BLE traffic (`docs/bt-logs/btsnoop_hci.log`). Extends the earlier empirical notes
in [decoding.md](decoding.md).

The protocol is built around a **SmartCraft data dictionary**: every value is a numbered
*data item* with a defined type, gain (scale factor), and units. The full dictionary is
reproduced in §7. Items flagged below as *unconfirmed* are inferred and not yet observed in
a capture.

---

## 1. GATT services & characteristics

All custom UUIDs use the base `0000XXXX-0000-1000-8000-ec55f9f5b963`.

| Service | Service UUID | Characteristic | Char UUID |
|---|---|---|---|
| Module Service | `00000000-…` | Module Command | `00000001-…` |
| Engine Data Service | `00000100-…` | Protocol Version | `00000101-…` |
| | | **Channel 1 … 15** | `00000102-…` … `00000110-…` |
| | | **UserVar Command** | `00000111-…` |
| **Fault Service** | `00000200-…` | **Fault Alert** | `00000201-…` |
| Reflash Service | `00000300-…` | Reflash Command / Data | `00000301-…` / `00000302-…` |
| Security Service | `00000400-…` | Security Control | `00000401-…` |

The CCCD (notification/indication descriptor) is the standard `00002902-…`.

---

## 2. Engine-data channel decode

The 15 "Channel" characteristics (`0x102…0x110`) are **generic, runtime-configurable
slots**. Each is configured to carry one *SmartCraft data item*; the device then notifies
that channel with the item's value(s).

### 2.1 Notification payload layout

```
[ uint16 LE: SmartCraft data-item ID ][ value_engine1 ][ value_engine2 ][ value_engine3 ][ value_engine4 ]
```

- **Channel ID** = first 2 bytes, **little-endian uint16** = the `Id` from the data
  dictionary.
- **Values follow the ID, one per engine.** Items with `AccessType="Engines"` carry **4
  values** (engine 1–4); items with `AccessType="Vessel"` carry a **single** value.
- Each value width = the item's `Type` size (`uint1`=1B, `uint2`/`16bit`=2B, `uint3`=3B,
  `uint4`=4B, `sint*` signed, etc.).
- Values are **little-endian**, signed per `Type`.
- **Physical value = raw × `Gain`.** Resulting unit is the item's `Units` (kPa, °C,
  liters/hour, volts, revs/minute, minutes, percent, …). For SI/SignalK use the post-Gain
  value directly (then kPa→Pa, °C→K, etc. as needed at publish time).
- **Special case — ID 10000 "Active Engines"** is a 1-byte bitfield, not a per-engine array.

### 2.2 Worked example (RPM, from capture)

Handle `0x001d` (char `0x102`): `01 00 58 02 00 00 00 00 00 00`
- ID = `00 01` LE = **1** → "RPM" (Gain 1, uint2)
- engine1 = `58 02` LE = `0x0258` = **600 rpm**; engines 2–4 = `0000` = 0.

Other confirmed channels in the capture: Voltage `e800 bb38…` → 0x38bb×0.001 = **14.52 V**;
Engine Run Time `9600 ae16…` → 5806 min = **96.7 h** (matches the app's own readout).

### 2.3 This device's live channel map vs. the default template

There is a **default 12-channel template**, but the **actual map is negotiated at connect
time** and can differ per firmware. The capture from this boat differs from the default
(e.g. it streams *Fuel Flow Total* and *Active Engines* where the default lists *Fuel Flow
Average* and *Actual Gear*):

| Char | This device (capture) | ID | Default template | ID |
|---|---|---|---|---|
| 0x102 | RPM | 1 | RPM | 1 |
| 0x103 | Starboard Coolant Temp | 210 | Starboard Coolant Temp | 210 |
| 0x104 | Voltage | 232 | Voltage | 232 |
| 0x105 | Fuel Used (Fuel Burned Trip A) | 6000 | Fuel Used | 6000 |
| 0x106 | Engine Run Time | 150 | Engine Hours | 150 |
| 0x107 | **Fuel Flow Total** | **10** | Fuel Flow Average | 6004 |
| 0x108 | Fuel Remaining (Vessel, 1 value) | 8000 | Fuel Remaining | 8000 |
| 0x109 | **Active Engines** (bitfield) | **10000** | Actual Gear | 2 |
| 0x10a | Oil Pressure | 181 | Oil Pressure | 181 |
| 0x10b | **Block Pressure** | 212 | Block Pressure | 212 |
| 0x10c | Oil Temperature | 182 | Oil Temperature | 182 |
| 0x10d | Seawater Temperature | 251 | Seawater Temperature | 251 |

> **Implication:** a robust connector should **read the channel→ID map at runtime** rather
> than hard-coding it. The map is reported during the `Module Command` (`0x01`) config
> exchange (the `28 00 03 01` write and its multi-part indication on handle `0x0015`, which
> lists `slot→dataItemId` pairs, little-endian — see [decoding.md](decoding.md) §"Available
> Signal Information").

### 2.4 Channel configuration write format

Each channel is configured with a 6-byte write:

| Bytes | Meaning |
|---|---|
| 0–1 | `UniversalId` (uint16 LE) — which data item this channel streams |
| 2 | bits 0–3 = engine bitmask (1,2,4,8 for engines 1–4); bits 4–7 = `Rate` low nibble |
| 3 | `Rate` high bits; bits 6–7 = `Samples` |
| 4 | `Min` |
| 5 | `Max` |

Default `Rate` = 20 for all channels in the template.

---

## 3. Fault subsystem

This is the headline gap in the current connector. Faults are **not** in the engine-data
channels; they arrive on the dedicated **Fault Service**.

### 3.1 Transport

- **Characteristic:** Fault Alert `00000201-…`, delivered as **BLE indications**.
- Each indication is one fault event. Payload length selects the format:
  **4 bytes → LegacyFault**, **9 bytes → UniversalFault**.

### 3.2 Common header (both formats)

| Byte | Field | Meaning |
|---|---|---|
| 0, low nibble | `FaultType` | enum: 0=Unknown, 1=Universal, 2=Legacy |
| 0, high nibble | `Position` | engine position 1–4 |
| 1, bit 0 | `IsActive` | 1 = fault set, 0 = fault cleared |

### 3.3 LegacyFault (4 bytes)

- bytes 2–3: `FaultId` = uint16 LE.
- Fault key = `"{FaultId}-Legacy"`.

### 3.4 UniversalFault (9 bytes)

Bytes 2–8 (7 bytes) are zero-padded to 8 and read as a **uint64 LE**, then bit-unpacked:

| Field | Bits (mask) |
|---|---|
| `FaultSeverity` | 0–2 (`& 0x7`) |
| `ActionId` | 3–11 (`& 0xFF8 >> 3`) |
| `LongId` | 12–22 (`& 0x7FF000 >> 12`) |
| `ShortId` | 23–34 (`& 0x7FF800000 >> 23`) |
| `FailureTypeId` | 35–41 (`& 0x3F800000000 >> 35`) |
| `FaultId` | 42–55 (`& 0xFFFC0000000000 >> 42`) |

The **bit masks are authoritative** (they match the app's decode exactly); the bit-range
column is derived from them. `FaultId` is therefore 14 bits (max 16383).

Fault key = `"{FaultId}-{FailureTypeId}"`.

### 3.5 Human-readable fault text — cloud-dependent

The official app resolves the description / severity / recommended-action through a **cloud
API**, keyed by the fault code **and the engine's Software ID** (read via UserVar). There is
no local fault-code dictionary.

> **Implication:** an offline connector can fully decode the **fault code, engine position,
> active/cleared state, severity, and IDs**, but **not** the human-readable text without
> either that cloud API or an independently-sourced SmartCraft/J1939 fault table.

### 3.6 Offline fault *flags* available without the cloud

Several boolean/bitfield fault indicators exist as ordinary data items that can be streamed
on a channel (no cloud needed) — e.g. **Seven Function Gauge Data (ID 97)** packs:
`Oil Fault, Guardian/Check Engine, CAN Fault, Water in Fuel, Voltage Fault, Water Pressure
Fault, Coolant Temperature Fault`; **Guardian Cause (ID 87)** enumerates the active guardian
condition (low oil, overtemp, low battery, sensor fault, …); plus standalone flags IDs
98–106. See the dictionary below.

---

## 4. UserVar mechanism (engine metadata)

The **UserVar Command** characteristic `00000111-…` reads string/large data items via a
paged request/indication protocol: write the uint16 LE item ID; the device replies with
page 0 = `[00][id:2][msgType][len:2][data…]`, continued in subsequent pages (`++page`) until
`len` bytes are gathered, then formatted by type. Used for the string items **Software Id
(4000–4003), Calibration Id (4004–4007), Serial Number (4008–4011), ECU Serial
(4012–4015)** and the read/write **Tank Capacity / Fuel Onboard** items (4016–4040). The
**Software Id is required to decode faults** via the cloud (§3.5).

---

## 5. Connection / streaming sequence

Matches [decoding.md](decoding.md); summarized here with the new understanding:

1. Read Reflash Data `0x302` (security/version handshake).
2. Enable indications on Module Command `0x01`; write `0d 00` to **stop** streaming.
3. Write `28 00 03 01` to Module Command → device returns the **available-items / channel
   map** as a multi-part indication on handle `0x0015` (slot→dataItemId pairs, LE).
4. UserVar exchanges on `0x111` (e.g. `10 27 00` = item 10000) to read engine metadata.
5. Enable notifications on the active channel characteristics `0x102…`.
6. Enable indications on **Fault Alert `0x201`**.
7. Write `0d 01` to Module Command → **start** streaming. Channels then notify continuously;
   faults indicate as they occur/clear.

---

## 6. Implications for `vvm_to_signalk` (next cycle)

1. **Multi-engine:** each engine channel carries **up to 4 engine values** — the connector
   should decode all present engines, not just the first.
2. **Generic decoder:** replace per-characteristic hard-coding with a generic
   `[id LE][values × Gain]` decoder driven by the data dictionary (§7), and read the
   channel→ID map at runtime (§2.3).
3. **New parameters now identified** (previously "unknown"): Block Pressure (212),
   Oil Temperature (182), Seawater Temperature (251), Fuel Burned Trip A (6000),
   Fuel Remaining (8000), Active Engines (10000), Fuel Flow Total (10).
4. **Faults:** subscribe to indications on `0x201`, decode per §3, publish code/position/
   severity/active state to SignalK `notifications.*`. Decide separately how to source
   human-readable text (cloud vs. a J1939/SmartCraft table).

---

## 7. SmartCraft data dictionary

`Id` = the 2-byte channel ID (LE); physical value = raw × `Gain` in `Units`. `Type` gives
byte width / signedness.

| Id | Name | Type | Gain | Units | Enum / Bits | Access |
|---|---|---|---|---|---|---|
| 1 | RPM | uint2 | 1 | revs/minute |  | Channel/Engines |
| 2 | Actual Gear | uint1 | 1 | enumerated | {0:DIAG_SHORT,1:REVERSE,2:FORWARD,3:DIAG_OPEN,4:NEUTRAL,5:IN_GEAR} | Channel/Engines |
| 3 | Manifold Pressure | uint2 | 0.01 | kPa |  | Channel/Engines |
| 4 | City In Control Troll | uint1 | 1 |  |  | Channel/Engines |
| 5 | City Requesting Control Troll | uint1 | 1 |  |  | Channel/Engines |
| 10 | Fuel Flow Total | uint2 | 0.01 | liters/hour |  | Channel/Engines |
| 11 | Fuel Pressure | uint2 | 0.01 | kPa |  | Channel/Engines |
| 12 | Manifold Vacuum | sint2 | 0.01 | kPa |  | Channel/Engines |
| 20 | Pitot Boat Speed | uint2 | 0.01 | percent |  | Channel/Engines |
| 21 | Paddle Wheel Boat Speed | uint4 | 0.01 | Hz |  | Channel/Engines |
| 30 | Engine Trim Position | uint2 | 0.01 | percent |  | Channel/Engines |
| 35 | Trim Position Delta | uint2 | 1 | A/D Counts |  | Channel/Engines |
| 40 | Port Vessel Trim Tab Position | uint2 | 0.01 | percent |  | Channel/Engines |
| 41 | Starboard Vessel Trim Tab Position | uint2 | 0.01 | percent |  | Channel/Engines |
| 42 | Center Vessel Trim Tab Position | uint2 | 0.01 | percent |  | Channel/Engines |
| 50 | Steering Position | sint2 | 0.01 | percent |  | Channel/Engines |
| 51 | Throttle Position | uint1 | 0.4 | percent |  | Channel/Engines |
| 52 | Percent Load | uint1 | 1 | percent |  | Channel/Engines |
| 87 | Guardian Cause | uint1 | 1 | enumerated | {0 : GC_NONE,1 : GC_CHI,2 : GC_BLK_PRESS_LOW,3 : GC_TEMPERATURE_HIGH,4 : GC_LOW_OIL,5 : GC_CRITICAL_OIL,6 : GC_BATT_VOLT,7 : GC_BREAKIN,8 : GC_SENSOR_FAULT,9 : GC_FORCED_IDLE,10 : GC_OIL_PUMP_FAULT,11 : GC_OIL_PRESSURE,12 : GC_EMCT_TEMP,13 : GC_DISPLAY_OFS,14 : GC_OIL_TEMP,15 : GC_SC_TEMP,16 : GC_CHARGE_TEMP,17 : GC_TRAILER_LIMIT,18 : GC_AIRFLOW_GROUP} | Channel/Engines |
| 88 | Assert Functions | 8bit | 1 | Bitfield | {0-1:Remote Horn On,1-7:Reserved} | Channel/Engines |
| 97 | Seven Function Gauge Data | 8bit | 1 | Bitfield | {0-1:Oil Fault,1-1:Reserved,2-1:Guardian/Check Engine,3-1:CAN Fault,4-1:Water in Fuel,5-1:Voltage Fault,6-1:Water Pressure Fault,7-1:Coolant Temperature Fault | Channel/Engines |
| 98 | Oil Fault | boolean | 1 | Flag |  | Channel/Engines |
| 100 | Guardian/Check Engine | boolean | 1 | Flag |  | Channel/Engines |
| 101 | CAN Fault | boolean | 1 | Flag |  | Channel/Engines |
| 102 | Water in Fuel | boolean | 1 | Flag |  | Channel/Engines |
| 103 | Voltage Fault | boolean | 1 | Flag |  | Channel/Engines |
| 104 | Water Pressure Fault | boolean | 1 | Flag |  | Channel/Engines |
| 105 | Coolant Temperature Fault | boolean | 1 | Flag |  | Channel/Engines |
| 106 | Malfunction Indicator Light (MIL) Data | uint1 | 1 | enumerated | {0:MIL Off,1:MIL Constant On} | Channel/Engines |
| 110 | Diesel Flag | uint1 | 1 | enumerated | {0:Gasoline Engine,1:Diesel Engine} | Channel/Engines |
| 130 | Engine State | uint1 | 1 | enumerated | {0:DEAD,1:STALL,2:CRANK,3:RUN,4:POWEROFF} | Channel/Engines |
| 131 | Engine Operating Mode | uint1 | 1 | enumerated | {0:ENGOPERMODE_NONE,1:ENGOPERMODE_IDLE,2:ENGOPERMODE_OFF_IDLE} | Channel/Engines |
| 132 | RPM Control State | uint1 | 1 | enumerated | {0:RPM_CTRL_DISABLE_STATE,1:RPM_CTRL_ACTIVE_STATE} | Channel/Engines |
| 140 | Power Limit Setpoint Latched | uint1 | 0.78125 | percent |  | Channel/Engines |
| 141 | Gear Pressure | uint2 | 0.1 | kPa |  | Channel/Engines |
| 142 | Gear Temperature | sint2 | 1 | degrees C |  | Channel/Engines |
| 143 | Intake Manifold Temperature | sint1 | 1 | degrees C |  | Channel/Engines |
| 150 | Engine Run Time | uint4 | 1 | minutes |  | Channel/Engines |
| 160 | Break-in Time Required | uint2 | 1 | minutes |  | Channel/Engines |
| 161 | Accumulated Break-in Time | uint2 | 1 | minutes |  | Channel/Engines |
| 170 | Fuel Level 1 | uint2 | 0.01 | percent |  | Channel/Engines |
| 171 | Fuel Level 2 | uint2 | 0.01 | percent |  | Channel/Engines |
| 180 | Oil Level | uint2 | 0.01 | percent |  | Channel/Engines |
| 181 | Oil Pressure | uint2 | 0.01 | kPa |  | Channel/Engines |
| 182 | Oil Temperature | sint2 | 1 | degrees C |  | Channel/Engines |
| 190 | Oil Prime Remaining | uint2 | 0.01 | percent |  | Channel/Engines |
| 191 | Reserve Oil Remaining | uint2 | 0.1 | percent |  | Channel/Engines |
| 210 | Starboard Coolant Temp | sint2 | 1 | degrees C |  | Channel/Engines |
| 211 | Port Coolant Temp | sint2 | 1 | degrees C |  | Channel/Engines |
| 212 | Block Pressure | uint2 | 0.01 | kPa |  | Channel/Engines |
| 220 | Starboard EMCT | sint2 | 1 | degrees C |  | Channel/Engines |
| 221 | Port EMCT | sint2 | 1 | degrees C |  | Channel/Engines |
| 230 | Barometric Pressure | uint2 | 0.01 | kPa |  | Channel/Engines |
| 231 | Sea Water Temperature | sint1 | 1 | degrees C |  | Channel/Engines |
| 232 | Voltage | uint2 | 0.001 | volts |  | Channel/Engines |
| 240 | Troll RPM Max | uint1 | 10 | revs/minute |  | Channel/Engines |
| 241 | Troll RPM Min | uint1 | 10 | revs/minute |  | Channel/Engines |
| 242 | Fuel Flow Max | uint2 | 0.01 | liters/hour |  | Channel/Engines |
| 243 | RPM Rev. Limit (Redline) | uint2 | 1 | revs/minute |  | Channel/Engines |
| 244 | Engine Type | uint1 | 1 | enumerated | {00:UNDEFINED,01:2S_OUTBOARD,02:4S_OUTBOARD,03:STERN_NO_TROLL,04:INBRD_NO_TROLL,05:JET_DRIVE,06:STERNDRIVE,07:INBOARD,08:MAKO} | Channel/Engines |
| 250 | Depth | uint2 | 0.01 | meters |  | Channel/Engines |
| 251 | Seawater Temperature | sint2 | 0.1 | degrees C |  | Channel/Engines |
| 252 | Boat Speed | uint2 | 0.1 | km/hour |  | Channel/Engines |
| 270 | Optional Temperature | sint2 | 0.1 | degrees C |  | Channel/Engines |
| 272 | Optional Temperature Data Valid | boolean | 1 | Flag |  | Channel/Engines |
| 300 | Engine Run Time | uint4 | 1 | minutes |  | Channel/Engines |
| 310 | Band 1 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 311 | Band 1 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 312 | Band 1 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 320 | Band 2 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 321 | Band 2 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 322 | Band 2 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 330 | Band 3 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 331 | Band 3 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 332 | Band 3 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 340 | Band 4 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 341 | Band 4 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 342 | Band 4 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 350 | Band 5 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 351 | Band 5 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 352 | Band 5 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 360 | Band 6 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 361 | Band 6 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 362 | Band 6 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 370 | Band 7 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 371 | Band 7 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 372 | Band 7 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 380 | Band 8 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 381 | Band 8 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 382 | Band 8 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 390 | Band 9 Time | uint4 | 1 | minutes |  | Channel/Engines |
| 391 | Band 9 Low | uint1 | 50 | revs/minute |  | Channel/Engines |
| 392 | Band 9 High | uint1 | 50 | revs/minute |  | Channel/Engines |
| 900 | Project ID | uint1 | 1 | enumerated | {27:Mercury (outb.),41:merCruiser,43:Demo} | Channel/Engines |
| 901 | BootVerMaj | uint1 | 1 |  |  | Channel/Engines |
| 902 | BootVerMin | uint1 | 1 |  |  | Channel/Engines |
| 903 | EcuHwMaj | uint1 | 1 |  |  | Channel/Engines |
| 904 | EcuHwMin | uint1 | 1 |  |  | Channel/Engines |
| 4000 | Engine 1 Software Id | string | - |  |  | UserVar/- |
| 4001 | Engine 2 Software Id | string | - |  |  | UserVar/- |
| 4002 | Engine 3 Software Id | string | - |  |  | UserVar/- |
| 4003 | Engine 4 Software Id | string | - |  |  | UserVar/- |
| 4004 | Engine 1 Calibration Id | string | - |  |  | UserVar/- |
| 4005 | Engine 2 Calibration Id | string | - |  |  | UserVar/- |
| 4006 | Engine 3 Calibration Id | string | - |  |  | UserVar/- |
| 4007 | Engine 4 Calibration Id | string | - |  |  | UserVar/- |
| 4008 | Engine 1 Serial Number | string | - |  |  | UserVar/- |
| 4009 | Engine 2 Serial Number | string | - |  |  | UserVar/- |
| 4010 | Engine 3 Serial Number | string | - |  |  | UserVar/- |
| 4011 | Engine 4 Serial Number | string | - |  |  | UserVar/- |
| 4012 | ECU 1 Serial Number | string | - |  |  | UserVar/- |
| 4013 | ECU 2 Serial Number | string | - |  |  | UserVar/- |
| 4014 | ECU 3 Serial Number | string | - |  |  | UserVar/- |
| 4015 | ECU 4 Serial Number | string | - |  |  | UserVar/- |
| 4016 | Tank 1 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4017 | Tank 2 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4018 | Tank 3 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4019 | Tank 4 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4020 | Tank 5 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4021 | Tank 6 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4022 | Tank 7 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4023 | Tank 8 Capacity | uint4 | 0.01 | liters |  | UserVar/- |
| 4024 | Tank 1 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4025 | Tank 2 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4026 | Tank 3 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4027 | Tank 4 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4028 | Tank 5 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4029 | Tank 6 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4030 | Tank 7 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4031 | Tank 8 ADC Full | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4032 | Tank 1 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4033 | Tank 2 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4034 | Tank 3 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4035 | Tank 4 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4036 | Tank 5 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4037 | Tank 6 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4038 | Tank 7 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4039 | Tank 8 ADC Empty | uint2 | 1 | A/D Counts |  | UserVar/- |
| 4040 | Fuel Onboard | uint4 | 0.01 | liters |  | UserVar/- |
| 4041 | Max Engines Connected | uint1 | 1 | Engines |  | UserVar/- |
| 4042 | Software Calibration or Serial Changed | 8bit | 1 | Bitfield | {0-1:Engine 1,1-1:Engine 2,2-1:Engine 3,3-1:Engine 4} | UserVar/- |
| 6000 | Fuel Burned Trip A | uint4 | 0.01 | liters |  | Channel/Engines |
| 6001 | Fuel Burned Trip B | uint4 | 0.01 | liters |  | Channel/Engines |
| 6002 | Duration Trip A | uint4 | 1 | minutes |  | Channel/Engines |
| 6003 | Duration Trip B | uint4 | 1 | minutes |  | Channel/Engines |
| 6004 | Fuel Flow Average Trip A | uint2 | 0.01 | liters/hour |  | Channel/Engines |
| 6005 | Fuel Flow Average Trip B | uint2 | 0.01 | liters/hour |  | Channel/Engines |
| 6006 | Fuel Burned Current | uint4 | 0.01 | liters |  | Channel/Engines |
| 6007 | Duration Current | uint4 | 1 | minutes |  | Channel/Engines |
| 6008 | Fuel Flow Average Current | uint2 | 0.01 | liters/hour |  | Channel/Engines |
| 8000 | Fuel Remaining | uint4 | 0.01 | liters |  | Channel/Vessel |
| 10000 | Active Engines | 8bit | 1 | Bitfield | {0-1:Engine 1,1-1:Engine 2,2-1:Engine 3,3-1:Engine 4} | UserVar,Channel/Vessel |
| 10001 | Key Switch State | boolean | 1 | enumerated | {0:Off,1:On} | UserVar,Channel/Vessel |

_Total: 153 data items._
