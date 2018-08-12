"""MySensors constants for version 2.0 of MySensors."""
import voluptuous as vol

# pylint: disable=unused-import
from mysensors.const_15 import (
    VALID_INTERNAL, VALID_SETREQ, VALID_STREAM, VALID_TYPES, BaseConst,
    MessageType, Stream)
from mysensors.const_15 import MAX_NODE_ID  # noqa: F401
from mysensors.validation import is_version

from .handler import HANDLERS_20


def get_handler_registry():
    """Return handler registry for this version."""
    return HANDLERS_20


class Presentation(BaseConst):
    """MySensors presentation sub-types."""

    # pylint: disable=too-few-public-methods
    S_DOOR = 0                      # Door and window sensors
    S_MOTION = 1                    # Motion sensors
    S_SMOKE = 2                     # Smoke sensor
    S_BINARY = 3                    # Binary device (on/off), Alias for S_LIGHT
    S_LIGHT = 3                     # Light Actuator (on/off)
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
    S_ARDUINO_RELAY = 18            # Alias for compatability
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
    # LCD text device / Simple information device on controller, V_TEXT
    S_INFO = 36
    S_GAS = 37                      # Gas meter, V_FLOW, V_VOLUME
    S_GPS = 38                      # GPS Sensor, V_POSITION
    S_WATER_QUALITY = 39            # V_TEMP, V_PH, V_ORP, V_EC, V_STATUS


class SetReq(BaseConst):
    """MySensors set/req sub-types."""

    # pylint: disable=too-few-public-methods
    V_TEMP = 0              # S_TEMP, S_HEATER, S_HVAC. Temperature.
    V_HUM = 1               # S_HUM. Humidity.
    # S_LIGHT, S_DIMMER, S_SPRINKLER, S_HVAC, S_HEATER.
    # Binary status, 0=off, 1=on.
    V_STATUS = 2
    # Deprecated. Alias for V_STATUS. Light Status.0=off 1=on.
    V_LIGHT = 2
    V_PERCENTAGE = 3        # S_DIMMER. Percentage value 0-100 (%).
    # Deprecated. Alias for V_PERCENTAGE. Dimmer value. 0-100 (%).
    V_DIMMER = 3
    V_PRESSURE = 4          # S_BARO. Atmospheric Pressure.
    # S_BARO. Weather forecast. One of "stable", "sunny", "cloudy", "unstable",
    # "thunderstorm" or "unknown".
    V_FORECAST = 5
    V_RAIN = 6              # S_RAIN. Amount of rain.
    V_RAINRATE = 7          # S_RAIN. Rate of rain.
    V_WIND = 8              # S_WIND. Wind speed.
    V_GUST = 9              # S_WIND. Gust.
    V_DIRECTION = 10        # S_WIND. Wind direction 0-360 (degrees).
    V_UV = 11               # S_UV. UV light level.
    V_WEIGHT = 12           # S_WEIGHT. Weight(for scales etc).
    V_DISTANCE = 13         # S_DISTANCE. Distance.
    V_IMPEDANCE = 14        # S_MULTIMETER, S_WEIGHT. Impedance value.
    # S_DOOR, S_MOTION, S_SMOKE, S_SPRINKLER.
    # Armed status of a security sensor.  1=Armed, 0=Bypassed.
    V_ARMED = 15
    # S_DOOR, S_MOTION, S_SMOKE, S_SPRINKLER, S_WATER_LEAK, S_SOUND,
    # S_VIBRATION, S_MOISTURE.
    # Tripped status of a security sensor. 1=Tripped, 0=Untripped.
    V_TRIPPED = 16
    # S_POWER, S_LIGHT, S_DIMMER, S_RGB_LIGHT, S_RGBW_LIGHT.
    # Watt value for power meters.
    V_WATT = 17
    # S_POWER. Accumulated number of KWH for a power meter.
    V_KWH = 18
    V_SCENE_ON = 19         # S_SCENE_CONTROLLER. Turn on a scene.
    V_SCENE_OFF = 20        # S_SCENE_CONTROLLER. Turn off a scene.
    # S_HEATER, S_HVAC.
    # Mode of heater. One of "Off", "HeatOn", "CoolOn", or "AutoChangeOver"
    V_HVAC_FLOW_STATE = 21
    # S_HEATER, S_HVAC. HVAC/Heater fan speed ("Min", "Normal", "Max", "Auto")
    V_HVAC_SPEED = 22
    # S_LIGHT_LEVEL.
    # Uncalibrated light level. 0-100%. Use V_LEVEL for light level in lux.
    V_LIGHT_LEVEL = 23
    V_VAR1 = 24             # Custom value
    V_VAR2 = 25             # Custom value
    V_VAR3 = 26             # Custom value
    V_VAR4 = 27             # Custom value
    V_VAR5 = 28             # Custom value
    V_UP = 29               # S_COVER. Window covering. Up.
    V_DOWN = 30             # S_COVER. Window covering. Down.
    V_STOP = 31             # S_COVER. Window covering. Stop.
    V_IR_SEND = 32          # S_IR. Send out an IR-command.
    # S_IR. This message contains a received IR-command.
    V_IR_RECEIVE = 33
    V_FLOW = 34             # S_WATER. Flow of water (in meter).
    V_VOLUME = 35           # S_WATER. Water volume.
    # S_LOCK. Set or get lock status. 1=Locked, 0=Unlocked.
    V_LOCK_STATUS = 36
    # S_DUST, S_AIR_QUALITY, S_SOUND (dB), S_VIBRATION (hz),
    # S_LIGHT_LEVEL (lux).
    V_LEVEL = 37
    V_DUST_LEVEL = 37       # Dust level
    V_VOLTAGE = 38          # S_MULTIMETER. Voltage level.
    V_CURRENT = 39          # S_MULTIMETER. Current level.
    # S_RGB_LIGHT, S_COLOR_SENSOR.
    # RGB value transmitted as ASCII hex string (I.e "ff0000" for red)
    V_RGB = 40
    # S_RGBW_LIGHT.
    # RGBW value transmitted as ASCII hex string (I.e "ff0000ff" for red +
    # full white)
    V_RGBW = 41
    # Optional unique sensor id (e.g. OneWire DS1820b ids)
    V_ID = 42               # S_TEMP.
    # S_DUST, S_AIR_QUALITY, S_DISTANCE.
    # Allows sensors to send in a string representing the unit prefix to be
    # displayed in GUI.
    # This is not parsed by controller! E.g. cm, m, km, inch.
    V_UNIT_PREFIX = 43
    # S_HVAC. HVAC cool setpoint (Integer between 0-100).
    V_HVAC_SETPOINT_COOL = 44
    # S_HEATER, S_HVAC. HVAC/Heater setpoint (Integer between 0-100).
    V_HVAC_SETPOINT_HEAT = 45
    # S_HVAC. Flow mode for HVAC ("Auto", "ContinuousOn", "PeriodicOn").
    V_HVAC_FLOW_MODE = 46
    # S_INFO. Text message to display on LCD or controller device
    V_TEXT = 47
    # S_CUSTOM.
    # Custom messages used for controller/inter node specific commands,
    # preferably using S_CUSTOM device type.
    V_CUSTOM = 48
    # S_GPS.
    # GPS position and altitude. Payload: latitude;longitude;altitude(m).
    # E.g. "55.722526;13.017972;18"
    V_POSITION = 49
    V_IR_RECORD = 50            # S_IR. Record IR codes for playback
    V_PH = 51                   # S_WATER_QUALITY, water pH.
    # S_WATER_QUALITY, water ORP : redox potential in mV.
    V_ORP = 52
    # S_WATER_QUALITY, water electric conductivity μS/cm (microSiemens/cm).
    V_EC = 53
    V_VAR = 54  # S_POWER, Reactive power: volt-ampere reactive (var)
    V_VA = 55  # S_POWER, Apparent power: volt-ampere (VA)
    # S_POWER
    # Ratio of real power to apparent power.
    # Floating point value in the range [-1,..,1]
    V_POWER_FACTOR = 56


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
    # Provides signing related preferences (first byte is preference version).
    I_SIGNING_PRESENTATION = 15
    I_REQUEST_SIGNING = 15  # alias from version 1.5
    # Request for a nonce.
    I_NONCE_REQUEST = 16
    I_GET_NONCE = 16  # alias from version 1.5
    # Payload is nonce data.
    I_NONCE_RESPONSE = 17
    I_GET_NONCE_RESPONSE = 17  # alias from version 1.5
    I_HEARTBEAT = 18
    I_PRESENTATION = 19
    I_DISCOVER = 20
    I_DISCOVER_RESPONSE = 21
    I_HEARTBEAT_RESPONSE = 22
    # Node is locked (reason in string-payload).
    I_LOCKED = 23
    I_PING = 24  # Ping sent to node, payload incremental hop counter
    # In return to ping, sent back to sender, payload incremental hop counter
    I_PONG = 25
    I_REGISTRATION_REQUEST = 26  # Register request to GW
    I_REGISTRATION_RESPONSE = 27  # Register response from GW
    I_DEBUG = 28  # Debug message


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
    Presentation.S_ARDUINO_REPEATER_NODE: is_version,
    Presentation.S_ARDUINO_RELAY: is_version})

VALID_TYPES = dict(VALID_TYPES)
VALID_TYPES.update({
    Presentation.S_POWER: [
        SetReq.V_WATT, SetReq.V_KWH, SetReq.V_VAR, SetReq.V_VA,
        SetReq.V_POWER_FACTOR, SetReq.V_UNIT_PREFIX],
    Presentation.S_IR: [
        SetReq.V_IR_SEND, SetReq.V_IR_RECEIVE, SetReq.V_IR_RECORD],
    Presentation.S_CUSTOM: [
        SetReq.V_VAR1, SetReq.V_VAR2, SetReq.V_VAR3, SetReq.V_VAR4,
        SetReq.V_VAR5, SetReq.V_CUSTOM, SetReq.V_UNIT_PREFIX],
    Presentation.S_INFO: [SetReq.V_TEXT],
    Presentation.S_GAS: [SetReq.V_FLOW, SetReq.V_VOLUME, SetReq.V_UNIT_PREFIX],
    Presentation.S_GPS: [SetReq.V_POSITION],
    Presentation.S_WATER_QUALITY: [
        SetReq.V_TEMP, SetReq.V_PH, SetReq.V_ORP, SetReq.V_EC,
        SetReq.V_STATUS, SetReq.V_UNIT_PREFIX],
})


def validate_gps(value):
    """Validate GPS value."""
    try:
        latitude, longitude, altitude = value.split(',')
        vol.Coerce(float)(latitude)
        vol.Coerce(float)(longitude)
        vol.Coerce(float)(altitude)
    except (TypeError, ValueError, vol.Invalid):
        raise vol.Invalid(
            'GPS value should be of format "latitude,longitude,altitude"')
    return value


VALID_SETREQ = dict(VALID_SETREQ)
VALID_SETREQ.update({
    SetReq.V_TEXT: str,
    SetReq.V_CUSTOM: str,
    SetReq.V_POSITION: vol.All(str, validate_gps),
    SetReq.V_IR_RECORD: str,
    SetReq.V_PH: str,
    SetReq.V_ORP: str,
    SetReq.V_EC: str,
    SetReq.V_VAR: str,
    SetReq.V_VA: str,
    SetReq.V_POWER_FACTOR: vol.All(
        vol.Coerce(float), vol.Range(min=-1.0, max=1.0), vol.Coerce(str),
        msg='value should be between -1.0 and 1.0'),
})

VALID_INTERNAL = dict(VALID_INTERNAL)
VALID_INTERNAL.update({
    Internal.I_HEARTBEAT: '',
    Internal.I_PRESENTATION: '',
    Internal.I_DISCOVER: '',
    Internal.I_DISCOVER_RESPONSE: vol.All(
        vol.Coerce(int), vol.Range(min=0, max=MAX_NODE_ID), vol.Coerce(str)),
    Internal.I_HEARTBEAT_RESPONSE: vol.All(vol.Coerce(int), vol.Coerce(str)),
    Internal.I_LOCKED: str,
    Internal.I_PING: vol.All(vol.Coerce(int), vol.Coerce(str)),
    Internal.I_PONG: vol.All(vol.Coerce(int), vol.Coerce(str)),
    Internal.I_REGISTRATION_REQUEST: str,
    Internal.I_REGISTRATION_RESPONSE: str,
    Internal.I_DEBUG: str,
})

VALID_PAYLOADS = {
    MessageType.presentation: VALID_PRESENTATION,
    MessageType.set: VALID_SETREQ,
    MessageType.req: {member: '' for member in list(SetReq)},
    MessageType.internal: VALID_INTERNAL,
    MessageType.stream: VALID_STREAM,
}
