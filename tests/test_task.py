"""Test task module."""
from unittest import mock

from mysensors import Gateway
from mysensors.task import SyncTasks


def get_gateway(**kwargs):
    """Return a gateway instance."""
    _gateway = Gateway(**kwargs)
    _gateway.tasks = SyncTasks(
        _gateway.const, True, "mysensors.pickle", _gateway.sensors, mock.MagicMock()
    )
    return _gateway


@mock.patch("mysensors.persistence.Persistence.save_sensors")
@mock.patch("mysensors.task.threading.Timer")
def test_threading_persistence(mock_timer_class, mock_save_sensors):
    """Test schedule persistence on threading gateway."""
    mock_timer_1 = mock.MagicMock()
    mock_timer_2 = mock.MagicMock()
    mock_timer_class.side_effect = [mock_timer_1, mock_timer_2]
    gateway = get_gateway()
    gateway.tasks.persistence.schedule_save_sensors()
    assert mock_save_sensors.call_count == 1
    assert mock_timer_class.call_count == 1
    assert mock_timer_1.start.call_count == 1
    gateway.tasks.persistence.schedule_save_sensors()
    assert mock_save_sensors.call_count == 2
    assert mock_timer_class.call_count == 2
    assert mock_timer_1.start.call_count == 1
    assert mock_timer_2.start.call_count == 1
    gateway.tasks.stop()
    assert mock_timer_2.cancel.call_count == 1
    assert mock_save_sensors.call_count == 3
