"""Tests for C5.0's inert cross-platform submission contract."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core import database
from backend.app.drivers.contract import (
    Capability,
    ConnectionPhase,
    DriverKind,
    DriverObservation,
    NormalizedPrinterSnapshot,
    PrinterIdentity,
)
from backend.app.submission.contract import (
    PlatformSubmissionState,
    SubmissionArtifactKind,
    SubmissionArtifactReference,
    new_platform_submission_intent,
    submission_operation_is_available,
)

_HASH = "a" * 64


def _observation(*, driver: DriverKind, state: str, capabilities: frozenset[Capability]) -> DriverObservation:
    snapshot = NormalizedPrinterSnapshot(
        identity=PrinterIdentity("fixture-printer", "Fixture printer"),
        driver=driver,
        observed_at=datetime.now(timezone.utc),
        state=state,
        capabilities=capabilities,
    )
    return DriverObservation(ConnectionPhase.READY, capabilities, current=snapshot)


@pytest.mark.parametrize("driver", [DriverKind.BAMBU, DriverKind.ELEGOO_SDCP_V3, DriverKind.MOONRAKER])
def test_submission_intent_is_local_and_closed(driver: DriverKind) -> None:
    artifact = SubmissionArtifactReference(SubmissionArtifactKind.ARCHIVE, 7, _HASH)
    intent = new_platform_submission_intent(driver, 5, 2, "Configured printer", artifact)

    assert intent.driver is driver
    assert intent.artifact == artifact
    assert len(intent.idempotency_key) == 32
    assert PlatformSubmissionState.DRAFT.value == "draft"


@pytest.mark.parametrize(
    "artifact",
    [
        ("archive", 7, _HASH),
        (SubmissionArtifactKind.ARCHIVE, 0, _HASH),
        (SubmissionArtifactKind.LIBRARY_FILE, 3, "not-a-hash"),
    ],
)
def test_submission_artifact_reference_rejects_unbounded_or_unverified_inputs(
    artifact: tuple[object, object, object],
) -> None:
    with pytest.raises(ValueError):
        SubmissionArtifactReference(*artifact)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("driver", "idle_state"),
    [
        (DriverKind.BAMBU, "IDLE"),
        (DriverKind.ELEGOO_SDCP_V3, "idle"),
        (DriverKind.MOONRAKER, "idle"),
    ],
)
def test_submission_is_default_off_even_for_an_idle_printer(driver: DriverKind, idle_state: str) -> None:
    default_off = _observation(driver=driver, state=idle_state, capabilities=frozenset({Capability.JOB_STATUS}))
    assert not submission_operation_is_available(default_off)

    explicitly_granted = _observation(
        driver=driver,
        state=idle_state,
        capabilities=frozenset({Capability.JOB_STATUS, Capability.JOB_SUBMISSION}),
    )
    assert submission_operation_is_available(explicitly_granted)
    assert not submission_operation_is_available(
        _observation(
            driver=driver,
            state="printing" if driver is not DriverKind.BAMBU else "RUNNING",
            capabilities=frozenset({Capability.JOB_SUBMISSION}),
        )
    )


@pytest.mark.asyncio
async def test_submission_intent_migration_is_closed_and_contains_no_transport_surface(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            await database._migrate_platform_submission_intents(conn)
            await database._migrate_platform_submission_intents(conn)
            await conn.execute(
                text(
                    "INSERT INTO platform_submission_intents "
                    "(driver, source_id, configuration_revision, target_label, artifact_kind, artifact_id, "
                    "artifact_hash, status, idempotency_key) VALUES "
                    "('moonraker', 4, 1, 'Fixture printer', 'archive', 9, :artifact_hash, 'draft', :idempotency_key)"
                ),
                {"artifact_hash": _HASH, "idempotency_key": "b" * 32},
            )
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text(
                        "INSERT INTO platform_submission_intents "
                        "(driver, source_id, configuration_revision, target_label, artifact_kind, artifact_id, "
                        "artifact_hash, idempotency_key) VALUES "
                        "('moonraker', 4, 1, 'Fixture printer', 'path', 9, :artifact_hash, :idempotency_key)"
                    ),
                    {"artifact_hash": _HASH, "idempotency_key": "c" * 32},
                )
            columns = (await conn.execute(text("PRAGMA table_info(platform_submission_intents)"))).all()
            column_names = {column[1] for column in columns}
            assert {"file_path", "destination", "payload", "command", "url", "credential"}.isdisjoint(column_names)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_interrupted_submission_states_fail_closed_without_a_replay(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            await database._migrate_platform_submission_intents(conn)
            for status, key in (("draft", "c"), ("queued", "d"), ("transferring", "e"), ("starting", "f")):
                await conn.execute(
                    text(
                        "INSERT INTO platform_submission_intents "
                        "(driver, source_id, configuration_revision, target_label, artifact_kind, artifact_id, "
                        "artifact_hash, status, idempotency_key) VALUES "
                        "('moonraker', 4, 1, 'Fixture printer', 'library-file', 9, :artifact_hash, :status, :key)"
                    ),
                    {"artifact_hash": _HASH, "status": status, "key": key * 32},
                )
            await database._reconcile_interrupted_platform_submission_intents(conn)
            rows = (
                await conn.execute(text("SELECT status, error_code FROM platform_submission_intents ORDER BY id"))
            ).all()
            assert rows == [
                ("draft", None),
                ("failed", "restart_interrupted"),
                ("failed", "restart_interrupted"),
                ("failed", "restart_interrupted"),
            ]
    finally:
        await engine.dispose()
