"""Closed SDCP v3 job-control serialization tests."""

from __future__ import annotations

import inspect
import json
import uuid

import pytest

from backend.app.control.contract import PlatformControlOperation
from backend.app.services.elegoo_sdcp_control import serialize_control_request

_IDENTITY = "fixture-mainboard-01"


@pytest.mark.parametrize(
    ("operation", "command"),
    [
        (PlatformControlOperation.PAUSE_JOB, 129),
        (PlatformControlOperation.CANCEL_JOB, 130),
        (PlatformControlOperation.RESUME_JOB, 131),
    ],
)
def test_serializer_emits_only_documented_job_control_envelopes(
    operation: PlatformControlOperation, command: int
) -> None:
    envelope = json.loads(serialize_control_request(operation, _IDENTITY))

    assert envelope["Topic"] == f"sdcp/request/{_IDENTITY}"
    assert envelope["Data"] == {
        "Cmd": command,
        "Data": {},
        "RequestID": envelope["Data"]["RequestID"],
        "MainboardID": _IDENTITY,
        "TimeStamp": envelope["Data"]["TimeStamp"],
        "From": 0,
    }
    assert str(uuid.UUID(envelope["Id"])) == envelope["Id"]
    assert str(uuid.UUID(envelope["Data"]["RequestID"])) == envelope["Data"]["RequestID"]
    assert isinstance(envelope["Data"]["TimeStamp"], int)


@pytest.mark.parametrize("operation", [129, 130, 131, "pause_job", True, None, {"Cmd": 129}])
def test_serializer_rejects_command_numbers_and_all_non_enum_inputs(operation: object) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        serialize_control_request(operation, _IDENTITY)


@pytest.mark.parametrize("identity", ["", "bad/id", "bad whitespace", 123, None, {"id": "x"}])
def test_serializer_rejects_malformed_identity_without_echoing_it(identity: object) -> None:
    with pytest.raises(ValueError, match="identity") as error:
        serialize_control_request(PlatformControlOperation.PAUSE_JOB, identity)
    if isinstance(identity, str) and identity:
        assert identity not in str(error.value)


def test_serializer_has_no_command_path_or_payload_parameter() -> None:
    """Callers cannot smuggle an SDCP command or raw payload into the adapter."""

    assert tuple(inspect.signature(serialize_control_request).parameters) == ("operation", "mainboard_id")
    with pytest.raises(TypeError):
        serialize_control_request(  # type: ignore[call-arg]
            PlatformControlOperation.PAUSE_JOB, _IDENTITY, payload={"Cmd": 999, "Data": {"gcode": "M112"}}
        )
