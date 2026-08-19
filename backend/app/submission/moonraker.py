"""Offline, fail-closed Moonraker C5 submission contract.

This module models the one documented Moonraker upload/start sequence without
opening a connection, reading artifact bytes, or exposing a dispatch method.
It is deliberately a serializer and response validator for a future adapter,
not that adapter.  A caller must persist the claimed start transition before
any later transport implementation sends the one permitted start request.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

from backend.app.core.compat import StrEnum
from backend.app.drivers.contract import ConnectionPhase, DriverKind, DriverObservation
from backend.app.submission.contract import PlatformSubmissionIntent


class MoonrakerSubmissionContractError(ValueError):
    """A supplied artifact, receipt, or state transition is outside C5."""


class MoonrakerSubmissionStage(StrEnum):
    """The closed local lifecycle for one future Moonraker submission."""

    PREPARED = "prepared"
    UPLOADED = "uploaded"
    START_DISPATCHED = "start-dispatched"
    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


_UPLOAD_ENDPOINT = "/server/files/upload"
_START_ENDPOINT = "/printer/print/start"
_ROOT = "gcodes"
_SAFE_GCODE_BASENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,95}\.gcode$", re.IGNORECASE)


@dataclass(frozen=True)
class MoonrakerGcodeArtifact:
    """A validated G-code identity without a path or its byte contents."""

    source_filename: str
    content_size_bytes: int

    def __post_init__(self) -> None:
        if not isinstance(self.source_filename, str) or not _SAFE_GCODE_BASENAME.fullmatch(self.source_filename):
            raise MoonrakerSubmissionContractError("Moonraker requires a safe .gcode artifact basename")
        if type(self.content_size_bytes) is not int or self.content_size_bytes < 1:
            raise MoonrakerSubmissionContractError("Moonraker artifact size must be a positive integer")


@dataclass(frozen=True)
class MoonrakerUploadRequest:
    """The exact bounded multipart upload shape, without body bytes."""

    filename: str
    checksum: str
    file_field: str = "file"
    root: str = _ROOT
    method: str = "POST"
    endpoint: str = _UPLOAD_ENDPOINT

    def __post_init__(self) -> None:
        if (
            self.method != "POST"
            or self.endpoint != _UPLOAD_ENDPOINT
            or self.root != _ROOT
            or self.file_field != "file"
            or not _SAFE_GCODE_BASENAME.fullmatch(self.filename)
            or not re.fullmatch(r"[a-f0-9]{64}", self.checksum)
        ):
            raise MoonrakerSubmissionContractError("invalid bounded Moonraker upload request")

    @property
    def optional_fields(self) -> Mapping[str, str]:
        """Only fields permitted beyond the multipart file itself.

        ``path`` and ``print`` are intentionally absent: path creation and
        upload-triggered starts are outside the C5 contract.
        """

        return MappingProxyType({"root": self.root, "checksum": self.checksum})


@dataclass(frozen=True)
class MoonrakerStartRequest:
    """One fixed HTTP start request; no JSON-RPC or generic G-code exists."""

    filename: str
    method: str = "POST"
    endpoint: str = _START_ENDPOINT

    def __post_init__(self) -> None:
        if (
            self.method != "POST"
            or self.endpoint != _START_ENDPOINT
            or not _SAFE_GCODE_BASENAME.fullmatch(self.filename)
        ):
            raise MoonrakerSubmissionContractError("invalid bounded Moonraker start request")

    @property
    def query(self) -> Mapping[str, str]:
        return MappingProxyType({"filename": self.filename})


@dataclass(frozen=True)
class MoonrakerUploadReceipt:
    """Validated, content-free acknowledgement of an exact upload plan."""

    filename: str
    size_bytes: int


@dataclass(frozen=True)
class MoonrakerSubmissionAttempt:
    """Immutable local state that makes a second start claim impossible."""

    intent: PlatformSubmissionIntent
    artifact: MoonrakerGcodeArtifact
    remote_filename: str
    stage: MoonrakerSubmissionStage = MoonrakerSubmissionStage.PREPARED
    receipt: MoonrakerUploadReceipt | None = None

    def __post_init__(self) -> None:
        if self.intent.driver is not DriverKind.MOONRAKER:
            raise MoonrakerSubmissionContractError("Moonraker attempt requires a Moonraker intent")
        if not _SAFE_GCODE_BASENAME.fullmatch(self.remote_filename):
            raise MoonrakerSubmissionContractError("invalid normalized Moonraker filename")
        if self.stage is MoonrakerSubmissionStage.UPLOADED and self.receipt is None:
            raise MoonrakerSubmissionContractError("uploaded attempt requires a validated receipt")
        if self.stage is MoonrakerSubmissionStage.PREPARED and self.receipt is not None:
            raise MoonrakerSubmissionContractError("prepared attempt cannot have a receipt")

    @property
    def upload_request(self) -> MoonrakerUploadRequest:
        if self.stage is not MoonrakerSubmissionStage.PREPARED:
            raise MoonrakerSubmissionContractError("upload is no longer available for this attempt")
        return MoonrakerUploadRequest(filename=self.remote_filename, checksum=self.intent.artifact.content_hash)

    def accept_upload_response(self, *, status_code: object, payload: object) -> MoonrakerSubmissionAttempt:
        """Validate the minimal documented success receipt without retaining it."""

        if self.stage is not MoonrakerSubmissionStage.PREPARED:
            raise MoonrakerSubmissionContractError("upload response is not expected for this attempt")
        if status_code != 201 or not isinstance(payload, Mapping):
            raise MoonrakerSubmissionContractError("Moonraker upload was not confirmed")
        item = payload.get("item")
        if not isinstance(item, Mapping):
            raise MoonrakerSubmissionContractError("Moonraker upload receipt has no item")
        if (
            item.get("root") != _ROOT
            or item.get("path") != self.remote_filename
            or item.get("size") != self.artifact.content_size_bytes
            or payload.get("action") != "create_file"
            or payload.get("print_started") is not False
            or payload.get("print_queued") is not False
        ):
            raise MoonrakerSubmissionContractError("Moonraker upload receipt violates the bounded contract")
        receipt = MoonrakerUploadReceipt(self.remote_filename, self.artifact.content_size_bytes)
        return replace(self, stage=MoonrakerSubmissionStage.UPLOADED, receipt=receipt)

    def claim_start_request(self) -> tuple[MoonrakerStartRequest, MoonrakerSubmissionAttempt]:
        """Atomically claim the sole start request and advance local state.

        A later transport must persist the returned ``START_DISPATCHED`` state
        before it opens the fixed endpoint.  Timeouts and lost acknowledgements
        therefore become unconfirmed outcomes, never automatic retries.
        """

        if self.stage is not MoonrakerSubmissionStage.UPLOADED or self.receipt is None:
            raise MoonrakerSubmissionContractError("Moonraker start is not available for this attempt")
        request = MoonrakerStartRequest(filename=self.receipt.filename)
        return request, replace(self, stage=MoonrakerSubmissionStage.START_DISPATCHED)

    def settle_from_observation(self, observation: DriverObservation) -> MoonrakerSubmissionAttempt:
        """Confirm only a fresh matching ``printing`` job; every other result is unconfirmed."""

        confirmed = (
            self.stage is MoonrakerSubmissionStage.START_DISPATCHED
            and observation.phase is ConnectionPhase.READY
            and observation.current is not None
            and observation.current.driver is DriverKind.MOONRAKER
            and observation.current.state == "printing"
            and observation.current.job is not None
            and observation.current.job.state == "printing"
            and observation.current.job.name == self.remote_filename
        )
        return replace(
            self,
            stage=MoonrakerSubmissionStage.CONFIRMED if confirmed else MoonrakerSubmissionStage.UNCONFIRMED,
        )


def prepare_moonraker_submission(
    intent: PlatformSubmissionIntent, artifact: MoonrakerGcodeArtifact
) -> MoonrakerSubmissionAttempt:
    """Create a deterministic remote basename; no file is opened or transferred."""

    if intent.driver is not DriverKind.MOONRAKER:
        raise MoonrakerSubmissionContractError("Moonraker preparation requires a Moonraker intent")
    # A content-addressed basename avoids raw user paths and prevents the
    # uploader from selecting a directory.  The source filename is validated
    # only as evidence that the local immutable artifact is G-code.
    remote_filename = f"goo-buddy-{intent.artifact.artifact_id}-{intent.artifact.content_hash[:16]}.gcode"
    return MoonrakerSubmissionAttempt(intent=intent, artifact=artifact, remote_filename=remote_filename)
