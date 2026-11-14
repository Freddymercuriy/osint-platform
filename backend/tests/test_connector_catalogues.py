"""hibp_breaches, cisa_kev, nvd_cves: tarmoqsiz (httpx.MockTransport) testlar, yozib olingan javoblar bilan."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.services.connectors import cisa_kev, http, nvd
from app.services.connectors.base import FetchContext, SourceView
from app.services.connectors.cisa_kev import CisaKevConnector
from app.services.connectors.hibp import HibpBreachesConnector
from app.services.connectors.http import HttpFetcher
from app.services.connectors.nvd import NvdCvesConnector
from tests.helpers import fixture_bytes


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(http, "PAUSE_RANGE", (0.0, 0.0))
    monkeypatch.setattr(nvd, "PAGE_PAUSE_NO_KEY", 0.0)
    monkeypatch.setattr(nvd, "PAGE_PAUSE_KEY", 0.0)
    http.reset_gates()


def _ctx(handler, kind, state=None, api_key=None, backfill_days=14, etag=None, dry_run=False, config=None):
    src = SourceView(id=1, name=kind, kind=kind, config=config or {}, lang="en", scope="global", region_filter=False,
                     cyber_filter=False, api_key_env=None, etag=etag, last_modified=None, state=state or {},
                     backfill_days=backfill_days)
    fetcher = HttpFetcher.create(transport=httpx.MockTransport(handler), ssrf_guard=False)
    return FetchContext(source=src, http=fetcher, api_key=api_key, dry_run=dry_run)


def _json(name):
    return json.loads(fixture_bytes(name))


# ================================================================ HIBP
def _hibp_days(data):
    """Fixture'ni hozirga nisbatan siljitadi: eng yangi element — 1 kun oldin (backfill oynasi barqaror bo'lsin)."""
    newest = max(datetime.fromisoformat(b["AddedDate"].replace("Z", "+00:00")) for b in data)
    shift = datetime.now(UTC) - timedelta(days=1) - newest
    for b in data:
        d = datetime.fromisoformat(b["AddedDate"].replace("Z", "+00:00")) + shift
        b["AddedDate"] = d.strftime("%Y-%m-%dT%H:%M:%SZ")
    return data


async def test_hibp_parse_scope_and_filters():
    data = _hibp_days(_json("hibp_breaches.json"))
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=data, headers={"etag": '"abc"'})

    res = await HibpBreachesConnector().fetch(_ctx(handler, "hibp_breaches", backfill_days=10_000))
    assert seen[0].url.path == "/api/v3/breaches"
    assert "OSINT-Platform" in seen[0].headers["user-agent"]
    # spam / fabricated / retired tashlab ketilgan
    flagged = [b for b in data if b["IsSpamList"] or b["IsFabricated"] or b["IsRetired"]]
    assert len(flagged) >= 3 and len(res.items) == len(data) - len(flagged)
    assert res.etag == '"abc"'
    by_name = {i.extra["breach_name"]: i for i in res.items}
    kz = by_name["ExampleKzShop"]
    assert kz.scope == "regional" and "KZ" in kz.countries
    assert kz.title == f"Example KZ Shop: {kz.extra['pwn_count']:,} accounts breached"
    assert kz.category == "leak" and kz.channel == "api" and kz.extra["template"] == "breach"
    assert all(isinstance(c, str) for c in kz.extra["data_classes"])
    others = [i for n, i in by_name.items() if n != "ExampleKzShop"]
    assert any(i.scope == "global" for i in others)
    for i in res.items:
        assert i.published.tzinfo is not None and len(i.summary) <= 600 and "<" not in i.summary
        assert i.url.startswith("https://") and "is_verified" in i.extra
    assert res.state["last_added"] == max(i.published for i in res.items).isoformat()


async def test_hibp_country_named_in_description_is_regional():
    data = [{"Name": "X", "Title": "X", "Domain": "x.com", "BreachDate": "2026-01-01",
             "AddedDate": (datetime.now(UTC) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ"), "PwnCount": 5,
             "Description": "Customers of an <b>Uzbekistan</b> bank " + "x" * 900, "DataClasses": ["Emails"],
             "IsVerified": True, "IsSensitive": False, "IsSpamList": False, "IsFabricated": False, "IsRetired": False}]
    res = await HibpBreachesConnector().fetch(_ctx(lambda r: httpx.Response(200, json=data), "hibp_breaches"))
    item = res.items[0]
    assert item.scope == "regional" and item.countries == ["UZ"]
    assert len(item.summary) == 600 and "<b>" not in item.summary


async def test_hibp_cursor_returns_only_newer():
    data = _hibp_days(_json("hibp_breaches.json"))
    first = await HibpBreachesConnector().fetch(
        _ctx(lambda r: httpx.Response(200, json=data), "hibp_breaches", backfill_days=10_000))
    again = await HibpBreachesConnector().fetch(
        _ctx(lambda r: httpx.Response(200, json=data), "hibp_breaches", state=first.state, backfill_days=10_000))
    assert first.items and again.items == []
    newer = dict(data[0], Name="Brand New", Title="Brand New",
                 AddedDate=(datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    third = await HibpBreachesConnector().fetch(
        _ctx(lambda r: httpx.Response(200, json=data + [newer]), "hibp_breaches", state=first.state,
             backfill_days=10_000))
    assert [i.extra["breach_name"] for i in third.items] == ["Brand New"]


async def test_hibp_first_run_respects_backfill_and_dry_run_ignores_cursor():
    data = _hibp_days(_json("hibp_breaches.json"))
    handler = lambda r: httpx.Response(200, json=data)  # noqa: E731
    narrow = await HibpBreachesConnector().fetch(_ctx(handler, "hibp_breaches", backfill_days=2))
    assert 1 <= len(narrow.items) < 20
    state = {"last_added": datetime.now(UTC).isoformat()}
    dry = await HibpBreachesConnector().fetch(_ctx(handler, "hibp_breaches", state=state, backfill_days=10_000,
                                                   dry_run=True))
    assert dry.items and dry.state is None


async def test_hibp_conditional_get_and_304():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(304)

    res = await HibpBreachesConnector().fetch(_ctx(handler, "hibp_breaches", etag='"abc"'))
    assert res.not_modified and res.items == [] and res.http_status == 304
    assert seen[0].headers["if-none-match"] == '"abc"'
    await HibpBreachesConnector().fetch(_ctx(handler, "hibp_breaches", etag='"abc"', dry_run=True))
    assert "if-none-match" not in seen[1].headers


# ================================================================ CISA KEV
async def test_kev_parse_first_run_and_severity():
    data = _json("cisa_kev.json")
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=data, headers={"etag": '"k1"', "content-type": "text/plain"})

    assert "cisagov/kev-data" in cisa_kev.DEFAULT_URL
    res = await CisaKevConnector().fetch(_ctx(handler, "cisa_kev", backfill_days=100_000))
    assert len(res.items) == len(data["vulnerabilities"]) and res.etag == '"k1"'
    by = {i.extra["cve_id"]: i for i in res.items}
    known = [v for v in data["vulnerabilities"] if v["knownRansomwareCampaignUse"] == "Known"][0]
    assert by[known["cveID"]].severity == "critical"
    plain = [v for v in data["vulnerabilities"] if v["knownRansomwareCampaignUse"] != "Known"][0]
    it = by[plain["cveID"]]
    assert it.severity == "high" and it.scope == "global" and it.category == "vulnerability" and it.channel == "api"
    assert it.url == f"https://nvd.nist.gov/vuln/detail/{plain['cveID']}"
    assert it.title == f"{plain['cveID']}: {plain['vendorProject']} {plain['product']} — {plain['vulnerabilityName']}"
    assert it.extra["kev"] is True and it.extra["due_date"] == plain["dueDate"] and it.extra["cwes"] == plain["cwes"]
    assert it.published.tzinfo is not None and len(it.summary) <= 600
    # birinchi chaqiruv oynasi: backfill_days=0 → hech narsa (fixture eski)
    none = await CisaKevConnector().fetch(_ctx(handler, "cisa_kev", backfill_days=0))
    assert none.items == []


async def test_kev_cursor_only_newer_and_same_day_additions():
    data = _json("cisa_kev.json")
    handler = lambda r: httpx.Response(200, json=data)  # noqa: E731
    first = await CisaKevConnector().fetch(_ctx(handler, "cisa_kev", backfill_days=100_000))
    top = max(v["dateAdded"] for v in data["vulnerabilities"])
    assert first.state["last_added"] == top
    again = await CisaKevConnector().fetch(_ctx(handler, "cisa_kev", state=first.state, backfill_days=100_000))
    assert again.items == []
    extra = dict(data["vulnerabilities"][0], cveID="CVE-2099-0001", dateAdded=top)
    later = dict(data, vulnerabilities=data["vulnerabilities"] + [extra])
    same_day = await CisaKevConnector().fetch(
        _ctx(lambda r: httpx.Response(200, json=later), "cisa_kev", state=first.state))
    assert [i.extra["cve_id"] for i in same_day.items] == ["CVE-2099-0001"]
    assert "CVE-2099-0001" in same_day.state["seen"] and len(same_day.state["seen"]) > 1
    newer = dict(extra, cveID="CVE-2099-0002", dateAdded="2099-01-01")
    nxt = await CisaKevConnector().fetch(
        _ctx(lambda r: httpx.Response(200, json=dict(data, vulnerabilities=data["vulnerabilities"] + [newer])),
             "cisa_kev", state=first.state))
    assert [i.extra["cve_id"] for i in nxt.items] == ["CVE-2099-0002"] and nxt.state["last_added"] == "2099-01-01"


async def test_kev_304_and_custom_url():
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(304)

    res = await CisaKevConnector().fetch(_ctx(handler, "cisa_kev", etag='"k1"', config={"url": "https://m.example/k.json"}))
    assert res.not_modified and seen[0].headers["if-none-match"] == '"k1"' and seen[0].url.host == "m.example"


# ================================================================ NVD
def _nvd_fixture_shifted():
    data = _json("nvd_cves.json")
    now = datetime.now(UTC)
    for n, v in enumerate(data["vulnerabilities"]):
        v["cve"]["published"] = (now - timedelta(days=10 - n)).strftime("%Y-%m-%dT%H:%M:%S.000")
    return data


async def test_nvd_parse_and_params_without_key():
    data = _nvd_fixture_shifted()
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=data)

    res = await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves"))
    req = seen[0]
    assert "apikey" not in req.headers
    q = dict(req.url.params)
    assert q["cvssV3Severity"] == "CRITICAL" and q["resultsPerPage"] == "2000" and q["startIndex"] == "0"
    start = datetime.fromisoformat(q["pubStartDate"]).replace(tzinfo=UTC)
    end = datetime.fromisoformat(q["pubEndDate"]).replace(tzinfo=UTC)
    assert timedelta(days=13) < end - start < timedelta(days=15)
    assert len(res.items) == len(data["vulnerabilities"])
    first = res.items[0]
    assert first.extra["template"] == "cve" and first.extra["cvss"] >= 9 and first.severity == "critical"
    assert first.scope == "global" and first.category == "vulnerability" and first.channel == "api"
    by = {i.extra["cve_id"]: i for i in res.items}
    kev = by["CVE-2026-116606"]
    assert kev.extra["kev"] is True and kev.extra["vendor"] == "barracuda"
    assert by["CVE-2026-100358"].extra["kev"] is False and by["CVE-2026-100358"].extra["product"] == "suitecrm"
    assert kev.title.startswith("CVE-2026-116606: An authentication bypass") and len(kev.title) <= 18 + 160 + 1
    assert kev.url == "https://nvd.nist.gov/vuln/detail/CVE-2026-116606"
    assert res.state["last_published"] == max(i.published for i in res.items).isoformat()


async def test_nvd_api_key_header_only_when_given():
    data = _nvd_fixture_shifted()
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=data)

    await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves", api_key="SECRET"))
    assert seen[0].headers["apikey"] == "SECRET"
    assert "SECRET" not in str(seen[0].url)


async def test_nvd_cursor_and_range_limit():
    data = _nvd_fixture_shifted()
    seen = []

    def handler(req):
        seen.append(req)
        return httpx.Response(200, json=data)

    first = await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves"))
    again = await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves", state=first.state))
    assert again.items == [] and again.state == first.state
    # backfill 400 kun → 120 kunga qisqartiriladi
    await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves", backfill_days=400))
    q = dict(seen[-1].url.params)
    span = datetime.fromisoformat(q["pubEndDate"]) - datetime.fromisoformat(q["pubStartDate"])
    assert span <= timedelta(days=120)
    # eski kursor ham 120 kundan oshmaydi
    old = {"last_published": (datetime.now(UTC) - timedelta(days=300)).isoformat()}
    await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves", state=old))
    q = dict(seen[-1].url.params)
    assert datetime.fromisoformat(q["pubEndDate"]) - datetime.fromisoformat(q["pubStartDate"]) <= timedelta(days=120)


async def test_nvd_pagination_and_page_pause(monkeypatch):
    data = _nvd_fixture_shifted()
    vulns = data["vulnerabilities"]
    monkeypatch.setattr(nvd, "PAGE_SIZE", 2)
    pauses = []
    real_sleep = nvd.asyncio.sleep

    async def fake_sleep(s):
        pauses.append(s)
        await real_sleep(0)

    monkeypatch.setattr(nvd.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(nvd, "PAGE_PAUSE_NO_KEY", 6.0)
    seen = []

    def handler(req):
        seen.append(req)
        i = int(req.url.params["startIndex"])
        return httpx.Response(200, json=dict(data, totalResults=len(vulns), startIndex=i,
                                             vulnerabilities=vulns[i:i + 2]))

    res = await NvdCvesConnector().fetch(_ctx(handler, "nvd_cves"))
    assert [r.url.params["startIndex"] for r in seen] == ["0", "2", "4"][: len(seen)] and len(seen) == 3
    assert len(res.items) == len(vulns)
    assert pauses.count(6.0) == 2


async def test_nvd_skips_non_critical_items():
    data = _nvd_fixture_shifted()
    data["vulnerabilities"][0]["cve"]["metrics"] = {
        "cvssMetricV31": [{"cvssData": {"version": "3.1", "baseScore": 7.5, "baseSeverity": "HIGH"}}]}
    res = await NvdCvesConnector().fetch(_ctx(lambda r: httpx.Response(200, json=data), "nvd_cves"))
    assert len(res.items) == len(data["vulnerabilities"]) - 1


def test_nvd_registration_and_key_meta():
    from app.services.connectors.base import CONNECTORS
    assert CONNECTORS["nvd_cves"].key == "optional" and CONNECTORS["nvd_cves"].default_key_env == "NVD_API_KEY"
    assert {"hibp_breaches", "cisa_kev", "nvd_cves"} <= set(CONNECTORS)
