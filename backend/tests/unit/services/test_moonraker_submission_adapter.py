"""In-memory tests for the dormant, fixed Moonraker C5.3 adapter."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import aiohttp
import pytest

from backend.app.drivers.contract import (
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
)
from backend.app.drivers.moonraker import MoonrakerDriver
from backend.app.services.moonraker_manager import MoonrakerManager, _LiveMoonraker
from backend.app.submission.contract import (
    PlatformSubmissionUnconfirmed,
    SubmissionArtifactKind,
    SubmissionArtifactReference,
    new_platform_submission_intent,
)
from backend.app.submission.evidence import SubmissionAcknowledgement
from backend.app.submission.moonraker import MoonrakerGcodeArtifact, prepare_moonraker_submission


class _Content:
    def __init__(self, body: bytes = b"") -> None:
        self._body = body

    async def read(self, limit: int) -> bytes:
        assert limit >= len(self._body)
        return self._body


class _Response:
    def __init__(self, status: int, *, content_type: str = "application/json", body: bytes = b"") -> None:
        self.status = status
        self.content_type = content_type
        self.content = _Content(body)

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class StrictMoonrakerSubmissionPeer:
    """Accept exactly one upload and one fixed start; never open a socket."""

    def __init__(self, base_url: str, filename: str, checksum: str) -> None:
        self.base_url = base_url
        self.filename = filename
        self.checksum = checksum
        self.calls: list[str] = []

    def post(self, url: str, **kwargs: object) -> _Response:
        if url == f"{self.base_url}/server/files/upload":
            assert set(kwargs) == {"data", "allow_redirects"}
            assert kwargs["allow_redirects"] is False
            form = kwargs["data"]
            assert isinstance(form, aiohttp.FormData)
            fields = {field[0]["name"]: field for field in form._fields}
            field_values = {name: field[2] for name, field in fields.items()}
            assert field_values == {"file": field_values["file"], "root": "gcodes", "checksum": self.checksum}
            assert fields["file"][0]["filename"] == self.filename
            self.calls.append("upload")
            return _Response(
                201,
                body=json.dumps(
                    {
                        "item": {"root": "gcodes", "path": self.filename, "size": 14},
                        "print_started": False,
                        "print_queued": False,
                        "action": "create_file",
                    }
                ).encode(),
            )
        if url == f"{self.base_url}/printer/print/start":
            assert kwargs == {"params": {"filename": self.filename}, "allow_redirects": False}
            self.calls.append("start")
            return _Response(200, content_type="text/plain")
        raise AssertionError("unsupported Moonraker submission request")


def _attempt():
    content = b"G1 X1\n;fixture"
    checksum = hashlib.sha256(content).hexdigest()
    intent = new_platform_submission_intent(
        DriverKind.MOONRAKER,
        source_id=7,
        configuration_revision=3,
        target_label="Synthetic Moonraker",
        artifact=SubmissionArtifactReference(SubmissionArtifactKind.LIBRARY_FILE, 4, checksum),
        idempotency_key="b" * 32,
    )
    return prepare_moonraker_submission(intent, MoonrakerGcodeArtifact("fixture.gcode", len(content))), content


def _observation(state: str, filename: str | None = None) -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity("fixture", "Synthetic Moonraker", model="fixture-model", firmware="fixture-firmware"),
        driver=DriverKind.MOONRAKER,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=frozenset(),
        job=JobProgress(name=filename, state=state) if filename is not None else None,
    )
    return DriverObservation(ConnectionPhase.READY, frozenset(), current=snapshot)


def _live(attempt) -> _LiveMoonraker:
    acknowledgement = SubmissionAcknowledgement(3, "fixture-model", "fixture-firmware", "moonraker-c5.1")
    return _LiveMoonraker(
        7,
        "Synthetic Moonraker",
        "192.168.1.44",
        7125,
        "http",
        None,
        MoonrakerDriver("moonraker-7", "Synthetic Moonraker"),
        configuration_revision=3,
        submission_enabled=True,
        submission_acknowledgement=acknowledgement,
    )


@pytest.mark.asyncio
async def test_dormant_submission_adapter_uses_only_fixed_upload_then_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    attempt, content = _attempt()
    live = _live(attempt)
    peer = StrictMoonrakerSubmissionPeer(
        "http://192.168.1.44:7125", attempt.remote_filename, attempt.intent.artifact.content_hash
    )
    live.client = peer  # type: ignore[assignment]
    manager._sources[7] = live
    observations = iter(
        [
            _observation("idle"),
            _observation("idle"),
            _observation("idle"),
            _observation("printing", attempt.remote_filename),
        ]
    )
    monkeypatch.setattr(manager, "observation", lambda _source_id: next(observations))

    assert await manager.dispatch_submission(attempt, content) is True
    assert peer.calls == ["upload", "start"]


@pytest.mark.asyncio
async def test_submission_adapter_never_contacts_a_source_without_its_separate_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    attempt, content = _attempt()
    live = _live(attempt)
    live.submission_enabled = False
    peer = StrictMoonrakerSubmissionPeer(
        "http://192.168.1.44:7125", attempt.remote_filename, attempt.intent.artifact.content_hash
    )
    live.client = peer  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _observation("idle"))

    assert await manager.dispatch_submission(attempt, content) is False
    assert peer.calls == []


@pytest.mark.asyncio
async def test_submission_adapter_rejects_any_content_hash_or_size_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    attempt, content = _attempt()
    live = _live(attempt)
    peer = StrictMoonrakerSubmissionPeer(
        "http://192.168.1.44:7125", attempt.remote_filename, attempt.intent.artifact.content_hash
    )
    live.client = peer  # type: ignore[assignment]
    manager._sources[7] = live
    monkeypatch.setattr(manager, "observation", lambda _source_id: _observation("idle"))

    assert await manager.dispatch_submission(attempt, content + b"!") is False
    assert peer.calls == []


@pytest.mark.asyncio
async def test_manager_enable_never_restores_submission_from_a_boolean_without_exact_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    monkeypatch.setattr(manager, "_run", AsyncMock())

    await manager.enable(
        7,
        "Synthetic Moonraker",
        "192.168.1.44",
        7125,
        "http",
        None,
        configuration_revision=3,
        submission_enabled=True,
    )

    assert manager._sources[7].submission_enabled is False
    assert manager._sources[7].submission_acknowledgement is None
    await manager.disable(7)


@pytest.mark.asyncio
async def test_submission_adapter_never_retries_a_start_without_fresh_matching_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = MoonrakerManager()
    attempt, content = _attempt()
    live = _live(attempt)
    peer = StrictMoonrakerSubmissionPeer(
        "http://192.168.1.44:7125", attempt.remote_filename, attempt.intent.artifact.content_hash
    )
    live.client = peer  # type: ignore[assignment]
    manager._sources[7] = live
    observations = iter([_observation("idle"), _observation("idle"), _observation("idle")])
    monkeypatch.setattr(manager, "observation", lambda _source_id: next(observations))
    monkeypatch.setattr(manager, "_await_submission_confirmation", AsyncMock(return_value=False))

    with pytest.raises(PlatformSubmissionUnconfirmed):
        await manager.dispatch_submission(attempt, content)
    assert peer.calls == ["upload", "start"]
