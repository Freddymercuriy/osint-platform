"""NewsNow ulagichi. Fixture: www.newsnow.com/us/Tech/Cyber+Security/Cyber+Attacks sahifasidan qisqartirilgan nusxa
(foydalanuvchi brauzerda saqlagan; 4 kartochka, bittasi boshqa bo'limdagi takror). Tarmoqqa chiqilmaydi."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import func, select

from app.models import EventRecord, Source
from app.services.connectors import http as http_mod
from app.services.connectors.base import ConfigError, ConnectorError, FetchContext, SourceBlocked, SourceView
from app.services.connectors.http import HttpFetcher
from app.services.connectors.newsnow import NewsNowConnector, check_url, parse_page
from app.services.events import scheduler
from app.services.events.filters import apply_filters
from tests.helpers import ago, fixture_bytes, use_transport

URL = "https://www.newsnow.com/us/Tech/Cyber+Security/Cyber+Attacks"
HTML_HEADERS = {"content-type": "text/html; charset=utf-8"}


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(http_mod, "PAUSE_RANGE", (0.0, 0.0))
    http_mod.reset_gates()


def _ctx(handler, url: str = URL) -> FetchContext:
    src = SourceView(
        id=1, name="NewsNow: Cyber Attacks", kind="newsnow", config={"url": url}, lang="en", scope="global",
        region_filter=False, cyber_filter=True, api_key_env=None, etag=None, last_modified=None,
        state={}, backfill_days=7,
    )
    return FetchContext(source=src, http=HttpFetcher.create(transport=httpx.MockTransport(handler), ssrf_guard=False))


def test_parses_real_page():
    items = parse_page(fixture_bytes("newsnow_cyber_attacks.html"), URL)
    assert len(items) == 3  # 4 kartochka, bittasi takror
    first = items[0]
    assert first.title.startswith("Operation Endgame takes down Gootloader")
    assert first.url == "https://c.newsnow.com/A/1329703694?-1000:1000000000"
    assert first.source_name == "The Hacker News (NewsNow)"
    assert first.published == datetime.fromtimestamp(1794567464, UTC)
    assert first.dedup_key == "newsnow:1329703694"
    assert first.extra == {"newsnow_id": "1329703694", "publisher_country": "United States"}
    assert items[2].source_name == "Hromadske International (NewsNow)" and "publisher_country" not in items[2].extra
    assert len({i.dedup_key for i in items}) == 3 and all(i.summary == "" for i in items)


def test_skips_cards_without_article_link_or_title():
    html = (
        '<article class="article-card"><a class="article-card__headline" href="https://evil.example/A/1">'
        '<span class="article-title">Offsite</span></a></article>'
        '<article class="article-card"><a class="article-card__headline" href="https://c.newsnow.com/A/2">'
        '<span class="article-title">  </span></a></article>'
        '<article class="article-card"><a class="article-card__headline" href="https://c.newsnow.com/A/3?x">'
        '<span class="article-title">Ok</span></a><span class="article-publisher__timestamp" data-timestamp="abc">'
        "</span></article>"
    )
    items = parse_page(html, URL)
    assert [(i.title, i.url, i.published, i.source_name) for i in items] == [
        ("Ok", "https://c.newsnow.com/A/3?x", None, None)]


@pytest.mark.parametrize("url", [
    URL, "https://newsnow.com/us/World/Asia/Uzbekistan", "https://www.newsnow.co.uk/h/Technology/Security",
])
def test_valid_urls(url):
    check_url(url)


@pytest.mark.parametrize("url", [
    "http://www.newsnow.com/us/Tech",  # https emas
    "https://evil.example/us/Tech",  # boshqa xost
    "https://www.newsnow.com/", "https://www.newsnow.com",  # mavzu sahifasi emas
    "https://www.newsnow.com/us/Tech/Cyber+Security?p=2",  # sahifalash — robots.txt'da yopiq
    "https://www.newsnow.com/A/1329703694",  # maqolaga o'tish — yopiq
    "https://www.newsnow.com/cgi-bin/x", "https://www.newsnow.com/share/x", "https://www.newsnow.co.uk/reg/x",
    "", None,
])
def test_invalid_urls(url):
    with pytest.raises(ConfigError):
        NewsNowConnector().validate_config({"url": url})


async def test_fetch_reads_only_the_topic_page():
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, content=fixture_bytes("newsnow_cyber_attacks.html"), headers=HTML_HEADERS)

    ctx = _ctx(handler)
    res = await NewsNowConnector().fetch(ctx)
    assert res.http_status == 200 and len(res.items) == 3
    assert [str(r.url) for r in seen] == [URL]  # bitta so'rov; /A/ havolalarga kirilmaydi
    assert "OSINT-Platform" in seen[0].headers["user-agent"]
    await ctx.http.aclose()


def test_fallback_by_article_links_when_cards_missing():
    html = (
        '<div class="hl"><a class="hll" href="https://c.newsnow.com/A/11?-1:2">First headline</a>'
        '<span class="src">BBC</span><span class="time" data-time="1794836512">14:22</span></div>'
        '<ul><li><a href="https://c.newsnow.com/A/12">Second headline</a></li>'
        '<li><a href="https://c.newsnow.com/A/11?-3:4">First headline</a></li></ul>'  # takror
    )
    items = parse_page(html, URL)
    assert [(i.title, i.source_name, i.dedup_key) for i in items] == [
        ("First headline", "BBC (NewsNow)", "newsnow:11"), ("Second headline", None, "newsnow:12")]
    assert items[0].published == datetime.fromtimestamp(1794836512, UTC) and items[1].published is None


async def test_empty_page_is_an_error_with_fingerprint():
    page = "<html><head><title>NewsNow</title></head><body><noscript>Please enable JavaScript</noscript>" \
           "<script></script><script></script></body></html>"
    ctx = _ctx(lambda r: httpx.Response(200, text=page, headers=HTML_HEADERS))
    with pytest.raises(ConnectorError, match="yangilik topilmadi") as exc:
        await NewsNowConnector().fetch(ctx)
    msg = str(exc.value)
    assert "<title>: 'NewsNow'" in msg and "<article>: 0" in msg and "<script>: 2" in msg and "JavaScript kerak" in msg
    assert exc.value.http_status == 200
    await ctx.http.aclose()


async def test_challenge_and_403_are_blocked():
    ctx = _ctx(lambda r: httpx.Response(200, text="<title>Just a moment...</title>", headers=HTML_HEADERS))
    with pytest.raises(SourceBlocked):
        await NewsNowConnector().fetch(ctx)
    await ctx.http.aclose()
    ctx = _ctx(lambda r: httpx.Response(403, text="no"))
    with pytest.raises(SourceBlocked):
        await NewsNowConnector().fetch(ctx)
    await ctx.http.aclose()


async def test_redirect_off_newsnow_is_rejected():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.host == "www.newsnow.com":
            return httpx.Response(302, headers={"location": "https://elsewhere.example/page"})
        return httpx.Response(200, content=fixture_bytes("newsnow_cyber_attacks.html"), headers=HTML_HEADERS)

    ctx = _ctx(handler)
    with pytest.raises(ConnectorError, match="yo'naltirdi"):
        await NewsNowConnector().fetch(ctx)
    await ctx.http.aclose()


# ---------------------------------------------------------------- seed manba + scheduler (oxirigacha)
def _recent_page(suffix: str) -> bytes:
    """Fixture vaqtlarini hozirga yaqinlashtiradi (backfill oynasi) va havola qo'shimchasini almashtiradi."""
    html = fixture_bytes("newsnow_cyber_attacks.html").decode()
    stamps = iter(range(3600, 100 * 3600, 3600))
    html = re.sub(r'data-timestamp="\d+"', lambda m: f'data-timestamp="{int(ago(seconds=next(stamps)).timestamp())}"',
                  html)
    return html.replace("?-1000:1000000000", suffix).encode()


async def test_seeded_source_end_to_end_dedups_by_article_id(db, monkeypatch):
    s = await db.scalar(select(Source).where(Source.kind == "newsnow"))
    assert s is not None and s.config == {"url": URL}
    assert not s.enabled and s.status == "disabled"  # migratsiya o'chiq qo'shadi — admin yoqadi
    assert s.scope == "global" and s.cyber_filter and not s.region_filter and s.interval_seconds == 1800
    s.enabled, s.status = True, "never_run"
    await db.commit()

    page = {"body": _recent_page("?-1:111")}
    seen = use_transport(monkeypatch, lambda req: httpx.Response(200, content=page["body"], headers=HTML_HEADERS))
    r = await scheduler.run_source(s.id)
    assert r.ok and r.outcome == "ok"
    expected = apply_filters(parse_page(page["body"], URL), SimpleNamespace(
        kind="newsnow", config=s.config, scope="global", region_filter=False, cyber_filter=True))
    titles = set((await db.scalars(select(EventRecord.title))).all())
    assert titles == {i.title for i in expected} and titles
    rows = (await db.scalars(select(EventRecord))).all()
    assert all(e.scope == "global" and e.source.endswith("(NewsNow)") and e.extra["dedup_key"].startswith("newsnow:")
               for e in rows)

    # Keyingi ochilishda havola qo'shimchasi o'zgardi — o'sha maqolalar qayta yozilmaydi
    page["body"] = _recent_page("?-2:222")
    r = await scheduler.run_source(s.id)
    assert r.ok and r.new == 0
    assert await db.scalar(select(func.count(EventRecord.id))) == len(titles)
    assert {str(q.url) for q in seen} == {URL}


def test_foreign_rule_only_for_regional_sources():
    """"Chet el belgisi bor, mintaqa so'zi yo'q" qoidasi mahalliy saytlar uchun; global manbada jahon yangiligi qoladi."""
    from app.services.connectors.base import RawItem

    def items():
        return [RawItem(title="FBI warns of AI pentesting tool used in cyberattacks worldwide", url="https://x.example/1"),
                RawItem(title="Hackers breach Kazakhstan telecom, FBI says", url="https://x.example/2")]

    flags = dict(kind="rss", config={}, region_filter=False, cyber_filter=True)
    local = apply_filters(items(), SimpleNamespace(scope="regional", **flags))
    assert [i.url[-1] for i in local] == ["2"]
    glob = apply_filters(items(), SimpleNamespace(scope="global", **flags))
    assert [i.url[-1] for i in glob] == ["1", "2"] and all(i.matched_keywords for i in glob)
