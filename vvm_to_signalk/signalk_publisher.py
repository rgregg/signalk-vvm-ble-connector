"""Module for SignalK data processing"""

from typing import Any
import json
import logging
import uuid
import asyncio
import websockets

from .futures_queue import FuturesQueue
from .config_decoder import EngineParameter, EngineParameterType
from .conversion import Conversion

logger = logging.getLogger(__name__)

class SignalKPublisher:
    """Class for publishing data to SignalK API"""

    def __init__(self, config: 'SignalKConfig', health_status):
        self.__config = config
        
        self.__websocket = None
        self.__socket_connected = False
        self.__abort = False
        self.__notifications = FuturesQueue()
        self.__health = health_status
        self.__should_log_connection_down = True

    @property
    def websocket_url(self):
        """URL for the SignalK websocket"""
        return self.__config.websocket_url
    
    @property
    def username(self):
        """Username for authenticating with SignalK"""
        return self.__config.username
    
    @property
    def password(self):
        """Password for authenticating with SignalK"""
        return self.__config.password
    
    @property
    def retry_interval_seconds(self):
        """Interval in seconds the system will return the connection
        if it fails"""
        return self.__config.retry_interval
    
    @property
    def socket_connected(self):
        """Indicates conncetion status to SignalK API"""
        return self.__socket_connected
    
    @socket_connected.setter
    def socket_connected(self, value):
        self.__socket_connected = value

    def set_health(self, value: bool, message: str = None):
        """Sets the health of the SignalK connection"""
        self.__health["signalk"] = value
        if message is None:
            self.__health.pop("signalk_error", None)
        else:
            self.__health["signalk_error"] = message
            logger.info(message)

    async def connect_websocket(self):
        """Connect to the Signal K server using a websocket."""
        logger.info("Connecting to SignalK: %s", self.websocket_url)
        user_agent_string = "vvmble_to_signalk/1.0"
        try:
            self.__websocket = await websockets.connect(self.websocket_url,
                                                      logger=logger,
                                                      user_agent_header=user_agent_string
                                                      )
            self.set_health(True)
            self.socket_connected = True
        except TimeoutError:
            self.set_health(False, "Websocket connection timed out.")
            self.socket_connected = False
        except OSError as e:  # TCP connection fails
            self.set_health(False, f"Connection failed to '{self.websocket_url}': {e}")
            self.socket_connected = False
        except websockets.exceptions.InvalidURI:
            self.set_health(False, f"Invalid URI: {self.websocket_url}")
            self.socket_connected = False
        except websockets.exceptions.InvalidHandshake:
            self.set_health(False, "Websocket service error. Check that the service is running and working properly.")        
            self.socket_connected = False
        return self.socket_connected
                
    async def close(self):
        """Closes the connection to SignalK API"""
        logger.info("Closing websocket...")
        if self.socket_connected:
            self.__abort = True
            await self.__websocket.close()
            self.set_health(False, "websocket closed")
            self.socket_connected = False
            
        logger.info("Websocket closed.")

    async def run(self, task_group):
        """Starts a run loop for the SignalK websocket"""
        self.__task_group = task_group
        while not self.__abort:
            await self.connect_websocket()
            while not self.socket_connected:
                logger.warning("Unable to connect to signalk websocket. Will retry...")
                await asyncio.sleep(self.retry_interval_seconds)
                await self.connect_websocket()
            
            logger.info("Connected to signalk websocket %s", self.websocket_url)
        
            # authenticate
            if self.username is not None:
                await self.authenticate(self.username, self.password)

            # receive messages
            while self.socket_connected:
                try:
                    if (msg := await self.__websocket.recv()) is not None:
                        self.process_websocket_message(msg)                    
                except (websockets.exceptions.ConnectionClosedOK, websockets.exceptions.ConnectionClosedError) as e:
                    self.set_health(False, f"websocket connection was closed: {e}")
                    self.socket_connected = False

    def process_websocket_message(self, msg):
        """Process a received message from the websocket"""

        logger.debug("Websocket message received: %s", msg)
        data = json.loads(msg)
        if "requestId" in data:
            request_id = data["requestId"]
            self.__notifications.trigger(request_id, data)
        else:
            logger.debug("No request ID was in received websocket message: %s", msg)

    async def authenticate(self, username, password):
        """Authenticate with the SignalK server via websocket"""
        logger.info("Authenticating with websocket...")

        login_request = self.generate_request_id()
        data = { 
            "requestId": login_request,
            "login": {
                "username": username,
                "password": password
            }
        }

        def process_login(future):
            response_json = future.result()
            logger.debug("response_json: %s", response_json)
            if response_json is not None:
                try:
                    # Check to see if the response was successful
                    if response_json.get("statusCode") == 200:
                        logger.info("authenticated with singalk successfully")
                        self.__auth_token = response_json.get("login", {}).get("token")
                    else:
                        logger.critical("Unable to authenticate with SignalK server. Username or password may be incorrect. Response: %s", response_json)
                except Exception as e:
                    logger.critical("Error processing authentication response: %s. Response: %s", e, response_json)

        self.__notifications.register_callback(login_request, process_login)
        await self.__websocket.send(json.dumps(data))
        

    def generate_request_id(self):
        """Generate a new require ID (UUID)"""
        return str(uuid.uuid4())

    def generate_delta(self, path, value):
        """Generates a delta message for SignalK based on a path and value"""
        delta = {
            "requestId": self.generate_request_id(),
            "context": "vessels.self",
            "updates": [
                {
                    "values": [
                        {
                            "path": path,
                            "value": value
                        }
                    ]
                }
            ]
        }
        return delta
    
    def convert_value(self, param: EngineParameter, value):
        """Converts the data from an engine parameter into the format for SignalK"""
        if (conversion_func := Conversion.conversion_for_parameter_type(param.parameter_type)) is None:
            logger.warning("No conversion function specified for %s", param.parameter_type.name)
            return value
        
        converted_value = conversion_func(value)
        return converted_value
    
    def path_for_parameter(self, param: EngineParameter):
        """Return the Signal K path for the parameter"""
        engine_name = "port"
        if (param.engine_id == 1):
            engine_name = "starboard"
        if (param.engine_id > 1):
            engine_name = str(param.engine_id)

        match param.parameter_type:
            case EngineParameterType.ENGINE_RPM:
                return f"propulsion.{engine_name}.revolutions"
            case EngineParameterType.COOLANT_TEMPERATURE:
                return f"propulsion.{engine_name}.temperature"
            case EngineParameterType.BATTERY_VOLTAGE:
                return f"propulsion.{engine_name}.alternatorVoltage"
            case EngineParameterType.ENGINE_RUNTIME:
                return f"propulsion.{engine_name}.runTime"
            case EngineParameterType.CURRENT_FUEL_FLOW:
                return f"propulsion.{engine_name}.fuel.rate"
            case EngineParameterType.OIL_PRESSURE:
                return f"propulsion.{engine_name}.oilPressure"
        
        logger.debug("Unable to map SignalK path for parameter type %s on engine %s.", param.parameter_type, param.engine_id)
        return f"propulsion.{engine_name}.{param.parameter_type.name}"

    async def accept_engine_data(self, param: EngineParameter, value: Any) -> None:
        """Publishes a delta to the SignalK API for the engine data"""

        if not self.__config.send_unknown_parameters and param.is_unknown():
            # skip unknown parameters
            logger.debug("Skipping unknown parameter due to configuration setting")
            return
        
        signalk_path = self.path_for_parameter(param)
        signalk_value = self.convert_value(param, value)
        logger.debug("Sending path %s with value %s.", signalk_path, signalk_value)
        
        if self.socket_connected:
            delta = self.generate_delta(signalk_path, signalk_value)
            try:
                await self.__websocket.send(json.dumps(delta))
                self.__should_log_connection_down = True    # Reset the flag to log connection down only once
            except websockets.exceptions.ConnectionClosed:
                logger.warning("Websocket connection closed. Data delta may not have been published.")
            except Exception as e:
                logger.warning("Error sending on websocket: %s", e)
        elif self.__should_log_connection_down:
                logger.debug("Websocket connection closed. No data was sent.")
                self.__should_log_connection_down = False

class SignalKConfig:
    """Defines the configuration for the SignalK server"""
    def __init__(self, data: dict = None):
        self.__websocket_url = None
        self.__username = None
        self.__password = None
        self.__retry_interval = 5
        self.__send_unknown_parameters = False
        if data is not None:
            self.read(data)
    
    def read(self, data: dict):
        """Reads configuration from a dictionary"""
        if data is None:
            return
        self.__websocket_url = data.get('websocket-url', self.__websocket_url)
        self.__username = data.get('username', self.__username)
        self.__password = data.get('password', self.__password)
        self.__retry_interval = data.get('retry-interval-seconds', self.__retry_interval)
        self.__send_unknown_parameters = data.get('send-unknown-parameters', self.__send_unknown_parameters)

    @property
    def websocket_url(self):
        """URL for the SignalK Websocket"""
        return self.__websocket_url
    
    @websocket_url.setter
    def websocket_url(self, value):
        self.__websocket_url = value

    @property
    def username(self):
        """Username for authenticating with SignalK"""
        return self.__username
    
    @username.setter
    def username(self, value):
        self.__username = value

    @property
    def password(self):
        """Password for authenticating with SignalK"""
        return self.__password
    
    @password.setter
    def password(self, value):
        self.__password = value

    @property
    def retry_interval(self):
        """Retry interval in seconds for connection to SignalK websocket"""
        return self.__retry_interval
    
    @retry_interval.setter
    def retry_interval(self, value):
        self.__retry_interval = value

    @property
    def valid(self):
        """Indicates if the configuration is valid with required parameters populated"""
        return self.__websocket_url is not None
    
    @property
    def send_unknown_parameters(self):
        """Option to skip exporting unknown values to signal k"""
        return self.__send_unknown_parameters
    
    @send_unknown_parameters.setter
    def send_unknown_parameters(self, value):
        self.__send_unknown_parameters = value
    


