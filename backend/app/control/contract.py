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
from backend.app.drivers.contract import Capability, ConnectionPhase, DriverKind, DriverObservation


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
    idempotency_key: str | None = None,
) -> PlatformControlCommand:
    """Create an operation-only command with a bounded idempotency key.

    HTTP callers supply their already-generated key so a network retry can be
    reconciled with its original audit row.  Internal callers may omit it, in
    which case the server creates an equally bounded value.  Neither form can
    carry protocol data.
    """

    return PlatformControlCommand(
        driver=driver,
        source_id=source_id,
        configuration_revision=configuration_revision,
        operation=operation,
        idempotency_key=idempotency_key if idempotency_key is not None else uuid.uuid4().hex,
    )


def control_operation_is_available(operation: object, observation: DriverObservation) -> bool:
    """Return whether a fresh observation permits one closed job operation.

    A generic ``JOB_CONTROL`` capability alone is deliberately insufficient:
    a command must also match the currently observed job state.  This avoids
    sending pause/resume/cancel blindly after the printer has changed state.
    """

    if type(operation) is not PlatformControlOperation:
        return False
    if (
        observation.phase is not ConnectionPhase.READY
        or Capability.JOB_CONTROL not in observation.capabilities
        or observation.current is None
        or observation.current.job is None
    ):
        return False
    state = observation.current.job.state
    if operation is PlatformControlOperation.PAUSE_JOB:
        return state == "printing"
    if operation is PlatformControlOperation.RESUME_JOB:
        return state == "paused"
    return state in {"printing", "paused"}
