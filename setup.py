"""Setup file for mysensors package."""
import os
from setuptools import setup, find_packages

exec(open('mysensors/version.py').read())

if os.path.exists('README.rst'):
    README = open('README.rst').read()
else:
    README = ''

REQUIRES = [
    'pyserial>=3.1.1', 'crcmod>=1.7', 'IntelHex>=2.1', 'voluptuous>=0.10.5',
]

setup(
    name='pymysensors',
    version=__version__,
    description='Python API for talking to a MySensors gateway',
    long_description=README,
    url='https://github.com/theolind/pymysensors',
    author='Theodor Lindquist',
    author_email='theodor.lindquist@gmail.com',
    license='MIT License',
    install_requires=REQUIRES,
    packages=find_packages(exclude=['tests', 'tests.*']),
    keywords=['sensor', 'actuator', 'IoT', 'DYI'],
    zip_safe=True,
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Home Automation',
    ])
