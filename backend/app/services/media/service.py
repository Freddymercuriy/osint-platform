"""Hodisa rasmi: tayyor bo'lsa — kesh; bo'lmasa maqola rasmi → illyustratsiya → zaxira. Rasmsiz hodisa bo'lmaydi.

- `ensure_image(db, ev, fetch=...)` — hodisaning rasmi (fayllar + `event_images` qatori). `fetch=True` — maqola
  rasmi tarmoqdan qidiriladi (fon ishchisi); `False` — faqat mahalliy illyustratsiya (API so'rovi, kanal posti kutib
  bo'lgach): tarmoq kutilmaydi, ishchi keyinroq maqola rasmini topsa almashtiradi.
- Saytning umumiy rasmi (bir nechta hodisada bir xil og:image — odatda logotip) ishlatilmaydi; avval shu rasmni olgan
  hodisalar ham illyustratsiyaga o'tkaziladi.
- `process_pending` — fon ishchisi: rasmi yo'q yoki maqola rasmi hali qidirilmagan hodisalar, eng yangisidan.
- `purge_orphans` — o'chirilgan hodisalarning fayllari (housekeeping).
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventImage, EventRecord, Source
from app.services.connectors.http import HttpFetcher
from app.services.media import art, source, store
from app.services.media.rubric import motif_of, rubric_of

log = logging.getLogger("osint.media")

BATCH = 12
TICK_BUDGET_SECONDS = 90.0


@dataclass
class MediaStats:
    done: int = 0
    source: int = 0
    generated: int = 0
    errors: int = 0
    ids: list[int] = field(default_factory=list)


_http: HttpFetcher | None = None


def http() -> HttpFetcher:
    global _http
    if _http is None:
        _http = HttpFetcher.create()  # SSRF himoyasi yoqiq, xostlar bo'yicha pauza (xushmuomalalik)
    return _http


async def aclose() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


def spec_for(ev: EventRecord) -> art.ArtSpec:
    rubric = rubric_of(ev.category, ev.title, ev.summary or "")
    return art.ArtSpec(seed=int(ev.id) * 7919 + 17, rubric=rubric,
                       motif=motif_of(ev.category, rubric, ev.title, ev.summary or ""),
                       countries=tuple(c.upper() for c in (ev.countries or [])))


def _draw(spec: art.ArtSpec) -> tuple[bytes, bytes, str]:
    try:
        return (*store.encode(art.render(spec)), "generated")
    except Exception:  # chizishdagi har qanday xato — zaxira rasm (post rasmsiz qolmasin)
        log.exception("Illyustratsiya chizilmadi (rubrika %s, motiv %s) — zaxira rasm", spec.rubric, spec.motif)
        return (*store.encode(art.render_fallback(spec.rubric)), "fallback")


async def _save(db: AsyncSession, ev: EventRecord, *, kind: str, large: bytes, small: bytes, spec: art.ArtSpec,
                checked: bool, error: str | None, source_url: str | None = None) -> EventImage:
    version = await asyncio.to_thread(store.write, ev.id, large, small)
    values = {
        "event_id": ev.id, "kind": kind, "version": version, "rubric": spec.rubric,
        "motif": None if kind == "source" else spec.motif,
        "source_url": source_url, "source_hash": source.url_hash(source_url) if source_url else None,
        "source_checked": checked, "width": store.LARGE[0], "height": store.LARGE[1], "bytes": len(large),
        "error": (error or None) and error[:300],
    }
    update = {k: v for k, v in values.items() if k != "event_id"}
    await db.execute(insert(EventImage).values(**values)
                     .on_conflict_do_update(index_elements=["event_id"], set_={**update, "updated_at": datetime.now(UTC)}))
    await db.flush()
    row = await db.get(EventImage, ev.id, populate_existing=True)
    assert row is not None
    return row


async def _reliability(db: AsyncSession, ev: EventRecord) -> str:
    if not ev.source_id:
        return "media"
    src = await db.get(Source, ev.source_id)
    return (getattr(src, "reliability", None) or "media") if src else "media"


async def _demote_generic(db: AsyncSession, url_hash: str, keep_out: int) -> None:
    """Shu og:image boshqa hodisada ham bor — saytning umumiy rasmi: ular illyustratsiyaga o'tadi."""
    others = (await db.scalars(select(EventImage).where(EventImage.source_hash == url_hash,
                                                        EventImage.event_id != keep_out))).all()
    for row in others:
        ev = await db.get(EventRecord, row.event_id)
        if ev is None:
            continue
        spec = spec_for(ev)
        large, small, kind = await asyncio.to_thread(_draw, spec)
        await _save(db, ev, kind=kind, large=large, small=small, spec=spec, checked=True, error="generic_site_image")


async def ensure_image(db: AsyncSession, ev: EventRecord, *, fetch: bool = False) -> EventImage:
    """Hodisaning tayyor rasmi (qator + fayllar). Hech qachon rasmsiz qaytmaydi."""
    row = await db.get(EventImage, ev.id, populate_existing=True)
    files = row is not None and await asyncio.to_thread(store.exists, ev.id)
    if files and (row.source_checked or not fetch):
        return row
    spec = spec_for(ev)
    reason = source.ineligible(category=ev.category, channel=ev.channel, reliability=await _reliability(db, ev),
                               url=ev.url)
    if fetch and reason is None:
        hinted = (ev.extra or {}).get("image")
        hinted = hinted if isinstance(hinted, str) else None
        try:
            img, url = await source.find(http(), ev.url, hinted)
        except source.SourceImageError as exc:
            reason = str(exc)
        else:
            h = source.url_hash(url)
            used = await db.scalar(select(exists().where(EventImage.source_hash == h, EventImage.event_id != ev.id)))
            if used:
                await _demote_generic(db, h, ev.id)
                reason = "generic_site_image"
            else:
                large, small = await asyncio.to_thread(store.encode, img)
                return await _save(db, ev, kind="source", large=large, small=small, spec=spec, checked=True,
                                   error=None, source_url=url)
    checked = fetch or reason is not None  # qidirib bo'lmaydigan hodisa — qayta urinilmaydi
    if files and row is not None:  # illyustratsiya bor — faqat holat yangilanadi
        row.source_checked, row.error = row.source_checked or checked, (reason or None) and reason[:300]
        await db.flush()
        return row
    large, small, kind = await asyncio.to_thread(_draw, spec)
    return await _save(db, ev, kind=kind, large=large, small=small, spec=spec, checked=checked, error=reason)


async def process_pending(db: AsyncSession, *, limit: int = BATCH, budget: float = TICK_BUDGET_SECONDS,
                          clock=time.monotonic) -> MediaStats:
    """Fon ishchisi: rasmi yo'q yoki maqola rasmi qidirilmagan hodisalar (eng yangisidan), vaqt cheklovi bilan."""
    stats = MediaStats()
    started = clock()
    no_row = ~exists().where(EventImage.event_id == EventRecord.id)
    unchecked = exists().where(EventImage.event_id == EventRecord.id, EventImage.source_checked.is_(False))
    ids = (await db.scalars(
        select(EventRecord.id).where(or_(no_row, unchecked))
        .order_by(EventRecord.first_seen.desc(), EventRecord.id.desc()).limit(limit)
    )).all()
    await db.commit()
    for event_id in ids:
        if clock() - started > budget:
            break
        ev = await db.get(EventRecord, event_id)
        if ev is None:
            continue
        try:
            row = await ensure_image(db, ev, fetch=True)
            await db.commit()
        except Exception:
            await db.rollback()
            stats.errors += 1
            log.exception("Hodisa %s rasmi tayyorlanmadi", event_id)
            continue
        stats.done += 1
        stats.ids.append(event_id)
        if row.kind == "source":
            stats.source += 1
        else:
            stats.generated += 1
    return stats


async def invalidate(db: AsyncSession, event_id: int) -> None:
    """Kategoriya o'zgardi — illyustratsiya qayta chiziladi (maqolaning o'z rasmi qoladi)."""
    row = await db.get(EventImage, event_id)
    if row is not None and row.kind != "source":
        await db.delete(row)
        await asyncio.to_thread(store.remove, event_id)


async def purge_orphans(db: AsyncSession) -> int:
    """Hodisasi o'chirilgan rasm fayllari."""
    on_disk = await asyncio.to_thread(store.stored_ids)
    if not on_disk:
        return 0
    alive = set((await db.scalars(select(EventRecord.id).where(EventRecord.id.in_(list(on_disk))))).all())
    gone = on_disk - alive
    for event_id in gone:
        await asyncio.to_thread(store.remove, event_id)
    return len(gone)
