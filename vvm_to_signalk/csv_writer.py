"""Outputs data in CSV format to storage"""
import asyncio
import csv
import logging
from typing import Any
from datetime import datetime
from .config_decoder import EngineParameter

logger = logging.getLogger(__name__)

class CsvWriter:
    """CSV writer class accepts data parameters and periodicly writes the current values out to CSV output"""

    def __init__(self, config: 'CsvWriterConfig'):
        self.__config = config
        # self.filename = filename
        # self.fieldnames = fieldnames
        #self.data = {field: None for field in fieldnames}
        self.__data = {}
        self.__timer = None
        self.__writer = None
        self.__flush_interval = config.flush_interval
        self.__fieldnames = None
        self.__wrote_fieldnames = False
        self.__output_stream = None
        self.__writer = None
        
        # Create the CSV file and write the header

    def update_engine_parameters(self, parameters: list[EngineParameter]):
        """Update the columns for the CSV output"""
        if parameters is None:
            return
        
        if self.__wrote_fieldnames:
            logging.warning("already wrote fieldnames - new fields won't be used")
            return
        
        self.__data.clear()
        fieldnames = ["timestamp"]
        for param in parameters:
            key = self.key_for_param(param)
            fieldnames.append(key)
            self.__data[key] = None
        self.__fieldnames = fieldnames

    # pylint: disable=consider-using-with
    def open_output_file(self) -> bool:
        """Open the output file and logger, closing any existing open file"""
        
        if self.__output_stream is not None:
            self.__writer = None
            self.__output_stream.close()
            self.__output_stream = None

        if self.__fieldnames is None:
            logger.warning("Fieldnames have not be set. CSV output is disabled.")
            self.__config.enabled = False
            return False

        if self.__config.enabled:
            try:
                self.__output_stream = open(self.__config.filename, 'a', newline='', encoding="utf-8")
                self.__writer = csv.DictWriter(self.__output_stream, fieldnames=self.__fieldnames)
                self.__writer.writeheader()
                self.__wrote_fieldnames = True
                return True
            except OSError as err:
                logger.warning("Unable to open CSV output file: %s", err)
                self.__config.enabled = False
                return False
        else:
            return False

    async def accept_engine_data(self, param: EngineParameter, value: Any) -> None:
        """Takes the latest data for an engine parameter and queues it for writing"""
        if not self.__config.enabled:
            return
        
        key = self.key_for_param(param)
        self.__data[key] = value
        self.__data["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.__timer is None:
            self.__timer = asyncio.create_task(self._flush_timer_task())

    def key_for_param(self, param: EngineParameter):
        """Generate the unique string for an engine parameter"""
        return f"{param.engine_id}_{param.parameter_type.name}"

    async def _flush_timer_task(self):
        """Flush a record to the CSV output file"""
        await asyncio.sleep(self.__flush_interval)
        await self.flush_queue_to_csv()
        self.__timer = None

    async def flush_queue_to_csv(self):
        """Flushes the queued data to the output file """
        self.__writer.writerow(self.__data)

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        self.flush_queue_to_csv()
        self.__output_stream.close()

class CsvWriterConfig:

    """Configuration settings for the CSV Writer"""
    def __init__(self, data = None):
        self.__enabled = False
        self.__filename = "./logs/data.csv"
        self.__flush_interval = 1.0
        if data is not None:
            self.read(data)

    def read(self, data: dict):
        """Loads settings from a dictionary"""
        self.__enabled = data.get("enabled", self.__enabled)
        self.__filename = data.get("filename", self.__filename)
        self.__flush_interval = data.get("interval", self.__flush_interval)


    @property
    def enabled(self):
        """Enable output of data logging to CSV"""
        return self.__enabled
    
    @enabled.setter
    def enabled(self, value):
        self.__enabled = value

    @property
    def filename(self):
        """CSV output file"""
        return self.__filename
    
    @filename.setter
    def filename(self, value):
        self.__filename = value

    @property
    def flush_interval(self):
        """Minimum amount of time in seconds between updates to the CSV file"""
        return self.__flush_interval
    
    @flush_interval.setter
    def flush_interval(self, value):
        self.__flush_interval = value

    @property
    def valid(self):
        """Validate the configuration"""
        return (not self.__enabled or self.__filename is not None) and self.__flush_interval > 0

    
