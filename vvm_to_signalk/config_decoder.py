"""Configuration module"""

import logging
from enum import Enum
from collections.abc import Iterable
from typing import Protocol, Any

logger = logging.getLogger(__name__)

class ConfigDecoder:
    """Decodes saved configuration data into objects"""
    def __init__(self):
        self.__known_data = []  # array of byte arrays
        self.__has_all_data = None
        self.__parameters = []
    
    def add(self, item):
        """Adds a new data packet to the decoder"""
        if isinstance(item, Iterable) and not isinstance(item, (str, bytes)):
            self.__known_data.extend(item)
        else:
            self.__known_data.append(item)
        self.__has_all_data = None

    @property
    def has_all_data(self):
        """Indicates the configuration has all the data required"""
        if self.__has_all_data is None:
            try:
                self.combine_and_parse_data()
            except ValueError:
                pass

        return self.__has_all_data
    
    @has_all_data.setter
    def has_all_data(self, value):
        self.__has_all_data = value

    @property
    def engine_parameters(self):
        """List of engine parameters detected"""
        return self.__parameters
    
    @engine_parameters.setter
    def engine_parameters(self, value):
        self.__parameters = value

    def combine_and_parse_data(self) -> list['EngineParameter']:
        """Combine data received from the device into one package"""
        
        # sort known_data by the first byte
        data = self.__known_data
        logger.debug("Starting data: %s", data)

        sorted_data = sorted(data, key=lambda x: x[0])
        logger.debug("Sorted data: %s", sorted_data)

        # drop the first byte of each packet
        clean_data = [byte_array[1:] for byte_array in sorted_data]

        # combine the known data into a single byte stream
        combined = b''.join(clean_data)
        logger.debug("Combined data: %s", combined.hex())

        return self.parse_params(combined)

    def parse_params(self, combined_data) -> list['EngineParameter']:
        """Parse parameters to make sure they are valid"""

        # check to see if we have a valid header on the data
        if not combined_data:
            self.has_all_data = None
            raise ValueError("No data to parse.")

        if combined_data[0] != 0x28:
            logger.warning("Unexpected data format - value doesn't start with 0x28: %s", combined_data.hex())
            self.has_all_data = False
            raise ValueError("Value of first byte is not expected value.")

        # check to see if we have all the data we expect
        length_of_data = int.from_bytes(combined_data[1:2], byteorder='little')
        actual_length = len(combined_data[3:])
        logger.debug("Expected data length %s, actual %s", length_of_data, actual_length)
        if actual_length != length_of_data:
            self.has_all_data = False
            raise ValueError(f"Expected {length_of_data} bytes, but only have {actual_length}.")

        # parse the data into output
        magic_number, parsing_data = ConfigDecoder.pop_bytes(combined_data[3:], 2)
        logger.debug("Magic number was %s", magic_number.hex())
        found_params = []
        while len(parsing_data) != 0:
            next_param, parsing_data = ConfigDecoder.pop_bytes(parsing_data, 4)
            param_id = int.from_bytes(next_param[:2])
            header_id = int.from_bytes(next_param[2:])
            logger.debug("Parameter: %s with header: %s", param_id, header_id)
            found_params.append(EngineParameter(param_id, header_id))

            remaining_bytes = len(parsing_data)
            if 0 < remaining_bytes < 4:
                logger.debug("Remaining bytes (%s) indicate the data is incomplete.", remaining_bytes)
                self.has_all_data = False
                raise ValueError("Incorrect data length.")

        self.engine_parameters = found_params
        self.has_all_data = True
        
        return found_params
    
    @staticmethod
    def pop_bytes(byte_array, num_bytes):
        """Pops a count of bytes off the begining of an array"""
        # Extract the first num_bytes
        popped_bytes = byte_array[:num_bytes]
        # Update the original byte array by removing the popped bytes
        remaining_bytes = byte_array[num_bytes:]
        return popped_bytes, remaining_bytes

class EngineParameterType(Enum):
    """Known parameter types for Vessel View"""

    ENGINE_RPM = 0
    COOLANT_TEMPERATURE = 1
    BATTERY_VOLTAGE = 2
    UNKNOWN_3 = 3
    ENGINE_RUNTIME = 4
    CURRENT_FUEL_FLOW = 5
    UNKNOWN_6 = 6
    UNKNOWN_7 = 7
    OIL_PRESSURE = 8
    UNKNOWN_9 = 9
    UNKNOWN_A = 10
    UNKNOWN_B = 11
    UNKNOWN_C = 12
    UNKNOWN_D = 13
    UNKNOWN_E = 14
    UNKNOWN_F = 15

class EngineParameter:
    """Represents a single engine parameter and the decoded details"""

    def __init__(self, parameter: int, notification_header: int):
        self.__parameter_id = parameter
        self.__notification_header = notification_header
        self.__param_enabled = (notification_header != 0)
        self.__engine_id = parameter >> 8
        self.__parameter_type = EngineParameterType(parameter & 0xFF)

    def __str__(self):
        return f"EngineParameter(id={self.parameter_id}, header={self.notification_header}, type={self.parameter_type.name}, engine={self.engine_id})"

    @property
    def parameter_id(self):
        """Parameters unique ID"""
        return self.__parameter_id
    
    @property
    def notification_header(self):
        """The first two bytes of a notiifcation for this parameter"""
        return self.__notification_header

    @property
    def enabled(self):
        """Enable collecting data for this parameter"""
        return self.__param_enabled
    
    @property
    def engine_id(self):
        """Engine ID"""
        return self.__engine_id
    
    @property
    def parameter_type(self):
        """Returns the parameter type"""
        return self.__parameter_type
   
    def is_unknown(self):
        """Returns True if the parameter is a known parameter."""
        match self.parameter_type:
            case EngineParameterType.ENGINE_RPM | EngineParameterType.BATTERY_VOLTAGE | EngineParameterType.COOLANT_TEMPERATURE | EngineParameterType.COOLANT_TEMPERATURE | EngineParameterType.CURRENT_FUEL_FLOW | EngineParameterType.ENGINE_RUNTIME | EngineParameterType.OIL_PRESSURE:
                return False
            case _:
                return True

# pylint: disable=missing-function-docstring
class EngineDataReceiver(Protocol):
    """Protocol for classes that can receive engine data"""
    async def accept_engine_data(self, param: EngineParameter, value: Any) -> None:
        ...

    def update_engine_parameters(self, parameters: list[EngineParameter]) -> None:
        ...
