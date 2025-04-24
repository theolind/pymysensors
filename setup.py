"""Setup file for mysensors package."""

from pathlib import Path

from setuptools import setup

PROJECT_DIR = Path(__file__).parent.resolve()
VERSION = (PROJECT_DIR / "mysensors" / "VERSION").read_text(encoding="utf-8").strip()


setup(version=VERSION)
