"""A passive adapter for the existing Bambu state cache.

It never owns or starts a ``BambuMQTTClient``. The existing Bambu integration
continues to be authoritative; this adapter only shows how that state can be
represented by the new read-only driver contract.
"""

from __future__ import annotations

from datetime import datetime

from backend.app.drivers.contract import (
    Capability,
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
    TemperatureReading,
    freeze_temperatures,
)
from backend.app.services.bambu_mqtt import PrinterState


def _finite_progress(value: object) -> float | None:
    if isinstance(value, (int, float)) and 0 <= value <= 100:
        return float(value)
    return None


class BambuStateAdapter:
    """Project an already-cached Bambu ``PrinterState`` without changing it."""

    kind = DriverKind.BAMBU

    def __init__(self, local_id: str, display_name: str, model: str | None = None):
        self._identity = PrinterIdentity(local_id=local_id, display_name=display_name, model=model)

    def from_state(self, state: PrinterState | None, observed_at: datetime) -> DriverObservation:
        if state is None or not state.connected:
            return DriverObservation(
                phase=ConnectionPhase.DISCONNECTED,
                capabilities=frozenset(),
            )

        temperatures: dict[str, TemperatureReading] = {}
        for name, raw in (state.temperatures or {}).items():
            if not isinstance(raw, dict):
                continue
            current = raw.get("current")
            target = raw.get("target")
            if isinstance(current, (int, float)):
                temperatures[str(name)] = TemperatureReading(
                    current_c=float(current),
                    target_c=float(target) if isinstance(target, (int, float)) else None,
                )

        capabilities: set[Capability] = set()
        if temperatures:
            capabilities.add(Capability.TEMPERATURES)

        job = None
        if state.current_print is not None or state.state:
            capabilities.add(Capability.JOB_STATUS)
            progress = _finite_progress(state.progress)
            if progress is not None:
                capabilities.add(Capability.JOB_PROGRESS)
            if state.layer_num or state.total_layers:
                capabilities.add(Capability.LAYERS)
            job = JobProgress(
                name=state.current_print,
                state=state.state or "unknown",
                progress_percent=progress,
                current_layer=state.layer_num or None,
                total_layers=state.total_layers or None,
            )

        snapshot = NormalizedPrinterSnapshot(
            identity=self._identity,
            driver=self.kind,
            observed_at=observed_at,
            state=state.state or "unknown",
            capabilities=frozenset(capabilities),
            temperatures=freeze_temperatures(temperatures),
            job=job,
        )
        return DriverObservation(
            phase=ConnectionPhase.READY,
            capabilities=snapshot.capabilities,
            current=snapshot,
        )
