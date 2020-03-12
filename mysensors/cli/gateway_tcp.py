"""Start a tcp gateway."""
import click

from mysensors.cli.helper import (
    common_gateway_options,
    handle_msg,
    run_async_gateway,
    run_gateway,
)
from mysensors.gateway_tcp import AsyncTCPGateway, TCPGateway


def common_tcp_options(func):
    """Supply common tcp gateway options."""
    func = click.option(
        "-p",
        "--port",
        default=5003,
        show_default=True,
        type=int,
        help="TCP port of the connection.",
    )(func)
    func = click.option(
        "-H", "--host", required=True, help="TCP address of the gateway."
    )(func)
    return func


@click.command(options_metavar="<options>")
@common_tcp_options
@common_gateway_options
def tcp_gateway(**kwargs):
    """Start a tcp gateway."""
    gateway = TCPGateway(event_callback=handle_msg, **kwargs)
    run_gateway(gateway)


@click.command(options_metavar="<options>")
@common_tcp_options
@common_gateway_options
def async_tcp_gateway(**kwargs):
    """Start an async tcp gateway."""
    gateway = AsyncTCPGateway(event_callback=handle_msg, **kwargs)
    run_async_gateway(gateway)
