"""Helpers for const."""
# pylint: disable=no-name-in-module, import-error
from distutils.version import LooseVersion as parse_ver
from importlib import import_module

LOADED_CONST = {}

CONST_VERSIONS = {
    "1.4": "mysensors.const_14",
    "1.5": "mysensors.const_15",
    "2.0": "mysensors.const_20",
    "2.1": "mysensors.const_21",
    "2.2": "mysensors.const_22",
}

SYSTEM_CHILD_ID = 255


def get_const(protocol_version):
    """Return the const module for the protocol_version."""
    path = next(
        (
            CONST_VERSIONS[const_version]
            for const_version in sorted(CONST_VERSIONS, reverse=True)
            if parse_ver(protocol_version) >= parse_ver(const_version)
        ),
        "mysensors.const_14",
    )
    if path in LOADED_CONST:
        return LOADED_CONST[path]
    const = import_module(path)
    LOADED_CONST[path] = const  # Cache the module
    return const
