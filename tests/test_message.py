"""Test mysensors messages."""
from unittest import TestCase

from mysensors import get_const, Message
from mysensors.const_14 import Internal, MessageType

SET_FIXTURES_14 = {
    'V_TEMP': '20.0',
    'V_HUM': '30',
    'V_LIGHT': '1',
    'V_DIMMER': '99',
    'V_PRESSURE': '101325',
    'V_FORECAST': 'stable',
    'V_RAIN': '30',
    'V_RAINRATE': '2',
    'V_WIND': '10',
    'V_GUST': '20',
    'V_DIRECTION': '270',
    'V_UV': '7',
    'V_WEIGHT': '10',
    'V_DISTANCE': '100',
    'V_IMPEDANCE': '10',
    'V_ARMED': '1',
    'V_TRIPPED': '1',
    'V_WATT': '1000',
    'V_KWH': '20',
    'V_SCENE_ON': 'scene_3',
    'V_SCENE_OFF': 'scene_4',
    'V_HEATER': 'AutoChangeOver',
    'V_HEATER_SW': '1',
    'V_LIGHT_LEVEL': '99',
    'V_VAR1': 'test1',
    'V_VAR2': 'test2',
    'V_VAR3': 'test3',
    'V_VAR4': 'test4',
    'V_VAR5': 'test5',
    'V_UP': '',
    'V_DOWN': '',
    'V_STOP': '',
    'V_IR_SEND': 'code',
    'V_IR_RECEIVE': 'code',
    'V_FLOW': '1.5',
    'V_VOLUME': '3.0',
    'V_LOCK_STATUS': '1',
    'V_DUST_LEVEL': '80',
    'V_VOLTAGE': '3.3',
    'V_CURRENT': '1.2',
}

SET_FIXTURES_15 = dict(SET_FIXTURES_14)
SET_FIXTURES_15.update({
    'V_STATUS': '1',
    'V_PERCENTAGE': '99',
    'V_HVAC_FLOW_STATE': 'AutoChangeOver',
    'V_HVAC_SPEED': 'Auto',
    'V_LEVEL': '89',
    'V_RGB': 'ffffff',
    'V_RGBW': 'ffffffff',
    'V_ID': '1',
    'V_UNIT_PREFIX': 'mV',
    'V_HVAC_SETPOINT_COOL': '24.0',
    'V_HVAC_SETPOINT_HEAT': '20.0',
    'V_HVAC_FLOW_MODE': 'Auto',
})
SET_FIXTURES_15.pop('V_HEATER')
SET_FIXTURES_15.pop('V_HEATER_SW')

SET_FIXTURES_20 = dict(SET_FIXTURES_15)
SET_FIXTURES_20.update({
    'V_TEXT': 'test text',
    'V_CUSTOM': 'test custom',
    'V_POSITION': '10.0,10.0,10.0',
    'V_IR_RECORD': 'code_id_to_store',
    'V_PH': '7.0',
    'V_ORP': '300',
    'V_EC': '5.5',
    'V_VAR': '100',
    'V_VA': '500',
    'V_POWER_FACTOR': '0.9',
})

INTERNAL_FIXTURES_14 = {
    'I_BATTERY_LEVEL': '99',
    'I_TIME': '1500000000',
    'I_VERSION': '1.4.1',
    'I_ID_REQUEST': '',
    'I_ID_RESPONSE': '254',
    'I_INCLUSION_MODE': '1',
    'I_CONFIG': 'M',
    'I_FIND_PARENT': '',
    'I_FIND_PARENT_RESPONSE': '254',
    'I_LOG_MESSAGE': 'test log message',
    'I_CHILDREN': 'C',  # clear routing data for the node
    'I_SKETCH_NAME': 'test sketch name',
    'I_SKETCH_VERSION': '1.0.0',
    'I_REBOOT': '',
    'I_GATEWAY_READY': 'Gateway startup complete.',
}

INTERNAL_FIXTURES_15 = dict(INTERNAL_FIXTURES_14)
INTERNAL_FIXTURES_15.update({
    'I_REQUEST_SIGNING': 'test signing request',
    'I_GET_NONCE': 'test get nonce',
    'I_GET_NONCE_RESPONSE': 'test get nonce response',
})

INTERNAL_FIXTURES_20 = dict(INTERNAL_FIXTURES_15)
INTERNAL_FIXTURES_20.update({
    'I_HEARTBEAT': '',
    'I_PRESENTATION': '',
    'I_DISCOVER': '',
    'I_DISCOVER_RESPONSE': '254',
    'I_HEARTBEAT_RESPONSE': '123465',
    'I_LOCKED': 'TMFV',
    'I_PING': '123456',
    'I_PONG': '123456',
    'I_REGISTRATION_REQUEST': '2.0.0',
    'I_REGISTRATION_RESPONSE': '1',
    'I_DEBUG': 'test debug',
})


class TestMessage(TestCase):
    """Test the Message class and it's encode/decode functions."""

    def test_encode(self):
        """Test encode of message."""
        msg = Message()
        cmd = msg.encode()
        self.assertEqual(cmd, '0;0;0;0;0;\n')

        msg.node_id = 1
        msg.child_id = 255
        msg.type = MessageType.internal
        msg.sub_type = Internal.I_BATTERY_LEVEL
        msg.ack = 0
        msg.payload = 57

        cmd = msg.encode()
        self.assertEqual(cmd, '1;255;3;0;0;57\n')

    def test_encode_bad_message(self):
        """Test encode of bad message."""
        msg = Message()
        msg.sub_type = 'bad'
        cmd = msg.encode()
        self.assertEqual(cmd, None)

    def test_decode(self):
        """Test decode of message."""
        msg = Message('1;255;3;0;0;57\n')
        self.assertEqual(msg.node_id, 1)
        self.assertEqual(msg.child_id, 255)
        self.assertEqual(msg.type, MessageType.internal)
        self.assertEqual(msg.sub_type, Internal.I_BATTERY_LEVEL)
        self.assertEqual(msg.ack, 0)
        self.assertEqual(msg.payload, '57')

    def test_decode_bad_message(self):
        """Test decode of bad message."""
        with self.assertRaises(ValueError):
            Message('bad;bad;bad;bad;bad;bad\n')


def test_validate_set():
    """Test Set messages."""
    versions = [
        ('1.4', SET_FIXTURES_14), ('1.5', SET_FIXTURES_15),
        ('2.0', SET_FIXTURES_20)]
    for protocol_version, fixture in versions:
        const = get_const(protocol_version)
        for name, payload in fixture.items():
            sub_type = const.SetReq[name]
            msg = Message('1;0;1;0;{};{}\n'.format(sub_type, payload))
            valid = msg.validate(protocol_version)
            assert valid == {
                'node_id': 1, 'child_id': 0, 'type': 1, 'ack': 0,
                'sub_type': sub_type, 'payload': payload}


def test_validate_internal():
    """Test Internal messages."""
    versions = [
        ('1.4', INTERNAL_FIXTURES_14), ('1.5', INTERNAL_FIXTURES_15),
        ('2.0', INTERNAL_FIXTURES_20)]
    for protocol_version, fixture in versions:
        const = get_const(protocol_version)
        for name, payload in fixture.items():
            sub_type = const.Internal[name]
            msg = Message('1;255;3;0;{};{}\n'.format(sub_type, payload))
            valid = msg.validate(protocol_version)
            assert valid == {
                'node_id': 1, 'child_id': 255, 'type': 3, 'ack': 0,
                'sub_type': sub_type, 'payload': payload}
