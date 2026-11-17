"""Tarjimalar: event_translations, translation_cache, translation_usage

Mavjud hodisalar uchun qatorlar ilova tomonidan yaratiladi (`services/i18n/worker.ensure_rows`, fon yig'uvchi har
tsiklda) — til aniqlash va shablonlar kodda.

Revision ID: 0009_translations
Revises: 0008_category_rules
Create Date: 2026-11-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_translations"
down_revision: str | None = "0008_category_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "event_translations",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("lang", sa.String(8), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(16), server_default="none", nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", _TS, nullable=True),
        sa.Column("translated_at", _TS, nullable=True),
        sa.UniqueConstraint("event_id", "lang", name="uq_event_translations_event_lang"),
    )
    op.create_index("ix_event_translations_event_id", "event_translations", ["event_id"])
    op.create_index("ix_event_translations_status", "event_translations", ["status"])
    op.create_table(
        "translation_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("source_lang", sa.String(8), nullable=False),
        sa.Column("target_lang", sa.String(8), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("chars", sa.Integer(), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "translation_usage",
        sa.Column("month", sa.Date(), primary_key=True),
        sa.Column("chars", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("requests", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("translation_usage")
    op.drop_table("translation_cache")
    op.drop_table("event_translations")
