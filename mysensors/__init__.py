"""Python implementation of MySensors API."""
import calendar
import json
import logging
import os
import pickle
import threading
import time
from collections import deque
# pylint: disable=import-error, no-name-in-module
from distutils.version import LooseVersion as parse_ver
from importlib import import_module
from queue import Queue
from timeit import default_timer as timer

import voluptuous as vol

from .validation import is_battery_level, safe_is_version
from .ota import OTAFirmware
from .version import __version__  # noqa: F401

_LOGGER = logging.getLogger(__name__)

BROADCAST_ID = 255
LOADED_CONST = {}
SYSTEM_CHILD_ID = 255


def get_const(protocol_version):
    """Return the const module for the protocol_version."""
    version = protocol_version
    if parse_ver('1.5') <= parse_ver(version) < parse_ver('2.0'):
        path = 'mysensors.const_15'
    elif parse_ver(version) >= parse_ver('2.0'):
        path = 'mysensors.const_20'
    else:
        path = 'mysensors.const_14'
    if path in LOADED_CONST:
        return LOADED_CONST[path]
    const = import_module(path)
    LOADED_CONST[path] = const  # Cache the module
    return const


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
        self.protocol_version = safe_is_version(protocol_version)
        self.const = get_const(self.protocol_version)
        self.ota = OTAFirmware(self.sensors, self.const)
        if persistence:
            self._safe_load_sensors()

    def __repr__(self):
        """Return the representation."""
        return self.__class__.__name__

    def _handle_presentation(self, msg):
        """Process a presentation message."""
        if msg.child_id == SYSTEM_CHILD_ID:
            # this is a presentation of the sensor platform
            sensorid = self.add_sensor(msg.node_id)
            if sensorid is None:
                if msg.node_id in self.sensors:
                    self.sensors[msg.node_id].reboot = False
                return None
            self.sensors[msg.node_id].type = msg.sub_type
            self.sensors[msg.node_id].protocol_version = msg.payload
            self.alert(msg)
            return msg
        else:
            # this is a presentation of a child sensor
            if not self.is_sensor(msg.node_id):
                _LOGGER.error('Node %s is unknown, will not add child %s.',
                              msg.node_id, msg.child_id)
                return None
            child_id = self.sensors[msg.node_id].add_child_sensor(
                msg.child_id, msg.sub_type, msg.payload)
            if child_id is None:
                return None
            self.alert(msg)
            return msg

    def _handle_set(self, msg):
        """Process a set message."""
        if not self.is_sensor(msg.node_id, msg.child_id):
            return None
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
                child_id=SYSTEM_CHILD_ID, type=self.const.MessageType.internal,
                ack=0, sub_type=self.const.Internal.I_REBOOT, payload='')
        return None

    def _handle_req(self, msg):
        """Process a req message.

        This will return the value if it exists. If no value exists,
        nothing is returned.
        """
        if not self.is_sensor(msg.node_id, msg.child_id):
            return None
        value = self.sensors[msg.node_id].children[
            msg.child_id].values.get(msg.sub_type)
        if value is not None:
            return msg.modify(
                type=self.const.MessageType.set, payload=value)
        return None

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
        if actions.get('is_sensor') and not self.is_sensor(msg.node_id):
            return None
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
        return None

    def _handle_stream(self, msg):
        """Process a stream type message."""
        if not self.is_sensor(msg.node_id):
            return None
        if msg.sub_type == self.const.Stream.ST_FIRMWARE_CONFIG_REQUEST:
            return self.ota.respond_fw_config(msg)
        elif msg.sub_type == self.const.Stream.ST_FIRMWARE_REQUEST:
            return self.ota.respond_fw(msg)
        return None

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
            msg.validate(self.protocol_version)
        except (ValueError, vol.Invalid) as exc:
            _LOGGER.warning('Not a valid message: %s', exc)
            return None

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
            json.dump(self.sensors, file_handle, cls=MySensorsJSONEncoder,
                      indent=4)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    def _load_json(self, filename):
        """Load sensors from json file."""
        with open(filename, 'r') as file_handle:
            self.sensors.update(json.load(
                file_handle, cls=MySensorsJSONDecoder))

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
        if next_id <= self.const.MAX_NODE_ID:
            return next_id
        return None

    def add_sensor(self, sensorid=None):
        """Add a sensor to the gateway."""
        if sensorid is None:
            sensorid = self._get_next_id()
        if sensorid is not None and sensorid not in self.sensors:
            self.sensors[sensorid] = Sensor(sensorid)
            return sensorid
        return None

    def is_sensor(self, sensorid, child_id=None):
        """Return True if a sensor and its child exist."""
        ret = sensorid in self.sensors
        if not ret:
            _LOGGER.warning('Node %s is unknown', sensorid)
        if ret and child_id is not None:
            ret = child_id in self.sensors[sensorid].children
            if not ret:
                _LOGGER.warning('Child %s is unknown', child_id)
        if not ret and parse_ver(self.protocol_version) >= parse_ver('2.0'):
            _LOGGER.info('Requesting new presentation for node %s',
                         sensorid)
            msg = Message(gateway=self).modify(
                node_id=sensorid, child_id=SYSTEM_CHILD_ID,
                type=self.const.MessageType.internal,
                sub_type=self.const.Internal.I_PRESENTATION)
            if self._route_message(msg):
                self.fill_queue(msg.encode)
        return ret

    def _route_message(self, msg):
        if not isinstance(msg, Message) or \
                msg.type == self.const.MessageType.presentation:
            return None
        if (msg.node_id not in self.sensors or
                msg.type == self.const.MessageType.stream or
                not self.sensors[msg.node_id].new_state):
            return msg
        self.sensors[msg.node_id].queue.append(msg.encode())
        return None

    def handle_queue(self, queue=None):
        """Handle queue.

        If queue is not empty, get the function and any args and kwargs
        from the queue. Run the function and return output.
        """
        if queue is None:
            queue = self.queue
        if queue.empty():
            return None
        start = timer()
        func, args, kwargs = queue.get()
        reply = func(*args, **kwargs)
        queue.task_done()
        end = timer()
        if end - start > 0.1:
            _LOGGER.debug(
                'Handle queue with call %s(%s, %s) took %.3f seconds',
                func, args, kwargs, end - start)
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
        self._protocol_version = '1.4'
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

    def __getstate__(self):
        """Get state to save as pickle."""
        state = self.__dict__.copy()
        for attr in ('_battery_level', '_protocol_version'):
            value = state.pop(attr, None)
            prop = attr
            if prop.startswith('_'):
                prop = prop[1:]
            if value is not None:
                state[prop] = value

        return state

    def __setstate__(self, state):
        """Set state when loading pickle."""
        # Restore instance attributes
        for key, val in state.items():
            setattr(self, key, val)
        # Reset some attributes
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

    def __repr__(self):
        """Return the representation."""
        return '<Sensor sensor_id={}, children: {}>'.format(
            self.sensor_id, self.children)

    @property
    def battery_level(self):
        """Return battery level."""
        return self._battery_level

    @battery_level.setter
    def battery_level(self, value):
        """Set valid battery level."""
        self._battery_level = is_battery_level(value)

    @property
    def protocol_version(self):
        """Return protocol version."""
        return self._protocol_version

    @protocol_version.setter
    def protocol_version(self, value):
        """Set valid protocol version."""
        self._protocol_version = safe_is_version(value)

    def add_child_sensor(self, child_id, child_type, description=''):
        """Create and add a child sensor."""
        if child_id in self.children:
            _LOGGER.warning(
                'child_id %s already exists in children of node %s, '
                'cannot add child', child_id, self.sensor_id)
            return None
        self.children[child_id] = ChildSensor(
            child_id, child_type, description)
        return child_id

    def set_child_value(self, child_id, value_type, value, **kwargs):
        """Set a child sensor's value."""
        children = kwargs.get('children', self.children)
        if not isinstance(children, dict) or child_id not in children:
            return None
        msg_type = kwargs.get('msg_type', 1)
        ack = kwargs.get('ack', 0)
        msg = Message().modify(
            node_id=self.sensor_id, child_id=child_id, type=msg_type, ack=ack,
            sub_type=value_type, payload=value)
        msg_string = msg.encode()
        if msg_string is None:
            _LOGGER.error(
                'Not a valid message: node %s, child %s, type %s, ack %s, '
                'sub_type %s, payload %s',
                self.sensor_id, child_id, msg_type, ack, value_type, value)
            return None
        try:
            msg = Message(msg_string)
            msg.validate(self.protocol_version)
        except (ValueError, AttributeError, vol.Invalid) as exc:
            _LOGGER.error('Not a valid message: %s', exc)
            return None
        child = children[msg.child_id]
        child.values[msg.sub_type] = msg.payload
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
        ret = ('<ChildSensor child_id={0!s}, child_type={1!s}, '
               'description={2!s}, values: {3!s}>')
        return ret.format(self.id, self.type, self.description, self.values)

    def get_schema(self, protocol_version):
        """Return the child schema for the correct const version."""
        const = get_const(protocol_version)
        return vol.Schema({
            typ.value: const.VALID_SETREQ[typ]
            for typ in const.VALID_TYPES[self.type]})

    def validate(self, protocol_version, values=None):
        """Validate child value types and values against protocol_version."""
        if values is None:
            values = self.values
        return self.get_schema(protocol_version)(values)


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

    def __repr__(self):
        """Return the representation."""
        return '<Message data="{};{};{};{};{};{}">'.format(
            self.node_id, self.child_id, self.type, self.ack, self.sub_type,
            self.payload)

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

    def validate(self, protocol_version):
        """Validate message."""
        const = get_const(protocol_version)
        valid_node_ids = vol.All(vol.Coerce(int), vol.Range(
            min=0, max=BROADCAST_ID, msg='Not valid node_id: {}'.format(
                self.node_id)))
        valid_child_ids = vol.All(vol.Coerce(int), vol.Range(
            min=0, max=SYSTEM_CHILD_ID, msg='Not valid child_id: {}'.format(
                self.child_id)))
        if self.type in (const.MessageType.internal, const.MessageType.stream):
            valid_child_ids = vol.All(vol.Coerce(int), vol.In(
                [SYSTEM_CHILD_ID],
                msg='When message type is {}, child_id must be {}'.format(
                    self.type, SYSTEM_CHILD_ID)))
        if (self.type == const.MessageType.internal and
                self.sub_type in [
                    const.Internal.I_ID_REQUEST,
                    const.Internal.I_ID_RESPONSE]):
            valid_child_ids = vol.Coerce(int)
        valid_types = vol.All(vol.Coerce(int), vol.In(
            [member.value for member in const.VALID_MESSAGE_TYPES],
            msg='Not valid message type: {}'.format(self.type)))
        if self.child_id == SYSTEM_CHILD_ID:
            valid_types = vol.All(vol.Coerce(int), vol.In(
                [const.MessageType.presentation.value,
                 const.MessageType.internal.value,
                 const.MessageType.stream.value],
                msg=(
                    'When child_id is {}, {} is not a valid '
                    'message type'.format(SYSTEM_CHILD_ID, self.type))))
        valid_ack = vol.In([0, 1], msg='Not valid ack flag: {}'.format(
            self.ack))
        valid_sub_types = vol.In(
            [member.value for member
             in const.VALID_MESSAGE_TYPES.get(self.type, [])],
            msg='Not valid message sub-type: {}'.format(self.sub_type))
        valid_payload = const.VALID_PAYLOADS.get(
            self.type, {}).get(self.sub_type, '')
        schema = vol.Schema({
            'node_id': valid_node_ids, 'child_id': valid_child_ids,
            'type': valid_types, 'ack': valid_ack, 'sub_type': valid_sub_types,
            'payload': valid_payload})
        to_validate = {attr: getattr(self, attr) for attr in schema.schema}
        return schema(to_validate)


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
                'battery_level': obj.battery_level,
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
            child = ChildSensor(
                obj['id'], obj['type'], obj.get('description', ''))
            child.values = obj['values']
            return child
        elif all(k.isdigit() for k in obj.keys()):
            return {int(k): v for k, v in obj.items()}
        return obj
