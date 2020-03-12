"""Test persistence."""
import json
import os
from collections import deque
from unittest import mock

import pytest

from mysensors import Gateway
from mysensors.persistence import MySensorsJSONEncoder, Persistence
from mysensors.sensor import ChildSensor, Sensor

# pylint: disable=redefined-outer-name


@pytest.fixture
def gateway():
    """Return gateway instance."""
    return Gateway()


@pytest.fixture
def add_sensor(gateway):
    """Return function for adding node."""

    def _add_sensor(sensor_id):
        """Add sensor node. Return sensor node instance."""
        gateway.sensors[sensor_id] = Sensor(sensor_id)
        return gateway.sensors[sensor_id]

    return _add_sensor


@pytest.mark.parametrize("filename", ["file.pickle", "file.json"])
def test_persistence(gateway, add_sensor, filename, tmpdir):
    """Test persistence."""
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL, "test")
    sensor.children[0].values[gateway.const.SetReq.V_LIGHT_LEVEL] = "43"
    sensor.type = gateway.const.Presentation.S_ARDUINO_NODE
    sensor.sketch_name = "testsketch"
    sensor.sketch_version = "1.0"
    sensor.battery_level = 78
    sensor.protocol_version = "1.4.1"
    sensor.heartbeat = 123456

    persistence_file = tmpdir.join(filename)
    gateway.persistence = Persistence(
        gateway.sensors, mock.MagicMock(), persistence_file.strpath
    )
    gateway.persistence.save_sensors()
    del gateway.sensors[1]
    assert 1 not in gateway.sensors
    gateway.persistence.safe_load_sensors()
    assert gateway.sensors[1].sketch_name == sensor.sketch_name
    assert gateway.sensors[1].sketch_version == sensor.sketch_version
    assert gateway.sensors[1].battery_level == sensor.battery_level
    assert gateway.sensors[1].type == sensor.type
    assert gateway.sensors[1].protocol_version == sensor.protocol_version
    assert gateway.sensors[1].heartbeat == sensor.heartbeat
    assert gateway.sensors[1].children[0].id == sensor.children[0].id
    assert gateway.sensors[1].children[0].type == sensor.children[0].type
    assert gateway.sensors[1].children[0].description == sensor.children[0].description
    assert gateway.sensors[1].children[0].values == sensor.children[0].values
    gateway.persistence.save_sensors()
    del gateway.sensors[1]
    assert 1 not in gateway.sensors
    gateway.persistence.safe_load_sensors()
    assert 1 in gateway.sensors


def test_bad_file_name(gateway, add_sensor, tmpdir):
    """Test persistence with bad file name."""
    add_sensor(1)
    persistence_file = tmpdir.join("file.bad")
    gateway.persistence = Persistence(
        gateway.sensors, mock.MagicMock(), persistence_file.strpath
    )
    with pytest.raises(Exception):
        gateway.persistence.save_sensors()


def test_json_no_files(gateway, tmpdir):
    """Test json persistence with no files existing."""
    assert not gateway.sensors
    persistence_file = tmpdir.join("file.json")
    gateway.persistence = Persistence(
        gateway.sensors, mock.MagicMock(), persistence_file.strpath
    )
    gateway.persistence.safe_load_sensors()
    assert not gateway.sensors


@pytest.mark.parametrize("filename", ["file.pickle", "file.json"])
def test_empty_files(gateway, filename, tmpdir):
    """Test persistence with empty files."""
    assert not gateway.sensors
    persistence_file = tmpdir.join(filename)
    gateway.persistence = Persistence(
        gateway.sensors, mock.MagicMock(), persistence_file.strpath
    )
    persistence = gateway.persistence
    persistence_file.write("")
    with open(persistence.persistence_bak, "w") as file_handle:
        file_handle.write("")
    gateway.persistence.safe_load_sensors()
    assert not gateway.sensors


def test_json_empty_file_good_bak(gateway, add_sensor, tmpdir):
    """Test json persistence with empty file but good backup."""
    add_sensor(1)
    assert 1 in gateway.sensors
    persistence_file = tmpdir.join("file.json")
    orig_file_name = persistence_file.strpath
    gateway.persistence = Persistence(gateway.sensors, mock.MagicMock(), orig_file_name)
    gateway.persistence.save_sensors()
    del gateway.sensors[1]
    assert 1 not in gateway.sensors
    persistence_file.rename(gateway.persistence.persistence_bak)
    with open(orig_file_name, "w") as json_file:
        json_file.write("")
    gateway.persistence.safe_load_sensors()
    assert 1 in gateway.sensors


@pytest.mark.parametrize("filename", ["file.pickle", "file.json"])
@mock.patch("mysensors.persistence.Persistence._save_json")
def test_persistence_upgrade(mock_save_json, gateway, add_sensor, filename, tmpdir):
    """Test that all attributes are present after persistence upgrade."""

    def save_json_upgrade(filename):
        """Save sensors to json file.

        Only used for testing upgrade with missing attributes.
        """
        with open(filename, "w") as file_handle:
            json.dump(gateway.sensors, file_handle, cls=MySensorsJSONEncoderTestUpgrade)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    mock_save_json.side_effect = save_json_upgrade
    sensor = add_sensor(1)
    sensor.add_child_sensor(0, gateway.const.Presentation.S_LIGHT_LEVEL)
    del sensor.__dict__["new_state"]
    assert "new_state" not in sensor.__dict__
    del sensor.__dict__["queue"]
    assert "queue" not in sensor.__dict__
    del sensor.__dict__["reboot"]
    assert "reboot" not in sensor.__dict__
    del sensor.__dict__["_battery_level"]
    assert "_battery_level" not in sensor.__dict__
    sensor.__dict__["battery_level"] = 58
    del sensor.__dict__["_protocol_version"]
    assert "_protocol_version" not in sensor.__dict__
    sensor.__dict__["protocol_version"] = gateway.protocol_version
    del sensor.__dict__["_heartbeat"]
    assert "_heartbeat" not in sensor.__dict__
    del sensor.children[0].__dict__["description"]
    assert "description" not in sensor.children[0].__dict__
    persistence_file = tmpdir.join(filename)
    gateway.persistence = Persistence(
        gateway.sensors, mock.MagicMock(), persistence_file.strpath
    )
    gateway.persistence.save_sensors()
    del gateway.sensors[1]
    assert 1 not in gateway.sensors
    gateway.persistence.safe_load_sensors()
    assert gateway.sensors[1].battery_level == 58
    assert gateway.sensors[1].protocol_version == gateway.protocol_version
    assert gateway.sensors[1].heartbeat == 0
    assert gateway.sensors[1].new_state == {}
    assert gateway.sensors[1].queue == deque()
    assert gateway.sensors[1].reboot is False
    assert gateway.sensors[1].children[0].description == ""
    assert gateway.sensors[1].children[0].id == sensor.children[0].id
    assert gateway.sensors[1].children[0].type == sensor.children[0].type


class MySensorsJSONEncoderTestUpgrade(MySensorsJSONEncoder):
    """JSON encoder used for testing upgrade with missing attributes."""

    def default(self, obj):  # pylint: disable=E0202
        """Serialize obj into JSON."""
        if isinstance(obj, Sensor):
            return obj.__dict__
        if isinstance(obj, ChildSensor):
            return {
                "id": obj.id,
                "type": obj.type,
                "values": obj.values,
            }
        return super().default(obj)
