from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.models import Result, SearchJob
from app.models.user import User
from app.schemas import (
    CollectResultOut,
    JobReport,
    ReportJob,
    ReportMeta,
    ReportSummary,
    SearchJobOut,
    SearchRequest,
    SearchResponse,
)
from app.services.collectors.base import BaseCollector
from app.services.collectors.domain import DomainCollector
from app.services.collectors.email import EmailCollector
from app.services.collectors.phone import PhoneCollector
from app.services.collectors.username import UsernameCollector

router = APIRouter(prefix="/api/search", tags=["search"])


def _response_from_job(job: SearchJob, results) -> SearchResponse:
    found = sum(1 for r in results if r.status == "found")
    return SearchResponse(
        job_id=job.id,
        query=job.query,
        kind=job.kind,
        checked=len(results),
        found=found,
        created_at=job.created_at,
        results=[CollectResultOut.model_validate(r) for r in results],
    )


def _clip(value: str | None, limit: int) -> str | None:
    """DB ustun uzunligidan oshmasligi uchun (tashqi manba matni uzun bo'lishi mumkin)."""
    if value is None or len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


async def _run_and_save(
    collector: BaseCollector,
    kind: str,
    data: SearchRequest,
    user: User,
    db: DbSession,
) -> SearchResponse:
    try:
        results = await collector.run(data.query)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    job = SearchJob(user_id=user.id, kind=kind, query=data.query.strip())
    for r in results:
        job.results.append(
            Result(
                source=_clip(r.source, 64),
                type=_clip(r.type, 32),
                value=_clip(r.value, 512),
                url=_clip(r.url, 1024),
                detail=_clip(r.detail, 512),
                status=r.status,
                confidence=r.confidence,
            )
        )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return _response_from_job(job, results)


@router.post("/username", response_model=SearchResponse)
async def search_username(data: SearchRequest, current_user: CurrentUser, db: DbSession):
    return await _run_and_save(UsernameCollector(), "username", data, current_user, db)


@router.post("/email", response_model=SearchResponse)
async def search_email(data: SearchRequest, current_user: CurrentUser, db: DbSession):
    return await _run_and_save(EmailCollector(), "email", data, current_user, db)


@router.post("/phone", response_model=SearchResponse)
async def search_phone(data: SearchRequest, current_user: CurrentUser, db: DbSession):
    return await _run_and_save(PhoneCollector(), "phone", data, current_user, db)


@router.post("/domain", response_model=SearchResponse)
async def search_domain(data: SearchRequest, current_user: CurrentUser, db: DbSession):
    return await _run_and_save(DomainCollector(), "domain", data, current_user, db)


def _like_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/history", response_model=list[SearchJobOut])
async def history(
    current_user: CurrentUser,
    db: DbSession,
    kind: str | None = Query(None, max_length=32),
    q: str | None = Query(None, max_length=256),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[SearchJob]:
    stmt = select(SearchJob).where(SearchJob.user_id == current_user.id)
    if kind:
        stmt = stmt.where(SearchJob.kind == kind)
    if q and q.strip():
        stmt = stmt.where(SearchJob.query.ilike(f"%{_like_escape(q.strip())}%", escape="\\"))
    rows = await db.scalars(
        stmt.order_by(SearchJob.created_at.desc(), SearchJob.id.desc()).limit(limit).offset(offset)
    )
    return list(rows)


@router.delete("/history")
async def clear_history(
    current_user: CurrentUser,
    db: DbSession,
    kind: str | None = Query(None, max_length=32),
) -> dict[str, int]:
    """Foydalanuvchining qidiruv tarixini o'chiradi (natijalar FK CASCADE bilan birga ketadi)."""
    stmt = delete(SearchJob).where(SearchJob.user_id == current_user.id)
    if kind:
        stmt = stmt.where(SearchJob.kind == kind)
    result = await db.execute(stmt)
    await db.commit()
    return {"deleted": result.rowcount or 0}


async def _own_job(job_id: int, user: User, db: DbSession) -> SearchJob:
    job = await db.scalar(
        select(SearchJob).where(SearchJob.id == job_id, SearchJob.user_id == user.id)
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qidiruv topilmadi")
    return job


@router.get("/jobs/{job_id}", response_model=SearchResponse)
async def job_detail(job_id: int, current_user: CurrentUser, db: DbSession) -> SearchResponse:
    job = await _own_job(job_id, current_user, db)
    return _response_from_job(job, job.results)


_STATUS_ORDER = {"found": 0, "error": 1, "not_found": 2}
_REPORT_NOTICE = (
    "Hisobot faqat ochiq (public) manbalardan olingan ma'lumotlar asosida tuzilgan. "
    "Natijalar tekshiruv bajarilgan vaqtdagi holatni aks ettiradi."
)


@router.get("/jobs/{job_id}/export", response_model=JobReport)
async def export_job(
    job_id: int, response: Response, current_user: CurrentUser, db: DbSession
) -> JobReport:
    """Qidiruv hisoboti (JSON). Brauzerda ochilsa fayl sifatida yuklanadi."""
    job = await _own_job(job_id, current_user, db)
    results = sorted(job.results, key=lambda r: (_STATUS_ORDER.get(r.status, 3), r.source.lower()))
    by_status = {"found": 0, "not_found": 0, "error": 0}
    for r in results:
        # noma'lum holatlar UI'dagi kabi "noaniq" (error) hisoblanadi
        by_status[r.status if r.status in by_status else "error"] += 1

    response.headers["Content-Disposition"] = (
        f'attachment; filename="osint-hisobot-{job.kind}-{job.id}.json"'
    )
    return JobReport(
        report=ReportMeta(
            platform=settings.app_name,
            generated_at=datetime.now(UTC),
            notice=_REPORT_NOTICE,
        ),
        job=ReportJob(
            id=job.id, kind=job.kind, query=job.query, status=job.status, created_at=job.created_at
        ),
        summary=ReportSummary(checked=len(results), **by_status),
        results=[CollectResultOut.model_validate(r) for r in results],
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(job_id: int, current_user: CurrentUser, db: DbSession) -> Response:
    job = await _own_job(job_id, current_user, db)
    await db.delete(job)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
