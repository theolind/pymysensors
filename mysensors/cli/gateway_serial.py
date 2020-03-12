"""Start a serial gateway."""
import click

from mysensors.cli.helper import (
    common_gateway_options,
    handle_msg,
    run_async_gateway,
    run_gateway,
)
from mysensors.gateway_serial import AsyncSerialGateway, SerialGateway


def common_serial_options(func):
    """Supply common serial gateway options."""
    func = click.option(
        "-b",
        "--baud",
        default=115200,
        show_default=True,
        type=int,
        help="Baudrate of the serial connection.",
    )(func)
    func = click.option(
        "-p", "--port", required=True, help="Serial port of the gateway."
    )(func)
    return func


@click.command(options_metavar="<options>")
@common_serial_options
@common_gateway_options
def serial_gateway(**kwargs):
    """Start a serial gateway."""
    gateway = SerialGateway(event_callback=handle_msg, **kwargs)
    run_gateway(gateway)


@click.command(options_metavar="<options>")
@common_serial_options
@common_gateway_options
def async_serial_gateway(**kwargs):
    """Start an async serial gateway."""
    gateway = AsyncSerialGateway(event_callback=handle_msg, **kwargs)
    run_async_gateway(gateway)
