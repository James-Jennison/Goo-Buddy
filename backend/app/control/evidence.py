"""Evidence registry for capability-gated lifecycle control activation.

This intentionally contains only the redacted, supervised result that has
been accepted for a specific platform/model/firmware combination.  It is not a
vendor capability table and must never be expanded from a model name, port, or
transport acknowledgement alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.control.contract import PlatformControlOperation
from backend.app.drivers.contract import ConnectionPhase, DriverKind, DriverObservation


@dataclass(frozen=True)
class ControlEvidence:
    """One exact, hardware-validated lifecycle-control evidence record."""

    driver: DriverKind
    model: str
    firmware: str
    operations: frozenset[PlatformControlOperation]


@dataclass(frozen=True)
class ControlAcknowledgement:
    """Persisted owner acknowledgement constrained to reviewed evidence."""

    configuration_revision: int
    model: str
    firmware: str
    operations: frozenset[PlatformControlOperation]


# The CC1 supervised session established exactly these operations for this
# observed configuration.  It does not grant the capability to another Elegoo
# model, firmware, endpoint revision, or protocol family.
_VALIDATED_CONTROL_EVIDENCE = (
    ControlEvidence(
        driver=DriverKind.ELEGOO_SDCP_V3,
        model="Centauri Carbon",
        firmware="V0.4.0-o",
        operations=frozenset(
            {
                PlatformControlOperation.PAUSE_JOB,
                PlatformControlOperation.RESUME_JOB,
                PlatformControlOperation.CANCEL_JOB,
            }
        ),
    ),
    # One supervised Moonraker session established the three fixed lifecycle
    # endpoint transitions for this exact normalized source identity. It does
    # not authorize a different Moonraker/Klipper version or configuration.
    ControlEvidence(
        driver=DriverKind.MOONRAKER,
        model="Klipper",
        firmware="v0.10.0-31-gd5ee171",
        operations=frozenset(
            {
                PlatformControlOperation.PAUSE_JOB,
                PlatformControlOperation.RESUME_JOB,
                PlatformControlOperation.CANCEL_JOB,
            }
        ),
    ),
)


def encode_acknowledged_operations(operations: frozenset[PlatformControlOperation]) -> str:
    """Persist only the closed operation identifiers in a stable form."""

    return ",".join(sorted(operation.value for operation in operations))


def decode_acknowledged_operations(value: str | None) -> frozenset[PlatformControlOperation]:
    """Reject malformed persisted values instead of widening the allowlist."""

    if not value:
        return frozenset()
    try:
        operations = frozenset(PlatformControlOperation(item) for item in value.split(","))
    except ValueError:
        return frozenset()
    return operations if encode_acknowledged_operations(operations) == value else frozenset()


def validated_control_evidence(driver: DriverKind, observation: DriverObservation) -> ControlEvidence | None:
    """Return evidence only for a fresh, exact observed identity match."""

    current = observation.current
    if observation.phase is not ConnectionPhase.READY or current is None:
        return None
    identity = current.identity
    for evidence in _VALIDATED_CONTROL_EVIDENCE:
        if evidence.driver is driver and identity.model == evidence.model and identity.firmware == evidence.firmware:
            return evidence
    return None


def acknowledgement_matches_observation(
    *,
    driver: DriverKind,
    model: str | None,
    firmware: str | None,
    operations: frozenset[PlatformControlOperation],
    observation: DriverObservation,
) -> bool:
    """Keep an already-validated acknowledgement bound to current identity.

    The API creates an acknowledgement only from ``validated_control_evidence``.
    The long-running manager must then compare the saved identity directly so a
    reconnect, replacement, or firmware change fails closed without treating a
    registry lookup as a new grant of authority.
    """

    current = observation.current
    if current is None:
        return False
    return bool(
        observation.phase is ConnectionPhase.READY
        and driver is current.driver
        and current.identity.model == model
        and current.identity.firmware == firmware
        and operations
    )
