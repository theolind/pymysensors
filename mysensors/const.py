"""Helpers for const."""
from importlib import import_module

from awesomeversion import AwesomeVersion

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
            if AwesomeVersion(protocol_version) >= AwesomeVersion(const_version)
        ),
        "mysensors.const_14",
    )
    if path in LOADED_CONST:
        return LOADED_CONST[path]
    const = import_module(path)
    LOADED_CONST[path] = const  # Cache the module
    return const
