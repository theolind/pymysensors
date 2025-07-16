"""MySensors constants for version 2.4 of MySensors."""

import voluptuous as vol

# pylint: disable=unused-import
from mysensors.const_22 import (  # noqa: F401
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
    Internal,
)

from .handler import HANDLERS_24


def get_handler_registry():
    """Return handler registry for this protocol version."""
    return HANDLERS_24


class SetReq(BaseConst):
    """MySensors set/req sub-types for protocol 2.4."""

    V_TILT = 58  # Tilt position. Percentage (0-100 %)


VALID_SETREQ = dict(VALID_SETREQ)
VALID_SETREQ.update(
    {
        SetReq.V_TILT: vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100), vol.Coerce(str)
        ),
    }
)

VALID_TYPES = dict(VALID_TYPES)
VALID_TYPES.setdefault(Presentation.S_COVER, []).append(SetReq.V_TILT)

VALID_PAYLOADS = {
    MessageType.presentation: VALID_PRESENTATION,
    MessageType.set: VALID_SETREQ,
    MessageType.req: {member: "" for member in list(SetReq)},
    MessageType.internal: VALID_INTERNAL,
    MessageType.stream: VALID_STREAM,
}

VALID_MESSAGE_TYPES = {
    MessageType.presentation: list(Presentation),
    MessageType.set: list(SetReq),
    MessageType.req: list(SetReq),
    MessageType.internal: list(Internal),
    MessageType.stream: list(Stream),
}
