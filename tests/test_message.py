"""Test mysensors messages."""
from unittest import mock

import pytest
import voluptuous as vol

from mysensors import Gateway, Message, get_const, Sensor
from mysensors.const_14 import Internal, MessageType
from mysensors.task import SyncTasks

# pylint: disable=unnecessary-comprehension

PRES_FIXTURES_14 = {
    "S_DOOR": "Front Door",
    "S_ARDUINO_NODE": "1.4",
    "S_ARDUINO_RELAY": "1.4",
}

PRES_FIXTURES_15 = {
    "S_DOOR": "Front Door",
    "S_ARDUINO_NODE": "1.5",
    "S_ARDUINO_REPEATER_NODE": "1.5",
    "S_ARDUINO_RELAY": "1.5",
    "S_MOISTURE": "Moisture Sensor",
}

PRES_FIXTURES_20 = {
    "S_DOOR": "Front Door",
    "S_ARDUINO_NODE": "2.0",
    "S_ARDUINO_REPEATER_NODE": "2.0",
    "S_ARDUINO_RELAY": "2.0",
    "S_MOISTURE": "Moisture Sensor",
    "S_WATER_QUALITY": "Water Quality Sensor",
}

PRES_BAD_FIXTURES_14 = {
    "S_ARDUINO_NODE": "None",
    "S_ARDUINO_RELAY": "-1",
}

PRES_BAD_FIXTURES_15 = {
    "S_ARDUINO_NODE": "None",
    "S_ARDUINO_REPEATER_NODE": "1.3",
    "S_ARDUINO_RELAY": "-1",
}

PRES_BAD_FIXTURES_20 = {
    "S_ARDUINO_NODE": "None",
    "S_ARDUINO_REPEATER_NODE": "1.3",
    "S_ARDUINO_RELAY": "-1",
}

SET_FIXTURES_14 = {
    "V_TEMP": "20.0",
    "V_HUM": "30",
    "V_LIGHT": "1",
    "V_DIMMER": "99",
    "V_PRESSURE": "101325",
    "V_FORECAST": "stable",
    "V_RAIN": "30",
    "V_RAINRATE": "2",
    "V_WIND": "10",
    "V_GUST": "20",
    "V_DIRECTION": "270",
    "V_UV": "7",
    "V_WEIGHT": "10",
    "V_DISTANCE": "100",
    "V_IMPEDANCE": "10",
    "V_ARMED": "1",
    "V_TRIPPED": "1",
    "V_WATT": "1000",
    "V_KWH": "20",
    "V_SCENE_ON": "scene_3",
    "V_SCENE_OFF": "scene_4",
    "V_HEATER": "AutoChangeOver",
    "V_HEATER_SW": "1",
    "V_LIGHT_LEVEL": "99.0",
    "V_VAR1": "test1",
    "V_VAR2": "test2",
    "V_VAR3": "test3",
    "V_VAR4": "test4",
    "V_VAR5": "test5",
    "V_UP": "",
    "V_DOWN": "",
    "V_STOP": "",
    "V_IR_SEND": "code",
    "V_IR_RECEIVE": "code",
    "V_FLOW": "1.5",
    "V_VOLUME": "3.0",
    "V_LOCK_STATUS": "1",
    "V_DUST_LEVEL": "80",
    "V_VOLTAGE": "3.3",
    "V_CURRENT": "1.2",
}

SET_FIXTURES_15 = dict(SET_FIXTURES_14)
SET_FIXTURES_15.update(
    {
        "V_STATUS": "1",
        "V_PERCENTAGE": "99",
        "V_HVAC_FLOW_STATE": "AutoChangeOver",
        "V_HVAC_SPEED": "Auto",
        "V_LEVEL": "89",
        "V_RGB": "ffffff",
        "V_RGBW": "ffffffff",
        "V_ID": "1",
        "V_UNIT_PREFIX": "mV",
        "V_HVAC_SETPOINT_COOL": "24.0",
        "V_HVAC_SETPOINT_HEAT": "20.0",
        "V_HVAC_FLOW_MODE": "Auto",
    }
)
SET_FIXTURES_15.pop("V_HEATER")
SET_FIXTURES_15.pop("V_HEATER_SW")

SET_FIXTURES_20 = dict(SET_FIXTURES_15)
SET_FIXTURES_20.update(
    {
        "V_TEXT": "test text",
        "V_CUSTOM": "test custom",
        "V_POSITION": "10.0,10.0,10.0",
        "V_IR_RECORD": "code_id_to_store",
        "V_PH": "7.0",
        "V_ORP": "300",
        "V_EC": "5.5",
        "V_VAR": "100",
        "V_VA": "500",
        "V_POWER_FACTOR": "0.9",
    }
)

INTERNAL_FIXTURES_14 = {
    "I_BATTERY_LEVEL": "99",
    "I_TIME": {"payload": "1500000000", "return": True},
    "I_VERSION": "1.4.1",
    "I_ID_REQUEST": {"payload": "", "return": True},
    "I_ID_RESPONSE": "254",
    "I_INCLUSION_MODE": "1",
    "I_CONFIG": {"payload": "M", "return": True},
    "I_FIND_PARENT": "",
    "I_FIND_PARENT_RESPONSE": "254",
    "I_LOG_MESSAGE": "test log message",
    "I_CHILDREN": "C",  # clear routing data for the node
    "I_SKETCH_NAME": "test sketch name",
    "I_SKETCH_VERSION": "1.0.0",
    "I_REBOOT": "",
    "I_GATEWAY_READY": "Gateway startup complete.",
}

INTERNAL_FIXTURES_15 = dict(INTERNAL_FIXTURES_14)
INTERNAL_FIXTURES_15.update(
    {
        "I_REQUEST_SIGNING": "test signing request",
        "I_GET_NONCE": "test get nonce",
        "I_GET_NONCE_RESPONSE": "test get nonce response",
    }
)

INTERNAL_FIXTURES_20 = dict(INTERNAL_FIXTURES_15)
INTERNAL_FIXTURES_20.update(
    {
        "I_GATEWAY_READY": {"payload": "Gateway startup complete.", "return": True},
        "I_HEARTBEAT": "",
        "I_PRESENTATION": "",
        "I_DISCOVER": "",
        "I_DISCOVER_RESPONSE": "254",
        "I_HEARTBEAT_RESPONSE": "123465",
        "I_LOCKED": "TMFV",
        "I_PING": "123456",
        "I_PONG": "123456",
        "I_REGISTRATION_REQUEST": "2.0.0",
        "I_REGISTRATION_RESPONSE": "1",
        "I_DEBUG": "test debug",
    }
)


INTERNAL_FIXTURES_21 = dict(INTERNAL_FIXTURES_20)
INTERNAL_FIXTURES_21.update(
    {"I_FIND_PARENT_REQUEST": "", "I_HEARTBEAT_REQUEST": "", "I_DISCOVER_REQUEST": "",}
)


INTERNAL_FIXTURES_22 = dict(INTERNAL_FIXTURES_21)
INTERNAL_FIXTURES_22.update(
    {
        "I_SIGNAL_REPORT_REQUEST": "test",
        "I_SIGNAL_REPORT_REVERSE": "123",
        "I_SIGNAL_REPORT_RESPONSE": "123",
        "I_PRE_SLEEP_NOTIFICATION": "123",
        "I_POST_SLEEP_NOTIFICATION": "123",
    }
)


def get_gateway(**kwargs):
    """Return a gateway instance."""
    _gateway = Gateway(**kwargs)
    _gateway.tasks = SyncTasks(
        _gateway.const, False, None, _gateway.sensors, mock.MagicMock()
    )
    return _gateway


def get_message(message_data=None):
    """Return a message."""
    return Message(message_data)


def get_sensor(sensor_id, gateway):
    """Add sensor on gateway and return sensor instance."""
    gateway.sensors[sensor_id] = Sensor(sensor_id)
    return gateway.sensors[sensor_id]


def test_encode():
    """Test encode of message."""
    msg = get_message()
    cmd = msg.encode()
    assert cmd == "0;0;0;0;0;\n"

    msg.node_id = 1
    msg.child_id = 255
    msg.type = MessageType.internal
    msg.sub_type = Internal.I_BATTERY_LEVEL
    msg.ack = 0
    msg.payload = 57

    cmd = msg.encode()
    assert cmd == "1;255;3;0;0;57\n"


def test_encode_bad_message():
    """Test encode of bad message."""
    msg = get_message()
    msg.sub_type = "bad"
    cmd = msg.encode()
    assert cmd is None


def test_decode():
    """Test decode of message."""
    msg = get_message("1;255;3;0;0;57\n")
    assert msg.node_id == 1
    assert msg.child_id == 255
    assert msg.type == MessageType.internal
    assert msg.sub_type == Internal.I_BATTERY_LEVEL
    assert msg.ack == 0
    assert msg.payload == "57"


def test_decode_bad_message():
    """Test decode of bad message."""
    with pytest.raises(ValueError):
        get_message("bad;bad;bad;bad;bad;bad\n")


@pytest.mark.parametrize(
    "protocol_version, name, payload",
    [("1.4", name, payload) for name, payload in PRES_FIXTURES_14.items()]
    + [("1.5", name, payload) for name, payload in PRES_FIXTURES_15.items()]
    + [("2.0", name, payload) for name, payload in PRES_FIXTURES_20.items()]
    + [("2.1", name, payload) for name, payload in PRES_FIXTURES_20.items()]
    + [("2.2", name, payload) for name, payload in PRES_FIXTURES_20.items()],
)
def test_validate_pres(protocol_version, name, payload):
    """Test Presentation messages."""
    gateway = get_gateway(protocol_version=protocol_version)
    const = get_const(protocol_version)
    sub_type = const.Presentation[name]
    msg_string = "1;0;0;0;{};{}\n".format(sub_type, payload)
    msg = get_message(msg_string)
    valid = msg.validate(protocol_version)
    assert str(valid) == str(msg)
    ret = gateway.logic("1;0;0;0;{};{}\n".format(sub_type, payload))
    assert ret is None


@pytest.mark.parametrize(
    "protocol_version, name, payload",
    [("1.4", name, payload) for name, payload in PRES_BAD_FIXTURES_14.items()]
    + [("1.5", name, payload) for name, payload in PRES_BAD_FIXTURES_15.items()]
    + [("2.0", name, payload) for name, payload in PRES_BAD_FIXTURES_20.items()]
    + [("2.1", name, payload) for name, payload in PRES_BAD_FIXTURES_20.items()]
    + [("2.2", name, payload) for name, payload in PRES_BAD_FIXTURES_20.items()],
)
def test_validate_bad_pres(protocol_version, name, payload):
    """Test bad Presentation messages."""
    const = get_const(protocol_version)
    sub_type = const.Presentation[name]
    msg = get_message("1;0;0;0;{};{}\n".format(sub_type, payload))
    with pytest.raises(vol.Invalid):
        msg.validate(protocol_version)


@pytest.mark.parametrize(
    "protocol_version, name, payload",
    [("1.4", name, payload) for name, payload in SET_FIXTURES_14.items()]
    + [("1.5", name, payload) for name, payload in SET_FIXTURES_15.items()]
    + [("2.0", name, payload) for name, payload in SET_FIXTURES_20.items()]
    + [("2.1", name, payload) for name, payload in SET_FIXTURES_20.items()]
    + [("2.2", name, payload) for name, payload in SET_FIXTURES_20.items()],
)
def test_validate_set(protocol_version, name, payload):
    """Test Set messages."""
    gateway = get_gateway(protocol_version=protocol_version)
    const = get_const(protocol_version)
    sub_type = const.SetReq[name]
    msg_string = "1;0;1;0;{};{}\n".format(sub_type, payload)
    msg = get_message(msg_string)
    valid = msg.validate(protocol_version)
    assert str(valid) == str(msg)
    ret = gateway.logic(msg_string)
    assert ret is None


@pytest.mark.parametrize(
    "protocol_version, name, payload",
    [("1.4", name, payload) for name, payload in INTERNAL_FIXTURES_14.items()]
    + [("1.5", name, payload) for name, payload in INTERNAL_FIXTURES_15.items()]
    + [("2.0", name, payload) for name, payload in INTERNAL_FIXTURES_20.items()]
    + [("2.1", name, payload) for name, payload in INTERNAL_FIXTURES_21.items()]
    + [("2.2", name, payload) for name, payload in INTERNAL_FIXTURES_22.items()],
)
def test_validate_internal(protocol_version, name, payload):
    """Test Internal messages."""
    gateway = get_gateway(protocol_version=protocol_version)
    get_sensor(1, gateway)
    const = get_const(protocol_version)
    if isinstance(payload, dict):
        _payload = payload.get("payload")
        return_value = payload.get("return")
    else:
        _payload = payload
        return_value = None
    sub_type = const.Internal[name]
    msg_string = "1;255;3;0;{};{}\n".format(sub_type, _payload)
    msg = get_message(msg_string)
    valid = msg.validate(protocol_version)
    assert str(valid) == str(msg)
    ret = gateway.logic(msg_string)
    if return_value is None:
        assert ret is None, "Version: {} Message: {}".format(protocol_version, msg)
    else:
        assert ret, "Version: {} Message: {}".format(protocol_version, msg)
