"""Handle MySensors OTA FW updates."""
import binascii
import logging
import os
import struct

import crcmod.predefined
from intelhex import IntelHex, IntelHexError

FIRMWARE_BLOCK_SIZE = 16
_LOGGER = logging.getLogger(__name__)


def fw_hex_to_int(hex_str, words):
    """Unpack hex string into integers.

    Use little-endian and unsigned int format. Specify number of words to
    unpack with argument words.
    """
    return struct.unpack('<{}H'.format(words), binascii.unhexlify(hex_str))


def fw_int_to_hex(*args):
    """Pack integers into hex string.

    Use little-endian and unsigned int format.
    """
    return binascii.hexlify(
        struct.pack('<{}H'.format(len(args)), *args)).decode('utf-8')


def compute_crc(data):
    """Compute CRC16 of data and return an int."""
    crc16 = crcmod.predefined.Crc('modbus')
    crc16.update(data)
    return int(crc16.hexdigest(), 16)


def load_fw(path):
    """Open firmware file and return a binary string."""
    fname = os.path.realpath(path)
    exists = os.path.isfile(fname)
    if not exists or not os.access(fname, os.R_OK):
        _LOGGER.error(
            'Firmware path %s does not exist or is not readable',
            path)
        return None
    try:
        intel_hex = IntelHex()
        with open(path, 'r') as file_handle:
            intel_hex.fromfile(file_handle, format='hex')
        return intel_hex.tobinstr()
    except (IntelHexError, TypeError, ValueError) as exc:
        _LOGGER.error(
            'Firmware not valid, check the hex file at %s: %s', path, exc)
        return None


def prepare_fw(bin_string):
    """Check that firmware is valid and return dict with binary data."""
    pads = len(bin_string) % 128  # 128 bytes per page for atmega328
    for _ in range(128 - pads):  # pad up to even 128 bytes
        bin_string += b'\xff'
    fware = {
        'blocks': int(len(bin_string) / FIRMWARE_BLOCK_SIZE),
        'crc': compute_crc(bin_string),
        'data': bin_string,
    }
    return fware


class OTAFirmware:
    """Organize OTAFirmware updates."""

    def __init__(self, sensors, const):
        """Set up OTA firmware instance."""
        self._sensors = sensors
        self._const = const
        self.firmware = {}
        self.requested = {}
        self.started = {}
        self.unstarted = {}

    def _get_fw(self, msg, updates, req_fw_type=None, req_fw_ver=None):
        """Get firmware type, version and a dict holding binary data."""
        fw_type = None
        fw_ver = None
        if not isinstance(updates, tuple):
            updates = (updates, )
        for store in updates:
            fw_id = store.pop(msg.node_id, None)
            if fw_id is not None:
                fw_type, fw_ver = fw_id
                updates[-1][msg.node_id] = fw_id
                break
        if fw_type is None or fw_ver is None:
            _LOGGER.debug(
                'Node %s is not set for firmware update', msg.node_id)
            return None, None, None
        if req_fw_type is not None and req_fw_ver is not None:
            fw_type, fw_ver = req_fw_type, req_fw_ver
        fware = self.firmware.get((fw_type, fw_ver))
        if fware is None:
            _LOGGER.debug(
                'No firmware of type %s and version %s found',
                fw_type, fw_ver)
            return None, None, None
        return fw_type, fw_ver, fware

    def respond_fw(self, msg):
        """Respond to a firmware request."""
        req_fw_type, req_fw_ver, req_blk = fw_hex_to_int(msg.payload, 3)
        _LOGGER.debug(
            'Received firmware request with firmware type %s, '
            'firmware version %s, block index %s',
            req_fw_type, req_fw_ver, req_blk)
        fw_type, fw_ver, fware = self._get_fw(
            msg, (self.unstarted, self.started), req_fw_type, req_fw_ver)
        if fware is None:
            return None
        blk_data = fware['data'][
            req_blk * FIRMWARE_BLOCK_SIZE:
            req_blk * FIRMWARE_BLOCK_SIZE + FIRMWARE_BLOCK_SIZE]
        msg = msg.copy(sub_type=self._const.Stream.ST_FIRMWARE_RESPONSE)
        msg.payload = fw_int_to_hex(fw_type, fw_ver, req_blk)
        # format blk_data into payload format
        msg.payload = msg.payload + binascii.hexlify(blk_data).decode('utf-8')
        return msg

    def respond_fw_config(self, msg):
        """Respond to a firmware config request."""
        (req_fw_type,
         req_fw_ver,
         req_blocks,
         req_crc,
         bloader_ver) = fw_hex_to_int(msg.payload, 5)
        _LOGGER.debug(
            'Received firmware config request with firmware type %s, '
            'firmware version %s, %s blocks, CRC %s, bootloader %s',
            req_fw_type, req_fw_ver, req_blocks, req_crc, bloader_ver)
        fw_type, fw_ver, fware = self._get_fw(
            msg, (self.requested, self.unstarted))
        if fware is None:
            return None
        if fw_type != req_fw_type:
            _LOGGER.warning(
                'Firmware type %s of update is not identical to existing '
                'firmware type %s for node %s',
                fw_type, req_fw_type, msg.node_id)
        _LOGGER.info(
            'Updating node %s to firmware type %s version %s from type %s '
            'version %s', msg.node_id, fw_type, fw_ver, req_fw_type,
            req_fw_ver)
        msg = msg.copy(sub_type=self._const.Stream.ST_FIRMWARE_CONFIG_RESPONSE)
        msg.payload = fw_int_to_hex(
            fw_type, fw_ver, fware['blocks'], fware['crc'])
        return msg

    def make_update(self, nids, fw_type, fw_ver, fw_bin=None):
        """Start firmware update process for one or more node_id."""
        try:
            fw_type, fw_ver = int(fw_type), int(fw_ver)
        except ValueError:
            _LOGGER.error(
                'Firmware type %s or version %s not valid, '
                'please enter integers', fw_type, fw_ver)
            return
        if fw_bin is not None:
            fware = prepare_fw(fw_bin)
            self.firmware[fw_type, fw_ver] = fware
        if (fw_type, fw_ver) not in self.firmware:
            _LOGGER.error(
                'No firmware of type %s and version %s found, '
                'please enter path to firmware in call', fw_type, fw_ver)
            return
        if not isinstance(nids, list):
            nids = [nids]
        for node_id in nids:
            if node_id not in self._sensors:
                continue
            for store in self.unstarted, self.started:
                store.pop(node_id, None)
            self.requested[node_id] = fw_type, fw_ver
            self._sensors[node_id].reboot = True
