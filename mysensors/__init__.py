"""Python implementation of MySensors API."""
import asyncio
import logging
import threading
import time
from collections import deque
# pylint: disable=no-name-in-module, import-error
from distutils.version import LooseVersion as parse_ver
from functools import partial
from timeit import default_timer as timer

import serial.threaded
import voluptuous as vol

from .const import SYSTEM_CHILD_ID, get_const
from .message import Message
from .ota import OTAFirmware, load_fw
from .persistence import Persistence
from .sensor import Sensor
from .validation import safe_is_version
from .version import __version__  # noqa: F401

_LOGGER = logging.getLogger(__name__)


class Gateway:
    """Base implementation for a MySensors Gateway."""

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    def __init__(self, event_callback=None, persistence=False,
                 persistence_file='mysensors.pickle',
                 persistence_scheduler=None, protocol_version='1.4'):
        """Set up Gateway."""
        super().__init__()
        self.queue = deque()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True  # if true - use metric, if false - use imperial
        if persistence:
            self.persistence = Persistence(
                self.sensors, persistence_scheduler, persistence_file)
        else:
            self.persistence = None
        self.protocol_version = safe_is_version(protocol_version)
        self.const = get_const(self.protocol_version)
        handlers = self.const.get_handler_registry()
        # Copy to allow safe modification.
        self.handlers = dict(handlers)
        self.ota = OTAFirmware(self.sensors, self.const)
        self.can_log = False

    def __repr__(self):
        """Return the representation."""
        return '<{}>'.format(self.__class__.__name__)

    def logic(self, data):
        """Parse the data and respond to it appropriately.

        Response is returned to the caller and has to be sent
        data as a mysensors command string.
        """
        try:
            msg = Message(data, self)
            msg.validate(self.protocol_version)
        except (ValueError, vol.Invalid) as exc:
            _LOGGER.warning('Not a valid message: %s', exc)
            return None

        message_type = self.const.MessageType(msg.type)
        handler = message_type.get_handler(self.handlers)
        ret = handler(msg)
        ret = self._route_message(ret)
        ret = ret.encode() if ret else None
        return ret

    def alert(self, msg):
        """Tell anyone who wants to know that a sensor was updated."""
        if self.event_callback is not None:
            try:
                self.event_callback(msg)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(exception)

        if self.persistence:
            self.persistence.need_save = True

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
        return sensorid if sensorid in self.sensors else None

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
                self.add_job(msg.encode)
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

    def run_job(self, job=None):
        """Run a job, either passed in or from the queue.

        A job is a tuple of function and optional args. Keyword arguments
        can be passed via use of functools.partial. The job should return a
        string that should be sent by the gateway protocol. The function will
        be called with the arguments and the result will be returned.
        """
        if job is None:
            if not self.queue:
                return None
            job = self.queue.popleft()
        start = timer()
        func, args = job
        reply = func(*args)
        end = timer()
        if end - start > 0.1:
            _LOGGER.debug(
                'Handle queue with call %s(%s) took %.3f seconds',
                func, args, end - start)
        return reply

    def add_job(self, func, *args):
        """Add a job that should return a reply to be sent.

        A job is a tuple of function and optional args. Keyword arguments
        can be passed via use of functools.partial. The job should return a
        string that should be sent by the gateway protocol.
        """
        self.queue.append((func, args))

    def set_child_value(
            self, sensor_id, child_id, value_type, value, **kwargs):
        """Add a command to set a sensor value, to the queue.

        A queued command will be sent to the sensor when the gateway
        thread has sent all previously queued commands.

        If the sensor attribute new_state returns True, the command will be
        buffered in a queue on the sensor, and only the internal sensor state
        will be updated. When a smartsleep message is received, the internal
        state will be pushed to the sensor, via _handle_smartsleep method.
        """
        if not self.is_sensor(sensor_id, child_id):
            return
        if self.sensors[sensor_id].new_state:
            self.sensors[sensor_id].set_child_value(
                child_id, value_type, value,
                children=self.sensors[sensor_id].new_state)
        else:
            self.add_job(partial(
                self.sensors[sensor_id].set_child_value, child_id, value_type,
                value, **kwargs))

    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        raise NotImplementedError

    def send(self, message):
        """Send a command string to the gateway.

        Implement this method in a child class.
        """
        raise NotImplementedError

    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare of all node_ids in nids.

        Implement this method in a child class.
        """
        raise NotImplementedError

    def start_persistence(self):
        """Load persistence file and schedule saving of persistence file.

        Implement this method in a child class.
        """
        raise NotImplementedError


class ThreadingGateway(Gateway):
    """Gateway that implements a new thread."""

    def __init__(self, *args, **kwargs):
        """Set up gateway instance."""
        super().__init__(
            *args, persistence_scheduler=self._create_scheduler, **kwargs)
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
        self._cancel_save = None

    def start(self):
        """Start the connection to a transport."""
        connect_thread = threading.Thread(target=self._connect)
        connect_thread.start()

    def _connect(self):
        raise NotImplementedError

    def _poll_queue(self):
        """Poll the queue for work."""
        while not self._stop_event.is_set():
            reply = self.run_job()
            self.send(reply)
            if self.queue:
                continue
            time.sleep(0.02)

    def _create_scheduler(self, save_sensors):
        """Return function to schedule saving sensors."""
        def schedule_save():
            """Save sensors and schedule a new save."""
            save_sensors()
            scheduler = threading.Timer(10.0, schedule_save)
            scheduler.start()
            self._cancel_save = scheduler.cancel
        return schedule_save

    def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        if not self.persistence:
            return
        self.persistence.safe_load_sensors()
        self.persistence.schedule_save_sensors()

    def stop(self):
        """Stop the background thread."""
        self._stop_event.set()
        if not self.persistence:
            return
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None
        self.persistence.save_sensors()

    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare of all node_ids in nids."""
        fw_bin = None
        if fw_path:
            fw_bin = load_fw(fw_path)
            if not fw_bin:
                return
        self.ota.make_update(nids, fw_type, fw_ver, fw_bin)


class BaseTransportGateway(Gateway):
    """MySensors base gateway for a transport."""

    # pylint: disable=abstract-method

    def __init__(self, timeout=1.0, reconnect_timeout=10.0, **kwargs):
        """Set up gateway."""
        super().__init__(**kwargs)
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout
        self.protocol = None

    def _disconnect(self):
        """Disconnect from the transport."""
        if not self.protocol or not self.protocol.transport:
            self.protocol = None  # Make sure protocol is None
            return
        _LOGGER.info('Disconnecting from gateway')
        self.protocol.transport.close()
        self.protocol = None

    def send(self, message):
        """Write a message to the gateway."""
        if not message or not self.protocol or not self.protocol.transport:
            return
        if not self.can_log:
            _LOGGER.debug('Sending %s', message.strip())
        try:
            self.protocol.transport.write(message.encode())
        except OSError as exc:
            _LOGGER.error(
                'Failed writing to transport %s: %s',
                self.protocol.transport, exc)
            self.protocol.transport.close()
            self.protocol.conn_lost_callback()


class BaseAsyncGateway(BaseTransportGateway):
    """MySensors base async gateway."""

    def __init__(self, *args, loop=None, protocol=None, **kwargs):
        """Set up async serial gateway."""
        super().__init__(
            *args, persistence_scheduler=self._create_scheduler, **kwargs)
        self.loop = loop or asyncio.get_event_loop()
        self.connect_task = None

        def conn_lost():
            """Handle connection_lost in protocol class."""
            # pylint: disable=deprecated-method
            self.connect_task = self.loop.create_task(self._connect())

        if not protocol:
            protocol = AsyncMySensorsProtocol
        self.protocol = protocol(self, conn_lost)
        self._cancel_save = None

    @asyncio.coroutine
    def _connect(self):
        """Connect to the transport."""
        raise NotImplementedError

    @asyncio.coroutine
    def start(self):
        """Start the connection to a transport."""
        yield from self._connect()

    @asyncio.coroutine
    def stop(self):
        """Stop the gateway."""
        _LOGGER.info('Stopping gateway')
        self._disconnect()
        if self.connect_task and not self.connect_task.cancelled():
            self.connect_task.cancel()
            self.connect_task = None
        if not self.persistence:
            return
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None
        yield from self.loop.run_in_executor(
            None, self.persistence.save_sensors)

    def add_job(self, func, *args):
        """Add a job that should return a reply to be sent.

        A job is a tuple of function and optional args. Keyword arguments
        can be passed via use of functools.partial. The job should return a
        string that should be sent by the gateway protocol.

        The async version of this method will send the reply directly.
        """
        job = func, args
        reply = self.run_job(job)
        self.send(reply)

    def _create_scheduler(self, save_sensors):
        """Return function to schedule saving sensors."""
        @asyncio.coroutine
        def schedule_save():
            """Save sensors and schedule a new save."""
            yield from self.loop.run_in_executor(None, save_sensors)
            callback = partial(self.loop.create_task, schedule_save())
            task = self.loop.call_later(10.0, callback)
            self._cancel_save = task.cancel
        return schedule_save

    @asyncio.coroutine
    def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        if not self.persistence:
            return
        yield from self.loop.run_in_executor(
            None, self.persistence.safe_load_sensors)
        yield from self.persistence.schedule_save_sensors()

    @asyncio.coroutine
    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Start update firwmare of all node_ids in nids in executor."""
        fw_bin = None
        if fw_path:
            fw_bin = yield from self.loop.run_in_executor(
                None, load_fw, fw_path)
            if not fw_bin:
                return
        self.ota.make_update(nids, fw_type, fw_ver, fw_bin)


class BaseMySensorsProtocol(serial.threaded.LineReader):
    """MySensors base protocol class."""

    TERMINATOR = b'\n'

    def __init__(self, gateway, conn_lost_callback):
        """Set up base protocol."""
        super().__init__()
        self.gateway = gateway
        self.conn_lost_callback = conn_lost_callback

    def __repr__(self):
        """Return the representation."""
        return '<{}>'.format(self.__class__.__name__)

    def connection_made(self, transport):
        """Handle created connection."""
        super().connection_made(transport)
        if hasattr(self.transport, 'serial'):
            _LOGGER.info('Connected to %s', self.transport.serial)
        else:
            _LOGGER.info('Connected to %s', self.transport)

    def handle_line(self, line):
        """Handle incoming string data one line at a time."""
        if not self.gateway.can_log:
            _LOGGER.debug('Receiving %s', line)
        self.gateway.add_job(self.gateway.logic, line)

    def connection_lost(self, exc):
        """Handle lost connection."""
        _LOGGER.debug('Connection lost with %s', self.transport.serial)
        if exc:
            _LOGGER.error(exc)
            self.transport.serial.close()
            self.conn_lost_callback()
        self.transport = None


class AsyncMySensorsProtocol(BaseMySensorsProtocol, asyncio.Protocol):
    """Async serial protocol class."""

    def connection_lost(self, exc):
        """Handle lost connection."""
        _LOGGER.debug('Connection lost with %s', self.transport)
        if exc:
            _LOGGER.error(exc)
            self.conn_lost_callback()
        self.transport = None
