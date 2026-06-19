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
