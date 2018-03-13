"""Test mysensors MQTT gateway with unittest."""
import os
import tempfile
import time
from unittest import TestCase, main, mock

from mysensors.gateway_mqtt import MQTTGateway
from mysensors.persistence import Persistence
from mysensors.sensor import ChildSensor, Sensor


class TestMQTTGateway(TestCase):
    """Test the MQTT Gateway."""

    def setUp(self):
        """Set up gateway."""
        self.mock_pub = mock.Mock()
        self.mock_sub = mock.Mock()
        self.gateway = MQTTGateway(self.mock_pub, self.mock_sub)

    def tearDown(self):
        """Stop MQTTGateway if alive."""
        if self.gateway.is_alive():
            self.gateway.stop()

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = Sensor(sensorid)
        return self.gateway.sensors[sensorid]

    def test_send(self):
        """Test send method."""
        self.gateway.send('1;1;1;0;1;20\n')
        self.mock_pub.assert_called_with('/1/1/1/0/1', '20', 0, True)

    def test_send_empty_string(self):
        """Test send method with empty string."""
        self.gateway.send('')
        self.assertFalse(self.mock_pub.called)

    def test_send_error(self):
        """Test send method with error on publish."""
        self.mock_pub.side_effect = ValueError(
            'Publish topic cannot contain wildcards.')
        with self.assertLogs(level='ERROR') as test_handle:
            self.gateway.send('1;1;1;0;1;20\n')
        self.mock_pub.assert_called_with('/1/1/1/0/1', '20', 0, True)
        self.assertEqual(
            # only check first line of error log
            test_handle.output[0].split('\n', 1)[0],
            'ERROR:mysensors.gateway_mqtt:Publish to /1/1/1/0/1 failed: '
            'Publish topic cannot contain wildcards.')

    def test_recv(self):
        """Test recv method."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.children[1].values[self.gateway.const.SetReq.V_HUM] = '20'
        self.gateway.recv('/1/1/2/0/1', '', 0)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;1;1;0;1;20\n')
        self.gateway.recv('/1/1/2/0/1', '', 1)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;1;1;1;1;20\n')

    def test_recv_wrong_prefix(self):
        """Test recv method with wrong topic prefix."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.children[1].values[self.gateway.const.SetReq.V_HUM] = '20'
        self.gateway.recv('wrong/1/1/2/0/1', '', 0)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)

    def test_presentation(self):
        """Test handle presentation message."""
        self._add_sensor(1)
        self.gateway.logic('1;1;0;0;7;Humidity Sensor\n')
        calls = [
            mock.call('/1/1/1/+/+', self.gateway.recv, 0),
            mock.call('/1/1/2/+/+', self.gateway.recv, 0),
            mock.call('/1/+/4/+/+', self.gateway.recv, 0)]
        self.mock_sub.assert_has_calls(calls)

    def test_presentation_no_sensor(self):
        """Test handle presentation message without sensor."""
        self.gateway.logic('1;1;0;0;7;Humidity Sensor\n')
        self.assertFalse(self.mock_sub.called)

    def test_subscribe_error(self):
        """Test subscribe throws error."""
        self._add_sensor(1)
        self.mock_sub.side_effect = ValueError(
            'No topic specified, or incorrect topic type.')
        with self.assertLogs(level='ERROR') as test_handle:
            self.gateway.logic('1;1;0;0;7;Humidity Sensor\n')
        calls = [
            mock.call('/1/1/1/+/+', self.gateway.recv, 0),
            mock.call('/1/1/2/+/+', self.gateway.recv, 0)]
        self.mock_sub.assert_has_calls(calls)
        self.assertEqual(
            # only check first line of error log
            test_handle.output[0].split('\n', 1)[0],
            'ERROR:mysensors.gateway_mqtt:Subscribe to /1/1/1/+/+ failed: '
            'No topic specified, or incorrect topic type.')

    @mock.patch('mysensors.persistence.Persistence.safe_load_sensors')
    @mock.patch('mysensors.persistence.Persistence.save_sensors')
    def test_start_stop_gateway(self, mock_save, mock_load):
        """Test start and stop of MQTT gateway."""
        self.gateway.persistence = Persistence(self.gateway.sensors)
        mock_cancel_save = mock.MagicMock()
        mock_schedule_save = mock.MagicMock()
        mock_schedule_save.return_value = mock_cancel_save
        self.gateway.persistence.schedule_save_sensors = mock_schedule_save
        self.assertFalse(self.gateway.is_alive())
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.children[1].values[self.gateway.const.SetReq.V_HUM] = '20'
        self.gateway.recv('/1/1/2/0/1', '', 0)
        self.gateway.recv('/1/1/1/0/1', '30', 0)
        self.gateway.recv('/1/1/2/0/1', '', 0)
        self.gateway.start_persistence()
        assert mock_load.call_count == 1
        assert mock_schedule_save.call_count == 1
        self.gateway.start()
        time.sleep(0.05)
        self.assertTrue(self.gateway.is_alive())
        calls = [
            mock.call('/+/+/0/+/+', self.gateway.recv, 0),
            mock.call('/+/+/3/+/+', self.gateway.recv, 0)]
        self.mock_sub.assert_has_calls(calls)
        calls = [
            mock.call('/1/1/1/0/1', '20', 0, True),
            mock.call('/1/1/1/0/1', '30', 0, True)]
        self.mock_pub.assert_has_calls(calls)
        self.gateway.stop()
        self.gateway.join(timeout=0.5)
        self.assertFalse(self.gateway.is_alive())
        assert mock_cancel_save.call_count == 1
        assert mock_save.call_count == 1

    def test_mqtt_load_persistence(self):
        """Test load persistence file for MQTTGateway."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.children[1].values[self.gateway.const.SetReq.V_HUM] = '20'

        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_file = os.path.join(temp_dir, 'file.json')
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            self.gateway.persistence.save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway.persistence.safe_load_sensors()
            # pylint: disable=protected-access
            self.gateway._init_topics()
        self.assertEqual(
            self.gateway.sensors[1].children[1].id,
            sensor.children[1].id)
        self.assertEqual(
            self.gateway.sensors[1].children[1].type,
            sensor.children[1].type)
        self.assertEqual(
            self.gateway.sensors[1].children[1].values,
            sensor.children[1].values)
        calls = [
            mock.call('/1/1/1/+/+', self.gateway.recv, 0),
            mock.call('/1/1/2/+/+', self.gateway.recv, 0),
            mock.call('/1/+/4/+/+', self.gateway.recv, 0)]
        self.mock_sub.assert_has_calls(calls)


class TestMQTTGatewayCustomPrefix(TestCase):
    """Test the MQTT Gateway with custom topic prefix."""

    def setUp(self):
        """Set up test."""
        self.mock_pub = mock.Mock()
        self.mock_sub = mock.Mock()
        self.gateway = None

    def _setup(self, in_prefix, out_prefix):
        """Set up gateway."""
        self.gateway = MQTTGateway(
            self.mock_pub, self.mock_sub, in_prefix=in_prefix,
            out_prefix=out_prefix)

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = Sensor(sensorid)
        return self.gateway.sensors[sensorid]

    def test_nested_prefix(self):
        """Test recv method with nested topic prefix."""
        self._setup('test/test-in', 'test/test-out')
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.children[1].values[self.gateway.const.SetReq.V_HUM] = '20'
        self.gateway.recv('test/test-in/1/1/2/0/1', '', 0)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;1;1;0;1;20\n')
        self.gateway.recv('test/test-in/1/1/2/0/1', '', 1)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;1;1;1;1;20\n')


if __name__ == '__main__':
    main()
