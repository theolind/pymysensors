"""Util functions and classes."""

# Copyright 2013-2018 The Home Assistant Authors
# https://github.com/home-assistant/home-assistant/blob/master/LICENSE.md


class Registry(dict):
    """Registry of items."""

    def register(self, name):
        """Return decorator to register item with a specific name."""

        def decorator(func):
            """Register decorated function."""
            self[name] = func
            return func

        return decorator
