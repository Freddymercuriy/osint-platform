from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NotificationState(Base):
    """Foydalanuvchi ogohlantirishlarni oxirgi marta qachon "o'qildi" qilgani.

    `first_seen > seen_at` bo'lgan (notify kategoriyalardagi) hodisalar — o'qilmagan.
    """

    __tablename__ = "notification_state"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
