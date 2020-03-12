"""Offer common helper functions for the CLI."""
import logging
import time

import click

_LOGGER = logging.getLogger(__name__)


def common_gateway_options(func):
    """Supply common gateway options."""
    func = click.option(
        "-v",
        "--protocol_version",
        help="Protocol version of the gateway.",
        default="2.2",
        show_default=True,
    )(func)
    func = click.option(
        "-s", "--persistence", help="Turn on persistence.", is_flag=True
    )(func)
    return func


def handle_msg(msg):
    """Handle mysensors updates."""
    _LOGGER.info("Received message: %s", msg.encode().strip())


def run_gateway(gateway):
    """Run a sync gateway."""
    gateway.start_persistence()
    gateway.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        gateway.stop()


def run_async_gateway(gateway, stop_task=None):
    """Run an async gateway."""
    try:
        gateway.tasks.loop.run_until_complete(gateway.start_persistence())
        gateway.tasks.loop.run_until_complete(gateway.start())
        gateway.tasks.loop.run_forever()
    except KeyboardInterrupt:
        gateway.tasks.loop.run_until_complete(gateway.stop())
        if stop_task:
            gateway.tasks.loop.run_until_complete(stop_task)
        gateway.tasks.loop.close()
