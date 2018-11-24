"""Implement a command line interface for pymysensors."""
import logging

import click

from mysensors import __version__
from mysensors.cli.gateway_serial import serial_gateway

SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(
    options_metavar='', subcommand_metavar='<command>',
    context_settings=SETTINGS)
@click.option('--debug', is_flag=True, help='Start pymysensors in debug mode.')
@click.version_option(__version__)
def cli(debug):
    """Run pymysensors as an app for testing purposes."""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


cli.add_command(serial_gateway)
