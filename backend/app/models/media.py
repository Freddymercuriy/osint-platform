from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

IMAGE_KINDS = ("source", "generated", "fallback")


class EventImage(Base):
    """Hodisaning 16:9 rasmi (fayl — `MEDIA_DIR`, bu yerda meta). Bitta hodisa — bitta qator.

    kind: source (maqolaning o'z rasmi: og:image / RSS media) | generated (platforma chizgan illyustratsiya) |
    fallback (illyustratsiya chizilmadi — rubrika zaxira rasmi). `source_checked` — maqola rasmi qidirilganmi
    (false — fon ishchisi keyinroq qidiradi, topilsa illyustratsiyani almashtiradi). `version` — fayl mazmuni
    xeshi: URL'da (kesh yangilanadi).
    """

    __tablename__ = "event_images"
    __table_args__ = (CheckConstraint("kind in ('source', 'generated', 'fallback')", name="ck_event_images_kind"),)

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    rubric: Mapped[str | None] = mapped_column(String(16), nullable=True)
    motif: Mapped[str | None] = mapped_column(String(24), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    source_checked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)
