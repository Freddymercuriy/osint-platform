"""html_list ulagichi. Fixture: cert.gov.kg/ru/news/ (KG-CERT) sahifasidan qisqartirilgan haqiqiy nusxa."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.services.connectors import http as http_mod
from app.services.connectors.base import ConfigError, FetchContext, SourceBlocked, SourceView
from app.services.connectors.html_list import HtmlListConnector, parse_date
from app.services.connectors.http import HttpFetcher
from tests.helpers import fixture_bytes

URL = "https://cert.gov.kg/ru/news/"
CFG = {
    "url": URL,
    "item": "a.news-pages-card",
    "title": ".news-title",
    "link": ".",
    "date": ".news-data-text",
    "date_format": "auto",
    "summary": ".main-text",
}


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(http_mod, "PAUSE_RANGE", (0.0, 0.0))
    http_mod.reset_gates()


def _ctx(handler, config=None) -> FetchContext:
    src = SourceView(
        id=1, name="KG-CERT", kind="html_list", config=config or dict(CFG), lang="ru", scope="regional",
        region_filter=False, cyber_filter=False, api_key_env=None, etag=None, last_modified=None,
        state={}, backfill_days=30,
    )
    return FetchContext(source=src, http=HttpFetcher.create(transport=httpx.MockTransport(handler), ssrf_guard=False))


async def test_parses_real_page():
    page = fixture_bytes("html_list_kgcert.html")
    ctx = _ctx(lambda r: httpx.Response(200, content=page, headers={"content-type": "text/html; charset=utf-8"}))
    res = await HtmlListConnector().fetch(ctx)
    assert res.http_status == 200
    assert len(res.items) == 9
    first = res.items[0]
    assert first.title.startswith("МВД России опровергли")
    assert first.url == "https://cert.gov.kg/ru/news/1/"
    assert first.published == datetime(2025, 6, 25, tzinfo=UTC)
    assert first.summary.startswith("Информация о масштабной утечке")
    assert res.items[2].published == datetime(2025, 9, 11, tzinfo=UTC)
    assert all(i.url.startswith("https://cert.gov.kg/") and i.published for i in res.items)
    await ctx.http.aclose()


async def test_offsite_and_non_http_links_dropped():
    html = (
        '<ul><li class="n"><a href="https://evil.example/x">Off</a><i>2025-01-02</i></li>'
        '<li class="n"><a href="javascript:alert(1)">JS</a></li>'
        '<li class="n"><a href="mailto:a@b.c">Mail</a></li>'
        '<li class="n"><a href="/ok/1#frag">Ok</a><i>2025-01-02T10:30:00</i></li></ul>'
    )
    cfg = {"url": "https://cert.example/list", "item": "li.n", "title": "a", "link": "a", "date": "i"}
    ctx = _ctx(lambda r: httpx.Response(200, text=html, headers={"content-type": "text/html"}), cfg)
    res = await HtmlListConnector().fetch(ctx)
    assert [i.url for i in res.items] == ["https://cert.example/ok/1"]
    assert res.items[0].published == datetime(2025, 1, 2, 10, 30, tzinfo=UTC)
    await ctx.http.aclose()


async def test_http_errors_become_connector_errors():
    ctx = _ctx(lambda r: httpx.Response(403, text="no"))
    with pytest.raises(SourceBlocked):
        await HtmlListConnector().fetch(ctx)
    await ctx.http.aclose()


def test_validate_config():
    c = HtmlListConnector()
    c.validate_config(CFG)
    for bad in (
        {**CFG, "url": "ftp://x"},
        {k: v for k, v in CFG.items() if k != "item"},
        {k: v for k, v in CFG.items() if k != "title"},
        {k: v for k, v in CFG.items() if k != "link"},
        {**CFG, "item": "div[["},
    ):
        with pytest.raises(ConfigError):
            c.validate_config(bad)


def test_target_urls():
    ctx = _ctx(lambda r: httpx.Response(200))
    assert HtmlListConnector().target_urls(ctx.source) == [URL]


def test_parse_date_variants():
    assert parse_date("11 Сентябрь 2025") == datetime(2025, 9, 11, tzinfo=UTC)
    assert parse_date("3 марта 2026") == datetime(2026, 3, 3, tzinfo=UTC)
    assert parse_date("12 November 2026") == datetime(2026, 11, 12, tzinfo=UTC)
    assert parse_date("08.10.2026") == datetime(2026, 10, 8, tzinfo=UTC)
    assert parse_date("2026-10-08T09:05:00") == datetime(2026, 10, 8, 9, 5, tzinfo=UTC)
    assert parse_date("31/02/2026") is None
    assert parse_date("вчера") is None
    assert parse_date("08 Oct 2026", "%d %b %Y") == datetime(2026, 10, 8, tzinfo=UTC)
