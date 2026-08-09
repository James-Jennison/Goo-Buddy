"""Closed Moonraker job-control endpoint tests."""

from __future__ import annotations

import inspect

import pytest

from backend.app.control.contract import PlatformControlOperation
from backend.app.services.moonraker_control import MoonrakerControlRequest, request_for_control_operation


@pytest.mark.parametrize(
    ("operation", "path"),
    [
        (PlatformControlOperation.PAUSE_JOB, "/printer/print/pause"),
        (PlatformControlOperation.RESUME_JOB, "/printer/print/resume"),
        (PlatformControlOperation.CANCEL_JOB, "/printer/print/cancel"),
    ],
)
def test_request_builder_returns_only_documented_bodyless_post_endpoints(
    operation: PlatformControlOperation, path: str
) -> None:
    request = request_for_control_operation(operation)

    assert request.method == "POST"
    assert request.path == path
    assert set(request.__dict__) == {"method", "path"}


@pytest.mark.parametrize(
    "operation",
    [
        "printer.gcode.script",
        "/printer/print/pause",
        "pause_job",
        0,
        True,
        None,
        {"method": "POST", "path": "/printer/print/pause"},
    ],
)
def test_request_builder_rejects_gcode_paths_methods_and_all_non_enum_inputs(operation: object) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        request_for_control_operation(operation)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/printer/print/pause"),
        ("POST", "/printer/gcode/script"),
        ("POST", "/server/restart"),
        ("POST", "/printer/print/pause?gcode=M112"),
    ],
)
def test_request_value_rejects_arbitrary_methods_paths_and_gcode(method: str, path: str) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        MoonrakerControlRequest(method, path)


def test_request_builder_has_no_payload_path_or_method_parameter() -> None:
    """The adapter cannot become a JSON-RPC, G-code, or arbitrary HTTP tunnel."""

    assert tuple(inspect.signature(request_for_control_operation).parameters) == ("operation",)
    with pytest.raises(TypeError):
        request_for_control_operation(  # type: ignore[call-arg]
            PlatformControlOperation.PAUSE_JOB,
            payload={"script": "M112"},
        )
