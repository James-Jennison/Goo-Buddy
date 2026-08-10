"""One owner-configured, bounded SDCP UDP discovery exchange.

This service does not enable sources, persist candidates, or open any
per-device connection.  Its sole network action is an ``M99999`` datagram to
the broadcast address calculated from the owner's validated private CIDR.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
from dataclasses import dataclass
from typing import Protocol

from backend.app.schemas.printer import canonical_private_discovery_cidr
from backend.app.services.elegoo_sdcp_read_only import validate_mainboard_id

DISCOVERY_PORT = 3000
DISCOVERY_MESSAGE = b"M99999"
DISCOVERY_TIMEOUT_SECONDS = 1.5
DISCOVERY_ATTEMPTS = 2
MAX_RESPONSE_BYTES = 8192
MAX_CANDIDATES = 32


@dataclass(frozen=True)
class DiscoveryDatagram:
    payload: bytes
    source_ipv4: str
    source_port: int


@dataclass(frozen=True)
class ElegooSDCPDiscoveryCandidate:
    private_ipv4: str
    mainboard_id: str
    name: str | None = None
    model: str | None = None
    protocol_version: str | None = None
    firmware: str | None = None


class DiscoveryTransport(Protocol):
    async def broadcast(
        self, *, broadcast_ipv4: str, port: int, message: bytes, attempts: int, timeout_seconds: float, max_bytes: int
    ) -> list[DiscoveryDatagram]: ...


class UDPSocketDiscoveryTransport:
    """Small stdlib-only UDP transport; it neither connects nor scans hosts."""

    async def broadcast(
        self, *, broadcast_ipv4: str, port: int, message: bytes, attempts: int, timeout_seconds: float, max_bytes: int
    ) -> list[DiscoveryDatagram]:
        if (
            port != DISCOVERY_PORT
            or message != DISCOVERY_MESSAGE
            or attempts != DISCOVERY_ATTEMPTS
            or timeout_seconds != DISCOVERY_TIMEOUT_SECONDS
            or max_bytes != MAX_RESPONSE_BYTES
        ):
            raise ValueError("invalid bounded SDCP discovery request")
        loop = asyncio.get_running_loop()
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.setblocking(False)
        received: list[DiscoveryDatagram] = []
        try:
            for _ in range(attempts):
                await loop.sock_sendto(udp_socket, message, (broadcast_ipv4, port))
                deadline = loop.time() + timeout_seconds
                while True:
                    remaining = deadline - loop.time()
                    if remaining <= 0:
                        break
                    try:
                        # Ask for one byte over the accepted limit. Datagram
                        # receives otherwise truncate silently, which could
                        # make an oversized response look valid.
                        payload, peer = await asyncio.wait_for(
                            loop.sock_recvfrom(udp_socket, max_bytes + 1), timeout=remaining
                        )
                    except asyncio.TimeoutError:
                        break
                    if len(payload) <= max_bytes and isinstance(peer, tuple) and len(peer) >= 2:
                        received.append(DiscoveryDatagram(payload, str(peer[0]), int(peer[1])))
        finally:
            udp_socket.close()
        return received


def _optional_text(record: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value and len(value) <= 100 and value.isprintable():
                return value
    return None


def _candidate_from_datagram(
    datagram: DiscoveryDatagram, network: ipaddress.IPv4Network
) -> ElegooSDCPDiscoveryCandidate | None:
    """Accept only a bounded JSON response from an in-bound network peer."""

    if datagram.source_port != DISCOVERY_PORT or len(datagram.payload) > MAX_RESPONSE_BYTES:
        return None
    try:
        source = ipaddress.IPv4Address(datagram.source_ipv4)
        payload = json.loads(datagram.payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ipaddress.AddressValueError):
        return None
    if source not in network or source in {network.network_address, network.broadcast_address}:
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("Data"), dict):
        return None
    data = payload["Data"]
    try:
        mainboard_id = validate_mainboard_id(data.get("MainboardID"))
    except ValueError:
        return None
    declared_ipv4 = _optional_text(data, "IPAddress", "IP", "MainboardIP")
    if declared_ipv4 is not None:
        try:
            if ipaddress.IPv4Address(declared_ipv4) != source:
                return None
        except ipaddress.AddressValueError:
            return None
    return ElegooSDCPDiscoveryCandidate(
        private_ipv4=str(source),
        mainboard_id=mainboard_id,
        name=_optional_text(data, "Name", "DeviceName"),
        model=_optional_text(data, "MachineName", "Model"),
        protocol_version=_optional_text(data, "ProtocolVersion", "SDCPVersion"),
        firmware=_optional_text(data, "FirmwareVersion"),
    )


class ElegooSDCPDiscoveryService:
    """Validate first, broadcast exactly once per bounded attempt, retain nothing."""

    def __init__(self, transport: DiscoveryTransport | None = None) -> None:
        self._transport = transport or UDPSocketDiscoveryTransport()

    async def discover(self, private_ipv4_cidr: str) -> list[ElegooSDCPDiscoveryCandidate]:
        canonical_cidr = canonical_private_discovery_cidr(private_ipv4_cidr)
        network = ipaddress.IPv4Network(canonical_cidr)
        packets = await self._transport.broadcast(
            broadcast_ipv4=str(network.broadcast_address),
            port=DISCOVERY_PORT,
            message=DISCOVERY_MESSAGE,
            attempts=DISCOVERY_ATTEMPTS,
            timeout_seconds=DISCOVERY_TIMEOUT_SECONDS,
            max_bytes=MAX_RESPONSE_BYTES,
        )
        candidates: dict[str, ElegooSDCPDiscoveryCandidate] = {}
        for packet in packets:
            candidate = _candidate_from_datagram(packet, network)
            if candidate is not None and candidate.mainboard_id not in candidates:
                candidates[candidate.mainboard_id] = candidate
                if len(candidates) == MAX_CANDIDATES:
                    break
        return list(candidates.values())


elegoo_sdcp_discovery = ElegooSDCPDiscoveryService()
