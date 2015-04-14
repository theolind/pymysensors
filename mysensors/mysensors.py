"""
pymysensors - Python implementation of the MySensors SerialGateway
"""
import serial
import time
import threading
from .const import Internal, MessageType
import logging
import pickle

LOGGER = logging.getLogger(__name__)


class Gateway(object):
    """ Base implementation for a MySensors Gateway. """

    def __init__(self, event_callback=None, persistence = False):
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True   # if true - use metric, if false - use imperial
        self.debug = False   # if true - print all received messages
        self.persistence = persistence # if true - save sensors to disk
        if persistence:
            self._load_sensors()

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

    def _save_sensors(self):
        """ Save sensors to file """
        with open('mysensors.pickle', 'wb') as f:
            pickle.dump(self.sensors, f, pickle.HIGHEST_PROTOCOL)


    def _load_sensors(self):
        """ Load sensors from file """
        try:
            with open('mysensors.pickle', 'rb') as f:
                self.sensors = pickle.load(f)
        except IOError:
            pass

    def alert(self, nid):
        """ Tell anyone who wants to know that a sensor was updated. """
        if self.event_callback is not None:
            self.event_callback("sensor_update", nid)

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

    def __init__(self, port, event_callback=None, baud=115200, timeout=1.0,
                 reconnect_timeout=10.0):
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback)
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
            except ValueError:
                LOGGER.exception()
                continue
            response = self.logic(msg)
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
