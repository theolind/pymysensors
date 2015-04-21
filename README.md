# pymysensors
Python API for talking to a MySensors gateway

# Usage
Currently the API is best used by implementing a callback handler
```python
import pymysensors.mysensors.mysensors as mysensors

def event(type, nid):
    print(type+" "+str(nid))

gw = mysensors.SerialGateway('/dev/ttyACM0', event)
gw.start()
```

In the above example PyMysensors will call "event" whenever a node in the Mysensors network has been updated.

The data structure of a gateway and it's network is described below.
```
SerialGateway
    sensors - a dict containing all nodes for the gateway; node is of type Sensor

Sensor - a sensor node
    children - a dict containing all child sensors for the gateway
    id - node id on the MySensors network
    type
    sketch_name
    sketch_version
    battery_level

ChildSensor - a child sensor
    id - Child id on the parent node
    type - Data type, S_HUM, S_TEMP etc.
    values - a dictionary of values (V_HUM, V_TEMP, etc.)
```

Getting the type and values of node 23, child sensor 4 would be performed as follows:
```
type = gw.sensors[23].children[4].type
values = gw.sensors[23].children[4].values
```

PyMysensors also supports three other settings. Debug mode, which prints debug information, persistence mode,
which saves the sensor network between runs. With persistence mode on, you can restart the gateway without
having to restart each individual node in your sensor network. To enable persistance mode, the third argument
in the constructor should be True. Debug mode is enabled by setting SerialGateway.debug = True. A path to the config file
can be specified as a fourth argument.

```
import pymysensors.mysensors.mysensors as mysensors

gw = mysensors.SerialGateway('/dev/ttyACM0', None, True, 'somefolder/mysensors.pickle')
gw.debug = True
gw.start()
