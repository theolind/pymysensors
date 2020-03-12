"""Python implementation of MySensors API."""
import logging

# pylint: disable=no-name-in-module, import-error
from distutils.version import LooseVersion as parse_ver
from functools import partial
from pathlib import Path

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .const import SYSTEM_CHILD_ID, get_const
from .message import Message
from .sensor import Sensor
from .task import AsyncTasks, SyncTasks
from .validation import safe_is_version

_LOGGER = logging.getLogger(__name__)
__version__ = (Path(__file__).parent / "VERSION").read_text().strip()


class Gateway:
    """Base implementation for a MySensors Gateway."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, event_callback=None, protocol_version="1.4"):
        """Set up Gateway."""
        protocol_version = safe_is_version(protocol_version)
        self.const = get_const(protocol_version)
        self.event_callback = event_callback
        self.metric = True  # if true - use metric, if false - use imperial
        handlers = self.const.get_handler_registry()
        # Copy to allow safe modification.
        self.handlers = dict(handlers)
        self.can_log = False
        self.on_conn_made = None
        self.on_conn_lost = None
        self.protocol_version = protocol_version
        self.sensors = {}
        self.tasks = None

    def __repr__(self):
        """Return the representation."""
        return "<{}>".format(self.__class__.__name__)

    def logic(self, data):
        """Parse the data and respond to it appropriately.

        Response is returned to the caller and has to be sent
        data as a mysensors command string.
        """
        try:
            msg = Message(data)
        except ValueError as exc:
            _LOGGER.warning("Not a valid message: %s", exc)
            return None
        try:
            msg.validate(self.protocol_version)
        except vol.Invalid as exc:
            _LOGGER.warning("Invalid %s: %s", msg, humanize_error(msg.__dict__, exc))
            return None

        msg.gateway = self
        message_type = self.const.MessageType(msg.type)
        handler = message_type.get_handler(self.handlers)
        msg = handler(msg)
        msg = self._route_message(msg)
        return msg.encode() if msg else None

    def alert(self, msg):
        """Tell anyone who wants to know that a sensor was updated."""
        if self.event_callback is not None:
            try:
                self.event_callback(msg)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(exception)

        if self.tasks.persistence:
            self.tasks.persistence.need_save = True

    def _get_next_id(self):
        """Return the next available sensor id."""
        if self.sensors:
            next_id = max(self.sensors.keys()) + 1
        else:
            next_id = 1
        if next_id <= self.const.MAX_NODE_ID:
            return next_id
        return None

    def add_sensor(self, sensorid=None):
        """Add a sensor to the gateway."""
        if sensorid is None:
            sensorid = self._get_next_id()
        if sensorid is not None and sensorid not in self.sensors:
            self.sensors[sensorid] = Sensor(sensorid)
        return sensorid if sensorid in self.sensors else None

    def is_sensor(self, sensorid, child_id=None):
        """Return True if a sensor and its child exist."""
        ret = sensorid in self.sensors
        if not ret:
            _LOGGER.warning("Node %s is unknown", sensorid)
        if ret and child_id is not None:
            ret = child_id in self.sensors[sensorid].children
            if not ret:
                _LOGGER.warning("Child %s is unknown", child_id)
        if not ret and parse_ver(self.protocol_version) >= parse_ver("2.0"):
            _LOGGER.info("Requesting new presentation for node %s", sensorid)
            msg = Message(gateway=self).modify(
                node_id=sensorid,
                child_id=SYSTEM_CHILD_ID,
                type=self.const.MessageType.internal,
                sub_type=self.const.Internal.I_PRESENTATION,
            )
            if self._route_message(msg):
                self.tasks.add_job(msg.encode)
        return ret

    def _route_message(self, msg):
        if (
            not isinstance(msg, Message)
            or msg.type == self.const.MessageType.presentation
        ):
            return None
        if (
            msg.node_id not in self.sensors
            or msg.type == self.const.MessageType.stream
            or not self.sensors[msg.node_id].new_state
        ):
            return msg
        self.sensors[msg.node_id].queue.append(msg.encode())
        return None

    def set_child_value(self, sensor_id, child_id, value_type, value, **kwargs):
        """Add a command to set a sensor value, to the queue.

        A queued command will be sent to the sensor when the gateway
        thread has sent all previously queued commands.

        If the sensor attribute new_state returns True, the command will be
        buffered in a queue on the sensor, and only the internal sensor state
        will be updated. When a smartsleep message is received, the internal
        state will be pushed to the sensor, via _handle_smartsleep method.
        """
        if not self.is_sensor(sensor_id, child_id):
            return
        if self.sensors[sensor_id].new_state:
            self.sensors[sensor_id].set_child_value(
                child_id, value_type, value, children=self.sensors[sensor_id].new_state
            )
        else:
            self.tasks.add_job(
                partial(
                    self.sensors[sensor_id].set_child_value,
                    child_id,
                    value_type,
                    value,
                    **kwargs
                )
            )

    def send(self, message):
        """Write a message to the arduino gateway."""
        self.tasks.transport.send(message)

    def start(self):
        """Start the gateway and task allow tasks to be scheduled."""
        self.tasks.start()

    def stop(self):
        """Stop the gateway and stop allowing tasks for the scheduler."""
        self.tasks.stop()

    def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        self.tasks.start_persistence()

    def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare of all node_ids in nids."""
        self.tasks.update_fw(nids, fw_type, fw_ver, fw_path=fw_path)


class BaseSyncGateway(Gateway):
    """MySensors base sync gateway."""

    def __init__(
        self,
        transport,
        *args,
        persistence=False,
        persistence_file="mysensors.pickle",
        **kwargs
    ):
        """Set up gateway."""
        super().__init__(*args, **kwargs)
        self.tasks = SyncTasks(
            self.const, persistence, persistence_file, self.sensors, transport
        )


class BaseAsyncGateway(Gateway):
    """MySensors base async gateway."""

    def __init__(
        self,
        transport,
        *args,
        loop=None,
        persistence=False,
        persistence_file="mysensors.pickle",
        **kwargs
    ):
        """Set up gateway."""
        super().__init__(*args, **kwargs)
        self.tasks = AsyncTasks(
            self.const,
            persistence,
            persistence_file,
            self.sensors,
            transport,
            loop=loop,
        )

    async def start(self):
        """Start the gateway and task allow tasks to be scheduled."""
        await self.tasks.start()

    async def stop(self):
        """Stop the gateway and stop allowing tasks for the scheduler."""
        await self.tasks.stop()

    async def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        await self.tasks.start_persistence()

    async def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firwmare of all node_ids in nids."""
        await self.tasks.update_fw(nids, fw_type, fw_ver, fw_path=fw_path)
