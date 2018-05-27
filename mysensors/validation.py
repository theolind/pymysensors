"""Expose validators to use in the library."""
# pylint: disable=import-error, no-name-in-module
from distutils.version import LooseVersion as parse_ver
import logging

import voluptuous as vol

# pylint: disable=invalid-name

_LOGGER = logging.getLogger(__name__)

percent_int = vol.All(vol.Coerce(int), vol.Range(min=0, max=100))


def is_version(value):
    """Validate that value is a valid version string."""
    try:
        value = str(value)
        if not parse_ver('1.4') <= parse_ver(value):
            raise ValueError()
        return value
    except (AttributeError, TypeError, ValueError):
        raise vol.Invalid(
            '{} is not a valid version specifier'.format(value))


def safe_is_version(value):
    """Validate that value is a valid version string."""
    try:
        return is_version(value)
    except vol.Invalid:
        _LOGGER.warning(
            '%s is not a valid version specifier, '
            'falling back to version 1.4', value)
        return '1.4'


def is_battery_level(value):
    """Validate that value is a valid battery level integer."""
    try:
        value = percent_int(value)
        return value
    except vol.Invalid:
        _LOGGER.warning(
            '%s is not a valid battery level, falling back to battery level 0',
            value)
        return 0


def is_heartbeat(value):
    """Validate that value is a valid heartbeat integer."""
    try:
        value = vol.Coerce(int)(value)
        return value
    except vol.Invalid:
        _LOGGER.warning(
            '%s is not a valid heartbeat value, falling back to heartbeat 0',
            value)
        return 0
