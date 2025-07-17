"""MySensors constants for version 2.4 of MySensors."""

import voluptuous as vol

# pylint: disable=unused-import
from mysensors.const_22 import (  # noqa: F401
    MAX_NODE_ID,
    VALID_INTERNAL,
    VALID_PRESENTATION,
    VALID_SETREQ,
    VALID_STREAM,
    VALID_TYPES,
    BaseConst,
    MessageType,
    Presentation,
    Stream,
    Internal,
)

from .handler import HANDLERS_22 as HANDLERS_24


def get_handler_registry():
    """Return handler registry for this protocol version."""
    return HANDLERS_24


class SetReq(BaseConst):
    """MySensors set/req sub-types."""

    V_TEMP = 0  # S_TEMP, S_HEATER, S_HVAC. Temperature.
    V_HUM = 1  # S_HUM. Humidity.
    # S_LIGHT, S_DIMMER, S_SPRINKLER, S_HVAC, S_HEATER.
    # Binary status, 0=off, 1=on.
    V_STATUS = 2
    # Deprecated. Alias for V_STATUS. Light Status.0=off 1=on.
    V_LIGHT = 2
    V_PERCENTAGE = 3  # S_DIMMER. Percentage value 0-100 (%).
    # Deprecated. Alias for V_PERCENTAGE. Dimmer value. 0-100 (%).
    V_DIMMER = 3
    V_PRESSURE = 4  # S_BARO. Atmospheric Pressure.
    # S_BARO. Weather forecast. One of "stable", "sunny", "cloudy", "unstable",
    # "thunderstorm" or "unknown".
    V_FORECAST = 5
    V_RAIN = 6  # S_RAIN. Amount of rain.
    V_RAINRATE = 7  # S_RAIN. Rate of rain.
    V_WIND = 8  # S_WIND. Wind speed.
    V_GUST = 9  # S_WIND. Gust.
    V_DIRECTION = 10  # S_WIND. Wind direction 0-360 (degrees).
    V_UV = 11  # S_UV. UV light level.
    V_WEIGHT = 12  # S_WEIGHT. Weight(for scales etc).
    V_DISTANCE = 13  # S_DISTANCE. Distance.
    V_IMPEDANCE = 14  # S_MULTIMETER, S_WEIGHT. Impedance value.
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
    V_SCENE_ON = 19  # S_SCENE_CONTROLLER. Turn on a scene.
    V_SCENE_OFF = 20  # S_SCENE_CONTROLLER. Turn off a scene.
    # S_HEATER, S_HVAC.
    # Mode of heater. One of "Off", "HeatOn", "CoolOn", or "AutoChangeOver"
    V_HVAC_FLOW_STATE = 21
    # S_HEATER, S_HVAC. HVAC/Heater fan speed ("Min", "Normal", "Max", "Auto")
    V_HVAC_SPEED = 22
    # S_LIGHT_LEVEL.
    # Uncalibrated light level. 0-100%. Use V_LEVEL for light level in lux.
    V_LIGHT_LEVEL = 23
    V_VAR1 = 24  # Custom value
    V_VAR2 = 25  # Custom value
    V_VAR3 = 26  # Custom value
    V_VAR4 = 27  # Custom value
    V_VAR5 = 28  # Custom value
    V_UP = 29  # S_COVER. Window covering. Up.
    V_DOWN = 30  # S_COVER. Window covering. Down.
    V_STOP = 31  # S_COVER. Window covering. Stop.
    V_IR_SEND = 32  # S_IR. Send out an IR-command.
    # S_IR. This message contains a received IR-command.
    V_IR_RECEIVE = 33
    V_FLOW = 34  # S_WATER. Flow of water (in meter).
    V_VOLUME = 35  # S_WATER. Water volume.
    # S_LOCK. Set or get lock status. 1=Locked, 0=Unlocked.
    V_LOCK_STATUS = 36
    # S_DUST, S_AIR_QUALITY, S_SOUND (dB), S_VIBRATION (hz),
    # S_LIGHT_LEVEL (lux).
    V_LEVEL = 37
    V_DUST_LEVEL = 37  # Dust level
    V_VOLTAGE = 38  # S_MULTIMETER. Voltage level.
    V_CURRENT = 39  # S_MULTIMETER. Current level.
    # S_RGB_LIGHT, S_COLOR_SENSOR.
    # RGB value transmitted as ASCII hex string (I.e "ff0000" for red)
    V_RGB = 40
    # S_RGBW_LIGHT.
    # RGBW value transmitted as ASCII hex string (I.e "ff0000ff" for red +
    # full white)
    V_RGBW = 41
    # Optional unique sensor id (e.g. OneWire DS1820b ids)
    V_ID = 42  # S_TEMP.
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
    V_IR_RECORD = 50  # S_IR. Record IR codes for playback
    V_PH = 51  # S_WATER_QUALITY, water pH.
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
    # V_MULTI_MESSAGE = 57 Multi message is not supported
    V_TILT = 58  # S_COVER, Tilt position (Integer between 0-100)


VALID_SETREQ = dict(VALID_SETREQ)
VALID_SETREQ.update(
    {
        SetReq.V_TILT: vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100), vol.Coerce(str)
        ),
    }
)

VALID_TYPES = dict(VALID_TYPES)
VALID_TYPES.setdefault(Presentation.S_COVER, []).append(SetReq.V_TILT)

VALID_PAYLOADS = {
    MessageType.presentation: VALID_PRESENTATION,
    MessageType.set: VALID_SETREQ,
    MessageType.req: {member: "" for member in list(SetReq)},
    MessageType.internal: VALID_INTERNAL,
    MessageType.stream: VALID_STREAM,
}

VALID_MESSAGE_TYPES = {
    MessageType.presentation: list(Presentation),
    MessageType.set: list(SetReq),
    MessageType.req: list(SetReq),
    MessageType.internal: list(Internal),
    MessageType.stream: list(Stream),
}
