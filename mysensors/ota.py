"""Handle MySensors OTA FW updates."""

import asyncio
import binascii
from dataclasses import dataclass, field
import logging
from io import StringIO
import os
from pathlib import Path
import struct

import crc
from intelhex import IntelHex, IntelHexError

from .const import SYSTEM_CHILD_ID

FIRMWARE_BLOCK_SIZE = 16
FIRMWARE_PAGE_SIZE = 128
MAX_FIRMWARE_SIZE = (65535 * FIRMWARE_BLOCK_SIZE // FIRMWARE_PAGE_SIZE) * 128
_LOGGER = logging.getLogger(__name__)


def fw_hex_to_int(hex_str, words):
    """Unpack hex string into integers.

    Use little-endian and unsigned int format. Specify number of words to
    unpack with argument words.
    """
    try:
        return struct.unpack(f"<{words}H", binascii.unhexlify(hex_str))
    except (binascii.Error, struct.error, TypeError, ValueError) as exc:
        raise ValueError("Invalid firmware payload") from exc


def fw_int_to_hex(*args):
    """Pack integers into hex string.

    Use little-endian and unsigned int format.
    """
    return binascii.hexlify(struct.pack(f"<{len(args)}H", *args)).decode("utf-8")


def compute_crc(data):
    """Compute CRC16 of data and return an int."""
    crc16 = crc.Calculator(crc.Crc16.MODBUS, optimized=True)
    return crc16.checksum(data)


def load_fw(path):
    """Open firmware file and return a binary string."""
    fname = os.path.realpath(path)
    exists = os.path.isfile(fname)
    if not exists or not os.access(fname, os.R_OK):
        _LOGGER.error("Firmware path %s does not exist or is not readable", path)
        return None
    try:
        intel_hex = IntelHex()
        with open(path, "r", encoding="utf-8") as file_handle:
            intel_hex.fromfile(file_handle, format="hex")
        return intel_hex.tobinstr()
    except (IntelHexError, TypeError, ValueError) as exc:
        _LOGGER.error("Firmware not valid, check the hex file at %s: %s", path, exc)
        return None


def prepare_fw(bin_string):
    """Check that firmware is valid and return dict with binary data."""
    bin_string += b"\xff" * (-len(bin_string) % FIRMWARE_PAGE_SIZE)
    fware = {
        "blocks": int(len(bin_string) / FIRMWARE_BLOCK_SIZE),
        "crc": compute_crc(bin_string),
        "data": bin_string,
    }
    return fware


def _uint16(value):
    """Reject values that cannot be represented by a protocol word."""
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 65535:
        raise ValueError("Firmware fields must be uint16 integers")


@dataclass(frozen=True)
class FirmwareConfig:
    """A node's five-word, little-endian firmware capability announcement."""

    firmware_type: int
    firmware_version: int
    blocks: int
    crc: int
    bootloader_version: int

    def __post_init__(self):
        """Validate all five protocol words."""
        for value in (*self.image_words, self.bootloader_version):
            _uint16(value)

    @property
    def image_words(self):
        """Return the four words identifying the running image."""
        return self.firmware_type, self.firmware_version, self.blocks, self.crc

    @property
    def payload(self):
        """Return the canonical five-word config request payload."""
        return fw_int_to_hex(*self.image_words, self.bootloader_version)

    @classmethod
    def from_payload(cls, payload):
        """Parse exactly five little-endian uint16 words."""
        return cls(*fw_hex_to_int(payload, 5))


@dataclass(frozen=True)
class FirmwareImage:
    """An immutable image, padded once to the next flash page boundary."""

    firmware_type: int
    firmware_version: int
    data: bytes
    _crc: int = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        """Validate and canonicalize bytes even when constructed directly."""
        _uint16(self.firmware_type)
        _uint16(self.firmware_version)
        if not isinstance(self.data, bytes) or not self.data:
            raise ValueError("Firmware image must contain nonempty bytes")
        if len(self.data) > MAX_FIRMWARE_SIZE:
            raise ValueError("Firmware image exceeds the uint16 block count")
        data = self.data + b"\xff" * (-len(self.data) % FIRMWARE_PAGE_SIZE)
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "_crc", compute_crc(data))

    @property
    def blocks(self) -> int:
        """Return the count of 16-byte protocol blocks."""
        return len(self.data) // FIRMWARE_BLOCK_SIZE

    @property
    def crc(self) -> int:
        """Return the MySensors CRC16/MODBUS of canonical image bytes."""
        return self._crc

    @property
    def image_words(self):
        """Return the four words identifying this image."""
        return self.firmware_type, self.firmware_version, self.blocks, self.crc

    @classmethod
    def from_bytes(
        cls, data: bytes, firmware_type: int, firmware_version: int
    ) -> "FirmwareImage":
        """Import bytes for tests or storage without file I/O."""
        return cls(firmware_type, firmware_version, data)

    @classmethod
    def from_file(
        cls, path, firmware_type: int, firmware_version: int
    ) -> "FirmwareImage":
        """Import binary or IntelHEX synchronously; use an executor if needed."""
        try:
            path = Path(path)
            if path.suffix.lower() == ".bin":
                with path.open("rb") as firmware_file:
                    data = firmware_file.read(MAX_FIRMWARE_SIZE + 1)
            elif path.suffix.lower() in (".hex", ".ihex"):
                records = path.read_text(encoding="ascii").splitlines()
                records = [record for record in records if record.strip()]
                if not records or records[-1].upper() != ":00000001FF":
                    raise ValueError("IntelHEX must end with its EOF record")
                if any(record.upper() == ":00000001FF" for record in records[:-1]):
                    raise ValueError("IntelHEX has content after EOF")
                intel_hex = IntelHex(StringIO("\n".join(records)))
                if not intel_hex.addresses():
                    raise ValueError("Firmware image is empty")
                if intel_hex.maxaddr() >= MAX_FIRMWARE_SIZE:
                    raise ValueError("Firmware image exceeds the uint16 block count")
                data = intel_hex.tobinstr(start=0)
            else:
                raise ValueError("Firmware file must be .bin, .hex or .ihex")
        except (OSError, IntelHexError, UnicodeError, TypeError) as exc:
            raise ValueError(f"Cannot import firmware: {exc}") from exc
        return cls.from_bytes(data, firmware_type, firmware_version)


class FirmwareUpdateError(RuntimeError):
    """An install failed without proving the requested image is running."""


class FirmwareUpdateBusy(FirmwareUpdateError):
    """A gateway already has an active or conflicting legacy install."""


class FirmwareUpdateTimeout(FirmwareUpdateError):
    """An install exhausted its inactivity or confirmation deadline."""


def _application_evidence(msg):
    """Identify a validated non-echo application announcement."""
    const = msg.gateway.const
    internal = {
        const.Internal.I_SKETCH_NAME,
        const.Internal.I_SKETCH_VERSION,
        getattr(const.Internal, "I_HEARTBEAT_RESPONSE", None),
    }
    return not msg.ack and (
        msg.type == const.MessageType.presentation
        or (msg.type == const.MessageType.internal and msg.sub_type in internal)
    )


class FirmwareSession:
    """Serve one explicitly armed install, then require fresh application proof."""

    # pylint: disable=too-many-instance-attributes

    def __init__(
        self, node_id, image, progress_callback, timeout, confirmation_timeout
    ):
        """Arm the session before the gateway sends a single direct reboot."""
        self.node_id = node_id
        self.image = image
        self.progress_callback = progress_callback
        self.timeout = timeout
        self.confirmation_timeout = confirmation_timeout
        self.loop = asyncio.get_running_loop()
        self.result = self.loop.create_future()
        self.changed = asyncio.Event()
        self.served = set()
        self.reboot_sent = False
        self.offered = False
        self.initial_config = None
        self.confirmed_config = None
        self.probed_phases = set()
        self.last_activity = self.loop.time()
        self.deadline = self.last_activity + min(3600.0, timeout * (image.blocks + 1))
        self.confirmation_deadline = None
        self.percent = -1

    def fail(self, reason):
        """Terminate without offering or retrying another image."""
        if not self.result.done():
            self.result.set_exception(reason)
            self.changed.set()

    def _progress(self, percent):
        if percent <= self.percent:
            return
        self.percent = percent
        if self.progress_callback is not None:
            try:
                self.progress_callback(percent)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Firmware progress callback failed")

    def _touch(self):
        self.last_activity = self.loop.time()
        self.changed.set()

    def _expires_at(self):
        if self.confirmation_deadline is not None:
            return self.confirmation_deadline
        return min(self.last_activity + self.timeout, self.deadline)

    def _is_active(self):
        if self.result.done():
            return False
        if self.loop.time() >= self._expires_at():
            self.fail(FirmwareUpdateTimeout("Firmware install timed out"))
            return False
        return True

    def config(self, msg, config):
        """Offer once, or acknowledge the final image without a second install."""
        if not self._is_active():
            return None
        retransmitted = not self.served and config == self.initial_config
        if not self.offered:
            if config.firmware_type != self.image.firmware_type:
                self.fail(FirmwareUpdateError("Firmware type does not match target"))
                return None
            if config.image_words == self.image.image_words:
                self.fail(FirmwareUpdateError("Requested image is already installed"))
                return None
            self.offered = True
            self.initial_config = config
            self._progress(0)
        elif not retransmitted:
            if len(self.served) != self.image.blocks:
                self.fail(
                    FirmwareUpdateError("Config received before complete transfer")
                )
                return None
            if config.image_words != self.image.image_words:
                self.fail(FirmwareUpdateError("Node reports a different running image"))
                return None
            self.confirmed_config = config
        # Pre-block handshake duplicates reuse the offer without extending either
        # the inactivity or fixed transfer deadline.
        if not retransmitted:
            self._touch()
        return msg.copy(
            sub_type=msg.gateway.const.Stream.ST_FIRMWARE_CONFIG_RESPONSE,
            payload=fw_int_to_hex(*self.image.image_words),
        )

    def block(self, msg):
        """Serve exact requested blocks, allowing duplicates and descending order."""
        if not self._is_active():
            return None
        try:
            firmware_type, version, index = fw_hex_to_int(msg.payload, 3)
        except ValueError as exc:
            self.fail(FirmwareUpdateError(str(exc)))
            return None
        if (
            not self.offered
            or (firmware_type, version)
            != (self.image.firmware_type, self.image.firmware_version)
            or index >= self.image.blocks
        ):
            self.fail(FirmwareUpdateError("Invalid firmware block request"))
            return None
        start = index * FIRMWARE_BLOCK_SIZE
        payload = fw_int_to_hex(firmware_type, version, index)
        payload += self.image.data[start : start + FIRMWARE_BLOCK_SIZE].hex()
        self.served.add(index)
        self._progress(min(99, len(self.served) * 100 // self.image.blocks))
        if len(self.served) == self.image.blocks and self.confirmation_deadline is None:
            self.confirmation_deadline = self.loop.time() + self.confirmation_timeout
        self._touch()
        return msg.copy(
            sub_type=msg.gateway.const.Stream.ST_FIRMWARE_RESPONSE, payload=payload
        )

    def application(self, msg):
        """Accept application evidence only after a matching final config."""
        if (
            not self._is_active()
            or not self.reboot_sent
            or msg.node_id != self.node_id
            or not _application_evidence(msg)
        ):
            return None
        if self.confirmed_config is None:
            if self.offered and len(self.served) != self.image.blocks:
                return None
            # Opening a USB serial port can discard the startup config while
            # later application announcements survive. Solicit it once per
            # reboot phase, without extending deadlines or restarting transfer.
            phase = "confirmation" if self.offered else "discovery"
            presentation = getattr(msg.gateway.const.Internal, "I_PRESENTATION", None)
            if phase in self.probed_phases or presentation is None:
                return None
            self.probed_phases.add(phase)
            return msg.copy(
                child_id=SYSTEM_CHILD_ID,
                type=msg.gateway.const.MessageType.internal,
                sub_type=presentation,
                ack=0,
                payload="",
            )
        self.result.set_result(self.confirmed_config)
        self._progress(100)
        self.changed.set()
        return None

    async def wait(self):
        """Enforce inactivity, a bounded transfer, and a fixed proof deadline."""
        try:
            while not self.result.done():
                remaining = self._expires_at() - self.loop.time()
                if remaining <= 0:
                    raise FirmwareUpdateTimeout("Firmware install timed out")
                self.changed.clear()
                wakeup = self.loop.create_task(self.changed.wait())
                try:
                    # wait_for can swallow external cancellation when its child
                    # finishes in the same tick on Python 3.10/3.11.
                    done, _ = await asyncio.wait({wakeup}, timeout=remaining)
                    if not done:
                        raise FirmwareUpdateTimeout("Firmware install timed out")
                finally:
                    wakeup.cancel()
                    await asyncio.gather(wakeup, return_exceptions=True)
            return self.result.result()
        finally:
            if not self.result.done():
                self.result.cancel()
            elif not self.result.cancelled():
                self.result.exception()


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
        self._served = {}
        self._confirmed = set()

    @property
    def active(self):
        """Return whether a legacy install is queued or awaiting completion proof."""
        return bool(self.requested or self.unstarted or self.started)

    def application(self, msg):
        """Release a completed legacy install after fresh application evidence."""
        if msg.node_id not in self._confirmed or not _application_evidence(msg):
            return
        for store in self.requested, self.unstarted, self.started, self._served:
            store.pop(msg.node_id, None)
        self._confirmed.discard(msg.node_id)
        sensor = self._sensors.get(msg.node_id)
        if sensor is not None:
            sensor.reboot = False

    def _confirm_config(self, node_id, image_words):
        self._confirmed.discard(node_id)
        fware = self.firmware.get(self.started[node_id])
        if fware is None or len(self._served.get(node_id, ())) != fware["blocks"]:
            return False
        expected = (*self.started[node_id], fware["blocks"], fware["crc"])
        if image_words != expected:
            return False
        self._confirmed.add(node_id)
        return True

    def _get_fw(self, msg, updates, req_fw_type=None, req_fw_ver=None):
        """Get firmware type, version and a dict holding binary data."""
        fw_type = None
        fw_ver = None
        if not isinstance(updates, tuple):
            updates = (updates,)
        for store in updates:
            fw_id = store.pop(msg.node_id, None)
            if fw_id is not None:
                fw_type, fw_ver = fw_id
                updates[-1][msg.node_id] = fw_id
                break
        if fw_type is None or fw_ver is None:
            _LOGGER.debug("Node %s is not set for firmware update", msg.node_id)
            return None, None, None
        if req_fw_type is not None and req_fw_ver is not None:
            if (req_fw_type, req_fw_ver) != (fw_type, fw_ver):
                return None, None, None
        fware = self.firmware.get((fw_type, fw_ver))
        if fware is None:
            _LOGGER.debug(
                "No firmware of type %s and version %s found", fw_type, fw_ver
            )
            return None, None, None
        return fw_type, fw_ver, fware

    def respond_fw(self, msg):
        """Respond to a firmware request."""
        if msg.ack:
            return None
        try:
            req_fw_type, req_fw_ver, req_blk = fw_hex_to_int(msg.payload, 3)
        except ValueError:
            return None
        _LOGGER.debug(
            "Received firmware request with firmware type %s, "
            "firmware version %s, block index %s",
            req_fw_type,
            req_fw_ver,
            req_blk,
        )
        fw_type, fw_ver, fware = self._get_fw(
            msg, (self.unstarted, self.started), req_fw_type, req_fw_ver
        )
        if fware is None or req_blk >= fware["blocks"]:
            return None
        self._served.setdefault(msg.node_id, set()).add(req_blk)
        blk_data = fware["data"][
            req_blk * FIRMWARE_BLOCK_SIZE : req_blk * FIRMWARE_BLOCK_SIZE
            + FIRMWARE_BLOCK_SIZE
        ]
        msg = msg.copy(sub_type=self._const.Stream.ST_FIRMWARE_RESPONSE)
        msg.payload = fw_int_to_hex(fw_type, fw_ver, req_blk)
        # format blk_data into payload format
        msg.payload = msg.payload + binascii.hexlify(blk_data).decode("utf-8")
        return msg

    def respond_fw_config(self, msg):
        """Respond to a firmware config request."""
        if msg.ack:
            return None
        self._confirmed.discard(msg.node_id)
        try:
            req_fw_type, req_fw_ver, req_blocks, req_crc, bloader_ver = fw_hex_to_int(
                msg.payload, 5
            )
        except ValueError:
            return None
        _LOGGER.debug(
            "Received firmware config request with firmware type %s, "
            "firmware version %s, %s blocks, CRC %s, bootloader %s",
            req_fw_type,
            req_fw_ver,
            req_blocks,
            req_crc,
            bloader_ver,
        )
        if msg.node_id in self.started:
            image_words = (req_fw_type, req_fw_ver, req_blocks, req_crc)
            if not self._confirm_config(msg.node_id, image_words):
                return None
            return msg.copy(
                sub_type=self._const.Stream.ST_FIRMWARE_CONFIG_RESPONSE,
                payload=fw_int_to_hex(*image_words),
            )
        fw_type, fw_ver, fware = self._get_fw(msg, (self.requested, self.unstarted))
        if fware is None:
            return None
        if fw_type != req_fw_type:
            _LOGGER.warning(
                "Firmware type %s of update is not identical to existing "
                "firmware type %s for node %s",
                fw_type,
                req_fw_type,
                msg.node_id,
            )
        _LOGGER.info(
            "Updating node %s to firmware type %s version %s from type %s "
            "version %s",
            msg.node_id,
            fw_type,
            fw_ver,
            req_fw_type,
            req_fw_ver,
        )
        msg = msg.copy(sub_type=self._const.Stream.ST_FIRMWARE_CONFIG_RESPONSE)
        msg.payload = fw_int_to_hex(fw_type, fw_ver, fware["blocks"], fware["crc"])
        return msg

    def make_update(self, nids, fw_type, fw_ver, fw_bin=None):
        """Start firmware update process for one or more node_id."""
        try:
            fw_type, fw_ver = int(fw_type), int(fw_ver)
        except ValueError:
            _LOGGER.error(
                "Firmware type %s or version %s not valid, please enter integers",
                fw_type,
                fw_ver,
            )
            return
        if fw_bin is not None:
            fware = prepare_fw(fw_bin)
            self.firmware[fw_type, fw_ver] = fware
        if (fw_type, fw_ver) not in self.firmware:
            _LOGGER.error(
                "No firmware of type %s and version %s found, "
                "please enter path to firmware in call",
                fw_type,
                fw_ver,
            )
            return
        if not isinstance(nids, list):
            nids = [nids]
        for node_id in nids:
            if node_id not in self._sensors:
                continue
            for store in self.unstarted, self.started, self._served:
                store.pop(node_id, None)
            self._confirmed.discard(node_id)
            self.requested[node_id] = fw_type, fw_ver
            self._sensors[node_id].reboot = True
