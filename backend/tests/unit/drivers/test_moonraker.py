from datetime import datetime, timedelta, timezone

from backend.app.drivers.contract import Capability, ConnectionPhase, RetentionReason
from backend.app.drivers.moonraker import MoonrakerDriver, normalize_moonraker_observation

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _status():
    return {
        "webhooks": {"state": "ready"},
        "print_stats": {
            "state": "printing",
            "filename": "jobs/synthetic.gcode",
            "print_duration": 120,
            "info": {"current_layer": 2, "total_layer": 8},
        },
        "virtual_sdcard": {"progress": 0.25},
        "extruder": {"temperature": 210, "target": 215},
        "heater_bed": {"temperature": 60, "target": 60},
        "toolhead": {"extruder": "extruder", "homed_axes": "xyz"},
    }


def _server():
    return {"klippy_state": "ready", "moonraker_version": "synthetic"}


def test_normalizes_observed_moonraker_monitoring_values_only():
    snapshot = normalize_moonraker_observation(
        local_id="moon-1", display_name="Synthetic Klipper", observed_at=NOW, status=_status(), server=_server()
    )
    assert snapshot.state == "printing"
    assert snapshot.temperatures["nozzle"].current_c == 210
    assert snapshot.job and snapshot.job.progress_percent == 25
    assert snapshot.job.current_layer == 2 and snapshot.job.total_layers == 8
    assert snapshot.job.elapsed_seconds == 120 and snapshot.job.estimated_remaining_seconds == 360
    assert Capability.LAYERS in snapshot.capabilities
    assert Capability.JOB_CONTROL in snapshot.capabilities
    assert Capability.JOB_SUBMISSION not in snapshot.capabilities
    assert Capability.FILES not in snapshot.capabilities
    assert snapshot.toolhead and snapshot.toolhead.active_extruder == "extruder"
    assert snapshot.toolhead.homed_axes == "xyz"
    assert Capability.TOOLHEAD_TELEMETRY in snapshot.capabilities


def test_normalizer_withholds_malformed_toolhead_telemetry():
    status = _status()
    status["toolhead"] = {"extruder": "extruder\x00secret", "homed_axes": "xyza"}
    snapshot = normalize_moonraker_observation(
        local_id="moon-1", display_name="Synthetic Klipper", observed_at=NOW, status=status, server=_server()
    )

    assert snapshot.toolhead is None
    assert Capability.TOOLHEAD_TELEMETRY not in snapshot.capabilities


def test_normalizer_withholds_job_control_when_no_active_job_can_be_observed():
    status = _status()
    status["print_stats"]["state"] = "complete"
    snapshot = normalize_moonraker_observation(
        local_id="moon-1", display_name="Synthetic Klipper", observed_at=NOW, status=status, server=_server()
    )

    assert Capability.JOB_CONTROL not in snapshot.capabilities


def test_normalizer_preserves_observed_cancelled_as_a_terminal_job_state():
    status = _status()
    status["print_stats"]["state"] = "cancelled"
    snapshot = normalize_moonraker_observation(
        local_id="moon-1", display_name="Synthetic Klipper", observed_at=NOW, status=status, server=_server()
    )

    assert snapshot.state == "cancelled"
    assert snapshot.job and snapshot.job.state == "cancelled"
    assert Capability.JOB_CONTROL not in snapshot.capabilities


def test_normalizer_advertises_camera_only_after_the_manager_validates_a_source():
    snapshot = normalize_moonraker_observation(
        local_id="moon-1",
        display_name="Synthetic Klipper",
        observed_at=NOW,
        status=_status(),
        server=_server(),
        camera_available=True,
    )
    assert Capability.CAMERA in snapshot.capabilities


def test_driver_labels_stale_and_disconnected_data_as_retained():
    driver = MoonrakerDriver("moon-1", "Synthetic", stale_after=timedelta(seconds=30))
    driver.start_session("a")
    assert driver.observe("a", _status(), _server(), NOW)
    assert driver.observation(NOW).phase is ConnectionPhase.READY
    stale = driver.observation(NOW + timedelta(seconds=30))
    assert stale.phase is ConnectionPhase.STALE and stale.retained and stale.retained.reason is RetentionReason.STALE
    driver.disconnect("a")
    disconnected = driver.observation(NOW + timedelta(seconds=31))
    assert (
        disconnected.phase is ConnectionPhase.DISCONNECTED
        and disconnected.retained
        and disconnected.retained.reason is RetentionReason.DISCONNECTED
    )
