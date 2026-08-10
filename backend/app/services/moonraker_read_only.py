"""Closed Moonraker monitoring vocabulary.

There is deliberately no generic JSON-RPC builder. The manager can serialize
only the two documented, non-mutating WebSocket methods below, with arguments
created from a fixed object-name allowlist. Object discovery is a separately
fixed HTTP GET path, never a JSON-RPC method.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final


class MoonrakerReadOnlyMethod(str, Enum):
    OBJECTS_QUERY = "printer.objects.query"
    OBJECTS_SUBSCRIBE = "printer.objects.subscribe"


# Object names and fields are selected locally; config-defined macros,
# arbitrary object names, and unreviewed fields are never reflected into a
# request.  M3 adds only active tool and homed-axis telemetry from ``toolhead``.
MONITORED_OBJECT_FIELDS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "webhooks": ("state",),
        "print_stats": ("state", "filename", "print_duration", "current_layer", "total_layer"),
        "virtual_sdcard": ("progress",),
        "toolhead": ("extruder", "homed_axes"),
        "extruder": ("temperature", "target"),
        "heater_bed": ("temperature", "target"),
        "chamber": ("temperature", "target"),
    }
)
MONITORED_OBJECTS: Final[frozenset[str]] = frozenset(MONITORED_OBJECT_FIELDS)
_request_ids = itertools.count(1)
MAX_GCODE_FILES: Final = 100
MAX_GCODE_PATH_LENGTH: Final = 240
MAX_GCODE_FILE_BYTES: Final = 1 << 40
MAX_GCODE_METADATA_TEXT_LENGTH: Final = 160
MAX_GCODE_METADATA_NUMBER: Final = 1 << 40
MAX_GCODE_THUMBNAILS: Final = 16
MAX_GCODE_THUMBNAIL_PATH_LENGTH: Final = 320
MAX_GCODE_THUMBNAIL_DIMENSION: Final = 4096
MAX_GCODE_THUMBNAIL_BYTES: Final = 1 * 1024 * 1024
CONSOLE_HISTORY_COUNT: Final = 50
MAX_CONSOLE_MESSAGE_LENGTH: Final = 500


@dataclass(frozen=True)
class MoonrakerGcodeFile:
    """A bounded, display-only item from Moonraker's fixed ``gcodes`` root."""

    path: str
    size: int
    modified: float


@dataclass(frozen=True)
class MoonrakerGcodeMetadata:
    """Small, display-only projection of a validated G-code metadata record."""

    path: str
    slicer: str | None
    slicer_version: str | None
    estimated_time: float | None
    object_height: float | None
    filament_weight_total: float | None
    layer_height: float | None
    nozzle_diameter: float | None
    thumbnail: MoonrakerGcodeThumbnail | None = None


@dataclass(frozen=True)
class MoonrakerGcodeThumbnail:
    """A server-only, fixed-root thumbnail reference from G-code metadata."""

    path: str
    width: int
    height: int
    size: int


@dataclass(frozen=True)
class MoonrakerConsoleEntry:
    """A bounded, display-only entry from Moonraker's cached G-code store."""

    message: str
    timestamp: float
    kind: str


def parse_gcode_file_inventory(payload: object) -> tuple[MoonrakerGcodeFile, ...]:
    """Validate the documented ``/server/files/list?root=gcodes`` response.

    This deliberately models only a small, display-safe inventory. The result
    cannot be supplied back to Moonraker as a filename or path, so it creates
    no download, upload, deletion, or G-code execution surface.
    """

    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, list) or len(result) > MAX_GCODE_FILES:
        raise ValueError("invalid Moonraker gcode inventory")
    files: list[MoonrakerGcodeFile] = []
    for item in result:
        if not isinstance(item, dict):
            raise ValueError("invalid Moonraker gcode inventory")
        path, size, modified = item.get("path"), item.get("size"), item.get("modified")
        if (
            not isinstance(path, str)
            or not path
            or len(path) > MAX_GCODE_PATH_LENGTH
            or "\\" in path
            or path.startswith("/")
            or any(part in {"", ".", ".."} for part in path.split("/"))
            or type(size) is not int
            or not 0 <= size <= MAX_GCODE_FILE_BYTES
            or not isinstance(modified, (int, float))
            or isinstance(modified, bool)
            or not math.isfinite(modified)
            or modified < 0
        ):
            raise ValueError("invalid Moonraker gcode inventory")
        files.append(MoonrakerGcodeFile(path=path, size=size, modified=float(modified)))
    return tuple(files)


def parse_gcode_metadata(payload: object, path: object) -> MoonrakerGcodeMetadata:
    """Validate a metadata response for one current fixed-root inventory entry.

    ``path`` is never a transport parameter supplied to this parser: the
    manager first proves it belongs to its bounded cached inventory, then uses
    it for Moonraker's documented metadata request. Unknown response fields
    are intentionally discarded.
    """

    if (
        not isinstance(path, str)
        or not path
        or len(path) > MAX_GCODE_PATH_LENGTH
        or "\\" in path
        or path.startswith("/")
        or any(part in {"", ".", ".."} for part in path.split("/"))
    ):
        raise ValueError("invalid Moonraker gcode metadata")
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict) or result.get("filename") != path:
        raise ValueError("invalid Moonraker gcode metadata")

    def text(name: str) -> str | None:
        value = result.get(name)
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > MAX_GCODE_METADATA_TEXT_LENGTH or "\x00" in value:
            raise ValueError("invalid Moonraker gcode metadata")
        return value

    def number(name: str) -> float | None:
        value = result.get(name)
        if value is None:
            return None
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ValueError("invalid Moonraker gcode metadata")
        value = float(value)
        if not 0 <= value <= MAX_GCODE_METADATA_NUMBER:
            raise ValueError("invalid Moonraker gcode metadata")
        return value

    thumbnail = _select_gcode_thumbnail(result, path)

    return MoonrakerGcodeMetadata(
        path=path,
        slicer=text("slicer"),
        slicer_version=text("slicer_version"),
        estimated_time=number("estimated_time"),
        object_height=number("object_height"),
        filament_weight_total=number("filament_weight_total"),
        layer_height=number("layer_height"),
        nozzle_diameter=number("nozzle_diameter"),
        thumbnail=thumbnail,
    )


def _select_gcode_thumbnail(result: dict[str, object], gcode_path: str) -> MoonrakerGcodeThumbnail | None:
    """Project one safe thumbnail reference without exposing its path to clients.

    Moonraker documents ``relative_path`` as relative to the G-code file's
    directory.  The joined path must therefore remain a normal child of the
    fixed ``gcodes`` root; parent traversal and URL-like path syntax are not
    valid thumbnail references for Goo Buddy.
    """

    thumbnails = result.get("thumbnails")
    if thumbnails is None:
        return None
    if not isinstance(thumbnails, list) or len(thumbnails) > MAX_GCODE_THUMBNAILS:
        raise ValueError("invalid Moonraker gcode metadata")

    parent_parts = gcode_path.split("/")[:-1]
    valid: list[MoonrakerGcodeThumbnail] = []
    for item in thumbnails:
        if not isinstance(item, dict):
            raise ValueError("invalid Moonraker gcode metadata")
        relative_path, width, height, size = (
            item.get("relative_path"),
            item.get("width"),
            item.get("height"),
            item.get("size"),
        )
        if (
            not isinstance(relative_path, str)
            or not relative_path
            or len(relative_path) > MAX_GCODE_THUMBNAIL_PATH_LENGTH
            or "\\" in relative_path
            or relative_path.startswith("/")
            or any(part in {"", ".", ".."} for part in relative_path.split("/"))
            or type(width) is not int
            or type(height) is not int
            or type(size) is not int
            or not 1 <= width <= MAX_GCODE_THUMBNAIL_DIMENSION
            or not 1 <= height <= MAX_GCODE_THUMBNAIL_DIMENSION
            or not 1 <= size <= MAX_GCODE_THUMBNAIL_BYTES
        ):
            raise ValueError("invalid Moonraker gcode metadata")
        valid.append(MoonrakerGcodeThumbnail("/".join((*parent_parts, *relative_path.split("/"))), width, height, size))

    # The largest declared resolution is the most useful compact preview. A
    # deterministic tie-break prevents a remote array order from becoming UI
    # behavior while still keeping every path internal to this process.
    return max(valid, key=lambda item: (item.width * item.height, item.width, item.height, item.path), default=None)


def parse_console_history(payload: object) -> tuple[MoonrakerConsoleEntry, ...]:
    """Validate the fixed-size cached G-code history response.

    Goo Buddy neither sends nor replays these strings. They remain bounded
    display data retrieved solely from the documented read-only cache.
    """

    result = payload.get("result") if isinstance(payload, dict) else None
    history = result.get("gcode_store") if isinstance(result, dict) else None
    if not isinstance(history, list) or len(history) > CONSOLE_HISTORY_COUNT:
        raise ValueError("invalid Moonraker console history")
    entries: list[MoonrakerConsoleEntry] = []
    for item in history:
        if not isinstance(item, dict):
            raise ValueError("invalid Moonraker console history")
        message, timestamp, kind = item.get("message"), item.get("time"), item.get("type")
        if (
            not isinstance(message, str)
            or not message
            or len(message) > MAX_CONSOLE_MESSAGE_LENGTH
            or "\x00" in message
            or not isinstance(timestamp, (int, float))
            or isinstance(timestamp, bool)
            or not math.isfinite(timestamp)
            or timestamp < 0
            or kind not in {"command", "response"}
        ):
            raise ValueError("invalid Moonraker console history")
        entries.append(MoonrakerConsoleEntry(message=message, timestamp=float(timestamp), kind=kind))
    return tuple(entries)


def select_monitored_objects(available: object) -> dict[str, list[str]]:
    """Intersect a server-provided list with the fixed monitorable fields."""

    if not isinstance(available, list) or not all(isinstance(item, str) for item in available):
        raise ValueError("invalid object list")
    return {name: list(MONITORED_OBJECT_FIELDS[name]) for name in sorted(MONITORED_OBJECTS.intersection(available))}


def serialize_read_only_request(method: object, objects: object | None = None) -> str:
    """Serialize one allowlisted JSON-RPC request, rejecting all lookalikes."""

    if type(method) is not MoonrakerReadOnlyMethod:
        raise ValueError("unsupported Moonraker read-only method")
    if not isinstance(objects, dict) or set(objects) - MONITORED_OBJECTS:
        raise ValueError("invalid monitored object selection")
    if any(value != list(MONITORED_OBJECT_FIELDS[name]) for name, value in objects.items()):
        raise ValueError("invalid monitored object selection")
    params: dict[str, object] = {"objects": objects}
    return json.dumps(
        {"jsonrpc": "2.0", "method": method.value, "params": params, "id": next(_request_ids)},
        separators=(",", ":"),
        ensure_ascii=True,
    )
