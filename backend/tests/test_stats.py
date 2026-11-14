"""Bosqich 8: statistika endpointlari (filtrlar, Toshkent vaqti bo'yicha bo'laklar, oldingi davr, top-N)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models import EventRecord, Source

NOW = datetime.now(UTC)


def ev(uid, *, hours_ago, category="phishing", severity="medium", countries=("UZ",), source="S1", channel="news",
       scope="regional", actor=None, sector=None, also=0):
    return EventRecord(
        uid=uid, source=source, category=category, title=uid, url=f"https://x.example/{uid}", summary="", lang="en",
        published=NOW - timedelta(hours=hours_ago), severity=severity, countries=list(countries), channel=channel,
        scope=scope, actor=actor, sector=sector, also_reported_by=[{"source": "X", "url": "u", "at": "t"}] * also,
    )


@pytest.fixture
async def data(db):
    rows = [
        ev("a", hours_ago=1, category="ransomware", severity="critical", actor="akira", sector="finance", channel="api"),
        ev("b", hours_ago=2, category="ransomware", severity="critical", actor="akira", countries=("KZ",), channel="api"),
        ev("c", hours_ago=30, category="leak", severity="high", countries=("UZ", "KZ"), also=2),
        ev("d", hours_ago=50, category="phishing", source="S2"),
        ev("e", hours_ago=60, category="fraud", countries=()),
        ev("f", hours_ago=24 * 9, category="leak", severity="high"),  # oldingi 7 kunlik davrda
        ev("g", hours_ago=24 * 10, category="phishing"),
        ev("h", hours_ago=5, category="vulnerability", severity="high", scope="global", countries=()),
    ]
    db.add_all(rows)
    await db.commit()
    return rows


async def test_kpis_with_previous_period(client, analyst_headers, data):
    k = (await client.get("/api/stats/kpis?range=7d", headers=analyst_headers)).json()
    assert k["total"] == 5 and k["previous_total"] == 2 and k["change_pct"] == 150.0
    assert k["critical_high"] == 3 and k["critical_high_previous"] == 1
    assert k["by_severity"] == {"critical": 2, "high": 1, "medium": 2}
    assert k["countries_affected"] == 2 and k["sources_reporting"] == 2 and k["multi_source"] == 1
    assert k["ransomware"] == 2 and k["ransomware_previous"] == 0
    g = (await client.get("/api/stats/kpis?range=7d&scope=all", headers=analyst_headers)).json()
    assert g["total"] == 6  # global CVE ham
    f = (await client.get("/api/stats/kpis?range=7d&category=ransomware&country=KZ", headers=analyst_headers)).json()
    assert f["total"] == 1


async def test_timeseries_buckets_and_grouping(client, analyst_headers, data):
    t = (await client.get("/api/stats/timeseries?range=7d&group_by=category", headers=analyst_headers)).json()
    assert t["bucket"] == "day" and len(t["buckets"]) in (7, 8) and sum(t["totals"]) == 5
    keys = {s["key"]: s["total"] for s in t["series"]}
    assert keys == {"ransomware": 2, "leak": 1, "phishing": 1, "fraud": 1}
    assert all(len(s["values"]) == len(t["buckets"]) for s in t["series"])
    # top=2 → qolganlari "__other__"
    t2 = (await client.get("/api/stats/timeseries?range=7d&group_by=category&top=2", headers=analyst_headers)).json()
    assert [s["key"] for s in t2["series"]][-1] == "__other__" and len(t2["series"]) == 3
    assert sum(s["total"] for s in t2["series"]) == 5
    # davlat: bitta hodisa ikki davlatda; davlatsiz — "__none__"
    c = (await client.get("/api/stats/timeseries?range=7d&group_by=country", headers=analyst_headers)).json()
    assert {s["key"]: s["total"] for s in c["series"]} == {"UZ": 3, "KZ": 2, "__none__": 1}
    assert sum(c["totals"]) == 5
    h = (await client.get("/api/stats/timeseries?range=24h", headers=analyst_headers)).json()
    assert h["bucket"] == "hour" and sum(h["totals"]) == 2 and h["series"] == []


async def test_timeseries_uses_tashkent_days(client, analyst_headers, db):
    # 2026-11-10 20:30 UTC = 2026-11-11 01:30 Toshkent → 11-noyabr kuniga tushishi kerak
    db.add(EventRecord(uid="tz", source="S", category="leak", title="t", url="https://x.example/tz", summary="",
                       lang="en", published=datetime(2026, 11, 10, 20, 30, tzinfo=UTC)))
    await db.commit()
    t = (await client.get("/api/stats/timeseries?date_from=2026-11-10&date_to=2026-11-11&bucket=day",
                          headers=analyst_headers)).json()
    assert t["buckets"] == ["2026-11-10T00:00:00", "2026-11-11T00:00:00"]
    assert t["totals"] == [0, 1]


async def test_breakdowns(client, analyst_headers, data):
    b = (await client.get("/api/stats/breakdown?range=7d&by=category", headers=analyst_headers)).json()
    assert b["items"][0] == {"key": "ransomware", "count": 2} and b["total"] == 5 and b["other"] == 0
    a = (await client.get("/api/stats/breakdown?range=7d&by=actor", headers=analyst_headers)).json()
    assert a["items"] == [{"key": "akira", "count": 2}]
    s = (await client.get("/api/stats/breakdown?range=7d&by=sector", headers=analyst_headers)).json()
    assert s["items"] == [{"key": "finance", "count": 1}]
    c = (await client.get("/api/stats/breakdown?range=7d&by=country&include_none=true", headers=analyst_headers)).json()
    assert {i["key"]: i["count"] for i in c["items"]} == {"UZ": 3, "KZ": 2, "__none__": 1}
    lim = (await client.get("/api/stats/breakdown?range=7d&by=category&limit=1", headers=analyst_headers)).json()
    assert len(lim["items"]) == 1 and lim["other"] == 3


async def test_heatmap(client, analyst_headers, data):
    h = (await client.get("/api/stats/heatmap?range=7d", headers=analyst_headers)).json()
    assert h["timezone"] == "Asia/Tashkent" and sum(c[2] for c in h["cells"]) == 5
    assert all(0 <= c[0] <= 6 and 0 <= c[1] <= 23 for c in h["cells"]) and h["max"] >= 1


async def test_source_health_and_latest(client, analyst_headers, data, db):
    db.add(Source(name="Broken", kind="rss", config={"url": "https://b.example/rss"}, status="down",
                  down_since=NOW - timedelta(hours=5), last_error="HTTP 500"))
    await db.commit()
    sh = (await client.get("/api/stats/source-health", headers=analyst_headers)).json()
    assert sh["by_status"]["down"] == 1 and sh["failing"][0]["name"] == "Broken"
    lt = (await client.get("/api/stats/latest?range=7d&min_severity=high", headers=analyst_headers)).json()
    assert [e["title"] for e in lt] == ["a", "b", "c"]


async def test_stats_require_auth(client):
    for p in ("kpis", "timeseries", "breakdown", "heatmap", "source-health", "latest"):
        assert (await client.get(f"/api/stats/{p}")).status_code == 401
