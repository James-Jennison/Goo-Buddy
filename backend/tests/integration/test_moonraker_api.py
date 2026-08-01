"""API redaction and lifecycle boundaries for synthetic Moonraker sources."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moonraker_source_is_manual_and_redacts_endpoint_and_api_key(async_client: AsyncClient):
    body = {
        "name": "Synthetic Klipper",
        "private_ipv4": "192.168.50.44",
        "port": 7125,
        "scheme": "http",
        "api_key": "synthetic-key",
        "read_only_acknowledged": True,
        "is_enabled": False,
    }
    response = await async_client.post("/api/v1/printers/moonraker", json=body)
    assert response.status_code == 200
    source = response.json()
    assert source["platform"] == "moonraker" and source["api_key_configured"] is True
    assert "192.168.50.44" not in response.text and "synthetic-key" not in response.text
    listed = await async_client.get("/api/v1/printers/")
    assert "192.168.50.44" not in listed.text and "synthetic-key" not in listed.text


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.parametrize(
    "address", ["8.8.8.8", "127.0.0.1", "169.254.1.1", "printer.local", "http://192.168.1.2", "192.168.1.2/path"]
)
async def test_moonraker_rejects_unsafe_endpoint_inputs_without_reflection(async_client: AsyncClient, address: str):
    response = await async_client.post(
        "/api/v1/printers/moonraker", json={"name": "Test", "private_ipv4": address, "read_only_acknowledged": True}
    )
    assert response.status_code == 422
    assert address not in response.text


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moonraker_endpoint_or_key_edit_cancels_and_requires_explicit_reenable(async_client: AsyncClient):
    created = await async_client.post(
        "/api/v1/printers/moonraker", json={"name": "Test", "private_ipv4": "10.0.0.24", "read_only_acknowledged": True}
    )
    source_id = -1_000_000 - created.json()["id"]
    with patch("backend.app.api.routes.printers.moonraker_manager.disable", new=AsyncMock()) as disable:
        changed = await async_client.patch(
            f"/api/v1/printers/moonraker/{source_id}", json={"api_key": "replacement", "is_enabled": True}
        )
    assert changed.status_code == 200 and changed.json()["is_active"] is False
    disable.assert_awaited_once()
