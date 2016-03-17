"""Test mysensors with unittest."""
import unittest
from unittest.mock import patch

import mysensors.mysensors as my
from mysensors.const_14 import MessageType, Internal, Presentation, SetReq


class TestGateway(unittest.TestCase):
    """Test the Gateway logic function."""

    def setUp(self):
        """Setup gateway."""
        self.gateway = my.Gateway()

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = my.Sensor(sensorid)
        return self.gateway.sensors[sensorid]

    def test_logic_bad_message(self):
        """Test decode of bad message in logic method."""
        self.assertEqual(self.gateway.logic('bad;bad;bad;bad;bad;bad\n'), None)

    def test_non_presented_sensor(self):
        """Test non presented sensor node."""
        self.gateway.logic('1;0;1;0;23;43\n')
        self.assertNotIn(1, self.gateway.sensors)

        self.gateway.logic('1;1;1;0;1;75\n')
        self.assertNotIn(1, self.gateway.sensors)

        self.gateway.logic('1;255;3;0;0;79\n')
        self.assertNotIn(1, self.gateway.sensors)

    def test_internal_id_request(self):
        """Test internal node id request."""
        ret = self.gateway.logic('255;255;3;0;3;\n')
        self.assertEqual(ret.encode(), '255;255;3;0;4;1\n')
        self.assertIn(1, self.gateway.sensors)

    def test_presentation_arduino_node(self):
        """Test presentation of sensor node."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;255;0;0;17;1.4.1\n')
        self.assertEqual(sensor.type, Presentation.S_ARDUINO_NODE)
        self.assertEqual(sensor.protocol_version, '1.4.1')

    def test_internal_config(self):
        """Test internal config request, metric or imperial."""
        # metric
        ret = self.gateway.logic('1;255;3;0;6;0\n')
        self.assertEqual(ret.encode(), '1;255;3;0;6;M\n')
        # imperial
        self.gateway.metric = False
        ret = self.gateway.logic('1;255;3;0;6;0\n')
        self.assertEqual(ret.encode(), '1;255;3;0;6;I\n')

    def test_internal_time(self):
        """Test internal time request."""
        self._add_sensor(1)
        with patch('mysensors.mysensors.time') as mock_time:
            mock_time.time.return_value = 123456789
            ret = self.gateway.logic('1;255;3;0;1;\n')
            self.assertEqual(ret.encode(), '1;255;3;0;1;123456789\n')

    def test_internal_sketch_name(self):
        """Test internal receive of sketch name."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;255;3;0;11;lighthum demo sens\n')
        self.assertEqual(sensor.sketch_name, 'lighthum demo sens')

    def test_internal_sketch_version(self):
        """Test internal receive of sketch version."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;255;3;0;12;1.0\n')
        self.assertEqual(sensor.sketch_version, '1.0')

    def test_present_light_level_sensor(self):
        """Test presentation of a light level sensor."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;0;0;0;16;\n')
        self.assertIn(0, sensor.children)
        self.assertEqual(sensor.children[0].type, Presentation.S_LIGHT_LEVEL)

    def test_present_humidity_sensor(self):
        """Test presentation of a humidity sensor."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;0;0;0;7;\n')
        self.assertEqual(0 in sensor.children, True)
        self.assertEqual(sensor.children[0].type, Presentation.S_HUM)

    def test_set_light_level(self):
        """Test set of light level."""
        sensor = self._add_sensor(1)
        sensor.children[0] = my.ChildSensor(0, Presentation.S_LIGHT_LEVEL)
        self.gateway.logic('1;0;1;0;23;43\n')
        self.assertEqual(sensor.children[0].values[SetReq.V_LIGHT_LEVEL], '43')

    def test_set_humidity_level(self):
        """Test set humidity level."""
        sensor = self._add_sensor(1)
        sensor.children[1] = my.ChildSensor(1, Presentation.S_HUM)
        self.gateway.logic('1;1;1;0;1;75\n')
        self.assertEqual(sensor.children[1].values[SetReq.V_HUM], '75')

    def test_battery_level(self):
        """Test internal receive of battery level."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;255;3;0;0;79\n')
        self.assertEqual(sensor.battery_level, 79)

    def test_req(self):
        """Test req message in case where value exists."""
        sensor = self._add_sensor(1)
        sensor.children[1] = my.ChildSensor(1, Presentation.S_POWER)
        sensor.set_child_value(1, SetReq.V_VAR1, 42)
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret.encode(), '1;1;1;0;24;42\n')

    def test_req_novalue(self):
        """Test req message for sensor with no value."""
        sensor = self._add_sensor(1)
        sensor.children[1] = my.ChildSensor(1, Presentation.S_POWER)
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret, None)

    def test_req_notasensor(self):
        """Test req message for non-existent sensor."""
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret, None)

    def test_persistence(self):
        """Test persistence using pickle."""
        self._add_sensor(1)
        self.gateway.sensors[1].type = Presentation.S_ARDUINO_NODE
        self.gateway.sensors[1].sketch_name = 'testsketch'
        self.gateway.sensors[1].sketch_version = '1.0'
        self.gateway.sensors[1].battery_level = 78

        sensor = self.gateway.sensors[1]
        self.gateway.persistence_file = 'persistence.file.pickle'
        self.gateway._save_sensors()  # pylint: disable=protected-access
        del self.gateway.sensors[1]
        self.gateway._load_sensors()  # pylint: disable=protected-access
        self.assertEqual(
            self.gateway.sensors[1].sketch_name, sensor.sketch_name)
        self.assertEqual(self.gateway.sensors[1].sketch_version,
                         sensor.sketch_version)
        self.assertEqual(
            self.gateway.sensors[1].battery_level, sensor.battery_level)
        self.assertEqual(self.gateway.sensors[1].type, sensor.type)

    def test_json_persistence(self):
        """Test persistence using json."""
        sensor = self._add_sensor(1)
        sensor.children[0] = my.ChildSensor(0, Presentation.S_LIGHT_LEVEL)
        self.gateway.sensors[1].type = Presentation.S_ARDUINO_NODE
        self.gateway.sensors[1].sketch_name = 'testsketch'
        self.gateway.sensors[1].sketch_version = '1.0'
        self.gateway.sensors[1].battery_level = 78
        self.gateway.sensors[1].protocol_version = '1.4.1'

        sensor = self.gateway.sensors[1]
        self.gateway.persistence_file = 'persistence.file.json'
        self.gateway._save_sensors()  # pylint: disable=protected-access
        del self.gateway.sensors[1]
        self.gateway._load_sensors()  # pylint: disable=protected-access
        self.assertEqual(
            self.gateway.sensors[1].sketch_name, sensor.sketch_name)
        self.assertEqual(self.gateway.sensors[1].sketch_version,
                         sensor.sketch_version)
        self.assertEqual(
            self.gateway.sensors[1].battery_level, sensor.battery_level)
        self.assertEqual(self.gateway.sensors[1].type, sensor.type)
        self.assertEqual(self.gateway.sensors[1].protocol_version,
                         sensor.protocol_version)


class TestMessage(unittest.TestCase):
    """Test the Message class and it's encode/decode functions."""

    def test_encode(self):
        """Test encode of message."""
        msg = my.Message()
        cmd = msg.encode()
        self.assertEqual(cmd, '0;0;0;0;0;\n')

        msg.node_id = 255
        msg.child_id = 255
        msg.type = MessageType.internal
        msg.sub_type = Internal.I_BATTERY_LEVEL
        msg.ack = 0
        msg.payload = 57

        cmd = msg.encode()
        self.assertEqual(cmd, '255;255;3;0;0;57\n')

    def test_encode_bad_message(self):
        """Test encode of bad message."""
        msg = my.Message()
        msg.sub_type = 'bad'
        cmd = msg.encode()
        self.assertEqual(cmd, None)

    def test_decode(self):
        """Test decode of message."""
        msg = my.Message('255;255;3;0;0;57\n')
        self.assertEqual(msg.node_id, 255)
        self.assertEqual(msg.child_id, 255)
        self.assertEqual(msg.type, MessageType.internal)
        self.assertEqual(msg.sub_type, Internal.I_BATTERY_LEVEL)
        self.assertEqual(msg.ack, 0)
        self.assertEqual(msg.payload, '57')

    def test_decode_bad_message(self):
        """Test decode of bad message."""
        with self.assertRaises(ValueError):
            my.Message('bad;bad;bad;bad;bad;bad\n')

if __name__ == '__main__':
    unittest.main()
