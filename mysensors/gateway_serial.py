"""Implement a serial gateway."""
import logging
import time

import serial

from mysensors import ThreadingGateway

_LOGGER = logging.getLogger(__name__)


class SerialGateway(ThreadingGateway):
    """Serial gateway for MySensors."""

    # pylint: disable=too-many-arguments

    def __init__(
            self, port, baud=115200, timeout=1.0, reconnect_timeout=10.0,
            **kwargs):
        """Set up serial gateway."""
        super().__init__(**kwargs)
        self.serial = None
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout

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

    def run(self):
        """Background thread that reads messages from the gateway."""
        while not self._stop_event.is_set():
            if self.serial is None and not self.connect():
                time.sleep(self.reconnect_timeout)
                continue
            response = self.handle_queue()
            if response is not None:
                self.send(response)
            if not self.queue.empty():
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
            self.fill_queue(self.logic, (string,))
        self.disconnect()  # Disconnect after stop event is set

    def send(self, message):
        """Write a command string to the gateway."""
        if not message:
            return
        # Lock to make sure only one thread writes at a time to serial port.
        with self.lock:
            self.serial.write(message.encode())
