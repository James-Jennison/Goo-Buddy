"""Redacted deterministic peer for closed Moonraker job controls.

The peer accepts only the three bodyless job-control POST endpoints.  It does
not model JSON-RPC, G-code, an arbitrary HTTP request builder, credentials, or
a real printer endpoint.
"""

from __future__ import annotations

from types import MappingProxyType
from urllib.parse import urlsplit

from backend.app.control.contract import PlatformControlOperation

PATH_BY_OPERATION = MappingProxyType(
    {
        PlatformControlOperation.PAUSE_JOB: "/printer/print/pause",
        PlatformControlOperation.RESUME_JOB: "/printer/print/resume",
        PlatformControlOperation.CANCEL_JOB: "/printer/print/cancel",
    }
)
OPERATION_BY_PATH = MappingProxyType({path: operation for operation, path in PATH_BY_OPERATION.items()})


class _AcceptedControlResponse:
    status = 200

    async def __aenter__(self) -> _AcceptedControlResponse:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class StrictMoonrakerControlPeer:
    """In-memory client accepting exactly the documented bodyless POSTs."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.operations: list[PlatformControlOperation] = []

    def post(self, url: str, **kwargs: object) -> _AcceptedControlResponse:
        if type(url) is not str or not url.startswith(self.base_url):
            raise AssertionError("unexpected Moonraker control target")
        parsed = urlsplit(url)
        if parsed.query or parsed.fragment:
            raise AssertionError("unexpected Moonraker control parameters")
        operation = OPERATION_BY_PATH.get(parsed.path)
        if operation is None or url != f"{self.base_url}{parsed.path}":
            raise AssertionError("unsupported Moonraker control path")
        if kwargs != {"allow_redirects": False}:
            raise AssertionError("Moonraker control requests must be bodyless and non-redirecting")
        self.operations.append(operation)
        return _AcceptedControlResponse()
