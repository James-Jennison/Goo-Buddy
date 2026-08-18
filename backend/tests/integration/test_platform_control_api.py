"""Closed, permission-gated API paths for non-Bambu job control."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.control.contract import PlatformControlOperation, PlatformControlUnconfirmed
from backend.app.drivers.contract import (
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
)
from backend.app.models.elegoo_sdcp_source import ElegooSDCPSource
from backend.app.models.moonraker_source import MoonrakerSource
from backend.app.models.platform_control_command import PlatformControlCommand as PlatformControlCommandRecord


def _control_headers(key: str = "0123456789abcdef0123456789abcdef") -> dict[str, str]:
    return {"Idempotency-Key": key}


def _validated_cc1_observation() -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            "fixture-cc1",
            "Synthetic CC1",
            model="Centauri Carbon",
            firmware="V0.4.0-o",
        ),
        driver=DriverKind.ELEGOO_SDCP_V3,
        observed_at=datetime.now(timezone.utc),
        state="idle",
        capabilities=frozenset(),
        job=JobProgress(name=None, state="idle"),
    )
    return DriverObservation(ConnectionPhase.READY, snapshot.capabilities, current=snapshot)


def _validated_moonraker_observation() -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            "fixture-moonraker",
            "Synthetic Klipper",
            model="Klipper",
            firmware="v0.10.0-31-gd5ee171",
        ),
        driver=DriverKind.MOONRAKER,
        observed_at=datetime.now(timezone.utc),
        state="cancelled",
        capabilities=frozenset(),
        job=JobProgress(name=None, state="cancelled"),
    )
    return DriverObservation(ConnectionPhase.READY, snapshot.capabilities, current=snapshot)


async def _create_source(async_client: AsyncClient, db_session, platform: str, *, control_enabled: bool = False) -> int:
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
        source_id = -response.json()["id"]
    else:
        response = await async_client.post(
            "/api/v1/printers/moonraker",
            json={
                "name": "Synthetic Klipper",
                "private_ipv4": "192.168.50.31",
                "read_only_acknowledged": True,
                "is_enabled": False,
            },
        )
        source_id = -1_000_000 - response.json()["id"]
    if control_enabled:
        source_model = ElegooSDCPSource if platform == "elegoo" else MoonrakerSource
        # ``source_id`` is the route's positive source-table identifier after
        # the public negative compatibility ID has been translated above.
        stored_id = source_id
        # The source was committed by the application request in another test
        # session. End the fixture's pre-request transaction before reading it.
        await db_session.rollback()
        source = await db_session.get(source_model, stored_id)
        assert source is not None
        source.control_enabled = True
        source.control_acknowledged_revision = source.configuration_revision
        source.control_acknowledged_model = "fixture-model"
        source.control_acknowledged_firmware = "fixture-firmware"
        source.control_acknowledged_operations = "cancel_job,pause_job,resume_job"
        await db_session.commit()
    return source_id


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("platform", ["elegoo", "moonraker"])
async def test_new_monitoring_sources_fail_closed_before_control_dispatch(
    async_client: AsyncClient, db_session, platform: str
) -> None:
    source_id = await _create_source(async_client, db_session, platform)
    dispatch_target = "elegoo_sdcp_manager" if platform == "elegoo" else "moonraker_manager"
    dispatch = AsyncMock(return_value=True)

    with patch(f"backend.app.api.routes.printers.{dispatch_target}.dispatch_command", dispatch):
        response = await async_client.post(
            f"/api/v1/printers/{platform}/{source_id}/control/pause", headers=_control_headers()
        )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"]
    dispatch.assert_not_awaited()
    assert (await db_session.execute(select(PlatformControlCommandRecord))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("platform", ["elegoo", "moonraker"])
async def test_endpoint_replacement_revokes_fixture_control_activation(
    async_client: AsyncClient, db_session, platform: str
) -> None:
    source_id = await _create_source(async_client, db_session, platform, control_enabled=True)
    replacement = "192.168.50.32" if platform == "elegoo" else "192.168.50.33"

    response = await async_client.patch(f"/api/v1/printers/{platform}/{source_id}", json={"private_ipv4": replacement})

    assert response.status_code == 200, response.text
    await db_session.rollback()
    source_model = ElegooSDCPSource if platform == "elegoo" else MoonrakerSource
    source = await db_session.get(source_model, source_id)
    assert source is not None
    assert source.is_enabled is False
    assert source.control_enabled is False
    assert source.control_acknowledged_revision is None
    assert source.control_acknowledged_operations is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_owner_acknowledgement_requires_exact_current_validated_evidence(
    async_client: AsyncClient, db_session
) -> None:
    source_id = await _create_source(async_client, db_session, "elegoo")
    with patch(
        "backend.app.api.routes.printers.elegoo_sdcp_manager.observation",
        return_value=_validated_cc1_observation(),
    ):
        response = await async_client.post(
            f"/api/v1/printers/elegoo/{source_id}/control/acknowledgement", json={"acknowledged": True}
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "acknowledged",
        "configuration_revision": 1,
        "operations": ["cancel_job", "pause_job", "resume_job"],
    }
    await db_session.rollback()
    source = await db_session.get(ElegooSDCPSource, source_id)
    assert source is not None
    assert source.control_enabled is True
    assert source.control_acknowledged_model == "Centauri Carbon"
    assert source.control_acknowledged_firmware == "V0.4.0-o"
    assert source.control_acknowledged_operations == "cancel_job,pause_job,resume_job"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moonraker_owner_acknowledgement_requires_exact_current_validated_evidence(
    async_client: AsyncClient, db_session
) -> None:
    source_id = await _create_source(async_client, db_session, "moonraker")
    with patch(
        "backend.app.api.routes.printers.moonraker_manager.observation",
        return_value=_validated_moonraker_observation(),
    ):
        response = await async_client.post(
            f"/api/v1/printers/moonraker/{source_id}/control/acknowledgement", json={"acknowledged": True}
        )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "status": "acknowledged",
        "configuration_revision": 1,
        "operations": ["cancel_job", "pause_job", "resume_job"],
    }
    await db_session.rollback()
    source = await db_session.get(MoonrakerSource, source_id)
    assert source is not None
    assert source.control_enabled is True
    assert source.control_acknowledged_model == "Klipper"
    assert source.control_acknowledged_firmware == "v0.10.0-31-gd5ee171"
    assert source.control_acknowledged_operations == "cancel_job,pause_job,resume_job"


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("platform", ["elegoo", "moonraker"])
async def test_submission_acknowledgement_is_source_scoped_but_fails_closed_without_c5_hardware_evidence(
    async_client: AsyncClient, db_session, platform: str
) -> None:
    source_id = await _create_source(async_client, db_session, platform)
    response = await async_client.post(
        f"/api/v1/printers/{platform}/{source_id}/submission/acknowledgement",
        json={"acknowledged": True},
    )

    assert response.status_code == 409
    assert "job-submission" in response.json()["detail"]
    source_model = ElegooSDCPSource if platform == "elegoo" else MoonrakerSource
    await db_session.rollback()
    source = await db_session.get(source_model, source_id)
    assert source is not None
    await db_session.refresh(source)
    assert source.submission_enabled is False
    assert source.submission_acknowledged_revision is None
    assert source.submission_acknowledged_model is None
    assert source.submission_acknowledged_firmware is None
    assert source.submission_acknowledged_contract is None
    projection = await async_client.get(f"/api/v1/printers/{platform}/{source_id}")
    assert projection.status_code == 200
    assert projection.json()["submission_acknowledgement"] == {
        "status": "not-evidenced",
        "configuration_revision": 1,
        "contract_id": None,
    }


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("platform", ["elegoo", "moonraker"])
async def test_submission_acknowledgement_rejects_artifact_or_transport_data(
    async_client: AsyncClient, platform: str
) -> None:
    source_id = await _create_source(async_client, None, platform)
    response = await async_client.post(
        f"/api/v1/printers/{platform}/{source_id}/submission/acknowledgement",
        json={"acknowledged": True, "filename": "unsafe.gcode"},
    )

    assert response.status_code == 422
    assert "unsafe.gcode" not in response.text


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("platform", ["elegoo", "moonraker"])
async def test_source_change_revokes_any_persisted_submission_acknowledgement(
    async_client: AsyncClient, db_session, platform: str
) -> None:
    source_id = await _create_source(async_client, db_session, platform)
    source_model = ElegooSDCPSource if platform == "elegoo" else MoonrakerSource
    await db_session.rollback()
    source = await db_session.get(source_model, source_id)
    assert source is not None
    source.submission_enabled = True
    source.submission_acknowledged_revision = source.configuration_revision
    source.submission_acknowledged_model = "fixture-model"
    source.submission_acknowledged_firmware = "fixture-firmware"
    source.submission_acknowledged_contract = "fixture-contract"
    await db_session.commit()

    replacement = "192.168.50.32" if platform == "elegoo" else "192.168.50.33"
    response = await async_client.patch(f"/api/v1/printers/{platform}/{source_id}", json={"private_ipv4": replacement})

    assert response.status_code == 200, response.text
    await db_session.rollback()
    source = await db_session.get(source_model, source_id)
    assert source is not None
    await db_session.refresh(source)
    assert source.submission_enabled is False
    assert source.submission_acknowledged_revision is None
    assert source.submission_acknowledged_model is None
    assert source.submission_acknowledged_firmware is None
    assert source.submission_acknowledged_contract is None


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
    source_id = await _create_source(async_client, db_session, platform, control_enabled=True)
    dispatch = AsyncMock(return_value=True)
    with patch(f"backend.app.api.routes.printers.{patch_target}.dispatch_command", dispatch):
        response = await async_client.post(
            f"/api/v1/printers/{platform}/{source_id}/control/{route_operation}", headers=_control_headers()
        )

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
    async_client: AsyncClient, db_session, payload: dict[str, object]
) -> None:
    source_id = await _create_source(async_client, db_session, "elegoo", control_enabled=True)
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
    source_id = await _create_source(async_client, db_session, "moonraker", control_enabled=True)
    await async_client.post(
        "/api/v1/auth/setup",
        json={"auth_enabled": True, "admin_username": "control-admin", "admin_password": "AdminPass1!"},
    )
    denied = await async_client.post(
        f"/api/v1/printers/moonraker/{source_id}/control/pause", headers=_control_headers()
    )
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
            headers={"Authorization": f"Bearer {token}", **_control_headers()},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    record = (await db_session.execute(select(PlatformControlCommandRecord))).scalar_one()
    assert record.error_code == "dispatch_timeout"
    assert record.requested_by is not None


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    ("platform", "route_operation", "patch_target"),
    [
        ("elegoo", "pause", "elegoo_sdcp_manager"),
        ("moonraker", "cancel", "moonraker_manager"),
    ],
)
async def test_control_routes_record_disconnects_without_exposing_transport_details(
    async_client: AsyncClient,
    db_session,
    platform: str,
    route_operation: str,
    patch_target: str,
) -> None:
    source_id = await _create_source(async_client, db_session, platform, control_enabled=True)
    disconnect = AsyncMock(side_effect=ConnectionError("private transport disconnected"))

    with patch(f"backend.app.api.routes.printers.{patch_target}.dispatch_command", disconnect):
        response = await async_client.post(
            f"/api/v1/printers/{platform}/{source_id}/control/{route_operation}", headers=_control_headers()
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert "private transport" not in response.text
    record = (await db_session.execute(select(PlatformControlCommandRecord))).scalar_one()
    assert (record.status, record.error_code) == ("failed", "dispatch_failed")


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    ("platform", "route_operation", "patch_target"),
    [
        ("elegoo", "pause", "elegoo_sdcp_manager"),
        ("moonraker", "pause", "moonraker_manager"),
    ],
)
async def test_control_reports_a_missing_state_confirmation_without_acknowledging_it(
    async_client: AsyncClient,
    db_session,
    platform: str,
    route_operation: str,
    patch_target: str,
) -> None:
    source_id = await _create_source(async_client, db_session, platform, control_enabled=True)
    dispatch = AsyncMock(side_effect=PlatformControlUnconfirmed)

    with patch(f"backend.app.api.routes.printers.{patch_target}.dispatch_command", dispatch):
        response = await async_client.post(
            f"/api/v1/printers/{platform}/{source_id}/control/{route_operation}", headers=_control_headers()
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error_code"] == "unconfirmed"
    record = (await db_session.execute(select(PlatformControlCommandRecord))).scalar_one()
    assert (record.status, record.error_code) == ("failed", "unconfirmed")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_routes_replay_the_same_key_without_a_second_dispatch(
    async_client: AsyncClient, db_session
) -> None:
    source_id = await _create_source(async_client, db_session, "elegoo", control_enabled=True)
    dispatch = AsyncMock(return_value=True)
    key = "abcdef0123456789abcdef0123456789"
    with patch("backend.app.api.routes.printers.elegoo_sdcp_manager.dispatch_command", dispatch):
        first = await async_client.post(
            f"/api/v1/printers/elegoo/{source_id}/control/pause", headers=_control_headers(key)
        )
        replay = await async_client.post(
            f"/api/v1/printers/elegoo/{source_id}/control/pause", headers=_control_headers(key)
        )

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert dispatch.await_count == 1
    assert len((await db_session.execute(select(PlatformControlCommandRecord))).scalars().all()) == 1


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("key", ["M112", "/printer/gcode/script", "A" * 32, "0" * 31])
async def test_control_routes_reject_invalid_idempotency_keys(async_client: AsyncClient, db_session, key: str) -> None:
    source_id = await _create_source(async_client, db_session, "moonraker", control_enabled=True)
    response = await async_client.post(
        f"/api/v1/printers/moonraker/{source_id}/control/cancel", headers={"Idempotency-Key": key}
    )

    assert response.status_code == 422
    assert "M112" not in response.text and "gcode/script" not in response.text
    assert (await db_session.execute(select(PlatformControlCommandRecord))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_control_routes_reject_key_reuse_for_a_different_fixed_operation(
    async_client: AsyncClient, db_session
) -> None:
    source_id = await _create_source(async_client, db_session, "moonraker", control_enabled=True)
    key = "fedcba9876543210fedcba9876543210"
    dispatch = AsyncMock(return_value=True)
    with patch("backend.app.api.routes.printers.moonraker_manager.dispatch_command", dispatch):
        accepted = await async_client.post(
            f"/api/v1/printers/moonraker/{source_id}/control/pause", headers=_control_headers(key)
        )
        rejected = await async_client.post(
            f"/api/v1/printers/moonraker/{source_id}/control/cancel", headers=_control_headers(key)
        )

    assert accepted.status_code == 200
    assert rejected.status_code == 409
    assert dispatch.await_count == 1
    assert len((await db_session.execute(select(PlatformControlCommandRecord))).scalars().all()) == 1


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize("platform", ["elegoo", "moonraker"])
async def test_non_bambu_sources_cannot_enter_bambu_only_workflows(
    async_client: AsyncClient, db_session, platform: str
) -> None:
    """Keep source namespaces out of legacy Bambu command and data paths.

    These are representative entry points for the Bambu-only command, queue,
    FTP/file upload, virtual-printer, camera, and maintenance workflows.  The
    public source identifier is deliberately synthetic, and every legacy path
    must reject it before touching a Bambu transport or persisting work.
    """

    source_id = await _create_source(async_client, db_session, platform)

    command = await async_client.post(f"/api/v1/printers/{source_id}/print/pause")
    queue = await async_client.post(
        "/api/v1/queue/",
        json={"archive_id": 999_999, "printer_id": source_id},
    )
    file_manager = await async_client.get(f"/api/v1/printers/{source_id}/files")
    camera = await async_client.get(f"/api/v1/printers/{source_id}/camera/test")
    maintenance = await async_client.get(f"/api/v1/maintenance/printers/{source_id}")
    virtual_printer = await async_client.post(
        "/api/v1/virtual-printers",
        json={"name": "Rejected non-Bambu target", "target_printer_id": source_id},
    )
    upload = await async_client.post(
        f"/api/v1/archives/upload?printer_id={source_id}",
        files={"file": ("source.3mf", b"not-a-3mf", "application/octet-stream")},
    )
    bulk_upload = await async_client.post(
        f"/api/v1/archives/upload-bulk?printer_id={source_id}",
        files=[("files", ("source.3mf", b"not-a-3mf", "application/octet-stream"))],
    )

    assert command.status_code == 404
    assert queue.status_code == 400
    assert file_manager.status_code == 404
    assert camera.status_code == 404
    assert maintenance.status_code == 404
    assert virtual_printer.status_code == 400
    assert upload.status_code == 400
    assert bulk_upload.status_code == 400
