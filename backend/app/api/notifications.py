from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models import AdminAlert, Category, EventRecord, NotificationState
from app.api.events import localize
from app.schemas import EventItemOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class NotificationItem(EventItemOut):
    is_new: bool


class SystemAlert(BaseModel):
    """Adminlar uchun: matni frontendda `kind` bo'yicha tarjima qilinadi."""

    id: int
    kind: str
    source_id: int | None
    data: dict
    created_at: datetime
    is_new: bool


class NotificationsResponse(BaseModel):
    unread: int
    categories: list[str]
    seen_at: datetime | None
    items: list[NotificationItem]
    system: list[SystemAlert] = []


async def _seen_at(db: DbSession, user_id: int) -> datetime | None:
    state = await db.get(NotificationState, user_id)
    return state.seen_at if state else None


@router.get("", response_model=NotificationsResponse)
async def list_notifications(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
    lang: str | None = Query(None, pattern="^(en|ru|uz|uz-Cyrl)$", description="Ko'rsatish tili"),
) -> NotificationsResponse:
    # Ogohlantiriladigan kategoriyalar — bazadan (categories.notify). Baseline hodisalar ogohlantirish bermaydi.
    cats = list((await db.scalars(
        select(Category.slug).where(Category.notify, Category.enabled).order_by(Category.sort_order)
    )).all())
    seen_at = await _seen_at(db, current_user.id)
    base = EventRecord.category.in_(cats) & EventRecord.is_baseline.is_(False)

    unread_stmt = select(func.count(EventRecord.id)).where(base)
    if seen_at:
        unread_stmt = unread_stmt.where(EventRecord.first_seen > seen_at)
    unread = await db.scalar(unread_stmt) or 0

    rows = (await db.scalars(
        select(EventRecord).where(base).order_by(EventRecord.first_seen.desc()).limit(limit)
    )).all()
    localized = await localize(db, rows, lang)
    items = [
        NotificationItem(**it.model_dump(), is_new=seen_at is None or r.first_seen > seen_at)
        for it, r in zip(localized, rows, strict=True)
    ]
    system: list[SystemAlert] = []
    if current_user.role == "admin":
        alerts = (await db.scalars(
            select(AdminAlert).where(AdminAlert.resolved_at.is_(None)).order_by(AdminAlert.created_at.desc()).limit(20)
        )).all()
        system = [SystemAlert(id=a.id, kind=a.kind, source_id=a.source_id, data=a.data, created_at=a.created_at,
                              is_new=seen_at is None or a.created_at > seen_at) for a in alerts]
        unread += sum(1 for a in system if a.is_new)
    return NotificationsResponse(unread=unread, categories=cats, seen_at=seen_at, items=items, system=system)


@router.post("/read")
async def mark_all_read(current_user: CurrentUser, db: DbSession) -> dict[str, int]:
    state = await db.get(NotificationState, current_user.id)
    now = datetime.now(UTC)
    if state is None:
        db.add(NotificationState(user_id=current_user.id, seen_at=now))
    else:
        state.seen_at = now
    await db.commit()
    return {"unread": 0}
