"""Deterministic C5.1 tests for the offline Moonraker submission contract."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone

import pytest

from backend.app.drivers.contract import (
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    JobProgress,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
)
from backend.app.submission.contract import (
    SubmissionArtifactKind,
    SubmissionArtifactReference,
    new_platform_submission_intent,
)
from backend.app.submission.moonraker import (
    MoonrakerGcodeArtifact,
    MoonrakerSubmissionContractError,
    MoonrakerSubmissionStage,
    prepare_moonraker_submission,
)

_HASH = "a" * 64


def _intent() -> object:
    return new_platform_submission_intent(
        DriverKind.MOONRAKER,
        source_id=7,
        configuration_revision=2,
        target_label="Moonraker fixture",
        artifact=SubmissionArtifactReference(SubmissionArtifactKind.LIBRARY_FILE, 5, _HASH),
        idempotency_key="b" * 32,
    )


def _artifact() -> MoonrakerGcodeArtifact:
    return MoonrakerGcodeArtifact("fixture-print.gcode", 321)


def _upload_payload(filename: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "item": {"root": "gcodes", "path": filename, "size": 321},
        "print_started": False,
        "print_queued": False,
        "action": "create_file",
    }
    payload.update(overrides)
    return payload


def _observation(
    *, filename: str, state: str = "printing", phase: ConnectionPhase = ConnectionPhase.READY
) -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity("moonraker-fixture", "Moonraker fixture"),
        driver=DriverKind.MOONRAKER,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=frozenset(),
        job=JobProgress(name=filename, state=state),
    )
    return DriverObservation(phase, frozenset(), current=snapshot if phase is ConnectionPhase.READY else None)


def test_moonraker_contract_is_a_closed_no_network_serializer() -> None:
    attempt = prepare_moonraker_submission(_intent(), _artifact())  # type: ignore[arg-type]
    request = attempt.upload_request

    assert request.method == "POST"
    assert request.endpoint == "/server/files/upload"
    assert request.file_field == "file"
    assert request.filename == "goo-buddy-5-aaaaaaaaaaaaaaaa.gcode"
    assert dict(request.optional_fields) == {"root": "gcodes", "checksum": _HASH}
    assert "path" not in request.optional_fields
    assert "print" not in request.optional_fields
    assert "socket" not in inspect.getsource(prepare_moonraker_submission)
    assert "aiohttp" not in inspect.getsource(prepare_moonraker_submission)


@pytest.mark.parametrize(
    ("filename", "size"),
    [
        ("../unsafe.gcode", 1),
        ("subdir/unsafe.gcode", 1),
        ("unsafe.g", 1),
        ("unsafe.gcode\\x00", 1),
        ("unsafe.gcode", 0),
    ],
)
def test_moonraker_contract_rejects_unallowed_artifact_inputs(filename: str, size: int) -> None:
    with pytest.raises(MoonrakerSubmissionContractError):
        MoonrakerGcodeArtifact(filename, size)


def test_upload_receipt_requires_exact_root_name_size_and_no_implicit_start() -> None:
    prepared = prepare_moonraker_submission(_intent(), _artifact())  # type: ignore[arg-type]
    uploaded = prepared.accept_upload_response(
        status_code=201,
        payload=_upload_payload(prepared.remote_filename),
    )

    assert uploaded.stage is MoonrakerSubmissionStage.UPLOADED
    assert uploaded.receipt is not None
    assert uploaded.receipt.filename == prepared.remote_filename

    invalid_responses = [
        (422, _upload_payload(prepared.remote_filename)),
        (201, _upload_payload(prepared.remote_filename, print_started=True)),
        (201, _upload_payload(prepared.remote_filename, print_queued=True)),
        (201, _upload_payload("different.gcode")),
        (
            201,
            _upload_payload(
                prepared.remote_filename, item={"root": "config", "path": prepared.remote_filename, "size": 321}
            ),
        ),
        (
            201,
            _upload_payload(
                prepared.remote_filename, item={"root": "gcodes", "path": prepared.remote_filename, "size": 320}
            ),
        ),
    ]
    for status_code, payload in invalid_responses:
        with pytest.raises(MoonrakerSubmissionContractError):
            prepared.accept_upload_response(status_code=status_code, payload=payload)


def test_start_can_be_claimed_once_then_requires_fresh_matching_printing_observation() -> None:
    prepared = prepare_moonraker_submission(_intent(), _artifact())  # type: ignore[arg-type]
    uploaded = prepared.accept_upload_response(status_code=201, payload=_upload_payload(prepared.remote_filename))
    start_request, dispatched = uploaded.claim_start_request()

    assert start_request.method == "POST"
    assert start_request.endpoint == "/printer/print/start"
    assert dict(start_request.query) == {"filename": prepared.remote_filename}
    assert dispatched.stage is MoonrakerSubmissionStage.START_DISPATCHED
    with pytest.raises(MoonrakerSubmissionContractError):
        dispatched.claim_start_request()

    assert (
        dispatched.settle_from_observation(_observation(filename=prepared.remote_filename)).stage
        is MoonrakerSubmissionStage.CONFIRMED
    )
    assert (
        dispatched.settle_from_observation(_observation(filename="other.gcode")).stage
        is MoonrakerSubmissionStage.UNCONFIRMED
    )
    assert (
        dispatched.settle_from_observation(
            _observation(filename=prepared.remote_filename, phase=ConnectionPhase.STALE)
        ).stage
        is MoonrakerSubmissionStage.UNCONFIRMED
    )


def test_moonraker_contract_rejects_a_non_moonraker_intent() -> None:
    non_moonraker = new_platform_submission_intent(
        DriverKind.ELEGOO_SDCP_V3,
        source_id=7,
        configuration_revision=2,
        target_label="Other fixture",
        artifact=SubmissionArtifactReference(SubmissionArtifactKind.LIBRARY_FILE, 5, _HASH),
        idempotency_key="c" * 32,
    )
    with pytest.raises(MoonrakerSubmissionContractError):
        prepare_moonraker_submission(non_moonraker, _artifact())
