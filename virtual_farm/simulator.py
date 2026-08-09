"""Deterministic localhost-only virtual farm; never imported by app startup."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import re
from collections.abc import Awaitable, Callable
from typing import Protocol

from aiohttp import web

FIXTURE_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAX/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABBQJ//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAwEBPwF//8QAFBEBAAAAAAAAAAAAAAAAAAAAAP/aAAgBAgEBPwF//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQAGPwJ//8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPyF//9k="
)
VIDEO_DEVICE_PATTERN = re.compile(r"^/dev/video(0|[1-9][0-9]?)$")
CAPTURE_TIMEOUT_SECONDS = 5
CAMERA_ENABLED = web.AppKey("camera_enabled", bool)


class CameraUnavailable(RuntimeError):
    """The explicitly configured virtual-farm camera cannot provide a frame."""


class FrameSource(Protocol):
    """A local camera source used only by the virtual-farm simulator."""

    name: str

    async def frame(self) -> bytes: ...


CAMERA_SOURCE = web.AppKey("camera_source", FrameSource | None)


class FixtureFrameSource:
    """Deterministic source used by the automated virtual-farm profile."""

    name = "fixture"

    async def frame(self) -> bytes:
        return FIXTURE_JPEG


async def capture_v4l2_frame(device: str) -> bytes:
    """Capture one JPEG from an explicitly mapped V4L2 device with ffmpeg.

    No device probing occurs here: the caller supplies one already validated
    ``/dev/videoN`` path, and Compose maps only that same path into the USB
    profile container. A fresh short-lived capture per request makes a lost
    device or frame visible as an unavailable camera rather than stale media.
    """
    if VIDEO_DEVICE_PATTERN.fullmatch(device) is None:
        raise CameraUnavailable("invalid V4L2 device")

    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "v4l2",
            "-i",
            device,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        payload, _stderr = await asyncio.wait_for(process.communicate(), timeout=CAPTURE_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        raise CameraUnavailable("V4L2 capture timed out") from exc
    except asyncio.CancelledError:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        raise
    except (FileNotFoundError, OSError) as exc:
        # Includes missing ffmpeg, device permissions, unavailable/busy device,
        # and capture-start failures. Do not expose host error details in HTTP.
        raise CameraUnavailable("V4L2 capture could not start") from exc

    if process.returncode != 0:
        raise CameraUnavailable("V4L2 capture failed")
    if not payload.startswith(b"\xff\xd8"):
        raise CameraUnavailable("V4L2 returned no JPEG frame")
    return payload


class V4L2FrameSource:
    """Frame source for manual USB-webcam validation only."""

    name = "v4l2"

    def __init__(
        self,
        device: str,
        capture: Callable[[str], Awaitable[bytes]] = capture_v4l2_frame,
    ) -> None:
        self._device = device
        self._capture = capture

    async def frame(self) -> bytes:
        return await self._capture(self._device)


async def info(_: web.Request) -> web.Response:
    return web.json_response({"result": {"klippy_state": "ready", "software_version": "virtual-farm-v1"}})


async def objects(_: web.Request) -> web.Response:
    return web.json_response({"result": {"objects": ["webhooks", "extruder", "heater_bed", "print_stats"]}})


async def webcams(request: web.Request) -> web.Response:
    cameras = (
        []
        if not request.app[CAMERA_ENABLED]
        else [
            {
                "enabled": True,
                "name": "virtual-farm-camera",
                "location": "virtual-farm simulated source",
                "snapshot_url": "/camera/snapshot",
                "stream_url": "/camera/stream",
            }
        ]
    )
    return web.json_response({"result": {"webcams": cameras}})


async def camera_frame(request: web.Request) -> web.Response:
    if not request.app[CAMERA_ENABLED]:
        raise web.HTTPServiceUnavailable(reason="virtual-farm camera disabled")
    source = request.app[CAMERA_SOURCE]
    assert source is not None
    try:
        payload = await source.frame()
    except CameraUnavailable:
        return web.json_response(
            {"error": "virtual-farm camera unavailable", "source": source.name},
            status=web.HTTPServiceUnavailable.status_code,
            headers={"X-Virtual-Farm-Camera": source.name},
        )
    return web.Response(
        body=payload,
        content_type="image/jpeg",
        headers={"X-Virtual-Farm-Camera": source.name},
    )


async def ws(request: web.Request) -> web.WebSocketResponse:
    socket = web.WebSocketResponse()
    await socket.prepare(request)
    async for message in socket:
        if message.type == web.WSMsgType.TEXT:
            payload = json.loads(message.data)
            if payload.get("method") not in {"printer.objects.query", "printer.objects.subscribe"}:
                await socket.close(code=1008)
                break
            await socket.send_json(
                {
                    "id": payload.get("id"),
                    "result": {
                        "status": {
                            "webhooks": {"state": "ready"},
                            "extruder": {"temperature": 25.0},
                            "heater_bed": {"temperature": 25.0},
                            "print_stats": {"state": "standby"},
                        }
                    },
                }
            )
    return socket


def app(
    camera_mode: str = "off",
    camera_device: str | None = None,
    frame_source: FrameSource | None = None,
) -> web.Application:
    """Build the isolated Moonraker simulator with an explicit camera source."""
    result = web.Application()
    if camera_mode == "fixture":
        source = frame_source or FixtureFrameSource()
    elif camera_mode == "v4l2" and camera_device and VIDEO_DEVICE_PATTERN.fullmatch(camera_device):
        source = frame_source or V4L2FrameSource(camera_device)
    else:
        source = None
    result[CAMERA_ENABLED] = source is not None
    result[CAMERA_SOURCE] = source
    result.add_routes(
        [
            web.get("/server/info", info),
            web.get("/printer/objects/list", objects),
            web.get("/server/webcams/list", webcams),
            web.get("/camera/snapshot", camera_frame),
            web.get("/camera/stream", camera_frame),
            web.get("/websocket", ws),
        ]
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=17125)
    parser.add_argument("--camera-mode", choices=("off", "fixture", "v4l2"), default="off")
    parser.add_argument("--camera-device")
    args = parser.parse_args()
    if args.camera_mode == "v4l2" and args.camera_device is None:
        parser.error("--camera-device is required with --camera-mode v4l2")
    web.run_app(app(args.camera_mode, args.camera_device), host="127.0.0.1", port=args.port)
