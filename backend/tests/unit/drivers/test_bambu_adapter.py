from datetime import datetime, timezone

from backend.app.drivers.bambu import BambuStateAdapter
from backend.app.drivers.contract import Capability, ConnectionPhase, DriverKind
from backend.app.services.bambu_mqtt import PrinterState


def test_bambu_adapter_passively_projects_existing_cached_state():
    state = PrinterState()
    state.connected = True
    state.state = "RUNNING"
    state.current_print = "existing-bambu-job.gcode.3mf"
    state.progress = 40
    state.layer_num = 12
    state.total_layers = 30
    state.temperatures = {"nozzle": {"current": 220, "target": 220}}

    observation = BambuStateAdapter("bambu-1", "Existing Bambu", "X1C").from_state(
        state, datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert observation.phase is ConnectionPhase.READY
    assert observation.current is not None
    assert observation.current.driver is DriverKind.BAMBU
    assert observation.current.job is not None
    assert observation.current.job.progress_percent == 40
    assert {
        Capability.TEMPERATURES,
        Capability.JOB_STATUS,
        Capability.JOB_PROGRESS,
        Capability.LAYERS,
    } <= observation.capabilities
    assert Capability.JOB_SUBMISSION not in observation.capabilities


def test_bambu_adapter_does_not_create_or_connect_a_client():
    adapter = BambuStateAdapter("bambu-1", "Existing Bambu")
    assert adapter.from_state(None, datetime(2026, 1, 1, tzinfo=timezone.utc)).phase is ConnectionPhase.DISCONNECTED
    assert not any("connect" in name or "command" in name for name in dir(adapter) if not name.startswith("_"))
