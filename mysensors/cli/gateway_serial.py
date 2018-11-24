"""Start a serial gateway."""
import asyncio
import time

import click

from mysensors.cli.helper import common_gateway_options, handle_msg
from mysensors.gateway_serial import AsyncSerialGateway, SerialGateway


def common_serial_options(func):
    """Supply common serial gateway options."""
    func = click.option(
        '-b', '--baud', default=115200, show_default=True, type=int,
        help='Baudrate of the serial connection.')(func)
    func = click.option(
        '-p', '--port', required=True, help='Serial port of the gateway.'
        )(func)
    return func


@click.command(options_metavar='<options>')
@common_serial_options
@common_gateway_options
def serial_gateway(**kwargs):
    """Start a serial gateway."""
    gateway = SerialGateway(event_callback=handle_msg, **kwargs)
    gateway.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        gateway.stop()


@click.command(options_metavar='<options>')
@common_serial_options
@common_gateway_options
def async_serial_gateway(**kwargs):
    """Start an async serial gateway."""
    loop = asyncio.get_event_loop()
    gateway = AsyncSerialGateway(
        event_callback=handle_msg, loop=loop, **kwargs)
    try:
        loop.run_until_complete(gateway.start())
        loop.run_forever()
    except KeyboardInterrupt:
        gateway.stop()
        loop.close()
