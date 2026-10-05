"""Exercise native OTA through the actual parser, scheduler and transport."""

import asyncio
from dataclasses import FrozenInstanceError
import struct
from unittest import IsolatedAsyncioTestCase, mock

from intelhex import IntelHex
import pytest

from mysensors import BaseAsyncGateway, BaseSyncGateway
from mysensors.gateway_mqtt import AsyncMQTTGateway
from mysensors.gateway_tcp import AsyncTCPGateway
from mysensors.ota import (
    FirmwareConfig,
    FirmwareImage,
    FirmwareUpdateBusy,
    FirmwareUpdateError,
    FirmwareUpdateTimeout,
    MAX_FIRMWARE_SIZE,
    prepare_fw,
)
from mysensors.transport import AsyncTransport


def words(*values):
    """Encode independent protocol fixtures without the library serializer."""
    return struct.pack(f"<{len(values)}H", *values).hex().upper()


def line(subtype, payload, node=31, child=255, ack=0, kind=4):
    """Build a serial protocol fixture."""
    return f"{node};{child};{kind};{ack};{subtype};{payload}\n"


def test_config_words():
    """All five config words are uint16 and bootloader metadata is separate."""
    config = FirmwareConfig(42, 9, 16, 0x1234, 0x0301)
    assert config.payload == "2a000900100034120103"
    assert FirmwareConfig.from_payload(config.payload.upper()) == config
    assert config.image_words == (42, 9, 16, 0x1234)
    with pytest.raises(FrozenInstanceError):
        config.blocks = 1
    for value in (-1, 65536, True, "1"):
        with pytest.raises(ValueError):
            FirmwareConfig(value, 0, 0, 0, 0)
    for payload in ("", "zz" * 10, words(1, 2, 3, 4), words(1, 2, 3, 4, 5, 6)):
        with pytest.raises(ValueError):
            FirmwareConfig.from_payload(payload)


@pytest.mark.parametrize(
    "size,expected", [(1, 128), (128, 128), (129, 256), (256, 256)]
)
def test_image_padding(size, expected):
    """Canonical images and legacy preparation never add an aligned page."""
    raw = bytes(index % 256 for index in range(size))
    image = FirmwareImage.from_bytes(raw, 42, 9)
    assert image.data == raw + b"\xff" * (expected - size)
    assert image.blocks == expected // 16
    assert image.crc == prepare_fw(raw)["crc"]
    assert FirmwareImage.from_bytes(image.data, 42, 9) == image
    assert len(prepare_fw(raw)["data"]) == expected


def test_image_bounds():
    """Enforce the uint16 block count, including page rounding."""
    image = FirmwareImage.from_bytes(b"\xff" * MAX_FIRMWARE_SIZE, 65535, 0)
    assert image.blocks == 65528
    for raw in (b"", b"\x00" * (MAX_FIRMWARE_SIZE + 1), bytearray(b"a")):
        with pytest.raises(ValueError):
            FirmwareImage.from_bytes(raw, 42, 9)
    for value in (-1, 65536, True, "9"):
        with pytest.raises(ValueError):
            FirmwareImage.from_bytes(b"x", 42, value)


@pytest.mark.parametrize("suffix", [".bin", ".hex", ".ihex", ".HEX"])
def test_image_import(tmp_path, suffix):
    """Binary and IntelHEX files produce identical page bytes and known CRC."""
    path = tmp_path / f"firmware{suffix}"
    raw = bytes.fromhex("0c94ac030c9491240c94b8240c94d403")
    if suffix == ".bin":
        path.write_bytes(raw)
    else:
        IntelHex(dict(enumerate(raw))).write_hex_file(str(path))
    image = FirmwareImage.from_file(path, 1, 1)
    assert image.data == raw + b"\xff" * 112
    assert image.crc == 362
    assert image.blocks == 8


@pytest.mark.parametrize(
    "contents",
    [
        "",
        ":00000001FF",
        "badcontent",
        ":0100000000FE",
        "\udcff",
        ":0100000000FF",
        ":0100000000FF\n:00000001FF\nbadcontent",
        ":0100000000FF\n:00000001FF\n:00000001FF",
    ],
)
def test_malformed_hex(tmp_path, contents):
    """Reject empty, malformed, bad-checksum and non-UTF-8 IntelHEX files."""
    path = tmp_path / "bad.hex"
    path.write_bytes(contents.encode("utf-8", errors="surrogateescape"))
    with pytest.raises(ValueError):
        FirmwareImage.from_file(path, 42, 9)


def test_file_bounds_and_offsets(tmp_path):
    """Preserve address-zero offsets and reject huge sparse images before allocation."""
    path = tmp_path / "sparse.hex"
    IntelHex({16: 1, 17: 2}).write_hex_file(str(path))
    assert FirmwareImage.from_file(path, 42, 9).data[:18] == b"\xff" * 16 + b"\x01\x02"
    IntelHex({MAX_FIRMWARE_SIZE: 1}).write_hex_file(str(path))
    with pytest.raises(ValueError):
        FirmwareImage.from_file(path, 42, 9)
    path = tmp_path / "large.bin"
    path.write_bytes(b"\x00" * (MAX_FIRMWARE_SIZE + 1))
    with pytest.raises(ValueError):
        FirmwareImage.from_file(path, 42, 9)
    for path in (tmp_path / "missing.bin", tmp_path / "firmware.txt"):
        with pytest.raises(ValueError):
            FirmwareImage.from_file(path, 42, 9)
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    with pytest.raises(ValueError):
        FirmwareImage.from_file(path, 42, 9)


class TestNativeSession(IsolatedAsyncioTestCase):
    """Test native sessions with real protocol parsing and transport writes."""

    # pylint: disable=too-many-instance-attributes,too-many-public-methods

    async def asyncSetUp(self):
        """Create an unpresented target and a byte transport for the real protocol."""
        self.events = []
        self.progress = []
        self.writes = []
        self.gateway = BaseAsyncGateway(
            None, protocol_version="2.3", event_callback=self.events.append
        )
        self.connection = mock.Mock()
        self.connection.write.side_effect = self.writes.append

        async def connect(transport):
            """Reattach the serial protocol to a connected byte transport."""
            transport.protocol.connection_made(self.connection)

        self.transport = AsyncTransport(self.gateway, connect)
        self.gateway.tasks.transport = self.transport
        await self.gateway.start()
        self.image = FirmwareImage.from_bytes(bytes(range(129)), 42, 9)
        self.current = FirmwareConfig(42, 8, 8, 123, 0x0301)
        self.final = FirmwareConfig(42, 9, self.image.blocks, self.image.crc, 0x0302)
        self.task = None

    async def asyncTearDown(self):
        """Clear unfinished installs and connection tasks."""
        if self.task is not None and not self.task.done():
            self.task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await self.task
        await self.gateway.stop()

    def receive(self, message):
        """Feed fragmented bytes through the real serial protocol and async jobs."""
        data = message.encode()
        for offset in range(0, len(data), 3):
            self.transport.protocol.data_received(data[offset : offset + 3])

    async def arm(self, **kwargs):
        """Start an install and let it send its one direct reboot."""
        self.progress.clear()
        self.task = asyncio.create_task(
            self.gateway.install_firmware(
                31, self.image, progress_callback=self.progress.append, **kwargs
            )
        )
        await asyncio.sleep(0)
        assert self.writes == [b"31;255;3;0;13;\n"]
        return self.task

    def offer(self):
        """Present the initial bootloader config and check the four-word offer."""
        self.receive(line(0, self.current.payload))
        assert (
            self.writes[-1] == line(1, words(*self.image.image_words).lower()).encode()
        )

    def transfer(self):
        """Request descending blocks and an initial duplicate."""
        order = list(reversed(range(self.image.blocks)))
        order.insert(1, order[0])
        for index in order:
            self.receive(line(2, words(42, 9, index)))
            expected = words(42, 9, index).lower()
            expected += self.image.data[index * 16 : (index + 1) * 16].hex()
            assert self.writes[-1] == line(3, expected).encode()
        assert self.progress[-1] == 99
        assert self.progress == sorted(set(self.progress))

    async def test_complete_config_then_fresh_application(self):
        """Neither transfer completion nor bootloader config proves running code."""
        await self.arm()
        assert 31 not in self.gateway.sensors
        self.offer()
        self.receive(line(17, "2.3.2", kind=0))
        self.transfer()
        self.receive(line(22, "1", kind=3))
        assert not self.task.done()
        self.receive(line(0, self.final.payload))
        assert (
            self.writes[-1] == line(1, words(*self.image.image_words).lower()).encode()
        )
        assert not self.task.done()
        self.receive(line(17, "2.3.2", node=32, kind=0))
        self.receive(line(22, "2", ack=1, kind=3))
        assert not self.task.done()
        self.receive(line(17, "2.3.2", kind=0))
        assert await self.task == self.final
        assert self.progress[-1] == 100
        assert self.gateway.firmware_configs[31] == self.final
        assert self.writes.count(b"31;255;3;0;13;\n") == 1
        assert not self.gateway.sensors[31].reboot
        assert not self.gateway.tasks.ota.firmware

    async def test_discovery_before_presentation(self):
        """Expose validated capability announcements through the existing event API."""
        configs = self.gateway.firmware_configs
        self.receive(line(0, self.current.payload))
        assert configs[31] == self.current
        assert 31 not in self.gateway.sensors
        assert self.events[-1].node_id == 31
        assert self.events[-1].payload == self.current.payload
        with self.assertRaises(TypeError):
            configs[31] = self.final
        before = len(self.events)
        for message in (
            line(0, "xx"),
            line(0, words(42, 9, 8, 123)),
            line(0, self.current.payload, ack=1),
            line(0, self.current.payload, child=1),
            line(0, self.current.payload, node=0),
            line(0, self.current.payload, node=255),
        ):
            self.receive(message)
        assert len(self.events) == before
        assert configs[31] == self.current

    async def test_wrong_target_child_and_echo(self):
        """Invalid envelopes cannot arm an offer, serve a block or prove install."""
        await self.arm()
        for message in (
            line(0, self.current.payload, node=32),
            line(0, self.current.payload, child=1),
            line(0, self.current.payload, ack=1),
        ):
            self.receive(message)
        assert not self.progress
        self.offer()
        before = len(self.writes)
        for message in (
            line(2, words(42, 9, 0), node=32),
            line(2, words(42, 9, 0), child=1),
            line(2, words(42, 9, 0), ack=1),
        ):
            self.receive(message)
        assert len(self.writes) == before
        self.transfer()
        self.receive(line(0, self.final.payload))
        self.receive(line(11, "new sketch", kind=3))
        assert await self.task == self.final

    async def test_wrong_block_and_malformed_messages(self):
        """Reject corrupt block requests and requests for another cached image."""
        for payload in (
            words(43, 9, 0),
            words(42, 10, 0),
            words(42, 9, self.image.blocks),
            words(42, 9, 65535),
            "xx",
            words(42, 9),
            words(42, 9, 0, 1),
        ):
            with self.subTest(payload=payload):
                self.writes.clear()
                await self.arm()
                self.offer()
                before = len(self.writes)
                self.receive(line(2, payload))
                with self.assertRaises(FirmwareUpdateError):
                    await self.task
                assert len(self.writes) == before
                assert 100 not in self.progress

    async def test_bad_initial_config(self):
        """Reject malformed and wrong-type initial announcements without an offer."""
        for payload in (
            "xx",
            words(42, 9, 1, 2),
            words(43, 8, 8, 123, 1),
            self.final.payload,
        ):
            with self.subTest(payload=payload):
                self.writes.clear()
                await self.arm()
                self.receive(line(0, payload))
                with self.assertRaises(FirmwareUpdateError):
                    await self.task
                assert self.writes == [b"31;255;3;0;13;\n"]

    async def test_wrong_running_image(self):
        """A version rollback or changed type, count or CRC fails after full serving."""
        for field in range(4):
            with self.subTest(field=field):
                self.writes.clear()
                await self.arm()
                self.offer()
                self.transfer()
                values = list(self.final.image_words)
                values[field] ^= 1
                before = len(self.writes)
                self.receive(line(0, words(*values, 3)))
                self.receive(line(17, "2.3.2", kind=0))
                with self.assertRaises(FirmwareUpdateError):
                    await self.task
                assert len(self.writes) == before
                assert 100 not in self.progress

    async def test_active_target_defers_discovery_requests(self):
        """Avoid provoking a bootloader config restart while discovery is incomplete."""
        await self.arm()
        self.offer()
        before = len(self.writes)
        self.receive(line(11, "starting application", kind=3))
        self.receive(line(22, "1", kind=3))
        self.receive(line(1, "state", kind=1, child=19))
        assert len(self.writes) == before
        assert not self.gateway.is_sensor(31)
        assert len(self.writes) == before
        self.gateway.is_sensor(32)
        assert self.writes[-1] == b"32;255;3;0;19;\n"
        self.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await self.task
        self.gateway.is_sensor(31)
        assert self.writes[-1] == b"31;255;3;0;19;\n"

    async def test_initial_handshake_retransmission(self):
        """Identical pre-block handshakes reuse the offer with unchanged deadlines."""
        await self.arm()
        self.offer()
        session = self.gateway._firmware_session  # pylint: disable=protected-access
        deadline, activity = session.deadline, session.last_activity
        first_offer = self.writes[-1]
        self.offer()
        assert self.writes[-1] == first_offer
        assert (session.deadline, session.last_activity) == (deadline, activity)
        assert self.progress == [0]
        self.transfer()
        self.receive(line(0, self.final.payload))
        self.receive(line(17, "2.3.2", kind=0))
        assert await self.task == self.final

    async def test_handshake_change_and_post_block_retransmission(self):
        """Changed initial config or stale config after first block cannot restart."""
        for payload, started in (
            (words(42, 7, 8, 123, 0x0301), False),
            (self.current.payload, True),
        ):
            with self.subTest(started=started):
                self.writes.clear()
                await self.arm()
                self.offer()
                if started:
                    self.receive(line(2, words(42, 9, 0)))
                before = len(self.writes)
                self.receive(line(0, payload))
                with self.assertRaises(FirmwareUpdateError):
                    await self.task
                assert len(self.writes) == before

    async def test_config_before_all_blocks(self):
        """Matching config cannot bypass coverage of all blocks."""
        await self.arm()
        self.offer()
        self.receive(line(2, words(42, 9, 0)))
        self.receive(line(0, self.final.payload))
        with self.assertRaises(FirmwareUpdateError):
            await self.task
        assert 100 not in self.progress

    async def test_timeouts(self):
        """Initial config, block inactivity and missing app proof are bounded."""
        for phase in ("config", "transfer", "proof"):
            with self.subTest(phase=phase):
                self.writes.clear()
                await self.arm(timeout=0.02, confirmation_timeout=0.02)
                if phase != "config":
                    self.offer()
                if phase == "proof":
                    self.transfer()
                    self.receive(line(0, self.final.payload))
                with self.assertRaises(FirmwareUpdateTimeout):
                    await self.task
                assert 100 not in self.progress
                assert self.writes.count(b"31;255;3;0;13;\n") == 1
                before = len(self.writes)
                self.receive(line(2, words(42, 9, 0)))
                assert len(self.writes) == before

    async def test_duplicates_cannot_extend_whole_deadline(self):
        """Bound incomplete transfers despite repeated valid requests."""
        await self.arm(timeout=0.01)
        self.offer()
        while not self.task.done():
            self.receive(line(2, words(42, 9, 0)))
            await asyncio.sleep(0.001)
        with self.assertRaises(FirmwareUpdateTimeout):
            await self.task
        assert self.progress[-1] < 99

    async def test_cancel_busy_and_no_replay(self):
        """Clear cancellation without creating legacy resume or reboot jobs."""
        await self.arm()
        with self.assertRaises(FirmwareUpdateBusy):
            await self.gateway.install_firmware(32, self.image)
        with self.assertRaises(FirmwareUpdateBusy):
            await self.gateway.update_fw(31, 42, 9)
        self.offer()
        self.receive(line(2, words(42, 9, 0)))
        self.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await self.task
        before = len(self.writes)
        self.receive(line(2, words(42, 9, 0)))
        self.receive(line(0, self.current.payload))
        assert len(self.writes) == before + 1
        assert (
            self.writes[-1]
            == line(1, words(*self.current.image_words).lower()).encode()
        )
        self.writes.clear()
        await self.arm()

    async def test_reboot_window_disconnects(self):
        """Preserve the bounded session across both expected USB resets."""
        await self.arm()
        self.transport.protocol.connection_lost(None)
        # Unrelated outgoing traffic is dropped during expected re-enumeration.
        self.gateway.send("32;255;3;0;18;\n")
        await asyncio.sleep(0)
        # Clean connection loss also reconnects during the expected reboot.
        assert self.transport.protocol.transport is self.connection
        self.offer()
        self.transfer()
        self.transport.protocol.connection_lost(OSError("USB re-enumeration"))
        self.gateway.send("32;255;3;0;18;\n")
        await asyncio.sleep(0)
        self.receive(line(0, self.final.payload))
        self.receive(line(17, "2.3.2", kind=0))
        assert await self.task == self.final
        assert self.writes.count(b"31;255;3;0;13;\n") == 1

    async def test_midtransfer_disconnect_and_stop(self):
        """Transfer disconnect and explicit stop remain terminal in every phase."""
        for phase in ("config", "transfer", "confirm"):
            with self.subTest(phase=phase):
                self.writes.clear()
                await self.arm()
                if phase != "config":
                    self.offer()
                if phase == "confirm":
                    self.transfer()
                if phase == "transfer":
                    self.transport.protocol.connection_lost(None)
                else:
                    await self.gateway.stop()
                with self.assertRaises(FirmwareUpdateError):
                    await self.task
                self.transport = AsyncTransport(
                    self.gateway,
                    self.transport._connect,  # pylint: disable=protected-access
                )
                self.gateway.tasks.transport = self.transport
                await self.gateway.start()
                before = len(self.writes)
                self.receive(line(2, words(42, 9, 0)))
                assert len(self.writes) == before

    async def test_install_without_connected_transport(self):
        """Reject a reboot that cannot be written; reconnect must not replay it."""
        self.transport.protocol.transport = None
        self.task = asyncio.create_task(self.gateway.install_firmware(31, self.image))
        with self.assertRaises(FirmwareUpdateError):
            await self.task
        assert not self.writes
        await self.transport.connect()
        self.receive(line(0, self.current.payload))
        assert self.writes == [
            line(1, words(*self.current.image_words).lower()).encode()
        ]

    async def test_send_error_clears_session(self):
        """A failed initial write cannot turn into a later replayed install."""
        self.connection.write.side_effect = OSError("transport write failed")
        self.task = asyncio.create_task(self.gateway.install_firmware(31, self.image))
        with self.assertRaises(FirmwareUpdateError):
            await self.task
        assert not self.gateway.tasks.ota.requested

    async def test_invalid_arguments_and_legacy_conflict(self):
        """Reject invalid inputs before reboot and isolate queued legacy updates."""
        for node in (0, 255, -1, True, "31"):
            with self.assertRaises(ValueError):
                await self.gateway.install_firmware(node, self.image)
        for value in (0, -1, float("nan"), float("inf"), "1"):
            with self.assertRaises(ValueError):
                await self.gateway.install_firmware(31, self.image, timeout=value)
            with self.assertRaises(ValueError):
                await self.gateway.install_firmware(
                    31, self.image, confirmation_timeout=value
                )
        with self.assertRaises(ValueError):
            await self.gateway.install_firmware(31, b"bad")
        self.gateway.tasks.ota.requested[31] = (42, 8)
        with self.assertRaises(FirmwareUpdateBusy):
            await self.gateway.install_firmware(31, self.image)
        assert not self.writes

    async def test_late_proof_cannot_bypass_deadline(self):
        """Reject late application messages even before timeout handling runs."""
        await self.arm()
        self.offer()
        self.transfer()
        self.receive(line(0, self.final.payload))
        session = self.gateway._firmware_session  # pylint: disable=protected-access
        with mock.patch.object(
            session.loop, "time", return_value=session.confirmation_deadline + 1
        ):
            self.receive(line(17, "2.3.2", kind=0))
        with self.assertRaises(FirmwareUpdateTimeout):
            await self.task
        assert 100 not in self.progress

    async def test_legacy_import_race(self):
        """A legacy file import reserves its operation before executor suspension."""
        self.gateway.tasks.update_fw = mock.AsyncMock()
        entered, release = asyncio.Event(), asyncio.Event()

        async def importing(*_args, **_kwargs):
            """Hold legacy work at the file-import suspension point."""
            entered.set()
            await release.wait()

        self.gateway.tasks.update_fw.side_effect = importing
        legacy = asyncio.create_task(
            self.gateway.update_fw(31, 42, 9, fw_path="test.hex")
        )
        await entered.wait()
        try:
            with self.assertRaises(FirmwareUpdateBusy):
                await self.gateway.install_firmware(31, self.image)
        finally:
            release.set()
            await legacy
        assert not self.writes


class TestMQTTAndTCP(IsolatedAsyncioTestCase):
    """Exercise alternate async gateway message and disconnect paths."""

    async def test_mqtt_pipeline_nonretained(self):
        """Subscribe before presentation and send OTA replies without retention."""
        publish, subscribe = mock.Mock(), mock.Mock()
        gateway = AsyncMQTTGateway(publish, subscribe, protocol_version="2.3")
        await gateway.start()
        subscribe.assert_any_call("/+/255/4/+/+", gateway.tasks.transport.recv, 0)
        image = FirmwareImage.from_bytes(b"x", 42, 9)
        task = asyncio.create_task(gateway.install_firmware(31, image))
        await asyncio.sleep(0)
        publish.assert_called_with("/31/255/3/0/13", "", 0, False)
        gateway.tasks.transport.recv("/31/255/4/0/0", words(42, 8, 8, 1, 3), 0, False)
        for index in range(image.blocks):
            gateway.tasks.transport.recv("/31/255/4/0/2", words(42, 9, index), 0, False)
        gateway.tasks.transport.recv(
            "/31/255/4/0/0", words(*image.image_words, 3), 0, False
        )
        assert not task.done()
        gateway.tasks.transport.recv("/31/255/0/0/17", "2.3.2", 0, False)
        assert (await task).image_words == image.image_words
        assert all(call.args[-1] is False for call in publish.call_args_list)
        await gateway.stop()

    async def test_tcp_connection_lost(self):
        """TCP disconnect notifies the session and preserves the public callback."""
        gateway = AsyncTCPGateway("localhost", protocol_version="2.3")
        gateway.on_conn_lost = mock.Mock()
        connection = mock.Mock()
        gateway.tasks.transport.protocol.connection_made(connection)
        task = asyncio.create_task(
            gateway.install_firmware(31, FirmwareImage.from_bytes(b"x", 42, 9))
        )
        await asyncio.sleep(0)
        gateway.tasks.add_job(gateway.logic, line(0, words(42, 8, 8, 1, 3)))
        gateway.tasks.transport.protocol.connection_lost(None)
        with self.assertRaises(FirmwareUpdateError):
            await task
        gateway.on_conn_lost.assert_called_once_with(gateway, None)
        await gateway.stop()


def test_legacy_wrong_blocks():
    """Reject cached-image selection and invalid block data in legacy OTA."""
    gateway = BaseSyncGateway(None, protocol_version="2.3")
    gateway.add_sensor(31)
    gateway.tasks.ota.make_update(31, 42, 9, b"x")
    gateway.tasks.ota.firmware[43, 10] = prepare_fw(b"other image")
    gateway.logic(line(0, words(42, 8, 8, 1, 3)))
    for payload in (words(43, 10, 0), words(42, 9, 8), "xx", words(42, 9)):
        assert gateway.logic(line(2, payload)) is None
    assert gateway.logic(line(2, words(42, 9, 0))) is not None
    assert gateway.logic(line(0, "xx")) is None
