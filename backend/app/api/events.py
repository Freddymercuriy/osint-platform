from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.config import settings
from app.models import EventRecord, Source
from app.schemas import EventItemOut, EventsResponse
from app.services.events import scheduler

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventsResponse)
async def list_events(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(60, ge=1, le=500),
    offset: int = Query(0, ge=0),
    q: str | None = Query(None, description="Sarlavha/matn bo'yicha filtr"),
    category: str | None = Query(None, description="news | ransomware | telegram | tg_group | leak"),
) -> EventsResponse:
    """Fon yig'uvchi bazaga yozgan hodisalar (tez — tashqi so'rov yo'q)."""
    stmt = select(EventRecord)
    count_stmt = select(func.count(EventRecord.id))
    filters = []
    if category:
        filters.append(EventRecord.category == category)
    if q:
        like = f"%{q}%"
        filters.append(or_(EventRecord.title.ilike(like), EventRecord.summary.ilike(like)))
    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    order = func.coalesce(EventRecord.published, EventRecord.first_seen).desc()
    rows = (await db.scalars(stmt.order_by(order).offset(offset).limit(limit))).all()
    total = await db.scalar(count_stmt) or 0
    return EventsResponse(count=total, items=[EventItemOut.model_validate(r) for r in rows])


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
    rows = (await db.execute(
        select(EventRecord.category, func.count(EventRecord.id)).group_by(EventRecord.category)
    )).all()
    by_cat = {c: n for c, n in rows}
    last_check, last_error = (await db.execute(
        select(func.max(Source.last_check_at),
               select(Source.last_error).where(Source.enabled, Source.status == "down")
               .order_by(Source.last_check_at.desc()).limit(1).scalar_subquery())
    )).one()
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
        notify_categories=settings.notify_categories_list,
        notified_total=0,
        since=settings.events_since_dt,
        retention_days=max(0, settings.events_retention_days),
        retention_keep=settings.events_retention_keep_list,
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
