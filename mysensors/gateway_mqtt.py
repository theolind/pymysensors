"""Implement an MQTT gateway."""
import asyncio
import logging
import threading

from mysensors import BaseAsyncGateway, Gateway, Message, ThreadingGateway
from .handler import handle_presentation

_LOGGER = logging.getLogger(__name__)


class BaseMQTTGateway(Gateway):
    """MySensors MQTT client gateway."""

    # pylint: disable=too-many-arguments, abstract-method

    def __init__(
            self, pub_callback, sub_callback, in_prefix='', out_prefix='',
            retain=True, **kwargs):
        """Set up MQTT client gateway."""
        super().__init__(**kwargs)
        # Should accept topic, payload, qos, retain.
        self._pub_callback = pub_callback
        # Should accept topic, function callback for receive and qos.
        self._sub_callback = sub_callback
        self._in_prefix = in_prefix  # prefix for topics gw -> controller
        self._out_prefix = out_prefix  # prefix for topics controller -> gw
        self._retain = retain  # flag to publish with retain
        # topic structure:
        # prefix/node/child/type/ack/subtype : payload
        self.const.MessageType.presentation.set_handler(
            self.handlers, self._handle_presentation)

    def _handle_subscription(self, topics):
        """Handle subscription of topics."""
        if not isinstance(topics, list):
            topics = [topics]
        for topic in topics:
            topic_levels = topic.split('/')
            try:
                qos = int(topic_levels[-2])
            except ValueError:
                qos = 0
            try:
                _LOGGER.debug('Subscribing to: %s, qos: %s', topic, qos)
                self._sub_callback(topic, self.recv, qos)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    'Subscribe to %s failed: %s', topic, exception)

    def _init_topics(self):
        """Set up initial subscription of mysensors topics."""
        _LOGGER.info('Setting up initial MQTT topic subscription')
        init_topics = [
            '{}/+/+/0/+/+'.format(self._in_prefix),
            '{}/+/+/3/+/+'.format(self._in_prefix),
        ]
        self._handle_subscription(init_topics)
        if not self.persistence:
            return
        topics = [
            '{}/{}/{}/{}/+/+'.format(
                self._in_prefix, str(sensor.sensor_id), str(child.id),
                msg_type) for sensor in self.sensors.values()
            for child in sensor.children.values()
            for msg_type in (int(self.const.MessageType.set),
                             int(self.const.MessageType.req))
        ]
        topics.extend([
            '{}/{}/+/{}/+/+'.format(
                self._in_prefix, str(sensor.sensor_id),
                int(self.const.MessageType.stream))
            for sensor in self.sensors.values()])
        self._handle_subscription(topics)

    def _parse_mqtt_to_message(self, topic, payload, qos):
        """Parse a MQTT topic and payload.

        Return a mysensors command string.
        """
        topic_levels = topic.split('/')
        topic_levels = not_prefix = topic_levels[-5:]
        prefix_end_idx = topic.find('/'.join(not_prefix)) - 1
        prefix = topic[:prefix_end_idx]
        if prefix != self._in_prefix:
            return None
        if qos and qos > 0:
            ack = '1'
        else:
            ack = '0'
        topic_levels[3] = ack
        topic_levels.append(str(payload))
        return ';'.join(topic_levels)

    def _parse_message_to_mqtt(self, data):
        """Parse a mysensors command string.

        Return a MQTT topic, payload and qos-level as a tuple.
        """
        msg = Message(data, self)
        payload = str(msg.payload)
        msg.payload = ''
        # prefix/node/child/type/ack/subtype : payload
        return ('{}/{}'.format(self._out_prefix, msg.encode('/'))[:-2],
                payload, msg.ack)

    def _handle_presentation(self, msg):
        """Process a MQTT presentation message."""
        ret_msg = handle_presentation(msg)
        if msg.child_id == 255 or ret_msg is None:
            return
        # this is a presentation of a child sensor
        topics = [
            '{}/{}/{}/{}/+/+'.format(
                self._in_prefix, str(msg.node_id), str(msg.child_id),
                msg_type)
            for msg_type in (int(self.const.MessageType.set),
                             int(self.const.MessageType.req))
        ]
        topics.append('{}/{}/+/{}/+/+'.format(
            self._in_prefix, str(msg.node_id),
            int(self.const.MessageType.stream)))
        self._handle_subscription(topics)

    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        return self._in_prefix if self._in_prefix else None

    def recv(self, topic, payload, qos):
        """Receive a MQTT message.

        Call this method when a message is received from the MQTT broker.
        """
        data = self._parse_mqtt_to_message(topic, payload, qos)
        if data is None:
            return
        _LOGGER.debug('Receiving %s', data)
        self.add_job(self.logic, data)

    def send(self, message):
        """Publish a command string to the gateway via MQTT."""
        if not message:
            return
        topic, payload, qos = self._parse_message_to_mqtt(message)
        try:
            _LOGGER.debug('Publishing %s', message.strip())
            self._pub_callback(topic, payload, qos, self._retain)
        except Exception as exception:  # pylint: disable=broad-except
            _LOGGER.exception('Publish to %s failed: %s', topic, exception)


class MQTTGateway(BaseMQTTGateway, ThreadingGateway):
    """MySensors MQTT client gateway."""

    # pylint: disable=abstract-method

    def send(self, message):
        """Publish a command string to the gateway via MQTT."""
        with self.lock:
            super().send(message)

    def start(self):
        """Start the connection to a transport."""
        self._init_topics()
        poll_thread = threading.Thread(target=self._poll_queue)
        poll_thread.start()

    def stop(self):
        """Stop the gateway."""
        _LOGGER.info('Stopping gateway')
        super().stop()


class AsyncMQTTGateway(BaseMQTTGateway, BaseAsyncGateway):
    """MySensors async MQTT client gateway."""

    @asyncio.coroutine
    def _connect(self):
        """Connect to the transport."""
        self._init_topics()

    @asyncio.coroutine
    def get_gateway_id(self):
        """Return a unique id for the gateway."""
        return super().get_gateway_id()
