"""Organize MySensors transports."""
import asyncio
import logging
import threading

import serial.threaded

_LOGGER = logging.getLogger(__name__)


class Transport:
    """Handle gateway transport.

    I/O is allowed in this class. This class should host methods that
    are related to the gateway transport type.
    """

    # pylint: disable=unused-argument

    def __init__(self, gateway, connect, timeout=1.0, reconnect_timeout=10.0, **kwargs):
        """Set up transport."""
        self._connect = connect
        self.can_log = False
        self.connect_task = None
        self.gateway = gateway
        self.protocol = None
        self.reconnect_timeout = reconnect_timeout
        self.timeout = timeout

    def connect(self):
        """Connect to the transport."""
        raise NotImplementedError

    def disconnect(self):
        """Disconnect from the transport."""
        if not self.protocol or not self.protocol.transport:
            self.protocol = None  # Make sure protocol is None
            return
        _LOGGER.info("Disconnecting from gateway")
        self.protocol.transport.close()
        self.protocol = None

    def send(self, message):
        """Write a message to the gateway."""
        if not message or not self.protocol or not self.protocol.transport:
            return
        if not self.can_log:
            _LOGGER.debug("Sending %s", message.strip())
        try:
            self.protocol.transport.write(message.encode())
        except OSError as exc:
            _LOGGER.error(
                "Failed writing to transport %s: %s", self.protocol.transport, exc
            )
            self.protocol.transport.close()
            self.protocol.conn_lost_callback()


class SyncTransport(Transport):
    """Sync version of transport class."""

    def __init__(self, *args, **kwargs):
        """Set up transport."""
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self.protocol = BaseMySensorsProtocol(self.gateway, self.connect)

    def connect(self):
        """Connect to the transport."""
        connect_thread = threading.Thread(target=self._connect, args=(self,))
        connect_thread.start()

    def send(self, message):
        """Write a message to the gateway."""
        with self._lock:
            super().send(message)


class AsyncTransport(Transport):
    """Async version of transport class."""

    def __init__(self, *args, loop=None, protocol=None, **kwargs):
        """Set up transport."""
        super().__init__(*args, **kwargs)
        self.loop = loop or asyncio.get_event_loop()

        def conn_lost():
            """Handle connection_lost in protocol class."""
            self.connect_task = self.loop.create_task(self.connect())

        if not protocol:
            protocol = AsyncMySensorsProtocol
        self.protocol = protocol(self.gateway, conn_lost)

    async def connect(self):
        """Connect to the transport."""
        await self._connect(self)


class BaseMySensorsProtocol(serial.threaded.LineReader):
    """MySensors base protocol class."""

    TERMINATOR = b"\n"

    def __init__(self, gateway, conn_lost_callback):
        """Set up base protocol."""
        super().__init__()
        self.gateway = gateway
        self.conn_lost_callback = conn_lost_callback

    def __repr__(self):
        """Return the representation."""
        return "<{}>".format(self.__class__.__name__)

    def connection_made(self, transport):
        """Handle created connection."""
        super().connection_made(transport)
        if hasattr(self.transport, "serial"):
            _LOGGER.info("Connected to %s", self.transport.serial)
        else:
            _LOGGER.info("Connected to %s", self.transport)
        self._connection_made()

    def handle_line(self, line):
        """Handle incoming string data one line at a time."""
        if not self.gateway.tasks.transport.can_log:
            _LOGGER.debug("Receiving %s", line)
        self.gateway.tasks.add_job(self.gateway.logic, line)

    def connection_lost(self, exc):
        """Handle lost connection."""
        _LOGGER.debug("Connection lost with %s", self.transport.serial)
        if exc:
            self.transport.serial.close()
        self._connection_lost(exc)

    def _connection_made(self):
        """Call connection made callbacks."""
        if self.gateway.on_conn_made is not None:
            self.gateway.on_conn_made(self.gateway)

    def _connection_lost(self, exc):
        """Call connection lost callbacks."""
        if self.gateway.on_conn_lost is not None:
            self.gateway.on_conn_lost(self.gateway, exc)
        if exc:
            _LOGGER.error(exc)
            self.conn_lost_callback()
        self.transport = None


class AsyncMySensorsProtocol(BaseMySensorsProtocol, asyncio.Protocol):
    """Async serial protocol class."""

    def connection_lost(self, exc):
        """Handle lost connection."""
        _LOGGER.debug("Connection lost with %s", self.transport)
        self._connection_lost(exc)
