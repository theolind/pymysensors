"""Offer common helper functions for the CLI."""
import click


def common_gateway_options(func):
    """Supply common gateway options."""
    func = click.option(
        '-v', '--protocol_version', help='Protocol version of the gateway.',
        default='2.2', show_default=True)(func)
    func = click.option(
        '-s', '--persistence', help='Turn on persistence.',
        is_flag=True)(func)
    return func


def handle_msg(msg):
    """Handle mysensors updates."""
    print('Received message:', str(msg.node_id))
