"""API redaction and lifecycle boundaries for synthetic Moonraker sources."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from backend.app.models.moonraker_source import MoonrakerSource


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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moonraker_camera_proxy_is_hostless_and_drops_cache_busters(async_client: AsyncClient):
    created = await async_client.post(
        "/api/v1/printers/moonraker",
        json={
            "name": "Synthetic camera proxy",
            "private_ipv4": "10.0.0.55",
            "camera_proxy_scheme": "http",
            "camera_proxy_port": 80,
            "camera_proxy_path": "/webcam/?action=stream&cacheBust=12345",
            "read_only_acknowledged": True,
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["camera_proxy_configured"] is True
    assert "10.0.0.55" not in created.text
    assert "webcam" not in created.text

    public_id = -1_000_000 - payload["id"]
    incomplete = await async_client.patch(f"/api/v1/printers/moonraker/{public_id}", json={"camera_proxy_path": None})
    assert incomplete.status_code == 422


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moonraker_camera_snapshot_is_backend_proxied_and_bounded_to_the_source(
    async_client: AsyncClient, db_session
):
    """The browser receives only Goo Buddy JPEG bytes, never a printer URL."""
    source = MoonrakerSource(
        display_name="Synthetic camera",
        private_ipv4="10.0.0.45",
        port=7125,
        scheme="http",
        is_enabled=True,
        read_only_acknowledged=True,
    )
    db_session.add(source)
    await db_session.commit()
    await db_session.refresh(source)
    public_id = -1_000_000 - source.id

    with patch(
        "backend.app.api.routes.camera.moonraker_manager.camera_snapshot",
        new=AsyncMock(return_value=b"\xff\xd8synthetic-jpeg"),
    ) as snapshot:
        response = await async_client.get(f"/api/v1/printers/moonraker/{public_id}/camera/snapshot")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == b"\xff\xd8synthetic-jpeg"
    snapshot.assert_awaited_once_with(source.id)


def test_moonraker_camera_snapshot_uses_browser_image_stream_token_gate():
    """A bearer-only dependency would make a protected ``<img>`` unusable."""
    from backend.app.core.auth import RequireCameraStreamTokenIfAuthEnabled
    from backend.app.main import app

    route = next(
        route
        for route in app.routes
        if getattr(route, "path", None) == "/api/v1/printers/moonraker/{source_id}/camera/snapshot"
    )
    gates = [dependency.call for dependency in route.dependant.dependencies if dependency.call]
    assert RequireCameraStreamTokenIfAuthEnabled.dependency in gates
