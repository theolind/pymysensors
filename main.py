"""Example for using pymysensors."""
import logging

import mysensors.mysensors as mysensors

logging.basicConfig(level=logging.DEBUG)


def event(message):
    """Callback for mysensors updates."""
    print("sensor_update " + str(message.node_id))


# To create a serial gateway.
GATEWAY = mysensors.SerialGateway(
    "/dev/ttyACM0", event_callback=event, protocol_version="2.0"
)

# To create a TCP gateway.
# GATEWAY = mysensors.TCPGateway('127.0.0.1', event_callback=event)

GATEWAY.start()
# To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
# GATEWAY.set_child_value(1, 1, 2, 1)
# GATEWAY.stop()
