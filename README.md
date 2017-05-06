# pymysensors [![Build Status][build-badge]][build]
Python API for talking to a MySensors gateway (http://www.mysensors.org/). Currently supports serial protocol v1.4, v1.5 and v2.0. Not all features of v2.0 are implemented yet.

- Supports smartsleep with serial API v2.0.
- Supports the MQTT client gateway with serial API v2.0.
- Supports OTA updates, for both [DualOptiboot](https://github.com/mysensors/DualOptiboot) and [MYSBootloader](https://github.com/mysensors/MySensorsBootloaderRF24) bootloaders.

# Usage
Currently the API is best used by implementing a callback handler

```python
import mysensors.mysensors as mysensors

def event(message):
    """Callback for mysensors updates."""
    print("sensor_update " + str(message.node_id))

GATEWAY = mysensors.SerialGateway('/dev/ttyACM0', event)
GATEWAY.start()
```

In the above example PyMysensors will call "event" whenever a node in the Mysensors network has been updated. The message passed to the callback handler has the following data:

```
Message
    gateway - the gateway instance
    node_id - the sensor node identifier
    child_id - the child sensor id
    type - the message type (int)
    ack - True is message was an ACK, false otherwise
    sub_type - the message sub_type (int)
    payload - the payload of the message (string)
```

Symbolic names for the Message types and sub_types are defined in the protocol version-specific const_X.py files.

The data structure of a gateway and it's network is described below.

```
SerialGateway/TCPGateway/MQTTGateway
    sensors - a dict containing all nodes for the gateway; node is of type Sensor

Sensor - a sensor node
    children - a dict containing all child sensors for the node
    sensor_id - node id on the MySensors network
    type - 17 for node or 18 for repeater
    sketch_name
    sketch_version
    battery_level
    protocol_version - the mysensors protocol version used by the node

ChildSensor - a child sensor
    id - Child id on the parent node
    type - Data type, S_HUM, S_TEMP etc.
    values - a dictionary of values (V_HUM, V_TEMP, etc.)
```

Getting the type and values of node 23, child sensor 4 would be performed as follows:

```python
s_type = GATEWAY.sensors[23].children[4].type
values = GATEWAY.sensors[23].children[4].values
```
To update a node child sensor value and send it to the node, use the set_child_value method in the Gateway class:

```python
# To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
GATEWAY.set_child_value(1, 1, 2, 1)
```

PyMysensors also supports three other settings. Persistence mode,
which saves the sensor network between runs, persistence file path, which sets the type and path of the persistence file and protocol version which sets the MySensors serial API version.

With persistence mode on, you can restart the gateway without
having to restart each individual node in your sensor network. To enable persistance mode, the third argument
in the constructor should be True. A path to the config file
can be specified as a fourth argument. The file type (.pickle or .json) will set which persistence protocol to use, pickle or json. JSON files can be read using a normal text editor.

The serial gateway also supports setting the baudrate, read timeout and reconnect timeout.

```python
import mysensors.mysensors as mysensors

def event(message):
    """Callback for mysensors updates."""
    print("sensor_update " + str(message.node_id))

GATEWAY = mysensors.SerialGateway(
  '/dev/ttyACM0', event_callback=event, persistence=True,
  persistence_file='somefolder/mysensors.pickle', protocol_version='1.4', baud=115200,
  timeout=1.0, reconnect_timeout=10.0)
GATEWAY.start()
```

There are two other gateway types supported besides the serial gateway: the tcp-ethernet gateway and the MQTT gateway.

The ethernet gateway is initialized similar to the serial gateway. The ethernet gateway supports setting the tcp host port, receive timeout and reconnect timeout, besides the common settings and the host ip address.

```python
GATEWAY = mysensors.TCPGateway(
  '127.0.0.1', event_callback=event, persistence=True,
  persistence_file='somefolder/mysensors.pickle', protocol_version='1.4',
  port=5003, timeout=1.0, reconnect_timeout=10.0)
```

The MQTT gateway requires MySensors serial API v2.0 and the MQTT client gateway example sketch loaded in the gateway Arduino. The gateway also requires an MQTT broker and a python MQTT client interface to the broker. See [mqtt.py](https://github.com/theolind/pymysensors/blob/master/mqtt.py) for an example of how to implement this and initialize the MQTT gateway.

## Over the air (OTA) firmware updates
Call `Gateway` method `update_fw` to set one or more nodes for OTA
firmware update. The method takes three positional arguments and one
keyword arguement. The first argument should be the node id of the node to
update. This can also be a list of many node ids. The next two arguments should
be integers representing the firwmare type and version. The keyword argument is
optional and should be a path to a hex file with the new firmware.

```python
GATEWAY.update_fw([1, 2], 1, 2, fw_path='/path/to/firmware.hex')
```

After the `update_fw` method has been called the node(s) will be requested
to restart when pymysensors Gateway receives the next set message. After
restart and during the MySensors `begin` method, the node will send a firmware
config request. The pymysensors library will respond to the config request. If
the node receives a proper firmware config response it will send a firmware
request for a block of firmware. The pymysensors library will handle this and
send a firmware response message. The latter request-response conversation will
continue until all blocks of firmware are sent. If the CRC of the transmitted
firmware match the CRC of the firmware config response, the node will restart
and load the new firmware.

[build-badge]: https://travis-ci.org/theolind/pymysensors.svg?branch=master
[build]: https://travis-ci.org/theolind/pymysensors
