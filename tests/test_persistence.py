"""Test persistence."""
import json
import os
import tempfile
from collections import deque
from unittest import TestCase, mock

from mysensors import Gateway
from mysensors.sensor import ChildSensor, Sensor
from mysensors.persistence import MySensorsJSONEncoder, Persistence


class TestPersistence(TestCase):
    """Test the Persistence logic."""

    def setUp(self):
        """Set up gateway."""
        self.gateway = Gateway()

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = Sensor(sensorid)
        return self.gateway.sensors[sensorid]

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
            persistence_file = os.path.join(temp_dir, filename)
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            self.gateway.persistence.save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway.persistence.safe_load_sensors()
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
            self.gateway.persistence.save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway.persistence.safe_load_sensors()
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
            persistence_file = os.path.join(temp_dir, 'file.bad')
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            with self.assertRaises(Exception):
                self.gateway.persistence.save_sensors()

    def test_json_no_files(self):
        """Test json persistence with no files existing."""
        self.assertFalse(self.gateway.sensors)
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_file = os.path.join(temp_dir, 'file.json')
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            self.gateway.persistence.safe_load_sensors()
        self.assertFalse(self.gateway.sensors)

    def _test_empty_files(self, filename):
        """Test persistence with empty files."""
        self.assertFalse(self.gateway.sensors)
        with tempfile.TemporaryDirectory() as temp_dir:
            persistence_file = os.path.join(temp_dir, filename)
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            persistence = self.gateway.persistence
            with open(persistence_file, 'w') as file_handle:
                file_handle.write('')
            with open(persistence.persistence_bak, 'w') as file_handle:
                file_handle.write('')
            self.gateway.persistence.safe_load_sensors()
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
            persistence_file = os.path.join(temp_dir, 'file.json')
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            self.gateway.persistence.save_sensors()
            del self.gateway.sensors[1]
            os.rename(
                persistence_file, self.gateway.persistence.persistence_bak)
            with open(persistence_file, 'w') as json_file:
                json_file.write('')
            self.gateway.persistence.safe_load_sensors()
        self.assertIn(1, self.gateway.sensors)

    @mock.patch('mysensors.persistence.Persistence.safe_load_sensors')
    def test_persistence_at_init(self, mock_load_sensors):
        """Test call to load persistence_file at init of Gateway."""
        self.gateway = Gateway(persistence=True)
        assert mock_load_sensors.call_count == 1

    def save_json_upgrade(self, filename):
        """Save sensors to json file.

        Only used for testing upgrade with missing attributes.
        """
        with open(filename, 'w') as file_handle:
            json.dump(
                self.gateway.sensors, file_handle,
                cls=MySensorsJSONEncoderTestUpgrade)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    @mock.patch('mysensors.persistence.Persistence._save_json')
    def _test_persistence_upgrade(self, filename, mock_save_json):
        """Test that all attributes are present after persistence upgrade."""
        mock_save_json.side_effect = self.save_json_upgrade
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
            persistence_file = os.path.join(temp_dir, filename)
            self.gateway.persistence = Persistence(
                self.gateway.sensors, persistence_file)
            self.gateway.persistence.save_sensors()
            del self.gateway.sensors[1]
            self.assertNotIn(1, self.gateway.sensors)
            self.gateway.persistence.safe_load_sensors()
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

    @mock.patch('mysensors.persistence.threading.Timer')
    @mock.patch('mysensors.persistence.Persistence.save_sensors')
    def test_schedule_save_sensors(self, mock_save, mock_timer_class):
        """Test schedule save sensors."""
        mock_timer = mock.MagicMock()
        mock_timer_class.return_value = mock_timer
        self.gateway.persistence = Persistence(self.gateway.sensors)
        self.gateway.persistence.schedule_save_sensors()
        assert mock_save.call_count == 1
        assert mock_timer.start.call_count == 1


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
