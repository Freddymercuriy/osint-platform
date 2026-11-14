"""Admin: manbalar (CRUD, yoqish/o'chirish, sinov, hozir yig'ish, tarix, eksport/import) va yig'uvchi holati."""

from __future__ import annotations

import random
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import case, func, select

from app.core.errors import api_error
from app.api.deps import AdminUser, DbSession
from app.models import Category, EventRecord, Source, SourceRun
from app.services.connectors import CONNECTORS, get_connector
from app.services.connectors.base import ConfigError, ConnectorError
from app.services.connectors.http import assert_public_url
from app.services.events import scheduler

router = APIRouter(prefix="/api/admin", tags=["admin"])

_KEY_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]*_(API_KEY|KEY|TOKEN|AUTH_KEY)$")
_FORBIDDEN_ENV = {"SECRET_KEY", "TG_API_HASH", "TG_API_ID", "DATABASE_URL"}

Scope = Literal["regional", "global"]


def _check_key_env(v: str | None) -> str | None:
    if v in (None, ""):
        return None
    if v in _FORBIDDEN_ENV or not _KEY_ENV_RE.match(v):
        raise ValueError("api_key_env — kalit o'zgaruvchisi nomi (..._API_KEY / ..._KEY / ..._TOKEN), SECRET_KEY emas")
    return v


class SourceBase(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    lang: str = Field("en", min_length=2, max_length=8)
    category: str | None = None  # qat'iy kategoriya slug'i
    scope: Scope = "regional"
    region_filter: bool = False
    cyber_filter: bool = False
    translate: bool = True
    enabled: bool = True
    interval_seconds: int = Field(900, ge=60, le=7 * 24 * 3600)
    jitter_pct: int = Field(20, ge=0, le=90)
    backfill_days: int = Field(14, ge=0, le=365)
    api_key_env: str | None = None
    notes: str = Field("", max_length=2000)

    @field_validator("api_key_env")
    @classmethod
    def _key_env(cls, v: str | None) -> str | None:
        return _check_key_env(v)


class SourceIn(SourceBase):
    name: str = Field(min_length=2, max_length=128)
    kind: str = Field(min_length=2, max_length=32)


class SourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=128)
    config: dict[str, Any] | None = None
    lang: str | None = Field(None, min_length=2, max_length=8)
    category: str | None = None
    scope: Scope | None = None
    region_filter: bool | None = None
    cyber_filter: bool | None = None
    translate: bool | None = None
    enabled: bool | None = None
    interval_seconds: int | None = Field(None, ge=60, le=7 * 24 * 3600)
    jitter_pct: int | None = Field(None, ge=0, le=90)
    backfill_days: int | None = Field(None, ge=0, le=365)
    api_key_env: str | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("api_key_env")
    @classmethod
    def _key_env(cls, v: str | None) -> str | None:
        return _check_key_env(v)


class SourceOut(SourceIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    key_configured: bool | None = None  # None — kalit kerak emas
    next_run_at: datetime | None
    last_check_at: datetime | None
    last_success_at: datetime | None
    last_error: str | None
    last_http_status: int | None
    last_latency_ms: int | None
    consecutive_failures: int
    last_items: int | None
    last_new_items: int | None
    newest_item_at: datetime | None
    down_since: datetime | None
    baseline_done: bool
    items_24h: int = 0
    uptime_7d: float | None = None  # 0..1, urinish bo'lmasa None
    created_at: datetime
    updated_at: datetime


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    duration_ms: int | None
    http_status: int | None
    ok: bool
    outcome: str
    items: int
    new_items: int
    error: str | None
    manual: bool


class TestOut(BaseModel):
    ok: bool
    outcome: str
    http_status: int | None
    latency_ms: int
    items: int
    passed: int
    samples: list[dict]
    error: str | None = None
    note: str | None = None


class RunNowOut(BaseModel):
    ok: bool
    outcome: str
    status: str
    http_status: int | None
    duration_ms: int
    items: int
    passed: int
    new: int
    merged: int
    error: str | None
    next_run_at: datetime | None


class ConnectorOut(BaseModel):
    kind: str
    title: str
    config_fields: list[str]
    key: str | None
    default_key_env: str | None


# ---------------------------------------------------------------- yordamchilar
async def _category_id(db, slug: str | None) -> int | None:
    if not slug:
        return None
    cid = await db.scalar(select(Category.id).where(Category.slug == slug))
    if cid is None:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "category_slug_not_found", slug=slug)
    return cid


async def _validate(kind: str, config: dict) -> None:
    connector = get_connector(kind)
    if connector is None:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "source_kind_unknown", kind=kind)
    try:
        connector.validate_config(config)
        for url in connector.target_urls(_view_like(kind, config)):
            await assert_public_url(url)
    except ConfigError as exc:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "config_invalid", message=str(exc)) from exc
    except ConnectorError:  # DNS hozir topilmadi va h.k. — saqlashga to'sqinlik qilmaydi (sog'liqda ko'rinadi)
        pass


def _view_like(kind: str, config: dict):
    from app.services.connectors.base import SourceView

    return SourceView(id=None, name="", kind=kind, config=config, lang="en", scope="regional",
                      region_filter=False, cyber_filter=False, api_key_env=None, etag=None,
                      last_modified=None, state={}, backfill_days=14)


def _key_configured(s: Source) -> bool | None:
    connector = get_connector(s.kind)
    if connector is None or (connector.key is None and not s.api_key_env):
        return None
    _env, key = scheduler.api_key_for(s, connector)
    return bool(key)


async def _out(db, rows: list[Source]) -> list[SourceOut]:
    if not rows:
        return []
    ids = [s.id for s in rows]
    now = datetime.now(UTC)
    slugs = dict((await db.execute(select(Category.id, Category.slug))).all())
    items_24h = dict((await db.execute(
        select(EventRecord.source_id, func.count(EventRecord.id))
        .where(EventRecord.source_id.in_(ids), EventRecord.first_seen >= now - timedelta(hours=24))
        .group_by(EventRecord.source_id)
    )).all())
    uptime = {
        sid: (ok / total if total else None)
        for sid, ok, total in (await db.execute(
            select(SourceRun.source_id, func.sum(case((SourceRun.ok, 1), else_=0)), func.count(SourceRun.id))
            .where(SourceRun.source_id.in_(ids), SourceRun.started_at >= now - timedelta(days=7))
            .group_by(SourceRun.source_id)
        )).all()
    }
    out = []
    for s in rows:
        o = SourceOut.model_validate(s, from_attributes=True).model_copy(update={
            "category": slugs.get(s.category_id),
            "items_24h": items_24h.get(s.id, 0),
            "uptime_7d": uptime.get(s.id),
            "key_configured": _key_configured(s),
        })
        out.append(o)
    return out


async def _get(db, source_id: int) -> Source:
    s = await db.get(Source, source_id)
    if s is None:
        raise api_error(status.HTTP_404_NOT_FOUND, "source_not_found")
    return s


async def _status_from_last_run(db, source: Source) -> str:
    last = await db.scalar(
        select(SourceRun.outcome).where(SourceRun.source_id == source.id).order_by(SourceRun.started_at.desc()).limit(1)
    )
    return {None: "never_run", "ok": "ok", "not_modified": "ok", "blocked": "blocked", "rate_limited": "blocked",
            "auth_missing": "auth_missing"}.get(last, "down")


# ---------------------------------------------------------------- manbalar
@router.get("/connectors", response_model=list[ConnectorOut])
async def list_connectors(_: AdminUser) -> list[ConnectorOut]:
    return [ConnectorOut(kind=k, title=c.title or k, config_fields=list(c.config_fields), key=c.key,
                         default_key_env=c.default_key_env) for k, c in sorted(CONNECTORS.items())]


@router.get("/sources", response_model=list[SourceOut])
async def list_sources(
    _: AdminUser, db: DbSession,
    status_: str | None = Query(None, alias="status"),
    kind: str | None = None,
    enabled: bool | None = None,
) -> list[SourceOut]:
    stmt = select(Source).order_by(Source.name)
    if status_:
        stmt = stmt.where(Source.status == status_)
    if kind:
        stmt = stmt.where(Source.kind == kind)
    if enabled is not None:
        stmt = stmt.where(Source.enabled == enabled)
    return await _out(db, list((await db.scalars(stmt)).all()))


@router.get("/sources/export")
async def export_sources(_: AdminUser, db: DbSession, response: Response) -> dict:
    """Manbalar ro'yxati (boshqa kompyuterga ko'chirish uchun). Holat, kesh va kalitlar kirmaydi."""
    slugs = dict((await db.execute(select(Category.id, Category.slug))).all())
    rows = (await db.scalars(select(Source).order_by(Source.name))).all()
    response.headers["Content-Disposition"] = 'attachment; filename="osint-sources.json"'
    return {
        "format": "osint-sources", "version": 1, "exported_at": datetime.now(UTC).isoformat(),
        "sources": [
            SourceIn(name=s.name, kind=s.kind, config=s.config, lang=s.lang, category=slugs.get(s.category_id),
                     scope=s.scope, region_filter=s.region_filter, cyber_filter=s.cyber_filter,
                     translate=s.translate, enabled=s.enabled, interval_seconds=s.interval_seconds,
                     jitter_pct=s.jitter_pct, backfill_days=s.backfill_days, api_key_env=s.api_key_env,
                     notes=s.notes).model_dump()
            for s in rows
        ],
    }


class ImportIn(BaseModel):
    sources: list[SourceIn] = Field(max_length=2000)
    format: str | None = None
    version: int | None = None


@router.post("/sources/import")
async def import_sources(data: ImportIn, _: AdminUser, db: DbSession) -> dict[str, int]:
    """Nom bo'yicha upsert: bor bo'lsa sozlamalari yangilanadi (holati saqlanadi), yo'q bo'lsa yaratiladi."""
    created = updated = 0
    for item in data.sources:
        await _validate(item.kind, item.config)
        cid = await _category_id(db, item.category)
        fields = item.model_dump(exclude={"category"})
        existing = await db.scalar(select(Source).where(Source.name == item.name))
        if existing is None:
            db.add(Source(**fields, category_id=cid, status="never_run" if item.enabled else "disabled"))
            created += 1
        else:
            if existing.config != item.config or existing.kind != item.kind:
                existing.etag = existing.last_modified = None
                existing.state = {}
                existing.baseline_done = False
            for k, v in fields.items():
                setattr(existing, k, v)
            existing.category_id = cid
            updated += 1
    await db.commit()
    await scheduler.schedule_unplanned()
    return {"created": created, "updated": updated}


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(data: SourceIn, _: AdminUser, db: DbSession) -> SourceOut:
    if await db.scalar(select(Source.id).where(Source.name == data.name)):
        raise api_error(status.HTTP_409_CONFLICT, "source_name_taken")
    await _validate(data.kind, data.config)
    s = Source(**data.model_dump(exclude={"category"}), category_id=await _category_id(db, data.category),
               status="never_run" if data.enabled else "disabled")
    if data.enabled:
        s.next_run_at = datetime.now(UTC) + timedelta(seconds=random.uniform(5, 60))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return (await _out(db, [s]))[0]


@router.get("/sources/{source_id}", response_model=SourceOut)
async def get_source(source_id: int, _: AdminUser, db: DbSession) -> SourceOut:
    return (await _out(db, [await _get(db, source_id)]))[0]


@router.patch("/sources/{source_id}", response_model=SourceOut)
async def update_source(source_id: int, data: SourceUpdate, _: AdminUser, db: DbSession) -> SourceOut:
    s = await _get(db, source_id)
    changes = data.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] != s.name:
        if await db.scalar(select(Source.id).where(Source.name == changes["name"])):
            raise api_error(status.HTTP_409_CONFLICT, "source_name_taken")
    if "config" in changes and changes["config"] != s.config:
        await _validate(s.kind, changes["config"])
        s.etag = s.last_modified = None
        s.state = {}
        s.baseline_done = False  # yangi manzil — qayta baseline (eski elementlar ogohlantirish bermaydi)
    if "category" in changes:
        s.category_id = await _category_id(db, changes.pop("category"))
    enabled_before = s.enabled
    for k, v in changes.items():
        if k != "category":
            setattr(s, k, v)
    if enabled_before and not s.enabled:
        s.status, s.next_run_at = "disabled", None
    elif not enabled_before and s.enabled:
        s.status = await _status_from_last_run(db, s)
        s.next_run_at = datetime.now(UTC) + timedelta(seconds=random.uniform(5, 60))
    await db.commit()
    await db.refresh(s)
    return (await _out(db, [s]))[0]


@router.post("/sources/{source_id}/enable", response_model=SourceOut)
async def enable_source(source_id: int, admin: AdminUser, db: DbSession) -> SourceOut:
    return await update_source(source_id, SourceUpdate(enabled=True), admin, db)


@router.post("/sources/{source_id}/disable", response_model=SourceOut)
async def disable_source(source_id: int, admin: AdminUser, db: DbSession) -> SourceOut:
    return await update_source(source_id, SourceUpdate(enabled=False), admin, db)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(source_id: int, _: AdminUser, db: DbSession) -> Response:
    """Manba o'chiriladi; uning hodisalari qoladi (manba nomi bilan, `source_id` bo'shatiladi)."""
    s = await _get(db, source_id)
    await db.delete(s)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sources/test", response_model=TestOut)
async def test_draft(data: SourceIn, _: AdminUser, db: DbSession) -> TestOut:
    """Saqlanmagan manbani sinash (yaratish formasi uchun). Hech narsa yozilmaydi."""
    await _validate(data.kind, data.config)
    view = _view_like(data.kind, data.config)
    view.name, view.lang, view.scope = data.name, data.lang, data.scope
    view.region_filter, view.cyber_filter, view.api_key_env = data.region_filter, data.cyber_filter, data.api_key_env
    view.category_slug = data.category
    r = await scheduler.test_source(view)
    return TestOut(**r.__dict__)


@router.post("/sources/{source_id}/test", response_model=TestOut)
async def test_source(source_id: int, _: AdminUser, db: DbSession) -> TestOut:
    """Dry run: so'rov + filtrlar, bazaga / ETag / kursorga hech narsa yozilmaydi."""
    s = await _get(db, source_id)
    r = await scheduler.test_source(scheduler.view_of(s))
    return TestOut(**r.__dict__)


@router.post("/sources/{source_id}/run", response_model=RunNowOut)
async def run_source_now(source_id: int, _: AdminUser, db: DbSession) -> RunNowOut:
    await _get(db, source_id)
    if source_id in scheduler.state.active:
        raise api_error(status.HTTP_409_CONFLICT, "source_busy")
    r = await scheduler._guarded_run(source_id, manual=True)
    if r is None:
        raise api_error(status.HTTP_409_CONFLICT, "source_busy")
    return RunNowOut(ok=r.ok, outcome=r.outcome, status=r.status, http_status=r.http_status,
                     duration_ms=r.duration_ms, items=r.items, passed=r.passed, new=r.new, merged=r.merged,
                     error=r.error, next_run_at=r.next_run_at)


@router.get("/sources/{source_id}/runs", response_model=list[RunOut])
async def source_runs(source_id: int, _: AdminUser, db: DbSession,
                      limit: int = Query(50, ge=1, le=500)) -> list[SourceRun]:
    await _get(db, source_id)
    return list((await db.scalars(
        select(SourceRun).where(SourceRun.source_id == source_id).order_by(SourceRun.started_at.desc()).limit(limit)
    )).all())


# ---------------------------------------------------------------- yig'uvchi holati
class CollectorOut(BaseModel):
    enabled: bool
    running: bool
    lock_held: bool
    started_at: datetime | None
    last_tick: datetime | None
    active: list[int]
    runs: int
    last_error: str | None
    sources_total: int
    sources_enabled: int
    by_status: dict[str, int]
    runs_24h: int
    failed_runs_24h: int


@router.get("/collector", response_model=CollectorOut)
async def collector_status(_: AdminUser, db: DbSession) -> CollectorOut:
    from app.core.config import settings

    st = scheduler.state
    by_status = dict((await db.execute(select(Source.status, func.count(Source.id)).group_by(Source.status))).all())
    total = sum(by_status.values())
    enabled = await db.scalar(select(func.count(Source.id)).where(Source.enabled)) or 0
    since = datetime.now(UTC) - timedelta(hours=24)
    runs, failed = (await db.execute(
        select(func.count(SourceRun.id), func.sum(case((SourceRun.ok, 0), else_=1)))
        .where(SourceRun.started_at >= since)
    )).one()
    return CollectorOut(
        enabled=settings.events_poll_enabled, running=st.running, lock_held=st.lock_held,
        started_at=st.started_at, last_tick=st.last_tick, active=sorted(st.active), runs=st.runs,
        last_error=st.last_error, sources_total=total, sources_enabled=enabled, by_status=by_status,
        runs_24h=runs or 0, failed_runs_24h=failed or 0,
    )
