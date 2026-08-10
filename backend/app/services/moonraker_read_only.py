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
from dataclasses import dataclass
from enum import Enum
from typing import Final


class MoonrakerReadOnlyMethod(str, Enum):
    OBJECTS_QUERY = "printer.objects.query"
    OBJECTS_SUBSCRIBE = "printer.objects.subscribe"


# Object names are selected locally; config-defined macros and arbitrary
# object names are never reflected into a request.
MONITORED_OBJECTS: Final[frozenset[str]] = frozenset(
    {"webhooks", "print_stats", "virtual_sdcard", "display_status", "toolhead", "extruder", "heater_bed", "chamber"}
)
_request_ids = itertools.count(1)
MAX_GCODE_FILES: Final = 100
MAX_GCODE_PATH_LENGTH: Final = 240
MAX_GCODE_FILE_BYTES: Final = 1 << 40


@dataclass(frozen=True)
class MoonrakerGcodeFile:
    """A bounded, display-only item from Moonraker's fixed ``gcodes`` root."""

    path: str
    size: int
    modified: float


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


def select_monitored_objects(available: object) -> dict[str, list[str] | None]:
    """Intersect a server-provided list with the fixed monitorable objects."""

    if not isinstance(available, list) or not all(isinstance(item, str) for item in available):
        raise ValueError("invalid object list")
    return dict.fromkeys(sorted(MONITORED_OBJECTS.intersection(available)))


def serialize_read_only_request(method: object, objects: object | None = None) -> str:
    """Serialize one allowlisted JSON-RPC request, rejecting all lookalikes."""

    if type(method) is not MoonrakerReadOnlyMethod:
        raise ValueError("unsupported Moonraker read-only method")
    if not isinstance(objects, dict) or set(objects) - MONITORED_OBJECTS:
        raise ValueError("invalid monitored object selection")
    if not all(value is None or value == [] for value in objects.values()):
        raise ValueError("invalid monitored object selection")
    params: dict[str, object] = {"objects": objects}
    return json.dumps(
        {"jsonrpc": "2.0", "method": method.value, "params": params, "id": next(_request_ids)},
        separators=(",", ":"),
        ensure_ascii=True,
    )
