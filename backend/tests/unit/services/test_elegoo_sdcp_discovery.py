"""Deterministic safety coverage for owner-bounded SDCP discovery."""

import json

import pytest

from backend.app.schemas.printer import canonical_private_discovery_cidr
from backend.app.services.elegoo_sdcp_discovery import (
    DISCOVERY_ATTEMPTS,
    DISCOVERY_MESSAGE,
    DISCOVERY_PORT,
    MAX_RESPONSE_BYTES,
    DiscoveryDatagram,
    ElegooSDCPDiscoveryService,
)


class _FixtureTransport:
    def __init__(self, packets: list[DiscoveryDatagram]) -> None:
        self.packets = packets
        self.calls: list[dict[str, object]] = []

    async def broadcast(self, **kwargs) -> list[DiscoveryDatagram]:
        self.calls.append(kwargs)
        return self.packets


def _response(mainboard_id: str, **data: object) -> bytes:
    return json.dumps({"Data": {"MainboardID": mainboard_id, **data}}).encode()


@pytest.mark.parametrize(
    "value",
    [
        "192.168.1.0/23",
        "192.168.1.1/24",
        "192.168.1.0/31",
        "127.0.0.0/24",
        "169.254.0.0/24",
        "224.0.0.0/24",
        "8.8.8.0/24",
        "192.0.2.0/24",
        "printer.local/24",
        "192.168.1.0/24 ",
    ],
)
def test_discovery_cidr_rejects_non_private_noncanonical_or_unbounded_targets(value: str):
    with pytest.raises(ValueError, match="bounded private"):
        canonical_private_discovery_cidr(value)


@pytest.mark.asyncio
async def test_discovery_sends_only_the_documented_broadcast_request():
    transport = _FixtureTransport([])
    service = ElegooSDCPDiscoveryService(transport)

    assert await service.discover("192.168.50.0/24") == []
    assert transport.calls == [
        {
            "broadcast_ipv4": "192.168.50.255",
            "port": DISCOVERY_PORT,
            "message": DISCOVERY_MESSAGE,
            "attempts": DISCOVERY_ATTEMPTS,
            "timeout_seconds": 1.5,
            "max_bytes": MAX_RESPONSE_BYTES,
        }
    ]


@pytest.mark.asyncio
async def test_discovery_validates_and_deduplicates_ephemeral_candidates_without_followup_contact():
    valid = DiscoveryDatagram(
        _response(
            "synthetic-board-01",
            IPAddress="192.168.50.22",
            Name="Synthetic CC1",
            MachineName="Centauri Carbon",
            ProtocolVersion="v3",
            FirmwareVersion="fixture",
        ),
        "192.168.50.22",
        3000,
    )
    transport = _FixtureTransport(
        [
            valid,
            valid,
            DiscoveryDatagram(_response("other", IPAddress="192.168.51.22"), "192.168.51.22", 3000),
            DiscoveryDatagram(b"not-json", "192.168.50.23", 3000),
            DiscoveryDatagram(_response("wrong-peer", IPAddress="192.168.50.99"), "192.168.50.24", 3000),
            DiscoveryDatagram(_response("wrong-port"), "192.168.50.25", 3001),
            DiscoveryDatagram(b"x" * (MAX_RESPONSE_BYTES + 1), "192.168.50.26", 3000),
        ]
    )
    service = ElegooSDCPDiscoveryService(transport)

    candidates = await service.discover("192.168.50.0/24")
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.private_ipv4 == "192.168.50.22"
    assert candidate.mainboard_id == "synthetic-board-01"
    assert candidate.name == "Synthetic CC1"
    assert candidate.model == "Centauri Carbon"
    # Discovery performs one broadcast only. Candidate follow-up is owned by
    # the manager and can be called only by the route with these validated
    # candidates; this service never opens HTTP, RTSP, media, or control.
    assert len(transport.calls) == 1
