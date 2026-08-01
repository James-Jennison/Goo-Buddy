import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core import database


@pytest.mark.asyncio
async def test_moonraker_migration_is_idempotent_and_preserves_existing_bambu_rows(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE printers (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"))
            await conn.execute(text("INSERT INTO printers (name) VALUES ('Existing Bambu')"))
            await database._migrate_moonraker_sources(conn)
            await database._migrate_moonraker_sources(conn)
            await conn.execute(
                text("INSERT INTO moonraker_sources (display_name, private_ipv4) VALUES ('Synthetic', '192.168.1.44')")
            )
            assert (await conn.execute(text("SELECT name FROM printers"))).one() == ("Existing Bambu",)
            assert (await conn.execute(text("SELECT id, port, scheme FROM moonraker_sources"))).one() == (
                1,
                7125,
                "http",
            )
    finally:
        await engine.dispose()
