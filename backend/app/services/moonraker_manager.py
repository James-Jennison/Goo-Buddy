"""Opt-in, closed Moonraker monitoring lifecycle.

Only explicitly enabled sources open a connection.  The manager derives fixed
Moonraker paths from validated private IPv4 configuration and can emit only
the enum-backed monitoring requests in :mod:`moonraker_read_only`.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import socket
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

import aiohttp

from backend.app.control.contract import PlatformControlCommand, control_operation_is_available
from backend.app.drivers.contract import ConnectionPhase, DriverKind, DriverObservation
from backend.app.drivers.moonraker import MoonrakerDriver
from backend.app.schemas.printer import canonical_rfc1918_ipv4, normalize_mainsail_camera_proxy_path
from backend.app.services.moonraker_control import request_for_control_operation
from backend.app.services.moonraker_read_only import (
    MoonrakerGcodeFile,
    MoonrakerReadOnlyMethod,
    parse_gcode_file_inventory,
    select_monitored_objects,
    serialize_read_only_request,
)

CONNECT_TIMEOUT_SECONDS = 8
REQUEST_TIMEOUT_SECONDS = 10
MAX_FRAME_BYTES = 128 * 1024
MAX_BACKOFF_SECONDS = 60
NO_VALID_INBOUND_SECONDS = 45
MAX_CAMERA_SNAPSHOT_BYTES = 5 * 1024 * 1024
MAX_MJPEG_HEADERS_BYTES = 32 * 1024
MAX_MJPEG_RESPONSE_BYTES = MAX_CAMERA_SNAPSHOT_BYTES + (2 * MAX_MJPEG_HEADERS_BYTES)
MJPEG_READ_CHUNK_BYTES = 16 * 1024


@dataclass
class _LiveMoonraker:
    source_id: int
    display_name: str
    private_ipv4: str
    port: int
    scheme: str
    api_key: str | None
    driver: MoonrakerDriver
    configuration_revision: int = 1
    camera_proxy_port: int | None = None
    camera_proxy_scheme: str | None = None
    camera_proxy_path: str | None = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None
    connected: bool = False
    reconnecting: bool = False
    error: str | None = None
    server: dict[str, object] | None = None
    last_liveness: float | None = None
    client: aiohttp.ClientSession | None = None
    control_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    camera_snapshot_path: str | None = None
    camera_stream_path: str | None = None
    camera_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    gcode_files: tuple[MoonrakerGcodeFile, ...] | None = None


class MoonrakerManager:
    def __init__(self) -> None:
        self._sources: dict[int, _LiveMoonraker] = {}

    async def enable(
        self,
        source_id: int,
        display_name: str,
        private_ipv4: str,
        port: int,
        scheme: str,
        api_key: str | None,
        configuration_revision: int = 1,
        camera_proxy_port: int | None = None,
        camera_proxy_scheme: str | None = None,
        camera_proxy_path: str | None = None,
    ) -> None:
        private_ipv4 = canonical_rfc1918_ipv4(private_ipv4)
        if type(port) is not int or isinstance(port, bool) or not 1 <= port <= 65535 or scheme not in {"http", "https"}:
            raise ValueError("invalid Moonraker transport")
        if type(configuration_revision) is not int or configuration_revision < 1:
            raise ValueError("invalid platform control configuration revision")
        proxy_values = (camera_proxy_port, camera_proxy_scheme, camera_proxy_path)
        if any(value is not None for value in proxy_values):
            if (
                any(value is None for value in proxy_values)
                or type(camera_proxy_port) is not int
                or isinstance(camera_proxy_port, bool)
                or not 1 <= camera_proxy_port <= 65535
                or camera_proxy_scheme not in {"http", "https"}
            ):
                raise ValueError("invalid Mainsail camera proxy")
            camera_proxy_path = normalize_mainsail_camera_proxy_path(camera_proxy_path)
        await self.disable(source_id)
        live = _LiveMoonraker(
            source_id,
            display_name,
            private_ipv4,
            port,
            scheme,
            api_key,
            MoonrakerDriver(f"moonraker-{source_id}", display_name),
            configuration_revision=configuration_revision,
            camera_proxy_port=camera_proxy_port,
            camera_proxy_scheme=camera_proxy_scheme,
            camera_proxy_path=camera_proxy_path,
        )
        self._sources[source_id] = live
        live.task = asyncio.create_task(self._run(live), name=f"moonraker-{source_id}")

    async def disable(self, source_id: int) -> None:
        live = self._sources.pop(source_id, None)
        if live is None:
            return
        live.stop.set()
        if live.task and live.task is not asyncio.current_task():
            live.task.cancel()
            try:
                await live.task
            except asyncio.CancelledError:
                pass

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.disable(source_id) for source_id in list(self._sources)), return_exceptions=True)

    def observation(self, source_id: int, now: datetime | None = None) -> DriverObservation:
        live = self._sources.get(source_id)
        if live is None:
            return DriverObservation(ConnectionPhase.DISCONNECTED, frozenset())
        observed = live.driver.observation(now or datetime.now(timezone.utc))
        if live.error in {"invalid_response", "no_supported_objects", "oversized_frame"}:
            return DriverObservation(
                ConnectionPhase.INVALID,
                observed.capabilities,
                retained=observed.retained,
                error=live.error,
                session_id=observed.session_id,
            )
        if live.connected and observed.phase is ConnectionPhase.WAITING:
            return observed
        if live.reconnecting and observed.phase is ConnectionPhase.DISCONNECTED:
            return DriverObservation(
                ConnectionPhase.RECONNECTING, observed.capabilities, retained=observed.retained, error=live.error
            )
        if live.error and observed.phase not in {ConnectionPhase.READY, ConnectionPhase.STALE}:
            return DriverObservation(
                observed.phase,
                observed.capabilities,
                current=observed.current,
                retained=observed.retained,
                error=live.error,
                session_id=observed.session_id,
            )
        return observed

    def gcode_inventory(self, source_id: int) -> tuple[MoonrakerGcodeFile, ...] | None:
        """Return the fixed-root inventory only while its observation is fresh.

        This method accepts no path, filename, filter, or root; the only
        request that populates it is the fixed ``gcodes`` listing.
        """

        live = self._sources.get(source_id)
        if live is None or self.observation(source_id).phase is not ConnectionPhase.READY:
            return None
        return live.gcode_files

    async def dispatch_command(self, command: object) -> bool:
        """Send one bodyless, fixed Moonraker job-control endpoint request.

        The operation-only command contract and the private adapter together
        leave no call path for JSON-RPC methods, G-code, HTTP paths, or bodies.
        """

        if type(command) is not PlatformControlCommand or command.driver is not DriverKind.MOONRAKER:
            raise ValueError("unsupported Moonraker control command")
        live = self._sources.get(command.source_id)
        if live is None or command.configuration_revision != live.configuration_revision:
            return False
        observation = self.observation(command.source_id)
        if not control_operation_is_available(command.operation, observation):
            return False
        if live.client is None or live.stop.is_set():
            return False
        request = request_for_control_operation(command.operation)
        async with live.control_lock:
            if live.client is None or live.stop.is_set():
                return False
            async with live.client.post(f"{self._base_url(live)}{request.path}", allow_redirects=False) as response:
                return 200 <= response.status < 300

    async def camera_snapshot(self, source_id: int) -> bytes | None:
        """Fetch one bounded JPEG through a discovered or owner-configured path.

        URLs from Moonraker are never returned to callers. Only an enabled
        webcam's validated relative snapshot path is used with the already
        configured private Moonraker origin and its protected API-key header.
        An explicit Mainsail proxy is still bound to the same private address,
        and uses a separate unauthenticated client so the Moonraker API key is
        never forwarded to it.
        """
        live = self._sources.get(source_id)
        if live is None or live.client is None or live.stop.is_set():
            return None
        if self.observation(source_id).phase is not ConnectionPhase.READY:
            return None
        async with live.camera_lock:
            if live.client is None or live.stop.is_set():
                return None
            if live.camera_snapshot_path is not None:
                async with live.client.get(
                    f"{self._base_url(live)}{live.camera_snapshot_path}", allow_redirects=False
                ) as response:
                    frame = await self._camera_frame_from_response(response)
                    if frame is not None:
                        return frame
            if live.camera_stream_path is not None:
                async with live.client.get(
                    f"{self._base_url(live)}{live.camera_stream_path}", allow_redirects=False
                ) as response:
                    frame = await self._camera_frame_from_response(response)
                    if frame is not None:
                        return frame
            if live.camera_proxy_path is None:
                return None
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS, sock_connect=CONNECT_TIMEOUT_SECONDS)
            connector = aiohttp.TCPConnector(family=socket.AF_INET, use_dns_cache=False)
            async with (
                aiohttp.ClientSession(timeout=timeout, connector=connector) as proxy_client,
                proxy_client.get(
                    f"{self._camera_proxy_base_url(live)}{live.camera_proxy_path}", allow_redirects=False
                ) as response,
            ):
                return await self._camera_frame_from_response(response)

    async def _camera_frame_from_response(self, response: aiohttp.ClientResponse) -> bytes | None:
        """Return one JPEG without retaining any camera response or URL."""
        if response.status != 200:
            return None
        if response.content_type == "image/jpeg":
            payload = await response.content.read(MAX_CAMERA_SNAPSHOT_BYTES + 1)
            return (
                payload if 0 < len(payload) <= MAX_CAMERA_SNAPSHOT_BYTES and payload.startswith(b"\xff\xd8") else None
            )
        if response.content_type != "multipart/x-mixed-replace":
            return None
        boundary = self._multipart_boundary(response.headers.get("Content-Type"))
        return await self._first_mjpeg_frame(response.content, boundary) if boundary else None

    @staticmethod
    def _multipart_boundary(content_type: str | None) -> bytes | None:
        """Accept only a short, printable multipart boundary."""
        if not isinstance(content_type, str):
            return None
        match = re.search(r'(?:^|;)\s*boundary=(?:"([^"]+)"|([^;\s]+))', content_type, re.IGNORECASE)
        value = (match.group(1) or match.group(2)) if match else None
        if value is None or not re.fullmatch(r"[A-Za-z0-9'()+_,./:=?-]{1,70}", value):
            return None
        return value.encode("ascii")

    @staticmethod
    def _extract_mjpeg_frame(payload: bytes, boundary: bytes) -> bytes | None:
        """Extract exactly one bounded JPEG part from a multipart response."""
        marker = b"--" + boundary
        marker_at = payload.find(marker)
        if marker_at < 0:
            return None
        header_start = marker_at + len(marker)
        if payload[header_start : header_start + 2] == b"\r\n":
            header_start += 2
        header_end = payload.find(b"\r\n\r\n", header_start)
        if header_end < 0 or header_end - header_start > MAX_MJPEG_HEADERS_BYTES:
            return None
        headers: dict[bytes, bytes] = {}
        for line in payload[header_start:header_end].split(b"\r\n"):
            name, separator, value = line.partition(b":")
            if not separator:
                return None
            headers[name.strip().lower()] = value.strip()
        if headers.get(b"content-type", b"").split(b";", 1)[0].lower() != b"image/jpeg":
            return None
        frame_start = header_end + 4
        declared_length = headers.get(b"content-length")
        if declared_length is not None:
            if not declared_length.isdigit():
                return None
            length = int(declared_length)
            if not 0 < length <= MAX_CAMERA_SNAPSHOT_BYTES or len(payload) < frame_start + length:
                return None
            frame = payload[frame_start : frame_start + length]
        else:
            next_marker = payload.find(b"\r\n" + marker, frame_start)
            if next_marker < 0:
                return None
            frame = payload[frame_start:next_marker]
            if not 0 < len(frame) <= MAX_CAMERA_SNAPSHOT_BYTES:
                return None
        return frame if frame.startswith(b"\xff\xd8") else None

    async def _first_mjpeg_frame(self, content: aiohttp.StreamReader, boundary: bytes) -> bytes | None:
        """Read only enough of a trusted same-origin stream to obtain one frame."""
        payload = bytearray()
        while len(payload) < MAX_MJPEG_RESPONSE_BYTES:
            chunk = await content.read(min(MJPEG_READ_CHUNK_BYTES, MAX_MJPEG_RESPONSE_BYTES - len(payload)))
            if not chunk:
                return self._extract_mjpeg_frame(bytes(payload), boundary)
            payload.extend(chunk)
            frame = self._extract_mjpeg_frame(bytes(payload), boundary)
            if frame is not None:
                return frame
        return None

    @staticmethod
    def _base_url(live: _LiveMoonraker) -> str:
        return f"{live.scheme}://{live.private_ipv4}:{live.port}"

    @staticmethod
    def _camera_proxy_base_url(live: _LiveMoonraker) -> str:
        if live.camera_proxy_scheme is None or live.camera_proxy_port is None:
            raise ValueError("Mainsail camera proxy is not configured")
        return f"{live.camera_proxy_scheme}://{live.private_ipv4}:{live.camera_proxy_port}"

    @staticmethod
    def _websocket_url(live: _LiveMoonraker) -> str:
        ws_scheme = "wss" if live.scheme == "https" else "ws"
        return f"{ws_scheme}://{live.private_ipv4}:{live.port}/websocket"

    @staticmethod
    def _headers(live: _LiveMoonraker) -> dict[str, str]:
        return {"X-Api-Key": live.api_key} if live.api_key else {}

    async def _run(self, live: _LiveMoonraker) -> None:
        attempt = 0
        while not live.stop.is_set():
            session_id = uuid.uuid4().hex
            live.driver.start_session(session_id)
            live.connected, live.reconnecting, live.last_liveness = False, attempt > 0, None
            live.gcode_files = None
            live.driver.set_files_available(False)
            try:
                timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS, sock_connect=CONNECT_TIMEOUT_SECONDS)
                connector = aiohttp.TCPConnector(family=socket.AF_INET, use_dns_cache=False)
                async with aiohttp.ClientSession(
                    timeout=timeout, connector=connector, headers=self._headers(live)
                ) as client:
                    live.client = client
                    try:
                        (
                            live.server,
                            available,
                            live.camera_snapshot_path,
                            live.camera_stream_path,
                            live.gcode_files,
                        ) = await self._discover(client, live)
                        live.driver.set_camera_available(
                            live.camera_snapshot_path is not None
                            or live.camera_stream_path is not None
                            or live.camera_proxy_path is not None
                        )
                        live.driver.set_files_available(live.gcode_files is not None)
                        objects = select_monitored_objects(available)
                        if not objects:
                            live.error = "no_supported_objects"
                            return
                        async with client.ws_connect(
                            self._websocket_url(live), autoping=True, heartbeat=None, max_msg_size=MAX_FRAME_BYTES
                        ) as websocket:
                            live.connected, live.reconnecting, live.error = True, False, None
                            await self._serve(websocket, live, session_id, objects)
                    finally:
                        if live.client is client:
                            live.client = None
            except asyncio.CancelledError:
                live.driver.disconnect(session_id)
                raise
            except aiohttp.ClientResponseError as exc:
                live.error = "unauthorized" if exc.status in {401, 403} else "http_failed"
            except asyncio.TimeoutError:
                live.error = "connection_timeout"
            except aiohttp.ClientError:
                live.error = "connection_failed"
            except ValueError:
                live.error = "invalid_response"
            except Exception:
                live.error = "connection_failed"
            finally:
                live.connected = False
                live.driver.disconnect(session_id)
            if live.stop.is_set():
                break
            attempt += 1
            live.reconnecting = True
            try:
                await asyncio.wait_for(
                    live.stop.wait(), timeout=min(MAX_BACKOFF_SECONDS, 2 ** min(attempt, 6)) + random.uniform(0, 0.5)
                )
            except asyncio.TimeoutError:
                continue

    async def _discover(
        self, client: aiohttp.ClientSession, live: _LiveMoonraker
    ) -> tuple[dict[str, object], list[str], str | None, str | None, tuple[MoonrakerGcodeFile, ...] | None]:
        """Use fixed HTTP GET endpoints; redirects are always rejected."""
        async with client.get(f"{self._base_url(live)}/server/info", allow_redirects=False) as response:
            if response.status in {401, 403}:
                raise aiohttp.ClientResponseError(response.request_info, response.history, status=response.status)
            response.raise_for_status()
            server_payload = await response.json(content_type=None)
        async with client.get(f"{self._base_url(live)}/printer/objects/list", allow_redirects=False) as response:
            if response.status in {401, 403}:
                raise aiohttp.ClientResponseError(response.request_info, response.history, status=response.status)
            response.raise_for_status()
            objects_payload = await response.json(content_type=None)
        async with client.get(f"{self._base_url(live)}/server/webcams/list", allow_redirects=False) as response:
            webcams_payload = await response.json(content_type=None) if response.status == 200 else None
        async with client.get(
            f"{self._base_url(live)}/server/files/list", params={"root": "gcodes"}, allow_redirects=False
        ) as response:
            files_payload = await response.json(content_type=None) if response.status == 200 else None
        if not isinstance(server_payload, dict) or not isinstance(server_payload.get("result"), dict):
            raise ValueError("invalid server response")
        result = objects_payload.get("result") if isinstance(objects_payload, dict) else None
        available = result.get("objects") if isinstance(result, dict) else None
        if not isinstance(available, list):
            raise ValueError("invalid object response")
        return (
            server_payload["result"],
            available,
            self._validated_camera_path(webcams_payload, "snapshot_url"),
            self._validated_camera_path(webcams_payload, "stream_url"),
            self._validated_gcode_inventory(files_payload),
        )

    @staticmethod
    def _validated_gcode_inventory(payload: object) -> tuple[MoonrakerGcodeFile, ...] | None:
        """Treat an absent or malformed optional inventory as unavailable."""

        if payload is None:
            return None
        try:
            return parse_gcode_file_inventory(payload)
        except ValueError:
            return None

    @staticmethod
    def _validated_camera_path(payload: object, field: str) -> str | None:
        """Select one enabled, same-origin camera path without accepting a URL authority."""
        if field not in {"snapshot_url", "stream_url"}:
            raise ValueError("unsupported webcam field")
        result = payload.get("result") if isinstance(payload, dict) else None
        webcams = result.get("webcams") if isinstance(result, dict) else None
        if not isinstance(webcams, list):
            return None
        for webcam in webcams:
            if not isinstance(webcam, dict) or webcam.get("enabled") is not True:
                continue
            candidate = webcam.get(field)
            if not isinstance(candidate, str) or len(candidate) > 512:
                continue
            parsed = urlsplit(candidate)
            if (
                parsed.scheme
                or parsed.netloc
                or parsed.fragment
                or not parsed.path.startswith("/")
                or parsed.path.startswith("//")
            ):
                continue
            # Preserve only ordinary absolute paths.  Percent-encoded paths can
            # conceal separators or traversal segments after a proxy decodes
            # them, so they are deliberately outside this first closed surface.
            if "%" in parsed.path or any(segment in {"", ".", ".."} for segment in parsed.path.split("/")[1:-1]):
                continue
            return parsed.path + (f"?{parsed.query}" if parsed.query else "")
        return None

    @staticmethod
    def _validated_snapshot_path(payload: object) -> str | None:
        """Backward-compatible narrow helper for snapshot-only callers and tests."""
        return MoonrakerManager._validated_camera_path(payload, "snapshot_url")

    async def _serve(
        self,
        websocket: aiohttp.ClientWebSocketResponse,
        live: _LiveMoonraker,
        session_id: str,
        objects: dict[str, list[str] | None],
    ) -> None:
        # This fixed sequence is the complete outbound WebSocket vocabulary.
        query = serialize_read_only_request(MoonrakerReadOnlyMethod.OBJECTS_QUERY, objects)
        subscribe = serialize_read_only_request(MoonrakerReadOnlyMethod.OBJECTS_SUBSCRIBE, objects)
        # IDs are generated locally by the closed serializer, retained only for
        # this session, and used to reject unsolicited JSON-RPC results.
        expected_ids = {json.loads(query)["id"], json.loads(subscribe)["id"]}
        await websocket.send_str(query)
        await websocket.send_str(subscribe)
        status: dict[str, object] = {}
        while not live.stop.is_set():
            remaining = (
                NO_VALID_INBOUND_SECONDS
                if live.last_liveness is None
                else max(0, NO_VALID_INBOUND_SECONDS - (time.monotonic() - live.last_liveness))
            )
            if remaining <= 0:
                live.error = "inbound_timeout"
                await websocket.close()
                return
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=remaining)
            except asyncio.TimeoutError:
                live.error = "inbound_timeout"
                await websocket.close()
                return
            if message.type is aiohttp.WSMsgType.TEXT:
                raw = message.data
                if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
                    live.error = "oversized_frame"
                    return
                update = self._validated_status_message(raw, objects, expected_ids)
                if update is None:
                    continue
                status.update(update)
                if live.server is not None and live.driver.observe(
                    session_id, status, live.server, datetime.now(timezone.utc)
                ):
                    live.last_liveness = time.monotonic()
            elif message.type in {aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING}:
                return
            elif message.type is aiohttp.WSMsgType.ERROR:
                live.error = "connection_closed"
                return

    @staticmethod
    def _validated_status_message(
        raw: str, objects: dict[str, list[str] | None], expected_ids: set[int] | None = None
    ) -> dict[str, object] | None:
        """Accept only status result/notifications for the local fixed object set."""
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(message, dict):
            return None
        if message.get("method") == "notify_status_update":
            params = message.get("params")
            candidate = params[0] if isinstance(params, list) and params else None
        else:
            if type(message.get("id")) is not int or (expected_ids is not None and message["id"] not in expected_ids):
                return None
            result = message.get("result")
            candidate = result.get("status") if isinstance(result, dict) else None
        if not isinstance(candidate, dict) or set(candidate) - set(objects):
            return None
        return candidate


moonraker_manager = MoonrakerManager()
