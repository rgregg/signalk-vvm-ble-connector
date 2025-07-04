"""Static unit conversion methods"""

import logging
from .config_decoder import EngineParameterType

logger = logging.getLogger(__name__)

class Conversion:
    """Static conversion methods from hardware parameters to SI units"""
    @staticmethod
    def rpm_to_hertz(rpm):
        """Convert from RPM to Hertz (revolutions per second)"""
        # Conversion factor: 60 rpm = 1 Hz
        return rpm / 60.0
    
    @staticmethod
    def celsius_to_kelvin(celsius):
        """Convert from Celsius to Kelvin"""
        # Conversion factor = 0 celsius = 273.15 kelvin
        return celsius + 273.15
    
    @staticmethod
    def minutes_to_seconds(minutes):
        """Convert minutes to seconds"""
        return minutes * 60
   
    @staticmethod
    def cl_per_hour_to_m3_per_sec(cl_per_hour):
        """Convert centileters per hour to cubic meters per second (signal K expected format)"""
        # Conversion factor: 1 cL/h = 2.77778e-9 m³/s
        return cl_per_hour * 2.77778e-9
    
    @staticmethod
    def decapascals_to_pascals(value):
        """Convert decapascals to pascals"""
        # Conversion factor: 1 decapascal = 10 pascal
        return value * 10
    
    @staticmethod
    def convert_pressure_to_pascals(value):
        """Convert unit from mercury to pscals"""
        return value / 1.25
    
    @staticmethod
    def millivolts_to_volts(value):
        """Convert millivolts to volts"""
        # Conversionf actor: 1 millivolt = 0.0001 volts
        return value / 1000.0
    
    @staticmethod
    def identity_function(value):
        """No conversion, return the input"""
        return value
    
    @staticmethod
    def conversion_for_parameter_type(param: EngineParameterType):
        """Provide the conversion function based on parameter type"""
        match param:
            case EngineParameterType.BATTERY_VOLTAGE:
                return Conversion.millivolts_to_volts
            case EngineParameterType.COOLANT_TEMPERATURE:
                return Conversion.celsius_to_kelvin
            case EngineParameterType.CURRENT_FUEL_FLOW:
                return Conversion.cl_per_hour_to_m3_per_sec
            case EngineParameterType.ENGINE_RPM:
                return Conversion.rpm_to_hertz
            case EngineParameterType.ENGINE_RUNTIME:
                return Conversion.minutes_to_seconds
            case EngineParameterType.OIL_PRESSURE | EngineParameterType.WATER_PRESSURE:
                return Conversion.convert_pressure_to_pascals
            case _:            
                logger.debug("Unknown conversion for unknown datatype: %s", param)
                return Conversion.identity_function