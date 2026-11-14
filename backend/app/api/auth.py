from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas import Token, UserCreate, UserOut, UserUpdate
from app.services.admin_roles import role_for_new_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthConfig(BaseModel):
    registration_open: bool


@router.get("/config", response_model=AuthConfig)
async def auth_config() -> AuthConfig:
    """Login/ro'yxatdan o'tish sahifalari uchun ochiq sozlamalar."""
    return AuthConfig(registration_open=settings.registration_allowed)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate, db: DbSession) -> User:
    if not settings.registration_allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ro'yxatdan o'tish yopiq")
    exists = await db.scalar(select(User).where(func.lower(User.email) == data.email.lower()))
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu email allaqachon ro'yxatdan o'tgan")
    users_before = await db.scalar(select(func.count(User.id))) or 0
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        role=role_for_new_user(data.email, users_before),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    # OAuth2 formasi 'username' maydonini ishlatadi — bu yerda email
    user = await db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email yoki parol noto'g'ri")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Akkaunt o'chirilgan")
    token = create_access_token(subject=str(user.id))
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> User:
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserUpdate, current_user: CurrentUser, db: DbSession) -> User:
    """Foydalanuvchining o'z sozlamalari (hozircha interfeys tili)."""
    if "locale" in data.model_fields_set:
        current_user.locale = data.locale
    await db.commit()
    await db.refresh(current_user)
    return current_user
