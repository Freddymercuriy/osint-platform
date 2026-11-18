"""Rahbariyat Telegram kanali: kuzatuv ro'yxati va publisher sozlamalari (ustuvorlik og'irliklari)."""

from datetime import datetime, time

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
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


# ---------------------------------------------------------------- nashr (Bosqich 2)
LANGS = ("uz", "uz-Cyrl", "ru", "en")
MODES = ("dry_run", "review", "auto")
QUIET_POLICIES = ("uz_sound", "all_silent", "hold")  # sokin soatlarda: faqat UZ kritik ovozli | hamma kritik ovozsiz | hech biri
POST_KINDS = ("alert", "group", "daily", "weekly", "update", "correction", "test")
POST_STATUSES = ("waiting_translation", "draft", "awaiting_approval", "queued", "sending", "sent", "failed",
                 "skipped", "rejected", "expired", "unknown")
OPEN_STATUSES = ("waiting_translation", "draft", "awaiting_approval", "queued", "sending")
COUNTRIES = ("UZ", "KZ", "KG", "TJ", "TM")


class ChannelDestination(Base):
    """Bot post qiladigan Telegram chat (rahbariyat kanali). Har yangi kanal `dry_run` da boshlanadi."""

    __tablename__ = "channel_destinations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    chat_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_type: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chat_username: Mapped[str | None] = mapped_column(String(64), nullable=True)  # bor — ochiq kanal
    topic_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lang: Mapped[str] = mapped_column(String(8), default="uz", server_default="uz", nullable=False)
    mode: Mapped[str] = mapped_column(String(8), default="dry_run", server_default="dry_run", nullable=False)
    is_test: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    countries: Mapped[list[str]] = mapped_column(ARRAY(String(2)), default=lambda: list(COUNTRIES),
                                                 server_default=text("'{UZ,KZ,KG,TJ,TM}'"), nullable=False)
    include_global: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String(48)), default=list, server_default=text("'{}'"),
                                                  nullable=False)  # bo'sh — hammasi
    instant_min_band: Mapped[str] = mapped_column(String(8), default="critical", server_default="critical",
                                                  nullable=False)
    brief_min_band: Mapped[str] = mapped_column(String(8), default="medium", server_default="medium", nullable=False)
    daily_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    daily_time: Mapped[time] = mapped_column(Time, default=time(8, 30), server_default=text("'08:30'"), nullable=False)
    daily_weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), default=lambda: [1, 2, 3, 4, 5],
                                                      server_default=text("'{1,2,3,4,5}'"), nullable=False)
    weekly_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    weekly_day: Mapped[int] = mapped_column(SmallInteger, default=1, server_default="1", nullable=False)  # ISO: 1 = Du
    weekly_time: Mapped[time] = mapped_column(Time, default=time(8, 45), server_default=text("'08:45'"),
                                              nullable=False)
    quiet_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    quiet_start: Mapped[time] = mapped_column(Time, default=time(22, 0), server_default=text("'22:00'"),
                                              nullable=False)
    quiet_end: Mapped[time] = mapped_column(Time, default=time(7, 0), server_default=text("'07:00'"), nullable=False)
    quiet_policy: Mapped[str] = mapped_column(String(16), default="uz_sound", server_default="uz_sound",
                                              nullable=False)
    max_instant_per_day: Mapped[int] = mapped_column(SmallInteger, default=6, server_default="6", nullable=False)
    protect_content: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    show_original: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    explain_terms: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    # true — post faqat kanal tilida: tarjima tayyor bo'lmaguncha kutadi, asl matn yuborilmaydi (0022)
    require_translation: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false",
                                                      nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                        nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="unknown", server_default="unknown", nullable=False)
    down_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    rights: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    rights_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def is_public(self) -> bool:
        return bool(self.chat_username)


class ChannelPost(Base):
    """Outbox va audit: rahbariyatga nima, qachon, kim tasdig'i bilan aytilgani. Kamida 1 yil saqlanadi."""

    __tablename__ = "channel_posts"
    __table_args__ = (
        UniqueConstraint("destination_id", "dedup_key", name="uq_channel_posts_destination_dedup"),
        Index("ix_channel_posts_status_next", "status", "next_attempt_at"),
        Index("ix_channel_posts_destination_created", "destination_id", "created_at"),
        Index("ix_channel_posts_event_ids", "event_ids", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey("channel_destinations.id", ondelete="CASCADE"),
                                                nullable=False)
    kind: Mapped[str] = mapped_column(String(12), nullable=False)
    event_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, server_default=text("'{}'"),
                                                 nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", server_default="draft", nullable=False)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    edited_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    buttons: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    silent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    reply_to_post_id: Mapped[int | None] = mapped_column(ForeignKey("channel_posts.id", ondelete="SET NULL"),
                                                         nullable=True)
    priority: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # token yashirilgan (`bot.redact`)
    skip_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"),
                                                            nullable=True)
    approved_by_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approved_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    review_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    band_at_send: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sources_at_send: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def final_text(self) -> str:
        return self.edited_text if self.edited_text is not None else self.text


class BotChat(Base):
    """Bot qo'shilgan yoki unga yozgan chat (`my_chat_member`, `/start`) va botning undagi holati / huquqlari."""

    __tablename__ = "bot_chats"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rights: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    added_by_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    added_by_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                    nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Reviewer(Base):
    """Postlarni Telegram'da tasdiqlashga ruxsat etilgan foydalanuvchi (platforma foydalanuvchisiga bog'lanishi mumkin)."""

    __tablename__ = "reviewers"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class PublisherState(Base):
    """Bitta qator (id = 1): getUpdates offset, umumiy pauza, tekshiruv chati, bot holati."""

    __tablename__ = "publisher_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_publisher_state_single"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    updates_offset: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    paused_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bot_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bot_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bot_status: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown", nullable=False)
    bot_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_poll_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
