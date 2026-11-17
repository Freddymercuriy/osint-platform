"""0014: xalqaro kiber-saytlar Global (hudud filtrisiz); global manbaning Markaziy Osiyo haqidagi yangiligi — regional."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from sqlalchemy import select

from app.models import EventRecord, Source
from app.services.connectors.base import RawItem
from app.services.events import pipeline, scheduler
from tests.helpers import ago, rss, use_transport


async def test_migration_made_international_cyber_sites_global(db):
    rows = {s.name: s for s in (await db.scalars(select(Source))).all()}
    for name in ("The Hacker News", "SecurityWeek", "Habr: Информационная безопасность", "Dark Web Informer",
                 "BleepingComputer", "CyberNews", "The Cyber Express"):
        s = rows[name]
        assert s.scope == "global" and not s.region_filter and not s.cyber_filter, name
        assert s.baseline_done is False and s.etag is None and "Global (0014)" in s.notes, name
    assert rows["BleepingComputer"].config["query"] == "site:bleepingcomputer.com when:7d"
    # Mahalliy yangilik saytlari (kiber filtri) va Markaziy Osiyo Google News so'rovlari o'zgarmagan
    assert rows["Kun.uz (UZ)"].scope == "regional" and rows["Kun.uz (UZ)"].cyber_filter
    assert rows["Google News (EN)"].scope == "regional" and "Uzbekistan" in rows["Google News (EN)"].config["query"]
    global_rss = [s for s in rows.values() if s.kind == "rss" and s.scope == "global"]
    assert all("Global (0014)" in s.notes and not s.region_filter for s in global_rss)
    # 25 ta yoqilgan xalqaro kiber-sayt + o'chiq "Have I Been Pwned" RSS (0007 da API bilan almashtirilgan)
    assert len([s for s in global_rss if s.enabled]) == 25 and len(global_rss) == 26


async def test_global_source_item_about_central_asia_is_regional(db):
    s = Source(name="Global feed", kind="rss", config={"url": "https://feed.example/g"}, scope="global")
    db.add(s)
    await db.commit()
    now = datetime.now(UTC)
    items = [
        RawItem(title="Hackers breach Kazakhstan telecom operator", url="https://feed.example/1", published=now),
        RawItem(title="Ransomware gang hits US hospital", url="https://feed.example/2", published=now),
        RawItem(title="Uzbekistan domain in breach list", url="https://feed.example/3", published=now,
                scope="global"),  # ulagich aniq bergan scope o'zgarmaydi
    ]
    await pipeline.store_items(db, s, items, now, baseline=False)
    got = {e.url[-1]: e for e in (await db.scalars(select(EventRecord))).all()}
    assert got["1"].scope == "regional" and got["1"].matched_keywords
    assert got["2"].scope == "global" and got["3"].scope == "global"


async def test_first_run_after_switch_is_baseline_without_alerts(db, monkeypatch, client, analyst_headers):
    s = await db.scalar(select(Source).where(Source.name == "The Hacker News"))
    s.enabled = True
    await db.commit()
    feed = rss([("Massive data breach at global retailer", "https://thn.example/a", ago(hours=3)),
                ("Ransomware hits Kyrgyzstan bank", "https://thn.example/b", ago(hours=2))])
    use_transport(monkeypatch, lambda req: httpx.Response(200, content=feed, headers={"content-type": "application/rss+xml"}))
    r = await scheduler.run_source(s.id)
    assert r.ok and r.new == 2
    ev = {e.url: e for e in (await db.scalars(select(EventRecord).where(EventRecord.source_id == s.id))).all()}
    assert ev["https://thn.example/a"].scope == "global" and ev["https://thn.example/b"].scope == "regional"
    assert all(e.is_baseline and e.notified for e in ev.values())  # 🔔 oqimi yo'q
    n = (await client.get("/api/notifications", headers=analyst_headers)).json()
    assert n["unread"] == 0
