"""Implement a serial gateway."""
import asyncio
import logging
import threading
import time
from functools import partial

import serial
import serial.threaded
import serial_asyncio

from mysensors import (
    BaseMySensorsProtocol, BaseTransportGateway, ThreadingGateway)
from .ota import load_fw

try:
    from asyncio import ensure_future  # pylint: disable=ungrouped-imports
except ImportError:
    # Python 3.4.3 and earlier has this as async
    # pylint: disable=unused-import
    from asyncio import async  # pylint: disable=ungrouped-imports
    ensure_future = async

_LOGGER = logging.getLogger(__name__)


class AsyncSerialProtocol(BaseMySensorsProtocol, asyncio.Protocol):
    """Async serial protocol class."""


class BaseSerialGateway(BaseTransportGateway):
    """MySensors base serial gateway."""

    # pylint: disable=abstract-method

    def __init__(self, port, baud=115200, **kwargs):
        """Set up base serial gateway."""
        super().__init__(**kwargs)
        self.port = port
        self.baud = baud


class SerialGateway(ThreadingGateway, BaseSerialGateway):
    """MySensors serial gateway."""

    def __init__(self, *args, **kwargs):
        """Set up serial gateway."""
        super().__init__(*args, **kwargs)
        self.protocol = BaseMySensorsProtocol(self, self.start)

    def _connect(self):
        """Connect to the serial port. This should be run in a new thread."""
        while self.protocol:
            _LOGGER.info('Trying to connect to %s', self.port)
            try:
                ser = serial.serial_for_url(
                    self.port, self.baud, timeout=self.timeout)
            except serial.SerialException:
                _LOGGER.error('Unable to connect to %s', self.port)
                _LOGGER.info(
                    'Waiting %s secs before trying to connect again.',
                    self.reconnect_timeout)
                time.sleep(self.reconnect_timeout)
            else:
                transport = serial.threaded.ReaderThread(
                    ser, lambda: self.protocol)
                transport.daemon = False
                poll_thread = threading.Thread(target=self._poll_queue)
                self._stop_event.clear()
                poll_thread.start()
                transport.start()
                transport.connect()
                return

    def stop(self):
        """Stop the gateway."""
        _LOGGER.info('Stopping gateway')
        self._disconnect()
        super().stop()


class AsyncSerialGateway(BaseSerialGateway):
    """MySensors async serial gateway."""

    def __init__(self, *args, loop=None, **kwargs):
        """Set up async serial gateway."""
        super().__init__(
            *args, persistence_scheduler=self._create_scheduler, **kwargs)
        self.loop = loop or asyncio.get_event_loop()

        def conn_lost():
            """Handle connection_lost in protocol class."""
            # pylint: disable=deprecated-method
            ensure_future(self._connect(), loop=self.loop)

        self.protocol = AsyncSerialProtocol(self, conn_lost)
        self._cancel_save = None

    @asyncio.coroutine
    def _connect(self):
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
                    _LOGGER.info(
                        'Waiting %s secs before trying to connect again.',
                        self.reconnect_timeout)
                    yield from asyncio.sleep(
                        self.reconnect_timeout, loop=self.loop)
        except asyncio.CancelledError:
            _LOGGER.debug('Connect attempt to %s cancelled', self.port)

    @asyncio.coroutine
    def start(self):
        """Start the connection to a serial port."""
        yield from self._connect()

    @asyncio.coroutine
    def stop(self):
        """Stop the gateway."""
        _LOGGER.info('Stopping gateway')
        self._disconnect()
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
