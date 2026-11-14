"""baseline: v1 sxemasi (create_all yaratgan jadvallar, 2026-11-14 holati)

Mavjud bazalar bu reviziyaga `stamp` qilinadi (scripts/migrate.py avtomatik), yangi bazada jadvallar
shu yerda yaratiladi.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

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

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("uid", sa.String(64), nullable=False),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("url", sa.String(1024), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("lang", sa.String(8), nullable=False),
        sa.Column("published", _TS, nullable=True),
        sa.Column("first_seen", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_events_uid", "events", ["uid"], unique=True)
    op.create_index("ix_events_category", "events", ["category"])
    op.create_index("ix_events_published", "events", ["published"])
    op.create_index("ix_events_first_seen", "events", ["first_seen"])

    op.create_table(
        "notification_state",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("seen_at", _TS, nullable=True),
    )

    op.create_table(
        "tg_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tg_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("usernames", sa.String(512), nullable=False),
        sa.Column("first_seen", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_tg_observations_tg_id", "tg_observations", ["tg_id"])


def downgrade() -> None:
    for table in ("tg_observations", "notification_state", "events", "results", "search_jobs", "users"):
        op.drop_table(table)
