"""Tekshiruvlar bo'limi olib tashlandi — qidiruv jadvallari o'chiriladi

OSINT tekshiruv modullari (username / email / telefon / domen) butunlay olib tashlandi
(egasi talabi, 2026-11-24). Ularning saqlangan tarixi `search_jobs` va `results`
jadvallarida edi — ikkalasi ham tashlanadi. Downgrade jadvallarni bo'sh holda qayta
yaratadi (ma'lumot qaytmaydi; migratsiyadan oldingi to'liq nusxa pg_dump'da).

Revision ID: 0027_remove_checks
Revises: 0026_daryo_blocked_feeds
Create Date: 2026-11-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_remove_checks"
down_revision: str | None = "0026_daryo_blocked_feeds"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.drop_index("ix_results_job_id", table_name="results")
    op.drop_table("results")
    op.drop_index("ix_search_jobs_user_id", table_name="search_jobs")
    op.drop_table("search_jobs")


def downgrade() -> None:
    op.create_table(
        "search_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("query", sa.String(256), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_search_jobs_user_id", "search_jobs", ["user_id"])

    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("url", sa.String(1024), nullable=True),
        sa.Column("detail", sa.String(512), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_results_job_id", "results", ["job_id"])
