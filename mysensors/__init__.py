"""Python implementation of MySensors API."""
import calendar
import json
import logging
import os
import pickle
import threading
import time
from collections import deque
from importlib import import_module
from queue import Queue

from .ota import OTAFirmware

_LOGGER = logging.getLogger(__name__)


class Gateway(object):
    """Base implementation for a MySensors Gateway."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, event_callback=None, persistence=False,
                 persistence_file='mysensors.pickle', protocol_version='1.4'):
        """Set up Gateway."""
        self.queue = Queue()
        self.lock = threading.Lock()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True  # if true - use metric, if false - use imperial
        self.persistence = persistence  # if true - save sensors to disk
        self.persistence_file = persistence_file  # path to persistence file
        self.persistence_bak = '{}.bak'.format(self.persistence_file)
        self.protocol_version = float(protocol_version)
        if 1.5 <= self.protocol_version < 2.0:
            _const = import_module('mysensors.const_15')
        elif self.protocol_version >= 2.0:
            _const = import_module('mysensors.const_20')
        else:
            _const = import_module('mysensors.const_14')
        self.const = _const
        self.ota = OTAFirmware(self.sensors, self.const)
        if persistence:
            self._safe_load_sensors()

    def _handle_presentation(self, msg):
        """Process a presentation message."""
        if msg.child_id == 255:
            # this is a presentation of the sensor platform
            sensorid = self.add_sensor(msg.node_id)
            if sensorid is None:
                return
            self.sensors[msg.node_id].type = msg.sub_type
            self.sensors[msg.node_id].protocol_version = msg.payload
            self.sensors[msg.node_id].reboot = False
            self.alert(msg)
            return msg
        else:
            # this is a presentation of a child sensor
            if not self.is_sensor(msg.node_id):
                _LOGGER.error('Node %s is unknown, will not add child %s.',
                              msg.node_id, msg.child_id)
                return
            child_id = self.sensors[msg.node_id].add_child_sensor(
                msg.child_id, msg.sub_type, msg.payload)
            if child_id is None:
                return
            self.alert(msg)
            return msg

    def _handle_set(self, msg):
        """Process a set message."""
        if not self.is_sensor(msg.node_id, msg.child_id):
            return
        self.sensors[msg.node_id].set_child_value(
            msg.child_id, msg.sub_type, msg.payload)
        if self.sensors[msg.node_id].new_state:
            self.sensors[msg.node_id].set_child_value(
                msg.child_id, msg.sub_type, msg.payload,
                children=self.sensors[msg.node_id].new_state)
        self.alert(msg)
        # Check if reboot is true
        if self.sensors[msg.node_id].reboot:
            return msg.modify(
                child_id=255, type=self.const.MessageType.internal, ack=0,
                sub_type=self.const.Internal.I_REBOOT, payload='')

    def _handle_req(self, msg):
        """Process a req message.

        This will return the value if it exists. If no value exists,
        nothing is returned.
        """
        if self.is_sensor(msg.node_id, msg.child_id):
            value = self.sensors[msg.node_id].children[
                msg.child_id].values.get(msg.sub_type)
            if value is not None:
                return msg.modify(
                    type=self.const.MessageType.set, payload=value)

    def _handle_heartbeat(self, msg):
        """Process a heartbeat message."""
        if not self.is_sensor(msg.node_id):
            return
        while self.sensors[msg.node_id].queue:
            self.fill_queue(str, (self.sensors[msg.node_id].queue.popleft(), ))
        for child in self.sensors[msg.node_id].children.values():
            new_child = self.sensors[msg.node_id].new_state.get(
                child.id, ChildSensor(child.id, child.type, child.description))
            self.sensors[msg.node_id].new_state[child.id] = new_child
            for value_type, value in child.values.items():
                new_value = new_child.values.get(value_type)
                if new_value is not None and new_value != value:
                    self.fill_queue(self.sensors[msg.node_id].set_child_value,
                                    (child.id, value_type, new_value))

    def _handle_internal(self, msg):
        """Process an internal protocol message."""
        if msg.sub_type == self.const.Internal.I_ID_REQUEST:
            node_id = self.add_sensor()
            return msg.modify(
                ack=0, sub_type=self.const.Internal.I_ID_RESPONSE,
                payload=node_id) if node_id is not None else None
        elif msg.sub_type == self.const.Internal.I_CONFIG:
            return msg.modify(ack=0, payload='M' if self.metric else 'I')
        elif msg.sub_type == self.const.Internal.I_TIME:
            return msg.modify(ack=0, payload=calendar.timegm(time.localtime()))
        actions = self.const.HANDLE_INTERNAL.get(msg.sub_type)
        if not actions:
            return
        if actions.get('is_sensor') and not self.is_sensor(msg.node_id):
            return
        if actions.get('setattr'):
            setattr(self.sensors[msg.node_id], actions['setattr'], msg.payload)
        if actions.get('fun'):
            getattr(self, actions['fun'])(msg)
        if actions.get('log'):
            getattr(_LOGGER, actions['log'])('n:%s c:%s t:%s s:%s p:%s',
                                             msg.node_id,
                                             msg.child_id,
                                             msg.type,
                                             msg.sub_type,
                                             msg.payload)
        if actions.get('msg'):
            return msg.modify(**actions['msg'])

    def _handle_stream(self, msg):
        """Process a stream type message."""
        if not self.is_sensor(msg.node_id):
            return
        if msg.sub_type == self.const.Stream.ST_FIRMWARE_CONFIG_REQUEST:
            return self.ota.respond_fw_config(msg)
        elif msg.sub_type == self.const.Stream.ST_FIRMWARE_REQUEST:
            return self.ota.respond_fw(msg)

    def send(self, message):
        """Implement this method in a child class."""
        raise NotImplementedError

    def logic(self, data):
        """Parse the data and respond to it appropriately.

        Response is returned to the caller and has to be sent
        data as a mysensors command string.
        """
        ret = None
        try:
            msg = Message(data, self)
        except ValueError:
            return

        if msg.type == self.const.MessageType.presentation:
            ret = self._handle_presentation(msg)
        elif msg.type == self.const.MessageType.set:
            ret = self._handle_set(msg)
        elif msg.type == self.const.MessageType.req:
            ret = self._handle_req(msg)
        elif msg.type == self.const.MessageType.internal:
            ret = self._handle_internal(msg)
        elif msg.type == self.const.MessageType.stream:
            ret = self._handle_stream(msg)
        ret = self._route_message(ret)
        ret = ret.encode() if ret else None
        return ret

    def _save_pickle(self, filename):
        """Save sensors to pickle file."""
        with open(filename, 'wb') as file_handle:
            pickle.dump(self.sensors, file_handle, pickle.HIGHEST_PROTOCOL)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    def _load_pickle(self, filename):
        """Load sensors from pickle file."""
        with open(filename, 'rb') as file_handle:
            self.sensors.update(pickle.load(file_handle))

    def _save_json(self, filename):
        """Save sensors to json file."""
        with open(filename, 'w') as file_handle:
            json.dump(self.sensors, file_handle, cls=MySensorsJSONEncoder)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    def _load_json(self, filename):
        """Load sensors from json file."""
        with open(filename, 'r') as file_handle:
            self.sensors.update(
                json.load(file_handle, cls=MySensorsJSONDecoder))

    def _save_sensors(self):
        """Save sensors to file."""
        fname = os.path.realpath(self.persistence_file)
        exists = os.path.isfile(fname)
        dirname = os.path.dirname(fname)
        if exists and os.access(fname, os.W_OK) and \
           os.access(dirname, os.W_OK) or \
           not exists and os.access(dirname, os.W_OK):
            split_fname = os.path.splitext(fname)
            tmp_fname = '{}.tmp{}'.format(split_fname[0], split_fname[1])
            self._perform_file_action(tmp_fname, 'save')
            if exists:
                os.rename(fname, self.persistence_bak)
            os.rename(tmp_fname, fname)
            if exists:
                os.remove(self.persistence_bak)
        else:
            _LOGGER.error('Permission denied when writing to %s', fname)

    def _load_sensors(self, path=None):
        """Load sensors from file."""
        if path is None:
            path = self.persistence_file
        exists = os.path.isfile(path)
        if exists and os.access(path, os.R_OK):
            if path == self.persistence_bak:
                os.rename(path, self.persistence_file)
                path = self.persistence_file
            self._perform_file_action(path, 'load')
            return True
        else:
            _LOGGER.warning('File does not exist or is not readable: %s', path)
            return False

    def _safe_load_sensors(self):
        """Load sensors safely from file."""
        try:
            loaded = self._load_sensors()
        except (EOFError, ValueError):
            _LOGGER.error('Bad file contents: %s', self.persistence_file)
            loaded = False
        if not loaded:
            _LOGGER.warning('Trying backup file: %s', self.persistence_bak)
            try:
                if not self._load_sensors(self.persistence_bak):
                    _LOGGER.warning('Failed to load sensors from file: %s',
                                    self.persistence_file)
            except (EOFError, ValueError):
                _LOGGER.error('Bad file contents: %s', self.persistence_file)
                _LOGGER.warning('Removing file: %s', self.persistence_file)
                os.remove(self.persistence_file)

    def _perform_file_action(self, filename, action):
        """Perform action on specific file types.

        Dynamic dispatch function for performing actions on
        specific file types.
        """
        ext = os.path.splitext(filename)[1]
        func = getattr(self, '_%s_%s' % (action, ext[1:]), None)
        if func is None:
            raise Exception('Unsupported file type %s' % ext[1:])
        func(filename)

    def alert(self, msg):
        """Tell anyone who wants to know that a sensor was updated.

        Also save sensors if persistence is enabled.
        """
        if self.event_callback is not None:
            try:
                self.event_callback(msg)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(exception)

        if self.persistence:
            self._save_sensors()

    def _get_next_id(self):
        """Return the next available sensor id."""
        if self.sensors:
            next_id = max(self.sensors.keys()) + 1
        else:
            next_id = 1
        if next_id <= 254:
            return next_id

    def add_sensor(self, sensorid=None):
        """Add a sensor to the gateway."""
        if sensorid is None:
            sensorid = self._get_next_id()
        if sensorid is not None and sensorid not in self.sensors:
            self.sensors[sensorid] = Sensor(sensorid)
            return sensorid

    def is_sensor(self, sensorid, child_id=None):
        """Return True if a sensor and its child exist."""
        ret = sensorid in self.sensors
        if not ret:
            _LOGGER.warning('Node %s is unknown', sensorid)
        if ret and child_id is not None:
            ret = child_id in self.sensors[sensorid].children
            if not ret:
                _LOGGER.warning('Child %s is unknown', child_id)
        if not ret and self.protocol_version >= 2.0:
            _LOGGER.info('Requesting new presentation for node %s',
                         sensorid)
            msg = Message(gateway=self).modify(
                node_id=sensorid, child_id=255,
                type=self.const.MessageType.internal,
                sub_type=self.const.Internal.I_PRESENTATION)
            if self._route_message(msg):
                self.fill_queue(msg.encode)
        return ret

    def _route_message(self, msg):
        if not isinstance(msg, Message) or \
                msg.type == self.const.MessageType.presentation:
            return
        if (msg.node_id not in self.sensors or
                msg.type == self.const.MessageType.stream or
                not self.sensors[msg.node_id].new_state):
            return msg
        self.sensors[msg.node_id].queue.append(msg.encode())

    def handle_queue(self, queue=None):
        """Handle queue.

        If queue is not empty, get the function and any args and kwargs
        from the queue. Run the function and return output.
        """
        if queue is None:
            queue = self.queue
        if not queue.empty():
            func, args, kwargs = queue.get()
            reply = func(*args, **kwargs)
            queue.task_done()
            return reply

    def fill_queue(self, func, args=None, kwargs=None, queue=None):
        """Put a function in a queue.

        Put the function 'func', a tuple of arguments 'args' and a dict
        of keyword arguments 'kwargs', as a tuple in the queue.
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        if queue is None:
            queue = self.queue
        queue.put((func, args, kwargs))

    def set_child_value(
            self, sensor_id, child_id, value_type, value, **kwargs):
        """Add a command to set a sensor value, to the queue.

        A queued command will be sent to the sensor when the gateway
        thread has sent all previously queued commands to the FIFO queue.
        If the sensor attribute new_state returns True, the command will not be
        put on the queue, but the internal sensor state will be updated. When a
        heartbeat response is received, the internal state will be pushed to
        the sensor, via _handle_heartbeat method.
        """
        if not self.is_sensor(sensor_id, child_id):
            return
        if self.sensors[sensor_id].new_state:
            self.sensors[sensor_id].set_child_value(
                child_id, value_type, value,
                children=self.sensors[sensor_id].new_state)
        else:
            self.fill_queue(self.sensors[sensor_id].set_child_value,
                            (child_id, value_type, value), kwargs)

    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare of all node_ids in nids."""
        self.ota.make_update(nids, fw_type, fw_ver, fw_path)


class Sensor(object):
    """Represent a sensor."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, sensor_id):
        """Set up sensor."""
        self.sensor_id = sensor_id
        self.children = {}
        self.type = None
        self.sketch_name = None
        self.sketch_version = None
        self._battery_level = 0
        self.protocol_version = None
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

    def __setstate__(self, state):
        """Set state when loading pickle."""
        # Restore instance attributes
        for key, val in state.items():
            setattr(self, key, val)
        # Reset some attributes
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

    @property
    def battery_level(self):
        """Return battery level."""
        return self._battery_level

    @battery_level.setter
    def battery_level(self, value):
        """Set battery level as int."""
        self._battery_level = int(value)

    def add_child_sensor(self, child_id, child_type, description=''):
        """Create and add a child sensor."""
        if child_id in self.children:
            _LOGGER.warning(
                'child_id %s already exists in children of node %s, '
                'cannot add child', child_id, self.sensor_id)
            return
        self.children[child_id] = ChildSensor(
            child_id, child_type, description)
        return child_id

    def set_child_value(self, child_id, value_type, value, **kwargs):
        """Set a child sensor's value."""
        children = kwargs.get('children', self.children)
        if not isinstance(children, dict) or child_id not in children:
            return
        msg_type = kwargs.get('msg_type', 1)
        ack = kwargs.get('ack', 0)
        msg = Message(gateway=self).modify(
            node_id=self.sensor_id, child_id=child_id, type=msg_type, ack=ack,
            sub_type=value_type, payload=value)
        msg_string = msg.encode()
        if msg_string is None:
            _LOGGER.error(
                'Not a valid message: node %s, child %s, type %s, ack %s, '
                'sub_type %s, payload %s',
                self.sensor_id, child_id, msg_type, ack, value_type, value)
            return
        try:
            msg = Message(msg_string)  # Validate child values
        except (ValueError, AttributeError) as exception:
            _LOGGER.error('Error validating child values: %s', exception)
            return
        children[msg.child_id].values[msg.sub_type] = msg.payload
        return msg_string


class ChildSensor(object):
    """Represent a child sensor."""

    # pylint: disable=too-few-public-methods

    def __init__(self, child_id, child_type, description=''):
        """Set up child sensor."""
        # pylint: disable=invalid-name
        self.id = child_id
        self.type = child_type
        self.description = description
        self.values = {}

    def __setstate__(self, state):
        """Set state when loading pickle."""
        # Restore instance attributes
        self.__dict__.update(state)
        # Make sure all attributes exist
        if 'description' not in self.__dict__:
            self.description = ''

    def __repr__(self):
        """Return the representation."""
        return self.__str__()

    def __str__(self):
        """Return the string representation."""
        ret = ('child_id={0!s}, child_type={1!s}, description={2!s}, '
               'values = {3!s}')
        return ret.format(self.id, self.type, self.description, self.values)


class Message(object):
    """Represent a message from the gateway."""

    def __init__(self, data=None, gateway=None):
        """Set up message."""
        self.node_id = 0
        self.child_id = 0
        self.type = 0
        self.ack = 0
        self.sub_type = 0
        self.payload = ''  # All data except payload are integers
        self.gateway = gateway
        if data is not None:
            self.decode(data)

    def copy(self, **kwargs):
        """Copy a message, optionally replace attributes with kwargs."""
        msg = Message(self.encode(), self.gateway)
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg

    def modify(self, **kwargs):
        """Modify and return message, replace attributes with kwargs."""
        for key, val in kwargs.items():
            setattr(self, key, val)
        return self

    def decode(self, data, delimiter=';'):
        """Decode a message from command string."""
        try:
            list_data = data.rstrip().split(delimiter)
            self.payload = list_data.pop()
            (self.node_id,
             self.child_id,
             self.type,
             self.ack,
             self.sub_type) = [int(f) for f in list_data]
        except ValueError:
            _LOGGER.warning('Error decoding message from gateway, '
                            'bad data received: %s', data)
            raise ValueError

    def encode(self, delimiter=';'):
        """Encode a command string from message."""
        try:
            return delimiter.join([str(f) for f in [
                self.node_id,
                self.child_id,
                int(self.type),
                self.ack,
                int(self.sub_type),
                self.payload,
            ]]) + '\n'
        except ValueError:
            _LOGGER.error('Error encoding message to gateway')


class MySensorsJSONEncoder(json.JSONEncoder):
    """JSON encoder."""

    def default(self, obj):
        """Serialize obj into JSON."""
        # pylint: disable=method-hidden, protected-access, arguments-differ
        if isinstance(obj, Sensor):
            return {
                'sensor_id': obj.sensor_id,
                'children': obj.children,
                'type': obj.type,
                'sketch_name': obj.sketch_name,
                'sketch_version': obj.sketch_version,
                '_battery_level': obj.battery_level,
                'protocol_version': obj.protocol_version,
            }
        if isinstance(obj, ChildSensor):
            return {
                'id': obj.id,
                'type': obj.type,
                'description': obj.description,
                'values': obj.values,
            }
        return json.JSONEncoder.default(self, obj)


class MySensorsJSONDecoder(json.JSONDecoder):
    """JSON decoder."""

    def __init__(self):
        """Set up decoder."""
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object)

    def dict_to_object(self, obj):  # pylint: disable=no-self-use
        """Return object from dict."""
        if not isinstance(obj, dict):
            return obj
        if 'sensor_id' in obj:
            sensor = Sensor(obj['sensor_id'])
            for key, val in obj.items():
                setattr(sensor, key, val)
            return sensor
        elif all(k in obj for k in ['id', 'type', 'values']):
            # Handle new optional description attribute
            if 'description' in obj:
                child = ChildSensor(obj['id'], obj['type'], obj['description'])
            else:
                child = ChildSensor(obj['id'], obj['type'])
            child.values = obj['values']
            return child
        elif all(k.isdigit() for k in obj.keys()):
            return {int(k): v for k, v in obj.items()}
        return obj
