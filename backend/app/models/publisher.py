"""Rahbariyat Telegram kanali: kuzatuv ro'yxati va publisher sozlamalari (ustuvorlik og'irliklari)."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

WATCH_KINDS = ("organisation", "domain", "brand", "product", "person")
RELIABILITY = ("official", "tracker", "media", "community", "underground")
BANDS = ("low", "medium", "high", "critical")
BAND_RANK = {b: i for i, b in enumerate(BANDS)}


class WatchlistEntry(Base):
    """Kuzatiladigan nom: tashkilot, domen, brend, mahsulot yoki shaxs (faqat tashkilotning o'z rahbarlari).

    `aliases` — lotin va kirill yozilishlari; o'zbekcha lotin ↔ kirill varianti avtomatik qo'shiladi (moslashda).
    """

    __tablename__ = "watchlist"
    __table_args__ = (
        CheckConstraint("kind in ('organisation', 'domain', 'brand', 'product', 'person')", name="ck_watchlist_kind"),
        UniqueConstraint("kind", "name", name="uq_watchlist_kind_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default=text("'{}'"), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PublisherSettings(Base):
    """Bitta qator (id = 1): ustuvorlik og'irliklari va band chegaralari (`services/publisher/priority.py`)."""

    __tablename__ = "publisher_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_publisher_settings_single"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    bands: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
