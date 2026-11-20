from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

SOURCE_STATUSES = ("ok", "degraded", "down", "blocked", "auth_missing", "disabled", "never_run")
SCOPES = ("regional", "global")
CHANNELS = ("news", "telegram_channel", "telegram_group", "api", "forum")


class Source(Base):
    """Events manbasi (runtime'dagi yagona haqiqat manbai — kodda manbalar ro'yxati yo'q).

    `config` — ulagich sozlamalari: {"url": ...} | {"query": ...} | {"countries": [...]} | {"chat": ...}.
    `api_key_env` — kalit saqlanadigan muhit o'zgaruvchisining NOMI (kalitning o'zi bazaga yozilmaydi).
    `state` — ulagichning kursor/kesh holati (masalan oxirgi ko'rilgan ID), restartdan keyin ham saqlanadi.
    """

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("scope in ('regional', 'global')", name="ck_sources_scope"),
        CheckConstraint(
            "status in ('ok', 'degraded', 'down', 'blocked', 'auth_missing', 'disabled', 'never_run')",
            name="ck_sources_status",
        ),
        CheckConstraint("interval_seconds >= 60", name="ck_sources_interval"),
        CheckConstraint("jitter_pct between 0 and 90", name="ck_sources_jitter"),
        Index("ix_sources_due", "enabled", "next_run_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    lang: Mapped[str] = mapped_column(String(8), default="en", server_default="en", nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String(16), default="regional", server_default="regional", nullable=False)
    region_filter: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    cyber_filter: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    translate: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    interval_seconds: Mapped[int] = mapped_column(Integer, default=900, server_default="900", nullable=False)
    jitter_pct: Mapped[int] = mapped_column(Integer, default=20, server_default="20", nullable=False)
    backfill_days: Mapped[int] = mapped_column(Integer, default=14, server_default="14", nullable=False)
    api_key_env: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="", nullable=False)
    # Ishonchlilik (ustuvorlik va postdagi "Ishonchlilik" satri): official | tracker | media | community | underground
    reliability: Mapped[str] = mapped_column(String(12), default="media", server_default="media", nullable=False)

    # HTTP kesh va jadval
    etag: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    baseline_done: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    # Sog'liq
    status: Mapped[str] = mapped_column(String(16), default="never_run", server_default="never_run", nullable=False)
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_new_items: Mapped[int | None] = mapped_column(Integer, nullable=True)
    newest_item_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    down_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Oxirgi urinish natijasi (ok / not_modified / blocked / rate_limited / error ...) va oxirgi xatoda sayt so'ragan
    # kutish (Retry-After / FloodWait, soniya) — admin panelda "nega va qancha kutyapti" ko'rinsin
    last_outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SourceRun(Base):
    """Bitta yig'ish urinishi (30 kun saqlanadi)."""

    __tablename__ = "source_runs"
    __table_args__ = (Index("ix_source_runs_source_started", "source_id", "started_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)  # ok | not_modified | blocked | ...
    items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    new_items: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)  # sayt so'ragan kutish
    wait_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)  # keyingi urinishgacha rejalashtirilgan
