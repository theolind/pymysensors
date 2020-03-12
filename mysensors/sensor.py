"""Handle sensor classes."""
import logging
from collections import deque

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .const import get_const
from .message import Message
from .validation import is_battery_level, is_heartbeat, safe_is_version

_LOGGER = logging.getLogger(__name__)


class Sensor:
    """Represent a sensor."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, sensor_id):
        """Set up sensor."""
        self.sensor_id = sensor_id
        self.children = {}
        self.type = None
        self.sketch_name = None
        self.sketch_version = None
        self._battery_level = 0
        self._protocol_version = "1.4"
        self._heartbeat = 0
        self.new_state = {}
        self.queue = deque()
        self.reboot = False

    def __getstate__(self):
        """Get state to save as pickle."""
        state = self.__dict__.copy()
        for attr in ("_battery_level", "_heartbeat", "_protocol_version"):
            value = state.pop(attr, None)
            prop = attr
            if prop.startswith("_"):
                prop = prop[1:]
            if value is not None:
                state[prop] = value

        return state

    def __setstate__(self, state):
        """Set state when loading pickle."""
        # Restore instance attributes
        for key, val in state.items():
            setattr(self, key, val)
        # Reset some attributes
        self.new_state = {}
        self.queue = deque()
        self.reboot = False
        if "_heartbeat" not in self.__dict__:
            self.heartbeat = 0

    def __repr__(self):
        """Return the representation."""
        return "<Sensor sensor_id={}, children: {}>".format(
            self.sensor_id, self.children
        )

    @property
    def battery_level(self):
        """Return battery level."""
        return self._battery_level

    @battery_level.setter
    def battery_level(self, value):
        """Set valid battery level."""
        self._battery_level = is_battery_level(value)

    @property
    def heartbeat(self):
        """Return heartbeat value."""
        return self._heartbeat

    @heartbeat.setter
    def heartbeat(self, value):
        """Set valid heartbeat value."""
        self._heartbeat = is_heartbeat(value)

    @property
    def protocol_version(self):
        """Return protocol version."""
        return self._protocol_version

    @protocol_version.setter
    def protocol_version(self, value):
        """Set valid protocol version."""
        self._protocol_version = safe_is_version(value)

    def add_child_sensor(self, child_id, child_type, description=""):
        """Create and add a child sensor."""
        if child_id in self.children:
            _LOGGER.warning(
                "child_id %s already exists in children of node %s, "
                "cannot add child",
                child_id,
                self.sensor_id,
            )
            return None
        self.children[child_id] = ChildSensor(child_id, child_type, description)
        return child_id

    def set_child_value(self, child_id, value_type, value, **kwargs):
        """Set a child sensor's value."""
        children = kwargs.get("children", self.children)
        if not isinstance(children, dict) or child_id not in children:
            return None
        msg_type = kwargs.get("msg_type", 1)
        ack = kwargs.get("ack", 0)
        msg = Message().modify(
            node_id=self.sensor_id,
            child_id=child_id,
            type=msg_type,
            ack=ack,
            sub_type=value_type,
            payload=value,
        )
        msg_string = msg.encode()
        if msg_string is None:
            _LOGGER.error(
                "Not a valid message: node %s, child %s, type %s, ack %s, "
                "sub_type %s, payload %s",
                self.sensor_id,
                child_id,
                msg_type,
                ack,
                value_type,
                value,
            )
            return None
        msg = Message(msg_string)
        try:
            msg.validate(self.protocol_version)
        except AttributeError as exc:
            _LOGGER.error("Invalid %s: %s", msg, exc)
            return None
        except vol.Invalid as exc:
            _LOGGER.error("Invalid %s: %s", msg, humanize_error(msg.__dict__, exc))
            return None
        child = children[msg.child_id]
        child.values[msg.sub_type] = msg.payload
        return msg_string


class ChildSensor:
    """Represent a child sensor."""

    def __init__(self, child_id, child_type, description=""):
        """Set up child sensor."""
        # pylint: disable=invalid-name
        self.id = child_id
        self.type = child_type
        self.description = description
        self.values = {}

    def __setstate__(self, state):
        """Set state when loading pickle."""
        # Restore instance attributes
        self.__dict__.update(state)
        # Make sure all attributes exist
        if "description" not in self.__dict__:
            self.description = ""

    def __repr__(self):
        """Return the representation."""
        ret = (
            "<ChildSensor child_id={0!s}, child_type={1!s}, "
            "description={2!s}, values: {3!s}>"
        )
        return ret.format(self.id, self.type, self.description, self.values)

    def get_schema(self, protocol_version):
        """Return the child schema for the correct const version."""
        const = get_const(protocol_version)
        custom_schema = vol.Schema(
            {
                typ.value: const.VALID_SETREQ[typ]
                for typ in const.VALID_TYPES[const.Presentation.S_CUSTOM]
            }
        )
        return custom_schema.extend(
            {typ.value: const.VALID_SETREQ[typ] for typ in const.VALID_TYPES[self.type]}
        )

    def validate(self, protocol_version, values=None):
        """Validate child value types and values against protocol_version."""
        if values is None:
            values = self.values
        return self.get_schema(protocol_version)(values)
