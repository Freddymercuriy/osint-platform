"""Dialoglar ro'yxatining birinchi `TG_DIALOG_LIMIT` tasidan tashqaridagi chat (kam yoziladigan kanal ro'yxat pastida):
to'g'ridan-to'g'ri aniqlanadi — faqat akkaunt a'zo bo'lsa o'qiladi."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import telegram_user as tg


class _Channel:
    def __init__(self, id_, username, left=False, megagroup=False):
        self.id, self.username, self.left, self.megagroup = id_, username, left, megagroup


class _User:
    def __init__(self, id_, username):
        self.id, self.username = id_, username


class _Client:
    def __init__(self, dialogs, entities):
        self.dialogs, self.entities, self.resolved = dialogs, entities, []

    async def iter_dialogs(self, limit=None, folder=None):
        for d in (self.dialogs if folder == 0 else [])[:limit]:
            yield d

    async def get_input_entity(self, key):
        if key not in self.entities:
            raise ValueError(f'No user has "{key}" as username')
        self.resolved.append(key)
        return key

    async def get_entity(self, peer):
        return self.entities[peer]

    async def iter_messages(self, entity, limit=None, min_id=0):
        for i in (3, 2, 1):
            if i > min_id:
                yield SimpleNamespace(id=i, message=f"{entity.username} {i}", date=None)


@pytest.fixture
def tgc(monkeypatch):
    monkeypatch.setattr(tg, "Channel", _Channel)
    monkeypatch.setattr(tg, "_dialog_cache", {})
    monkeypatch.setattr(tg, "_dialog_cache_at", 0.0)
    monkeypatch.setattr(settings, "tg_dialog_limit", 2)
    monkeypatch.setattr("telethon.utils.get_peer_id", lambda e: -1000000000000 - e.id)
    monkeypatch.setattr("telethon.utils.get_display_name", lambda e: f"Title {e.username}")
    top = [SimpleNamespace(id=-1000000000000 - n, name=f"Top {n}", entity=_Channel(n, f"top{n}")) for n in (1, 2)]
    c = _Client(top, {
        "crackedstatusupdate": _Channel(138, "crackedstatusupdate"),  # ro'yxatda 138-o'rinda, a'zo
        "leftchan": _Channel(50, "leftchan", left=True),                # a'zolikdan chiqilgan
        "somebot": _User(7, "somebot"),                                 # shaxsiy suhbat / bot
    })

    async def _get_client():
        return c

    monkeypatch.setattr(tg, "get_client", _get_client)
    return c


async def test_chat_beyond_dialog_limit_is_resolved_and_cached(tgc):
    msgs = await tg.fetch_chat_messages("@CrackedStatusUpdate", limit=10, min_id=1)
    assert [(m.msg_id, m.text) for m in msgs] == [(3, "crackedstatusupdate 3"), (2, "crackedstatusupdate 2")]
    assert msgs[0].chat.id == -1000000000138 and msgs[0].chat.kind == "channel"
    assert msgs[0].url == "https://t.me/crackedstatusupdate/3"
    await tg.fetch_chat_messages("crackedstatusupdate", limit=10)
    assert tgc.resolved == ["crackedstatusupdate"]  # ikkinchi yig'ish — keshdan


async def test_chat_in_dialog_list_is_not_resolved(tgc):
    assert len(await tg.fetch_chat_messages("top2", limit=10)) == 3
    assert tgc.resolved == []


@pytest.mark.parametrize("chat", ["leftchan", "somebot", "no_such_chat"])
async def test_not_member_or_not_a_chat_still_fails(tgc, chat):
    with pytest.raises(ValueError, match="Chat topilmadi yoki akkaunt a'zo emas"):
        await tg.fetch_chat_messages(chat, limit=10)


class _ListClient:
    def __init__(self, folders):
        self.folders, self.calls = folders, []

    async def iter_dialogs(self, limit=None, folder=None):
        self.calls.append((folder, limit))
        for d in self.folders.get(folder, [])[:limit]:
            yield d


async def test_picker_list_is_full_and_cached(monkeypatch):
    """Admin chat tanlash ro'yxati — `TG_DIALOG_LIMIT` chegarasisiz, 5 daqiqa keshlanadi, `refresh` qayta o'qiydi."""
    monkeypatch.setattr(tg, "Channel", _Channel)
    monkeypatch.setattr(tg, "_all_chats", [])
    monkeypatch.setattr(settings, "tg_dialog_limit", 2)
    main = [SimpleNamespace(id=-1000000000000 - n, name=f"Chan {n}", entity=_Channel(n, f"chan{n}")) for n in range(5)]
    c = _ListClient({0: main, 1: []})

    async def _get_client():
        return c

    monkeypatch.setattr(tg, "get_client", _get_client)
    assert len(await tg.list_chats()) == 2  # yig'uvchi chegarasi o'zgarmagan
    assert len(await tg.list_chats(full=True)) == 5
    assert c.calls[-2:] == [(0, None), (1, None)]
    n = len(c.calls)
    await tg.list_chats(full=True)
    assert len(c.calls) == n  # keshdan
    await tg.list_chats(full=True, refresh=True)
    assert len(c.calls) == n + 2


async def test_chats_endpoint_marks_monitored(db, client, admin_headers, monkeypatch):
    from app.models import Source

    db.add_all([
        Source(name="Telegram: chan1", kind="telegram_user", config={"chat": "@Chan1"}),
        Source(name="Telegram: -100777", kind="telegram_user", config={"chat": "-100777"}, enabled=False),
    ])
    await db.commit()

    async def fake_list(*, full=False, refresh=False):
        assert full
        return [tg.ChatInfo(-1001, "Chan 1", "chan1", "channel"), tg.ChatInfo(-100777, "Closed", None, "group"),
                tg.ChatInfo(-1002, "New", "newchan", "channel", archived=True)]

    monkeypatch.setattr(tg, "list_chats", fake_list)
    r = await client.get("/api/telegram/chats", headers=admin_headers)
    assert r.status_code == 200
    assert [(x["username"], x["monitored"], x["archived"]) for x in r.json()] == [
        ("chan1", True, False), (None, True, False), ("newchan", False, True)]
