"""Test mysensors OTA FW with unittest."""
import binascii
import struct
import tempfile
from unittest import TestCase, main

from mysensors import Gateway, Sensor
from mysensors.ota import FIRMWARE_BLOCK_SIZE, load_fw
from mysensors.task import SyncTasks

FW_TYPE = 1
FW_VER = 1
HEX_FILE_STR = ":100000000C94AC030C9491240C94B8240C94D40359\n:00000001FF"
PADDED_HEX_STR = (
    "0c94ac030c9491240c94b8240c94d403ffffffffffffffffffffffffffffffff"
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
    "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
)
CRC = 362
BLOCKS = int(len(PADDED_HEX_STR) / (2 * FIRMWARE_BLOCK_SIZE))
BAD_HEX_FILE = "badcontent"


class TestOTA(TestCase):
    """Test the OTA FW logic."""

    def setUp(self):
        """Set up gateway."""
        self.gateway = Gateway()
        self.gateway.tasks = SyncTasks(
            self.gateway.const, False, None, self.gateway.sensors, None
        )

    def _add_sensor(self, sensorid):
        """Add sensor node. Return sensor node instance."""
        self.gateway.sensors[sensorid] = Sensor(sensorid)
        return self.gateway.sensors[sensorid]

    def _setup_firmware(self, nids, hex_file_str):
        """Add node(s) and call update_fw method."""
        if not isinstance(nids, list):
            nids = [nids]
        sensors = [self._add_sensor(node_id) for node_id in nids]
        with tempfile.NamedTemporaryFile() as file_handle:
            file_handle.write(hex_file_str.encode("utf-8"))
            file_handle.flush()
            fw_bin = load_fw(file_handle.name)
            self.gateway.tasks.ota.make_update(
                [sensor.sensor_id for sensor in sensors], FW_TYPE, FW_VER, fw_bin
            )

    def test_bad_fw(self):
        """Test firmware update with bad firmware."""
        self._setup_firmware(1, BAD_HEX_FILE)
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        self.assertEqual(ret, None)

    def test_no_fw(self):
        """Test firmware update with no firmware loaded."""
        sensor = self._add_sensor(1)
        self.gateway.tasks.ota.make_update(sensor.sensor_id, FW_TYPE, FW_VER)
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        self.assertEqual(ret, None)

    def test_bad_fw_type_or_version(self):
        """Test firmware update with bad firmware type or version."""
        sensor = self._add_sensor(1)
        self.gateway.tasks.ota.make_update(sensor.sensor_id, "a", "b")
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        self.assertEqual(ret, None)

    def test_update_for_no_node(self):
        """Test firmware update for a not existing node."""
        with tempfile.NamedTemporaryFile() as file_handle:
            file_handle.write(HEX_FILE_STR.encode("utf-8"))
            file_handle.flush()
            fw_bin = load_fw(file_handle.name)
            self.gateway.tasks.ota.make_update(1, FW_TYPE, FW_VER, fw_bin)
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        self.assertEqual(ret, None)

    def test_respond_fw_config(self):
        """Test respond to firmware config request."""
        self._setup_firmware(1, HEX_FILE_STR)
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        payload = binascii.hexlify(
            struct.pack("<4H", FW_TYPE, FW_VER, BLOCKS, CRC)
        ).decode("utf-8")
        self.assertEqual(ret, "1;255;4;0;1;{}\n".format(payload))

    def test_respond_fw(self):
        """Test respond to firmware request."""
        self._setup_firmware(1, HEX_FILE_STR)
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        # Test that firmware config request generates a response.
        # A detailed test of the response is done in another test.
        self.assertIsNotNone(ret)
        for block in reversed(range(BLOCKS)):
            payload = binascii.hexlify(
                struct.pack("<3H", FW_TYPE, FW_VER, block)
            ).decode("utf-8")
            ret = self.gateway.logic("1;255;4;0;2;{}\n".format(payload))
            payload = binascii.hexlify(
                struct.pack("<3H", FW_TYPE, FW_VER, block)
            ).decode("utf-8")
            blk_data = binascii.unhexlify(PADDED_HEX_STR.encode("utf-8"))[
                block * FIRMWARE_BLOCK_SIZE : block * FIRMWARE_BLOCK_SIZE
                + FIRMWARE_BLOCK_SIZE
            ]
            payload += binascii.hexlify(blk_data).decode("utf-8")
            self.assertEqual(ret, "1;255;4;0;3;{}\n".format(payload))
        # Test that firmware config request does not generate a new response.
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        self.assertEqual(ret, None)

    def test_restart_fw_update(self):
        """Test response after a new call to update firmware of node."""
        self._setup_firmware(1, HEX_FILE_STR)
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        # Test that firmware config request generates a response.
        # A detailed test of the response is done in another test.
        self.assertIsNotNone(ret)
        block = BLOCKS - 1
        payload = binascii.hexlify(struct.pack("<3H", FW_TYPE, FW_VER, block)).decode(
            "utf-8"
        )
        ret = self.gateway.logic("1;255;4;0;2;{}\n".format(payload))
        payload = binascii.hexlify(struct.pack("<3H", FW_TYPE, FW_VER, block)).decode(
            "utf-8"
        )
        blk_data = binascii.unhexlify(PADDED_HEX_STR.encode("utf-8"))[
            block * FIRMWARE_BLOCK_SIZE : block * FIRMWARE_BLOCK_SIZE
            + FIRMWARE_BLOCK_SIZE
        ]
        payload += binascii.hexlify(blk_data).decode("utf-8")
        self.assertEqual(ret, "1;255;4;0;3;{}\n".format(payload))
        with tempfile.NamedTemporaryFile() as file_handle:
            file_handle.write(HEX_FILE_STR.encode("utf-8"))
            file_handle.flush()
            fw_bin = load_fw(file_handle.name)
            self.gateway.tasks.ota.make_update(1, FW_TYPE, FW_VER, fw_bin)
        payload = binascii.hexlify(
            struct.pack("<3H", FW_TYPE, FW_VER, block - 1)
        ).decode("utf-8")
        ret = self.gateway.logic("1;255;4;0;2;{}\n".format(payload))
        # Test that firmware request does not generate a response.
        self.assertEqual(ret, None)
        # Test that firmware config request generates a new response.
        ret = self.gateway.logic("1;255;4;0;0;01000200B00626E80300\n")
        self.assertIsNotNone(ret)
        # Test that firmware request generates all the correct responses.
        for block in reversed(range(BLOCKS)):
            payload = binascii.hexlify(
                struct.pack("<3H", FW_TYPE, FW_VER, block)
            ).decode("utf-8")
            ret = self.gateway.logic("1;255;4;0;2;{}\n".format(payload))
            payload = binascii.hexlify(
                struct.pack("<3H", FW_TYPE, FW_VER, block)
            ).decode("utf-8")
            blk_data = binascii.unhexlify(PADDED_HEX_STR.encode("utf-8"))[
                block * FIRMWARE_BLOCK_SIZE : block * FIRMWARE_BLOCK_SIZE
                + FIRMWARE_BLOCK_SIZE
            ]
            payload += binascii.hexlify(blk_data).decode("utf-8")
            self.assertEqual(ret, "1;255;4;0;3;{}\n".format(payload))

    def test_respond_fw_two_nodes(self):
        """Test respond to firmware request for two different nodes."""
        nodes = [1, 2]
        self._setup_firmware(nodes, HEX_FILE_STR)
        for node_id in nodes:
            ret = self.gateway.logic(
                "{};255;4;0;0;01000200B00626E80300\n".format(node_id)
            )
            # Test that firmware config request generates a response.
            # A detailed test of the response is done in another test.
            self.assertIsNotNone(ret)
        for block in reversed(range(BLOCKS)):
            for node_id in nodes:
                payload = binascii.hexlify(
                    struct.pack("<3H", FW_TYPE, FW_VER, block)
                ).decode("utf-8")
                ret = self.gateway.logic("{};255;4;0;2;{}\n".format(node_id, payload))
                payload = binascii.hexlify(
                    struct.pack("<3H", FW_TYPE, FW_VER, block)
                ).decode("utf-8")
                blk_data = binascii.unhexlify(PADDED_HEX_STR.encode("utf-8"))[
                    block * FIRMWARE_BLOCK_SIZE : block * FIRMWARE_BLOCK_SIZE
                    + FIRMWARE_BLOCK_SIZE
                ]
                payload += binascii.hexlify(blk_data).decode("utf-8")
                self.assertEqual(ret, "{};255;4;0;3;{}\n".format(node_id, payload))

    def test_different_firmware_type(self):
        """Test respond to fw config request for a different firmware type."""
        self._setup_firmware(1, HEX_FILE_STR)
        ret = self.gateway.logic("1;255;4;0;0;02000200B00626E80300\n")
        payload = binascii.hexlify(
            struct.pack("<4H", FW_TYPE, FW_VER, BLOCKS, CRC)
        ).decode("utf-8")
        self.assertEqual(ret, "1;255;4;0;1;{}\n".format(payload))


if __name__ == "__main__":
    main()
