"""Closed C5 submission intent and availability contract.

The contract binds an already-validated local artifact to a saved printer
source without carrying a printer path, endpoint, payload, command, or file
contents. It cannot upload or start a print; those operations remain outside
C5.0 until a platform-specific transport contract is approved.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from backend.app.core.compat import StrEnum
from backend.app.drivers.contract import Capability, ConnectionPhase, DriverKind, DriverObservation


class SubmissionArtifactKind(StrEnum):
    """The only local artifact references C5 may eventually submit."""

    ARCHIVE = "archive"
    LIBRARY_FILE = "library-file"


class PlatformSubmissionState(StrEnum):
    """Closed audit states reserved for later bounded submission dispatch."""

    DRAFT = "draft"
    QUEUED = "queued"
    TRANSFERRING = "transferring"
    STARTING = "starting"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlatformSubmissionUnconfirmed(Exception):
    """A start was accepted but fresh status did not confirm the submitted job."""


_SUPPORTED_DRIVERS = frozenset({DriverKind.BAMBU, DriverKind.ELEGOO_SDCP_V3, DriverKind.MOONRAKER})
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_IDEMPOTENCY_KEY = re.compile(r"^[a-f0-9]{32}$")
_TARGET_LABEL = re.compile(r"^[^\x00-\x1f\x7f]{1,100}$")
_READY_STATES = {
    DriverKind.BAMBU: frozenset({"IDLE"}),
    DriverKind.ELEGOO_SDCP_V3: frozenset({"idle"}),
    DriverKind.MOONRAKER: frozenset({"idle"}),
}


@dataclass(frozen=True)
class SubmissionArtifactReference:
    """An immutable local artifact identity, never a filesystem path."""

    kind: SubmissionArtifactKind
    artifact_id: int
    content_hash: str

    def __post_init__(self) -> None:
        if type(self.kind) is not SubmissionArtifactKind:
            raise ValueError("unsupported submission artifact kind")
        if type(self.artifact_id) is not int or self.artifact_id < 1:
            raise ValueError("invalid submission artifact")
        if not isinstance(self.content_hash, str) or not _SHA256.fullmatch(self.content_hash):
            raise ValueError("submission artifact requires a SHA-256 content hash")


@dataclass(frozen=True)
class PlatformSubmissionIntent:
    """A bounded request record that is deliberately not dispatchable in C5.0."""

    driver: DriverKind
    source_id: int
    configuration_revision: int
    target_label: str
    artifact: SubmissionArtifactReference
    idempotency_key: str

    def __post_init__(self) -> None:
        if self.driver not in _SUPPORTED_DRIVERS:
            raise ValueError("unsupported platform submission driver")
        if type(self.source_id) is not int or self.source_id < 1:
            raise ValueError("invalid platform submission source")
        if type(self.configuration_revision) is not int or self.configuration_revision < 1:
            raise ValueError("invalid platform submission configuration revision")
        if not isinstance(self.target_label, str) or not _TARGET_LABEL.fullmatch(self.target_label):
            raise ValueError("invalid platform submission target")
        if type(self.artifact) is not SubmissionArtifactReference:
            raise ValueError("invalid submission artifact reference")
        if not isinstance(self.idempotency_key, str) or not _IDEMPOTENCY_KEY.fullmatch(self.idempotency_key):
            raise ValueError("invalid platform submission idempotency key")


def new_platform_submission_intent(
    driver: DriverKind,
    source_id: int,
    configuration_revision: int,
    target_label: str,
    artifact: SubmissionArtifactReference,
    idempotency_key: str | None = None,
) -> PlatformSubmissionIntent:
    """Create a local audit intent without opening, reading, or transferring a file."""

    return PlatformSubmissionIntent(
        driver=driver,
        source_id=source_id,
        configuration_revision=configuration_revision,
        target_label=target_label,
        artifact=artifact,
        idempotency_key=idempotency_key if idempotency_key is not None else uuid.uuid4().hex,
    )


def submission_operation_is_available(observation: DriverObservation) -> bool:
    """Return true only for a future explicitly granted, fresh idle source.

    No current driver adds ``JOB_SUBMISSION``. This gate exists so a later
    adapter cannot accidentally surface a submit/start UI from ordinary file,
    job, or control telemetry alone.
    """

    current = observation.current
    if (
        observation.phase is not ConnectionPhase.READY
        or current is None
        or Capability.JOB_SUBMISSION not in observation.capabilities
        or Capability.JOB_SUBMISSION not in current.capabilities
    ):
        return False
    return current.state in _READY_STATES.get(current.driver, frozenset())
