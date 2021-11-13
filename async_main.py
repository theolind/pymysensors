"""Show how to implement pymysensors async."""
import asyncio
import logging

from mysensors import mysensors


logging.basicConfig(level=logging.DEBUG)


def event(message):
    """Handle mysensors updates."""
    print("sensor_update " + str(message.node_id))


async def main():
    """Run main function."""
    # To create a serial gateway.
    gateway = mysensors.AsyncSerialGateway(
        "/dev/ttyACM0", event_callback=event, protocol_version="2.1"
    )
    await gateway.start()
    # To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
    # gateway.set_child_value(1, 1, 2, 1)
    try:
        await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        await gateway.stop()
        raise
    except Exception as exc:  # pylint: disable=broad-except
        print(exc)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
