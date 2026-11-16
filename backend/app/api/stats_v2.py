"""Statistika (dashboard): filtrlanadigan endpointlar. Har raqam — saqlangan qatorlar ustidan SQL.

Hamma endpoint bir xil filtrlarni qabul qiladi (`/api/events` bilan bir xil nomlar) + davr:
`range` = 24h | 7d | 30d | 90d (standart 7d) yoki `date_from`/`date_to` (Toshkent kuni). Oldingi davr — xuddi shu
uzunlikdagi undan oldingi oraliq (o'zgarish foizi uchun). Vaqt bo'laklari `APP_TIMEZONE` (Asia/Tashkent) bo'yicha.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.api.events import RANGES, _csv, event_filters, localize
from app.core.config import settings
from app.models import EventRecord, Source, SourceRun
from app.schemas import EventItemOut

router = APIRouter(prefix="/api/stats", tags=["stats"])

AUTO_BUCKET = {"24h": "hour", "7d": "day", "30d": "day", "90d": "week"}
Bucket = Literal["hour", "day", "week", "month"]
GroupBy = Literal["category", "country", "source", "channel", "severity"]
BreakdownBy = Literal["category", "country", "source", "channel", "severity", "actor", "sector"]
OTHER = "__other__"
NONE = "__none__"


def tz() -> ZoneInfo:
    return ZoneInfo(settings.app_timezone)


def when_col():
    return func.coalesce(EventRecord.published, EventRecord.first_seen)


def local_when():
    """Hodisa vaqti mahalliy zonada (timestamp without time zone)."""
    return func.timezone(settings.app_timezone, when_col())


@dataclass
class Window:
    start: datetime
    end: datetime
    prev_start: datetime
    prev_end: datetime
    range_key: str
    filters: list

    @property
    def where(self) -> list:
        w = when_col()
        return [*self.filters, w >= self.start, w < self.end]

    @property
    def where_prev(self) -> list:
        w = when_col()
        return [*self.filters, w >= self.prev_start, w < self.prev_end]


def _local_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=tz()).astimezone(UTC)


async def stats_window(
    range: Literal["24h", "7d", "30d", "90d", "custom"] = Query("7d"),  # noqa: A002 - query nomi
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    q: str | None = Query(None, max_length=200),
    category: list[str] | None = Query(None),
    severity: list[str] | None = Query(None),
    country: list[str] | None = Query(None),
    channel: list[str] | None = Query(None),
    source: list[str] | None = Query(None),
    scope: str | None = Query(None, pattern="^(regional|global|all)$"),
    source_lang: list[str] | None = Query(None),
) -> Window:
    now = datetime.now(UTC)
    if date_from or date_to or range == "custom":
        start = _local_midnight(date_from) if date_from else now - RANGES["30d"]
        end = _local_midnight(date_to) + timedelta(days=1) if date_to else now
        key = "custom"
    else:
        start, end, key = now - RANGES[range], now, range
    length = max(end - start, timedelta(hours=1))
    filters = event_filters(
        categories=_csv(category), severity=_csv(severity), countries=_csv(country), channel=_csv(channel),
        sources=_csv(source), scope=scope, lang=_csv(source_lang), date_from=None, date_to=None, q=q,
    )
    return Window(start, end, start - length, start, key, filters)


StatsWindow = Annotated[Window, Depends(stats_window)]


class Period(BaseModel):
    start: datetime
    end: datetime
    range: str


# ---------------------------------------------------------------- KPI
class Kpis(BaseModel):
    period: Period
    total: int
    previous_total: int
    change_pct: float | None
    critical_high: int
    critical_high_previous: int
    by_severity: dict[str, int]
    countries_affected: int
    sources_reporting: int
    multi_source: int  # bir nechta manba xabar qilgan hodisalar
    ransomware: int
    ransomware_previous: int


def _pct(cur: int, prev: int) -> float | None:
    return None if prev == 0 else round((cur - prev) / prev * 100, 1)


@router.get("/kpis", response_model=Kpis)
async def kpis(_: CurrentUser, db: DbSession, w: StatsWindow) -> Kpis:
    async def count(where, *extra):
        return await db.scalar(select(func.count(EventRecord.id)).where(*where, *extra)) or 0

    hi = EventRecord.severity.in_(("critical", "high"))
    rw = EventRecord.category == "ransomware"
    total, prev = await count(w.where), await count(w.where_prev)
    by_sev = dict((await db.execute(
        select(EventRecord.severity, func.count(EventRecord.id)).where(*w.where).group_by(EventRecord.severity)
    )).all())
    sub = select(func.unnest(EventRecord.countries).label("c")).where(*w.where).subquery()
    countries = await db.scalar(select(func.count(func.distinct(sub.c.c)))) or 0
    sources = await db.scalar(select(func.count(func.distinct(EventRecord.source))).where(*w.where)) or 0
    multi = await count(w.where, func.jsonb_array_length(EventRecord.also_reported_by) > 0)
    return Kpis(
        period=Period(start=w.start, end=w.end, range=w.range_key), total=total, previous_total=prev,
        change_pct=_pct(total, prev), critical_high=await count(w.where, hi),
        critical_high_previous=await count(w.where_prev, hi), by_severity=by_sev, countries_affected=countries,
        sources_reporting=sources, multi_source=multi, ransomware=await count(w.where, rw),
        ransomware_previous=await count(w.where_prev, rw),
    )


# ---------------------------------------------------------------- vaqt qatori
def _group_col(group_by: str):
    return {
        "category": EventRecord.category,
        "source": EventRecord.source,
        "channel": EventRecord.channel,
        "severity": EventRecord.severity,
        "actor": EventRecord.actor,
        "sector": EventRecord.sector,
    }[group_by]


def _bucket_starts(start: datetime, end: datetime, bucket: str) -> list[datetime]:
    """Mahalliy zonadagi bo'lak boshlari (naive, Postgres date_trunc natijasi bilan mos)."""
    local_start = start.astimezone(tz()).replace(tzinfo=None)
    local_end = end.astimezone(tz()).replace(tzinfo=None)
    if bucket == "hour":
        cur = local_start.replace(minute=0, second=0, microsecond=0)
        step = lambda d: d + timedelta(hours=1)  # noqa: E731
    elif bucket == "day":
        cur = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
        step = lambda d: d + timedelta(days=1)  # noqa: E731
    elif bucket == "week":
        cur = (local_start - timedelta(days=local_start.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        step = lambda d: d + timedelta(days=7)  # noqa: E731
    else:
        cur = local_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        step = lambda d: (d.replace(day=28) + timedelta(days=4)).replace(day=1)  # noqa: E731
    out = []
    while cur < local_end and len(out) < 2000:
        out.append(cur)
        cur = step(cur)
    return out


class Series(BaseModel):
    key: str  # kategoriya slug'i, davlat kodi, manba nomi ...; "__other__" — qolganlari, "__none__" — qiymatsiz
    total: int
    values: list[int]


class TimeSeries(BaseModel):
    period: Period
    bucket: str
    group_by: str | None
    buckets: list[str]  # mahalliy vaqt, ISO (zonasiz) — "2026-11-14T00:00:00"
    totals: list[int]
    series: list[Series]


@router.get("/timeseries", response_model=TimeSeries)
async def timeseries(
    _: CurrentUser, db: DbSession, w: StatsWindow,
    bucket: Bucket | None = None,
    group_by: GroupBy | None = None,
    top: int = Query(7, ge=1, le=50, description="Alohida seriyalar soni (qolgani 'Other'). Grafikda ≤ 8 rang — "
                     "frontend barqaror to'plamga (≤ 7 + Other) qayta yig'adi"),
) -> TimeSeries:
    b = bucket or AUTO_BUCKET.get(w.range_key, "day")
    starts = _bucket_starts(w.start, w.end, b)
    index = {d: i for i, d in enumerate(starts)}
    bcol = func.date_trunc(b, local_when()).label("b")
    if group_by == "country":
        inner = select(bcol, func.unnest(EventRecord.countries).label("g")).where(*w.where).subquery()
        rows = (await db.execute(select(inner.c.b, inner.c.g, func.count()).group_by(inner.c.b, inner.c.g))).all()
        rows += [(bb, NONE, n) for bb, n in (await db.execute(
            select(bcol, func.count(EventRecord.id)).where(*w.where, func.cardinality(EventRecord.countries) == 0)
            .group_by(bcol)
        )).all()]
    elif group_by:
        g = func.coalesce(_group_col(group_by), NONE).label("g")
        rows = (await db.execute(select(bcol, g, func.count(EventRecord.id)).where(*w.where).group_by(bcol, g))).all()
    else:
        rows = [(bb, None, n) for bb, n in (await db.execute(
            select(bcol, func.count(EventRecord.id)).where(*w.where).group_by(bcol)
        )).all()]

    per: dict[str, list[int]] = {}
    totals = [0] * len(starts)
    for bb, key, n in rows:
        i = index.get(bb)
        if i is None:
            continue
        totals[i] += n if group_by != "country" else 0
        if key is not None:
            per.setdefault(key, [0] * len(starts))[i] += n
    if group_by == "country" or not group_by:
        # davlat bo'yicha bitta hodisa bir nechta davlatda bo'lishi mumkin — jami alohida
        tot_rows = (await db.execute(
            select(bcol, func.count(EventRecord.id)).where(*w.where).group_by(bcol)
        )).all()
        totals = [0] * len(starts)
        for bb, n in tot_rows:
            if bb in index:
                totals[index[bb]] = n
    ranked = sorted(per.items(), key=lambda kv: (-sum(kv[1]), kv[0]))
    series = [Series(key=k, total=sum(v), values=v) for k, v in ranked[:top]]
    rest = ranked[top:]
    if rest:
        other = [sum(v[i] for _, v in rest) for i in range(len(starts))]
        series.append(Series(key=OTHER, total=sum(other), values=other))
    return TimeSeries(period=Period(start=w.start, end=w.end, range=w.range_key), bucket=b, group_by=group_by,
                      buckets=[d.isoformat() for d in starts], totals=totals, series=series)


# ---------------------------------------------------------------- top-N
class BreakdownItem(BaseModel):
    key: str
    count: int


class Breakdown(BaseModel):
    period: Period
    by: str
    total: int  # filtrga mos hodisalar (davlat bo'yicha yig'indi undan katta bo'lishi mumkin)
    items: list[BreakdownItem]
    other: int  # top'dan tashqaridagi yig'indi


@router.get("/breakdown", response_model=Breakdown)
async def breakdown(
    _: CurrentUser, db: DbSession, w: StatsWindow,
    by: BreakdownBy = Query("category"),
    limit: int = Query(10, ge=1, le=50),
    include_none: bool = Query(False, description="Qiymati yo'q (masalan davlatsiz) hodisalarni ham sanash"),
) -> Breakdown:
    total = await db.scalar(select(func.count(EventRecord.id)).where(*w.where)) or 0
    if by == "country":
        sub = select(func.unnest(EventRecord.countries).label("g")).where(*w.where).subquery()
        rows = (await db.execute(select(sub.c.g, func.count()).group_by(sub.c.g).order_by(func.count().desc()))).all()
        if include_none:
            none = await db.scalar(select(func.count(EventRecord.id)).where(
                *w.where, func.cardinality(EventRecord.countries) == 0)) or 0
            if none:
                rows = [*rows, (NONE, none)]
    else:
        col = _group_col(by)
        stmt = select(col, func.count(EventRecord.id)).where(*w.where).group_by(col).order_by(func.count(EventRecord.id).desc())
        if not include_none:
            stmt = stmt.where(col.is_not(None))
        rows = [(k if k is not None else NONE, n) for k, n in (await db.execute(stmt)).all()]
    rows = sorted(rows, key=lambda r: (-r[1], str(r[0])))
    items = [BreakdownItem(key=str(k), count=n) for k, n in rows[:limit]]
    return Breakdown(period=Period(start=w.start, end=w.end, range=w.range_key), by=by, total=total, items=items,
                     other=sum(n for _, n in rows[limit:]))


# ---------------------------------------------------------------- issiqlik xaritasi
class Heatmap(BaseModel):
    period: Period
    timezone: str
    cells: list[list[int]]  # [hafta kuni 0=Dushanba .. 6, soat 0..23, soni]
    max: int


@router.get("/heatmap", response_model=Heatmap)
async def heatmap(_: CurrentUser, db: DbSession, w: StatsWindow) -> Heatmap:
    lw = local_when()
    dow = (func.extract("isodow", lw) - 1).label("d")
    hour = func.extract("hour", lw).label("h")
    rows = (await db.execute(select(dow, hour, func.count(EventRecord.id)).where(*w.where).group_by(dow, hour))).all()
    cells = [[int(d), int(h), n] for d, h, n in rows]
    return Heatmap(period=Period(start=w.start, end=w.end, range=w.range_key), timezone=settings.app_timezone,
                   cells=cells, max=max((c[2] for c in cells), default=0))


# ---------------------------------------------------------------- manbalar sog'lig'i
class FailingSource(BaseModel):
    id: int
    name: str
    status: str
    since: datetime | None
    last_error: str | None


class SourceHealth(BaseModel):
    total: int
    enabled: int
    by_status: dict[str, int]
    runs_24h: int
    failed_runs_24h: int
    failing: list[FailingSource]


@router.get("/source-health", response_model=SourceHealth)
async def source_health(_: CurrentUser, db: DbSession) -> SourceHealth:
    by_status = dict((await db.execute(select(Source.status, func.count(Source.id)).group_by(Source.status))).all())
    enabled = await db.scalar(select(func.count(Source.id)).where(Source.enabled)) or 0
    since = datetime.now(UTC) - timedelta(hours=24)
    runs = await db.scalar(select(func.count(SourceRun.id)).where(SourceRun.started_at >= since)) or 0
    failed = await db.scalar(select(func.count(SourceRun.id)).where(SourceRun.started_at >= since,
                                                                     SourceRun.ok.is_(False))) or 0
    failing = (await db.scalars(
        select(Source).where(Source.enabled, Source.status.in_(("down", "blocked", "degraded")))
        .order_by(Source.down_since.asc().nulls_last(), Source.name).limit(10)
    )).all()
    return SourceHealth(
        total=sum(by_status.values()), enabled=enabled, by_status=by_status, runs_24h=runs, failed_runs_24h=failed,
        failing=[FailingSource(id=s.id, name=s.name, status=s.status, since=s.down_since, last_error=s.last_error)
                 for s in failing],
    )


# ---------------------------------------------------------------- so'nggi muhim hodisalar
@router.get("/latest", response_model=list[EventItemOut])
async def latest(
    _: CurrentUser, db: DbSession, w: StatsWindow,
    min_severity: Literal["critical", "high", "medium", "low", "info"] = Query("high"),
    limit: int = Query(8, ge=1, le=50),
    lang: str | None = Query(None, pattern="^(en|ru|uz)$"),
) -> list[EventItemOut]:
    order = ["info", "low", "medium", "high", "critical"]
    sev = order[order.index(min_severity):]
    rows = (await db.scalars(
        select(EventRecord).where(*w.where, EventRecord.severity.in_(sev))
        .order_by(when_col().desc(), EventRecord.id.desc()).limit(limit)
    )).all()
    return await localize(db, rows, lang)

