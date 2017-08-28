"""Test mysensors with unittest."""
import json
import os
import tempfile
import time
from collections import deque
from unittest import TestCase, main, mock

import voluptuous as vol

from mysensors import (ChildSensor, Gateway, Message, MySensorsJSONEncoder,
                       Sensor)


class TestGateway(TestCase):
    """Test the Gateway logic function."""

    # pylint: disable=too-many-public-methods

    def setUp(self):
        """Set up gateway."""
        self.gateway = Gateway()

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = Sensor(sensorid)
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

    def test_present_to_non_sensor(self):
        """Test presenting a child to a non presented sensor node."""
        ret = self.gateway.logic('1;1;0;0;0;\n')
        self.assertNotIn(1, self.gateway.sensors)
        self.assertEqual(ret, None)

    def test_internal_id_request(self):
        """Test internal node id request."""
        ret = self.gateway.logic('255;255;3;0;3;\n')
        self.assertEqual(ret, '255;255;3;0;4;1\n')
        self.assertIn(1, self.gateway.sensors)
        ret = self.gateway.logic('255;255;3;0;3;\n')
        self.assertEqual(ret, '255;255;3;0;4;2\n')
        self.assertIn(2, self.gateway.sensors)
        self._add_sensor(254)
        self.assertIn(254, self.gateway.sensors)
        ret = self.gateway.logic('255;255;3;0;3;\n')
        self.assertEqual(ret, None)
        self.assertNotIn(255, self.gateway.sensors)

    def test_id_request_with_node_zero(self):
        """Test internal node id request with node 0 already assigned."""
        self._add_sensor(0)
        ret = self.gateway.logic('255;255;3;0;3;\n')
        self.assertEqual(ret, '255;255;3;0;4;1\n')
        self.assertIn(1, self.gateway.sensors)

    def test_presentation_arduino_node(self):
        """Test presentation of sensor node."""
        self.gateway.logic('1;255;0;0;17;1.4.1\n')
        self.assertEqual(
            self.gateway.sensors[1].type,
            self.gateway.const.Presentation.S_ARDUINO_NODE)
        self.assertEqual(self.gateway.sensors[1].protocol_version, '1.4.1')

    def test_internal_config(self):
        """Test internal config request, metric or imperial."""
        # metric
        ret = self.gateway.logic('1;255;3;0;6;0\n')
        self.assertEqual(ret, '1;255;3;0;6;M\n')
        # imperial
        self.gateway.metric = False
        ret = self.gateway.logic('1;255;3;0;6;0\n')
        self.assertEqual(ret, '1;255;3;0;6;I\n')

    def test_internal_time(self):
        """Test internal time request."""
        self._add_sensor(1)
        with mock.patch('mysensors.time') as mock_time:
            mock_time.localtime.return_value = time.gmtime(123456789)
            ret = self.gateway.logic('1;255;3;0;1;\n')
            self.assertEqual(ret, '1;255;3;0;1;123456789\n')

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

    def test_internal_log_message(self):
        """Test internal receive of log message."""
        payload = 'read: 1-1-0 s=0,c=1,t=1,pt=7,l=5,sg=0:22.0\n'
        data = '0;255;3;0;9;{}'.format(payload)
        with self.assertLogs(level='DEBUG') as test_handle:
            self.gateway.logic(data)
        self.assertEqual(
            test_handle.output,
            ['DEBUG:mysensors:n:0 c:255 t:3 s:9 p:{}'.format(
                payload[:-1])])

    def test_internal_gateway_ready(self):
        """Test internal receive gateway ready and send discover request."""
        payload = 'Gateway startup complete.\n'
        data = '0;255;3;0;14;{}'.format(payload)
        with self.assertLogs(level='INFO') as test_handle:
            ret = self.gateway.logic(data)
        self.assertEqual(
            test_handle.output,
            ['INFO:mysensors:n:0 c:255 t:3 s:14 p:{}'.format(
                payload[:-1])])
        self.assertEqual(ret, None)

    def test_present_light_level_sensor(self):
        """Test presentation of a light level sensor."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;0;0;0;16;\n')
        self.assertIn(0, sensor.children)
        self.assertEqual(sensor.children[0].type,
                         self.gateway.const.Presentation.S_LIGHT_LEVEL)

    def test_present_humidity_sensor(self):
        """Test presentation of a humidity sensor."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;0;0;0;7;\n')
        self.assertEqual(0 in sensor.children, True)
        self.assertEqual(sensor.children[0].type,
                         self.gateway.const.Presentation.S_HUM)

    def test_present_same_child(self):
        """Test presentation of the same child id again."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;0;0;0;16;\n')
        self.assertIn(0, sensor.children)
        self.assertEqual(sensor.children[0].type,
                         self.gateway.const.Presentation.S_LIGHT_LEVEL)
        self.gateway.logic('1;0;0;0;7;\n')
        self.assertIn(0, sensor.children)
        self.assertEqual(sensor.children[0].type,
                         self.gateway.const.Presentation.S_LIGHT_LEVEL)

    def test_set_light_level(self):
        """Test set of light level."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        self.gateway.logic('1;0;1;0;23;43\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_LIGHT_LEVEL],
            '43')

    def test_set_humidity_level(self):
        """Test set humidity level."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_HUM)
        self.gateway.logic('1;1;1;0;1;75\n')
        self.assertEqual(
            sensor.children[1].values[self.gateway.const.SetReq.V_HUM], '75')

    def test_battery_level(self):
        """Test internal receive of battery level."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;255;3;0;0;79\n')
        self.assertEqual(sensor.battery_level, 79)

    def test_bad_battery_level(self):
        """Test internal receive of bad battery level."""
        sensor = self._add_sensor(1)
        self.gateway.logic('1;255;3;0;0;-1\n')
        self.assertEqual(sensor.battery_level, 0)

    def test_req(self):
        """Test req message in case where value exists."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_POWER)
        sensor.set_child_value(1, self.gateway.const.SetReq.V_VAR1, 42)
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret, '1;1;1;0;24;42\n')

    def test_req_zerovalue(self):
        """Test req message in case where value exists but is zero."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_POWER)
        sensor.set_child_value(1, self.gateway.const.SetReq.V_VAR1, 0)
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret, '1;1;1;0;24;0\n')

    def test_req_novalue(self):
        """Test req message for sensor with no value."""
        sensor = self._add_sensor(1)
        sensor.children[1] = ChildSensor(
            1, self.gateway.const.Presentation.S_POWER)
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret, None)

    def test_req_notasensor(self):
        """Test req message for non-existent sensor."""
        ret = self.gateway.logic('1;1;2;0;24;\n')
        self.assertEqual(ret, None)

    def _test_persistence(self, filename):
        """Test persistence."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL, 'test')
        sensor.children[0].values[
            self.gateway.const.SetReq.V_LIGHT_LEVEL] = '43'
        self.gateway.sensors[
            1].type = self.gateway.const.Presentation.S_ARDUINO_NODE
        self.gateway.sensors[1].sketch_name = 'testsketch'
        self.gateway.sensors[1].sketch_version = '1.0'
        self.gateway.sensors[1].battery_level = 78
        self.gateway.sensors[1].protocol_version = '1.4.1'

        with tempfile.TemporaryDirectory() as temp_dir:
            self.gateway.persistence_file = os.path.join(temp_dir, filename)
            self.gateway.persistence_bak = os.path.join(
                temp_dir, '{}.bak'.format(filename))
            # pylint: disable=protected-access
            self.gateway._save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway._safe_load_sensors()
            self.assertEqual(
                self.gateway.sensors[1].sketch_name, sensor.sketch_name)
            self.assertEqual(self.gateway.sensors[1].sketch_version,
                             sensor.sketch_version)
            self.assertEqual(
                self.gateway.sensors[1].battery_level,
                sensor.battery_level)
            self.assertEqual(self.gateway.sensors[1].type, sensor.type)
            self.assertEqual(self.gateway.sensors[1].protocol_version,
                             sensor.protocol_version)
            self.assertEqual(
                self.gateway.sensors[1].children[0].id,
                sensor.children[0].id)
            self.assertEqual(
                self.gateway.sensors[1].children[0].type,
                sensor.children[0].type)
            self.assertEqual(
                self.gateway.sensors[1].children[0].description,
                sensor.children[0].description)
            self.assertEqual(
                self.gateway.sensors[1].children[0].values,
                sensor.children[0].values)
            self.gateway._save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway._safe_load_sensors()
            self.assertIn(1, self.gateway.sensors)

    def test_pickle_persistence(self):
        """Test persistence using pickle."""
        self._test_persistence('file.pickle')

    def test_json_persistence(self):
        """Test persistence using JSON."""
        self._test_persistence('file.json')

    def test_bad_file_name(self):
        """Test persistence with bad file name."""
        self._add_sensor(1)
        with tempfile.TemporaryDirectory() as temp_dir:
            self.gateway.persistence_file = os.path.join(temp_dir, 'file.bad')
            self.gateway.persistence_bak = os.path.join(
                temp_dir, 'file.bad.bak')
            with self.assertRaises(Exception):
                # pylint: disable=protected-access
                self.gateway._save_sensors()

    def test_json_no_files(self):
        """Test json persistence with no files existing."""
        self.assertFalse(self.gateway.sensors)
        with tempfile.TemporaryDirectory() as temp_dir:
            self.gateway.persistence_file = os.path.join(temp_dir, 'file.json')
            self.gateway.persistence_bak = os.path.join(
                temp_dir, 'file.json.bak')
            # pylint: disable=protected-access
            self.gateway._safe_load_sensors()
        self.assertFalse(self.gateway.sensors)

    def _test_empty_files(self, filename):
        """Test persistence with empty files."""
        self.assertFalse(self.gateway.sensors)
        with tempfile.TemporaryDirectory() as temp_dir:
            self.gateway.persistence_file = os.path.join(temp_dir, filename)
            self.gateway.persistence_bak = os.path.join(
                temp_dir, '{}.bak'.format(filename))
            with open(self.gateway.persistence_file, 'w') as file_handle:
                file_handle.write('')
            with open(self.gateway.persistence_bak, 'w') as file_handle:
                file_handle.write('')
            # pylint: disable=protected-access
            self.gateway._safe_load_sensors()
        self.assertFalse(self.gateway.sensors)

    def test_pickle_empty_files(self):
        """Test persistence with empty pickle files."""
        self._test_empty_files('file.pickle')

    def test_json_empty_files(self):
        """Test persistence with empty JSON files."""
        self._test_empty_files('file.json')

    def test_json_empty_file_good_bak(self):
        """Test json persistence with empty file but good backup."""
        self._add_sensor(1)
        self.assertIn(1, self.gateway.sensors)
        with tempfile.TemporaryDirectory() as temp_dir:
            self.gateway.persistence_file = os.path.join(temp_dir, 'file.json')
            self.gateway.persistence_bak = os.path.join(
                temp_dir, 'file.json.bak')
            # pylint: disable=protected-access
            self.gateway._save_sensors()
            del self.gateway.sensors[1]
            os.rename(
                self.gateway.persistence_file, self.gateway.persistence_bak)
            with open(self.gateway.persistence_file, 'w') as json_file:
                json_file.write('')
            # pylint: disable=protected-access
            self.gateway._safe_load_sensors()
        self.assertIn(1, self.gateway.sensors)

    @mock.patch('mysensors.mysensors.Gateway._safe_load_sensors')
    def test_persistence_at_init(self, mock_load_sensors):
        """Test call to load persistence_file at init of Gateway."""
        self.gateway = Gateway(persistence=True)
        assert mock_load_sensors.called

    def _save_json_upgrade(self, filename):
        """Save sensors to json file.

        Only used for testing upgrade with missing attributes.
        """
        with open(filename, 'w') as file_handle:
            json.dump(
                self.gateway.sensors, file_handle,
                cls=MySensorsJSONEncoderTestUpgrade)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    @mock.patch('mysensors.mysensors.Gateway._save_json')
    def _test_persistence_upgrade(self, filename, mock_save_json):
        """Test that all attributes are present after persistence upgrade."""
        # pylint: disable=protected-access
        mock_save_json.side_effect = self._save_json_upgrade
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        del self.gateway.sensors[1].__dict__['new_state']
        self.assertNotIn('new_state', self.gateway.sensors[1].__dict__)
        del self.gateway.sensors[1].__dict__['queue']
        self.assertNotIn('queue', self.gateway.sensors[1].__dict__)
        del self.gateway.sensors[1].__dict__['reboot']
        self.assertNotIn('reboot', self.gateway.sensors[1].__dict__)
        del self.gateway.sensors[1].__dict__['_battery_level']
        self.assertNotIn('_battery_level', self.gateway.sensors[1].__dict__)
        self.gateway.sensors[1].__dict__['battery_level'] = 58
        del self.gateway.sensors[1].__dict__['_protocol_version']
        self.assertNotIn('_protocol_version', self.gateway.sensors[1].__dict__)
        self.gateway.sensors[1].__dict__[
            'protocol_version'] = self.gateway.protocol_version
        del self.gateway.sensors[1].children[0].__dict__['description']
        self.assertNotIn(
            'description', self.gateway.sensors[1].children[0].__dict__)
        with tempfile.TemporaryDirectory() as temp_dir:
            self.gateway.persistence_file = os.path.join(temp_dir, filename)
            self.gateway.persistence_bak = os.path.join(
                temp_dir, '{}.bak'.format(filename))
            self.gateway._save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway._safe_load_sensors()
            self.assertEqual(self.gateway.sensors[1].battery_level, 58)
            self.assertEqual(
                self.gateway.sensors[1].protocol_version,
                self.gateway.protocol_version)
            self.assertEqual(self.gateway.sensors[1].new_state, {})
            self.assertEqual(self.gateway.sensors[1].queue, deque())
            self.assertEqual(self.gateway.sensors[1].reboot, False)
            self.assertEqual(
                self.gateway.sensors[1].children[0].description, '')
            self.assertEqual(
                self.gateway.sensors[1].children[0].id,
                sensor.children[0].id)
            self.assertEqual(
                self.gateway.sensors[1].children[0].type,
                sensor.children[0].type)

    def test_pickle_upgrade(self):
        """Test that all attributes are present after pickle upgrade."""
        # pylint: disable=no-value-for-parameter
        self._test_persistence_upgrade('file.pickle')

    def test_json_upgrade(self):
        """Test that all attributes are present after JSON upgrade."""
        # pylint: disable=no-value-for-parameter
        self._test_persistence_upgrade('file.json')

    def _callback(self, message):
        self.gateway.test_callback_message = message

    @mock.patch('mysensors.mysensors.Gateway._save_sensors')
    def test_callback(self, mock_save_sensors):
        """Test gateway callback function."""
        self.gateway.event_callback = self._callback
        self.gateway.persistence = True
        self.gateway.test_callback_message = None
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        self.gateway.logic('1;0;1;0;23;43\n')
        self.assertIsNotNone(self.gateway.test_callback_message)
        self.assertEqual(self.gateway,
                         self.gateway.test_callback_message.gateway)
        self.assertEqual(1, self.gateway.test_callback_message.node_id)
        self.assertEqual(0, self.gateway.test_callback_message.child_id)
        self.assertEqual(1, self.gateway.test_callback_message.type)
        self.assertEqual(0, self.gateway.test_callback_message.ack)
        self.assertEqual(23, self.gateway.test_callback_message.sub_type)
        self.assertEqual('43', self.gateway.test_callback_message.payload)
        assert mock_save_sensors.called

    def test_callback_exception(self):
        """Test gateway callback with exception."""
        side_effect = ValueError('test')
        self.gateway = Gateway(event_callback=self._callback)
        with mock.patch.object(self.gateway, 'event_callback',
                               side_effect=side_effect) as mock_callback:
            with self.assertLogs(level='ERROR') as test_handle:
                msg = Message()
                msg.node_id = 1
                self.gateway.alert(msg)
            assert mock_callback.called
            self.assertEqual(
                # only check first line of error log
                test_handle.output[0].split('\n', 1)[0],
                'ERROR:mysensors:test')

    def test_set_and_reboot(self):
        """Test set message with reboot attribute true."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        sensor.reboot = True
        ret = self.gateway.logic('1;0;1;0;23;43\n')
        self.assertEqual(ret, '1;255;3;0;13;\n')

    def test_set_child_value(self):
        """Test Gateway method set_child_value."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT)
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, '1')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;0;1;0;2;1\n')
        # test integer value
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, 0)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;0;1;0;2;0\n')

    def test_set_child_value_no_sensor(self):
        """Test Gateway method set_child_value with no sensor."""
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, '1')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)

    def test_set_child_no_children(self):
        """Test Gateway method set_child_value without child in children."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT)
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, 1, children={})
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)

    def test_set_child_value_bad_type(self):
        """Test Gateway method set_child_value with bad type."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT)
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, 1, msg_type='one')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)

    def test_set_child_value_bad_ack(self):
        """Test Gateway method set_child_value with bad ack."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT)
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, 1, ack='one')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)

    def test_set_child_value_value_type(self):
        """Test Gateway method set_child_value with string value type."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT)
        self.gateway.set_child_value(1, 0, 2, 1)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;0;1;0;2;1\n')
        child_values = dict(sensor.children[0].values)
        self.gateway.set_child_value(1, 0, '2', 1)
        ret = self.gateway.handle_queue()
        self.assertEqual(child_values, sensor.children[0].values)
        self.assertEqual(ret, '1;0;1;0;2;1\n')

    def test_child_validate(self):
        """Test child validate method."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        sensor.children[0].values[
            self.gateway.const.SetReq.V_LIGHT_LEVEL] = '43'
        sensor.children[0].validate(self.gateway.protocol_version)
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_LIGHT_LEVEL],
            '43')
        sensor.children[0].values[self.gateway.const.SetReq.V_TRIPPED] = '1'
        with self.assertRaises(vol.Invalid):
            sensor.children[0].validate(self.gateway.protocol_version)

    def test_set_forecast(self):
        """Test set of V_FORECAST."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_BARO)
        self.gateway.logic('1;0;1;0;5;sunny\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_FORECAST],
            'sunny')
        self.gateway.logic('1;0;1;0;5;rainy\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_FORECAST],
            'rainy')

    def test_set_bad_battery_attribute(self):
        """Test set a bad battery_level attribute on a node."""
        sensor = self._add_sensor(1)
        sensor.battery_level = None
        self.assertEqual(sensor.battery_level, 0)


class TestGateway15(TestGateway):
    """Use protocol_version 1.5."""

    def setUp(self):
        """Set up gateway."""
        self.gateway = Gateway(protocol_version='1.5')

    def test_set_rgb(self):
        """Test set of V_RGB."""
        sensor = self._add_sensor(1)
        sensor.protocol_version = '1.5'
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_RGB_LIGHT)
        self.gateway.logic('1;0;1;0;40;ffffff\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_RGB],
            'ffffff')
        self.gateway.logic('1;0;1;0;40;ffffff00\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_RGB],
            'ffffff')
        self.gateway.logic('1;0;1;0;40;nothex\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_RGB],
            'ffffff')

    def test_set_rgbw(self):
        """Test set of V_RGBW."""
        sensor = self._add_sensor(1)
        sensor.protocol_version = '1.5'
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_RGBW_LIGHT)
        self.gateway.logic('1;0;1;0;41;ffffffff\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_RGBW],
            'ffffffff')
        self.gateway.logic('1;0;1;0;41;ffffffff00\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_RGBW],
            'ffffffff')
        self.gateway.logic('1;0;1;0;41;nothexxx\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_RGBW],
            'ffffffff')


class TestGateway20(TestGateway):
    """Use protocol_version 2.0."""

    def setUp(self):
        """Set up gateway."""
        self.gateway = Gateway(protocol_version='2.0')

    def test_non_presented_sensor(self):
        """Test non presented sensor node."""
        self.gateway.logic('1;0;1;0;23;43\n')
        self.assertNotIn(1, self.gateway.sensors)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

        self.gateway.logic('1;1;1;0;1;75\n')
        self.assertNotIn(1, self.gateway.sensors)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

        self.gateway.logic('1;255;3;0;0;79\n')
        self.assertNotIn(1, self.gateway.sensors)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

    def test_present_to_non_sensor(self):
        """Test presenting a child to a non presented sensor node."""
        ret = self.gateway.logic('1;1;0;0;0;\n')
        self.assertNotIn(1, self.gateway.sensors)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

    def test_non_presented_child(self):
        """Test non presented sensor child."""
        self._add_sensor(1)
        self.gateway.logic('1;0;1;0;23;43\n')
        self.assertNotIn(0, self.gateway.sensors[1].children)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

        self.gateway.logic('1;1;2;0;1;\n')
        self.assertNotIn(1, self.gateway.sensors[1].children)
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

    def test_set_child_value_no_sensor(self):
        """Test Gateway method set_child_value with no sensor."""
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT, '1')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

    def test_heartbeat(self):
        """Test heartbeat message."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        self.gateway.logic('1;0;1;0;23;43\n')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, None)
        # heartbeat
        self.gateway.logic('1;255;3;0;22;\n')
        ret = self.gateway.handle_queue()
        # nothing has changed
        self.assertEqual(ret, None)
        # change from controller side
        self.gateway.set_child_value(
            1, 0, self.gateway.const.SetReq.V_LIGHT_LEVEL, '57')
        ret = self.gateway.handle_queue()
        # no heartbeat
        self.assertEqual(ret, None)
        # heartbeat comes in
        self.gateway.logic('1;255;3;0;22;\n')
        ret = self.gateway.handle_queue()
        # instance responds with new values
        self.assertEqual(ret, '1;0;1;0;23;57\n')
        # request from node
        self.gateway.logic('1;0;2;0;23;\n')
        ret = self.gateway.handle_queue()
        # no heartbeat
        self.assertEqual(ret, None)
        # heartbeat
        self.gateway.logic('1;255;3;0;22;\n')
        ret = self.gateway.handle_queue()
        # instance responds to request with current value
        self.assertEqual(ret, '1;0;1;0;23;57\n')
        # heartbeat
        self.gateway.logic('1;255;3;0;22;\n')
        ret = self.gateway.handle_queue()
        # nothing has changed
        self.assertEqual(ret, None)

    def test_heartbeat_from_unknown(self):
        """Test heartbeat message from unknown node."""
        self.gateway.logic('1;255;3;0;22;\n')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

    def test_set_with_new_state(self):
        """Test set message with populated new_state."""
        sensor = self._add_sensor(1)
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_LIGHT_LEVEL)
        self.gateway.logic('1;0;1;0;23;43\n')
        self.gateway.logic('1;255;3;0;22;\n')
        self.gateway.logic('1;0;1;0;23;57\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_LIGHT_LEVEL],
            sensor.new_state[0].values[
                self.gateway.const.SetReq.V_LIGHT_LEVEL])

    def test_internal_gateway_ready(self):
        """Test internal receive gateway ready and send discover request."""
        payload = 'Gateway startup complete.\n'
        data = '0;255;3;0;14;{}'.format(payload)
        with self.assertLogs(level='INFO') as test_handle:
            ret = self.gateway.logic(data)
        self.assertEqual(
            test_handle.output,
            ['INFO:mysensors:n:0 c:255 t:3 s:14 p:{}'.format(
                payload[:-1])])
        self.assertEqual(ret, '255;255;3;0;20;\n')

    def test_discover_response_unknown(self):
        """Test internal receive discover response."""
        # Test sensor 1 unknown.
        self.gateway.logic('1;255;3;0;21;0')
        ret = self.gateway.handle_queue()
        self.assertEqual(ret, '1;255;3;0;19;\n')

    @mock.patch('mysensors.mysensors.Gateway.is_sensor')
    def test_discover_response_known(self, mock_is_sensor):
        """Test internal receive discover response."""
        # Test sensor 1 known.
        self._add_sensor(1)
        self.gateway.logic('1;255;3;0;21;0')
        assert mock_is_sensor.called

    def test_set_position(self):
        """Test set of V_POSITION."""
        sensor = self._add_sensor(1)
        sensor.protocol_version = '2.0'
        sensor.children[0] = ChildSensor(
            0, self.gateway.const.Presentation.S_GPS)
        self.gateway.logic('1;0;1;0;49;10.0,10.0,10.0\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_POSITION],
            '10.0,10.0,10.0')
        self.gateway.logic('1;0;1;0;49;bad,format\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_POSITION],
            '10.0,10.0,10.0')
        self.gateway.logic('1;0;1;0;41;bad,bad,bad\n')
        self.assertEqual(
            sensor.children[0].values[self.gateway.const.SetReq.V_POSITION],
            '10.0,10.0,10.0')


def test_gateway_bad_protocol():
    """Test initializing gateway with a bad protocol_version."""
    gateway = Gateway(protocol_version=None)
    assert gateway.protocol_version == '1.4'


def test_gateway_low_protocol():
    """Test initializing gateway with too low protocol_version."""
    gateway = Gateway(protocol_version='1.3')
    assert gateway.protocol_version == '1.4'


class MySensorsJSONEncoderTestUpgrade(MySensorsJSONEncoder):
    """JSON encoder used for testing upgrade with missing attributes."""

    def default(self, obj):  # pylint: disable=E0202
        """Serialize obj into JSON."""
        if isinstance(obj, Sensor):
            return obj.__dict__
        if isinstance(obj, ChildSensor):
            return {
                'id': obj.id,
                'type': obj.type,
                'values': obj.values,
            }
        return super().default(obj)


if __name__ == '__main__':
    main()
