"""Synthetic transport-boundary tests: no socket or printer is contacted."""

import asyncio
from datetime import datetime, timezone

import pytest
from aiohttp import WSMsgType

from backend.app.drivers.contract import ConnectionPhase
from backend.app.drivers.elegoo_sdcp_v3 import SyntheticElegooSdcpV3Driver
from backend.app.services.elegoo_sdcp_manager import MAX_FRAME_BYTES, ElegooSDCPManager, _LiveSource
from backend.tests._fixtures.elegoo_sdcp_v3 import attributes, status


def _live() -> tuple[ElegooSDCPManager, _LiveSource, str]:
    manager = ElegooSDCPManager()
    live = _LiveSource(1, "192.168.1.40", SyntheticElegooSdcpV3Driver("elegoo-1"))
    manager._sources[1] = live
    session_id = "synthetic-session"
    live.driver.start_session(session_id)
    return manager, live, session_id


def test_transport_accepts_both_documented_topic_orders_without_exposing_topic_identity():
    manager, live, session_id = _live()
    manager._observe_text(
        live, session_id, '{"Topic":"sdcp/attributes/redacted","Data":' + str(attributes()).replace("'", '"') + "}"
    )
    manager._observe_text(
        live, session_id, '{"Topic":"sdcp/status/redacted","Data":' + str(status()).replace("'", '"') + "}"
    )

    observation = manager.observation(1, datetime.now(timezone.utc))
    assert observation.phase is ConnectionPhase.READY
    assert observation.current is not None
    assert observation.current.identity.display_name == "Synthetic Centauri"


def test_transport_rejects_invalid_json_and_ignores_unknown_topics():
    manager, live, session_id = _live()
    manager._observe_text(live, session_id, "{")
    assert manager.observation(1).error == "invalid_json"

    manager._observe_text(live, session_id, '{"Topic":"sdcp/canvas/redacted","Data":{}}')
    assert manager.observation(1).phase is ConnectionPhase.CONNECTING

    manager._observe_text(live, session_id, '{"Topic":"sdcp/status/","Data":{}}')
    assert manager.observation(1).phase is ConnectionPhase.CONNECTING


def test_open_socket_without_observation_is_waiting_not_connecting():
    manager, live, _ = _live()
    live.connected = True
    assert manager.observation(1).phase is ConnectionPhase.WAITING


def test_reconnecting_state_never_presents_retained_data_as_current():
    manager, live, session_id = _live()
    manager._observe_text(
        live, session_id, '{"Topic":"sdcp/attributes/redacted","Data":' + str(attributes()).replace("'", '"') + "}"
    )
    manager._observe_text(
        live, session_id, '{"Topic":"sdcp/status/redacted","Data":' + str(status()).replace("'", '"') + "}"
    )
    assert manager.observation(1).phase is ConnectionPhase.READY
    live.driver.disconnect(session_id)
    live.reconnecting = True
    observation = manager.observation(1)
    assert observation.phase is ConnectionPhase.RECONNECTING
    assert observation.current is None
    assert observation.retained is not None


@pytest.mark.asyncio
async def test_shutdown_cancels_owned_source_task_without_leaking_it():
    manager, live, _ = _live()
    live.task = asyncio.create_task(asyncio.Event().wait())
    await manager.shutdown()
    assert manager._sources == {}
    assert live.task.cancelled()


@pytest.mark.asyncio
async def test_service_boundary_rejects_non_private_or_non_literal_addresses_before_creating_a_task():
    manager = ElegooSDCPManager()
    for address in ("8.8.8.8", "printer.local", "ws://192.168.1.40/websocket", "192.168.1.40:3030"):
        with pytest.raises(ValueError):
            await manager.enable(1, address)
    assert manager._sources == {}


def test_transport_duplicate_frame_refreshes_current_snapshot_without_invalidating_it():
    manager, live, session_id = _live()
    attrs = '{"Topic":"sdcp/attributes/redacted","Data":' + str(attributes()).replace("'", '"') + "}"
    stat = '{"Topic":"sdcp/status/redacted","Data":' + str(status()).replace("'", '"') + "}"
    manager._observe_text(live, session_id, attrs)
    manager._observe_text(live, session_id, stat)
    manager._observe_text(live, session_id, stat)
    assert manager.observation(1).phase is ConnectionPhase.READY
    assert live.status_received.is_set() is True


@pytest.mark.asyncio
async def test_transport_stops_on_an_oversized_text_frame_without_retaining_it():
    class _SingleMessageSocket:
        def __init__(self):
            self._used = False

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self._used:
                raise StopAsyncIteration
            self._used = True
            return type("Message", (), {"type": WSMsgType.TEXT, "data": "x" * (MAX_FRAME_BYTES + 1)})()

    manager, live, session_id = _live()
    await manager._consume(_SingleMessageSocket(), live, session_id)
    assert manager.observation(1).error == "oversized_frame"
