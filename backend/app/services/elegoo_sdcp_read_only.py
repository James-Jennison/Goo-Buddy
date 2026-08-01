"""Closed SDCP v3 read-only message vocabulary.

This module intentionally has no public raw-message or arbitrary-command
builder.  Its only serializable WebSocket application messages are the
documented text heartbeat and the two non-mutating information commands.
"""

from __future__ import annotations

import json
import re
import time
import uuid
from enum import Enum


class ReadOnlyInformationOperation(Enum):
    """The complete, non-mutating SDCP request allowlist."""

    STATUS_REFRESH = 0
    ATTRIBUTES = 1


_MAINBOARD_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def validate_mainboard_id(value: object) -> str:
    """Accept a topic-safe MainboardID without ever returning it in errors."""

    if not isinstance(value, str) or not _MAINBOARD_ID.fullmatch(value):
        raise ValueError("invalid SDCP identity")
    return value


def serialize_heartbeat() -> str:
    """Return the exact documented, non-mutating liveness text."""

    return "ping"


def serialize_information_request(operation: object, mainboard_id: object) -> str:
    """Serialize exactly Cmd 0 or Cmd 1 immediately before transmission.

    ``operation`` must be one of the enum instances above.  Accepting an
    ``object`` at the boundary is deliberate: it lets this function reject
    integers, booleans, strings, and lookalikes rather than coercing them into
    a command number.
    """

    if type(operation) is not ReadOnlyInformationOperation:
        raise ValueError("unsupported read-only information operation")
    identity = validate_mainboard_id(mainboard_id)
    request_id = str(uuid.uuid4())
    envelope = {
        "Id": str(uuid.uuid4()),
        "Data": {
            "Cmd": operation.value,
            "Data": {},
            "RequestID": request_id,
            "MainboardID": identity,
            "TimeStamp": int(time.time()),
            "From": 0,
        },
        "Topic": f"sdcp/request/{identity}",
    }
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)


def mainboard_id_from_discovery(payload: object) -> str:
    """Extract only the identity from one unicast M99999 response in memory."""

    if not isinstance(payload, dict):
        raise ValueError("invalid SDCP identity response")
    data = payload.get("Data")
    if not isinstance(data, dict):
        raise ValueError("invalid SDCP identity response")
    return validate_mainboard_id(data.get("MainboardID"))
