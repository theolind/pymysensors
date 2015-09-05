"""
pymysensors - Python implementation of the MySensors SerialGateway
"""
import serial
import time
import threading
import logging
import pickle
import os
import json

# Correct versions will be dynamically imported when creating a gateway
global Internal, MessageType

LOGGER = logging.getLogger(__name__)


class Gateway(object):
    """ Base implementation for a MySensors Gateway. """

    def __init__(self, event_callback=None, persistence=False,
                 persistence_file="mysensors.pickle", protocol_version="1.4"):
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True   # if true - use metric, if false - use imperial
        self.debug = False   # if true - print all received messages
        self.persistence = persistence  # if true - save sensors to disk
        self.persistence_file = persistence_file    # path to persistence file
        if persistence:
            self._load_sensors()
        if protocol_version == "1.4":
            _const = __import__("mysensors.const_14", globals(), locals(), ['Internal', 'MessageType'], 0)
        elif protocol_version == "1.5":
            _const = __import__("mysensors.const_15", globals(), locals(), ['Internal', 'MessageType'], 0)
        global Internal, MessageType
        Internal = _const.Internal
        MessageType = _const.MessageType

    def _handle_presentation(self, msg):
        """ Processes a presentation message. """
        if msg.child_id == 255:
            # this is a presentation of the sensor platform
            self.add_sensor(msg.node_id)
            self.sensors[msg.node_id].type = msg.sub_type
            self.sensors[msg.node_id].version = msg.payload
            self.alert(msg.node_id)
        else:
            # this is a presentation of a child sensor
            self.sensors[msg.node_id].add_child_sensor(msg.child_id,
                                                       msg.sub_type)
            self.alert(msg.node_id)

    def _handle_set(self, msg):
        """ Processes a set message. """
        if self.is_sensor(msg.node_id, msg.child_id):
            self.sensors[msg.node_id].set_child_value(
                msg.child_id, msg.sub_type, msg.payload)
            self.alert(msg.node_id)

    def _handle_internal(self, msg):
        """ Processes an internal protocol message. """
        if msg.sub_type == Internal.I_ID_REQUEST:
            return msg.copy(ack=0,
                            sub_type=Internal.I_ID_RESPONSE,
                            payload=self.add_sensor())
        elif msg.sub_type == Internal.I_SKETCH_NAME:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].sketch_name = msg.payload
                self.alert(msg.node_id)
        elif msg.sub_type == Internal.I_SKETCH_VERSION:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].sketch_version = msg.payload
                self.alert(msg.node_id)
        elif msg.sub_type == Internal.I_CONFIG:
            return msg.copy(ack=0, payload='M' if self.metric else 'I')
        elif msg.sub_type == Internal.I_BATTERY_LEVEL:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].battery_level = int(msg.payload)
                self.alert(msg.node_id)
        elif msg.sub_type == Internal.I_TIME:
            return msg.copy(ack=0, payload=int(time.time()))
        elif msg.sub_type == Internal.I_LOG_MESSAGE and self.debug:
            LOGGER.debug("n:%s c:%s t:%s s:%s p:%s",
                         msg.node_id,
                         msg.child_id,
                         msg.type,
                         msg.sub_type,
                         msg.payload)

    def send(self, message):
        """ Should be implemented by a child class. """
        pass

    def logic(self, data):
        """
        Parse the data and respond to it appropriately.
        Response is returned to the caller and has to be sent
        data is a mysensors command string
        """
        msg = Message(data)

        if msg.type == MessageType.presentation:
            self._handle_presentation(msg)
        elif msg.type == MessageType.set:
            self._handle_set(msg)
        elif msg.type == MessageType.internal:
            return self._handle_internal(msg)
        return None

    def _save_pickle(self, filename):
        """ Save sensors to pickle file """
        with open(filename, 'wb') as f:
            pickle.dump(self.sensors, f, pickle.HIGHEST_PROTOCOL)

    def _load_pickle(self, filename):
        """ Load sensors from pickle file """
        try:
            with open(filename, 'rb') as f:
                self.sensors = pickle.load(f)
        except IOError:
            pass

    def _save_json(self, filename):
        """ Save sensors to json file """
        with open(filename, 'w') as f:
            json.dump(self.sensors, f, cls=MySensorsJSONEncoder)

    def _load_json(self, filename):
        """ Load sensors from json file """
        with open(filename, 'r') as f:
            self.sensors = json.load(f, cls=MySensorsJSONDecoder)

    def _save_sensors(self):
        """ Save sensors to file """
        fname = os.path.realpath(self.persistence_file)
        exists = os.path.isfile(fname)
        dirname = os.path.dirname(fname)
        if (exists and os.access(fname, os.W_OK)) or \
           (not exists and os.access(dirname, os.W_OK)):
            self._perform_file_action(fname, 'save')
        else:
            LOGGER.info('Permission denied when writing to %s' % fname)

    def _load_sensors(self):
        """ Load sensors from file """
        exists = os.path.isfile(self.persistence_file)
        if exists and os.access(self.persistence_file, os.R_OK):
            self._perform_file_action(self.persistence_file, 'load')
        else:
            LOGGER.info('File does not exist or is not '
                        'readable: %s' % self.persistence_file)

    def _perform_file_action(self, filename, action):
        """
        Dynamic dispatch function for performing actions on
        specific file types.
        """
        path, ext = os.path.splitext(filename)
        fn = getattr(self, '_%s_%s' % (action, ext[1:]), None)
        if fn is None:
            raise Exception('Unsupported file type %s' % ext[1:])
        fn(filename)

    def alert(self, nid):
        """
        Tell anyone who wants to know that a sensor was updated. Also save
        sensors if persistence is enabled
        """
        if self.event_callback is not None:
            self.event_callback("sensor_update", nid)

        if self.persistence:
            self._save_sensors()

    def _get_next_id(self):
        """ Returns the next available sensor id. """
        if len(self.sensors):
            next_id = max(self.sensors.keys()) + 1
        else:
            next_id = 1
        if next_id <= 254:
            return next_id
        return None

    def add_sensor(self, sensorid=None):
        """ Adds a sensor to the gateway. """
        if sensorid is None:
            sensorid = self._get_next_id()

        if sensorid is not None and sensorid not in self.sensors:
            self.sensors[sensorid] = Sensor(sensorid)
            return sensorid
        return None

    def is_sensor(self, sensorid, child_id=None):
        """ Returns True if a sensor and its child exists. """
        if sensorid not in self.sensors:
            return False
        if child_id is not None:
            return child_id in self.sensors[sensorid].children
        return True


class SerialGateway(Gateway, threading.Thread):
    """ MySensors serial gateway. """
    # pylint: disable=too-many-arguments

    def __init__(self, port, event_callback=None, persistence=False,
                 persistence_file="mysensors.pickle",
                 baud=115200, timeout=1.0, reconnect_timeout=10.0):
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback, persistence, persistence_file)
        self.serial = None
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout
        self._stop_event = threading.Event()

    def connect(self):
        """ Connects to the serial port. """
        if self.serial:
            return True
        try:
            self.serial = serial.Serial(self.port, self.baud,
                                        timeout=self.timeout)
        except serial.SerialException:
            LOGGER.exception('Unable to connect to %s', self.port)
            return False
        return True

    def disconnect(self):
        """ Disconnects from the serial port. """
        if self.serial is not None:
            self.serial.close()
            self.serial = None

    def stop(self):
        """ Stops the background thread. """
        self._stop_event.set()

    def run(self):
        """ Background thread that reads messages from the gateway. """
        while not self._stop_event.is_set():
            if self.serial is None and not self.connect():
                time.sleep(self.reconnect_timeout)
                continue
            try:
                line = self.serial.readline()
                if not line:
                    continue
            except serial.SerialException:
                LOGGER.exception('Serial exception')
                continue
            except TypeError:
                # pyserial has a bug that causes a TypeError to be thrown when
                # the port disconnects instead of a SerialException
                self.disconnect()
                continue
            try:
                msg = line.decode('utf-8')
                response = self.logic(msg)
            except ValueError:
                LOGGER.warning('Error decoding message from gateway, probably received bad byte.')
                continue
            if response is not None:
                try:
                    self.send(response.encode())
                except ValueError:
                    LOGGER.exception('Invalid response')
                    continue

    def send(self, message):
        """ Writes a Message to the gateway. """
        self.serial.write(message.encode())


class Sensor:
    """ Represents a sensor. """

    def __init__(self, sensor_id):
        self.sensor_id = sensor_id
        self.children = {}
        self.type = None
        self.sketch_name = None
        self.sketch_version = None
        self.battery_level = 0

    def add_child_sensor(self, child_id, child_type):
        """ Creates and adds a child sensor. """
        self.children[child_id] = ChildSensor(child_id, child_type)

    def set_child_value(self, child_id, value_type, value):
        """ Sets a child sensor's value. """
        if child_id in self.children:
            self.children[child_id].values[value_type] = value
        # TODO: Handle error


class ChildSensor:
    """ Represents a child sensor. """
    # pylint: disable=too-few-public-methods

    def __init__(self, child_id, child_type):
        self.id = child_id
        self.type = child_type
        self.values = {}


class Message:
    """ Represents a message from the gateway. """

    def __init__(self, data=None):
        self.node_id = 0
        self.child_id = 0
        self.type = ""
        self.ack = 0
        self.sub_type = ""
        self.payload = ""
        if data is not None:
            self.decode(data)

    def copy(self, **kwargs):
        """
        Copies a message, optionally replacing attributes with keyword
        arguments.
        """
        msg = Message(self.encode())
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg

    def decode(self, data):
        """ Decode a message from command string. """
        data = data.rstrip().split(';')
        self.payload = data.pop()
        (self.node_id,
         self.child_id,
         self.type,
         self.ack,
         self.sub_type) = [int(f) for f in data]

    def encode(self):
        """ Encode a command string from message. """
        return ";".join([str(f) for f in [
            self.node_id,
            self.child_id,
            int(self.type),
            self.ack,
            int(self.sub_type),
            self.payload,
        ]]) + "\n"


class MySensorsJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Sensor):
            return {
                'sensor_id': o.sensor_id,
                'children': o.children,
                'type': o.type,
                'sketch_name': o.sketch_name,
                'sketch_version': o.sketch_version,
                'battery_level': o.battery_level,
            }
        if isinstance(o, ChildSensor):
            return {
                'id': o.id,
                'type': o.type,
                'values': o.values,
            }
        return json.JSONEncoder.default(self, o)


class MySensorsJSONDecoder(json.JSONDecoder):
    def __init__(self):
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object)

    def dict_to_object(self, o):
        if not isinstance(o, dict):
            return o
        if 'sensor_id' in o:
            sensor = Sensor(o['sensor_id'])
            sensor.__dict__.update(o)
            return sensor
        elif all(k in o for k in ['id', 'type', 'values']):
            child = ChildSensor(o['id'], o['type'])
            child.values = o['values']
            return child
        elif all(k.isdigit() for k in o.keys()):
            return {int(k): v for k,v in o.items()}
        return o
