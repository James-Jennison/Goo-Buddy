"""Synthetic-only proof of the closed Moonraker request vocabulary."""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from aiohttp import WSMsgType

from backend.app.services.moonraker_read_only import (
    MoonrakerReadOnlyMethod,
    select_monitored_objects,
    serialize_read_only_request,
)


def test_only_allowlisted_read_only_methods_are_serialized():
    objects = select_monitored_objects(["webhooks", "extruder", "gcode", "heater_bed"])
    assert objects == {"extruder": None, "heater_bed": None, "webhooks": None}
    for method in MoonrakerReadOnlyMethod:
        request = json.loads(serialize_read_only_request(method, objects))
        assert request["method"] in {"printer.objects.query", "printer.objects.subscribe"}
        assert request["jsonrpc"] == "2.0"


@pytest.mark.parametrize(
    "method", ["printer.gcode.script", "printer.print.start", 0, True, {"method": "printer.objects.query"}, None]
)
def test_no_generic_or_mutating_rpc_method_can_be_serialized(method):
    with pytest.raises(ValueError, match="unsupported"):
        serialize_read_only_request(method, {})


@pytest.mark.parametrize("objects", [{"gcode": None}, {"extruder": ["temperature"]}, ["extruder"], None])
def test_object_selection_cannot_request_fields_or_arbitrary_objects(objects):
    with pytest.raises(ValueError, match="invalid monitored"):
        serialize_read_only_request(MoonrakerReadOnlyMethod.OBJECTS_QUERY, objects)


def test_status_parser_ignores_unknown_or_malformed_payloads():
    from backend.app.services.moonraker_manager import MoonrakerManager

    selection = {"extruder": None, "webhooks": None}
    assert (
        MoonrakerManager._validated_status_message(
            '{"method":"notify_status_update","params":[{"gcode":{}}]}', selection
        )
        is None
    )
    assert MoonrakerManager._validated_status_message("not-json", selection) is None
    assert MoonrakerManager._validated_status_message(
        '{"id":1,"result":{"status":{"extruder":{"temperature":210}}}}', selection, {1}
    ) == {"extruder": {"temperature": 210}}
    assert (
        MoonrakerManager._validated_status_message(
            '{"id":2,"result":{"status":{"extruder":{"temperature":210}}}}', selection, {1}
        )
        is None
    )


def test_webcam_snapshot_path_is_same_origin_and_never_exposes_full_urls():
    from backend.app.services.moonraker_manager import MoonrakerManager

    payload = {
        "result": {
            "webcams": [
                {"enabled": True, "snapshot_url": "https://camera.example/snapshot"},
                {"enabled": True, "snapshot_url": "/webcam/?action=snapshot"},
            ]
        }
    }
    assert MoonrakerManager._validated_snapshot_path(payload) == "/webcam/?action=snapshot"
    for candidate in (
        "//camera/snapshot",
        "/../server/config",
        "/%2e%2e/server/config",
        "/webcam/%2f..%2fserver/config",
        "/webcam/#fragment",
        "http://camera/snapshot",
    ):
        assert (
            MoonrakerManager._validated_snapshot_path(
                {"result": {"webcams": [{"enabled": True, "snapshot_url": candidate}]}}
            )
            is None
        )


def test_webcam_stream_path_is_same_origin_and_a_mjpeg_frame_is_bounded():
    from backend.app.services.moonraker_manager import MoonrakerManager

    payload = {"result": {"webcams": [{"enabled": True, "stream_url": "/webcam/?action=stream"}]}}
    assert MoonrakerManager._validated_camera_path(payload, "stream_url") == "/webcam/?action=stream"
    boundary = MoonrakerManager._multipart_boundary("multipart/x-mixed-replace; boundary=frame")
    assert boundary == b"frame"
    frame = b"\xff\xd8synthetic-jpeg"
    stream = b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 16\r\n\r\n" + frame + b"\r\n--frame--\r\n"
    assert MoonrakerManager._extract_mjpeg_frame(stream, boundary) == frame
    assert MoonrakerManager._extract_mjpeg_frame(stream.replace(b"image/jpeg", b"text/plain"), boundary) is None


def test_mainsail_camera_proxy_path_drops_cache_busters_and_rejects_other_urls():
    from backend.app.schemas.printer import normalize_mainsail_camera_proxy_path

    assert normalize_mainsail_camera_proxy_path("/webcam/?action=stream&cacheBust=12345") == "/webcam/?action=stream"
    for candidate in (
        "http://camera/webcam/?action=stream",
        "//camera/webcam/?action=stream",
        "/server/files/?action=stream",
        "/webcam/?action=stream&token=opaque",
        "/webcam/?action=stream&cacheBust=not-a-number",
    ):
        with pytest.raises(ValueError, match="Invalid Mainsail camera proxy path"):
            normalize_mainsail_camera_proxy_path(candidate)


class _FixtureMoonrakerSocket:
    """Deterministic in-memory Moonraker peer with no control vocabulary."""

    def __init__(self):
        self.sent: list[dict] = []
        self._incoming: asyncio.Queue[object] = asyncio.Queue()

    async def send_str(self, payload: str) -> None:
        request = json.loads(payload)
        self.sent.append(request)
        if len(self.sent) == 2:
            status = {
                "webhooks": {"state": "ready"},
                "print_stats": {"state": "standby"},
                "extruder": {"temperature": 25},
            }
            await self._incoming.put(
                type(
                    "Message",
                    (),
                    {
                        "type": WSMsgType.TEXT,
                        "data": json.dumps({"id": self.sent[0]["id"], "result": {"status": status}}),
                    },
                )()
            )
            await self._incoming.put(type("Message", (), {"type": WSMsgType.CLOSED, "data": None})())

    async def receive(self):
        return await self._incoming.get()

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_fixture_server_receives_only_query_and_subscription_and_yields_valid_status():
    from backend.app.drivers.moonraker import MoonrakerDriver
    from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker

    manager = MoonrakerManager()
    live = _LiveMoonraker(
        1,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-1", "Synthetic"),
        server={"klippy_state": "ready"},
    )
    live.driver.start_session("fixture")
    socket = _FixtureMoonrakerSocket()
    await manager._serve(socket, live, "fixture", {"webhooks": None, "print_stats": None, "extruder": None})
    assert [item["method"] for item in socket.sent] == ["printer.objects.query", "printer.objects.subscribe"]
    assert live.driver.observation(datetime.now(timezone.utc)).phase.value == "ready"


def test_unsafe_or_oversized_response_category_is_exposed_as_invalid_not_ready():
    from backend.app.drivers.moonraker import MoonrakerDriver
    from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker

    manager = MoonrakerManager()
    live = _LiveMoonraker(
        1,
        "Synthetic",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-1", "Synthetic"),
        error="oversized_frame",
    )
    manager._sources[1] = live
    assert manager.observation(1).phase.value == "invalid"
