# pymysensors [![Build Status][build-badge]][build]
Python API for talking to a MySensors gateway (http://www.mysensors.org/). Currently supports serial protocol v1.4 and v1.5.

Does not support OTA updates.

# Usage
Currently the API is best used by implementing a callback handler
```python
import mysensors.mysensors as mysensors

def event(update_type, nid):
    """Callback for mysensors updates."""
    print(update_type + " " + str(nid))

GATEWAY = mysensors.SerialGateway('/dev/ttyACM0', event)
GATEWAY.start()
```

In the above example PyMysensors will call "event" whenever a node in the Mysensors network has been updated.

The data structure of a gateway and it's network is described below.
```
SerialGateway
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

PyMysensors also supports three other settings. Debug mode, which prints debug information, persistence mode,
which saves the sensor network between runs and persistence file path, which sets the type and path of the persistence file.

Debug mode is enabled by setting SerialGateway.debug = True. With persistence mode on, you can restart the gateway without
having to restart each individual node in your sensor network. To enable persistance mode, the third argument
in the constructor should be True. A path to the config file
can be specified as a fourth argument. The file type (.pickle or .json) will set which persistence protocol to use, pickle or json. JSON files can be read using a normal text editor.

```python
import mysensors.mysensors as mysensors

GATEWAY = mysensors.SerialGateway('/dev/ttyACM0', None, True, 'somefolder/mysensors.pickle')
GATEWAY.debug = True
GATEWAY.start()
```

[build-badge]: https://travis-ci.org/theolind/pymysensors.svg?branch=master
[build]: https://travis-ci.org/theolind/pymysensors
