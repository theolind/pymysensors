"""Implement a serial gateway."""
import asyncio
import logging
import threading
import time

import serial
import serial.threaded
import serial.tools.list_ports
import serial_asyncio

from mysensors import (
    BaseAsyncGateway, BaseMySensorsProtocol, BaseTransportGateway,
    ThreadingGateway)

_LOGGER = logging.getLogger(__name__)


class BaseSerialGateway(BaseTransportGateway):
    """MySensors base serial gateway."""

    # pylint: disable=abstract-method

    def __init__(self, port, baud=115200, **kwargs):
        """Set up base serial gateway."""
        super().__init__(**kwargs)
        self.port = port
        self.baud = baud

    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        info = next(serial.tools.list_ports.grep(self.port), None)
        return info.serial_number if info is not None else None


class SerialGateway(BaseSerialGateway, ThreadingGateway):
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
                    'Waiting %s secs before trying to connect again',
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


class AsyncSerialGateway(BaseSerialGateway, BaseAsyncGateway):
    """MySensors async serial gateway."""

    @asyncio.coroutine
    def _connect(self):
        """Connect to the serial port."""
        try:
            while True:
                _LOGGER.info('Trying to connect to %s', self.port)
                try:
                    yield from serial_asyncio.create_serial_connection(
                        self.loop, lambda: self.protocol, self.port, self.baud)
                    return
                except serial.SerialException:
                    _LOGGER.error('Unable to connect to %s', self.port)
                    _LOGGER.info(
                        'Waiting %s secs before trying to connect again',
                        self.reconnect_timeout)
                    yield from asyncio.sleep(
                        self.reconnect_timeout, loop=self.loop)
        except asyncio.CancelledError:
            _LOGGER.debug('Connect attempt to %s cancelled', self.port)

    @asyncio.coroutine
    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        serial_number = yield from self.loop.run_in_executor(
            None, super().get_gateway_id)
        return serial_number
