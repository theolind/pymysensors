"""Offer common helper functions for the CLI."""
import time

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


def run_gateway(gateway):
    """Run a sync gateway."""
    gateway.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        gateway.stop()


def run_async_gateway(gateway):
    """Run an async gateway."""
    try:
        gateway.loop.run_until_complete(gateway.start())
        gateway.loop.run_forever()
    except KeyboardInterrupt:
        gateway.stop()
        gateway.loop.close()
