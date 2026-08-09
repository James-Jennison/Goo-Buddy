#!/usr/bin/env python3
"""Validate owner-authorized lab printers through closed read-only paths.

Targets are supplied only through environment variables by the local
supervisor. This script deliberately produces no addresses, identities, raw
payloads, or credentials in its output.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.drivers.contract import ConnectionPhase
from backend.app.services.elegoo_sdcp_manager import ElegooSDCPManager


class HardwareUnavailable(RuntimeError):
    """An explicitly configured lab target is deliberately offline or unreachable."""


def private_ipv4_from_env(name: str) -> str:
    """Return a canonical RFC1918 IPv4 address without echoing invalid input."""

    value = os.environ.get(name, "")
    try:
        parsed = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as error:
        raise ValueError(f"missing or invalid {name}") from error
    if not parsed.is_private or str(parsed) != value:
        raise ValueError(f"missing or invalid {name}")
    return value


async def validate_elegoo(host: str) -> None:
    manager = ElegooSDCPManager()
    source_id = 1
    try:
        await manager.enable(source_id, host)
        await asyncio.sleep(5)
        observation = manager.observation(source_id)
    finally:
        await manager.disable(source_id)
    if observation.phase is not ConnectionPhase.READY or observation.current is None:
        raise HardwareUnavailable("Elegoo lab printer is unavailable")


async def validate_moonraker(host: str) -> None:
    timeout = aiohttp.ClientTimeout(total=4, connect=2)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as session,
            session.get(f"http://{host}:7125/server/info", allow_redirects=False) as response,
        ):
            if response.status != 200:
                raise RuntimeError("Moonraker read-only validation returned a non-success status")
            payload = await response.json(content_type=None)
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as error:
        raise HardwareUnavailable("Moonraker lab printer is unavailable") from error
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict) or result.get("klippy_connected") is not True:
        raise RuntimeError("Moonraker read-only validation did not confirm a connected Klippy instance")


async def main() -> None:
    elegoo_host = private_ipv4_from_env("ELEGOO_SDCP_HOST")
    moonraker_host = private_ipv4_from_env("MOONRAKER_HOST")
    await validate_elegoo(elegoo_host)
    await validate_moonraker(moonraker_host)
    print("Authorized Elegoo and Moonraker read-only validation passed.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except HardwareUnavailable as error:
        print(f"Hardware read-only validation skipped: {error}")
        raise SystemExit(2) from None
