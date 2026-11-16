"""NewsNow manbasi: Cyber Attacks mavzu sahifasi (`newsnow` ulagichi)

O'chiq qo'shiladi — admin panelda yoqiladi. NewsNow robots.txt'da AI botlarini to'sgan va foydalanish shartlari
avtomatik yig'ishni cheklashi mumkin; yoqish — platforma egasining qarori. Global kiber yangiliklar: scope
`global` (Events standart ko'rinishi — regional — toza qoladi), faqat kiber mavzu filtri.

Revision ID: 0012_newsnow_source
Revises: 0011_stats_indexes
Create Date: 2026-11-16
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_newsnow_source"
down_revision: str | None = "0011_stats_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "NewsNow: Cyber Attacks"
CONFIG = {"url": "https://www.newsnow.com/us/Tech/Cyber+Security/Cyber+Attacks"}
NOTES = ("Faqat mavzu sahifasining birinchi sahifasi (robots.txt: ?p= va /A/ yopiq). Havolalar NewsNow orqali "
         "(c.newsnow.com/A/...) — platforma ularga kirmaydi. Faqat Markaziy Osiyo kerak bo'lsa: hudud filtrini yoqing.")


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "insert into sources (name, kind, config, lang, scope, region_filter, cyber_filter, translate, "
        "interval_seconds, jitter_pct, backfill_days, enabled, status, notes) values (:name, 'newsnow', "
        "cast(:config as jsonb), 'en', 'global', false, true, true, 1800, 20, 7, false, 'disabled', :notes) "
        "on conflict (name) do nothing"
    ), {"name": NAME, "config": json.dumps(CONFIG), "notes": NOTES})


def downgrade() -> None:
    op.get_bind().execute(sa.text("delete from sources where name = :name and kind = 'newsnow'"), {"name": NAME})
