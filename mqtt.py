"""Example for using pymysensors with mqtt."""
import paho.mqtt.client as mqtt

from mysensors import mysensors


class MQTT:
    """MQTT client example."""

    def __init__(self, broker, port, keepalive):
        """Set up MQTT client."""
        self.topics = {}
        self._mqttc = mqtt.Client()
        self._mqttc.connect(broker, port, keepalive)

    def publish(self, topic, payload, qos, retain):
        """Publish an MQTT message."""
        self._mqttc.publish(topic, payload, qos, retain)

    def subscribe(self, topic, callback, qos):
        """Subscribe to an MQTT topic."""
        # pylint: disable=unused-argument

        if topic in self.topics:
            return

        def _message_callback(mqttc, userdata, msg):
            """Run callback for received message."""
            callback(msg.topic, msg.payload.decode("utf-8"), msg.qos)

        self._mqttc.subscribe(topic, qos)
        self._mqttc.message_callback_add(topic, _message_callback)
        self.topics[topic] = callback

    def start(self):
        """Run the MQTT client."""
        print("Start MQTT client")
        self._mqttc.loop_start()

    def stop(self):
        """Stop the MQTT client."""
        print("Stop MQTT client")
        self._mqttc.disconnect()
        self._mqttc.loop_stop()


def event(message):
    """Run callback for mysensors updates."""
    print("sensor_update " + str(message.node_id))


MQTTC = MQTT("localhost", 1883, 60)
MQTTC.start()

GATEWAY = mysensors.MQTTGateway(
    MQTTC.publish,
    MQTTC.subscribe,
    in_prefix="mygateway1-out",
    out_prefix="mygateway1-in",
    retain=True,
    event_callback=event,
    protocol_version="2.0",
)

GATEWAY.start()
