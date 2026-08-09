"""Synthetic-only Elegoo SDCP v3 observation foundation.

This module parses a deliberately small status/attributes subset supplied by
tests or a future transport. It does not import networking code, persist data,
discover printers, accept credentials, or issue SDCP requests/commands.
"""

from __future__ import annotations

from copy import deepcopy
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


class SdcpNormalizationError(ValueError):
    """A conservative, payload-free error suitable for user-facing state."""


def _record(value: object) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _candidate_records(payload: object, container: str) -> list[dict[str, Any]]:
    root = _record(payload)
    if root is None:
        return []
    data = _record(root.get("Data"))
    nested = _record(data.get("Data")) if data else None
    candidates = [
        _record(root.get(container)),
        _record(data.get(container)) if data else None,
        _record(nested.get(container)) if nested else None,
        nested,
        data,
        root,
    ]
    return [candidate for candidate in candidates if candidate is not None]


def _status_record(payload: object) -> dict[str, Any] | None:
    return next((item for item in _candidate_records(payload, "Status") if "CurrentStatus" in item), None)


def _attributes_record(payload: object) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in _candidate_records(payload, "Attributes")
            if any(key in item for key in ("Name", "MachineName", "FirmwareVersion", "Capabilities"))
        ),
        None,
    )


def _text(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _number(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _non_negative_int(value: object) -> int | None:
    number = _number(value)
    return int(number) if number is not None and number >= 0 and number.is_integer() else None


def _state(status: dict[str, Any]) -> str:
    print_info = _record(status.get("PrintInfo")) or {}
    error = _number(print_info.get("ErrorNumber"))
    if error not in (None, 0):
        return "error"
    raw = status.get("CurrentStatus")
    codes = raw if isinstance(raw, list) else [raw]
    code_value = _number(codes[0]) if len(codes) == 1 else None
    if code_value is None:
        return "error"
    code = int(code_value)
    if code == 0:
        return "idle"
    if code == 1:
        return "paused" if _number(print_info.get("Status")) in (5, 6) else "printing"
    if code == 3:
        return "calibrating"
    return "error"


def _temperature(status: dict[str, Any], current_key: str, target_key: str) -> TemperatureReading | None:
    current = _number(status.get(current_key))
    if current is None:
        return None
    return TemperatureReading(current_c=current, target_c=_number(status.get(target_key)))


def normalize_synthetic_sdcp_v3(
    *, local_id: str, observed_at: datetime, status_payload: object, attributes_payload: object
) -> NormalizedPrinterSnapshot:
    """Normalize only documented synthetic fixture fields, failing closed on ambiguity."""

    if not local_id or local_id != local_id.strip():
        raise SdcpNormalizationError("invalid local printer id")
    if observed_at.tzinfo is None:
        raise SdcpNormalizationError("observed_at must be timezone-aware")
    status = _status_record(status_payload)
    attributes = _attributes_record(attributes_payload)
    if status is None:
        raise SdcpNormalizationError("missing status record")
    if attributes is None:
        raise SdcpNormalizationError("missing attributes record")
    name = _text(attributes, "Name", "MachineName")
    model = _text(attributes, "MachineName", "Model")
    if name is None or model is None:
        raise SdcpNormalizationError("incomplete printer identity")

    # Declared protocol capabilities are not a safe UI claim by themselves.
    # This driver exposes only data it has actually parsed.  Its three fixed
    # SDCP v3 job commands are available only for a fresh, active print state;
    # CANVAS or other declared capabilities never become action capabilities.
    capabilities: set[Capability] = set()
    temperatures: dict[str, TemperatureReading] = {}
    for key, current, target in (
        # OpenCentauri's SDCP v3 reference names targets ``TempTarget*``.
        # Keep the older fixture aliases as a compatibility-only fallback so
        # the transport accepts the documented spelling without inventing
        # another temperature source.
        ("nozzle", "TempOfNozzle", "TempTargetNozzle"),
        ("bed", "TempOfHotbed", "TempTargetHotbed"),
        ("chamber", "TempOfBox", "TempTargetBox"),
    ):
        value = _temperature(
            status,
            current,
            target if target in status else f"Target{current}",
        )
        if value is not None:
            temperatures[key] = value
    if temperatures:
        capabilities.add(Capability.TEMPERATURES)

    state = _state(status)
    print_info = _record(status.get("PrintInfo"))
    job = None
    # Printers can retain a completed job's final progress and layer values in
    # PrintInfo after returning to idle. Those fields are history, not a live
    # job, and must not make the dashboard present a finished print as active.
    if print_info is not None and state in {"printing", "paused"}:
        current_ticks = _number(print_info.get("CurrentTicks"))
        total_ticks = _number(print_info.get("TotalTicks"))
        current_layer = _non_negative_int(print_info.get("CurrentLayer"))
        total_layers = _non_negative_int(print_info.get("TotalLayer"))
        progress = None
        if (
            current_ticks is not None
            and total_ticks is not None
            and total_ticks > 0
            and 0 <= current_ticks <= total_ticks
        ):
            progress = current_ticks / total_ticks * 100
        elif (
            current_layer is not None
            and total_layers is not None
            and total_layers > 0
            and current_layer <= total_layers
        ):
            progress = current_layer / total_layers * 100
        if progress is not None or current_layer is not None or total_layers is not None:
            job = JobProgress(
                # G-code filenames are intentionally never retained or
                # projected through the ordinary dashboard API.
                name=None,
                state=state,
                progress_percent=progress,
                current_layer=current_layer,
                total_layers=total_layers,
            )
            capabilities.add(Capability.JOB_STATUS)
            if job.state in {"printing", "paused"}:
                capabilities.add(Capability.JOB_CONTROL)
            if progress is not None:
                capabilities.add(Capability.JOB_PROGRESS)
            if current_layer is not None or total_layers is not None:
                capabilities.add(Capability.LAYERS)

    return NormalizedPrinterSnapshot(
        identity=PrinterIdentity(
            local_id=local_id,
            display_name=name,
            model=model,
            firmware=_text(attributes, "FirmwareVersion"),
        ),
        driver=DriverKind.ELEGOO_SDCP_V3,
        observed_at=observed_at.astimezone(timezone.utc),
        state=state,
        capabilities=frozenset(capabilities),
        temperatures=freeze_temperatures(temperatures),
        job=job,
    )


@dataclass
class _ActiveSession:
    session_id: str
    status_payload: object | None = None
    status_at: datetime | None = None
    attributes_payload: object | None = None
    attributes_at: datetime | None = None


class SyntheticElegooSdcpV3Driver:
    """State machine for injected synthetic observations; no I/O is possible here."""

    kind = DriverKind.ELEGOO_SDCP_V3

    def __init__(self, local_id: str, stale_after: timedelta = timedelta(seconds=30)):
        if not local_id or local_id != local_id.strip():
            raise ValueError("local_id must be a non-empty, trimmed string")
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        self._local_id = local_id
        self._stale_after = stale_after
        self._active: _ActiveSession | None = None
        self._closed_sessions: set[str] = set()
        self._retained: NormalizedPrinterSnapshot | None = None
        self._invalid_error: str | None = None

    def start_session(self, session_id: str) -> None:
        if (
            not session_id
            or session_id != session_id.strip()
            or session_id in self._closed_sessions
            or (self._active is not None and session_id == self._active.session_id)
        ):
            self._invalid_error = "invalid session"
            return
        if self._active is not None:
            self._closed_sessions.add(self._active.session_id)
        self._active = _ActiveSession(session_id=session_id)
        self._invalid_error = None

    def observe_status(self, session_id: str, payload: object, observed_at: datetime) -> None:
        if not self._accepts(session_id, observed_at, self._active.status_at if self._active else None):
            return
        assert self._active is not None
        try:
            self._active.status_payload = deepcopy(payload)
        except (TypeError, ValueError, RecursionError):
            self._invalid_error = "invalid synthetic observation"
            return
        self._active.status_at = observed_at

    def observe_attributes(self, session_id: str, payload: object, observed_at: datetime) -> None:
        if not self._accepts(session_id, observed_at, self._active.attributes_at if self._active else None):
            return
        assert self._active is not None
        try:
            self._active.attributes_payload = deepcopy(payload)
        except (TypeError, ValueError, RecursionError):
            self._invalid_error = "invalid synthetic observation"
            return
        self._active.attributes_at = observed_at

    def disconnect(self, session_id: str) -> None:
        if self._active is None or self._active.session_id != session_id:
            return
        # Preserve a complete observation even when the socket closes before a
        # dashboard poll. Retention must reflect what was received, not the
        # timing of an unrelated HTTP status request.
        if (
            self._active.status_payload is not None
            and self._active.attributes_payload is not None
            and self._active.status_at is not None
            and self._active.attributes_at is not None
        ):
            try:
                self._retained = normalize_synthetic_sdcp_v3(
                    local_id=self._local_id,
                    observed_at=max(self._active.status_at, self._active.attributes_at),
                    status_payload=self._active.status_payload,
                    attributes_payload=self._active.attributes_payload,
                )
            except SdcpNormalizationError:
                self._invalid_error = "invalid SDCP observation"
        self._closed_sessions.add(session_id)
        self._active = None

    def observation(self, now: datetime) -> DriverObservation:
        if now.tzinfo is None:
            return self._invalid("invalid observation clock")
        if self._invalid_error is not None:
            return self._invalid(self._invalid_error)
        if self._active is None:
            return DriverObservation(
                phase=ConnectionPhase.DISCONNECTED,
                capabilities=self._retained.capabilities if self._retained is not None else frozenset(),
                retained=self._retained_view(RetentionReason.DISCONNECTED),
            )
        active = self._active
        if active.status_payload is None and active.attributes_payload is None:
            return DriverObservation(
                phase=ConnectionPhase.CONNECTING,
                capabilities=frozenset(),
                session_id=active.session_id,
            )
        if (
            active.status_payload is None
            or active.attributes_payload is None
            or active.status_at is None
            or active.attributes_at is None
        ):
            return DriverObservation(
                phase=ConnectionPhase.WAITING,
                capabilities=frozenset(),
                session_id=active.session_id,
            )
        observed_at = max(active.status_at, active.attributes_at)
        if now.astimezone(timezone.utc) < observed_at.astimezone(timezone.utc):
            self._invalid_error = "invalid observation clock"
            return self._invalid(self._invalid_error)
        try:
            snapshot = normalize_synthetic_sdcp_v3(
                local_id=self._local_id,
                observed_at=observed_at,
                status_payload=active.status_payload,
                attributes_payload=active.attributes_payload,
            )
        except SdcpNormalizationError:
            self._invalid_error = "invalid SDCP observation"
            return self._invalid(self._invalid_error)
        self._retained = snapshot
        if now.astimezone(timezone.utc) - snapshot.observed_at >= self._stale_after:
            return DriverObservation(
                phase=ConnectionPhase.STALE,
                capabilities=snapshot.capabilities,
                retained=self._retained_view(RetentionReason.STALE),
                session_id=active.session_id,
            )
        return DriverObservation(
            phase=ConnectionPhase.READY,
            capabilities=snapshot.capabilities,
            current=snapshot,
            session_id=active.session_id,
        )

    def _accepts(self, session_id: str, observed_at: datetime, last_for_topic: datetime | None) -> bool:
        if observed_at.tzinfo is None or self._active is None or self._active.session_id != session_id:
            self._invalid_error = "invalid or superseded session observation"
            return False
        # Attributes and status are independently pushed and either documented
        # order is valid. Only reject an older observation for the *same*
        # topic; a transport can therefore receive attributes before status.
        if last_for_topic is not None and observed_at < last_for_topic:
            self._invalid_error = "out-of-order observation"
            return False
        return True

    def _retained_view(self, reason: RetentionReason) -> RetainedSnapshot | None:
        return RetainedSnapshot(snapshot=self._retained, reason=reason) if self._retained is not None else None

    def _invalid(self, message: str) -> DriverObservation:
        return DriverObservation(
            phase=ConnectionPhase.INVALID,
            capabilities=frozenset(),
            retained=self._retained_view(RetentionReason.INVALID),
            error=message,
            session_id=self._active.session_id if self._active else None,
        )
