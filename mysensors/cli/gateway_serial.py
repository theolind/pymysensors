"""Start a serial gateway."""
import time

import click

from mysensors.cli.helper import common_gateway_options, handle_msg
from mysensors.gateway_serial import SerialGateway


@click.command(options_metavar='<options>')
@click.option(
    '-p', '--port', required=True, help='Serial port of the gateway.')
@click.option(
    '-b', '--baud', default=115200, show_default=True, type=int,
    help='Baudrate of the serial connection.')
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
