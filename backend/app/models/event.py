from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class EventRecord(Base):
    """Fon yig'uvchi topgan bitta hodisa.

    Faqat metadata va qisqa parcha saqlanadi — leak'ning o'zi (dump, PII, credential) saqlanmaydi.

    - `category` — kategoriya slug'i (denormalizatsiya; `category_id` bilan bir xil saqlanadi, slug o'zgarmaydi).
    - `channel` — qayerdan kelgani: news | telegram_channel | telegram_group | api.
    - `source` — manba nomi (manba o'chirilsa ham qoladi), `source_id` — manba yozuvi (SET NULL).
    - `also_reported_by` — shu voqeani yana xabar qilgan manbalar: [{"source": ..., "url": ..., "at": ...}].
    - `is_baseline` — manbaning birinchi (baseline) yig'ishidan: ogohlantirish bermaydi, "o'qilmagan" hisoblanmaydi.
    """

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_countries", "countries", postgresql_using="gin"),
        Index("ix_events_category_id", "category_id"),
        Index("ix_events_source_id", "source_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # takrorni oldini olish
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(48), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    lang: Mapped[str] = mapped_column(String(8), default="uz", nullable=False)
    published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # v2
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    category_locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    channel: Mapped[str] = mapped_column(String(24), default="news", server_default="news", nullable=False)
    scope: Mapped[str] = mapped_column(String(16), default="regional", server_default="regional", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info", server_default="info", nullable=False)
    countries: Mapped[list[str]] = mapped_column(
        ARRAY(String(2)), default=list, server_default=text("'{}'"), nullable=False
    )
    sector: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(128), nullable=True)
    matched_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'"), nullable=False
    )
    extra: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    also_reported_by: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    @property
    def event_time(self) -> datetime:
        return self.published or self.first_seen
