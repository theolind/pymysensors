"""Show how to implement pymysensors async."""
import asyncio
import logging

import mysensors.mysensors as mysensors


logging.basicConfig(level=logging.DEBUG)


def event(message):
    """Handle mysensors updates."""
    print("sensor_update " + str(message.node_id))


LOOP = asyncio.get_event_loop()
LOOP.set_debug(True)

try:
    # To create a serial gateway.
    GATEWAY = mysensors.AsyncSerialGateway(
        "/dev/ttyACM0", loop=LOOP, event_callback=event, protocol_version="2.1"
    )
    LOOP.run_until_complete(GATEWAY.start())
    LOOP.run_forever()
except KeyboardInterrupt:
    GATEWAY.stop()
    LOOP.close()
except Exception as exc:  # pylint: disable=broad-except
    print(exc)

# To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
# GATEWAY.set_child_value(1, 1, 2, 1)
