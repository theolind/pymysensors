"""Test task module."""

import pytest
import voluptuous

from mysensors.sensor import ChildSensor, Sensor
from mysensors.const import get_const


def test_is_smart_sleep_node():
    """Test schedule persistence on threading gateway."""
    const = get_const("1.4")
    sensor_id = 1

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(0, const.Presentation.S_LIGHT_LEVEL)

    assert not sensor.is_smart_sleep_node

    sensor.new_state[sensor_id] = {}

    assert sensor.is_smart_sleep_node


def test_init_smart_sleep_mode():
    """Test that the new state array is populated correctly."""
    const = get_const("1.4")
    sensor_id = 1

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(0, const.Presentation.S_LIGHT_LEVEL)
    sensor.add_child_sensor(1, const.Presentation.S_LIGHT_LEVEL)

    assert not sensor.new_state

    sensor.init_smart_sleep_mode()

    assert 0 in sensor.new_state
    assert isinstance(sensor.new_state[0], ChildSensor)
    assert 1 in sensor.new_state
    assert isinstance(sensor.new_state[1], ChildSensor)


def test_get_desired_value():
    """Test that sensor returns correct desired value in different states."""
    const = get_const("1.4")
    sensor_id = 1
    child_id = 0
    value_type = const.SetReq.V_LIGHT_LEVEL
    wrong_child_id = 100
    wrong_value_type = 9999

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(child_id, const.Presentation.S_LIGHT_LEVEL)

    assert sensor.get_desired_value(child_id, value_type) is None

    sensor.update_child_value(child_id, value_type, "50")
    assert sensor.get_desired_value(child_id, value_type) == "50"

    sensor.init_smart_sleep_mode()

    sensor.set_child_desired_state(child_id, value_type, "90")
    assert sensor.get_desired_value(child_id, value_type) == "90"

    sensor.update_child_value(child_id, value_type, "70")
    assert sensor.get_desired_value(child_id, value_type) == "70"

    assert sensor.get_desired_value(wrong_child_id, value_type) is None
    assert sensor.get_desired_value(child_id, wrong_value_type) is None


def test_get_desired_value_empty_string():
    """Test that sensor returns correct value if the desired state is empty string."""
    const = get_const("1.4")
    sensor_id = 1
    child_id = 0
    value_type = const.SetReq.V_VAR1

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(child_id, const.Presentation.S_CUSTOM)

    assert sensor.get_desired_value(child_id, value_type) is None

    sensor.update_child_value(child_id, value_type, "Some string")
    assert sensor.get_desired_value(child_id, value_type) == "Some string"

    sensor.init_smart_sleep_mode()

    sensor.set_child_desired_state(child_id, value_type, "")
    assert sensor.get_desired_value(child_id, value_type) == ""


def test_set_child_desired_state():
    """Test that we area able to set the desired state."""
    const = get_const("1.4")
    sensor_id = 1
    child_id = 0
    value_type = const.SetReq.V_LIGHT_LEVEL
    wrong_child_id = 100
    wrong_value_type = 99999

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(child_id, const.Presentation.S_LIGHT_LEVEL)
    sensor.init_smart_sleep_mode()

    # able to set
    sensor.set_child_desired_state(child_id, value_type, "50")
    assert child_id in sensor.new_state
    assert value_type in sensor.new_state[child_id].values
    assert sensor.new_state[child_id].values[value_type] == "50"

    # able to update
    sensor.set_child_desired_state(child_id, value_type, "90")
    assert sensor.new_state[child_id].values[value_type] == "90"

    # does not set unknown child
    with pytest.raises(ValueError):
        sensor.set_child_desired_state(wrong_child_id, value_type, "50")

    # does not set wrong value type
    with pytest.raises(voluptuous.error.MultipleInvalid):
        sensor.set_child_desired_state(child_id, wrong_value_type, "50")

    # does not set wrong value type
    with pytest.raises(voluptuous.error.MultipleInvalid):
        sensor.set_child_desired_state(child_id, value_type, "bad value")


def test_update_child_value():
    """Test that we can update child state."""
    const = get_const("1.4")
    sensor_id = 1
    child_id = 0
    wrong_child_id = 100
    value_type = const.SetReq.V_LIGHT_LEVEL

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(child_id, const.Presentation.S_LIGHT_LEVEL)

    assert value_type not in sensor.children[child_id].values

    # able to set
    sensor.update_child_value(child_id, value_type, "50")
    assert sensor.children[child_id].values[value_type] == "50"

    # able to update
    sensor.update_child_value(child_id, value_type, "90")
    assert sensor.children[child_id].values[value_type] == "90"

    # does not set unknown child
    sensor.update_child_value(wrong_child_id, value_type, "50")
    assert wrong_child_id not in sensor.children


def test_update_child_value_resets_new_state():
    """Test that update of child state resets the new state."""
    const = get_const("1.4")
    sensor_id = 1
    child_id = 0
    value_type = const.SetReq.V_LIGHT_LEVEL

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(child_id, const.Presentation.S_LIGHT_LEVEL)
    sensor.init_smart_sleep_mode()
    sensor.set_child_desired_state(child_id, value_type, "50")

    assert sensor.new_state[child_id].values[value_type] == "50"

    sensor.update_child_value(child_id, value_type, "60")

    assert sensor.new_state[child_id].values[value_type] is None


def test_validate_child_state():
    """Test that update of child state resets the new state."""
    const = get_const("1.4")
    sensor_id = 1
    child_id = 0
    value_type = const.SetReq.V_LIGHT_LEVEL

    sensor = Sensor(sensor_id)
    sensor.add_child_sensor(child_id, const.Presentation.S_LIGHT_LEVEL)

    with pytest.raises(voluptuous.error.MultipleInvalid):
        sensor.validate_child_state(child_id, value_type, "bad value")

    with pytest.raises(voluptuous.error.MultipleInvalid):
        sensor.validate_child_state(300, value_type, "50")

    with pytest.raises(voluptuous.error.MultipleInvalid):
        sensor.validate_child_state(child_id, 9999, "50")

    with pytest.raises(ValueError):
        sensor.validate_child_state(child_id, "bad value type", "50")

    with pytest.raises(ValueError):
        sensor.validate_child_state(child_id, None, "50")

    sensor.validate_child_state(child_id, value_type, "50")
