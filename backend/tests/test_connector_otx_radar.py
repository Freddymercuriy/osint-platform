"""OTX pulses va Cloudflare Radar ulagichlari (tarmoqsiz).

Fixture'lar kalitsiz olinmagan — hujjat/SDK shaklida qo'lda tuzilgan:
- otx_pulses_page*.json: OTX-Python-SDK (OTXv2.py) `pulses/subscribed` javobi (`results`, `next`) va pulse maydonlari.
- cloudflare_radar_outages.json: Cloudflare OpenAPI sxemasi `GET /radar/annotations/outages`
  (developers.cloudflare.com/api/operations/radar-get-annotations-outages), `result.annotations[]`.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.connectors import cloudflare_radar, http, otx  # noqa: F401  (ro'yxatga oladi)
from app.services.connectors.base import AuthMissing, FetchContext, SourceBlocked, SourceView
from app.services.connectors.http import HttpFetcher
from tests.helpers import fixture_bytes


@pytest.fixture(autouse=True)
def _nopause(monkeypatch):
    monkeypatch.setattr(http, "PAUSE_RANGE", (0.0, 0.0))
    http.reset_gates()


def _ctx(kind, handler, state=None, key="x", config=None, dry_run=False):
    src = SourceView(id=1, name=kind, kind=kind, config=config or {}, lang="en", scope="regional", region_filter=True,
                     cyber_filter=False, api_key_env=None, etag=None, last_modified=None, state=state or {},
                     backfill_days=14)
    fetcher = HttpFetcher.create(transport=httpx.MockTransport(handler), ssrf_guard=False)
    return FetchContext(source=src, http=fetcher, api_key=key, dry_run=dry_run)


def _otx_handler(seen):
    def h(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        name = "otx_pulses_page2.json" if req.url.params.get("page") == "2" else "otx_pulses_page1.json"
        return httpx.Response(200, content=fixture_bytes(name))
    return h


async def test_otx_region_filter_tlp_pagination_cursor():
    seen: list[httpx.Request] = []
    res = await otx.OtxPulsesConnector().fetch(_ctx("otx_pulses", _otx_handler(seen)))
    assert len(seen) == 2
    assert all(r.headers["x-otx-api-key"] == "x" for r in seen)
    assert seen[0].url.params["modified_since"] and seen[0].url.params["limit"] == "50"
    ids = [i.extra["otx_id"] for i in res.items]
    assert ids == ["6700000000000000000000a1", "6700000000000000000000a4"]  # Germany va TLP:red tashlandi
    a1, a4 = res.items
    assert a1.countries == ["UZ"] and a1.category == "phishing" and a1.actor == "TA-Example"
    assert a1.channel == "api" and a1.url.endswith("/pulse/6700000000000000000000a1")
    assert a1.extra["attack_ids"] == ["T1566"] and a1.extra["indicator_count"] == 2
    assert a1.extra["malware_families"] == ["Agent"] and a1.published is not None
    assert a4.countries == ["KG"] and a4.category == "ransomware" and a4.extra["malware_families"] == ["LockBit"]
    assert res.state == {"modified_since": "2026-11-11T07:00:00"}


async def test_otx_uses_saved_cursor_and_dry_run_ignores_it():
    seen: list[httpx.Request] = []
    await otx.OtxPulsesConnector().fetch(_ctx("otx_pulses", _otx_handler(seen), state={"modified_since": "2026-11-09T00:00:00"}))
    assert seen[0].url.params["modified_since"] == "2026-11-09T00:00:00"
    seen.clear()
    res = await otx.OtxPulsesConnector().fetch(
        _ctx("otx_pulses", _otx_handler(seen), state={"modified_since": "2026-11-09T00:00:00"}, dry_run=True))
    assert seen[0].url.params["modified_since"] != "2026-11-09T00:00:00" and res.state is None


async def test_otx_page_cap():
    seen: list[httpx.Request] = []
    res = await otx.OtxPulsesConnector().fetch(_ctx("otx_pulses", _otx_handler(seen), config={"max_pages": 1}))
    assert len(seen) == 1 and res.note


@pytest.mark.parametrize("code, exc", [(401, AuthMissing), (403, AuthMissing)])
async def test_otx_auth_errors(code, exc):
    with pytest.raises(exc):
        await otx.OtxPulsesConnector().fetch(_ctx("otx_pulses", lambda r: httpx.Response(code, json={"detail": "x"})))


async def test_otx_missing_key():
    with pytest.raises(AuthMissing):
        await otx.OtxPulsesConnector().fetch(_ctx("otx_pulses", lambda r: httpx.Response(200), key=None))


async def test_radar_outage_items_and_auth_header():
    seen: list[httpx.Request] = []

    def h(req):
        seen.append(req)
        return httpx.Response(200, content=fixture_bytes("cloudflare_radar_outages.json"))

    res = await cloudflare_radar.CloudflareRadarConnector().fetch(_ctx("cloudflare_radar", h))
    assert [r.url.params["location"] for r in seen] == ["UZ", "KZ", "KG", "TJ", "TM"]
    assert all(r.headers["authorization"] == "Bearer x" and r.url.params["dateStart"] for r in seen)
    assert all(r.url.params["dateEnd"] > r.url.params["dateStart"] for r in seen)  # dateEnd'siz API — 400
    assert len(res.items) == 2  # id bo'yicha takrorsiz, AQSh tashlandi
    a, b = res.items
    assert a.title == "Internet outage in Kazakhstan: power outage" and a.url == "https://example.org/report"
    assert a.category == "ddos-outage" and a.channel == "api" and a.scope == "regional" and a.countries == ["KZ"]
    assert a.extra == {**a.extra, "template": "outage", "country": "Kazakhstan", "scope": "Country",
                       "cause": "power outage", "start": "2026-11-05T10:00:00Z", "end": "2026-11-05T14:30:00Z",
                       "asns": [41202, 8449]}
    assert a.dedup_key == "radar-outage:550" and a.published is not None
    assert b.countries == ["KZ", "KG"] and b.url == cloudflare_radar.OUTAGE_CENTER and b.extra["end"] is None
    assert "last_run" in res.state


async def test_radar_state_window_and_errors():
    seen: list[httpx.Request] = []

    def h(req):
        seen.append(req)
        return httpx.Response(200, json={"result": {"annotations": []}})

    await cloudflare_radar.CloudflareRadarConnector().fetch(
        _ctx("cloudflare_radar", h, state={"last_run": "2026-11-10T00:00:00Z"}, config={"countries": ["UZ"]}))
    assert len(seen) == 1 and seen[0].url.params["dateStart"] == "2026-11-03T00:00:00Z"
    with pytest.raises(AuthMissing):
        await cloudflare_radar.CloudflareRadarConnector().fetch(_ctx("cloudflare_radar", lambda r: httpx.Response(401)))
    with pytest.raises(SourceBlocked):
        await cloudflare_radar.CloudflareRadarConnector().fetch(_ctx("cloudflare_radar", lambda r: httpx.Response(403)))
