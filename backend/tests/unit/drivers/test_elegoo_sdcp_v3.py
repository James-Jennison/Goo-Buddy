from datetime import datetime, timedelta, timezone

import pytest

from backend.app.drivers.contract import Capability, ConnectionPhase, DriverKind, RetentionReason
from backend.app.drivers.elegoo_sdcp_v3 import (
    SdcpNormalizationError,
    SyntheticElegooSdcpV3Driver,
    normalize_synthetic_sdcp_v3,
)
from backend.tests._fixtures.elegoo_sdcp_v3 import attributes, status

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_normalizes_only_observed_sdcp_fields_and_advertised_capabilities():
    snapshot = normalize_synthetic_sdcp_v3(
        local_id="synthetic-centauri-1",
        observed_at=NOW,
        status_payload=status(),
        attributes_payload=attributes(),
    )

    assert snapshot.driver is DriverKind.ELEGOO_SDCP_V3
    assert snapshot.identity.local_id == "synthetic-centauri-1"
    assert snapshot.identity.display_name == "Synthetic Centauri"
    assert snapshot.state == "printing"
    assert snapshot.temperatures["nozzle"].current_c == 215
    assert snapshot.job is not None
    assert snapshot.job.name is None
    assert snapshot.job.progress_percent == 25
    assert snapshot.job.current_layer == 5
    assert snapshot.job.total_layers == 20
    assert Capability.TEMPERATURES in snapshot.capabilities
    assert Capability.JOB_STATUS in snapshot.capabilities
    assert Capability.JOB_CONTROL in snapshot.capabilities
    assert Capability.MULTI_MATERIAL not in snapshot.capabilities


def test_normalizer_advertises_only_closed_active_job_control_not_other_declared_capabilities():
    snapshot = normalize_synthetic_sdcp_v3(
        local_id="synthetic-centauri-1",
        observed_at=NOW,
        status_payload=status(),
        attributes_payload=attributes(capabilities=["canvas", "print_control", "camera", "file_transfer"]),
    )

    assert Capability.MULTI_MATERIAL not in snapshot.capabilities
    assert Capability.JOB_CONTROL in snapshot.capabilities
    assert Capability.CAMERA not in snapshot.capabilities
    assert Capability.FILES not in snapshot.capabilities


def test_normalizer_withholds_job_control_when_no_active_job_can_be_observed():
    idle = normalize_synthetic_sdcp_v3(
        local_id="synthetic-centauri-1",
        observed_at=NOW,
        status_payload=status(current_status=0),
        attributes_payload=attributes(),
    )

    assert Capability.JOB_CONTROL not in idle.capabilities
    assert idle.job is None
    assert Capability.JOB_STATUS not in idle.capabilities
    assert Capability.JOB_PROGRESS not in idle.capabilities
    assert Capability.LAYERS not in idle.capabilities


def test_normalizer_marks_ambiguous_state_as_error_and_rejects_incomplete_identity():
    ambiguous = normalize_synthetic_sdcp_v3(
        local_id="synthetic-centauri-1",
        observed_at=NOW,
        status_payload={"Status": {"CurrentStatus": [0, 1]}},
        attributes_payload=attributes(),
    )
    assert ambiguous.state == "error"

    with pytest.raises(SdcpNormalizationError):
        normalize_synthetic_sdcp_v3(
            local_id="synthetic-centauri-1",
            observed_at=NOW,
            status_payload=status(),
            attributes_payload={"Attributes": {"Name": "Synthetic Centauri"}},
        )


def test_normalizer_preserves_observed_idle_state_code_zero():
    snapshot = normalize_synthetic_sdcp_v3(
        local_id="synthetic-centauri-1",
        observed_at=NOW,
        status_payload=status(current_status=0),
        attributes_payload=attributes(),
    )

    assert snapshot.state == "idle"


def test_driver_separates_current_stale_disconnected_and_retained_snapshots():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1", stale_after=timedelta(seconds=30))
    driver.start_session("fixture-session-a")
    assert driver.observation(NOW).phase is ConnectionPhase.CONNECTING
    driver.observe_status("fixture-session-a", status(), NOW)
    assert driver.observation(NOW).phase is ConnectionPhase.WAITING

    driver.observe_attributes("fixture-session-a", attributes(), NOW)
    ready = driver.observation(NOW + timedelta(seconds=29))
    assert ready.phase is ConnectionPhase.READY
    assert ready.current is not None
    assert ready.retained is None

    stale = driver.observation(NOW + timedelta(seconds=30))
    assert stale.phase is ConnectionPhase.STALE
    assert stale.current is None
    assert stale.retained is not None
    assert stale.retained.reason is RetentionReason.STALE

    driver.disconnect("fixture-session-a")
    disconnected = driver.observation(NOW + timedelta(seconds=31))
    assert disconnected.phase is ConnectionPhase.DISCONNECTED
    assert disconnected.current is None
    assert disconnected.retained is not None
    assert disconnected.retained.reason is RetentionReason.DISCONNECTED
    assert Capability.TEMPERATURES in disconnected.capabilities


def test_driver_retains_a_complete_observation_when_disconnect_precedes_first_dashboard_poll():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    driver.start_session("fixture-session-a")
    driver.observe_status("fixture-session-a", status(), NOW)
    driver.observe_attributes("fixture-session-a", attributes(), NOW)
    driver.disconnect("fixture-session-a")

    observation = driver.observation(NOW)
    assert observation.phase is ConnectionPhase.DISCONNECTED
    assert observation.current is None
    assert observation.retained is not None
    assert observation.retained.reason is RetentionReason.DISCONNECTED


def test_driver_rejects_superseded_sessions_but_accepts_both_documented_topic_orders():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    driver.start_session("fixture-session-a")
    driver.observe_status("fixture-session-a", status(), NOW)
    driver.start_session("fixture-session-b")
    driver.observe_attributes("fixture-session-a", attributes(), NOW)

    rejected = driver.observation(NOW)
    assert rejected.phase is ConnectionPhase.INVALID
    assert rejected.error == "invalid or superseded session observation"

    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    driver.start_session("fixture-session-a")
    # Attributes can be pushed before status; timestamps are local arrival
    # ordering per topic, never interpreted as a printer tick unit.
    driver.observe_attributes("fixture-session-a", attributes(), NOW - timedelta(seconds=1))
    driver.observe_status("fixture-session-a", status(), NOW)
    assert driver.observation(NOW).phase is ConnectionPhase.READY


def test_driver_fails_closed_when_the_freshness_clock_regresses():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    driver.start_session("fixture-session-a")
    driver.observe_status("fixture-session-a", status(), NOW)
    driver.observe_attributes("fixture-session-a", attributes(), NOW)

    observation = driver.observation(NOW - timedelta(seconds=1))
    assert observation.phase is ConnectionPhase.INVALID
    assert observation.error == "invalid observation clock"


def test_driver_defensively_copies_injected_payloads_and_exposed_temperatures():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    status_payload = status()
    attributes_payload = attributes()
    driver.start_session("fixture-session-a")
    driver.observe_status("fixture-session-a", status_payload, NOW)
    driver.observe_attributes("fixture-session-a", attributes_payload, NOW)
    status_payload["Status"]["TempOfNozzle"] = 999.0
    attributes_payload["Attributes"]["Name"] = "Mutated input"

    observation = driver.observation(NOW)
    assert observation.current is not None
    assert observation.current.identity.display_name == "Synthetic Centauri"
    assert observation.current.temperatures["nozzle"].current_c == 215.0
    with pytest.raises(TypeError):
        observation.current.temperatures["nozzle"] = observation.current.temperatures["nozzle"]


def test_driver_rejects_duplicate_active_session_ids():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    driver.start_session("fixture-session-a")
    driver.start_session("fixture-session-a")

    observation = driver.observation(NOW)
    assert observation.phase is ConnectionPhase.INVALID
    assert observation.error == "invalid session"


def test_driver_has_no_network_or_command_surface():
    driver = SyntheticElegooSdcpV3Driver("synthetic-centauri-1")
    public_methods = {name for name in dir(driver) if not name.startswith("_")}
    assert public_methods == {
        "disconnect",
        "kind",
        "observation",
        "observe_attributes",
        "observe_status",
        "start_session",
    }
