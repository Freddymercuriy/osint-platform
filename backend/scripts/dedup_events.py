"""Bazadagi takror yangiliklarni topadi (va `--apply` bilan o'chiradi).

Yig'uvchi takrorlarni faqat YOZISH paytida kesadi; qoida o'zgargach bazada qolgan eski takrorlarni
shu skript tozalaydi. Tartib yig'uvchidagi bilan bir xil: to'g'ridan-to'g'ri manba Google News
nusxasidan, eski sana yangisidan ustun.

    docker-compose exec backend python scripts/dedup_events.py           # faqat ko'rsatadi
    docker-compose exec backend python scripts/dedup_events.py --apply   # o'chiradi
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models import EventRecord  # noqa: E402
from app.services.events.aggregator import GOOGLE_NEWS_TAG  # noqa: E402
from app.services.events.collector import DEDUP_CATEGORIES, DEDUP_WINDOW  # noqa: E402
from app.services.events.dedup import signature, same_story  # noqa: E402


def _when(r: EventRecord) -> datetime:
    w = r.published or r.first_seen
    return w if w.tzinfo else w.replace(tzinfo=UTC)


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = list((await db.scalars(
            select(EventRecord).where(EventRecord.category.in_(DEDUP_CATEGORIES))
        )).all())
        rows.sort(key=lambda r: (GOOGLE_NEWS_TAG in r.source, _when(r)))

        kept: list[tuple[EventRecord, object, list[EventRecord]]] = []
        for r in rows:
            sig, when = signature(r.title), _when(r)
            for keeper, ksig, dupes in kept:
                if abs(when - _when(keeper)) <= DEDUP_WINDOW and same_story(sig, ksig):
                    dupes.append(r)
                    break
            else:
                kept.append((r, sig, []))

        drop_ids: list[int] = []
        for keeper, _sig, dupes in kept:
            if not dupes:
                continue
            print(f"\n✔ [{keeper.id}] {keeper.source}: {keeper.title}")
            for d in dupes:
                print(f"   ✗ [{d.id}] {d.source}: {d.title}")
                drop_ids.append(d.id)

        print(f"\nYangiliklar: {len(rows)}, takror: {len(drop_ids)}, qoladi: {len(rows) - len(drop_ids)}")
        if apply and drop_ids:
            await db.execute(delete(EventRecord).where(EventRecord.id.in_(drop_ids)))
            await db.commit()
            print(f"O'chirildi: {len(drop_ids)}")
        elif drop_ids:
            print("Hech narsa o'chirilmadi (o'chirish uchun: --apply)")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv[1:]))
