"""Persisted, opt-in read-only SDCP v3 sources.

This deliberately does not reuse ``printers``: that table is the mature
Bambu/MQTT configuration contract and requires a serial number and access
code. Keeping the source isolated prevents an Elegoo row from entering any
Bambu command, queue, FTP, camera, or discovery path.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class ElegooSDCPSource(Base):
    __tablename__ = "elegoo_sdcp_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    # Never serialize or log this field. It is accepted only after strict
    # RFC1918 validation and is used solely to construct the fixed SDCP URL.
    private_ipv4: Mapped[str] = mapped_column(String(15), unique=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    read_only_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    # C4 starts fail-closed. This is intentionally not exposed through the
    # read-only source API; a later, evidence-backed owner-acknowledgement
    # milestone may enable it for an approved source/revision.
    control_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # C4.2 acknowledgement is deliberately separate from the read-only
    # acknowledgement. It captures only the exact evidence identity and
    # allowlisted operation names, never protocol payloads or endpoints.
    control_acknowledged_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    control_acknowledged_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    control_acknowledged_firmware: Mapped[str | None] = mapped_column(String(100), nullable=True)
    control_acknowledged_operations: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # C5 owner acknowledgement is separate from monitoring and C4 controls.
    # No current evidence can set this true; the additive fields are a
    # fail-closed upgrade boundary for a later source-specific validation.
    submission_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    submission_acknowledged_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submission_acknowledged_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submission_acknowledged_firmware: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submission_acknowledged_contract: Mapped[str | None] = mapped_column(String(64), nullable=True)
    configuration_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
