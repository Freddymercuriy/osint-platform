"""Telegram "Arxiv" papkasi: dialoglar ro'yxati (asosiy + arxiv) va arxivdagi chatlar → avtomatik manbalar."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy import select

from app.core.config import settings
from app.models import Source
from app.services import telegram_user as tg
from app.services.events import telegram_archive


class _Channel:
    def __init__(self, username=None, megagroup=False):
        self.username, self.megagroup = username, megagroup


class _Chat:
    username = None


class _FakeClient:
    def __init__(self, folders):
        self.folders, self.calls = folders, []

    async def iter_dialogs(self, limit=None, folder=None):
        self.calls.append((folder, limit))
        for d in self.folders.get(folder, [])[:limit]:
            yield d


def _dialog(id_, name, entity):
    return SimpleNamespace(id=id_, name=name, entity=entity)


async def test_iter_chat_dialogs_main_and_archive(monkeypatch):
    monkeypatch.setattr(tg, "Channel", _Channel)
    monkeypatch.setattr(tg, "Chat", _Chat)
    monkeypatch.setattr(settings, "tg_dialog_limit", 50)
    monkeypatch.setattr(settings, "tg_archive_limit", 7)
    client = _FakeClient({
        0: [_dialog(-1001, "Main chan", _Channel("main_chan")), _dialog(5, "Ali", object()),  # shaxsiy — yo'q
            _dialog(-12, "Basic group", _Chat())],
        1: [_dialog(-1002, "Arch group", _Channel(None, megagroup=True)),
            _dialog(-1001, "Main chan", _Channel("main_chan"))],  # takror — bir marta
    })
    got = [info async for _, info in tg.iter_chat_dialogs(client)]
    assert [(i.id, i.kind, i.archived) for i in got] == [
        (-1001, "channel", False), (-12, "group", False), (-1002, "group", True)]
    assert client.calls == [(0, 50), (1, 7)]

    only_archive = [info.id async for _, info in tg.iter_chat_dialogs(client, main=False)]
    assert only_archive == [-1002, -1001]


async def test_sync_archived_sources_creates_once(db, monkeypatch):
    db.add_all([
        Source(name="Telegram: known_chan", kind="telegram_user", config={"chat": "@Known_Chan"}),
        Source(name="Telegram: -100555", kind="telegram_user", config={"chat": "-100555"}, enabled=False),
    ])
    await db.commit()
    chats = [
        tg.ChatInfo(-100111, "Known", "known_chan", "channel", True),   # username bo'yicha bor
        tg.ChatInfo(-100555, "Disabled", None, "group", True),          # ID bo'yicha bor (o'chiq) — tegilmaydi
        tg.ChatInfo(-100777, "Yopiq guruh", None, "group", True),
        tg.ChatInfo(-100888, "Ochiq kanal", "open_chan", "channel", True),
    ]
    now = datetime(2026, 11, 16, 12, 0, tzinfo=UTC)
    created = await telegram_archive.sync_archived_sources(db, chats, now=now)
    assert [s.name for s in created] == ["Telegram: Yopiq guruh [-100777]", "Telegram: Ochiq kanal [open_chan]"]

    rows = {s.config["chat"]: s for s in (await db.scalars(
        select(Source).where(Source.kind == "telegram_user"))).all() if "chat" in s.config}
    assert set(rows) == {"@Known_Chan", "-100555", "-100777", "open_chan"}
    priv, pub = rows["-100777"], rows["open_chan"]
    assert priv.translate is False and pub.translate is True  # yopiq guruh matni tarjimaga yuborilmaydi
    assert priv.enabled and priv.status == "never_run" and priv.state == {"origin": "archive"}
    assert priv.interval_seconds == 600 and priv.next_run_at > now
    assert rows["-100555"].enabled is False

    assert await telegram_archive.sync_archived_sources(db, chats, now=now) == []  # ikkinchi marta — hech narsa

    monkeypatch.setattr(settings, "tg_monitor_archived", False)
    assert await telegram_archive.maybe_sync() == 0  # sozlama o'chiq — Telegram'ga murojaat yo'q
