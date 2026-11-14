"""Migratsiyalar: oxirigacha pastga (base) va qayta yuqoriga (head) — alohida vaqtinchalik bazada."""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import asyncpg

from tests.conftest import ADMIN_DATABASE_URL, TEST_DATABASE_URL, _plain, scratch_db_name

ROOT = Path(__file__).resolve().parent.parent
SCRATCH_NAME = scratch_db_name("osint_migration_scratch")
SCRATCH = TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{SCRATCH_NAME}"


async def _admin(sql: str) -> None:
    conn = await asyncpg.connect(_plain(ADMIN_DATABASE_URL))
    try:
        await conn.execute(sql)
    finally:
        await conn.close()


async def _tables(url: str) -> set[str]:
    conn = await asyncpg.connect(_plain(url))
    try:
        rows = await conn.fetch("select tablename from pg_tables where schemaname='public'")
        return {r[0] for r in rows}
    finally:
        await conn.close()


def _migrate(*args: str) -> None:
    env = dict(os.environ, DATABASE_URL=SCRATCH)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate.py"), *args],
                   cwd=ROOT, env=env, check=True, capture_output=True, text=True)


def test_migrations_up_down_up():
    asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{SCRATCH_NAME}" WITH (FORCE)'))
    asyncio.run(_admin(f'CREATE DATABASE "{SCRATCH_NAME}"'))
    try:
        _migrate()
        assert {"users", "events", "alembic_version"} <= asyncio.run(_tables(SCRATCH))
        _migrate("downgrade", "base")
        assert asyncio.run(_tables(SCRATCH)) == {"alembic_version"}
        _migrate()
        assert "users" in asyncio.run(_tables(SCRATCH))
    finally:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{SCRATCH_NAME}" WITH (FORCE)'))
