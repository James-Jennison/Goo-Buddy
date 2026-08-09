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
    freeze_temperatures,
)


class MoonrakerNormalizationError(ValueError):
    pass


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _record(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MoonrakerNormalizationError("invalid Moonraker observation")
    return value


def _layer(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None


def normalize_moonraker_observation(
    *, local_id: str, display_name: str, observed_at: datetime, status: object, server: object
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
