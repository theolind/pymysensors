"""Implement a serial gateway."""
import asyncio
import logging
import time

import serial
import serial.threaded
import serial.tools.list_ports
import serial_asyncio

from mysensors import BaseSyncGateway, BaseAsyncGateway, Gateway
from .transport import AsyncTransport, SyncTransport

_LOGGER = logging.getLogger(__name__)


class BaseSerialGateway(Gateway):
    """MySensors base serial gateway."""

    def __init__(self, port, baud=115200, **kwargs):
        """Set up base serial gateway."""
        super().__init__(**kwargs)
        self.port = port
        self.baud = baud

    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        info = next(serial.tools.list_ports.grep(self.port), None)
        return info.serial_number if info is not None else None


class SerialGateway(BaseSyncGateway, BaseSerialGateway):
    """MySensors serial gateway."""

    def __init__(self, *args, **kwargs):
        """Set up serial gateway."""
        transport = SerialSyncTransport(self, **kwargs)
        super().__init__(transport, *args, **kwargs)


class SerialSyncTransport(SyncTransport):
    """Serial sync version of transport class."""

    def _connect(self):
        """Connect to the serial port. This should be run in a new thread."""
        while self.protocol:
            _LOGGER.info('Trying to connect to %s', self.gateway.port)
            try:
                ser = serial.serial_for_url(
                    self.gateway.port, self.gateway.baud, timeout=self.timeout)
            except serial.SerialException:
                _LOGGER.error('Unable to connect to %s', self.gateway.port)
                _LOGGER.info(
                    'Waiting %s secs before trying to connect again',
                    self.reconnect_timeout)
                time.sleep(self.reconnect_timeout)
            else:
                transport = serial.threaded.ReaderThread(
                    ser, lambda: self.protocol)
                transport.daemon = False
                transport.start()
                transport.connect()
                return


class AsyncSerialGateway(BaseAsyncGateway, BaseSerialGateway):
    """MySensors async serial gateway."""

    def __init__(self, *args, loop=None, **kwargs):
        """Set up serial gateway."""
        transport = SerialAsyncTransport(self, loop=loop, **kwargs)
        super().__init__(transport, *args, loop=loop, **kwargs)

    @asyncio.coroutine
    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        serial_number = yield from self.tasks.loop.run_in_executor(
            None, super().get_gateway_id)
        return serial_number


class SerialAsyncTransport(AsyncTransport):
    """Serial async version of transport class."""

    @asyncio.coroutine
    def connect(self):
        """Connect to the serial port."""
        try:
            while True:
                _LOGGER.info('Trying to connect to %s', self.gateway.port)
                try:
                    yield from serial_asyncio.create_serial_connection(
                        self.loop, lambda: self.protocol,
                        self.gateway.port, self.gateway.baud)
                    return
                except serial.SerialException:
                    _LOGGER.error('Unable to connect to %s', self.gateway.port)
                    _LOGGER.info(
                        'Waiting %s secs before trying to connect again',
                        self.reconnect_timeout)
                    yield from asyncio.sleep(
                        self.reconnect_timeout, loop=self.loop)
        except asyncio.CancelledError:
            _LOGGER.debug('Connect attempt to %s cancelled', self.gateway.port)
