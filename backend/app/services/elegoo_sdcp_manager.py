"""Opt-in SDCP v3 lifecycle with a closed, non-mutating request allowlist.

The transport can emit only the documented text ``ping`` heartbeat plus Cmd 0
(status refresh) and Cmd 1 (attributes).  It cannot construct arbitrary SDCP
commands, issue G-code, discover a subnet, or use an alternate endpoint.
"""

from __future__ import annotations

import asyncio
import json
import random
import socket
import time
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

import aiohttp

from backend.app.control.contract import (
    PlatformControlCommand,
    PlatformControlOperation,
    PlatformControlUnconfirmed,
    control_operation_is_available,
)
from backend.app.control.evidence import ControlAcknowledgement, acknowledgement_matches_observation
from backend.app.control.reconciliation import observation_satisfies_reconciliation
from backend.app.drivers.contract import Capability, ConnectionPhase, DriverKind, DriverObservation
from backend.app.drivers.elegoo_sdcp_v3 import SyntheticElegooSdcpV3Driver
from backend.app.schemas.printer import canonical_rfc1918_ipv4
from backend.app.services.elegoo_sdcp_control import serialize_control_request
from backend.app.services.elegoo_sdcp_read_only import (
    ReadOnlyInformationOperation,
    mainboard_id_from_discovery,
    serialize_heartbeat,
    serialize_information_request,
    validate_mainboard_id,
)

CONNECT_TIMEOUT_SECONDS = 8
HANDSHAKE_TIMEOUT_SECONDS = 12
MAX_FRAME_BYTES = 128 * 1024
STALE_AFTER = timedelta(seconds=45)
MAX_BACKOFF_SECONDS = 60
PASSIVE_IDENTITY_WAIT_SECONDS = 1
IDENTITY_DISCOVERY_TIMEOUT_SECONDS = 2
PONG_TIMEOUT_SECONDS = 5
NO_INBOUND_TRAFFIC_TIMEOUT_SECONDS = 45
# SDCP status and attributes are explicitly requested through the documented
# Cmd 0/1 allowlist. Refresh before the inbound deadline so a printer which
# only answers requests can keep one session fresh without a reconnect loop.
INFORMATION_REFRESH_INTERVAL_SECONDS = 15
CONTROL_CONFIRMATION_TIMEOUT_SECONDS = 20
_IDENTITY_DISCOVERY_MESSAGE = b"M99999"


ElegooControlUnconfirmed = PlatformControlUnconfirmed


@dataclass
class _LiveSource:
    source_id: int
    private_ipv4: str
    driver: SyntheticElegooSdcpV3Driver
    configuration_revision: int = 1
    control_enabled: bool = False
    control_acknowledgement: ControlAcknowledgement | None = None
    task: asyncio.Task[None] | None = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    connected: bool = False
    reconnecting: bool = False
    error: str | None = None
    mainboard_id: str | None = None
    identity_discovery_attempted: bool = False
    identity_ready: asyncio.Event = field(default_factory=asyncio.Event)
    pong_received: asyncio.Event = field(default_factory=asyncio.Event)
    liveness_received: asyncio.Event = field(default_factory=asyncio.Event)
    status_received: asyncio.Event = field(default_factory=asyncio.Event)
    attributes_received: asyncio.Event = field(default_factory=asyncio.Event)
    last_liveness_at: float | None = None
    websocket: aiohttp.ClientWebSocketResponse | None = None
    control_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ElegooSDCPManager:
    """Owns explicitly enabled SDCP connections and exposes safe observations."""

    def __init__(self) -> None:
        self._sources: dict[int, _LiveSource] = {}

    async def enable(
        self,
        source_id: int,
        private_ipv4: str,
        configuration_revision: int = 1,
        control_enabled: bool = False,
        control_acknowledgement: ControlAcknowledgement | None = None,
    ) -> None:
        # This is intentionally repeated at the I/O boundary. Callers outside
        # the API (including boot restoration) must not be able to direct the
        # transport to a hostname, public address, URL, or alternate endpoint.
        private_ipv4 = canonical_rfc1918_ipv4(private_ipv4)
        if type(configuration_revision) is not int or configuration_revision < 1:
            raise ValueError("invalid platform control configuration revision")
        if type(control_enabled) is not bool:
            raise ValueError("invalid platform control activation")
        # A restart or legacy caller with no acknowledgement must fail closed,
        # never restore a formerly enabled writer from a boolean alone.
        if control_acknowledgement is None:
            control_enabled = False
        if (
            control_acknowledgement is not None
            and control_acknowledgement.configuration_revision != configuration_revision
        ):
            raise ValueError("invalid platform control acknowledgement revision")
        await self.disable(source_id)
        live = _LiveSource(
            source_id=source_id,
            private_ipv4=private_ipv4,
            driver=SyntheticElegooSdcpV3Driver(f"elegoo-{source_id}", stale_after=STALE_AFTER),
            configuration_revision=configuration_revision,
            control_enabled=control_enabled,
            control_acknowledgement=control_acknowledgement,
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

    async def observe_discovery_candidate(self, private_ipv4: str, mainboard_id: str) -> str:
        """Perform one ephemeral Cmd 0/Cmd 1 observation of a responder only.

        Discovery calls this only after its UDP response validation.  The
        temporary driver is never placed in ``_sources`` and therefore cannot
        become an enabled source or acquire a reconnect loop.  The returned
        classification intentionally exposes no raw response or endpoint.
        """

        private_ipv4 = canonical_rfc1918_ipv4(private_ipv4)
        mainboard_id = validate_mainboard_id(mainboard_id)
        session_id = str(uuid.uuid4())
        live = _LiveSource(0, private_ipv4, SyntheticElegooSdcpV3Driver("elegoo-discovery"))
        live.mainboard_id = mainboard_id
        live.identity_ready.set()
        live.driver.start_session(session_id)
        try:
            timeout = aiohttp.ClientTimeout(total=HANDSHAKE_TIMEOUT_SECONDS, sock_connect=CONNECT_TIMEOUT_SECONDS)
            connector = aiohttp.TCPConnector(family=socket.AF_INET, use_dns_cache=False)
            async with (
                aiohttp.ClientSession(timeout=timeout, connector=connector) as session,
                session.ws_connect(
                    f"ws://{private_ipv4}:3030/websocket",
                    heartbeat=None,
                    autoping=False,
                    max_msg_size=MAX_FRAME_BYTES,
                ) as websocket,
            ):
                live.connected = True
                await self._observe_candidate_connection(websocket, live, session_id)
                if live.driver.observation(datetime.now(timezone.utc)).current is not None:
                    return "observed"
        except asyncio.TimeoutError:
            return "unavailable"
        except (aiohttp.ClientError, aiohttp.WSServerHandshakeError):
            return "unavailable"
        except Exception:
            # Do not leak endpoint or payload details from an ephemeral probe.
            return "error"
        finally:
            live.connected = False
            live.driver.disconnect(session_id)
        return "error" if live.error else "unavailable"

    async def _observe_candidate_connection(
        self, websocket: aiohttp.ClientWebSocketResponse, live: _LiveSource, session_id: str
    ) -> None:
        """Use the persistent client's parser for one bounded candidate read."""

        live.websocket = websocket
        consume_task = asyncio.create_task(self._consume(websocket, live, session_id))
        try:
            if not await self._send_heartbeat(websocket, live):
                return
            mainboard_id = live.mainboard_id
            if mainboard_id is None:
                live.error = "identity_unavailable"
                return
            await self._send_information_request(
                websocket, live, ReadOnlyInformationOperation.STATUS_REFRESH, mainboard_id
            )
            await self._send_information_request(websocket, live, ReadOnlyInformationOperation.ATTRIBUTES, mainboard_id)
            if not await self._await_initial_liveness(websocket, live, PONG_TIMEOUT_SECONDS):
                return
            status_wait = asyncio.create_task(live.status_received.wait())
            attributes_wait = asyncio.create_task(live.attributes_received.wait())
            try:
                await asyncio.wait_for(asyncio.gather(status_wait, attributes_wait), timeout=HANDSHAKE_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                live.error = live.error or "observation_timeout"
            finally:
                for wait in (status_wait, attributes_wait):
                    if not wait.done():
                        wait.cancel()
                        try:
                            await wait
                        except asyncio.CancelledError:
                            pass
        finally:
            if live.websocket is websocket:
                live.websocket = None
            if not consume_task.done():
                consume_task.cancel()
                try:
                    await consume_task
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
            return self._with_control_gate(
                live,
                DriverObservation(
                    phase=ConnectionPhase.WAITING,
                    capabilities=frozenset(),
                    session_id=observation.session_id,
                ),
            )
        if live.reconnecting and observation.phase is ConnectionPhase.DISCONNECTED:
            return self._with_control_gate(
                live,
                DriverObservation(
                    phase=ConnectionPhase.RECONNECTING,
                    capabilities=observation.capabilities,
                    retained=observation.retained,
                    error=live.error,
                ),
            )
        if live.error and observation.error is None and observation.phase is not ConnectionPhase.READY:
            return self._with_control_gate(
                live,
                DriverObservation(
                    phase=observation.phase,
                    capabilities=observation.capabilities,
                    current=observation.current,
                    retained=observation.retained,
                    error=live.error,
                    session_id=observation.session_id,
                ),
            )
        return self._with_control_gate(live, observation)

    @staticmethod
    def _with_control_gate(live: _LiveSource, observation: DriverObservation) -> DriverObservation:
        """Project control only for an explicitly enabled, fresh active job.

        The SDCP normalizer deliberately never infers a control capability from
        an attributes declaration.  The manager is the sole activation
        boundary: an explicit per-source gate may add the capability only to a
        ready current printing/paused observation; every other observation
        remains unavailable.
        """

        acknowledgement = live.control_acknowledgement
        if (
            live.control_enabled
            and acknowledgement is not None
            and acknowledgement_matches_observation(
                driver=DriverKind.ELEGOO_SDCP_V3,
                model=acknowledgement.model,
                firmware=acknowledgement.firmware,
                operations=acknowledgement.operations,
                observation=observation,
            )
        ):
            current = observation.current
            if (
                observation.phase is ConnectionPhase.READY
                and current is not None
                and current.state in {"printing", "paused"}
                and (current.job is None or current.state == current.job.state)
                and Capability.JOB_CONTROL not in observation.capabilities
            ):
                capabilities = frozenset({*observation.capabilities, Capability.JOB_CONTROL})
                return replace(
                    observation, capabilities=capabilities, current=replace(current, capabilities=capabilities)
                )
            return observation
        if Capability.JOB_CONTROL not in observation.capabilities:
            return observation
        capabilities = frozenset(
            capability for capability in observation.capabilities if capability is not Capability.JOB_CONTROL
        )
        current = replace(observation.current, capabilities=capabilities) if observation.current is not None else None
        retained = (
            replace(
                observation.retained,
                snapshot=replace(observation.retained.snapshot, capabilities=capabilities),
            )
            if observation.retained is not None
            else None
        )
        return replace(
            observation,
            capabilities=capabilities,
            current=current,
            retained=retained,
        )

    async def dispatch_command(self, command: object) -> bool:
        """Send one capability-gated SDCP job command through the active session.

        The only caller input accepted here is the persisted, operation-only
        contract.  This manager has no way to receive a raw SDCP envelope,
        command number, topic, payload, or G-code string.
        """

        if type(command) is not PlatformControlCommand or command.driver is not DriverKind.ELEGOO_SDCP_V3:
            raise ValueError("unsupported Elegoo control command")
        live = self._sources.get(command.source_id)
        if live is None or command.configuration_revision != live.configuration_revision:
            return False
        acknowledgement = live.control_acknowledgement
        if not live.control_enabled or acknowledgement is None:
            return False
        observation = self.observation(command.source_id)
        if not acknowledgement_matches_observation(
            driver=DriverKind.ELEGOO_SDCP_V3,
            model=acknowledgement.model,
            firmware=acknowledgement.firmware,
            operations=acknowledgement.operations,
            observation=observation,
        ):
            return False
        if not control_operation_is_available(command.operation, observation):
            return False
        if live.mainboard_id is None or live.websocket is None or live.stop.is_set():
            return False
        async with live.control_lock:
            websocket = live.websocket
            mainboard_id = live.mainboard_id
            if websocket is None or mainboard_id is None or live.stop.is_set():
                return False
            # A status received before this point cannot confirm this command.
            live.status_received.clear()
            await websocket.send_str(serialize_control_request(command.operation, mainboard_id))
            # Ask for the one already-allowlisted state record immediately;
            # do not infer a response schema for the control command itself.
            await self._send_information_request(
                websocket, live, ReadOnlyInformationOperation.STATUS_REFRESH, mainboard_id
            )
        if await self._await_control_confirmation(live, command.operation):
            return True
        raise ElegooControlUnconfirmed

    async def _run(self, live: _LiveSource) -> None:
        # The documented identity lookup precedes the WebSocket session. It is
        # still bounded to one exact-address unicast per enabled source.
        await self._prepare_identity(live)
        attempt = 0
        while not live.stop.is_set():
            session_id = uuid.uuid4().hex
            live.driver.start_session(session_id)
            live.connected = False
            live.reconnecting = attempt > 0
            live.pong_received.clear()
            live.liveness_received.clear()
            live.status_received.clear()
            live.last_liveness_at = None
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
                    await self._serve_connection(websocket, live, session_id)
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

    async def _prepare_identity(self, live: _LiveSource) -> None:
        """Acquire a required identity before opening the fixed WebSocket endpoint."""

        if live.mainboard_id is None:
            await self._discover_mainboard_id_unicast(live)

    async def _serve_connection(
        self, websocket: aiohttp.ClientWebSocketResponse, live: _LiveSource, session_id: str
    ) -> None:
        """Run one session; no request can be emitted outside this method."""

        live.websocket = websocket
        consume_task = asyncio.create_task(self._consume(websocket, live, session_id))
        try:
            # Start the documented liveness exchange immediately, but do not
            # wait idly for it before acquiring the identity required for the
            # two documented information requests.  A bounded pong deadline
            # still closes this session fail-closed below.
            heartbeat_started = asyncio.get_running_loop().time()
            if not await self._send_heartbeat(websocket, live):
                return

            mainboard_id = live.mainboard_id
            if mainboard_id is None:
                try:
                    await asyncio.wait_for(live.identity_ready.wait(), timeout=PASSIVE_IDENTITY_WAIT_SECONDS)
                except asyncio.TimeoutError:
                    pass
                mainboard_id = live.mainboard_id
            if mainboard_id is None:
                mainboard_id = await self._discover_mainboard_id_unicast(live)

            if mainboard_id is None:
                # Exactly one unicast discovery attempt is permitted per enabled
                # source. Keep the connected session passive after that attempt.
                live.error = "identity_unavailable"
            elif not live.stop.is_set():
                await self._send_information_request(
                    websocket, live, ReadOnlyInformationOperation.STATUS_REFRESH, mainboard_id
                )
                await self._send_information_request(
                    websocket, live, ReadOnlyInformationOperation.ATTRIBUTES, mainboard_id
                )

            remaining_liveness_timeout = PONG_TIMEOUT_SECONDS - (asyncio.get_running_loop().time() - heartbeat_started)
            if not await self._await_initial_liveness(websocket, live, max(0, remaining_liveness_timeout)):
                return
            await self._wait_for_inbound_traffic(websocket, live, consume_task)
        finally:
            if live.websocket is websocket:
                live.websocket = None
            if not consume_task.done():
                consume_task.cancel()
                try:
                    await consume_task
                except asyncio.CancelledError:
                    pass

    async def _await_initial_liveness(
        self, websocket: aiohttp.ClientWebSocketResponse, live: _LiveSource, timeout: float
    ) -> bool:
        """Accept text pong or a validated allowed SDCP inbound message once."""

        if live.liveness_received.is_set():
            return True
        liveness_wait = asyncio.create_task(live.liveness_received.wait())
        try:
            await asyncio.wait_for(liveness_wait, timeout=timeout)
        except asyncio.TimeoutError:
            live.error = "heartbeat_timeout"
            await websocket.close()
            return False
        finally:
            if not liveness_wait.done():
                liveness_wait.cancel()
                try:
                    await liveness_wait
                except asyncio.CancelledError:
                    pass
        return True

    async def _wait_for_inbound_traffic(
        self, websocket: aiohttp.ClientWebSocketResponse, live: _LiveSource, consume_task: asyncio.Task[None]
    ) -> None:
        """Keep an established session only while validated inbound traffic remains fresh."""

        loop = asyncio.get_running_loop()
        next_refresh_at = loop.time() + INFORMATION_REFRESH_INTERVAL_SECONDS
        while not consume_task.done() and not live.stop.is_set():
            last_liveness_at = live.last_liveness_at or loop.time()
            remaining = NO_INBOUND_TRAFFIC_TIMEOUT_SECONDS - (loop.time() - last_liveness_at)
            if remaining <= 0:
                live.error = "inbound_timeout"
                await websocket.close()
                return
            update_wait = asyncio.create_task(live.liveness_received.wait())
            done, _pending = await asyncio.wait(
                {consume_task, update_wait},
                timeout=min(remaining, max(0, next_refresh_at - loop.time())),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if update_wait in done:
                live.liveness_received.clear()
                continue
            if not update_wait.done():
                update_wait.cancel()
                try:
                    await update_wait
                except asyncio.CancelledError:
                    pass
            if consume_task in done:
                return
            if loop.time() >= next_refresh_at:
                mainboard_id = live.mainboard_id
                if mainboard_id is not None:
                    await self._send_information_request(
                        websocket, live, ReadOnlyInformationOperation.STATUS_REFRESH, mainboard_id
                    )
                    await self._send_information_request(
                        websocket, live, ReadOnlyInformationOperation.ATTRIBUTES, mainboard_id
                    )
                next_refresh_at = loop.time() + INFORMATION_REFRESH_INTERVAL_SECONDS
                continue
            live.error = "inbound_timeout"
            await websocket.close()
            return

    async def _await_control_confirmation(self, live: _LiveSource, operation: PlatformControlOperation) -> bool:
        """Require a post-dispatch, fresh state transition before reporting success."""

        loop = asyncio.get_running_loop()
        deadline = loop.time() + CONTROL_CONFIRMATION_TIMEOUT_SECONDS
        while not live.stop.is_set() and live.websocket is not None:
            if self._control_state_matches(operation, self.observation(live.source_id)):
                return True
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            status_wait = asyncio.create_task(live.status_received.wait())
            try:
                await asyncio.wait_for(status_wait, timeout=remaining)
            except asyncio.TimeoutError:
                return False
            finally:
                if not status_wait.done():
                    status_wait.cancel()
                    try:
                        await status_wait
                    except asyncio.CancelledError:
                        pass
            live.status_received.clear()
        return False

    async def _send_heartbeat(self, websocket: aiohttp.ClientWebSocketResponse, live: _LiveSource) -> bool:
        """Transmit the one allowed liveness message after immediate serialization."""

        if live.stop.is_set():
            return False
        await websocket.send_str(serialize_heartbeat())
        return True

    async def _send_information_request(
        self,
        websocket: aiohttp.ClientWebSocketResponse,
        live: _LiveSource,
        operation: ReadOnlyInformationOperation,
        mainboard_id: str,
    ) -> None:
        """Transmit Cmd 0 or Cmd 1 only; the serializer rejects every other value."""

        if live.stop.is_set():
            return
        await websocket.send_str(serialize_information_request(operation, mainboard_id))

    async def _discover_mainboard_id_unicast(self, live: _LiveSource) -> str | None:
        """Perform at most one exact-address UDP identity lookup, never broadcast."""

        if live.identity_discovery_attempted or live.stop.is_set():
            return live.mainboard_id
        live.identity_discovery_attempted = True
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setblocking(False)
        try:
            # ``private_ipv4`` was independently canonicalized at the I/O
            # boundary; connect() forces this one datagram to that exact host.
            udp_socket.connect((live.private_ipv4, 3000))
            loop = asyncio.get_running_loop()
            await loop.sock_sendall(udp_socket, _IDENTITY_DISCOVERY_MESSAGE)
            raw = await asyncio.wait_for(loop.sock_recv(udp_socket, 8192), timeout=IDENTITY_DISCOVERY_TIMEOUT_SECONDS)
            try:
                payload = json.loads(raw.decode("utf-8"))
                mainboard_id = mainboard_id_from_discovery(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                live.error = "identity_unavailable"
                return None
            self._set_mainboard_id(live, mainboard_id)
            return live.mainboard_id
        except (OSError, asyncio.TimeoutError):
            live.error = "identity_unavailable"
            return None
        finally:
            udp_socket.close()

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
        if raw == "pong":
            live.pong_received.set()
            self._mark_liveness(live)
            return
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
            response_prefix = "sdcp/response/"
            if topic.startswith(response_prefix) and len(topic) > len(response_prefix):
                response = envelope.get("Data")
                if (
                    self._set_mainboard_id(live, topic[len(response_prefix) :])
                    and isinstance(response, dict)
                    and type(response.get("Cmd")) is int
                    and response["Cmd"] in {0, 1}
                ):
                    self._mark_liveness(live)
            # A future topic is not an error and never becomes a capability.
            return
        if not self._set_mainboard_id(live, topic[len(status_prefix if kind == "status" else attributes_prefix) :]):
            return
        # Centauri status/attributes use documented top-level ``Status`` /
        # ``Attributes`` records, while fixtures and some implementations
        # nest them under ``Data``. Both shapes are already normalized by the
        # driver; neither a bare topic nor an unrelated object is liveness.
        record_name = "Status" if kind == "status" else "Attributes"
        nested_data = envelope.get("Data")
        has_documented_record = isinstance(envelope.get(record_name), dict) or (
            isinstance(nested_data, dict) and isinstance(nested_data.get(record_name), dict)
        )
        if not has_documented_record:
            live.error = "invalid_envelope"
            return
        observed_at = datetime.now(timezone.utc)
        if kind == "status":
            live.driver.observe_status(session_id, envelope, observed_at)
            live.status_received.set()
        else:
            live.driver.observe_attributes(session_id, envelope, observed_at)
            live.attributes_received.set()
        self._mark_liveness(live)

    @staticmethod
    def _control_state_matches(operation: PlatformControlOperation, observation: DriverObservation) -> bool:
        return observation_satisfies_reconciliation(operation, observation)

    @staticmethod
    def _set_mainboard_id(live: _LiveSource, candidate: object) -> bool:
        try:
            mainboard_id = validate_mainboard_id(candidate)
        except ValueError:
            live.error = "invalid_identity"
            return False
        if live.mainboard_id is None:
            live.mainboard_id = mainboard_id
            live.identity_ready.set()
        elif live.mainboard_id != mainboard_id:
            live.error = "identity_mismatch"
            return False
        return True

    @staticmethod
    def _mark_liveness(live: _LiveSource) -> None:
        live.last_liveness_at = time.monotonic()
        live.liveness_received.set()


elegoo_sdcp_manager = ElegooSDCPManager()
