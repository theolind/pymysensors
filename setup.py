"""Setup file for mysensors package."""
from setuptools import setup, find_packages

with open('README.md') as readme_file:
    README = readme_file.read()

setup(
    name='pymysensors',
    version='0.10.0.dev0',
    description='Python API for talking to a MySensors gateway',
    long_description=README,
    url='https://github.com/theolind/pymysensors',
    author='Theodor Lindquist',
    license='MIT License',
    install_requires=['pyserial>=3.1.1', 'crcmod>=1.7', 'IntelHex>=2.1'],
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
