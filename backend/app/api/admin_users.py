"""Admin: foydalanuvchilar ro'yxati, rolni o'zgartirish, faolsizlantirish."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.core.errors import api_error
from app.models import SearchJob, User

router = APIRouter(prefix="/api/admin/users", tags=["admin"])


class UserRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    is_active: bool
    locale: str | None
    created_at: datetime
    searches: int = 0


class UserPatch(BaseModel):
    role: Literal["admin", "analyst"] | None = None
    is_active: bool | None = None


@router.get("", response_model=list[UserRow])
async def list_users(_: AdminUser, db: DbSession) -> list[UserRow]:
    counts = dict((await db.execute(select(SearchJob.user_id, func.count(SearchJob.id)).group_by(SearchJob.user_id))).all())
    rows = (await db.scalars(select(User).order_by(User.created_at, User.id))).all()
    return [UserRow.model_validate(u).model_copy(update={"searches": counts.get(u.id, 0)}) for u in rows]


@router.patch("/{user_id}", response_model=UserRow)
async def update_user(user_id: int, data: UserPatch, _: AdminUser, db: DbSession) -> UserRow:
    user = await db.get(User, user_id)
    if user is None:
        raise api_error(404, "user_not_found")
    demote = data.role == "analyst" and user.role == "admin"
    deactivate = data.is_active is False and user.is_active and user.role == "admin"
    if demote or deactivate:
        admins = await db.scalar(select(func.count(User.id)).where(User.role == "admin", User.is_active)) or 0
        if admins <= 1:
            raise api_error(409, "last_admin")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    await db.commit()
    await db.refresh(user)
    n = await db.scalar(select(func.count(SearchJob.id)).where(SearchJob.user_id == user.id)) or 0
    return UserRow.model_validate(user).model_copy(update={"searches": n})
