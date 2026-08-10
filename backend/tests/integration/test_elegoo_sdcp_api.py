"""Safety boundaries for the opt-in, passive SDCP dashboard slice."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.drivers.elegoo_sdcp_v3 import SyntheticElegooSdcpV3Driver
from backend.app.services.elegoo_sdcp_manager import _LiveSource, elegoo_sdcp_manager
from backend.tests._fixtures.elegoo_sdcp_v3 import attributes, cc1_idle_after_job_status, status


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_source_requires_acknowledgement_and_never_returns_address(async_client: AsyncClient):
    body = {
        "name": "Workshop Centauri",
        "private_ipv4": "192.168.50.20",
        "read_only_acknowledged": False,
        "is_enabled": False,
    }
    assert (await async_client.post("/api/v1/printers/elegoo", json=body)).status_code == 422

    body["read_only_acknowledged"] = True
    response = await async_client.post("/api/v1/printers/elegoo", json=body)
    assert response.status_code == 200
    source = response.json()
    assert source["id"] < 0
    assert source["platform"] == "elegoo"
    assert source["read_only"] is True
    assert "192.168.50.20" not in response.text

    listed = await async_client.get("/api/v1/printers/")
    assert listed.status_code == 200
    assert "192.168.50.20" not in listed.text
    assert next(item for item in listed.json() if item["id"] == source["id"])["ip_address"] == "Private IPv4 configured"

    status = await async_client.get(f"/api/v1/printers/elegoo/{-source['id']}/status")
    assert status.status_code == 200
    assert status.json()["phase"] == "disabled"
    assert "192.168.50.20" not in status.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_job_filename_is_not_exposed_by_any_ordinary_status_view(async_client: AsyncClient):
    created = await async_client.post(
        "/api/v1/printers/elegoo",
        json={"name": "Test", "private_ipv4": "192.168.50.21", "read_only_acknowledged": True, "is_enabled": False},
    )
    source_id = -created.json()["id"]
    live = _LiveSource(source_id, "192.168.50.21", SyntheticElegooSdcpV3Driver(f"elegoo-{source_id}"))
    elegoo_sdcp_manager._sources[source_id] = live
    live.driver.start_session("synthetic-session")
    observed_at = datetime.now(timezone.utc)
    live.driver.observe_status("synthetic-session", status(), observed_at)
    live.driver.observe_attributes("synthetic-session", attributes(), observed_at)
    try:
        response = await async_client.get(f"/api/v1/printers/{-source_id}/status")
        assert response.status_code == 200
        assert "synthetic-cube.gcode" not in response.text
        assert response.json()["current_print"] is None
    finally:
        await elegoo_sdcp_manager.disable(source_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_idle_retained_job_is_stale_not_current_and_environment_is_read_only(async_client: AsyncClient):
    with patch("backend.app.api.routes.printers.elegoo_sdcp_manager.enable", new=AsyncMock()):
        created = await async_client.post(
            "/api/v1/printers/elegoo",
            json={"name": "Test", "private_ipv4": "192.168.50.23", "read_only_acknowledged": True, "is_enabled": True},
        )
    source_id = -created.json()["id"]
    live = _LiveSource(source_id, "192.168.50.23", SyntheticElegooSdcpV3Driver(f"elegoo-{source_id}"))
    elegoo_sdcp_manager._sources[source_id] = live
    live.driver.start_session("synthetic-session")
    observed_at = datetime.now(timezone.utc)
    live.driver.observe_status("synthetic-session", cc1_idle_after_job_status(), observed_at)
    live.driver.observe_attributes("synthetic-session", attributes(), observed_at)
    try:
        dashboard = await async_client.get(f"/api/v1/printers/elegoo/{source_id}/status")
        assert dashboard.status_code == 200
        body = dashboard.json()
        assert body["state"] == "idle"
        assert body["job"] is None
        assert body["stale_job"]["progress_percent"] == pytest.approx(97.65625)
        assert body["stale_job"]["current_layer"] == 126
        assert body["stale_job"]["elapsed_seconds"] is None
        assert body["stale_job"]["estimated_remaining_seconds"] is None
        assert body["environment"] == {
            "fan": {"availability": "observed", "speed_percent": 42.0},
            "chamber_light": {"availability": "observed", "is_on": True},
        }
        assert "job-control" not in body["capabilities"]

        generic = await async_client.get(f"/api/v1/printers/{-source_id}/status")
        assert generic.status_code == 200
        assert generic.json()["progress"] is None
        assert generic.json()["layer_num"] is None
        assert generic.json()["total_layers"] is None
    finally:
        await elegoo_sdcp_manager.disable(source_id)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    "address",
    ["8.8.8.8", "127.0.0.1", "169.254.1.1", "224.0.0.1", "192.0.2.1", "printer.local", "ws://192.168.1.2/websocket"],
)
async def test_elegoo_source_rejects_non_rfc1918_or_url_inputs(async_client: AsyncClient, address: str):
    response = await async_client.post(
        "/api/v1/printers/elegoo",
        json={"name": "Test", "private_ipv4": address, "read_only_acknowledged": True, "is_enabled": False},
    )
    assert response.status_code == 422
    assert address not in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_endpoint_change_cancels_and_requires_reenable(async_client: AsyncClient):
    created = await async_client.post(
        "/api/v1/printers/elegoo",
        json={"name": "Test", "private_ipv4": "10.0.0.8", "read_only_acknowledged": True, "is_enabled": False},
    )
    source_id = -created.json()["id"]
    with patch("backend.app.api.routes.printers.elegoo_sdcp_manager.disable", new=AsyncMock()) as disable:
        response = await async_client.patch(
            f"/api/v1/printers/elegoo/{source_id}", json={"private_ipv4": "10.0.0.9", "is_enabled": True}
        )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    disable.assert_awaited()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_enabled_source_starts_only_after_explicit_enable(async_client: AsyncClient):
    with patch("backend.app.api.routes.printers.elegoo_sdcp_manager.enable", new=AsyncMock()) as enable:
        response = await async_client.post(
            "/api/v1/printers/elegoo",
            json={"name": "Test", "private_ipv4": "172.16.2.4", "read_only_acknowledged": True, "is_enabled": True},
        )
    assert response.status_code == 200
    enable.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_elegoo_source_disable_enable_and_delete_cancel_the_active_manager(async_client: AsyncClient):
    created = await async_client.post(
        "/api/v1/printers/elegoo",
        json={"name": "Test", "private_ipv4": "192.168.50.22", "read_only_acknowledged": True, "is_enabled": False},
    )
    source_id = -created.json()["id"]
    with patch("backend.app.api.routes.printers.elegoo_sdcp_manager.enable", new=AsyncMock()) as enable:
        enabled = await async_client.patch(f"/api/v1/printers/elegoo/{source_id}", json={"is_enabled": True})
    assert enabled.status_code == 200
    assert enabled.json()["is_active"] is True
    enable.assert_awaited_once()

    with patch("backend.app.api.routes.printers.elegoo_sdcp_manager.disable", new=AsyncMock()) as disable:
        disabled = await async_client.patch(f"/api/v1/printers/elegoo/{source_id}", json={"is_enabled": False})
        deleted = await async_client.delete(f"/api/v1/printers/elegoo/{source_id}")
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert deleted.status_code == 200
    assert disable.await_count == 2
    assert (await async_client.get(f"/api/v1/printers/elegoo/{source_id}")).status_code == 404
