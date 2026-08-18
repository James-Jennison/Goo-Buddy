"""Strict Moonraker monitoring normalizer; networking belongs to its manager."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.app.drivers.contract import (
    Capability,
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
    RetainedSnapshot,
    RetentionReason,
    TemperatureReading,
    ToolheadTelemetry,
    freeze_temperatures,
)


class MoonrakerNormalizationError(ValueError):
    pass


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _bounded_text(value: object, *, allowed: frozenset[str] | None = None) -> str | None:
    if not isinstance(value, str) or len(value) > 80 or "\x00" in value:
        return None
    if allowed is not None and any(character not in allowed for character in value):
        return None
    return value


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MoonrakerNormalizationError("invalid Moonraker observation")
    return value


def _layer(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None


def normalize_moonraker_observation(
    *,
    local_id: str,
    display_name: str,
    observed_at: datetime,
    status: object,
    server: object,
    camera_available: bool = False,
    files_available: bool = False,
    console_history_available: bool = False,
) -> NormalizedPrinterSnapshot:
    """Normalize only a small, safe status subset supplied by fixed queries."""
    if not local_id or not display_name or observed_at.tzinfo is None:
        raise MoonrakerNormalizationError("invalid Moonraker observation")
    state = _record(status)
    server_info = _record(server)
    webhooks = state.get("webhooks") if isinstance(state.get("webhooks"), dict) else {}
    print_stats = state.get("print_stats") if isinstance(state.get("print_stats"), dict) else {}
    virtual_sdcard = state.get("virtual_sdcard") if isinstance(state.get("virtual_sdcard"), dict) else {}
    klippy_state = webhooks.get("state") if isinstance(webhooks.get("state"), str) else server_info.get("klippy_state")
    print_state = print_stats.get("state") if isinstance(print_stats.get("state"), str) else ""
    normalized_state = {
        "printing": "printing",
        "paused": "paused",
        "complete": "idle",
        "standby": "idle",
        # This is an observed terminal print state, distinct from an idle
        # printer. Keeping it distinct prevents a cancelled job from being
        # rewritten as a healthy idle state or from becoming control-eligible.
        "cancelled": "cancelled",
        "error": "error",
    }.get(print_state.lower())
    if normalized_state is None:
        normalized_state = (
            "error" if klippy_state == "shutdown" else "idle" if klippy_state == "ready" else "disconnected"
        )
    temperatures: dict[str, TemperatureReading] = {}
    for object_name, label in (("extruder", "nozzle"), ("heater_bed", "bed"), ("chamber", "chamber")):
        item = state.get(object_name)
        if isinstance(item, dict):
            current, target = _number(item.get("temperature")), _number(item.get("target"))
            if current is not None:
                temperatures[label] = TemperatureReading(current, target)
    caps: set[Capability] = {Capability.TEMPERATURES} if temperatures else set()
    toolhead_state = state.get("toolhead") if isinstance(state.get("toolhead"), dict) else {}
    active_extruder = _bounded_text(toolhead_state.get("extruder"))
    homed_axes = _bounded_text(toolhead_state.get("homed_axes"), allowed=frozenset("xyz"))
    toolhead = (
        ToolheadTelemetry(active_extruder=active_extruder, homed_axes=homed_axes)
        if (active_extruder is not None or homed_axes is not None)
        else None
    )
    if toolhead is not None:
        caps.add(Capability.TOOLHEAD_TELEMETRY)
    if camera_available:
        caps.add(Capability.CAMERA)
    if files_available:
        caps.add(Capability.FILES)
    if console_history_available:
        caps.add(Capability.CONSOLE_HISTORY)
    progress = _number(virtual_sdcard.get("progress"))
    progress_percent = progress * 100 if progress is not None and 0 <= progress <= 1 else None
    info = print_stats.get("info") if isinstance(print_stats.get("info"), dict) else {}
    current_layer = _layer(info.get("current_layer", print_stats.get("current_layer")))
    total_layers = _layer(info.get("total_layer", print_stats.get("total_layer")))
    elapsed_seconds = _number(print_stats.get("print_duration"))
    # This is only exposed when the firmware has supplied both an elapsed
    # duration and a bounded completion ratio; no file metadata or heuristic
    # speed profile is queried to manufacture an ETA.
    remaining_seconds = (
        elapsed_seconds * (1 - progress) / progress
        if elapsed_seconds is not None and progress and 0 < progress <= 1
        else None
    )
    job = None
    if print_state or progress_percent is not None or current_layer is not None or elapsed_seconds is not None:
        # Moonraker reports a configured filename. Keep only a bounded basename
        # for the owner-facing card; no raw response or path is logged/stored.
        raw_name = print_stats.get("filename")
        name = raw_name.rsplit("/", 1)[-1][:100] if isinstance(raw_name, str) and raw_name else None
        job = JobProgress(
            name=name,
            state=normalized_state,
            progress_percent=progress_percent,
            current_layer=current_layer,
            total_layers=total_layers,
            elapsed_seconds=elapsed_seconds,
            estimated_remaining_seconds=remaining_seconds,
        )
        caps.add(Capability.JOB_STATUS)
        if job.state in {"printing", "paused"}:
            caps.add(Capability.JOB_CONTROL)
        if progress_percent is not None:
            caps.add(Capability.JOB_PROGRESS)
        if current_layer is not None or total_layers is not None:
            caps.add(Capability.LAYERS)
    return NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            local_id=local_id,
            display_name=display_name,
            model="Klipper",
            firmware=server_info.get("moonraker_version")
            if isinstance(server_info.get("moonraker_version"), str)
            else None,
        ),
        driver=DriverKind.MOONRAKER,
        observed_at=observed_at.astimezone(timezone.utc),
        state=normalized_state,
        capabilities=frozenset(caps),
        temperatures=freeze_temperatures(temperatures),
        job=job,
        toolhead=toolhead,
    )


@dataclass
class _Session:
    session_id: str
    status: object | None = None
    server: object | None = None
    observed_at: datetime | None = None


class MoonrakerDriver:
    kind = DriverKind.MOONRAKER

    def __init__(self, local_id: str, display_name: str, stale_after: timedelta = timedelta(seconds=45)) -> None:
        self.local_id, self.display_name, self.stale_after = local_id, display_name, stale_after
        self.active: _Session | None = None
        self.retained: NormalizedPrinterSnapshot | None = None
        self.invalid_error: str | None = None
        self.camera_available = False
        self.files_available = False
        self.console_history_available = False

    def set_camera_available(self, available: bool) -> None:
        self.camera_available = available is True

    def set_files_available(self, available: bool) -> None:
        self.files_available = available is True

    def set_console_history_available(self, available: bool) -> None:
        self.console_history_available = available is True

    def start_session(self, session_id: str) -> None:
        self.active, self.invalid_error = _Session(session_id), None

    def observe(self, session_id: str, status: object, server: object, observed_at: datetime) -> bool:
        if self.active is None or self.active.session_id != session_id or observed_at.tzinfo is None:
            return False
        try:
            normalize_moonraker_observation(
                local_id=self.local_id,
                display_name=self.display_name,
                observed_at=observed_at,
                status=status,
                server=server,
                camera_available=self.camera_available,
                files_available=self.files_available,
                console_history_available=self.console_history_available,
            )
        except MoonrakerNormalizationError:
            self.invalid_error = "invalid Moonraker observation"
            return False
        self.active.status, self.active.server, self.active.observed_at = status, server, observed_at
        return True

    def disconnect(self, session_id: str) -> None:
        if self.active and self.active.session_id == session_id:
            if self.active.status is not None and self.active.server is not None and self.active.observed_at:
                try:
                    self.retained = normalize_moonraker_observation(
                        local_id=self.local_id,
                        display_name=self.display_name,
                        observed_at=self.active.observed_at,
                        status=self.active.status,
                        server=self.active.server,
                        camera_available=self.camera_available,
                        files_available=self.files_available,
                        console_history_available=self.console_history_available,
                    )
                except MoonrakerNormalizationError:
                    self.invalid_error = "invalid Moonraker observation"
            self.active = None

    def observation(self, now: datetime) -> DriverObservation:
        if now.tzinfo is None or self.invalid_error:
            return DriverObservation(
                ConnectionPhase.INVALID,
                frozenset(),
                retained=RetainedSnapshot(self.retained, RetentionReason.INVALID) if self.retained else None,
                error=self.invalid_error or "invalid clock",
            )
        if self.active is None:
            return DriverObservation(
                ConnectionPhase.DISCONNECTED,
                self.retained.capabilities if self.retained else frozenset(),
                retained=RetainedSnapshot(self.retained, RetentionReason.DISCONNECTED) if self.retained else None,
            )
        if self.active.status is None or self.active.server is None or self.active.observed_at is None:
            return DriverObservation(ConnectionPhase.WAITING, frozenset(), session_id=self.active.session_id)
        snap = normalize_moonraker_observation(
            local_id=self.local_id,
            display_name=self.display_name,
            observed_at=self.active.observed_at,
            status=self.active.status,
            server=self.active.server,
            camera_available=self.camera_available,
            files_available=self.files_available,
            console_history_available=self.console_history_available,
        )
        self.retained = snap
        if now.astimezone(timezone.utc) - snap.observed_at >= self.stale_after:
            return DriverObservation(
                ConnectionPhase.STALE,
                snap.capabilities,
                retained=RetainedSnapshot(snap, RetentionReason.STALE),
                session_id=self.active.session_id,
            )
        return DriverObservation(
            ConnectionPhase.READY, snap.capabilities, current=snap, session_id=self.active.session_id
        )
