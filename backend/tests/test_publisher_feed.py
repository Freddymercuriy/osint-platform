"""Yangiliklar lentasi kanali: post ko'rinishi, rejalashtiruvchi, yuboruvchi va bot yangilanishlari (soxta Telegram)."""

from __future__ import annotations

import json
import logging
from email import policy as email_policy
from email.parser import BytesParser
from datetime import UTC, datetime, time, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import AdminAlert, BotChat, ChannelDestination, ChannelPost, EventRecord, EventTranslation, Source
from app.services.publisher import bot, planner, render, sender, stories, updates
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
    stories.clear_cache()


def _multipart(req: httpx.Request) -> dict:
    """multipart/form-data (sendPhoto) → maydonlar (JSON qiymatlar ochiladi) + "photo" baytlari, fayl nomi, turi."""
    msg = BytesParser(policy=email_policy.default).parsebytes(
        b"Content-Type: " + req.headers["content-type"].encode() + b"\r\n\r\n" + req.read())
    out: dict = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        data = part.get_payload(decode=True)
        if part.get_filename():
            out[name], out[f"{name}_filename"], out[f"{name}_type"] = data, part.get_filename(), part.get_content_type()
            continue
        text = data.decode()
        try:
            out[name] = json.loads(text) if text[:1] in "[{" or text.lstrip("-").isdigit() else text
        except ValueError:
            out[name] = text
    return out


class FakeTelegram:
    """Bot API: `sendMessage` / `sendPhoto` → muvaffaqiyat (yoki navbatdagi tayyorlangan xato), so'rovlar yoziladi."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.methods: list[str] = []
        self.errors: list[tuple[int, dict]] = []
        self.updates: list[dict] = []
        self.next_id = 100

    def handler(self, req: httpx.Request) -> httpx.Response:
        method = req.url.path.rsplit("/", 1)[-1]
        multipart = req.headers.get("content-type", "").startswith("multipart/")
        body = _multipart(req) if multipart else json.loads(req.content or b"{}")
        if method == "getUpdates":
            ups, self.updates = self.updates, []
            return httpx.Response(200, json={"ok": True, "result": ups})
        if method in ("sendMessage", "sendPhoto", "answerCallbackQuery"):
            if self.errors:
                code, extra = self.errors.pop(0)
                return httpx.Response(code, json={"ok": False, "error_code": code, **extra})
            self.sent.append(body)
            self.methods.append(method)
            if method == "answerCallbackQuery":
                return httpx.Response(200, json={"ok": True, "result": True})
            self.next_id += 1
            ents = [{"type": "bold", "offset": 0, "length": 3}] if body.get("parse_mode") == "HTML" else []
            result = {"message_id": self.next_id, "chat": {"id": body["chat_id"]}, "date": 1}
            if method == "sendPhoto":
                result.update(caption="x", caption_entities=ents, photo=[{"file_id": "f", "width": 1280}])
            else:
                result.update(text="x", entities=ents)
            return httpx.Response(200, json={"ok": True, "result": result})
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
                sector="finance", source="Kun.uz", reliability="media", action="Parollarni almashtirish.",
                rubric="cyber")
    base.update(kw)
    return render.EventView(**base)


def test_render_uzbek_cyrillic_post():
    r = render.render_event(_view(), "uz-Cyrl")
    lines = r.text.split("\n")
    assert lines[0] == "🛡 <b>КИБЕРХАВФСИЗЛИК</b> | <b>🇺🇿 ЎЗБЕКИСТОН</b>"  # rubrika | hudud
    assert lines[1] == "🟠 <b>ЮҚОРИ ДАРАЖА</b>"
    assert lines[3] == "<b>Хакерлар банкка ҳужум қилди</b>"
    assert lines[4] == "<i>18-ноябрь, 14:05 (Тошкент)</i>"  # Toshkent vaqti (UTC+5)
    assert "Ҳужум тафсилотлари. Иккинчи гап." in r.text and "Учинчи" not in r.text  # 2 gap
    assert "📌 <b>АСОСИЙ МАЪЛУМОТЛАР</b>\n• Соҳа: Молия" in r.text
    assert "✅ <b>ТАВСИЯ</b>\nПаролларни алмаштириш." in r.text
    assert "🔎 <b>Манба:</b> Kun.uz · <i>ОАВ хабари</i>" in r.text  # manba nomi o'girilmaydi
    assert lines[-1] == "#UZ #darkweb_sale #finance"  # ASCII hashtag
    assert r.buttons == [[{"text": "🌐 Асл манбани очиш", "url": "https://kun.uz/news/1"}]]
    assert render.tg_len(r.text) <= render.POST_BUDGET and r.more == ""


def test_render_structured_facts_only_from_the_source():
    v = _view(category_slug="ransomware", actor="Akira", cves=["CVE-2026-114938"], cvss="9.8", records=1_200_000,
              countries=["UZ"], reasons=[{"code": "country_uz", "points": 30}, {"code": "sector", "arg": "finance"},
                                         {"code": "records_1m", "arg": 1_200_000}, {"code": "official_source"}])
    r = render.render_event(v, "uz")
    assert "• CVE: CVE-2026-114938" in r.text and "• CVSS bahosi: 9.8" in r.text and "• Guruh: Akira" in r.text
    assert "• Yozuvlar soni: 1 200 000" in r.text
    # nima uchun muhim — faqat sabablardan; "rasmiy manba" ishonchlilik qatorida, bu yerda takrorlanmaydi
    assert "⚠️ <b>NIMA UCHUN MUHIM?</b>\nO'zbekistondagi moliya tashkiloti; taxminan 1 200 000 ta yozuv." in r.text
    low = render.render_event(_view(band="low", sector=None, reasons=v.reasons), "uz")
    assert "DARAJA" not in low.text and "MUHIM" not in low.text and "TAVSIYA" not in low.text
    assert "ASOSIY" not in low.text  # ko'rsatadigan maydon yo'q — bo'lim ham yo'q (hech narsa o'ylab topilmaydi)


@pytest.mark.parametrize("text,cves,cvss", [
    ("Critical flaw CVE-2026-114938 (CVSS 9.8) and cve-2025-1234", ["CVE-2026-114938", "CVE-2025-1234"], "9.8"),
    ("CVSS v3.1 score of 7,5 for CVE-2024-00001x", [], "7.5"),
    ("CVSS v3.1 bo'yicha baholanmagan", [], None),
    ("Uyazvimost s otsenkoy CVSS: 10.0", [], "10.0"),
])
def test_cve_and_cvss_are_taken_verbatim(text, cves, cvss):
    assert render.cves_in(text) == cves and render.cvss_in(text) == cvss


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
    assert "🔎 <b>Source:</b> CyberScoop · <i>media report</i>" in one.text  # bitta nashr — "bir nechta" emas
    multi = render.render_event(_view(also_sources=["Gazeta.uz", "UzDaily"]), "en")
    assert "<b>Source:</b> Kun.uz, Gazeta.uz, UzDaily · <i>confirmed by several sources</i>" in multi.text
    claim = render.render_event(_view(reliability="tracker", category_slug="ransomware"), "ru")
    assert "заявление группировки, не подтверждено" in claim.text
    under = render.render_event(_view(reliability="underground"), "uz")
    assert "yashirin kanaldagi da'vo, tasdiqlanmagan" in under.text


def test_render_global_and_untranslated_note():
    r = render.render_event(_view(countries=[], scope="global", band="critical", translated=False,
                                  title="Hackers attacked", summary="", rubric="ai"), "uz-Cyrl")
    assert r.text.startswith("🤖 <b>СУНЪИЙ ИНТЕЛЛЕКТ</b> | <b>🌍 ДУНЁ</b>\n🔴 <b>КРИТИК ДАРАЖА</b>")
    assert "<b>Hackers attacked</b>" in r.text  # asl matn kirillga o'girilmaydi
    assert "Таржима ҳали тайёр эмас" in r.text and "#global" in r.text
    ca = render.render_event(_view(countries=[], scope="regional"), "ru")
    assert "🌏 ЦЕНТРАЛЬНАЯ АЗИЯ" in ca.text.split("\n")[0]


def test_render_long_caption_moves_sections_to_a_reply():
    long = " ".join(f"Bu {i}-gap juda uzun bo'lib, hujum tafsilotlari haqida batafsil ma'lumot beradi." for i in range(30))
    v = _view(title="Sarlavha " * 20, summary=long, action="Tizimlarni tekshirish va yangilash. " * 20,
              cves=[f"CVE-2026-{i:05d}" for i in range(5)], actor="Akira", category_slug="ransomware",
              records=5_000_000)
    r = render.render_event(v, "uz", photo=True)
    assert render.tg_len(r.text) <= render.CAPTION_LIMIT  # izoh chegarasi (UTF-16)
    assert "<b>Sarlavha" in r.text and "🔎 <b>Manba:</b>" in r.text and "#UZ" in r.text  # asosiysi izohda
    assert "• CVE: CVE-2026-00000, CVE-2026-00001, CVE-2026-00002" in r.text  # ma'lumotlar izohda (3 qator)
    assert "Yozuvlar soni" not in r.text and "TAVSIYA" not in r.text
    assert r.more.startswith("✅ <b>TAVSIYA</b>\nTizimlarni tekshirish")  # sig'magan bo'lim — javob xabarida
    huge = render.render_event(_view(**{**v.__dict__, "title": "Sarlavha " * 80}), "uz", photo=True)
    assert render.tg_len(huge.text) <= render.CAPTION_LIMIT and "ASOSIY" not in huge.text
    assert huge.more.startswith("📌 <b>ASOSIY MA'LUMOTLAR</b>") and "• Yozuvlar soni: 5 000 000" in huge.more
    assert "✅ <b>TAVSIYA</b>" in huge.more and huge.more.count("<b>") == huge.more.count("</b>")
    assert render.render_event(_view(), "uz", photo=True).more == ""  # sig'adigan post — bitta xabar


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
    await _event(db, uid="g", title="Ransomware hits a port", uz=("Ransomware portni to'xtatib qo'ydi", ""))  # global
    await _event(db, uid="uz", scope="regional", countries=["UZ"], title="Leak in Tashkent",
                 uz=("Toshkentdagi klinika bazasi sizib chiqdi", ""))
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
    await _event(db, uid="m", title="Phishing wave", uz=("Fishing to'lqini pochtalarga tarqalmoqda", ""))
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
    assert stats.sent == 1 and tg.methods == ["sendPhoto"]
    body = tg.sent[0]
    assert body["chat_id"] == CHAT and body["parse_mode"] == "HTML" and "<b>" in body["caption"]
    assert body["photo"][:3] == b"\xff\xd8\xff" and body["photo_type"] == "image/jpeg"  # JPEG, 1280×720
    assert body["photo_filename"].endswith(".jpg")
    assert body["reply_markup"]["inline_keyboard"][0][0]["text"] == "🌐 Асл манбани очиш"
    [p] = await _posts(db, d)
    assert p.status == "sent" and p.message_id == 101 and p.sent_at is not None
    assert p.meta["image"]["kind"] == "generated" and p.meta["rubric"] == "cyber"
    await db.refresh(d)
    assert d.status == "ok" and d.last_success_at is not None
    await c.aclose()


async def test_sender_rate_limit_and_parse_error_fallback(db):
    d = await _dest(db)
    await _event(db, uid="a")
    await _event(db, uid="b", title="Phishing wave", uz=("Fishing to'lqini pochtalarga tarqalmoqda", ""))
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
    assert tg.sent[0].get("parse_mode") is None and "<b>" not in tg.sent[0]["caption"]  # oddiy matn sifatida
    assert tg.sent[0]["photo"][:3] == b"\xff\xd8\xff"  # rasm baribir bor
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


async def test_channel_discovered_from_channel_post_and_forward(db):
    st = await get_state(db)
    st.bot_id = 555
    await db.commit()
    calls: list[dict] = []
    tg = FakeTelegram()
    base = tg.handler

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/getChatMember"):
            calls.append(json.loads(req.content))
            return httpx.Response(200, json={"ok": True, "result": {
                "status": "administrator", "can_post_messages": True, "user": {"id": 555}}})
        return base(req)

    c = bot.BotClient(TOKEN, transport=httpx.MockTransport(handler))
    channel = {"id": CHAT, "type": "channel", "title": "osint"}
    tg.updates = [{"update_id": 1, "channel_post": {"message_id": 3, "chat": channel, "date": 1, "text": "test"}},
                  {"update_id": 2, "channel_post": {"message_id": 4, "chat": channel, "date": 1, "text": "yana"}}]
    await updates.poll_once(db, c, timeout=0)
    chat = await db.get(BotChat, CHAT)
    assert chat.title == "osint" and chat.status == "administrator" and chat.rights["can_post_messages"] is True
    assert calls == [{"chat_id": CHAT, "user_id": 555}]  # ma'lum chat har postda qayta so'ralmaydi

    other = {"id": -1009, "type": "channel", "title": "Boshqa"}
    tg.updates = [{"update_id": 3, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7},
                                               "forward_origin": {"type": "channel", "chat": other, "message_id": 1,
                                                                  "date": 1}}}]
    await updates.poll_once(db, c, timeout=0)
    assert (await db.get(BotChat, -1009)).status == "administrator"
    assert "Kanal topildi: «Boshqa»" in tg.sent[-1]["text"]
    await c.aclose()


# ---------------------------------------------------------------- bitta voqea — bitta post
# Jonli bazadagi (2026-11-18) hujjat chastotalari: 1665 o'zbekcha tarjima, umumiy so'zlar ko'p uchraydi
_DF = {"2.1": 4, "2026": 423, "aniql": 109, "apach": 10, "aqsh": 35, "aybla": 15, "dastu": 175, "ekspe": 12,
       "ekstr": 14, "etild": 21, "faol": 37, "firib": 50, "fosh": 11, "foyda": 284, "gumon": 19, "guruh": 74,
       "hujum": 302, "itali": 12, "java": 17, "kaspe": 12, "kiber": 294, "kishi": 25, "kompa": 137, "kriti": 17,
       "milli": 96, "mlrd": 5, "nisho": 49, "olind": 7, "ozbek": 25, "qildi": 112, "qilin": 118, "qilis": 187,
       "qolga": 22, "qozog": 30, "ranso": 47, "rezet": 5, "serve": 123, "shaxs": 57, "shifo": 9, "tahdi": 68,
       "toxta": 42, "xaker": 176, "xalqa": 15, "zaifl": 316, "zarar": 154}
_CORPUS = stories.Corpus(n=1665, df=__import__("collections").Counter(_DF))
_T0 = datetime(2026, 11, 18, 8, 0, tzinfo=UTC)


def _story(i, title, summary="", *, source="Src", lang="en", countries=("KZ",), hours=0.0) -> stories.Story:
    ev = EventRecord(id=i, source=source, lang=lang, countries=list(countries), first_seen=_T0 + timedelta(hours=hours))
    return stories.make(_CORPUS, ev, title, summary, "uz")


@pytest.mark.parametrize("a,b", [
    (("Qozog'istonlik ransomware xakerlaridan gumon qilinayotgan shaxs Italiyadan ekstraditsiya qilindi", ""),
     ("Ransomware guruhining gumon qilingan a'zosi Italiyadan AQShda shifoxonada, maktabda ta'qib qilish ishi "
      "bo'yicha ayblovlarga duch kelishi uchun ekstraditsiya qilindi",
      "AQSh shifoxonalari va maktablarini nishonga olgan ransomware va o'g'irlash fitnasida ayblangan Qozog'iston "
      "fuqarosi")),
    (("Rezet xakerlari O'zbekiston va MDH kompaniyalariga hujum qildi", ""),
     ("Rezet xakerlari O'zbekiston va MDHdagi kompaniyalarni nishonga olmoqda",
      "F6 xabar berishicha, Rezet kiber-jasuslik guruhi O'zbekiston kompaniyalariga qarshi fishing kampaniyalarini")),
    (("Kaspersky kompaniyasi O'zbekistonda 2,1 million firibgarlik urinishlarini to'xtatdi",
      "Kaspersky kompaniyasi O'zbekistondagi 2,1 million firibgarlik veb-saytlariga kirish urinishlarini to'xtatdi"),
     ("2,1 mln bloklangan fishin o'tish yo'li: Kasperskiy laboratoriyasi ekspertlari O'zbekistondagi kiber "
      "tahdidlar haqida", "O'zbekistonda foydalanuvchilarning yarmidan ko'pi mahalliy kiber tahdidlarga duchor")),
])
def test_same_story_across_outlets_and_languages(a, b):
    assert stories.same_story(_story(1, *a), _story(2, *b, source="Other", lang="ru", hours=5), _CORPUS)


def test_different_stories_stay_separate():
    # umumiy so'zlar ("fosh etildi", "kiberjinoiy guruh") voqeani ajratmaydi
    gang = _story(1, "Mirobod tumanida xalqaro kiberjinoiy guruhlar fosh etildi – 72 kishi qo'lga olindi",
                  countries=())
    fraud = _story(2, "O'zbekistonda 83 kishini qariyb 1 mlrd so'mga aldagan kiberjinoiy guruh fosh etildi",
                   source="Daryo", countries=("UZ",))
    assert not stories.same_story(gang, fraud, _CORPUS)
    # bir manbaning bir tildagi turli e'lonlari
    apache = _story(3, "Apache HTTP Server dasturidagi kritik zaiflikdan kiberhujumlarda faol foydalanilmoqda!",
                    source="UZCERT", lang="uz")
    java = _story(4, "OpenJDK dasturidagi kritik Java4Shell zaifligi serverlarda kod bajarish imkonini beradi",
                  source="UZCERT", lang="uz")
    assert not stories.same_story(apache, java, _CORPUS)
    # boshqa davlat yoki 48 soatdan uzoq — boshqa voqea
    rezet = ("Rezet xakerlari O'zbekiston va MDH kompaniyalariga hujum qildi", "")
    assert not stories.same_story(_story(5, *rezet, countries=("UZ",)), _story(6, *rezet, countries=("KZ",)), _CORPUS)
    assert not stories.same_story(_story(7, *rezet), _story(8, *rezet, source="B", hours=49), _CORPUS)
    assert stories.same_story(_story(9, *rezet), _story(10, *rezet, source="B", hours=47), _CORPUS)


async def test_planner_skips_story_already_posted_by_another_outlet(db):
    d = await _dest(db)
    first = await _event(db, uid="rec", source="The Record", title="Kazakh ransomware suspect extradited from Italy",
                         uz=("Qozog'istonlik ransomware xakerlaridan gumon qilinayotgan shaxs Italiyadan "
                             "ekstraditsiya qilindi", ""))
    await planner.plan(db)
    dup = await _event(db, uid="cs", source="CyberScoop", title="Alleged ransomware member extradited from Italy",
                       uz=("Ransomware guruhining gumon qilinayotgan a'zosi Italiyadan ekstraditsiya qilindi", ""))
    other = await _event(db, uid="ph", source="CyberScoop", title="Phishing wave",
                         uz=("Fishing to'lqini O'zbekiston pochtalariga tarqalmoqda", ""))
    stats = await planner.plan(db)
    assert stats.by_status == {"queued": 1, "skipped": 1}
    posts = {p.event_ids[0]: p for p in await _posts(db, d)}
    assert posts[first.id].status == "queued" and posts[other.id].status == "queued"
    skipped = posts[dup.id]
    assert skipped.status == "skipped" and skipped.skip_reason == "duplicate" and skipped.text == ""
    assert skipped.meta == {"duplicate_of_event": first.id, "duplicate_of_post": posts[first.id].id}


async def test_duplicates_within_one_tick_and_dry_run(db):
    d = await _dest(db, name="Dry", mode="dry_run", chat_id=None)
    texts = ["Rezet xakerlari O'zbekiston va MDH kompaniyalariga hujum qildi",
             "Rezet xakerlari O'zbekiston va MDHdagi kompaniyalarni nishonga olmoqda"]
    for i, text in enumerate(texts):
        await _event(db, uid=f"r{i}", source=f"Outlet {i}", title=f"Rezet {i}", uz=(text, ""))
    await planner.plan(db)
    posts = await _posts(db, d)
    assert [(p.status, p.skip_reason) for p in posts] == [("skipped", "dry_run"), ("skipped", "duplicate")]
    # uchinchi nusxa faqat takrorga o'xshaydi — u ham asl postga bog'lanadi (keyingi tick, bazadan o'qiladi)
    third_ev = await _event(db, uid="r2", source="Outlet 2", title="Rezet 2",
                            uz=("MDHdagi kompaniyalarni nishonga olmoqda: yangi kampaniya", ""))
    stories.clear_cache()
    await planner.plan(db)
    third = (await _posts(db, d))[-1]
    assert third.event_ids == [third_ev.id] and third.skip_reason == "duplicate"
    assert third.meta == {"duplicate_of_event": posts[1].event_ids[0], "duplicate_of_post": posts[0].id}



# ---------------------------------------------------------------- rasmli post, davom xabari
async def _long_post_event(db):
    from app.models import Category

    cat = await db.scalar(select(Category).where(Category.slug == "vulnerability"))
    cat.action_uz = "Ta'sirlangan tizimlarni aniqlab, ishlab chiqaruvchi yangilanishini o'rnating. " * 6
    await db.commit()
    summary = " ".join(f"{i}-gap: zaiflik masofadan kod bajarishga olib kelishi mumkin." for i in range(8))
    return await _event(db, uid="long", category="vulnerability", priority_band="high", countries=["UZ"],
                        scope="regional", title="Critical OpenJDK flaw CVE-2026-114938 (CVSS 9.8) exploited",
                        summary="Java4Shell CVE-2026-114938 lets attackers run code.", actor="Unknown",
                        uz=("OpenJDK dasturidagi kritik Java4Shell zaifligi " * 6, summary))


async def test_photo_post_with_followup_reply_in_order(db):
    d = await _dest(db, lang="uz")
    ev = await _long_post_event(db)
    await planner.plan(db)
    main, more = await _posts(db, d)
    assert main.kind == "alert" and main.photo[:3] == b"\xff\xd8\xff" and main.meta["image"]["kind"] == "generated"
    assert "• CVE: CVE-2026-114938" in main.text + more.text and "CVSS bahosi: 9.8" in main.text + more.text
    assert more.kind == "followup" and more.reply_to_post_id == main.id and more.silent and more.photo is None
    assert more.dedup_key == f"followup:{ev.id}" and "TAVSIYA" in more.text
    tg = FakeTelegram()
    c = tg.client()
    stats = await sender.send_due(db, c, sleep=_no_sleep)
    assert stats.sent == 2 and tg.methods == ["sendPhoto", "sendMessage"]
    reply = tg.sent[1]
    assert reply["reply_parameters"]["message_id"] == 101 and reply["disable_notification"] is True
    assert (await planner.plan(db)).created == 0  # qayta rejalashtirilmaydi
    await c.aclose()


async def test_followup_waits_for_parent_and_is_dropped_if_parent_fails(db):
    d = await _dest(db, lang="uz")
    await _long_post_event(db)
    await planner.plan(db)
    main, more = await _posts(db, d)
    tg = FakeTelegram()
    tg.errors = [(429, {"description": "Too Many Requests", "parameters": {"retry_after": 30}})]
    c = tg.client()
    await sender.send_due(db, c, sleep=_no_sleep)
    assert tg.sent == [] and (await _posts(db, d))[1].status == "queued"  # asl post kutmoqda — javob ham
    main.status, main.next_attempt_at = "failed", None
    await db.commit()
    await sender.send_due(db, c, sleep=_no_sleep)
    more = (await _posts(db, d))[1]
    assert more.status == "skipped" and more.skip_reason == "parent_not_sent" and tg.sent == []
    await c.aclose()


async def test_planner_waits_for_article_image_then_draws_one(db, monkeypatch):
    from app.services.media import service as media_service

    monkeypatch.setattr(settings, "publisher_image_wait_minutes", 3)
    d = await _dest(db)
    ev = await _event(db, uid="img")
    stats = await planner.plan(db)
    assert stats.waiting == 1 and await _posts(db, d) == []  # fon ishchisi maqola rasmini qidirmoqda
    await media_service.ensure_image(db, ev, fetch=True)  # ishchi o'z ishini qildi (rasm topilmadi)
    await db.commit()
    assert (await planner.plan(db)).created == 1
    [p] = await _posts(db, d)
    assert p.photo and p.meta["image"]["kind"] == "generated"
    late = await _event(db, uid="late", title="Phishing wave", uz=("Fishing to'lqini pochtalarga tarqalmoqda", ""),
                        first_seen=datetime.now(UTC) - timedelta(minutes=4))
    await planner.plan(db)  # 3 daqiqadan oshgan — kutilmaydi, illyustratsiya darhol chiziladi
    assert any(late.id in x.event_ids and x.photo for x in await _posts(db, d))


async def test_rejected_photo_is_resent_with_fallback_image(db):
    d = await _dest(db)
    await _event(db)
    await planner.plan(db)
    tg = FakeTelegram()
    tg.errors = [(400, {"description": "Bad Request: IMAGE_PROCESS_FAILED"})]
    c = tg.client()
    assert (await sender.send_due(db, c, sleep=_no_sleep)).sent == 1
    [p] = await _posts(db, d)
    assert p.status == "sent" and p.meta["photo_fallback"] is True and tg.methods == ["sendPhoto"]
    assert tg.sent[0]["photo"][:3] == b"\xff\xd8\xff"  # post rasmsiz chiqmadi
    await c.aclose()


async def test_text_mode_when_photos_are_disabled(db, monkeypatch):
    monkeypatch.setattr(settings, "publisher_photos", False)
    d = await _dest(db)
    await _event(db)
    await planner.plan(db)
    [p] = await _posts(db, d)
    assert p.photo is None and "image" not in p.meta
    tg = FakeTelegram()
    c = tg.client()
    await sender.send_due(db, c, sleep=_no_sleep)
    assert tg.methods == ["sendMessage"] and tg.sent[0]["link_preview_options"] == {"is_disabled": True}
    await c.aclose()
