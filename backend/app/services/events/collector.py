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

Boshlanish sanasi: `events_since` berilsa, undan oldingi hodisalar kategoriyasidan qat'i nazar
yig'ilmaydi va bazadan o'chiriladi (lenta shu sanadan boshlanadi).
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
from app.services.events.aggregator import GOOGLE_NEWS_TAG, EventItem, collect_all
from app.services.events.dedup import TitleSig, same_story, signature

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


def is_expired(
    category: str,
    when: datetime | None,
    cutoff: datetime | None,
    since: datetime | None = None,
) -> bool:
    """Hodisa saqlanmasligi kerakmi.

    - `since` (boshlanish sanasi) dan oldingi hodisa — har qanday kategoriyada;
    - retention `cutoff` idan eski hodisa — saqlanadigan kategoriyalardan tashqari.
    Sanasi noma'lum hodisa hozir topilgan deb hisoblanadi (o'tmaydi).
    """
    if when is None:
        return False
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    if since is not None and when < since:
        return True
    if cutoff is None or category in settings.events_retention_keep_list:
        return False
    return when < cutoff


async def _purge_expired(db, cutoff: datetime | None, since: datetime | None = None) -> int:
    when = func.coalesce(EventRecord.published, EventRecord.first_seen)
    purged = 0
    if since is not None:
        result = await db.execute(delete(EventRecord).where(when < since))
        purged += result.rowcount or 0
    if cutoff is not None:
        stmt = delete(EventRecord).where(when < cutoff)
        keep = settings.events_retention_keep_list
        if keep:
            stmt = stmt.where(EventRecord.category.notin_(keep))
        result = await db.execute(stmt)
        purged += result.rowcount or 0
    await db.commit()
    return purged


# ---------------------------------------------------------------- takror yangiliklar
# Bitta voqeani o'nlab nashr turlicha sarlavha (va tilda) bosadi, ayniqsa Google News orqali.
# Sarlavha imzolari (`dedup.signature`) solishtiriladi; yaqin sanadagi o'sha voqea yozilmaydi.
DEDUP_CATEGORIES = ("news",)
DEDUP_WINDOW = timedelta(days=3)  # shu oraliqdagi sarlavhalargina solishtiriladi
DEDUP_LOOKBACK = timedelta(days=14)  # bazadan qancha orqaga qarash


def _aware(when: datetime | None, default: datetime) -> datetime:
    if when is None:
        return default
    return when if when.tzinfo else when.replace(tzinfo=UTC)


def drop_similar(
    candidates: list[EventItem],
    known: list[tuple[TitleSig, datetime]],
    now: datetime,
) -> list[EventItem]:
    """`known` (bazadagi yaqin yangiliklar) ga yoki bir-biriga o'xshash yangiliklarni tashlaydi.

    To'g'ridan-to'g'ri manba Google News'dan, eski sana yangisidan ustun.
    `known` ro'yxati qabul qilinganlar bilan to'ldirib boriladi.
    """
    ordered = sorted(
        candidates,
        key=lambda i: (GOOGLE_NEWS_TAG in i.source, _aware(i.published, now)),
    )
    kept: list[EventItem] = []
    for item in ordered:
        if item.category not in DEDUP_CATEGORIES:
            kept.append(item)
            continue
        sig, when = signature(item.title), _aware(item.published, now)
        if any(abs(when - w) <= DEDUP_WINDOW and same_story(sig, s) for s, w in known):
            continue
        known.append((sig, when))
        kept.append(item)
    return kept


def _format_alert(records: list[EventRecord]) -> str:
    icons = {"leak": "🟠", "ransomware": "🔴"}
    lines = [f"🚨 OSINT: Markaziy Osiyo bo'yicha {len(records)} ta yangi hodisa\n"]
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
            since = settings.events_since_dt
            items = [
                i for i in await collect_all(force=True)
                if not is_expired(i.category, i.published, cutoff, since)
            ]
            async with AsyncSessionLocal() as db:
                is_bootstrap = (await db.scalar(select(func.count(EventRecord.id)))) == 0

                uids = {_uid(i): i for i in items}
                existing = set(
                    (await db.scalars(
                        select(EventRecord.uid).where(EventRecord.uid.in_(list(uids)))
                    )).all()
                ) if uids else set()

                # Takror yangiliklar: bazadagi yaqin sarlavhalar va shu to'plam ichida
                fresh = {uid: i for uid, i in uids.items() if uid not in existing}
                known: list[tuple[TitleSig, datetime]] = []
                if any(i.category in DEDUP_CATEGORIES for i in fresh.values()):
                    rows = (await db.execute(
                        select(EventRecord.title, EventRecord.published, EventRecord.first_seen)
                        .where(
                            EventRecord.category.in_(DEDUP_CATEGORIES),
                            EventRecord.first_seen >= started - DEDUP_LOOKBACK,
                        )
                    )).all()
                    known = [(signature(t), _aware(p or f, started)) for t, p, f in rows]
                unique_ids = {id(i) for i in drop_similar(list(fresh.values()), known, started)}

                new_records: list[EventRecord] = []
                for uid, i in fresh.items():
                    if id(i) not in unique_ids:
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

                purged = await _purge_expired(db, cutoff, since)
                state.last_purged = purged
                state.purged_total += purged
                if purged:
                    log.info(
                        "Retention: %d ta eski hodisa o'chirildi (boshlanish: %s, muddat: %s)",
                        purged, since or "-", cutoff or "-",
                    )

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
