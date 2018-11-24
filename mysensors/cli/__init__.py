"""Implement a command line interface for pymysensors."""
import click

from mysensors import __version__

SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(
    options_metavar='', subcommand_metavar='<command>',
    context_settings=SETTINGS)
@click.version_option(__version__)
def cli():
    """Run pymysensors as an app for testing purposes."""
    pass
