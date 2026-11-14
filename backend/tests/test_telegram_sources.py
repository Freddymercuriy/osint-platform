"""Bosqich 3: Telegram chatlari alohida manbalar (0006) va bitta chat ulagichining kursori."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import asyncpg

from app.services.connectors.base import FetchContext, SourceView
from app.services.connectors.telegram_user import TelegramUserConnector
from tests.conftest import ADMIN_DATABASE_URL, TEST_DATABASE_URL, _plain, scratch_db_name

ROOT = Path(__file__).resolve().parent.parent
NAME = scratch_db_name("osint_tg_scratch")
URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + f"/{NAME}"


async def _admin(sql: str) -> None:
    c = await asyncpg.connect(_plain(ADMIN_DATABASE_URL))
    try:
        await c.execute(sql)
    finally:
        await c.close()


async def _rows(sql: str):
    c = await asyncpg.connect(_plain(URL))
    try:
        return await c.fetch(sql)
    finally:
        await c.close()


def _migrate(*args: str, **env) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate.py"), *args], cwd=ROOT, check=True,
                   capture_output=True, text=True, env=dict(os.environ, DATABASE_URL=URL, **env))


def test_per_chat_sources_seeded_from_env():
    asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)'))
    asyncio.run(_admin(f'CREATE DATABASE "{NAME}"'))
    try:
        _migrate(TG_CHATS="thehackernews,-1003968753730,@catseclist", TG_LEAK_CHATS="catseclist,-1004361457833")
        rows = {r["name"]: r for r in asyncio.run(_rows(
            "select s.name, s.config->>'chat' as chat, s.translate, c.slug from sources s "
            "left join categories c on c.id = s.category_id where s.kind = 'telegram_user'"))}
        assert set(rows) == {"Telegram: thehackernews", "Telegram: -1003968753730", "Telegram: catseclist",
                             "Telegram: -1004361457833"}
        assert rows["Telegram: thehackernews"]["translate"] is True
        assert rows["Telegram: -1003968753730"]["translate"] is False  # yopiq chat — tarjimaga yuborilmaydi
        assert rows["Telegram: catseclist"]["slug"] == "leak" and rows["Telegram: thehackernews"]["slug"] is None
        _migrate("downgrade", "0005_event_uid_v2", TG_CHATS="", TG_LEAK_CHATS="")
        names = [r["name"] for r in asyncio.run(_rows("select name from sources where kind = 'telegram_user'"))]
        assert names == ["Telegram (akkaunt)"]
    finally:
        asyncio.run(_admin(f'DROP DATABASE IF EXISTS "{NAME}" WITH (FORCE)'))


class _Chat:
    def __init__(self, kind="channel"):
        self.id, self.title, self.username, self.kind = -1001, "Leak Chat", "leakchat", kind


class _Msg:
    def __init__(self, mid, text):
        self.chat, self.msg_id, self.text, self.date = _Chat(), mid, text, datetime.now(UTC)

    @property
    def url(self):
        return f"https://t.me/leakchat/{self.msg_id}"


async def test_single_chat_cursor(monkeypatch):
    from app.services import telegram_user as tg

    calls = []

    async def fake_fetch(chat, limit, min_id=0):
        calls.append((chat, min_id))
        return [_Msg(10, "Uzbekistan bank database leak"), _Msg(12, "unrelated post"), _Msg(11, "Toshkent: test")]

    monkeypatch.setattr(tg, "is_configured", lambda: True)
    monkeypatch.setattr(tg, "fetch_chat_messages", fake_fetch)
    view = SourceView(id=1, name="Telegram: leakchat", kind="telegram_user", config={"chat": "leakchat"}, lang="uz",
                      scope="regional", region_filter=False, cyber_filter=False, api_key_env=None, etag=None,
                      last_modified=None, state={"last_id": 7}, backfill_days=14)
    res = await TelegramUserConnector().fetch(FetchContext(source=view, http=None))
    assert calls == [("leakchat", 7)]
    assert res.state == {"last_id": 12}  # kursor filtrdan qat'i nazar oxirgi xabarga suriladi
    assert sorted(i.url for i in res.items) == ["https://t.me/leakchat/10", "https://t.me/leakchat/11"]
    assert all(i.channel == "telegram_channel" and i.category is None for i in res.items)

    # dry run kursorni ishlatmaydi va yangilamaydi
    res = await TelegramUserConnector().fetch(FetchContext(source=view, http=None, dry_run=True))
    assert calls[-1] == ("leakchat", 0) and res.state is None
