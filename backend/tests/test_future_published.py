"""Kelajak sanali yozuv (manba ertangi pubDate bergan) — `published` yig'ish vaqti bilan cheklanadi, asl sana extra'da."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models import EventRecord, Source
from app.services.connectors.base import RawItem
from app.services.events import pipeline


async def test_future_published_is_capped_at_collection_time(db):
    s = Source(name="Future feed", kind="rss", config={"url": "https://feed.example/f"}, scope="global")
    db.add(s)
    await db.commit()
    now = datetime.now(UTC).replace(microsecond=0)
    tomorrow, earlier = now + timedelta(hours=21), now - timedelta(minutes=2)
    items = [
        RawItem(title="Uber says 150,000 impacted by third-party breach", url="https://feed.example/1",
                published=tomorrow, extra={"author": "x"}),
        RawItem(title="Ransomware gang hits US hospital", url="https://feed.example/2", published=earlier),
    ]
    stats = await pipeline.store_items(db, s, items, now, baseline=False)
    assert stats.new == 2
    got = {e.url[-1]: e for e in (await db.scalars(select(EventRecord))).all()}
    assert got["1"].published == now and got["1"].event_time == now
    assert got["1"].extra["published_original"] == tomorrow.isoformat() and got["1"].extra["author"] == "x"
    assert not got["1"].notified  # yangi yozuv sifatida 🔔 beradi (sana endi "hozir")
    assert got["2"].published == earlier and "published_original" not in got["2"].extra
