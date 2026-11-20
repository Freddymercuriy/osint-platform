"""`telegram` ulagichi (ochiq kanal, t.me/s) va Daryo.uz manbalarining ko'chirilishi (0026).

Fixture `telegram_public_channel.html` — t.me/s sahifasi tuzilishi (2026-11-20 da yozib olingan sahifadan);
kanal nomi, matnlar va havolalar o'ylab topilgan.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import select

from app.models.event import EventRecord
from app.models.source import Source
from app.services.connectors.telegram_public import _NOISE_LINE, parse_channel
from app.services.events import scheduler
from tests.helpers import ago, fixture_bytes, rss, use_transport

HTML_HEADERS = {"content-type": "text/html; charset=utf-8"}


def _page() -> str:
    return fixture_bytes("telegram_public_channel.html").decode()


def test_title_is_first_line_and_service_lines_are_dropped():
    items = parse_channel(_page(), "Example News (UZ)")
    assert [i.url for i in items] == [f"https://t.me/ExampleNews/{n}" for n in (101, 103, 104)]  # 102 — matnsiz
    a, b, c = items
    assert a.title == "Xakerlar O‘zbekistondagi bankning 1,2 mln mijozi ma’lumotlarini sotuvga qo‘ydi"
    assert a.summary == "Ma’lumotlar bazasi darknet forumida e’lon qilingan. Bank kiberhujum faktini tekshirmoqda."
    assert a.published.isoformat() == "2026-11-20T07:55:10+00:00"
    assert a.source_name == "TG: Example News (UZ)" and a.channel == "telegram_channel"
    # Uzun birinchi qator kesiladi; "Подробнее: <havola>" tashlanadi
    assert b.title.endswith("...") and len(b.title) == 143 and b.title.startswith("Voqealar zanjiri: Toshkentda")
    assert b.summary == "Bekat ertalabdan ishlay boshladi."
    # Bir qatorli post — sarlavha ham, matn ham o'sha qator
    assert c.title == c.summary == "Kiberhujum: davlat portali 3 soat ishlamadi"
    assert all("Batafsil" not in i.summary and "@examplenews" not in i.summary and "http" not in i.summary
               for i in items)


def test_noise_line_keeps_real_headlines():
    for line in ("Batafsil — https://daryo.uz/p/1/", "👉 Obuna bo‘ling — @daryo", "Подробнее:", "@daryo",
                 "https://x.uz/a", "👉"):
        assert _NOISE_LINE.match(line), line
    for line in ("Kiberhujum: bank tizimi to'xtadi", "Hackerlar 1,5 mln yozuvni sotuvga qo'ydi — UZCERT",
                 "UZCERT ogohlantirdi"):
        assert not _NOISE_LINE.match(line), line


def _recent(html: str) -> bytes:
    """Fixture sanalari — hozirgi vaqtga yaqin (baseline backfill oynasiga tushishi uchun)."""
    minutes = iter(range(10, 200, 10))
    return re.sub(r'datetime="[^"]+"', lambda m: f'datetime="{ago(minutes=next(minutes)).isoformat()}"',
                  html).encode()


async def test_daryo_uz_reads_official_telegram_channel(db, monkeypatch):
    s = await db.scalar(select(Source).where(Source.name == "Daryo.uz (UZ)"))
    assert s.kind == "telegram" and s.config == {"channel": "Daryo"} and s.lang == "uz"
    assert s.scope == "regional" and s.cyber_filter and not s.baseline_done and s.interval_seconds == 600

    body = _recent(_page())
    seen = use_transport(monkeypatch, lambda req: httpx.Response(200, content=body, headers=HTML_HEADERS))
    r = await scheduler.run_source(s.id)
    assert r.ok, r.error
    assert [str(q.url) for q in seen] == ["https://t.me/s/Daryo"]  # daryo.uz'ning o'ziga so'rov yo'q
    rows = (await db.scalars(select(EventRecord).order_by(EventRecord.id))).all()
    assert rows and all(e.url.startswith("https://t.me/ExampleNews/") and e.is_baseline for e in rows)
    assert "metro" not in " ".join(e.title for e in rows).lower()  # kiber mavzusi emas — filtrdan o'tmaydi
    await db.refresh(s)
    assert s.status == "ok" and s.baseline_done


async def test_daryo_ru_reads_google_news(db, monkeypatch):
    s = await db.scalar(select(Source).where(Source.name == "Daryo.uz (RU)"))
    assert s.kind == "google_news" and s.config == {"query": "site:daryo.uz when:7d"} and s.lang == "ru"
    assert s.interval_seconds == 1800 and not s.baseline_done

    feed = rss([("Хакеры взломали сайт министерства Узбекистана - Daryo",
                 "https://news.google.com/rss/articles/CBMiAAA", ago(hours=2))])
    seen = use_transport(monkeypatch, lambda req: httpx.Response(200, content=feed,
                                                                 headers={"content-type": "application/xml"}))
    r = await scheduler.run_source(s.id)
    assert r.ok, r.error
    assert len(seen) == 1 and seen[0].url.host == "news.google.com"
    q = parse_qs(urlparse(str(seen[0].url)).query)
    assert q["q"] == ["site:daryo.uz when:7d"] and q["hl"] == ["ru"]
