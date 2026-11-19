"""Bosqich 2: jadval (jitter, backoff), baseline, sog'liq holatlari, 304, URL tekshiruvi, SSRF, advisory lock."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import func, select

from app.core.db import engine
from app.models import Category, EventRecord, Source, SourceRun
from app.services.connectors.base import CONNECTORS, Connector, FetchResult, register
from app.services.events import scheduler
from tests.helpers import ago, fixture_bytes, rss, use_transport


# ---------------------------------------------------------------- jadval matematikasi
def test_jitter_bounds():
    rng = random.Random(1)
    vals = [scheduler.jittered(600, 20, rng) for _ in range(2000)]
    assert min(vals) >= 480 and max(vals) <= 720
    assert max(vals) - min(vals) > 200  # haqiqatan tarqalgan
    assert scheduler.jittered(600, 0, rng) == 600


def test_backoff_growth_cap_and_retry_after():
    rng = random.Random(2)
    d1 = scheduler.backoff_delay(600, 1, rng=rng)
    d3 = scheduler.backoff_delay(600, 3, rng=rng)
    assert 480 <= d1 <= 720 and 1920 <= d3 <= 2880
    assert scheduler.backoff_delay(600, 30, rng=rng) <= scheduler.MAX_BACKOFF
    assert scheduler.backoff_delay(600, 1, retry_after=7200, rng=rng) >= 7200


def test_backoff_cap_depends_on_why_the_source_failed():
    """Sayt ishlamasa (timeout, DNS, 5xx) — ≤ 1 soat; blok / limit — ≤ 6 soat; hech qachon intervaldan tez emas."""
    from app.services.connectors.base import ConnectorError, RateLimited, SourceBlocked

    down, blocked, limited = ConnectorError("HTTP 503", 503), SourceBlocked("HTTP 403", 403), RateLimited("429", 429)
    assert scheduler.backoff_cap(down, 600) == scheduler.DOWN_MAX_BACKOFF == 3600
    assert scheduler.backoff_cap(blocked, 600) == scheduler.backoff_cap(limited, 600) == scheduler.MAX_BACKOFF
    assert scheduler.backoff_cap(down, 21600) == 21600 and scheduler.backoff_cap(blocked, 86400) == 86400
    rng = random.Random(4)
    many = [scheduler.backoff_delay(600, n, rng=rng, cap=3600) for n in (6, 50, 10_000)]
    assert all(2880 <= d <= 3600 for d in many)
    assert scheduler.backoff_delay(600, 6, retry_after=7200, rng=rng, cap=3600) >= 7200  # sayt so'ragani ustun


def test_initial_offset_within_interval():
    rng = random.Random(3)
    offs = [scheduler.initial_offset(900, rng) for _ in range(500)]
    assert 0 <= min(offs) and max(offs) <= 900 and max(offs) > 600


# ---------------------------------------------------------------- yordamchi
async def _source(db, **kw) -> Source:
    defaults = dict(name="Test RSS", kind="rss", config={"url": "https://feed.example/rss"}, lang="en",
                    interval_seconds=600, jitter_pct=20, backfill_days=14, enabled=True)
    defaults.update(kw)
    s = Source(**defaults)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _reload(db, s: Source) -> Source:
    await db.refresh(s)
    return s


# ---------------------------------------------------------------- baseline, 304, yangi element
async def test_baseline_then_not_modified_then_new(db, monkeypatch, client, analyst_headers):
    leak = await db.scalar(select(Category).where(Category.slug == "leak"))
    s = await _source(db, category_id=leak.id)
    feed = {"body": rss([
        ("Recent leak", "https://feed.example/a", ago(days=2)),
        ("Old leak", "https://feed.example/b", ago(days=40)),
        ("Bad link", "javascript:alert(1)", ago(days=1)),
    ]), "etag": '"v1"'}

    def handler(req: httpx.Request) -> httpx.Response:
        if req.headers.get("if-none-match") == feed["etag"]:
            return httpx.Response(304)
        return httpx.Response(200, content=feed["body"], headers={"ETag": feed["etag"], "content-type": "application/rss+xml"})

    use_transport(monkeypatch, handler)

    before = datetime.now(UTC)
    r = await scheduler.run_source(s.id)
    assert r.ok and r.outcome == "ok" and r.new == 1
    s = await _reload(db, s)
    assert s.status == "ok" and s.baseline_done and s.etag == '"v1"' and s.consecutive_failures == 0
    assert before + timedelta(seconds=480) <= s.next_run_at <= datetime.now(UTC) + timedelta(seconds=720)
    ev = (await db.scalars(select(EventRecord))).all()
    assert [e.title for e in ev] == ["Recent leak"]
    assert ev[0].is_baseline and ev[0].notified and ev[0].category == "leak" and ev[0].source_id == s.id

    # baseline hodisa o'qilmagan hisoblanmaydi
    n = await client.get("/api/notifications", headers=analyst_headers)
    assert n.json()["unread"] == 0 and n.json()["items"] == []

    r = await scheduler.run_source(s.id)
    assert r.ok and r.outcome == "not_modified" and r.new == 0

    feed["body"] = rss([("Fresh leak", "https://feed.example/c", ago(hours=1)),
                        ("Recent leak", "https://feed.example/a", ago(days=2))])
    feed["etag"] = '"v2"'
    r = await scheduler.run_source(s.id)
    assert r.new == 1
    fresh = await db.scalar(select(EventRecord).where(EventRecord.title == "Fresh leak"))
    assert not fresh.is_baseline and not fresh.notified
    n = await client.get("/api/notifications", headers=analyst_headers)
    assert n.json()["unread"] == 1

    runs = (await db.scalars(select(SourceRun.outcome).order_by(SourceRun.id))).all()
    assert runs == ["ok", "not_modified", "ok"]


# ---------------------------------------------------------------- xatolar va sog'liq
async def test_failures_backoff_down_and_recovery(db, monkeypatch):
    s = await _source(db)
    mode = {"code": 500}

    def handler(req):
        if mode["code"] == 200:
            return httpx.Response(200, content=rss([("Item", "https://feed.example/1", ago(hours=1))]))
        return httpx.Response(mode["code"])

    use_transport(monkeypatch, handler)
    statuses, delays = [], []
    for _ in range(3):
        t0 = datetime.now(UTC)
        r = await scheduler.run_source(s.id)
        s = await _reload(db, s)
        statuses.append(s.status)
        delays.append((s.next_run_at - t0).total_seconds())
    assert statuses == ["degraded", "degraded", "down"]
    assert s.consecutive_failures == 3 and s.down_since is not None
    assert delays[2] > delays[0] * 2.5  # eksponensial
    assert "HTTP 500" in s.last_error

    mode["code"] = 200
    r = await scheduler.run_source(s.id)
    s = await _reload(db, s)
    # ko'p xatodan keyin muvaffaqiyat: oxirgi 10 urinishda 3 xato → "degraded" (flapping), lekin ishlayapti
    assert r.ok and s.consecutive_failures == 0 and s.down_since is None
    assert s.status in ("ok", "degraded") and s.last_success_at is not None


async def test_long_outage_is_rechecked_hourly_and_banner_clears(db, monkeypatch, client, analyst_headers):
    """Sputnik Кыргызстан ssenariysi: DNS xatosi → timeout'lar → 503 (soatlab). Kutish 1 soatdan oshmaydi (avval
    6 soatgacha o'sardi — sayt tiklangach ham banner soatlab "ishlamayapti · qayta urinish 2 soatdan keyin" edi);
    sayt tiklangan zahoti manba ishlaydi va banner yo'qoladi. Blok (403) esa uzoqroq kutadi."""
    import socket

    from app.services.connectors import http

    s = await _source(db, name="Outage feed", interval_seconds=600)
    blocked = await _source(db, name="Blocked feed", config={"url": "https://blocked.example/rss"}, interval_seconds=600)
    mode = {"now": "dns"}

    def handler(req):
        if req.url.host == "blocked.example":
            return httpx.Response(403, text="forbidden")
        if mode["now"] == "timeout":
            raise httpx.ConnectTimeout("timed out", request=req)
        if mode["now"] == "503":
            return httpx.Response(503, text="Service Unavailable")
        return httpx.Response(200, content=rss([("Back", "https://feed.example/back", ago(minutes=5))]),
                              headers={"content-type": "application/rss+xml"})

    def resolver(host):
        if mode["now"] == "dns" and host == "feed.example":
            raise socket.gaierror(-2, "Name or service not known")
        return ["93.184.216.34"]

    use_transport(monkeypatch, handler)
    monkeypatch.setattr(http, "RESOLVER", resolver)
    waits = []
    for step in ["dns", "timeout", "timeout", "timeout", "503", "503", "503", "503"]:
        mode["now"] = step
        r = await scheduler.run_source(s.id)
        s = await _reload(db, s)
        assert not r.ok
        waits.append((s.next_run_at - s.last_check_at).total_seconds())
    assert s.status == "down" and s.consecutive_failures == 8 and s.last_http_status == 503
    assert max(waits) <= scheduler.DOWN_MAX_BACKOFF and min(waits[3:]) >= 0.8 * scheduler.DOWN_MAX_BACKOFF
    body = (await client.get("/api/events/status", headers=analyst_headers)).json()
    assert body["failing_total"] == 1 and body["failing"][0]["name"] == "Outage feed"

    for _ in range(4):
        await scheduler.run_source(blocked.id)
    blocked = await _reload(db, blocked)
    assert blocked.status == "blocked"
    assert (blocked.next_run_at - blocked.last_check_at).total_seconds() > scheduler.DOWN_MAX_BACKOFF

    mode["now"] = "ok"
    r = await scheduler.run_source(s.id)
    s = await _reload(db, s)
    assert r.ok and r.new == 1 and s.down_since is None and s.status in ("ok", "degraded")
    body = (await client.get("/api/events/status", headers=analyst_headers)).json()
    assert [f["name"] for f in body["failing"]] == ["Blocked feed"]


@pytest.mark.parametrize("response,expected_status,expected_outcome", [
    (lambda: httpx.Response(403), "blocked", "blocked"),
    (lambda: httpx.Response(429, headers={"Retry-After": "7200"}), "blocked", "rate_limited"),
    (lambda: httpx.Response(200, html="<html><title>Just a moment...</title>challenge-platform</html>"),
     "blocked", "blocked"),
    (lambda: httpx.Response(401), "auth_missing", "auth_missing"),
])
async def test_blocked_and_rate_limited(db, monkeypatch, response, expected_status, expected_outcome):
    s = await _source(db)
    use_transport(monkeypatch, lambda req: response())
    t0 = datetime.now(UTC)
    r = await scheduler.run_source(s.id)
    s = await _reload(db, s)
    assert not r.ok and r.outcome == expected_outcome and s.status == expected_status
    assert s.last_outcome == expected_outcome
    run = await db.scalar(select(SourceRun).where(SourceRun.source_id == s.id))
    assert run.wait_seconds == r.wait_seconds and r.wait_seconds > 0
    if expected_outcome == "rate_limited":
        assert s.next_run_at >= t0 + timedelta(seconds=7200)
        assert s.retry_after_seconds == r.retry_after_seconds == run.retry_after_seconds == 7200
        assert r.wait_seconds >= 7200
    else:
        assert s.retry_after_seconds is None and run.retry_after_seconds is None


async def test_rate_limit_wait_visible_then_cleared(db, monkeypatch, client, admin_headers):
    """429 + Retry-After: admin API'da sabab, sayt so'ragan kutish va rejalashtirilgan kutish; muvaffaqiyatdan keyin tozalanadi."""
    s = await _source(db, interval_seconds=60, jitter_pct=0)
    resp = {"r": httpx.Response(429, headers={"Retry-After": "300"})}
    use_transport(monkeypatch, lambda req: resp["r"])
    r = await scheduler.run_source(s.id)
    assert r.outcome == "rate_limited" and r.retry_after_seconds == 300 and 300 <= r.wait_seconds <= 301

    body = (await client.get(f"/api/admin/sources/{s.id}", headers=admin_headers)).json()
    # bitta qisqa cheklov (Retry-After 5 daq) — vaqtinchalik: "degraded", "ishlamayapti" emas
    assert body["status"] == "degraded" and body["last_outcome"] == "rate_limited"
    assert body["retry_after_seconds"] == 300 and body["last_http_status"] == 429
    runs = (await client.get(f"/api/admin/sources/{s.id}/runs", headers=admin_headers)).json()
    assert runs[0]["retry_after_seconds"] == 300 and runs[0]["wait_seconds"] == r.wait_seconds

    resp["r"] = httpx.Response(200, content=rss([("Fresh", "https://feed.example/x", ago(hours=1))]),
                               headers={"content-type": "application/rss+xml"})
    r = await scheduler.run_source(s.id)
    assert r.ok and r.retry_after_seconds is None and r.wait_seconds == 60
    body = (await client.get(f"/api/admin/sources/{s.id}", headers=admin_headers)).json()
    assert body["last_outcome"] == "ok" and body["retry_after_seconds"] is None


async def test_auth_missing_without_request(db, monkeypatch):
    @register
    class _Keyed(Connector):
        kind = "test_keyed"
        key = "required"
        default_key_env = "TEST_DUMMY_API_KEY"

        async def fetch(self, ctx):  # pragma: no cover - chaqirilmasligi kerak
            return FetchResult([])

    try:
        s = await _source(db, kind="test_keyed", config={})
        seen = use_transport(monkeypatch, lambda req: httpx.Response(200))
        r = await scheduler.run_source(s.id)
        s = await _reload(db, s)
        assert r.outcome == "auth_missing" and s.status == "auth_missing" and seen == []
        assert "TEST_DUMMY_API_KEY" in s.last_error
        assert (s.next_run_at - datetime.now(UTC)).total_seconds() >= scheduler.AUTH_RECHECK - 5
    finally:
        CONNECTORS.pop("test_keyed", None)


async def test_ssrf_private_address_refused(db, monkeypatch):
    s = await _source(db, config={"url": "https://internal.example/rss"})
    seen = use_transport(monkeypatch, lambda req: httpx.Response(200, content=b""))
    r = await scheduler.run_source(s.id)
    assert not r.ok and "Ichki" in (r.error or "") and seen == []


async def test_slow_source_is_degraded(db, monkeypatch):
    s = await _source(db)
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=rss([("x", "https://feed.example/x", ago(hours=1))])))
    monkeypatch.setattr(scheduler, "SLOW_MS", -1)
    await scheduler.run_source(s.id)
    assert (await _reload(db, s)).status == "degraded"


async def test_stale_feed_is_degraded(db, monkeypatch):
    s = await _source(db)
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=rss([("x", "https://feed.example/x", ago(days=60))])))
    await scheduler.run_source(s.id)
    s = await _reload(db, s)
    assert s.status == "degraded" and s.last_new_items == 0


# ---------------------------------------------------------------- takrorlar: also_reported_by
async def test_news_duplicate_merged_into_also_reported_by(db, monkeypatch):
    a = await _source(db, name="Source A", config={"url": "https://a.example/rss"}, baseline_done=True)
    b = await _source(db, name="Source B", config={"url": "https://b.example/rss"}, baseline_done=True)
    title_a = "Хакеры атаковали систему лесного хозяйства Узбекистана"
    title_b = "Систему лесного хозяйства Узбекистана атаковали хакеры"
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=rss(
        [(title_a if req.url.host == "a.example" else title_b, f"https://{req.url.host}/1", ago(hours=2))])))
    await scheduler.run_source(a.id)
    r = await scheduler.run_source(b.id)
    assert r.new == 0 and r.merged == 1
    ev = (await db.scalars(select(EventRecord))).all()
    assert len(ev) == 1 and ev[0].source == "Source A"
    assert [x["source"] for x in ev[0].also_reported_by] == ["Source B"]
    assert ev[0].countries == ["UZ"]


async def test_ransomware_cross_source_dedup(db, monkeypatch):
    import json

    data = json.loads(fixture_bytes("ransomware_live_recent.json"))
    data.append({"victim": "Example Bank", "group": "lockbit5", "country": "KZ", "domain": "examplebank.kz",
                 "discovered": ago(hours=3).isoformat(), "url": "https://www.ransomware.live/id/x"})
    rl = await _source(db, name="RL test", kind="ransomware_live", config={"countries": ["KZ"]},
                       baseline_done=True)
    use_transport(monkeypatch, lambda req: httpx.Response(200, json=data))
    r = await scheduler.run_source(rl.id)
    assert r.ok and r.new == 1
    ev = await db.scalar(select(EventRecord))
    assert ev.title == "[lockbit5] Example Bank (KZ)" and ev.actor == "lockbit5" and ev.countries == ["KZ"]
    assert ev.channel == "api" and ev.category == "ransomware" and ev.severity == "critical"
    assert ev.extra["dedup_key"] == "victim:examplebank.kz"

    # ikkinchi manba (boshqa nom) xuddi shu qurbonni xabar qilsa — yangi qator yo'q
    other = await _source(db, name="RL mirror", kind="ransomware_live", config={"countries": ["KZ"]},
                          baseline_done=True)
    r = await scheduler.run_source(other.id)
    assert r.new == 0 and r.merged == 1
    await db.refresh(ev)
    assert [x["source"] for x in ev.also_reported_by] == ["RL mirror"]


# ---------------------------------------------------------------- yozib olingan javoblar
async def test_recorded_uzcert_feed(db, monkeypatch):
    s = await _source(db, name="UZCERT test", config={"url": "https://uzcert.uz/rss", "default_countries": ["UZ"]},
                      backfill_days=3650)
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=fixture_bytes("uzcert_rss.xml"),
                                                          headers={"content-type": "application/rss+xml"}))
    r = await scheduler.run_source(s.id)
    assert r.ok and r.items >= 10 and r.new == r.items
    ev = (await db.scalars(select(EventRecord))).all()
    assert all(e.countries == ["UZ"] and e.url.startswith("https://") for e in ev)


async def test_recorded_google_news(db, monkeypatch):
    s = await _source(db, name="GN test", kind="google_news",
                      config={"query": "(Uzbekistan OR Kazakhstan) hackers when:7d"}, backfill_days=3650)
    seen = use_transport(monkeypatch, lambda req: httpx.Response(200, content=fixture_bytes("google_news.xml")))
    r = await scheduler.run_source(s.id)
    assert r.ok and r.items > 0
    assert seen[0].url.host == "news.google.com" and "q=" in str(seen[0].url)
    ev = (await db.scalars(select(EventRecord))).all()
    assert ev and all(e.source.endswith("(Google News)") and e.source_id == s.id for e in ev)
    assert all(" - " + e.source.replace(" (Google News)", "") not in e.title for e in ev)


# ---------------------------------------------------------------- rejalashtirish va lock
async def test_schedule_unplanned_spreads(db):
    n = await scheduler.schedule_unplanned()
    assert n > 0
    now = datetime.now(UTC)
    rows = (await db.scalars(select(Source).where(Source.enabled))).all()
    assert all(r.next_run_at is not None for r in rows)
    assert all(r.next_run_at <= now + timedelta(seconds=r.interval_seconds + 5) for r in rows)
    assert len({r.next_run_at for r in rows}) == len(rows)  # bir vaqtga to'planmagan
    due = await scheduler.due_sources(now + timedelta(days=2))
    assert len(due) == min(50, len(rows))


async def test_advisory_lock_single_holder():
    c1 = await engine.connect()
    c2 = await engine.connect()
    try:
        assert await scheduler.try_lock(c1) is True
        assert await scheduler.try_lock(c2) is False
    finally:
        await c1.close()
        await c2.close()


async def test_cloudflare_522_named_in_events_status(db, monkeypatch, client, analyst_headers):
    """Bitta manbaning 522 xatosi "yig'uvchi xatosi" emas: Events holatida manba nomi, sabab va qayta urinish vaqti."""
    s = await _source(db, name="CF site")
    await _source(db, name="Off site", enabled=False, status="down", last_error="HTTP 500")  # o'chiq — ko'rsatilmaydi
    await _source(db, name="Limited site", status="blocked", last_outcome="rate_limited", last_error="So'rovlar cheklandi",
                  retry_after_seconds=300, last_check_at=datetime.now(UTC) - timedelta(hours=1))
    use_transport(monkeypatch, lambda req: httpx.Response(522, text="origin timeout"))
    for _ in range(scheduler.DOWN_AFTER):
        r = await scheduler.run_source(s.id)
    s = await _reload(db, s)
    assert s.status == "down" and s.last_http_status == 522
    assert s.last_error == "HTTP 522 — Cloudflare: sayt serveri javob bermadi (ulanish vaqti tugadi)" == r.error

    body = (await client.get("/api/events/status", headers=analyst_headers)).json()
    assert body["failing_total"] == 2
    first, second = body["failing"]
    assert (first["name"], first["status"], first["http_status"]) == ("CF site", "down", 522)
    assert first["error"].startswith("HTTP 522 — Cloudflare") and first["next_run_at"] and first["since"]
    assert (second["name"], second["outcome"], second["retry_after_seconds"]) == ("Limited site", "rate_limited", 300)
    assert body["last_error"] == f"CF site: {s.last_error}"


async def test_occasional_429_is_not_reported_as_a_broken_source(db, monkeypatch, client, analyst_headers):
    """Google News kabi xost ba'zan 429 qaytaradi (Retry-After'siz): bitta-ikkita — "degraded", banner'da yo'q;
    ketma-ket DOWN_AFTER marta — "blocked" va banner'da."""
    s = await _source(db, name="Rate limited feed", interval_seconds=1800)
    use_transport(monkeypatch, lambda req: httpx.Response(429, text="unusual traffic"))
    for i in range(1, scheduler.DOWN_AFTER + 1):
        r = await scheduler.run_source(s.id)
        s = await _reload(db, s)
        body = (await client.get("/api/events/status", headers=analyst_headers)).json()
        if i < scheduler.DOWN_AFTER:
            assert r.outcome == "rate_limited" and s.status == "degraded" and s.down_since is None
            assert body["failing_total"] == 0
        else:
            assert s.status == "blocked" and s.down_since is not None
            assert body["failing_total"] == 1 and body["failing"][0]["outcome"] == "rate_limited"


async def test_google_news_requests_are_spaced_and_429_pauses_the_host(monkeypatch):
    """news.google.com: so'rovlar orasida xostga xos oraliq; 429 dan keyin tanaffus; navbatda kutish GATE_WAIT'da."""
    from app.services.connectors import http

    monkeypatch.setattr(http, "PAUSE_RANGE", (0.01, 0.01))
    monkeypatch.setattr(http, "HOST_PAUSE_RANGE", {"news.google.com": (0.25, 0.25)})
    monkeypatch.setattr(http, "RATE_LIMIT_COOLDOWN", (0.4, 0.4))
    monkeypatch.setattr(http, "RESOLVER", lambda host: ["93.184.216.34"])
    http.reset_gates()
    codes = iter([200, 429, 200, 200])
    fetcher = http.HttpFetcher.create(transport=httpx.MockTransport(lambda req: httpx.Response(next(codes))))
    waited = [0.0]
    token = http.GATE_WAIT.set(waited)
    try:
        await fetcher.get("https://news.google.com/rss/search?q=a", raise_errors=False)
        await fetcher.get("https://news.google.com/rss/search?q=b", raise_errors=False)  # ~0.25 s oraliq, keyin 429
        first = waited[0]
        await fetcher.get("https://news.google.com/rss/search?q=c", raise_errors=False)  # 429 tanaffusi ~0.4 s
        after_429 = waited[0] - first
        await fetcher.get("https://other.example/x", raise_errors=False)  # boshqa xost — kutmaydi
    finally:
        http.GATE_WAIT.reset(token)
        await fetcher.aclose()
    assert 0.2 <= first <= 0.35 and 0.33 <= after_429 <= 0.5
    assert waited[0] - first - after_429 < 0.05


async def test_latency_excludes_our_own_politeness_wait(db, monkeypatch):
    """Xost navbatidagi kutish manba tezligiga qo'shilmaydi (aks holda Google manbalari "sekin" deb belgilanardi)."""
    import time as _time

    from app.services.connectors import http

    s = await _source(db)
    use_transport(monkeypatch, lambda req: httpx.Response(
        200, content=rss([("Fresh", "https://feed.example/x", ago(hours=1))]),
        headers={"content-type": "application/rss+xml"}))
    host = "feed.example"
    http._gate(host).ready_at = _time.monotonic() + 0.6  # boshqa manba hozirgina so'rov yuborgan
    r = await scheduler.run_source(s.id)
    s = await _reload(db, s)
    assert r.ok and s.last_latency_ms < 500 and r.duration_ms < 500

