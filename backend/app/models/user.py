from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


ROLES = ("admin", "analyst")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role in ('admin', 'analyst')", name="ck_users_role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # admin — manbalar, kategoriyalar, yig'uvchi, Telegram; analyst — ko'rish va tekshiruvlar
    role: Mapped[str] = mapped_column(String(16), default="analyst", server_default="analyst", nullable=False)
    locale: Mapped[str | None] = mapped_column(String(8), nullable=True)  # uz | ru | en; None = brauzer
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
