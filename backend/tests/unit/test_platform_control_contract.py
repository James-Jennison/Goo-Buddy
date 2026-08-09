"""Tests for the closed cross-platform control contract and audit migration."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.control.contract import (
    PlatformControlOperation,
    PlatformControlState,
    new_platform_control_command,
)
from backend.app.core import database
from backend.app.drivers.contract import DriverKind


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
