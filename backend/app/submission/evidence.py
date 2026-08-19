"""Evidence-gated source acknowledgement for future managed submission.

This is independent of C4 lifecycle-control evidence.  It records no network
method, artifact path, request body, credential, or capability grant.  Until a
specific source/firmware completes C5.3 supervised validation, the registry is
empty and every acknowledgement attempt fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.app.drivers.contract import ConnectionPhase, DriverKind, DriverObservation


@dataclass(frozen=True)
class SubmissionEvidence:
    """One exact hardware-validated submission contract identity."""

    driver: DriverKind
    model: str
    firmware: str
    contract_id: str


@dataclass(frozen=True)
class SubmissionAcknowledgement:
    """An owner acknowledgement bound to one saved source revision."""

    configuration_revision: int
    model: str
    firmware: str
    contract_id: str


# C5.1 is documentation and deterministic-offline contract evidence only.
# No entry belongs here until C5.3 validates a concrete source/firmware with a
# disposable artifact under explicit owner supervision.
_VALIDATED_SUBMISSION_EVIDENCE: tuple[SubmissionEvidence, ...] = ()


def validated_submission_evidence(driver: DriverKind, observation: DriverObservation) -> SubmissionEvidence | None:
    """Return an exact fresh evidence match, never a model or port inference."""

    current = observation.current
    if observation.phase is not ConnectionPhase.READY or current is None:
        return None
    for evidence in _VALIDATED_SUBMISSION_EVIDENCE:
        if (
            evidence.driver is driver
            and current.identity.model == evidence.model
            and current.identity.firmware == evidence.firmware
        ):
            return evidence
    return None


def acknowledgement_matches_observation(
    *,
    driver: DriverKind,
    model: str | None,
    firmware: str | None,
    contract_id: str | None,
    observation: DriverObservation,
) -> bool:
    """Fail closed when the identity, firmware, or contract has changed."""

    current = observation.current
    return bool(
        observation.phase is ConnectionPhase.READY
        and current is not None
        and current.driver is driver
        and current.identity.model == model
        and current.identity.firmware == firmware
        and isinstance(contract_id, str)
        and contract_id
    )
