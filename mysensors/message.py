"""Handle messages."""
import logging

import voluptuous as vol

from .const import SYSTEM_CHILD_ID, get_const

_LOGGER = logging.getLogger(__name__)

BROADCAST_ID = 255


class Message:
    """Represent a message from the gateway."""

    def __init__(self, data=None, gateway=None):
        """Set up message."""
        self.node_id = 0
        self.child_id = 0
        self.type = 0
        self.ack = 0
        self.sub_type = 0
        self.payload = ''  # All data except payload are integers
        self.gateway = gateway
        if data is not None:
            self.decode(data)

    def __repr__(self):
        """Return the representation."""
        return '<Message data="{};{};{};{};{};{}">'.format(
            self.node_id, self.child_id, self.type, self.ack, self.sub_type,
            self.payload)

    def copy(self, **kwargs):
        """Copy a message, optionally replace attributes with kwargs."""
        msg = Message(self.encode(), self.gateway)
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg

    def modify(self, **kwargs):
        """Modify and return message, replace attributes with kwargs."""
        for key, val in kwargs.items():
            setattr(self, key, val)
        return self

    def decode(self, data, delimiter=';'):
        """Decode a message from command string."""
        try:
            list_data = data.rstrip().split(delimiter)
            self.payload = list_data.pop()
            (self.node_id,
             self.child_id,
             self.type,
             self.ack,
             self.sub_type) = [int(f) for f in list_data]
        except ValueError:
            _LOGGER.warning('Error decoding message from gateway, '
                            'bad data received: %s', data.rstrip())
            raise

    def encode(self, delimiter=';'):
        """Encode a command string from message."""
        try:
            return delimiter.join([str(f) for f in [
                self.node_id,
                self.child_id,
                int(self.type),
                self.ack,
                int(self.sub_type),
                self.payload,
            ]]) + '\n'
        except ValueError:
            _LOGGER.error('Error encoding message to gateway')

    def validate(self, protocol_version):
        """Validate message."""
        const = get_const(protocol_version)
        valid_node_ids = vol.All(vol.Coerce(int), vol.Range(
            min=0, max=BROADCAST_ID, msg='Not valid node_id: {}'.format(
                self.node_id)))
        valid_child_ids = vol.All(vol.Coerce(int), vol.Range(
            min=0, max=SYSTEM_CHILD_ID, msg='Not valid child_id: {}'.format(
                self.child_id)))
        if self.type in (const.MessageType.internal, const.MessageType.stream):
            valid_child_ids = vol.All(vol.Coerce(int), vol.In(
                [SYSTEM_CHILD_ID],
                msg='When message type is {}, child_id must be {}'.format(
                    self.type, SYSTEM_CHILD_ID)))
        if (self.type == const.MessageType.internal and
                self.sub_type in [
                    const.Internal.I_ID_REQUEST,
                    const.Internal.I_ID_RESPONSE]):
            valid_child_ids = vol.Coerce(int)
        valid_types = vol.All(vol.Coerce(int), vol.In(
            [member.value for member in const.VALID_MESSAGE_TYPES],
            msg='Not valid message type: {}'.format(self.type)))
        if self.child_id == SYSTEM_CHILD_ID:
            valid_types = vol.All(vol.Coerce(int), vol.In(
                [const.MessageType.presentation.value,
                 const.MessageType.internal.value,
                 const.MessageType.stream.value],
                msg=(
                    'When child_id is {}, {} is not a valid '
                    'message type'.format(SYSTEM_CHILD_ID, self.type))))
        valid_ack = vol.In([0, 1], msg='Not valid ack flag: {}'.format(
            self.ack))
        valid_sub_types = vol.In(
            [member.value for member
             in const.VALID_MESSAGE_TYPES.get(self.type, [])],
            msg='Not valid message sub-type: {}'.format(self.sub_type))
        valid_payload = const.VALID_PAYLOADS.get(
            self.type, {}).get(self.sub_type, '')
        schema = vol.Schema({
            'node_id': valid_node_ids, 'child_id': valid_child_ids,
            'type': valid_types, 'ack': valid_ack, 'sub_type': valid_sub_types,
            'payload': valid_payload})
        to_validate = {attr: getattr(self, attr) for attr in schema.schema}
        return schema(to_validate)
