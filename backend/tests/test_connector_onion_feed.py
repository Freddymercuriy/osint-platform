"""onion_feed ulagichi (Tor orqali .onion forum lentalari) va Tor mijozi qoidalari.

Fixture `onion_feed_mybb.xml` — MyBB 1.8 `syndication.php` javobi tuzilishi (2026-11-20 da Tor orqali yozib olingan
javobdan); sarlavha, muallif, manzil va post matni o'ylab topilgan (haqiqiy forum matni git'da yo'q).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.event import EventRecord
from app.models.source import Source
from app.services.connectors import http as http_mod
from app.services.connectors.base import (
    ConfigError,
    ConnectorError,
    FetchContext,
    SourceBlocked,
    SourceView,
)
from app.services.connectors.http import BlockedAddress, HttpFetcher, assert_public_url, is_onion_url
from app.services.connectors import onion_feed
from app.services.connectors.onion_feed import OnionFeedConnector, title_key
from app.services.events import scheduler
from tests.helpers import ago, fixture_bytes, use_transport

HOST = "a" * 50 + "bcdefg" + ".onion"  # fixture'dagi (o'ylab topilgan) v3 manzil
FEED = f"http://{HOST}/syndication.php?fid=10&limit=50"
RSS_HEADERS = {"content-type": 'text/xml; charset="UTF-8"'}
CFG = {"site": "TestForums", "feeds": [{"url": FEED, "category": "leak", "section": "Databases"}]}
BODY_SECRETS = ("john.doe", "Passw0rd", "+998", "password_hash", "$2y$", "download link")


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(http_mod, "PAUSE_RANGE", (0.0, 0.0))
    http_mod.reset_gates()


def _ctx(handler, config=None, state=None, dry_run=False) -> FetchContext:
    src = SourceView(
        id=1, name="TestForums (Tor)", kind="onion_feed", config=config or dict(CFG), lang="en", scope="global",
        region_filter=False, cyber_filter=False, api_key_env=None, etag=None, last_modified=None,
        state=state or {}, backfill_days=3,
    )
    transport = httpx.MockTransport(handler)
    return FetchContext(source=src, http=HttpFetcher.create(transport=transport), dry_run=dry_run,
                        tor=HttpFetcher.create_tor("socks5h://tor:9050", transport=transport))


def _feed(_req=None) -> httpx.Response:
    return httpx.Response(200, content=fixture_bytes("onion_feed_mybb.xml"), headers=RSS_HEADERS)


# ---------------------------------------------------------------- tahlil
async def test_parses_metadata_only():
    ctx = _ctx(_feed)
    res = await OnionFeedConnector().fetch(ctx)
    assert res.http_status == 200
    titles = [i.title for i in res.items]
    # 4 mavzudan bittasi — qayta e'lon (sarlavha bir xil, emoji / tinish farqi), bittasi oddiy saytga havola
    assert titles == [
        "Uzbekistan - Example Telecom 2.1M Customer Records",
        "Malaysia — Example Shop Database — 1.38M Records 🇲🇾",
        "FRESH 100K PASSWORDS.TXT FREE",
    ]
    first = res.items[0]
    assert first.url == f"http://{HOST}/Thread-Uzbekistan-Example-Telecom-2-1M-Customer-Records"
    assert first.published.isoformat() == "2026-11-20T02:35:24+00:00"
    assert first.channel == "forum" and first.category == "leak" and first.actor == "ShadowTest"
    assert first.extra["forum"] == "TestForums" and first.extra["section"] == "Databases"
    for it in res.items:
        assert it.summary == "TestForums · Databases"  # post matni EMAS
        blob = repr(it)
        assert not any(s in blob for s in BODY_SECRETS), blob
        assert is_onion_url(it.url) and HOST in it.url
    assert res.state["seen"] == [i.extra["title_key"] for i in res.items]
    await ctx.http.aclose()
    await ctx.tor.aclose()


async def test_reposts_are_remembered_between_runs():
    first = await OnionFeedConnector().fetch(_ctx(_feed))
    again = await OnionFeedConnector().fetch(_ctx(_feed, state=first.state))
    assert again.items == [] and again.state["seen"] == first.state["seen"]
    assert title_key("🔥 FRESH 100K PASSWORDS.TXT — FREE 🔥") == title_key("FRESH 100K PASSWORDS.TXT FREE")
    # Xotira chegarasi
    cfg = {**CFG, "repost_memory": 2}
    small = await OnionFeedConnector().fetch(_ctx(_feed, config=cfg))
    assert len(small.state["seen"]) == 2


async def test_dry_run_ignores_and_keeps_state():
    res = await OnionFeedConnector().fetch(_ctx(_feed, state={"seen": [title_key("FRESH 100K PASSWORDS.TXT FREE")]},
                                                dry_run=True))
    assert len(res.items) == 3 and res.state is None


# ---------------------------------------------------------------- bloklanmaslik qoidalari
def _feeds(n: int, every: list[int] | None = None) -> dict:
    every = every or [0] * n
    return {"site": "TestForums", "feeds": [
        {"url": f"http://{HOST}/syndication.php?fid={i + 1}&limit=20", "category": "leak", "section": f"S{i}",
         "every_minutes": every[i]} for i in range(n)]}


def _counting():
    calls: list[str] = []

    def handler(req):
        calls.append(str(req.url))
        return _feed()

    return calls, handler


async def test_each_feed_runs_on_its_own_schedule(monkeypatch):
    t0 = datetime(2026, 11, 20, 6, 0, tzinfo=UTC)
    clock = {"now": t0}
    monkeypatch.setattr(onion_feed, "_now", lambda: clock["now"])
    cfg = _feeds(3, every=[0, 120, 720])
    calls, handler = _counting()

    first = await OnionFeedConnector().fetch(_ctx(handler, config=cfg))
    assert len(calls) == 3 and first.note == "lentalar: 3/3"  # birinchi marta — hammasi
    state = first.state
    for minutes, expected in [(55, ["fid=1"]), (100, ["fid=1", "fid=2"]), (600, ["fid=1", "fid=2", "fid=3"])]:
        calls.clear()
        clock["now"] = t0 + timedelta(minutes=minutes)
        res = await OnionFeedConnector().fetch(_ctx(handler, config=cfg, state=state))
        assert [re.search(r"fid=\d+", c).group(0) for c in calls] == expected, minutes
        state = res.state
    # 55-daqiqada: 2 va 3-lenta navbatda emas — izohda ko'rinadi
    clock["now"] = t0 + timedelta(minutes=655)
    calls.clear()
    res = await OnionFeedConnector().fetch(_ctx(handler, config=cfg, state=state))
    assert len(calls) == 1 and res.note == "lentalar: 1/3 (qolganlari hali navbatda emas)"


async def test_daily_request_cap_is_hard_and_resets_next_day(monkeypatch):
    t0 = datetime(2026, 11, 20, 23, 0, tzinfo=UTC)
    clock = {"now": t0}
    monkeypatch.setattr(onion_feed, "_now", lambda: clock["now"])
    cfg = {**_feeds(3), "max_requests_per_day": 4}
    calls, handler = _counting()

    first = await OnionFeedConnector().fetch(_ctx(handler, config=cfg))
    assert len(calls) == 3 and first.state["budget"] == {"day": "2026-11-20", "count": 3}
    calls.clear()
    second = await OnionFeedConnector().fetch(_ctx(handler, config=cfg, state=first.state))
    assert len(calls) == 1 and "kunlik so'rov limiti (4)" in second.note  # xato emas, qolgani ertaga
    calls.clear()
    third = await OnionFeedConnector().fetch(_ctx(handler, config=cfg, state=second.state))
    assert calls == [] and third.items == [] and third.state["budget"]["count"] == 4
    clock["now"] = t0 + timedelta(hours=2)  # yangi UTC kuni
    calls.clear()
    fourth = await OnionFeedConnector().fetch(_ctx(handler, config=cfg, state=third.state))
    assert len(calls) == 3 and fourth.state["budget"] == {"day": "2026-11-21", "count": 3}


async def test_dry_run_asks_only_the_first_feed():
    calls, handler = _counting()
    res = await OnionFeedConnector().fetch(_ctx(handler, config=_feeds(4), dry_run=True))
    assert len(calls) == 1 and "fid=1" in calls[0] and res.state is None and res.note == "lentalar: 1/4 (qolganlari hali navbatda emas)"


@pytest.mark.parametrize("code, headers", [(429, {"retry-after": "600"}), (403, {})])
async def test_block_signal_stops_all_feeds_at_once(code, headers):
    calls: list[str] = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(code, headers=headers)

    with pytest.raises(SourceBlocked):
        await OnionFeedConnector().fetch(_ctx(handler, config=_feeds(4)))
    assert len(calls) == 1  # birinchi blok belgisidan keyin qolgan 3 lenta so'ralmadi


def test_honest_client_no_disguise():
    tor = HttpFetcher.create_tor("socks5h://tor:9050")
    assert "OSINT-Platform" in tor.client.headers["user-agent"]  # brauzerga o'xshatilmaydi
    assert http_mod.ONION_PAUSE_RANGE[0] >= 10


async def test_html_instead_of_feed_is_blocked_not_bypassed():
    login = b"<html><body><form action='member.php'>Please login</form></body></html>"
    ctx = _ctx(lambda r: httpx.Response(200, content=login, headers={"content-type": "text/html"}))
    with pytest.raises(SourceBlocked, match="HTML"):
        await OnionFeedConnector().fetch(ctx)
    captcha = b"<html><div class='g-recaptcha'></div></html>"
    ctx = _ctx(lambda r: httpx.Response(200, content=captcha, headers={"content-type": "text/html"}))
    with pytest.raises(SourceBlocked):
        await OnionFeedConnector().fetch(ctx)


async def test_one_feed_failing_keeps_the_others():
    cfg = {"site": "TestForums", "feeds": [
        {"url": FEED, "category": "leak", "section": "Databases"},
        {"url": f"http://{HOST}/syndication.php?fid=52", "category": "credentials", "section": "Stealer Logs"},
    ]}

    def handler(req):
        if "fid=52" in str(req.url):
            raise httpx.ReadTimeout("slow circuit", request=req)
        return _feed()

    res = await OnionFeedConnector().fetch(_ctx(handler, config=cfg))
    assert len(res.items) == 3

    def down(req):
        raise httpx.ConnectError("tor down", request=req)

    with pytest.raises(ConnectorError):
        await OnionFeedConnector().fetch(_ctx(down, config=cfg))


@pytest.mark.parametrize("config, match", [
    ({"feeds": []}, "1..10"),
    ({"feeds": [{"url": "https://example.com/rss"}]}, "onion"),
    ({"feeds": [{"url": "http://abcdefghijklmnop.onion/rss"}]}, "onion"),  # v2 manzil
    ({"feeds": [{"url": "ftp://" + HOST + "/x"}]}, "onion"),
    ({"feeds": [{"url": FEED}, {"url": "http://" + "b" * 56 + ".onion/rss"}]}, "bitta"),
    ({"feeds": [{"url": FEED, "category": "Leak!"}]}, "category"),
    ({"feeds": [{"url": FEED}], "repost_memory": -1}, "repost_memory"),
    ({"feeds": [{"url": FEED, "every_minutes": -5}]}, "every_minutes"),
    ({"feeds": [{"url": FEED}], "max_requests_per_day": 0}, "max_requests_per_day"),
    ({"feeds": [{"url": FEED}], "max_requests_per_day": 10_000}, "max_requests_per_day"),
])
def test_config_validation(config, match):
    with pytest.raises(ConfigError, match=match):
        OnionFeedConnector().validate_config(config)


def test_config_ok_and_no_dns_check_targets():
    OnionFeedConnector().validate_config({**CFG, "feeds": CFG["feeds"] + [{"url": FEED + "&x=1", "category": None}]})
    assert OnionFeedConnector().target_urls(None) == []


# ---------------------------------------------------------------- Tor mijozi va oddiy mijoz chegarasi
async def test_tor_client_refuses_clearnet_and_redirects_off_onion():
    calls: list[str] = []

    def handler(req):
        calls.append(str(req.url))
        if req.url.path == "/go":
            return httpx.Response(302, headers={"location": "https://evil.example/steal"})
        return httpx.Response(200, text="ok")

    tor = HttpFetcher.create_tor("socks5h://tor:9050", transport=httpx.MockTransport(handler))
    with pytest.raises(BlockedAddress):
        await tor.get("https://example.com/")
    with pytest.raises(BlockedAddress):
        await tor.get("http://127.0.0.1:5432/")
    with pytest.raises(BlockedAddress):
        await tor.get(f"http://{HOST}/go")  # .onion → oddiy saytga redirect
    assert calls == [f"http://{HOST}/go"]  # clearnet'ga birorta ham so'rov ketmadi
    await tor.aclose()


async def test_clearnet_client_never_resolves_onion(monkeypatch):
    def resolver(host):
        raise AssertionError(f"DNS'ga so'raldi: {host}")

    monkeypatch.setattr(http_mod, "RESOLVER", resolver)
    with pytest.raises(BlockedAddress, match="Tor"):
        await assert_public_url(f"http://{HOST}/")


def test_tor_client_uses_proxy_and_ignores_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://evil-proxy.example:3128")
    tor = HttpFetcher.create_tor("socks5h://tor:9050")
    assert tor.client._trust_env is False
    mounts = list(tor.client._mounts.values())
    assert mounts and all(type(m).__name__ == "AsyncHTTPTransport" for m in mounts)
    pool = mounts[0]._pool
    assert type(pool).__name__ == "AsyncSOCKSProxy" and pool._proxy_url.host == b"tor"


# ---------------------------------------------------------------- seed manba + scheduler
def _recent(content: bytes, host: str) -> bytes:
    text = content.decode().replace(HOST, host)
    hours = iter(range(1, 50))
    text = re.sub(r"<pubDate>[^<]+</pubDate>",
                  lambda m: f"<pubDate>{format_datetime(ago(hours=next(hours)))}</pubDate>", text)
    return text.encode()


async def test_seeded_darkforums_source(db, monkeypatch):
    s = await db.scalar(select(Source).where(Source.kind == "onion_feed"))
    assert s is not None and s.name == "DarkForums (Tor)" and s.enabled
    assert s.scope == "global" and s.reliability == "underground" and not s.cyber_filter and not s.region_filter
    assert s.interval_seconds == 3600 and s.config["max_requests_per_day"] == 80  # 0025: bloklanmaslik qoidalari
    assert [f["every_minutes"] for f in s.config["feeds"]] == [0, 120, 120, 180, 720]
    assert all(int(re.search(r"limit=(\d+)", f["url"]).group(1)) <= 30 for f in s.config["feeds"])
    OnionFeedConnector().validate_config(s.config)
    cats = [f["category"] for f in s.config["feeds"]]
    assert cats == ["leak", "credentials", "darkweb-sale", "fraud", None]
    real_host = re.match(r"http://([^/]+)/", s.config["feeds"][0]["url"]).group(1)
    assert is_onion_url(f"http://{real_host}/")
    # Doxes (42) va Combolists (53) ataylab yo'q; Premium (47, 51) mehmonga bo'sh — olib tashlangan (0025)
    fids = {int(x) for f in s.config["feeds"] for x in re.search(r"fid=([\d,]+)", f["url"]).group(1).split(",")}
    assert not fids & {42, 88, 53, 85, 47, 51}

    # TOR_PROXY_URL yo'q — auth_missing, birorta ham so'rov ketmaydi
    monkeypatch.setattr(settings, "tor_proxy_url", "")
    seen = use_transport(monkeypatch, lambda req: httpx.Response(500))
    r = await scheduler.run_source(s.id)
    assert not r.ok and r.status == "auth_missing" and seen == []

    # Proksi bor — 5 lenta Tor mijozi orqali
    monkeypatch.setattr(settings, "tor_proxy_url", "socks5h://tor:9050")
    body = _recent(fixture_bytes("onion_feed_mybb.xml"), real_host)
    seen = use_transport(monkeypatch, lambda req: httpx.Response(200, content=body, headers=RSS_HEADERS))
    r = await scheduler.run_source(s.id)
    assert r.ok, r.error
    assert len(seen) == 5 and all(real_host in str(q.url) for q in seen)
    rows = (await db.scalars(select(EventRecord).order_by(EventRecord.id))).all()
    # 5 lenta bir xil javob qaytardi — bir xil sarlavha birinchi lentadan (leak) bir marta olinadi
    assert len(rows) == 3
    assert all(e.channel == "forum" and e.source == "DarkForums (Tor)" and e.category == "leak" for e in rows)
    assert all(not any(x in (e.summary or "") for x in BODY_SECRETS) for e in rows)
    by_title = {e.title: e for e in rows}
    uz = by_title["Uzbekistan - Example Telecom 2.1M Customer Records"]
    assert uz.scope == "regional" and "UZ" in (uz.countries or [])  # Markaziy Osiyo — asosiy lentaga
    assert by_title["FRESH 100K PASSWORDS.TXT FREE"].scope == "global"

    # Qayta yig'ish darhol — faqat har yig'ishdagi lenta (sizishlar) so'raladi, o'sha mavzular yangi hodisa bo'lmaydi
    seen.clear()
    r = await scheduler.run_source(s.id)
    assert r.ok and r.new == 0
    assert len(seen) == 1 and "fid=10,13,12" in str(seen[0].url)
    assert await db.scalar(select(func.count(EventRecord.id))) == 3
    await db.refresh(s)
    assert s.state["budget"]["count"] == 6 and len(s.state["fetched_at"]) == 5
