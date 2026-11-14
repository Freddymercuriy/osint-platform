"""URLhaus, ThreatFox, OpenPhish ulagichlari — tarmoqsiz (httpx.MockTransport)."""

from __future__ import annotations

import json

import httpx
import pytest

from app.core.config import settings
from app.services.connectors import abusech, openphish  # noqa: F401  (ro'yxatga olinadi)
from app.services.connectors import http as http_mod
from app.services.connectors.base import AuthMissing, FetchContext, SourceBlocked, SourceView, get_connector
from app.services.connectors.http import HttpFetcher
from tests.helpers import fixture_bytes


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(http_mod, "PAUSE_RANGE", (0.0, 0.0))
    http_mod.reset_gates()


def _ctx(kind: str, handler, *, api_key: str | None = "x", config=None, etag=None, dry_run=False, state=None):
    src = SourceView(id=1, name=kind, kind=kind, config=config or {}, lang="en", scope="regional",
                     region_filter=False, cyber_filter=False, api_key_env=None, etag=etag, last_modified=None,
                     state=state or {}, backfill_days=3)
    http = HttpFetcher.create(transport=httpx.MockTransport(handler), ssrf_guard=False)
    return FetchContext(source=src, http=http, api_key=api_key, dry_run=dry_run)


def _json_handler(name: str, seen: list | None = None):
    body = fixture_bytes(name)

    def h(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(req)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    return h


# ---------------------------------------------------------------- URLhaus
async def test_urlhaus_regional_filter_defang_and_links():
    seen: list = []
    ctx = _ctx("urlhaus", _json_handler("urlhaus_recent.json", seen))
    res = await get_connector("urlhaus").fetch(ctx)
    assert seen[0].headers["Auth-Key"] == "x"
    assert seen[0].method == "GET" and str(seen[0].url).startswith("https://urlhaus-api.abuse.ch/v1/urls/recent/")
    assert [i.countries for i in res.items] == [["UZ"], ["KZ"]]  # IP, .com, notkz.com tashlangan
    uz, kz = res.items
    assert uz.title == "Malware URL on cdn.example-bank.uz (apk, Mirai)"
    assert kz.title == "Malware URL on shop.example.kz (malware_download)"
    assert uz.category == "malware" and uz.channel == "api" and uz.scope == "regional"
    ex = uz.extra
    assert ex["template"] == "indicator" and ex["ioc_type"] == "url" and ex["url_status"] == "online"
    assert ex["ioc"] == "hxxp://cdn[.]example-bank[.]uz/files/update[.]apk"  # query (email) olib tashlangan
    assert "victim" not in json.dumps(uz.__dict__, default=str)
    assert uz.url == "https://urlhaus.abuse.ch/url/3000001/"
    assert uz.dedup_key == "ioc:url:http://cdn.example-bank.uz/files/update.apk"
    assert uz.published is not None and uz.published.tzinfo is not None


async def test_urlhaus_item_url_is_never_the_malicious_url():
    res = await get_connector("urlhaus").fetch(_ctx("urlhaus", _json_handler("urlhaus_recent.json")))
    for it in res.items:
        assert it.url.startswith("https://urlhaus.abuse.ch/url/")
        assert it.extra["host"] not in it.url


async def test_urlhaus_no_results_and_missing_key():
    h = lambda r: httpx.Response(200, json={"query_status": "no_results"})  # noqa: E731
    assert (await get_connector("urlhaus").fetch(_ctx("urlhaus", h))).items == []
    with pytest.raises(AuthMissing):
        await get_connector("urlhaus").fetch(_ctx("urlhaus", h, api_key=None))


@pytest.mark.parametrize("kind", ["urlhaus", "threatfox"])
async def test_abusech_auth_errors(kind):
    with pytest.raises(AuthMissing):
        await get_connector(kind).fetch(_ctx(kind, lambda r: httpx.Response(401, json={})))
    with pytest.raises(SourceBlocked):
        await get_connector(kind).fetch(_ctx(kind, lambda r: httpx.Response(403, json={})))
    with pytest.raises(AuthMissing):  # 200 + query_status=unauthorized
        await get_connector(kind).fetch(_ctx(kind, lambda r: httpx.Response(200, json={"query_status": "unauthorized"})))


# ---------------------------------------------------------------- ThreatFox
async def test_threatfox_filter_and_shape():
    seen: list = []
    ctx = _ctx("threatfox", _json_handler("threatfox_get_iocs.json", seen))
    res = await get_connector("threatfox").fetch(ctx)
    req = seen[0]
    assert req.method == "POST" and req.headers["Auth-Key"] == "x"
    assert json.loads(req.content) == {"query": "get_iocs", "days": 3}
    # domain .uz, url .kg, IP (API davlat bergan: KZ); IP davlatsiz, .com, hash tashlangan
    assert [(i.extra["ioc_type"], i.countries) for i in res.items] == [("domain", ["UZ"]), ("url", ["KG"]), ("ip", ["KZ"])]
    dom, url, ip = res.items
    assert dom.title == "Malware IOC on c2.example.uz (Dridex)"
    assert dom.extra["ioc"] == "c2[.]example[.]uz" and dom.extra["threat"] == "Dridex" and dom.extra["confidence"] == 50
    assert dom.url == "https://threatfox.abuse.ch/ioc/41/"
    assert url.extra["ioc"] == "hxxps://drop[.]example[.]kg/gate[.]php"  # query olib tashlangan
    assert "user@" not in json.dumps(url.__dict__, default=str)
    assert url.dedup_key == "ioc:url:https://drop.example.kg/gate.php"
    assert ip.extra["host"] == "203.0.113.7" and ip.extra["ioc"] == "203[.]0[.]113[.]7:443"
    assert all(i.category == "malware" and i.channel == "api" and i.url.startswith("https://threatfox.abuse.ch/ioc/")
               for i in res.items)
    assert res.state and "last_seen" in res.state


async def test_threatfox_days_from_state_and_dry_run():
    seen: list = []
    h = _json_handler("threatfox_get_iocs.json", seen)
    await get_connector("threatfox").fetch(_ctx("threatfox", h, state={"last_seen": "2000-01-01T00:00:00+00:00"}))
    assert json.loads(seen[-1].content)["days"] == 7
    res = await get_connector("threatfox").fetch(_ctx("threatfox", h, dry_run=True))
    assert res.state is None


# ---------------------------------------------------------------- OpenPhish
SYNTHETIC = [  # SINTETIK qatorlar (haqiqiy lentada ular yo'q)
    "https://login.example-bank.uz/auth/verify.php?email=victim@example.com&token=abc#frag",
    "http://secure.example.kz/a/user@example.com/x",
    "https://payme-update.example.com/pay",
    "https://example.org/humo/card?x=1",
    "https://example.org/payment/form",       # 'payme' bo'lak, butun so'z emas
    "https://uzcard.example.net:8443/",
    "not a url",
]


def _feed() -> bytes:
    return fixture_bytes("openphish_feed.txt") + ("\n" + "\n".join(SYNTHETIC) + "\n").encode()


@pytest.fixture
def brands(monkeypatch):
    monkeypatch.setattr(settings, "tg_extra_keywords", "uzcard,humo,payme,xalq banki")


async def test_openphish_filter_brand_and_privacy(brands):
    seen: list = []

    def h(req):
        seen.append(req)
        return httpx.Response(200, content=_feed(), headers={"etag": '"abc"', "content-type": "text/plain"})

    res = await get_connector("openphish").fetch(_ctx("openphish", h, api_key=None))
    got = {i.extra["host"]: i for i in res.items}
    # haqiqiy 25 qatorlik namunada regional/brend yo'q → faqat sintetik qatorlar qoladi
    assert set(got) == {"login.example-bank.uz", "secure.example.kz", "payme-update.example.com",
                        "example.org", "uzcard.example.net"}
    assert len(res.items) == 5  # '/payment/form' qoldirilmagan
    uz = got["login.example-bank.uz"]
    assert uz.title == "Phishing URL on login.example-bank.uz" and uz.countries == ["UZ"]
    assert uz.extra["ioc"] == "hxxps://login[.]example-bank[.]uz/auth/verify[.]php"
    assert uz.extra["brand"] is None and uz.extra["ioc_type"] == "url"
    assert uz.category == "phishing" and uz.channel == "api" and uz.scope == "regional"
    assert uz.dedup_key == "ioc:url:https://login.example-bank.uz/auth/verify.php"
    assert got["payme-update.example.com"].title == "Phishing URL on payme-update.example.com targeting payme"
    assert got["example.org"].extra["brand"] == "humo"
    assert got["uzcard.example.net"].extra["ioc"] == "hxxps://uzcard[.]example[.]net:8443/"
    blob = json.dumps([i.__dict__ for i in res.items], default=str)
    for leak in ("victim", "user@", "token=", "?", "#frag"):
        assert leak not in blob
    assert res.etag == '"abc"'


async def test_openphish_item_url_never_the_phishing_url(brands):
    h = lambda r: httpx.Response(200, content=_feed())  # noqa: E731
    res = await get_connector("openphish").fetch(_ctx("openphish", h))
    assert res.items
    uids = set()
    for it in res.items:
        assert it.url.startswith("https://urlscan.io/") and "#ioc-" in it.url
        assert it.url != it.dedup_key.removeprefix("ioc:url:")
        uids.add(it.url)
    assert len(uids) == len(res.items)


async def test_openphish_without_brands_only_regional(monkeypatch):
    monkeypatch.setattr(settings, "tg_extra_keywords", "")
    h = lambda r: httpx.Response(200, content=_feed())  # noqa: E731
    res = await get_connector("openphish").fetch(_ctx("openphish", h))
    assert {i.extra["host"] for i in res.items} == {"login.example-bank.uz", "secure.example.kz"}
    assert next(i for i in res.items if i.extra["host"] == "secure.example.kz").extra["ioc"].count("@") == 0


async def test_openphish_conditional_get(brands):
    seen: list = []

    def h(req):
        seen.append(req)
        return httpx.Response(304) if req.headers.get("if-none-match") == '"abc"' else httpx.Response(200, content=_feed())

    res = await get_connector("openphish").fetch(_ctx("openphish", h, etag='"abc"'))
    assert res.not_modified and res.items == [] and seen[0].headers["if-none-match"] == '"abc"'
    res = await get_connector("openphish").fetch(_ctx("openphish", h, etag='"abc"', dry_run=True))
    assert "if-none-match" not in seen[-1].headers and res.items
    assert "auth-key" not in {k.lower() for k in seen[-1].headers}


async def test_openphish_follows_redirect_and_blocked(brands):
    def h(req):
        if req.url.host == "openphish.com":
            return httpx.Response(302, headers={"location": "https://raw.githubusercontent.com/openphish/public_feed/refs/heads/main/feed.txt"})
        return httpx.Response(200, content=_feed())

    assert (await get_connector("openphish").fetch(_ctx("openphish", h))).items
    with pytest.raises(SourceBlocked):
        await get_connector("openphish").fetch(_ctx("openphish", lambda r: httpx.Response(403, text="no")))
