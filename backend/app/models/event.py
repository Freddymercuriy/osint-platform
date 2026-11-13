from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EventRecord(Base):
    """Fon yig'uvchi topgan bitta hodisa (yangilik / TG post / ransomware / leak).

    Faqat metadata va qisqa parcha saqlanadi — leak'ning o'zi (dump, PII) saqlanmaydi.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # takrorni oldini olish
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    lang: Mapped[str] = mapped_column(String(8), default="uz", nullable=False)
    published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
