"""Setup file for mysensors package."""
from pathlib import Path

from setuptools import setup, find_packages

PROJECT_DIR = Path(__file__).parent.resolve()
VERSION = (PROJECT_DIR / "mysensors" / "VERSION").read_text(encoding="utf-8").strip()

README_FILE = PROJECT_DIR / "README.md"
LONG_DESCRIPTION = README_FILE.read_text(encoding="utf-8")

REQUIRES = [
    "awesomeversion",
    "click",
    "crcmod>=1.7",
    "getmac",
    "IntelHex>=2.2.1",
    "pyserial>=3.4",
    "pyserial-asyncio>=0.4",
    "voluptuous>=0.11.1",
]
EXTRAS = {"mqtt-client": ["paho-mqtt"]}


setup(
    name="pymysensors",
    version=VERSION,
    description="Python API for talking to a MySensors gateway",
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    url="https://github.com/theolind/pymysensors",
    author="Theodor Lindquist",
    author_email="theodor.lindquist@gmail.com",
    license="MIT License",
    install_requires=REQUIRES,
    extras_require=EXTRAS,
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    python_requires=">=3.7",
    entry_points={"console_scripts": ["pymysensors = mysensors.cli:cli"]},
    keywords=["sensor", "actuator", "IoT", "DYI"],
    zip_safe=True,
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Home Automation",
    ],
)
