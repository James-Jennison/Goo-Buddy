"""Closed Elegoo SDCP v3 print-job control vocabulary.

This module contains the complete initial SDCP command map.  It deliberately
accepts only :class:`PlatformControlOperation`, never a caller-supplied command
number or payload, so higher layers cannot turn it into a raw SDCP tunnel.
"""

from __future__ import annotations

import json
import time
import uuid
from types import MappingProxyType

from backend.app.control.contract import PlatformControlOperation
from backend.app.services.elegoo_sdcp_read_only import validate_mainboard_id

# SDCP v3's documented print-job commands. The mapping is private and frozen
# so no API, configuration, or plugin can extend it at runtime.
_COMMAND_BY_OPERATION = MappingProxyType(
    {
        PlatformControlOperation.PAUSE_JOB: 129,
        PlatformControlOperation.CANCEL_JOB: 130,
        PlatformControlOperation.RESUME_JOB: 131,
    }
)


def serialize_control_request(operation: object, mainboard_id: object) -> str:
    """Serialize exactly one documented SDCP print-job control request.

    The serializer has no general ``cmd``, ``data``, or topic parameter. The
    manager that eventually dispatches it therefore has one narrow outbound
    vocabulary to audit and test.
    """

    if type(operation) is not PlatformControlOperation:
        raise ValueError("unsupported SDCP control operation")
    identity = validate_mainboard_id(mainboard_id)
    command = _COMMAND_BY_OPERATION[operation]
    envelope = {
        "Id": str(uuid.uuid4()),
        "Data": {
            "Cmd": command,
            "Data": {},
            "RequestID": str(uuid.uuid4()),
            "MainboardID": identity,
            "TimeStamp": int(time.time()),
            "From": 0,
        },
        "Topic": f"sdcp/request/{identity}",
    }
    return json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
