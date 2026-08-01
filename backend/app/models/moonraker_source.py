"""Persisted, opt-in Moonraker read-only monitoring sources.

This is intentionally separate from both ``printers`` (Bambu) and the SDCP
source table.  A Moonraker row can never enter a Bambu command/queue path and
cannot be mistaken for an operational Klipper integration.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base
from backend.app.core.encryption import mfa_decrypt, mfa_encrypt


class MoonrakerSource(Base):
    __tablename__ = "moonraker_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100))
    # These values are never serialized in normal APIs or logger calls.
    private_ipv4: Mapped[str] = mapped_column(String(15), unique=True)
    port: Mapped[int] = mapped_column(Integer, default=7125)
    scheme: Mapped[str] = mapped_column(String(5), default="http")
    _api_key_enc: Mapped[str | None] = mapped_column("api_key", String(2048), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    read_only_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    configuration_revision: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    @property
    def api_key(self) -> str | None:
        return mfa_decrypt(self._api_key_enc) if self._api_key_enc else None

    @api_key.setter
    def api_key(self, value: str | None) -> None:
        self._api_key_enc = mfa_encrypt(value) if value else None
