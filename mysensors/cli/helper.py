"""Offer common helper functions for the CLI."""
import asyncio
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


def run_async_gateway(gateway_factory):
    """Run an async gateway."""
    try:
        asyncio.run(handle_async_gateway(gateway_factory))
    except KeyboardInterrupt:
        pass


async def handle_async_gateway(gateway_factory):
    """Handle gateway."""
    gateway, stop_task = await gateway_factory()
    await gateway.start_persistence()
    await gateway.start()

    try:
        while True:
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        await gateway.stop()
        if stop_task:
            await stop_task()
        raise
