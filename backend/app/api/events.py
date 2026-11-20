import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.core.errors import api_error
from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core import ratelimit
from app.core.config import settings
from app.core.i18n import UZ_CYRL
from app.models import Category, EventImage, EventRecord, EventTranslation, Source
from app.schemas import EventImageOut, EventItemOut, EventsResponse
from app.services.events import export, scheduler
from app.services.events.categories import effective_severity
from app.services.i18n.text import uz_to_cyrillic
from app.services.media import service as media
from app.services.media import store as media_store
from app.services.media.rubric import rubric_of

router = APIRouter(prefix="/api/events", tags=["events"])

# v1 frontend tablari: endi bular kategoriya emas, kanal
LEGACY_CHANNEL = {"news": "news", "telegram": "telegram_channel", "tg_group": "telegram_group"}
TASHKENT = timedelta(hours=5)
# Nisbiy davrlar (hozirdan orqaga, soat aniqligida) — Events va statistika uchun bir xil
RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "90d": timedelta(days=90)}
RangeKey = Literal["24h", "7d", "30d", "90d"]


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
    since: datetime | None = None,
    bands: list[str] | None = None,
) -> list:
    """Barcha filtrlar birlashadi (AND), har biri ichida — YOKI."""
    f = []
    if bands:  # ustuvorlik bandi (low | medium | high | critical)
        f.append(EventRecord.priority_band.in_([b for b in bands if b in ("low", "medium", "high", "critical")]))
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
    if since:
        f.append(when >= since)
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
    band: list[str] | None = Query(None, description="Ustuvorlik bandi: low | medium | high | critical"),
    country: list[str] | None = Query(None, description="UZ, KZ, KG, TJ, TM"),
    channel: list[str] | None = Query(None, description="news | telegram_channel | telegram_group | api | forum"),
    source: list[str] | None = Query(None, description="Manba ID yoki nomi"),
    scope: str | None = Query(None, pattern="^(regional|global|all)$", description="Standart: regional"),
    source_lang: list[str] | None = Query(None, description="Asl til filtri (en, ru, uz, kk ...)"),
    date_from: date | None = Query(None, description="YYYY-MM-DD (Toshkent vaqti)"),
    date_to: date | None = Query(None, description="YYYY-MM-DD, shu kun ham kiradi"),
    range: RangeKey | None = Query(None, description="Nisbiy davr hozirdan orqaga (24h = aynan 24 soat). date_from/date_to berilsa e'tiborsiz"),  # noqa: A002
    lang: str | None = Query(None, pattern="^(en|ru|uz|uz-Cyrl)$", description="Ko'rsatish tili: sarlavha/matn shu tilda"),
) -> EventsResponse:
    """Bazadagi hodisalar; barcha filtrlar birlashadi. `lang` — ko'rsatish tili (asl matn ham qaytadi)."""
    # Statistika bilan bir xil qoida: aniq sanalar bo'lsa — ular, aks holda nisbiy davr
    since = datetime.now(UTC) - RANGES[range] if range and not (date_from or date_to) else None
    filters = event_filters(
        categories=_csv(category), severity=_csv(severity), countries=_csv(country), channel=_csv(channel),
        sources=_csv(source), scope=scope, lang=_csv(source_lang), date_from=date_from, date_to=date_to, q=q,
        since=since, bands=_csv(band),
    )
    order = func.coalesce(EventRecord.published, EventRecord.first_seen).desc()
    rows = (await db.scalars(
        select(EventRecord).where(*filters).order_by(order, EventRecord.id.desc()).offset(offset).limit(limit)
    )).all()
    total = await db.scalar(select(func.count(EventRecord.id)).where(*filters)) or 0
    items = await localize(db, rows, lang)
    await attach_media(db, items, rows)
    return EventsResponse(count=total, items=items)


async def attach_media(db, items: list[EventItemOut], rows) -> None:
    """Rasm havolasi (imzolangan; rasm hali yo'q bo'lsa ham — so'rovda chiziladi) va rubrika."""
    if not rows:
        return
    imgs = {r.event_id: r for r in (await db.scalars(
        select(EventImage).where(EventImage.event_id.in_([r.id for r in rows]))
    )).all()}
    for it, r in zip(items, rows, strict=True):
        img = imgs.get(r.id)
        links = media_store.urls(r.id, img.version if img else None)
        it.image = EventImageOut(url=links["url"], thumb=links["thumb"], kind=img.kind if img else "pending")
        it.rubric = rubric_of(r.category, r.title, r.summary or "")


@router.get("/export", responses={200: {"content": {"text/csv": {}, "application/json": {}}}})
async def export_events(
    current_user: CurrentUser,
    db: DbSession,
    format: Literal["csv", "json"] = Query("csv"),  # noqa: A002
    q: str | None = Query(None, max_length=200),
    category: list[str] | None = Query(None),
    severity: list[str] | None = Query(None),
    band: list[str] | None = Query(None),
    country: list[str] | None = Query(None),
    channel: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    scope: str | None = Query(None, pattern="^(regional|global|all)$"),
    source_lang: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    range: RangeKey | None = Query(None),  # noqa: A002
    lang: str | None = Query(None, pattern="^(en|ru|uz|uz-Cyrl)$"),
) -> Response:
    """Events ro'yxati bilan bir xil filtrlar — eng yangi `export.MAX_ROWS` ta hodisa CSV yoki JSON faylda."""
    ratelimit.check("events-export", str(current_user.id), settings.refresh_rate * 2, settings.refresh_rate_window)
    now = datetime.now(UTC)
    since = now - RANGES[range] if range and not (date_from or date_to) else None
    filters = event_filters(
        categories=_csv(category), severity=_csv(severity), countries=_csv(country), channel=_csv(channel),
        sources=_csv(source), scope=scope, lang=_csv(source_lang), date_from=date_from, date_to=date_to, q=q,
        since=since, bands=_csv(band),
    )
    order = func.coalesce(EventRecord.published, EventRecord.first_seen).desc()
    rows = (await db.scalars(
        select(EventRecord).where(*filters).order_by(order, EventRecord.id.desc()).limit(export.MAX_ROWS)
    )).all()
    total = await db.scalar(select(func.count(EventRecord.id)).where(*filters)) or 0
    items = await localize(db, rows, lang)
    stamp = now.strftime("%Y%m%d-%H%M")
    headers = {"Content-Disposition": f'attachment; filename="osint-events-{stamp}.{format}"',
               "X-Export-Total": str(total), "X-Export-Count": str(len(items))}
    if format == "json":
        applied = {k: v for k, v in {
            "q": q, "category": _csv(category), "severity": _csv(severity), "band": _csv(band),
            "country": _csv(country),
            "channel": _csv(channel), "source": _csv(source), "scope": scope or "regional",
            "source_lang": _csv(source_lang), "date_from": date_from and date_from.isoformat(),
            "date_to": date_to and date_to.isoformat(), "range": range, "lang": lang,
        }.items() if v}
        body = json.dumps(export.to_json(items, filters=applied, total=total, exported_at=now), ensure_ascii=False)
        return Response(body, media_type="application/json", headers=headers)
    return Response(export.to_csv(items), media_type="text/csv; charset=utf-8", headers=headers)


async def localize(db, rows, lang: str | None) -> list[EventItemOut]:
    """Har hodisa: so'ralgan til → en → asl matn (sarlavha va matn alohida tanlanadi).

    `uz-Cyrl` — o'zbekcha (lotin) matn latin.jaybi.uz dvigateli bilan kirillga o'giriladi (`display_lang = "uz-Cyrl"`);
    bu tarjima emas, shuning uchun o'zbekcha asl matn uchun `translated` false qoladi.
    """
    if lang == UZ_CYRL:
        items = await localize(db, rows, "uz")
        for it in items:
            if it.display_lang == "uz":
                it.title = uz_to_cyrillic(it.title or "")
                it.summary = uz_to_cyrillic(it.summary) if it.summary else it.summary
                it.display_lang = UZ_CYRL
        return items
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


class FacetItem(BaseModel):
    value: str
    label: str | None = None
    count: int


class Facets(BaseModel):
    sources: list[FacetItem]
    countries: list[FacetItem]
    source_langs: list[FacetItem]
    channels: list[FacetItem]
    severities: list[FacetItem]
    scopes: list[FacetItem]


@router.get("/facets", response_model=Facets)
async def facets(current_user: CurrentUser, db: DbSession) -> Facets:
    """Filtr paneli uchun mavjud qiymatlar va hodisalar soni (barcha saqlangan hodisalar bo'yicha)."""
    async def grouped(col, limit: int = 200):
        rows = (await db.execute(
            select(col, func.count(EventRecord.id)).group_by(col).order_by(func.count(EventRecord.id).desc()).limit(limit)
        )).all()
        return [FacetItem(value=str(v), count=n) for v, n in rows if v is not None]

    country = func.unnest(EventRecord.countries).label("c")
    sub = select(country).subquery()
    countries = [FacetItem(value=c, count=n) for c, n in (await db.execute(
        select(sub.c.c, func.count()).group_by(sub.c.c).order_by(func.count().desc())
    )).all()]
    src_rows = (await db.execute(
        select(EventRecord.source_id, Source.name, func.count(EventRecord.id))
        .join(Source, Source.id == EventRecord.source_id)
        .group_by(EventRecord.source_id, Source.name).order_by(func.count(EventRecord.id).desc()).limit(300)
    )).all()
    return Facets(
        sources=[FacetItem(value=str(i), label=name, count=n) for i, name, n in src_rows],
        countries=countries,
        source_langs=await grouped(EventRecord.lang),
        channels=await grouped(EventRecord.channel),
        severities=await grouped(EventRecord.severity),
        scopes=await grouped(EventRecord.scope),
    )


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
    changed = ev.category != cat.slug
    ev.category, ev.category_id, ev.category_locked = cat.slug, cat.id, True
    ev.severity = effective_severity(cat.severity, (ev.extra or {}).get("severity_floor"))
    if changed:
        await media.invalidate(db, ev.id)  # illyustratsiya yangi kategoriyaga mos qayta chiziladi
    await db.commit()
    from app.services.publisher.scoring import recompute

    await recompute(db, [ev.id])
    await db.refresh(ev)
    return ev


class FailingSourceOut(BaseModel):
    """Ishlamayotgan (down / blocked) yoqilgan manba — Events sahifasida nomi va sababi bilan."""

    id: int
    name: str
    status: str
    outcome: str | None
    http_status: int | None
    error: str | None
    since: datetime | None
    next_run_at: datetime | None
    retry_after_seconds: int | None


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
    # Yig'uvchining o'zi emas — alohida manbalar (eng yangi tekshirilganlari, ≤ 5) va jami soni
    failing: list[FailingSourceOut] = []
    failing_total: int = 0


@router.get("/status", response_model=CollectorStatus)
async def collector_status(current_user: CurrentUser, db: DbSession) -> CollectorStatus:
    """Yig'uvchi holati (v1 shakli saqlangan; manbalar bo'yicha batafsil — /api/admin/collector)."""
    by_cat = dict((await db.execute(
        select(EventRecord.category, func.count(EventRecord.id)).group_by(EventRecord.category)
    )).all())
    last_check = await db.scalar(select(func.max(Source.last_check_at)))
    failing_q = Source.enabled & Source.status.in_(("down", "blocked"))
    failing_rows = (await db.scalars(
        select(Source).where(failing_q).order_by(Source.last_check_at.desc().nulls_last()).limit(5)
    )).all()
    failing_total = await db.scalar(select(func.count(Source.id)).where(failing_q)) or 0
    failing = [FailingSourceOut(
        id=r.id, name=r.name, status=r.status, outcome=r.last_outcome, http_status=r.last_http_status,
        error=(r.last_error or "")[:300] or None, since=r.down_since, next_run_at=r.next_run_at,
        retry_after_seconds=r.retry_after_seconds,
    ) for r in failing_rows]
    # v1 maydoni: endi manba nomi bilan (eski mijozlar uchun)
    last_error = next((f"{x.name}: {x.error}" for x in failing if x.status == "down" and x.error), None)
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
        failing=failing,
        failing_total=failing_total,
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
    ratelimit.check("refresh", str(current_user.id), settings.refresh_rate, settings.refresh_rate_window)
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
