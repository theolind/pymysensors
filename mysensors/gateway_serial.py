"""Implement a serial gateway."""
import asyncio
import io
import logging
import time
from functools import partial

import serial
import serial_asyncio

from mysensors import Gateway, ThreadingGateway
from .ota import load_fw

try:
    from asyncio import ensure_future  # pylint: disable=ungrouped-imports
except ImportError:
    # Python 3.4.3 and earlier has this as async
    # pylint: disable=unused-import
    from asyncio import async  # pylint: disable=ungrouped-imports
    ensure_future = async

_LOGGER = logging.getLogger(__name__)


class BaseSerialGateway(Gateway):
    """Base class for serial gateways."""

    # pylint: disable=too-many-arguments, abstract-method

    def __init__(
            self, port, baud=115200, timeout=1.0, reconnect_timeout=10.0,
            **kwargs):
        """Set up base serial gateway."""
        super().__init__(**kwargs)
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout


class SerialGateway(BaseSerialGateway, ThreadingGateway):
    """Serial gateway for MySensors."""

    def __init__(self, *args, **kwargs):
        """Set up serial gateway."""
        super().__init__(*args, **kwargs)
        self.serial = None

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

    def send(self, message):
        """Write a Message to the gateway."""
        if not message:
            return
        # Lock to make sure only one thread writes at a time to serial port.
        with self.lock:
            self.serial.write(message.encode())

    def run(self):
        """Background thread that reads messages from the gateway."""
        while not self._stop_event.is_set():
            if self.serial is None and not self.connect():
                time.sleep(self.reconnect_timeout)
                continue
            response = self.run_job()
            if response is not None:
                self.send(response)
            if self.queue:
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
            self.add_job(self.logic, string)
        self.disconnect()  # Disconnect after stop event is set


class AsyncSerialGateway(BaseSerialGateway):
    """Serial gateway for MySensors using asyncio."""

    def __init__(self, *args, loop=None, **kwargs):
        """Set up async serial gateway."""
        super().__init__(
            *args, persistence_scheduler=self.create_scheduler, **kwargs)
        self.loop = loop or asyncio.get_event_loop()

        def conn_lost():
            """Handle connection_lost in protocol class."""
            # pylint: disable=deprecated-method
            ensure_future(self.connect(), loop=self.loop)

        self.protocol = AsyncSerialProtocol(self, conn_lost)
        self._cancel_save = None

    @asyncio.coroutine
    def connect(self):
        """Connect to the serial port."""
        try:
            while self.loop.is_running() and self.protocol:
                _LOGGER.info('Trying to connect to %s', self.port)
                try:
                    yield from serial_asyncio.create_serial_connection(
                        self.loop, lambda: self.protocol, self.port, self.baud)
                    return
                except serial.SerialException:
                    _LOGGER.error('Unable to connect to %s', self.port)
                    yield from asyncio.sleep(
                        self.reconnect_timeout, loop=self.loop)
        except asyncio.CancelledError:
            _LOGGER.debug('Connect attempt to %s cancelled', self.port)

    @asyncio.coroutine
    def start(self):
        """Start the connection to a serial port."""
        yield from self.connect()

    def disconnect(self):
        """Disconnect from the serial port."""
        if self.protocol.transport:
            name = self.protocol.transport.serial.name
            _LOGGER.info('Disconnecting from %s', name)
            self.protocol.transport.close()
            _LOGGER.info('Disconnected from %s', name)

    @asyncio.coroutine
    def stop(self):
        """Stop the gateway."""
        _LOGGER.info('Stopping gateway')
        self.disconnect()
        self.protocol = None
        if not self.persistence:
            return
        if self._cancel_save is not None:
            self._cancel_save()
            self._cancel_save = None
        yield from self.loop.run_in_executor(
            None, self.persistence.save_sensors)

    def send(self, message):
        """Write a command string to the gateway."""
        if not message:
            return
        _LOGGER.debug('Sending %s', message)
        self.protocol.transport.write(message.encode())

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

    def create_scheduler(self, save_sensors):
        """Return function to schedule saving sensors."""
        @asyncio.coroutine
        def schedule_save():
            """Return a function to cancel the schedule."""
            yield from self.loop.run_in_executor(None, save_sensors)
            callback = partial(
                ensure_future, schedule_save(), loop=self.loop)
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


class AsyncSerialProtocol(asyncio.Protocol):
    """Async serial protocol."""

    def __init__(self, gateway, conn_lost_callback):
        """Set up async protocol."""
        self.transport = None
        self.gateway = gateway
        self.conn_lost_callback = conn_lost_callback
        self._buffer = io.StringIO()

    def connection_made(self, transport):
        """Handle a created connection."""
        self.transport = transport
        self.transport.serial.rts = False
        if self.transport.serial.is_open:
            _LOGGER.info('%s is open...', self.transport.serial.name)
            _LOGGER.info('Connected to %s', self.transport.serial.name)

    def data_received(self, data):
        """Handle received data."""
        try:
            self._buffer.write(data.decode('utf-8'))
        except ValueError:
            _LOGGER.warning(
                'Error decoding message from gateway, '
                'probably received bad byte.')
            return
        if '\n' not in self._buffer.getvalue():
            return
        self._buffer.seek(0)
        while True:
            line = self._buffer.readline()
            if '\n' not in line:
                self._buffer = io.StringIO()
                self._buffer.write(line)
                break
            _LOGGER.debug('Receiving %s', line)
            self.gateway.add_job(self.gateway.logic, line)

    def connection_lost(self, exc):
        """Handle a lost connection."""
        if exc is not None:
            _LOGGER.error(exc)
            self.conn_lost_callback()
        self.transport = None
