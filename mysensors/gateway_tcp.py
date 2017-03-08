"""Implement a TCP gateway."""
import logging
import select
import socket
import threading
import time

from mysensors import Gateway, Message

_LOGGER = logging.getLogger(__name__)


class TCPGateway(Gateway, threading.Thread):
    """MySensors TCP ethernet gateway."""

    # pylint: disable=too-many-arguments

    def __init__(self, host, event_callback=None,
                 persistence=False, persistence_file='mysensors.pickle',
                 protocol_version='1.4', port=5003, timeout=1.0,
                 reconnect_timeout=10.0):
        """Setup TCP ethernet gateway."""
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback, persistence,
                         persistence_file, protocol_version)
        self.sock = None
        self.server_address = (host, port)
        self.timeout = timeout
        self.tcp_check_timer = time.time()
        self.tcp_disconnect_timer = time.time()
        self.reconnect_timeout = reconnect_timeout
        self._stop_event = threading.Event()

    def _check_connection(self):
        """Check if connection is alive every reconnect_timeout seconds."""
        if ((self.tcp_disconnect_timer + 2 * self.reconnect_timeout) <
                time.time()):
            self.tcp_disconnect_timer = time.time()
            self.disconnect()
            _LOGGER.info('No response. Disconnected.')
            return
        if not (self.tcp_check_timer + self.reconnect_timeout) < time.time():
            return
        msg = Message().copy(
            child_id=255, type=self.const.MessageType.internal,
            sub_type=self.const.Internal.I_VERSION)
        self.fill_queue(msg.encode)
        self.tcp_check_timer = time.time()

    def _handle_internal(self, msg):
        if msg.sub_type == self.const.Internal.I_VERSION:
            self.tcp_disconnect_timer = time.time()
        else:
            return super()._handle_internal(msg)

    def connect(self):
        """Connect to the socket object, on host and port."""
        if self.sock:
            _LOGGER.info('Already connected to %s', self.sock)
            return True
        try:
            # Connect to the server at the port
            _LOGGER.info(
                'Trying to connect to %s', self.server_address)
            self.sock = socket.create_connection(
                self.server_address, self.reconnect_timeout)
            _LOGGER.info('Connected to %s', self.server_address)
            return True

        except TimeoutError:
            _LOGGER.error(
                'Connecting to socket timed out for %s.', self.server_address)
            return False
        except OSError:
            _LOGGER.error(
                'Failed to connect to socket at %s.', self.server_address)
            return False

    def disconnect(self):
        """Close the socket."""
        if not self.sock:
            return
        _LOGGER.info('Closing socket at %s.', self.server_address)
        try:
            self.sock.shutdown(socket.SHUT_WR)
        except OSError:
            _LOGGER.error('Failed to shutdown socket at %s.',
                          self.server_address)
        self.sock.close()
        self.sock = None
        _LOGGER.info('Socket closed at %s.', self.server_address)

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info('Stopping thread')
        self._stop_event.set()

    def _check_socket(self, sock=None, timeout=None):
        """Check if socket is readable/writable."""
        if sock is None:
            sock = self.sock
        available_socks = select.select([sock], [sock], [sock], timeout)
        if available_socks[2]:
            raise OSError
        return available_socks

    def recv_timeout(self):
        """Receive reply from server, with a timeout."""
        # make socket non blocking
        self.sock.setblocking(False)
        # total data in an array
        total_data = []
        data_string = ''
        joined_data = ''
        # start time
        begin = time.time()

        while not data_string.endswith('\n'):
            data_string = ''
            # break after timeout
            if time.time() - begin > self.timeout:
                break
            # receive data
            try:
                # Buffer size from gateway should be 120 bytes
                # according to mysensors ethernet gateway util.
                data_bytes = self.sock.recv(120)
                if data_bytes:
                    data_string = data_bytes.decode('utf-8')
                    _LOGGER.debug('Received %s', data_string)
                    total_data.append(data_string)
                    # reset start time
                    begin = time.time()
                    # join all data to final data
                    joined_data = ''.join(total_data)
                else:
                    # sleep to add time difference
                    time.sleep(0.1)
            except OSError:
                _LOGGER.error('Receive from server failed.')
                self.disconnect()
                break
            except ValueError:
                _LOGGER.warning(
                    'Error decoding message from gateway, '
                    'probably received bad byte.')
                break

        return joined_data

    def send(self, message):
        """Write a command string to the gateway via the socket."""
        if not message:
            return
        with self.lock:
            try:
                # Send data
                _LOGGER.debug('Sending %s', message)
                self.sock.sendall(message.encode())

            except OSError:
                # Send failed
                _LOGGER.error('Send to server failed.')
                self.disconnect()

    def run(self):
        """Background thread that reads messages from the gateway."""
        while not self._stop_event.is_set():
            if self.sock is None and not self.connect():
                _LOGGER.info('Waiting 10 secs before trying to connect again.')
                time.sleep(self.reconnect_timeout)
                continue
            try:
                available_socks = self._check_socket()
            except OSError:
                _LOGGER.error('Server socket %s has an error.', self.sock)
                self.disconnect()
                continue
            if available_socks[1] and self.sock is not None:
                response = self.handle_queue()
                if response is not None:
                    self.send(response)
            if not self.queue.empty():
                continue
            time.sleep(0.02)  # short sleep to avoid burning 100% cpu
            if available_socks[0] and self.sock is not None:
                string = self.recv_timeout()
                lines = string.split('\n')
                # Throw away last empty line or uncompleted message.
                del lines[-1]
                for line in lines:
                    self.fill_queue(self.logic, (line,))
            self._check_connection()
        self.disconnect()
