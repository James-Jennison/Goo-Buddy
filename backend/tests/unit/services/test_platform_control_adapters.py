"""Protocol-adapter dispatch tests using in-memory transports only."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone

import pytest

from backend.app.control.contract import PlatformControlCommand, PlatformControlOperation
from backend.app.drivers.contract import (
    Capability,
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
)
from backend.app.drivers.elegoo_sdcp_v3 import SyntheticElegooSdcpV3Driver
from backend.app.drivers.moonraker import MoonrakerDriver
from backend.app.services.elegoo_sdcp_manager import ElegooSDCPManager, _LiveSource
from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker
from backend.tests._fixtures.elegoo_sdcp_v3_control import (
    COMMAND_BY_OPERATION,
    MAINBOARD_ID,
    StrictSdcpControlPeer,
)
from backend.tests._fixtures.moonraker_control import PATH_BY_OPERATION, StrictMoonrakerControlPeer


def _command(driver: DriverKind, operation: PlatformControlOperation, revision: int = 3) -> PlatformControlCommand:
    return PlatformControlCommand(driver, 7, revision, operation, "0123456789abcdef0123456789abcdef")


def _ready_observation(operation: PlatformControlOperation) -> DriverObservation:
    state = "paused" if operation is PlatformControlOperation.RESUME_JOB else "printing"
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity("fixture-printer", "Fixture printer"),
        driver=DriverKind.ELEGOO_SDCP_V3,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=frozenset({Capability.JOB_CONTROL}),
        job=JobProgress(name=None, state=state),
    )
    return DriverObservation(ConnectionPhase.READY, snapshot.capabilities, current=snapshot)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "protocol_command"),
    [
        (PlatformControlOperation.PAUSE_JOB, 129),
        (PlatformControlOperation.RESUME_JOB, 131),
        (PlatformControlOperation.CANCEL_JOB, 130),
    ],
)
async def test_elegoo_dispatch_uses_only_the_closed_sdcp_operation_map(
    monkeypatch: pytest.MonkeyPatch, operation: PlatformControlOperation, protocol_command: int
) -> None:
    manager = ElegooSDCPManager()
    socket = StrictSdcpControlPeer()
    live = _LiveSource(7, "192.168.1.40", SyntheticElegooSdcpV3Driver("elegoo-7"), configuration_revision=3)
    live.mainboard_id = MAINBOARD_ID
    live.websocket = socket  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _ready_observation(operation))

    assert await manager.dispatch_command(_command(DriverKind.ELEGOO_SDCP_V3, operation)) is True
    assert socket.operations == [operation]
    assert protocol_command == COMMAND_BY_OPERATION[operation]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "command_data",
    [
        {
            "Cmd": 999,
            "Data": {},
            "RequestID": "00000000-0000-4000-8000-000000000001",
            "MainboardID": MAINBOARD_ID,
            "TimeStamp": 1,
            "From": 0,
        },
        {
            "Cmd": 129,
            "Data": {"gcode": "M112"},
            "RequestID": "00000000-0000-4000-8000-000000000001",
            "MainboardID": MAINBOARD_ID,
            "TimeStamp": 1,
            "From": 0,
        },
    ],
)
async def test_elegoo_control_simulator_rejects_arbitrary_commands_and_payloads(
    command_data: dict[str, object],
) -> None:
    peer = StrictSdcpControlPeer()
    payload = json.dumps(
        {
            "Id": "00000000-0000-4000-8000-000000000000",
            "Data": command_data,
            "Topic": f"sdcp/request/{MAINBOARD_ID}",
        }
    )

    with pytest.raises(AssertionError):
        await peer.send_str(payload)
    assert peer.operations == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation",
    [
        PlatformControlOperation.PAUSE_JOB,
        PlatformControlOperation.RESUME_JOB,
        PlatformControlOperation.CANCEL_JOB,
    ],
)
async def test_moonraker_dispatch_uses_only_the_closed_bodyless_operation_map(
    monkeypatch: pytest.MonkeyPatch, operation: PlatformControlOperation
) -> None:
    manager = MoonrakerManager()
    base_url = "http://192.168.1.44:7125"
    client = StrictMoonrakerControlPeer(base_url)
    live = _LiveMoonraker(
        7,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-7", "Synthetic"),
        configuration_revision=3,
    )
    live.client = client  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _ready_observation(operation))

    assert await manager.dispatch_command(_command(DriverKind.MOONRAKER, operation)) is True
    assert client.operations == [operation]
    assert PATH_BY_OPERATION[operation] in {"/printer/print/pause", "/printer/print/resume", "/printer/print/cancel"}


@pytest.mark.parametrize(
    ("url", "kwargs"),
    [
        ("http://192.168.1.44:7125/printer/gcode/script", {"allow_redirects": False}),
        ("http://192.168.1.44:7125/printer/print/pause?gcode=M112", {"allow_redirects": False}),
        ("http://192.168.1.44:7125/printer/print/pause", {"allow_redirects": True}),
        ("http://192.168.1.44:7125/printer/print/pause", {"allow_redirects": False, "json": {"script": "M112"}}),
    ],
)
def test_moonraker_control_simulator_rejects_arbitrary_paths_payloads_and_gcode(
    url: str, kwargs: dict[str, object]
) -> None:
    peer = StrictMoonrakerControlPeer("http://192.168.1.44:7125")

    with pytest.raises(AssertionError):
        peer.post(url, **kwargs)
    assert peer.operations == []


@pytest.mark.asyncio
@pytest.mark.parametrize("manager", [ElegooSDCPManager(), MoonrakerManager()])
async def test_dispatch_rejects_non_contract_values_and_has_no_raw_transport_parameters(manager: object) -> None:
    dispatch = manager.dispatch_command  # type: ignore[attr-defined]
    assert tuple(inspect.signature(dispatch).parameters) == ("command",)
    for value in ("M112", 129, "/printer/gcode/script", {"payload": {"gcode": "M112"}}, None):
        with pytest.raises(ValueError, match="unsupported"):
            await dispatch(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("manager_kind", ["elegoo", "moonraker"])
async def test_dispatch_fails_closed_for_an_unavailable_capability_or_stale_configuration(
    monkeypatch: pytest.MonkeyPatch,
    manager_kind: str,
) -> None:
    if manager_kind == "elegoo":
        manager = ElegooSDCPManager()
        live = _LiveSource(7, "192.168.1.40", SyntheticElegooSdcpV3Driver("elegoo-7"), configuration_revision=3)
        live.mainboard_id = MAINBOARD_ID
        live.websocket = StrictSdcpControlPeer()  # type: ignore[assignment]
        manager._sources[7] = live
        driver = DriverKind.ELEGOO_SDCP_V3
    else:
        manager = MoonrakerManager()
        live = _LiveMoonraker(
            7,
            "Synthetic",
            "192.168.1.44",
            7125,
            "http",
            None,
            MoonrakerDriver("moonraker-7", "Synthetic"),
            configuration_revision=3,
        )
        live.client = StrictMoonrakerControlPeer("http://192.168.1.44:7125")  # type: ignore[assignment]
        manager._sources[7] = live
        driver = DriverKind.MOONRAKER
    monkeypatch.setattr(
        manager, "observation", lambda _source_id: DriverObservation(ConnectionPhase.READY, frozenset())
    )

    assert await manager.dispatch_command(_command(driver, PlatformControlOperation.PAUSE_JOB)) is False
    monkeypatch.setattr(
        manager,
        "observation",
        lambda _source_id: _ready_observation(PlatformControlOperation.PAUSE_JOB),
    )
    assert await manager.dispatch_command(_command(driver, PlatformControlOperation.PAUSE_JOB, 2)) is False
    monkeypatch.setattr(
        manager,
        "observation",
        lambda _source_id: DriverObservation(ConnectionPhase.STALE, frozenset({Capability.JOB_CONTROL})),
    )
    assert await manager.dispatch_command(_command(driver, PlatformControlOperation.PAUSE_JOB)) is False
