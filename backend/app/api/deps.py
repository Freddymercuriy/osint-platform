from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.errors import api_error
from app.core.security import decode_access_token
from app.models import User

class _Bearer(OAuth2PasswordBearer):
    """Token yo'q bo'lsa FastAPI'ning inglizcha 401 o'rniga kodli xato ("not_authenticated")."""

    async def __call__(self, request: Request) -> str:  # type: ignore[override]
        token = await super().__call__(request)
        if not token:
            raise api_error(status.HTTP_401_UNAUTHORIZED, "not_authenticated", headers={"WWW-Authenticate": "Bearer"})
        return token


oauth2_scheme = _Bearer(tokenUrl="/api/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> User:
    credentials_exc = api_error(
        status.HTTP_401_UNAUTHORIZED, "invalid_token", headers={"WWW-Authenticate": "Bearer"}
    )
    subject = decode_access_token(token)
    if subject is None or not str(subject).isdigit():
        raise credentials_exc
    user = await db.scalar(select(User).where(User.id == int(subject)))
    if user is None or not user.is_active:
        raise credentials_exc
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(current_user: CurrentUser) -> User:
    """Faqat admin: /api/admin/*, manual yig'ish, Telegram akkaunt ma'lumotlari."""
    if current_user.role != "admin":
        raise api_error(status.HTTP_403_FORBIDDEN, "admin_only")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
