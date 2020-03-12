"""Start a mqtt gateway."""
import asyncio
from contextlib import contextmanager
import logging
import socket
import sys

import click

from mysensors.cli.helper import (
    common_gateway_options,
    handle_msg,
    run_async_gateway,
    run_gateway,
)
from mysensors.gateway_mqtt import AsyncMQTTGateway, MQTTGateway

_LOGGER = logging.getLogger(__name__)


def common_mqtt_options(func):
    """Supply common mqtt gateway options."""
    func = click.option(
        "-r",
        "--retain",
        is_flag=True,
        default=False,
        help="Turn on retain on published messages at broker.",
    )(func)
    func = click.option(
        "--out-prefix",
        default="mygateway1-in",
        show_default=True,
        help="Topic prefix for outgoing messages.",
    )(func)
    func = click.option(
        "--in-prefix",
        default="mygateway1-out",
        show_default=True,
        help="Topic prefix for incoming messages.",
    )(func)
    func = click.option(
        "-p",
        "--port",
        default=1883,
        show_default=True,
        type=int,
        help="MQTT port of the connection.",
    )(func)
    func = click.option("-b", "--broker", required=True, help="MQTT broker address.")(
        func
    )
    return func


@click.command(options_metavar="<options>")
@common_mqtt_options
@common_gateway_options
def mqtt_gateway(broker, port, **kwargs):
    """Start an mqtt gateway."""
    with run_mqtt_client(broker, port) as mqttc:
        gateway = MQTTGateway(
            mqttc.publish, mqttc.subscribe, event_callback=handle_msg, **kwargs
        )
        run_gateway(gateway)


@click.command(options_metavar="<options>")
@common_mqtt_options
@common_gateway_options
def async_mqtt_gateway(broker, port, **kwargs):
    """Start an async mqtt gateway."""
    loop = asyncio.get_event_loop()
    mqttc = loop.run_until_complete(async_start_mqtt_client(loop, broker, port))
    gateway = AsyncMQTTGateway(
        mqttc.publish, mqttc.subscribe, event_callback=handle_msg, loop=loop, **kwargs
    )
    run_async_gateway(gateway, mqttc.stop())


@contextmanager
def run_mqtt_client(broker, port):
    """Run mqtt client."""
    mqttc = MQTTClient(broker, port)
    try:
        mqttc.start()
    except OSError as exc:
        _LOGGER.error(
            "Connecting to broker %s:%s failed, exiting: %s", broker, port, exc
        )
        sys.exit()
    try:
        yield mqttc
    finally:
        mqttc.stop()


async def async_start_mqtt_client(loop, broker, port):
    """Start async mqtt client."""
    mqttc = AsyncMQTTClient(loop, broker, port)
    try:
        await mqttc.start()
    except OSError as exc:
        _LOGGER.error(
            "Connecting to broker %s:%s failed, exiting: %s", broker, port, exc
        )
        sys.exit()
    return mqttc


class MQTTClient:
    """MQTT client."""

    def __init__(self, broker, port=1883, keepalive=60):
        """Set up MQTT client."""
        try:
            # pylint: disable=import-error, import-outside-toplevel
            import paho.mqtt.client as mqtt
        except ImportError:
            _LOGGER.error(
                "paho.mqtt.client is missing. "
                "Make sure to install extras:\n"
                "pip3 install pymysensors[mqtt-client]"
            )
            sys.exit()
        self.broker = broker
        self.port = port
        self.keepalive = keepalive
        self.topics = {}
        self._client = mqtt.Client()

    def _connect(self):
        """Connect to broker."""
        self._client.connect(self.broker, self.port, self.keepalive)

    def publish(self, topic, payload, qos, retain):
        """Publish an MQTT message."""
        self._client.publish(topic, payload, qos, retain)

    def subscribe(self, topic, callback, qos):
        """Subscribe to an MQTT topic."""
        if topic in self.topics:
            return

        def message_callback(mqttc, userdata, msg):
            """Handle received message."""
            # pylint: disable=unused-argument
            callback(msg.topic, msg.payload.decode("utf-8"), msg.qos)

        self._client.subscribe(topic, qos)
        self._client.message_callback_add(topic, message_callback)
        self.topics[topic] = callback

    def start(self):
        """Run the MQTT client."""
        _LOGGER.info("Start MQTT client")
        self._connect()
        self._client.loop_start()

    def stop(self):
        """Stop the MQTT client."""
        _LOGGER.info("Stop MQTT client")
        self._client.disconnect()
        self._client.loop_stop()


class AsyncMQTTClient(MQTTClient):
    """Async MQTT client."""

    def __init__(self, loop, *args):
        """Set up async MQTT client."""
        self.loop = loop
        self.disconnected = None
        self._aio_helper = None
        super().__init__(*args)

    def on_disconnect(self, client, userdata, ret_code):
        """Handle disconnection."""
        # pylint: disable=unused-argument
        self.disconnected.set_result(ret_code)

    def _connect(self):
        """Connect to broker."""
        self.disconnected = self.loop.create_future()
        self._client.on_disconnect = self.on_disconnect
        self._aio_helper = AsyncioHelper(self.loop, self._client)
        super()._connect()
        self._client.socket().setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2048)

    async def start(self):
        """Run the MQTT client."""
        _LOGGER.info("Start MQTT client")
        self._connect()

    async def stop(self):
        """Stop the MQTT client."""
        _LOGGER.info("Stop MQTT client")
        self._client.disconnect()
        await self.disconnected


class AsyncioHelper:
    """Provide asyncio loop support.

    Based on example at https://github.com/eclipse/paho.mqtt.python.
    """

    # pylint: disable=unused-argument

    def __init__(self, loop, client):
        """Set up instance."""
        self.loop = loop
        self._client = client
        self._client.on_socket_open = self.on_socket_open
        self._client.on_socket_close = self.on_socket_close
        self._client.on_socket_register_write = self.register_write
        self._client.on_socket_unregister_write = self.unregister_write
        self.misc_loop_task = None

    def on_socket_open(self, client, userdata, sock):
        """Handle socket open."""

        def callback():
            client.loop_read()

        self.loop.add_reader(sock, callback)
        self.misc_loop_task = self.loop.create_task(self.run_misc_loop())

    def on_socket_close(self, client, userdata, sock):
        """Handle socket close."""
        self.loop.remove_reader(sock)
        self.misc_loop_task.cancel()

    def register_write(self, client, userdata, sock):
        """Register write callback."""

        def callback():
            client.loop_write()

        self.loop.add_writer(sock, callback)

    def unregister_write(self, client, userdata, sock):
        """Unregister write callback."""
        self.loop.remove_writer(sock)

    async def run_misc_loop(self):
        """Provide loop for paho mqtt."""
        # pylint: disable=import-error, import-outside-toplevel
        import paho.mqtt.client as mqtt

        while self._client.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
