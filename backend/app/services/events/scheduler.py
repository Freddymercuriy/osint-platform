"""Yig'uvchi dvigatel: har manba o'z tasodifiy jadvali bilan.

- `next_run_at = now + interval × random(1 − jitter, 1 + jitter)`; ishga tushganda rejasiz manbalar bir interval
  ichida tasodifiy taqsimlanadi (hammasi birdan otilmaydi). Jadval va kesh (ETag, kursor) bazada — restart
  hammasini qayta yuklamaydi va rate limit'ni unutmaydi.
- Bitta tsikl har 15–30 s uyg'onadi va vaqti kelganlarni ishga tushiradi: bir vaqtda ko'pi bilan 8 ta,
  bir xostga bittadan (pauza `connectors/http.py` da).
- Xato → eksponensial backoff (jitter bilan, ≤ 6 soat); 429/503 Retry-After va Telegram FloodWait hurmat qilinadi.
- PostgreSQL advisory lock: ikkinchi worker ikkinchi rejalashtiruvchini ishga tushirmaydi
  (Telethon sessiya fayli ikki jarayonda ishlatilmasligi kerak — yig'uvchi API jarayoni ichida).

Tasodifiy vaqt yukni tarqatish va manba limitlaridan pastda qolish uchun; u bot-himoyasini chetlab o'tmaydi.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.core.db import AsyncSessionLocal, engine
from app.models import AdminAlert, Category, Source, SourceRun
from app.services.connectors import get_connector
from app.services.connectors.base import (
    AuthMissing,
    ConnectorError,
    FetchContext,
    FetchResult,
    RateLimited,
    SourceBlocked,
    SourceView,
)
from app.services.connectors.http import HttpFetcher
from app.services.events import pipeline
from app.services.events.filters import apply_filters

log = logging.getLogger("osint.events")

LOCK_KEY = 72_620_261_114  # pg_advisory_lock kaliti (shu loyiha uchun, ixtiyoriy son)
MAX_CONCURRENT = 8
TICK_RANGE = (15.0, 30.0)
MAX_BACKOFF = 6 * 3600
MAX_RETRY_AFTER = 24 * 3600
AUTH_RECHECK = 3600  # kalit yo'q manbani qayta tekshirish oralig'i
DOWN_AFTER = 3  # ketma-ket shuncha xatodan keyin "down"
SLOW_MS = 15_000
STALE_DAYS = 14  # lentaning eng yangi elementi shundan eski bo'lsa — "degraded"
HOUSEKEEPING_EVERY = 600

# Testlar almashtiradi
HTTP_TRANSPORT = None


# ---------------------------------------------------------------- jadval matematikasi
def jittered(interval: int, jitter_pct: int, rng: random.Random | None = None) -> float:
    j = max(0, min(jitter_pct, 90)) / 100
    return interval * (rng or random).uniform(1 - j, 1 + j)


def backoff_delay(interval: int, failures: int, retry_after: float | None = None,
                  rng: random.Random | None = None) -> float:
    """Eksponensial backoff: interval × 2^(failures−1), ±20% jitter, ≤ 6 soat; Retry-After'dan kam emas."""
    base = min(MAX_BACKOFF, interval * (2 ** max(0, failures - 1)))
    delay = min(MAX_BACKOFF, base * (rng or random).uniform(0.8, 1.2))
    if retry_after:
        delay = max(delay, min(float(retry_after), MAX_RETRY_AFTER))
    return delay


def initial_offset(interval: int, rng: random.Random | None = None) -> float:
    return (rng or random).uniform(0, interval)


# ---------------------------------------------------------------- holat
@dataclass
class SchedulerState:
    running: bool = False
    lock_held: bool = False
    started_at: datetime | None = None
    last_tick: datetime | None = None
    runs: int = 0
    last_run_at: datetime | None = None
    last_new: int = 0
    last_error: str | None = None
    active: set[int] = field(default_factory=set)
    _task: asyncio.Task | None = field(default=None, repr=False)
    _sem: asyncio.Semaphore | None = field(default=None, repr=False)
    _http: HttpFetcher | None = field(default=None, repr=False)
    _tr_http: HttpFetcher | None = field(default=None, repr=False)  # tarjima servisi uchun alohida mijoz
    _last_housekeeping: float = 0.0


state = SchedulerState()


def _http() -> HttpFetcher:
    if state._http is None:
        state._http = HttpFetcher.create(transport=HTTP_TRANSPORT)
    return state._http


def _sem() -> asyncio.Semaphore:
    if state._sem is None:
        state._sem = asyncio.Semaphore(MAX_CONCURRENT)
    return state._sem


def view_of(source: Source, category_slug: str | None = None) -> SourceView:
    return SourceView(
        id=source.id, name=source.name, kind=source.kind, config=dict(source.config or {}),
        lang=source.lang, scope=source.scope, region_filter=source.region_filter,
        cyber_filter=source.cyber_filter, api_key_env=source.api_key_env, etag=source.etag,
        last_modified=source.last_modified, state=dict(source.state or {}),
        backfill_days=source.backfill_days, category_slug=category_slug,
    )


def api_key_for(source: Source | SourceView, connector) -> tuple[str | None, str | None]:
    """(muhit o'zgaruvchisi nomi, qiymati). Kalitning o'zi hech qayerga yozilmaydi."""
    env = source.api_key_env or connector.default_key_env
    return env, (os.environ.get(env) or getattr(settings, env.lower(), None)) if env else None


# ---------------------------------------------------------------- bitta manba
@dataclass
class RunSummary:
    source_id: int
    ok: bool
    outcome: str
    status: str
    http_status: int | None = None
    duration_ms: int = 0
    items: int = 0
    passed: int = 0
    new: int = 0
    merged: int = 0
    error: str | None = None
    next_run_at: datetime | None = None
    retry_after_seconds: int | None = None  # sayt so'ragan kutish (Retry-After / FloodWait)
    wait_seconds: int | None = None  # keyingi urinishgacha rejalashtirilgan kutish


def retry_after_of(error: ConnectorError) -> int | None:
    """Sayt so'ragan kutish, butun soniya (yo'q bo'lsa None)."""
    ra = error.retry_after
    return min(int(ra + 0.999), 10**9) if ra and ra > 0 else None


async def _fetch(source_view: SourceView, connector, dry_run: bool) -> FetchResult:
    env, key = api_key_for(source_view, connector)
    if connector.key == "required" and not key:
        raise AuthMissing(f"Kalit sozlanmagan: {env or '?'} (backend/.env)")
    ctx = FetchContext(source=source_view, http=_http(), api_key=key, dry_run=dry_run)
    return await connector.fetch(ctx)


def _health_after_success(source: Source, latency_ms: int, newest, now: datetime, failures_recent: int) -> str:
    if latency_ms > SLOW_MS or failures_recent >= 3:
        return "degraded"
    stale_days = int((source.config or {}).get("stale_after_days") or STALE_DAYS)
    if newest is not None and newest < now - timedelta(days=stale_days):
        return "degraded"
    return "ok"


async def run_source(source_id: int, *, manual: bool = False) -> RunSummary:
    """Manbani hozir yig'adi (haqiqiy: bazaga yozadi, holatni yangilaydi, source_runs qatori)."""
    started = datetime.now(UTC)
    t0 = time.monotonic()
    async with AsyncSessionLocal() as db:
        source = await db.get(Source, source_id)
        if source is None:
            return RunSummary(source_id, False, "error", "down", error="Manba topilmadi")
        connector = get_connector(source.kind)
        cat_slug = (await db.scalar(select(Category.slug).where(Category.id == source.category_id))
                    if source.category_id else None)
        view = view_of(source, cat_slug)
        summary = RunSummary(source_id, False, "error", source.status)
        result: FetchResult | None = None
        error: ConnectorError | None = None
        try:
            if connector is None:
                raise ConnectorError(f"Noma'lum manba turi: {source.kind}")
            result = await _fetch(view, connector, dry_run=False)
        except ConnectorError as exc:
            error = exc
        except Exception as exc:  # ulagichdagi kutilmagan xato — boshqa manbalarga ta'sir qilmaydi
            log.exception("Manba %s: kutilmagan xato", source.name)
            error = ConnectorError(f"{type(exc).__name__}: {exc}")

        now = datetime.now(UTC)
        duration = int((time.monotonic() - t0) * 1000)
        summary.duration_ms = duration
        source.last_check_at = now
        source.last_latency_ms = duration

        if error is None and result is not None:
            baseline = not source.baseline_done
            raw = result.items
            items = apply_filters(raw, view) if (view.region_filter or view.cyber_filter) else raw
            stats = await pipeline.store_items(db, source, items, now, baseline=baseline)
            source = await db.get(Source, source_id)  # store_items commit qildi
            newest = max((pipeline.aware(i.published, now) for i in raw if i.published), default=None)
            if newest is not None:
                source.newest_item_at = newest
            failures_recent = await db.scalar(text(
                "select count(*) from (select ok from source_runs where source_id = :sid "
                "order by started_at desc limit 10) t where not ok"
            ), {"sid": source_id}) or 0
            source.status = _health_after_success(source, duration, source.newest_item_at, now, failures_recent)
            source.consecutive_failures = 0
            source.down_since = None
            await resolve_alerts(db, source_id, now)
            source.last_success_at = now
            source.last_error = None
            source.last_http_status = result.http_status
            source.last_items = len(raw)
            source.last_new_items = stats.new
            source.baseline_done = True
            if result.etag is not None or result.last_modified is not None:
                source.etag, source.last_modified = result.etag, result.last_modified
            if result.state is not None:
                source.state = result.state
            delay = jittered(source.interval_seconds, source.jitter_pct)
            source.next_run_at = now + timedelta(seconds=delay)
            outcome = "not_modified" if result.not_modified else "ok"
            source.last_outcome, source.retry_after_seconds = outcome, None
            summary.wait_seconds = int(delay)
            summary.ok, summary.outcome, summary.http_status = True, outcome, result.http_status
            summary.items, summary.passed, summary.new, summary.merged = len(raw), len(items), stats.new, stats.merged
            db.add(SourceRun(source_id=source_id, started_at=started, duration_ms=duration,
                             http_status=result.http_status, ok=True, outcome=outcome, items=len(raw),
                             new_items=stats.new, manual=manual, wait_seconds=int(delay),
                             error=(f"baseline: {stats.new} ta yozildi" if baseline else result.note)))
            await db.commit()
            await pipeline.notify_new(db, stats.records)
        else:
            assert error is not None
            source.consecutive_failures += 1
            source.last_error = str(error)[:2000]
            source.last_http_status = error.http_status
            if isinstance(error, AuthMissing):
                source.status = "auth_missing"
                delay = max(AUTH_RECHECK, source.interval_seconds)
            else:
                if isinstance(error, SourceBlocked):
                    source.status = "blocked"
                elif source.consecutive_failures >= DOWN_AFTER:
                    source.status = "down"
                else:
                    source.status = "degraded"
                delay = backoff_delay(source.interval_seconds, source.consecutive_failures, error.retry_after)
            if source.status in ("down", "blocked") and source.down_since is None:
                source.down_since = now
            source.next_run_at = now + timedelta(seconds=delay)
            retry_after = retry_after_of(error)
            source.last_outcome, source.retry_after_seconds = error.outcome, retry_after
            summary.outcome, summary.error, summary.http_status = error.outcome, str(error), error.http_status
            summary.retry_after_seconds, summary.wait_seconds = retry_after, int(delay)
            db.add(SourceRun(source_id=source_id, started_at=started, duration_ms=duration,
                             http_status=error.http_status, ok=False, outcome=error.outcome,
                             error=str(error)[:2000], manual=manual,
                             retry_after_seconds=retry_after, wait_seconds=int(delay)))
            await db.commit()
            log.info("Manba %s: %s (%s)%s, keyingi urinish %d daq.dan keyin", source.name, error.outcome, error,
                     f", sayt {retry_after} s kutishni so'radi" if retry_after else "", int(delay // 60))
        summary.status = source.status
        summary.next_run_at = source.next_run_at
    state.runs += 1
    state.last_run_at = started
    state.last_new = summary.new
    return summary


# ---------------------------------------------------------------- sinov (hech narsa yozilmaydi)
@dataclass
class TestResult:
    ok: bool
    outcome: str
    http_status: int | None
    latency_ms: int
    items: int
    passed: int
    samples: list[dict]
    error: str | None = None
    note: str | None = None
    retry_after_seconds: int | None = None


async def test_source(view: SourceView) -> TestResult:
    """Dry run: ulagich + filtrlar; bazaga, ETag/kursorga hech narsa yozilmaydi."""
    connector = get_connector(view.kind)
    t0 = time.monotonic()
    if connector is None:
        return TestResult(False, "error", None, 0, 0, 0, [], error=f"Noma'lum manba turi: {view.kind}")
    try:
        result = await _fetch(view, connector, dry_run=True)
    except ConnectorError as exc:
        return TestResult(False, exc.outcome, exc.http_status, int((time.monotonic() - t0) * 1000), 0, 0, [],
                          error=str(exc), retry_after_seconds=retry_after_of(exc))
    except Exception as exc:
        return TestResult(False, "error", None, int((time.monotonic() - t0) * 1000), 0, 0, [],
                          error=f"{type(exc).__name__}: {exc}")
    latency = int((time.monotonic() - t0) * 1000)
    raw = result.items
    passed = apply_filters(list(raw), view) if (view.region_filter or view.cyber_filter) else raw
    passed = [i for i in passed if pipeline.valid_url(i.url) and i.title.strip()]
    samples = [
        {"title": i.title[:200], "url": i.url, "published": i.published.isoformat() if i.published else None,
         "matched_keywords": i.matched_keywords[:6]}
        for i in passed[:3]
    ]
    return TestResult(True, "not_modified" if result.not_modified else "ok", result.http_status, latency,
                      len(raw), len(passed), samples, note=result.note)


# ---------------------------------------------------------------- rejalashtiruvchi tsikli
async def schedule_unplanned(now: datetime | None = None) -> int:
    """Rejasiz (next_run_at bo'sh) yoqilgan manbalarni bir interval ichida tasodifiy taqsimlaydi."""
    now = now or datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        rows = (await db.scalars(select(Source).where(Source.enabled, Source.next_run_at.is_(None)))).all()
        for s in rows:
            s.next_run_at = now + timedelta(seconds=initial_offset(s.interval_seconds))
        await db.commit()
        return len(rows)


async def due_sources(now: datetime, limit: int = 50) -> list[int]:
    async with AsyncSessionLocal() as db:
        stmt = (select(Source.id).where(Source.enabled, Source.next_run_at <= now)
                .order_by(Source.next_run_at).limit(limit))
        if state.active:
            stmt = stmt.where(Source.id.notin_(state.active))
        return list((await db.scalars(stmt)).all())


async def _guarded_run(source_id: int, manual: bool = False) -> RunSummary | None:
    if source_id in state.active:
        return None
    state.active.add(source_id)
    try:
        async with _sem():
            return await run_source(source_id, manual=manual)
    except Exception as exc:
        state.last_error = f"{type(exc).__name__}: {exc}"
        log.exception("Manba %s ni yig'ishda xato", source_id)
        return None
    finally:
        state.active.discard(source_id)


def translator():
    from app.services.i18n.translator import NllbTranslator

    if state._tr_http is None:
        # O'z servisimiz: URL operator sozlamasidan (foydalanuvchi kiritmaydi) — SSRF filtri va xushmuomalalik
        # pauzasi kerak emas (servis ichki manzilga ko'chirilsa ham ishlaydi)
        state._tr_http = HttpFetcher.create(transport=HTTP_TRANSPORT, ssrf_guard=False, pause_range=(0.0, 0.0))
    return NllbTranslator(settings.translate_api_url, state._tr_http, timeout=settings.translate_timeout_seconds)


async def translation_tick() -> dict:
    """Yangi hodisalar uchun tarjima rejasi + navbatdan bir qism (kalit bo'lsa)."""
    from app.services.i18n import worker

    async with AsyncSessionLocal() as db:
        planned = await worker.ensure_rows(db)
    stats = None
    if settings.translate_enabled:
        async with AsyncSessionLocal() as db:
            stats = await worker.process_pending(db, translator())
            if stats.done_event_ids:
                from app.services.publisher.scoring import recompute_safe

                await recompute_safe(db, stats.done_event_ids)
    return {"planned": planned, "stats": stats}


async def resolve_alerts(db, source_id: int, now: datetime) -> None:
    await db.execute(update(AdminAlert).where(
        AdminAlert.kind == "source_down", AdminAlert.source_id == source_id, AdminAlert.resolved_at.is_(None)
    ).values(resolved_at=now))


async def raise_down_alerts(db, now: datetime | None = None) -> int:
    """Yoqilgan manba `source_down_alert_hours` dan beri down/blocked bo'lsa — adminlarga ogohlantirish (bir marta)."""
    now = now or datetime.now(UTC)
    limit = now - timedelta(hours=max(1, settings.source_down_alert_hours))
    open_ids = set((await db.scalars(
        select(AdminAlert.source_id).where(AdminAlert.kind == "source_down", AdminAlert.resolved_at.is_(None))
    )).all())
    rows = (await db.scalars(select(Source).where(
        Source.enabled, Source.status.in_(("down", "blocked")), Source.down_since <= limit,
    ))).all()
    created = 0
    for s in rows:
        if s.id in open_ids:
            continue
        db.add(AdminAlert(kind="source_down", source_id=s.id, created_at=now, data={
            "source": s.name, "status": s.status, "since": s.down_since.isoformat() if s.down_since else None,
            "error": (s.last_error or "")[:300], "http_status": s.last_http_status,
        }))
        created += 1
    await db.commit()
    return created


async def housekeeping() -> None:
    async with AsyncSessionLocal() as db:
        alerts = await raise_down_alerts(db)
        if alerts:
            log.warning("%d ta manba uzoq vaqt ishlamayapti — adminlarga ogohlantirish", alerts)
        purged = await pipeline.purge_expired(db, datetime.now(UTC))
    if purged:
        log.info("Retention: %d ta eski hodisa o'chirildi", purged)
    from app.services.publisher import scoring

    async with AsyncSessionLocal() as db:
        # Bali yo'q hodisalar (migratsiyadan keyin yoki biror yo'l o'tkazib yuborgan bo'lsa)
        filled = await scoring.recompute(db, only_missing=True)
    if filled:
        log.info("Ustuvorlik: %d ta hodisa uchun hisoblandi", filled)
    from app.services.events import telegram_archive

    try:
        await telegram_archive.maybe_sync()  # TG_MONITOR_ARCHIVED: arxivdagi kanal/guruhlar → manbalar
    except Exception:
        log.exception("Telegram arxivi sinxronlash xatosi")


async def try_lock(conn: AsyncConnection) -> bool:
    got = (await conn.execute(text("select pg_try_advisory_lock(:k)"), {"k": LOCK_KEY})).scalar()
    await conn.commit()  # session-level lock tranzaksiyadan keyin ham saqlanadi
    return bool(got)


async def _loop() -> None:
    state.running = True
    state.started_at = datetime.now(UTC)
    await asyncio.sleep(3)  # ilova to'liq ishga tushsin
    lock_conn: AsyncConnection | None = None
    tasks: set[asyncio.Task] = set()
    try:
        while True:
            if lock_conn is None:
                lock_conn = await engine.connect()
                if not await try_lock(lock_conn):
                    await lock_conn.close()
                    lock_conn = None
                    state.lock_held = False
                    log.info("Yig'uvchi boshqa jarayonda ishlayapti (advisory lock band) — 60 s kutamiz")
                    await asyncio.sleep(60)
                    continue
                state.lock_held = True
                planned = await schedule_unplanned()
                log.info("Yig'uvchi ishga tushdi (advisory lock olindi); %d manba rejalashtirildi", planned)
            try:
                await lock_conn.execute(text("select 1"))
                await lock_conn.commit()
            except Exception:
                log.warning("Advisory lock ulanishi uzildi — qayta olinadi")
                state.lock_held = False
                try:
                    await lock_conn.close()
                except Exception:
                    pass
                lock_conn = None
                continue

            now = datetime.now(UTC)
            state.last_tick = now
            for sid in await due_sources(now):
                t = asyncio.create_task(_guarded_run(sid), name=f"source-{sid}")
                tasks.add(t)
                t.add_done_callback(tasks.discard)
            try:
                await translation_tick()
            except Exception:
                log.exception("Tarjima navbati xatosi")
            if time.monotonic() - state._last_housekeeping > HOUSEKEEPING_EVERY:
                state._last_housekeeping = time.monotonic()
                try:
                    await housekeeping()
                except Exception:
                    log.exception("Housekeeping xatosi")
            await asyncio.sleep(random.uniform(*TICK_RANGE))
    except asyncio.CancelledError:
        pass
    finally:
        for t in tasks:
            t.cancel()
        if lock_conn is not None:
            try:
                await lock_conn.execute(text("select pg_advisory_unlock(:k)"), {"k": LOCK_KEY})
                await lock_conn.close()
            except Exception:
                pass
        state.running = False
        state.lock_held = False


def start() -> None:
    if settings.events_poll_enabled and state._task is None:
        state._task = asyncio.create_task(_loop(), name="events-scheduler")


async def stop() -> None:
    if state._task:
        state._task.cancel()
        try:
            await state._task
        except asyncio.CancelledError:
            pass
        state._task = None
    if state._http is not None:
        await state._http.aclose()
        state._http = None
    if state._tr_http is not None:
        await state._tr_http.aclose()
        state._tr_http = None
    state._sem = None


async def run_many(source_ids: list[int], manual: bool = True, timeout: float = 120) -> list[RunSummary]:
    """Bir nechta manbani hozir yig'ish (umumiy limit va xost navbati bilan)."""
    tasks = [asyncio.create_task(_guarded_run(sid, manual=manual)) for sid in source_ids]
    if not tasks:
        return []
    # Vaqt tugasa ham qolganlari fon'da tugaydi; natijasi keyingi so'rovda ko'rinadi
    done, _pending = await asyncio.wait(tasks, timeout=timeout)
    return [r for t in done if (r := t.result()) is not None]


async def mark_due_now(source_ids: list[int]) -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(update(Source).where(Source.id.in_(source_ids)).values(next_run_at=datetime.now(UTC)))
        await db.commit()
