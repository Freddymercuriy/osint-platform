"""Admin: tarjima holati (navbat, xatolar, oylik belgilar), xatolarni qayta urinish, navbatni hozir ishlatish."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.core.config import settings
from app.models import EventTranslation, TranslationCache
from app.services.events import scheduler
from app.services.i18n import worker

router = APIRouter(prefix="/api/admin/translations", tags=["admin"])


class FailedItem(BaseModel):
    event_id: int
    lang: str
    attempts: int
    error: str | None


class TranslationStatus(BaseModel):
    provider: str
    configured: bool
    enabled: bool
    month: date
    chars_used: int
    requests: int
    char_limit: int
    remaining: int
    budget_exhausted: bool
    key_rejected: bool
    paused_until: datetime | None
    last_run: datetime | None
    last_error: str | None
    counts: dict[str, dict[str, int]]  # status → til → soni
    cache_entries: int
    failed: list[FailedItem]


@router.get("", response_model=TranslationStatus)
async def translation_status(_: AdminUser, db: DbSession) -> TranslationStatus:
    usage = await worker.usage_row(db)
    await db.commit()
    st = worker.state
    failed = (await db.scalars(
        select(EventTranslation).where(EventTranslation.status == "failed")
        .order_by(EventTranslation.id.desc()).limit(20)
    )).all()
    return TranslationStatus(
        provider="google", configured=bool(settings.google_translate_api_key), enabled=settings.translate_enabled,
        month=usage.month, chars_used=usage.chars, requests=usage.requests,
        char_limit=settings.translate_monthly_char_limit,
        remaining=max(0, settings.translate_monthly_char_limit - usage.chars),
        budget_exhausted=usage.chars >= settings.translate_monthly_char_limit, key_rejected=st.key_rejected,
        paused_until=st.paused_until, last_run=st.last_run, last_error=st.last_error,
        counts=await worker.counts(db),
        cache_entries=await db.scalar(select(func.count()).select_from(TranslationCache)) or 0,
        failed=[FailedItem(event_id=f.event_id, lang=f.lang, attempts=f.attempts, error=f.error) for f in failed],
    )


@router.post("/retry-failed")
async def retry_failed(_: AdminUser, db: DbSession) -> dict[str, int]:
    return {"requeued": await worker.retry_failed(db)}


@router.post("/run")
async def run_now(_: AdminUser) -> dict:
    """Navbatni hozir ishlatish (fon yig'uvchi buni har 15–30 s da o'zi qiladi)."""
    res = await scheduler.translation_tick()
    stats = res["stats"]
    return {"planned": res["planned"], **({} if stats is None else {
        "rows": stats.rows, "done": stats.done, "from_cache": stats.from_cache, "chars_sent": stats.chars_sent,
        "requests": stats.requests, "failed": stats.failed, "stopped": stats.stopped})}
