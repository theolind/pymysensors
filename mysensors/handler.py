"""Implement message handlers."""
import calendar
import logging
import time
from .const import SYSTEM_CHILD_ID
from .sensor import ChildSensor
from .util import Registry

_LOGGER = logging.getLogger(__name__)

HANDLERS = Registry()


def handle_smartsleep(msg):
    """Process a message before going back to smartsleep."""
    while msg.gateway.sensors[msg.node_id].queue:
        msg.gateway.add_job(
            str, msg.gateway.sensors[msg.node_id].queue.popleft())
    for child in msg.gateway.sensors[msg.node_id].children.values():
        new_child = msg.gateway.sensors[msg.node_id].new_state.get(
            child.id, ChildSensor(child.id, child.type, child.description))
        msg.gateway.sensors[msg.node_id].new_state[child.id] = new_child
        for value_type, value in child.values.items():
            new_value = new_child.values.get(value_type)
            if new_value is not None and new_value != value:
                msg.gateway.add_job(
                    msg.gateway.sensors[msg.node_id].set_child_value,
                    child.id, value_type, new_value)


@HANDLERS.register('presentation')
def handle_presentation(msg):
    """Process a presentation message."""
    if msg.child_id == SYSTEM_CHILD_ID:
        # this is a presentation of the sensor platform
        sensorid = msg.gateway.add_sensor(msg.node_id)
        if sensorid is None:
            return None
        msg.gateway.sensors[msg.node_id].type = msg.sub_type
        msg.gateway.sensors[msg.node_id].protocol_version = msg.payload
        # Set reboot to False after a node reboot.
        msg.gateway.sensors[msg.node_id].reboot = False
        msg.gateway.alert(msg)
        return msg
    # this is a presentation of a child sensor
    if not msg.gateway.is_sensor(msg.node_id):
        _LOGGER.error('Node %s is unknown, will not add child %s',
                      msg.node_id, msg.child_id)
        return None
    child_id = msg.gateway.sensors[msg.node_id].add_child_sensor(
        msg.child_id, msg.sub_type, msg.payload)
    if child_id is None:
        return None
    msg.gateway.alert(msg)
    return msg


@HANDLERS.register('set')
def handle_set(msg):
    """Process a set message."""
    if not msg.gateway.is_sensor(msg.node_id, msg.child_id):
        return None
    msg.gateway.sensors[msg.node_id].set_child_value(
        msg.child_id, msg.sub_type, msg.payload)
    if msg.gateway.sensors[msg.node_id].new_state:
        msg.gateway.sensors[msg.node_id].set_child_value(
            msg.child_id, msg.sub_type, msg.payload,
            children=msg.gateway.sensors[msg.node_id].new_state)
    msg.gateway.alert(msg)
    # Check if reboot is true
    if msg.gateway.sensors[msg.node_id].reboot:
        return msg.copy(
            child_id=SYSTEM_CHILD_ID,
            type=msg.gateway.const.MessageType.internal, ack=0,
            sub_type=msg.gateway.const.Internal.I_REBOOT, payload='')
    return None


@HANDLERS.register('req')
def handle_req(msg):
    """Process a req message.

    This will return the value if it exists. If no value exists,
    nothing is returned.
    """
    if not msg.gateway.is_sensor(msg.node_id, msg.child_id):
        return None
    value = msg.gateway.sensors[msg.node_id].children[
        msg.child_id].values.get(msg.sub_type)
    if value is not None:
        return msg.copy(
            type=msg.gateway.const.MessageType.set, payload=value)
    return None


@HANDLERS.register('internal')
def handle_internal(msg):
    """Process an internal message."""
    internal = msg.gateway.const.Internal(msg.sub_type)
    handler = internal.get_handler(msg.gateway.handlers)
    if handler is None:
        return None
    return handler(msg)


@HANDLERS.register('stream')
def handle_stream(msg):
    """Process a stream type message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    stream = msg.gateway.const.Stream(msg.sub_type)
    handler = stream.get_handler(msg.gateway.handlers)
    if handler is None:
        return None
    return handler(msg)


@HANDLERS.register('ST_FIRMWARE_CONFIG_REQUEST')
def handle_firmware_config_request(msg):
    """Process a firmware config request message."""
    return msg.gateway.ota.respond_fw_config(msg)


@HANDLERS.register('ST_FIRMWARE_REQUEST')
def handle_firmware_request(msg):
    """Process a firmware request message."""
    return msg.gateway.ota.respond_fw(msg)


@HANDLERS.register('I_ID_REQUEST')
def handle_id_request(msg):
    """Process an internal id request message."""
    node_id = msg.gateway.add_sensor()
    return msg.copy(
        ack=0, sub_type=msg.gateway.const.Internal['I_ID_RESPONSE'],
        payload=node_id) if node_id is not None else None


@HANDLERS.register('I_CONFIG')
def handle_config(msg):
    """Process an internal config message."""
    return msg.copy(ack=0, payload='M' if msg.gateway.metric else 'I')


@HANDLERS.register('I_TIME')
def handle_time(msg):
    """Process an internal time request message."""
    return msg.copy(ack=0, payload=calendar.timegm(time.localtime()))


@HANDLERS.register('I_BATTERY_LEVEL')
def handle_battery_level(msg):
    """Process an internal battery level message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    msg.gateway.sensors[msg.node_id].battery_level = msg.payload
    msg.gateway.alert(msg)
    return None


@HANDLERS.register('I_SKETCH_NAME')
def handle_sketch_name(msg):
    """Process an internal sketch name message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    msg.gateway.sensors[msg.node_id].sketch_name = msg.payload
    msg.gateway.alert(msg)
    return None


@HANDLERS.register('I_SKETCH_VERSION')
def handle_sketch_version(msg):
    """Process an internal sketch version message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    msg.gateway.sensors[msg.node_id].sketch_version = msg.payload
    msg.gateway.alert(msg)
    return None


@HANDLERS.register('I_LOG_MESSAGE')
def handle_log_message(msg):  # pylint: disable=useless-return
    """Process an internal log message."""
    msg.gateway.can_log = True
    _LOGGER.debug(
        'n:%s c:%s t:%s s:%s p:%s', msg.node_id, msg.child_id, msg.type,
        msg.sub_type, msg.payload)
    return None


@HANDLERS.register('I_GATEWAY_READY')
def handle_gateway_ready(msg):  # pylint: disable=useless-return
    """Process an internal gateway ready message."""
    _LOGGER.info(
        'n:%s c:%s t:%s s:%s p:%s', msg.node_id, msg.child_id, msg.type,
        msg.sub_type, msg.payload)
    msg.gateway.alert(msg)
    return None


HANDLERS_20 = Registry()
HANDLERS_20.update(HANDLERS)


@HANDLERS_20.register('I_GATEWAY_READY')
def handle_gateway_ready_20(msg):
    """Process an internal gateway ready message."""
    _LOGGER.info(
        'n:%s c:%s t:%s s:%s p:%s', msg.node_id, msg.child_id, msg.type,
        msg.sub_type, msg.payload)
    msg.gateway.alert(msg)
    return msg.copy(
        node_id=255, ack=0,
        sub_type=msg.gateway.const.Internal.I_DISCOVER, payload='')


@HANDLERS_20.register('I_HEARTBEAT_RESPONSE')
def handle_heartbeat_response(msg):
    """Process an internal heartbeat response message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    handle_smartsleep(msg)
    msg.gateway.sensors[msg.node_id].heartbeat = msg.payload
    msg.gateway.alert(msg)
    return None


@HANDLERS_20.register('I_DISCOVER_RESPONSE')
def handle_discover_response(msg):  # pylint: disable=useless-return
    """Process an internal discover response message."""
    msg.gateway.is_sensor(msg.node_id)
    return None


HANDLERS_22 = Registry()
HANDLERS_22.update(HANDLERS_20)
HANDLERS_22.pop('I_HEARTBEAT_RESPONSE')


@HANDLERS_22.register('I_HEARTBEAT_RESPONSE')
def handle_heartbeat_response_22(msg):
    """Process an internal heartbeat response message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    msg.gateway.sensors[msg.node_id].heartbeat = msg.payload
    msg.gateway.alert(msg)
    return None


@HANDLERS_22.register('I_PRE_SLEEP_NOTIFICATION')
def handle_pre_sleep_notification(msg):
    """Process an internal pre sleep notification message."""
    if not msg.gateway.is_sensor(msg.node_id):
        return None
    handle_smartsleep(msg)
    return None
