"""Owner-configured boundary for bounded Elegoo SDCP discovery."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.core.database import Base


class ElegooSDCPDiscoveryConfiguration(Base):
    """A singleton configuration; candidates are intentionally never stored."""

    __tablename__ = "elegoo_sdcp_discovery_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    private_ipv4_cidr: Mapped[str] = mapped_column(String(18), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    owner_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
