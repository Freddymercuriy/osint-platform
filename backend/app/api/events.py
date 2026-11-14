from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.core.errors import api_error
from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.config import settings
from app.models import Category, EventRecord, EventTranslation, Source
from app.schemas import EventItemOut, EventsResponse
from app.services.events import scheduler
from app.services.events.categories import effective_severity

router = APIRouter(prefix="/api/events", tags=["events"])

# v1 frontend tablari: endi bular kategoriya emas, kanal
LEGACY_CHANNEL = {"news": "news", "telegram": "telegram_channel", "tg_group": "telegram_group"}
TASHKENT = timedelta(hours=5)


def _csv(values: list[str] | None) -> list[str]:
    """`?x=a,b&x=c` → [a, b, c]"""
    out: list[str] = []
    for v in values or []:
        out += [p.strip() for p in v.split(",") if p.strip()]
    return out


def like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _day_bound(d: date, end: bool) -> datetime:
    """Sana — Toshkent vaqti bo'yicha kun boshi / oxiri (UTC ga o'tkazilgan)."""
    base = datetime.combine(d, time.min).replace(tzinfo=UTC) - TASHKENT
    return base + timedelta(days=1) if end else base


def event_filters(
    *,
    categories: list[str],
    severity: list[str],
    countries: list[str],
    channel: list[str],
    sources: list[str],
    scope: str | None,
    lang: list[str],
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> list:
    """Barcha filtrlar birlashadi (AND), har biri ichida — YOKI."""
    f = []
    cats = [c for c in categories if c not in LEGACY_CHANNEL]
    legacy = [LEGACY_CHANNEL[c] for c in categories if c in LEGACY_CHANNEL]
    if cats:
        f.append(EventRecord.category.in_(cats))
    chans = channel + legacy
    if chans:
        f.append(EventRecord.channel.in_(chans))
    if severity:
        f.append(EventRecord.severity.in_(severity))
    if countries:
        f.append(EventRecord.countries.overlap([c.upper()[:2] for c in countries]))
    if sources:
        ids = [int(s) for s in sources if s.isdigit()]
        names = [s for s in sources if not s.isdigit()]
        conds = []
        if ids:
            conds.append(EventRecord.source_id.in_(ids))
        if names:
            conds.append(EventRecord.source.in_(names))
        f.append(or_(*conds))
    # Standart ko'rinish — mintaqaviy; global (KEV, NVD ...) faqat so'ralganda
    if scope in (None, "", "regional"):
        f.append(EventRecord.scope == "regional")
    elif scope == "global":
        f.append(EventRecord.scope == "global")
    if lang:
        f.append(EventRecord.lang.in_(lang))
    when = func.coalesce(EventRecord.published, EventRecord.first_seen)
    if date_from:
        f.append(when >= _day_bound(date_from, end=False))
    if date_to:
        f.append(when < _day_bound(date_to, end=True))
    if q and q.strip():
        like = f"%{like_escape(q.strip())}%"
        in_translations = select(EventTranslation.id).where(
            EventTranslation.event_id == EventRecord.id,
            or_(EventTranslation.title.ilike(like, escape="\\"), EventTranslation.summary.ilike(like, escape="\\")),
        ).exists()
        f.append(or_(EventRecord.title.ilike(like, escape="\\"), EventRecord.summary.ilike(like, escape="\\"),
                     EventRecord.source.ilike(like, escape="\\"), EventRecord.actor.ilike(like, escape="\\"),
                     in_translations))
    return f


@router.get("", response_model=EventsResponse)
async def list_events(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, max_length=200, description="Sarlavha / matn / manba / guruh bo'yicha qidiruv"),
    category: list[str] | None = Query(None, description="Kategoriya slug'lari (vergul yoki takror). v1: news|telegram|tg_group — kanal"),
    severity: list[str] | None = Query(None),
    country: list[str] | None = Query(None, description="UZ, KZ, KG, TJ, TM"),
    channel: list[str] | None = Query(None, description="news | telegram_channel | telegram_group | api"),
    source: list[str] | None = Query(None, description="Manba ID yoki nomi"),
    scope: str | None = Query(None, pattern="^(regional|global|all)$", description="Standart: regional"),
    source_lang: list[str] | None = Query(None, description="Asl til filtri (en, ru, uz, kk ...)"),
    date_from: date | None = Query(None, description="YYYY-MM-DD (Toshkent vaqti)"),
    date_to: date | None = Query(None, description="YYYY-MM-DD, shu kun ham kiradi"),
    lang: str | None = Query(None, pattern="^(en|ru|uz)$", description="Ko'rsatish tili: sarlavha/matn shu tilda"),
) -> EventsResponse:
    """Bazadagi hodisalar; barcha filtrlar birlashadi. `lang` — ko'rsatish tili (asl matn ham qaytadi)."""
    filters = event_filters(
        categories=_csv(category), severity=_csv(severity), countries=_csv(country), channel=_csv(channel),
        sources=_csv(source), scope=scope, lang=_csv(source_lang), date_from=date_from, date_to=date_to, q=q,
    )
    order = func.coalesce(EventRecord.published, EventRecord.first_seen).desc()
    rows = (await db.scalars(
        select(EventRecord).where(*filters).order_by(order, EventRecord.id.desc()).offset(offset).limit(limit)
    )).all()
    total = await db.scalar(select(func.count(EventRecord.id)).where(*filters)) or 0
    return EventsResponse(count=total, items=await localize(db, rows, lang))


async def localize(db, rows, lang: str | None) -> list[EventItemOut]:
    """Har hodisa: so'ralgan til → en → asl matn (sarlavha va matn alohida tanlanadi)."""
    items = [EventItemOut.model_validate(r) for r in rows]
    for it, r in zip(items, rows, strict=True):
        it.source_lang = r.lang
        it.original_title, it.original_summary = r.title, r.summary
        it.display_lang = r.lang
    if not lang or not rows:
        return items
    trs = (await db.scalars(
        select(EventTranslation).where(EventTranslation.event_id.in_([r.id for r in rows]),
                                       EventTranslation.lang.in_({lang, "en"}))
    )).all()
    by = {(t.event_id, t.lang): t for t in trs}
    for it, r in zip(items, rows, strict=True):
        want = by.get((r.id, lang))
        it.translation_status = want.status if want else None
        for cand in (want, by.get((r.id, "en"))):
            if cand is not None and cand.status == "done" and cand.title:
                it.title = cand.title
                it.summary = cand.summary if cand.summary is not None else r.summary
                it.display_lang = cand.lang
                break
        it.translated = it.display_lang != r.lang
    return items


class EventUpdate(BaseModel):
    category: str


@router.patch("/{event_id}", response_model=EventItemOut)
async def update_event(event_id: int, data: EventUpdate, _: AdminUser, db: DbSession) -> EventRecord:
    """Kategoriyani qo'lda o'zgartirish (`category_locked` — qayta tasniflash buni o'zgartirmaydi)."""
    ev = await db.get(EventRecord, event_id)
    if ev is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "event_not_found")
    cat = await db.scalar(select(Category).where(Category.slug == data.category))
    if cat is None:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "category_slug_not_found", slug=data.category)
    ev.category, ev.category_id, ev.category_locked = cat.slug, cat.id, True
    ev.severity = effective_severity(cat.severity, (ev.extra or {}).get("severity_floor"))
    await db.commit()
    await db.refresh(ev)
    return ev


class CollectorStatus(BaseModel):
    enabled: bool
    running: bool
    poll_seconds: int
    last_run: datetime | None
    last_duration: float | None
    last_new: int
    last_error: str | None
    runs: int
    total_events: int
    by_category: dict[str, int]
    notify_telegram: bool
    notify_categories: list[str]
    notified_total: int
    since: datetime | None  # lenta boshlanish sanasi (undan oldingi hodisalar saqlanmaydi)
    retention_days: int  # 0 = eski hodisalar o'chirilmaydi
    retention_keep: list[str]  # muddatidan qat'i nazar saqlanadigan kategoriyalar
    last_purged: int
    purged_total: int


@router.get("/status", response_model=CollectorStatus)
async def collector_status(current_user: CurrentUser, db: DbSession) -> CollectorStatus:
    """Yig'uvchi holati (v1 shakli saqlangan; manbalar bo'yicha batafsil — /api/admin/collector)."""
    by_cat = dict((await db.execute(
        select(EventRecord.category, func.count(EventRecord.id)).group_by(EventRecord.category)
    )).all())
    last_check = await db.scalar(select(func.max(Source.last_check_at)))
    last_error = await db.scalar(
        select(Source.last_error).where(Source.enabled, Source.status == "down")
        .order_by(Source.last_check_at.desc()).limit(1)
    )
    cats = (await db.execute(select(Category.slug, Category.notify, Category.retention_days))).all()
    s = scheduler.state
    return CollectorStatus(
        enabled=settings.events_poll_enabled,
        running=s.running and s.lock_held,
        poll_seconds=int(scheduler.TICK_RANGE[1]),
        last_run=last_check or s.last_run_at,
        last_duration=None,
        last_new=s.last_new,
        last_error=last_error,
        runs=s.runs,
        total_events=sum(by_cat.values()),
        by_category=by_cat,
        notify_telegram=settings.notify_telegram,
        notify_categories=[c.slug for c in cats if c.notify],
        notified_total=0,
        since=settings.events_since_dt,
        retention_days=max(0, settings.events_retention_days),
        retention_keep=[c.slug for c in cats if c.retention_days is None],
        last_purged=0,
        purged_total=0,
    )


@router.post("/refresh")
async def refresh(current_user: AdminUser, db: DbSession) -> dict[str, int]:
    """Hozir yig'ish: yoqilgan, backoff'da bo'lmagan va oxirgi tekshiruvi intervalining yarmidan eski manbalar.

    Rate limit'i qattiq manbalar (Google News, ransomware.live) shu qoida bilan ortiqcha so'ralmaydi.
    """
    now = datetime.now(UTC)
    rows = (await db.scalars(select(Source).where(Source.enabled))).all()
    due = [
        s.id for s in rows
        if s.consecutive_failures == 0
        and (s.last_check_at is None or (now - s.last_check_at).total_seconds() >= max(60, s.interval_seconds / 2))
    ]
    results = await scheduler.run_many(due, manual=True, timeout=90)
    return {"new": sum(r.new for r in results), "sources": len(due), "finished": len(results)}
