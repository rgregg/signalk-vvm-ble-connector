"""Map SmartCraft data items to SignalK paths and SI units."""
import logging
import re

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
