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
    objects = select_monitored_objects(["webhooks", "extruder", "gcode", "heater_bed", "toolhead"])
    assert objects == {
        "extruder": ["temperature", "target"],
        "heater_bed": ["temperature", "target"],
        "toolhead": ["extruder", "homed_axes"],
        "webhooks": ["state"],
    }
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

    selection = {"extruder": ["temperature", "target"], "webhooks": ["state"]}
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
            '{"id":1,"result":{"status":{"extruder":{"temperature":210,"unsafe":"discard"}}}}', selection, {1}
        )
        is None
    )
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


def test_fixed_gcode_inventory_is_bounded_display_data_only():
    from backend.app.services.moonraker_read_only import parse_gcode_file_inventory

    inventory = parse_gcode_file_inventory(
        {
            "result": [
                {"path": "models/benchy.gcode", "size": 4926481, "modified": 1700000000.5},
                {"path": "cube.gcode", "size": 324236, "modified": 1700000060},
            ]
        }
    )
    assert [(item.path, item.size, item.modified) for item in inventory] == [
        ("models/benchy.gcode", 4926481, 1700000000.5),
        ("cube.gcode", 324236, 1700000060.0),
    ]

    for payload in (
        {"result": [{"path": "../printer.cfg", "size": 1, "modified": 1}]},
        {"result": [{"path": "/absolute.gcode", "size": 1, "modified": 1}]},
        {"result": [{"path": "cube.gcode", "size": -1, "modified": 1}]},
        {"result": [{"path": "cube.gcode", "size": 1, "modified": float("nan")}]},
        {"result": "not-a-list"},
    ):
        with pytest.raises(ValueError, match="invalid Moonraker gcode inventory"):
            parse_gcode_file_inventory(payload)


def test_gcode_metadata_is_projected_only_for_the_selected_inventory_path():
    from backend.app.services.moonraker_read_only import parse_gcode_metadata

    metadata = parse_gcode_metadata(
        {
            "result": {
                "filename": "models/benchy.gcode",
                "slicer": "OrcaSlicer",
                "slicer_version": "2.3.0",
                "estimated_time": 3600,
                "object_height": 48.2,
                "filament_weight_total": 18.4,
                "layer_height": 0.2,
                "nozzle_diameter": 0.4,
                "ignored_raw_payload": {"arbitrary": "data"},
            }
        },
        "models/benchy.gcode",
    )
    assert metadata.path == "models/benchy.gcode"
    assert metadata.slicer == "OrcaSlicer"
    assert metadata.estimated_time == 3600.0
    assert not hasattr(metadata, "ignored_raw_payload")

    for payload, path in (
        ({"result": {"filename": "other.gcode"}}, "models/benchy.gcode"),
        ({"result": {"filename": "models/benchy.gcode", "slicer": "x" * 161}}, "models/benchy.gcode"),
        ({"result": {"filename": "models/benchy.gcode", "estimated_time": -1}}, "models/benchy.gcode"),
        ({"result": {"filename": "models/benchy.gcode", "layer_height": float("nan")}}, "models/benchy.gcode"),
        ({"result": {"filename": "models/benchy.gcode"}}, "../printer.cfg"),
    ):
        with pytest.raises(ValueError, match="invalid Moonraker gcode metadata"):
            parse_gcode_metadata(payload, path)


def test_gcode_thumbnail_reference_is_internal_and_cannot_traverse_the_gcodes_root():
    from backend.app.services.moonraker_read_only import parse_gcode_metadata

    metadata = parse_gcode_metadata(
        {
            "result": {
                "filename": "models/benchy.gcode",
                "thumbnails": [
                    {"width": 400, "height": 300, "size": 1024, "relative_path": ".thumbs/benchy-400.png"},
                    {"width": 32, "height": 32, "size": 100, "relative_path": ".thumbs/benchy-32.png"},
                ],
            }
        },
        "models/benchy.gcode",
    )
    assert metadata.thumbnail is not None
    assert metadata.thumbnail.path == "models/.thumbs/benchy-400.png"
    assert (metadata.thumbnail.width, metadata.thumbnail.height, metadata.thumbnail.size) == (400, 300, 1024)

    for relative_path in (
        "../printer.cfg",
        "/server/files/config",
        "https://example.invalid/thumb.png",
        "thumbs\\evil.png",
    ):
        with pytest.raises(ValueError, match="invalid Moonraker gcode metadata"):
            parse_gcode_metadata(
                {
                    "result": {
                        "filename": "models/benchy.gcode",
                        "thumbnails": [{"width": 400, "height": 300, "size": 1024, "relative_path": relative_path}],
                    }
                },
                "models/benchy.gcode",
            )


@pytest.mark.asyncio
async def test_metadata_request_is_bound_to_the_fresh_cached_inventory():
    from backend.app.drivers.moonraker import MoonrakerDriver
    from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker
    from backend.app.services.moonraker_read_only import MoonrakerGcodeFile

    class _Content:
        async def read(self, _limit):
            return b'{"result":{"filename":"models/benchy.gcode","slicer":"OrcaSlicer"}}'

    class _Response:
        status = 200
        content_type = "application/json"
        content = _Content()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class _Client:
        def __init__(self):
            self.requests = []

        def get(self, url, **kwargs):
            self.requests.append((url, kwargs))
            return _Response()

    driver = MoonrakerDriver("moonraker-1", "Synthetic")
    driver.start_session("session")
    assert driver.observe(
        "session",
        {"webhooks": {"state": "ready"}, "extruder": {"temperature": 25}},
        {"klippy_state": "ready"},
        datetime.now(timezone.utc),
    )
    live = _LiveMoonraker(1, "Synthetic", "192.168.1.44", 7125, "http", None, driver)
    client = _Client()
    live.client = client
    live.gcode_files = (MoonrakerGcodeFile("models/benchy.gcode", 1, 1.0),)
    manager = MoonrakerManager()
    manager._sources[1] = live

    metadata = await manager.gcode_metadata(1, "models/benchy.gcode")
    assert metadata is not None and metadata.slicer == "OrcaSlicer"
    assert client.requests == [
        (
            "http://192.168.1.44:7125/server/files/metadata",
            {"params": {"filename": "models/benchy.gcode"}, "allow_redirects": False},
        )
    ]
    assert await manager.gcode_metadata(1, "../printer.cfg") is None
    assert len(client.requests) == 1


@pytest.mark.asyncio
async def test_thumbnail_request_is_bound_to_metadata_and_returns_only_a_valid_image():
    from backend.app.drivers.moonraker import MoonrakerDriver
    from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker
    from backend.app.services.moonraker_read_only import MoonrakerGcodeFile

    class _Content:
        def __init__(self, payload):
            self.payload = payload

        async def read(self, _limit):
            return self.payload

    class _Response:
        status = 200

        def __init__(self, content_type, payload):
            self.content_type = content_type
            self.content = _Content(payload)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

    class _Client:
        def __init__(self):
            self.requests = []

        def get(self, url, **kwargs):
            self.requests.append((url, kwargs))
            if url.endswith("/metadata"):
                return _Response(
                    "application/json",
                    b'{"result":{"filename":"models/benchy.gcode","thumbnails":[{"width":400,"height":300,"size":16,"relative_path":".thumbs/benchy.png"}]}}',
                )
            return _Response("image/png", b"\x89PNG\r\n\x1a\nsynthetic-thumbnail")

    driver = MoonrakerDriver("moonraker-1", "Synthetic")
    driver.start_session("session")
    assert driver.observe(
        "session",
        {"webhooks": {"state": "ready"}, "extruder": {"temperature": 25}},
        {"klippy_state": "ready"},
        datetime.now(timezone.utc),
    )
    live = _LiveMoonraker(1, "Synthetic", "192.168.1.44", 7125, "http", None, driver)
    client = _Client()
    live.client = client
    live.gcode_files = (MoonrakerGcodeFile("models/benchy.gcode", 1, 1.0),)
    manager = MoonrakerManager()
    manager._sources[1] = live

    thumbnail = await manager.gcode_thumbnail(1, "models/benchy.gcode")
    assert thumbnail is not None
    assert thumbnail.media_type == "image/png"
    assert thumbnail.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert client.requests == [
        (
            "http://192.168.1.44:7125/server/files/metadata",
            {"params": {"filename": "models/benchy.gcode"}, "allow_redirects": False},
        ),
        ("http://192.168.1.44:7125/server/files/gcodes/models/.thumbs/benchy.png", {"allow_redirects": False}),
    ]


@pytest.mark.asyncio
async def test_thumbnail_response_rejects_mismatched_mime_and_magic_bytes():
    from backend.app.services.moonraker_manager import MoonrakerManager

    class _Content:
        async def read(self, _limit):
            return b"not-an-image"

    class _Response:
        status = 200
        content_type = "image/png"
        content = _Content()

    assert await MoonrakerManager._gcode_thumbnail_from_response(_Response()) is None


def test_file_capability_requires_a_valid_fixed_root_inventory():
    from backend.app.drivers.contract import Capability
    from backend.app.drivers.moonraker import normalize_moonraker_observation

    snapshot = normalize_moonraker_observation(
        local_id="moonraker-1",
        display_name="Synthetic",
        observed_at=datetime.now(timezone.utc),
        status={"webhooks": {"state": "ready"}, "extruder": {"temperature": 25}},
        server={"klippy_state": "ready"},
        files_available=True,
    )
    assert Capability.FILES in snapshot.capabilities


def test_fixed_console_history_is_bounded_and_cannot_be_a_command_path():
    from backend.app.services.moonraker_read_only import parse_console_history

    history = parse_console_history(
        {
            "result": {
                "gcode_store": [
                    {"message": "STATUS", "time": 1700000000, "type": "command"},
                    {"message": "// Klipper state: Ready", "time": 1700000000.1, "type": "response"},
                ]
            }
        }
    )
    assert [(entry.message, entry.kind) for entry in history] == [
        ("STATUS", "command"),
        ("// Klipper state: Ready", "response"),
    ]
    for payload in (
        {"result": {"gcode_store": [{"message": "G28", "time": 1, "type": "other"}]}},
        {"result": {"gcode_store": [{"message": "\x00", "time": 1, "type": "command"}]}},
        {"result": {"gcode_store": "not-a-list"}},
    ):
        with pytest.raises(ValueError, match="invalid Moonraker console history"):
            parse_console_history(payload)


def test_console_history_capability_requires_valid_cached_history():
    from backend.app.drivers.contract import Capability
    from backend.app.drivers.moonraker import normalize_moonraker_observation

    snapshot = normalize_moonraker_observation(
        local_id="moonraker-1",
        display_name="Synthetic",
        observed_at=datetime.now(timezone.utc),
        status={"webhooks": {"state": "ready"}, "extruder": {"temperature": 25}},
        server={"klippy_state": "ready"},
        console_history_available=True,
    )
    assert Capability.CONSOLE_HISTORY in snapshot.capabilities


@pytest.mark.asyncio
async def test_discovery_uses_only_the_fixed_gcodes_list_request():
    from backend.app.drivers.moonraker import MoonrakerDriver
    from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker

    class _Response:
        def __init__(self, payload):
            self.status = 200
            self._payload = payload

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        async def json(self, **_):
            return self._payload

        def raise_for_status(self):
            return None

    class _Client:
        def __init__(self):
            self.requests = []

        def get(self, url, **kwargs):
            self.requests.append((url, kwargs))
            payloads = {
                "/server/info": {"result": {"klippy_state": "ready"}},
                "/printer/objects/list": {"result": {"objects": ["webhooks", "extruder"]}},
                "/server/webcams/list": {"result": {"webcams": []}},
                "/server/files/list": {"result": [{"path": "benchy.gcode", "size": 1, "modified": 1}]},
                "/server/gcode_store": {"result": {"gcode_store": []}},
            }
            return _Response(next(payload for suffix, payload in payloads.items() if url.endswith(suffix)))

    manager = MoonrakerManager()
    live = _LiveMoonraker(
        1, "Synthetic", "192.168.1.44", 7125, "http", None, MoonrakerDriver("moonraker-1", "Synthetic")
    )
    client = _Client()
    _server, _objects, _snapshot, _stream, inventory, history = await manager._discover(client, live)

    assert inventory is not None and inventory[0].path == "benchy.gcode"
    assert history == ()
    assert client.requests[-2] == (
        "http://192.168.1.44:7125/server/files/list",
        {"params": {"root": "gcodes"}, "allow_redirects": False},
    )
    assert client.requests[-1] == (
        "http://192.168.1.44:7125/server/gcode_store",
        {"params": {"count": 50}, "allow_redirects": False},
    )


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
    await manager._serve(
        socket,
        live,
        "fixture",
        {
            "webhooks": ["state"],
            "print_stats": ["state", "filename", "print_duration", "current_layer", "total_layer"],
            "extruder": ["temperature", "target"],
        },
    )
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
