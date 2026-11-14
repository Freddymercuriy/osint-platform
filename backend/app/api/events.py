from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models import EventRecord
from app.schemas import EventItemOut, EventsResponse
from app.services.events import collector

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
    retention_days: int  # 0 = eski hodisalar o'chirilmaydi
    retention_keep: list[str]  # muddatidan qat'i nazar saqlanadigan kategoriyalar
    last_purged: int
    purged_total: int


@router.get("/status", response_model=CollectorStatus)
async def collector_status(current_user: CurrentUser, db: DbSession) -> CollectorStatus:
    rows = (await db.execute(
        select(EventRecord.category, func.count(EventRecord.id)).group_by(EventRecord.category)
    )).all()
    by_cat = {c: n for c, n in rows}
    s = collector.state
    return CollectorStatus(
        enabled=settings.events_poll_enabled,
        running=s.running,
        poll_seconds=settings.events_poll_seconds,
        last_run=s.last_run,
        last_duration=s.last_duration,
        last_new=s.last_new,
        last_error=s.last_error,
        runs=s.runs,
        total_events=sum(by_cat.values()),
        by_category=by_cat,
        notify_telegram=settings.notify_telegram,
        notify_categories=settings.notify_categories_list,
        notified_total=s.notified_total,
        retention_days=max(0, settings.events_retention_days),
        retention_keep=settings.events_retention_keep_list,
        last_purged=s.last_purged,
        purged_total=s.purged_total,
    )


@router.post("/refresh")
async def refresh(current_user: CurrentUser) -> dict[str, int]:
    """Hozir yig'ish (navbatdagi fon tsiklini kutmasdan)."""
    new = await collector.run_once()
    return {"new": new}
