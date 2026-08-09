"""Closed, auditable control commands for non-Bambu printer sources.

This is intentionally not a transport abstraction.  It models only the small
set of user-visible print-job operations that future protocol adapters may
implement.  There is no payload, URL, JSON-RPC method, G-code, or raw SDCP
message field to prevent a caller from turning this contract into an arbitrary
printer-control escape hatch.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from backend.app.core.compat import StrEnum
from backend.app.drivers.contract import DriverKind


class PlatformControlOperation(StrEnum):
    """The complete initial cross-platform operation allowlist."""

    PAUSE_JOB = "pause_job"
    RESUME_JOB = "resume_job"
    CANCEL_JOB = "cancel_job"


class PlatformControlState(StrEnum):
    """Persisted command lifecycle states."""

    QUEUED = "queued"
    DISPATCHING = "dispatching"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    CANCELLED = "cancelled"


_SUPPORTED_DRIVERS = frozenset({DriverKind.ELEGOO_SDCP_V3, DriverKind.MOONRAKER})
_IDEMPOTENCY_KEY = re.compile(r"^[a-f0-9]{32}$")


@dataclass(frozen=True)
class PlatformControlCommand:
    """A request that can be persisted without a raw transport payload."""

    driver: DriverKind
    source_id: int
    configuration_revision: int
    operation: PlatformControlOperation
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.driver not in _SUPPORTED_DRIVERS:
            raise ValueError("unsupported platform control driver")
        if type(self.source_id) is not int or self.source_id < 1:
            raise ValueError("invalid platform control source")
        if type(self.configuration_revision) is not int or self.configuration_revision < 1:
            raise ValueError("invalid platform control configuration revision")
        if type(self.operation) is not PlatformControlOperation:
            raise ValueError("unsupported platform control operation")
        if not isinstance(self.idempotency_key, str) or not _IDEMPOTENCY_KEY.fullmatch(self.idempotency_key):
            raise ValueError("invalid platform control idempotency key")


def new_platform_control_command(
    driver: DriverKind,
    source_id: int,
    configuration_revision: int,
    operation: PlatformControlOperation,
) -> PlatformControlCommand:
    """Create an operation-only command with a server-generated idempotency key."""

    return PlatformControlCommand(
        driver=driver,
        source_id=source_id,
        configuration_revision=configuration_revision,
        operation=operation,
        idempotency_key=uuid.uuid4().hex,
    )
