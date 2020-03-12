"""Implement a TCP gateway."""
import asyncio
import ipaddress
import logging
import select
import socket
import time

import serial.threaded
from getmac import get_mac_address

from mysensors import BaseAsyncGateway, BaseSyncGateway, Gateway, Message
from .transport import AsyncTransport, BaseMySensorsProtocol, SyncTransport

_LOGGER = logging.getLogger(__name__)


class BaseTCPGateway(Gateway):
    """MySensors base TCP gateway."""

    def __init__(self, host, port=5003, **kwargs):
        """Set up base TCP gateway."""
        super().__init__(**kwargs)
        self.server_address = (host, port)
        self.tcp_check_timer = time.time()
        self.tcp_disconnect_timer = time.time()
        self.const.Internal.I_VERSION.set_handler(self.handlers, self._handle_i_version)

    def check_connection(self):
        """Check if connection is alive every reconnect_timeout seconds."""
        if (
            self.tcp_disconnect_timer + 2 * self.tasks.transport.reconnect_timeout
        ) < time.time():
            self.tcp_disconnect_timer = time.time()
            raise OSError(
                "No response from {}. Disconnecting".format(self.server_address)
            )
        if (
            self.tcp_check_timer + self.tasks.transport.reconnect_timeout
        ) >= time.time():
            return
        msg = Message().modify(
            child_id=255,
            type=self.const.MessageType.internal,
            sub_type=self.const.Internal.I_VERSION,
        )
        self.tasks.add_job(msg.encode)
        self.tcp_check_timer = time.time()

    def _handle_i_version(self, msg):  # pylint: disable=useless-return
        # pylint: disable=unused-argument
        self.tcp_disconnect_timer = time.time()
        return None

    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        host, _ = self.server_address
        try:
            ip_address = ipaddress.ip_address(host)
        except ValueError:
            # Only hosts using ip address supports unique id.
            return None
        if ip_address.version == 6:
            mac = get_mac_address(ip6=host)
        else:
            mac = get_mac_address(ip=host)
        return mac


class TCPGateway(BaseSyncGateway, BaseTCPGateway):
    """MySensors TCP gateway."""

    def __init__(self, *args, **kwargs):
        """Set up TCP gateway."""
        transport = SyncTransport(self, sync_connect, **kwargs)
        super().__init__(transport, *args, **kwargs)


def sync_connect(transport):
    """Connect to socket. This should be run in a new thread."""
    while transport.protocol:
        _LOGGER.info("Trying to connect to %s", transport.gateway.server_address)
        try:
            sock = socket.create_connection(
                transport.gateway.server_address, transport.reconnect_timeout
            )
        except socket.timeout:
            _LOGGER.error(
                "Connecting to socket timed out for %s",
                transport.gateway.server_address,
            )
            _LOGGER.info(
                "Waiting %s secs before trying to connect again",
                transport.reconnect_timeout,
            )
            time.sleep(transport.reconnect_timeout)
        except OSError:
            _LOGGER.error(
                "Failed to connect to socket at %s", transport.gateway.server_address
            )
            _LOGGER.info(
                "Waiting %s secs before trying to connect again",
                transport.reconnect_timeout,
            )
            time.sleep(transport.reconnect_timeout)
        else:
            transport.gateway.tcp_check_timer = time.time()
            transport.gateway.tcp_disconnect_timer = time.time()
            tcp_transport = TCPTransport(
                sock, lambda: transport.protocol, transport.gateway.check_connection
            )
            tcp_transport.start()
            tcp_transport.connect()
            return


class AsyncTCPGateway(BaseAsyncGateway, BaseTCPGateway):
    """MySensors async TCP gateway."""

    def __init__(self, *args, loop=None, **kwargs):
        """Set up TCP gateway."""
        self.cancel_check_conn = None
        protocol = AsyncTCPMySensorsProtocol
        transport = AsyncTransport(
            self, async_connect, loop=loop, protocol=protocol, **kwargs
        )
        super().__init__(transport, *args, loop=loop, **kwargs)

    def check_connection(self):
        """Check if connection is alive every reconnect_timeout seconds."""
        try:
            super().check_connection()
        except OSError as exc:
            _LOGGER.error(exc)
            self.tasks.transport.protocol.transport.close()
            self.tasks.transport.protocol.conn_lost_callback()
            return
        task = self.tasks.loop.call_later(
            self.tasks.transport.reconnect_timeout + 0.1, self.check_connection
        )
        self.cancel_check_conn = task.cancel

    async def get_gateway_id(self):
        """Return a unique id for the gateway."""
        mac = await self.tasks.loop.run_in_executor(None, super().get_gateway_id)
        return mac


async def async_connect(transport):
    """Connect to the socket."""
    try:
        while True:
            _LOGGER.info("Trying to connect to %s", transport.gateway.server_address)
            try:
                await asyncio.wait_for(
                    transport.loop.create_connection(
                        lambda: transport.protocol, *transport.gateway.server_address
                    ),
                    transport.reconnect_timeout,
                    loop=transport.loop,
                )
                transport.gateway.tcp_check_timer = time.time()
                transport.gateway.tcp_disconnect_timer = time.time()
                transport.gateway.check_connection()
                return
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "Connecting to socket timed out for %s",
                    transport.gateway.server_address,
                )
                _LOGGER.info(
                    "Waiting %s secs before trying to connect again",
                    transport.reconnect_timeout,
                )
                await asyncio.sleep(transport.reconnect_timeout, loop=transport.loop)
            except OSError:
                _LOGGER.error(
                    "Failed to connect to socket at %s",
                    transport.gateway.server_address,
                )
                _LOGGER.info(
                    "Waiting %s secs before trying to connect again",
                    transport.reconnect_timeout,
                )
                await asyncio.sleep(transport.reconnect_timeout, loop=transport.loop)
    except asyncio.CancelledError:
        _LOGGER.debug(
            "Connect attempt to %s cancelled", transport.gateway.server_address
        )


class AsyncTCPMySensorsProtocol(BaseMySensorsProtocol, asyncio.Protocol):
    """Async TCP protocol class."""

    def connection_lost(self, exc):
        """Handle lost connection."""
        _LOGGER.debug("Connection lost with %s", self.transport)
        if self.gateway.cancel_check_conn:
            self.gateway.cancel_check_conn()
            self.gateway.cancel_check_conn = None
        if exc:
            _LOGGER.error(exc)
            self.conn_lost_callback()
        self.transport = None


class TCPTransport(serial.threaded.ReaderThread):
    """Transport for TCP gateway."""

    def __init__(self, sock, protocol_factory, check_conn):
        """Set up transport."""
        super().__init__(sock, protocol_factory)
        self.sock = sock
        # make socket non blocking
        self.sock.setblocking(False)
        self._check_connection = check_conn

    def _check_socket(self, timeout=None):
        """Check if socket is readable/writable."""
        sock = self.sock
        available_socks = select.select([sock], [sock], [sock], timeout)
        if available_socks[2]:
            raise OSError
        return available_socks

    def write(self, data):
        """Write data to the socket."""
        with self._lock:
            self.sock.sendall(data)

    def run(self):
        """Transport thread loop."""
        # pylint: disable=broad-except
        self.protocol = self.protocol_factory()
        try:
            self.protocol.connection_made(self)
        except Exception as exc:
            self.alive = False
            self.protocol.connection_lost(exc)
            self._connection_made.set()
            return
        error = None
        self._connection_made.set()
        while self.alive:
            data = None
            try:
                available_socks = self._check_socket()
                if available_socks[0]:
                    data = self.sock.recv(120)
            except Exception as exc:
                error = exc
                break
            else:
                if data:
                    try:
                        self.protocol.data_received(data)
                    except Exception as exc:
                        error = exc
                        break
            try:
                self._check_connection()
            except OSError as exc:
                error = exc
                break
            time.sleep(0.02)  # short sleep to avoid burning 100% cpu
        self.alive = False
        self.protocol.connection_lost(error)
        self.protocol = None
