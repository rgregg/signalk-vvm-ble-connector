"""Vessel View Mobile module"""
import argparse
import asyncio
import logging
import os
import signal
from datetime import datetime
from logging.handlers import RotatingFileHandler

import yaml

from .ble_connection import BleConnectionConfig, BleDeviceConnection
from .signalk_publisher import SignalKConfig, SignalKPublisher
from .config_decoder import EngineParameter
from .csv_writer import CsvWriter, CsvWriterConfig

logger = logging.getLogger(__name__)

class VesselViewMobileDataRecorder:
    """Captures and records data from Vessel View Mobile BLE device"""
    
    def __init__(self):
        self.__signalk_socket = None
        self.__ble_connection = None
        self.__csv_writer = None
        self.__health = {"signalk": False, "bluetooth": False}

    async def main(self):
        """Main function loop for the program"""

        loop = asyncio.get_event_loop()
        loop.add_signal_handler(signal.SIGINT, lambda : asyncio.create_task(self.signal_handler()))

        # read configuration data from various sources, in increasing priority
        config = VVMConfig()
        VesselViewMobileDataRecorder.load_config_file(config)
        VesselViewMobileDataRecorder.parse_arguments(config)
        VesselViewMobileDataRecorder.parse_env_variables(config)

        # enable logging
        self.setup_logging(config)

        logger.info("*** VVM_Monitor started ***")

        # start the main loops
        if config.bluetooth.valid:
            self.__ble_connection = BleDeviceConnection(config.bluetooth, self.publish_data_func, self.__health)
        else:
            logger.warning("Skipping bluetooth connection - configuration is invalid.")
            
        if config.signalk.valid:
            self.__signalk_socket = SignalKPublisher(config.signalk, self.__health)
        else:
            logger.warning("Skipping signalk connection - configuration is invalid.")

        if config.csv.valid:
            self.__csv_writer = CsvWriter(config.csv)
        else:
            logger.warning("Skipping csv output - configuration is invalid.")

        # configure csv output


        background_tasks = set()
        async with asyncio.TaskGroup() as tg:
            if self.__ble_connection is not None:
                task = tg.create_task(self.__ble_connection.run(tg))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            if self.__signalk_socket is not None:
                task = tg.create_task(self.__signalk_socket.run(tg))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
            if config.healthcheck_enable:
                logger.info("Starting healthcheck writer")
                task = tg.create_task(self.write_healthcheck())
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
        
        # won't return until all tasks in the TaskGroup are finished
        logger.info("*** VVM_Monitor finished ***")

    def setup_logging(self, config):
        """Configure the logging framework"""

        logging.basicConfig(
            level=config.logging_level,
            format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
        )

        if config.logging_file is not None:
            try:
                handler = RotatingFileHandler(config.logging_file, maxBytes=5*1024*1024, backupCount=config.logging_keep)
                handler.setLevel(config.logging_level)
                formatter = logging.Formatter("%(asctime)-15s %(name)-8s %(levelname)s: %(message)s")
                handler.setFormatter(formatter)
                logging.getLogger().addHandler(handler)
            except Exception as e:
                logger.error("Error setting up logging file handler: %s", e)

    def update_engine_parameters(self, parameters: list[EngineParameter]) -> None:
        """Update the known parameters for this engine"""
        if self.__csv_writer is not None:
            self.__csv_writer.update_parameters(parameters)
            self.__csv_writer.open_output_file()

    async def publish_data_func(self, param:EngineParameter, value):
        """Callback for publishing data to the websocket"""

        if self.__signalk_socket is not None:
            await self.__signalk_socket.accept_engine_data(param, value)

        if self.__csv_writer is not None:
            await self.__csv_writer.accept_engine_data(param, value)

    @staticmethod
    def parse_arguments(config: 'VVMConfig'):
        """Parse command line arguments"""

        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-a",
            "--device-address",
            metavar="<address>",
            help="the address of the bluetooth device to connect to",
        )

        parser.add_argument(
            "--device-name",
            metavar="<name>",
            help="the name of the bluetooth device to connect to"
        )

        parser.add_argument(
            "-ws",
            "--signalk-websocket-url",
            metavar="<websocket url>",
            help="The URL for the signalk websocket service.",
        )

        parser.add_argument(
            "--username",
            help="Username for SignalK authentication"
        )

        parser.add_argument(
            "--password",
            help="Password for SignalK authentication"

        )
        
        parser.add_argument(
            "-d",
            "--debug",
            action="store_true",
            help="sets the log level to debug",
        )

        args = parser.parse_args()
        if args.signalk_websocket_url is not None:
            config.signalk.websocket_url = args.signalk_websocket_url
        if args.device_address is not None:
            config.bluetooth.device_address = args.device_address
        if args.device_name is not None:
            config.bluetooth.device_name = args.device_name
        if args.debug:
            config.logging_level = logging.DEBUG
        if args.username is not None:
            config.signalk.username = args.username
        if args.password is not None:
            config.signalk.password = args.password

    async def signal_handler(self):
        """Handle the program receiving a signal to shutdown"""

        logger.info("Gracefully shutting down...")

        if self.__ble_connection is not None:
            await self.__ble_connection.close()
            self.__ble_connection = None
        if self.__signalk_socket is not None:
            await self.__signalk_socket.close()
            self.__signalk_socket = None

        logger.info("Exiting.")
        asyncio.get_event_loop().stop()

    @staticmethod
    def parse_env_variables(config : 'VVMConfig'):
        """Parse configuration from environment variables"""

        if (signalk_url := os.getenv('VVM_SIGNALK_URL')) is not None:
            config.signalk.websocket_url = signalk_url

        if (ble_device_address := os.getenv("VVM_DEVICE_ADDRESS")) is not None:
            config.bluetooth.device_address = ble_device_address

        if (ble_device_name := os.getenv('VVM_DEVICE_NAME')) is not None:
            config.bluetooth.device_name = ble_device_name

        if (debug_env := os.getenv("VVM_DEBUG")) is not None:
            if debug_env.lower() == "true" or debug_env == "1":
                config.logging_level = logging.DEBUG

        if (username := os.getenv("VVM_USERNAME")) is not None:
            config.signalk.username = username

        if (password := os.getenv("VVM_PASSWORD")) is not None:
            config.signalk.password = password

        if (healthcheck_env := os.getenv("APP_HEALTHCHECK_ENABLE")) is not None:
            if healthcheck_env.lower() == "true" or healthcheck_env == "1":
                config.healthcheck_enable = True
            else:
                config.healthcheck_enable = False

    @staticmethod
    def load_config_file(config: 'VVMConfig'):
        """Parse configuration from a config file"""

        # Read from the vvm_monitor.yaml file
        file_path = "config/vvm_monitor.yaml"
        if not os.path.exists(file_path):
            logger.debug("Skipping loading configuration from YAML - config file doesn't exist.")
            return
        
        try:
            with open(file_path, 'r', encoding="utf-8") as file:
                logger.info("Reading configuration from %s.", file_path)
                data = yaml.safe_load(file)
                config.read(data)
        except Exception as e:
            logger.warning("Error loading configuration file: %s", e)

    async def write_healthcheck(self):
        """Write the healthcheck status to a file"""
        while True:
            with open("/tmp/healthcheck", "w", encoding="utf-8") as f:
                if not self.__health["signalk"]:
                    f.write(f"BAD SignalK Disconnected {datetime.utcnow().isoformat()}\n")
                else:
                    f.write(f"OK {datetime.utcnow().isoformat()}\n")
            await asyncio.sleep(15)

class VVMConfig:
    """Program configuration"""

    def __init__(self, data: dict = None):
        self._ble_config = BleConnectionConfig()
        self._signalk_config = SignalKConfig()
        self._csv_config = CsvWriterConfig()

        self._logging_level = logging.INFO
        self._logging_file = "./logs/vvm_monitor.log"
        self._logging_keep = 5

        self.__healthcheck_enabled = False
        self.__healthcheck_port = "5000"
        self.__healthcheck_ip = "127.0.0.1"

        if data is not None:
            self.read(data)

    def read(self, data: dict):
        """Read data from a dictionary"""
        if data is None:
            return
        
        self.signalk.read(data.get('signalk'))
        self.bluetooth.read(data.get('ble-device'))
        self.csv.read(data.get('csv'))

        if (log_config := data.get('logging')) is not None:
            if (level := log_config.get('level', "INFO")) is not None:
                level = level.upper()
                match(level):
                    case "DEBUG":
                        self.__logging_level = logging.DEBUG
                    case "WARNING":
                        self.__logging_level = logging.WARNING
                    case "ERROR":
                        self.__logging_level = logging.ERROR
                    case "CRITICAL":
                        self.__logging_level = logging.CRITICAL
                    case _:
                        self.__logging_level = logging.INFO
            else:
                self.__logging_level = logging.INFO

            self._logging_file = log_config.get('file', self._logging_file)
            self._logging_keep = log_config.get('keep', self._logging_keep)
    
    @property
    def signalk(self):
        """Properties for SignalK websocket"""
        return self._signalk_config
    
    @signalk.setter
    def signalk(self, value):
        self._signalk_config = value
    
    @property
    def bluetooth(self):
        """Properties for BLE device"""

        return self._ble_config
    
    @bluetooth.setter
    def bluetooth(self, value):
        self._ble_config = value

    @property
    def csv(self):
        """Configuration properties for the CSV writer"""
        return self._csv_config
    
    @csv.setter
    def csv(self, value):
        self._csv_config = value

    @property
    def logging_level(self):
        """Logging output level"""
        return self._logging_level
    
    @logging_level.setter
    def logging_level(self, value):
        self._logging_level = value

    @property
    def logging_file(self):
        """Logging output file"""
        return self._logging_file
    
    @logging_file.setter
    def logging_file(self, value):
        self._logging_file = value

    @property
    def logging_keep(self):
        """Indicates the number of log files to keep"""
        return self._logging_keep
    
    @logging_keep.setter
    def logging_keep(self, value):
        self._logging_keep = value


    @property
    def healthcheck_enable(self):
        """Determines if health checks are enabled"""
        return self.__healthcheck_enabled
    
    @healthcheck_enable.setter
    def healthcheck_enable(self, value):
        self.__healthcheck_enabled = value

