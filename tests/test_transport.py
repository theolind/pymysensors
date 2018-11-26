"""Test the gateway transport."""
from unittest import mock

import pytest

from mysensors import Gateway
from mysensors.task import SyncTasks
from mysensors.transport import BaseMySensorsProtocol, Transport

# pylint: disable=redefined-outer-name


@pytest.fixture
def connection_transport():
    """Return a mock connection transport."""
    return mock.MagicMock()


@pytest.fixture
def reconnect_callback():
    """Return a mock reconnect callback."""
    return mock.MagicMock()


@pytest.fixture
def gateway(connection_transport, reconnect_callback):
    """Return gateway instance."""
    _gateway = Gateway()
    protocol = BaseMySensorsProtocol(_gateway, reconnect_callback)

    def connect():
        """Connect to device."""
        protocol.connection_made(connection_transport)

    transport = Transport(gateway, connect)
    transport.connect = connect
    transport.protocol = protocol
    _gateway.tasks = SyncTasks(
        _gateway.const, False, None, _gateway.sensors, transport)
    return _gateway


def test_connection_made(gateway, connection_transport):
    """Test connection is made."""
    assert gateway.tasks.transport.protocol.transport is None
    gateway.tasks.transport.connect()
    assert gateway.tasks.transport.protocol.transport is connection_transport


def test_connection_made_callback(gateway, connection_transport):
    """Test that callbacks are called when connection is made."""
    conn_made = mock.MagicMock()
    gateway.on_conn_made = conn_made
    assert gateway.tasks.transport.protocol.transport is None
    gateway.tasks.transport.connect()
    assert gateway.tasks.transport.protocol.transport is connection_transport
    assert conn_made.call_count == 1


def test_handle_line(gateway):
    """Test handle line."""
    line = '1;255;0;0;17;1.4.1\n'
    gateway.tasks.transport.protocol.handle_line(line)
    gateway.tasks.run_job()
    assert 1 in gateway.sensors


def test_disconnect(gateway, connection_transport):
    """Test disconnect."""
    assert gateway.tasks.transport.protocol.transport is None
    gateway.tasks.transport.connect()
    assert gateway.tasks.transport.protocol.transport is connection_transport
    gateway.tasks.transport.disconnect()
    assert connection_transport.close.call_count == 1
    assert gateway.tasks.transport.protocol is None


def test_disconnect_no_connection(gateway, connection_transport):
    """Test disconnect without active connection."""
    assert gateway.tasks.transport.protocol is not None
    assert gateway.tasks.transport.protocol.transport is None
    gateway.tasks.transport.disconnect()
    assert connection_transport.close.call_count == 0
    assert gateway.tasks.transport.protocol is None


def test_connection_lost(gateway, connection_transport, reconnect_callback):
    """Test connection is lost."""
    assert gateway.tasks.transport.protocol.transport is None
    gateway.tasks.transport.connect()
    assert gateway.tasks.transport.protocol.transport is connection_transport
    gateway.tasks.transport.protocol.connection_lost('error')
    assert connection_transport.serial.close.call_count == 1
    assert reconnect_callback.call_count == 1
    assert gateway.tasks.transport.protocol.transport is None


def test_connection_lost_callback(
        gateway, connection_transport, reconnect_callback):
    """Test connection is lost."""
    conn_lost = mock.MagicMock()
    gateway.on_conn_lost = conn_lost
    assert gateway.tasks.transport.protocol.transport is None
    gateway.tasks.transport.connect()
    assert gateway.tasks.transport.protocol.transport is connection_transport
    gateway.tasks.transport.protocol.connection_lost('error')
    assert connection_transport.serial.close.call_count == 1
    assert conn_lost.call_count == 1
    assert conn_lost.call_args == mock.call(gateway, 'error')
    assert reconnect_callback.call_count == 1
    assert gateway.tasks.transport.protocol.transport is None
