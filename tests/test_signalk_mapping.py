import math
from vvm_to_signalk.signalk_mapping import to_si
from vvm_to_signalk.data_dictionary import DataDictionary
from vvm_to_signalk.signalk_mapping import engine_label, signalk_path

D = DataDictionary.load()

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

def test_path_starboard_coolant_temp():
    assert signalk_path(D.by_id(210), 1) == "propulsion.starboard.coolantTemperature"

def test_path_port_coolant_temp_distinct():
    assert signalk_path(D.by_id(211), 1) == "propulsion.starboard.vvm.portCoolantTemperature"
