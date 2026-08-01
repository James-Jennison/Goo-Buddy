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
    configuration_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
