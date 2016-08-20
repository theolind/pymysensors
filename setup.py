"""Setup file for mysensors package."""
from setuptools import setup

setup(name='pymysensors',
      version='0.7',
      description='Python API for talking to a MySensors gateway',
      url='https://github.com/theolind/pymysensors',
      author='Theodor Lindquist',
      license='MIT',
      install_requires=['pyserial>=3.1.1', 'crcmod>=1.7', 'IntelHex>=2.1'],
      packages=['mysensors'],
      zip_safe=True)
