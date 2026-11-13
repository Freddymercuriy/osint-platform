from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Result, SearchJob
from app.models.user import User
from app.schemas import CollectResultOut, SearchJobOut, SearchRequest, SearchResponse
from app.services.collectors.base import BaseCollector
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
        results=[CollectResultOut.model_validate(r) for r in results],
    )


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
                source=r.source,
                type=r.type,
                value=r.value,
                url=r.url,
                detail=r.detail,
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


@router.get("/history", response_model=list[SearchJobOut])
async def history(current_user: CurrentUser, db: DbSession) -> list[SearchJob]:
    rows = await db.scalars(
        select(SearchJob)
        .where(SearchJob.user_id == current_user.id)
        .order_by(SearchJob.created_at.desc())
        .limit(50)
    )
    return list(rows)


@router.get("/jobs/{job_id}", response_model=SearchResponse)
async def job_detail(job_id: int, current_user: CurrentUser, db: DbSession) -> SearchResponse:
    job = await db.scalar(
        select(SearchJob).where(SearchJob.id == job_id, SearchJob.user_id == current_user.id)
    )
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Qidiruv topilmadi")
    return _response_from_job(job, job.results)
