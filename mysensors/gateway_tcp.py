"""Implement a TCP gateway."""
import asyncio
import ipaddress
import logging
import select
import socket
import threading
import time

import serial.threaded
from getmac import get_mac_address

from mysensors import (BaseAsyncGateway, BaseMySensorsProtocol,
                       BaseTransportGateway, Message, ThreadingGateway)

_LOGGER = logging.getLogger(__name__)


class BaseTCPGateway(BaseTransportGateway):
    """MySensors base TCP gateway."""

    # pylint: disable=abstract-method

    def __init__(self, host, port=5003, **kwargs):
        """Set up base TCP gateway."""
        super().__init__(**kwargs)
        self.server_address = (host, port)
        self.tcp_check_timer = time.time()
        self.tcp_disconnect_timer = time.time()
        self.const.Internal.I_VERSION.set_handler(
            self.handlers, self._handle_i_version)

    def _check_connection(self):
        """Check if connection is alive every reconnect_timeout seconds."""
        if ((self.tcp_disconnect_timer + 2 * self.reconnect_timeout) <
                time.time()):
            self.tcp_disconnect_timer = time.time()
            raise OSError('No response from {}. Disconnecting'.format(
                self.server_address))
        if (self.tcp_check_timer + self.reconnect_timeout) >= time.time():
            return
        msg = Message().modify(
            child_id=255, type=self.const.MessageType.internal,
            sub_type=self.const.Internal.I_VERSION)
        self.add_job(msg.encode)
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


class TCPGateway(BaseTCPGateway, ThreadingGateway):
    """MySensors TCP gateway."""

    def __init__(self, *args, **kwargs):
        """Set up TCP gateway."""
        super().__init__(*args, **kwargs)
        self.protocol = BaseMySensorsProtocol(self, self.start)

    def _connect(self):
        """Connect to socket. This should be run in a new thread."""
        while self.protocol:
            _LOGGER.info('Trying to connect to %s', self.server_address)
            try:
                sock = socket.create_connection(
                    self.server_address, self.reconnect_timeout)
            except socket.timeout:
                _LOGGER.error(
                    'Connecting to socket timed out for %s',
                    self.server_address)
                _LOGGER.info(
                    'Waiting %s secs before trying to connect again',
                    self.reconnect_timeout)
                time.sleep(self.reconnect_timeout)
            except OSError:
                _LOGGER.error(
                    'Failed to connect to socket at %s', self.server_address)
                _LOGGER.info(
                    'Waiting %s secs before trying to connect again',
                    self.reconnect_timeout)
                time.sleep(self.reconnect_timeout)
            else:
                self.tcp_check_timer = time.time()
                self.tcp_disconnect_timer = time.time()
                transport = TCPTransport(
                    sock, lambda: self.protocol, self._check_connection)
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


class AsyncTCPGateway(BaseTCPGateway, BaseAsyncGateway):
    """MySensors async TCP gateway."""

    def __init__(self, *args, **kwargs):
        """Set up async TCP gateway."""
        self.cancel_check_conn = None
        protocol = AsyncTCPMySensorsProtocol
        super().__init__(*args, protocol=protocol, **kwargs)

    @asyncio.coroutine
    def _connect(self):
        """Connect to the socket."""
        try:
            while True:
                _LOGGER.info('Trying to connect to %s', self.server_address)
                try:
                    yield from asyncio.wait_for(
                        self.loop.create_connection(
                            lambda: self.protocol, *self.server_address),
                        self.reconnect_timeout, loop=self.loop)
                    self.tcp_check_timer = time.time()
                    self.tcp_disconnect_timer = time.time()
                    self._check_connection()
                    return
                except asyncio.TimeoutError:
                    _LOGGER.error(
                        'Connecting to socket timed out for %s',
                        self.server_address)
                    _LOGGER.info(
                        'Waiting %s secs before trying to connect again',
                        self.reconnect_timeout)
                    yield from asyncio.sleep(
                        self.reconnect_timeout, loop=self.loop)
                except OSError:
                    _LOGGER.error(
                        'Failed to connect to socket at %s',
                        self.server_address)
                    _LOGGER.info(
                        'Waiting %s secs before trying to connect again',
                        self.reconnect_timeout)
                    yield from asyncio.sleep(
                        self.reconnect_timeout, loop=self.loop)
        except asyncio.CancelledError:
            _LOGGER.debug(
                'Connect attempt to %s cancelled', self.server_address)

    def _check_connection(self):
        """Check if connection is alive every reconnect_timeout seconds."""
        try:
            super()._check_connection()
        except OSError as exc:
            _LOGGER.error(exc)
            self.protocol.transport.close()
            self.protocol.conn_lost_callback()
            return
        task = self.loop.call_later(
            self.reconnect_timeout + 0.1, self._check_connection)
        self.cancel_check_conn = task.cancel

    @asyncio.coroutine
    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        mac = yield from self.loop.run_in_executor(
            None, super().get_gateway_id)
        return mac


class AsyncTCPMySensorsProtocol(BaseMySensorsProtocol, asyncio.Protocol):
    """Async TCP protocol class."""

    def connection_lost(self, exc):
        """Handle lost connection."""
        _LOGGER.debug('Connection lost with %s', self.transport)
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
