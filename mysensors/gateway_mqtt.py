"""Implement an MQTT gateway."""
import logging

from mysensors import BaseAsyncGateway, BaseSyncGateway, Gateway, Message
from .handler import handle_presentation
from .transport import Transport

_LOGGER = logging.getLogger(__name__)


class BaseMQTTGateway(Gateway):
    """MySensors MQTT client gateway."""

    def __init__(self, **kwargs):
        """Set up MQTT client gateway."""
        super().__init__(**kwargs)
        self.const.MessageType.presentation.set_handler(
            self.handlers, self._handle_presentation
        )

    def init_topics(self):
        """Set up initial subscription of mysensors topics."""
        _LOGGER.info("Setting up initial MQTT topic subscription")
        init_topics = [
            "/+/+/0/+/+",
            "/+/+/3/+/+",
        ]
        self.tasks.transport.handle_subscription(init_topics)
        if not self.tasks.persistence:
            return
        topics = [
            "/{}/{}/{}/+/+".format(str(sensor.sensor_id), str(child.id), msg_type)
            for sensor in self.sensors.values()
            for child in sensor.children.values()
            for msg_type in (
                int(self.const.MessageType.set),
                int(self.const.MessageType.req),
            )
        ]
        topics.extend(
            [
                "/{}/+/{}/+/+".format(
                    str(sensor.sensor_id), int(self.const.MessageType.stream)
                )
                for sensor in self.sensors.values()
            ]
        )
        self.tasks.transport.handle_subscription(topics)

    def _handle_presentation(self, msg):
        """Process a MQTT presentation message."""
        ret_msg = handle_presentation(msg)
        if msg.child_id == 255 or ret_msg is None:
            return
        # this is a presentation of a child sensor
        topics = [
            "/{}/{}/{}/+/+".format(str(msg.node_id), str(msg.child_id), msg_type)
            for msg_type in (
                int(self.const.MessageType.set),
                int(self.const.MessageType.req),
            )
        ]
        topics.append(
            "/{}/+/{}/+/+".format(str(msg.node_id), int(self.const.MessageType.stream))
        )
        self.tasks.transport.handle_subscription(topics)

    def parse_mqtt_to_message(self, topic, payload, qos):
        """Parse a MQTT topic and payload.

        Return a mysensors command string.
        """
        # pylint: disable=no-self-use
        topic_levels = topic.split("/")
        topic_levels = not_prefix = topic_levels[-5:]
        prefix_end_idx = topic.find("/".join(not_prefix)) - 1
        prefix = topic[:prefix_end_idx]
        if prefix != self.tasks.transport.in_prefix:
            return None
        if qos and qos > 0:
            ack = "1"
        else:
            ack = "0"
        topic_levels[3] = ack
        topic_levels.append(str(payload))
        return ";".join(topic_levels)

    def parse_message_to_mqtt(self, data):
        """Parse a mysensors command string.

        Return a MQTT topic, payload and qos-level as a tuple.
        """
        msg = Message(data, self)
        payload = str(msg.payload)
        msg.payload = ""
        # prefix/node/child/type/ack/subtype : payload
        return "/{}".format(msg.encode("/"))[:-2], payload, msg.ack

    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        return (
            self.tasks.transport.in_prefix if self.tasks.transport.in_prefix else None
        )


class MQTTGateway(BaseSyncGateway, BaseMQTTGateway):
    """MySensors MQTT client gateway."""

    # pylint: disable=too-many-arguments

    def __init__(
        self,
        pub_callback,
        sub_callback,
        in_prefix="",
        out_prefix="",
        retain=True,
        **kwargs
    ):
        """Set up MQTT gateway."""
        transport = MQTTSyncTransport(
            self,
            pub_callback,
            sub_callback,
            in_prefix=in_prefix,
            out_prefix=out_prefix,
            retain=retain,
        )
        super().__init__(transport, **kwargs)


class AsyncMQTTGateway(BaseAsyncGateway, BaseMQTTGateway):
    """MySensors async MQTT client gateway."""

    # pylint: disable=too-many-arguments, useless-super-delegation

    def __init__(
        self,
        pub_callback,
        sub_callback,
        loop=None,
        in_prefix="",
        out_prefix="",
        retain=True,
        **kwargs
    ):
        """Set up MQTT gateway."""
        transport = MQTTAsyncTransport(
            self,
            pub_callback,
            sub_callback,
            in_prefix=in_prefix,
            out_prefix=out_prefix,
            retain=retain,
        )
        super().__init__(transport, loop=loop, **kwargs)

    async def get_gateway_id(self):
        """Return a unique id for the gateway."""
        return super().get_gateway_id()


class MQTTTransport(Transport):
    """MySensors MQTT transport."""

    # pylint: disable=too-many-arguments

    def __init__(
        self,
        gateway,
        pub_callback,
        sub_callback,
        in_prefix="",
        out_prefix="",
        retain=True,
    ):
        """Set up MQTT client gateway."""
        super().__init__(gateway, None)
        # Should accept topic, payload, qos, retain.
        self._pub_callback = pub_callback
        # Should accept topic, function callback for receive and qos.
        self._sub_callback = sub_callback
        self.in_prefix = in_prefix  # prefix for topics gw -> controller
        self.out_prefix = out_prefix  # prefix for topics controller -> gw
        self._retain = retain  # flag to publish with retain
        # topic structure:
        # prefix/node/child/type/ack/subtype : payload
        self.gateway = gateway

    def connect(self):
        """Connect to the transport."""
        raise NotImplementedError

    def disconnect(self):
        """Disconnect from the transport.

        The MQTT gateway doesn't need to disconnect.
        """

    def handle_subscription(self, topics):
        """Handle subscription of topics."""
        if not isinstance(topics, list):
            topics = [topics]
        for topic in topics:
            topic = self.in_prefix + topic
            topic_levels = topic.split("/")
            try:
                qos = int(topic_levels[-2])
            except ValueError:
                qos = 0
            try:
                _LOGGER.debug("Subscribing to: %s, qos: %s", topic, qos)
                self._sub_callback(topic, self.recv, qos)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception("Subscribe to %s failed: %s", topic, exception)

    def recv(self, topic, payload, qos):
        """Receive a MQTT message.

        Call this method when a message is received from the MQTT broker.
        """
        data = self.gateway.parse_mqtt_to_message(topic, payload, qos)
        if data is None:
            return
        _LOGGER.debug("Receiving %s", data)
        self.gateway.tasks.add_job(self.gateway.logic, data)

    def send(self, message):
        """Publish a command string to the gateway via MQTT."""
        if not message:
            return
        topic, payload, qos = self.gateway.parse_message_to_mqtt(message)
        topic = self.out_prefix + topic
        try:
            _LOGGER.debug("Publishing %s", message.strip())
            self._pub_callback(topic, payload, qos, self._retain)
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception("Publish to %s failed: %s", topic, exception)


class MQTTSyncTransport(MQTTTransport):
    """TCP sync version of transport class."""

    def connect(self):
        """Connect to the transport."""
        self.gateway.init_topics()


class MQTTAsyncTransport(MQTTTransport):
    """TCP async version of transport class."""

    async def connect(self):
        """Connect to the transport."""
        self.gateway.init_topics()
