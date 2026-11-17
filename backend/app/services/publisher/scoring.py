"""Ustuvorlikni bazadagi hodisalarga qo'llash: kontekst (sozlamalar, kuzatuv ro'yxati, manba ishonchliligi) va qayta
hisoblash.

Qachon chaqiriladi:
- yangi hodisa yozilganda va boshqa manba qo'shilganda (`pipeline.store_items`);
- tarjimalar kelganda (`scheduler.translation_tick`) — kuzatuv ro'yxati tarjimadan ham qidiriladi;
- admin kategoriyani o'zgartirganda, qayta tasniflash, kategoriya jiddiyligi o'zgarganda;
- kuzatuv ro'yxati / og'irliklar / manba ishonchliligi o'zgarganda — oxirgi 14 kun;
- housekeeping: `priority is null` hodisalar (migratsiyadan keyin va biror yo'l o'tkazib yuborgan bo'lsa).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventRecord, EventTranslation, PublisherSettings, Source, WatchlistEntry
from app.services.publisher import priority as pr
from app.services.publisher.watchlist import CompiledWatch, compile_watchlist, event_texts, match

log = logging.getLogger("osint.publisher")

RECENT_DAYS = 14
CHUNK = 400


@dataclass
class ScoringContext:
    weights: dict
    bands: dict
    watch: list[CompiledWatch]
    reliability_by_id: dict[int, str]


async def load_settings(db: AsyncSession) -> tuple[dict, dict]:
    row = await db.get(PublisherSettings, 1)
    if row is None:
        return pr.merged_weights(None), pr.merged_bands(None)
    return pr.merged_weights(row.weights), pr.merged_bands(row.bands)


async def load_context(db: AsyncSession, *, weights: dict | None = None, bands: dict | None = None,
                       watch_entries: list | None = None) -> ScoringContext:
    w, b = await load_settings(db)
    if weights is not None:
        w = pr.merged_weights(weights)
    if bands is not None:
        b = pr.merged_bands(bands)
    if watch_entries is None:
        watch_entries = list((await db.scalars(
            select(WatchlistEntry).where(WatchlistEntry.enabled).order_by(WatchlistEntry.id)
        )).all())
    rel = dict((await db.execute(select(Source.id, Source.reliability))).all())
    return ScoringContext(weights=w, bands=b, watch=compile_watchlist(watch_entries), reliability_by_id=rel)


def input_of(ev: EventRecord, ctx: ScoringContext, translations: Iterable[tuple[str | None, str | None]] = (),
             reliability: str | None = None) -> pr.PriorityInput:
    texts = event_texts(ev.title, ev.summary, ev.matched_keywords, ev.extra, translations)
    hits = match(ctx.watch, texts)
    rel = reliability if reliability is not None else ctx.reliability_by_id.get(ev.source_id or -1)
    return pr.PriorityInput(
        severity=ev.severity, countries=list(ev.countries or []), sector=ev.sector, scope=ev.scope,
        reliability=rel, source=ev.source, also_reported_by=list(ev.also_reported_by or []),
        published=ev.published, first_seen=ev.first_seen,
        records=pr.record_count(ev.title, ev.summary, ev.extra),
        watch_hits=[(h.kind, h.name) for h in hits],
    )


def score_event(ev: EventRecord, ctx: ScoringContext,
                translations: Iterable[tuple[str | None, str | None]] = ()) -> pr.Priority:
    return pr.compute(input_of(ev, ctx, translations), ctx.weights, ctx.bands)


async def _translations(db: AsyncSession, ids: list[int]) -> dict[int, list[tuple[str | None, str | None]]]:
    out: dict[int, list[tuple[str | None, str | None]]] = {}
    if not ids:
        return out
    rows = (await db.execute(
        select(EventTranslation.event_id, EventTranslation.title, EventTranslation.summary).where(
            EventTranslation.event_id.in_(ids), EventTranslation.status == "done",
        )
    )).all()
    for eid, t, s in rows:
        out.setdefault(eid, []).append((t, s))
    return out


async def recompute(db: AsyncSession, event_ids: Iterable[int] | None = None, *, since: datetime | None = None,
                    only_missing: bool = False, ctx: ScoringContext | None = None, commit: bool = True) -> int:
    """Berilgan hodisalar (yoki `since` dan keyingilari / bali yo'qlari) uchun ustuvorlikni yangilaydi.

    Qaytaradi: o'zgargan hodisalar soni.
    """
    ctx = ctx or await load_context(db)
    stmt = select(EventRecord)
    if event_ids is not None:
        ids = sorted({int(i) for i in event_ids if i})
        if not ids:
            return 0
        stmt = stmt.where(EventRecord.id.in_(ids))
    if since is not None:
        stmt = stmt.where(EventRecord.first_seen >= since)
    if only_missing:
        stmt = stmt.where(EventRecord.priority.is_(None))
    changed = 0
    last_id = 0
    while True:
        rows = list((await db.scalars(stmt.where(EventRecord.id > last_id).order_by(EventRecord.id).limit(CHUNK))).all())
        if not rows:
            break
        last_id = rows[-1].id
        trs = await _translations(db, [r.id for r in rows])
        for ev in rows:
            p = score_event(ev, ctx, trs.get(ev.id, ()))
            if (ev.priority, ev.priority_band, ev.priority_reasons) != p.as_tuple():
                await db.execute(update(EventRecord).where(EventRecord.id == ev.id).values(
                    priority=p.score, priority_band=p.band, priority_reasons=p.reasons))
                changed += 1
        if len(rows) < CHUNK:
            break
    if commit:
        await db.commit()
    return changed


async def recompute_recent(db: AsyncSession, days: int = RECENT_DAYS, ctx: ScoringContext | None = None) -> int:
    return await recompute(db, since=datetime.now(UTC) - timedelta(days=days), ctx=ctx)


async def recompute_safe(db: AsyncSession, event_ids: Iterable[int]) -> int:
    """Yig'ish / tarjima yo'lida: xato yig'ishni to'xtatmasin (housekeeping keyin to'ldiradi)."""
    try:
        return await recompute(db, event_ids)
    except Exception:  # noqa: BLE001
        log.exception("Ustuvorlikni hisoblash xatosi")
        await db.rollback()
        return 0


async def missing_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count(EventRecord.id)).where(EventRecord.priority.is_(None))) or 0
