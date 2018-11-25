"""Start a mqtt gateway."""
import sys
from contextlib import contextmanager

import click

from mysensors.cli.helper import (
    common_gateway_options, handle_msg, run_async_gateway, run_gateway)
from mysensors.gateway_mqtt import AsyncMQTTGateway, MQTTGateway


def common_mqtt_options(func):
    """Supply common mqtt gateway options."""
    func = click.option(
        '-r', '--retain', is_flag=True, default=False,
        help='Turn on retain on published messages at broker.')(func)
    func = click.option(
        '--out-prefix', default='mygateway1-in', show_default=True,
        help='Topic prefix for outgoing messages.')(func)
    func = click.option(
        '--in-prefix', default='mygateway1-out', show_default=True,
        help='Topic prefix for incoming messages.')(func)
    func = click.option(
        '-p', '--port', default=1883, show_default=True, type=int,
        help='MQTT port of the connection.')(func)
    func = click.option(
        '-b', '--broker', required=True,
        help='MQTT broker address.')(func)
    return func


@click.command(options_metavar='<options>')
@common_mqtt_options
@common_gateway_options
def mqtt_gateway(broker, port, **kwargs):
    """Start an mqtt gateway."""
    with run_mqtt_client(broker, port) as mqttc:
        gateway = MQTTGateway(
            mqttc.publish, mqttc.subscribe, event_callback=handle_msg,
            **kwargs)
        run_gateway(gateway)


@click.command(options_metavar='<options>')
@common_mqtt_options
@common_gateway_options
def async_mqtt_gateway(broker, port, **kwargs):
    """Start an async mqtt gateway."""
    with run_mqtt_client(broker, port) as mqttc:
        # FIXME: fix async client publish and subscribe callbacks
        gateway = AsyncMQTTGateway(
            mqttc.publish, mqttc.subscribe, event_callback=handle_msg,
            **kwargs)
        run_async_gateway(gateway)


@contextmanager
def run_mqtt_client(broker, port):
    """Run mqtt client."""
    mqttc = MQTTClient(broker, port)
    try:
        mqttc.connect()
    except OSError as exc:
        print(
            'Connecting to broker {}:{} failed, exiting: {}'.format(
                broker, port, exc))
        sys.exit()
    mqttc.start()
    try:
        yield mqttc
    finally:
        mqttc.stop()


class MQTTClient:
    """MQTT client."""

    def __init__(self, broker, port=1883, keepalive=60):
        """Set up MQTT client."""
        try:
            import paho.mqtt.client as mqtt  # pylint: disable=import-error
        except ImportError:
            print('paho.mqtt.client is missing. Make sure to install extras')
            sys.exit()
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.topics = {}
        self._mqttc = mqtt.Client()

    def connect(self):
        """Connect to broker."""
        self._mqttc.connect(self.broker, self.port, self.keepalive)

    def publish(self, topic, payload, qos, retain):
        """Publish an MQTT message."""
        self._mqttc.publish(topic, payload, qos, retain)

    def subscribe(self, topic, callback, qos):
        """Subscribe to an MQTT topic."""
        if topic in self.topics:
            return

        def _message_callback(mqttc, userdata, msg):
            """Handle received message."""
            # pylint: disable=unused-argument
            callback(msg.topic, msg.payload.decode('utf-8'), msg.qos)

        self._mqttc.subscribe(topic, qos)
        self._mqttc.message_callback_add(topic, _message_callback)
        self.topics[topic] = callback

    def start(self):
        """Run the MQTT client."""
        print('Start MQTT client')
        self._mqttc.loop_start()

    def stop(self):
        """Stop the MQTT client."""
        print('Stop MQTT client')
        self._mqttc.disconnect()
        self._mqttc.loop_stop()
