"""Setup file for mysensors package."""
from setuptools import setup, find_packages

exec(open('mysensors/version.py').read())

README = open('README.md').read()

REQUIRES = [
    'crcmod>=1.7', 'get-mac>=0.2.1', 'IntelHex>=2.2.1', 'pyserial>=3.4',
    'pyserial-asyncio>=0.4', 'voluptuous>=0.11.1',
]

setup(
    name='pymysensors',
    version=__version__,
    description='Python API for talking to a MySensors gateway',
    long_description=README,
    long_description_content_type='text/markdown',
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
