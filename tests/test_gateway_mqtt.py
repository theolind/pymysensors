"""Test mysensors MQTT gateway with unittest."""
import logging
import time
from unittest import mock

import pytest

from mysensors.gateway_mqtt import MQTTGateway
from mysensors.sensor import Sensor

# pylint: disable=redefined-outer-name, too-many-arguments


@pytest.fixture
def mock_pub():
    """Return a mock callback to publish to mqtt broker."""
    return mock.Mock()


@pytest.fixture
def mock_sub():
    """Return a mock callback to subscribe to a mqtt topic."""
    return mock.Mock()


@pytest.fixture
def gateway(mock_pub, mock_sub):
    """Yield gateway instance."""
    _gateway = MQTTGateway(mock_pub, mock_sub)
    yield _gateway
    _gateway.tasks.stop()


def get_gateway(*args, **kwargs):
    """Return a gateway instance."""
    return MQTTGateway(*args, **kwargs)


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


def test_send(gateway, mock_pub):
    """Test send method."""
    gateway.send("1;1;1;0;1;20\n")
    assert mock_pub.call_count == 1
    assert mock_pub.call_args == mock.call("/1/1/1/0/1", "20", 0, True)


def test_send_empty_string(gateway, mock_pub):
    """Test send method with empty string."""
    gateway.send("")
    assert mock_pub.call_count == 0


def test_send_error(gateway, mock_pub, caplog):
    """Test send method with error on publish."""
    mock_pub.side_effect = ValueError("Publish topic cannot contain wildcards.")
    caplog.set_level(logging.ERROR)
    gateway.send("1;1;1;0;1;20\n")
    assert mock_pub.call_count == 1
    assert mock_pub.call_args == mock.call("/1/1/1/0/1", "20", 0, True)
    assert (
        "Publish to /1/1/1/0/1 failed: "
        "Publish topic cannot contain wildcards." in caplog.text
    )


def test_recv(gateway, add_sensor):
    """Test recv method."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_HUM)
    sensor.children[1].values[gateway.const.SetReq.V_HUM] = "20"
    gateway.tasks.transport.recv("/1/1/2/0/1", "", 0)
    ret = gateway.tasks.run_job()
    assert ret == "1;1;1;0;1;20\n"
    gateway.tasks.transport.recv("/1/1/2/0/1", "", 1)
    ret = gateway.tasks.run_job()
    assert ret == "1;1;1;1;1;20\n"


def test_recv_wrong_prefix(gateway, add_sensor):
    """Test recv method with wrong topic prefix."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_HUM)
    sensor.children[1].values[gateway.const.SetReq.V_HUM] = "20"
    gateway.tasks.transport.recv("wrong/1/1/2/0/1", "", 0)
    ret = gateway.tasks.run_job()
    assert ret is None


def test_presentation(gateway, add_sensor, mock_sub):
    """Test handle presentation message."""
    add_sensor(1)
    gateway.logic("1;1;0;0;7;Humidity Sensor\n")
    calls = [
        mock.call("/1/1/1/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/1/2/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/+/4/+/+", gateway.tasks.transport.recv, 0),
    ]
    assert mock_sub.call_count == 3
    assert mock_sub.mock_calls == calls


def test_presentation_no_sensor(gateway, mock_sub):
    """Test handle presentation message without sensor."""
    gateway.logic("1;1;0;0;7;Humidity Sensor\n")
    assert mock_sub.call_count == 0


def test_subscribe_error(gateway, add_sensor, mock_sub, caplog):
    """Test subscribe throws error."""
    add_sensor(1)
    mock_sub.side_effect = ValueError("No topic specified, or incorrect topic type.")
    caplog.set_level(logging.ERROR)
    gateway.logic("1;1;0;0;7;Humidity Sensor\n")
    calls = [
        mock.call("/1/1/1/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/1/2/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/+/4/+/+", gateway.tasks.transport.recv, 0),
    ]
    assert mock_sub.call_count == 3
    assert mock_sub.mock_calls == calls
    assert (
        "Subscribe to /1/1/1/+/+ failed: "
        "No topic specified, or incorrect topic type." in caplog.text
    )


@mock.patch("mysensors.persistence.Persistence.safe_load_sensors")
@mock.patch("mysensors.persistence.Persistence.save_sensors")
def test_start_stop_gateway(mock_save, mock_load, mock_pub, mock_sub):
    """Test start and stop of MQTT gateway."""
    gateway = get_gateway(mock_pub, mock_sub, persistence=True)
    mock_schedule_save = mock.MagicMock()
    gateway.tasks.persistence.schedule_save_sensors = mock_schedule_save
    sensor = get_sensor(1, gateway)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_HUM)
    sensor.children[1].values[gateway.const.SetReq.V_HUM] = "20"
    # should generate a publish of 20
    gateway.tasks.transport.recv("/1/1/2/0/1", "", 0)
    gateway.tasks.transport.recv("/1/1/1/0/1", "30", 0)
    # should generate a publish of 30
    gateway.tasks.transport.recv("/1/1/2/0/1", "", 0)
    gateway.start_persistence()
    assert mock_load.call_count == 1
    assert mock_schedule_save.call_count == 1
    gateway.start()
    time.sleep(0.05)
    calls = [
        mock.call("/+/+/0/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/+/+/3/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/1/1/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/1/2/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/+/4/+/+", gateway.tasks.transport.recv, 0),
    ]
    assert mock_sub.call_count == 5
    assert mock_sub.mock_calls == calls
    calls = [
        mock.call("/1/1/1/0/1", "20", 0, True),
        mock.call("/1/1/1/0/1", "30", 0, True),
    ]
    assert mock_pub.call_count == 2
    assert mock_pub.mock_calls == calls
    gateway.stop()
    assert mock_save.call_count == 1


def test_mqtt_load_persistence(mock_pub, mock_sub, tmpdir):
    """Test load persistence file for MQTTGateway."""
    gateway = get_gateway(mock_pub, mock_sub, persistence=True)
    sensor = get_sensor(1, gateway)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_HUM)
    sensor.children[1].values[gateway.const.SetReq.V_HUM] = "20"

    persistence_file = tmpdir.join("file.json")
    gateway.tasks.persistence.persistence_file = persistence_file.strpath
    gateway.tasks.persistence.save_sensors()
    del gateway.sensors[1]
    assert 1 not in gateway.sensors
    gateway.tasks.persistence.safe_load_sensors()
    # pylint: disable=protected-access
    gateway.init_topics()
    assert gateway.sensors[1].children[1].id == sensor.children[1].id
    assert gateway.sensors[1].children[1].type == sensor.children[1].type
    assert gateway.sensors[1].children[1].values == sensor.children[1].values
    calls = [
        mock.call("/+/+/0/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/+/+/3/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/1/1/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/1/2/+/+", gateway.tasks.transport.recv, 0),
        mock.call("/1/+/4/+/+", gateway.tasks.transport.recv, 0),
    ]
    assert mock_sub.call_count == 5
    assert mock_sub.mock_calls == calls


def test_nested_prefix(mock_pub, mock_sub):
    """Test recv and send method with nested topic prefix."""
    gateway = get_gateway(
        mock_pub, mock_sub, in_prefix="test/test-in", out_prefix="test/test-out"
    )
    sensor = get_sensor(1, gateway)
    sensor.add_child_sensor(1, gateway.const.Presentation.S_HUM)
    sensor.children[1].values[gateway.const.SetReq.V_HUM] = "20"
    gateway.tasks.transport.recv("test/test-in/1/1/2/0/1", "", 0)
    ret = gateway.tasks.run_job()
    assert ret == "1;1;1;0;1;20\n"
    gateway.tasks.transport.send(ret)
    assert mock_pub.call_args == mock.call("test/test-out/1/1/1/0/1", "20", 0, True)
    gateway.tasks.transport.recv("test/test-in/1/1/2/0/1", "", 1)
    ret = gateway.tasks.run_job()
    assert ret == "1;1;1;1;1;20\n"
    gateway.tasks.transport.send(ret)
    assert mock_pub.call_args == mock.call("test/test-out/1/1/1/1/1", "20", 1, True)


def test_get_gateway_id(mock_pub, mock_sub):
    """Test get_gateway_id method."""
    gateway = get_gateway(
        mock_pub, mock_sub, in_prefix="test/test-in", out_prefix="test/test-out"
    )
    gateway_id = gateway.get_gateway_id()
    assert gateway_id == "test/test-in"
