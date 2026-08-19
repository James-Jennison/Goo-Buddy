"""Protocol-adapter dispatch tests using in-memory transports only."""

from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from backend.app.control.contract import PlatformControlCommand, PlatformControlOperation, PlatformControlUnconfirmed
from backend.app.control.evidence import ControlAcknowledgement
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
from backend.app.services import (
    elegoo_sdcp_manager as elegoo_manager_module,
    moonraker_manager as moonraker_manager_module,
)
from backend.app.services.elegoo_sdcp_manager import ElegooControlUnconfirmed, ElegooSDCPManager, _LiveSource
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
        identity=PrinterIdentity(
            "fixture-printer", "Fixture printer", model="fixture-model", firmware="fixture-firmware"
        ),
        driver=DriverKind.ELEGOO_SDCP_V3,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=frozenset({Capability.JOB_CONTROL}),
        job=JobProgress(name=None, state=state),
    )
    return DriverObservation(ConnectionPhase.READY, snapshot.capabilities, current=snapshot)


def _ready_moonraker_observation(state: str) -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            "moonraker-fixture", "Moonraker fixture", model="fixture-model", firmware="fixture-firmware"
        ),
        driver=DriverKind.MOONRAKER,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=frozenset({Capability.JOB_CONTROL}),
        job=JobProgress(name=None, state=state),
    )
    return DriverObservation(ConnectionPhase.READY, snapshot.capabilities, current=snapshot)


def _acknowledgement(driver: DriverKind, revision: int = 3) -> ControlAcknowledgement:
    return ControlAcknowledgement(
        configuration_revision=revision,
        model="fixture-model",
        firmware="fixture-firmware",
        operations=frozenset(PlatformControlOperation),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("manager_kind", ["elegoo", "moonraker"])
async def test_non_bambu_manager_enable_never_restores_control_from_a_boolean(
    monkeypatch: pytest.MonkeyPatch, manager_kind: str
) -> None:
    """A startup caller must supply fresh acknowledgement, not a persisted flag."""

    if manager_kind == "elegoo":
        manager = ElegooSDCPManager()
        monkeypatch.setattr(manager, "_run", AsyncMock())
        await manager.enable(7, "192.168.1.40", configuration_revision=3, control_enabled=True)
    else:
        manager = MoonrakerManager()
        monkeypatch.setattr(manager, "_run", AsyncMock())
        await manager.enable(
            7,
            "Synthetic",
            "192.168.1.44",
            7125,
            "http",
            None,
            configuration_revision=3,
            control_enabled=True,
        )

    assert manager._sources[7].control_enabled is False
    assert manager._sources[7].control_acknowledgement is None
    await manager.disable(7)


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

    class RecordingSocket:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send_str(self, payload: str) -> None:
            self.sent.append(payload)

    socket = RecordingSocket()
    live = _LiveSource(
        7,
        "192.168.1.40",
        SyntheticElegooSdcpV3Driver("elegoo-7"),
        configuration_revision=3,
        control_enabled=True,
        control_acknowledgement=_acknowledgement(DriverKind.ELEGOO_SDCP_V3),
    )
    live.mainboard_id = MAINBOARD_ID
    live.websocket = socket  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _ready_observation(operation))
    confirmation = AsyncMock(return_value=True)
    monkeypatch.setattr(manager, "_await_control_confirmation", confirmation)

    assert await manager.dispatch_command(_command(DriverKind.ELEGOO_SDCP_V3, operation)) is True
    control_request, status_request = map(json.loads, socket.sent)
    assert control_request["Data"]["Cmd"] == protocol_command
    assert status_request["Data"]["Cmd"] == 0
    confirmation.assert_awaited_once_with(live, operation)
    assert protocol_command == COMMAND_BY_OPERATION[operation]


@pytest.mark.asyncio
async def test_elegoo_dispatch_never_reports_success_without_a_fresh_expected_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingSocket:
        async def send_str(self, _payload: str) -> None:
            return None

    manager = ElegooSDCPManager()
    live = _LiveSource(
        7,
        "192.168.1.40",
        SyntheticElegooSdcpV3Driver("elegoo-7"),
        configuration_revision=3,
        control_enabled=True,
        control_acknowledgement=_acknowledgement(DriverKind.ELEGOO_SDCP_V3),
    )
    live.mainboard_id = MAINBOARD_ID
    live.websocket = RecordingSocket()  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(
        manager, "observation", lambda _source_id: _ready_observation(PlatformControlOperation.PAUSE_JOB)
    )
    monkeypatch.setattr(elegoo_manager_module, "CONTROL_CONFIRMATION_TIMEOUT_SECONDS", 0.001)

    with pytest.raises(ElegooControlUnconfirmed):
        await manager.dispatch_command(_command(DriverKind.ELEGOO_SDCP_V3, PlatformControlOperation.PAUSE_JOB))


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
        control_enabled=True,
        control_acknowledgement=_acknowledgement(DriverKind.MOONRAKER),
    )
    live.client = client  # type: ignore[assignment]
    manager._sources[7] = live
    state = "paused" if operation is PlatformControlOperation.RESUME_JOB else "printing"
    monkeypatch.setattr(manager, "observation", lambda _source_id: _ready_moonraker_observation(state))
    confirmation = AsyncMock(return_value=True)
    monkeypatch.setattr(manager, "_await_control_confirmation", confirmation)

    assert await manager.dispatch_command(_command(DriverKind.MOONRAKER, operation)) is True
    assert client.operations == [operation]
    confirmation.assert_awaited_once_with(live, operation)
    assert PATH_BY_OPERATION[operation] in {"/printer/print/pause", "/printer/print/resume", "/printer/print/cancel"}


@pytest.mark.asyncio
async def test_moonraker_dispatch_never_reports_success_without_a_fresh_expected_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    client = StrictMoonrakerControlPeer("http://192.168.1.44:7125")
    live = _LiveMoonraker(
        7,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-7", "Synthetic"),
        configuration_revision=3,
        control_enabled=True,
        control_acknowledgement=_acknowledgement(DriverKind.MOONRAKER),
    )
    live.client = client  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _ready_moonraker_observation("printing"))
    monkeypatch.setattr(manager, "_await_control_confirmation", AsyncMock(return_value=False))

    with pytest.raises(PlatformControlUnconfirmed):
        await manager.dispatch_command(_command(DriverKind.MOONRAKER, PlatformControlOperation.PAUSE_JOB))
    assert client.operations == [PlatformControlOperation.PAUSE_JOB]


@pytest.mark.asyncio
async def test_moonraker_confirmation_accepts_only_a_post_request_expected_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    live = _LiveMoonraker(
        7,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-7", "Synthetic"),
    )
    # A connection is required for the wait loop, but this object is never
    # used as an HTTP transport by the confirmation helper.
    live.client = object()  # type: ignore[assignment]
    manager._sources[7] = live
    observations = iter(
        [
            _ready_moonraker_observation("printing"),
            _ready_moonraker_observation("paused"),
        ]
    )
    monkeypatch.setattr(manager, "observation", lambda _source_id: next(observations))
    live.status_received.set()

    assert await manager._await_control_confirmation(live, PlatformControlOperation.PAUSE_JOB) is True


@pytest.mark.asyncio
async def test_moonraker_confirmation_fails_closed_on_timeout_or_disconnect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    live = _LiveMoonraker(
        7,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-7", "Synthetic"),
    )
    live.client = object()  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _ready_moonraker_observation("printing"))
    monkeypatch.setattr(moonraker_manager_module, "CONTROL_CONFIRMATION_TIMEOUT_SECONDS", 0.001)

    assert await manager._await_control_confirmation(live, PlatformControlOperation.PAUSE_JOB) is False
    live.stop.set()
    assert await manager._await_control_confirmation(live, PlatformControlOperation.PAUSE_JOB) is False


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
        driver = DriverKind.ELEGOO_SDCP_V3
        live = _LiveSource(
            7,
            "192.168.1.40",
            SyntheticElegooSdcpV3Driver("elegoo-7"),
            configuration_revision=3,
            control_enabled=True,
            control_acknowledgement=_acknowledgement(driver),
        )
        live.mainboard_id = MAINBOARD_ID
        live.websocket = StrictSdcpControlPeer()  # type: ignore[assignment]
        manager._sources[7] = live
    else:
        manager = MoonrakerManager()
        driver = DriverKind.MOONRAKER
        live = _LiveMoonraker(
            7,
            "Synthetic",
            "192.168.1.44",
            7125,
            "http",
            None,
            MoonrakerDriver("moonraker-7", "Synthetic"),
            configuration_revision=3,
            control_enabled=True,
            control_acknowledgement=_acknowledgement(driver),
        )
        live.client = StrictMoonrakerControlPeer("http://192.168.1.44:7125")  # type: ignore[assignment]
        manager._sources[7] = live
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


@pytest.mark.asyncio
@pytest.mark.parametrize("manager_kind", ["elegoo", "moonraker"])
async def test_dormant_source_control_gate_blocks_dispatch_before_a_transport_write(
    monkeypatch: pytest.MonkeyPatch, manager_kind: str
) -> None:
    if manager_kind == "elegoo":
        manager = ElegooSDCPManager()

        class RecordingSocket:
            def __init__(self) -> None:
                self.sent: list[str] = []

            async def send_str(self, payload: str) -> None:
                self.sent.append(payload)

        socket = RecordingSocket()
        live = _LiveSource(7, "192.168.1.40", SyntheticElegooSdcpV3Driver("elegoo-7"), configuration_revision=3)
        live.mainboard_id = MAINBOARD_ID
        live.websocket = socket  # type: ignore[assignment]
        manager._sources[7] = live
        monkeypatch.setattr(
            manager, "observation", lambda _source_id: _ready_observation(PlatformControlOperation.PAUSE_JOB)
        )
        command = _command(DriverKind.ELEGOO_SDCP_V3, PlatformControlOperation.PAUSE_JOB)
    else:
        manager = MoonrakerManager()
        client = StrictMoonrakerControlPeer("http://192.168.1.44:7125")
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
        monkeypatch.setattr(
            manager, "observation", lambda _source_id: _ready_observation(PlatformControlOperation.PAUSE_JOB)
        )
        command = _command(DriverKind.MOONRAKER, PlatformControlOperation.PAUSE_JOB)

    assert await manager.dispatch_command(command) is False
    if manager_kind == "elegoo":
        assert socket.sent == []
    else:
        assert client.operations == []


def test_dormant_moonraker_source_does_not_project_job_control_capability() -> None:
    manager = MoonrakerManager()
    live = _LiveMoonraker(
        7,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-7", "Synthetic"),
    )

    gated = manager._with_control_gate(live, _ready_observation(PlatformControlOperation.PAUSE_JOB))

    assert Capability.JOB_CONTROL not in gated.capabilities
    assert gated.current is not None
    assert Capability.JOB_CONTROL not in gated.current.capabilities


def test_enabled_elegoo_source_projects_job_control_only_for_a_fresh_consistent_active_job() -> None:
    manager = ElegooSDCPManager()
    live = _LiveSource(
        7,
        "192.168.1.40",
        SyntheticElegooSdcpV3Driver("elegoo-7"),
        control_enabled=True,
        control_acknowledgement=_acknowledgement(DriverKind.ELEGOO_SDCP_V3, 1),
    )

    active = manager._with_control_gate(live, _ready_observation(PlatformControlOperation.PAUSE_JOB))
    assert Capability.JOB_CONTROL in active.capabilities
    assert active.current is not None
    assert Capability.JOB_CONTROL in active.current.capabilities

    paused_without_print_info = NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            "fixture-printer", "Fixture printer", model="fixture-model", firmware="fixture-firmware"
        ),
        driver=DriverKind.ELEGOO_SDCP_V3,
        observed_at=datetime.now(timezone.utc),
        state="paused",
        capabilities=frozenset(),
        job=None,
    )
    paused = manager._with_control_gate(
        live,
        DriverObservation(
            ConnectionPhase.READY,
            paused_without_print_info.capabilities,
            current=paused_without_print_info,
        ),
    )
    assert Capability.JOB_CONTROL in paused.capabilities

    idle_snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            "fixture-printer", "Fixture printer", model="fixture-model", firmware="fixture-firmware"
        ),
        driver=DriverKind.ELEGOO_SDCP_V3,
        observed_at=datetime.now(timezone.utc),
        state="idle",
        capabilities=frozenset(),
        job=None,
    )
    idle = manager._with_control_gate(
        live, DriverObservation(ConnectionPhase.READY, idle_snapshot.capabilities, current=idle_snapshot)
    )
    assert Capability.JOB_CONTROL not in idle.capabilities
