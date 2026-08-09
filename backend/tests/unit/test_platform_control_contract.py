"""Tests for the closed cross-platform control contract and audit migration."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.control.contract import (
    PlatformControlOperation,
    PlatformControlState,
    control_operation_is_available,
    new_platform_control_command,
)
from backend.app.core import database
from backend.app.drivers.contract import (
    Capability,
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
)


def _ready_observation(state: str) -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity("fixture-printer", "Fixture printer"),
        driver=DriverKind.MOONRAKER,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=frozenset({Capability.JOB_CONTROL}),
        job=JobProgress(name=None, state=state),
    )
    return DriverObservation(ConnectionPhase.READY, snapshot.capabilities, current=snapshot)


def test_platform_control_command_accepts_only_supported_drivers_and_operations():
    command = new_platform_control_command(
        DriverKind.ELEGOO_SDCP_V3,
        source_id=7,
        configuration_revision=2,
        operation=PlatformControlOperation.PAUSE_JOB,
    )
    assert command.driver is DriverKind.ELEGOO_SDCP_V3
    assert command.operation is PlatformControlOperation.PAUSE_JOB
    assert len(command.idempotency_key) == 32

    with pytest.raises(ValueError, match="unsupported platform control driver"):
        new_platform_control_command(
            DriverKind.BAMBU,
            source_id=7,
            configuration_revision=2,
            operation=PlatformControlOperation.PAUSE_JOB,
        )
    with pytest.raises(ValueError, match="unsupported platform control operation"):
        new_platform_control_command(
            DriverKind.MOONRAKER,
            source_id=7,
            configuration_revision=2,
            operation="printer.gcode.script",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("operation", "state", "available"),
    [
        (PlatformControlOperation.PAUSE_JOB, "printing", True),
        (PlatformControlOperation.PAUSE_JOB, "paused", False),
        (PlatformControlOperation.RESUME_JOB, "paused", True),
        (PlatformControlOperation.RESUME_JOB, "printing", False),
        (PlatformControlOperation.CANCEL_JOB, "printing", True),
        (PlatformControlOperation.CANCEL_JOB, "paused", True),
        (PlatformControlOperation.CANCEL_JOB, "idle", False),
    ],
)
def test_control_operation_availability_is_closed_and_state_gated(
    operation: PlatformControlOperation, state: str, available: bool
) -> None:
    assert control_operation_is_available(operation, _ready_observation(state)) is available


@pytest.mark.parametrize("operation", ["M112", 129, "/printer/gcode/script", {"Cmd": 129}, None])
def test_control_operation_availability_rejects_arbitrary_values(operation: object) -> None:
    assert control_operation_is_available(operation, _ready_observation("printing")) is False


@pytest.mark.asyncio
async def test_platform_control_migration_is_idempotent_and_rejects_unlisted_operations(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            await database._migrate_platform_control_commands(conn)
            await database._migrate_platform_control_commands(conn)
            await conn.execute(
                text(
                    "INSERT INTO platform_control_commands "
                    "(driver, source_id, configuration_revision, operation, status, idempotency_key) "
                    "VALUES ('moonraker', 4, 1, 'pause_job', 'queued', '0123456789abcdef0123456789abcdef')"
                )
            )
            row = (
                await conn.execute(text("SELECT driver, source_id, operation, status FROM platform_control_commands"))
            ).one()
            assert row == ("moonraker", 4, "pause_job", PlatformControlState.QUEUED.value)
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        "INSERT INTO platform_control_commands "
                        "(driver, source_id, configuration_revision, operation, idempotency_key) "
                        "VALUES ('moonraker', 4, 1, 'raw_gcode', 'fedcba9876543210fedcba9876543210')"
                    )
                )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_platform_control_restart_recovery_never_replays_interrupted_commands(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            await database._migrate_platform_control_commands(conn)
            await conn.execute(
                text(
                    "INSERT INTO platform_control_commands "
                    "(driver, source_id, configuration_revision, operation, status, idempotency_key) VALUES "
                    "('elegoo.sdcp-v3', 7, 1, 'pause_job', 'queued', '0123456789abcdef0123456789abcdef'), "
                    "('moonraker', 8, 1, 'cancel_job', 'dispatching', 'abcdef0123456789abcdef0123456789'), "
                    "('moonraker', 9, 1, 'resume_job', 'acknowledged', 'fedcba9876543210fedcba9876543210')"
                )
            )

            await database._reconcile_interrupted_platform_control_commands(conn)
            rows = (
                await conn.execute(
                    text("SELECT status, error_code, completed_at FROM platform_control_commands ORDER BY source_id")
                )
            ).all()

            assert rows[0][0:2] == ("failed", "restart_interrupted")
            assert rows[0][2] is not None
            assert rows[1][0:2] == ("failed", "restart_interrupted")
            assert rows[1][2] is not None
            assert rows[2] == ("acknowledged", None, None)
    finally:
        await engine.dispose()
