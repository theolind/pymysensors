"""Python implementation of MySensors API."""
import calendar
import logging
import threading
import time
# pylint: disable=no-name-in-module, import-error
from distutils.version import LooseVersion as parse_ver
from queue import Queue
from timeit import default_timer as timer

import voluptuous as vol

from .const import get_const
from .message import SYSTEM_CHILD_ID, Message
from .ota import OTAFirmware
from .persistence import Persistence
from .sensor import ChildSensor, Sensor
from .validation import safe_is_version
from .version import __version__  # noqa: F401

_LOGGER = logging.getLogger(__name__)


class Gateway(object):
    """Base implementation for a MySensors Gateway."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    def __init__(self, event_callback=None, persistence=False,
                 persistence_file='mysensors.pickle',
                 persistence_scheduler=None, protocol_version='1.4'):
        """Set up Gateway."""
        self.queue = Queue()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True  # if true - use metric, if false - use imperial
        if persistence:
            self.persistence = Persistence(
                self.sensors, persistence_file, persistence_scheduler)
        else:
            self.persistence = None
        self.protocol_version = safe_is_version(protocol_version)
        self.const = get_const(self.protocol_version)
        self.ota = OTAFirmware(self.sensors, self.const)

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

    def _handle_smartsleep(self, msg):
        """Process a message before going back to smartsleep."""
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
        actions = self.const.HANDLE_INTERNAL.get(msg.sub_type, {})
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

    def alert(self, msg):
        """Tell anyone who wants to know that a sensor was updated.

        Also save sensors if persistence is enabled.
        """
        if self.event_callback is not None:
            try:
                self.event_callback(msg)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(exception)

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
        smartsleep message is received, the internal state will be pushed to
        the sensor, via _handle_smartsleep method.
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


class ThreadingGateway(Gateway, threading.Thread):
    """Gateway that implements a new thread."""

    def __init__(self, **kwargs):
        """Set up gateway instance."""
        threading.Thread.__init__(self)
        Gateway.__init__(self, **kwargs)
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._cancel_save = None

    def send(self, message):
        """Implement this method in a child class."""
        raise NotImplementedError

    def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        if not self.persistence:
            return
        self.persistence.safe_load_sensors()
        self._cancel_save = self.persistence.schedule_save_sensors()

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info('Stopping thread')
        self._stop_event.set()
        if not self.persistence:
            return
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None
        self.persistence.save_sensors()
