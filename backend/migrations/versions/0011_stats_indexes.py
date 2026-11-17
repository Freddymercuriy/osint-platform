"""Statistika so'rovlari uchun indekslar: hodisa vaqti (coalesce), jiddiylik, kanal, scope

Revision ID: 0011_stats_indexes
Revises: 0010_admin_alerts
Create Date: 2026-11-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_stats_indexes"
down_revision: str | None = "0010_admin_alerts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_events_when", "events", [sa.text("coalesce(published, first_seen)")])
    op.create_index("ix_events_severity", "events", ["severity"])
    op.create_index("ix_events_channel", "events", ["channel"])
    op.create_index("ix_events_scope_when", "events", ["scope", sa.text("coalesce(published, first_seen)")])


def downgrade() -> None:
    for name in ("ix_events_scope_when", "ix_events_channel", "ix_events_severity", "ix_events_when"):
        op.drop_index(name, "events")
