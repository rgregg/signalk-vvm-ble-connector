"""Static unit conversion methods"""

import logging
import re
from .config_decoder import EngineParameterType

logger = logging.getLogger(__name__)

class ConversionConfig:
    """Configuration for parameter conversions"""
    
    def __init__(self, data: dict = None):
        self.__conversions = {}
        if data is not None:
            self.read(data)
    
    def read(self, data: dict):
        """Read conversion configurations from dictionary"""
        if data is None:
            return
        
        # Parse conversions for each parameter type
        for param_name, formula in data.items():
            try:
                # Convert parameter name to EngineParameterType
                param_type = EngineParameterType[param_name.upper()]
                self.__conversions[param_type] = formula
                logger.debug("Loaded conversion for %s: %s", param_name, formula)
            except KeyError:
                logger.warning("Unknown parameter type in conversions config: %s", param_name)
    
    def get_conversion_formula(self, param_type: EngineParameterType) -> str:
        """Get the conversion formula for a parameter type"""
        return self.__conversions.get(param_type)
    
    def has_conversion(self, param_type: EngineParameterType) -> bool:
        """Check if a conversion is configured for this parameter type"""
        return param_type in self.__conversions


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
    def safe_eval_formula(formula: str, value: float) -> float:
        """Safely evaluate a conversion formula with the given value"""
        if formula is None:
            return value
        
        # Only allow safe mathematical operations
        allowed_names = {
            "value": value,
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
            "pow": pow,
            "__builtins__": {},
        }
        
        # Dynamically construct regex to allow safe characters and valid function names from allowed_names
        allowed_identifiers = '|'.join(re.escape(key) for key in allowed_names.keys() if key.isidentifier())
        safe_pattern = rf'^[0-9+\-*/.() \t\n]|({allowed_identifiers})+$'
        if not re.match(safe_pattern, formula):
            logger.warning("Formula contains unsafe characters: %s", formula)
            return value
        
        try:
            result = eval(formula, allowed_names)
            return float(result)
        except Exception as e:
            logger.warning("Error evaluating conversion formula '%s': %s", formula, e)
            return value
    
    @staticmethod
    def convert_with_config(param: EngineParameterType, value: float, config: ConversionConfig = None):
        """Convert value using configuration or default conversion"""
        if config and config.has_conversion(param):
            formula = config.get_conversion_formula(param)
            return Conversion.safe_eval_formula(formula, value)
        else:
            # Fall back to default conversion
            conversion_func = Conversion.conversion_for_parameter_type(param)
            return conversion_func(value)
    
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