"""MySensors constants for version 1.4 of MySensors."""
from enum import IntEnum

import voluptuous as vol

from mysensors.validation import is_version, percent_int
from .handler import HANDLERS


def get_handler_registry():
    """Return handler registry for this version."""
    return HANDLERS


class BaseConst(IntEnum):
    """MySensors message types."""

    def get_handler(self, handler_registry):
        """Return correct message handler."""
        return handler_registry.get(self.name)

    def set_handler(self, handler_registry, function):
        """Set message handler for name."""
        handler_registry[self.name] = function


class MessageType(BaseConst):
    """MySensors message types."""

    # pylint: disable=too-few-public-methods
    presentation = 0        # sent by a node when presenting attached sensors
    set = 1                 # sent from/to sensor when value should be updated
    req = 2                 # requests a variable value
    internal = 3            # internal message
    stream = 4              # OTA firmware updates


class Presentation(BaseConst):
    """MySensors presentation sub-types."""

    # pylint: disable=too-few-public-methods
    S_DOOR = 0                  # Door and window sensors
    S_MOTION = 1                # Motion sensors
    S_SMOKE = 2                 # Smoke sensor
    S_LIGHT = 3                 # Light Actuator (on/off)
    S_DIMMER = 4                # Dimmable device of some kind
    S_COVER = 5                 # Window covers or shades
    S_TEMP = 6                  # Temperature sensor
    S_HUM = 7                   # Humidity sensor
    S_BARO = 8                  # Barometer sensor (Pressure)
    S_WIND = 9                  # Wind sensor
    S_RAIN = 10                 # Rain sensor
    S_UV = 11                   # UV sensor
    S_WEIGHT = 12               # Weight sensor for scales etc.
    S_POWER = 13                # Power measuring device, like power meters
    S_HEATER = 14               # Heater device
    S_DISTANCE = 15             # Distance sensor
    S_LIGHT_LEVEL = 16          # Light sensor
    S_ARDUINO_NODE = 17         # Arduino node device
    S_ARDUINO_RELAY = 18        # Arduino repeating node device
    S_LOCK = 19                 # Lock device
    S_IR = 20                   # Ir sender/receiver device
    S_WATER = 21                # Water meter
    S_AIR_QUALITY = 22          # Air quality sensor e.g. MQ-2
    S_CUSTOM = 23               # Use this for custom sensors
    S_DUST = 24                 # Dust level sensor
    S_SCENE_CONTROLLER = 25     # Scene controller device


class SetReq(BaseConst):
    """MySensors set/req sub-types."""

    # pylint: disable=too-few-public-methods
    V_TEMP = 0              # Temperature
    V_HUM = 1               # Humidity
    V_LIGHT = 2             # Light status. 0=off 1=on
    V_DIMMER = 3            # Dimmer value. 0-100%
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
    V_WATT = 17             # Watt value for power meters
    V_KWH = 18              # Accumulated number of KWH for a power meter
    V_SCENE_ON = 19         # Turn on a scene
    V_SCENE_OFF = 20        # Turn off a scene
    # Mode of heater. One of "Off", "HeatOn", "CoolOn", or "AutoChangeOver"
    V_HEATER = 21
    V_HEATER_SW = 22        # Heater switch power. 1=On, 0=Off
    V_LIGHT_LEVEL = 23      # Light level. 0-100%
    V_VAR1 = 24             # Custom value
    V_VAR2 = 25             # Custom value
    V_VAR3 = 26             # Custom value
    V_VAR4 = 27             # Custom value
    V_VAR5 = 28             # Custom value
    V_UP = 29               # Window covering. Up.
    V_DOWN = 30             # Window covering. Down.
    V_STOP = 31             # Window covering. Stop.
    V_IR_SEND = 32          # Send out an IR-command
    V_IR_RECEIVE = 33       # This message contains a received IR-command
    V_FLOW = 34             # Flow of water (in meter)
    V_VOLUME = 35           # Water volume
    V_LOCK_STATUS = 36      # Set or get lock status. 1=Locked, 0=Unlocked
    V_DUST_LEVEL = 37       # Dust level
    V_VOLTAGE = 38          # Voltage level
    V_CURRENT = 39          # Current level


class Internal(BaseConst):
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


class Stream(BaseConst):
    """MySensors stream sub-types."""

    # Request new FW, payload contains current FW details
    ST_FIRMWARE_CONFIG_REQUEST = 0
    # New FW details to initiate OTA FW update
    ST_FIRMWARE_CONFIG_RESPONSE = 1
    ST_FIRMWARE_REQUEST = 2  # Request FW block
    ST_FIRMWARE_RESPONSE = 3  # Response FW block
    ST_SOUND = 4  # Sound
    ST_IMAGE = 5  # Image


VALID_MESSAGE_TYPES = {
    MessageType.presentation: list(Presentation),
    MessageType.set: list(SetReq),
    MessageType.req: list(SetReq),
    MessageType.internal: list(Internal),
    MessageType.stream: list(Stream),
}

VALID_PRESENTATION = {
    member: str for member in list(Presentation)
}
VALID_PRESENTATION.update({
    Presentation.S_ARDUINO_NODE: is_version,
    Presentation.S_ARDUINO_RELAY: is_version})

VALID_TYPES = {
    Presentation.S_DOOR: [SetReq.V_TRIPPED, SetReq.V_ARMED],
    Presentation.S_MOTION: [SetReq.V_TRIPPED, SetReq.V_ARMED],
    Presentation.S_SMOKE: [SetReq.V_TRIPPED, SetReq.V_ARMED],
    Presentation.S_LIGHT: [SetReq.V_LIGHT, SetReq.V_WATT],
    Presentation.S_DIMMER: [SetReq.V_LIGHT, SetReq.V_DIMMER, SetReq.V_WATT],
    Presentation.S_COVER: [
        SetReq.V_UP, SetReq.V_DOWN, SetReq.V_STOP, SetReq.V_DIMMER],
    Presentation.S_TEMP: [SetReq.V_TEMP],
    Presentation.S_HUM: [SetReq.V_HUM],
    Presentation.S_BARO: [
        SetReq.V_PRESSURE, SetReq.V_FORECAST],
    Presentation.S_WIND: [
        SetReq.V_WIND, SetReq.V_GUST, SetReq.V_DIRECTION],
    Presentation.S_RAIN: [
        SetReq.V_RAIN, SetReq.V_RAINRATE],
    Presentation.S_UV: [SetReq.V_UV],
    Presentation.S_WEIGHT: [
        SetReq.V_WEIGHT, SetReq.V_IMPEDANCE],
    Presentation.S_POWER: [SetReq.V_WATT, SetReq.V_KWH],
    Presentation.S_HEATER: [
        SetReq.V_HEATER, SetReq.V_HEATER_SW, SetReq.V_TEMP],
    Presentation.S_DISTANCE: [SetReq.V_DISTANCE],
    Presentation.S_LIGHT_LEVEL: [SetReq.V_LIGHT_LEVEL],
    Presentation.S_ARDUINO_NODE: [],
    Presentation.S_ARDUINO_RELAY: [],
    Presentation.S_LOCK: [SetReq.V_LOCK_STATUS],
    Presentation.S_IR: [SetReq.V_IR_SEND, SetReq.V_IR_RECEIVE],
    Presentation.S_WATER: [SetReq.V_FLOW, SetReq.V_VOLUME],
    Presentation.S_AIR_QUALITY: [SetReq.V_DUST_LEVEL],
    Presentation.S_CUSTOM: [
        SetReq.V_VAR1, SetReq.V_VAR2, SetReq.V_VAR3, SetReq.V_VAR4,
        SetReq.V_VAR5],
    Presentation.S_DUST: [SetReq.V_DUST_LEVEL],
    Presentation.S_SCENE_CONTROLLER: [SetReq.V_SCENE_ON, SetReq.V_SCENE_OFF],
}

LOGICAL_ZERO = '0'
LOGICAL_ONE = '1'
OFF = 'Off'
HEAT_ON = 'HeatOn'
COOL_ON = 'CoolOn'
AUTO_CHANGE_OVER = 'AutoChangeOver'
STABLE = 'stable'
SUNNY = 'sunny'
CLOUDY = 'cloudy'
UNSTABLE = 'unstable'
THUNDERSTORM = 'thunderstorm'
UNKNOWN = 'unknown'
FORECASTS = (STABLE, SUNNY, CLOUDY, UNSTABLE, THUNDERSTORM, UNKNOWN)

VALID_SETREQ = {
    SetReq.V_TEMP: str,
    SetReq.V_HUM: str,
    SetReq.V_LIGHT: vol.In(
        [LOGICAL_ZERO, LOGICAL_ONE],
        msg='value must be either {} or {}'.format(LOGICAL_ZERO, LOGICAL_ONE)),
    SetReq.V_DIMMER: vol.All(
        percent_int, vol.Coerce(str),
        msg='value must be integer between {} and {}'.format(0, 100)),
    SetReq.V_PRESSURE: str,
    SetReq.V_FORECAST: vol.Any(str, vol.In(
        FORECASTS,
        msg='forecast must be one of: {}, {}, {}, {}, {}, {}'.format(
            *FORECASTS))),
    SetReq.V_RAIN: str,
    SetReq.V_RAINRATE: str,
    SetReq.V_WIND: str,
    SetReq.V_GUST: str,
    SetReq.V_DIRECTION: str,
    SetReq.V_UV: str,
    SetReq.V_WEIGHT: str,
    SetReq.V_DISTANCE: str,
    SetReq.V_IMPEDANCE: str,
    SetReq.V_ARMED: vol.In(
        [LOGICAL_ZERO, LOGICAL_ONE],
        msg='value must be either {} or {}'.format(LOGICAL_ZERO, LOGICAL_ONE)),
    SetReq.V_TRIPPED: vol.In(
        [LOGICAL_ZERO, LOGICAL_ONE],
        msg='value must be either {} or {}'.format(LOGICAL_ZERO, LOGICAL_ONE)),
    SetReq.V_WATT: str,
    SetReq.V_KWH: str,
    SetReq.V_SCENE_ON: str,
    SetReq.V_SCENE_OFF: str,
    SetReq.V_HEATER: vol.In(
        [OFF, HEAT_ON, COOL_ON, AUTO_CHANGE_OVER],
        msg='value must be one of: {}, {}, {} or {}'.format(
            OFF, HEAT_ON, COOL_ON, AUTO_CHANGE_OVER)),
    SetReq.V_HEATER_SW: vol.In(
        [LOGICAL_ZERO, LOGICAL_ONE],
        msg='value must be either {} or {}'.format(LOGICAL_ZERO, LOGICAL_ONE)),
    SetReq.V_LIGHT_LEVEL: vol.All(
        vol.Coerce(float), vol.Range(min=0.0, max=100.0), vol.Coerce(str),
        msg='value must be float between {} and {}'.format(0.0, 100.0)),
    SetReq.V_VAR1: str,
    SetReq.V_VAR2: str,
    SetReq.V_VAR3: str,
    SetReq.V_VAR4: str,
    SetReq.V_VAR5: str,
    SetReq.V_UP: str,
    SetReq.V_DOWN: str,
    SetReq.V_STOP: str,
    SetReq.V_IR_SEND: str,
    SetReq.V_IR_RECEIVE: str,
    SetReq.V_FLOW: str,
    SetReq.V_VOLUME: str,
    SetReq.V_LOCK_STATUS: vol.In(
        [LOGICAL_ZERO, LOGICAL_ONE],
        msg='value must be either {} or {}'.format(LOGICAL_ZERO, LOGICAL_ONE)),
    SetReq.V_DUST_LEVEL: str,
    SetReq.V_VOLTAGE: str,
    SetReq.V_CURRENT: str,
}

CONF_METRIC = 'M'
CONF_IMPERIAL = 'I'
MAX_NODE_ID = 254

VALID_INTERNAL = {
    Internal.I_BATTERY_LEVEL: vol.All(
        percent_int, vol.Coerce(str),
        msg='value must be integer between {} and {}'.format(0, 100)),
    Internal.I_TIME: vol.Any('', vol.All(vol.Coerce(int), vol.Coerce(str))),
    Internal.I_VERSION: str,
    Internal.I_ID_REQUEST: '',
    Internal.I_ID_RESPONSE: vol.All(
        vol.Coerce(int), vol.Range(min=1, max=MAX_NODE_ID), vol.Coerce(str)),
    Internal.I_INCLUSION_MODE: vol.In([LOGICAL_ZERO, LOGICAL_ONE]),
    Internal.I_CONFIG: vol.Any(
        vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_NODE_ID)),
        CONF_METRIC, CONF_IMPERIAL),
    Internal.I_FIND_PARENT: '',
    Internal.I_FIND_PARENT_RESPONSE: vol.All(
        vol.Coerce(int), vol.Range(min=0, max=MAX_NODE_ID), vol.Coerce(str)),
    Internal.I_LOG_MESSAGE: str,
    Internal.I_CHILDREN: str,
    Internal.I_SKETCH_NAME: str,
    Internal.I_SKETCH_VERSION: str,
    Internal.I_REBOOT: '',
    Internal.I_GATEWAY_READY: str,
}

VALID_STREAM = {
    Stream.ST_FIRMWARE_CONFIG_REQUEST: str,
    Stream.ST_FIRMWARE_CONFIG_RESPONSE: str,
    Stream.ST_FIRMWARE_REQUEST: str,
    Stream.ST_FIRMWARE_RESPONSE: str,
    Stream.ST_SOUND: str,
    Stream.ST_IMAGE: str,
}

VALID_PAYLOADS = {
    MessageType.presentation: VALID_PRESENTATION,
    MessageType.set: VALID_SETREQ,
    MessageType.req: {member: '' for member in list(SetReq)},
    MessageType.internal: VALID_INTERNAL,
    MessageType.stream: VALID_STREAM,
}
