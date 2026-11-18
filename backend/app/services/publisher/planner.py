"""Rejalashtiruvchi: yangi hodisalar → kanal postlari (outbox, `channel_posts`, tur `alert`).

Har yoqilgan (pauzada emas) kanal uchun nomzodlar:
- baseline emas; kanal yoqilganidan (`enabled_at`) keyin va oxirgi 24 soatda yig'ilgan (yoqish eski hodisalar bilan
  to'ldirmaydi);
- band `instant_min_band` dan past emas (bandi hali hisoblanmagan — `low`);
- davlatlar (bo'sh — mintaqaviy hammasi) yoki `include_global` bo'lsa global; kategoriyalar (bo'sh — hammasi).

Har hodisa bir marta: `dedup_key = alert:<event_id>` (`(destination_id, dedup_key)` noyob — restart / ikki tick zararsiz).
Til: kanal tilidagi tarjima (`event_translations.status = done`) kutiladi. `require_translation` — tayyor bo'lmaguncha
kutadi (6 soatdan keyin `skipped / translation_missing`), aks holda `PUBLISHER_TRANSLATION_WAIT_MINUTES` dan keyin asl
matn izoh bilan. Rejim: `dry_run` — post to'liq tayyorlanib saqlanadi, Telegram'ga chiqmaydi (`skipped / dry_run`);
`review` — `awaiting_approval`; `auto` — `queued`, lekin yagona manbasi yashirin kanal bo'lsa `awaiting_approval`.
Sokin soatlar (Toshkent): `all_silent` — ovozsiz; `uz_sound` — faqat O'zbekiston kritik ovozli; `hold` — tonggacha.
Kunlik chegara (`max_instant_per_day`) dan oshgani — `skipped / daily_cap`.
Bitta voqea — bitta post: shu kanalga oxirgi 48 soatda chiqqan voqeani boshqa nashr yozgan bo'lsa (`stories.py`,
kanal tilidagi matn bo'yicha) — `skipped / duplicate`, `meta.duplicate_of_post`.
Rasm (`PUBLISHER_PHOTOS`): har post hodisa rasmi bilan (`media.service`) — fon ishchisi maqola rasmini qidirib
bo'lguncha `PUBLISHER_IMAGE_WAIT_MINUTES` kutiladi, keyin illyustratsiya chiziladi; rasmsiz post chiqmaydi. Izohga
(1024 belgi) sig'magan bo'limlar — `followup` posti (rasmli postga javob, ovozsiz).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Category, ChannelDestination, ChannelPost, EventRecord, EventTranslation, Source
from app.models.publisher import BANDS
from app.models import EventImage
from app.services.media import service as media
from app.services.media import store as media_store
from app.services.media.rubric import rubric_of
from app.services.publisher import stories
from app.services.publisher.outbox import insert_post
from app.services.publisher.priority import band_at_least, record_count
from app.services.publisher.render import EventView, base_lang, cves_in, cvss_in, render_event

log = logging.getLogger("osint.publisher")

WINDOW = timedelta(hours=24)
EXPIRE = timedelta(hours=6)  # shundan keyin yuborilmagan tezkor xabar eskirgan
BATCH = 60  # bitta kanal uchun bir tick'da ko'rib chiqiladigan hodisalar
COUNTED = ("awaiting_approval", "queued", "sending", "sent", "unknown")  # kunlik chegaraga kiradi


@dataclass
class PlanStats:
    created: int = 0
    waiting: int = 0
    by_status: dict[str, int] = field(default_factory=dict)


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def in_quiet(local: time, start: time, end: time) -> bool:
    if start == end:
        return False
    return (start <= local or local < end) if start > end else (start <= local < end)


def quiet_end_after(now: datetime, start: time, end: time) -> datetime:
    """Joriy sokin oraliq tugaydigan vaqt (UTC)."""
    local = now.astimezone(_tz())
    day = local.date()
    if start > end and local.time() >= start:  # kechki qism — tugashi ertaga
        day = day + timedelta(days=1)
    return datetime.combine(day, end, tzinfo=_tz()).astimezone(UTC)


def _country_filter(d: ChannelDestination):
    regional = EventRecord.countries.overlap(list(d.countries)) if d.countries else (EventRecord.scope != "global")
    return or_(regional, EventRecord.scope == "global") if d.include_global else regional


def _band_filter(d: ChannelDestination):
    allowed = [b for b in BANDS if band_at_least(b, d.instant_min_band)]
    cond = EventRecord.priority_band.in_(allowed)
    return or_(cond, EventRecord.priority_band.is_(None)) if "low" in allowed else cond


async def candidates(db: AsyncSession, d: ChannelDestination, now: datetime) -> list[EventRecord]:
    since = max(d.enabled_at or now, now - WINDOW)
    posted = (select(ChannelPost.id)
              .where(ChannelPost.destination_id == d.id,
                     ChannelPost.dedup_key == func.concat(literal("alert:"), EventRecord.id))
              .exists())
    stmt = (select(EventRecord)
            .where(EventRecord.is_baseline.is_(False), EventRecord.first_seen >= since, ~posted,
                   _country_filter(d), _band_filter(d))
            .order_by(EventRecord.first_seen, EventRecord.id)
            .limit(BATCH))
    if d.categories:
        stmt = stmt.where(EventRecord.category.in_(list(d.categories)))
    return list((await db.scalars(stmt)).all())


async def _today_count(db: AsyncSession, d: ChannelDestination, now: datetime) -> int:
    local_midnight = datetime.combine(now.astimezone(_tz()).date(), time(0), tzinfo=_tz())
    return await db.scalar(
        select(func.count(ChannelPost.id)).where(
            ChannelPost.destination_id == d.id, ChannelPost.kind == "alert", ChannelPost.status.in_(COUNTED),
            ChannelPost.created_at >= local_midnight)
    ) or 0


async def plan_destination(db: AsyncSession, d: ChannelDestination, now: datetime, stats: PlanStats) -> None:
    events = await candidates(db, d, now)
    if not events:
        return
    lang = d.lang
    tr_lang = base_lang(lang)
    ids = [e.id for e in events]
    trs = {t.event_id: t for t in (await db.scalars(
        select(EventTranslation).where(EventTranslation.event_id.in_(ids), EventTranslation.lang == tr_lang)
    )).all()}
    cats = {c.slug: c for c in (await db.scalars(
        select(Category).where(Category.slug.in_({e.category for e in events}))
    )).all()}
    rel = dict((await db.execute(
        select(Source.id, Source.reliability).where(Source.id.in_({e.source_id for e in events if e.source_id}))
    )).all())
    used_today = await _today_count(db, d, now)
    photos = settings.publisher_photos and d.mode != "dry_run"
    imgs = {r.event_id: r for r in (await db.scalars(
        select(EventImage).where(EventImage.event_id.in_(ids)).execution_options(populate_existing=True)
    )).all()} if photos else {}
    img_wait = timedelta(minutes=max(0, settings.publisher_image_wait_minutes))
    corpus = await stories.corpus_for(db, tr_lang, now)
    posted = await _posted_stories(db, d, tr_lang, corpus, now)
    wait = timedelta(minutes=max(0, settings.publisher_translation_wait_minutes))
    local_now = now.astimezone(_tz()).time()
    quiet = d.quiet_enabled and in_quiet(local_now, d.quiet_start, d.quiet_end)

    for ev in events:
        age = now - ev.first_seen
        tr = trs.get(ev.id)
        ready = tr is not None and tr.status == "done" and bool(tr.title)
        settled = tr is not None and tr.status in ("failed", "skipped")  # tarjima kelmaydi
        if not ready:
            if d.require_translation:
                if age < EXPIRE and not settled:
                    stats.waiting += 1
                    continue
                await _skip(db, d, ev, "translation_missing", stats)
                continue
            if age < wait and not settled:
                stats.waiting += 1
                continue
        if age > EXPIRE:
            await _skip(db, d, ev, "stale", stats, status="expired")
            continue

        title = tr.title if ready else ev.title
        summary = (tr.summary if ready and tr.summary is not None else ev.summary) or ""
        story = stories.make(corpus, ev, title, summary, tr_lang)
        if (dup := stories.find_duplicate(story, posted, corpus)) is not None:
            await _skip(db, d, ev, "duplicate", stats,
                        meta={"duplicate_of_event": dup.event_id, "duplicate_of_post": dup.post_id})
            story.post_id = dup.post_id
            posted.append(story)  # keyingi nusxa shu matnga o'xshasa ham — bitta voqea (guruh tranzitiv)
            continue

        photo: bytes | None = None
        img_meta: dict | None = None
        if photos:
            row = imgs.get(ev.id)
            if (row is None or not row.source_checked) and age < img_wait:
                stats.waiting += 1  # fon ishchisi maqola rasmini qidiryapti
                continue
            row = await media.ensure_image(db, ev, fetch=False)  # yo'q bo'lsa — illyustratsiya hozir chiziladi
            photo = media_store.read(ev.id, "l")
            img_meta = {"kind": row.kind, "version": row.version, "source_url": row.source_url}

        cat = cats.get(ev.category)
        reliability = rel.get(ev.source_id, "media")
        also = [str(a.get("source")) for a in (ev.also_reported_by or []) if isinstance(a, dict) and a.get("source")]
        view = EventView(
            id=ev.id,
            title=title,
            summary=summary,
            url=ev.url, when=ev.published or ev.first_seen, band=ev.priority_band or "low",
            countries=list(ev.countries or []), scope=ev.scope, category_slug=ev.category,
            category_name=(getattr(cat, f"name_{tr_lang}", "") or getattr(cat, "name_en", "")) if cat else ev.category,
            sector=ev.sector, source=ev.source, reliability=reliability, also_sources=also,
            action=(getattr(cat, f"action_{tr_lang}", "") or "") if cat else "",
            translated=ready,
            rubric=rubric_of(ev.category, ev.title, ev.summary or ""),
            cves=cves_in(ev.title, ev.summary, title, summary),
            cvss=cvss_in(ev.title, ev.summary),
            actor=ev.actor,
            records=record_count(ev.title, ev.summary, ev.extra),
            reasons=list(ev.priority_reasons or []),
        )
        rendered = render_event(view, lang, public_app_url=settings.public_app_url, photo=photo is not None)
        underground_only = reliability == "underground" and not also

        status, skip_reason, silent, scheduled = "queued", None, False, None
        if d.mode == "dry_run":
            status, skip_reason = "skipped", "dry_run"
        elif d.mode == "review" or underground_only:
            status = "awaiting_approval"
        if status != "skipped" and used_today >= d.max_instant_per_day:
            status, skip_reason = "skipped", "daily_cap"
        if quiet:
            if d.quiet_policy == "hold":
                scheduled = quiet_end_after(now, d.quiet_start, d.quiet_end)
            elif d.quiet_policy == "all_silent" or not (view.band == "critical" and "UZ" in view.countries):
                silent = True

        meta = {"translated": ready, "reliability": reliability, "underground_only": underground_only,
                "rubric": view.rubric}
        if img_meta:
            meta["image"] = img_meta
        post = await insert_post(
            db, destination_id=d.id, kind="alert", dedup_key=f"alert:{ev.id}", event_ids=[ev.id], status=status,
            lang=lang, text=rendered.text, buttons=rendered.buttons, silent=silent, priority=ev.priority,
            scheduled_at=scheduled, skip_reason=skip_reason, band_at_send=view.band,
            sources_at_send=1 + len(set(also)), photo=photo if status != "skipped" else None, meta=meta,
        )
        if post is None:
            continue
        if rendered.more and skip_reason != "daily_cap":
            # izohga sig'magan bo'limlar — rasmli postga javob (yuboruvchi asl post chiqqach yuboradi)
            await insert_post(
                db, destination_id=d.id, kind="followup", dedup_key=f"followup:{ev.id}", event_ids=[ev.id],
                status="queued" if status == "awaiting_approval" else status, lang=lang, text=rendered.more,
                buttons=[], silent=True, priority=ev.priority, scheduled_at=scheduled, skip_reason=skip_reason,
                reply_to_post_id=post.id, band_at_send=view.band, meta={"part_of": post.id},
            )
        if status in COUNTED:
            used_today += 1
        if status in COUNTED or skip_reason == "dry_run":
            story.post_id = post.id
            posted.append(story)
        stats.created += 1
        stats.by_status[status] = stats.by_status.get(status, 0) + 1


async def _posted_stories(db: AsyncSession, d: ChannelDestination, tr_lang: str, corpus: stories.Corpus,
                          now: datetime) -> list[stories.Story]:
    """Shu kanalga oxirgi `stories.WINDOW` da chiqqan (navbatdagi, dry-run'da tayyorlangan) hodisalar va ularning
    takror deb tashlangan nusxalari (`post_id` — asl post)."""
    rows = (await db.execute(
        select(ChannelPost.id, ChannelPost.event_ids, ChannelPost.skip_reason, ChannelPost.meta).where(
            ChannelPost.destination_id == d.id, ChannelPost.kind == "alert",
            ChannelPost.created_at >= now - stories.WINDOW - WINDOW,
            or_(ChannelPost.status.in_(COUNTED), ChannelPost.skip_reason.in_(("dry_run", "duplicate"))))
    )).all()
    post_of = {eid: (meta or {}).get("duplicate_of_post") if reason == "duplicate" else pid
               for pid, ids, reason, meta in rows for eid in (ids or [])}
    if not post_of:
        return []
    evs = (await db.scalars(select(EventRecord).where(EventRecord.id.in_(list(post_of))))).all()
    trs = {t.event_id: t for t in (await db.scalars(
        select(EventTranslation).where(EventTranslation.event_id.in_(list(post_of)), EventTranslation.lang == tr_lang,
                                       EventTranslation.status == "done")
    )).all()}
    out = []
    for ev in evs:
        tr = trs.get(ev.id)
        title = tr.title if tr is not None and tr.title else ev.title
        summary = (tr.summary if tr is not None and tr.title and tr.summary is not None else ev.summary) or ""
        out.append(stories.make(corpus, ev, title, summary, tr_lang, post_id=post_of[ev.id]))
    return out


async def _skip(db: AsyncSession, d: ChannelDestination, ev: EventRecord, reason: str, stats: PlanStats,
                status: str = "skipped", meta: dict | None = None) -> None:
    """Hodisa bu kanalga chiqmaydi — sababi bilan yoziladi (qayta ko'rib chiqilmaydi, admin tarixda ko'radi)."""
    post = await insert_post(db, destination_id=d.id, kind="alert", dedup_key=f"alert:{ev.id}", event_ids=[ev.id],
                             status=status, lang=d.lang, skip_reason=reason, band_at_send=ev.priority_band,
                             meta=meta or {})
    if post is not None:
        stats.created += 1
        stats.by_status[status] = stats.by_status.get(status, 0) + 1


async def plan(db: AsyncSession, now: datetime | None = None) -> PlanStats:
    now = now or datetime.now(UTC)
    stats = PlanStats()
    dests = (await db.scalars(
        select(ChannelDestination).where(ChannelDestination.enabled.is_(True), ChannelDestination.paused.is_(False))
        .order_by(ChannelDestination.id)
    )).all()
    for d in dests:
        if d.mode != "dry_run" and d.chat_id is None:
            continue  # manzilsiz kanal faqat dry-run bo'la oladi
        try:
            await plan_destination(db, d, now, stats)
        except Exception:
            log.exception("Kanal %s uchun rejalashtirish xatosi", d.id)
            await db.rollback()
            continue
        await db.commit()
    return stats
