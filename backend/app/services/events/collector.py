"""Events fon yig'uvchisi.

Har `events_poll_seconds` da barcha manbalarni yig'adi, yangi hodisalarni `events`
jadvaliga yozadi va `notify_categories` dagi yangi hodisalar haqida foydalanuvchining
Telegram "Saved Messages" chatiga xabar yuboradi.

Birinchi ishga tushishda (jadval bo'sh) eski hodisalar uchun ogohlantirish yuborilmaydi —
faqat "monitoring boshlandi" xabari.

Retention: `events_retention_days` dan eski hodisalar har yig'ishdan keyin o'chiriladi
(`events_retention_keep` kategoriyalaridan tashqari). Manbalar eski yozuvlarni qayta-qayta
qaytarishi mumkin, shuning uchun muddati o'tgan element bazaga umuman yozilmaydi — aks holda
u har tsiklda "yangi" bo'lib qayta paydo bo'lardi.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.config import settings
from app.core.db import AsyncSessionLocal
from app.models import EventRecord
from app.services.events.aggregator import EventItem, collect_all

log = logging.getLogger("osint.events")


@dataclass
class CollectorState:
    running: bool = False
    last_run: datetime | None = None
    last_duration: float | None = None
    last_new: int = 0
    last_error: str | None = None
    runs: int = 0
    notified_total: int = 0
    last_purged: int = 0
    purged_total: int = 0
    _task: asyncio.Task | None = field(default=None, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


state = CollectorState()


def _uid(item: EventItem) -> str:
    raw = f"{item.category}|{item.source}|{item.title}|{item.url}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def retention_cutoff(now: datetime | None = None) -> datetime | None:
    """Shu vaqtdan eski hodisalar saqlanmaydi. Retention o'chiq bo'lsa — None."""
    days = settings.events_retention_days
    if days <= 0:
        return None
    return (now or datetime.now(UTC)) - timedelta(days=days)


def is_expired(category: str, when: datetime | None, cutoff: datetime | None) -> bool:
    """Hodisa retention muddatidan o'tganmi (saqlanadigan kategoriyalar hech qachon o'tmaydi)."""
    if cutoff is None or when is None or category in settings.events_retention_keep_list:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return when < cutoff


async def _purge_expired(db, cutoff: datetime | None) -> int:
    if cutoff is None:
        return 0
    stmt = delete(EventRecord).where(
        func.coalesce(EventRecord.published, EventRecord.first_seen) < cutoff
    )
    keep = settings.events_retention_keep_list
    if keep:
        stmt = stmt.where(EventRecord.category.notin_(keep))
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


def _format_alert(records: list[EventRecord]) -> str:
    icons = {"leak": "🟠", "ransomware": "🔴"}
    lines = [f"🚨 OSINT: O'zbekiston bo'yicha {len(records)} ta yangi hodisa\n"]
    for r in records[:10]:
        lines.append(
            f"{icons.get(r.category, '•')} [{r.category}] {r.source}\n"
            f"{r.title[:200]}\n{r.summary[:250]}\n{r.url}\n"
        )
    if len(records) > 10:
        lines.append(f"... va yana {len(records) - 10} ta. Platformada ko'ring.")
    return "\n".join(lines)


async def _send_telegram(text: str) -> bool:
    if not settings.notify_telegram:
        return False
    from app.services import telegram_user as tg

    if not tg.is_configured():
        return False
    try:
        client = await tg.get_client()
        await client.send_message("me", text, link_preview=False)
        return True
    except Exception as exc:  # ogohlantirish yiqilsa ham yig'ish davom etadi
        log.warning("Telegram ogohlantirish yuborilmadi: %s", exc)
        return False


async def run_once() -> int:
    """Bir marta yig'ish. Yangi yozuvlar sonini qaytaradi."""
    async with state._lock:  # parallel ishga tushishning oldini olish
        started = datetime.now(UTC)
        try:
            cutoff = retention_cutoff(started)
            items = [
                i for i in await collect_all(force=True)
                if not is_expired(i.category, i.published, cutoff)
            ]
            async with AsyncSessionLocal() as db:
                is_bootstrap = (await db.scalar(select(func.count(EventRecord.id)))) == 0

                uids = {_uid(i): i for i in items}
                existing = set(
                    (await db.scalars(
                        select(EventRecord.uid).where(EventRecord.uid.in_(list(uids)))
                    )).all()
                ) if uids else set()

                new_records: list[EventRecord] = []
                for uid, i in uids.items():
                    if uid in existing:
                        continue
                    rec = EventRecord(
                        uid=uid, source=i.source[:128], category=i.category,
                        title=i.title[:512], url=i.url[:1024], summary=i.summary,
                        lang=i.lang[:8], published=i.published,
                        notified=is_bootstrap,  # birinchi yig'ishda eski narsalar uchun ogohlantirmaymiz
                    )
                    db.add(rec)
                    new_records.append(rec)
                await db.commit()

                if is_bootstrap and new_records:
                    await _send_telegram(
                        f"✅ OSINT monitoring boshlandi. Bazaga {len(new_records)} ta hodisa yozildi. "
                        f"Bundan keyin yangi {', '.join(settings.notify_categories_list)} "
                        f"hodisalari shu yerga keladi."
                    )
                else:
                    to_notify = [
                        r for r in new_records
                        if r.category in settings.notify_categories_list and not r.notified
                    ]
                    if to_notify and await _send_telegram(_format_alert(to_notify)):
                        for r in to_notify:
                            r.notified = True
                        await db.commit()
                        state.notified_total += len(to_notify)

                purged = await _purge_expired(db, cutoff)
                state.last_purged = purged
                state.purged_total += purged
                if purged:
                    log.info("Retention: %d ta eski hodisa o'chirildi (< %s)", purged, cutoff.date())

            state.last_new = len(new_records)
            state.last_error = None
            log.info("Events yig'ildi: %d ta manba-element, %d ta yangi", len(items), len(new_records))
            return len(new_records)
        except Exception as exc:
            state.last_error = f"{type(exc).__name__}: {exc}"
            log.exception("Events yig'ishda xato")
            return 0
        finally:
            state.last_run = started
            state.last_duration = (datetime.now(UTC) - started).total_seconds()
            state.runs += 1


async def _loop() -> None:
    state.running = True
    await asyncio.sleep(5)  # ilova to'liq ishga tushishini kutamiz
    try:
        while True:
            await run_once()
            await asyncio.sleep(settings.events_poll_seconds)
    except asyncio.CancelledError:
        pass
    finally:
        state.running = False


def start() -> None:
    if settings.events_poll_enabled and state._task is None:
        state._task = asyncio.create_task(_loop(), name="events-collector")


async def stop() -> None:
    if state._task:
        state._task.cancel()
        try:
            await state._task
        except asyncio.CancelledError:
            pass
        state._task = None
