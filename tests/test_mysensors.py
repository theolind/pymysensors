"""Test mysensors with unittest."""
import logging
import time
from unittest import mock

import pytest
import voluptuous as vol

from mysensors import Gateway
from mysensors.sensor import Sensor
from mysensors.task import SyncTasks

# pylint: disable=redefined-outer-name


@pytest.fixture(params=["1.4", "1.5", "2.0", "2.1", "2.2"])
def gateway(request):
    """Return gateway instance."""
    _gateway = Gateway(protocol_version=request.param)
    _gateway.tasks = SyncTasks(_gateway.const, False, None, _gateway.sensors, None)
    return _gateway


def get_gateway(**kwargs):
    """Return a gateway instance."""
    _gateway = Gateway(**kwargs)
    _gateway.tasks = SyncTasks(_gateway.const, False, None, _gateway.sensors, None)
    return _gateway


@pytest.fixture
def add_sensor(gateway):
    """Return function for adding node."""

    def _add_sensor(sensor_id):
        """Add sensor node. Return sensor node instance."""
        gateway.sensors[sensor_id] = Sensor(sensor_id)
        return gateway.sensors[sensor_id]

    return _add_sensor


def get_sensor(sensor_id, gateway):
    """Add sensor on gateway and return sensor instance."""
    gateway.sensors[sensor_id] = Sensor(sensor_id)
    return gateway.sensors[sensor_id]


def test_logic_bad_message(gateway):
    """Test decode of bad message in logic method."""
    assert gateway.logic("bad;bad;bad;bad;bad;bad\n") is None


def test_per_instance_handler():
    """Test that gateway can add own handlers."""
    gateway_1 = get_gateway()
    gateway_2 = get_gateway()
    gateway_1_actions = []
    gateway_2_actions = []

    def gateway_1_handler(_):  # pylint: disable=useless-return
        """Handle message for gateway_1."""
        gateway_1_actions.append(1)
        return None

    def gateway_2_handler(_):  # pylint: disable=useless-return
        """Handle message for gateway_2."""
        gateway_2_actions.append(2)
        return None

    gateway_1.const.Internal.I_VERSION.set_handler(
        gateway_1.handlers, gateway_1_handler
    )
    gateway_2.const.Internal.I_VERSION.set_handler(
        gateway_2.handlers, gateway_2_handler
    )

    gateway_2.logic("0;255;3;0;2;\n")
    assert gateway_2_actions[-1] == 2
    gateway_1.logic("0;255;3;0;2;\n")
    assert gateway_1_actions[-1] == 1


@pytest.mark.parametrize(
    "protocol_version, return_value",
    [
        ("1.4", None),
        ("1.5", None),
        ("2.0", "1;255;3;0;19;\n"),
        ("2.1", "1;255;3;0;19;\n"),
        ("2.2", "1;255;3;0;19;\n"),
    ],
)
def test_non_presented_sensor(protocol_version, return_value):
    """Test non presented sensor node."""
    gateway = get_gateway(protocol_version=protocol_version)

    gateway.logic("1;0;1;0;23;43\n")
    ret = gateway.tasks.run_job()
    assert 1 not in gateway.sensors
    assert ret == return_value

    gateway.logic("1;1;1;0;1;75\n")
    ret = gateway.tasks.run_job()
    assert 1 not in gateway.sensors
    assert ret == return_value

    gateway.logic("1;255;3;0;0;79\n")
    ret = gateway.tasks.run_job()
    assert 1 not in gateway.sensors
    assert ret == return_value


@pytest.mark.parametrize(
    "protocol_version, return_value",
    [
        ("1.4", None),
        ("1.5", None),
        ("2.0", "1;255;3;0;19;\n"),
        ("2.1", "1;255;3;0;19;\n"),
        ("2.2", "1;255;3;0;19;\n"),
    ],
)
def test_present_to_non_sensor(protocol_version, return_value):
    """Test presenting a child to a non presented sensor node."""
    gateway = get_gateway(protocol_version=protocol_version)
    ret = gateway.logic("1;1;0;0;0;\n")
    assert 1 not in gateway.sensors
    ret = gateway.tasks.run_job()
    assert ret == return_value


def test_internal_id_request(gateway, add_sensor):
    """Test internal node id request."""
    ret = gateway.logic("255;255;3;0;3;\n")
    assert ret == "255;255;3;0;4;1\n"
    assert 1 in gateway.sensors
    ret = gateway.logic("255;255;3;0;3;\n")
    assert ret == "255;255;3;0;4;2\n"
    assert 2 in gateway.sensors
    add_sensor(254)
    assert 254 in gateway.sensors
    ret = gateway.logic("255;255;3;0;3;\n")
    assert ret is None
    assert 255 not in gateway.sensors


def test_id_request_with_node_zero(gateway, add_sensor):
    """Test internal node id request with node 0 already assigned."""
    add_sensor(0)
    ret = gateway.logic("255;255;3;0;3;\n")
    assert ret == "255;255;3;0;4;1\n"
    assert 1 in gateway.sensors


def test_presentation_arduino_node(gateway):
    """Test presentation of sensor node."""
    gateway.logic("1;255;0;0;17;1.4.1\n")
    assert gateway.sensors[1].type == gateway.const.Presentation.S_ARDUINO_NODE
    assert gateway.sensors[1].protocol_version == "1.4.1"


def test_id_request_presentation(gateway):
    """Test id request with subsequent presentation."""
    ret = gateway.logic("255;255;3;0;3;\n")
    assert ret == "255;255;3;0;4;1\n"
    assert 1 in gateway.sensors
    gateway.logic("1;255;0;0;17;1.5.0\n")
    assert gateway.sensors[1].type == gateway.const.Presentation.S_ARDUINO_NODE
    assert gateway.sensors[1].protocol_version == "1.5.0"


def test_internal_config(gateway):
    """Test internal config request, metric or imperial."""
    # metric
    ret = gateway.logic("1;255;3;0;6;0\n")
    assert ret == "1;255;3;0;6;M\n"
    # imperial
    gateway.metric = False
    ret = gateway.logic("1;255;3;0;6;0\n")
    assert ret == "1;255;3;0;6;I\n"


def test_internal_time(gateway, add_sensor):
    """Test internal time request."""
    add_sensor(1)
    with mock.patch("mysensors.handler.time") as mock_time:
        mock_time.localtime.return_value = time.gmtime(123456789)
        ret = gateway.logic("1;255;3;0;1;\n")
        assert ret == "1;255;3;0;1;123456789\n"


def test_internal_sketch_name(gateway, add_sensor):
    """Test internal receive of sketch name."""
    sensor = add_sensor(1)
    gateway.logic("1;255;3;0;11;lighthum demo sens\n")
    assert sensor.sketch_name, "lighthum demo sens"


def test_internal_sketch_version(gateway, add_sensor):
    """Test internal receive of sketch version."""
    sensor = add_sensor(1)
    gateway.logic("1;255;3;0;12;1.0\n")
    assert sensor.sketch_version == "1.0"


def test_internal_log_message(gateway, caplog):
    """Test internal receive of log message."""
    mock_transport = mock.MagicMock()
    mock_transport.can_log = False
    gateway.tasks.transport = mock_transport
    payload = "read: 1-1-0 s=0,c=1,t=1,pt=7,l=5,sg=0:22.0\n"
    data = "0;255;3;0;9;{}".format(payload)
    caplog.set_level(logging.DEBUG)
    gateway.logic(data)
    assert "n:0 c:255 t:3 s:9 p:{}".format(payload[:-1]) in caplog.text


@pytest.mark.parametrize(
    "protocol_version, return_value",
    [
        ("1.4", None),
        ("1.5", None),
        ("2.0", "255;255;3;0;20;\n"),
        ("2.1", "255;255;3;0;20;\n"),
        ("2.2", "255;255;3;0;20;\n"),
    ],
)
def test_internal_gateway_ready(protocol_version, return_value, caplog):
    """Test internal receive gateway ready and send discover request."""
    payload = "Gateway startup complete.\n"
    data = "0;255;3;0;14;{}".format(payload)
    caplog.set_level(logging.INFO)
    gateway = get_gateway(protocol_version=protocol_version)
    ret = gateway.logic(data)
    assert ret == return_value
    assert "n:0 c:255 t:3 s:14 p:{}".format(payload[:-1]) in caplog.text


def test_present_light_level_sensor(gateway, add_sensor):
    """Test presentation of a light level sensor."""
    sensor = add_sensor(1)
    gateway.logic("1;0;0;0;16;\n")
    assert 0 in sensor.children
    assert sensor.children[0].type == gateway.const.Presentation.S_LIGHT_LEVEL


def test_present_humidity_sensor(gateway, add_sensor):
    """Test presentation of a humidity sensor."""
    sensor = add_sensor(1)
    gateway.logic("1;0;0;0;7;\n")
    assert 0 in sensor.children
    assert sensor.children[0].type == gateway.const.Presentation.S_HUM


def test_present_same_child(gateway, add_sensor):
    """Test presentation of the same child id again."""
    sensor = add_sensor(1)
    gateway.logic("1;0;0;0;16;\n")
    assert 0 in sensor.children
    assert sensor.children[0].type == gateway.const.Presentation.S_LIGHT_LEVEL
    gateway.logic("1;0;0;0;7;\n")
    assert 0 in sensor.children
    assert sensor.children[0].type == gateway.const.Presentation.S_LIGHT_LEVEL


def test_set_light_level(gateway, add_sensor):
    """Test set of light level."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    gateway.logic("1;0;1;0;23;43\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_LIGHT_LEVEL] == "43"


def test_set_humidity_level(gateway, add_sensor):
    """Test set humidity level."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_HUM)
    gateway.logic("1;1;1;0;1;75\n")
    assert sensor.children[1].values[gateway.const.SetReq.V_HUM] == "75"


def test_battery_level(gateway, add_sensor):
    """Test internal receive of battery level."""
    sensor = add_sensor(1)
    gateway.logic("1;255;3;0;0;79\n")
    assert sensor.battery_level == 79


def test_bad_battery_level(gateway, add_sensor):
    """Test internal receive of bad battery level."""
    sensor = add_sensor(1)
    gateway.logic("1;255;3;0;0;-1\n")
    assert sensor.battery_level == 0


@pytest.mark.parametrize(
    "protocol_version, return_value, call_count",
    [
        ("1.4", 0, 0),
        ("1.5", 0, 0),
        ("2.0", 123456, 1),
        ("2.1", 123456, 1),
        ("2.2", 123456, 1),
    ],
)
@mock.patch("mysensors.Gateway.alert")
def test_heartbeat_value(mock_alert, protocol_version, return_value, call_count):
    """Test internal receive of heartbeat."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    gateway.logic("1;255;3;0;22;123456\n")
    assert sensor.heartbeat == return_value
    assert mock_alert.call_count == call_count


@mock.patch("mysensors.Gateway.alert")
def test_bad_heartbeat_value(mock_alert, gateway, add_sensor):
    """Test internal receive of bad heartbeat."""
    sensor = add_sensor(1)
    gateway.logic("1;255;3;0;22;bad\n")
    assert sensor.heartbeat == 0
    assert mock_alert.call_count == 0


def test_set_bad_heartbeat(add_sensor):
    """Test set a bad heartbeat attribute on a node."""
    sensor = add_sensor(1)
    sensor.heartbeat = "bad"
    assert sensor.heartbeat == 0


def test_req(gateway, add_sensor):
    """Test req message in case where value exists."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_POWER)
    sensor.set_child_value(1, gateway.const.SetReq.V_WATT, 42)
    ret = gateway.logic("1;1;2;0;17;\n")
    assert ret == "1;1;1;0;17;42\n"


def test_req_zerovalue(gateway, add_sensor):
    """Test req message in case where value exists but is zero."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_POWER)
    sensor.set_child_value(1, gateway.const.SetReq.V_WATT, 0)
    ret = gateway.logic("1;1;2;0;17;\n")
    assert ret == "1;1;1;0;17;0\n"


def test_req_novalue(gateway, add_sensor):
    """Test req message for sensor with no value."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_POWER)
    ret = gateway.logic("1;1;2;0;17;\n")
    assert ret is None


def test_req_notasensor(gateway):
    """Test req message for non-existent sensor."""
    ret = gateway.logic("1;1;2;0;17;\n")
    assert ret is None


def test_callback(gateway, add_sensor):
    """Test gateway callback function."""
    messages = []

    def callback(message):
        """Add message to messages list."""
        messages.append(message)

    gateway.event_callback = callback
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    gateway.logic("1;0;1;0;23;43\n")
    assert len(messages) == 1
    assert messages[0].gateway is gateway
    assert messages[0].node_id == 1
    assert messages[0].child_id == 0
    assert messages[0].type == 1
    assert messages[0].ack == 0
    assert messages[0].sub_type == 23
    assert messages[0].payload == "43"


def test_callback_exception(gateway, caplog):
    """Test gateway callback with exception."""
    side_effect = ValueError("test callback error")
    msg = mock.MagicMock()
    caplog.set_level(logging.ERROR)
    with mock.patch.object(
        gateway, "event_callback", side_effect=side_effect
    ) as mock_callback:
        gateway.alert(msg)
    assert mock_callback.call_count == 1
    assert "test callback error" in caplog.text


def test_set_and_reboot(gateway, add_sensor):
    """Test set message with reboot attribute true."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    sensor.reboot = True
    ret = gateway.logic("1;0;1;0;23;43\n")
    assert ret == "1;255;3;0;13;\n"
    gateway.logic("1;255;0;0;17;1.4.1\n")
    assert sensor.reboot is False


def test_set_child_value(gateway, add_sensor):
    """Test Gateway method set_child_value."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT)
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT, "1")
    ret = gateway.tasks.run_job()
    assert ret == "1;0;1;0;2;1\n"
    # test integer value
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT, 0)
    ret = gateway.tasks.run_job()
    assert ret == "1;0;1;0;2;0\n"


@pytest.mark.parametrize(
    "protocol_version, return_value",
    [
        ("1.4", None),
        ("1.5", None),
        ("2.0", "1;255;3;0;19;\n"),
        ("2.1", "1;255;3;0;19;\n"),
        ("2.2", "1;255;3;0;19;\n"),
    ],
)
def test_set_child_value_no_sensor(protocol_version, return_value):
    """Test Gateway method set_child_value with no sensor."""
    gateway = get_gateway(protocol_version=protocol_version)
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT, "1")
    ret = gateway.tasks.run_job()
    assert ret == return_value


@pytest.mark.parametrize(
    "protocol_version, return_value",
    [
        ("1.4", None),
        ("1.5", None),
        ("2.0", "1;255;3;0;19;\n"),
        ("2.1", "1;255;3;0;19;\n"),
        ("2.2", "1;255;3;0;19;\n"),
    ],
)
def test_non_presented_child(protocol_version, return_value):
    """Test non presented sensor child."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    gateway.logic("1;0;1;0;23;43\n")
    assert 0 not in sensor.children
    ret = gateway.tasks.run_job()
    assert ret == return_value
    gateway.logic("1;1;2;0;1;\n")
    assert 1 not in sensor.children
    ret = gateway.tasks.run_job()
    assert ret == return_value


def test_set_child_no_children(gateway, add_sensor):
    """Test Gateway method set_child_value without child in children."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT)
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT, 1, children={})
    ret = gateway.tasks.run_job()
    assert ret is None


def test_set_child_value_bad_type(gateway, add_sensor):
    """Test Gateway method set_child_value with bad type."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT)
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT, 1, msg_type="one")
    ret = gateway.tasks.run_job()
    assert ret is None


def test_set_child_value_bad_ack(gateway, add_sensor):
    """Test Gateway method set_child_value with bad ack."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT)
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT, 1, ack="one")
    ret = gateway.tasks.run_job()
    assert ret is None


def test_set_child_value_value_type(gateway, add_sensor):
    """Test Gateway method set_child_value with string value type."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT)
    gateway.set_child_value(1, 0, 2, 1)
    ret = gateway.tasks.run_job()
    assert ret == "1;0;1;0;2;1\n"
    child_values = dict(sensor.children[0].values)
    gateway.set_child_value(1, 0, "2", 1)
    ret = gateway.tasks.run_job()
    assert child_values == sensor.children[0].values
    assert ret == "1;0;1;0;2;1\n"


def test_child_validate(gateway, add_sensor):
    """Test child validate method."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    sensor.children[0].values[gateway.const.SetReq.V_LIGHT_LEVEL] = "43"
    sensor.children[0].validate(gateway.protocol_version)
    assert sensor.children[0].values[gateway.const.SetReq.V_LIGHT_LEVEL] == "43"
    sensor.children[0].values[gateway.const.SetReq.V_VAR1] = "custom"
    sensor.children[0].validate(gateway.protocol_version)
    assert sensor.children[0].values[gateway.const.SetReq.V_VAR1] == "custom"
    sensor.children[0].values[gateway.const.SetReq.V_TRIPPED] = "1"
    with pytest.raises(vol.Invalid):
        sensor.children[0].validate(gateway.protocol_version)


def test_set_forecast(gateway, add_sensor):
    """Test set of V_FORECAST."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_BARO)
    gateway.logic("1;0;1;0;5;sunny\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_FORECAST] == "sunny"
    gateway.logic("1;0;1;0;5;rainy\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_FORECAST] == "rainy"


def test_set_bad_battery_attribute(add_sensor):
    """Test set a bad battery_level attribute on a node."""
    sensor = add_sensor(1)
    sensor.battery_level = None
    assert sensor.battery_level == 0


@pytest.mark.parametrize("protocol_version", ["1.5", "2.0", "2.1", "2.2"])
def test_set_rgb(protocol_version):
    """Test set of V_RGB."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    sensor.protocol_version = protocol_version
    sensor.add_child_sensor(0, gateway.const.Presentation.S_RGB_LIGHT)
    gateway.logic("1;0;1;0;40;ffffff\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_RGB] == "ffffff"
    gateway.logic("1;0;1;0;40;ffffff00\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_RGB] == "ffffff"
    gateway.logic("1;0;1;0;40;nothex\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_RGB] == "ffffff"


@pytest.mark.parametrize("protocol_version", ["1.5", "2.0", "2.1", "2.2"])
def test_set_rgbw(protocol_version):
    """Test set of V_RGBW."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    sensor.protocol_version = protocol_version
    sensor.add_child_sensor(0, gateway.const.Presentation.S_RGBW_LIGHT)
    gateway.logic("1;0;1;0;41;ffffffff\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_RGBW] == "ffffffff"
    gateway.logic("1;0;1;0;41;ffffffff00\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_RGBW] == "ffffffff"
    gateway.logic("1;0;1;0;41;nothexxx\n")
    assert sensor.children[0].values[gateway.const.SetReq.V_RGBW] == "ffffffff"


@pytest.mark.parametrize(
    "protocol_version, wake_msg",
    [
        ("2.0", "1;255;3;0;22;123456\n"),
        ("2.1", "1;255;3;0;22;123456\n"),
        ("2.2", "1;255;3;0;32;500\n"),
    ],
)
def test_smartsleep(protocol_version, wake_msg):
    """Test smartsleep feature."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    gateway.logic("1;0;1;0;23;43\n")
    ret = gateway.tasks.run_job()
    assert ret is None
    # heartbeat
    gateway.logic(wake_msg)
    ret = gateway.tasks.run_job()
    # nothing has changed
    assert ret is None
    # change from controller side
    gateway.set_child_value(1, 0, gateway.const.SetReq.V_LIGHT_LEVEL, "57")
    ret = gateway.tasks.run_job()
    # no heartbeat
    assert ret is None
    # heartbeat comes in
    gateway.logic(wake_msg)
    ret = gateway.tasks.run_job()
    # instance responds with new values
    assert ret == "1;0;1;0;23;57\n"
    # request from node
    gateway.logic("1;0;2;0;23;\n")
    ret = gateway.tasks.run_job()
    # no heartbeat
    assert ret is None
    # heartbeat
    gateway.logic(wake_msg)
    ret = gateway.tasks.run_job()
    # instance responds to request with current value
    assert ret == "1;0;1;0;23;57\n"
    # heartbeat
    gateway.logic(wake_msg)
    ret = gateway.tasks.run_job()
    # nothing has changed
    assert ret is None


@pytest.mark.parametrize(
    "protocol_version, wake_msg",
    [
        ("2.0", "1;255;3;0;22;123456\n"),
        ("2.1", "1;255;3;0;22;123456\n"),
        ("2.2", "1;255;3;0;32;500\n"),
    ],
)
def test_smartsleep_from_unknown(protocol_version, wake_msg):
    """Test smartsleep message from unknown node."""
    gateway = get_gateway(protocol_version=protocol_version)
    gateway.logic(wake_msg)
    ret = gateway.tasks.run_job()
    assert ret == "1;255;3;0;19;\n"


@pytest.mark.parametrize(
    "protocol_version, wake_msg",
    [
        ("2.0", "1;255;3;0;22;123456\n"),
        ("2.1", "1;255;3;0;22;123456\n"),
        ("2.2", "1;255;3;0;32;500\n"),
    ],
)
def test_set_with_new_state(protocol_version, wake_msg):
    """Test set message with populated new_state."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    gateway.logic("1;0;1;0;23;43\n")
    gateway.logic(wake_msg)
    gateway.logic("1;0;1;0;23;57\n")
    assert (
        sensor.children[0].values[gateway.const.SetReq.V_LIGHT_LEVEL]
        == sensor.new_state[0].values[gateway.const.SetReq.V_LIGHT_LEVEL]
    )


@pytest.mark.parametrize("protocol_version", ["2.0", "2.1", "2.2"])
def test_discover_response_unknown(protocol_version):
    """Test internal receive discover response."""
    gateway = get_gateway(protocol_version=protocol_version)
    # Test sensor 1 unknown.
    gateway.logic("1;255;3;0;21;0")
    ret = gateway.tasks.run_job()
    assert ret == "1;255;3;0;19;\n"


@pytest.mark.parametrize("protocol_version", ["2.0", "2.1", "2.2"])
@mock.patch("mysensors.Gateway.is_sensor")
def test_discover_response_known(mock_is_sensor, protocol_version):
    """Test internal receive discover response."""
    gateway = get_gateway(protocol_version=protocol_version)
    # Test sensor 1 known.
    get_sensor(1, gateway)
    gateway.logic("1;255;3;0;21;0")
    assert mock_is_sensor.call_count == 1


@pytest.mark.parametrize("protocol_version", ["2.0", "2.1", "2.2"])
def test_set_position(protocol_version):
    """Test set of V_POSITION."""
    gateway = get_gateway(protocol_version=protocol_version)
    sensor = get_sensor(1, gateway)
    sensor.protocol_version = protocol_version
    sensor.add_child_sensor(0, gateway.const.Presentation.S_GPS)
    gateway.logic("1;0;1;0;49;10.0,10.0,10.0\n")
    assert (
        sensor.children[0].values[gateway.const.SetReq.V_POSITION] == "10.0,10.0,10.0"
    )
    gateway.logic("1;0;1;0;49;bad,format\n")
    assert (
        sensor.children[0].values[gateway.const.SetReq.V_POSITION] == "10.0,10.0,10.0"
    )
    gateway.logic("1;0;1;0;41;bad,bad,bad\n")
    assert (
        sensor.children[0].values[gateway.const.SetReq.V_POSITION] == "10.0,10.0,10.0"
    )


def test_gateway_bad_protocol():
    """Test initializing gateway with a bad protocol_version."""
    gateway = get_gateway(protocol_version=None)
    assert gateway.protocol_version == "1.4"


def test_gateway_low_protocol():
    """Test initializing gateway with too low protocol_version."""
    gateway = get_gateway(protocol_version="1.3")
    assert gateway.protocol_version == "1.4"


def test_update_fw():
    """Test calling fw_update."""
    gateway = get_gateway()
    mock_update = mock.MagicMock()
    gateway.tasks.ota.make_update = mock_update
    gateway.update_fw(1, 1, 1)
    assert mock_update.call_count == 1


def test_update_fw_bad_path(caplog):
    """Test calling fw_update with bad path."""
    gateway = get_gateway()
    mock_update = mock.MagicMock()
    gateway.tasks.ota.make_update = mock_update
    bad_path = "/bad/path"
    gateway.update_fw(1, 1, 1, bad_path)
    log_msg = "Firmware path {} does not exist or is not readable".format(bad_path)
    assert mock_update.call_count == 0
    assert log_msg in caplog.text
