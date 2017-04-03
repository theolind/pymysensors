"""MySensors constants for version 1.5 of MySensors."""
from enum import IntEnum
# pylint: disable=unused-import
from mysensors.const_14 import HANDLE_INTERNAL  # noqa: F401


class MessageType(IntEnum):
    """MySensors message types."""

    # pylint: disable=too-few-public-methods
    presentation = 0        # sent by a node when presenting attached sensors
    set = 1                 # sent from/to sensor when value should be updated
    req = 2                 # requests a variable value
    internal = 3            # internal message
    stream = 4              # OTA firmware updates


class Presentation(IntEnum):
    """MySensors presentation sub-types."""

    # pylint: disable=too-few-public-methods
    S_DOOR = 0                      # Door and window sensors
    S_MOTION = 1                    # Motion sensors
    S_SMOKE = 2                     # Smoke sensor
    S_LIGHT = 3                     # Light Actuator (on/off)
    S_BINARY = 3                    # Binary device (on/off), Alias for S_LIGHT
    S_DIMMER = 4                    # Dimmable device of some kind
    S_COVER = 5                     # Window covers or shades
    S_TEMP = 6                      # Temperature sensor
    S_HUM = 7                       # Humidity sensor
    S_BARO = 8                      # Barometer sensor (Pressure)
    S_WIND = 9                      # Wind sensor
    S_RAIN = 10                     # Rain sensor
    S_UV = 11                       # UV sensor
    S_WEIGHT = 12                   # Weight sensor for scales etc.
    S_POWER = 13                    # Power measuring device, like power meters
    S_HEATER = 14                   # Heater device
    S_DISTANCE = 15                 # Distance sensor
    S_LIGHT_LEVEL = 16              # Light sensor
    S_ARDUINO_NODE = 17             # Arduino node device
    S_ARDUINO_REPEATER_NODE = 18    # Arduino repeating node device
    S_LOCK = 19                     # Lock device
    S_IR = 20                       # Ir sender/receiver device
    S_WATER = 21                    # Water meter
    S_AIR_QUALITY = 22              # Air quality sensor e.g. MQ-2
    S_CUSTOM = 23                   # Use this for custom sensors
    S_DUST = 24                     # Dust level sensor
    S_SCENE_CONTROLLER = 25         # Scene controller device
    S_RGB_LIGHT = 26                # RGB light
    # RGBW light (with separate white component)
    S_RGBW_LIGHT = 27
    S_COLOR_SENSOR = 28             # Color sensor
    S_HVAC = 29                     # Thermostat/HVAC device
    S_MULTIMETER = 30               # Multimeter device
    S_SPRINKLER = 31                # Sprinkler device
    S_WATER_LEAK = 32               # Water leak sensor
    S_SOUND = 33                    # Sound sensor
    S_VIBRATION = 34                # Vibration sensor
    S_MOISTURE = 35                 # Moisture sensor


class SetReq(IntEnum):
    """MySensors set/req sub-types."""

    # pylint: disable=too-few-public-methods
    V_TEMP = 0              # Temperature
    V_HUM = 1               # Humidity
    V_STATUS = 2            # Binary status, 0=off, 1=on
    # Deprecated. Alias for V_STATUS. Light Status.0=off 1=on
    V_LIGHT = 2
    V_PERCENTAGE = 3        # Percentage value. 0-100 (%)
    # Deprecated. Alias for V_PERCENTAGE. Dimmer value. 0-100 (%)
    V_DIMMER = 3
    V_PRESSURE = 4          # Atmospheric Pressure
    # Weather forecast. One of "stable", "sunny", "cloudy", "unstable",
    # "thunderstorm" or "unknown"
    V_FORECAST = 5
    V_RAIN = 6              # Amount of rain
    V_RAINRATE = 7          # Rate of rain
    V_WIND = 8              # Windspeed
    V_GUST = 9              # Gust
    V_DIRECTION = 10        # Wind direction
    V_UV = 11               # UV light level
    V_WEIGHT = 12           # Weight (for scales etc)
    V_DISTANCE = 13         # Distance
    V_IMPEDANCE = 14        # Impedance value
    # Armed status of a security sensor.  1=Armed, 0=Bypassed
    V_ARMED = 15
    # Tripped status of a security sensor. 1=Tripped, 0=Untripped
    V_TRIPPED = 16
    V_WATT = 17                 # Watt value for power meters
    V_KWH = 18                  # Accumulated number of KWH for a power meter
    V_SCENE_ON = 19             # Turn on a scene
    V_SCENE_OFF = 20            # Turn off a scene
    # Mode of heater. One of "Off", "HeatOn", "CoolOn", or "AutoChangeOver"
    V_HVAC_FLOW_STATE = 21
    # HVAC/Heater fan speed ("Min", "Normal", "Max", "Auto")
    V_HVAC_SPEED = 22
    # Uncalibrated light level. 0-100%. Use V_LEVEL for light level in lux.
    V_LIGHT_LEVEL = 23
    V_VAR1 = 24                 # Custom value
    V_VAR2 = 25                 # Custom value
    V_VAR3 = 26                 # Custom value
    V_VAR4 = 27                 # Custom value
    V_VAR5 = 28                 # Custom value
    V_UP = 29                   # Window covering. Up.
    V_DOWN = 30                 # Window covering. Down.
    V_STOP = 31                 # Window covering. Stop.
    V_IR_SEND = 32              # Send out an IR-command
    V_IR_RECEIVE = 33           # This message contains a received IR-command
    V_FLOW = 34                 # Flow of water (in meter)
    V_VOLUME = 35               # Water volume
    V_LOCK_STATUS = 36          # Set or get lock status. 1=Locked, 0=Unlocked
    V_LEVEL = 37                # Used for sending level-value
    V_VOLTAGE = 38              # Voltage level
    V_CURRENT = 39              # Current level
    # RGB value transmitted as ASCII hex string (I.e "ff0000" for red)
    V_RGB = 40
    # RGBW value transmitted as ASCII hex string (I.e "ff0000ff" for red +
    # full white)
    V_RGBW = 41
    # Optional unique sensor id (e.g. OneWire DS1820b ids)
    V_ID = 42
    # Allows sensors to send in a string representing the unit prefix to be
    # displayed in GUI.
    # This is not parsed by controller! E.g. cm, m, km, inch.
    V_UNIT_PREFIX = 43
    V_HVAC_SETPOINT_COOL = 44   # HVAC cold setpoint (Integer between 0-100)
    V_HVAC_SETPOINT_HEAT = 45   # HVAC/Heater setpoint (Integer between 0-100)
    # Flow mode for HVAC ("Auto", "ContinuousOn", "PeriodicOn")
    V_HVAC_FLOW_MODE = 45


class Internal(IntEnum):
    """MySensors internal sub-types."""

    # pylint: disable=too-few-public-methods
    # Use this to report the battery level (in percent 0-100).
    I_BATTERY_LEVEL = 0
    # Sensors can request the current time from the Controller using this
    # message. The time will be reported as the seconds since 1970
    I_TIME = 1
    # Sensors report their library version at startup using this message type
    I_VERSION = 2
    # Use this to request a unique node id from the controller.
    I_ID_REQUEST = 3
    # Id response back to sensor. Payload contains sensor id.
    I_ID_RESPONSE = 4
    # Start/stop inclusion mode of the Controller (1=start, 0=stop).
    I_INCLUSION_MODE = 5
    # Config request from node. Reply with (M)etric or (I)mperal back to sensor
    I_CONFIG = 6
    # When a sensor starts up, it broadcast a search request to all neighbor
    # nodes. They reply with a I_FIND_PARENT_RESPONSE.
    I_FIND_PARENT = 7
    # Reply message type to I_FIND_PARENT request.
    I_FIND_PARENT_RESPONSE = 8
    # Sent by the gateway to the Controller to trace-log a message
    I_LOG_MESSAGE = 9
    # A message that can be used to transfer child sensors
    # (from EEPROM routing table) of a repeating node.
    I_CHILDREN = 10
    # Optional sketch name that can be used to identify sensor in the
    # Controller GUI
    I_SKETCH_NAME = 11
    # Optional sketch version that can be reported to keep track of the version
    # of sensor in the Controller GUI.
    I_SKETCH_VERSION = 12
    # Used by OTA firmware updates. Request for node to reboot.
    I_REBOOT = 13
    # Send by gateway to controller when startup is complete
    I_GATEWAY_READY = 14
    # Used between sensors when initialting signing.
    I_REQUEST_SIGNING = 15
    # Used between sensors when requesting nonce.
    I_GET_NONCE = 16
    # Used between sensors for nonce response.
    I_GET_NONCE_RESPONSE = 17


class Stream(IntEnum):
    """MySensors stream sub-types."""

    # Request new FW, payload contains current FW details
    ST_FIRMWARE_CONFIG_REQUEST = 0
    # New FW details to initiate OTA FW update
    ST_FIRMWARE_CONFIG_RESPONSE = 1
    ST_FIRMWARE_REQUEST = 2  # Request FW block
    ST_FIRMWARE_RESPONSE = 3  # Response FW block
    ST_SOUND = 4  # Sound
    ST_IMAGE = 5  # Image
