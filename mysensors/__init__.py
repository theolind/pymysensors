"""Python implementation of MySensors API."""

import logging
import math
from types import MappingProxyType
from pathlib import Path

import voluptuous as vol
from awesomeversion import AwesomeVersion
from voluptuous.humanize import humanize_error

from .const import SYSTEM_CHILD_ID, get_const
from .message import Message
from .ota import (
    FirmwareConfig,
    FirmwareImage,
    FirmwareSession,
    FirmwareUpdateBusy,
    FirmwareUpdateError,
    fw_int_to_hex,
)
from .sensor import Sensor
from .task import AsyncTasks, SyncTasks
from .validation import safe_is_version

_LOGGER = logging.getLogger(__name__)
__version__ = (Path(__file__).parent / "VERSION").read_text(encoding="utf-8").strip()


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
        return f"<{self.__class__.__name__}>"

    def logic(self, data, *, retained=False):
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

        msg.retained = retained
        if (
            retained is not False
            and msg.type == self.const.MessageType.stream
            and msg.sub_type
            in (
                self.const.Stream.ST_FIRMWARE_CONFIG_REQUEST,
                self.const.Stream.ST_FIRMWARE_CONFIG_RESPONSE,
                self.const.Stream.ST_FIRMWARE_REQUEST,
                self.const.Stream.ST_FIRMWARE_RESPONSE,
            )
        ):
            return None
        msg.gateway = self
        reply = self._handle_message(msg, retained=retained)
        if self.tasks is not None and retained is False:
            self.tasks.ota.application(msg)
        reply = self._route_message(reply)
        return reply.encode() if reply else None

    def _handle_message(
        self, msg, *, retained=False
    ):  # pylint: disable=unused-argument
        message_type = self.const.MessageType(msg.type)
        handler = message_type.get_handler(self.handlers)
        return handler(msg)

    def _firmware_connection_lost(self, *, stopping=False):
        """Notify OTA sessions when a transport becomes unavailable."""

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

    def create_message_to_set_sensor_value(
        self, sensor, child_id, value_type, value, **kwargs
    ):
        """Create a message to set specified sensor child value."""
        msg_type = kwargs.get("msg_type", self.const.MessageType.set)
        ack = kwargs.get("ack", 0)

        try:
            value_type = int(value_type)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid value_type provided: {value_type}") from exc

        value = str(value)

        msg = Message(
            node_id=sensor.sensor_id,
            child_id=child_id,
            type=msg_type,
            ack=ack,
            sub_type=value_type,
            payload=value,
        )

        msg_string = msg.encode()

        if msg_string is None:
            raise ValueError(
                f"Unable to encode message: node {sensor.sensor_id}, child {child_id}, "
                "type {msg_type}, ack {ack}, sub_type {value_type}, payload {value}"
            )

        msg.validate(self.protocol_version)

        return msg

    def is_sensor(self, sensorid, child_id=None):
        """Return True if a sensor and its child exist."""
        ret = sensorid in self.sensors
        if not ret:
            _LOGGER.warning("Node %s is unknown", sensorid)
        if ret and child_id is not None:
            ret = child_id in self.sensors[sensorid].children
            if not ret:
                _LOGGER.warning("Child %s is unknown", child_id)
        if (
            not ret
            and self._can_request_presentation(sensorid)
            and AwesomeVersion(self.protocol_version) >= AwesomeVersion("2.0")
        ):
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

    def _can_request_presentation(self, sensorid):  # pylint: disable=unused-argument
        """Allow normal discovery except while a native target is installing."""
        return True

    def _route_message(self, msg):
        if (
            not isinstance(msg, Message)
            or msg.type == self.const.MessageType.presentation
        ):
            return None

        if (
            msg.node_id not in self.sensors
            or msg.type == self.const.MessageType.stream
            or not self.sensors[msg.node_id].is_smart_sleep_node
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

        sensor = self.sensors[sensor_id]

        if sensor.is_smart_sleep_node:
            sensor.set_child_desired_state(child_id, value_type, value)
            return

        msg_to_send = self.create_message_to_set_sensor_value(
            sensor, child_id, value_type, value, **kwargs
        )

        self.tasks.add_job(msg_to_send.encode)

    def send(self, message):
        """Write a message to the arduino gateway."""
        self.tasks.transport.send(message)


class BaseSyncGateway(Gateway):
    """MySensors base sync gateway."""

    def __init__(
        self,
        transport,
        *args,
        persistence=False,
        persistence_file="mysensors.pickle",
        **kwargs,
    ):
        """Set up gateway."""
        super().__init__(*args, **kwargs)
        self.tasks = SyncTasks(
            self.const, persistence, persistence_file, self.sensors, transport
        )

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
        """Update firmware of all node_ids in nids."""
        self.tasks.update_fw(nids, fw_type, fw_ver, fw_path=fw_path)


class BaseAsyncGateway(Gateway):
    """MySensors base async gateway."""

    def __init__(
        self,
        transport,
        *args,
        persistence=False,
        persistence_file="mysensors.pickle",
        **kwargs,
    ):
        """Set up gateway."""
        super().__init__(*args, **kwargs)
        self._firmware_configs = {}
        self._firmware_session = None
        self._legacy_firmware_imports = 0
        self.tasks = AsyncTasks(
            self.const,
            persistence,
            persistence_file,
            self.sensors,
            transport,
        )

    @property
    def firmware_configs(self):
        """Return validated node configs, including nodes not yet presented."""
        return MappingProxyType(self._firmware_configs)

    def _can_request_presentation(self, sensorid):
        session = self._firmware_session
        return session is None or session.node_id != sensorid

    def _firmware_connection_lost(self, *, stopping=False):
        session = self._firmware_session
        if session is not None and (
            stopping
            or not session.reboot_sent
            or (session.offered and len(session.served) != session.image.blocks)
        ):
            session.fail(FirmwareUpdateError("Gateway disconnected"))
            self._firmware_session = None
            return False
        return session is not None and not session.result.done()

    def _handle_firmware_config(self, msg, session):
        try:
            config = FirmwareConfig.from_payload(msg.payload)
        except ValueError:
            if session is not None and msg.node_id == session.node_id:
                session.fail(FirmwareUpdateError("Invalid firmware config"))
            return None
        self._firmware_configs[msg.node_id] = config
        if session is not None and msg.node_id == session.node_id:
            reply = session.config(msg, config)
        elif session is None and any(
            msg.node_id in store
            for store in (
                self.tasks.ota.requested,
                self.tasks.ota.unstarted,
                self.tasks.ota.started,
            )
        ):
            reply = self.tasks.ota.respond_fw_config(msg)
        else:
            # Acknowledge the running config so AVR bootloaders can boot.
            reply = msg.copy(
                sub_type=self.const.Stream.ST_FIRMWARE_CONFIG_RESPONSE,
                payload=fw_int_to_hex(*config.image_words),
            )
        self.alert(msg)
        return reply

    def _handle_message(self, msg, *, retained=False):
        session = self._firmware_session
        if msg.type != self.const.MessageType.stream:
            reply = super()._handle_message(msg, retained=retained)
            if session is not None and retained is False:
                if probe := session.application(msg):
                    self.send(probe.encode())
            return reply
        if msg.ack or not 1 <= msg.node_id <= self.const.MAX_NODE_ID:
            return None
        if msg.sub_type == self.const.Stream.ST_FIRMWARE_CONFIG_REQUEST:
            return self._handle_firmware_config(msg, session)
        if msg.sub_type == self.const.Stream.ST_FIRMWARE_REQUEST:
            if session is not None:
                reply = session.block(msg) if msg.node_id == session.node_id else None
            else:
                # Ignore unarmed block requests; don't request app presentation.
                reply = self.tasks.ota.respond_fw(msg)
            if reply is not None:
                self.alert(msg)
            return reply
        return super()._handle_message(msg, retained=retained)

    async def install_firmware(
        self,
        node_id: int,
        image: FirmwareImage,
        *,
        progress_callback=None,
        timeout=30.0,
        confirmation_timeout=60.0,
    ) -> FirmwareConfig:
        """Install one image; return only after config and fresh application proof.

        Timeout is transfer inactivity. The whole transfer is bounded by the
        smaller of one timeout per block plus config and one hour. Confirmation
        has a separate fixed deadline, starting when all blocks have been served.
        Reboot-window transport loss is tolerated within these deadlines.
        Cancellation, stop or mid-transfer loss clears the session without replay.
        """
        if (
            not isinstance(node_id, int)
            or isinstance(node_id, bool)
            or not 1 <= node_id <= self.const.MAX_NODE_ID
        ):
            raise ValueError("Invalid firmware target node")
        if not isinstance(image, FirmwareImage):
            raise ValueError("image must be a FirmwareImage")
        if any(
            not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
            for value in (timeout, confirmation_timeout)
        ):
            raise ValueError("Firmware timeouts must be positive finite seconds")
        if progress_callback is not None and not callable(progress_callback):
            raise ValueError("progress_callback must be callable")
        if (
            self._firmware_session is not None
            or self._legacy_firmware_imports
            or self.tasks.ota.active
            or any(sensor.reboot for sensor in self.sensors.values())
        ):
            raise FirmwareUpdateBusy("Gateway has an active or legacy firmware install")
        session = FirmwareSession(
            node_id, image, progress_callback, timeout, confirmation_timeout
        )
        self._firmware_session = session
        try:
            self.send(
                Message(
                    node_id=node_id,
                    child_id=SYSTEM_CHILD_ID,
                    type=self.const.MessageType.internal,
                    sub_type=self.const.Internal.I_REBOOT,
                    ack=0,
                    payload="",
                ).encode()
            )
            session.reboot_sent = True
            return await session.wait()
        finally:
            if self._firmware_session is session:
                self._firmware_session = None
            if not session.result.done():
                session.result.cancel()
            elif not session.result.cancelled():
                session.result.exception()

    async def start(self):
        """Start the gateway and task allow tasks to be scheduled."""
        await self.tasks.start()

    async def stop(self):
        """Stop the gateway and stop allowing tasks for the scheduler."""
        self._firmware_connection_lost(stopping=True)
        await self.tasks.stop()

    async def start_persistence(self):
        """Load persistence file and schedule saving of persistence file."""
        await self.tasks.start_persistence()

    async def update_fw(self, nids, fw_type, fw_ver, fw_path=None):
        """Update firmware of all node_ids in nids."""
        if self._firmware_session is not None:
            raise FirmwareUpdateBusy("Gateway has an active native firmware install")
        self._legacy_firmware_imports += 1
        try:
            await self.tasks.update_fw(nids, fw_type, fw_ver, fw_path=fw_path)
        finally:
            self._legacy_firmware_imports -= 1
