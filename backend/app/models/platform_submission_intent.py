"""Operation-only C5 audit records; no transfer or printer command fields."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class PlatformSubmissionIntent(Base):
    """One local, bounded intent for a future evidence-backed submission.

    The row persists source/artifact identities and their hashes only. It does
    not contain a printer path, raw filename, URL, request body, credential,
    G-code, file bytes, or transport command.
    """

    __tablename__ = "platform_submission_intents"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[int] = mapped_column(Integer)
    configuration_revision: Mapped[int] = mapped_column(Integer)
    target_label: Mapped[str] = mapped_column(String(100))
    artifact_kind: Mapped[str] = mapped_column(String(16))
    artifact_id: Mapped[int] = mapped_column(Integer)
    artifact_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="draft")
    idempotency_key: Mapped[str] = mapped_column(String(32), unique=True)
    requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(64))
