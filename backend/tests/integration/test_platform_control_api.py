"""Closed, permission-gated API paths for non-Bambu job control."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.control.contract import PlatformControlOperation
from backend.app.drivers.contract import DriverKind
from backend.app.models.platform_control_command import PlatformControlCommand as PlatformControlCommandRecord


async def _create_source(async_client: AsyncClient, platform: str) -> int:
    if platform == "elegoo":
        response = await async_client.post(
            "/api/v1/printers/elegoo",
            json={
                "name": "Synthetic Centauri",
                "private_ipv4": "192.168.50.30",
                "read_only_acknowledged": True,
                "is_enabled": False,
            },
        )
        return -response.json()["id"]
    response = await async_client.post(
        "/api/v1/printers/moonraker",
        json={
            "name": "Synthetic Klipper",
            "private_ipv4": "192.168.50.31",
            "read_only_acknowledged": True,
            "is_enabled": False,
        },
    )
    return -1_000_000 - response.json()["id"]


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    ("platform", "operation", "route_operation", "driver", "patch_target"),
    [
        ("elegoo", PlatformControlOperation.PAUSE_JOB, "pause", DriverKind.ELEGOO_SDCP_V3, "elegoo_sdcp_manager"),
        ("elegoo", PlatformControlOperation.RESUME_JOB, "resume", DriverKind.ELEGOO_SDCP_V3, "elegoo_sdcp_manager"),
        ("elegoo", PlatformControlOperation.CANCEL_JOB, "cancel", DriverKind.ELEGOO_SDCP_V3, "elegoo_sdcp_manager"),
        ("moonraker", PlatformControlOperation.PAUSE_JOB, "pause", DriverKind.MOONRAKER, "moonraker_manager"),
        ("moonraker", PlatformControlOperation.RESUME_JOB, "resume", DriverKind.MOONRAKER, "moonraker_manager"),
        ("moonraker", PlatformControlOperation.CANCEL_JOB, "cancel", DriverKind.MOONRAKER, "moonraker_manager"),
    ],
)
async def test_control_routes_persist_and_dispatch_only_fixed_operations(
    async_client: AsyncClient,
    db_session,
    platform: str,
    operation: PlatformControlOperation,
    route_operation: str,
    driver: DriverKind,
    patch_target: str,
) -> None:
    source_id = await _create_source(async_client, platform)
    dispatch = AsyncMock(return_value=True)
    with patch(f"backend.app.api.routes.printers.{patch_target}.dispatch_command", dispatch):
        response = await async_client.post(f"/api/v1/printers/{platform}/{source_id}/control/{route_operation}")

    assert response.status_code == 200, response.text
    assert response.json()["operation"] == operation.value
    assert response.json()["status"] == "acknowledged"
    dispatched = dispatch.await_args.args[0]
    assert dispatched.driver is driver
    assert dispatched.operation is operation
    assert tuple(dispatched.__dict__) == (
        "driver",
        "source_id",
        "configuration_revision",
        "operation",
        "idempotency_key",
    )
    record = (await db_session.execute(select(PlatformControlCommandRecord))).scalar_one()
    assert (record.driver, record.source_id, record.operation, record.status) == (
        driver.value,
        source_id,
        operation.value,
        "acknowledged",
    )


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("payload", [{"gcode": "M112"}, {"path": "/printer/gcode/script"}, {"Cmd": 999}])
async def test_control_routes_reject_payloads_and_non_allowlisted_paths(
    async_client: AsyncClient, payload: dict[str, object]
) -> None:
    source_id = await _create_source(async_client, "elegoo")
    response = await async_client.post(f"/api/v1/printers/elegoo/{source_id}/control/pause", json=payload)
    assert response.status_code == 422
    assert "M112" not in response.text and "gcode/script" not in response.text

    unsupported = await async_client.post(f"/api/v1/printers/elegoo/{source_id}/control/raw-gcode")
    assert unsupported.status_code in {404, 405}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_routes_require_printer_control_permission_and_record_timeouts(
    async_client: AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_id = await _create_source(async_client, "moonraker")
    await async_client.post(
        "/api/v1/auth/setup",
        json={"auth_enabled": True, "admin_username": "control-admin", "admin_password": "AdminPass1!"},
    )
    denied = await async_client.post(f"/api/v1/printers/moonraker/{source_id}/control/pause")
    assert denied.status_code == 401

    login = await async_client.post("/api/v1/auth/login", json={"username": "control-admin", "password": "AdminPass1!"})
    token = login.json()["access_token"]

    async def never_dispatch(_command: object) -> bool:
        await asyncio.Event().wait()
        return False

    monkeypatch.setattr("backend.app.api.routes.printers.PLATFORM_CONTROL_DISPATCH_TIMEOUT_SECONDS", 0.001)
    with patch("backend.app.api.routes.printers.moonraker_manager.dispatch_command", never_dispatch):
        response = await async_client.post(
            f"/api/v1/printers/moonraker/{source_id}/control/pause",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    record = (await db_session.execute(select(PlatformControlCommandRecord))).scalar_one()
    assert record.error_code == "dispatch_timeout"
    assert record.requested_by is not None
