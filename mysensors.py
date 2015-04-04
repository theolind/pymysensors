import serial
import time
import threading
from const import Internal, SetReq, Presentation, MessageType
import logging

LOGGER = logging.getLogger(__name__)


class Gateway(object):
    """ Base implementation for a MySensors Gateway. """

    def __init__(self, event_callback=None):
        self.eventCallback = event_callback
        self.sensors = {}
        self.metric = True   # if true - use metric, if false - use imperial
        self.debug = False   # if true - print all received messages

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
            self.sensors[msg.node_id].addChildSensor(msg.child_id, msg.sub_type)
            self.alert(msg.node_id)

    def _handle_set(self, msg):
        """ Processes a set message. """
        if self.is_sensor(msg.node_id, msg.child_id):
            self.sensors[msg.node_id].children[msg.child_id].value = msg.payload
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
            LOGGER.debug("n:{} c:{} t:{} s:{} p:{}".format(
                msg.node_id,
                msg.child_id,
                msg.type,
                msg.sub_type,
                msg.payload,
            ))

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

    def alert(self, nid):
        """ Tell anyone who wants to know that a sensor was updated. """
        if self.eventCallback is not None:
            self.eventCallback("sensor_update", nid)

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

    def __init__(self, port, event_callback=None, baud=115200):
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback)
        self.port = port
        self.baud = baud
        self._stop_event = threading.Event()

    def listen(self):
        """
        Opens the serial port and starts a background thread to read
        messages from the gateway.
        """
        self.serial = serial.Serial(self.port, self.baud)
        self.start()

    def stop(self):
        """ Stops the background thread. """
        self._stop_event.set()

    def run(self):
        """ Background thread that reads messages from the gateway. """
        while not self._stop_event.is_set():
            s = self.serial.readline()
            try:
                msg = s.decode('utf-8')
            except Exception as ex:
                LOGGER.exception()
                continue
            r = self.logic(msg)
            if r is not None:
                self.send(r.encode())

    def send(self, message):
        """ Writes a Message to the gateway. """
        self.serial.write(message.encode())


class Sensor:
    """ Represents a sensor. """

    def __init__(self, id):
        self.id = id
        self.children = {}
        self.type = None
        self.sketch_name = None
        self.sketch_version = None
        self.battery_level = 0

    def addChildSensor(self, id, type):
        """ Creates and adds a child sensor. """
        self.children[id] = ChildSensor(id, type)

    def setChildValue(self, id, value):
        """ Set's a child sensor's value. """
        if id in self.children:
            self.children[id].value = value
        #TODO: Handle error


class ChildSensor:
    """ Represents a child sensor. """

    def __init__(self, id, type):
        self.id = id
        self.type = type
        self.value = None


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
        for k,v in kwargs.items():
            setattr(msg, k, v)
        return msg

    def decode(self, data):
        """ Decode a message from command string. """
        data = data.rstrip().split(';')
        self.payload = data.pop()
        (self.node_id, self.child_id, self.type, self.ack, self.sub_type) = \
            [int(f) for f in data]

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
