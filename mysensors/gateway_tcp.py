"""Implement a TCP gateway."""
import logging
import select
import socket
import threading
import time

import serial.threaded

from mysensors import (
    BaseMySensorsProtocol, BaseTransportGateway, ThreadingGateway, Message)

_LOGGER = logging.getLogger(__name__)


class TCPGateway(ThreadingGateway, BaseTransportGateway):
    """MySensors TCP ethernet gateway."""

    def __init__(self, host, port=5003, **kwargs):
        """Set up TCP gateway."""
        super().__init__(**kwargs)
        self.server_address = (host, port)
        self.tcp_check_timer = time.time()
        self.tcp_disconnect_timer = time.time()
        self.protocol = BaseMySensorsProtocol(self, self.start)

    def _check_connection(self):
        """Check if connection is alive every reconnect_timeout seconds."""
        if ((self.tcp_disconnect_timer + 2 * self.reconnect_timeout) <
                time.time()):
            self.tcp_disconnect_timer = time.time()
            raise OSError('No response from {}. Disconnecting'.format(
                self.server_address))
        if (self.tcp_check_timer + self.reconnect_timeout) >= time.time():
            return
        msg = Message().copy(
            child_id=255, type=self.const.MessageType.internal,
            sub_type=self.const.Internal.I_VERSION)
        self.add_job(msg.encode)
        self.tcp_check_timer = time.time()
        return

    def _handle_internal(self, msg):
        if msg.sub_type == self.const.Internal.I_VERSION:
            self.tcp_disconnect_timer = time.time()
            return None
        return super()._handle_internal(msg)

    def _connect(self):
        """Connect to socket. This should be run in a new thread."""
        while self.protocol:
            _LOGGER.info('Trying to connect to %s', self.server_address)
            try:
                sock = socket.create_connection(
                    self.server_address, self.reconnect_timeout)
            except TimeoutError:
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
