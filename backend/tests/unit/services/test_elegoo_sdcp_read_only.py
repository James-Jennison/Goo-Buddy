"""Synthetic SDCP fixture-server coverage for the closed read-only allowlist."""

from __future__ import annotations

import ast
import asyncio
import inspect
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from aiohttp import WSMsgType

from backend.app.drivers.contract import ConnectionPhase
from backend.app.drivers.elegoo_sdcp_v3 import SyntheticElegooSdcpV3Driver
from backend.app.services import elegoo_sdcp_manager as manager_module
from backend.app.services.elegoo_sdcp_manager import ElegooSDCPManager, _LiveSource
from backend.app.services.elegoo_sdcp_read_only import (
    ReadOnlyInformationOperation,
    mainboard_id_from_discovery,
    serialize_heartbeat,
    serialize_information_request,
)
from backend.tests._fixtures.elegoo_sdcp_v3 import attributes, status

_FIXTURE_MAINBOARD_ID = "fixture-mainboard-01"


class _FixtureServerSocket:
    """In-memory fixture server: records client writes and emits only safe fixtures."""

    def __init__(
        self, *, reply_to_ping: bool = True, response_only: bool = False, emit_information: bool = True
    ) -> None:
        self.sent: list[str] = []
        self.closed = False
        self._reply_to_ping = reply_to_ping
        self._response_only = response_only
        self._emit_information = emit_information
        self._incoming: asyncio.Queue[object] = asyncio.Queue()
        self._information_messages = 0

    async def send_str(self, text: str) -> None:
        self.sent.append(text)
        if text == "ping":
            if self._reply_to_ping:
                await self._incoming.put(type("Message", (), {"type": WSMsgType.TEXT, "data": "pong"})())
            return
        envelope = json.loads(text)
        assert envelope["Data"]["Cmd"] in (0, 1)
        self._information_messages += 1
        if self._information_messages == 2 and self._emit_information:
            if self._response_only:
                await self._incoming.put(
                    type(
                        "Message",
                        (),
                        {
                            "type": WSMsgType.TEXT,
                            "data": json.dumps(
                                {
                                    "Topic": f"sdcp/response/{_FIXTURE_MAINBOARD_ID}",
                                    "Data": {"Cmd": 0, "Data": {"Ack": 0}},
                                }
                            ),
                        },
                    )()
                )
                return
            await self._incoming.put(
                type(
                    "Message",
                    (),
                    {
                        "type": WSMsgType.TEXT,
                        "data": json.dumps({"Topic": f"sdcp/attributes/{_FIXTURE_MAINBOARD_ID}", "Data": attributes()}),
                    },
                )()
            )
            await self._incoming.put(
                type(
                    "Message",
                    (),
                    {
                        "type": WSMsgType.TEXT,
                        "data": json.dumps({"Topic": f"sdcp/status/{_FIXTURE_MAINBOARD_ID}", "Data": status()}),
                    },
                )()
            )

    async def close(self) -> None:
        self.closed = True
        await self._incoming.put(type("Message", (), {"type": WSMsgType.CLOSED, "data": None})())

    def __aiter__(self):
        return self

    async def __anext__(self):
        message = await self._incoming.get()
        if message.type is WSMsgType.CLOSED:
            raise StopAsyncIteration
        return message


class _UnicastSocket:
    """A UDP-only fake that makes a prohibited broadcast impossible to hide."""

    def __init__(self) -> None:
        self.connected_to: tuple[str, int] | None = None
        self.blocking: bool | None = None
        self.closed = False

    def setblocking(self, value: bool) -> None:
        self.blocking = value

    def connect(self, target: tuple[str, int]) -> None:
        self.connected_to = target

    def close(self) -> None:
        self.closed = True


class _UnicastLoop:
    def __init__(self) -> None:
        self.sent: list[tuple[_UnicastSocket, bytes]] = []

    async def sock_sendall(self, udp_socket: _UnicastSocket, payload: bytes) -> None:
        self.sent.append((udp_socket, payload))

    async def sock_recv(self, udp_socket: _UnicastSocket, size: int) -> bytes:
        assert size == 8192
        return json.dumps({"Data": {"MainboardID": _FIXTURE_MAINBOARD_ID}}).encode()


def _live() -> tuple[ElegooSDCPManager, _LiveSource, str]:
    manager = ElegooSDCPManager()
    live = _LiveSource(1, "192.168.1.40", SyntheticElegooSdcpV3Driver("elegoo-1"))
    manager._sources[1] = live
    session_id = "fixture-session"
    live.driver.start_session(session_id)
    live.connected = True
    live.mainboard_id = _FIXTURE_MAINBOARD_ID
    live.identity_ready.set()
    return manager, live, session_id


def test_allowlist_serializes_exact_ping_and_only_documented_information_envelopes():
    assert serialize_heartbeat() == "ping"
    for operation in ReadOnlyInformationOperation:
        envelope = json.loads(serialize_information_request(operation, _FIXTURE_MAINBOARD_ID))
        assert envelope["Data"]["Cmd"] == operation.value
        assert envelope["Data"]["Data"] == {}
        assert envelope["Data"]["From"] == 0
        assert envelope["Data"]["MainboardID"] == _FIXTURE_MAINBOARD_ID
        assert envelope["Topic"] == f"sdcp/request/{_FIXTURE_MAINBOARD_ID}"
        assert len(envelope["Id"]) == 36
        assert len(envelope["Data"]["RequestID"]) == 36
        assert str(uuid.UUID(envelope["Id"])) == envelope["Id"]
        assert str(uuid.UUID(envelope["Data"]["RequestID"])) == envelope["Data"]["RequestID"]
        assert isinstance(envelope["Data"]["TimeStamp"], int)


@pytest.mark.parametrize("value", [-1, 2, 128, True, False, "0", {"Cmd": 0}, [0], None])
def test_allowlist_rejects_every_non_enum_command_representation(value: object):
    with pytest.raises(ValueError, match="unsupported"):
        serialize_information_request(value, _FIXTURE_MAINBOARD_ID)


@pytest.mark.parametrize("identity", ["", "bad/id", "bad whitespace", 123, None, {"id": "x"}])
def test_allowlist_rejects_malformed_identity_without_echoing_it(identity: object):
    with pytest.raises(ValueError, match="identity") as error:
        serialize_information_request(ReadOnlyInformationOperation.STATUS_REFRESH, identity)
    if isinstance(identity, str) and identity:
        assert identity not in str(error.value)


def test_unicast_discovery_parser_retains_only_a_valid_identity():
    assert mainboard_id_from_discovery({"Data": {"MainboardID": _FIXTURE_MAINBOARD_ID}}) == _FIXTURE_MAINBOARD_ID
    for payload in ({}, {"Data": {}}, {"Data": {"MainboardID": "bad/id"}}, "raw"):
        with pytest.raises(ValueError, match="identity"):
            mainboard_id_from_discovery(payload)


@pytest.mark.asyncio
async def test_fixture_server_receives_exact_initial_ping_and_one_information_pair_and_normalizes_responses():
    manager, live, session_id = _live()
    websocket = _FixtureServerSocket()
    task = asyncio.create_task(manager._serve_connection(websocket, live, session_id))
    for _ in range(50):
        if len(websocket.sent) == 3:
            break
        await asyncio.sleep(0.01)
    await websocket.close()
    await task

    assert websocket.sent[0] == "ping"
    requests = [json.loads(text) for text in websocket.sent[1:]]
    assert [request["Data"]["Cmd"] for request in requests] == [0, 1]
    assert all(request["Topic"] == f"sdcp/request/{_FIXTURE_MAINBOARD_ID}" for request in requests)
    observation = manager.observation(1, datetime.now(timezone.utc))
    assert observation.phase is ConnectionPhase.READY
    assert observation.current is not None
    assert observation.current.identity.display_name == "Synthetic Centauri"


@pytest.mark.asyncio
async def test_initial_information_pair_is_once_per_new_session():
    manager, live, first_session_id = _live()

    async def serve_one_session(session_id: str) -> list[str]:
        websocket = _FixtureServerSocket()
        task = asyncio.create_task(manager._serve_connection(websocket, live, session_id))
        for _ in range(50):
            if len(websocket.sent) == 3:
                break
            await asyncio.sleep(0.01)
        await websocket.close()
        await task
        return websocket.sent

    first_messages = await serve_one_session(first_session_id)
    live.driver.start_session("fixture-session-two")
    second_messages = await serve_one_session("fixture-session-two")

    for messages in (first_messages, second_messages):
        assert messages[0] == "ping"
        assert [json.loads(message)["Data"]["Cmd"] for message in messages[1:]] == [0, 1]


@pytest.mark.asyncio
async def test_liveness_timeout_closes_when_no_text_pong_or_valid_sdcp_message(
    monkeypatch: pytest.MonkeyPatch,
):
    manager, live, session_id = _live()
    websocket = _FixtureServerSocket(reply_to_ping=False, emit_information=False)
    monkeypatch.setattr(manager_module, "PONG_TIMEOUT_SECONDS", 0.01)
    await manager._serve_connection(websocket, live, session_id)
    assert websocket.sent[0] == "ping"
    assert [json.loads(message)["Data"]["Cmd"] for message in websocket.sent[1:]] == [0, 1]
    assert websocket.closed is True
    assert live.error == "heartbeat_timeout"


@pytest.mark.asyncio
async def test_valid_allowlisted_response_establishes_liveness_without_any_pong():
    manager, live, session_id = _live()
    websocket = _FixtureServerSocket(reply_to_ping=False, response_only=True)
    task = asyncio.create_task(manager._serve_connection(websocket, live, session_id))
    for _ in range(50):
        if len(websocket.sent) == 3:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0)
    assert task.done() is False
    assert live.liveness_received.is_set() is False
    assert live.error is None
    await websocket.close()
    await task


@pytest.mark.asyncio
async def test_valid_liveness_still_closes_after_the_separate_no_inbound_timeout(
    monkeypatch: pytest.MonkeyPatch,
):
    manager, live, session_id = _live()
    websocket = _FixtureServerSocket(reply_to_ping=False, response_only=True)
    monkeypatch.setattr(manager_module, "NO_INBOUND_TRAFFIC_TIMEOUT_SECONDS", 0.01)
    await manager._serve_connection(websocket, live, session_id)
    assert websocket.closed is True
    assert live.error == "inbound_timeout"


@pytest.mark.asyncio
async def test_valid_liveness_at_the_idle_window_boundary_restarts_the_full_window(
    monkeypatch: pytest.MonkeyPatch,
):
    manager, live, _ = _live()
    websocket = _FixtureServerSocket()
    consume_task = asyncio.create_task(asyncio.sleep(1))
    monkeypatch.setattr(manager_module, "NO_INBOUND_TRAFFIC_TIMEOUT_SECONDS", 0.02)
    manager._mark_liveness(live)
    wait_task = asyncio.create_task(manager._wait_for_inbound_traffic(websocket, live, consume_task))
    await asyncio.sleep(0.005)
    assert websocket.closed is False
    await wait_task
    assert websocket.closed is True
    consume_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await consume_task


def test_invalid_or_unrelated_inbound_frames_never_reset_liveness():
    manager, live, session_id = _live()
    manager._observe_text(live, session_id, "not-json")
    assert live.liveness_received.is_set() is False
    unrelated_response = json.dumps(
        {
            "Topic": f"sdcp/response/{_FIXTURE_MAINBOARD_ID}",
            "Data": {"Cmd": 128, "Data": {}},
        }
    )
    manager._observe_text(live, session_id, unrelated_response)
    assert live.liveness_received.is_set() is False


def test_documented_top_level_status_and_attributes_are_valid_liveness():
    manager, live, session_id = _live()
    manager._observe_text(
        live,
        session_id,
        json.dumps({"Topic": f"sdcp/status/{_FIXTURE_MAINBOARD_ID}", "Status": {"CurrentStatus": [0]}}),
    )
    assert live.liveness_received.is_set() is True
    live.liveness_received.clear()
    manager._observe_text(
        live,
        session_id,
        json.dumps(
            {
                "Topic": f"sdcp/attributes/{_FIXTURE_MAINBOARD_ID}",
                "Attributes": {"Name": "Synthetic Centauri", "MachineName": "Synthetic Centauri"},
            }
        ),
    )
    assert live.liveness_received.is_set() is True


@pytest.mark.asyncio
async def test_identity_discovery_is_one_exact_unicast_without_a_broadcast(monkeypatch: pytest.MonkeyPatch):
    manager, live, _ = _live()
    live.mainboard_id = None
    live.identity_ready.clear()
    udp_socket = _UnicastSocket()
    loop = _UnicastLoop()
    monkeypatch.setattr(manager_module.socket, "socket", lambda *_args: udp_socket)
    monkeypatch.setattr(manager_module.asyncio, "get_running_loop", lambda: loop)

    assert await manager._discover_mainboard_id_unicast(live) == _FIXTURE_MAINBOARD_ID
    assert udp_socket.connected_to == (live.private_ipv4, 3000)
    assert udp_socket.blocking is False
    assert loop.sent == [(udp_socket, b"M99999")]
    assert udp_socket.closed is True
    assert await manager._discover_mainboard_id_unicast(live) == _FIXTURE_MAINBOARD_ID
    assert len(loop.sent) == 1


@pytest.mark.asyncio
async def test_identity_is_prepared_once_before_the_websocket_session(monkeypatch: pytest.MonkeyPatch):
    manager, live, _ = _live()
    live.mainboard_id = None
    discovery = AsyncMock(return_value=None)
    monkeypatch.setattr(manager, "_discover_mainboard_id_unicast", discovery)
    await manager._prepare_identity(live)
    discovery.assert_awaited_once_with(live)
    live.mainboard_id = _FIXTURE_MAINBOARD_ID
    await manager._prepare_identity(live)
    discovery.assert_awaited_once()


@pytest.mark.asyncio
async def test_disable_cancels_the_only_session_task_and_prevents_later_sends():
    manager, live, _ = _live()
    websocket = _FixtureServerSocket()
    live.task = asyncio.create_task(asyncio.sleep(60))
    await manager.disable(live.source_id)
    assert live.task.cancelled()
    assert websocket.sent == []


def test_manager_has_no_generic_or_raw_command_send_escape_hatch():
    tree = ast.parse(inspect.getsource(manager_module))
    send_parents: list[str] = []

    class Visitor(ast.NodeVisitor):
        current_function = "<module>"

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            previous = self.current_function
            self.current_function = node.name
            self.generic_visit(node)
            self.current_function = previous

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            previous = self.current_function
            self.current_function = node.name
            self.generic_visit(node)
            self.current_function = previous

        def visit_Call(self, node: ast.Call) -> None:
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"send_str", "send_json", "send_bytes"}:
                send_parents.append(self.current_function)
            self.generic_visit(node)

    Visitor().visit(tree)
    assert send_parents == ["_send_heartbeat", "_send_information_request"]
    source = inspect.getsource(manager_module)
    assert "def send(" not in source
    assert "def request(" not in source
    assert "_heartbeat_loop" not in source
