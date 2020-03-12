"""MySensors constants for version 2.2 of MySensors."""
import voluptuous as vol

# pylint: disable=unused-import
from mysensors.const_21 import (  # noqa: F401
    MAX_NODE_ID,
    VALID_INTERNAL,
    VALID_PRESENTATION,
    VALID_SETREQ,
    VALID_STREAM,
    VALID_TYPES,
    BaseConst,
    MessageType,
    Presentation,
    SetReq,
    Stream,
)

from .handler import HANDLERS_22


def get_handler_registry():
    """Return handler registry for this version."""
    return HANDLERS_22


class Internal(BaseConst):
    """MySensors internal sub-types."""

    # pylint: disable=too-few-public-methods
    # Use this to report the battery level (in percent 0-100).
    I_BATTERY_LEVEL = 0
    # Sensors can request the current time from the Controller using this
    # message. The time will be reported as the seconds since 1970
    I_TIME = 1
    # Sensors report their library version at startup using this message type
    I_VERSION = 2
    # Use this to request a unique node id from the controller.
    I_ID_REQUEST = 3
    # Id response back to sensor. Payload contains sensor id.
    I_ID_RESPONSE = 4
    # Start/stop inclusion mode of the Controller (1=start, 0=stop).
    I_INCLUSION_MODE = 5
    # Config request from node. Reply with (M)etric or (I)mperal back to sensor
    I_CONFIG = 6
    # When a sensor starts up, it broadcast a search request to all neighbor
    # nodes. They reply with a I_FIND_PARENT_RESPONSE.
    I_FIND_PARENT_REQUEST = 7
    I_FIND_PARENT = 7  # alias from version 2.0
    # Reply message type to I_FIND_PARENT request.
    I_FIND_PARENT_RESPONSE = 8
    # Sent by the gateway to the Controller to trace-log a message
    I_LOG_MESSAGE = 9
    # A message that can be used to transfer child sensors
    # (from EEPROM routing table) of a repeating node.
    I_CHILDREN = 10
    # Optional sketch name that can be used to identify sensor in the
    # Controller GUI
    I_SKETCH_NAME = 11
    # Optional sketch version that can be reported to keep track of the version
    # of sensor in the Controller GUI.
    I_SKETCH_VERSION = 12
    # Used by OTA firmware updates. Request for node to reboot.
    I_REBOOT = 13
    # Send by gateway to controller when startup is complete
    I_GATEWAY_READY = 14
    # Provides signing related preferences (first byte is preference version).
    I_SIGNING_PRESENTATION = 15
    I_REQUEST_SIGNING = 15  # alias from version 1.5
    # Request for a nonce.
    I_NONCE_REQUEST = 16
    I_GET_NONCE = 16  # alias from version 1.5
    # Payload is nonce data.
    I_NONCE_RESPONSE = 17
    I_GET_NONCE_RESPONSE = 17  # alias from version 1.5
    I_HEARTBEAT_REQUEST = 18
    I_HEARTBEAT = 18  # alias from version 2.0
    I_PRESENTATION = 19
    I_DISCOVER_REQUEST = 20
    I_DISCOVER = 20  # alias from version 2.0
    I_DISCOVER_RESPONSE = 21
    I_HEARTBEAT_RESPONSE = 22
    # Node is locked (reason in string-payload).
    I_LOCKED = 23
    I_PING = 24  # Ping sent to node, payload incremental hop counter
    # In return to ping, sent back to sender, payload incremental hop counter
    I_PONG = 25
    I_REGISTRATION_REQUEST = 26  # Register request to GW
    I_REGISTRATION_RESPONSE = 27  # Register response from GW
    I_DEBUG = 28  # Debug message
    I_SIGNAL_REPORT_REQUEST = 29  # Device signal strength request
    I_SIGNAL_REPORT_REVERSE = 30  # Internal
    I_SIGNAL_REPORT_RESPONSE = 31  # Device signal strength response (RSSI)
    I_PRE_SLEEP_NOTIFICATION = 32  # Message sent before node is going to sleep
    I_POST_SLEEP_NOTIFICATION = 33  # Message sent after node woke up


VALID_MESSAGE_TYPES = {
    MessageType.presentation: list(Presentation),
    MessageType.set: list(SetReq),
    MessageType.req: list(SetReq),
    MessageType.internal: list(Internal),
    MessageType.stream: list(Stream),
}


VALID_INTERNAL = dict(VALID_INTERNAL)
VALID_INTERNAL.update(
    {
        Internal.I_SIGNAL_REPORT_REQUEST: str,
        Internal.I_SIGNAL_REPORT_REVERSE: vol.All(vol.Coerce(int), vol.Coerce(str)),
        Internal.I_SIGNAL_REPORT_RESPONSE: vol.All(vol.Coerce(int), vol.Coerce(str)),
        Internal.I_PRE_SLEEP_NOTIFICATION: vol.All(vol.Coerce(int), vol.Coerce(str)),
        Internal.I_POST_SLEEP_NOTIFICATION: vol.All(vol.Coerce(int), vol.Coerce(str)),
    }
)

VALID_PAYLOADS = {
    MessageType.presentation: VALID_PRESENTATION,
    MessageType.set: VALID_SETREQ,
    MessageType.req: {member: "" for member in list(SetReq)},
    MessageType.internal: VALID_INTERNAL,
    MessageType.stream: VALID_STREAM,
}
