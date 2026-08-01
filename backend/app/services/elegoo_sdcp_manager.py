"""Opt-in, passive SDCP v3 WebSocket lifecycle.

No request, command, G-code, discovery, credential, ping, or heartbeat is
sent by this module. A connection is useful only when the printer itself
pushes documented status and attributes envelopes.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import socket
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import aiohttp

from backend.app.drivers.contract import ConnectionPhase, DriverObservation
from backend.app.drivers.elegoo_sdcp_v3 import SyntheticElegooSdcpV3Driver
from backend.app.schemas.printer import canonical_rfc1918_ipv4

CONNECT_TIMEOUT_SECONDS = 8
HANDSHAKE_TIMEOUT_SECONDS = 12
MAX_FRAME_BYTES = 128 * 1024
STALE_AFTER = timedelta(seconds=45)
MAX_BACKOFF_SECONDS = 60


@dataclass
class _LiveSource:
    source_id: int
    private_ipv4: str
    driver: SyntheticElegooSdcpV3Driver
    task: asyncio.Task[None] | None = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    connected: bool = False
    reconnecting: bool = False
    error: str | None = None
    _payload_hashes: dict[str, str] = field(default_factory=dict)


class ElegooSDCPManager:
    """Owns explicitly enabled SDCP connections and exposes safe observations."""

    def __init__(self) -> None:
        self._sources: dict[int, _LiveSource] = {}

    async def enable(self, source_id: int, private_ipv4: str) -> None:
        # This is intentionally repeated at the I/O boundary. Callers outside
        # the API (including boot restoration) must not be able to direct the
        # transport to a hostname, public address, URL, or alternate endpoint.
        private_ipv4 = canonical_rfc1918_ipv4(private_ipv4)
        await self.disable(source_id)
        live = _LiveSource(
            source_id=source_id,
            private_ipv4=private_ipv4,
            driver=SyntheticElegooSdcpV3Driver(f"elegoo-{source_id}", stale_after=STALE_AFTER),
        )
        self._sources[source_id] = live
        live.task = asyncio.create_task(self._run(live), name=f"elegoo-sdcp-{source_id}")

    async def disable(self, source_id: int) -> None:
        live = self._sources.pop(source_id, None)
        if live is None:
            return
        live.stop.set()
        if live.task and live.task is not asyncio.current_task():
            live.task.cancel()
            try:
                await live.task
            except asyncio.CancelledError:
                pass

    async def shutdown(self) -> None:
        await asyncio.gather(*(self.disable(source_id) for source_id in list(self._sources)), return_exceptions=True)

    def observation(self, source_id: int, now: datetime | None = None) -> DriverObservation:
        live = self._sources.get(source_id)
        if live is None:
            return DriverObservation(phase=ConnectionPhase.DISCONNECTED, capabilities=frozenset())
        observation = live.driver.observation(now or datetime.now(timezone.utc))
        if live.connected and observation.phase is ConnectionPhase.CONNECTING:
            return DriverObservation(
                phase=ConnectionPhase.WAITING,
                capabilities=frozenset(),
                session_id=observation.session_id,
            )
        if live.reconnecting and observation.phase is ConnectionPhase.DISCONNECTED:
            return DriverObservation(
                phase=ConnectionPhase.RECONNECTING,
                capabilities=observation.capabilities,
                retained=observation.retained,
                error=live.error,
            )
        if live.error and observation.error is None and observation.phase is not ConnectionPhase.READY:
            return DriverObservation(
                phase=observation.phase,
                capabilities=observation.capabilities,
                current=observation.current,
                retained=observation.retained,
                error=live.error,
                session_id=observation.session_id,
            )
        return observation

    async def _run(self, live: _LiveSource) -> None:
        attempt = 0
        while not live.stop.is_set():
            session_id = uuid.uuid4().hex
            live.driver.start_session(session_id)
            live.connected = False
            live.reconnecting = attempt > 0
            try:
                timeout = aiohttp.ClientTimeout(total=HANDSHAKE_TIMEOUT_SECONDS, sock_connect=CONNECT_TIMEOUT_SECONDS)
                # The only endpoint accepted by the source schema is the fixed
                # documented WebSocket path. Never include endpoint in logging.
                url = f"ws://{live.private_ipv4}:3030/websocket"
                connector = aiohttp.TCPConnector(family=socket.AF_INET, use_dns_cache=False)
                async with (
                    aiohttp.ClientSession(timeout=timeout, connector=connector) as session,
                    session.ws_connect(
                        url,
                        heartbeat=None,
                        autoping=False,
                        max_msg_size=MAX_FRAME_BYTES,
                    ) as websocket,
                ):
                    live.connected = True
                    live.reconnecting = False
                    live.error = None
                    await self._consume(websocket, live, session_id)
            except asyncio.CancelledError:
                live.driver.disconnect(session_id)
                raise
            except asyncio.TimeoutError:
                live.error = "connection_timeout"
            except aiohttp.WSServerHandshakeError:
                live.error = "handshake_failed"
            except aiohttp.ClientError:
                live.error = "connection_failed"
            except Exception:  # defensive: no exception text may contain endpoint/payload
                live.error = "connection_failed"
            finally:
                live.connected = False
                live.driver.disconnect(session_id)

            if live.stop.is_set():
                break
            attempt += 1
            live.reconnecting = True
            delay = min(MAX_BACKOFF_SECONDS, 1 * (2 ** min(attempt, 6)))
            # Bounded jitter prevents synchronized reconnect bursts after a Pi
            # or printer reboot while still making tests deterministic by patching random.
            delay += random.uniform(0, min(1.0, delay * 0.1))
            try:
                await asyncio.wait_for(live.stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                continue

    async def _consume(self, websocket: aiohttp.ClientWebSocketResponse, live: _LiveSource, session_id: str) -> None:
        async for message in websocket:
            if live.stop.is_set():
                return
            if message.type is aiohttp.WSMsgType.TEXT:
                raw = message.data
                if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_FRAME_BYTES:
                    live.error = "oversized_frame"
                    return
                self._observe_text(live, session_id, raw)
            elif message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSING):
                return
            elif message.type is aiohttp.WSMsgType.ERROR:
                live.error = "connection_closed"
                return
            # Binary, ping and unknown WebSocket frames are deliberately ignored.

    def _observe_text(self, live: _LiveSource, session_id: str, raw: str) -> None:
        try:
            envelope = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            live.error = "invalid_json"
            return
        if not isinstance(envelope, dict):
            live.error = "invalid_envelope"
            return
        topic = envelope.get("Topic")
        if not isinstance(topic, str):
            live.error = "invalid_envelope"
            return
        status_prefix = "sdcp/status/"
        attributes_prefix = "sdcp/attributes/"
        if topic.startswith(status_prefix) and len(topic) > len(status_prefix):
            kind = "status"
        elif topic.startswith(attributes_prefix) and len(topic) > len(attributes_prefix):
            kind = "attributes"
        else:
            # A future topic is not an error and never becomes a capability.
            return
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        if live._payload_hashes.get(kind) == digest:
            return
        live._payload_hashes[kind] = digest
        observed_at = datetime.now(timezone.utc)
        if kind == "status":
            live.driver.observe_status(session_id, envelope, observed_at)
        else:
            live.driver.observe_attributes(session_id, envelope, observed_at)


elegoo_sdcp_manager = ElegooSDCPManager()
