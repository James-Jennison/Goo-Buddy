"""Rollback-safe migration coverage for the isolated SDCP source table."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.core import database


@pytest.mark.asyncio
async def test_elegoo_source_migration_is_idempotent_and_generates_sqlite_ids(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await database._migrate_elegoo_sdcp_sources(conn)
            await database._migrate_elegoo_sdcp_sources(conn)
            await conn.execute(
                text(
                    "INSERT INTO elegoo_sdcp_sources "
                    "(display_name, private_ipv4, is_enabled, read_only_acknowledged, configuration_revision) "
                    "VALUES ('Synthetic', '192.168.1.20', 0, 1, 1)"
                )
            )
            row = (
                await conn.execute(
                    text("SELECT id, is_enabled, read_only_acknowledged, control_enabled FROM elegoo_sdcp_sources")
                )
            ).one()
        assert row == (1, 0, 1, 0)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_elegoo_source_migration_uses_postgres_generated_id_form(monkeypatch):
    statements: list[str] = []

    async def capture_ddl(_conn, sql: str) -> None:
        statements.append(sql)

    monkeypatch.setattr(database, "is_sqlite", lambda: False)
    monkeypatch.setattr(database, "_safe_execute", capture_ddl)
    await database._migrate_elegoo_sdcp_sources(object())
    assert "id SERIAL PRIMARY KEY" in statements[0]
    assert any("control_enabled BOOLEAN DEFAULT 0 NOT NULL" in statement for statement in statements)


@pytest.mark.asyncio
async def test_elegoo_source_upgrade_preserves_a_representative_existing_bambu_row(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text("CREATE TABLE printers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, serial_number TEXT NOT NULL)")
            )
            await conn.execute(
                text("INSERT INTO printers (name, serial_number) VALUES ('Existing Bambu', '01S00A000000000')")
            )
            await database._migrate_elegoo_sdcp_sources(conn)
            bambu = (await conn.execute(text("SELECT name, serial_number FROM printers"))).one()
            sdcp_tables = (
                await conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='elegoo_sdcp_sources'")
                )
            ).all()
        assert bambu == ("Existing Bambu", "01S00A000000000")
        assert sdcp_tables == [("elegoo_sdcp_sources",)]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_elegoo_discovery_configuration_migration_is_additive_and_empty_by_default(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(database, "is_sqlite", lambda: True)
    try:
        async with engine.begin() as conn:
            await database._migrate_elegoo_sdcp_discovery_configuration(conn)
            await database._migrate_elegoo_sdcp_discovery_configuration(conn)
            rows = (await conn.execute(text("SELECT count(*) FROM elegoo_sdcp_discovery_configuration"))).scalar_one()
        assert rows == 0
    finally:
        await engine.dispose()
