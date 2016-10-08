"""Test mysensors MQTT gateway with unittest."""
import time
from unittest import TestCase, main, mock

import mysensors.mysensors as my


class TestMQTTGateway(TestCase):
    """Test the MQTT Gateway."""

    def setUp(self):
        """Set up gateway."""
        self.mock_pub = mock.Mock()
        self.mock_sub = mock.Mock()
        self.gateway = my.MQTTGateway(self.mock_pub, self.mock_sub)

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = my.Sensor(sensorid)
        return self.gateway.sensors[sensorid]

    def test_send(self):
        """Test send method. """
        self.gateway.send('1;1;1;0;1;20\n')
        self.mock_pub.assert_called_with('/1/1/1/0/1', '20', 0, True)

    def test_send_empty_string(self):
        """Test send method with empty string. """
        self.gateway.send('')
        self.assertFalse(self.mock_pub.called)

    def test_send_error(self):
        """Test send method with error on publish. """
        self.mock_pub.side_effect = ValueError(
            'Publish topic cannot contain wildcards.')
        with self.assertLogs(level='ERROR') as test_handle:
            self.gateway.send('1;1;1;0;1;20\n')
            self.mock_pub.assert_called_with('/1/1/1/0/1', '20', 0, True)
            self.assertEqual(
                # only check first line of error log
                test_handle.output[0].split('\n', 1)[0],
                'ERROR:mysensors.mysensors:Publish to /1/1/1/0/1 failed: '
                'Publish topic cannot contain wildcards.')

    def test_recv(self):
        """Test recv method. """
        sensor = self._add_sensor(1)
        sensor.children[1] = my.ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.set_child_value(1, self.gateway.const.SetReq.V_HUM, 20)
        self.gateway.recv('/1/1/2/0/1', '', 0)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;1;1;0;1;20\n')
        self.gateway.recv('/1/1/2/0/1', '', 1)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;1;1;1;1;20\n')

    def test_recv_wrong_prefix(self):
        """Test recv method with wrong topic prefix. """
        sensor = self._add_sensor(1)
        sensor.children[1] = my.ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        sensor.set_child_value(1, self.gateway.const.SetReq.V_HUM, 20)
        self.gateway.recv('wrong/1/1/2/0/1', '', 0)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)

    def test_presentation(self):
        """Test handle presentation message."""
        self._add_sensor(1)
        self.gateway.logic('1;1;0;0;7;Humidity Sensor\n')
        calls = [
            mock.call('/1/1/1/+/+', self.gateway.recv, 0),
            mock.call('/1/1/2/+/+', self.gateway.recv, 0)]
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
                'ERROR:mysensors.mysensors:Subscribe to /1/1/1/+/+ failed: '
                'No topic specified, or incorrect topic type.')

    def test_start_stop_gateway(self):
        """Test start and stop of MQTT gateway."""
        self.assertFalse(self.gateway.is_alive())
        self.gateway.start()
        self.assertTrue(self.gateway.is_alive())
        calls = [
            mock.call('/+/+/0/+/+', self.gateway.recv, 0),
            mock.call('/+/+/3/+/+', self.gateway.recv, 0)]
        self.mock_sub.assert_has_calls(calls)
        self.gateway.stop()
        time.sleep(0.05)
        self.assertFalse(self.gateway.is_alive())


if __name__ == '__main__':
    main()
