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
