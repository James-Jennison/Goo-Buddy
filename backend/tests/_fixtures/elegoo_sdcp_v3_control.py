"""Redacted deterministic peer for the closed SDCP v3 job controls.

The fixture deliberately models only the three request envelopes Goo Buddy may
emit.  It contains no endpoint, credential, printer identifier, or facility
data, and rejects a request with any additional payload shape.
"""

from __future__ import annotations

import json
import uuid
from types import MappingProxyType

from backend.app.control.contract import PlatformControlOperation

MAINBOARD_ID = "fixture-mainboard-01"

COMMAND_BY_OPERATION = MappingProxyType(
    {
        PlatformControlOperation.PAUSE_JOB: 129,
        PlatformControlOperation.CANCEL_JOB: 130,
        PlatformControlOperation.RESUME_JOB: 131,
    }
)
OPERATION_BY_COMMAND = MappingProxyType({command: operation for operation, command in COMMAND_BY_OPERATION.items()})


class StrictSdcpControlPeer:
    """In-memory peer that accepts exactly the documented control envelopes."""

    def __init__(self, mainboard_id: str = MAINBOARD_ID) -> None:
        self.mainboard_id = mainboard_id
        self.operations: list[PlatformControlOperation] = []

    async def send_str(self, payload: str) -> None:
        try:
            envelope = json.loads(payload)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AssertionError("SDCP control request must be JSON") from exc
        if not isinstance(envelope, dict) or set(envelope) != {"Id", "Data", "Topic"}:
            raise AssertionError("unexpected SDCP control envelope")
        if envelope["Topic"] != f"sdcp/request/{self.mainboard_id}":
            raise AssertionError("unexpected SDCP control topic")
        if not _is_uuid(envelope["Id"]):
            raise AssertionError("invalid SDCP control envelope id")
        data = envelope["Data"]
        if not isinstance(data, dict) or set(data) != {"Cmd", "Data", "RequestID", "MainboardID", "TimeStamp", "From"}:
            raise AssertionError("unexpected SDCP control data")
        if (
            data["Data"] != {}
            or data["MainboardID"] != self.mainboard_id
            or data["From"] != 0
            or type(data["TimeStamp"]) is not int
            or not _is_uuid(data["RequestID"])
        ):
            raise AssertionError("unexpected SDCP control payload")
        operation = OPERATION_BY_COMMAND.get(data["Cmd"])
        if operation is None:
            raise AssertionError("unsupported SDCP control command")
        self.operations.append(operation)


def _is_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False
