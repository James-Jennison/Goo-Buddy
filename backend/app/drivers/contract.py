"""Protocol-neutral, read-only printer observations.

The contract is deliberately narrower than Bambuddy's existing operational
surface. It models what a driver has *observed*, not what an application may
command. This keeps the first Elegoo implementation isolated from the mature
Bambu MQTT, FTP, queue, and database paths.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Protocol, runtime_checkable


class DriverKind(str, Enum):
    BAMBU = "bambu"
    ELEGOO_SDCP_V3 = "elegoo.sdcp-v3"
    MOONRAKER = "moonraker"


class Capability(str, Enum):
    TEMPERATURES = "temperatures"
    JOB_STATUS = "job-status"
    JOB_PROGRESS = "job-progress"
    LAYERS = "layers"
    CAMERA = "camera"
    FILES = "files"
    CONSOLE_HISTORY = "console-history"
    TOOLHEAD_TELEMETRY = "toolhead-telemetry"
    JOB_CONTROL = "job-control"
    MOTION = "motion"
    MULTI_MATERIAL = "multi-material"


class ConnectionPhase(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    WAITING = "waiting"
    RECONNECTING = "reconnecting"
    READY = "ready"
    STALE = "stale"
    INVALID = "invalid"


class RetentionReason(str, Enum):
    STALE = "stale"
    DISCONNECTED = "disconnected"
    INVALID = "invalid"


@dataclass(frozen=True)
class PrinterIdentity:
    """A normalized identity with a local, non-secret stable key."""

    local_id: str
    display_name: str
    model: str | None = None
    firmware: str | None = None


@dataclass(frozen=True)
class TemperatureReading:
    current_c: float
    target_c: float | None = None


@dataclass(frozen=True)
class JobProgress:
    name: str | None
    state: str
    progress_percent: float | None = None
    current_layer: int | None = None
    total_layers: int | None = None
    elapsed_seconds: float | None = None
    estimated_remaining_seconds: float | None = None


@dataclass(frozen=True)
class ToolheadTelemetry:
    """Small, display-only state projection for the configured toolhead."""

    active_extruder: str | None = None
    homed_axes: str | None = None


@dataclass(frozen=True)
class NormalizedPrinterSnapshot:
    identity: PrinterIdentity
    driver: DriverKind
    observed_at: datetime
    state: str
    capabilities: frozenset[Capability]
    temperatures: Mapping[str, TemperatureReading] = field(default_factory=lambda: MappingProxyType({}))
    job: JobProgress | None = None
    toolhead: ToolheadTelemetry | None = None


def freeze_temperatures(values: Mapping[str, TemperatureReading]) -> Mapping[str, TemperatureReading]:
    """Return an immutable, copied temperature view for a public snapshot."""

    return MappingProxyType(dict(values))


@dataclass(frozen=True)
class RetainedSnapshot:
    snapshot: NormalizedPrinterSnapshot
    reason: RetentionReason


@dataclass(frozen=True)
class DriverObservation:
    """The safe projection of a driver's latest observation.

    ``current`` is present only while fresh and ready. A stale, disconnected,
    or invalid driver may expose the last valid snapshot only through
    ``retained`` so a UI cannot accidentally present it as live data.
    """

    phase: ConnectionPhase
    capabilities: frozenset[Capability]
    current: NormalizedPrinterSnapshot | None = None
    retained: RetainedSnapshot | None = None
    error: str | None = None
    session_id: str | None = None


@runtime_checkable
class DriverProtocol(Protocol):
    """Read-only driver contract; it intentionally contains no command method."""

    kind: DriverKind

    def observation(self, now: datetime) -> DriverObservation: ...
