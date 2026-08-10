import json
from pathlib import Path

import pytest
from aiohttp.test_utils import make_mocked_request

ROOT = Path(__file__).resolve().parents[3]


def test_virtual_farm_matrix_is_complete_and_uniform():
    data = json.loads((ROOT / "virtual_farm/profiles.v1.json").read_text())
    assert data["version"] == 1
    required = {
        "Bambu Lab",
        "Elegoo SDCP v3",
        "Klipper via Moonraker",
        "RepRapFirmware / Duet 2 and Duet 3",
        "Direct serial G-code",
        "Repetier-Server-hosted printers",
        "Klipper/Moonraker derivatives",
        "FlashForge",
        "Raise3D",
        "Anycubic",
        "Snapmaker",
        "Creality",
        "PrusaLink",
    }
    assert {item["family"] for item in data["profiles"]} == required
    assert all(item["status"] in data["statuses"] and item["evidence"] for item in data["profiles"])


def test_virtual_farm_compose_is_localhost_only():
    compose = (ROOT / "docker-compose.virtual-farm.yml").read_text()
    assert "127.0.0.1:17125:17125" in compose and "profiles: [virtual-farm]" in compose
    assert "127.0.0.1:17126:17126" in compose and "VIRTUAL_FARM_VIDEO_DEVICE" not in compose
    usb = (ROOT / "docker-compose.virtual-farm-camera-usb.yml").read_text()
    assert "127.0.0.1:17127:17127" in usb
    assert "VIRTUAL_FARM_VIDEO_DEVICE" in usb
    assert '"--camera-mode", "v4l2"' in usb
    assert '"--host", "0.0.0.0"' in compose and '"--host", "0.0.0.0"' in usb
    assert "devices:" in usb
    assert "devices:" not in compose


def test_camera_fixture_is_opt_in():
    from virtual_farm.simulator import CAMERA_ENABLED, FIXTURE_JPEG, app

    assert app()[CAMERA_ENABLED] is False
    assert app("fixture")[CAMERA_ENABLED] is True
    assert FIXTURE_JPEG.startswith(b"\xff\xd8")


class _FrameSource:
    name = "v4l2"

    def __init__(self, payload: bytes | None = None, failure: Exception | None = None):
        self.payload = payload
        self.failure = failure
        self.calls = 0

    async def frame(self) -> bytes:
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        assert self.payload is not None
        return self.payload


async def _simulator_response(simulator, path: str):
    request = make_mocked_request("GET", path, app=simulator)
    match = await simulator.router.resolve(request)
    return await match.handler(request)


@pytest.mark.asyncio
async def test_v4l2_source_reaches_snapshot_and_stream_routes():
    from virtual_farm.simulator import CAMERA_ENABLED, FIXTURE_JPEG, app

    source = _FrameSource(FIXTURE_JPEG + b"v4l2")
    simulator = app("v4l2", camera_device="/dev/video7", frame_source=source)
    snapshot = await _simulator_response(simulator, "/camera/snapshot")
    stream = await _simulator_response(simulator, "/camera/stream")

    assert simulator[CAMERA_ENABLED] is True
    assert source.calls == 2
    assert snapshot.status == stream.status == 200
    assert snapshot.body == stream.body == FIXTURE_JPEG + b"v4l2"
    assert snapshot.headers["X-Virtual-Farm-Camera"] == "v4l2"


@pytest.mark.asyncio
async def test_v4l2_capture_failure_is_unavailable_not_fixture_data():
    from virtual_farm.simulator import CameraUnavailable, V4L2FrameSource, app

    devices: list[str] = []

    async def failed_capture(device: str) -> bytes:
        devices.append(device)
        raise CameraUnavailable("device lost")

    source = V4L2FrameSource("/dev/video7", capture=failed_capture)
    simulator = app("v4l2", camera_device="/dev/video7", frame_source=source)
    response = await _simulator_response(simulator, "/camera/snapshot")

    assert devices == ["/dev/video7"]
    assert response.status == 503
    assert b"unavailable" in response.body
    assert b"fixture" not in response.body


@pytest.mark.asyncio
async def test_fixture_camera_never_selects_injected_v4l2_source():
    from virtual_farm.simulator import FIXTURE_JPEG, app

    fixture = app("fixture")
    response = await _simulator_response(fixture, "/camera/snapshot")

    assert response.status == 200
    assert response.body == FIXTURE_JPEG
    assert response.headers["X-Virtual-Farm-Camera"] == "fixture"


@pytest.mark.asyncio
async def test_disabled_or_unconfigured_camera_does_not_advertise_endpoints():
    from virtual_farm.simulator import CAMERA_ENABLED, app

    for simulator in (app(), app("v4l2"), app("v4l2", camera_device="/dev/not-video")):
        response = await _simulator_response(simulator, "/server/webcams/list")
        assert simulator[CAMERA_ENABLED] is False
        assert json.loads(response.body) == {"result": {"webcams": []}}


@pytest.mark.asyncio
async def test_moonraker_simulator_exposes_only_fixed_gcode_inventory():
    from virtual_farm.simulator import app

    simulator = app()
    response = await _simulator_response(simulator, "/server/files/list?root=gcodes")
    assert response.status == 200
    assert json.loads(response.body) == {
        "result": [
            {"path": "virtual-farm-benchy.gcode", "size": 4926481, "modified": 1700000000.0},
            {"path": "fixtures/calibration-cube.gcode", "size": 324236, "modified": 1700000060.0},
        ]
    }
    rejected = await _simulator_response(simulator, "/server/files/list?root=config")
    assert rejected.status == 400


@pytest.mark.asyncio
async def test_moonraker_simulator_exposes_only_bounded_console_history():
    from virtual_farm.simulator import app

    simulator = app()
    response = await _simulator_response(simulator, "/server/gcode_store?count=50")
    assert response.status == 200
    assert json.loads(response.body)["result"]["gcode_store"][0]["type"] == "command"
    rejected = await _simulator_response(simulator, "/server/gcode_store?count=51")
    assert rejected.status == 400


@pytest.mark.asyncio
async def test_v4l2_source_uses_injected_capture_seam():
    from virtual_farm.simulator import FIXTURE_JPEG, V4L2FrameSource

    devices: list[str] = []

    async def capture(device: str) -> bytes:
        devices.append(device)
        return FIXTURE_JPEG

    source = V4L2FrameSource("/dev/video7", capture=capture)
    assert await source.frame() == FIXTURE_JPEG
    assert devices == ["/dev/video7"]
