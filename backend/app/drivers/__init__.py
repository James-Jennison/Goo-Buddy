"""Read-only, capability-based printer driver foundations.

This package intentionally has no network, persistence, command, or discovery
surface. Transport activation belongs to a later, separately reviewed goal.
"""

from backend.app.drivers.contract import (
    Capability,
    ConnectionPhase,
    DriverObservation,
    DriverProtocol,
    NormalizedPrinterSnapshot,
)

__all__ = [
    "Capability",
    "ConnectionPhase",
    "DriverObservation",
    "DriverProtocol",
    "NormalizedPrinterSnapshot",
]
