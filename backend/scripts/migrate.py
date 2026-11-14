"""Migratsiyalarni qo'llash (konteyner ishga tushganda `scripts/start.sh` chaqiradi).

Alembic'dan oldingi bazalar (jadvallar `create_all` bilan yaratilgan, `alembic_version` yo'q) avval
baseline reviziyaga "stamp" qilinadi — jadvallar qayta yaratilmaydi, ma'lumot o'zgarmaydi.

    python scripts/migrate.py            # upgrade head
    python scripts/migrate.py downgrade -1
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from app.core.config import settings  # noqa: E402

BASELINE = "0001_baseline"


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


async def _tables() -> set[str]:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.connect() as conn:
            return set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    finally:
        await engine.dispose()


def main(argv: list[str]) -> None:
    cfg = alembic_config()
    if argv and argv[0] == "downgrade":
        command.downgrade(cfg, argv[1] if len(argv) > 1 else "-1")
        return
    tables = asyncio.run(_tables())
    if "alembic_version" not in tables and "users" in tables:
        print(f"migrate: Alembic'dan oldingi baza — {BASELINE} ga stamp qilinadi", flush=True)
        command.stamp(cfg, BASELINE)
    command.upgrade(cfg, argv[0] if argv else "head")


if __name__ == "__main__":
    main(sys.argv[1:])
