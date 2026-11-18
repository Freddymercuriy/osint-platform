"""Yangiliklar lentasi kanali: post ko'rinishi, rejalashtiruvchi, yuboruvchi va bot yangilanishlari (soxta Telegram)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import AdminAlert, BotChat, ChannelDestination, ChannelPost, EventRecord, EventTranslation, Source
from app.services.publisher import bot, planner, render, sender, updates
from app.services.publisher.outbox import get_state

TOKEN = "123456789:AAH-fake_TOKEN_value_abcdefghijklmnopqr"
CHAT = -1001234567890
FEED = {"lang": "uz-Cyrl", "countries": [], "include_global": True, "categories": [], "instant_min_band": "low",
        "daily_enabled": False, "weekly_enabled": False, "quiet_enabled": False, "max_instant_per_day": 1000,
        "show_original": False, "explain_terms": False, "require_translation": True}


@pytest.fixture(autouse=True)
def _token(monkeypatch):
    monkeypatch.setattr(settings, "tg_bot_token", TOKEN)
    monkeypatch.setattr(settings, "public_app_url", "")
    sender.rate.__init__()


class FakeTelegram:
    """Bot API: `sendMessage` → muvaffaqiyat (yoki navbatdagi tayyorlangan xato), so'rovlar yoziladi."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.errors: list[tuple[int, dict]] = []
        self.updates: list[dict] = []
        self.next_id = 100

    def handler(self, req: httpx.Request) -> httpx.Response:
        method = req.url.path.rsplit("/", 1)[-1]
        body = json.loads(req.content or b"{}")
        if method == "getUpdates":
            ups, self.updates = self.updates, []
            return httpx.Response(200, json={"ok": True, "result": ups})
        if method in ("sendMessage", "answerCallbackQuery"):
            if self.errors:
                code, extra = self.errors.pop(0)
                return httpx.Response(code, json={"ok": False, "error_code": code, **extra})
            self.sent.append(body)
            if method == "answerCallbackQuery":
                return httpx.Response(200, json={"ok": True, "result": True})
            self.next_id += 1
            ents = [{"type": "bold", "offset": 0, "length": 3}] if body.get("parse_mode") == "HTML" else []
            return httpx.Response(200, json={"ok": True, "result": {
                "message_id": self.next_id, "chat": {"id": body["chat_id"]}, "date": 1, "text": "x",
                "entities": ents}})
        return httpx.Response(200, json={"ok": True, "result": {}})

    def client(self) -> bot.BotClient:
        return bot.BotClient(TOKEN, transport=httpx.MockTransport(self.handler))


async def _no_sleep(_s: float) -> None:
    return None


async def _dest(db, **kw) -> ChannelDestination:
    d = ChannelDestination(name=kw.pop("name", "Lenta"), chat_id=kw.pop("chat_id", CHAT), chat_type="channel",
                           mode=kw.pop("mode", "auto"), status="ok",
                           enabled_at=kw.pop("enabled_at", datetime.now(UTC) - timedelta(hours=1)), **{**FEED, **kw})
    db.add(d)
    await db.commit()
    return d


async def _event(db, *, uid="e1", title="Hackers attacked a bank", summary="Details of the attack.", lang="en",
                 uz=("Xakerlar bankka hujum qildi", "Hujum tafsilotlari."), first_seen=None, **kw) -> EventRecord:
    ev = EventRecord(uid=uid, source=kw.pop("source", "Kun.uz"), category=kw.pop("category", "other"), title=title,
                     url=kw.pop("url", f"https://news.example/{uid}"), summary=summary, lang=lang,
                     severity=kw.pop("severity", "medium"), first_seen=first_seen or datetime.now(UTC),
                     scope=kw.pop("scope", "global"), **kw)
    db.add(ev)
    await db.flush()
    if uz is not None:
        db.add(EventTranslation(event_id=ev.id, lang="uz", title=uz[0], summary=uz[1], status="done",
                                provider="fake", translated_at=datetime.now(UTC)))
    else:
        db.add(EventTranslation(event_id=ev.id, lang="uz", status="pending"))
    await db.commit()
    return ev


async def _posts(db, d=None) -> list[ChannelPost]:
    stmt = select(ChannelPost).order_by(ChannelPost.id)
    if d is not None:
        stmt = stmt.where(ChannelPost.destination_id == d.id)
    return list((await db.scalars(stmt.execution_options(populate_existing=True))).all())


# ---------------------------------------------------------------- ko'rinish
def _view(**kw) -> render.EventView:
    base = dict(id=1, title="Xakerlar bankka hujum qildi", summary="Hujum tafsilotlari. Ikkinchi gap. Uchinchi gap.",
                url="https://kun.uz/news/1", when=datetime(2026, 11, 18, 9, 5, tzinfo=UTC), band="high",
                countries=["UZ"], scope="regional", category_slug="darkweb-sale", category_name="Ma'lumot savdosi",
                sector="finance", source="Kun.uz", reliability="media", action="Parollarni almashtirish.")
    base.update(kw)
    return render.EventView(**base)


def test_render_uzbek_cyrillic_post():
    r = render.render_event(_view(), "uz-Cyrl")
    lines = r.text.split("\n")
    assert lines[0] == "🟠 ЮҚОРИ · 🇺🇿 Ўзбекистон · Маълумот савдоси"
    assert lines[1] == "<b>Хакерлар банкка ҳужум қилди</b>"
    assert lines[2] == "<i>18-ноябрь, 14:05 (Тошкент)</i>"  # Toshkent vaqti (UTC+5)
    assert "Ҳужум тафсилотлари. Иккинчи гап." in r.text and "Учинчи" not in r.text  # 2 gap
    assert "<b>Ишончлилик:</b> ОАВ хабари · манба: Kun.uz" in r.text  # manba nomi o'girilmaydi
    assert "<b>Тавсия:</b> Паролларни алмаштириш." in r.text
    assert lines[-1] == "#UZ #darkweb_sale #finance"  # ASCII hashtag
    assert r.buttons == [[{"text": "Манбани очиш", "url": "https://kun.uz/news/1"}]]
    assert render.visible_len(r.text) <= render.ALERT_MAX


def test_render_scrubs_links_personal_data_and_escapes():
    v = _view(title="Leak <b>x</b> & co", band="low", action="",
              summary="Bog'laning: admin@bank.uz yoki +998 90 123 45 67, 90 123-45-67. Batafsil https://evil.example/x "
                      "va abcdefghijklmnop.onion/dump @leaker #leak 🔥🔥 1 500 000 ta yozuv.")
    r = render.render_event(v, "uz")
    for bad in ("admin@bank.uz", "+998", "123-45-67", "https://", ".onion", "@leaker", "#leak ", "🔥"):
        assert bad not in r.text
    assert "1 500 000 ta yozuv" in r.text  # yozuvlar soni telefon deb o'chirilmaydi
    assert "<b>Leak x &amp; co</b>" in r.text  # HTML qoldig'i olib tashlanadi, & escape
    assert "Tavsiya" not in r.text  # past band — tavsiya yo'q


@pytest.mark.parametrize("url", ["http://abcdefghijklmnop.onion/x", "https://files.example/dump.sql",
                                 "https://x.example/leak.ZIP", "javascript:alert(1)", "ftp://x.example/a", None])
def test_unsafe_urls_get_no_button(url):
    assert render.safe_url(url) is None
    assert render.render_event(_view(url=url), "uz").buttons == []


def test_render_confidence_and_outlet_dedupe():
    one = render.render_event(_view(source="CyberScoop (NewsNow)", also_sources=["CyberScoop"]), "en")
    assert "media report · source: CyberScoop" in one.text  # bitta nashr — "bir nechta manba" emas
    multi = render.render_event(_view(also_sources=["Gazeta.uz", "UzDaily"]), "en")
    assert "confirmed by several sources · 3 sources: Kun.uz, Gazeta.uz, UzDaily" in multi.text
    claim = render.render_event(_view(reliability="tracker", category_slug="ransomware"), "ru")
    assert "заявление группировки, не подтверждено" in claim.text
    under = render.render_event(_view(reliability="underground"), "uz")
    assert "yashirin kanaldagi da'vo, tasdiqlanmagan" in under.text


def test_render_global_and_untranslated_note():
    r = render.render_event(_view(countries=[], scope="global", band="critical", translated=False,
                                  title="Hackers attacked", summary=""), "uz-Cyrl")
    assert r.text.startswith("🔴 КРИТИК · 🌐 Глобал")
    assert "<b>Hackers attacked</b>" in r.text  # asl matn kirillga o'girilmaydi
    assert "Таржима ҳали тайёр эмас" in r.text and "#global" in r.text


def test_render_long_text_stays_on_one_screen():
    long = " ".join(f"Bu {i}-gap juda uzun bo'lib, hujum tafsilotlari haqida batafsil ma'lumot beradi." for i in range(30))
    r = render.render_event(_view(title="Sarlavha " * 20, summary=long, action="Tavsiya " * 60), "uz")
    assert render.visible_len(r.text) <= render.ALERT_MAX and len(r.text) <= render.TEXT_LIMIT


def test_quiet_window_crosses_midnight():
    assert planner.in_quiet(time(23, 0), time(22, 0), time(7, 0))
    assert planner.in_quiet(time(6, 59), time(22, 0), time(7, 0))
    assert not planner.in_quiet(time(7, 0), time(22, 0), time(7, 0))
    assert planner.in_quiet(time(13, 0), time(12, 0), time(14, 0)) and not planner.in_quiet(time(15, 0), time(12, 0),
                                                                                             time(14, 0))


# ---------------------------------------------------------------- rejalashtiruvchi
async def test_planner_posts_each_event_once_in_channel_language(db):
    d = await _dest(db)
    await _event(db, uid="a")
    await _event(db, uid="b", title="Other", uz=("Boshqa xabar", ""))
    stats = await planner.plan(db)
    assert stats.created == 2 and stats.by_status == {"queued": 2}
    again = await planner.plan(db)  # ikkinchi tick — takror yo'q
    assert again.created == 0
    posts = await _posts(db, d)
    assert [p.status for p in posts] == ["queued", "queued"] and all(p.lang == "uz-Cyrl" for p in posts)
    assert "<b>Хакерлар банкка ҳужум қилди</b>" in posts[0].text and posts[0].dedup_key.startswith("alert:")


async def test_planner_waits_for_translation_and_never_sends_original(db):
    d = await _dest(db)
    ev = await _event(db, uz=None)
    assert (await planner.plan(db)).waiting == 1 and await _posts(db, d) == []
    tr = await db.scalar(select(EventTranslation).where(EventTranslation.event_id == ev.id))
    tr.status, tr.title, tr.summary = "done", "Xakerlar bankka hujum qildi", ""
    await db.commit()
    assert (await planner.plan(db)).created == 1
    old = await _event(db, uid="old", uz=None, first_seen=datetime.now(UTC) - timedelta(hours=7))
    d.enabled_at = datetime.now(UTC) - timedelta(hours=8)
    await db.commit()
    await planner.plan(db)
    skipped = [p for p in await _posts(db, d) if old.id in p.event_ids]
    assert skipped[0].status == "skipped" and skipped[0].skip_reason == "translation_missing" and skipped[0].text == ""


async def test_planner_without_require_translation_falls_back_after_wait(db, monkeypatch):
    monkeypatch.setattr(settings, "publisher_translation_wait_minutes", 10)
    d = await _dest(db, require_translation=False, lang="uz")
    await _event(db, uid="fresh", uz=None)
    await _event(db, uid="late", uz=None, title="Late news", first_seen=datetime.now(UTC) - timedelta(minutes=15))
    await planner.plan(db)
    posts = await _posts(db, d)
    assert len(posts) == 1 and "<b>Late news</b>" in posts[0].text and "Tarjima hali tayyor emas" in posts[0].text


async def test_planner_respects_enabled_at_filters_and_modes(db):
    d = await _dest(db, enabled_at=datetime.now(UTC))  # yoqilgandan oldingi hodisa — chiqmaydi
    await _event(db, uid="before", first_seen=datetime.now(UTC) - timedelta(minutes=5))
    await _event(db, uid="base", is_baseline=True)
    assert (await planner.plan(db)).created == 0

    dry = await _dest(db, name="Dry", mode="dry_run", chat_id=None)
    regional = await _dest(db, name="UZ", countries=["UZ"], include_global=False)
    await _event(db, uid="g")  # global
    await _event(db, uid="uz", scope="regional", countries=["UZ"])
    await planner.plan(db)
    dry_posts = await _posts(db, dry)
    assert {p.status for p in dry_posts} == {"skipped"} and {p.skip_reason for p in dry_posts} == {"dry_run"}
    assert all(p.text for p in dry_posts)  # dry-run — matn to'liq saqlanadi
    assert [p.event_ids for p in await _posts(db, regional)] == [[(await db.scalar(
        select(EventRecord.id).where(EventRecord.uid == "uz")))]]


async def test_underground_only_waits_for_approval_and_cap_applies(db):
    src = Source(name="Leak chat", kind="telegram_user", reliability="underground", config={}, enabled=True)
    db.add(src)
    await db.commit()
    d = await _dest(db, max_instant_per_day=1)
    await _event(db, uid="u", source="Leak chat", source_id=src.id, category="leak")
    await _event(db, uid="m")
    await planner.plan(db)
    posts = await _posts(db, d)
    assert [p.status for p in posts] == ["awaiting_approval", "skipped"]
    assert posts[1].skip_reason == "daily_cap" and posts[0].meta["underground_only"] is True


async def test_quiet_hours_send_silently(db, monkeypatch):
    d = await _dest(db, quiet_enabled=True, quiet_start=time(0, 0), quiet_end=time(23, 59), quiet_policy="all_silent")
    await _event(db)
    await planner.plan(db)
    assert (await _posts(db, d))[0].silent is True


# ---------------------------------------------------------------- yuboruvchi
async def test_sender_sends_queued_with_buttons_and_marks_sent(db):
    d = await _dest(db)
    await _event(db)
    await planner.plan(db)
    tg = FakeTelegram()
    c = tg.client()
    stats = await sender.send_due(db, c, sleep=_no_sleep)
    assert stats.sent == 1
    body = tg.sent[0]
    assert body["chat_id"] == CHAT and body["parse_mode"] == "HTML"
    assert body["reply_markup"]["inline_keyboard"][0][0]["text"] == "Манбани очиш"
    assert body["link_preview_options"] == {"is_disabled": True}
    [p] = await _posts(db, d)
    assert p.status == "sent" and p.message_id == 101 and p.sent_at is not None
    await db.refresh(d)
    assert d.status == "ok" and d.last_success_at is not None
    await c.aclose()


async def test_sender_rate_limit_and_parse_error_fallback(db):
    d = await _dest(db)
    await _event(db, uid="a")
    await _event(db, uid="b")
    await planner.plan(db)
    tg = FakeTelegram()
    tg.errors = [(429, {"description": "Too Many Requests", "parameters": {"retry_after": 30}})]
    c = tg.client()
    stats = await sender.send_due(db, c, sleep=_no_sleep)
    assert stats.stopped == "rate_limited" and stats.sent == 0
    posts = await _posts(db, d)
    assert posts[0].status == "queued" and posts[0].next_attempt_at > datetime.now(UTC) + timedelta(seconds=20)

    await db.execute(ChannelPost.__table__.update().values(next_attempt_at=None))
    await db.commit()
    tg.errors = [(400, {"description": "Bad Request: can't parse entities: unexpected end tag"})]
    stats = await sender.send_due(db, c, sleep=_no_sleep)
    assert stats.sent == 2
    assert tg.sent[0].get("parse_mode") is None and "<b>" not in tg.sent[0]["text"]  # oddiy matn sifatida
    assert (await _posts(db, d))[0].meta.get("sent_plain") is True
    await c.aclose()


async def test_sender_forbidden_marks_channel_down_and_token_never_stored(db, caplog):
    d = await _dest(db)
    await _event(db)
    await planner.plan(db)
    tg = FakeTelegram()
    tg.errors = [(403, {"description": f"Forbidden: bot was kicked from the channel chat (bot{TOKEN})"})]
    c = tg.client()
    with caplog.at_level(logging.DEBUG):
        await sender.send_due(db, c, sleep=_no_sleep)
    await db.refresh(d)
    [p] = await _posts(db, d)
    assert d.status == "down" and p.status == "queued"
    alert = await db.scalar(select(AdminAlert).where(AdminAlert.kind == "channel_down"))
    assert alert is not None and alert.data["key"] == d.id
    for text in (p.last_error, d.last_error, json.dumps(alert.data), caplog.text):
        assert TOKEN not in (text or "") and "AAH-fake" not in (text or "")
    assert (await sender.send_due(db, c, sleep=_no_sleep)).sent == 0  # down kanalga yuborilmaydi
    await c.aclose()


async def test_sender_unauthorized_stops_everything(db):
    await _dest(db)
    await _event(db)
    await planner.plan(db)
    tg = FakeTelegram()
    tg.errors = [(401, {"description": "Unauthorized"})]
    c = tg.client()
    assert (await sender.send_due(db, c, sleep=_no_sleep)).stopped == "unauthorized"
    st = await get_state(db)
    assert st.bot_status == "invalid"
    assert (await sender.send_due(db, c, sleep=_no_sleep)).stopped == "invalid"
    assert await db.scalar(select(AdminAlert).where(AdminAlert.kind == "bot_token_invalid")) is not None
    await c.aclose()


async def test_sender_expires_old_alerts_and_recovers_sending(db):
    d = await _dest(db)
    await _event(db, uid="a")
    await _event(db, uid="b")
    await planner.plan(db)
    posts = await _posts(db, d)
    await db.execute(ChannelPost.__table__.update().where(ChannelPost.__table__.c.id == posts[0].id)
                     .values(created_at=datetime.now(UTC) - timedelta(hours=7)))
    await db.execute(ChannelPost.__table__.update().where(ChannelPost.__table__.c.id == posts[1].id)
                     .values(status="sending"))
    await db.commit()
    assert await sender.recover_sending(db) == 1
    tg = FakeTelegram()
    c = tg.client()
    stats = await sender.send_due(db, c, sleep=_no_sleep)
    assert stats.expired == 1 and stats.sent == 0
    posts = await _posts(db, d)
    assert [p.status for p in posts] == ["expired", "unknown"]
    assert await db.scalar(select(AdminAlert).where(AdminAlert.kind == "post_unknown")) is not None
    await c.aclose()


async def test_rate_state_spacing_and_minute_cap():
    r = sender.RateState()
    assert r.delay(1, 100.0) == 0
    r.mark(1, 100.0)
    assert r.delay(1, 100.5) == pytest.approx(0.6)
    for i in range(sender.PER_MINUTE - 1):
        r.mark(1, 101.0 + i * 1.2)
    assert r.delay(1, 125.0) == pytest.approx(35.0)  # 18 ta / daqiqa — birinchisi 60 s o'tguncha kutadi


# ---------------------------------------------------------------- yangilanishlar
async def test_updates_track_chats_and_destination_health(db):
    d = await _dest(db)
    tg = FakeTelegram()
    member = {"chat": {"id": CHAT, "type": "channel", "title": "Yangiliklar"},
              "from": {"id": 7, "first_name": "Ali"}, "date": 1,
              "new_chat_member": {"status": "administrator", "can_post_messages": True, "user": {"id": 1}}}
    tg.updates = [{"update_id": 10, "my_chat_member": member},
                  {"update_id": 11, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7,
                                                "language_code": "ru"}, "text": "/start"}}]
    c = tg.client()
    assert await updates.poll_once(db, c, timeout=0) == 2
    chat = await db.get(BotChat, CHAT)
    assert chat.title == "Yangiliklar" and chat.status == "administrator" and chat.added_by_name == "Ali"
    assert "Ваш Telegram ID: 7" in tg.sent[0]["text"]
    st = await get_state(db)
    assert st.updates_offset == 12

    removed = {**member, "new_chat_member": {"status": "left", "user": {"id": 1}}}
    tg.updates = [{"update_id": 12, "my_chat_member": removed}]
    await updates.poll_once(db, c, timeout=0)
    await db.refresh(d)
    assert d.status == "down"
    tg.updates = [{"update_id": 13, "my_chat_member": member}]
    await updates.poll_once(db, c, timeout=0)
    await db.refresh(d)
    assert d.status == "ok"
    assert await db.scalar(select(AdminAlert).where(AdminAlert.kind == "channel_down",
                                                    AdminAlert.resolved_at.is_(None))) is None
    await c.aclose()


# ---------------------------------------------------------------- runner: bot holati bazadagi cheklovga mos
@pytest.mark.parametrize("webhook,code,expected", [("", 200, "ok"), ("https://other.example/hook", 200, "conflict"),
                                                    ("", 401, "invalid"), ("", 502, "error")])
async def test_check_bot_status_is_stored(db, webhook, code, expected):
    from app.services.publisher import runner

    def handler(req: httpx.Request) -> httpx.Response:
        if code != 200:
            return httpx.Response(code, json={"ok": False, "error_code": code, "description": "x"})
        if req.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"id": 5, "username": "lenta_bot"}})
        return httpx.Response(200, json={"ok": True, "result": {"url": webhook}})

    c = bot.BotClient(TOKEN, transport=httpx.MockTransport(handler))
    assert await runner.check_bot(c) == expected
    st = await get_state(db)
    await db.refresh(st)
    assert st.bot_status == expected
    await runner._set_status("missing")  # token yo'q holati ham cheklovdan o'tadi
    await c.aclose()
