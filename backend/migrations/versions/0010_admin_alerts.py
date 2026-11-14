"""admin_alerts: adminlar uchun tizim ogohlantirishlari (uzoq vaqt ishlamayotgan manba)

Revision ID: 0010_admin_alerts
Revises: 0009_translations
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0010_admin_alerts"
down_revision: str | None = "0009_translations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_alerts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=True),
        sa.Column("data", pg.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_admin_alerts_open", "admin_alerts", ["kind", "source_id", "resolved_at"])


def downgrade() -> None:
    op.drop_table("admin_alerts")
