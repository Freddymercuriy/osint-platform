"""ransomware_live_pro va ransomlook ulagichlari (tarmoqsiz).

- RansomLook: fixtures/ransomlook_recent.json — https://www.ransomlook.io/api/last/60 va /api/recent/100 dan yozib
  olingan HAQIQIY javob (kichraytirilgan, 8 element; 1 tasi haqiqiy UZ qurboni).
- PRO: kalit kerak, shuning uchun javob HUJJAT shaklida (https://api-pro.ransomware.live/swagger.json,
  `/victims/` tavsifidagi maydonlar: victim, group, attackdate, discovered, country, activity, website, permalink, id).
  Qiymatlar to'qilgan namuna.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.services.connectors import http as http_mod
from app.services.connectors import ransomlook, ransomware_live, ransomware_live_pro  # noqa: F401 (ro'yxatga olish)
from app.services.connectors.base import CONNECTORS, AuthMissing, FetchContext, SourceView
from app.services.connectors.http import HttpFetcher
from tests.helpers import fixture_bytes


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(http_mod, "PAUSE_RANGE", (0.0, 0.0))
    http_mod.reset_gates()


def _ctx(kind, handler, state=None, config=None, key="x", dry_run=False):
    src = SourceView(id=1, name=kind, kind=kind, config=config or {"countries": ["UZ", "KZ", "KG", "TJ", "TM"]},
                     lang="en", scope="regional", region_filter=False, cyber_filter=False, api_key_env=None,
                     etag=None, last_modified=None, state=state or {}, backfill_days=30)
    http = HttpFetcher.create(transport=httpx.MockTransport(handler), ssrf_guard=False)
    return FetchContext(source=src, http=http, api_key=key, dry_run=dry_run)


def _uz_nov(req) -> bool:
    """Namuna faqat UZ va sample sanasi oyi uchun qaytadi (backfill bir necha oyni so'raydi; joriy oy)."""
    return req.url.params["country"] == "UZ" and int(req.url.params["month"]) == datetime.now(UTC).month


PRO_SAMPLE = [
    {"victim": "Acme Bank", "group": "qilin", "attackdate": "2026-11-10T08:00:00+00:00",
     "discovered": "2026-11-10T09:00:00+00:00", "country": "UZ", "activity": "Financial Services",
     "website": "acme.uz", "screenshot": "", "press": None, "id": "QWNtZQ==",
     "permalink": "https://www.ransomware.live/id/QWNtZQ=="},
    {"victim": "Onion Co", "group": "akira", "attackdate": "2026-11-11T08:00:00+00:00",
     "discovered": "2026-11-11T09:00:00+00:00", "country": "UZ", "activity": "Not Found", "website": "",
     "permalink": "http://abcdef.onion/x"},
]


# ---------------------------------------------------------------- PRO
def test_pro_class_requires_key():
    cls = CONNECTORS["ransomware_live_pro"]
    assert cls.key == "required" and cls.default_key_env == "RANSOMWARE_LIVE_API_KEY"


async def test_pro_parses_and_sends_key_and_filters():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=PRO_SAMPLE if _uz_nov(req) else [])

    ctx = _ctx("ransomware_live_pro", handler)
    res = await CONNECTORS["ransomware_live_pro"]().fetch(ctx)
    assert all(r.headers["x-api-key"] == "x" for r in seen)
    assert all(r.url.host == "api-pro.ransomware.live" and r.url.path == "/victims/" for r in seen)
    assert {r.url.params["country"] for r in seen} == {"UZ", "KZ", "KG", "TJ", "TM"}
    assert all("year" in r.url.params and "month" in r.url.params for r in seen)
    assert len(res.items) == 2
    it = res.items[0]
    assert it.title == "[qilin] Acme Bank (UZ) — Financial Services"
    assert it.countries == ["UZ"] and it.actor == "qilin" and it.category == "ransomware"
    assert it.extra["template"] == "ransomware_victim" and it.url == "https://www.ransomware.live/id/QWNtZQ=="
    assert res.items[1].url == "https://www.ransomware.live/group/akira" and ".onion" not in res.items[1].url
    assert res.state == {"last_discovered": "2026-11-11T09:00:00+00:00"}


async def test_pro_cursor_skips_seen_and_dry_run_no_state():
    h = lambda req: httpx.Response(200, json=PRO_SAMPLE if _uz_nov(req) else [])  # noqa: E731
    res = await CONNECTORS["ransomware_live_pro"]().fetch(
        _ctx("ransomware_live_pro", h, state={"last_discovered": "2026-11-10T09:00:00+00:00"}))
    assert [i.extra["victim"] for i in res.items] == ["Onion Co"]
    dry = await CONNECTORS["ransomware_live_pro"]().fetch(_ctx("ransomware_live_pro", h, dry_run=True))
    assert len(dry.items) == 2 and dry.state is None


async def test_pro_401_is_auth_missing_and_404_is_empty():
    with pytest.raises(AuthMissing):
        await CONNECTORS["ransomware_live_pro"]().fetch(
            _ctx("ransomware_live_pro", lambda r: httpx.Response(401, json={"message": "Missing X-API-KEY header"})))
    res = await CONNECTORS["ransomware_live_pro"]().fetch(
        _ctx("ransomware_live_pro", lambda r: httpx.Response(404, json={})))
    assert res.items == []


async def test_pro_dedup_key_equals_legacy():
    legacy_row = {"victim": "Acme Bank", "group": "qilin", "country": "UZ", "domain": "acme.uz",
                  "activity": "Financial Services", "discovered": "2026-11-10T09:00:00+00:00",
                  "url": "https://www.ransomware.live/id/QWNtZQ=="}
    legacy = await CONNECTORS["ransomware_live"]().fetch(
        _ctx("ransomware_live", lambda r: httpx.Response(200, json=[legacy_row])))
    pro = await CONNECTORS["ransomware_live_pro"]().fetch(
        _ctx("ransomware_live_pro", lambda r: httpx.Response(200, json=PRO_SAMPLE[:1] if _uz_nov(r) else [])))
    a, b = legacy.items[0], pro.items[0]
    assert (a.dedup_key, a.title, a.actor, a.countries, a.extra) == (b.dedup_key, b.title, b.actor, b.countries, b.extra)


# ---------------------------------------------------------------- RansomLook
def _rl(extra=()):
    return json.loads(fixture_bytes("ransomlook_recent.json")) + list(extra)


async def test_ransomlook_real_fixture_keeps_only_central_asia():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=_rl())

    res = await CONNECTORS["ransomlook"]().fetch(_ctx("ransomlook", handler))
    assert seen[0].url.path == "/api/recent/100" and "x-api-key" not in seen[0].headers
    assert len(res.items) == 1
    it = res.items[0]
    assert it.countries == ["UZ"] and it.actor == "n0n" and it.category == "ransomware"
    assert it.title.startswith("[n0n] FinSoft")
    assert it.url == "https://www.ransomlook.io/group/n0n"
    assert it.published is not None and it.published.tzinfo is not None


async def test_ransomlook_domain_country_and_links_never_onion():
    extra = [
        {"post_title": "Acme Steel (acme.kz)", "group_name": "Qilin", "discovered": "2026-11-12 10:00:00.5",
         "description": "", "link": "/site/blog?uuid=1", "private": False},
        {"post_title": "Bad Link LLC (bad.kg)", "group_name": "akira", "discovered": "2026-11-12 11:00:00",
         "description": "", "link": "http://abc.onion/post", "private": False},
        {"post_title": "Elsewhere Inc (elsewhere.com)", "group_name": "akira", "discovered": "2026-11-12 11:00:00",
         "description": "US only", "link": None, "private": False},
    ]
    res = await CONNECTORS["ransomlook"]().fetch(_ctx("ransomlook", lambda r: httpx.Response(200, json=_rl(extra))))
    by = {i.extra["victim"]: i for i in res.items}
    assert set(by) == {"FinSoft (Kolibri retail back-office software)", "Acme Steel (acme.kz)", "Bad Link LLC (bad.kg)"}
    assert by["Acme Steel (acme.kz)"].countries == ["KZ"]
    assert by["Acme Steel (acme.kz)"].url == "https://www.ransomlook.io/site/blog?uuid=1"
    assert by["Bad Link LLC (bad.kg)"].url == "https://www.ransomlook.io/group/akira"
    assert all(".onion" not in i.url for i in res.items)


async def test_ransomlook_dedup_key_matches_ransomware_live():
    row = {"post_title": "Acme Steel (acme.kz)", "group_name": "qilin", "discovered": "2026-11-12 10:00:00",
           "description": "", "link": None, "private": False}
    rl = await CONNECTORS["ransomlook"]().fetch(_ctx("ransomlook", lambda r: httpx.Response(200, json=[row])))
    assert rl.items[0].dedup_key == ransomware_live.victim_key("Acme Steel (acme.kz)", "acme.kz") == "victim:acme.kz"
    live_row = {"victim": "Acme Steel (acme.kz)", "group": "qilin", "country": "KZ", "domain": "acme.kz",
                "discovered": "2026-11-12T10:00:00+00:00", "url": ""}
    live = await CONNECTORS["ransomware_live"]().fetch(_ctx("ransomware_live", lambda r: httpx.Response(200, json=[live_row])))
    assert live.items[0].dedup_key == rl.items[0].dedup_key


async def test_ransomlook_non_list_is_error():
    from app.services.connectors.base import ConnectorError

    with pytest.raises(ConnectorError):
        await CONNECTORS["ransomlook"]().fetch(_ctx("ransomlook", lambda r: httpx.Response(200, json={"message": "x"})))
