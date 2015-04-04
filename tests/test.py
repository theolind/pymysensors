import unittest
from unittest.mock import patch

import mysensors.mysensors as my
from mysensors.const import MessageType, Internal, Presentation

class TestGateway(unittest.TestCase):
    """ Test the Gateway logic function """

    def setUp(self):
        self.gw = my.Gateway()

    def _add_sensor(self, sensorid):
        self.gw.sensors[sensorid] = my.Sensor(sensorid)
        return self.gw.sensors[sensorid]

    def test_non_presented_sensor(self):
        self.gw.logic("1;0;1;0;23;43\n")
        self.assertNotIn(1, self.gw.sensors)

        self.gw.logic("1;1;1;0;1;75\n")
        self.assertNotIn(1, self.gw.sensors)

        self.gw.logic("1;255;3;0;0;79\n")
        self.assertNotIn(1, self.gw.sensors)

    def test_internal_id_request(self):
        ret = self.gw.logic("255;255;3;0;3;\n")
        self.assertEqual(ret.encode(), "255;255;3;0;4;1\n")
        self.assertIn(1, self.gw.sensors)

    def test_presenation_arduino_node(self):
        sensor = self._add_sensor(1)
        self.gw.logic("1;255;0;0;17;1.4.1\n")
        self.assertEqual(sensor.type, Presentation.S_ARDUINO_NODE)

    def test_internal_config(self):
        # metric
        ret = self.gw.logic("1;255;3;0;6;0\n")
        self.assertEqual(ret.encode(), "1;255;3;0;6;M\n")
        # imperial
        self.gw.metric = False
        ret = self.gw.logic("1;255;3;0;6;0\n")
        self.assertEqual(ret.encode(), "1;255;3;0;6;I\n")

    def test_internal_time(self):
        sensor = self._add_sensor(1)
        with patch('mysensors.mysensors.time') as mock_time:
            mock_time.time.return_value = 123456789
            ret = self.gw.logic("1;255;3;0;1;\n")
            self.assertEqual(ret.encode(), "1;255;3;0;1;123456789\n")

    def test_internal_sketch_name(self):
        sensor = self._add_sensor(1)
        self.gw.logic("1;255;3;0;11;lighthum demo sens\n")
        self.assertEqual(sensor.sketch_name, "lighthum demo sens")

    def test_internal_sketch_version(self):
        sensor = self._add_sensor(1)
        self.gw.logic("1;255;3;0;12;1.0\n")
        self.assertEqual(sensor.sketch_version, "1.0")

    def test_presenation_light_level_sensor(self):
        sensor = self._add_sensor(1)
        self.gw.logic("1;0;0;0;16;1.4.1\n")
        self.assertIn(0, sensor.children)
        self.assertEqual(sensor.children[0].type, Presentation.S_LIGHT_LEVEL)

    def test_presentation_humidity_sensor(self):
        sensor = self._add_sensor(1)
        self.gw.logic("1;0;0;0;7;1.4.1\n")
        self.assertEqual(0 in sensor.children, True)
        self.assertEqual(sensor.children[0].type, Presentation.S_HUM)

    def test_set_light_level(self):
        sensor = self._add_sensor(1)
        sensor.children[0] = my.ChildSensor(0, Presentation.S_LIGHT_LEVEL)
        self.gw.logic("1;0;1;0;23;43\n")
        self.assertEqual(sensor.children[0].value, '43')

    def test_humidity_level(self):
        sensor = self._add_sensor(1)
        sensor.children[1] = my.ChildSensor(1, Presentation.S_HUM)
        self.gw.logic("1;1;1;0;1;75\n")
        self.assertEqual(sensor.children[1].value, '75')

    def test_battery_level(self):
        sensor = self._add_sensor(1)
        self.gw.logic("1;255;3;0;0;79\n")
        self.assertEqual(sensor.battery_level, 79)


class TestMessage(unittest.TestCase):
    """ Test the Message class and it's encode/decode functions """

    def test_encode(self):
        m = my.Message()
        m.node_id = 255
        m.child_id = 255
        m.type = MessageType.internal
        m.sub_type = Internal.I_BATTERY_LEVEL
        m.ack = 0
        m.payload = 57

        cmd = m.encode()
        self.assertEqual(cmd, "255;255;3;0;0;57\n")

    def test_decode(self):
        m = my.Message("255;255;3;0;0;57\n")
        self.assertEqual(m.node_id, 255)
        self.assertEqual(m.child_id, 255)
        self.assertEqual(m.type, MessageType.internal)
        self.assertEqual(m.sub_type, Internal.I_BATTERY_LEVEL)
        self.assertEqual(m.ack, 0)
        self.assertEqual(m.payload, '57')

if __name__ == '__main__':
    unittest.main()
