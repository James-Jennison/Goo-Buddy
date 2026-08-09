"""Persisted audit ledger for closed non-Bambu printer-control commands."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class PlatformControlCommand(Base):
    """One explicit, capability-gated platform control request.

    The row deliberately carries operation metadata only.  Protocol adapters
    derive their fixed command from ``driver`` and ``operation``; no raw
    payload can be stored or replayed through this audit ledger.
    """

    __tablename__ = "platform_control_commands"

    id: Mapped[int] = mapped_column(primary_key=True)
    driver: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[int] = mapped_column(Integer)
    configuration_revision: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    idempotency_key: Mapped[str] = mapped_column(String(32), unique=True)
    requested_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    requested_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error_code: Mapped[str | None] = mapped_column(String(64))
