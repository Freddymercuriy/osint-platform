"""Test muhiti.

- Alohida baza: `<asosiy baza nomi>_test` (har sessiya boshida noldan yaratiladi, migratsiyalar bilan).
- Haqiqiy backend/.env o'qilmaydi (Telegram sessiyasi, kalitlar, ADMIN_EMAILS testga ta'sir qilmaydi).
- Tarmoqqa chiqadigan testlar yozib olingan javoblar (tests/fixtures) va httpx.MockTransport bilan.

Ishga tushirish:  docker-compose exec backend pytest
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- muhit (app import qilinishidan OLDIN)
_KEEP = {
    "PATH", "HOME", "HOSTNAME", "LANG", "LC_ALL", "TERM", "PWD", "SHLVL", "TZ",
    "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED", "PYTHON_VERSION",
    "PYTHON_SHA256", "GPG_KEY", "SSL_CERT_FILE",
}
_base_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://osint:osint@localhost:5432/osint"
)
for _k in list(os.environ):
    if _k not in _KEEP and not _k.startswith("PYTEST"):
        del os.environ[_k]

_parts = urlsplit(_base_url)
_db_name = _parts.path.lstrip("/") or "osint"
# Har pytest jarayoni o'z bazasida (parallel ishga tushirilganda bir-birining bazasini o'chirmasin)
RUN_ID = os.environ.get("OSINT_TEST_RUN_ID") or str(os.getpid())
TEST_DB_NAME = f"{_db_name.removesuffix('_test')}_test_{RUN_ID}"
TEST_DATABASE_URL = urlunsplit(_parts._replace(path=f"/{TEST_DB_NAME}"))
ADMIN_DATABASE_URL = urlunsplit(_parts._replace(path="/postgres"))

os.environ.update({
    "OSINT_ENV_FILE": str(ROOT / "tests" / ".env.none"),  # mavjud emas → .env o'qilmaydi
    "DATABASE_URL": TEST_DATABASE_URL,
    "ENVIRONMENT": "test",
    "SECRET_KEY": "test-secret-key-0123456789abcdef0123456789abcdef",
    "EVENTS_POLL_ENABLED": "false",
    "REGISTRATION_OPEN": "true",
    "TG_SESSION_PATH": "/tmp/osint-test-no-session/tg",
})


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _recreate_db() -> None:
    import asyncpg

    conn = await asyncpg.connect(_plain(ADMIN_DATABASE_URL))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
        await conn.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
    finally:
        await conn.close()


def run_migrations(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "migrate.py"), *args],
        cwd=ROOT, env=dict(os.environ), capture_output=True, text=True, check=True,
    )


# Migratsiyalar seed qilgan ma'lumot (kategoriyalar, manbalar) — har testdan oldin shu holatga qaytariladi
SEED_TABLES = ("categories", "sources")


async def _snapshot_seed() -> None:
    import asyncpg

    conn = await asyncpg.connect(_plain(TEST_DATABASE_URL))
    try:
        await conn.execute("create schema if not exists seed")
        for t in SEED_TABLES:
            await conn.execute(f"drop table if exists seed.{t}")
            await conn.execute(f"create table seed.{t} as select * from public.{t}")
    finally:
        await conn.close()


async def _drop_db() -> None:
    import asyncpg

    conn = await asyncpg.connect(_plain(ADMIN_DATABASE_URL))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def _database():
    asyncio.run(_recreate_db())
    run_migrations()
    asyncio.run(_snapshot_seed())
    yield
    from app.core.db import engine

    asyncio.run(engine.dispose())
    asyncio.run(_drop_db())


def scratch_db_name(prefix: str) -> str:
    return f"{prefix}_{RUN_ID}"


# ---------------------------------------------------------------- per-test
@pytest.fixture(autouse=True)
async def _clean_tables():
    """Har test toza bazada (jadvallar bo'shatiladi, sxema qoladi)."""
    from sqlalchemy import text

    from app.core.db import engine

    async with engine.begin() as conn:
        tables = (await conn.execute(text(
            "select tablename from pg_tables where schemaname = 'public' and tablename <> 'alembic_version'"
        ))).scalars().all()
        if tables:
            await conn.execute(text(
                "truncate " + ", ".join(f'"{t}"' for t in tables) + " restart identity cascade"
            ))
        for t in SEED_TABLES:
            await conn.execute(text(f"insert into public.{t} select * from seed.{t}"))
            await conn.execute(text(
                f"select setval(pg_get_serial_sequence('{t}', 'id'), coalesce((select max(id) from {t}), 1))"
            ))
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    from app.core import ratelimit

    ratelimit.limiter.clear()
    yield


@pytest.fixture
async def db():
    from app.core.db import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    import httpx

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def make_user(db):
    """Foydalanuvchi yaratadi va (user, auth headers) qaytaradi."""
    from app.core.security import create_access_token, hash_password
    from app.models import User

    async def _make(email: str = "analyst@example.com", role: str = "analyst", password: str = "password-123"):
        user = User(email=email, hashed_password=hash_password(password), role=role)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user, {"Authorization": f"Bearer {create_access_token(str(user.id))}"}

    return _make


@pytest.fixture
async def admin_headers(make_user):
    _, headers = await make_user("admin@example.com", role="admin")
    return headers


@pytest.fixture
async def analyst_headers(make_user):
    _, headers = await make_user("analyst@example.com", role="analyst")
    return headers
