"""Setup file for mysensors package."""
from setuptools import setup

setup(name='pymysensors',
      version='0.6',
      description='Python API for talking to a MySensors gateway',
      url='https://github.com/theolind/pymysensors',
      author='Theodor Lindquist',
      license='MIT',
      install_requires=['pyserial<=2.5'],
      packages=['mysensors'],
      zip_safe=True)
