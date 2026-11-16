"""O'z NLLB tarjima servisi klienti (tarmoqsiz, httpx.MockTransport) va worker bilan bog'lanishi."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import EventRecord, EventTranslation
from app.services.connectors.base import ConnectorError, RateLimited
from app.services.connectors.http import HttpFetcher
from app.services.i18n import translator as tr_mod
from app.services.i18n import worker
from app.services.i18n.translator import (
    FakeTranslator,
    NllbTranslator,
    TranslationRequestError,
    UnsupportedLanguage,
    split_text,
    translate_or_original,
)

BASE = "https://translate.test"


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(tr_mod, "RETRY_BASE", 0.0)
    worker.state.__init__()


def make(handler, max_input: int = 512) -> tuple[NllbTranslator, list[httpx.Request]]:
    """Servis: /model + /translate/batch ("<target>:<matn>"); `handler` qolgan holatlarni (yoki hammasini) boshqaradi."""
    seen: list[httpx.Request] = []

    def _h(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        if req.url.path == "/model":
            return httpx.Response(200, json={"max_input_length": max_input, "batch_size": 16})
        return handler(req)

    http = HttpFetcher.create(transport=httpx.MockTransport(_h), ssrf_guard=False, pause_range=(0.0, 0.0))
    return NllbTranslator(BASE, http, timeout=5), seen


def ok(req: httpx.Request) -> httpx.Response:
    body = json.loads(req.content)
    tag = body["target_lang"][:3].upper()
    return httpx.Response(200, json={
        "source_lang": body["source_lang"], "target_lang": body["target_lang"], "model": "nllb-test",
        "results": [{"text": t, "translation": f"{tag}:{t}"} for t in body["texts"]],
    })


def batches(seen: list[httpx.Request]) -> list[dict]:
    return [json.loads(r.content) for r in seen if r.url.path == "/translate/batch"]


# ---------------------------------------------------------------- muvaffaqiyat, kodlar, paketlar
async def test_success_maps_codes_and_caches_model_info():
    t, seen = make(ok)
    assert t.configured and t.name == "nllb"
    assert await t.translate(["Salom dunyo"], "uz", "ru") == ["RUS:Salom dunyo"]
    assert await t.translate(["Hello"], "en", "kk") == ["KAZ:Hello"]
    sent = batches(seen)
    assert sent[0] == {"texts": ["Salom dunyo"], "source_lang": "uzn_Latn", "target_lang": "rus_Cyrl"}
    assert (sent[1]["source_lang"], sent[1]["target_lang"]) == ("eng_Latn", "kaz_Cyrl")
    assert sum(r.url.path == "/model" for r in seen) == 1  # max_input_length bir marta so'raladi
    assert all(r.method == "POST" and not r.headers.get("authorization") for r in seen if r.url.path != "/model")


@pytest.mark.parametrize("code,nllb", [("uz", "uzn_Latn"), ("ru", "rus_Cyrl"), ("en", "eng_Latn"), ("kk", "kaz_Cyrl"),
                                       ("ky", "kir_Cyrl"), ("tg", "tgk_Cyrl"), ("tk", "tuk_Latn")])
def test_language_map(code, nllb):
    assert tr_mod.to_nllb(code) == nllb


async def test_batch_is_chunked_by_64_and_order_kept():
    t, seen = make(ok)
    texts = [f"matn {i}" for i in range(130)]
    out = await t.translate(texts, "ru", "en")
    assert out == [f"ENG:matn {i}" for i in range(130)]
    assert [len(b["texts"]) for b in batches(seen)] == [64, 64, 2]


async def test_long_text_is_split_by_sentences_and_rejoined():
    t, seen = make(ok, max_input=100)  # bo'lak ≤ 92 belgi
    long = " ".join(f"Bu {i}-gap bo'lib, unda kiberxavfsizlik haqida batafsil ma'lumot berilgan." for i in range(5))
    [out] = await t.translate([long], "uz", "en")
    pieces = batches(seen)[0]["texts"]
    assert len(pieces) == 5 and all(len(p) <= 92 for p in pieces)
    assert out == " ".join(f"ENG:{p}" for p in pieces)


def test_split_text_hard_splits_long_sentence():
    text = "so'z " * 100  # 500 belgi, nuqtasiz
    parts = split_text(text, 92)
    assert all(len(p) <= 92 for p in parts) and " ".join(parts) == text.strip()
    assert split_text("x" * 250, 100) == ["x" * 100, "x" * 100, "x" * 50]
    assert split_text("Qisqa matn.", 100) == ["Qisqa matn."]


async def test_uzbek_cyrillic_is_transliterated_before_sending():
    t, seen = make(ok)
    await t.translate(["Ўзбекистонда кибержиноятчилар қўлга олинди"], "uz", "en")
    sent = batches(seen)[0]
    assert sent["source_lang"] == "uzn_Latn"  # servisda uzn_Cyrl yo'q
    assert sent["texts"] == ["O'zbekistonda kiberjinoyatchilar qo'lga olindi"]


async def test_empty_texts_are_not_sent():
    t, seen = make(ok)
    assert await t.translate(["", "  ", "abc"], "ru", "en") == ["", "", "ENG:abc"]
    assert batches(seen)[0]["texts"] == ["abc"]
    assert await t.translate([], "ru", "en") == []


async def test_unsupported_language_sends_nothing():
    t, seen = make(ok)
    with pytest.raises(UnsupportedLanguage, match="'de'"):
        await t.translate(["Hallo"], "de", "en")
    assert seen == []


async def test_not_configured():
    t = NllbTranslator("", http=None)
    assert not t.configured
    with pytest.raises(ConnectorError, match="TRANSLATE_API_URL"):
        await t.translate(["x"], "ru", "en")


# ---------------------------------------------------------------- xatolar va qayta urinish
async def test_422_is_a_clear_error_without_retry():
    def bad(req):
        return httpx.Response(422, json={"detail": [
            {"loc": ["body", "source_lang"], "msg": "Noma'lum til kodi", "type": "value_error"}]})

    t, seen = make(bad)
    with pytest.raises(TranslationRequestError) as exc:
        await t.translate(["x"], "ru", "en")
    assert "422" in str(exc.value) and "source_lang: Noma'lum til kodi" in str(exc.value)
    assert exc.value.http_status == 422 and len(batches(seen)) == 1


async def test_5xx_is_retried_then_succeeds():
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else ok(req)

    t, seen = make(flaky)
    assert await t.translate(["x"], "ru", "en") == ["ENG:x"]
    assert len(batches(seen)) == 3


async def test_5xx_gives_up_after_retries():
    t, seen = make(lambda req: httpx.Response(500))
    with pytest.raises(ConnectorError, match="HTTP 500"):
        await t.translate(["x"], "ru", "en")
    assert len(batches(seen)) == 3  # 1 + 2 qayta urinish


async def test_connection_error_is_retried():
    calls = {"n": 0}

    def flaky(req):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused", request=req)
        return ok(req)

    t, _ = make(flaky)
    assert await t.translate(["x"], "ru", "en") == ["ENG:x"]
    assert calls["n"] == 2


async def test_timeout_is_not_retried():
    def slow(req):
        raise httpx.ReadTimeout("timed out", request=req)

    t, seen = make(slow)
    with pytest.raises(ConnectorError, match="5 s ichida javob bermadi"):
        await t.translate(["x"], "ru", "en")
    assert len(batches(seen)) == 1


async def test_429_is_rate_limited():
    t, _ = make(lambda req: httpx.Response(429, headers={"Retry-After": "90"}))
    with pytest.raises(RateLimited) as exc:
        await t.translate(["x"], "ru", "en")
    assert exc.value.retry_after == 90


async def test_model_endpoint_down_uses_default_limit():
    def h(req):
        return httpx.Response(500) if req.url.path == "/model" else ok(req)

    http = HttpFetcher.create(transport=httpx.MockTransport(h), ssrf_guard=False, pause_range=(0.0, 0.0))
    t = NllbTranslator(BASE, http)
    assert await t.translate(["x"], "ru", "en") == ["ENG:x"]
    assert await t.chunk_chars() == tr_mod.DEFAULT_MAX_INPUT - tr_mod.TOKEN_RESERVE


# ---------------------------------------------------------------- fallback (navbatdan tashqari)
async def test_translate_or_original_returns_original_and_warns(caplog):
    t, _ = make(lambda req: httpx.Response(500))
    with caplog.at_level(logging.WARNING, logger="osint.i18n"):
        out = await translate_or_original(t, ["Привет", "мир"], "ru", "en")
    assert out == ["Привет", "мир"]
    assert any("asl matn qaytarildi" in r.message for r in caplog.records)
    t2, _ = make(ok)
    assert await translate_or_original(t2, ["Привет"], "ru", "en") == ["ENG:Привет"]


# ---------------------------------------------------------------- worker bilan
async def _event(db) -> EventRecord:
    ev = EventRecord(uid="w1", source="S", category="other", title="Хакеры атаковали банк", url="https://x.example/w1",
                     summary="Подробности.", lang="ru", severity="info")
    db.add(ev)
    await db.commit()
    await worker.ensure_rows(db)
    return ev


async def _rows(db) -> list[EventTranslation]:
    return (await db.scalars(select(EventTranslation).where(EventTranslation.lang != "ru"))).all()


async def test_worker_keeps_rows_pending_on_transient_error(db, caplog):
    await _event(db)
    with caplog.at_level(logging.WARNING, logger="osint.i18n"):
        await worker.process_pending(db, FakeTranslator(fail=ConnectorError("Tarjima servisi: HTTP 503")))
    rows = await _rows(db)
    assert all(r.status == "pending" and r.attempts == 1 and r.title is None for r in rows)  # asl matn yozilmadi
    assert any("qayta urinadi" in r.message for r in caplog.records)


async def test_worker_fails_permanently_on_422(db):
    await _event(db)
    await worker.process_pending(db, FakeTranslator(fail=TranslationRequestError("422: bad", http_status=422)))
    rows = await _rows(db)
    assert all(r.status == "failed" and r.attempts == worker.MAX_ATTEMPTS and "422" in r.error for r in rows)


async def test_worker_zero_limit_means_unlimited(db, monkeypatch):
    monkeypatch.setattr(settings, "translate_monthly_char_limit", 0)
    await _event(db)
    stats = await worker.process_pending(db, FakeTranslator())
    assert stats.stopped is None and stats.done == 2 and not worker.state.budget_exhausted


async def test_scheduler_builds_nllb_translator(monkeypatch):
    from app.services.events import scheduler

    monkeypatch.setattr(settings, "translate_api_url", "https://translate.example/")
    monkeypatch.setattr(settings, "translate_timeout_seconds", 12.0)
    monkeypatch.setattr(scheduler.state, "_tr_http", None)
    t = scheduler.translator()
    assert isinstance(t, NllbTranslator) and t.base_url == "https://translate.example" and t.timeout == 12.0
    assert t.http.ssrf_guard is False and t.http.pause_range == (0.0, 0.0)
    assert t.http is not scheduler.state._http  # ulagichlar mijozidan alohida
    await t.http.aclose()
