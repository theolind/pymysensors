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
        transport = SyncTransport(self, sync_connect, **kwargs)
        super().__init__(transport, *args, **kwargs)


def sync_connect(transport):
    """Connect to the serial port.

    This should be run in a new thread.
    """
    while transport.protocol:
        _LOGGER.info("Trying to connect to %s", transport.gateway.port)
        try:
            ser = serial.serial_for_url(
                transport.gateway.port,
                transport.gateway.baud,
                timeout=transport.timeout,
            )
        except serial.SerialException:
            _LOGGER.error("Unable to connect to %s", transport.gateway.port)
            _LOGGER.info(
                "Waiting %s secs before trying to connect again",
                transport.reconnect_timeout,
            )
            time.sleep(transport.reconnect_timeout)
        else:
            serial_transport = serial.threaded.ReaderThread(
                ser, lambda: transport.protocol
            )
            serial_transport.daemon = False
            serial_transport.start()
            serial_transport.connect()
            return


class AsyncSerialGateway(BaseAsyncGateway, BaseSerialGateway):
    """MySensors async serial gateway."""

    def __init__(self, *args, loop=None, **kwargs):
        """Set up serial gateway."""
        transport = AsyncTransport(self, async_connect, loop=loop, **kwargs)
        super().__init__(transport, *args, loop=loop, **kwargs)

    async def get_gateway_id(self):
        """Return a unique id for the gateway."""
        serial_number = await self.tasks.loop.run_in_executor(
            None, super().get_gateway_id
        )
        return serial_number


async def async_connect(transport):
    """Connect to the serial port."""
    try:
        while True:
            _LOGGER.info("Trying to connect to %s", transport.gateway.port)
            try:
                await serial_asyncio.create_serial_connection(
                    transport.loop,
                    lambda: transport.protocol,
                    transport.gateway.port,
                    transport.gateway.baud,
                )
                return
            except serial.SerialException:
                _LOGGER.error("Unable to connect to %s", transport.gateway.port)
                _LOGGER.info(
                    "Waiting %s secs before trying to connect again",
                    transport.reconnect_timeout,
                )
                await asyncio.sleep(transport.reconnect_timeout, loop=transport.loop)
    except asyncio.CancelledError:
        _LOGGER.debug("Connect attempt to %s cancelled", transport.gateway.port)
