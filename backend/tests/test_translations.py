"""Bosqich 5: til aniqlash, transliteratsiya, shablonlar, tarjima navbati (soxta provayder), API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import EventRecord, EventTranslation, Source, TranslationCache, TranslationUsage
from app.services.connectors.base import AuthMissing, ConnectorError, RateLimited
from app.services.i18n import worker
from app.services.i18n.templates import render_title
from app.services.i18n.text import detect_lang, normalize_uz, uz_to_latin
from app.services.i18n.translator import FakeTranslator, NllbTranslator


@pytest.fixture(autouse=True)
def _reset_worker_state():
    worker.state.__init__()
    yield


@pytest.mark.parametrize("text,lang", [
    ("Хакеры атаковали систему лесного хозяйства Узбекистана", "ru"),
    ("Kazakh-linked hackers use AI to steal files from government", "en"),
    ("Apaçe Airflow tizimida kritik zaiflik aniqlandi va bartaraf etildi", "uz"),
    ("Toshkentda kiberjinoyatchilikda gumonlanayotgan ikki guruh fosh etildi", "uz"),
    ("Ўзбекистонда кибержиноятчилар қўлга олинди", "uz"),
    ("Бас прокуратура интернет-алаяқтықтың жаңа схемасы пайда болғанын ескертті", "kk"),
    ("Тоҷикистон ҳуҷҷатҳои амниятӣ дуздида шуданд", "tg"),
    ("short", "ru"),  # qisqa matn — manba tili
])
def test_detect_lang(text, lang):
    assert detect_lang(text, fallback="ru") == lang


def test_translit_and_normalize():
    assert uz_to_latin("Ўзбекистонда қўлга олинди. Ер, акция, Ғалаба, ҳужжат") == \
        "O'zbekistonda qo'lga olindi. Yer, aksiya, G'alaba, hujjat"
    # latin.jaybi.uz qoidalari: сентябрь → sentabr, ъ/ь, с+ҳ, katta harfli digraflar, boshqa apostroflar → '
    assert uz_to_latin("Сентябрь, объект, съезд, Исҳоқ, ШАҲАР, Ўзбек’") == "Sentabr, obyekt, syezd, Is'hoq, SHAHAR, O'zbek'"
    assert normalize_uz("Apaçe boşqariş qölga oʻzbek gʼalaba") == "Apache boshqarish qo'lga o'zbek g'alaba"


def test_templates():
    t = render_title({"template": "ransomware_victim", "victim": "Example Bank", "group": "akira"}, ["KZ"], "ransomware")
    assert t == {"en": "Ransomware: Example Bank (Kazakhstan) — listed by akira",
                 "ru": "Вымогатели: Example Bank (Казахстан) — группа akira",
                 "uz": "Ransomware: Example Bank (Qozog'iston) — akira guruhi"}
    t = render_title({"template": "cve", "cve_id": "CVE-2026-1", "vendor": "Google", "product": "Chromium",
                      "kev": True}, [], "vulnerability")
    assert t["ru"] == "CVE-2026-1: эксплуатируемая уязвимость в Google Chromium"
    t = render_title({"template": "breach", "breach_name": "SberSpasibo", "pwn_count": 3288711}, [], "leak")
    assert t["en"] == "SberSpasibo: 3,288,711 accounts breached" and "3 288 711" in t["uz"]
    t = render_title({"template": "indicator", "ioc_type": "url", "host": "x.uz", "threat": "mozi"}, ["UZ"], "malware")
    assert t["en"] == "Malicious URL on x.uz (mozi)"
    assert render_title({"template": "outage", "country": "TJ"}, ["TJ"], "ddos-outage")["uz"] == \
        "Internet uzilishi: Tojikiston"
    assert render_title({}, [], "other") is None


# ---------------------------------------------------------------- reja
def _ev(**kw) -> EventRecord:
    d = dict(id=1, uid="u", source="S", category="other", title="Хакеры атаковали банк в Ташкенте", url="https://x/1",
             summary="Подробности атаки на банк.", lang="en", countries=[], extra={})
    d.update(kw)
    return EventRecord(**d)


def test_plan_rows_source_copy_and_pending():
    ev = _ev()
    rows = {r.lang: r for r in worker.plan_rows(ev, True, datetime.now(UTC))}
    assert ev.lang == "ru" and ev.extra["feed_lang"] == "en"  # aniqlangan til
    assert rows["ru"].status == "done" and rows["ru"].provider == "source" and rows["ru"].title == ev.title
    assert rows["en"].status == "pending" and rows["en"].title is None and rows["en"].summary is None
    assert rows["uz"].status == "pending"


def test_plan_rows_cyrillic_uzbek_translit():
    ev = _ev(title="Ўзбекистонда кибержиноятчилар қўлга олинди", summary="Тошкентда икки гуруҳ ушланди", lang="uz")
    rows = {r.lang: r for r in worker.plan_rows(ev, True, datetime.now(UTC))}
    assert rows["uz"].provider == "translit" and rows["uz"].title == "O'zbekistonda kiberjinoyatchilar qo'lga olindi"
    assert rows["ru"].status == "pending"


def test_plan_rows_template_and_skipped():
    ev = _ev(title="[akira] Org (KZ)", summary="", lang="en", countries=["KZ"],
             extra={"template": "ransomware_victim", "victim": "Org", "group": "akira"})
    rows = {r.lang: r for r in worker.plan_rows(ev, True, datetime.now(UTC))}
    assert all(r.status == "done" for r in rows.values())
    assert rows["ru"].provider == "template" and rows["ru"].title.startswith("Вымогатели: Org")
    ev2 = _ev(id=2)
    rows2 = {r.lang: r for r in worker.plan_rows(ev2, False, datetime.now(UTC))}
    assert rows2["en"].status == "skipped" and rows2["ru"].status == "done"


# ---------------------------------------------------------------- navbat
async def _store(db, **kw) -> EventRecord:
    d = dict(uid=kw.pop("uid", "e1"), source="S", category="other", title="Хакеры атаковали банк в Ташкенте",
             url="https://x.example/1", summary="Подробности атаки.", lang="ru", severity="info")
    d.update(kw)
    ev = EventRecord(**d)
    db.add(ev)
    await db.commit()
    return ev


async def test_queue_translates_with_cache_and_priority(db):
    low = await _store(db, uid="low", severity="info", title="Мошенники обманули жителей Ташкента")
    high = await _store(db, uid="high", severity="critical", title="Шифровальщик атаковал банк в Алматы")
    assert await worker.ensure_rows(db) == 2
    fake = FakeTranslator()
    stats = await worker.process_pending(db, fake, limit=2)  # faqat 2 qator — jiddiysi birinchi
    assert stats.done == 2
    assert all("Шифровальщик" in c[2][0] for c in fake.calls)  # birinchi navbatda — critical hodisa
    done_events = {t.event_id for t in (await db.scalars(
        select(EventTranslation).where(EventTranslation.status == "done", EventTranslation.provider == "fake"))).all()}
    assert done_events == {high.id}

    stats = await worker.process_pending(db, fake)
    assert stats.done == 2
    tr = await db.scalar(select(EventTranslation).where(EventTranslation.event_id == low.id,
                                                        EventTranslation.lang == "en"))
    assert tr.title == "[en] Мошенники обманули жителей Ташкента" and tr.status == "done"
    usage = await db.get(TranslationUsage, worker.month_start())
    assert usage.chars > 0 and usage.requests >= 2

    # bir xil matn — keshdan, provayderga yuborilmaydi
    await _store(db, uid="dup", title="Мошенники обманули жителей Ташкента", summary="Подробности атаки.",
                 url="https://x.example/dup")
    await worker.ensure_rows(db)
    calls = len(fake.calls)
    stats = await worker.process_pending(db, fake)
    assert len(fake.calls) == calls and stats.from_cache == 4 and stats.done == 2


async def test_uz_output_in_cyrillic_is_transliterated(db):
    await _store(db)
    await worker.ensure_rows(db)
    await worker.process_pending(db, FakeTranslator(cyrillic_uz=True))
    uz = await db.scalar(select(EventTranslation).where(EventTranslation.lang == "uz"))
    assert uz.title.startswith("O'zbekcha: ") and "Ў" not in uz.title


async def test_budget_stops_queue(db, monkeypatch):
    monkeypatch.setattr(settings, "translate_monthly_char_limit", 10)
    await _store(db)
    await worker.ensure_rows(db)
    fake = FakeTranslator()
    stats = await worker.process_pending(db, fake)
    assert stats.stopped == "budget" and fake.calls == [] and worker.state.budget_exhausted
    assert {t.status for t in (await db.scalars(select(EventTranslation).where(EventTranslation.lang != "ru"))).all()} \
        == {"pending"}


async def test_failures_retry_then_fail(db):
    await _store(db)
    await worker.ensure_rows(db)
    fake = FakeTranslator(fail=ConnectorError("HTTP 500"))
    for _ in range(3):
        await worker.process_pending(db, fake)
        await db.execute(
            EventTranslation.__table__.update().values(next_attempt_at=None)
        )
        await db.commit()
    rows = (await db.scalars(select(EventTranslation).where(EventTranslation.lang != "ru"))).all()
    assert all(r.status == "failed" and r.attempts == 3 and "HTTP 500" in r.error for r in rows)
    assert await worker.retry_failed(db) == 2
    stats = await worker.process_pending(db, FakeTranslator())
    assert stats.done == 2


async def test_auth_and_rate_limit_pause(db):
    await _store(db)
    await worker.ensure_rows(db)
    stats = await worker.process_pending(db, FakeTranslator(fail=AuthMissing("kalit rad etildi")))
    assert stats.stopped == "auth" and worker.state.key_rejected
    stats = await worker.process_pending(db, FakeTranslator())
    assert stats.stopped == "paused"
    worker.state.paused_until = None
    stats = await worker.process_pending(db, FakeTranslator(fail=RateLimited("429", retry_after=120)))
    assert stats.stopped == "rate_limited" and worker.state.paused_until > datetime.now(UTC) + timedelta(seconds=60)


async def test_no_key_leaves_pending(db):
    await _store(db)
    await worker.ensure_rows(db)
    t = NllbTranslator(None, http=None)  # TRANSLATE_API_URL bo'sh
    stats = await worker.process_pending(db, t)
    assert stats.stopped == "no_key"


async def test_source_translate_switch_off(db):
    src = await db.scalar(select(Source).where(Source.name == "UZCERT"))
    src.translate = False
    await db.commit()
    await _store(db, source_id=src.id)
    await worker.ensure_rows(db)
    rows = {r.lang: r.status for r in (await db.scalars(select(EventTranslation))).all()}
    assert rows == {"ru": "done", "en": "skipped", "uz": "skipped"}


# ---------------------------------------------------------------- API
async def test_events_api_localized_with_fallback_and_search(client, analyst_headers, db):
    ev = await _store(db, title="Хакеры атаковали банк в Ташкенте")
    await worker.ensure_rows(db)
    await worker.process_pending(db, FakeTranslator())
    # uz tarjimasini "pending" ga qaytaramiz — en ga tushishi kerak
    await db.execute(EventTranslation.__table__.update()
                     .where(EventTranslation.__table__.c.lang == "uz").values(status="pending"))
    await db.commit()

    r = (await client.get("/api/events?lang=ru", headers=analyst_headers)).json()["items"][0]
    assert r["title"] == ev.title and r["translated"] is False and r["source_lang"] == "ru"
    r = (await client.get("/api/events?lang=en", headers=analyst_headers)).json()["items"][0]
    assert r["title"] == "[en] Хакеры атаковали банк в Ташкенте" and r["translated"] and r["display_lang"] == "en"
    assert r["original_title"] == ev.title and r["translation_status"] == "done"
    r = (await client.get("/api/events?lang=uz", headers=analyst_headers)).json()["items"][0]
    assert r["display_lang"] == "en" and r["translation_status"] == "pending"
    r = (await client.get("/api/events", headers=analyst_headers)).json()["items"][0]
    assert r["title"] == ev.title and r["display_lang"] == "ru"

    found = (await client.get("/api/events?q=%5Ben%5D", headers=analyst_headers)).json()
    assert found["count"] == 1  # tarjimadagi matn bo'yicha ham qidiradi


async def test_admin_translation_endpoints(client, admin_headers, analyst_headers, db):
    for m, p in (("get", "/api/admin/translations"), ("post", "/api/admin/translations/retry-failed"),
                 ("post", "/api/admin/translations/run")):
        assert (await client.request(m.upper(), p, headers=analyst_headers)).status_code == 403
    await _store(db)
    await worker.ensure_rows(db)
    body = (await client.get("/api/admin/translations", headers=admin_headers)).json()
    assert body["configured"] is False and body["counts"]["pending"] == {"en": 1, "uz": 1}
    assert body["counts"]["done"] == {"ru": 1} and body["char_limit"] == 0 and body["provider"] == "nllb"
    r = await client.post("/api/admin/translations/run", headers=admin_headers)
    assert r.status_code == 200 and r.json()["stopped"] == "no_key"
    assert (await client.post("/api/admin/translations/retry-failed", headers=admin_headers)).json() == {"requeued": 0}
