from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

TRANSLATION_STATUSES = ("done", "pending", "failed", "skipped")
PROVIDERS = ("source", "template", "translit", "google", "cache", "none")


class EventTranslation(Base):
    """Hodisaning bir tildagi matni (en / ru / uz). Asl tildagi qator — nusxa (`provider = source`).

    status: done | pending (navbatda) | failed (urinishlar tugadi) | skipped (manba tarjimaga ruxsat bermagan).
    """

    __tablename__ = "event_translations"
    __table_args__ = (UniqueConstraint("event_id", "lang", name="uq_event_translations_event_lang"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    lang: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(16), default="none", server_default="none", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", nullable=False,
                                        index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    translated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TranslationCache(Base):
    """Bir xil matn ikki marta pullik tarjimaga yuborilmaydi: kalit = sha256(manba til | maqsad til | matn)."""

    __tablename__ = "translation_cache"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_lang: Mapped[str] = mapped_column(String(8), nullable=False)
    target_lang: Mapped[str] = mapped_column(String(8), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chars: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TranslationUsage(Base):
    """Oylik hisob: tarjima xizmatiga yuborilgan belgilar (narx nazorati)."""

    __tablename__ = "translation_usage"

    month: Mapped[date] = mapped_column(Date, primary_key=True)  # oyning 1-kuni
    chars: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0", nullable=False)
    requests: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
