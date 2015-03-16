import unittest
import mysensors

""" Test the Gateway logic function """
class TestGateway(unittest.TestCase):
    def test_good_logic(self):
        # test unknown sensor
        gw = mysensors.Gateway()

        # a non presented sensor sends some values
        gw.logic("1;0;1;0;23;43\n")
        gw.logic("1;1;1;0;1;75\n")


        # test with presentation and id request
        gw = mysensors.Gateway()

        #internal id request
        ret = gw.logic("255;255;3;0;3;\n")
        self.assertEqual(ret.encode(), "255;255;3;0;4;1\n")
        self.assertEqual(1 in gw.sensors, True)

        sensor = gw.sensors[1]

        #presentation arduino node
        gw.logic("1;255;0;0;17;1.4.1\n")
        self.assertEqual(sensor.type, 'S_ARDUINO_NODE')

        #internal config
        ret = gw.logic("1;255;3;0;6;0\n")
        self.assertEqual(ret.encode(), "1;255;3;0;6;M\n")

        #internal sketch name
        gw.logic("1;255;3;0;11;lighthum demo sens\n")
        self.assertEqual(sensor.sketch_name, "lighthum demo sens")

        #internal sketch version
        gw.logic("1;255;3;0;12;1.0\n")
        self.assertEqual(sensor.sketch_version, "1.0")

        #presentation light level sensor
        gw.logic("1;0;0;0;16;1.4.1\n")
        self.assertEqual(0 in sensor.children, True)
        self.assertEqual(sensor.children[0].type, "S_LIGHT_LEVEL")

        #presentation humidity sensor
        gw.logic("1;1;0;0;7;1.4.1\n")
        self.assertEqual(1 in sensor.children, True)
        self.assertEqual(sensor.children[1].type, "S_HUM")

        #set light level
        gw.logic("1;0;1;0;23;43\n")
        self.assertEqual(sensor.children[0].value, '43')

        #set humidity level
        gw.logic("1;1;1;0;1;75\n")
        self.assertEqual(sensor.children[1].value, '75')


""" Test the Message class and it's encode/decode functions """
class TestMessage(unittest.TestCase):
    def test_encode(self):
        m = mysensors.Message()
        m.node_id = 255
        m.child_id = 255
        m.type = 'internal'
        m.sub_type = 'I_BATTERY_LEVEL'
        m.ack = 0
        m.payload = 57

        cmd = m.encode()
        self.assertEqual(cmd, "255;255;3;0;0;57\n")

    def test_decode(self):
        m = mysensors.Message("255;255;3;0;0;57\n")
        self.assertEqual(m.node_id, 255)
        self.assertEqual(m.child_id, 255)
        self.assertEqual(m.type, 'internal')
        self.assertEqual(m.sub_type, 'I_BATTERY_LEVEL')
        self.assertEqual(m.ack, 0)
        self.assertEqual(m.payload, '57')

if __name__ == '__main__':
    unittest.main()
