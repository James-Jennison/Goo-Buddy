"""Offline lifecycle-control reconciliation contracts.

This module records the exact state evidence a future, explicitly activated
pause/resume/cancel implementation must require before it can report success.
It is deliberately not a transport abstraction: it cannot send a command,
open a connection, or make a platform available for control.

The contracts are a cross-platform planning boundary.  They capture inherited
Bambu state names alongside the normalized state names used by the dormant
Elegoo and Moonraker adapters, without routing Bambu through the non-Bambu
control path.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from backend.app.control.contract import PlatformControlOperation
from backend.app.drivers.contract import ConnectionPhase, DriverKind, DriverObservation


@dataclass(frozen=True)
class LifecycleReconciliationContract:
    """One non-dispatching lifecycle operation contract.

    ``source_states`` is the authoritative state required before dispatch;
    ``success_states`` is the post-command state that a fresh observation must
    establish.  Cancel can reach several terminal states, so it is represented
    by an explicit finite set rather than a catch-all success condition.

    ``evidence_status`` describes code and fixture evidence only.  It never
    represents owner acknowledgement or supervised hardware validation.
    """

    driver: DriverKind
    operation: PlatformControlOperation
    source_states: frozenset[str]
    success_states: frozenset[str]
    evidence_status: str


_BAMBU_ACTIVE_STATES = frozenset({"PREPARE", "SLICING", "RUNNING", "PAUSE"})
_BAMBU_TERMINAL_STATES = frozenset({"IDLE", "FINISH", "FAILED"})
_NORMALIZED_ACTIVE_STATES = frozenset({"printing", "paused"})
_NORMALIZED_TERMINAL_STATES = frozenset({"idle", "finished", "error"})


def _contracts_for(
    driver: DriverKind,
    *,
    pause_source: frozenset[str],
    pause_success: frozenset[str],
    resume_source: frozenset[str],
    resume_success: frozenset[str],
    cancel_source: frozenset[str],
    cancel_success: frozenset[str],
    evidence_status: str,
) -> dict[tuple[DriverKind, PlatformControlOperation], LifecycleReconciliationContract]:
    return {
        (driver, PlatformControlOperation.PAUSE_JOB): LifecycleReconciliationContract(
            driver, PlatformControlOperation.PAUSE_JOB, pause_source, pause_success, evidence_status
        ),
        (driver, PlatformControlOperation.RESUME_JOB): LifecycleReconciliationContract(
            driver, PlatformControlOperation.RESUME_JOB, resume_source, resume_success, evidence_status
        ),
        (driver, PlatformControlOperation.CANCEL_JOB): LifecycleReconciliationContract(
            driver, PlatformControlOperation.CANCEL_JOB, cancel_source, cancel_success, evidence_status
        ),
    }


_CONTRACTS = MappingProxyType(
    {
        **_contracts_for(
            DriverKind.BAMBU,
            pause_source=frozenset({"RUNNING"}),
            pause_success=frozenset({"PAUSE"}),
            resume_source=frozenset({"PAUSE"}),
            resume_success=frozenset({"RUNNING"}),
            cancel_source=_BAMBU_ACTIVE_STATES,
            cancel_success=_BAMBU_TERMINAL_STATES,
            evidence_status="inherited-regression-covered",
        ),
        **_contracts_for(
            DriverKind.ELEGOO_SDCP_V3,
            pause_source=frozenset({"printing"}),
            pause_success=frozenset({"paused"}),
            resume_source=frozenset({"paused"}),
            resume_success=frozenset({"printing"}),
            cancel_source=_NORMALIZED_ACTIVE_STATES,
            cancel_success=_NORMALIZED_TERMINAL_STATES,
            evidence_status="dormant-adapter-only",
        ),
        **_contracts_for(
            DriverKind.MOONRAKER,
            pause_source=frozenset({"printing"}),
            pause_success=frozenset({"paused"}),
            resume_source=frozenset({"paused"}),
            resume_success=frozenset({"printing"}),
            cancel_source=_NORMALIZED_ACTIVE_STATES,
            cancel_success=_NORMALIZED_TERMINAL_STATES,
            evidence_status="dormant-adapter-only",
        ),
    }
)


def lifecycle_reconciliation_contract(driver: object, operation: object) -> LifecycleReconciliationContract | None:
    """Return a closed, offline contract for an exact supported pair.

    Returning a contract does not make a platform controllable.  Callers still
    need the separate owner acknowledgement, permission, audit, and supervised
    validation gates recorded in the C4 plan.
    """

    if type(driver) is not DriverKind or type(operation) is not PlatformControlOperation:
        return None
    return _CONTRACTS.get((driver, operation))


def observation_satisfies_reconciliation(operation: object, observation: DriverObservation) -> bool:
    """Whether a fresh normalized observation reaches its known success state.

    This helper is intentionally limited to the normalized non-Bambu driver
    observations.  Bambu retains its inherited status model and is mapped here
    for the C4 evidence ledger, not routed through this helper.
    """

    if type(operation) is not PlatformControlOperation:
        return False
    if observation.phase is not ConnectionPhase.READY or observation.current is None:
        return False
    contract = lifecycle_reconciliation_contract(observation.current.driver, operation)
    if contract is None or contract.driver is DriverKind.BAMBU:
        return False
    job = observation.current.job
    if job is None:
        # Some valid SDCP status updates carry an authoritative current state
        # while omitting PrintInfo entirely.  A fresh, ready snapshot state is
        # still sufficient to reconcile a fixed lifecycle operation; retained
        # snapshots never reach this branch.
        return observation.current.state in contract.success_states
    # A driver must not turn a retained or internally contradictory job field
    # into a successful lifecycle result.  The snapshot's authoritative state
    # and its current-job state must agree.
    return observation.current.state == job.state and job.state in contract.success_states
