"""pymysensors - Python implementation of the MySensors SerialGateway."""
import json
import logging
import os
import pickle
import select
import socket
import threading
import time
from collections import deque
from importlib import import_module
from queue import Queue

import serial

from mysensors.ota import OTAFirmware

_LOGGER = logging.getLogger(__name__)

# pylint: disable=too-many-lines


class Gateway(object):
    """Base implementation for a MySensors Gateway."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, event_callback=None, persistence=False,
                 persistence_file='mysensors.pickle', protocol_version='1.4'):
        """Setup Gateway."""
        self.queue = Queue()
        self.lock = threading.Lock()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True  # if true - use metric, if false - use imperial
        self.debug = False  # if true - print all received messages
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
            self.alert(msg.node_id)
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
            self.alert(msg.node_id)
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
        self.alert(msg.node_id)
        # Check if reboot is true
        if self.sensors[msg.node_id].reboot:
            return msg.copy(
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
                return msg.copy(type=self.const.MessageType.set, payload=value)

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
            return msg.copy(ack=0,
                            sub_type=self.const.Internal.I_ID_RESPONSE,
                            payload=node_id) if node_id is not None else None
        elif msg.sub_type == self.const.Internal.I_SKETCH_NAME:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].sketch_name = msg.payload
                self.alert(msg.node_id)
        elif msg.sub_type == self.const.Internal.I_SKETCH_VERSION:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].sketch_version = msg.payload
                self.alert(msg.node_id)
        elif msg.sub_type == self.const.Internal.I_CONFIG:
            return msg.copy(ack=0, payload='M' if self.metric else 'I')
        elif msg.sub_type == self.const.Internal.I_BATTERY_LEVEL:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].battery_level = int(msg.payload)
                self.alert(msg.node_id)
        elif msg.sub_type == self.const.Internal.I_TIME:
            return msg.copy(ack=0, payload=int(time.time()))
        elif (self.protocol_version >= 2.0 and
              msg.sub_type == self.const.Internal.I_HEARTBEAT_RESPONSE):
            self._handle_heartbeat(msg)
        elif msg.sub_type == self.const.Internal.I_LOG_MESSAGE and self.debug:
            _LOGGER.debug('n:%s c:%s t:%s s:%s p:%s',
                          msg.node_id,
                          msg.child_id,
                          msg.type,
                          msg.sub_type,
                          msg.payload)

    def _handle_stream(self, msg):
        """Process a stream type message."""
        if not self.is_sensor(msg.node_id):
            return
        if msg.sub_type == self.const.Stream.ST_FIRMWARE_CONFIG_REQUEST:
            return self.ota.respond_fw_config(msg)
        elif msg.sub_type == self.const.Stream.ST_FIRMWARE_REQUEST:
            return self.ota.respond_fw(msg)

    def send(self, message):
        """Should be implemented by a child class."""
        raise NotImplementedError

    def logic(self, data):
        """Parse the data and respond to it appropriately.

        Response is returned to the caller and has to be sent
        data as a mysensors command string.
        """
        ret = None
        try:
            msg = Message(data)
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
            self.sensors = pickle.load(file_handle)

    def _save_json(self, filename):
        """Save sensors to json file."""
        with open(filename, 'w') as file_handle:
            json.dump(self.sensors, file_handle, cls=MySensorsJSONEncoder)
            file_handle.flush()
            os.fsync(file_handle.fileno())

    def _load_json(self, filename):
        """Load sensors from json file."""
        with open(filename, 'r') as file_handle:
            self.sensors = json.load(file_handle, cls=MySensorsJSONDecoder)

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

    def alert(self, nid):
        """Tell anyone who wants to know that a sensor was updated.

        Also save sensors if persistence is enabled.
        """
        if self.event_callback is not None:
            try:
                self.event_callback('sensor_update', nid)
            except Exception as exception:  # pylint: disable=W0703
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
            msg = Message().copy(
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


class SerialGateway(Gateway, threading.Thread):
    """Serial gateway for MySensors."""

    # pylint: disable=too-many-arguments

    def __init__(self, port, event_callback=None,
                 persistence=False, persistence_file='mysensors.pickle',
                 protocol_version='1.4', baud=115200, timeout=1.0,
                 reconnect_timeout=10.0):
        """Setup serial gateway."""
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback, persistence,
                         persistence_file, protocol_version)
        self.serial = None
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout
        self._stop_event = threading.Event()

    def connect(self):
        """Connect to the serial port."""
        if self.serial:
            _LOGGER.info('Already connected to %s', self.port)
            return True
        try:
            _LOGGER.info('Trying to connect to %s', self.port)
            self.serial = serial.Serial(self.port, self.baud,
                                        timeout=self.timeout)
            if self.serial.isOpen():
                _LOGGER.info('%s is open...', self.serial.name)
                _LOGGER.info('Connected to %s', self.port)
            else:
                _LOGGER.info('%s is not open...', self.serial.name)
                self.serial = None
                return False

        except serial.SerialException:
            _LOGGER.error('Unable to connect to %s', self.port)
            return False
        return True

    def disconnect(self):
        """Disconnect from the serial port."""
        if self.serial is not None:
            name = self.serial.name
            _LOGGER.info('Disconnecting from %s', name)
            self.serial.close()
            self.serial = None
            _LOGGER.info('Disconnected from %s', name)

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info('Stopping thread')
        self._stop_event.set()

    def run(self):
        """Background thread that reads messages from the gateway."""
        while not self._stop_event.is_set():
            if self.serial is None and not self.connect():
                time.sleep(self.reconnect_timeout)
                continue
            response = self.handle_queue()
            if response is not None:
                self.send(response)
            if not self.queue.empty():
                continue
            try:
                line = self.serial.readline()
                if not line:
                    continue
            except serial.SerialException:
                _LOGGER.exception('Serial exception')
                self.disconnect()
                continue
            except TypeError:
                # pyserial has a bug that causes a TypeError to be thrown when
                # the port disconnects instead of a SerialException
                self.disconnect()
                continue
            try:
                string = line.decode('utf-8')
            except ValueError:
                _LOGGER.warning(
                    'Error decoding message from gateway, '
                    'probably received bad byte.')
                continue
            self.fill_queue(self.logic, (string,))
        self.disconnect()  # Disconnect after stop event is set

    def send(self, message):
        """Write a Message to the gateway."""
        if not message:
            return
        # Lock to make sure only one thread writes at a time to serial port.
        with self.lock:
            self.serial.write(message.encode())


class TCPGateway(Gateway, threading.Thread):
    """MySensors TCP ethernet gateway."""

    # pylint: disable=too-many-arguments

    def __init__(self, host, event_callback=None,
                 persistence=False, persistence_file='mysensors.pickle',
                 protocol_version='1.4', port=5003, timeout=1.0,
                 reconnect_timeout=10.0):
        """Setup TCP ethernet gateway."""
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback, persistence,
                         persistence_file, protocol_version)
        self.sock = None
        self.server_address = (host, port)
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout
        self._stop_event = threading.Event()

    def connect(self):
        """Connect to the socket object, on host and port."""
        if self.sock:
            _LOGGER.info('Already connected to %s', self.sock)
            return True
        try:
            # Connect to the server at the port
            _LOGGER.info(
                'Trying to connect to %s', self.server_address)
            self.sock = socket.create_connection(
                self.server_address, self.reconnect_timeout)
            _LOGGER.info('Connected to %s', self.server_address)
            return True

        except TimeoutError:
            _LOGGER.error(
                'Connecting to socket timed out for %s.', self.server_address)
            return False
        except OSError:
            _LOGGER.error(
                'Failed to connect to socket at %s.', self.server_address)
            return False

    def disconnect(self):
        """Close the socket."""
        if not self.sock:
            return
        _LOGGER.info('Closing socket at %s.', self.server_address)
        self.sock.shutdown(socket.SHUT_WR)
        self.sock.close()
        self.sock = None
        _LOGGER.info('Socket closed at %s.', self.server_address)

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info('Stopping thread')
        self._stop_event.set()

    def _check_socket(self, sock=None, timeout=None):
        """Check if socket is readable/writable."""
        if sock is None:
            sock = self.sock
        available_socks = select.select([sock], [sock], [sock], timeout)
        if available_socks[2]:
            raise OSError
        return available_socks

    def recv_timeout(self):
        """Receive reply from server, with a timeout."""
        # make socket non blocking
        self.sock.setblocking(False)
        # total data in an array
        total_data = []
        data_string = ''
        joined_data = ''
        # start time
        begin = time.time()

        while not data_string.endswith('\n'):
            data_string = ''
            # break after timeout
            if time.time() - begin > self.timeout:
                break
            # receive data
            try:
                # Buffer size from gateway should be 120 bytes
                # according to mysensors ethernet gateway util.
                data_bytes = self.sock.recv(120)
                if data_bytes:
                    data_string = data_bytes.decode('utf-8')
                    _LOGGER.debug('Received %s', data_string)
                    total_data.append(data_string)
                    # reset start time
                    begin = time.time()
                    # join all data to final data
                    joined_data = ''.join(total_data)
                else:
                    # sleep to add time difference
                    time.sleep(0.1)
            except OSError:
                _LOGGER.error('Receive from server failed.')
                self.disconnect()
                break
            except ValueError:
                _LOGGER.warning(
                    'Error decoding message from gateway, '
                    'probably received bad byte.')
                break

        return joined_data

    def send(self, message):
        """Write a command string to the gateway via the socket."""
        if not message:
            return
        with self.lock:
            try:
                # Send data
                _LOGGER.debug('Sending %s', message)
                self.sock.sendall(message.encode())

            except OSError:
                # Send failed
                _LOGGER.error('Send to server failed.')
                self.disconnect()

    def run(self):
        """Background thread that reads messages from the gateway."""
        while not self._stop_event.is_set():
            if self.sock is None and not self.connect():
                _LOGGER.info('Waiting 10 secs before trying to connect again.')
                time.sleep(self.reconnect_timeout)
                continue
            try:
                available_socks = self._check_socket()
            except OSError:
                _LOGGER.error('Server socket %s has an error.', self.sock)
                self.disconnect()
                continue
            if available_socks[1] and self.sock is not None:
                response = self.handle_queue()
                if response is not None:
                    self.send(response)
            if not self.queue.empty():
                continue
            time.sleep(0.02)  # short sleep to avoid burning 100% cpu
            if available_socks[0] and self.sock is not None:
                string = self.recv_timeout()
                lines = string.split('\n')
                # Throw away last empty line or uncompleted message.
                del lines[-1]
                for line in lines:
                    self.fill_queue(self.logic, (line,))
        self.disconnect()


class MQTTGateway(Gateway, threading.Thread):
    """MySensors MQTT client gateway."""

    # pylint: disable=too-many-arguments

    def __init__(self, pub_callback, sub_callback, event_callback=None,
                 persistence=False, persistence_file='mysensors.pickle',
                 protocol_version='1.4', in_prefix='', out_prefix='',
                 retain=True):
        """Setup MQTT client gateway."""
        threading.Thread.__init__(self)
        # Should accept topic, payload, qos, retain.
        self._pub_callback = pub_callback
        # Should accept topic, function callback for receive and qos.
        self._sub_callback = sub_callback
        self._in_prefix = in_prefix  # prefix for topics gw -> controller
        self._out_prefix = out_prefix  # prefix for topics controller -> gw
        self._retain = retain  # flag to publish with retain
        self._stop_event = threading.Event()
        # topic structure:
        # prefix/node/child/type/ack/subtype : payload
        Gateway.__init__(self, event_callback, persistence,
                         persistence_file, protocol_version)

    def _handle_subscription(self, topics):
        """Handle subscription of topics."""
        if not isinstance(topics, list):
            topics = [topics]
        for topic in topics:
            topic_levels = topic.split('/')
            try:
                qos = int(topic_levels[4])
            except ValueError:
                qos = 0
            try:
                _LOGGER.debug('Subscribing to: %s', topic)
                self._sub_callback(topic, self.recv, qos)
            except Exception as exception:  # pylint: disable=W0703
                _LOGGER.exception(
                    'Subscribe to %s failed: %s', topic, exception)

    def _init_topics(self):
        """Setup initial subscription of mysensors topics."""
        _LOGGER.info('Setting up initial MQTT topic subscription')
        init_topics = [
            '{}/+/+/0/+/+'.format(self._in_prefix),
            '{}/+/+/3/+/+'.format(self._in_prefix),
        ]
        self._handle_subscription(init_topics)

    def _parse_mqtt_to_message(self, topic, payload, qos):
        """Parse a MQTT topic and payload.

        Return a mysensors command string.
        """
        topic_levels = topic.split('/')
        prefix = topic_levels.pop(0)
        if prefix != self._in_prefix:
            return
        if qos and qos > 0:
            ack = '1'
        else:
            ack = '0'
        topic_levels[3] = ack
        topic_levels.append(str(payload))
        return ';'.join(topic_levels)

    def _parse_message_to_mqtt(self, data):
        """Parse a mysensors command string.

        Return a MQTT topic, payload and qos-level as a tuple.
        """
        msg = Message(data)
        payload = str(msg.payload)
        msg.payload = ''
        # prefix/node/child/type/ack/subtype : payload
        return ('{}/{}'.format(self._out_prefix, msg.encode('/'))[:-2],
                payload, msg.ack)

    def _handle_presentation(self, msg):
        """Process a MQTT presentation message."""
        ret_msg = super()._handle_presentation(msg)
        if msg.child_id == 255 or ret_msg is None:
            return
        # this is a presentation of a child sensor
        topics = [
            '{}/{}/{}/{}/+/+'.format(
                self._in_prefix, str(msg.node_id), str(msg.child_id),
                msg_type)
            for msg_type in (int(self.const.MessageType.set),
                             int(self.const.MessageType.req))
        ]
        topics.append('{}/{}/+/{}/+/+'.format(
            self._in_prefix, str(msg.node_id),
            int(self.const.MessageType.stream)))
        self._handle_subscription(topics)

    def _safe_load_sensors(self):
        """Load MQTT sensors safely from file."""
        super()._safe_load_sensors()
        topics = [
            '{}/{}/{}/{}/+/+'.format(
                self._in_prefix, str(sensor.sensor_id), str(child.id),
                msg_type) for sensor in self.sensors.values()
            for child in sensor.children.values()
            for msg_type in (int(self.const.MessageType.set),
                             int(self.const.MessageType.req))
        ]
        topics.extend([
            '{}/{}/+/{}/+/+'.format(
                self._in_prefix, str(sensor.sensor_id),
                int(self.const.MessageType.stream))
            for sensor in self.sensors.values()])
        self._handle_subscription(topics)

    def recv(self, topic, payload, qos):
        """Receive a MQTT message.

        Call this method when a message is received from the MQTT broker.
        """
        data = self._parse_mqtt_to_message(topic, payload, qos)
        if data is None:
            return
        _LOGGER.debug('Receiving %s', data)
        self.fill_queue(self.logic, (data,))

    def send(self, message):
        """Publish a command string to the gateway via MQTT."""
        if not message:
            return
        topic, payload, qos = self._parse_message_to_mqtt(message)
        with self.lock:
            try:
                _LOGGER.debug('Publishing %s', message)
                self._pub_callback(topic, payload, qos, self._retain)
            except Exception as exception:  # pylint: disable=W0703
                _LOGGER.exception('Publish to %s failed: %s', topic, exception)

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info('Stopping thread')
        self._stop_event.set()

    def run(self):
        """Background thread that sends messages to the gateway via MQTT."""
        self._init_topics()
        while not self._stop_event.is_set():
            response = self.handle_queue()
            if response is not None:
                self.send(response)
            if not self.queue.empty():
                continue
            time.sleep(0.02)  # short sleep to avoid burning 100% cpu


class Sensor:
    """Represent a sensor."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, sensor_id):
        """Setup sensor."""
        self.sensor_id = sensor_id
        self.children = {}
        self.type = None
        self.sketch_name = None
        self.sketch_version = None
        self.battery_level = 0
        self.protocol_version = None
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

    def __setstate__(self, state):
        """Set state when loading pickle."""
        # Restore instance attributes
        self.__dict__.update(state)
        # Reset some attributes
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

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
        msg_string = Message().copy(
            node_id=self.sensor_id, child_id=child_id, type=msg_type, ack=ack,
            sub_type=value_type, payload=value).encode()
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
        children[child_id].values[value_type] = msg.payload
        return msg_string


class ChildSensor:
    """Represent a child sensor."""

    # pylint: disable=too-few-public-methods

    def __init__(self, child_id, child_type, description=''):
        """Setup child sensor."""
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


class Message:
    """Represent a message from the gateway."""

    def __init__(self, data=None):
        """Setup message."""
        self.node_id = 0
        self.child_id = 0
        self.type = 0
        self.ack = 0
        self.sub_type = 0
        self.payload = ''  # All data except payload are integers
        if data is not None:
            self.decode(data)

    def copy(self, **kwargs):
        """Copy a message, optionally replace attributes with kwargs."""
        msg = Message(self.encode())
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg

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

    def default(self, obj):  # pylint: disable=E0202
        """Serialize obj into JSON."""
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
        """Setup decoder."""
        json.JSONDecoder.__init__(self, object_hook=self.dict_to_object)

    def dict_to_object(self, obj):  # pylint: disable=no-self-use
        """Return object from dict."""
        if not isinstance(obj, dict):
            return obj
        if 'sensor_id' in obj:
            sensor = Sensor(obj['sensor_id'])
            sensor.__dict__.update(obj)
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
