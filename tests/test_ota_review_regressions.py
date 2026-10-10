"""Regressions for MQTT provenance, legacy ownership and completion."""

import asyncio
from unittest import mock

import crc
import pytest

from mysensors import BaseAsyncGateway, BaseSyncGateway
from mysensors.cli.gateway_mqtt import BaseMQTTClient
from mysensors.gateway_mqtt import AsyncMQTTGateway
from mysensors.ota import FirmwareImage, FirmwareUpdateBusy, compute_crc
from tests.test_native_ota import line, words


@pytest.mark.parametrize("provenance", [None, True])
@pytest.mark.parametrize(
    "application", [(0, 17, "2.3.2"), (3, 11, "app"), (3, 12, "v9"), (3, 22, "10")]
)
def test_mqtt_requires_explicit_freshness(provenance, application):
    """Only explicit non-retained messages may advance a native MQTT session."""

    async def exercise():
        """Use the actual callback registered with the MQTT subscription adapter."""
        publish, subscribe, event = mock.Mock(), mock.Mock(), mock.Mock()
        gateway = AsyncMQTTGateway(
            publish, subscribe, event_callback=event, protocol_version="2.3"
        )
        await gateway.start()
        receive = subscribe.call_args_list[0].args[1]
        image = FirmwareImage.from_bytes(b"test", 42, 9)
        progress = []
        task = asyncio.create_task(
            gateway.install_firmware(
                31, image, progress_callback=progress.append, timeout=0.5
            )
        )
        await asyncio.sleep(0)
        try:
            config = words(42, 8, 8, 123, 3)
            # The preexisting three-argument adapter has unknown provenance.
            receive("/31/255/4/0/0", config, 0)
            receive("/31/255/4/0/0", config, 0, provenance)
            receive("/31/255/4/0/2", words(42, 9, 0), 0, provenance)
            assert publish.call_count == 1
            assert not gateway.firmware_configs
            assert not progress
            receive("/31/255/4/0/0", config, 0, False)
            assert publish.call_count == 2
            receive("/31/255/4/0/2", words(42, 9, 0), 0, provenance)
            assert publish.call_count == 2
            for index in range(image.blocks):
                receive("/31/255/4/0/2", words(42, 9, index), 0, False)
            before = publish.call_count
            final = words(*image.image_words, 3)
            receive("/31/255/4/0/0", final, 0, provenance)
            assert publish.call_count == before
            assert gateway.firmware_configs[31].firmware_version == 8
            # Fresh app data still cannot prove a retained/unknown final config.
            receive("/31/255/0/0/17", "2.3.2", 0, False)
            await asyncio.sleep(0)
            assert not task.done()
            assert 100 not in progress
            receive("/31/255/4/0/0", final, 0, False)
            # Stale metadata cannot overwrite the live final config or revoke it.
            receive("/31/255/4/0/0", config, 0, provenance)
            assert gateway.firmware_configs[31].firmware_version == 9
            kind, subtype, payload = application
            before = event.call_count
            receive(f"/31/255/{kind}/0/{subtype}", payload, 0, provenance)
            await asyncio.sleep(0)
            assert event.call_count == before + 1
            assert event.call_args.args[0].retained is provenance
            assert not task.done()
            assert 100 not in progress
            receive(f"/31/255/{kind}/0/{subtype}", payload, 0, False)
            assert (await task).image_words == image.image_words
            assert progress[-1] == 100
            assert event.call_args.args[0].retained is False
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await gateway.stop()

    asyncio.run(exercise())


def test_cli_preserves_broker_retain():
    """The bundled MQTT adapter forwards the actual broker provenance flag."""
    with mock.patch("paho.mqtt.client.Client") as client_type:
        client = BaseMQTTClient("localhost")
        receive = mock.Mock()
        client.subscribe("/+/255/4/+/+", receive, 0)
        on_message = client_type.return_value.message_callback_add.call_args.args[1]
        for retained in (True, False):
            message = mock.Mock(
                topic="/31/255/4/0/0", payload=b"payload", qos=0, retain=retained
            )
            on_message(None, None, message)
            receive.assert_called_with(message.topic, "payload", 0, retained)


@pytest.mark.parametrize("phase", ["requested", "unstarted", "started"])
def test_other_node_legacy_reserves_gateway(phase):
    """A native operation cannot interrupt legacy traffic on another node."""

    async def exercise():
        """Exercise actual legacy transitions instead of prepopulating state."""
        gateway = BaseAsyncGateway(mock.Mock(), protocol_version="2.3")
        gateway.add_sensor(32)
        image = FirmwareImage.from_bytes(b"test", 42, 9)
        gateway.tasks.ota.make_update(32, 42, 9, image.data)
        # Clear the legacy reboot flag through ordinary presentation so only
        # the correct activity store can enforce the gateway reservation.
        gateway.logic(line(17, "2.3.2", node=32, kind=0))
        if phase != "requested":
            assert gateway.logic(line(0, words(42, 8, 8, 123, 3), node=32))
        if phase == "started":
            assert gateway.logic(line(2, words(42, 9, 0), node=32))
        with pytest.raises(FirmwareUpdateBusy):
            await gateway.install_firmware(31, image)
        gateway.tasks.transport.send.assert_not_called()
        assert 32 in getattr(gateway.tasks.ota, phase)
        if phase != "requested":
            assert gateway.logic(line(2, words(42, 9, 1), node=32))

    asyncio.run(exercise())


@pytest.mark.parametrize("gateway_type", [BaseSyncGateway, BaseAsyncGateway])
@pytest.mark.parametrize("proof", [(0, 17, "2.3.2"), (3, 11, "app"), (3, 22, "1")])
def test_completed_legacy_releases_reservation(gateway_type, proof):
    """Completion releases ownership but keeps cached firmware reusable."""

    async def exercise():
        """Prove coverage, final config and subsequent live application evidence."""
        gateway = gateway_type(mock.Mock(), protocol_version="2.3")
        gateway.add_sensor(32)
        image = FirmwareImage.from_bytes(b"test", 42, 9)
        ota = gateway.tasks.ota
        ota.make_update(32, 42, 9, image.data)
        final = words(*image.image_words, 3)
        gateway.logic(line(0, words(42, 8, 8, 123, 3), node=32))
        for index in reversed(range(image.blocks)):
            assert gateway.logic(line(2, words(42, 9, index), node=32))
        # Fresh evidence before final config cannot end the operation.
        kind, subtype, payload = proof
        gateway.logic(line(subtype, payload, node=32, kind=kind))
        assert ota.active
        for metadata in (None, True):
            assert gateway.logic(line(0, final, node=32), retained=metadata) is None
            gateway.logic(line(subtype, payload, node=32, kind=kind))
            assert ota.active
        assert gateway.logic(line(0, final, node=32)) == line(
            1, final[:16].lower(), node=32
        )
        assert ota.active
        for metadata in (None, True):
            gateway.logic(line(subtype, payload, node=32, kind=kind), retained=metadata)
            assert ota.active
        gateway.logic(line(subtype, payload, node=31, kind=kind))
        assert ota.active
        gateway.logic(line(subtype, payload, node=32, kind=kind))
        assert not ota.active
        assert not gateway.sensors[32].reboot
        assert (42, 9) in ota.firmware
        assert not ota.requested and not ota.unstarted and not ota.started
        if gateway_type is BaseAsyncGateway:
            for target in (31, 32):
                task = asyncio.create_task(gateway.install_firmware(target, image))
                await asyncio.sleep(0)
                try:
                    assert not task.done()
                    gateway.tasks.transport.send.assert_called_with(
                        f"{target};255;3;0;13;\n"
                    )
                finally:
                    task.cancel()
                    with pytest.raises(asyncio.CancelledError):
                        await task
        # An explicit legacy operation may still reuse the cached image.
        ota.make_update(32, 42, 9)
        assert ota.active
        assert gateway.logic(line(0, words(42, 8, 8, 123, 3), node=32))

    asyncio.run(exercise())


@pytest.mark.parametrize("incomplete", [True, False])
def test_legacy_requires_complete_matching_config(incomplete):
    """Incomplete coverage or a wrong final CRC cannot release a legacy update."""
    gateway = BaseSyncGateway(mock.Mock(), protocol_version="2.3")
    gateway.add_sensor(32)
    image = FirmwareImage.from_bytes(b"test", 42, 9)
    ota = gateway.tasks.ota
    ota.make_update(32, 42, 9, image.data)
    gateway.logic(line(0, words(42, 8, 8, 123, 3), node=32))
    for index in range(image.blocks - int(incomplete)):
        gateway.logic(line(2, words(42, 9, index), node=32))
    final = words(42, 9, image.blocks, image.crc ^ int(not incomplete), 3)
    assert gateway.logic(line(0, final, node=32)) is None
    gateway.logic(line(22, "1", node=32, kind=3))
    assert ota.active


def test_optimized_crc_matches_reference():
    """The table implementation retains known MySensors and MODBUS checksums."""
    reference = crc.Calculator(crc.Crc16.MODBUS)
    for data in (b"123456789", bytes(range(256)), b"\xff" * 128):
        assert compute_crc(data) == reference.checksum(data)
    assert compute_crc(b"123456789") == 0x4B37


def test_serial_events_are_explicitly_fresh():
    """Expose serial provenance to the existing event callback after validation."""
    event = mock.Mock()
    gateway = BaseAsyncGateway(
        mock.Mock(), protocol_version="2.3", event_callback=event
    )
    gateway.logic(line(0, words(42, 8, 8, 123, 3)))
    assert event.call_args.args[0].retained is False
    assert gateway.firmware_configs[31].firmware_version == 8
    before = event.call_count
    gateway.logic(line(0, "malformed"))
    assert event.call_count == before
