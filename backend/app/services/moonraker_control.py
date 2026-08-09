"""Closed Moonraker print-job control endpoints.

Moonraker exposes these controls as fixed HTTP POST endpoints.  This module is
purposefully not a JSON-RPC or HTTP request builder: it accepts no path, body,
method, G-code, or arbitrary parameters from a caller.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from backend.app.control.contract import PlatformControlOperation


@dataclass(frozen=True)
class MoonrakerControlRequest:
    """A fixed, bodyless request that a trusted transport may issue."""

    method: str
    path: str

    def __post_init__(self) -> None:
        """Prevent this value object from becoming a generic HTTP request."""

        if (self.method, self.path) not in _CONTROL_ENDPOINTS:
            raise ValueError("unsupported Moonraker control request")


_CONTROL_ENDPOINTS = frozenset(
    {
        ("POST", "/printer/print/pause"),
        ("POST", "/printer/print/resume"),
        ("POST", "/printer/print/cancel"),
    }
)

_REQUEST_BY_OPERATION = MappingProxyType(
    {
        PlatformControlOperation.PAUSE_JOB: MoonrakerControlRequest("POST", "/printer/print/pause"),
        PlatformControlOperation.RESUME_JOB: MoonrakerControlRequest("POST", "/printer/print/resume"),
        PlatformControlOperation.CANCEL_JOB: MoonrakerControlRequest("POST", "/printer/print/cancel"),
    }
)


def request_for_control_operation(operation: object) -> MoonrakerControlRequest:
    """Return a copy of the sole permitted endpoint for an enum operation."""

    if type(operation) is not PlatformControlOperation:
        raise ValueError("unsupported Moonraker control operation")
    request = _REQUEST_BY_OPERATION[operation]
    return MoonrakerControlRequest(method=request.method, path=request.path)
