"""Bloklash / rate limit ko'rinishi: oxirgi urinish natijasi, sayt so'ragan kutish (Retry-After), tanlangan kutish

sources: `last_outcome` (ok / blocked / rate_limited / ...), `retry_after_seconds` (oxirgi xatoda sayt so'ragan kutish).
source_runs: `retry_after_seconds`, `wait_seconds` (shu urinishdan keyin keyingisigacha rejalashtirilgan kutish).

Revision ID: 0013_source_wait_info
Revises: 0012_newsnow_source
Create Date: 2026-11-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_source_wait_info"
down_revision: str | None = "0012_newsnow_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("last_outcome", sa.String(16), nullable=True))
    op.add_column("sources", sa.Column("retry_after_seconds", sa.Integer(), nullable=True))
    op.add_column("source_runs", sa.Column("retry_after_seconds", sa.Integer(), nullable=True))
    op.add_column("source_runs", sa.Column("wait_seconds", sa.Integer(), nullable=True))
    # Mavjud manbalar: oxirgi urinish natijasi tarixdan
    op.execute(
        "update sources s set last_outcome = r.outcome from (select distinct on (source_id) source_id, outcome "
        "from source_runs order by source_id, started_at desc) r where r.source_id = s.id"
    )


def downgrade() -> None:
    op.drop_column("source_runs", "wait_seconds")
    op.drop_column("source_runs", "retry_after_seconds")
    op.drop_column("sources", "retry_after_seconds")
    op.drop_column("sources", "last_outcome")
