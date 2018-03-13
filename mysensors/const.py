"""Helpers for const."""
# pylint: disable=no-name-in-module, import-error
from distutils.version import LooseVersion as parse_ver
from importlib import import_module

LOADED_CONST = {}


def get_const(protocol_version):
    """Return the const module for the protocol_version."""
    version = protocol_version
    if parse_ver('1.5') <= parse_ver(version) < parse_ver('2.0'):
        path = 'mysensors.const_15'
    elif parse_ver(version) >= parse_ver('2.2'):
        path = 'mysensors.const_22'
    elif parse_ver(version) >= parse_ver('2.1'):
        path = 'mysensors.const_21'
    elif parse_ver(version) >= parse_ver('2.0'):
        path = 'mysensors.const_20'
    else:
        path = 'mysensors.const_14'
    if path in LOADED_CONST:
        return LOADED_CONST[path]
    const = import_module(path)
    LOADED_CONST[path] = const  # Cache the module
    return const
