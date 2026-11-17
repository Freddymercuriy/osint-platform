"""Kelajak sanali hodisalar: `published` yig'ish vaqti (`first_seen`) bilan cheklanadi

Ba'zi manbalar ertangi sanani beradi (masalan, The Record RSS: `pubDate` 18-noyabr, yig'ilgani 17-noyabr) — bunday
yozuv sanasi kelguncha lenta tepasida turib qoladi. Yangi yozuvlarni `pipeline.store_items` cheklaydi; bu migratsiya
mavjudlarini tuzatadi. Asl sana `extra.published_original` da saqlanadi (downgrade uni qaytaradi).

Revision ID: 0015_cap_future_published
Revises: 0014_international_cyber_global
Create Date: 2026-11-17
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_cap_future_published"
down_revision: str | None = "0014_international_cyber_global"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "update events set "
        "extra = coalesce(extra, '{}'::jsonb) || jsonb_build_object('published_original', "
        "to_char(published at time zone 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"+00:00\"')), "
        "published = first_seen "
        "where published > first_seen"
    ))


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "update events set published = cast(extra->>'published_original' as timestamptz), "
        "extra = extra - 'published_original' "
        "where extra ? 'published_original'"
    ))
