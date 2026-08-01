"""Closed Moonraker monitoring vocabulary.

There is deliberately no generic JSON-RPC builder. The manager can serialize
only the two documented, non-mutating WebSocket methods below, with arguments
created from a fixed object-name allowlist. Object discovery is a separately
fixed HTTP GET path, never a JSON-RPC method.
"""

from __future__ import annotations

import itertools
import json
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
