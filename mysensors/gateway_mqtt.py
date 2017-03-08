"""Implement an MQTT gateway."""
import logging
import threading
import time

from mysensors import Gateway, Message

_LOGGER = logging.getLogger(__name__)


class MQTTGateway(Gateway, threading.Thread):
    """MySensors MQTT client gateway."""

    # pylint: disable=too-many-arguments

    def __init__(self, pub_callback, sub_callback, event_callback=None,
                 persistence=False, persistence_file='mysensors.pickle',
                 protocol_version='1.4', in_prefix='', out_prefix='',
                 retain=True):
        """Setup MQTT client gateway."""
        threading.Thread.__init__(self)
        # Should accept topic, payload, qos, retain.
        self._pub_callback = pub_callback
        # Should accept topic, function callback for receive and qos.
        self._sub_callback = sub_callback
        self._in_prefix = in_prefix  # prefix for topics gw -> controller
        self._out_prefix = out_prefix  # prefix for topics controller -> gw
        self._retain = retain  # flag to publish with retain
        self._stop_event = threading.Event()
        # topic structure:
        # prefix/node/child/type/ack/subtype : payload
        Gateway.__init__(self, event_callback, persistence,
                         persistence_file, protocol_version)

    def _handle_subscription(self, topics):
        """Handle subscription of topics."""
        if not isinstance(topics, list):
            topics = [topics]
        for topic in topics:
            topic_levels = topic.split('/')
            try:
                qos = int(topic_levels[4])
            except ValueError:
                qos = 0
            try:
                _LOGGER.debug('Subscribing to: %s', topic)
                self._sub_callback(topic, self.recv, qos)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception(
                    'Subscribe to %s failed: %s', topic, exception)

    def _init_topics(self):
        """Setup initial subscription of mysensors topics."""
        _LOGGER.info('Setting up initial MQTT topic subscription')
        init_topics = [
            '{}/+/+/0/+/+'.format(self._in_prefix),
            '{}/+/+/3/+/+'.format(self._in_prefix),
        ]
        self._handle_subscription(init_topics)

    def _parse_mqtt_to_message(self, topic, payload, qos):
        """Parse a MQTT topic and payload.

        Return a mysensors command string.
        """
        topic_levels = topic.split('/')
        prefix = topic_levels.pop(0)
        if prefix != self._in_prefix:
            return
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
        ret_msg = super()._handle_presentation(msg)
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

    def _safe_load_sensors(self):
        """Load MQTT sensors safely from file."""
        super()._safe_load_sensors()
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

    def recv(self, topic, payload, qos):
        """Receive a MQTT message.

        Call this method when a message is received from the MQTT broker.
        """
        data = self._parse_mqtt_to_message(topic, payload, qos)
        if data is None:
            return
        _LOGGER.debug('Receiving %s', data)
        self.fill_queue(self.logic, (data,))

    def send(self, message):
        """Publish a command string to the gateway via MQTT."""
        if not message:
            return
        topic, payload, qos = self._parse_message_to_mqtt(message)
        with self.lock:
            try:
                _LOGGER.debug('Publishing %s', message)
                self._pub_callback(topic, payload, qos, self._retain)
            except Exception as exception:  # pylint: disable=broad-except
                _LOGGER.exception('Publish to %s failed: %s', topic, exception)

    def stop(self):
        """Stop the background thread."""
        _LOGGER.info('Stopping thread')
        self._stop_event.set()

    def run(self):
        """Background thread that sends messages to the gateway via MQTT."""
        self._init_topics()
        while not self._stop_event.is_set():
            response = self.handle_queue()
            if response is not None:
                self.send(response)
            if not self.queue.empty():
                continue
            time.sleep(0.02)  # short sleep to avoid burning 100% cpu
