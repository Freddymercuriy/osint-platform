from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import EventRecord, SearchJob
from app.schemas import EventItemOut

router = APIRouter(prefix="/api/stats", tags=["stats"])


class DayBucket(BaseModel):
    day: date
    total: int
    by_category: dict[str, int]


class SourceCount(BaseModel):
    source: str
    count: int


class Overview(BaseModel):
    total_events: int
    new_24h: int
    by_category: dict[str, int]
    daily: list[DayBucket]  # eski → yangi, bo'sh kunlar 0 bilan
    top_sources: list[SourceCount]
    critical: list[EventItemOut]  # so'nggi ransomware/leak
    searches_total: int
    searches_by_kind: dict[str, int]


@router.get("/overview", response_model=Overview)
async def overview(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(14, ge=7, le=90),
) -> Overview:
    now = datetime.now(UTC)
    when = func.coalesce(EventRecord.published, EventRecord.first_seen)

    by_cat = dict((await db.execute(
        select(EventRecord.category, func.count(EventRecord.id)).group_by(EventRecord.category)
    )).all())

    new_24h = await db.scalar(
        select(func.count(EventRecord.id)).where(EventRecord.first_seen >= now - timedelta(hours=24))
    ) or 0

    # Kunlik taqsimot (hodisa sanasi bo'yicha, UTC)
    start = (now - timedelta(days=days - 1)).date()
    day_col = func.date(func.timezone("UTC", when))
    rows = (await db.execute(
        select(day_col, EventRecord.category, func.count(EventRecord.id))
        .where(when >= datetime.combine(start, datetime.min.time(), tzinfo=UTC))
        .group_by(day_col, EventRecord.category)
    )).all()
    buckets: dict[date, dict[str, int]] = {start + timedelta(days=i): {} for i in range(days)}
    for d, cat, n in rows:
        if d in buckets:
            buckets[d][cat] = n
    daily = [DayBucket(day=d, total=sum(c.values()), by_category=c) for d, c in buckets.items()]

    top_sources = [
        SourceCount(source=s, count=n)
        for s, n in (await db.execute(
            select(EventRecord.source, func.count(EventRecord.id).label("n"))
            .group_by(EventRecord.source).order_by(func.count(EventRecord.id).desc()).limit(6)
        )).all()
    ]

    critical = (await db.scalars(
        select(EventRecord)
        .where(EventRecord.category.in_(["ransomware", "leak"]))
        .order_by(when.desc()).limit(6)
    )).all()

    by_kind = dict((await db.execute(
        select(SearchJob.kind, func.count(SearchJob.id))
        .where(SearchJob.user_id == current_user.id).group_by(SearchJob.kind)
    )).all())

    return Overview(
        total_events=sum(by_cat.values()),
        new_24h=new_24h,
        by_category=by_cat,
        daily=daily,
        top_sources=top_sources,
        critical=[EventItemOut.model_validate(r) for r in critical],
        searches_total=sum(by_kind.values()),
        searches_by_kind=by_kind,
    )
